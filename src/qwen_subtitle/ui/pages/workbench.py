"""Main workbench page: pick a video, choose options, run the pipeline."""

from __future__ import annotations

import shutil
import threading
import uuid
from pathlib import Path

from PySide6.QtCore import QStandardPaths, Qt, QThread, QTimer, Signal
from PySide6.QtGui import QDesktopServices, QPixmap
from PySide6.QtCore import QUrl
from PySide6.QtWidgets import (
    QApplication,
    QComboBox,
    QFileDialog,
    QHBoxLayout,
    QLabel,
    QProgressBar,
    QPushButton,
    QScrollArea,
    QSizePolicy,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qwen_subtitle.constants import (
    ASR_MODEL_BY_KEY,
    ASR_MODELS,
    OUTPUT_MODES,
    OUTPUT_MODE_BY_KEY,
    REGIONS,
    SOURCE_LANGUAGES,
    SUBTITLE_FORMATS,
    SUBTITLE_FORMAT_BY_KEY,
    TARGET_LANGUAGES,
    TRANSLATION_MODELS,
    VIDEO_EXTENSIONS,
)
from qwen_subtitle.core.config import create_work_dir
from qwen_subtitle.core.errors import AppError, CancelledError
from qwen_subtitle.core.ffmpeg import (
    MediaInfo,
    format_duration,
    format_size,
    make_thumbnail,
    open_folder,
    probe_media,
    resolve_ffmpeg,
    reveal_file,
)
from qwen_subtitle.core.pipeline import PipelineOptions, PipelineResult, SubtitlePipeline
from qwen_subtitle.i18n import tr
from qwen_subtitle.ui.dialogs import CompletionDialog, ErrorDialog
from qwen_subtitle.ui.icons import icon
from qwen_subtitle.ui.state import AppState
from qwen_subtitle.ui.theme import ACCENT
from qwen_subtitle.ui.widgets import (
    Card,
    DropZone,
    FileCard,
    FadeLabel,
    SegmentedControl,
    Spinner,
    StepRow,
    divider,
    make_label,
)

_ASR_DETAIL = {
    "qwen-audio-3.1-asr-flash-filetrans": ("model.tagline.3.1", "model.desc.3.1"),
    "qwen-audio-3.0-asr-flash-filetrans": ("model.tagline.3.0", "model.desc.3.0"),
    "qwen3-asr-flash-filetrans": ("model.tagline.qwen3", "model.desc.qwen3"),
}
_MT_DETAIL = {
    "qwen-mt-plus": ("model.tagline.mt_plus", "model.desc.mt_plus"),
    "qwen-mt-flash": ("model.tagline.mt_flash", "model.desc.mt_flash"),
}


class PipelineWorker(QThread):
    progressed = Signal(str, int, str)
    succeeded = Signal(object)
    failed = Signal(str)
    cancelled = Signal()

    def __init__(self, options: PipelineOptions, cancel_event: threading.Event) -> None:
        super().__init__()
        self.options = options
        self.cancel_event = cancel_event

    def run(self) -> None:  # noqa: D401
        try:
            pipeline = SubtitlePipeline(
                self.options,
                progress=lambda stage, percent, message: self.progressed.emit(stage, percent, message),
                cancel_event=self.cancel_event,
            )
            result = pipeline.run()
            self.succeeded.emit(result)
        except CancelledError:
            self.cancelled.emit()
        except AppError as exc:
            self.failed.emit(exc.user_message)
        except Exception:
            self.failed.emit(tr("error.generic", message=tr("error.api")))


class WorkbenchPage(QWidget):
    open_settings = Signal()

    def __init__(self, state: AppState, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.state = state
        self._video_path: Path | None = None
        self._media: MediaInfo | None = None
        try:
            self._thumb_dir: Path | None = create_work_dir("ui-")
        except OSError:
            self._thumb_dir = None
        self._worker: PipelineWorker | None = None
        self._cancel_event: threading.Event | None = None
        self._busy = False
        self._last_result: PipelineResult | None = None
        self._last_message = ""
        self._stage_details = {"asr": "", "translate": "", "write": ""}
        self._field_labels: dict[str, QLabel] = {}
        self._build()
        self.retranslate()
        self.state.settings_changed.connect(self._sync_from_state)
        self._sync_from_state("")
        self._update_run_state()

    # ------------------------------------------------------------------ build
    def _build(self) -> None:
        outer = QVBoxLayout(self)
        outer.setContentsMargins(0, 0, 0, 0)
        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setHorizontalScrollBarPolicy(Qt.ScrollBarPolicy.ScrollBarAlwaysOff)
        self.scroll_area = scroll
        outer.addWidget(scroll)

        content = QWidget()
        scroll.setWidget(content)
        self.content_layout = QVBoxLayout(content)
        self.content_layout.setContentsMargins(40, 30, 40, 34)
        self.content_layout.setSpacing(18)

        header = QHBoxLayout()
        header.setSpacing(16)
        header_text = QVBoxLayout()
        header_text.setSpacing(5)
        self.eyebrow = make_label("", "Eyebrow")
        self.title = make_label("", "PageTitle")
        self.subtitle = make_label("", "PageSubtitle")
        header_text.addWidget(self.eyebrow)
        header_text.addWidget(self.title)
        header_text.addWidget(self.subtitle)
        header.addLayout(header_text, 1)
        right = QVBoxLayout()
        right.setSpacing(7)
        self.header_run_button = QPushButton()
        self.header_run_button.setObjectName("Primary")
        self.header_run_button.setMinimumWidth(148)
        self.header_run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.header_run_button.clicked.connect(self._start_run)
        right.addWidget(self.header_run_button, 0, Qt.AlignmentFlag.AlignRight)
        self.header_key_hint = make_label("", "Tiny")
        self.header_key_hint.setStyleSheet("color: #B25000; font-size: 10px;")
        self.header_key_hint.setAlignment(Qt.AlignmentFlag.AlignRight)
        self.header_key_hint.hide()
        right.addWidget(self.header_key_hint, 0, Qt.AlignmentFlag.AlignRight)
        self.region_pill = make_label("", "Pill")
        self.region_pill.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.region_pill.setSizePolicy(QSizePolicy.Policy.Fixed, QSizePolicy.Policy.Fixed)
        right.addWidget(self.region_pill, 0, Qt.AlignmentFlag.AlignRight)
        header.addLayout(right)
        self.content_layout.addLayout(header)

        self._build_video_card()
        self._build_settings_card()
        self._build_run_card()

        footer = QHBoxLayout()
        footer.setSpacing(6)
        lock = QLabel()
        lock.setPixmap(icon("lock", "#8E8E93", 13).pixmap(13, 13))
        footer.addWidget(lock)
        self.local_note = make_label("", "Tiny")
        footer.addWidget(self.local_note)
        footer.addStretch(1)
        self.content_layout.addLayout(footer)
        self.content_layout.addStretch(1)

    def _build_video_card(self) -> None:
        self.video_card = Card()
        layout = QVBoxLayout(self.video_card)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(11)
        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.video_title = make_label("", "CardTitle")
        self.video_hint = make_label("", "CardHint")
        titles.addWidget(self.video_title)
        titles.addWidget(self.video_hint)
        header.addLayout(titles)
        header.addStretch(1)
        layout.addLayout(header)

        self.video_stack = QStackedWidget()
        self.drop_zone = DropZone()
        self.drop_zone.choose_clicked.connect(self._choose_video)
        self.drop_zone.file_dropped.connect(self._load_video)
        self.file_card = FileCard()
        self.file_card.change_clicked.connect(self._choose_video)
        self.file_card.remove_clicked.connect(self._remove_video)
        self.video_stack.addWidget(self.drop_zone)
        self.video_stack.addWidget(self.file_card)
        layout.addWidget(self.video_stack)
        self.content_layout.addWidget(self.video_card)

    def _field(self, key: str, widget: QWidget) -> QWidget:
        container = QWidget()
        layout = QVBoxLayout(container)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(5)
        label = make_label("", "FieldLabel")
        self._field_labels[key] = label
        layout.addWidget(label)
        layout.addWidget(widget)
        return container

    def _build_settings_card(self) -> None:
        self.settings_card = Card()
        layout = QVBoxLayout(self.settings_card)
        layout.setContentsMargins(20, 18, 20, 20)
        layout.setSpacing(14)

        header = QHBoxLayout()
        titles = QVBoxLayout()
        titles.setSpacing(2)
        self.settings_title = make_label("", "CardTitle")
        self.settings_hint = make_label("", "CardHint")
        titles.addWidget(self.settings_title)
        titles.addWidget(self.settings_hint)
        header.addLayout(titles)
        header.addStretch(1)
        layout.addLayout(header)
        layout.addWidget(divider())

        self.source_combo = QComboBox()
        self.source_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.target_combo = QComboBox()
        self.target_combo.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.content_segment = SegmentedControl(
            [(mode.key, tr(f"content.{mode.key}")) for mode in OUTPUT_MODES]
        )
        self.content_segment.changed.connect(self._on_content_changed)

        row1 = QHBoxLayout()
        row1.setSpacing(14)
        row1.addWidget(self._field("caption.source", self.source_combo), 1)
        row1.addWidget(self._field("caption.target", self.target_combo), 1)
        row1.addWidget(self._field("caption.content", self.content_segment), 1)
        layout.addLayout(row1)

        self.content_hint = make_label("", "Muted")
        self.content_hint.setWordWrap(True)
        layout.addWidget(self.content_hint)

        self.asr_combo = QComboBox()
        self.mt_combo = QComboBox()
        self.asr_detail = make_label("", "Muted")
        self.asr_detail.setWordWrap(True)
        self.mt_detail = make_label("", "Muted")
        self.mt_detail.setWordWrap(True)
        row2 = QHBoxLayout()
        row2.setSpacing(14)
        asr_box = QWidget()
        asr_layout = QVBoxLayout(asr_box)
        asr_layout.setContentsMargins(0, 0, 0, 0)
        asr_layout.setSpacing(5)
        asr_layout.addWidget(self._field("caption.asr_model", self.asr_combo))
        asr_layout.addWidget(self.asr_detail)
        mt_box = QWidget()
        mt_layout = QVBoxLayout(mt_box)
        mt_layout.setContentsMargins(0, 0, 0, 0)
        mt_layout.setSpacing(5)
        mt_layout.addWidget(self._field("caption.mt_model", self.mt_combo))
        mt_layout.addWidget(self.mt_detail)
        row2.addWidget(asr_box, 1)
        row2.addWidget(mt_box, 1)
        layout.addLayout(row2)

        self.format_segment = SegmentedControl([(fmt.key, fmt.label) for fmt in SUBTITLE_FORMATS])
        self.format_segment.changed.connect(self._on_format_changed)
        self.region_segment = SegmentedControl(
            [(region.key, tr(f"region.{region.key}.short")) for region in REGIONS]
        )
        self.region_segment.changed.connect(self._on_region_changed)
        self.format_hint = make_label("", "Tiny")
        row3 = QHBoxLayout()
        row3.setSpacing(14)
        format_box = QWidget()
        format_layout = QVBoxLayout(format_box)
        format_layout.setContentsMargins(0, 0, 0, 0)
        format_layout.setSpacing(4)
        format_layout.addWidget(self._field("caption.format", self.format_segment))
        format_layout.addWidget(self.format_hint)
        row3.addWidget(format_box, 1)
        row3.addWidget(self._field("caption.region", self.region_segment), 1)
        layout.addLayout(row3)

        self.model_hint = make_label("", "Tiny")
        self.model_hint.setWordWrap(True)
        layout.addWidget(self.model_hint)
        self.content_layout.addWidget(self.settings_card)

        self.source_combo.currentIndexChanged.connect(self._on_source_changed)
        self.target_combo.currentIndexChanged.connect(self._on_target_changed)
        self.asr_combo.currentIndexChanged.connect(self._on_asr_changed)
        self.mt_combo.currentIndexChanged.connect(self._on_mt_changed)

    def _build_run_card(self) -> None:
        self.run_card = Card()
        layout = QVBoxLayout(self.run_card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(10)

        self.idle_box = QWidget()
        idle = QHBoxLayout(self.idle_box)
        idle.setContentsMargins(0, 0, 0, 0)
        idle.setSpacing(10)
        dot = QLabel()
        dot.setPixmap(icon("sparkles", ACCENT, 18).pixmap(18, 18))
        idle.addWidget(dot)
        idle_text = QVBoxLayout()
        idle_text.setSpacing(1)
        self.idle_title = make_label("", "Value")
        self.idle_hint = make_label("", "Muted")
        idle_text.addWidget(self.idle_title)
        idle_text.addWidget(self.idle_hint)
        idle.addLayout(idle_text, 1)
        self.settings_shortcut = QPushButton()
        self.settings_shortcut.setObjectName("Ghost")
        self.settings_shortcut.setCursor(Qt.CursorShape.PointingHandCursor)
        self.settings_shortcut.clicked.connect(self.open_settings)
        idle.addWidget(self.settings_shortcut)
        self.run_button = QPushButton()
        self.run_button.setObjectName("Primary")
        self.run_button.setMinimumWidth(150)
        self.run_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.run_button.clicked.connect(self._start_run)
        idle.addWidget(self.run_button)
        layout.addWidget(self.idle_box)

        self.key_warning = FadeLabel()
        self.key_warning.setStyleSheet("color: #B25000; font-size: 11px;")
        layout.addWidget(self.key_warning)

        self.progress_box = QWidget()
        progress_layout = QVBoxLayout(self.progress_box)
        progress_layout.setContentsMargins(0, 0, 0, 0)
        progress_layout.setSpacing(10)
        head = QHBoxLayout()
        head.setSpacing(8)
        self.header_spinner = Spinner(18, ACCENT)
        head.addWidget(self.header_spinner)
        self.progress_title = make_label("", "Value")
        self.progress_title.setStyleSheet("font-size: 14px;")
        head.addWidget(self.progress_title)
        head.addStretch(1)
        self.progress_percent = make_label("0%", "Muted")
        head.addWidget(self.progress_percent)
        progress_layout.addLayout(head)
        self.progress_note = make_label("", "Muted")
        progress_layout.addWidget(self.progress_note)
        self.progress_bar = QProgressBar()
        self.progress_bar.setRange(0, 100)
        self.progress_bar.setTextVisible(False)
        progress_layout.addWidget(self.progress_bar)
        steps = QHBoxLayout()
        steps.setSpacing(24)
        self.step_asr = StepRow(1, "")
        self.step_translate = StepRow(2, "")
        self.step_write = StepRow(3, "")
        for step in (self.step_asr, self.step_translate, self.step_write):
            steps.addWidget(step, 1)
        progress_layout.addLayout(steps)

        self.result_row = QWidget()
        result = QVBoxLayout(self.result_row)
        result.setContentsMargins(0, 2, 0, 0)
        result.setSpacing(8)
        self.result_path = make_label("", "PathBox")
        self.result_path.setWordWrap(True)
        self.result_path.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        result.addWidget(self.result_path)
        result_buttons = QHBoxLayout()
        result_buttons.setSpacing(8)
        self.again_button = QPushButton()
        self.again_button.setObjectName("Ghost")
        self.again_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.again_button.clicked.connect(self._reset_to_idle)
        result_buttons.addWidget(self.again_button)
        result_buttons.addStretch(1)
        self.open_file_button = QPushButton()
        self.open_file_button.setObjectName("Secondary")
        self.open_file_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_file_button.clicked.connect(self._open_last_file)
        result_buttons.addWidget(self.open_file_button)
        self.open_folder_button = QPushButton()
        self.open_folder_button.setObjectName("Primary")
        self.open_folder_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_folder_button.clicked.connect(self._open_last_folder)
        result_buttons.addWidget(self.open_folder_button)
        result.addLayout(result_buttons)
        progress_layout.addWidget(self.result_row)

        bottom = QHBoxLayout()
        bottom.addStretch(1)
        self.cancel_button = QPushButton()
        self.cancel_button.setObjectName("Secondary")
        self.cancel_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.cancel_button.clicked.connect(self._cancel_run)
        bottom.addWidget(self.cancel_button)
        progress_layout.addLayout(bottom)

        layout.addWidget(self.progress_box)
        self.progress_box.hide()
        self.result_row.hide()
        self.run_card.hide()
        self.content_layout.addWidget(self.run_card)

    # -------------------------------------------------------------- localise
    def retranslate(self) -> None:
        self.eyebrow.setText(tr("workbench.eyebrow"))
        self.title.setText(tr("workbench.title"))
        self.subtitle.setText(tr("workbench.subtitle"))
        self.local_note.setText(tr("workbench.local_note"))
        self.video_title.setText(tr("video.title"))
        self.video_hint.setText(tr("video.hint"))
        self.drop_zone.title.setText(tr("video.drop_title"))
        self.drop_zone.hint.setText(tr("video.drop_hint"))
        self.drop_zone.button.setText(tr("video.choose"))
        self.file_card.change_button.setText(tr("video.change"))
        self.file_card.remove_button.setText(tr("video.remove"))
        self.settings_title.setText(tr("caption.title"))
        self.settings_hint.setText(tr("caption.hint"))
        for key, label in self._field_labels.items():
            label.setText(tr(key))
        self.model_hint.setText(tr("caption.model_hint"))
        self.idle_title.setText(tr("run.ready"))
        self.idle_hint.setText(tr("run.hint"))
        self.settings_shortcut.setText(tr("error.open_settings"))
        self.run_button.setText(tr("run.start"))
        self.header_run_button.setText(tr("run.start"))
        self.header_key_hint.setText(tr("run.need_key_short"))
        self.cancel_button.setText(tr("run.cancel"))
        self.again_button.setText(tr("success.again"))
        self.open_file_button.setText(
            tr("success.open_translation")
            if self._last_result and len(self._last_result.output_paths) > 1
            else tr("success.open_file")
        )
        self.open_folder_button.setText(tr("success.open_folder"))
        self.step_asr.title.setText(tr("progress.asr"))
        self.step_translate.title.setText(tr("progress.translate"))
        self.step_write.title.setText(tr("progress.write"))
        self._refresh_labels()
        self._refresh_combo_labels()
        self._on_region_changed(self.state.settings.region, emit=False)
        self._on_content_changed(self.state.settings.output_mode, emit=False)
        self._on_format_changed(self.state.settings.subtitle_format, emit=False)
        self._update_model_details()
        if self._media:
            self._apply_media_text()
        self.progress_title.setText(tr("progress.title"))
        if self._busy:
            self.progress_note.setText(self._last_message)
        self._update_run_state()

    def _refresh_labels(self) -> None:
        region_labels = {r.key: tr(f"region.{r.key}.short") for r in REGIONS}
        self.region_segment.set_labels(region_labels)
        mode_labels = {m.key: tr(f"content.{m.key}") for m in OUTPUT_MODES}
        self.content_segment.set_labels(mode_labels)
        self.format_segment.set_labels({f.key: f.label for f in SUBTITLE_FORMATS})

    def _refresh_combo_labels(self) -> None:
        for combo, languages in ((self.source_combo, SOURCE_LANGUAGES), (self.target_combo, TARGET_LANGUAGES)):
            current = combo.currentData()
            combo.blockSignals(True)
            for index, lang in enumerate(languages):
                if index < combo.count():
                    combo.setItemText(index, tr(f"lang.{lang.code}"))
            if current is not None:
                combo.setCurrentIndex(combo.findData(current))
            combo.blockSignals(False)

    # ----------------------------------------------------------------- state
    def _sync_from_state(self, field: str) -> None:
        settings = self.state.settings
        widgets = [
            self.region_segment,
            self.source_combo,
            self.target_combo,
            self.content_segment,
            self.asr_combo,
            self.mt_combo,
            self.format_segment,
        ]
        for widget in widgets:
            widget.blockSignals(True)
        try:
            self._populate_combos_if_needed()
            self.region_segment.set_value(settings.region)
            self.source_combo.setCurrentIndex(max(0, self.source_combo.findData(settings.source_language)))
            self.target_combo.setCurrentIndex(max(0, self.target_combo.findData(settings.target_language)))
            self.content_segment.set_value(settings.output_mode)
            self.asr_combo.setCurrentIndex(max(0, self.asr_combo.findData(settings.asr_model)))
            self.mt_combo.setCurrentIndex(max(0, self.mt_combo.findData(settings.translation_model)))
            self.format_segment.set_value(settings.subtitle_format)
        finally:
            for widget in widgets:
                widget.blockSignals(False)
        self._refresh_labels()
        self._on_region_changed(settings.region, emit=False)
        self._on_content_changed(settings.output_mode, emit=False)
        self._on_format_changed(settings.subtitle_format, emit=False)
        self._update_model_details()
        self._update_run_state()

    def _populate_combos_if_needed(self) -> None:
        if self.source_combo.count() == 0:
            for lang in SOURCE_LANGUAGES:
                self.source_combo.addItem(tr(f"lang.{lang.code}"), lang.code)
        if self.target_combo.count() == 0:
            for lang in TARGET_LANGUAGES:
                self.target_combo.addItem(tr(f"lang.{lang.code}"), lang.code)
        if self.asr_combo.count() == 0:
            for model in ASR_MODELS:
                self.asr_combo.addItem(model.label, model.key)
        if self.mt_combo.count() == 0:
            for model in TRANSLATION_MODELS:
                self.mt_combo.addItem(model.label, model.key)

    def _update_model_details(self) -> None:
        asr_key = self.asr_combo.currentData() or self.state.settings.asr_model
        mt_key = self.mt_combo.currentData() or self.state.settings.translation_model
        asr_tagline, asr_desc = _ASR_DETAIL.get(asr_key, ("", ""))
        mt_tagline, mt_desc = _MT_DETAIL.get(mt_key, ("", ""))
        model = ASR_MODEL_BY_KEY.get(asr_key)
        badge = f" · {tr('model.latest')}" if model and model.badge else ""
        self.asr_detail.setText(f"{tr(asr_tagline)}{badge}" if asr_tagline else "")
        self.asr_detail.setToolTip(tr(asr_desc) if asr_desc else "")
        self.mt_detail.setText(tr(mt_tagline) if mt_tagline else "")
        self.mt_detail.setToolTip(tr(mt_desc) if mt_desc else "")

    def _update_run_state(self) -> None:
        if self._busy:
            return
        has_key = self.state.has_api_key()
        has_video = self._video_path is not None
        self.key_warning.setVisible(not has_key)
        self.key_warning.setText(tr("run.need_key") if not has_key else "")
        self.run_button.setEnabled(has_video)
        self.header_run_button.setEnabled(has_video and not self._busy)
        self.header_run_button.setText(tr("run.start") if not self._busy else tr("progress.running"))
        self.header_key_hint.setVisible(has_video and not has_key and not self._busy)

    def _on_region_changed(self, key: str, emit: bool = True) -> None:
        if emit:
            self.state.update(region=key)
        self.region_pill.setText(tr(f"region.{key}.short"))
        self._update_run_state()

    def _on_source_changed(self, _index: int) -> None:
        value = self.source_combo.currentData()
        if value:
            self.state.update(source_language=value)

    def _on_target_changed(self, _index: int) -> None:
        value = self.target_combo.currentData()
        if value:
            self.state.update(target_language=value)

    def _on_asr_changed(self, _index: int) -> None:
        value = self.asr_combo.currentData()
        if value:
            self.state.update(asr_model=value)
            self._update_model_details()

    def _on_mt_changed(self, _index: int) -> None:
        value = self.mt_combo.currentData()
        if value:
            self.state.update(translation_model=value)
            self._update_model_details()

    def _on_content_changed(self, key: str, emit: bool = True) -> None:
        mode = OUTPUT_MODE_BY_KEY.get(key)
        if not mode:
            return
        if emit:
            self.state.update(output_mode=key)
        needs_translation = key in ("translated", "bilingual")
        self.target_combo.setEnabled(needs_translation)
        self.mt_combo.setEnabled(needs_translation)
        self.content_hint.setText(tr(f"content.{key}_hint"))
        self.content_hint.setStyleSheet("" if needs_translation else "color: #B25000;")

    def _on_format_changed(self, key: str, emit: bool = True) -> None:
        fmt = SUBTITLE_FORMAT_BY_KEY.get(key)
        if not fmt:
            return
        if emit:
            self.state.update(subtitle_format=key)
        self.format_hint.setText(tr(f"format.{key}.desc"))

    # ---------------------------------------------------------------- media
    def _choose_video(self) -> None:
        if self._busy:
            return
        initial = QStandardPaths.writableLocation(QStandardPaths.StandardLocation.MoviesLocation)
        if not initial:
            initial = str(Path.home())
        filters = f"{tr('file_dialog.video_filter')};;{tr('file_dialog.all_files')}"
        path, _ = QFileDialog.getOpenFileName(self, tr("video.choose"), initial, filters)
        if path:
            self._load_video(path)

    def _load_video(self, path_value: str) -> None:
        if self._busy:
            return
        path = Path(path_value)
        if path.suffix.lower() not in VIDEO_EXTENSIONS:
            self._show_error(tr("error.ffmpeg_no_stream"))
            return
        QApplication.setOverrideCursor(Qt.CursorShape.WaitCursor)
        try:
            ffmpeg = resolve_ffmpeg(self.state.settings.ffmpeg_path)
            media = probe_media(ffmpeg.ffmpeg, path)
            if not media.has_audio:
                raise AppError(tr("video.no_audio"))
            thumb = None
            if self._thumb_dir is not None:
                thumb = make_thumbnail(
                    ffmpeg.ffmpeg,
                    path,
                    self._thumb_dir / f"thumb-{uuid.uuid4().hex[:10]}.jpg",
                    media.duration_ms,
                )
        except AppError as exc:
            QApplication.restoreOverrideCursor()
            self._show_error(exc.user_message)
            return
        finally:
            if QApplication.overrideCursor() is not None:
                QApplication.restoreOverrideCursor()
        self._video_path = path
        self._media = media
        pixmap = QPixmap(str(thumb)) if thumb else None
        self.file_card.set_file(path.name, "", pixmap)
        self._apply_media_text()
        self.video_stack.setCurrentWidget(self.file_card)
        self._update_run_state()

    def _apply_media_text(self) -> None:
        if not self._media or not self._video_path:
            return
        container = self._video_path.suffix.lstrip(".").upper() or "VIDEO"
        resolution = (
            f"{self._media.width}×{self._media.height}"
            if self._media.width and self._media.height
            else tr("video.no_resolution")
        )
        text = tr(
            "video.meta",
            container=container,
            duration=format_duration(self._media.duration_ms),
            resolution=resolution,
        )
        text = f"{text} · {format_size(self._media.size_bytes)}"
        self.file_card.set_file(self._video_path.name, text, self.file_card.thumbnail._pixmap)

    def _remove_video(self) -> None:
        if self._busy:
            return
        self._video_path = None
        self._media = None
        self.video_stack.setCurrentWidget(self.drop_zone)
        self._update_run_state()

    # ------------------------------------------------------------------ run
    def _start_run(self) -> None:
        if self._busy:
            return
        if self._video_path is None:
            self._show_error(tr("error.no_video"))
            return
        settings = self.state.settings
        if not self.state.has_api_key(settings.region):
            self._show_error(tr("error.no_key", region=tr(f"region.{settings.region}.short")))
            return
        mode = OUTPUT_MODE_BY_KEY.get(settings.output_mode)
        if mode is None:
            return
        needs_translation = mode.key in ("translated", "bilingual")
        source = self.source_combo.currentData()
        target = self.target_combo.currentData()
        if needs_translation and source and source != "auto" and source == target:
            self._show_error(tr("error.same_language"))
            return
        try:
            api_key = self.state.api_key(settings.region)
        except Exception as exc:
            self._show_error(tr("error.secret", message=str(exc)))
            return
        options = PipelineOptions(
            video_path=self._video_path,
            region=settings.region,
            api_key=api_key,
            asr_model=settings.asr_model,
            translation_model=settings.translation_model,
            source_language=settings.source_language,
            target_language=settings.target_language,
            output_mode=settings.output_mode,
            subtitle_format=settings.subtitle_format,
            output_dir=Path(settings.output_dir) if settings.output_dir else None,
            ffmpeg_path=settings.ffmpeg_path,
        )
        self._cancel_event = threading.Event()
        self._worker = PipelineWorker(options, self._cancel_event)
        self._worker.progressed.connect(self._on_progress)
        self._worker.succeeded.connect(self._on_success)
        self._worker.failed.connect(self._on_failed)
        self._worker.cancelled.connect(self._on_cancelled)
        self._set_busy(True)
        self.run_card.show()
        self.idle_box.hide()
        self.progress_box.show()
        self.result_row.hide()
        self.progress_bar.setValue(0)
        self.progress_percent.setText("0%")
        self.progress_title.setText(tr("progress.title"))
        self.progress_note.setText("")
        self.header_spinner.start()
        self.step_asr.set_state("active", tr("progress.extracting"))
        if needs_translation:
            self.step_translate.set_state("pending")
        else:
            self.step_translate.set_state("skipped", tr("progress.translate_skipped"))
        self.step_write.set_state("pending")
        self.cancel_button.setEnabled(True)
        self.cancel_button.setText(tr("run.cancel"))
        self._last_message = ""
        self._stage_details = {"asr": "", "translate": "", "write": ""}
        self._worker.start()
        QTimer.singleShot(80, self._scroll_to_progress)

    def _scroll_to_progress(self) -> None:
        bar = self.scroll_area.verticalScrollBar()
        bar.setValue(bar.maximum())

    def _set_busy(self, busy: bool) -> None:
        self._busy = busy
        self.settings_card.setEnabled(not busy)
        self.video_card.setEnabled(not busy)
        self.run_button.setEnabled(not busy and self._video_path is not None and self.state.has_api_key())
        self.header_run_button.setEnabled(not busy and self._video_path is not None)
        self.header_run_button.setText(tr("progress.running") if busy else tr("run.start"))
        self.header_key_hint.setVisible(
            not busy and self._video_path is not None and not self.state.has_api_key()
        )
        self.cancel_button.setVisible(busy)

    def _on_progress(self, stage: str, percent: int, message: str) -> None:
        self._last_message = message
        self.progress_percent.setText(f"{percent}%")
        self.progress_bar.setValue(percent)
        self.progress_note.setText(message)
        if stage == "asr":
            if percent >= 58:
                self.step_asr.set_state("done", message)
            else:
                self.step_asr.set_state("active", message)
        elif stage == "translate":
            if self.state.settings.output_mode == "original":
                self.step_translate.set_state("skipped", message)
            elif percent >= 94:
                self.step_translate.set_state("done", message)
            else:
                self.step_translate.set_state("active", message)
        elif stage == "write":
            self.step_asr.set_state("done", self._stage_details.get("asr", ""))
            if self.state.settings.output_mode == "original":
                self.step_translate.set_state("skipped", tr("progress.translate_skipped"))
            else:
                self.step_translate.set_state("done", self._stage_details.get("translate", ""))
            if percent >= 100:
                self.step_write.set_state("done", message)
            else:
                self.step_write.set_state("active", message)
        self._stage_details[stage] = message

    def _on_success(self, result: object) -> None:
        if not isinstance(result, PipelineResult):
            return
        self._last_result = result
        self._set_busy(False)
        self.header_spinner.stop()
        self.cancel_button.hide()
        self.progress_title.setText(tr("success.title"))
        if result.fallback_used:
            note_key = "success.fallback_body"
        elif len(result.output_paths) > 1:
            note_key = "success.two_files"
        else:
            note_key = "success.body"
        self.progress_note.setText(tr(note_key, count=result.cue_count))
        self.progress_percent.setText("100%")
        self.progress_bar.setValue(100)
        self.step_asr.set_state("done", self._stage_details.get("asr", tr("progress.done")))
        if result.output_mode == "original":
            self.step_translate.set_state("skipped", tr("progress.translate_skipped"))
        else:
            self.step_translate.set_state("done", self._stage_details.get("translate", tr("progress.done")))
        self.step_write.set_state("done", tr("progress.done"))
        self.result_path.setText("\n".join(str(path) for path in result.output_paths))
        self.open_file_button.setText(
            tr("success.open_translation") if len(result.output_paths) > 1 else tr("success.open_file")
        )
        self.result_row.show()
        QTimer.singleShot(220, self._show_completion)

    def _show_completion(self) -> None:
        if not self._last_result:
            return
        result = self._last_result
        dialog = CompletionDialog(
            result.output_paths,
            result.cue_count,
            on_open_folder=lambda: self._open_last_folder(),
            on_open_file=lambda: self._open_last_file(),
            fallback_used=result.fallback_used,
            parent=self.window(),
        )
        dialog.exec()

    def _on_failed(self, message: str) -> None:
        self._set_busy(False)
        self.header_spinner.stop()
        self.cancel_button.hide()
        if self._worker:
            self._worker = None
        dialog = ErrorDialog(message, on_settings=lambda: self.open_settings.emit(), parent=self.window())
        dialog.exec()
        self._reset_to_idle()

    def _on_cancelled(self) -> None:
        self._set_busy(False)
        self.header_spinner.stop()
        self.cancel_button.hide()
        self._reset_to_idle()
        self.idle_hint.setText(tr("error.cancelled"))
        QTimer.singleShot(2600, self._restore_idle_hint)

    def _restore_idle_hint(self) -> None:
        if not self._busy:
            self.idle_hint.setText(tr("run.hint"))

    def _cancel_run(self) -> None:
        if self._cancel_event:
            self._cancel_event.set()
        self.cancel_button.setEnabled(False)
        self.cancel_button.setText(tr("run.cancelling"))

    def _reset_to_idle(self) -> None:
        if self._busy:
            return
        self.progress_box.hide()
        self.run_card.hide()
        self.idle_box.show()
        self.result_row.hide()
        self.header_spinner.stop()
        self.progress_bar.setValue(0)
        self.progress_percent.setText("0%")
        self.progress_note.setText("")
        self.progress_title.setText(tr("progress.title"))
        self.step_asr.set_state("pending")
        self.step_translate.set_state("pending")
        self.step_write.set_state("pending")
        self.cancel_button.setVisible(False)
        self._worker = None
        self._last_message = ""
        self._update_run_state()

    # --------------------------------------------------------------- helpers
    def _open_last_folder(self) -> None:
        if not self._last_result:
            return
        try:
            if len(self._last_result.output_paths) == 1:
                reveal_file(self._last_result.output_path)
            else:
                open_folder(self._last_result.output_path.parent)
        except Exception:
            self._show_error(tr("error.open_folder"))

    def _open_last_file(self) -> None:
        if not self._last_result:
            return
        # In two-file mode, the last path is the translated subtitle.
        QDesktopServices.openUrl(QUrl.fromLocalFile(str(self._last_result.output_paths[-1])))

    def _show_error(self, message: str) -> None:
        dialog = ErrorDialog(message, on_settings=lambda: self.open_settings.emit(), parent=self.window())
        dialog.exec()

    def cancel_and_wait(self, timeout_ms: int = 4000) -> None:
        if self._cancel_event:
            self._cancel_event.set()
        if self._worker and self._worker.isRunning():
            if not self._worker.wait(timeout_ms):
                # Last-resort app shutdown: an HTTP read may be blocked.
                self._worker.terminate()
                self._worker.wait(1000)

    def is_busy(self) -> bool:
        return self._busy

    def cleanup(self) -> None:
        self.cancel_and_wait()
        if self._thumb_dir is not None:
            shutil.rmtree(self._thumb_dir, ignore_errors=True)
