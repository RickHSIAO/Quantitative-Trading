"""Fetch CoinMarketCap historical snapshots into SQLite.

The source pages are weekly historical snapshots such as:
https://coinmarketcap.com/historical/20201227/

This is research infrastructure for point-in-time universe construction. It
does not touch strategy logic, costs, or position sizing.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import sqlite3
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from html import unescape
from html.parser import HTMLParser
from pathlib import Path
from typing import Any

import pandas as pd
import requests

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import config


CMC_HISTORICAL_URL = "https://coinmarketcap.com/historical/{yyyymmdd}/"
USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
    "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0 Safari/537.36"
)

STABLE_SYMBOLS = {
    "USDT", "USDC", "DAI", "TUSD", "FDUSD", "USDE", "USDD", "PYUSD",
    "FRAX", "LUSD", "USD1", "USDP", "GUSD", "BUSD", "EURS", "EURC",
    "UST", "USTC", "HUSD", "PAX", "PAXG", "GUSD", "SUSD", "MIM",
}
WRAPPED_SYMBOLS = {
    "WBTC", "WETH", "WBNB", "WSTETH", "STETH", "RETH", "CBETH", "WEETH",
    "WAVAX", "WSOL", "WMATIC", "WFTM", "RENBTC",
}
LEVERAGED_SUFFIXES = (
    "2L", "2S", "3L", "3S", "4L", "4S", "5L", "5S",
    "UP", "DOWN", "BULL", "BEAR",
)


@dataclass(frozen=True)
class SnapshotRow:
    snapshot_date: str
    rank: int
    name: str
    symbol: str
    market_cap: float | None
    price: float | None
    circulating_supply: float | None
    volume_24h: float | None
    source_url: str
    fetched_at: str
    is_stablecoin: int
    is_wrapped: int
    is_leveraged: int


class TextExtractor(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.parts: list[str] = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if text:
            self.parts.append(unescape(text))


def _init_db() -> None:
    conn = sqlite3.connect(config.DB_PATH)
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS crypto_market_cap_rankings (
                snapshot_date TEXT NOT NULL,
                rank INTEGER NOT NULL,
                name TEXT,
                symbol TEXT NOT NULL,
                market_cap REAL,
                price REAL,
                circulating_supply REAL,
                volume_24h REAL,
                source TEXT NOT NULL,
                source_url TEXT NOT NULL,
                fetched_at TEXT NOT NULL,
                is_stablecoin INTEGER DEFAULT 0,
                is_wrapped INTEGER DEFAULT 0,
                is_leveraged INTEGER DEFAULT 0,
                PRIMARY KEY (snapshot_date, rank, symbol)
            )
        """)
        conn.execute("""
            CREATE INDEX IF NOT EXISTS idx_cmc_mcap_snapshot_symbol
            ON crypto_market_cap_rankings(snapshot_date, symbol)
        """)
    conn.close()


def _money_to_float(value: str) -> float | None:
    text = value.replace("$", "").replace(",", "").replace("<", "").strip()
    if not text or text in {"?", "--", "-"}:
        return None
    try:
        return float(text)
    except ValueError:
        return None


def _number_to_float(value: str) -> float | None:
    text = value.replace(",", "").replace("*", "").strip()
    if not text or text in {"?", "--", "-"}:
        return None
    try:
        return float(text.split()[0])
    except (ValueError, IndexError):
        return None


def _is_leveraged(symbol: str) -> bool:
    return symbol.upper().endswith(LEVERAGED_SUFFIXES)


def _flags(symbol: str) -> tuple[int, int, int]:
    sym = symbol.upper()
    return (
        int(sym in STABLE_SYMBOLS),
        int(sym in WRAPPED_SYMBOLS),
        int(_is_leveraged(sym)),
    )


def _extract_text(html: str) -> list[str]:
    parser = TextExtractor()
    parser.feed(html)
    return [part.strip() for part in parser.parts if part.strip()]


def _find_rank_positions(tokens: list[str], max_rank: int) -> list[tuple[int, int]]:
    out: list[tuple[int, int]] = []
    expected = 1
    for idx, token in enumerate(tokens):
        if token == str(expected):
            out.append((expected, idx))
            expected += 1
            if expected > max_rank:
                break
    return out


