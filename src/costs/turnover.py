from __future__ import annotations

import numpy as np
import pandas as pd


def prepare_positions(positions: pd.DataFrame) -> pd.DataFrame:
    required = {"date", "symbol", "weight"}
    missing = required - set(positions.columns)
    if missing:
        raise ValueError(f"positions missing columns: {sorted(missing)}")
    result = positions.loc[:, ["date", "symbol", "weight"]].copy()
    result["date"] = pd.to_datetime(result["date"]).dt.tz_localize(None)
    result["symbol"] = result["symbol"].astype(str)
    result["weight"] = result["weight"].astype(float)
    if result.duplicated(["date", "symbol"]).any():
        raise ValueError("positions contain duplicate date+symbol rows")
    return result


def build_weight_panel(baseline: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    dates = pd.to_datetime(baseline["date"]).dt.tz_localize(None).drop_duplicates().sort_values()
    prepared = prepare_positions(positions)
    current = prepared.pivot(index="date", columns="symbol", values="weight")
    panel = current.reindex(dates).fillna(0.0).sort_index()
    return panel


def build_turnover_events(baseline: pd.DataFrame, positions: pd.DataFrame) -> pd.DataFrame:
    panel = build_weight_panel(baseline, positions)
    previous = panel.shift(1).fillna(0.0)
    current = panel
    delta = current - previous
    mask = (current != 0.0) | (previous != 0.0) | (delta != 0.0)

    stacked = pd.DataFrame(
        {
            "weight": current.where(mask).stack(),
            "previous_weight": previous.where(mask).stack(),
            "delta_weight": delta.where(mask).stack(),
        }
    ).dropna(how="all").reset_index()
    stacked = stacked.rename(columns={"level_0": "date", "level_1": "symbol"})
    stacked["entry_turnover"], stacked["exit_turnover"] = _split_entry_exit(
        stacked["previous_weight"].to_numpy(dtype=float),
        stacked["weight"].to_numpy(dtype=float),
    )
    stacked["trade_turnover"] = stacked["entry_turnover"] + stacked["exit_turnover"]
    return stacked


def _split_entry_exit(previous: np.ndarray, current: np.ndarray) -> tuple[np.ndarray, np.ndarray]:
    entry = np.zeros_like(current, dtype=float)
    exit_ = np.zeros_like(current, dtype=float)

    for idx, (prev_weight, curr_weight) in enumerate(zip(previous, current)):
        if prev_weight == 0.0 and curr_weight == 0.0:
            continue
        if prev_weight == 0.0:
            entry[idx] = abs(curr_weight)
            continue
        if curr_weight == 0.0:
            exit_[idx] = abs(prev_weight)
            continue
        if np.sign(prev_weight) != np.sign(curr_weight):
            exit_[idx] = abs(prev_weight)
            entry[idx] = abs(curr_weight)
            continue
        prev_abs = abs(prev_weight)
        curr_abs = abs(curr_weight)
        if curr_abs > prev_abs:
            entry[idx] = curr_abs - prev_abs
        else:
            exit_[idx] = prev_abs - curr_abs
    return entry, exit_
