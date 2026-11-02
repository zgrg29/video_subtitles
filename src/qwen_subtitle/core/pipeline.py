"""End-to-end subtitle generation pipeline.

Stages exposed to the UI: ``asr`` -> ``translate`` -> ``write``.  When the
content mode is ``original``, the translation stage makes no network request at
all and is marked as skipped.
"""

from __future__ import annotations

import math
import re
import shutil
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from qwen_subtitle.constants import (
    ASR_MODEL_BY_KEY,
    OUTPUT_MODE_BY_KEY,
    REGION_BY_KEY,
    SOURCE_LANGUAGE_BY_CODE,
    SUBTITLE_FORMAT_BY_KEY,
    TARGET_LANGUAGE_BY_CODE,
    TRANSLATION_BATCH_SIZE,
    TRANSLATION_MODEL_BY_KEY,
)
from qwen_subtitle.core.config import create_work_dir, default_cache_dir
from qwen_subtitle.core.dashscope import QwenClient, parse_transcription_payload
from qwen_subtitle.core.errors import ApiError, AppError, CancelledError, MediaError
from qwen_subtitle.core.ffmpeg import (
    extract_audio,
    format_duration,
    probe_media,
    resolve_ffmpeg,
)
from qwen_subtitle.core.subtitle import (
    Cue,
    cues_from_sentences,
    split_oversized_cues,
    write_subtitle,
)
from qwen_subtitle.i18n import tr

ProgressCallback = Callable[[str, int, str], None]


@dataclass(frozen=True)
class PipelineOptions:
    video_path: Path
    region: str
    api_key: str
    asr_model: str
    translation_model: str
    source_language: str
    target_language: str
    output_mode: str
    subtitle_format: str
    output_dir: Path | None = None
    ffmpeg_path: str = ""


@dataclass(frozen=True)
class PipelineResult:
    output_paths: tuple[Path, ...]
    cue_count: int
    duration_ms: int
    output_mode: str
    subtitle_format: str
    fallback_used: bool = False

    @property
    def output_path(self) -> Path:
        """First output path, kept for callers/tests that expect one file."""

        return self.output_paths[0]


def _unique_output_path(video: Path, suffix: str, output_dir: Path | None) -> Path:
    folder = output_dir if output_dir else video.parent
    folder.mkdir(parents=True, exist_ok=True)
    # ``suffix`` already contains the language tag and extension.
    name = f"{video.stem}.{suffix}"
    candidate = folder / name
    if not candidate.exists():
        return candidate
    stem = candidate.stem
    extension = candidate.suffix
    index = 2
    while True:
        alternate = folder / f"{stem} ({index}){extension}"
        if not alternate.exists():
            return alternate
        index += 1


