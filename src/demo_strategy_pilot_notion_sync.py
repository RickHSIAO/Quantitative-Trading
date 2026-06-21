"""TASK-014BR -- gated Notion daily upsert adapter for the demo pilot.

The network action is DISABLED unless ``allow_network=True`` is explicitly
passed. Tests inject a fake transport; no test performs HTTP. The Notion token
is read from the existing approved env var only when a real send is authorized,
and is NEVER printed, serialized, or placed in any payload preview, journal,
audit log, or exception message.

Idempotency key: ``<pilot_id>:<YYYY-MM-DD>`` -- one Notion page per pilot/date;
a rerun updates the same record and never creates a second date row.

No order endpoints. Does not import the live order-execution stack.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import Any, Mapping

# Reuse the existing approved Notion credential env mechanism.
NOTION_TOKEN_ENV = "NOTION_TOKEN"
NOTION_PILOT_DATABASE_ID_ENV = "NOTION_PILOT_DATABASE_ID"
NOTION_FORWARD_DATABASE_ID_ENV = "NOTION_FORWARD_VALIDATION_DATABASE_ID"
NOTION_API_BASE = "https://api.notion.com/v1"
NOTION_API_VERSION = "2022-06-28"

SYNC_PASS = "PASS"
SYNC_FAIL = "FAIL"
SYNC_SKIPPED = "SKIPPED"


@dataclass(frozen=True)
class NotionSyncResult:
    status: str           # PASS / FAIL / SKIPPED
    operation: str        # upsert / none
    idempotency_key: str
    page_action: str      # created / updated / none
    detail: str           # sanitized; never contains the token
    network_attempted: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "operation": self.operation,
            "idempotency_key": self.idempotency_key,
            "page_action": self.page_action,
            "detail": self.detail,
            "network_attempted": self.network_attempted,
        }


def build_notion_payload(
    pilot_id: str,
    daily_record: Mapping[str, Any],
    *,
    plan_fingerprint: str = "",
    input_fingerprint: str = "",
) -> dict[str, Any]:
    """Build a sanitized Notion upsert payload (no token, no secrets)."""
    rec = dict(daily_record or {})
    date = str(rec.get("date", ""))
    sym = rec.get("current_position_symbol") or ""
    current_position = (
        "FLAT" if not sym
        else f"{sym} {rec.get('current_position_side', '')} {rec.get('current_position_qty', '0')}".strip()
    )
    properties = {
        "Date": date,
        "Pilot ID": pilot_id,
        "Pilot Day": rec.get("pilot_day", 0),
        "Runner Status": rec.get("runner_status", ""),
        "Signal Count": rec.get("signal_count", 0),
        "Order Count": rec.get("order_count", 0),
        "Filled Count": rec.get("filled_count", 0),
        "Closed Trade Count": rec.get("closed_trade_count", 0),
        "Realized PnL USDT": rec.get("realized_pnl_usdt", "0"),
        "Trading Fees USDT": rec.get("trading_fees_usdt", "0"),
        "Funding PnL USDT": rec.get("funding_pnl_usdt", "0"),
        "Daily Net PnL USDT": rec.get("daily_net_pnl_usdt", "0"),
        "Cumulative Net PnL USDT": rec.get("cumulative_net_pnl_usdt", "0"),
        "Daily Return %": rec.get("daily_return_pct", "0"),
        "Cumulative Return %": rec.get("cumulative_return_pct", "0"),
        "Max Drawdown %": rec.get("max_drawdown_pct", "0"),
        "Current Position": current_position,
        "Alerts Triggered": rec.get("alerts_triggered", []),
        "Excel Export Status": rec.get("excel_export_status", ""),
        "Notion Sync Status": rec.get("notion_sync_status", ""),
        "Discord Notify Status": rec.get("discord_notify_status", ""),
        "Notes": rec.get("notes", ""),
        "Plan Fingerprint": plan_fingerprint,
        "Input Fingerprint": input_fingerprint,
    }
    return {
        "preview_only_without_allow_network": True,
        "notion_token_in_payload": False,
        "operation": "upsert",
        "idempotency_key": f"{pilot_id}:{date}",
        "properties": properties,
    }


def _sanitize(detail: str, token: str) -> str:
    if token and token in detail:
        detail = detail.replace(token, "***")
    return detail


class NotionDailySync:
    """Gated Notion upsert. ``transport`` (when provided) must expose
    ``query(database_id, idempotency_key, headers)`` and
    ``upsert(database_id, page_id, properties, headers)``; tests inject a fake.
    """

    def __init__(self, *, allow_network: bool = False, transport: Any = None,
                 env: Mapping[str, str] | None = None) -> None:
        self.allow_network = allow_network
        self._transport = transport
        self._env = env if env is not None else os.environ

    def _database_id(self) -> str:
        return (self._env.get(NOTION_PILOT_DATABASE_ID_ENV, "")
                or self._env.get(NOTION_FORWARD_DATABASE_ID_ENV, "")).strip()

    def upsert(self, payload: Mapping[str, Any]) -> NotionSyncResult:
        key = str(payload.get("idempotency_key", ""))
        if not self.allow_network:
            return NotionSyncResult(SYNC_SKIPPED, "none", key, "none", "NETWORK_NOT_ALLOWED", False)
        # An explicit allow flag with no injected transport means the credential
        # / database id was absent at construction time -> fail closed.
        if self._transport is None:
            return NotionSyncResult(SYNC_FAIL, "upsert", key, "none", "CREDENTIAL_MISSING", False)
        token = self._env.get(NOTION_TOKEN_ENV, "").strip()
        db_id = self._database_id()
        headers = {"Notion-Version": NOTION_API_VERSION, "Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        props = dict(payload.get("properties", {}))
        try:
            existing = self._transport.query(database_id=db_id, idempotency_key=key,
                                             headers=headers, properties=props)
            page_id = existing.get("page_id") if isinstance(existing, Mapping) else None
            self._transport.upsert(database_id=db_id, page_id=page_id,
                                   properties=props, headers=headers)
            action = "updated" if page_id else "created"
            return NotionSyncResult(SYNC_PASS, "upsert", key, action, "ok", True)
        except Exception as exc:  # noqa: BLE001
            detail = _sanitize(str(exc), token)
            name = type(exc).__name__
            if name == "NotionDuplicateIdentityConflict" or "NOTION_DUPLICATE_IDENTITY_CONFLICT" in detail:
                detail = "NOTION_DUPLICATE_IDENTITY_CONFLICT"
            elif name == "NotionSchemaIncompatible" or "NOTION_DATABASE_SCHEMA_INCOMPATIBLE" in detail:
                detail = "NOTION_DATABASE_SCHEMA_INCOMPATIBLE"
            elif "HTTP_DELIVERY_FAILED" not in detail:
                detail = f"HTTP_DELIVERY_FAILED: {detail}"
            return NotionSyncResult(SYNC_FAIL, "upsert", key, "none", detail[:300], True)


__all__ = [
    "NOTION_API_BASE",
    "NOTION_API_VERSION",
    "NOTION_FORWARD_DATABASE_ID_ENV",
    "NOTION_PILOT_DATABASE_ID_ENV",
    "NOTION_TOKEN_ENV",
    "NotionDailySync",
    "NotionSyncResult",
    "SYNC_FAIL",
    "SYNC_PASS",
    "SYNC_SKIPPED",
    "build_notion_payload",
]
