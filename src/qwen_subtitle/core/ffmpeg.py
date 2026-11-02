"""FFmpeg discovery, media probing, audio extraction, and shell integration."""

from __future__ import annotations

import os
import re
import shutil
import subprocess
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Callable

from qwen_subtitle.core.errors import CancelledError, MediaError
from qwen_subtitle.i18n import tr

_CREATE_NO_WINDOW = 0x08000000 if os.name == "nt" else 0
_DURATION_RE = re.compile(r"Duration:\s*(\d+):(\d+):(\d+(?:\.\d+)?)")
_VIDEO_RE = re.compile(r"Video:\s*([^,\s]+).*?(\d{2,5})x(\d{2,5})")
_AUDIO_RE = re.compile(r"Audio:\s*([^,\s]+)")


@dataclass(frozen=True)
class FFmpegInfo:
    ffmpeg: str
    source: str
    version: str


@dataclass(frozen=True)
class MediaInfo:
    path: Path
    duration_ms: int
    width: int
    height: int
    video_codec: str
    audio_codec: str
    size_bytes: int
    has_audio: bool


def _candidate_from_path(value: str) -> str | None:
    candidate = Path(value).expanduser()
    if candidate.is_dir():
        candidate = candidate / ("ffmpeg.exe" if os.name == "nt" else "ffmpeg")
    if candidate.is_file():
        return str(candidate)
    return None


