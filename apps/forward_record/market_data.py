from __future__ import annotations

import json
import re
import urllib.parse
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Protocol

import pandas as pd


class MarketDataProvider(Protocol):
    data_source: str

    def load_prices(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        ...

    def load_funding(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        ...


@dataclass(frozen=True)
class CacheMarketDataProvider:
    prices_path: Path
    funding_path: Path
    data_source: str = "cache_fallback"

    def load_prices(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        frame = pd.read_parquet(self.prices_path)
        _require_columns(frame, {"date", "symbol", "open", "close"}, self.prices_path)
        frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
        return frame[frame["date"].le(pd.Timestamp(as_of_date).normalize())].copy()

    def load_funding(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        frame = pd.read_parquet(self.funding_path)
        _require_columns(frame, {"timestamp", "symbol", "funding_rate", "interval_hours"}, self.funding_path)
        frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
        as_of = pd.Timestamp(as_of_date).normalize().tz_localize("UTC") + pd.Timedelta(days=1)
        return frame[frame["timestamp"].lt(as_of)].copy()


@dataclass(frozen=True)
class BybitReadOnlyMarketDataProvider:
    allow_network: bool = False
    base_url: str = "https://api.bybit.com"
    data_source: str = "bybit_read_only_get"

    def load_prices(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        if not self.allow_network:
            raise RuntimeError("Bybit read-only GET disabled; use cache_fallback")
        payload = self._get_public_market("kline", {"category": "linear", "interval": "D"})
        return pd.DataFrame(payload.get("result", {}).get("list", []))

    def load_funding(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        if not self.allow_network:
            raise RuntimeError("Bybit read-only GET disabled; use cache_fallback")
        payload = self._get_public_market("funding/history", {"category": "linear"})
        return pd.DataFrame(payload.get("result", {}).get("list", []))

    def _get_public_market(self, resource: str, params: dict[str, Any]) -> dict[str, Any]:
        allowed = {"kline", "funding/history"}
        if resource not in allowed:
            raise ValueError(f"unsupported read-only market resource: {resource}")
        query = urllib.parse.urlencode(params)
        url = f"{self.base_url}/v5/market/{resource}?{query}"
        request = urllib.request.Request(
            url,
            method="GET",
            headers={"Accept": "application/json", "User-Agent": "QuantForwardRecord/1.0"},
        )
        with urllib.request.urlopen(request, timeout=20) as response:
            return json.loads(response.read().decode("utf-8"))



@dataclass(frozen=True)
class LiveReadOnlyMarketDataProvider:
    """
    TASK-011A: Hybrid provider — cache for historical data, Bybit public
    tickers (no auth) for dates past the cache cutoff.

    Bybit endpoint: GET /v5/market/tickers?category=linear
      - Read-only public GET, no API key required
      - Returns lastPrice for all linear perpetuals
    Symbol mapping: BYBIT:XYZUSDT.P  →  XYZUSDT  (strip prefix + .P suffix)
    Reverse:        XYZUSDT           →  BYBIT:XYZUSDT.P

    Safety: NO private endpoints, NO order API, NO write operations.
    """
    prices_path: Path
    funding_path: Path
    base_url: str = "https://api.bybit.com"
    data_source: str = "bybit_read_only_live"

    def load_prices(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        """
        Returns historical cache prices PLUS a synthetic row for each symbol
        at as_of_date using the latest Bybit public ticker (lastPrice).
        Falls back silently to cache-only if network is unavailable.
        """
        cache_provider = CacheMarketDataProvider(self.prices_path, self.funding_path)
        hist = cache_provider.load_prices(as_of_date)
        try:
            live_rows = _fetch_bybit_tickers(self.base_url, as_of_date)
            if not live_rows.empty:
                combined = pd.concat([hist, live_rows], ignore_index=True)
                return combined
        except Exception:
            pass  # network unavailable — fall back to cache silently
        return hist

    def load_funding(self, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
        """Funding from cache only (used for overlay signal logic, not MTM)."""
        return CacheMarketDataProvider(self.prices_path, self.funding_path).load_funding(as_of_date)


def _bybit_symbol_to_internal(bybit_sym: str) -> str:
    """BTCUSDT → BYBIT:BTCUSDT.P"""
    return f"BYBIT:{bybit_sym}.P"


def _internal_to_bybit_symbol(internal_sym: str) -> str:
    """BYBIT:BTCUSDT.P → BTCUSDT"""
    return re.sub(r"^BYBIT:", "", internal_sym).removesuffix(".P")


def _fetch_bybit_tickers(base_url: str, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    """
    Fetch /v5/market/tickers?category=linear (public, no auth).
    Returns DataFrame with columns: date, symbol (BYBIT:XYZ.P), open, close.
    Raises on network error so caller can fallback.
    """
    url = f"{base_url}/v5/market/tickers?category=linear"
    request = urllib.request.Request(
        url, method="GET",
        headers={"Accept": "application/json", "User-Agent": "QuantForwardRecord/1.0"},
    )
    with urllib.request.urlopen(request, timeout=20) as response:
        data = json.loads(response.read().decode("utf-8"))

    ret_code = data.get("retCode", -1)
    if ret_code != 0:
        raise RuntimeError(f"Bybit API retCode={ret_code}: {data.get('retMsg')}")

    today = pd.Timestamp(as_of_date).normalize()
    rows: list[dict] = []
    for item in data.get("result", {}).get("list", []):
        bybit_sym = item.get("symbol", "")
        last_px_str = item.get("lastPrice", "")
        if not last_px_str:
            continue
        try:
            last_px = float(last_px_str)
        except (ValueError, TypeError):
            continue
        if last_px <= 0:
            continue
        internal_sym = _bybit_symbol_to_internal(bybit_sym)
        rows.append({
            "date":   today,
            "symbol": internal_sym,
            "open":   last_px,   # used as hypothetical_fill_px in _decorate_positions
            "close":  last_px,
        })
    return pd.DataFrame(rows) if rows else pd.DataFrame(columns=["date", "symbol", "open", "close"])


def check_price_freshness(
    prices: pd.DataFrame,
    record_date: str | pd.Timestamp,
    symbols: list[str] | None = None,
) -> dict:
    """
    TASK-011A freshness diagnostic.
    Returns a dict describing the currency of market data relative to record_date.
    """
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    record_ts = pd.Timestamp(record_date).normalize()

    if frame.empty:
        return {
            "record_date": str(record_ts.date()),
            "cache_latest_date": None,
            "days_stale": None,
            "has_record_date_prices": False,
            "freshness_status": "NO_DATA",
        }

    cache_latest = frame["date"].max()
    days_stale = (record_ts - cache_latest).days
    has_today = bool((frame["date"] == record_ts).any())

    # Check if hypothetical_fill_px varies (proxy: use open column)
    if symbols:
        sym_frame = frame[frame["symbol"].isin(symbols)]
    else:
        sym_frame = frame

    px_variance: float | None = None
    if "open" in sym_frame.columns and not sym_frame.empty:
        try:
            px_variance = float(sym_frame.groupby("symbol")["open"].std().mean())
        except Exception:
            pass

    if days_stale == 0 and has_today:
        status = "FRESH"
    elif days_stale <= 3:
        status = "STALE_RECENT"
    else:
        status = "STALE_OLD"

    return {
        "record_date":           str(record_ts.date()),
        "cache_latest_date":     str(cache_latest.date()),
        "days_stale":            int(days_stale),
        "has_record_date_prices": has_today,
        "mean_price_std_across_days": px_variance,
        "freshness_status":      status,
    }


def latest_prices_by_symbol(prices: pd.DataFrame, as_of_date: str | pd.Timestamp) -> pd.DataFrame:
    frame = prices.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame = frame[frame["date"].le(pd.Timestamp(as_of_date).normalize())].copy()
    frame = frame.sort_values(["symbol", "date"]).groupby("symbol", as_index=False).tail(1)
    return frame.loc[:, ["symbol", "date", "open", "close"]].reset_index(drop=True)


def _require_columns(frame: pd.DataFrame, required: set[str], path: Path) -> None:
    missing = required - set(frame.columns)
    if missing:
        raise ValueError(f"{path} missing columns: {sorted(missing)}")

