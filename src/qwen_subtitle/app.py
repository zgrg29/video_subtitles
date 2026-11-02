"""Application entry point."""

from __future__ import annotations

import logging
import os
import sys
import traceback
from logging.handlers import RotatingFileHandler

from PySide6.QtCore import Qt
from PySide6.QtGui import QGuiApplication
from PySide6.QtWidgets import QApplication

from qwen_subtitle.constants import APP_ID, APP_NAME, VERSION
from qwen_subtitle.core.config import default_app_dir
from qwen_subtitle.ui.main_window import MainWindow
from qwen_subtitle.ui.state import AppState
from qwen_subtitle.ui.theme import apply_theme


def _setup_logging() -> None:
    """Local diagnostics without media names, paths, or secrets."""

    try:
        log_dir = default_app_dir()
        log_dir.mkdir(parents=True, exist_ok=True)
        handler = RotatingFileHandler(
            log_dir / "app.log",
            maxBytes=512 * 1024,
            backupCount=2,
            encoding="utf-8",
        )
        handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s %(name)s: %(message)s"))
        root = logging.getLogger()
        root.setLevel(logging.INFO)
        root.addHandler(handler)
    except OSError:
        logging.basicConfig(level=logging.WARNING)


def _set_windows_app_id() -> None:
    if os.name != "nt":
        return
    try:
        import ctypes

        ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(APP_ID)
    except Exception:
        pass


def _self_test_failure() -> None:
    """Write a local diagnostic when a frozen self-test fails.

    This is opt-in via an environment variable so normal users never get a
    stray diagnostic file.
    """

    target = os.environ.get("QWEN_SUBTITLE_SELF_TEST_LOG")
    if not target:
        return
    try:
        from pathlib import Path

        Path(target).write_text(traceback.format_exc(), encoding="utf-8")
    except Exception:
        pass


def main() -> int:
    self_test = "--self-test" in sys.argv
    if self_test:
        # Used by the packaging smoke test so CI can validate the frozen EXE
        # without requiring a desktop session.
        os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
    QGuiApplication.setHighDpiScaleFactorRoundingPolicy(
        Qt.HighDpiScaleFactorRoundingPolicy.PassThrough
    )
    _set_windows_app_id()
    app = QApplication(sys.argv)
    app.setApplicationName(APP_NAME)
    app.setApplicationDisplayName(APP_NAME)
    app.setOrganizationName(APP_ID)
    app.setApplicationVersion(VERSION)
    app.setQuitOnLastWindowClosed(True)
    _setup_logging()
    logging.info("Starting %s %s", APP_NAME, VERSION)
    apply_theme(app)
    state = AppState()
    window = MainWindow(state)
    window.show()
    if self_test:
        app.processEvents()
        window.close()
        app.processEvents()
        try:
            from qwen_subtitle.core.ffmpeg import resolve_ffmpeg

            ffmpeg = resolve_ffmpeg(state.settings.ffmpeg_path)
        except Exception:
            logging.exception("QwenSubtitle self-test: FFmpeg missing")
            _self_test_failure()
            return 3
        try:
            import shutil

            from qwen_subtitle.core.config import create_work_dir

            work_dir = create_work_dir("self-test-")
            (work_dir / "probe.txt").write_text("ok", encoding="utf-8")
            shutil.rmtree(work_dir, ignore_errors=True)
        except Exception:
            logging.exception("QwenSubtitle self-test: writable cache unavailable")
            _self_test_failure()
            return 4
        logging.info("QwenSubtitle self-test: ok (ffmpeg=%s, cache=writable)", ffmpeg.source)
        return 0
    code = app.exec()
    logging.info("Exited with code %s", code)
    return int(code)


if __name__ == "__main__":
    raise SystemExit(main())
