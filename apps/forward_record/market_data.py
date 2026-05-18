from __future__ import annotations

import json
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

