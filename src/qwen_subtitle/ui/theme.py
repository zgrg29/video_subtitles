"""Apple-inspired light theme tokens and Qt stylesheet."""

from __future__ import annotations

from pathlib import Path

from PySide6.QtGui import QColor, QFont, QFontDatabase
from PySide6.QtWidgets import QApplication, QGraphicsDropShadowEffect, QWidget

BG = "#F5F5F7"
SIDEBAR = "#ECECF0"
CARD = "#FFFFFF"
FIELD = "#F5F5F7"
TEXT = "#1D1D1F"
SECONDARY = "#6E6E73"
TERTIARY = "#86868B"
BORDER = "#E5E5EA"
BORDER_STRONG = "#D2D2D7"
ACCENT = "#0071E3"
ACCENT_HOVER = "#0077ED"
ACCENT_PRESSED = "#0068CF"
ACCENT_SOFT = "#EAF2FE"
GREEN = "#34C759"
GREEN_DARK = "#248A3D"
GREEN_SOFT = "#E9F8EE"
RED = "#FF3B30"
RED_DARK = "#D70015"
RED_SOFT = "#FDECEA"
AMBER = "#FF9F0A"

_RESOURCES = Path(__file__).resolve().parent.parent / "resources" / "icons"
_CHEVRON = (_RESOURCES / "chevron-down.svg").as_posix()


def preferred_font_family() -> str:
    families = set(QFontDatabase.families())
    for family in (
        "SF Pro Display",
        "SF Pro Text",
        "Segoe UI Variable Display",
        "Segoe UI Variable Text",
        "Segoe UI",
        "Microsoft YaHei UI",
        "PingFang SC",
    ):
        if family in families:
            return family
    return QApplication.font().family()


def apply_theme(app: QApplication) -> None:
    app.setStyle("Fusion")
    font = QFont(preferred_font_family())
    font.setPointSize(10)
    font.setWeight(QFont.Weight.Normal)
    app.setFont(font)
    app.setStyleSheet(stylesheet())


def shadow(widget: QWidget, blur: int = 34, y: int = 14, alpha: int = 46) -> QGraphicsDropShadowEffect:
    effect = QGraphicsDropShadowEffect(widget)
    effect.setBlurRadius(blur)
    effect.setOffset(0, y)
    effect.setColor(QColor(0, 0, 0, alpha))
    widget.setGraphicsEffect(effect)
    return effect


