"""Inline SVG icons so the app has no external icon dependency."""

from __future__ import annotations

from PySide6.QtCore import QByteArray, QRectF, Qt
from PySide6.QtGui import QIcon, QPainter, QPixmap
from PySide6.QtSvg import QSvgRenderer

from qwen_subtitle.ui.theme import TEXT

_TEMPLATE = """<svg width="24" height="24" viewBox="0 0 24 24" xmlns="http://www.w3.org/2000/svg">
{body}
</svg>"""

_ICONS = {
    "workbench": """
<rect x="3" y="3" width="7" height="7" rx="2" fill="none" stroke="{color}" stroke-width="1.7"/>
<rect x="14" y="3" width="7" height="7" rx="2" fill="none" stroke="{color}" stroke-width="1.7"/>
<rect x="3" y="14" width="7" height="7" rx="2" fill="none" stroke="{color}" stroke-width="1.7"/>
<rect x="14" y="14" width="7" height="7" rx="2" fill="none" stroke="{color}" stroke-width="1.7"/>
""",
    "settings": """
<path d="M4 7H20M4 17H20" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
<circle cx="9" cy="7" r="2.4" fill="none" stroke="{color}" stroke-width="1.7"/>
<circle cx="15" cy="17" r="2.4" fill="none" stroke="{color}" stroke-width="1.7"/>
""",
    "info": """
<circle cx="12" cy="12" r="8.4" fill="none" stroke="{color}" stroke-width="1.7"/>
<path d="M12 10.7V16" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
<circle cx="12" cy="7.8" r="1" fill="{color}"/>
""",
    "film": """
<rect x="3.2" y="4.5" width="17.6" height="15" rx="3" fill="none" stroke="{color}" stroke-width="1.7"/>
<path d="M7.7 4.5V19.5M16.3 4.5V19.5M3.2 9H7.7M3.2 15H7.7M16.3 9H20.8M16.3 15H20.8" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
""",
    "plus": """
<path d="M12 5V19M5 12H19" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
""",
    "folder": """
<path d="M3.2 7.2C3.2 6.1 4.1 5.2 5.2 5.2H9.6L11.6 7.5H18.8C19.9 7.5 20.8 8.4 20.8 9.5V17C20.8 18.1 19.9 19 18.8 19H5.2C4.1 19 3.2 18.1 3.2 17V7.2Z" fill="none" stroke="{color}" stroke-width="1.7" stroke-linejoin="round"/>
""",
    "lock": """
<rect x="5" y="10" width="14" height="10" rx="2.6" fill="none" stroke="{color}" stroke-width="1.7"/>
<path d="M8.2 10V7.8C8.2 5.7 9.9 4 12 4C14.1 4 15.8 5.7 15.8 7.8V10" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
<circle cx="12" cy="15" r="1.2" fill="{color}"/>
""",
    "eye": """
<path d="M2.8 12C4.4 8.4 7.8 6.2 12 6.2C16.2 6.2 19.6 8.4 21.2 12C19.6 15.6 16.2 17.8 12 17.8C7.8 17.8 4.4 15.6 2.8 12Z" fill="none" stroke="{color}" stroke-width="1.7" stroke-linejoin="round"/>
<circle cx="12" cy="12" r="2.7" fill="none" stroke="{color}" stroke-width="1.7"/>
""",
    "eye_off": """
<path d="M4 4L20 20" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
<path d="M9.9 6.6C10.6 6.4 11.3 6.3 12 6.3C16.2 6.3 19.6 8.5 21.2 12C20.7 13.1 20.1 14.1 19.3 15M6.4 8.1C5.0 9.1 3.8 10.4 2.8 12C4.4 15.6 7.8 17.8 12 17.8C13.5 17.8 14.9 17.5 16.2 17" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "check": """
<path d="M5 12.5L9.5 17L19 7.5" fill="none" stroke="{color}" stroke-width="2" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "alert": """
<path d="M12 4L21 19H3L12 4Z" fill="none" stroke="{color}" stroke-width="1.7" stroke-linejoin="round"/>
<path d="M12 9.5V14" stroke="{color}" stroke-width="1.8" stroke-linecap="round"/>
<circle cx="12" cy="16.8" r="1" fill="{color}"/>
""",
    "arrow_right": """
<path d="M4 12H20M14 6L20 12L14 18" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "key": """
<circle cx="8" cy="12" r="4.2" fill="none" stroke="{color}" stroke-width="1.7"/>
<path d="M12.2 12H21M17 12V15.2M20 12V14.5" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
""",
    "sparkles": """
<path d="M12 3.5L13.7 9.1L19.3 10.8L13.7 12.5L12 18.1L10.3 12.5L4.7 10.8L10.3 9.1L12 3.5Z" fill="none" stroke="{color}" stroke-width="1.6" stroke-linejoin="round"/>
<path d="M19 16L19.8 18.4L22 19.2L19.8 20L19 22.4L18.2 20L16 19.2L18.2 18.4L19 16Z" fill="{color}"/>
""",
    "upload": """
<path d="M12 16V4M7.5 8.5L12 4L16.5 8.5" fill="none" stroke="{color}" stroke-width="1.8" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M5 14V18.5C5 19.3 5.7 20 6.5 20H17.5C18.3 20 19 19.3 19 18.5V14" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
""",
    "external": """
<path d="M14 4H20V10M20 4L11 13" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
<path d="M18 14V19C18 19.6 17.6 20 17 20H5C4.4 20 4 19.6 4 19V7C4 6.4 4.4 6 5 6H10" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
""",
    "refresh": """
<path d="M20 11C19.5 7.1 16.3 4.5 12.5 4.5C8.4 4.5 5 7.9 5 12C5 16.1 8.4 19.5 12.5 19.5C15.6 19.5 18.2 17.6 19.4 14.9" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round"/>
<path d="M20 5V11H14" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
""",
    "globe": """
<circle cx="12" cy="12" r="8.4" fill="none" stroke="{color}" stroke-width="1.6"/>
<path d="M3.8 12H20.2M12 3.6C14.4 6 15.6 8.8 15.6 12C15.6 15.2 14.4 18 12 20.4C9.6 18 8.4 15.2 8.4 12C8.4 8.8 9.6 6 12 3.6Z" fill="none" stroke="{color}" stroke-width="1.5" stroke-linecap="round"/>
""",
    "trash": """
<path d="M4.5 7H19.5M9 7V4.8C9 4.4 9.4 4 9.8 4H14.2C14.6 4 15 4.4 15 4.8V7M6.5 7L7.4 19.2C7.4 19.6 7.8 20 8.2 20H15.8C16.2 20 16.6 19.6 16.6 19.2L17.5 7" fill="none" stroke="{color}" stroke-width="1.7" stroke-linecap="round" stroke-linejoin="round"/>
""",
}


def icon(name: str, color: str = TEXT, size: int = 18) -> QIcon:
    body = _ICONS.get(name, _ICONS["info"]).replace("{color}", color)
    svg = _TEMPLATE.format(body=body)
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    scale = 2
    pixmap = QPixmap(size * scale, size * scale)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, size * scale, size * scale))
    painter.end()
    pixmap.setDevicePixelRatio(scale)
    return QIcon(pixmap)


def app_icon() -> QIcon:
    svg = """<svg width="256" height="256" viewBox="0 0 256 256" xmlns="http://www.w3.org/2000/svg">
<defs>
<linearGradient id="g" x1="0" y1="0" x2="1" y2="1">
<stop offset="0" stop-color="#38A1FF"/><stop offset="1" stop-color="#0066E6"/>
</linearGradient>
</defs>
<rect x="8" y="8" width="240" height="240" rx="56" fill="url(#g)"/>
<path d="M52 136C52 128 62 128 62 136V160C62 168 52 168 52 160V136Z" fill="white" opacity="0.92"/>
<path d="M80 112C80 104 90 104 90 112V176C90 184 80 184 80 176V112Z" fill="white"/>
<path d="M108 88C108 80 120 80 120 88V184C120 192 108 192 108 184V88Z" fill="white"/>
<path d="M138 104C138 96 150 96 150 104V168C150 176 138 176 138 168V104Z" fill="white"/>
<path d="M167 122C167 114 177 114 177 122V150C177 158 167 158 167 150V122Z" fill="white" opacity="0.92"/>
<path d="M194 134C194 126 204 126 204 134V138C204 146 194 146 194 138V134Z" fill="white" opacity="0.8"/>
</svg>"""
    renderer = QSvgRenderer(QByteArray(svg.encode("utf-8")))
    pixmap = QPixmap(256, 256)
    pixmap.fill(Qt.GlobalColor.transparent)
    painter = QPainter(pixmap)
    painter.setRenderHint(QPainter.RenderHint.Antialiasing, True)
    renderer.render(painter, QRectF(0, 0, 256, 256))
    painter.end()
    return QIcon(pixmap)


def app_pixmap(size: int = 128) -> QPixmap:
    return app_icon().pixmap(size, size)
