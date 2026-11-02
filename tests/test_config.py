from __future__ import annotations

import json
from pathlib import Path

from qwen_subtitle.constants import (
    DEFAULT_ASR_MODEL,
    DEFAULT_TRANSLATION_MODEL,
    DEFAULT_UI_LANGUAGE,
    TRANSLATION_MODELS,
)
from qwen_subtitle.core.config import ConfigStore, Settings


def test_current_qwen_mt_catalog_is_plus_flash() -> None:
    assert [model.key for model in TRANSLATION_MODELS] == [
        "qwen-mt-plus",
        "qwen-mt-flash",
    ]
    assert "qwen-mt-turbo" not in {model.key for model in TRANSLATION_MODELS}
    assert "qwen-mt-lite" not in {model.key for model in TRANSLATION_MODELS}


def test_defaults_and_roundtrip(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    store = ConfigStore(path)
    settings = store.load()
    assert settings.asr_model == DEFAULT_ASR_MODEL
    assert settings.translation_model == DEFAULT_TRANSLATION_MODEL
    assert settings.ui_language == DEFAULT_UI_LANGUAGE
    settings.output_mode = "original"
    settings.asr_model = "qwen3-asr-flash-filetrans"
    settings.translation_model = "qwen-mt-flash"
    settings.ui_language = "ja"
    settings.subtitle_format = "ass"
    store.save(settings)
    loaded = store.load()
    assert loaded.output_mode == "original"
    assert loaded.asr_model == "qwen3-asr-flash-filetrans"
    assert loaded.translation_model == "qwen-mt-flash"
    assert loaded.ui_language == "ja"
    assert loaded.subtitle_format == "ass"


def test_invalid_values_are_normalised(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text(
        json.dumps(
            {
                "region": "unknown",
                "asr_model": "old-model",
                "translation_model": "old-mt",
                "output_mode": "wat",
                "subtitle_format": "docx",
                "ui_language": "fr",
                "source_language": None,
                "output_dir": None,
                "ffmpeg_path": None,
            }
        ),
        encoding="utf-8",
    )
    settings = ConfigStore(path).load()
    assert settings.region == "cn"
    assert settings.asr_model == DEFAULT_ASR_MODEL
    assert settings.translation_model == DEFAULT_TRANSLATION_MODEL
    assert settings.output_mode == "translated"
    assert settings.subtitle_format == "srt"
    assert settings.ui_language == DEFAULT_UI_LANGUAGE
    assert settings.output_dir == ""
    assert settings.ffmpeg_path == ""


def test_legacy_target_none_means_original() -> None:
    settings = Settings(target_language="none", output_mode="translated").normalized()
    assert settings.output_mode == "original"
    assert settings.target_language == "zh-Hans"


def test_broken_json_falls_back_without_crashing(tmp_path: Path) -> None:
    path = tmp_path / "settings.json"
    path.write_text("{not json", encoding="utf-8")
    assert ConfigStore(path).load().asr_model == DEFAULT_ASR_MODEL
