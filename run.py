"""Development launcher.

Install the project first (``pip install -e ".[dev]"``), or run this file from a
checkout where ``src`` is on ``PYTHONPATH``.
"""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent
SRC = ROOT / "src"
# Local development fallback for the DSH workspace (gitignored).
DEPS = ROOT / ".deps"
if DEPS.is_dir() and str(DEPS) not in sys.path:
    sys.path.insert(0, str(DEPS))
if str(SRC) not in sys.path:
    sys.path.insert(0, str(SRC))

from qwen_subtitle.app import main  # noqa: E402

if __name__ == "__main__":
    raise SystemExit(main())
