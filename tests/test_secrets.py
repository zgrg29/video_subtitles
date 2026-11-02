from __future__ import annotations

import os
from pathlib import Path

import pytest

from qwen_subtitle.core.secrets import SecretStore, SecretStoreError


pytestmark = pytest.mark.skipif(os.name != "nt", reason="Windows DPAPI only")


def test_dpapi_roundtrip_and_no_plaintext(tmp_path: Path) -> None:
    path = tmp_path / "secrets.bin"
    store = SecretStore(path)
    secret = "sk-test-only-not-a-real-key-123"
    store.set_api_key("cn", secret)
    assert store.has_api_key("cn")
    assert store.get_api_key("cn") == secret
    raw = path.read_bytes()
    assert secret.encode("utf-8") not in raw
    store.delete_api_key("cn")
    assert not store.has_api_key("cn")


def test_rejects_empty_and_multiline(tmp_path: Path) -> None:
    store = SecretStore(tmp_path / "secrets.bin")
    with pytest.raises(SecretStoreError):
        store.set_api_key("cn", " ")
    with pytest.raises(SecretStoreError):
        store.set_api_key("cn", "sk-a\nsk-b")
    with pytest.raises(SecretStoreError):
        store.set_api_key("mars", "sk-test")


def test_two_regions_are_independent(tmp_path: Path) -> None:
    store = SecretStore(tmp_path / "secrets.bin")
    store.set_api_key("cn", "sk-cn-test")
    store.set_api_key("intl", "sk-intl-test")
    assert store.get_api_key("cn") == "sk-cn-test"
    assert store.get_api_key("intl") == "sk-intl-test"
