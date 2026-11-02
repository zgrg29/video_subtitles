"""Regenerate assets/app.ico from the in-code app icon."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "src"))

from PySide6.QtWidgets import QApplication  # noqa: E402

from qwen_subtitle.ui.icons import app_icon  # noqa: E402


def main() -> int:
    app = QApplication([])
    app.setApplicationName("Qwen Subtitle icon builder")
    output = ROOT / "assets" / "app.ico"
    output.parent.mkdir(parents=True, exist_ok=True)
    if not app_icon().pixmap(256, 256).save(str(output), "ICO"):
        print("Could not write assets/app.ico", file=sys.stderr)
        return 1
    print(f"Wrote {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
