"""About page with product, privacy, and license information."""

from __future__ import annotations

from PySide6.QtCore import Qt
from PySide6.QtWidgets import (
    QHBoxLayout,
    QLabel,
    QScrollArea,
    QVBoxLayout,
    QWidget,
)

from qwen_subtitle.constants import VERSION
from qwen_subtitle.i18n import tr
from qwen_subtitle.ui.icons import app_pixmap
from qwen_subtitle.ui.theme import shadow
from qwen_subtitle.ui.widgets import Card, make_label


class AboutPage(QWidget):
    def __init__(self, parent: QWidget | None = None) -> None:
        super().__init__(parent)
        self._build()
        self.retranslate()

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
        panel.setMaximumWidth(720)
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

        hero = Card()
        hero_layout = QHBoxLayout(hero)
        hero_layout.setContentsMargins(22, 22, 22, 22)
        hero_layout.setSpacing(18)
        icon = QLabel()
        icon.setPixmap(app_pixmap(76))
        icon.setFixedSize(76, 76)
        shadow(icon, 24, 8, 50)
        hero_layout.addWidget(icon)
        text = QVBoxLayout()
        text.setSpacing(4)
        self.app_name = make_label("", "CardTitle")
        self.app_name.setStyleSheet("font-size: 19px;")
        self.version = make_label("", "Pill")
        self.version.setSizePolicy(self.version.sizePolicy().horizontalPolicy(), self.version.sizePolicy().verticalPolicy())
        version_row = QHBoxLayout()
        version_row.setSpacing(8)
        version_row.addWidget(self.version)
        version_row.addStretch(1)
        self.body = make_label("", "Body")
        self.body.setWordWrap(True)
        text.addWidget(self.app_name)
        text.addLayout(version_row)
        text.addSpacing(3)
        text.addWidget(self.body)
        hero_layout.addLayout(text, 1)
        self.panel_layout.addWidget(hero)

        self.privacy_card, self.privacy_title, self.privacy_body = self._info_card()
        self.tech_card, self.tech_title, self.tech_body = self._info_card()
        self.license_card, self.license_title, self.license_body = self._info_card()
        self.disclaimer = make_label("", "Tiny")
        self.disclaimer.setAlignment(Qt.AlignmentFlag.AlignHCenter)
        self.panel_layout.addWidget(self.disclaimer)
        self.panel_layout.addStretch(1)

    def _info_card(self) -> tuple[Card, QLabel, QLabel]:
        card = Card()
        layout = QVBoxLayout(card)
        layout.setContentsMargins(20, 16, 20, 16)
        layout.setSpacing(5)
        title = make_label("", "Value")
        body = make_label("", "Muted")
        body.setWordWrap(True)
        layout.addWidget(title)
        layout.addWidget(body)
        self.panel_layout.addWidget(card)
        return card, title, body

    def retranslate(self) -> None:
        self.eyebrow.setText(tr("about.eyebrow"))
        self.title.setText(tr("about.title"))
        self.subtitle.setText(tr("about.subtitle"))
        self.app_name.setText(tr("common.app_name"))
        self.version.setText(tr("about.version", version=VERSION))
        self.body.setText(tr("about.body"))
        self.privacy_title.setText(tr("about.privacy.title"))
        self.privacy_body.setText(tr("about.privacy.body"))
        self.tech_title.setText(tr("about.tech.title"))
        self.tech_body.setText(tr("about.tech.body"))
        self.license_title.setText(tr("about.license"))
        self.license_body.setText(tr("about.license.body"))
        self.disclaimer.setText(tr("about.disclaimer"))