def resolve_ffmpeg(preferred: str = "") -> FFmpegInfo:
    """Find FFmpeg in this order: user choice, bundle, PATH, imageio-ffmpeg."""

    candidates: list[tuple[str, str]] = []
    if preferred.strip():
        chosen = _candidate_from_path(preferred.strip())
        if chosen:
            candidates.append((chosen, "manual"))
    bundled = Path(getattr(sys, "_MEIPASS", Path(__file__).resolve().parents[3])) / "bin"
    bundle_name = "ffmpeg.exe" if os.name == "nt" else "ffmpeg"
    if (bundled / bundle_name).is_file():
        candidates.append((str(bundled / bundle_name), "bundled"))
    on_path = shutil.which("ffmpeg")
    if on_path:
        candidates.append((on_path, "path"))
    try:
        import imageio_ffmpeg

        candidates.append((imageio_ffmpeg.get_ffmpeg_exe(), "runtime"))
    except Exception:
        pass

    for path, source in candidates:
        try:
            completed = subprocess.run(
                [path, "-version"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=12,
                creationflags=_CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            continue
        if completed.returncode == 0:
            first = (completed.stdout or completed.stderr or "").splitlines()
            version = first[0].strip() if first else "FFmpeg"
            return FFmpegInfo(ffmpeg=path, source=source, version=version)
    raise MediaError(tr("error.ffmpeg_missing"))


def _run_probe(ffmpeg: str, media_path: Path) -> str:
    try:
        completed = subprocess.run(
            [ffmpeg, "-hide_banner", "-i", str(media_path)],
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=25,
            creationflags=_CREATE_NO_WINDOW,
        )
    except subprocess.TimeoutExpired as exc:
        raise MediaError(tr("error.ffmpeg_probe")) from exc
    except OSError as exc:
        raise MediaError(tr("error.ffmpeg_start")) from exc
    # ffmpeg exits non-zero when only probing; stderr still has the metadata.
    return f"{completed.stdout}\n{completed.stderr}"


def _duration_from_text(text: str) -> int:
    match = _DURATION_RE.search(text)
    if not match:
        return 0
    hours, minutes, seconds = match.groups()
    return int((int(hours) * 3600 + int(minutes) * 60 + float(seconds)) * 1000)


def probe_media(ffmpeg: str, media_path: Path) -> MediaInfo:
    media_path = Path(media_path)
    if not media_path.is_file():
        raise MediaError(tr("error.file_missing"))
    text = _run_probe(ffmpeg, media_path)
    duration_ms = _duration_from_text(text)
    video_match = _VIDEO_RE.search(text)
    audio_match = _AUDIO_RE.search(text)
    if not video_match and not audio_match:
        raise MediaError(tr("error.ffmpeg_no_stream"))
    width = int(video_match.group(2)) if video_match else 0
    height = int(video_match.group(3)) if video_match else 0
    if duration_ms <= 0:
        raise MediaError(tr("error.ffmpeg_no_duration"))
    return MediaInfo(
        path=media_path,
        duration_ms=duration_ms,
        width=width,
        height=height,
        video_codec=video_match.group(1).lower() if video_match else "",
        audio_codec=audio_match.group(1).lower() if audio_match else "",
        size_bytes=media_path.stat().st_size,
        has_audio=bool(audio_match),
    )


def format_duration(milliseconds: int) -> str:
    total_seconds = max(0, int(round(milliseconds / 1000)))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)
    if hours:
        return f"{hours:02d}:{minutes:02d}:{seconds:02d}"
    return f"{minutes:02d}:{seconds:02d}"


def format_size(size_bytes: int) -> str:
    value = float(max(0, size_bytes))
    for unit in ("B", "KB", "MB", "GB"):
        if value < 1024 or unit == "GB":
            return f"{value:.0f} {unit}" if unit == "B" else f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB"


def _run_ffmpeg(
    ffmpeg: str,
    args: list[str],
    *,
    timeout_seconds: int,
    on_progress: Callable[[int], None] | None = None,
    duration_ms: int = 0,
    cancelled: Callable[[], bool] | None = None,
) -> None:
    command = [ffmpeg, "-hide_banner", "-y", *args]
    try:
        process = subprocess.Popen(
            command,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
            encoding="utf-8",
            errors="replace",
            creationflags=_CREATE_NO_WINDOW,
        )
    except OSError as exc:
        raise MediaError(tr("error.ffmpeg_start")) from exc

    started = time.monotonic()
    tail: list[str] = []
    try:
        assert process.stdout is not None
        for line in process.stdout:
            if cancelled and cancelled():
                process.terminate()
                raise CancelledError()
            tail.append(line.rstrip())
            if len(tail) > 30:
                tail.pop(0)
            if on_progress and duration_ms > 0:
                if line.startswith("out_time_ms="):
                    try:
                        microseconds = int(line.split("=", 1)[1].strip())
                        percent = min(99, max(0, int(microseconds / (duration_ms * 10))))
                        on_progress(percent)
                    except ValueError:
                        pass
            if time.monotonic() - started > timeout_seconds:
                process.kill()
                raise MediaError(tr("error.ffmpeg_timeout"))
        code = process.wait(timeout=30)
    finally:
        if process.poll() is None:
            process.kill()
    if code != 0:
        detail = "\n".join(tail[-8:])
        if "does not contain any stream" in detail or "matches no streams" in detail:
            raise MediaError(tr("error.ffmpeg_no_audio"))
        raise MediaError(tr("error.ffmpeg_failed"), detail=detail)


def extract_audio(
    ffmpeg: str,
    video_path: Path,
    output_path: Path,
    duration_ms: int,
    on_progress: Callable[[int], None] | None = None,
    cancelled: Callable[[], bool] | None = None,
) -> Path:
    """Extract a compact 16 kHz mono MP3 suitable for long-audio ASR."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    attempts = [
        (
            [
                "-i",
                str(video_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "libmp3lame",
                "-b:a",
                "64k",
                "-progress",
                "pipe:1",
                "-nostats",
                str(output_path),
            ],
            output_path,
        ),
        (
            [
                "-i",
                str(video_path),
                "-map",
                "0:a:0",
                "-vn",
                "-ac",
                "1",
                "-ar",
                "16000",
                "-c:a",
                "aac",
                "-b:a",
                "64k",
                "-progress",
                "pipe:1",
                "-nostats",
                str(output_path.with_suffix(".m4a")),
            ],
            output_path.with_suffix(".m4a"),
        ),
    ]
    last_error: Exception | None = None
    for args, candidate in attempts:
        try:
            _run_ffmpeg(
                ffmpeg,
                args,
                timeout_seconds=max(120, int(duration_ms / 1000 * 2) + 60),
                on_progress=on_progress,
                duration_ms=duration_ms,
                cancelled=cancelled,
            )
            if candidate.is_file() and candidate.stat().st_size > 1024:
                return candidate
        except MediaError as exc:
            last_error = exc
            candidate.unlink(missing_ok=True)
        except CancelledError:
            candidate.unlink(missing_ok=True)
            raise
    if last_error:
        raise last_error
    raise MediaError(tr("error.ffmpeg_extract"))


def make_thumbnail(
    ffmpeg: str,
    video_path: Path,
    output_path: Path,
    duration_ms: int,
) -> Path | None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    offsets = [min(2.0, max(0.0, duration_ms / 2000)), 0.0]
    for offset in offsets:
        try:
            completed = subprocess.run(
                [
                    ffmpeg,
                    "-hide_banner",
                    "-y",
                    "-ss",
                    f"{offset:.2f}",
                    "-i",
                    str(video_path),
                    "-frames:v",
                    "1",
                    "-update",
                    "1",
                    "-vf",
                    "scale=480:-2",
                    "-q:v",
                    "3",
                    str(output_path),
                ],
                capture_output=True,
                timeout=30,
                creationflags=_CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return None
        if completed.returncode == 0 and output_path.is_file():
            return output_path
    return None


def reveal_file(path: Path) -> None:
    path = Path(path)
    if os.name == "nt":
        subprocess.Popen(["explorer", "/select,", str(path)], creationflags=_CREATE_NO_WINDOW)
        return
    _open_path(path.parent)


def open_folder(path: Path) -> None:
    _open_path(Path(path))


def _open_path(path: Path) -> None:
    if os.name == "nt":
        os.startfile(str(path))  # type: ignore[attr-defined]
    elif sys.platform == "darwin":
        subprocess.Popen(["open", str(path)])
    else:
        subprocess.Popen(["xdg-open", str(path)])
