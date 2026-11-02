"""Frameless main window with a macOS-inspired title bar and sidebar."""

from __future__ import annotations

from PySide6.QtCore import QSize, Qt
from PySide6.QtWidgets import (
    QButtonGroup,
    QComboBox,
    QFrame,
    QHBoxLayout,
    QLabel,
    QMainWindow,
    QPushButton,
    QSizeGrip,
    QStackedWidget,
    QVBoxLayout,
    QWidget,
)

from qwen_subtitle.constants import APP_NAME, UI_LANGUAGES, VERSION
from qwen_subtitle.i18n import tr, ui_language_label
from qwen_subtitle.ui.dialogs import ConfirmDialog, ErrorDialog
from qwen_subtitle.ui.icons import app_icon, icon
from qwen_subtitle.ui.pages.about import AboutPage
from qwen_subtitle.ui.pages.settings import SettingsPage
from qwen_subtitle.ui.pages.workbench import WorkbenchPage
from qwen_subtitle.ui.state import AppState
from qwen_subtitle.ui.theme import SECONDARY, shadow
from qwen_subtitle.ui.widgets import make_label

_WINDOW_MARGIN = 14


class TitleBar(QWidget):
    def __init__(self, window: "MainWindow") -> None:
        super().__init__(window)
        self.setObjectName("TitleBar")
        self.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.setFixedHeight(46)
        self._window = window
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 0, 0, 0)
        layout.setSpacing(0)

        # Language switcher is deliberately at the far left: a user who cannot
        # read the current UI language must find it without entering Settings.
        self.language_box = QWidget()
        self.language_box.setObjectName("LanguageBox")
        language_layout = QHBoxLayout(self.language_box)
        language_layout.setContentsMargins(7, 2, 3, 2)
        language_layout.setSpacing(3)
        globe = QLabel()
        globe.setPixmap(icon("globe", "#5F5F64", 14).pixmap(14, 14))
        globe.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        language_layout.addWidget(globe)
        self.language_combo = QComboBox()
        self.language_combo.setObjectName("LanguageCombo")
        self.language_combo.setCursor(Qt.CursorShape.PointingHandCursor)
        self.language_combo.setFocusPolicy(Qt.FocusPolicy.StrongFocus)
        self.language_combo.setFixedWidth(92)
        for code in UI_LANGUAGES:
            self.language_combo.addItem(ui_language_label(code), code)
        current = window.state.settings.ui_language
        self.language_combo.setCurrentIndex(max(0, self.language_combo.findData(current)))
        self.language_combo.currentIndexChanged.connect(self._language_selected)
        language_layout.addWidget(self.language_combo)
        layout.addWidget(self.language_box, 0, Qt.AlignmentFlag.AlignVCenter)
        layout.addStretch(1)

        self.title = make_label("", "WindowTitle")
        self.title.setAttribute(Qt.WidgetAttribute.WA_TransparentForMouseEvents, True)
        layout.addWidget(self.title)
        layout.addStretch(1)

        # Windows convention: minimise/maximise/close are on the right.
        self.min_button = self._window_button("WindowMin", "－", window.showMinimized, "titlebar.minimize")
        self.max_button = self._window_button("WindowMax", "□", window.toggle_maximized, "titlebar.maximize")
        self.close_button = self._window_button("WindowClose", "×", window.close, "titlebar.close")
        controls = QHBoxLayout()
        controls.setSpacing(0)
        controls.addWidget(self.min_button)
        controls.addWidget(self.max_button)
        controls.addWidget(self.close_button)
        layout.addLayout(controls)

    def _window_button(self, object_name: str, text: str, slot, tooltip_key: str) -> QPushButton:
        button = QPushButton(text)
        button.setObjectName(object_name)
        button.setFixedSize(46, 46)
        button.setCursor(Qt.CursorShape.PointingHandCursor)
        button.setFocusPolicy(Qt.FocusPolicy.NoFocus)
        button.setProperty("tooltipKey", tooltip_key)
        button.setToolTip(tr(tooltip_key))
        button.clicked.connect(slot)
        return button

    def _language_selected(self, _index: int) -> None:
        code = self.language_combo.currentData()
        if code and code != self._window.state.settings.ui_language:
            self._window.change_ui_language(str(code))

    def set_maximized(self, maximized: bool) -> None:
        self.max_button.setText("❐" if maximized else "□")

    def retranslate(self) -> None:
        for button in (self.close_button, self.min_button, self.max_button):
            key = button.property("tooltipKey")
            if key:
                button.setToolTip(tr(str(key)))
        self.language_combo.blockSignals(True)
        self.language_combo.setCurrentIndex(
            max(0, self.language_combo.findData(self._window.state.settings.ui_language))
        )
        self.language_combo.blockSignals(False)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.window().windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)

    def mouseDoubleClickEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            self._window.toggle_maximized()
        super().mouseDoubleClickEvent(event)


