from __future__ import annotations

import json
import urllib.error
import urllib.request
from dataclasses import asdict, dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class HttpResult:
    status_code: int
    text: str = ""


class HttpClient(Protocol):
    def post_json(self, url: str, payload: dict[str, Any], timeout_seconds: int) -> HttpResult:
        ...


class DefaultHttpClient:
    JSON_HEADERS = {
        "Content-Type": "application/json",
        "Accept": "application/json",
        "User-Agent": "QuantMonitor/1.0",
    }

    def post_json(self, url: str, payload: dict[str, Any], timeout_seconds: int) -> HttpResult:
        body = json.dumps(payload, ensure_ascii=False).encode("utf-8")
        request = urllib.request.Request(
            url,
            data=body,
            headers=self.JSON_HEADERS,
            method="POST",
        )
        try:
            with urllib.request.urlopen(request, timeout=timeout_seconds) as response:
                text = response.read().decode("utf-8", errors="replace")
                return HttpResult(status_code=int(response.status), text=text)
        except urllib.error.HTTPError as exc:
            text = exc.read().decode("utf-8", errors="replace")
            return HttpResult(status_code=int(exc.code), text=text)


@dataclass(frozen=True)
class ChannelResult:
    channel: str
    enabled: bool
    dry_run: bool
    test_send: bool
    status: str
    detail: str
    delivered_count: int = 0
    error_count: int = 0
    external_post_attempted: bool = False
    endpoint: str = ""
    diagnostics: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


def format_alert_message(alert: Any, bot_name: str) -> str:
    data = alert.to_dict() if hasattr(alert, "to_dict") else dict(alert)
    return "\n".join(
        [
            f"[{data.get('severity', 'INFO')}] {bot_name}",
            f"Time: {data.get('timestamp', '')} UTC",
            f"Category: {data.get('category', '')}",
            f"Message: {data.get('message', '')}",
            f"Action: {data.get('action_required', '')}",
            f"Paper: {data.get('paper_execution_status', 'FORBIDDEN')}",
            f"Live: {data.get('live_trading_status', 'FORBIDDEN')}",
        ]
    )
