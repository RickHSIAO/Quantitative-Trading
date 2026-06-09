"""
src/demo_market_price_guard.py
TASK-014O: Demo new-entry realtime market price guard.

Provides a read-only, fail-closed mechanism for verifying that a new-entry
candidate's `entry_reference_price` is anchored to a live market price
quoted by the Bybit Demo exchange (NOT a fixture, NOT a stale snapshot).

The module exposes:

    DemoMarketPriceGuard             - client that fetches realtime prices
    RealtimeMarketPrice              - dataclass returned by the client
    PriceGuardEvaluation             - per-candidate guard result
    evaluate_price_guard()           - pure-computation guard evaluator
    DEFAULT_PRICE_GUARD_THRESHOLD_PCT = 5.0

SAFETY INVARIANTS (verified by tests):
  * Only DEMO_BASE_URL (https://api-demo.bybit.com) is ever contacted.
  * Only the unauthenticated /v5/market/tickers path is GET-ed.
  * No order endpoint paths are referenced (create / cancel / amend / batch).
  * No HMAC signing, no API key/secret loaded by this module.
  * No imports of main / src.risk / BybitExecutor / demo_close_only_sender /
    demo_new_entry_sender / demo_emergency_close_sender / pybit.
  * Fixture mode (allow_real_network=False) performs zero I/O.

The realtime price source is the public Bybit V5 market-tickers endpoint
hosted on the demo URL.  It is read-only and requires no authentication.
"""
from __future__ import annotations

import json
import math
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# URL constants (re-declared locally to keep this module independent)
# ---------------------------------------------------------------------------

DEMO_BASE_URL  = "https://api-demo.bybit.com"
_LIVE_HOSTNAME = "api.bybit.com"   # sentinel only — never used as a request target

MARKET_TICKERS_ENDPOINT = "/v5/market/tickers"

_ALLOWED_PATHS: frozenset[str] = frozenset({MARKET_TICKERS_ENDPOINT})


# ---------------------------------------------------------------------------
# Public constants
# ---------------------------------------------------------------------------

DEFAULT_PRICE_GUARD_THRESHOLD_PCT: float = 5.0

PRICE_SOURCE_NONE                 = "none"
PRICE_SOURCE_FIXTURE              = "demo_market_price_guard_fixture"
PRICE_SOURCE_BYBIT_DEMO_TICKER    = "bybit_demo_v5_market_tickers"

GUARD_FAIL_MISSING_REALTIME_PRICE      = "missing_realtime_price"
GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE = "stale_entry_reference_price"
GUARD_FAIL_INVALID_CANDIDATE_PRICE     = "invalid_candidate_entry_reference_price"
GUARD_FAIL_INVALID_REALTIME_PRICE      = "invalid_realtime_market_price"
GUARD_FAIL_INVALID_THRESHOLD           = "invalid_price_guard_threshold"


# ---------------------------------------------------------------------------
# Fixture data — never assumes a particular SOLUSDT/AAVEUSDT price; the test
# suite supplies its own RealtimeMarketPrice objects.  These fixtures only
# exist for offline dev mode (allow_real_network=False).
# ---------------------------------------------------------------------------

FIXTURE_MARKET_PRICES: dict[str, float] = {
    "BTCUSDT":  67_000.0,
    "ETHUSDT":   3_500.0,
    "BNBUSDT":     600.0,
    "SOLUSDT":      66.47,   # matches the actual SOLUSDT fill in TASK-014L incident
    "XRPUSDT":       0.62,
    "ADAUSDT":       0.45,
    "DOTUSDT":       7.0,
    "LINKUSDT":     14.5,
    "AAVEUSDT":     90.0,
    "AVAXUSDT":     30.0,
}


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass
class RealtimeMarketPrice:
    """
    A single symbol's realtime market price snapshot.

    realtime_market_price > 0 indicates a usable reading; 0.0 with a non-empty
    fetch_error_reason indicates the price was unavailable and any candidate
    keyed to this symbol must be rejected.
    """
    symbol:                str
    realtime_market_price: float
    price_source:          str
    price_timestamp_utc:   str
    fetch_error_reason:    str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol":                self.symbol,
            "realtime_market_price": self.realtime_market_price,
            "price_source":          self.price_source,
            "price_timestamp_utc":   self.price_timestamp_utc,
            "fetch_error_reason":    self.fetch_error_reason,
        }

    def is_usable(self) -> bool:
        return (
            isinstance(self.realtime_market_price, (int, float))
            and math.isfinite(self.realtime_market_price)
            and self.realtime_market_price > 0
            and not self.fetch_error_reason
        )


