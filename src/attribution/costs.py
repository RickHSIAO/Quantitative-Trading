from __future__ import annotations

import pandas as pd


def load_primary_costs(positions_cost: pd.DataFrame, scenario: str) -> pd.DataFrame:
    required = {
        "date",
        "scenario",
        "symbol",
        "weight",
        "fee_cost",
        "funding_cost",
        "slippage_cost",
        "funding_gap",
        "outlier_count_today",
        "funding_settlement_count",
        "entry_turnover",
        "exit_turnover",
        "trade_turnover",
        "outlier_funding_cost",
    }
    missing = required - set(positions_cost.columns)
    if missing:
        raise ValueError(f"positions_cost missing columns: {sorted(missing)}")
    costs = positions_cost[positions_cost["scenario"].eq(scenario)].copy()
    if costs.empty:
        raise ValueError(f"positions_cost has no rows for scenario={scenario}")
    costs["date"] = pd.to_datetime(costs["date"]).dt.normalize()
    costs["symbol"] = costs["symbol"].astype(str)
    for col in [
        "weight",
        "fee_cost",
        "funding_cost",
        "slippage_cost",
        "outlier_count_today",
        "funding_settlement_count",
        "entry_turnover",
        "exit_turnover",
        "trade_turnover",
        "outlier_funding_cost",
    ]:
        costs[col] = pd.to_numeric(costs[col], errors="coerce").fillna(0.0)
    costs["funding_gap"] = costs["funding_gap"].astype(bool)
    if int(costs.duplicated(["date", "symbol"]).sum()):
        raise ValueError(f"positions_cost scenario={scenario} contains duplicate date+symbol rows")
    return costs.loc[
        :,
        [
            "date",
            "symbol",
            "weight",
            "fee_cost",
            "funding_cost",
            "slippage_cost",
            "funding_gap",
            "outlier_count_today",
            "funding_settlement_count",
            "entry_turnover",
            "exit_turnover",
            "trade_turnover",
            "outlier_funding_cost",
        ],
    ].rename(columns={"weight": "cost_weight"})


def funding_interval_map(funding: pd.DataFrame) -> pd.DataFrame:
    required = {"symbol", "interval_hours"}
    missing = required - set(funding.columns)
    if missing:
        raise ValueError(f"funding missing columns: {sorted(missing)}")
    frame = funding.loc[:, ["symbol", "interval_hours"]].copy()
    frame["symbol"] = frame["symbol"].astype(str)
    frame["interval_hours"] = pd.to_numeric(frame["interval_hours"], errors="coerce")
    unique_counts = frame.dropna().groupby("symbol")["interval_hours"].nunique()
    multi = unique_counts[unique_counts.gt(1)]
    if not multi.empty:
        raise RuntimeError(
            "NEED_CLARIFICATION: symbols with multiple funding interval labels: "
            f"{multi.head(20).to_dict()}"
        )
    interval = (
        frame.dropna()
        .drop_duplicates(["symbol", "interval_hours"])
        .sort_values(["symbol", "interval_hours"])
        .copy()
    )
    interval["funding_interval_group"] = interval["interval_hours"].astype(int).astype(str) + "h"
    return interval.loc[:, ["symbol", "funding_interval_group"]]

