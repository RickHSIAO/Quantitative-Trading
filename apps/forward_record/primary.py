from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.market_data import MarketDataProvider, latest_prices_by_symbol, check_price_freshness
from apps.forward_record.signal_loader import load_latest_positions
from apps.paper_trading.overlay import apply_variant_overlay


@dataclass(frozen=True)
class TrackRecord:
    variant: str
    record_date: str
    signal_date: str
    positions: pd.DataFrame
    overlay_check: dict[str, Any]
    source_position_count: int


def build_primary_record(config: ForwardRecordConfig, provider: MarketDataProvider) -> TrackRecord:
    record_ts = pd.Timestamp(config.output_date).normalize()
    loaded = load_latest_positions(config, record_ts)
    funding = provider.load_funding(loaded.signal_date)
    # TASK-011A: load prices at record_ts (today) so hypothetical_fill_px
    # reflects current market price, not the frozen signal-date open price.
    prices = provider.load_prices(record_ts)
    freshness = check_price_freshness(prices, record_ts,
                                      symbols=loaded.positions["symbol"].tolist())
    print(f"  data_freshness: {freshness}")
    overlay = apply_variant_overlay(
        loaded.positions,
        funding,
        loaded.signal_date,
        config.paper_config,
        variant=config.primary_variant,
    )
    positions = _decorate_positions(
        overlay.positions,
        latest_prices_by_symbol(prices, record_ts),
        config,
        config.primary_variant,
        record_ts,
        loaded.signal_date,
        provider.data_source,
    )
    return TrackRecord(
        variant=config.primary_variant,
        record_date=record_ts.strftime("%Y-%m-%d"),
        signal_date=loaded.signal_date.strftime("%Y-%m-%d"),
        positions=positions,
        overlay_check=_overlay_check(config, overlay.events, positions),
        source_position_count=int(len(loaded.positions)),
    )


def _decorate_positions(
    positions: pd.DataFrame,
    prices: pd.DataFrame,
    config: ForwardRecordConfig,
    variant: str,
    record_date: pd.Timestamp,
    signal_date: pd.Timestamp,
    data_source: str,
) -> pd.DataFrame:
    frame = positions.copy()
    frame = frame.merge(prices.rename(columns={"open": "hypothetical_fill_px"}), on="symbol", how="left")
    frame["record_date"] = record_date.strftime("%Y-%m-%d")
    frame["date"] = record_date.strftime("%Y-%m-%d")
    frame["signal_date"] = signal_date.strftime("%Y-%m-%d")
    frame["side"] = frame["weight"].map(lambda value: "long" if value > 0 else ("short" if value < 0 else "flat"))
    frame["weight_raw"] = frame["original_weight"].astype(float)
    frame["position_usd"] = frame["weight"].astype(float) * float(config.paper_config.initial_nav_usd)
    frame["data_source"] = data_source
    frame["variant"] = variant
    frame["dry_run"] = bool(config.dry_run)
    frame["clock_started"] = bool(config.clock_started)
    frame["paper_execution_status"] = config.paper_execution_status
    frame["live_trading_status"] = config.live_trading_status
    rules = frame["overlay_rules_applied"].fillna("").astype(str)
    frame["overlay_rule1_applied"] = rules.str.contains("long_cap_50pct", regex=False)
    frame["overlay_rule2_applied"] = rules.str.contains("symbol_cap_5pct", regex=False)
    frame["overlay_rule3_applied"] = rules.str.contains("funding_filter_0.03pct_8h", regex=False)
    ordered = [
        "date",
        "record_date",
        "signal_date",
        "symbol",
        "side",
        "weight",
        "weight_raw",
        "funding_rate_30d_avg",
        "overlay_rule1_applied",
        "overlay_rule2_applied",
        "overlay_rule3_applied",
        "overlay_rules_applied",
        "excluded_reason",
        "hypothetical_fill_px",
        "position_usd",
        "data_source",
        "variant",
        "dry_run",
        "clock_started",
        "paper_execution_status",
        "live_trading_status",
    ]
    return frame.loc[:, ordered].sort_values("symbol").reset_index(drop=True)


def _overlay_check(config: ForwardRecordConfig, events: list[dict[str, Any]], positions: pd.DataFrame) -> dict[str, Any]:
    rules = positions["overlay_rules_applied"].fillna("").astype(str)
    return {
        "date": config.output_date,
        "variant": config.primary_variant,
        "rule1_long_cap_50pct": {
            "triggered": bool(rules.str.contains("long_cap_50pct", regex=False).any()),
        },
        "rule2_symbol_cap_5pct": {
            "triggered": bool(rules.str.contains("symbol_cap_5pct", regex=False).any()),
            "capped_symbols": positions.loc[
                rules.str.contains("symbol_cap_5pct", regex=False), "symbol"
            ].tolist(),
        },
        "rule3_funding_filter_0.03pct_8h": {
            "triggered": bool(rules.str.contains("funding_filter_0.03pct_8h", regex=False).any()),
            "filtered_symbols": positions.loc[
                rules.str.contains("funding_filter_0.03pct_8h", regex=False), "symbol"
            ].tolist(),
        },
        "overlay_events": events,
        "overlay_pass": True,
        "paper_execution_status": config.paper_execution_status,
        "live_trading_status": config.live_trading_status,
    }