@dataclass
class PriceGuardEvaluation:
    """
    Per-candidate guard result.

    realtime_price_guard_verified is True iff:
      * a usable RealtimeMarketPrice was available, AND
      * |candidate_entry_reference_price - realtime_market_price|
            / realtime_market_price * 100 <= price_guard_threshold_pct.
    """
    symbol:                          str
    candidate_entry_reference_price: float
    realtime_market_price:           float
    price_source:                    str
    price_timestamp_utc:             str
    price_guard_threshold_pct:       float
    price_deviation_pct:             float
    realtime_price_guard_verified:   bool
    price_guard_fail_reason:         str

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol":                          self.symbol,
            "candidate_entry_reference_price": self.candidate_entry_reference_price,
            "realtime_market_price":           self.realtime_market_price,
            "price_source":                    self.price_source,
            "price_timestamp_utc":             self.price_timestamp_utc,
            "price_guard_threshold_pct":       self.price_guard_threshold_pct,
            "price_deviation_pct":             round(self.price_deviation_pct, 4),
            "realtime_price_guard_verified":   self.realtime_price_guard_verified,
            "price_guard_fail_reason":         self.price_guard_fail_reason,
        }


# ---------------------------------------------------------------------------
# Pure-computation evaluator
# ---------------------------------------------------------------------------

def evaluate_price_guard(
    symbol:                          str,
    candidate_entry_reference_price: float,
    market_price:                    RealtimeMarketPrice | None,
    threshold_pct:                   float = DEFAULT_PRICE_GUARD_THRESHOLD_PCT,
) -> PriceGuardEvaluation:
    """
    Evaluate the realtime price guard for a single candidate.

    Returns a PriceGuardEvaluation with:
      realtime_price_guard_verified=True   only when a usable market price was
                                          supplied AND |dev|% <= threshold.
      realtime_price_guard_verified=False  with a populated fail_reason in
                                          every other case.

    Pure function — no I/O, no global state.
    """
    # --- threshold sanity -------------------------------------------------
    if not (
        isinstance(threshold_pct, (int, float))
        and math.isfinite(threshold_pct)
        and threshold_pct > 0
    ):
        return PriceGuardEvaluation(
            symbol=symbol,
            candidate_entry_reference_price=float(candidate_entry_reference_price or 0.0),
            realtime_market_price=0.0,
            price_source=PRICE_SOURCE_NONE,
            price_timestamp_utc="",
            price_guard_threshold_pct=float(threshold_pct or 0.0),
            price_deviation_pct=0.0,
            realtime_price_guard_verified=False,
            price_guard_fail_reason=GUARD_FAIL_INVALID_THRESHOLD,
        )

    # --- candidate price sanity -------------------------------------------
    if not (
        isinstance(candidate_entry_reference_price, (int, float))
        and math.isfinite(candidate_entry_reference_price)
        and candidate_entry_reference_price > 0
    ):
        return PriceGuardEvaluation(
            symbol=symbol,
            candidate_entry_reference_price=float(candidate_entry_reference_price or 0.0),
            realtime_market_price=(market_price.realtime_market_price
                                   if market_price else 0.0),
            price_source=(market_price.price_source if market_price
                          else PRICE_SOURCE_NONE),
            price_timestamp_utc=(market_price.price_timestamp_utc
                                 if market_price else ""),
            price_guard_threshold_pct=float(threshold_pct),
            price_deviation_pct=0.0,
            realtime_price_guard_verified=False,
            price_guard_fail_reason=GUARD_FAIL_INVALID_CANDIDATE_PRICE,
        )

    # --- realtime market price sanity -------------------------------------
    if market_price is None or not market_price.is_usable():
        return PriceGuardEvaluation(
            symbol=symbol,
            candidate_entry_reference_price=float(candidate_entry_reference_price),
            realtime_market_price=(market_price.realtime_market_price
                                   if market_price else 0.0),
            price_source=(market_price.price_source if market_price
                          else PRICE_SOURCE_NONE),
            price_timestamp_utc=(market_price.price_timestamp_utc
                                 if market_price else ""),
            price_guard_threshold_pct=float(threshold_pct),
            price_deviation_pct=0.0,
            realtime_price_guard_verified=False,
            price_guard_fail_reason=GUARD_FAIL_MISSING_REALTIME_PRICE,
        )

    # --- deviation check --------------------------------------------------
    real_price = float(market_price.realtime_market_price)
    cand_price = float(candidate_entry_reference_price)
    deviation_pct = abs(cand_price - real_price) / real_price * 100.0
    verified = deviation_pct <= float(threshold_pct) + 1e-12
    fail_reason = "" if verified else GUARD_FAIL_STALE_ENTRY_REFERENCE_PRICE

    return PriceGuardEvaluation(
        symbol=symbol,
        candidate_entry_reference_price=cand_price,
        realtime_market_price=real_price,
        price_source=market_price.price_source,
        price_timestamp_utc=market_price.price_timestamp_utc,
        price_guard_threshold_pct=float(threshold_pct),
        price_deviation_pct=deviation_pct,
        realtime_price_guard_verified=verified,
        price_guard_fail_reason=fail_reason,
    )


