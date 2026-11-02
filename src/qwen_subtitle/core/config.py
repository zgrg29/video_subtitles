"""Local, non-secret application settings.

The settings file deliberately contains no API key, media content, or
personally identifying metadata.  It is stored under the current user's
application-data directory so it can never be committed by accident.
"""

from __future__ import annotations

import json
import os
import sys
import tempfile
from dataclasses import asdict, dataclass, replace
from pathlib import Path

from qwen_subtitle.constants import (
    APP_ID,
    ASR_MODEL_BY_KEY,
    DEFAULT_ASR_MODEL,
    DEFAULT_OUTPUT_MODE,
    DEFAULT_REGION,
    DEFAULT_SOURCE_LANGUAGE,
    DEFAULT_SUBTITLE_FORMAT,
    DEFAULT_TARGET_LANGUAGE,
    DEFAULT_TRANSLATION_MODEL,
    DEFAULT_UI_LANGUAGE,
    OUTPUT_MODE_BY_KEY,
    REGION_BY_KEY,
    SUBTITLE_FORMAT_BY_KEY,
    TARGET_LANGUAGE_BY_CODE,
    TRANSLATION_MODEL_BY_KEY,
    UI_LANGUAGES,
)

SETTINGS_VERSION = 1


_RESOLVED_APP_DIR: Path | None = None


def _is_writable_dir(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe = path / f".write-probe-{os.getpid()}"
        probe.write_text("ok", encoding="utf-8")
        probe.unlink()
        return True
    except OSError:
        return False


def default_app_dir() -> Path:
    """Return a writable, per-user application directory.

    On locked-down Windows profiles, AppData can be non-writable for a
    particular process.  Prefer AppData, then fall back to a ``portable-data``
    folder next to the frozen EXE.  This keeps the app usable without
    administrator rights and without writing to ``%TEMP%``.
    """

    global _RESOLVED_APP_DIR
    if _RESOLVED_APP_DIR is not None:
        return _RESOLVED_APP_DIR

    candidates: list[Path] = []
    if os.name == "nt":
        for env_name in ("LOCALAPPDATA", "APPDATA"):
            base = os.environ.get(env_name)
            if base:
                candidates.append(Path(base) / APP_ID)
    else:
        xdg = os.environ.get("XDG_DATA_HOME")
        if xdg:
            candidates.append(Path(xdg) / APP_ID)
        candidates.append(Path.home() / f".{APP_ID.lower()}")

    if getattr(sys, "frozen", False):
        candidates.append(Path(sys.executable).resolve().parent / "portable-data")
    else:
        candidates.append(Path.home() / f".{APP_ID.lower()}")
        candidates.append(Path.cwd() / f".{APP_ID.lower()}-data")

    seen: set[Path] = set()
    for candidate in candidates:
        if candidate in seen:
            continue
        seen.add(candidate)
        if _is_writable_dir(candidate):
            _RESOLVED_APP_DIR = candidate
            return candidate
    raise OSError("No writable application data directory is available.")


def default_cache_dir() -> Path:
    """Writable cache root, independent of the system TEMP setting.

    One-file PyInstaller bootloaders and some corporate Windows profiles have a
    TEMP directory that ordinary users cannot write.  Application work files
    must not depend on that setting.
    """

    return default_app_dir() / "cache"


def create_work_dir(prefix: str) -> Path:
    """Create a private work directory under the user's application cache."""

    root = default_cache_dir()
    root.mkdir(parents=True, exist_ok=True)
    return Path(tempfile.mkdtemp(prefix=prefix, dir=str(root)))


@dataclass
class Settings:
    """Persisted user preferences.

    Model and language choices are saved immediately by the UI so reopening the
    application restores exactly what the user selected last time.
    """

    version: int = SETTINGS_VERSION
    region: str = DEFAULT_REGION
    asr_model: str = DEFAULT_ASR_MODEL
    translation_model: str = DEFAULT_TRANSLATION_MODEL
    source_language: str = DEFAULT_SOURCE_LANGUAGE
    target_language: str = DEFAULT_TARGET_LANGUAGE
    output_mode: str = DEFAULT_OUTPUT_MODE
    subtitle_format: str = DEFAULT_SUBTITLE_FORMAT
    ui_language: str = DEFAULT_UI_LANGUAGE
    output_dir: str = ""
    ffmpeg_path: str = ""

    def normalized(self) -> "Settings":
        """Return a copy with every value validated against the catalogues."""

        def text_value(value: object, default: str = "") -> str:
            if not isinstance(value, str):
                return default
            return value.strip().replace("\x00", "")

        region = self.region if self.region in REGION_BY_KEY else DEFAULT_REGION
        asr_model = self.asr_model if self.asr_model in ASR_MODEL_BY_KEY else DEFAULT_ASR_MODEL
        mt_model = (
            self.translation_model
            if self.translation_model in TRANSLATION_MODEL_BY_KEY
            else DEFAULT_TRANSLATION_MODEL
        )
        fmt = self.subtitle_format if self.subtitle_format in SUBTITLE_FORMAT_BY_KEY else DEFAULT_SUBTITLE_FORMAT
        target = self.target_language if self.target_language in TARGET_LANGUAGE_BY_CODE else DEFAULT_TARGET_LANGUAGE
        source = text_value(self.source_language, DEFAULT_SOURCE_LANGUAGE) or DEFAULT_SOURCE_LANGUAGE
        output_mode = self.output_mode if self.output_mode in OUTPUT_MODE_BY_KEY else DEFAULT_OUTPUT_MODE
        ui_language = self.ui_language if self.ui_language in UI_LANGUAGES else DEFAULT_UI_LANGUAGE
        # Migrate a pre-release value that meant "do not translate".
        if self.target_language == "none":
            output_mode = "original"
        output_dir = text_value(self.output_dir)
        ffmpeg_path = text_value(self.ffmpeg_path)
        return replace(
            self,
            version=SETTINGS_VERSION,
            region=region,
            asr_model=asr_model,
            translation_model=mt_model,
            source_language=source,
            target_language=target,
            output_mode=output_mode,
            subtitle_format=fmt,
            ui_language=ui_language,
            output_dir=output_dir,
            ffmpeg_path=ffmpeg_path,
        )


class ConfigStore:
    """Read and atomically write :class:`Settings` as JSON."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (default_app_dir() / "settings.json")

    def load(self) -> Settings:
        if not self.path.exists():
            return Settings()
        try:
            raw = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, UnicodeError, json.JSONDecodeError):
            return Settings()
        if not isinstance(raw, dict):
            return Settings()
        known = {field: raw[field] for field in Settings.__dataclass_fields__ if field in raw}
        try:
            settings = Settings(**known)
        except TypeError:
            return Settings()
        return settings.normalized()

    def save(self, settings: Settings) -> None:
        settings = settings.normalized()
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(asdict(settings), ensure_ascii=False, indent=2) + "\n"
        fd, tmp_name = tempfile.mkstemp(
            prefix=".settings-",
            suffix=".json",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "w", encoding="utf-8", newline="\n") as handle:
                handle.write(payload)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise


def save_patch(base: Settings, **changes: object) -> Settings:
    """Small convenience used by UI event handlers."""

    updated = replace(base, **changes).normalized()
    return updated
