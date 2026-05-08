"""Fetch Bybit OHLCV for CMC point-in-time universe candidates.

This is data coverage infrastructure for EXP-005. It:
1. stores current Bybit linear USDT perpetual instruments in SQLite;
2. intersects CoinMarketCap historical ranking symbols with Bybit instruments;
3. downloads missing/short daily OHLCV into the existing prices table.

It does not modify strategy signals, parameters, costs, sizing, or execution
rules.
"""
from __future__ import annotations

import argparse
import sqlite3
import sys
import time
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config
from src.database import get_last_date, init_db, upsert_prices

try:
    from pybit.unified_trading import HTTP as BybitHTTP
except ImportError as exc:  # pragma: no cover
    raise SystemExit("pybit is required. Install with: pip install pybit") from exc


def _init_tables() -> None:
    init_db()
    conn = sqlite3.connect(config.DB_PATH)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crypto_bybit_linear_instruments (
                bybit_symbol TEXT PRIMARY KEY,
                base_coin TEXT,
                quote_coin TEXT,
                status TEXT,
                contract_type TEXT,
                launch_time TEXT,
                delivery_time TEXT,
                updated_at TEXT
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crypto_bybit_ohlcv_fetch_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                run_at TEXT NOT NULL,
                bybit_symbol TEXT NOT NULL,
                yf_symbol TEXT NOT NULL,
                status TEXT NOT NULL,
                rows INTEGER DEFAULT 0,
                start_date TEXT,
                end_date TEXT,
                message TEXT
            )
        """)
    conn.close()


def _ms_to_date(value: Any) -> str:
    try:
        ms = int(value)
    except (TypeError, ValueError):
        return ""
    if ms <= 0:
        return ""
    return datetime.fromtimestamp(ms / 1000, tz=timezone.utc).strftime("%Y-%m-%d")


def _fetch_instruments() -> dict[str, dict[str, Any]]:
    session = BybitHTTP()
    cursor = ""
    instruments: dict[str, dict[str, Any]] = {}
    while True:
        kwargs = {"category": "linear", "limit": 1000}
        if cursor:
            kwargs["cursor"] = cursor
        res = session.get_instruments_info(**kwargs)
        result = res.get("result", {})
        for item in result.get("list", []):
            symbol = str(item.get("symbol", "")).upper()
            quote = str(item.get("quoteCoin", "")).upper()
            if not symbol.endswith("USDT") or quote != "USDT":
                continue
            instruments[symbol] = item
        cursor = result.get("nextPageCursor") or ""
        if not cursor:
            break
    return instruments


def _save_instruments(instruments: dict[str, dict[str, Any]]) -> None:
    now = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    conn = sqlite3.connect(config.DB_PATH)
    with conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO crypto_bybit_linear_instruments
            (bybit_symbol, base_coin, quote_coin, status, contract_type,
             launch_time, delivery_time, updated_at)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            [
                (
                    sym,
                    item.get("baseCoin", ""),
                    item.get("quoteCoin", ""),
                    item.get("status", ""),
                    item.get("contractType", ""),
                    _ms_to_date(item.get("launchTime")),
                    _ms_to_date(item.get("deliveryTime")),
                    now,
                )
                for sym, item in instruments.items()
            ],
        )
    conn.close()


def _cmc_candidates(max_rank: int) -> pd.DataFrame:
    conn = sqlite3.connect(config.DB_PATH)
    try:
        exists = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='crypto_market_cap_rankings'"
        ).fetchone()
        if exists is None:
            raise RuntimeError("Missing crypto_market_cap_rankings. Run fetch_cmc_historical_rankings.py first.")
        df = pd.read_sql_query(
            """
            SELECT
                symbol,
                MAX(name) AS name,
                MIN(rank) AS best_rank,
                AVG(market_cap) AS avg_market_cap,
                COUNT(DISTINCT snapshot_date) AS snapshots
            FROM crypto_market_cap_rankings
            WHERE rank <= ?
              AND COALESCE(is_stablecoin, 0) = 0
              AND COALESCE(is_wrapped, 0) = 0
              AND COALESCE(is_leveraged, 0) = 0
            GROUP BY symbol
            ORDER BY best_rank ASC, avg_market_cap DESC
            """,
            conn,
            params=(int(max_rank),),
        )
    finally:
        conn.close()
    df["bybit_symbol"] = df["symbol"].str.upper() + "USDT"
    df["yf_symbol"] = "BYBIT:" + df["bybit_symbol"] + ".P"
    return df


def _download_bybit_daily(bybit_symbol: str, start: str, end: str,
                          sleep: float) -> pd.DataFrame | None:
    session = BybitHTTP()
    start_ts = int(datetime.strptime(start, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    end_ts = int(datetime.strptime(end, "%Y-%m-%d").replace(tzinfo=timezone.utc).timestamp() * 1000)
    cursor = end_ts
    all_rows: list[list[Any]] = []

    while True:
        res = session.get_kline(
            category="linear",
            symbol=bybit_symbol,
            interval="D",
            start=start_ts,
            end=cursor,
            limit=1000,
        )
        rows = res.get("result", {}).get("list", [])
        if not rows:
            break
        all_rows.extend(rows)
        oldest_ts = int(rows[-1][0])
        if oldest_ts <= start_ts:
            break
        cursor = oldest_ts - 1
        if sleep > 0:
            time.sleep(sleep)

    if not all_rows:
        return None
    df = pd.DataFrame(all_rows, columns=["ts", "Open", "High", "Low", "Close", "Volume", "_turnover"])
    df["ts"] = pd.to_datetime(df["ts"].astype(int), unit="ms")
    df = df.set_index("ts").sort_index()
    df = df[["Open", "High", "Low", "Close", "Volume"]].astype(float)
    df.index.name = None
    df = df[(df.index >= pd.Timestamp(start)) & (df.index <= pd.Timestamp(end))].dropna(subset=["Close"])
    return df if not df.empty else None


def _log_fetch(yf_symbol: str, bybit_symbol: str, status: str, rows: int,
               start: str, end: str, message: str = "") -> None:
    conn = sqlite3.connect(config.DB_PATH)
    with conn:
        conn.execute(
            """
            INSERT INTO crypto_bybit_ohlcv_fetch_log
            (run_at, bybit_symbol, yf_symbol, status, rows, start_date, end_date, message)
            VALUES (?,?,?,?,?,?,?,?)
            """,
            (
                datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
                bybit_symbol,
                yf_symbol,
                status,
                int(rows),
                start,
                end,
                message,
            ),
        )
    conn.close()


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch Bybit OHLCV for CMC PIT universe candidates.")
    parser.add_argument("--max-rank", type=int, default=200)
    parser.add_argument("--start-date", default="2018-01-01")
    parser.add_argument("--end-date", default=datetime.now().strftime("%Y-%m-%d"))
    parser.add_argument("--min-bars-before-skip", type=int, default=260)
    parser.add_argument("--sleep", type=float, default=0.05)
    parser.add_argument("--limit", type=int, default=0, help="Optional cap for smoke tests.")
    parser.add_argument("--output", default="output/bybit_pit_ohlcv_fetch_candidates.csv")
    args = parser.parse_args()

    _init_tables()
    instruments = _fetch_instruments()
    _save_instruments(instruments)

    candidates = _cmc_candidates(args.max_rank)
    tradable = candidates[candidates["bybit_symbol"].isin(instruments.keys())].copy()
    tradable["bybit_status"] = tradable["bybit_symbol"].map(lambda s: instruments[s].get("status", ""))
    tradable["launch_time"] = tradable["bybit_symbol"].map(lambda s: _ms_to_date(instruments[s].get("launchTime")))
    tradable["has_local_last_date"] = tradable["yf_symbol"].map(lambda s: get_last_date(s) or "")
    tradable.to_csv(args.output, index=False, encoding="utf-8")

    rows = tradable.to_dict("records")
    if args.limit and args.limit > 0:
        rows = rows[:args.limit]

    ok = skipped = failed = 0
    for idx, rec in enumerate(rows, start=1):
        bybit_symbol = rec["bybit_symbol"]
        yf_symbol = rec["yf_symbol"]
        last = get_last_date(yf_symbol)
        if last:
            local = None
            try:
                from src.database import load_prices
                local = load_prices(yf_symbol)
            except Exception:
                local = None
            if local is not None and len(local) >= args.min_bars_before_skip and pd.Timestamp(last) >= pd.Timestamp(args.end_date) - pd.Timedelta(days=3):
                skipped += 1
                _log_fetch(yf_symbol, bybit_symbol, "skip_existing_fresh", 0, "", "", "")
                continue
            start = (datetime.strptime(last, "%Y-%m-%d") + timedelta(days=1)).strftime("%Y-%m-%d")
        else:
            launch = rec.get("launch_time") or ""
            start = max(pd.Timestamp(args.start_date), pd.Timestamp(launch) if launch else pd.Timestamp(args.start_date)).strftime("%Y-%m-%d")

        try:
            df = _download_bybit_daily(bybit_symbol, start, args.end_date, args.sleep)
            if df is None or df.empty:
                failed += 1
                _log_fetch(yf_symbol, bybit_symbol, "no_rows", 0, start, args.end_date, "")
                print(f"[{idx}/{len(rows)}] {yf_symbol} no rows")
                continue
            upsert_prices(df, yf_symbol, "Crypto")
            ok += 1
            _log_fetch(yf_symbol, bybit_symbol, "ok", len(df), start, args.end_date, "")
            print(f"[{idx}/{len(rows)}] {yf_symbol} +{len(df)} rows")
        except Exception as exc:
            failed += 1
            _log_fetch(yf_symbol, bybit_symbol, "error", 0, start, args.end_date, str(exc))
            print(f"[{idx}/{len(rows)}] {yf_symbol} error: {exc}")
        if args.sleep > 0:
            time.sleep(args.sleep)

    print(
        f"\nBybit instruments={len(instruments)} "
        f"cmc_candidates={len(candidates)} tradable_intersection={len(tradable)} "
        f"fetched={ok} skipped={skipped} failed={failed}"
    )
    print(f"Saved candidates: {args.output}")


if __name__ == "__main__":
    main()
