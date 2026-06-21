"""TASK-014BR -- gated Discord daily notification adapter for the demo pilot.

The network action is DISABLED unless ``allow_network=True`` is explicitly
passed. Tests inject a fake transport; no test performs HTTP. The webhook URL is
read from the existing approved env var only when a real send is authorized, and
is NEVER printed, serialized, or placed in any journal, audit log, result, or
exception message.

The Chinese daily summary clearly states ``DRY-RUN／尚未授權自動下單``.

No order endpoints. Does not import the live order-execution stack.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Any, Mapping

# Reuse the existing approved Discord webhook env mechanism.
DISCORD_WEBHOOK_ENV = "MONITOR_DISCORD_WEBHOOK_URL"

NOTIFY_PASS = "PASS"
NOTIFY_FAIL = "FAIL"
NOTIFY_SKIPPED = "SKIPPED"

DRY_RUN_WARNING = "DRY-RUN／尚未授權自動下單"


@dataclass(frozen=True)
class DiscordNotifyResult:
    status: str           # PASS / FAIL / SKIPPED
    detail: str           # sanitized; never contains the webhook URL
    network_attempted: bool

    def to_dict(self) -> dict[str, Any]:
        return {"status": self.status, "detail": self.detail, "network_attempted": self.network_attempted}


def build_discord_summary(
    pilot_id: str,
    daily_record: Mapping[str, Any],
    *,
    data_status: str = "",
    proposed_action_count: int = 0,
    plan_fingerprint: str = "",
) -> str:
    """Build the sanitized Chinese dry-run daily summary."""
    rec = dict(daily_record or {})
    sym = rec.get("current_position_symbol") or ""
    position = "無持倉 (FLAT)" if not sym else f"{sym} {rec.get('current_position_side', '')} {rec.get('current_position_qty', '0')}".strip()
    alerts = rec.get("alerts_triggered") or []
    alerts_text = "、".join(str(a) for a in alerts) if alerts else "無"
    fp_short = (plan_fingerprint or "")[:12]
    lines = [
        f"【Bybit Demo 策略試運行日報】{DRY_RUN_WARNING}",
        f"Pilot ID：{pilot_id}（第 {rec.get('pilot_day', 0)} 天）",
        f"日期：{rec.get('date', '')}",
        f"資料狀態：{data_status or rec.get('runner_status', '')}",
        f"訊號數：{rec.get('signal_count', 0)}",
        f"提議動作數（hypothetical）：{proposed_action_count}",
        f"下單 / 成交：{rec.get('order_count', 0)} / {rec.get('filled_count', 0)}（尚未授權自動下單）",
        f"當日淨 PnL：{rec.get('daily_net_pnl_usdt', '0')} USDT",
        f"累計淨 PnL：{rec.get('cumulative_net_pnl_usdt', '0')} USDT",
        f"最大回撤：{rec.get('max_drawdown_pct', '0')}%",
        f"目前持倉：{position}",
        f"Excel 匯出狀態：{rec.get('excel_export_status', '')}",
        f"Notion 同步狀態：{rec.get('notion_sync_status', '')}",
        f"警示：{alerts_text}",
        f"Plan 指紋（短）：{fp_short}",
    ]
    return "\n".join(lines)


def _sanitize(detail: str, webhook: str) -> str:
    if webhook and webhook in detail:
        detail = detail.replace(webhook, "***")
    return detail


class DiscordDailyNotify:
    """Gated Discord notifier. ``transport`` (when provided) must expose
    ``post(webhook_url, content)``; tests inject a fake."""

    def __init__(self, *, allow_network: bool = False, transport: Any = None,
                 env: Mapping[str, str] | None = None) -> None:
        self.allow_network = allow_network
        self._transport = transport
        self._env = env if env is not None else os.environ

    def notify(self, message: str) -> DiscordNotifyResult:
        if not self.allow_network:
            return DiscordNotifyResult(NOTIFY_SKIPPED, "discord network disabled (allow_network=False)", False)
        webhook = self._env.get(DISCORD_WEBHOOK_ENV, "").strip()
        if not webhook:
            return DiscordNotifyResult(NOTIFY_FAIL, "discord webhook absent", False)
        if self._transport is None:
            return DiscordNotifyResult(NOTIFY_FAIL, "no discord transport injected", False)
        try:
            self._transport.post(webhook_url=webhook, content=message)
            return DiscordNotifyResult(NOTIFY_PASS, "ok", True)
        except Exception as exc:  # noqa: BLE001
            return DiscordNotifyResult(NOTIFY_FAIL, _sanitize(f"discord error: {exc}", webhook), True)


__all__ = [
    "DISCORD_WEBHOOK_ENV",
    "DRY_RUN_WARNING",
    "DiscordDailyNotify",
    "DiscordNotifyResult",
    "NOTIFY_FAIL",
    "NOTIFY_PASS",
    "NOTIFY_SKIPPED",
    "build_discord_summary",
]
