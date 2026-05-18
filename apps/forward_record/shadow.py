from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig
from apps.forward_record.market_data import MarketDataProvider, latest_prices_by_symbol
from apps.forward_record.primary import TrackRecord, _decorate_positions
from src.variants.task008 import VARIANT_SPECS


@dataclass(frozen=True)
class ShadowAdapterStatus:
    variant: str
    source: str
    spec_found: bool


def build_shadow_record(config: ForwardRecordConfig, provider: MarketDataProvider) -> TrackRecord:
    status = adapter_status(config)
    if not status.spec_found:
        raise ValueError(f"TASK-008 variant not found: {config.shadow_variant}")
    detail = pd.read_csv(config.task008_detail_path, parse_dates=["date"])
    required = {"variant", "date", "symbol", "original_weight", "variant_weight"}
    missing = required - set(detail.columns)
    if missing:
        raise ValueError(f"TASK-008 detail missing columns: {sorted(missing)}")
    detail = detail[detail["variant"].astype(str).eq(config.shadow_variant)].copy()
    if detail.empty:
        raise ValueError(f"TASK-008 detail has no rows for {config.shadow_variant}")
    detail["date"] = pd.to_datetime(detail["date"]).dt.normalize()
    record_ts = pd.Timestamp(config.output_date).normalize()
    dates = sorted(detail.loc[detail["date"].le(record_ts), "date"].drop_duplicates())
    if not dates:
        raise ValueError(f"no TASK-008 shadow weights on or before {record_ts.date()}")
    signal_date = pd.Timestamp(dates[-1]).normalize()
    frame = detail[detail["date"].eq(signal_date)].copy()
    frame = frame.rename(columns={"variant_weight": "weight"})
    frame["overlay_rules_applied"] = ""
    frame["excluded_reason"] = ""
    frame["funding_rate_30d_avg"] = 0.0
    prices = provider.load_prices(signal_date)
    positions = _decorate_positions(
        frame.loc[:, ["date", "symbol", "weight", "original_weight", "funding_rate_30d_avg", "overlay_rules_applied", "excluded_reason"]],
        latest_prices_by_symbol(prices, signal_date),
        config,
        config.shadow_variant,
        record_ts,
        signal_date,
        provider.data_source,
    )
    return TrackRecord(
        variant=config.shadow_variant,
        record_date=record_ts.strftime("%Y-%m-%d"),
        signal_date=signal_date.strftime("%Y-%m-%d"),
        positions=positions,
        overlay_check={
            "date": config.output_date,
            "variant": config.shadow_variant,
            "shadow_adapter": status.__dict__,
            "overlay_pass": True,
            "paper_execution_status": config.paper_execution_status,
            "live_trading_status": config.live_trading_status,
        },
        source_position_count=int(len(frame)),
    )


def adapter_status(config: ForwardRecordConfig) -> ShadowAdapterStatus:
    return ShadowAdapterStatus(
        variant=config.shadow_variant,
        source=str(config.task008_detail_path),
        spec_found=any(spec.name == config.shadow_variant for spec in VARIANT_SPECS),
    )

