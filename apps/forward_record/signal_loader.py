from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from apps.forward_record.config import ForwardRecordConfig


@dataclass(frozen=True)
class LoadedPositions:
    positions: pd.DataFrame
    signal_date: pd.Timestamp


def load_latest_positions(config: ForwardRecordConfig, record_date: str | pd.Timestamp) -> LoadedPositions:
    frame = pd.read_parquet(config.positions_path)
    required = {"date", "symbol", "weight"}
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"positions missing columns: {sorted(missing)}")
    frame = frame.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    requested = pd.Timestamp(record_date).normalize()
    eligible_dates = sorted(frame.loc[frame["date"].le(requested), "date"].drop_duplicates())
    if not eligible_dates:
        raise ValueError(f"no positions available on or before {requested.date()}")
    signal_date = pd.Timestamp(eligible_dates[-1]).normalize()
    selected = frame[frame["date"].eq(signal_date)].copy()
    selected["symbol"] = selected["symbol"].astype(str)
    return LoadedPositions(positions=selected.reset_index(drop=True), signal_date=signal_date)