def _parse_segment(snapshot_date: str,
                   rank: int,
                   segment: list[str],
                   source_url: str,
                   fetched_at: str) -> SnapshotRow | None:
    money_positions = [
        idx for idx, token in enumerate(segment)
        if token.startswith("$") and _money_to_float(token) is not None
    ]
    if len(money_positions) < 3:
        return None

    market_cap_idx, price_idx, volume_idx = money_positions[:3]
    symbol_candidates = [
        token for token in segment[:market_cap_idx]
        if re.fullmatch(r"[A-Z0-9]{2,15}", token)
    ]
    if not symbol_candidates:
        return None
    symbol = symbol_candidates[-1].upper()

    # CMC often emits image alt text and ticker links before the coin name.
    name_candidates = [
        token for token in segment[:market_cap_idx]
        if token != symbol
        and not token.startswith("Image:")
        and not re.fullmatch(r"[A-Z0-9]{2,15}", token)
    ]
    name = name_candidates[-1] if name_candidates else symbol

    supply_tokens = segment[price_idx + 1:volume_idx]
    supply = None
    if supply_tokens:
        supply = _number_to_float(supply_tokens[0])

    stable, wrapped, leveraged = _flags(symbol)
    return SnapshotRow(
        snapshot_date=snapshot_date,
        rank=rank,
        name=name,
        symbol=symbol,
        market_cap=_money_to_float(segment[market_cap_idx]),
        price=_money_to_float(segment[price_idx]),
        circulating_supply=supply,
        volume_24h=_money_to_float(segment[volume_idx]),
        source_url=source_url,
        fetched_at=fetched_at,
        is_stablecoin=stable,
        is_wrapped=wrapped,
        is_leveraged=leveraged,
    )


def parse_snapshot(html: str, snapshot_date: str, source_url: str,
                   max_rank: int = 300) -> list[SnapshotRow]:
    json_rows = _parse_next_data_snapshot(html, snapshot_date, source_url, max_rank)
    if json_rows:
        return json_rows

    tokens = _extract_text(html)
    positions = _find_rank_positions(tokens, max_rank)
    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[SnapshotRow] = []
    for idx, (rank, pos) in enumerate(positions):
        next_pos = positions[idx + 1][1] if idx + 1 < len(positions) else len(tokens)
        segment = tokens[pos + 1:next_pos]
        parsed = _parse_segment(snapshot_date, rank, segment, source_url, fetched_at)
        if parsed is not None:
            rows.append(parsed)
    return rows


def _parse_next_data_snapshot(html: str,
                              snapshot_date: str,
                              source_url: str,
                              max_rank: int) -> list[SnapshotRow]:
    match = re.search(
        r'<script id="__NEXT_DATA__" type="application/json"[^>]*>(.*?)</script>',
        html,
        flags=re.DOTALL,
    )
    if not match:
        return []
    try:
        next_data = json.loads(match.group(1))
        initial_state = next_data.get("props", {}).get("initialState")
        if isinstance(initial_state, str):
            initial_state = json.loads(initial_state)
        listing = (
            initial_state
            .get("cryptocurrency", {})
            .get("listingHistorical", {})
            .get("data", [])
        )
    except Exception:
        return []

    fetched_at = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    rows: list[SnapshotRow] = []
    for item in listing:
        if not isinstance(item, dict):
            continue
        rank = int(item.get("rank") or item.get("cmcRank") or 0)
        if rank <= 0 or rank > max_rank:
            continue
        symbol = str(item.get("symbol") or "").upper().strip()
        if not symbol:
            continue
        quote = item.get("quote", {}).get("USD", {}) if isinstance(item.get("quote"), dict) else {}
        stable, wrapped, leveraged = _flags(symbol)
        rows.append(SnapshotRow(
            snapshot_date=snapshot_date,
            rank=rank,
            name=str(item.get("name") or symbol),
            symbol=symbol,
            market_cap=float(quote["marketCap"]) if quote.get("marketCap") is not None else None,
            price=float(quote["price"]) if quote.get("price") is not None else None,
            circulating_supply=float(item["circulatingSupply"]) if item.get("circulatingSupply") is not None else None,
            volume_24h=float(quote["volume24h"]) if quote.get("volume24h") is not None else None,
            source_url=source_url,
            fetched_at=fetched_at,
            is_stablecoin=stable,
            is_wrapped=wrapped,
            is_leveraged=leveraged,
        ))
    return sorted(rows, key=lambda row: row.rank)


