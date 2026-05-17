from __future__ import annotations

import re
from collections.abc import Iterable


REDACTED = "<redacted>"

_SECRET_PATTERNS = [
    re.compile(r"\b\d{6,}:[A-Za-z0-9_-]{20,}\b"),
    re.compile(r"https://(?:discord(?:app)?\.com)/api/webhooks/[^\s'\"<>]+", re.IGNORECASE),
]


def redact_value(value: str | None) -> str:
    if not value:
        return ""
    return REDACTED


def redact_text(text: str, secrets: Iterable[str] = ()) -> str:
    out = text
    for secret in secrets:
        if secret:
            out = out.replace(secret, REDACTED)
    for pattern in _SECRET_PATTERNS:
        out = pattern.sub(REDACTED, out)
    return out


def redacted_telegram_endpoint() -> str:
    return "https://api.telegram.org/bot<redacted>/sendMessage"


def redacted_discord_endpoint() -> str:
    return "https://discord.com/api/webhooks/<redacted>"
