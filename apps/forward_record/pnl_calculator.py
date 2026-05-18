from __future__ import annotations

from typing import Any

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig


def build_pnl_payload(config: ForwardRecordConfig, positions: pd.DataFrame, variant: str, day_number: int) -> dict[str, Any]:
    weights = positions["weight"].astype(float)
    nonzero = positions[weights.abs().gt(1e-15)].copy()
    top = nonzero.assign(abs_weight=nonzero["weight"].abs()).sort_values("abs_weight", ascending=False).head(1)
    return {
        "date": config.output_date,
        "variant": variant,
        "day_number": int(day_number),
        "clock_started": bool(config.clock_started),
        "dry_run": bool(config.dry_run),
        "nav_usd": float(config.paper_config.initial_nav_usd),
        "nav_change_usd": 0.0,
        "daily_pnl_pct": 0.0,
        "cumulative_pnl_pct": 0.0,
        "gross_exposure": float(weights.abs().sum()),
        "net_exposure": float(weights.sum()),
        "long_weight_sum": float(weights[weights > 0].sum()),
        "short_weight_sum": float(weights[weights < 0].sum()),
        "top1_symbol": "" if top.empty else str(top["symbol"].iloc[0]),
        "top1_symbol_weight": 0.0 if top.empty else float(top["weight"].iloc[0]),
        "n_longs": int((weights > 0).sum()),
        "n_shorts": int((weights < 0).sum()),
        "funding_cost_usd": 0.0,
        "fee_cost_usd": 0.0,
        "slippage_cost_usd": 0.0,
        "overlay_events": [],
        "data_source": str(positions["data_source"].iloc[0]) if not positions.empty else config.data_source,
        "annualization": float(config.paper_config.annualization_factor),
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
    }

