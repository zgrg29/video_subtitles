"""Settings page: interface language, API keys, FFmpeg, output and privacy."""

from __future__ import annotations

from PySide6.QtCore import QThread, QTimer, Qt, QUrl, Signal
from PySide6.QtGui import QDesktopServices
from PySide6.QtWidgets import (
    QApplication,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from qwen_subtitle.constants import REGION_BY_KEY, REGIONS, UI_LANGUAGES
from qwen_subtitle.core.dashscope import QwenClient
from qwen_subtitle.core.errors import AppError
from qwen_subtitle.core.ffmpeg import FFmpegInfo, resolve_ffmpeg
from qwen_subtitle.i18n import tr, ui_language_label
from qwen_subtitle.ui.dialogs import ConfirmDialog, ErrorDialog
from qwen_subtitle.ui.icons import icon
from qwen_subtitle.ui.state import AppState
from qwen_subtitle.ui.widgets import (
    Card,
    FadeLabel,
    KeyField,
    SegmentedControl,
    make_label,
)


class ApiTestWorker(QThread):
    succeeded = Signal()
    failed = Signal(str)

    def __init__(self, base_url: str, api_key: str, model: str) -> None:
        super().__init__()
        self.base_url = base_url
        self.api_key = api_key
        self.model = model

    def run(self) -> None:
        try:
            QwenClient(self.base_url, self.api_key, timeout=(10.0, 30.0)).test_key(self.model)
            self.succeeded.emit()
        except AppError as exc:
            self.failed.emit(exc.user_message)
        except Exception:
            self.failed.emit(tr("error.network"))


class SettingsPage(QWidget):
    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._ffmpeg: FFmpegInfo | None = None
        self._test_worker: ApiTestWorker | None = None
        self._labels: dict[str, QLabel] = {}
        self._build()
        self.retranslate()
        self.state.settings_changed.connect(self._sync_from_state)
        self._sync_from_state("")
        QTimer.singleShot(60, self._detect_ffmpeg)

    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        outer.addWidget(scroll)

        host = QWidget()
        scroll.setWidget(host)
        host_layout = QHBoxLayout(host)
        host_layout.setContentsMargins(40, 30, 40, 34)
        host_layout.addStretch(1)
        panel = QWidget()
        panel.setMaximumWidth(760)
        self.panel_layout = QVBoxLayout(panel)
        self.panel_layout.setContentsMargins(0, 0, 0, 0)
        self.panel_layout.setSpacing(16)
        host_layout.addWidget(panel, 4)
        host_layout.addStretch(1)

        header = QVBoxLayout()
        header.setSpacing(5)
        self.eyebrow = make_label("", "Eyebrow")
        self.title = make_label("", "PageTitle")
        self.subtitle = make_label("", "PageSubtitle")
        header.addWidget(self.eyebrow)
        header.addWidget(self.title)
        header.addWidget(self.subtitle)
        self.panel_layout.addLayout(header)

        self._build_language_card()
        self._build_api_card()
        self._build_ffmpeg_card()
        self._build_output_card()
        self._build_privacy_card()
        self.panel_layout.addStretch(1)
        self.status = FadeLabel()
        self.panel_layout.addWidget(self.status)

    def _card(self, title_key: str, desc_key: str) -> tuple[Card, QVBoxLayout]:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(12)
        titles = QVBoxLayout()
        titles.setSpacing(2)
        title = make_label("", "CardTitle")
        desc = make_label("", "CardHint")
        desc.setWordWrap(True)
        self._labels[title_key] = title
        self._labels[desc_key] = desc
        titles.addWidget(title)
        titles.addWidget(desc)
        layout.addLayout(titles)
        return card, layout

    def _build_language_card(self) -> None:
        card, layout = self._card("settings.language.title", "settings.language.desc")
        self.language_segment = SegmentedControl(
            [(code, ui_language_label(code)) for code in UI_LANGUAGES]
        )
        self.language_segment.changed.connect(self._on_language_changed)
        layout.addWidget(self.language_segment)
        self.panel_layout.addWidget(card)

    def _build_api_card(self) -> None:
        card, layout = self._card("settings.api.title", "settings.api.desc")
        self.api_region_segment = SegmentedControl(
            [(region.key, tr(f"region.{region.key}.short")) for region in REGIONS]
        )
        self.api_region_segment.changed.connect(self._on_api_region_changed)
        region_label = make_label("", "FieldLabel")
        self._labels["settings.api.region"] = region_label
        layout.addWidget(region_label)
        layout.addWidget(self.api_region_segment)

        key_row = QHBoxLayout()
        key_row.setSpacing(8)
        key_col = QVBoxLayout()
        key_col.setSpacing(5)
        key_label = make_label("", "FieldLabel")
        self._labels["settings.api.key"] = key_label
        self.key_field = KeyField()
        self.key_field.edit.setMaxLength(512)
        key_col.addWidget(key_label)
        key_col.addWidget(self.key_field)
        key_row.addLayout(key_col, 1)
        self.save_key_button = QPushButton()
        self.save_key_button.setObjectName("Primary")
        self.save_key_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.save_key_button.clicked.connect(self._save_key)
        key_row.addWidget(self.save_key_button, 0, Qt.AlignmentFlag.AlignBottom)
        layout.addLayout(key_row)

        state_row = QHBoxLayout()
        state_row.setSpacing(8)
        self.key_state = make_label("", "Tiny")
        state_row.addWidget(self.key_state)
        state_row.addStretch(1)
        self.test_button = QPushButton()
        self.test_button.setObjectName("Secondary")
        self.test_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.test_button.clicked.connect(self._test_key)
        state_row.addWidget(self.test_button)
        self.delete_key_button = QPushButton()
        self.delete_key_button.setObjectName("Danger")
        self.delete_key_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.delete_key_button.clicked.connect(self._delete_key)
        state_row.addWidget(self.delete_key_button)
        layout.addLayout(state_row)

        note_row = QHBoxLayout()
        note_row.setSpacing(6)
        lock = QLabel()
        lock.setPixmap(icon("lock", "#8E8E93", 12).pixmap(12, 12))
        note_row.addWidget(lock)
        self.encrypted_note = make_label("", "Tiny")
        note_row.addWidget(self.encrypted_note)
        note_row.addStretch(1)
        self.get_key_button = QPushButton()
        self.get_key_button.setObjectName("Ghost")
        self.get_key_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.get_key_button.clicked.connect(self._open_console)
        note_row.addWidget(self.get_key_button)
        layout.addLayout(note_row)
        self.api_note = make_label("", "Tiny")
        self.api_note.setWordWrap(True)
        layout.addWidget(self.api_note)
        self.panel_layout.addWidget(card)

    def _build_ffmpeg_card(self) -> None:
        card, layout = self._card("settings.ffmpeg.title", "settings.ffmpeg.desc")
        status_row = QHBoxLayout()
        status_row.setSpacing(8)
        self.ffmpeg_badge = make_label("", "Pill")
        status_row.addWidget(self.ffmpeg_badge)
        self.ffmpeg_source = make_label("", "Muted")
        status_row.addWidget(self.ffmpeg_source)
        status_row.addStretch(1)
        layout.addLayout(status_row)
        self.ffmpeg_path = make_label("", "PathBox")
        self.ffmpeg_path.setWordWrap(True)
        self.ffmpeg_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.ffmpeg_path)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.redetect_button = QPushButton()
        self.redetect_button.setObjectName("Secondary")
        self.redetect_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.redetect_button.clicked.connect(self._detect_ffmpeg)
        buttons.addWidget(self.redetect_button)
        self.choose_ffmpeg_button = QPushButton()
        self.choose_ffmpeg_button.setObjectName("Secondary")
        self.choose_ffmpeg_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose_ffmpeg_button.clicked.connect(self._choose_ffmpeg)
        buttons.addWidget(self.choose_ffmpeg_button)
        layout.addLayout(buttons)
        self.panel_layout.addWidget(card)

    def _build_output_card(self) -> None:
        card, layout = self._card("settings.output.title", "settings.output.desc")
        self.output_path = make_label("", "PathBox")
        self.output_path.setWordWrap(True)
        self.output_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        layout.addWidget(self.output_path)
        buttons = QHBoxLayout()
        buttons.addStretch(1)
        self.reset_output_button = QPushButton()
        self.reset_output_button.setObjectName("Ghost")
        self.reset_output_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reset_output_button.clicked.connect(self._reset_output)
        buttons.addWidget(self.reset_output_button)
        self.choose_output_button = QPushButton()
        self.choose_output_button.setObjectName("Secondary")
        self.choose_output_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.choose_output_button.clicked.connect(self._choose_output)
        buttons.addWidget(self.choose_output_button)
        layout.addLayout(buttons)
        self.panel_layout.addWidget(card)

    def _build_privacy_card(self) -> None:
        card, layout = self._card("settings.privacy.title", "settings.privacy.hint")
        self.privacy_body = make_label("", "Body")
        self.privacy_body.setWordWrap(True)
        layout.addWidget(self.privacy_body)
        self.panel_layout.addWidget(card)

    # -------------------------------------------------------------- localise
    def retranslate(self) -> None:
        self.eyebrow.setText(tr("settings.eyebrow"))
        self.title.setText(tr("settings.title"))
        self.subtitle.setText(tr("settings.subtitle"))
        for key, label in self._labels.items():
            label.setText(tr(key))
        self.language_segment.set_labels({code: ui_language_label(code) for code in UI_LANGUAGES})
        self.api_region_segment.set_labels({r.key: tr(f"region.{r.key}.short") for r in REGIONS})
        self.save_key_button.setText(tr("settings.api.save"))
        self.test_button.setText(tr("settings.api.test"))
        self.delete_key_button.setText(tr("settings.api.delete"))
        self.get_key_button.setText(tr("settings.api.get"))
        self.encrypted_note.setText(tr("settings.api.encrypted"))
        self.api_note.setText(tr("settings.api.note"))
        self.redetect_button.setText(tr("settings.ffmpeg.redetect"))
        self.choose_ffmpeg_button.setText(tr("settings.ffmpeg.choose"))
        self.choose_output_button.setText(tr("settings.output.choose"))
        self.reset_output_button.setText(tr("settings.output.reset"))
        self._refresh_key_state()
        self._refresh_output_text()
        self._apply_ffmpeg_state()

    # ---------------------------------------------------------------- state
    def _sync_from_state(self, field: str) -> None:
        settings = self.state.settings
        for widget in (self.language_segment, self.api_region_segment):
            widget.blockSignals(True)
        self.language_segment.set_value(settings.ui_language)
        self.api_region_segment.set_value(settings.region)
        for widget in (self.language_segment, self.api_region_segment):
            widget.blockSignals(False)
        self._refresh_key_state()
        self._refresh_output_text()

    def _on_language_changed(self, code: str) -> None:
        try:
            self.state.update(ui_language=code)
        except OSError as exc:
            self._show_error(str(exc))

    def _on_api_region_changed(self, region: str) -> None:
        self.key_field.clear()
        try:
            self.state.update(region=region)
        except OSError as exc:
            self._show_error(str(exc))
            return
        self._refresh_key_state()

    def _refresh_key_state(self) -> None:
        region = self.state.settings.region
        has_key = self.state.has_api_key(region)
        self.key_field.edit.setPlaceholderText(
            tr("settings.api.saved_placeholder") if has_key else tr("settings.api.empty_placeholder")
        )
        self.key_state.setText(tr("settings.api.state_saved") if has_key else tr("settings.api.state_empty"))
        self.delete_key_button.setEnabled(has_key)
        self.test_button.setEnabled(has_key and self._test_worker is None)

    def _save_key(self) -> None:
        value = self.key_field.text().strip()
        if not value:
            self._show_error(tr("error.secret_empty"))
            return
        try:
            self.state.set_api_key(self.state.settings.region, value)
        except Exception as exc:
            self._show_error(tr("error.secret", message=str(exc)))
            return
        self.key_field.clear()
        self._refresh_key_state()
        self.status.show_message(tr("settings.api.saved"))

    def _delete_key(self) -> None:
        region = self.state.settings.region
        dialog = ConfirmDialog(
            tr("dialog.delete_key.title"),
            tr("dialog.delete_key.body"),
            confirm_text=tr("common.delete"),
            destructive=True,
            parent=self.window(),
        )
        if dialog.exec() and dialog.confirmed:
            try:
                self.state.delete_api_key(region)
            except Exception as exc:
                self._show_error(tr("error.secret", message=str(exc)))
                return
            self._refresh_key_state()
            self.status.show_message(tr("settings.api.deleted"))

    def _test_key(self) -> None:
        if self._test_worker is not None:
            return
        region = REGION_BY_KEY.get(self.state.settings.region)
        if region is None:
            return
        try:
            api_key = self.state.api_key(region.key)
        except Exception as exc:
            self._show_error(tr("error.secret", message=str(exc)))
            return
        if not api_key:
            self._show_error(tr("error.no_key", region=tr(f"region.{region.key}.short")))
            return
        self.test_button.setEnabled(False)
        self.test_button.setText(tr("settings.api.testing"))
        self._test_worker = ApiTestWorker(region.base_url, api_key, self.state.settings.asr_model)
        self._test_worker.succeeded.connect(self._test_succeeded)
        self._test_worker.failed.connect(self._test_failed)
        self._test_worker.finished.connect(self._test_finished)
        self._test_worker.start()

    def _test_succeeded(self) -> None:
        self.status.show_message(tr("settings.api.test_ok"))

    def _test_failed(self, message: str) -> None:
        self._show_error(tr("settings.api.test_fail", message=message))

    def _test_finished(self) -> None:
        worker = self._test_worker
        self._test_worker = None
        if worker:
            worker.deleteLater()
        self.test_button.setText(tr("settings.api.test"))
        self._refresh_key_state()

    def _open_console(self) -> None:
        region = REGION_BY_KEY.get(self.state.settings.region)
        if region:
            QDesktopServices.openUrl(QUrl(region.console_url))

    # -------------------------------------------------------------- ffmpeg
    def _detect_ffmpeg(self) -> None:
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            self._ffmpeg = resolve_ffmpeg(self.state.settings.ffmpeg_path)
        except AppError:
            self._ffmpeg = None
        finally:
            QApplication.restoreOverrideCursor()
        self._apply_ffmpeg_state()

    def _apply_ffmpeg_state(self) -> None:
        if not hasattr(self, "ffmpeg_badge"):
            return
        if self._ffmpeg:
            self.ffmpeg_badge.setText(tr("settings.ffmpeg.detected"))
            self.ffmpeg_badge.setStyleSheet("background: #E9F8EE; color: #248A3D;")
            source_label = tr(f"ffmpeg.source.{self._ffmpeg.source}")
            if source_label.startswith("ffmpeg.source."):
                source_label = self._ffmpeg.source
            self.ffmpeg_source.setText(tr("settings.ffmpeg.source", source=source_label))
            self.ffmpeg_path.setText(self._ffmpeg.ffmpeg)
        else:
            self.ffmpeg_badge.setText(tr("settings.ffmpeg.missing"))
            self.ffmpeg_badge.setStyleSheet("background: #FDECEA; color: #D70015;")
            self.ffmpeg_source.setText(tr("settings.ffmpeg.missing_hint"))
            self.ffmpeg_path.setText("—")

    def _choose_ffmpeg(self) -> None:
        path, _ = QFileDialog.getOpenFileName(
            self,
            tr("settings.ffmpeg.choose"),
            "",
            tr("file_dialog.ffmpeg_filter"),
        )
        if not path:
            return
        try:
            self.state.update(ffmpeg_path=path)
        except OSError as exc:
            self._show_error(str(exc))
            return
        self._detect_ffmpeg()

    # -------------------------------------------------------------- output
    def _choose_output(self) -> None:
        path = QFileDialog.getExistingDirectory(self, tr("settings.output.choose"), "")
        if not path:
            return
        try:
            self.state.update(output_dir=path)
        except OSError as exc:
            self._show_error(str(exc))
            return
        self._refresh_output_text()

    def _reset_output(self) -> None:
        try:
            self.state.update(output_dir="")
        except OSError as exc:
            self._show_error(str(exc))
            return
        self._refresh_output_text()

    def _refresh_output_text(self) -> None:
        self.output_path.setText(
            self.state.settings.output_dir or tr("settings.output.same")
        )

    def _show_error(self, message: str) -> None:
        ErrorDialog(message, parent=self.window()).exec()

    def cleanup(self) -> None:
        worker = self._test_worker
        if worker and worker.isRunning():
            if not worker.wait(2500):
                worker.terminate()
                worker.wait(800)
