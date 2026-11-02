from __future__ import annotations

from qwen_subtitle.core.errors import friendly_http_error
from qwen_subtitle.i18n import set_language


def test_free_tier_only_has_actionable_message() -> None:
    set_language("zh")
    message = friendly_http_error(
        403,
        "AllocationQuota.FreeTierOnly",
        "free tier quota does not cover this model",
    )
    assert "免费额度" in message
    assert "Flash" in message


def test_access_denied_mentions_model_access() -> None:
    set_language("zh")
    message = friendly_http_error(403, "AccessDenied", "model is not enabled")
    assert "权限" in message
    assert "Flash" in message
    set_language("zh")
