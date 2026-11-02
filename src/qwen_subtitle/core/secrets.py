"""Windows DPAPI-backed secret storage for DashScope API keys.

Keys are encrypted for the current Windows user with CryptProtectData and are
written to a local binary file outside the repository.  They are never stored
in settings.json, logs, command lines, environment files, or source code.
"""

from __future__ import annotations

import ctypes
import json
import os
import tempfile
import threading
from ctypes import wintypes
from pathlib import Path

from qwen_subtitle.constants import REGION_BY_KEY
from qwen_subtitle.core.config import default_app_dir
from qwen_subtitle.i18n import tr


class SecretStoreError(RuntimeError):
    """A safe, user-facing secret-store error without the secret value."""


class _DataBlob(ctypes.Structure):
    _fields_ = [
        ("cbData", wintypes.DWORD),
        ("pbData", ctypes.POINTER(ctypes.c_byte)),
    ]


def _blob_from_bytes(value: bytes) -> tuple[_DataBlob, ctypes.Array]:
    buffer = ctypes.create_string_buffer(value, len(value))
    blob = _DataBlob(
        len(value),
        ctypes.cast(buffer, ctypes.POINTER(ctypes.c_byte)),
    )
    return blob, buffer


def _dpapi_protect(value: bytes) -> bytes:
    if os.name != "nt":
        raise SecretStoreError(tr("error.secret_windows"))
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, _keepalive = _blob_from_bytes(value)
    output_blob = _DataBlob()
    crypt32.CryptProtectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        wintypes.LPCWSTR,
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptProtectData.restype = wintypes.BOOL
    ok = crypt32.CryptProtectData(
        ctypes.byref(input_blob),
        "Qwen Subtitle API key",
        None,
        None,
        None,
        0x1,  # CRYPTPROTECT_UI_FORBIDDEN
        ctypes.byref(output_blob),
    )
    if not ok:
        raise SecretStoreError(tr("error.secret_encrypt"))
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


def _dpapi_unprotect(value: bytes) -> bytes:
    if os.name != "nt":
        raise SecretStoreError(tr("error.secret_windows"))
    crypt32 = ctypes.windll.crypt32
    kernel32 = ctypes.windll.kernel32
    input_blob, _keepalive = _blob_from_bytes(value)
    output_blob = _DataBlob()
    crypt32.CryptUnprotectData.argtypes = [
        ctypes.POINTER(_DataBlob),
        ctypes.POINTER(wintypes.LPWSTR),
        ctypes.POINTER(_DataBlob),
        wintypes.LPVOID,
        wintypes.LPVOID,
        wintypes.DWORD,
        ctypes.POINTER(_DataBlob),
    ]
    crypt32.CryptUnprotectData.restype = wintypes.BOOL
    ok = crypt32.CryptUnprotectData(
        ctypes.byref(input_blob),
        None,
        None,
        None,
        None,
        0x1,
        ctypes.byref(output_blob),
    )
    if not ok:
        raise SecretStoreError(tr("error.secret_decrypt"))
    try:
        return ctypes.string_at(output_blob.pbData, output_blob.cbData)
    finally:
        kernel32.LocalFree(output_blob.pbData)


class SecretStore:
    """Store one API key per region, encrypted with the current user's DPAPI key."""

    def __init__(self, path: Path | None = None) -> None:
        self.path = path or (default_app_dir() / "secrets.bin")
        self._lock = threading.Lock()

    def _read_all(self) -> dict[str, str]:
        if not self.path.exists():
            return {}
        try:
            encrypted = self.path.read_bytes()
            raw = _dpapi_unprotect(encrypted)
            data = json.loads(raw.decode("utf-8"))
        except SecretStoreError:
            raise
        except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
            raise SecretStoreError(tr("error.secret_corrupt")) from exc
        if not isinstance(data, dict):
            return {}
        return {
            str(key): str(value)
            for key, value in data.items()
            if key in REGION_BY_KEY and isinstance(value, str) and value
        }

    def _write_all(self, values: dict[str, str]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        payload = json.dumps(values, ensure_ascii=False).encode("utf-8")
        encrypted = _dpapi_protect(payload)
        fd, tmp_name = tempfile.mkstemp(
            prefix=".secrets-",
            suffix=".bin",
            dir=str(self.path.parent),
        )
        try:
            with os.fdopen(fd, "wb") as handle:
                handle.write(encrypted)
                handle.flush()
                os.fsync(handle.fileno())
            os.replace(tmp_name, self.path)
        except Exception:
            try:
                os.unlink(tmp_name)
            except OSError:
                pass
            raise

    def set_api_key(self, region: str, api_key: str) -> None:
        if region not in REGION_BY_KEY:
            raise SecretStoreError(tr("error.secret_region"))
        key = api_key.strip()
        if not key:
            raise SecretStoreError(tr("error.secret_empty"))
        if len(key) > 512 or any(ch in key for ch in "\r\n\x00"):
            raise SecretStoreError(tr("error.secret_format"))
        with self._lock:
            values = self._read_all()
            values[region] = key
            self._write_all(values)

    def get_api_key(self, region: str) -> str:
        if region not in REGION_BY_KEY:
            return ""
        with self._lock:
            return self._read_all().get(region, "")

    def has_api_key(self, region: str) -> bool:
        try:
            return bool(self.get_api_key(region))
        except SecretStoreError:
            return False

    def delete_api_key(self, region: str) -> None:
        with self._lock:
            values = self._read_all()
            if region in values:
                values.pop(region, None)
                self._write_all(values)

    def masked_hint(self, region: str) -> str:
        return "已保存" if self.get_api_key(region) else "未保存"
