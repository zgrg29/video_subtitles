#!/usr/bin/env python3
"""Fail if a likely secret or personal path is about to enter a public repo.

This is a guardrail, not a replacement for review.  It scans text files that
are not ignored by the project and prints only redacted findings.
"""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
EXCLUDED_DIRS = {
    ".git",
    ".deps",
    ".venv",
    ".tmp",
    "__pycache__",
    ".pytest_cache",
    ".ruff_cache",
    "build",
    "dist",
    "node_modules",
}
TEXT_SUFFIXES = {
    ".py",
    ".md",
    ".txt",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ps1",
    ".cmd",
    ".bat",
    ".ini",
    ".cfg",
    ".html",
    ".css",
    ".js",
    ".ts",
    ".tsx",
    ".jsx",
    ".svg",
    ".example",
    "",
}

PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("API key", re.compile(r"\bsk-[A-Za-z0-9][A-Za-z0-9_\-]{16,}\b")),
    ("bearer token", re.compile(r"(?i)\bbearer\s+[A-Za-z0-9._\-]{20,}")),
    ("private key", re.compile(r"-----BEGIN (?:RSA |EC |OPENSSH )?PRIVATE KEY-----")),
    (
        "Windows user path",
        re.compile(r"(?i)\b[A-Z]:[\\/]+Users[\\/]+[^\\/\s`\"'，。；：、！？（）()\[\]{}]+"),
    ),
    (
        "Unix user path",
        re.compile(r"(?<![\w.])/(?:Users|home)/[^\\/\s`\"'，。；：、！？（）()\[\]{}]+"),
    ),
    ("email address", re.compile(r"\b[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}\b")),
    ("DashScope token assignment", re.compile(r"(?i)DASHSCOPE_API_KEY\s*=\s*['\"]?sk-")),
]
SAFE_SECRET_PREFIXES = ("sk-test", "sk-fake", "sk-example", "sk-your", "sk-xxx")
SAFE_EMAIL_DOMAINS = ("example.com", "example.org", "example.net", "localhost")
SELF = Path(__file__).resolve()


def iter_files() -> list[Path]:
    output: list[Path] = []
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        if any(part in EXCLUDED_DIRS for part in path.parts):
            continue
        if path == SELF:
            continue
        if path.suffix.lower() not in TEXT_SUFFIXES and path.name not in {".gitignore", ".gitattributes", ".editorconfig"}:
            continue
        if path.stat().st_size > 2_000_000:
            continue
        output.append(path)
    return output


def is_safe_match(kind: str, value: str) -> bool:
    lowered = value.lower()
    if kind == "API key":
        return lowered.startswith(SAFE_SECRET_PREFIXES)
    if kind == "DashScope token assignment":
        if any(prefix in lowered for prefix in SAFE_SECRET_PREFIXES) or "sk-…" in lowered:
            return True
        # The regex intentionally matches only the "sk-" prefix; a longer
        # real value is caught by the separate API-key pattern.
        return lowered.endswith("sk-")
    if kind == "email address":
        domain = lowered.rsplit("@", 1)[-1]
        return domain in SAFE_EMAIL_DOMAINS or domain.endswith(".example.com")
    if kind in {"Windows user path", "Unix user path"}:
        # Documentation may use explicit placeholders such as C:\Users\<name>.
        raw_tail = value.replace("\\", "/").rstrip("/").split("/")[-1]
        if raw_tail in {"...", "…"}:
            return True
        tail = raw_tail.strip("`.,;:()[]{}")
        return tail.startswith("<") and tail.endswith(">")
    return False


def main() -> int:
    findings: list[tuple[Path, int, str, str]] = []
    for path in iter_files():
        try:
            text = path.read_text(encoding="utf-8")
        except (OSError, UnicodeError):
            continue
        for line_number, line in enumerate(text.splitlines(), start=1):
            for kind, pattern in PATTERNS:
                for match in pattern.finditer(line):
                    value = match.group(0)
                    if is_safe_match(kind, value):
                        continue
                    redacted = value if len(value) <= 8 else value[:4] + "…" + value[-2:]
                    findings.append((path.relative_to(ROOT), line_number, kind, redacted))
    if not findings:
        print("public-repo scan: clean")
        return 0
    print("public-repo scan: potential issues found")
    for path, line_number, kind, value in findings:
        print(f"  {path}:{line_number}: {kind}: {value}")
    print("Remove or replace the value before publishing. Never commit a real key.")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
