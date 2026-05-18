from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from apps.paper_trading.config import PaperTradingConfig


@dataclass(frozen=True)
class OverlayResult:
    positions: pd.DataFrame
    events: list[dict[str, Any]]


def apply_variant_overlay(
    positions: pd.DataFrame,
    funding: pd.DataFrame,
    as_of_date: str | pd.Timestamp,
    config: PaperTradingConfig,
    variant: str | None = None,
) -> OverlayResult:
    variant_name = variant or config.primary_variant
    frame = _positions_for_date(positions, as_of_date)
    frame["original_weight"] = frame["weight"].astype(float)
    frame["weight"] = frame["original_weight"]
    funding_avg = funding_average_30d(funding, as_of_date, config)
    frame = frame.merge(funding_avg, on="symbol", how="left")
    frame["funding_rate_30d_avg"] = pd.to_numeric(
        frame["funding_rate_30d_avg"], errors="coerce"
    ).fillna(0.0)
    frame["overlay_rules_applied"] = ""
    frame["excluded_reason"] = ""

    events: list[dict[str, Any]] = []
    if variant_name in {config.primary_variant, config.secondary_variant}:
        frame, events = _apply_funding_filter(frame, config, events)
    if variant_name == config.primary_variant:
        frame, events = _apply_long_cap(frame, config, events)
        frame, events = _apply_symbol_cap(frame, config, events)
    elif variant_name != config.secondary_variant:
        raise ValueError(f"unsupported paper planning variant: {variant_name}")

    frame["direction"] = np.where(frame["weight"].gt(0), "long", np.where(frame["weight"].lt(0), "short", "flat"))
    frame["variant"] = variant_name
    return OverlayResult(positions=frame.sort_values("symbol").reset_index(drop=True), events=events)


def funding_average_30d(
    funding: pd.DataFrame,
    as_of_date: str | pd.Timestamp,
    config: PaperTradingConfig,
) -> pd.DataFrame:
    required = {"timestamp", "symbol", "funding_rate", "interval_hours"}
    missing = required - set(funding.columns)
    if missing:
        raise ValueError(f"funding missing columns: {sorted(missing)}")
    as_of = pd.Timestamp(as_of_date).normalize()
    start = as_of - pd.Timedelta(days=int(config.funding_window_days))
    frame = funding.loc[:, ["timestamp", "symbol", "funding_rate", "interval_hours"]].copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    frame["date"] = frame["timestamp"].dt.tz_convert("UTC").dt.tz_localize(None).dt.normalize()
    frame = frame[(frame["date"] > start) & (frame["date"] <= as_of)].copy()
    frame["funding_rate"] = pd.to_numeric(frame["funding_rate"], errors="coerce")
    frame["interval_hours"] = pd.to_numeric(frame["interval_hours"], errors="coerce")
    frame = frame.dropna(subset=["funding_rate", "interval_hours"])
    frame = frame[frame["interval_hours"].gt(0)].copy()
    frame["funding_rate_8h"] = frame["funding_rate"] * 8.0 / frame["interval_hours"]
    if frame.empty:
        return pd.DataFrame(columns=["symbol", "funding_rate_30d_avg"])
    return (
        frame.groupby("symbol", as_index=False)["funding_rate_8h"]
        .mean()
        .rename(columns={"funding_rate_8h": "funding_rate_30d_avg"})
    )


def portfolio_summary(frame: pd.DataFrame) -> dict[str, float | int]:
    weights = frame["weight"].astype(float)
    long_exposure = float(weights[weights > 0].sum())
    short_exposure = float(weights[weights < 0].abs().sum())
    gross = float(weights.abs().sum())
    return {
        "gross_exposure_pct": gross,
        "long_exposure_pct": long_exposure,
        "short_exposure_pct": short_exposure,
        "net_exposure_pct": float(weights.sum()),
        "n_longs": int((weights > 0).sum()),
        "n_shorts": int((weights < 0).sum()),
        "max_single_symbol_pct": float(weights.abs().max()) if len(weights) else 0.0,
    }


def _positions_for_date(positions: pd.DataFrame, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    required = {"date", "symbol", "weight"}
    missing = required - set(positions.columns)
    if missing:
        raise ValueError(f"positions missing columns: {sorted(missing)}")
    frame = positions.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    as_of = pd.Timestamp(as_of_date).normalize()
    out = frame[frame["date"].eq(as_of)].copy()
    if out.empty:
        raise ValueError(f"no positions for date {as_of.date()}")
    out["symbol"] = out["symbol"].astype(str)
    return out


def _apply_funding_filter(
    frame: pd.DataFrame,
    config: PaperTradingConfig,
    events: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    out = frame.copy()
    mask = out["weight"].astype(float).gt(0) & out["funding_rate_30d_avg"].gt(config.funding_threshold_8h)
    for row in out[mask].itertuples(index=False):
        events.append({
            "rule": "funding_filter_0.03pct_8h",
            "symbol": row.symbol,
            "original_weight": float(row.weight),
            "new_weight": 0.0,
            "funding_rate_30d_avg": float(row.funding_rate_30d_avg),
        })
    out.loc[mask, "weight"] = 0.0
    out.loc[mask, "excluded_reason"] = "funding_filter_0.03pct_8h"
    out.loc[mask, "overlay_rules_applied"] = _append_rule(out.loc[mask, "overlay_rules_applied"], "funding_filter_0.03pct_8h")
    return out, events


def _apply_long_cap(
    frame: pd.DataFrame,
    config: PaperTradingConfig,
    events: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    out = frame.copy()
    weights = out["weight"].astype(float)
    total_gross = float(weights.abs().sum())
    long_gross = float(weights[weights > 0].sum())
    target_long_gross = total_gross * config.long_cap_gross_share
    if long_gross > target_long_gross and long_gross > 0:
        scale = target_long_gross / long_gross
        mask = weights.gt(0)
        original = out.loc[mask, "weight"].astype(float)
        out.loc[mask, "weight"] = original * scale
        out.loc[mask, "overlay_rules_applied"] = _append_rule(out.loc[mask, "overlay_rules_applied"], "long_cap_50pct")
        events.append({
            "rule": "long_cap_50pct",
            "long_gross_before": long_gross,
            "long_gross_after": float(out.loc[out["weight"].gt(0), "weight"].sum()),
            "scale": float(scale),
        })
    return out, events


def _apply_symbol_cap(
    frame: pd.DataFrame,
    config: PaperTradingConfig,
    events: list[dict[str, Any]],
) -> tuple[pd.DataFrame, list[dict[str, Any]]]:
    out = frame.copy()
    cap = float(config.symbol_cap_abs_weight)
    weights = out["weight"].astype(float)
    mask = weights.abs().gt(cap)
    for row in out[mask].itertuples(index=False):
        new_weight = float(np.sign(row.weight) * cap)
        events.append({
            "rule": "symbol_cap_5pct",
            "symbol": row.symbol,
            "original_weight": float(row.weight),
            "new_weight": new_weight,
        })
    out.loc[mask, "weight"] = np.sign(out.loc[mask, "weight"].astype(float)) * cap
    out.loc[mask, "overlay_rules_applied"] = _append_rule(out.loc[mask, "overlay_rules_applied"], "symbol_cap_5pct")
    return out, events


def _append_rule(series: pd.Series, rule: str) -> pd.Series:
    return series.astype(str).map(lambda value: rule if not value else f"{value};{rule}")
