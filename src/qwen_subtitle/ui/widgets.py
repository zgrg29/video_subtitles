"""Reusable Apple-inspired widgets."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtCore import QPointF, QRectF, QSize, Qt, QTimer, Signal
from PySide6.QtGui import (
    QColor,
    QPainter,
    QPainterPath,
    QPen,
    QPixmap,
)
from PySide6.QtWidgets import (
    QButtonGroup,
    QFrame,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSizePolicy,
    QVBoxLayout,
    QWidget,
)

from qwen_subtitle.ui import icons
from qwen_subtitle.ui.theme import ACCENT, SECONDARY


def make_label(text: str = "", object_name: str = "Body") -> QLabel:
    label = QLabel(text)
    label.setObjectName(object_name)
    label.setTextInteractionFlags(Qt.TextInteractionFlag.NoTextInteraction)
    return label


def divider() -> QFrame:
    line = QFrame()
    line.setObjectName("Divider")
    line.setFixedHeight(1)
    return line


class Card(QFrame):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Card")


class SegmentedControl(QFrame):
    changed = Signal(str)

    def __init__(self, options: list[tuple[str, str]] | None = None, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Segmented")
        self._layout = QHBoxLayout(self)
        self._layout.setContentsMargins(3, 3, 3, 3)
        self._layout.setSpacing(2)
        self._buttons: dict[str, QPushButton] = {}
        self._group = QButtonGroup(self)
        self._group.setExclusive(True)
        self._current = ""
        self.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
        self.setFixedHeight(32)
        if options:
            self.set_options(options)

    def set_options(self, options: list[tuple[str, str]]) -> None:
        for button in self._buttons.values():
            self._group.removeButton(button)
            button.deleteLater()
        self._buttons.clear()
        while self._layout.count():
            item = self._layout.takeAt(0)
            if item.widget():
                item.widget().deleteLater()
        for key, label in options:
            button = QPushButton(label)
            button.setObjectName("SegmentButton")
            button.setCheckable(True)
            button.setCursor(Qt.CursorShape.PointingHandCursor)
            button.setSizePolicy(QSizePolicy.Policy.Expanding, QSizePolicy.Policy.Fixed)
            button.clicked.connect(lambda checked=False, value=key: self._on_clicked(value))
            self._group.addButton(button)
            self._layout.addWidget(button)
            self._buttons[key] = button
        if options:
            first = options[0][0]
            if self._current not in self._buttons:
                self._current = first
            self._buttons[self._current].setChecked(True)

    def _on_clicked(self, key: str) -> None:
        if key == self._current:
            return
        self._current = key
        self.changed.emit(key)

    def value(self) -> str:
        return self._current

    def set_value(self, key: str) -> None:
        if key not in self._buttons:
            return
        self._current = key
        self._buttons[key].setChecked(True)

    def set_labels(self, labels: dict[str, str]) -> None:
        for key, button in self._buttons.items():
            if key in labels:
                button.setText(labels[key])


class Spinner(QWidget):
    def __init__(self, size: int = 18, color: str = ACCENT, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._angle = 0
        self._color = QColor(color)
        self._timer = QTimer(self)
        self._timer.setInterval(16)
        self._timer.timeout.connect(self._advance)
        self.setFixedSize(size, size)
        self.hide()

    def start(self) -> None:
        self.show()
        if not self._timer.isActive():
            self._timer.start()

    def stop(self) -> None:
        self._timer.stop()
        self.hide()

    def _advance(self) -> None:
        self._angle = (self._angle + 9) % 360
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        pen = QPen(self._color, 2.2, Qt.PenStyle.SolidLine, Qt.PenCapStyle.RoundCap)
        painter.setPen(pen)
        rect = QRectF(3, 3, self.width() - 6, self.height() - 6)
        painter.drawArc(rect, int(-self._angle * 16), int(250 * 16))
        painter.end()


class RoundedThumbnail(QLabel):
    def __init__(self, width: int = 116, height: int = 66, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("Thumb")
        self.setFixedSize(width, height)
        self._pixmap: QPixmap | None = None

    def set_pixmap(self, pixmap: QPixmap | None) -> None:
        self._pixmap = pixmap
        self.update()

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
        rect = QRectF(0, 0, self.width(), self.height())
        path = QPainterPath()
        path.addRoundedRect(rect, 9, 9)
        painter.setClipPath(path)
        painter.fillPath(path, QColor("#E9E9EE"))
        if self._pixmap and not self._pixmap.isNull():
            scaled = self._pixmap.scaled(
                self.size(),
                Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                Qt.TransformationMode.SmoothTransformation,
            )
            x = (self.width() - scaled.width()) / 2
            y = (self.height() - scaled.height()) / 2
            painter.drawPixmap(int(x), int(y), scaled)
        else:
            painter.setPen(QPen(QColor("#C7C7CC"), 1.2))
            painter.drawLine(18, self.height() - 18, 34, self.height() - 34)
            painter.drawLine(34, self.height() - 34, 48, self.height() - 26)
            painter.drawLine(48, self.height() - 26, 66, self.height() - 46)
            painter.drawLine(66, self.height() - 46, self.width() - 16, self.height() - 18)
            painter.drawEllipse(QPointF(self.width() - 24, 18), 5, 5)
        painter.end()


class DropZone(QFrame):
    choose_clicked = Signal()
    file_dropped = Signal(str)

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("DropZone")
        self.setAcceptDrops(True)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMinimumHeight(112)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(20, 18, 20, 18)
        layout.setSpacing(16)

        self._icon_box = QLabel()
        self._icon_box.setFixedSize(54, 54)
        self._icon_box.setPixmap(icons.icon("film", ACCENT, 26).pixmap(26, 26))
        self._icon_box.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self._icon_box.setStyleSheet(
            "background: #EAF2FE; border-radius: 15px;"
        )
        layout.addWidget(self._icon_box)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self.title = make_label("", "Value")
        self.title.setStyleSheet("font-size: 14px;")
        self.hint = make_label("", "Muted")
        text_layout.addStretch(1)
        text_layout.addWidget(self.title)
        text_layout.addWidget(self.hint)
        text_layout.addStretch(1)
        layout.addLayout(text_layout, 1)

        self.button = QPushButton()
        self.button.setObjectName("Secondary")
        self.button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.button.clicked.connect(self.choose_clicked)
        layout.addWidget(self.button)

    def mouseReleaseEvent(self, event) -> None:  # noqa: N802
        if event.button() == Qt.MouseButton.LeftButton and self.rect().contains(event.position().toPoint()):
            self.choose_clicked.emit()
        super().mouseReleaseEvent(event)

    def dragEnterEvent(self, event) -> None:  # noqa: N802
        if event.mimeData().hasUrls():
            for url in event.mimeData().urls():
                if url.isLocalFile() and Path(url.toLocalFile()).suffix.lower() in {
                    ".mp4", ".mov", ".mkv", ".avi", ".webm", ".m4v", ".flv",
                    ".wmv", ".ts", ".mts", ".m2ts", ".mpg", ".mpeg", ".3gp",
                }:
                    event.acceptProposedAction()
                    self.setProperty("dragActive", True)
                    self.style().unpolish(self)
                    self.style().polish(self)
                    return
        event.ignore()

    def dragLeaveEvent(self, event) -> None:  # noqa: N802
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        super().dragLeaveEvent(event)

    def dropEvent(self, event) -> None:  # noqa: N802
        self.setProperty("dragActive", False)
        self.style().unpolish(self)
        self.style().polish(self)
        for url in event.mimeData().urls():
            if url.isLocalFile():
                self.file_dropped.emit(url.toLocalFile())
                event.acceptProposedAction()
                return
        event.ignore()


class FileCard(QFrame):
    change_clicked = Signal()
    remove_clicked = Signal()

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("FileCard")
        layout = QHBoxLayout(self)
        layout.setContentsMargins(10, 10, 12, 10)
        layout.setSpacing(13)

        self.thumbnail = RoundedThumbnail()
        layout.addWidget(self.thumbnail)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(4)
        self.filename = make_label("", "Value")
        self.filename.setStyleSheet("font-size: 14px;")
        self.filename.setTextInteractionFlags(Qt.TextInteractionFlag.TextSelectableByMouse)
        self.meta = make_label("", "Muted")
        text_layout.addStretch(1)
        text_layout.addWidget(self.filename)
        text_layout.addWidget(self.meta)
        text_layout.addStretch(1)
        layout.addLayout(text_layout, 1)

        self.change_button = QPushButton()
        self.change_button.setObjectName("Secondary")
        self.change_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.change_button.clicked.connect(self.change_clicked)
        layout.addWidget(self.change_button)

        self.remove_button = QPushButton()
        self.remove_button.setObjectName("Ghost")
        self.remove_button.setCursor(Qt.CursorShape.PointingHandCursor)
        self.remove_button.clicked.connect(self.remove_clicked)
        layout.addWidget(self.remove_button)

    def set_file(self, filename: str, meta: str, pixmap: QPixmap | None) -> None:
        self.filename.setText(filename)
        self.filename.setToolTip(filename)
        self.meta.setText(meta)
        self.thumbnail.set_pixmap(pixmap)


class StepRow(QWidget):
    def __init__(self, index: int, title: str, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.index = index
        self._state = "pending"
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 3, 0, 3)
        layout.setSpacing(10)

        self.circle = QLabel(str(index))
        self.circle.setObjectName("StepCircle")
        self.circle.setFixedSize(24, 24)
        self.circle.setAlignment(Qt.AlignmentFlag.AlignCenter)
        self.spinner = Spinner(18, ACCENT)
        layout.addWidget(self.circle)
        layout.addWidget(self.spinner)

        text_layout = QVBoxLayout()
        text_layout.setSpacing(1)
        self.title = make_label(title, "StepTitle")
        self.detail = make_label("", "StepDetail")
        text_layout.addWidget(self.title)
        text_layout.addWidget(self.detail)
        layout.addLayout(text_layout, 1)

    def set_state(self, state: str, detail: str = "") -> None:
        self._state = state
        self.circle.setProperty("state", state)
        self.circle.style().unpolish(self.circle)
        self.circle.style().polish(self.circle)
        if state == "active":
            self.circle.hide()
            self.spinner.start()
        else:
            self.spinner.stop()
            self.circle.show()
            symbols = {"done": "✓", "failed": "!", "skipped": "–"}
            self.circle.setText(symbols.get(state, str(self.index)))
        self.detail.setText(detail)


class IconButton(QPushButton):
    def __init__(self, icon_name: str, tooltip: str = "", size: int = 18, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self.setObjectName("IconButton")
        self.setIcon(icons.icon(icon_name, SECONDARY, size))
        self.setIconSize(QSize(size, size))
        self.setFixedSize(size + 14, size + 14)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        if tooltip:
            self.setToolTip(tooltip)


class KeyField(QWidget):
    """A line edit with a show/hide eye button."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        layout = QHBoxLayout(self)
        layout.setContentsMargins(0, 0, 0, 0)
        layout.setSpacing(0)

        from PySide6.QtWidgets import QLineEdit

        self.edit = QLineEdit()
        self.edit.setEchoMode(QLineEdit.EchoMode.Password)
        self.edit.setClearButtonEnabled(False)
        layout.addWidget(self.edit, 1)

        self.reveal = QPushButton()
        self.reveal.setObjectName("IconButton")
        self.reveal.setCheckable(True)
        self.reveal.setCursor(Qt.CursorShape.PointingHandCursor)
        self.reveal.setFixedSize(30, 30)
        self.reveal.setIcon(icons.icon("eye", SECONDARY, 17))
        self.reveal.setIconSize(QSize(17, 17))
        self.reveal.toggled.connect(self._toggle)
        layout.addWidget(self.reveal)

    def _toggle(self, visible: bool) -> None:
        from PySide6.QtWidgets import QLineEdit

        self.edit.setEchoMode(QLineEdit.EchoMode.Normal if visible else QLineEdit.EchoMode.Password)
        self.reveal.setIcon(icons.icon("eye_off" if visible else "eye", SECONDARY, 17))

    def text(self) -> str:
        return self.edit.text()

    def clear(self) -> None:
        self.edit.clear()


class FadeLabel(QLabel):
    """Small inline status label used instead of intrusive toast popups."""

    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__("", parent)
        self.setObjectName("Muted")
        self._timer = QTimer(self)
        self._timer.setSingleShot(True)
        self._timer.timeout.connect(lambda: self.setText(""))

    def show_message(self, text: str, msec: int = 2600) -> None:
        self.setText(text)
        self._timer.start(msec)
