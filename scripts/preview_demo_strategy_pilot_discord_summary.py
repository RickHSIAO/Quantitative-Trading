"""TASK-014BQ -- preview-only Discord Chinese daily summary for the pilot.

Strictly OFFLINE / PREVIEW ONLY. It reads the latest PilotDailyRecord from the
append-only store and prints a Chinese daily summary.

It reads NO webhook, performs ZERO HTTP requests, and sends NOTHING to Discord.
"""

from __future__ import annotations

import argparse
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


def _position(rec: Mapping[str, Any]) -> str:
    sym = rec.get("current_position_symbol") or ""
    if not sym:
        return "無持倉 (FLAT)"
    return f"{sym} {rec.get('current_position_side', '')} {rec.get('current_position_qty', '0')}".strip()


def build_discord_summary(pilot_id: str, rec: Mapping[str, Any] | None) -> str:
    """Build a sanitized Chinese daily summary (preview only)."""
    rec = dict(rec or {})
    alerts = rec.get("alerts_triggered") or []
    alerts_text = "、".join(str(a) for a in alerts) if alerts else "無"
    lines = [
        f"【Bybit Demo 策略試運行日報】(preview, 未發送)",
        f"Pilot ID：{pilot_id}（第 {rec.get('pilot_day', 0)} 天）",
        f"日期：{rec.get('date', '')}",
        f"Runner 狀態：{rec.get('runner_status', '')}",
        f"訊號 / 下單 / 成交：{rec.get('signal_count', 0)} / {rec.get('order_count', 0)} / {rec.get('filled_count', 0)}",
        f"已平倉交易數：{rec.get('closed_trade_count', 0)}",
        f"已實現 PnL：{rec.get('realized_pnl_usdt', '0')} USDT",
        f"交易手續費：{rec.get('trading_fees_usdt', '0')} USDT",
        f"資金費 (funding)：{rec.get('funding_pnl_usdt', '0')} USDT",
        f"當日淨 PnL：{rec.get('daily_net_pnl_usdt', '0')} USDT",
        f"累計淨 PnL：{rec.get('cumulative_net_pnl_usdt', '0')} USDT",
        f"當日 / 累計報酬率：{rec.get('daily_return_pct', '0')}% / {rec.get('cumulative_return_pct', '0')}%",
        f"最大回撤：{rec.get('max_drawdown_pct', '0')}%",
        f"目前持倉：{_position(rec)}",
        f"Notion 同步狀態：{rec.get('notion_sync_status', '')}",
        f"Excel 匯出狀態：{rec.get('excel_export_status', '')}",
        f"警示：{alerts_text}",
        f"備註：{rec.get('notes', '') or '無'}",
    ]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(prog="preview_demo_strategy_pilot_discord_summary.py",
                                description="Preview-only Chinese Discord daily summary (offline).")
    p.add_argument("--pilot-id", required=True)
    p.add_argument("--output-root", default=None)
    args = p.parse_args(argv)

    rec = _latest_daily(args.pilot_id, args.output_root)
    print(build_discord_summary(args.pilot_id, rec))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
