from __future__ import annotations

from qwen_subtitle.i18n import _STRINGS, get_language, set_language, tr


def test_all_ui_languages_have_the_same_keys() -> None:
    zh_keys = set(_STRINGS["zh"])
    assert set(_STRINGS["en"]) == zh_keys
    assert set(_STRINGS["ja"]) == zh_keys


def test_language_switch_and_placeholders() -> None:
    set_language("zh")
    assert get_language() == "zh"
    assert "字幕" in tr("workbench.title")
    set_language("en")
    assert "subtitles" in tr("workbench.title").lower()
    assert tr("progress.asr_done", count=3).endswith("3 sentences")
    set_language("ja")
    assert "字幕" in tr("workbench.title")
    set_language("zh")


def test_unknown_key_falls_back_to_key() -> None:
    set_language("en")
    assert tr("missing.translation.key") == "missing.translation.key"
    set_language("zh")
