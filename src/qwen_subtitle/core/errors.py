"""Typed errors with user-safe messages.

Exception messages must never contain an API key, full local path, or media
content.  The UI can display ``user_message`` directly.
"""

from __future__ import annotations


class AppError(RuntimeError):
    def __init__(self, user_message: str, *, detail: str = "") -> None:
        super().__init__(user_message)
        self.user_message = user_message
        self.detail = detail


class CancelledError(AppError):
    def __init__(self) -> None:
        super().__init__("任务已取消。")


class MediaError(AppError):
    pass


class ApiError(AppError):
    def __init__(
        self,
        user_message: str,
        *,
        status_code: int | None = None,
        code: str = "",
        retryable: bool = False,
        detail: str = "",
    ) -> None:
        super().__init__(user_message, detail=detail)
        self.status_code = status_code
        self.code = code
        self.retryable = retryable


class SecretError(AppError):
    pass


def friendly_http_error(status_code: int, code: str, message: str) -> str:
    """Map common DashScope failures to localised, actionable messages."""

    from qwen_subtitle.i18n import tr

    lowered = f"{code} {message}".lower()
    if "allocationquota" in lowered or "freetieronly" in lowered:
        return tr("error.free_tier_only")
    if status_code == 401 or "invalidapikey" in lowered or "unauthorized" in lowered:
        return tr("error.auth")
    if status_code == 403 or "accessdenied" in lowered or "access denied" in lowered:
        return tr("error.model_access")
    if status_code == 429 or "throttl" in lowered or "rate" in lowered:
        return tr("error.rate")
    if "quota" in lowered or "arrearage" in lowered or "balance" in lowered:
        return tr("error.quota")
    if "file" in lowered and ("403" in lowered or "forbidden" in lowered):
        return tr("error.file_access")
    if status_code >= 500:
        return tr("error.server")
    return tr("error.api_generic")