class MainWindow(QMainWindow):
    def __init__(self, state: AppState) -> None:
        super().__init__()
        self.state = state
        self.setWindowTitle(APP_NAME)
        self.setWindowIcon(app_icon())
        self.setWindowFlags(Qt.WindowType.FramelessWindowHint | Qt.WindowType.Window)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.resize(1180, 800)
        self.setMinimumSize(1024, 700)

        central = QWidget()
        central.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setCentralWidget(central)
        self.outer = QVBoxLayout(central)
        self.outer.setContentsMargins(_WINDOW_MARGIN, _WINDOW_MARGIN, _WINDOW_MARGIN, _WINDOW_MARGIN)
        self.shell = QWidget()
        self.shell.setObjectName("WindowShell")
        self.shell.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self._shell_shadow = shadow(self.shell, 46, 16, 62)
        self.outer.addWidget(self.shell)

        shell_layout = QVBoxLayout(self.shell)
        shell_layout.setContentsMargins(0, 0, 0, 0)
        shell_layout.setSpacing(0)
        self.title_bar = TitleBar(self)
        shell_layout.addWidget(self.title_bar)

        body = QWidget()
        body_layout = QHBoxLayout(body)
        body_layout.setContentsMargins(0, 0, 0, 0)
        body_layout.setSpacing(0)
        body_layout.addWidget(self._build_sidebar())
        self.stack = QStackedWidget()
        self.stack.setObjectName("Content")
        self.stack.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.workbench = WorkbenchPage(state)
        self.settings_page = SettingsPage(state)
        self.about_page = AboutPage()
        self.stack.addWidget(self.workbench)
        self.stack.addWidget(self.settings_page)
        self.stack.addWidget(self.about_page)
        body_layout.addWidget(self.stack, 1)
        shell_layout.addWidget(body, 1)

        self.workbench.open_settings.connect(lambda: self.show_page("settings"))
        self.state.language_changed.connect(self._language_changed)
        self.state.settings_changed.connect(self._settings_changed)
        self.show_page("workbench")
        self.retranslate()

        self.size_grip = QSizeGrip(self.shell)
        self.size_grip.setFixedSize(18, 18)
        self.size_grip.setStyleSheet("background: transparent;")
        self.size_grip.raise_()

    def _build_sidebar(self) -> QWidget:
        self.sidebar = QWidget()
        self.sidebar.setObjectName("Sidebar")
        self.sidebar.setAttribute(Qt.WidgetAttribute.WA_StyledBackground, True)
        self.sidebar.setFixedWidth(208)
        layout = QVBoxLayout(self.sidebar)
        layout.setContentsMargins(16, 18, 16, 16)
        layout.setSpacing(5)

        brand = QHBoxLayout()
        brand.setSpacing(9)
        logo = QLabel()
        logo.setPixmap(app_icon().pixmap(30, 30))
        logo.setFixedSize(30, 30)
        brand.addWidget(logo)
        brand_text = QVBoxLayout()
        brand_text.setSpacing(0)
        self.brand_name = make_label("", "BrandName")
        self.brand_sub = make_label("SUBTITLE STUDIO", "BrandSub")
        brand_text.addWidget(self.brand_name)
        brand_text.addWidget(self.brand_sub)
        brand.addLayout(brand_text)
        brand.addStretch(1)
        layout.addLayout(brand)
        layout.addSpacing(18)

        self.nav_group = QButtonGroup(self)
        self.nav_group.setExclusive(True)
        self.nav_buttons: dict[str, QPushButton] = {}
        for key, icon_name in (
            ("workbench", "workbench"),
            ("settings", "settings"),
            ("about", "info"),
        ):
            button = QPushButton()
            button.setObjectName("NavButton")
            button.setCheckable(True)
            button.setIcon(icon(icon_name, SECONDARY, 17))
            button.setIconSize(QSize(17, 17))
            button.setFixedHeight(36)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.clicked.connect(lambda checked=False, page=key: self.show_page(page))
            self.nav_group.addButton(button)
            self.nav_buttons[key] = button
            layout.addWidget(button)
        layout.addStretch(1)

        self.privacy_box = QFrame()
        self.privacy_box.setObjectName("PrivacyBox")
        privacy_layout = QVBoxLayout(self.privacy_box)
        privacy_layout.setContentsMargins(10, 9, 10, 9)
        privacy_layout.setSpacing(3)
        top = QHBoxLayout()
        top.setSpacing(6)
        lock = QLabel()
        lock.setPixmap(icon("lock", "#6E6E73", 12).pixmap(12, 12))
        top.addWidget(lock)
        self.privacy_title = make_label("", "Tiny")
        self.privacy_title.setStyleSheet("color: #4A4A4F; font-size: 10px; font-weight: 600;")
        top.addWidget(self.privacy_title, 1)
        privacy_layout.addLayout(top)
        self.privacy_hint = make_label("", "Tiny")
        self.privacy_hint.setStyleSheet("font-size: 9px;")
        self.privacy_hint.setWordWrap(True)
        privacy_layout.addWidget(self.privacy_hint)
        layout.addWidget(self.privacy_box)
        layout.addSpacing(8)
        self.version_label = make_label("", "Tiny")
        self.version_label.setStyleSheet("font-size: 9px;")
        layout.addWidget(self.version_label)
        return self.sidebar

    def show_page(self, key: str) -> None:
        pages = {
            "workbench": self.workbench,
            "settings": self.settings_page,
            "about": self.about_page,
        }
        page = pages.get(key)
        if page is None:
            return
        self.stack.setCurrentWidget(page)
        for name, button in self.nav_buttons.items():
            button.blockSignals(True)
            button.setChecked(name == key)
            button.blockSignals(False)
        if key == "settings":
            self.settings_page._sync_from_state("")
        elif key == "workbench":
            self.workbench._update_run_state()

    def change_ui_language(self, code: str) -> None:
        if code == self.state.settings.ui_language:
            return
        try:
            self.state.update(ui_language=code)
        except OSError as exc:
            ErrorDialog(tr("error.generic", message=str(exc)), parent=self).exec()
            self.retranslate()

    def retranslate(self) -> None:
        self.setWindowTitle(tr("common.app_name"))
        self.title_bar.title.setText(tr("common.app_name"))
        self.title_bar.retranslate()
        self.brand_name.setText(tr("common.app_name"))
        self.nav_buttons["workbench"].setText(tr("nav.workbench"))
        self.nav_buttons["settings"].setText(tr("nav.settings"))
        self.nav_buttons["about"].setText(tr("nav.about"))
        self.privacy_title.setText(tr("sidebar.privacy"))
        self.privacy_hint.setText(tr("sidebar.privacy_hint"))
        self.version_label.setText(f"v{VERSION}")
        self.workbench.retranslate()
        self.settings_page.retranslate()
        self.about_page.retranslate()

    def _language_changed(self, _language: str) -> None:
        self.retranslate()

    def _settings_changed(self, field: str) -> None:
        if field == "region":
            self.workbench._update_run_state()

    def toggle_maximized(self) -> None:
        if self.isMaximized():
            self.showNormal()
        else:
            self.showMaximized()
        self._apply_window_state()

    def _apply_window_state(self) -> None:
        if not hasattr(self, "outer"):
            return
        maximized = self.isMaximized()
        margin = 0 if maximized else _WINDOW_MARGIN
        self.outer.setContentsMargins(margin, margin, margin, margin)
        self.shell.setProperty("maximized", maximized)
        self.shell.style().unpolish(self.shell)
        self.shell.style().polish(self.shell)
        if hasattr(self, "_shell_shadow"):
            self._shell_shadow.setEnabled(not maximized)
        if hasattr(self, "size_grip"):
            self.size_grip.setVisible(not maximized)
            self.size_grip.raise_()
        if hasattr(self, "title_bar"):
            self.title_bar.set_maximized(maximized)

    def changeEvent(self, event) -> None:  # noqa: N802
        super().changeEvent(event)
        if event.type() == event.Type.WindowStateChange:
            self._apply_window_state()

    def resizeEvent(self, event) -> None:  # noqa: N802
        super().resizeEvent(event)
        if hasattr(self, "size_grip"):
            self.size_grip.move(self.shell.width() - 20, self.shell.height() - 20)

    def closeEvent(self, event) -> None:  # noqa: N802
        if self.workbench.is_busy():
            dialog = ConfirmDialog(
                tr("dialog.quit.title"),
                tr("dialog.quit.body"),
                confirm_text=tr("common.close"),
                parent=self,
            )
            if not (dialog.exec() and dialog.confirmed):
                event.ignore()
                return
        self.workbench.cleanup()
        self.settings_page.cleanup()
        event.accept()
