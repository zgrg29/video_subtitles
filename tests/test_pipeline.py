from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

import pytest

from qwen_subtitle.core.ffmpeg import MediaInfo
from qwen_subtitle.core.pipeline import (
    PipelineOptions,
    SubtitlePipeline,
    _output_specs,
    _unique_output_path,
)


def test_output_specs_use_separate_files_for_bilingual() -> None:
    assert _output_specs("original", "zh-Hans", "srt") == [("original.srt", "original")]
    assert _output_specs("translated", "en", "ass") == [("en.ass", "translated")]
    assert _output_specs("bilingual", "ja", "vtt") == [
        ("original.vtt", "original"),
        ("ja.vtt", "translated"),
    ]


def test_unique_output_path_puts_counter_before_extension(tmp_path: Path) -> None:
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"")
    first = _unique_output_path(video, "zh-Hans.srt", None)
    assert first.name == "demo.zh-Hans.srt"
    first.write_text("x", encoding="utf-8")
    second = _unique_output_path(video, "zh-Hans.srt", None)
    assert second.name == "demo.zh-Hans (2).srt"


class _FakeClient:
    def __init__(self, collapse: bool = False) -> None:
        self.calls: list[str] = []
        self.collapse = collapse
        self.translate_calls = 0

    def translate(self, text: str, **kwargs) -> str:
        self.calls.append(text)
        self.translate_calls += 1
        if self.collapse:
            return "single collapsed result"
        return "\n\n".join(f"T:{line}" for line in text.split("\n\n"))


def _options(tmp_path: Path, mode: str = "original") -> PipelineOptions:
    video = tmp_path / "demo.mp4"
    video.write_bytes(b"")
    return PipelineOptions(
        video_path=video,
        region="cn",
        api_key="sk-test",
        asr_model="qwen-audio-3.1-asr-flash-filetrans",
        translation_model="qwen-mt-plus",
        source_language="zh",
        target_language="en",
        output_mode=mode,
        subtitle_format="srt",
        output_dir=tmp_path,
    )


def test_translate_batch_preserves_alignment(tmp_path: Path) -> None:
    pipeline = SubtitlePipeline(_options(tmp_path))
    client = _FakeClient()
    result = pipeline._translate_batch(
        client,
        ["你好", "世界"],
        source_name="Chinese",
        target_name="English",
        model="qwen-mt-plus",
    )
    assert result == ["T:你好", "T:世界"]
    assert len(client.calls) == 1


def test_translate_batch_falls_back_when_line_count_changes(tmp_path: Path) -> None:
    pipeline = SubtitlePipeline(_options(tmp_path))
    client = _FakeClient(collapse=True)
    result = pipeline._translate_batch(
        client,
        ["你好", "世界"],
        source_name="Chinese",
        target_name="English",
        model="qwen-mt-plus",
    )
    assert result == ["single collapsed result", "single collapsed result"]
    assert len(client.calls) == 3


class _PipelineClient:
    instances: list["_PipelineClient"] = []

    def __init__(self, base_url: str, api_key: str) -> None:
        self.base_url = base_url
        self.api_key = api_key
        self.translate_calls = 0
        self.upload_calls = 0
        _PipelineClient.instances.append(self)

    def upload_audio(self, path, model, **kwargs):
        self.upload_calls += 1
        return SimpleNamespace(url="oss://demo/audio.mp3", bytes_sent=100)

    def submit_transcription(self, url, **kwargs):
        return "task-123"

    def wait_for_transcription(self, task_id, **kwargs):
        return {"output": {"task_status": "SUCCEEDED"}}

    @staticmethod
    def extract_transcription_url(body):
        return "https://dashscope-result.oss-cn-beijing.aliyuncs.com/result.json"

    def download_transcription(self, url, **kwargs):
        return {
            "transcripts": [
                {
                    "sentences": [
                        {"begin_time": 0, "end_time": 1200, "text": "你好。"},
                        {"begin_time": 1200, "end_time": 2400, "text": "世界。"},
                    ]
                }
            ]
        }

    def translate(self, text: str, **kwargs) -> str:
        self.translate_calls += 1
        return "\n\n".join(f"EN:{line}" for line in text.split("\n\n"))


@pytest.fixture()
def fake_pipeline(monkeypatch, tmp_path: Path):
    _PipelineClient.instances = []
    monkeypatch.setattr("qwen_subtitle.core.pipeline.QwenClient", _PipelineClient)
    monkeypatch.setattr(
        "qwen_subtitle.core.pipeline.resolve_ffmpeg",
        lambda preferred="": SimpleNamespace(ffmpeg="ffmpeg", source="test", version="test"),
    )
    monkeypatch.setattr(
        "qwen_subtitle.core.pipeline.probe_media",
        lambda ffmpeg, video: MediaInfo(
            path=video,
            duration_ms=4000,
            width=640,
            height=360,
            video_codec="h264",
            audio_codec="aac",
            size_bytes=100,
            has_audio=True,
        ),
    )
    monkeypatch.setattr(
        "qwen_subtitle.core.pipeline.extract_audio",
        lambda *args, **kwargs: tmp_path / "audio.mp3",
    )
    return tmp_path


def test_original_only_never_calls_translation(fake_pipeline: Path) -> None:
    pipeline = SubtitlePipeline(_options(fake_pipeline, "original"))
    result = pipeline.run()
    client = _PipelineClient.instances[-1]
    assert client.upload_calls == 1
    assert client.translate_calls == 0
    assert result.output_path.name == "demo.original.srt"
    assert "EN:" not in result.output_path.read_text(encoding="utf-8-sig")


def test_bilingual_mode_writes_two_separate_files(fake_pipeline: Path) -> None:
    pipeline = SubtitlePipeline(_options(fake_pipeline, "bilingual"))
    result = pipeline.run()
    client = _PipelineClient.instances[-1]
    assert client.translate_calls == 1
    assert len(result.output_paths) == 2
    original_path, translated_path = result.output_paths
    assert original_path.name == "demo.original.srt"
    assert translated_path.name == "demo.en.srt"
    original_content = original_path.read_text(encoding="utf-8-sig")
    translated_content = translated_path.read_text(encoding="utf-8-sig")
    assert "你好。" in original_content
    assert "EN:" not in original_content
    assert "EN:" in translated_content
    assert original_content != translated_content


def test_write_falls_back_when_primary_folder_is_not_writable(fake_pipeline: Path, monkeypatch) -> None:
    import qwen_subtitle.core.pipeline as pipeline_module

    original_write = pipeline_module.write_subtitle
    fallback = fake_pipeline / "fallback"
    calls: list[Path] = []

    def guarded_write(cues, format_key, path, mode):
        calls.append(Path(path))
        if Path(path).parent == fake_pipeline:
            raise OSError("simulated read-only folder")
        return original_write(cues, format_key, path, mode)

    monkeypatch.setattr(pipeline_module, "write_subtitle", guarded_write)
    monkeypatch.setattr(pipeline_module, "_fallback_output_dirs", lambda: [fallback])
    pipeline = SubtitlePipeline(_options(fake_pipeline, "original"))
    result = pipeline.run()
    assert result.fallback_used is True
    assert result.output_path.parent == fallback
    assert result.output_path.read_text(encoding="utf-8-sig").strip()
    assert len(calls) == 2
