"""Point-in-time crypto universe membership for Prev3Y research."""
from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd

from src.data.crypto_daily import price_availability


UNIVERSE_SCHEMA = [
    {"name": "date", "type": "datetime64[ns]", "unit": "UTC calendar date"},
    {"name": "symbol", "type": "string", "unit": "Bybit perpetual symbol"},
    {"name": "is_member", "type": "bool", "unit": "true rows only; absent rows are false"},
]


@dataclass(frozen=True)
class UniverseSnapshotInfo:
    path: Path
    row_count: int
    symbol_count: int
    min_date: str
    max_date: str
    avg_size_start_end: float
    created: bool


def to_bybit_symbol(symbol: str) -> str:
    raw = str(symbol).strip().upper()
    if not raw:
        return raw
    if raw.startswith("BYBIT:") and raw.endswith(".P"):
        return raw
    if raw.endswith("USDT"):
        return f"BYBIT:{raw}.P"
    return f"BYBIT:{raw}USDT.P"


def load_universe_membership(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["symbol"] = df["symbol"].astype(str)
    df["is_member"] = df["is_member"].astype(bool)
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def create_universe_membership_from_sqlite(
    db_path: Path,
    prices: pd.DataFrame,
    output_path: Path,
    warmup_start_date: str,
    start_date: str,
    end_date: str,
    max_rank: int = 200,
) -> UniverseSnapshotInfo:
    if output_path.exists():
        df = load_universe_membership(output_path)
        return _universe_info(output_path, df, start_date, end_date, created=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    rankings = _load_rankings(db_path, max_rank)
    if rankings.empty:
        raise RuntimeError("Missing crypto_market_cap_rankings rows; cannot build point-in-time universe")

    instruments = _load_instruments(db_path)
    availability = price_availability(prices).set_index("symbol")
    available_symbols = set(availability.index)
    dates = pd.date_range(warmup_start_date, end_date, freq="D")

    rows: list[dict[str, object]] = []
    snapshots = rankings["snapshot_date"].drop_duplicates().sort_values().to_list()
    snapshot_idx = 0
    active_snapshot = pd.DataFrame()

    for date in dates:
        while snapshot_idx < len(snapshots) and snapshots[snapshot_idx] <= date:
            snap_date = snapshots[snapshot_idx]
            active_snapshot = rankings[rankings["snapshot_date"].eq(snap_date)].copy()
            snapshot_idx += 1
        if active_snapshot.empty:
            continue

        for rec in active_snapshot.itertuples(index=False):
            symbol = rec.bybit_symbol
            if symbol not in available_symbols:
                continue
            price_meta = availability.loc[symbol]
            if date < price_meta["first_date"] or date > price_meta["last_date"]:
                continue
            if symbol in instruments:
                launch = instruments[symbol].get("launch_time")
                delivery = instruments[symbol].get("delivery_time")
                if pd.notna(launch) and launch and date < pd.Timestamp(launch):
                    continue
                if pd.notna(delivery) and delivery and date >= pd.Timestamp(delivery):
                    continue
            rows.append({"date": date, "symbol": symbol, "is_member": True})

    membership = pd.DataFrame(rows, columns=["date", "symbol", "is_member"])
    if membership.empty:
        raise RuntimeError("Constructed point-in-time universe is empty")
    membership = membership.sort_values(["date", "symbol"]).reset_index(drop=True)
    membership.to_parquet(output_path, index=False)
    return _universe_info(output_path, membership, start_date, end_date, created=True)


def universe_anomalies(membership: pd.DataFrame, prices: pd.DataFrame) -> list[dict[str, object]]:
    anomalies: list[dict[str, object]] = []
    availability = price_availability(prices).set_index("symbol")
    unknown = sorted(set(membership["symbol"]) - set(availability.index))
    for symbol in unknown:
        dates = membership.loc[membership["symbol"].eq(symbol), "date"]
        anomalies.append({
            "symbol": symbol,
            "start_date": str(pd.Timestamp(dates.min()).date()),
            "end_date": str(pd.Timestamp(dates.max()).date()),
            "issue": "universe_symbol_missing_from_prices",
        })

    known = membership[membership["symbol"].isin(availability.index)].copy()
    if not known.empty:
        known = known.join(availability, on="symbol")
        out_of_range = known[(known["date"] < known["first_date"]) | (known["date"] > known["last_date"])]
        if not out_of_range.empty:
            grouped = out_of_range.groupby("symbol")["date"].agg(["min", "max", "count"]).reset_index()
            for row in grouped.itertuples(index=False):
                anomalies.append({
                    "symbol": row.symbol,
                    "start_date": str(pd.Timestamp(row.min).date()),
                    "end_date": str(pd.Timestamp(row.max).date()),
                    "issue": f"membership_outside_price_range_rows={int(row.count)}",
                })
    return anomalies


def daily_universe_sizes(membership: pd.DataFrame, start_date: str, end_date: str) -> pd.Series:
    dates = pd.date_range(start_date, end_date, freq="D")
    counts = membership[membership["is_member"]].groupby("date")["symbol"].nunique()
    return counts.reindex(dates, fill_value=0).rename("universe_size")


def _load_rankings(db_path: Path, max_rank: int) -> pd.DataFrame:
    query = """
        SELECT snapshot_date, rank, symbol
        FROM crypto_market_cap_rankings
        WHERE rank <= ?
          AND COALESCE(is_stablecoin, 0) = 0
          AND COALESCE(is_wrapped, 0) = 0
          AND COALESCE(is_leveraged, 0) = 0
        ORDER BY snapshot_date, rank
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(int(max_rank),), parse_dates=["snapshot_date"])
    if df.empty:
        return df
    df["snapshot_date"] = pd.to_datetime(df["snapshot_date"]).dt.normalize()
    df["rank"] = pd.to_numeric(df["rank"], errors="coerce")
    df["bybit_symbol"] = df["symbol"].map(to_bybit_symbol)
    return df.dropna(subset=["snapshot_date", "rank", "bybit_symbol"]).sort_values(["snapshot_date", "rank"])


def _load_instruments(db_path: Path) -> dict[str, dict[str, object]]:
    with sqlite3.connect(db_path) as conn:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crypto_bybit_linear_instruments'"
        ).fetchone()
        if exists is None:
            return {}
        df = pd.read_sql_query(
            "SELECT bybit_symbol, launch_time, delivery_time FROM crypto_bybit_linear_instruments",
            conn,
        )
    out: dict[str, dict[str, object]] = {}
    for row in df.itertuples(index=False):
        symbol = f"BYBIT:{str(row.bybit_symbol).upper()}.P"
        out[symbol] = {
            "launch_time": pd.to_datetime(row.launch_time).normalize() if row.launch_time else None,
            "delivery_time": pd.to_datetime(row.delivery_time).normalize() if row.delivery_time else None,
        }
    return out


def _universe_info(
    path: Path,
    df: pd.DataFrame,
    start_date: str,
    end_date: str,
    created: bool,
) -> UniverseSnapshotInfo:
    sizes = daily_universe_sizes(df, start_date, end_date)
    return UniverseSnapshotInfo(
        path=path,
        row_count=int(len(df)),
        symbol_count=int(df["symbol"].nunique()),
        min_date=str(pd.Timestamp(df["date"].min()).date()),
        max_date=str(pd.Timestamp(df["date"].max()).date()),
        avg_size_start_end=float(sizes.mean()),
        created=created,
    )
