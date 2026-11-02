"""Shared UI state with immediate, persisted preference updates."""

from __future__ import annotations

from dataclasses import replace

from PySide6.QtCore import QObject, Signal

from qwen_subtitle.core.config import ConfigStore, Settings
from qwen_subtitle.core.secrets import SecretStore, SecretStoreError
from qwen_subtitle.i18n import set_language


class AppState(QObject):
    settings_changed = Signal(str)
    language_changed = Signal(str)

    def __init__(
        self,
        config_store: ConfigStore | None = None,
        secret_store: SecretStore | None = None,
        parent: QObject | None = None,
    ) -> None:
        super().__init__(parent)
        self.config_store = config_store or ConfigStore()
        self.secret_store = secret_store or SecretStore()
        self.settings = self.config_store.load()
        set_language(self.settings.ui_language)

    def update(self, **changes: object) -> Settings:
        previous = self.settings
        updated = replace(previous, **changes).normalized()
        self.config_store.save(updated)
        self.settings = updated
        if updated.ui_language != previous.ui_language:
            set_language(updated.ui_language)
            self.settings_changed.emit("ui_language")
            self.language_changed.emit(updated.ui_language)
            return updated
        for field in changes:
            if getattr(previous, field, None) != getattr(updated, field, None):
                self.settings_changed.emit(field)
        return updated

    def set_api_key(self, region: str, value: str) -> None:
        self.secret_store.set_api_key(region, value)

    def delete_api_key(self, region: str) -> None:
        self.secret_store.delete_api_key(region)

    def api_key(self, region: str | None = None) -> str:
        return self.secret_store.get_api_key(region or self.settings.region)

    def has_api_key(self, region: str | None = None) -> bool:
        try:
            return self.secret_store.has_api_key(region or self.settings.region)
        except SecretStoreError:
            return False

    def masked_hint(self, region: str | None = None) -> str:
        try:
            return self.secret_store.masked_hint(region or self.settings.region)
        except SecretStoreError:
            return "—"