def evaluate_candidates_against_market(
    candidate_entry_prices: dict[str, float],
    market_prices:          dict[str, RealtimeMarketPrice],
    threshold_pct:          float = DEFAULT_PRICE_GUARD_THRESHOLD_PCT,
) -> dict[str, PriceGuardEvaluation]:
    """
    Batch helper.  Pure function — no I/O.

    For every symbol in candidate_entry_prices, returns a PriceGuardEvaluation.
    Symbols not present in market_prices are evaluated against `None` and will
    fail with missing_realtime_price.
    """
    out: dict[str, PriceGuardEvaluation] = {}
    for symbol, cand_price in candidate_entry_prices.items():
        out[symbol] = evaluate_price_guard(
            symbol=symbol,
            candidate_entry_reference_price=cand_price,
            market_price=market_prices.get(symbol),
            threshold_pct=threshold_pct,
        )
    return out


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class DemoMarketPriceGuard:
    """
    Read-only fetcher for Bybit Demo V5 market tickers (public endpoint).

    Default (allow_real_network=False): returns FIXTURE_MARKET_PRICES values.
    Real mode (allow_real_network=True): unauthenticated GET to
      https://api-demo.bybit.com/v5/market/tickers?category=linear&symbol=...

    No API key, no API secret, no HMAC signing.  Only the demo URL is ever
    contacted.  Order endpoint paths are never referenced.
    """

    def __init__(self, allow_real_network: bool = False) -> None:
        self._allow_real = bool(allow_real_network)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def fetch_market_price(self, symbol: str) -> RealtimeMarketPrice:
        sym = (symbol or "").strip().upper()
        if not sym:
            return RealtimeMarketPrice(
                symbol="", realtime_market_price=0.0,
                price_source=PRICE_SOURCE_NONE,
                price_timestamp_utc="", fetch_error_reason="empty_symbol",
            )
        if not self._allow_real:
            price = FIXTURE_MARKET_PRICES.get(sym, 0.0)
            return RealtimeMarketPrice(
                symbol=sym,
                realtime_market_price=float(price),
                price_source=PRICE_SOURCE_FIXTURE,
                price_timestamp_utc=_utc_now_iso(),
                fetch_error_reason="" if price > 0 else "fixture_symbol_not_listed",
            )
        return self._fetch_real(sym)

    def fetch_market_prices(
        self, symbols: list[str],
    ) -> dict[str, RealtimeMarketPrice]:
        out: dict[str, RealtimeMarketPrice] = {}
        for s in symbols:
            snap = self.fetch_market_price(s)
            if snap.symbol:
                out[snap.symbol] = snap
        return out

    # ------------------------------------------------------------------
    # Real-mode internals
    # ------------------------------------------------------------------

    def _fetch_real(self, symbol: str) -> RealtimeMarketPrice:
        path = MARKET_TICKERS_ENDPOINT
        if path not in _ALLOWED_PATHS:
            return RealtimeMarketPrice(
                symbol=symbol, realtime_market_price=0.0,
                price_source=PRICE_SOURCE_NONE,
                price_timestamp_utc=_utc_now_iso(),
                fetch_error_reason=f"path_not_allowed:{path}",
            )
        params = {"category": "linear", "symbol": symbol}
        query  = urllib.parse.urlencode(sorted(params.items()))
        url    = f"{DEMO_BASE_URL}{path}?{query}"
        req = urllib.request.Request(
            url,
            headers={"Content-Type": "application/json"},
            method="GET",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode("utf-8"))
        except Exception as exc:  # noqa: BLE001 — surface any network/parse error
            return RealtimeMarketPrice(
                symbol=symbol, realtime_market_price=0.0,
                price_source=PRICE_SOURCE_BYBIT_DEMO_TICKER,
                price_timestamp_utc=_utc_now_iso(),
                fetch_error_reason=f"fetch_error:{type(exc).__name__}",
            )

        ret_code = data.get("retCode", -1)
        if ret_code != 0:
            return RealtimeMarketPrice(
                symbol=symbol, realtime_market_price=0.0,
                price_source=PRICE_SOURCE_BYBIT_DEMO_TICKER,
                price_timestamp_utc=_utc_now_iso(),
                fetch_error_reason=f"retCode={ret_code}",
            )
        rows = (data.get("result", {}) or {}).get("list", []) or []
        last_price = 0.0
        for row in rows:
            if (row.get("symbol", "") or "").upper() == symbol:
                try:
                    last_price = float(row.get("lastPrice", 0) or 0)
                except (TypeError, ValueError):
                    last_price = 0.0
                break
        if last_price <= 0 or not math.isfinite(last_price):
            return RealtimeMarketPrice(
                symbol=symbol, realtime_market_price=0.0,
                price_source=PRICE_SOURCE_BYBIT_DEMO_TICKER,
                price_timestamp_utc=_utc_now_iso(),
                fetch_error_reason="last_price_unavailable",
            )
        return RealtimeMarketPrice(
            symbol=symbol,
            realtime_market_price=last_price,
            price_source=PRICE_SOURCE_BYBIT_DEMO_TICKER,
            price_timestamp_utc=_utc_now_iso(),
            fetch_error_reason="",
        )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """ISO-8601 UTC timestamp without secret leakage."""
    return datetime.now(tz=timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
