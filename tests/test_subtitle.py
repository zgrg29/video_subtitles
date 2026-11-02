from __future__ import annotations

from pathlib import Path

from qwen_subtitle.core.subtitle import (
    Cue,
    cues_from_sentences,
    display_width,
    normalize_cues,
    parse_sentences,
    render_subtitle,
    split_oversized_cues,
    to_srt,
    wrap_subtitle,
    write_subtitle,
)


def sample_cues() -> list[Cue]:
    return [
        Cue(0, 1800, "这是一个测试句子。", "This is a test sentence."),
        Cue(1900, 3600, "第二句字幕。", "The second subtitle."),
    ]


def test_display_width_counts_cjk_as_two() -> None:
    assert display_width("中文") == 4
    assert display_width("abc") == 3
    assert display_width("A中") == 3


def test_srt_translated_and_bilingual() -> None:
    translated = to_srt(sample_cues(), "translated")
    assert "This is a test sentence." in translated
    assert "这是一个测试句子。" not in translated
    assert "00:00:00,000 --> 00:00:01,800" in translated
    bilingual = to_srt(sample_cues(), "bilingual")
    assert "这是一个测试句子。" in bilingual
    assert "This is a test sentence." in bilingual
    original = to_srt(sample_cues(), "original")
    assert "This is a test sentence." not in original


def test_ass_has_script_and_dialogue_lines() -> None:
    content = render_subtitle(sample_cues(), "ass", "bilingual")
    assert "[Script Info]" in content
    assert "Dialogue: 0,0:00:00.00,0:00:01.80" in content
    assert "\\N" in content


def test_vtt_has_header_and_dots() -> None:
    content = render_subtitle(sample_cues(), "vtt", "translated")
    assert content.startswith("WEBVTT")
    assert "00:00:00.000 --> 00:00:01.800" in content


def test_wrap_is_at_most_two_lines() -> None:
    text = "这是一个很长很长的字幕句子，" * 8
    wrapped = wrap_subtitle(text)
    assert len(wrapped.splitlines()) <= 2
    assert "".join(wrapped.splitlines()).replace(" ", "") == text.replace(" ", "")


def test_split_long_cue_preserves_text_and_order() -> None:
    cue = Cue(0, 8000, "这是一个需要被拆分的长句子，" * 8)
    split = split_oversized_cues([cue], max_units=42)
    assert len(split) > 1
    assert split[0].start_ms == 0
    assert split[-1].end_ms == 8000
    assert all(split[i].end_ms <= split[i + 1].start_ms for i in range(len(split) - 1))
    assert "".join(item.text for item in split).replace("，", "，") .startswith("这是一个")


def test_cues_from_qwen_sentences_repairs_timestamps() -> None:
    sentences = [
        {"begin_time": 100, "end_time": 900, "text": "你好。"},
        {"begin_time": 850, "end_time": 850, "text": "世界。"},
        {"begin_time": 5000, "end_time": 3000, "text": ""},
    ]
    cues = cues_from_sentences(sentences, audio_duration_ms=8000)
    assert len(cues) == 2
    assert cues[0].start_ms == 100
    assert cues[0].end_ms == 850
    assert cues[1].start_ms == 850
    assert cues[1].end_ms > cues[1].start_ms


def test_normalize_drops_out_of_range() -> None:
    cues = normalize_cues([Cue(9000, 9500, "超出"), Cue(-50, 1000, "有效")], 8000)
    assert len(cues) == 1
    assert cues[0].text == "有效"


def test_parse_sentences_supports_nested_shapes() -> None:
    assert parse_sentences({"transcripts": [{"sentences": [{"text": "a"}]}]}) == [{"text": "a"}]
    assert parse_sentences({"result": {"transcripts": [{"sentences": [{"text": "b"}]}]}}) == [{"text": "b"}]
    assert parse_sentences({"sentences": [{"text": "c"}]}) == [{"text": "c"}]


def test_write_subtitle_is_utf8_bom_and_atomic(tmp_path: Path) -> None:
    path = tmp_path / "demo.srt"
    write_subtitle(sample_cues(), "srt", path, "translated")
    raw = path.read_bytes()
    assert raw.startswith(b"\xef\xbb\xbf")
    assert b"This is a test sentence." in raw
    assert not list(tmp_path.glob(".subtitle-*"))