def fetch_snapshot(date: pd.Timestamp, max_rank: int, timeout: int) -> list[SnapshotRow]:
    yyyymmdd = date.strftime("%Y%m%d")
    url = CMC_HISTORICAL_URL.format(yyyymmdd=yyyymmdd)
    res = requests.get(
        url,
        headers={"User-Agent": USER_AGENT, "Accept-Language": "en-US,en;q=0.9"},
        timeout=timeout,
    )
    res.raise_for_status()
    rows = parse_snapshot(res.text, date.strftime("%Y-%m-%d"), url, max_rank=max_rank)
    if not rows:
        raise RuntimeError(f"No rows parsed from {url}")
    return rows


def _save_rows(rows: list[SnapshotRow]) -> None:
    if not rows:
        return
    conn = sqlite3.connect(config.DB_PATH)
    with conn:
        conn.executemany(
            """
            INSERT OR REPLACE INTO crypto_market_cap_rankings
            (snapshot_date, rank, name, symbol, market_cap, price,
             circulating_supply, volume_24h, source, source_url, fetched_at,
             is_stablecoin, is_wrapped, is_leveraged)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """,
            [
                (
                    r.snapshot_date, r.rank, r.name, r.symbol, r.market_cap,
                    r.price, r.circulating_supply, r.volume_24h,
                    "coinmarketcap_historical_snapshot", r.source_url, r.fetched_at,
                    r.is_stablecoin, r.is_wrapped, r.is_leveraged,
                )
                for r in rows
            ],
        )
    conn.close()


def _write_csv(path: Path, rows: list[SnapshotRow]) -> None:
    if not rows:
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=list(rows[0].__dict__.keys()))
        writer.writeheader()
        writer.writerows([r.__dict__ for r in rows])


def _snapshot_dates(start_year: int, end_year: int, freq: str) -> list[pd.Timestamp]:
    start = pd.Timestamp(f"{start_year}-01-01")
    end = pd.Timestamp(f"{end_year}-12-31")
    if freq == "weekly":
        return list(pd.date_range(start, end, freq="W-SUN"))
    if freq == "monthly":
        dates = pd.date_range(start, end, freq="ME")
        # CMC historical pages are Sunday snapshots. Use the previous Sunday
        # for each month-end point-in-time observation.
        return sorted({d - pd.Timedelta(days=(d.weekday() + 1) % 7) for d in dates})
    raise ValueError("freq must be weekly or monthly")


def main() -> None:
    parser = argparse.ArgumentParser(description="Fetch CMC historical rankings into SQLite.")
    parser.add_argument("--start-year", type=int, default=2018)
    parser.add_argument("--end-year", type=int, default=2025)
    parser.add_argument("--freq", choices=["weekly", "monthly"], default="monthly")
    parser.add_argument("--max-rank", type=int, default=300)
    parser.add_argument("--sleep", type=float, default=1.0)
    parser.add_argument("--timeout", type=int, default=30)
    parser.add_argument("--output-csv", default="")
    args = parser.parse_args()

    _init_db()
    all_rows: list[SnapshotRow] = []
    dates = _snapshot_dates(args.start_year, args.end_year, args.freq)
    for idx, date in enumerate(dates, start=1):
        try:
            rows = fetch_snapshot(date, args.max_rank, args.timeout)
            _save_rows(rows)
            all_rows.extend(rows)
            print(f"[{idx}/{len(dates)}] {date.date()} rows={len(rows)} saved")
        except Exception as exc:
            print(f"[WARN] {date.date()} failed: {exc}")
        if args.sleep > 0:
            time.sleep(args.sleep)

    if args.output_csv:
        _write_csv(Path(args.output_csv), all_rows)
        print(f"CSV saved: {args.output_csv}")
    print(f"Done. rows={len(all_rows)} db={config.DB_PATH}")


if __name__ == "__main__":
    main()
