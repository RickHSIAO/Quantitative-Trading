from __future__ import annotations

import json
from pathlib import Path

import pandas as pd

from apps.paper_trading.config import PaperTradingConfig


SIMULATED_FILL_COLUMNS = [
    "date",
    "symbol",
    "direction",
    "target_weight",
    "prev_weight",
    "weight_delta",
    "usd_notional",
    "simulated_fill_price",
    "simulated_fee_usd",
    "simulated_slippage_usd",
    "simulated_funding_usd",
    "overlay_rules_applied",
    "excluded_reason",
]


def build_intended_fills(
    target_positions: pd.DataFrame,
    all_positions: pd.DataFrame,
    prices: pd.DataFrame,
    config: PaperTradingConfig,
) -> pd.DataFrame:
    target = target_positions.copy()
    target["date"] = pd.to_datetime(target["date"]).dt.normalize()
    target_date = pd.Timestamp(target["date"].max()).normalize()
    previous_date = _previous_position_date(all_positions, target_date)
    previous = all_positions.copy()
    previous["date"] = pd.to_datetime(previous["date"]).dt.normalize()
    previous = previous[previous["date"].eq(previous_date)].loc[:, ["symbol", "weight"]]
    previous = previous.rename(columns={"weight": "prev_weight"})
    fills = target.merge(previous, on="symbol", how="left")
    fills["prev_weight"] = pd.to_numeric(fills["prev_weight"], errors="coerce").fillna(0.0)
    fills["target_weight"] = fills["weight"].astype(float)
    fills["weight_delta"] = fills["target_weight"] - fills["prev_weight"]
    fills = fills[fills["weight_delta"].abs().gt(1e-15)].copy()
    fills["usd_notional"] = fills["weight_delta"] * float(config.initial_nav_usd)
    fills["direction"] = fills["weight_delta"].map(lambda value: "long" if value > 0 else "short")
    fills["date"] = _next_price_date(prices, target_date).strftime("%Y-%m-%d")
    fill_prices = _fill_prices(prices, pd.Timestamp(fills["date"].iloc[0]) if not fills.empty else target_date)
    fills = fills.merge(fill_prices, on="symbol", how="left")
    fills["simulated_fill_price"] = pd.to_numeric(fills["open"], errors="coerce")
    fills["simulated_fee_usd"] = fills["usd_notional"].abs() * float(config.taker_fee_bps) / 10_000.0
    fills["simulated_slippage_usd"] = fills["usd_notional"].abs() * float(config.slippage_bps) / 10_000.0
    fills["simulated_funding_usd"] = 0.0
    fills["overlay_rules_applied"] = fills["overlay_rules_applied"].fillna("")
    fills["excluded_reason"] = fills["excluded_reason"].fillna("")
    return fills.loc[:, SIMULATED_FILL_COLUMNS].sort_values(["date", "symbol"]).reset_index(drop=True)


def write_target_positions(path: Path, payload: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True, ensure_ascii=False) + "\n", encoding="utf-8")


def write_simulated_fills(path: Path, fills: pd.DataFrame) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fills.loc[:, SIMULATED_FILL_COLUMNS].to_csv(path, index=False)


def _previous_position_date(all_positions: pd.DataFrame, target_date: pd.Timestamp) -> pd.Timestamp:
    dates = pd.to_datetime(all_positions["date"]).dt.normalize()
    prior = sorted(date for date in dates.drop_duplicates() if date < target_date)
    return pd.Timestamp(prior[-1]).normalize() if prior else target_date


def _next_price_date(prices: pd.DataFrame, target_date: pd.Timestamp) -> pd.Timestamp:
    dates = pd.to_datetime(prices["date"]).dt.normalize()
    future = sorted(date for date in dates.drop_duplicates() if date > target_date)
    return pd.Timestamp(future[0]).normalize() if future else target_date


def _fill_prices(prices: pd.DataFrame, fill_date: pd.Timestamp) -> pd.DataFrame:
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    out = frame[frame["date"].eq(fill_date)].loc[:, ["symbol", "open"]].copy()
    out["symbol"] = out["symbol"].astype(str)
    return out
