"""Minimal, dependency-light client for the Qwen ASR and Qwen-MT HTTP APIs.

Implemented directly against Alibaba Cloud Model Studio's documented HTTP
surface so the desktop app does not need the full DashScope SDK:

* temporary file upload -> ``oss://`` URL
* long-audio file transcription job -> poll -> download JSON
* Qwen-MT via the OpenAI-compatible chat endpoint

The client never logs or includes an API key in an exception message.
"""

from __future__ import annotations

import re
import threading
import time
import uuid
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlparse

import requests

from qwen_subtitle.constants import (
    MAX_UPLOAD_BYTES,
    POLL_INTERVAL_SECONDS,
    POLL_TIMEOUT_SECONDS,
)
from qwen_subtitle.core.errors import ApiError, CancelledError, friendly_http_error
from qwen_subtitle.i18n import tr

_SECRET_PATTERNS = (
    re.compile(r"sk-[A-Za-z0-9_\-]{8,}"),
    re.compile(r"(?i)(bearer\s+)[A-Za-z0-9_\-\.]{8,}"),
)


def _safe_text(value: object, limit: int = 280) -> str:
    text = str(value or "")
    for pattern in _SECRET_PATTERNS:
        text = pattern.sub("[redacted]", text)
    return text[:limit]


def _safe_server_message(payload: Any) -> tuple[str, str]:
    if not isinstance(payload, dict):
        return "", ""
    code = _safe_text(payload.get("code") or payload.get("error_code") or "", 80)
    message = _safe_text(payload.get("message") or payload.get("error") or "")
    return code, message


@dataclass(frozen=True)
class UploadedAudio:
    url: str
    bytes_sent: int


@dataclass(frozen=True)
class TranscriptionJob:
    task_id: str
    raw: dict


