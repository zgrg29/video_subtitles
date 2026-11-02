from __future__ import annotations

from pathlib import Path
from typing import Any

import pytest

from qwen_subtitle.core.dashscope import QwenClient, parse_transcription_payload
from qwen_subtitle.core.errors import ApiError


class _Response:
    def __init__(self, status_code: int = 200, payload: dict | None = None) -> None:
        self.status_code = status_code
        self._payload = payload or {}
        self.headers: dict[str, str] = {}

    def json(self) -> dict:
        return self._payload


class _Session:
    def __init__(self, payload: dict, post_payload: dict | None = None) -> None:
        self.payload = payload
        self.post_payload = post_payload or {}
        self.requests: list[dict[str, Any]] = []
        self.posts: list[dict[str, Any]] = []

    def request(self, method: str, url: str, **kwargs: Any) -> _Response:
        self.requests.append({"method": method, "url": url, **kwargs})
        return _Response(200, self.payload)

    def post(self, url: str, **kwargs: Any) -> _Response:
        self.posts.append({"url": url, **kwargs})
        return _Response(200, self.post_payload)


def test_extract_url_from_both_result_shapes() -> None:
    single = {"output": {"result": {"transcription_url": "https://files.example/a.json"}}}
    many = {
        "output": {
            "results": [
                {"subtask_status": "FAILED", "transcription_url": "https://files.example/bad.json"},
                {"subtask_status": "SUCCEEDED", "transcription_url": "https://files.example/good.json"},
            ]
        }
    }
    assert QwenClient.extract_transcription_url(single).endswith("a.json")
    assert QwenClient.extract_transcription_url(many).endswith("good.json")
    with pytest.raises(ApiError):
        QwenClient.extract_transcription_url({"output": {}})


def test_parse_transcription_payload_nested() -> None:
    assert parse_transcription_payload({"transcripts": [{"sentences": [{"text": "hi"}]}]}) == [
        {"text": "hi"}
    ]
    assert parse_transcription_payload(
        {"output": {"transcripts": [{"sentences": [{"text": "nested"}]}]}}
    ) == [{"text": "nested"}]


def test_translate_sends_translation_options_without_leaking_key() -> None:
    session = _Session(
        {"choices": [{"message": {"content": "Hello"}}]},
    )
    client = QwenClient("https://dashscope.aliyuncs.com", "sk-test-secret", session=session)
    result = client.translate(
        "你好",
        model="qwen-mt-plus",
        source_lang="Chinese",
        target_lang="English",
    )
    assert result == "Hello"
    call = session.requests[0]
    assert call["json"]["model"] == "qwen-mt-plus"
    assert call["json"]["translation_options"] == {
        "source_lang": "Chinese",
        "target_lang": "English",
    }
    assert "sk-test-secret" in call["headers"]["Authorization"]


def test_upload_policy_and_multipart(tmp_path: Path) -> None:
    policy = {
        "data": {
            "upload_host": "https://dashscope-file-x.oss-cn-beijing.aliyuncs.com",
            "upload_dir": "dashscope-instant/demo",
            "signature": "sig",
            "policy": "policy",
            "oss_access_key_id": "LTA-test",
            "x_oss_object_acl": "private",
            "x_oss_forbid_overwrite": "true",
            "max_file_size_mb": "100",
        }
    }
    session = _Session(policy, {})
    client = QwenClient("https://dashscope.aliyuncs.com", "sk-test-secret", session=session)
    audio = tmp_path / "audio.mp3"
    audio.write_bytes(b"ID3" + b"0" * 100)
    uploaded = client.upload_audio(audio, "qwen-audio-3.1-asr-flash-filetrans")
    assert uploaded.url.startswith("oss://dashscope-instant/demo/qwen-subtitle-")
    assert uploaded.bytes_sent == 103
    assert session.posts
    assert session.posts[0]["data"]["success_action_status"] == "200"


def test_rejected_upload_host_is_refused() -> None:
    session = _Session(
        {
            "data": {
                "upload_host": "https://evil.example.com",
                "upload_dir": "x",
                "signature": "s",
                "policy": "p",
                "oss_access_key_id": "k",
            }
        }
    )
    client = QwenClient("https://dashscope.aliyuncs.com", "sk-test-secret", session=session)
    with pytest.raises(ApiError):
        client.get_upload_policy("qwen3-asr-flash-filetrans")


def test_http_error_does_not_contain_key() -> None:
    class BadSession(_Session):
        def request(self, method: str, url: str, **kwargs: Any) -> _Response:
            return _Response(401, {"code": "InvalidApiKey", "message": "key sk-test-secret bad"})

    client = QwenClient(
        "https://dashscope.aliyuncs.com",
        "sk-test-secret",
        session=BadSession({}),
    )
    with pytest.raises(ApiError) as exc_info:
        client.get_upload_policy("qwen3-asr-flash-filetrans")
    assert "sk-test-secret" not in str(exc_info.value)
