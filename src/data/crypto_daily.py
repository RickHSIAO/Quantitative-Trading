"""Crypto daily OHLCV snapshots for the Prev3Y baseline.

This module keeps data extraction separate from universe construction and
strategy logic. The parquet files produced here are immutable task inputs for
the TASK-001 baseline run.
"""
from __future__ import annotations

import hashlib
import sqlite3
from dataclasses import dataclass
from pathlib import Path

import pandas as pd


PRICE_SCHEMA = [
    {"name": "date", "type": "datetime64[ns]", "unit": "UTC calendar date"},
    {"name": "symbol", "type": "string", "unit": "crypto symbol from local DB"},
    {"name": "open", "type": "float64", "unit": "USDT"},
    {"name": "high", "type": "float64", "unit": "USDT"},
    {"name": "low", "type": "float64", "unit": "USDT"},
    {"name": "close", "type": "float64", "unit": "USDT"},
    {"name": "volume", "type": "float64", "unit": "base asset contracts/coins"},
    {"name": "quote_volume", "type": "float64", "unit": "USDT proxy, close * volume"},
]


@dataclass(frozen=True)
class PriceSnapshotInfo:
    path: Path
    row_count: int
    symbol_count: int
    min_date: str
    max_date: str
    created: bool


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as fh:
        for chunk in iter(lambda: fh.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def sha256_files(paths: list[Path]) -> str:
    digest = hashlib.sha256()
    for path in sorted(paths, key=lambda p: str(p)):
        digest.update(str(path).encode("utf-8"))
        digest.update(b"\0")
        digest.update(sha256_file(path).encode("ascii"))
        digest.update(b"\0")
    return digest.hexdigest()


def load_price_snapshot(path: Path) -> pd.DataFrame:
    df = pd.read_parquet(path)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["symbol"] = df["symbol"].astype(str)
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def create_price_snapshot_from_sqlite(
    db_path: Path,
    output_path: Path,
    warmup_start_date: str,
    end_date: str,
) -> PriceSnapshotInfo:
    if output_path.exists():
        df = load_price_snapshot(output_path)
        return _price_info(output_path, df, created=False)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    query = """
        SELECT date, symbol, open, high, low, close, volume
        FROM prices
        WHERE asset_type = 'Crypto'
          AND date >= ?
          AND date <= ?
        ORDER BY date, symbol
    """
    with sqlite3.connect(db_path) as conn:
        df = pd.read_sql_query(query, conn, params=(warmup_start_date, end_date), parse_dates=["date"])

    if df.empty:
        raise RuntimeError(f"No crypto prices found in {db_path} for {warmup_start_date}..{end_date}")

    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    for col in ["open", "high", "low", "close", "volume"]:
        df[col] = pd.to_numeric(df[col], errors="coerce").astype("float64")
    df["quote_volume"] = (df["close"] * df["volume"]).astype("float64")
    df = df[["date", "symbol", "open", "high", "low", "close", "volume", "quote_volume"]]
    df = df.sort_values(["date", "symbol"]).reset_index(drop=True)
    df.to_parquet(output_path, index=False)
    return _price_info(output_path, df, created=True)


def price_availability(prices: pd.DataFrame) -> pd.DataFrame:
    return (
        prices.dropna(subset=["close"])
        .groupby("symbol", as_index=False)
        .agg(first_date=("date", "min"), last_date=("date", "max"), bars=("date", "nunique"))
    )


def price_anomalies(prices: pd.DataFrame) -> list[dict[str, object]]:
    anomalies: list[dict[str, object]] = []
    dupes = prices.duplicated(["date", "symbol"]).sum()
    if dupes:
        anomalies.append({"symbol": "*", "start_date": "", "end_date": "", "issue": f"duplicate date/symbol rows={dupes}"})

    for col in ["open", "high", "low", "close"]:
        bad = prices[~prices[col].gt(0) & prices[col].notna()]
        if not bad.empty:
            grouped = bad.groupby("symbol")["date"].agg(["min", "max", "count"]).reset_index()
            for row in grouped.itertuples(index=False):
                anomalies.append({
                    "symbol": row.symbol,
                    "start_date": str(pd.Timestamp(row.min).date()),
                    "end_date": str(pd.Timestamp(row.max).date()),
                    "issue": f"nonpositive_{col}_rows={int(row.count)}",
                })

    missing = prices[prices[["open", "high", "low", "close", "volume"]].isna().any(axis=1)]
    if not missing.empty:
        grouped = missing.groupby("symbol")["date"].agg(["min", "max", "count"]).reset_index()
        for row in grouped.itertuples(index=False):
            anomalies.append({
                "symbol": row.symbol,
                "start_date": str(pd.Timestamp(row.min).date()),
                "end_date": str(pd.Timestamp(row.max).date()),
                "issue": f"missing_ohlcv_rows={int(row.count)}",
            })

    return anomalies


def _price_info(path: Path, df: pd.DataFrame, created: bool) -> PriceSnapshotInfo:
    return PriceSnapshotInfo(
        path=path,
        row_count=int(len(df)),
        symbol_count=int(df["symbol"].nunique()),
        min_date=str(pd.Timestamp(df["date"].min()).date()),
        max_date=str(pd.Timestamp(df["date"].max()).date()),
        created=created,
    )