def stylesheet() -> str:
    return f"""
QWidget {{
    color: {TEXT};
    font-family: "{preferred_font_family()}";
    font-size: 13px;
}}
QMainWindow, QDialog {{
    background: transparent;
}}
QWidget#WindowShell {{
    background: {BG};
    border: 1px solid #D9D9DE;
    border-radius: 16px;
}}
QWidget#WindowShell[maximized="true"] {{
    border-radius: 0;
    border: none;
}}
QFrame#PrivacyBox {{
    background: rgba(255, 255, 255, 150);
    border: 1px solid #E4E4E9;
    border-radius: 12px;
}}
QLabel#BrandName {{
    color: {TEXT};
    font-size: 14px;
    font-weight: 700;
    letter-spacing: -0.2px;
}}
QLabel#BrandSub {{
    color: {TERTIARY};
    font-size: 8px;
    font-weight: 700;
    letter-spacing: 1.5px;
}}
QLabel#WindowTitle {{
    color: #3A3A3C;
    font-size: 12px;
    font-weight: 600;
}}
QStackedWidget {{
    background: transparent;
}}
QWidget#TitleBar {{
    background: {SIDEBAR};
    border-top-left-radius: 16px;
    border-top-right-radius: 16px;
    border-bottom: 1px solid #E1E1E6;
}}
QWidget#Sidebar {{
    background: {SIDEBAR};
    border-bottom-left-radius: 16px;
    border-right: 1px solid #E1E1E6;
}}
QWidget#Content {{
    background: {BG};
    border-bottom-right-radius: 16px;
}}
QScrollArea {{
    background: transparent;
    border: none;
}}
QScrollArea > QWidget > QWidget {{
    background: transparent;
}}
QScrollBar:vertical {{
    background: transparent;
    width: 9px;
    margin: 4px 2px 4px 0;
}}
QScrollBar::handle:vertical {{
    background: #C7C7CC;
    min-height: 32px;
    border-radius: 4px;
}}
QScrollBar::handle:vertical:hover {{
    background: #AEAEB2;
}}
QScrollBar::add-line:vertical, QScrollBar::sub-line:vertical,
QScrollBar::add-page:vertical, QScrollBar::sub-page:vertical {{
    background: transparent;
    height: 0;
}}
QFrame#Card {{
    background: {CARD};
    border: 1px solid #E8E8ED;
    border-radius: 18px;
}}
QFrame#DialogCard {{
    background: {CARD};
    border: 1px solid #E8E8ED;
    border-radius: 20px;
}}
QLabel#DialogTitle {{
    color: {TEXT};
    font-size: 20px;
    font-weight: 700;
    letter-spacing: -0.3px;
}}
QLabel#DialogBody {{
    color: {SECONDARY};
    font-size: 12px;
}}
QFrame#DropZone {{
    background: #FAFAFC;
    border: 1.5px dashed #C9C9CF;
    border-radius: 14px;
}}
QFrame#DropZone:hover, QFrame#DropZone[dragActive="true"] {{
    background: #F6FAFF;
    border-color: {ACCENT};
}}
QFrame#Divider {{
    background: #EFEFF3;
    border: none;
    max-height: 1px;
    min-height: 1px;
}}
QLabel#Thumb {{
    background: #E9E9EE;
    border-radius: 9px;
}}
QFrame#FileCard {{
    background: #F9F9FB;
    border: 1px solid #ECECF1;
    border-radius: 12px;
}}
QFrame#Segmented {{
    background: #E9E9EE;
    border: none;
    border-radius: 10px;
}}
QPushButton#SegmentButton {{
    background: transparent;
    border: none;
    border-radius: 8px;
    color: #4A4A4F;
    font-size: 12px;
    font-weight: 600;
    padding: 5px 11px;
}}
QPushButton#SegmentButton:hover {{
    color: {TEXT};
    background: rgba(255, 255, 255, 120);
}}
QPushButton#SegmentButton:checked {{
    background: {CARD};
    color: {TEXT};
}}
QPushButton#SegmentButton:disabled {{
    color: #AEAEB2;
}}
QLabel#Eyebrow {{
    color: {TERTIARY};
    font-size: 10px;
    font-weight: 700;
    letter-spacing: 1.4px;
}}
QLabel#PageTitle {{
    color: {TEXT};
    font-size: 34px;
    font-weight: 700;
    letter-spacing: -0.6px;
}}
QLabel#PageSubtitle {{
    color: {SECONDARY};
    font-size: 14px;
}}
QLabel#CardTitle {{
    color: {TEXT};
    font-size: 16px;
    font-weight: 700;
}}
QLabel#CardHint {{
    color: {TERTIARY};
    font-size: 12px;
}}
QLabel#FieldLabel {{
    color: {SECONDARY};
    font-size: 11px;
    font-weight: 600;
}}
QLabel#Muted {{
    color: {TERTIARY};
    font-size: 12px;
}}
QLabel#Tiny {{
    color: #8E8E93;
    font-size: 11px;
}}
QLabel#Body {{
    color: #3A3A3C;
    font-size: 13px;
}}
QLabel#Value {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#PathBox {{
    background: {FIELD};
    border: 1px solid #ECECF1;
    border-radius: 10px;
    color: {SECONDARY};
    font-size: 11px;
    padding: 9px 11px;
}}
QLabel#Pill {{
    background: {ACCENT_SOFT};
    color: #0066CC;
    border-radius: 8px;
    font-size: 10px;
    font-weight: 700;
    padding: 3px 8px;
}}
QLabel#SuccessIcon {{
    background: {GREEN_SOFT};
    color: {GREEN_DARK};
    border-radius: 28px;
    font-size: 24px;
    font-weight: 700;
}}
QLabel#ErrorIcon {{
    background: {RED_SOFT};
    color: {RED_DARK};
    border-radius: 28px;
    font-size: 24px;
    font-weight: 700;
}}
QLabel#StepCircle {{
    background: #F0F0F3;
    color: #86868B;
    border-radius: 12px;
    font-size: 11px;
    font-weight: 700;
}}
QLabel#StepCircle[state="active"] {{
    background: {ACCENT};
    color: white;
}}
QLabel#StepCircle[state="done"] {{
    background: {GREEN_SOFT};
    color: {GREEN_DARK};
}}
QLabel#StepCircle[state="failed"] {{
    background: {RED_SOFT};
    color: {RED_DARK};
}}
QLabel#StepTitle {{
    color: {TEXT};
    font-size: 13px;
    font-weight: 600;
}}
QLabel#StepDetail {{
    color: {TERTIARY};
    font-size: 11px;
}}
QPushButton#Primary {{
    background: {ACCENT};
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 13px;
    font-weight: 600;
    padding: 9px 18px;
}}
QPushButton#Primary:hover {{
    background: {ACCENT_HOVER};
}}
QPushButton#Primary:pressed {{
    background: {ACCENT_PRESSED};
}}
QPushButton#Primary:disabled {{
    background: #B8D7F7;
    color: #F7FBFF;
}}
QPushButton#Secondary {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid {BORDER_STRONG};
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
    padding: 7px 13px;
}}
QPushButton#Secondary:hover {{
    background: #FAFAFC;
    border-color: #BDBDC3;
}}
QPushButton#Secondary:pressed {{
    background: #F2F2F5;
}}
QPushButton#Secondary:disabled {{
    background: #F7F7F9;
    color: #B0B0B5;
    border-color: #E8E8ED;
}}
QPushButton#Ghost {{
    background: transparent;
    color: {ACCENT};
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 8px;
}}
QPushButton#Ghost:hover {{
    background: {ACCENT_SOFT};
}}
QPushButton#Ghost:disabled {{
    color: #B0B0B5;
    background: transparent;
}}
QPushButton#Danger {{
    background: transparent;
    color: {RED_DARK};
    border: none;
    border-radius: 8px;
    font-size: 12px;
    font-weight: 600;
    padding: 6px 8px;
}}
QPushButton#Danger:hover {{
    background: {RED_SOFT};
}}
QPushButton#Danger:disabled {{
    color: #C7C7CC;
    background: transparent;
}}
QPushButton#DangerSolid {{
    background: {RED};
    color: white;
    border: none;
    border-radius: 10px;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 15px;
}}
QPushButton#DangerSolid:hover {{
    background: #E0342B;
}}
QPushButton#NavButton {{
    background: transparent;
    color: #4A4A4F;
    border: none;
    border-radius: 9px;
    text-align: left;
    font-size: 12px;
    font-weight: 600;
    padding: 8px 10px;
}}
QPushButton#NavButton:hover {{
    background: rgba(255, 255, 255, 130);
    color: {TEXT};
}}
QPushButton#NavButton:checked {{
    background: {CARD};
    color: {TEXT};
}}
QWidget#LanguageBox {{
    background: #E4E4E9;
    border-radius: 7px;
}}
QComboBox#LanguageCombo {{
    background: transparent;
    color: #3A3A3C;
    border: none;
    border-radius: 7px;
    font-size: 11px;
    padding: 3px 18px 3px 3px;
    min-height: 22px;
}}
QComboBox#LanguageCombo:hover {{
    background: #DCDCE2;
}}
QComboBox#LanguageCombo::drop-down {{
    width: 18px;
    border: none;
}}
QComboBox#LanguageCombo::down-arrow {{
    image: url("{_CHEVRON}");
    width: 9px;
    height: 9px;
}}
QPushButton#WindowMin, QPushButton#WindowMax {{
    background: transparent;
    color: #4A4A4F;
    border: none;
    font-size: 14px;
    padding: 0;
}}
QPushButton#WindowMin:hover, QPushButton#WindowMax:hover {{
    background: #E1E1E6;
}}
QPushButton#WindowClose {{
    background: transparent;
    color: #4A4A4F;
    border: none;
    font-size: 15px;
    padding: 0;
}}
QPushButton#WindowClose:hover {{
    background: #E81123;
    color: white;
}}
QPushButton#IconButton {{
    background: transparent;
    border: none;
    border-radius: 7px;
    padding: 4px;
}}
QPushButton#IconButton:hover {{
    background: #EFEFF3;
}}
QLineEdit {{
    background: {FIELD};
    color: {TEXT};
    border: 1px solid #E4E4E9;
    border-radius: 9px;
    padding: 8px 11px;
    selection-background-color: {ACCENT};
    selection-color: white;
}}
QLineEdit:focus {{
    border: 1px solid {ACCENT};
    background: {CARD};
}}
QLineEdit:disabled {{
    color: #AEAEB2;
}}
QComboBox {{
    background: {FIELD};
    color: {TEXT};
    border: 1px solid #E4E4E9;
    border-radius: 9px;
    padding: 7px 29px 7px 11px;
    min-height: 20px;
}}
QComboBox:hover {{
    border-color: #C9C9CF;
}}
QComboBox:focus {{
    border: 1px solid {ACCENT};
    background: {CARD};
}}
QComboBox:disabled {{
    color: #AEAEB2;
    background: #F7F7F9;
}}
QComboBox::drop-down {{
    border: none;
    width: 28px;
}}
QComboBox::down-arrow {{
    image: url("{_CHEVRON}");
    width: 10px;
    height: 10px;
}}
QComboBox QAbstractItemView {{
    background: {CARD};
    color: {TEXT};
    border: 1px solid #E4E4E9;
    border-radius: 10px;
    padding: 5px;
    outline: 0;
    selection-background-color: {ACCENT_SOFT};
    selection-color: {TEXT};
}}
QComboBox QAbstractItemView::item {{
    min-height: 28px;
    padding: 2px 8px;
    border-radius: 6px;
}}
QProgressBar {{
    background: #ECECF0;
    border: none;
    border-radius: 4px;
    min-height: 8px;
    max-height: 8px;
    text-align: center;
}}
QProgressBar::chunk {{
    background: {ACCENT};
    border-radius: 4px;
}}
QToolTip {{
    background: #2C2C2E;
    color: white;
    border: none;
    border-radius: 6px;
    padding: 5px 8px;
    font-size: 11px;
}}
QMessageBox {{
    background: {CARD};
}}
QSplitter::handle {{
    background: transparent;
}}
"""
