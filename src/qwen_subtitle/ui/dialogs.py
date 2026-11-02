"""Custom modal dialogs in the same visual language as the main window."""

from __future__ import annotations

from pathlib import Path
from typing import Callable

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QDialog,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QVBoxLayout,
    QWidget,
)

from qwen_subtitle.i18n import tr
from qwen_subtitle.ui.theme import shadow
from qwen_subtitle.ui.widgets import make_label


class _BaseDialog(QDialog):
    def __init__(self, parent: QWidget | None = None, width: int = 460) -> None:
        super().__init__(parent)
        self.setModal(True)
        self.setWindowFlags(Qt.WindowType.Dialog | Qt.WindowType.FramelessWindowHint)
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground, True)
        self.setFixedWidth(width)
        outer = QVBoxLayout(self)
        outer.setContentsMargins(26, 26, 26, 26)
        self.card = QWidget()
        self.card.setObjectName("DialogCard")
        outer.addWidget(self.card)
        shadow(self.card, 48, 18, 60)
        self.body = QVBoxLayout(self.card)
        self.body.setContentsMargins(28, 26, 28, 22)
        self.body.setSpacing(12)

    def showEvent(self, event) -> None:  # noqa: N802
        super().showEvent(event)
        parent = self.parentWidget()
        if parent:
            center = parent.window().frameGeometry().center()
            self.move(center.x() - self.width() // 2, center.y() - self.height() // 2)

    def mousePressEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton:
            handle = self.windowHandle()
            if handle:
                handle.startSystemMove()
        super().mousePressEvent(event)


class CompletionDialog(_BaseDialog):
    def __init__(
        self,
        output_paths: tuple[Path, ...] | list[Path],
        cue_count: int,
        on_open_folder: Callable[[], None],
        on_open_file: Callable[[], None],
        fallback_used: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, width=470)
        self._on_open_folder = on_open_folder
        self._on_open_file = on_open_file
        path_list = tuple(output_paths)

        icon = QLabel("✓")
        icon.setObjectName("SuccessIcon")
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)

        title = make_label(tr("success.title"), "DialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.body.addWidget(title)

        if fallback_used:
            body_key = "success.fallback_body"
        elif len(path_list) > 1:
            body_key = "success.two_files"
        else:
            body_key = "success.body"
        body = make_label(tr(body_key, count=cue_count), "DialogBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.body.addWidget(body)

        path_label = make_label("\n".join(str(path) for path in path_list), "PathBox")
        path_label.setWordWrap(True)
        path_label.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.addWidget(path_label)
        self.body.addSpacing(6)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        close_button = QPushButton(tr("success.close"))
        close_button.setObjectName("Secondary")
        close_button.clicked.connect(self.accept)
        buttons.addWidget(close_button)
        open_file = QPushButton(
            tr("success.open_translation") if len(path_list) > 1 else tr("success.open_file")
        )
        open_file.setObjectName("Secondary")
        open_file.clicked.connect(self._open_file)
        buttons.addWidget(open_file)
        open_folder = QPushButton(tr("success.open_folder"))
        open_folder.setObjectName("Primary")
        open_folder.setDefault(True)
        open_folder.clicked.connect(self._open_folder_clicked)
        buttons.addWidget(open_folder)
        self.body.addLayout(buttons)

    def _open_folder_clicked(self) -> None:
        self._on_open_folder()
        self.accept()

    def _open_file(self) -> None:
        self._on_open_file()
        self.accept()


class ErrorDialog(_BaseDialog):
    def __init__(
        self,
        message: str,
        *,
        on_settings: Callable[[], None] | None = None,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, width=440)
        icon = QLabel("!")
        icon.setObjectName("ErrorIcon")
        icon.setFixedSize(56, 56)
        icon.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.body.addWidget(icon, 0, Qt.AlignmentFlag.AlignHCenter)

        title = make_label(tr("error.title"), "DialogTitle")
        title.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.body.addWidget(title)

        body = make_label(message, "DialogBody")
        body.setWordWrap(True)
        body.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        body.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.body.addWidget(body)
        self.body.addSpacing(6)

        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        if on_settings:
            settings = QPushButton(tr("error.open_settings"))
            settings.setObjectName("Secondary")
            settings.clicked.connect(lambda: (self.accept(), on_settings()))
            buttons.addWidget(settings)
        close = QPushButton(tr("error.close"))
        close.setObjectName("Primary")
        close.setDefault(True)
        close.clicked.connect(self.accept)
        buttons.addWidget(close)
        self.body.addLayout(buttons)


class ConfirmDialog(_BaseDialog):
    def __init__(
        self,
        title: str,
        message: str,
        *,
        confirm_text: str | None = None,
        destructive: bool = False,
        parent: QWidget | None = None,
    ) -> None:
        super().__init__(parent, width=430)
        self.confirmed = False
        title_label = make_label(title, "DialogTitle")
        self.body.addWidget(title_label)
        body = make_label(message, "DialogBody")
        body.setWordWrap(True)
        self.body.addWidget(body)
        self.body.addSpacing(8)
        buttons = QHBoxLayout()
        buttons.setSpacing(8)
        buttons.addStretch(1)
        cancel = QPushButton(tr("common.cancel"))
        cancel.setObjectName("Secondary")
        cancel.clicked.connect(self.reject)
        buttons.addWidget(cancel)
        confirm = QPushButton(confirm_text or tr("common.confirm"))
        confirm.setObjectName("DangerSolid" if destructive else "Primary")
        confirm.setDefault(True)
        confirm.clicked.connect(self._confirm)
        buttons.addWidget(confirm)
        self.body.addLayout(buttons)

    def _confirm(self) -> None:
        self.confirmed = True
        self.accept()
