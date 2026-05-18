from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import pandas as pd

from apps.paper_trading.config import PaperTradingConfig
from apps.paper_trading.overlay import apply_variant_overlay, portfolio_summary


@dataclass(frozen=True)
class SizingResult:
    payload: dict[str, Any]
    positions: pd.DataFrame
    events: list[dict[str, Any]]


def build_target_positions(
    positions: pd.DataFrame,
    funding: pd.DataFrame,
    config: PaperTradingConfig,
    as_of_date: str | pd.Timestamp | None = None,
    variant: str | None = None,
) -> SizingResult:
    target_date = _target_date(positions, as_of_date)
    overlay = apply_variant_overlay(positions, funding, target_date, config, variant)
    frame = overlay.positions.copy()
    frame["usd_notional"] = frame["weight"].astype(float) * float(config.initial_nav_usd)
    frame["rule_applied"] = frame["overlay_rules_applied"].replace("", pd.NA)
    summary = portfolio_summary(frame)
    cap_errors = frame.loc[frame["weight"].abs().gt(config.symbol_cap_abs_weight + 1e-12), ["symbol", "weight"]]
    if not cap_errors.empty and (variant or config.primary_variant) == config.primary_variant:
        raise ValueError(f"symbol cap violation: {cap_errors.to_dict(orient='records')}")
    payload = {
        "date": pd.Timestamp(target_date).strftime("%Y-%m-%d"),
        "nav_usd": float(config.initial_nav_usd),
        "currency": config.currency,
        "venue": config.venue,
        "account_type": config.account_type,
        "variant": variant or config.primary_variant,
        "overlay_rules_applied": [
            "funding_filter_0.03pct_8h",
            "long_cap_50pct",
            "symbol_cap_5pct",
        ] if (variant or config.primary_variant) == config.primary_variant else ["funding_filter_0.03pct_8h"],
        "excluded_symbols": sorted(frame.loc[frame["excluded_reason"].ne(""), "symbol"].astype(str).tolist()),
        "positions": [
            {
                "symbol": str(row.symbol),
                "weight": float(row.weight),
                "direction": str(row.direction),
                "usd_notional": float(row.usd_notional),
                "funding_rate_30d_avg": float(row.funding_rate_30d_avg),
                "rule_applied": None if pd.isna(row.rule_applied) else str(row.rule_applied),
            }
            for row in frame.itertuples(index=False)
            if abs(float(row.weight)) > 0.0
        ],
        "portfolio_summary": summary,
        "mandatory_caveats": config.mandatory_caveats,
        "analysis_basis": "offline planning only, not a trading decision",
        "disclaimer": "Local simulation output only. External execution is unsupported.",
    }
    return SizingResult(payload=payload, positions=frame, events=overlay.events)


def _target_date(positions: pd.DataFrame, as_of_date: str | pd.Timestamp | None) -> pd.Timestamp:
    if as_of_date is not None:
        return pd.Timestamp(as_of_date).normalize()
    dates = pd.to_datetime(positions["date"]).dt.normalize()
    active = positions.assign(_date=dates).groupby("_date")["weight"].apply(lambda x: x.astype(float).abs().sum())
    active = active[active > 0]
    if active.empty:
        raise ValueError("positions contain no active dates")
    return pd.Timestamp(active.index.max()).normalize()
