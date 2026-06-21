"""TASK-014BQ -- preview-only Notion upsert payload for the pilot daily record.

Strictly OFFLINE / PREVIEW ONLY. It reads the latest PilotDailyRecord from the
append-only store, builds a sanitized Notion upsert payload, and prints JSON.

It performs ZERO HTTP requests, reads NO Notion token, and does NOT import the
production Notion client/synchronizer. No real sync is performed.
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from typing import Any, Mapping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.demo_strategy_pilot_store import PilotStore  # noqa: E402


def _latest_daily(pilot_id: str, output_root: str | None) -> Mapping[str, Any] | None:
    rows = PilotStore(pilot_id, output_root).read_daily()
    if not rows:
        return None
    return sorted(rows, key=lambda r: str(r.get("date", "")))[-1]


def _current_position(rec: Mapping[str, Any]) -> str:
    sym = rec.get("current_position_symbol") or ""
    side = rec.get("current_position_side") or ""
    qty = rec.get("current_position_qty") or "0"
    if not sym:
        return "FLAT"
    return f"{sym} {side} {qty}".strip()


def build_notion_payload(pilot_id: str, rec: Mapping[str, Any] | None) -> dict[str, Any]:
    """Build a sanitized Notion upsert payload. Idempotent key = pilot_id+date."""
    rec = dict(rec or {})
    date = str(rec.get("date", ""))
    idempotency_key = f"{pilot_id}:{date}"
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
        "Current Position": _current_position(rec),
        "Alerts Triggered": rec.get("alerts_triggered", []),
        "Excel Export Status": rec.get("excel_export_status", ""),
        "Notion Sync Status": rec.get("notion_sync_status", ""),
        "Discord Notify Status": rec.get("discord_notify_status", ""),
        "Notes": rec.get("notes", ""),
    }
    return {
        "preview_only": True,
        "no_http_performed": True,
        "notion_token_read": False,
        "operation": "upsert",
        "idempotency_key": idempotency_key,
        "properties": properties,
    }


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="preview_demo_strategy_pilot_notion_payload.py",
                                description="Preview-only sanitized Notion payload (offline).")
    p.add_argument("--pilot-id", required=True)
    p.add_argument("--output-root", default=None)
    args = p.parse_args(argv)

    rec = _latest_daily(args.pilot_id, args.output_root)
    payload = build_notion_payload(args.pilot_id, rec)
    print(json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
