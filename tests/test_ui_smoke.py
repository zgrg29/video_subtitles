from __future__ import annotations

import os
from pathlib import Path

import pytest

from qwen_subtitle.constants import SOURCE_LANGUAGES
from qwen_subtitle.core.config import ConfigStore
from qwen_subtitle.core.secrets import SecretStore
from qwen_subtitle.ui.main_window import MainWindow
from qwen_subtitle.ui.state import AppState


def test_main_window_starts_in_chinese_and_switches_languages(qapp, tmp_path: Path) -> None:
    state = AppState(
        ConfigStore(tmp_path / "settings.json"),
        SecretStore(tmp_path / "secrets.bin"),
    )
    window = MainWindow(state)
    window.show()
    qapp.processEvents()

    assert window.stack.count() == 3
    assert window.nav_buttons["workbench"].text() == "工作台"
    assert window.title_bar.language_combo.currentData() == "zh"
    assert window.workbench.content_segment.value() == "translated"
    assert window.workbench.source_combo.count() == len(SOURCE_LANGUAGES)
    assert not window.workbench.header_run_button.isEnabled()
    assert window.title_bar.close_button.x() > window.width() // 2
    assert window.title_bar.language_combo.x() < 120

    # The title-bar language selector must work from anywhere without opening
    # Settings, and must remain in sync with the persisted preference.
    title_index = window.title_bar.language_combo.findData("en")
    window.title_bar.language_combo.setCurrentIndex(title_index)
    qapp.processEvents()
    assert state.settings.ui_language == "en"

    state.update(ui_language="en")
    qapp.processEvents()
    assert window.nav_buttons["workbench"].text() == "Workbench"
    assert "Subtitles" in window.workbench.settings_title.text() or "Subtitle" in window.workbench.settings_title.text()

    window.show_page("settings")
    qapp.processEvents()
    assert window.stack.currentWidget() is window.settings_page

    state.update(ui_language="zh")
    qapp.processEvents()
    assert window.nav_buttons["workbench"].text() == "工作台"
    window.close()
    qapp.processEvents()


def test_original_mode_disables_translation_controls(qapp, tmp_path: Path) -> None:
    state = AppState(
        ConfigStore(tmp_path / "settings.json"),
        SecretStore(tmp_path / "secrets.bin"),
    )
    window = MainWindow(state)
    window.workbench._on_content_changed("original")
    qapp.processEvents()
    assert window.workbench.target_combo.isEnabled() is False
    assert window.workbench.mt_combo.isEnabled() is False
    assert state.settings.output_mode == "original"
    window.workbench._on_content_changed("bilingual")
    assert window.workbench.target_combo.isEnabled() is True
    window.close()


@pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI only")
def test_settings_key_save_uses_secret_store(qapp, tmp_path: Path) -> None:
    state = AppState(
        ConfigStore(tmp_path / "settings.json"),
        SecretStore(tmp_path / "secrets.bin"),
    )
    window = MainWindow(state)
    window.show_page("settings")
    window.settings_page.key_field.edit.setText("sk-test-ui-only")
    window.settings_page._save_key()
    qapp.processEvents()
    assert state.has_api_key("cn")
    assert window.settings_page.key_field.text() == ""
    settings_path = tmp_path / "settings.json"
    if settings_path.exists():
        assert "sk-test-ui-only" not in settings_path.read_text(encoding="utf-8")
    secret_bytes = (tmp_path / "secrets.bin").read_bytes()
    assert b"sk-test-ui-only" not in secret_bytes
    window.close()