class SubtitlePipeline:
    def __init__(
        self,
        options: PipelineOptions,
        *,
        progress: ProgressCallback | None = None,
        cancel_event: threading.Event | None = None,
    ) -> None:
        self.options = options
        self._progress = progress or (lambda stage, percent, message: None)
        self.cancel_event = cancel_event or threading.Event()

    def _emit(self, stage: str, percent: int, message: str) -> None:
        if self.cancel_event.is_set():
            raise CancelledError()
        self._progress(stage, max(0, min(100, percent)), message)

    def _check_cancelled(self) -> None:
        if self.cancel_event.is_set():
            raise CancelledError()

    def run(self) -> PipelineResult:
        options = self.options
        video = Path(options.video_path)
        if not video.is_file():
            raise AppError(tr("error.file_missing"))
        if options.region not in REGION_BY_KEY:
            raise AppError(tr("error.api"))
        if options.asr_model not in ASR_MODEL_BY_KEY:
            raise AppError(tr("error.model_mismatch"))
        if options.output_mode not in OUTPUT_MODE_BY_KEY:
            raise AppError(tr("error.output"))
        if options.subtitle_format not in SUBTITLE_FORMAT_BY_KEY:
            raise AppError(tr("error.output"))

        asr_model = ASR_MODEL_BY_KEY[options.asr_model]
        fmt = SUBTITLE_FORMAT_BY_KEY[options.subtitle_format]
        mode = OUTPUT_MODE_BY_KEY[options.output_mode]
        needs_translation = mode.key in ("translated", "bilingual")
        if needs_translation and options.translation_model not in TRANSLATION_MODEL_BY_KEY:
            raise AppError(tr("error.model_mismatch"))

        source = SOURCE_LANGUAGE_BY_CODE.get(options.source_language)
        target = TARGET_LANGUAGE_BY_CODE.get(options.target_language)
        if source is None or target is None:
            raise AppError(tr("error.model_mismatch"))
        if needs_translation and source.code != "auto" and source.code == target.code:
            raise AppError(tr("error.same_language"))

        ffmpeg = resolve_ffmpeg(options.ffmpeg_path)
        self._emit("asr", 2, tr("progress.extracting"))
        media = probe_media(ffmpeg.ffmpeg, video)
        if not media.has_audio:
            raise MediaError(tr("video.no_audio"))
        region = REGION_BY_KEY[options.region]
        client = QwenClient(region.base_url, options.api_key)

        try:
            work_dir = create_work_dir("job-")
        except OSError as exc:
            raise AppError(tr("error.cache")) from exc
        try:
            temp = work_dir

            audio_path = extract_audio(
                ffmpeg.ffmpeg,
                video,
                temp / "audio.mp3",
                media.duration_ms,
                on_progress=lambda value: self._emit(
                    "asr",
                    2 + int(max(0, min(100, value)) * 0.10),
                    tr("progress.extracting"),
                ),
                cancelled=self.cancel_event.is_set,
            )
            self._check_cancelled()
            self._emit("asr", 14, tr("progress.uploading"))
            uploaded = client.upload_audio(audio_path, asr_model.key, cancel_event=self.cancel_event)
            self._emit("asr", 27, tr("progress.uploaded"))
            task_id = client.submit_transcription(
                uploaded.url,
                model=asr_model.key,
                api_style=asr_model.api_style,
                language_param=asr_model.language_param,
                language_code=source.asr_code,
                cancel_event=self.cancel_event,
            )
            self._emit("asr", 34, tr("progress.asr_submitted"))

            poll_count = 0

            def on_status(_status: str) -> None:
                nonlocal poll_count
                poll_count += 1
                percent = min(56, 36 + poll_count * 2)
                self._emit("asr", percent, tr("progress.asr_polling"))

            task = client.wait_for_transcription(
                task_id,
                cancel_event=self.cancel_event,
                on_status=on_status,
            )
            self._check_cancelled()
            transcription_url = client.extract_transcription_url(task)
            payload = client.download_transcription(
                transcription_url,
                cancel_event=self.cancel_event,
            )
            sentences = parse_transcription_payload(payload)
            if not sentences:
                raise ApiError(tr("error.asr_empty"))
            cues = split_oversized_cues(
                cues_from_sentences(sentences, media.duration_ms),
                max_units=42,
            )
            if not cues:
                raise ApiError(tr("error.asr_empty"))
            self._emit("asr", 58, tr("progress.asr_done", count=len(cues)))

            if needs_translation:
                cues = self._translate(
                    client,
                    cues,
                    source_name=source.qwen_name,
                    target_name=target.qwen_name,
                    model=options.translation_model,
                )
            else:
                self._emit("translate", 58, tr("progress.translate_skipped"))

            self._check_cancelled()
            self._emit("write", 95, tr("progress.writing", format=fmt.label))
            output_specs = _output_specs(mode.key, target.code, fmt.extension)
            output_paths, fallback_used = self._write_with_fallback(
                video,
                cues,
                fmt.key,
                output_specs,
                options.output_dir,
            )
            self._emit("write", 100, tr("progress.complete"))
            return PipelineResult(
                output_paths=tuple(output_paths),
                cue_count=len(cues),
                duration_ms=media.duration_ms,
                output_mode=mode.key,
                subtitle_format=fmt.key,
                fallback_used=fallback_used,
            )
        finally:
            shutil.rmtree(work_dir, ignore_errors=True)

    def _translate(
        self,
        client: QwenClient,
        cues: list[Cue],
        *,
        source_name: str,
        target_name: str,
        model: str,
    ) -> list[Cue]:
        total_batches = max(1, math.ceil(len(cues) / TRANSLATION_BATCH_SIZE))
        translated: list[Cue] = []
        for batch_index in range(total_batches):
            self._check_cancelled()
            start = batch_index * TRANSLATION_BATCH_SIZE
            batch = cues[start : start + TRANSLATION_BATCH_SIZE]
            self._emit(
                "translate",
                60 + int(34 * batch_index / total_batches),
                tr("progress.translating", current=batch_index + 1, total=total_batches),
            )
            texts = self._translate_batch(
                client,
                [cue.text for cue in batch],
                source_name=source_name,
                target_name=target_name,
                model=model,
            )
            for cue, text in zip(batch, texts, strict=True):
                translated.append(cue.with_translation(text))
        self._emit("translate", 94, tr("progress.translated"))
        return translated

    def _translate_batch(
        self,
        client: QwenClient,
        texts: list[str],
        *,
        source_name: str,
        target_name: str,
        model: str,
    ) -> list[str]:
        if len(texts) == 1:
            return [
                client.translate(
                    texts[0],
                    model=model,
                    source_lang=source_name,
                    target_lang=target_name,
                    cancel_event=self.cancel_event,
                )
            ]
        joined = "\n\n".join(texts)
        result = client.translate(
            joined,
            model=model,
            source_lang=source_name,
            target_lang=target_name,
            cancel_event=self.cancel_event,
        )
        parts = [part.strip() for part in re.split(r"\n\s*\n", result) if part.strip()]
        if len(parts) == len(texts):
            return parts
        # The translation model may collapse blank lines.  Fall back to one
        # request per line so timing and alignment stay correct.
        output = []
        for text in texts:
            self._check_cancelled()
            output.append(
                client.translate(
                    text,
                    model=model,
                    source_lang=source_name,
                    target_lang=target_name,
                    cancel_event=self.cancel_event,
                )
            )
        return output

    def _write_with_fallback(
        self,
        video: Path,
        cues: list[Cue],
        format_key: str,
        output_specs: list[tuple[str, str]],
        output_dir: Path | None,
    ) -> tuple[list[Path], bool]:
        """Write all requested files, falling back to a writable folder.

        ``bilingual`` writes two independent files (original and translated),
        not one merged file.  Only filesystem failures trigger the fallback;
        content/rendering failures still surface as an error.
        """

        primary = output_dir if output_dir else video.parent
        fallbacks = _fallback_output_dirs()
        candidates: list[Path] = [primary]
        for candidate in fallbacks:
            if candidate != primary:
                candidates.append(candidate)

        last_error: OSError | None = None
        for folder in candidates:
            written: list[Path] = []
            try:
                for suffix, content_mode in output_specs:
                    path = _unique_output_path(video, suffix, folder)
                    write_subtitle(cues, format_key, path, content_mode)
                    written.append(path)
                return written, folder != primary
            except OSError as exc:
                last_error = exc
                for path in written:
                    path.unlink(missing_ok=True)
                continue
            except ValueError as exc:
                for path in written:
                    path.unlink(missing_ok=True)
                raise AppError(tr("error.output")) from exc
        raise AppError(tr("error.output")) from last_error


def _output_specs(mode: str, target_code: str, extension: str) -> list[tuple[str, str]]:
    """Return ``(filename suffix, content mode)`` for the selected output mode."""

    original = (f"original.{extension}", "original")
    translated = (f"{target_code}.{extension}", "translated")
    if mode == "original":
        return [original]
    if mode == "translated":
        return [translated]
    return [original, translated]


def _fallback_output_dirs() -> list[Path]:
    home = Path.home()
    return [
        home / "Desktop",
        home / "OneDrive" / "Desktop",
        home / "Documents",
        home / "Videos",
        home,
        default_cache_dir() / "outputs",
    ]


def describe_media(duration_ms: int, width: int, height: int) -> str:
    resolution = f"{width}×{height}" if width and height else tr("video.no_resolution")
    return f"{format_duration(duration_ms)} · {resolution}"
