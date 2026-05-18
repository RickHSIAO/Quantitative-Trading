from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from src.data.prev3y_input_validator import validate_prev3y_inputs
from src.data_quality.missing import apply_data_quality_policy


def load_tradable_membership(config_path: Path, prices_path: Path, universe_path: Path) -> pd.DataFrame:
    validated = validate_prev3y_inputs(config_path, prices_path, universe_path)
    dq = apply_data_quality_policy(validated.prices, validated.membership, validated.config)
    tradable = dq.tradable_membership.loc[:, ["date", "symbol", "is_member"]].copy()
    tradable["date"] = pd.to_datetime(tradable["date"]).dt.normalize()
    tradable["symbol"] = tradable["symbol"].astype(str)
    tradable["is_member"] = tradable["is_member"].astype(bool)
    return tradable[tradable["is_member"]].drop_duplicates(["date", "symbol"]).reset_index(drop=True)


def symbol_open_to_open_returns(prices: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "open"}
    missing = required - set(prices.columns)
    if missing:
        raise ValueError(f"prices missing columns: {sorted(missing)}")
    px = prices.loc[:, ["date", "symbol", "open"]].copy()
    px["date"] = pd.to_datetime(px["date"]).dt.normalize()
    px["symbol"] = px["symbol"].astype(str)
    px["open"] = pd.to_numeric(px["open"], errors="coerce")
    px = px.sort_values(["symbol", "date"])
    px["symbol_return"] = (
        px.groupby("symbol", sort=False)["open"]
        .pct_change(fill_method=None)
        .replace([np.inf, -np.inf], np.nan)
    )
    return px.loc[:, ["date", "symbol", "symbol_return"]]


def build_gross_contributions(
    positions: pd.DataFrame,
    prices: pd.DataFrame,
    tradable_membership: pd.DataFrame,
) -> pd.DataFrame:
    required = {"date", "symbol", "weight", "signal_rank", "signal_value"}
    missing = required - set(positions.columns)
    if missing:
        raise ValueError(f"positions missing columns: {sorted(missing)}")
    pos = positions.loc[:, ["date", "symbol", "weight", "signal_rank", "signal_value"]].copy()
    pos["position_date"] = pd.to_datetime(pos["date"]).dt.normalize()
    pos["return_date"] = pos["position_date"] + pd.Timedelta(days=1)
    pos["symbol"] = pos["symbol"].astype(str)
    pos["weight_prior"] = pd.to_numeric(pos["weight"], errors="coerce").astype(float)
    pos["signal_rank"] = pd.to_numeric(pos["signal_rank"], errors="coerce").fillna(0).astype(int)
    pos["signal_value"] = pd.to_numeric(pos["signal_value"], errors="coerce")

    tradable = tradable_membership.loc[:, ["date", "symbol"]].copy()
    tradable["date"] = pd.to_datetime(tradable["date"]).dt.normalize()
    tradable["symbol"] = tradable["symbol"].astype(str)
    held = pos.merge(
        tradable,
        left_on=["return_date", "symbol"],
        right_on=["date", "symbol"],
        how="inner",
        suffixes=("", "_tradable"),
    )

    returns = symbol_open_to_open_returns(prices)
    merged = held.merge(
        returns,
        left_on=["return_date", "symbol"],
        right_on=["date", "symbol"],
        how="left",
        suffixes=("", "_return"),
    )
    if merged["symbol_return"].isna().any():
        missing_rows = merged.loc[merged["symbol_return"].isna(), ["return_date", "symbol"]]
        sample = missing_rows.head(10).to_dict("records")
        raise RuntimeError(
            "NEED_CLARIFICATION: tradable filtered positions still have missing returns; "
            f"sample={sample}"
        )
    merged["gross_contribution"] = merged["weight_prior"].astype(float) * merged["symbol_return"].astype(float)
    return merged.loc[
        :,
        [
            "return_date",
            "position_date",
            "symbol",
            "weight_prior",
            "symbol_return",
            "gross_contribution",
            "signal_rank",
            "signal_value",
        ],
    ].rename(columns={"return_date": "date"})