class QwenClient:
    def __init__(
        self,
        base_url: str,
        api_key: str,
        *,
        timeout: tuple[float, float] = (15.0, 120.0),
        session: requests.Session | None = None,
    ) -> None:
        if not base_url.startswith("https://"):
            raise ApiError(tr("error.https"))
        if not api_key:
            raise ApiError(tr("error.no_key", region=""))
        self.base_url = base_url.rstrip("/")
        self._api_key = api_key
        self.timeout = timeout
        self.session = session or requests.Session()

    def _headers(self, extra: dict[str, str] | None = None) -> dict[str, str]:
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
            "User-Agent": "QwenSubtitle/0.1",
        }
        if extra:
            headers.update(extra)
        return headers

    def _request(
        self,
        method: str,
        url: str,
        *,
        json_body: dict | None = None,
        params: dict | None = None,
        headers: dict | None = None,
        timeout: tuple[float, float] | None = None,
        attempts: int = 3,
        cancel_event: threading.Event | None = None,
    ) -> requests.Response:
        last_error: Exception | None = None
        for attempt in range(attempts):
            if cancel_event and cancel_event.is_set():
                raise CancelledError()
            try:
                response = self.session.request(
                    method,
                    url,
                    json=json_body,
                    params=params,
                    headers=self._headers(headers),
                    timeout=timeout or self.timeout,
                )
            except requests.Timeout as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise ApiError(tr("error.timeout")) from exc
                time.sleep(1.5 * (attempt + 1))
                continue
            except requests.RequestException as exc:
                last_error = exc
                if attempt + 1 >= attempts:
                    raise ApiError(tr("error.network")) from exc
                time.sleep(1.2 * (attempt + 1))
                continue
            if response.status_code == 200:
                return response
            payload: Any
            try:
                payload = response.json()
            except ValueError:
                payload = {}
            code, message = _safe_server_message(payload)
            if response.status_code in (429, 500, 502, 503, 504) and attempt + 1 < attempts:
                retry_after = response.headers.get("Retry-After")
                delay = 2.0 + attempt * 3.0
                if retry_after:
                    try:
                        delay = max(delay, min(30.0, float(retry_after)))
                    except ValueError:
                        pass
                time.sleep(delay)
                last_error = ApiError(
                    friendly_http_error(response.status_code, code, message),
                    status_code=response.status_code,
                    code=code,
                    retryable=True,
                )
                continue
            raise ApiError(
                friendly_http_error(response.status_code, code, message),
                status_code=response.status_code,
                code=code,
                retryable=response.status_code >= 500 or response.status_code == 429,
                detail=message,
            )
        raise ApiError(tr("error.network")) from last_error

    # ------------------------------------------------------------------ upload
    def get_upload_policy(self, model: str) -> dict:
        response = self._request(
            "GET",
            f"{self.base_url}/api/v1/uploads",
            params={"action": "getPolicy", "model": model},
        )
        try:
            payload = response.json()
            data = payload["data"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ApiError(tr("error.api"), detail="upload policy missing data") from exc
        if not isinstance(data, dict):
            raise ApiError(tr("error.api"), detail="upload policy is not an object")
        host = str(data.get("upload_host", ""))
        parsed = urlparse(host)
        if parsed.scheme != "https" or not (parsed.hostname or "").endswith(".aliyuncs.com"):
            raise ApiError(tr("error.api"), detail="unexpected upload host")
        for field in ("upload_dir", "signature", "policy", "oss_access_key_id"):
            if not data.get(field):
                raise ApiError(tr("error.api"), detail=f"upload policy missing {field}")
        return data

    def upload_audio(
        self,
        file_path: Path,
        model: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> UploadedAudio:
        path = Path(file_path)
        if not path.is_file():
            raise ApiError(tr("error.file_missing"))
        size = path.stat().st_size
        if size > MAX_UPLOAD_BYTES:
            raise ApiError(tr("error.file_too_large"))
        if cancel_event and cancel_event.is_set():
            raise CancelledError()

        policy = self.get_upload_policy(model)
        max_mb = int(policy.get("max_file_size_mb") or 0)
        if max_mb and size > max_mb * 1024 * 1024:
            raise ApiError(tr("error.file_too_large"))
        suffix = path.suffix.lower() if path.suffix.lower() in (".mp3", ".m4a") else ".mp3"
        object_name = f"qwen-subtitle-{uuid.uuid4().hex[:16]}{suffix}"
        key = f"{str(policy['upload_dir']).strip('/')}/{object_name}"
        mime = "audio/mpeg" if suffix == ".mp3" else "audio/mp4"
        fields = {
            "OSSAccessKeyId": policy["oss_access_key_id"],
            "Signature": policy["signature"],
            "policy": policy["policy"],
            "x-oss-object-acl": policy.get("x_oss_object_acl", "private"),
            "x-oss-forbid-overwrite": policy.get("x_oss_forbid_overwrite", "true"),
            "key": key,
            "success_action_status": "200",
        }
        try:
            with path.open("rb") as handle:
                files = {"file": (object_name, handle, mime)}
                response = self.session.post(
                    str(policy["upload_host"]),
                    data=fields,
                    files=files,
                    timeout=(15, 900),
                )
        except requests.RequestException as exc:
            raise ApiError(tr("error.network")) from exc
        if response.status_code != 200:
            raise ApiError(
                tr("error.upload"),
                status_code=response.status_code,
                retryable=True,
            )
        return UploadedAudio(url=f"oss://{key}", bytes_sent=size)

    # ------------------------------------------------------------------- ASR
    def submit_transcription(
        self,
        audio_url: str,
        *,
        model: str,
        api_style: str,
        language_param: str,
        language_code: str | None,
        cancel_event: threading.Event | None = None,
    ) -> str:
        input_obj: dict[str, Any]
        if api_style == "file_url":
            input_obj = {"file_url": audio_url}
        else:
            input_obj = {"file_urls": [audio_url]}
        parameters: dict[str, Any] = {
            "channel_id": [0],
            "enable_itn": True,
        }
        if language_code and language_code != "auto":
            parameters[language_param] = [language_code] if language_param == "language_hints" else language_code
        if api_style == "file_url":
            parameters["enable_words"] = True
        payload = {"model": model, "input": input_obj, "parameters": parameters}
        response = self._request(
            "POST",
            f"{self.base_url}/api/v1/services/audio/asr/transcription",
            json_body=payload,
            headers={
                "X-DashScope-Async": "enable",
                "X-DashScope-OssResourceResolve": "enable",
            },
            timeout=(15, 90),
            cancel_event=cancel_event,
        )
        try:
            body = response.json()
            task_id = body["output"]["task_id"]
        except (ValueError, KeyError, TypeError) as exc:
            raise ApiError(tr("error.asr_empty")) from exc
        return str(task_id)

    def wait_for_transcription(
        self,
        task_id: str,
        *,
        cancel_event: threading.Event | None = None,
        on_status: Any = None,
    ) -> dict:
        started = time.monotonic()
        while True:
            if cancel_event and cancel_event.is_set():
                raise CancelledError()
            if time.monotonic() - started > POLL_TIMEOUT_SECONDS:
                raise ApiError(tr("error.timeout"))
            response = self._request(
                "GET",
                f"{self.base_url}/api/v1/tasks/{task_id}",
                headers={"X-DashScope-OssResourceResolve": "enable"},
                timeout=(15, 60),
                cancel_event=cancel_event,
            )
            try:
                body = response.json()
            except ValueError as exc:
                raise ApiError(tr("error.api")) from exc
            output = body.get("output") if isinstance(body, dict) else None
            if not isinstance(output, dict):
                raise ApiError(tr("error.api"))
            status = str(output.get("task_status", "")).upper()
            if on_status:
                on_status(status)
            if status == "SUCCEEDED":
                return body
            if status in ("FAILED", "UNKNOWN"):
                code = _safe_text(output.get("code", ""))
                message = _safe_text(output.get("message", ""))
                raise ApiError(
                    friendly_http_error(400, code, message),
                    code=code,
                    detail=message,
                )
            # PENDING / RUNNING -> wait. The API has no percentage.
            if cancel_event:
                if cancel_event.wait(POLL_INTERVAL_SECONDS):
                    raise CancelledError()
            else:
                time.sleep(POLL_INTERVAL_SECONDS)

    @staticmethod
    def extract_transcription_url(task_body: dict) -> str:
        output = task_body.get("output") if isinstance(task_body, dict) else None
        if not isinstance(output, dict):
            raise ApiError(tr("error.asr_empty"))
        result = output.get("result")
        if isinstance(result, dict) and result.get("transcription_url"):
            return str(result["transcription_url"])
        results = output.get("results")
        if not isinstance(results, list) and isinstance(result, dict):
            results = result.get("results")
        if isinstance(results, list):
            for item in results:
                if not isinstance(item, dict):
                    continue
                status = str(item.get("subtask_status", "SUCCEEDED")).upper()
                if status in ("SUCCEEDED", "SUCCESS") and item.get("transcription_url"):
                    return str(item["transcription_url"])
            for item in results:
                if isinstance(item, dict) and item.get("transcription_url"):
                    return str(item["transcription_url"])
        raise ApiError(tr("error.asr_empty"))

    def download_transcription(
        self,
        url: str,
        *,
        cancel_event: threading.Event | None = None,
    ) -> dict:
        if not url.startswith(("https://", "http://")):
            raise ApiError(tr("error.api"), detail="invalid transcription URL")
        try:
            response = self.session.get(url, timeout=(15, 120))
        except requests.RequestException as exc:
            raise ApiError(tr("error.network")) from exc
        if response.status_code != 200:
            raise ApiError(tr("error.api"), status_code=response.status_code)
        try:
            return response.json()
        except ValueError as exc:
            raise ApiError(tr("error.asr_empty")) from exc

    # ------------------------------------------------------------- translation
    def translate(
        self,
        text: str,
        *,
        model: str,
        source_lang: str,
        target_lang: str,
        cancel_event: threading.Event | None = None,
    ) -> str:
        if cancel_event and cancel_event.is_set():
            raise CancelledError()
        payload = {
            "model": model,
            "messages": [{"role": "user", "content": text}],
            "translation_options": {
                "source_lang": source_lang,
                "target_lang": target_lang,
            },
            "stream": False,
        }
        response = self._request(
            "POST",
            f"{self.base_url}/compatible-mode/v1/chat/completions",
            json_body=payload,
            timeout=(15, 120),
            cancel_event=cancel_event,
        )
        try:
            body = response.json()
            content = body["choices"][0]["message"]["content"]
        except (ValueError, KeyError, IndexError, TypeError) as exc:
            raise ApiError(tr("error.translate_empty")) from exc
        if isinstance(content, list):
            content = "".join(
                str(part.get("text", "")) if isinstance(part, dict) else str(part)
                for part in content
            )
        result = str(content or "").strip()
        if not result:
            raise ApiError(tr("error.translate_empty"))
        return result

    def test_key(self, model: str) -> None:
        """Validate credentials without uploading media or generating tokens."""

        self.get_upload_policy(model)


def parse_transcription_payload(payload: dict) -> list[dict]:
    """Accept both ``file_urls`` and ``file_url`` result envelopes."""

    from qwen_subtitle.core.subtitle import parse_sentences

    sentences = parse_sentences(payload)
    if sentences:
        return sentences
    # Some filetrans envelopes nest the transcript JSON under result.
    if isinstance(payload, dict):
        for key in ("transcription", "data", "result"):
            nested = payload.get(key)
            if isinstance(nested, dict):
                sentences = parse_sentences(nested)
                if sentences:
                    return sentences
    return []



