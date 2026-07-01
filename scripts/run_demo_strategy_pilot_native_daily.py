"""TASK-014BX (+_FIX) -- production strategy-native daily Bybit Demo command.

Normal production invocation requires only the Pilot id, the execution date, and
the explicit Demo send flag -- NO manually prepared action JSON:

    python scripts/run_demo_strategy_pilot_native_daily.py \
        --pilot-id BYBIT_DEMO_PILOT_7D_202606_V1 --date YYYY-MM-DD \
        --send-orders-to-demo --json-only

Pipeline for one Pilot date:
    1. read the RUNNING Pilot state (execution-authorized; Live denied);
    2. load + validate the authoritative Primary Forward Record source (TASK-014BS);
    3. DERIVE concrete strategy-native actions with the canonical planner
       (src/demo_strategy_pilot_action_planner.py), which reuses the existing
       0.4 fractional-Kelly portfolio sizer + stop model + instrument rounding +
       target-vs-current position transition. No weight-to-quantity formula is
       invented; if a usable planner/account data is unavailable it fails closed
       with STRATEGY_NATIVE_ACTION_PLANNER_UNAVAILABLE;
    4. run all hard-safety / endpoint / protected-symbol / idempotency checks and
       send eligible orders ONLY to Bybit Demo (only under --send-orders-to-demo);
    5. reconcile every submission to an unambiguous state;
    6. on an unambiguous day, finalize the existing reporting foundation (Excel +
       output-status ledger; optional Notion/Discord) and advance the
       successful-day counter AT MOST once -- only after Excel built OK.

--reconcile-outputs-only retries reporting WITHOUT planning or executing.
Default (without --send-orders-to-demo) is a NO-NETWORK plan preview.

Live trading is never enabled. Reuses the Demo-only endpoint guard / read-only
client / sizer verbatim; imports neither main, src.risk nor BybitExecutor.
"""

from __future__ import annotations

import argparse
import contextlib
import hashlib
import hmac
import io
import json
import os
import re
import sys
import time
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from types import SimpleNamespace
from typing import Any, Mapping, Sequence

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_strategy_pilot_action_planner as planner  # noqa: E402
from src import demo_strategy_pilot_execution_gate as gate  # noqa: E402 (ISOLATED one-shot test utility)
from src import demo_strategy_native_v1_portfolio as v1  # noqa: E402 (ACTIVE V1 policy)
from src import demo_strategy_native_current_feasibility as cf  # noqa: E402 (CH4A feasibility model)
from src import demo_strategy_native_ws_price_binding as wb  # noqa: E402 (canonical qty rounding)
from src import demo_strategy_native_margin_freshness_audit as md  # noqa: E402 (TASK-014CD evidence)
from src import demo_strategy_native_account_mode_risk_tier_audit as ce  # noqa: E402 (TASK-014CE evidence)
from src import demo_strategy_pilot_forward_source as fs  # noqa: E402
from src import demo_strategy_pilot_native_execution as nx  # noqa: E402
from src import demo_strategy_pilot_native_reporting as nrep  # noqa: E402
from src import demo_strategy_pilot_readiness as rd  # noqa: E402
from src import demo_strategy_native_ws_bound_plan_only as wsbpo  # noqa: E402 (CH2 Plan-only WS binding)
from src import demo_strategy_native_ws_bound_plan_review as wsbpr  # noqa: E402 (CH3 review-only)
from src.demo_only_tiny_execution_adapter_single_real_demo_order import (  # noqa: E402
    DEMO_BASE_URL, DEMO_HOST, EP_ORDER_REALTIME, EP_ORDER_HISTORY,
    RealDemoHttpTransport, assert_demo_url, host_of, load_demo_credentials,
    _NoRedirectHandler,
)

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3
EXIT_PLANNER_UNAVAILABLE = 5
EXIT_AMBIGUOUS = 6
EXIT_V1_SIZING_UNVERIFIED = 7
EXIT_V1_CAPITAL_BASE_UNVERIFIED = 8
EXIT_V1_CAPITAL_BASE_CONFLICT = 9


# ---------------------------------------------------------------------------
# Real Bybit DEMO order transport (constructed ONLY under --send-orders-to-demo)
# ---------------------------------------------------------------------------


class RealDemoOrderTransport:
    """Real Bybit DEMO transport: signed POST create + signed GET reconcile.
    Demo host only; holds the Demo secret privately (never returned/printed)."""

    def __init__(self, *, api_key: str, api_secret: str, recv_window: str) -> None:
        self._poster = RealDemoHttpTransport(api_key=api_key, api_secret=api_secret,
                                             recv_window=recv_window)
        self._api_key = api_key
        self._api_secret = api_secret
        self._recv_window = recv_window
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def post_order_create(self, *, url: str, body: Mapping[str, Any]) -> dict[str, Any]:
        assert_demo_url(url)
        body_str = json.dumps(dict(body), separators=(",", ":"))
        headers = self._poster.signed_headers_for_post(body_str)
        return self._poster.post_order_create(url=url, headers=headers,
                                              body_bytes=body_str.encode("utf-8"))

    def _signed_get(self, path: str, params: Mapping[str, str]) -> dict[str, Any]:
        query = urllib.parse.urlencode(dict(params))
        ts = str(int(time.time() * 1000))
        sign_input = ts + self._api_key + self._recv_window + query
        sign = hmac.new(self._api_secret.encode("utf-8"), sign_input.encode("utf-8"),
                        hashlib.sha256).hexdigest()
        url = f"{DEMO_BASE_URL}{path}?{query}"
        assert_demo_url(url)
        req = urllib.request.Request(url, method="GET", headers={
            "X-BAPI-API-KEY": self._api_key, "X-BAPI-SIGN": sign,
            "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": self._recv_window})
        with self._opener.open(req, timeout=10) as resp:
            if host_of(resp.geturl()) != DEMO_HOST:
                raise RuntimeError("reconcile response host mismatch")
            return json.loads(resp.read().decode("utf-8"))

    def reconcile(self, *, order_link_id: str) -> dict[str, Any]:
        resp = self._signed_get(EP_ORDER_REALTIME,
                                {"category": "linear", "orderLinkId": order_link_id})
        if (resp.get("result") or {}).get("list"):
            return resp
        return self._signed_get(EP_ORDER_HISTORY,
                               {"category": "linear", "orderLinkId": order_link_id})


def _utc_iso(epoch: float) -> str:
    """Local UTC ISO-8601 timestamp for an epoch-seconds value. This is a LOCALLY
    generated request/response time, never an exchange/server timestamp."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(epoch))


def _canonical_network_top_level(*, review, planner_phase_audit, instrument_metadata_get_count):
    """ONE canonical complete-account network-audit schema for the top level. The
    top-level counters MIRROR ``strategy_native_review.network_audit`` EXACTLY. When the
    nested block is the complete-account CE audit (TASK-014CE), the top level mirrors all
    public/private GET counters and uses the canonical ``total_public_get_count`` /
    ``total_private_read_only_get_count`` (e.g. 105 / 3). When it is the older CD
    ticker-only audit, the top level falls back to ``instrument_metadata + ticker_http``.
    The pre-review planner-phase ticker counts are exposed under explicit
    ``planner_ticker_*`` names so no field carries two different meanings."""
    na = (review or {}).get("network_audit") or {}
    http = int(na.get("ticker_http_request_count", 0) or 0)
    # The complete-account CE audit is identifiable by its CE-only counters.
    is_complete_account = "server_time_public_get_count" in na
    total_public = (int(na.get("total_public_get_count", 0) or 0) if is_complete_account
                    else int(instrument_metadata_get_count or 0) + http)
    out = {
        # Canonical complete-account counters (mirror the nested network_audit).
        "ticker_http_request_count": http,
        "ticker_requested_symbol_count": int(na.get("ticker_requested_symbol_count", 0) or 0),
        "ticker_unique_symbol_count": int(na.get("ticker_unique_symbol_count", 0) or 0),
        "ticker_cache_hit_count": int(na.get("ticker_cache_hit_count", 0) or 0),
        "ticker_public_get_count": http,  # == HTTP requests (one GET per HTTP request)
        "total_priced_symbol_count": int(na.get("total_priced_symbol_count", 0) or 0),
        "network_audit_status": na.get("network_audit_status"),
        "total_public_get_count": total_public,
        # Planner-only INITIAL Strategy pricing phase (explicitly named; not canonical).
        "planner_ticker_http_request_count":
            int((planner_phase_audit or {}).get("ticker_http_request_count", 0) or 0),
        "planner_ticker_requested_symbol_count":
            int((planner_phase_audit or {}).get("ticker_requested_symbol_count", 0) or 0),
        "planner_ticker_unique_symbol_count":
            int((planner_phase_audit or {}).get("ticker_unique_symbol_count", 0) or 0),
        "planner_ticker_cache_hit_count":
            int((planner_phase_audit or {}).get("ticker_cache_hit_count", 0) or 0),
    }
    if is_complete_account:
        # Mirror the canonical complete-account public/private GET counters exactly.
        out.update({
            "instrument_metadata_public_get_count":
                int(na.get("instrument_metadata_public_get_count", 0) or 0),
            "server_time_public_get_count": int(na.get("server_time_public_get_count", 0) or 0),
            "risk_limit_public_get_count": int(na.get("risk_limit_public_get_count", 0) or 0),
            "risk_limit_page_count": int(na.get("risk_limit_page_count", 0) or 0),
            "account_info_private_read_only_get_count":
                int(na.get("account_info_private_read_only_get_count", 0) or 0),
            "wallet_private_read_only_get_count":
                int(na.get("wallet_private_read_only_get_count", 0) or 0),
            "positions_private_read_only_get_count":
                int(na.get("positions_private_read_only_get_count", 0) or 0),
            "total_private_read_only_get_count":
                int(na.get("total_private_read_only_get_count", 0) or 0),
        })
    return out


def _normalize_stop_price(value: Any) -> float:
    """Normalize a Demo position stop_price to the ``DemoOpenPosition.stop_price`` float contract.

    Bybit reports NO stop-loss as ``None`` (or occasionally an empty string). Those map to ``0.0``
    -- the canonical "missing stop" value, which the existing risk logic still treats as missing
    and fails closed on (``stop_price <= 0``). This NEVER relaxes a stop or fabricates a price:
    a non-empty but unparseable value is not silently accepted as a valid stop; ``float()`` raises
    (fail closed) rather than inventing one."""
    if value is None:
        return 0.0
    if isinstance(value, str):
        stripped = value.strip()
        if not stripped:
            return 0.0
        return float(stripped)
    return float(value)


def _build_production_provider(_client=None, _guard=None):
    """Build the canonical account/market provider from the existing read-only
    Demo client + market guard + instrument rules. Fails closed (returns None) if
    real reads are unavailable. Runs ONLY on the VPS under explicit authorization.

    Instrument metadata is fetched via the canonical DemoReadOnlyClient.get_instruments_info()
    public read-only GET (/v5/market/instruments-info, category=linear). The data is
    batch-loaded once per run and cached in _instruments. No API secret is required for
    this endpoint; pagination is handled by the client.

    Tests may inject fixture-mode ``_client`` / ``_guard`` for fully offline audits."""
    try:
        from src.demo_readonly_client import DemoReadOnlyClient
        from src.demo_market_price_guard import DemoMarketPriceGuard
        from src.demo_instrument_rules import InstrumentRules
        from src.demo_portfolio_risk import DemoOpenPosition
    except Exception:  # noqa: BLE001
        return None

    def _decimal_places(step: float) -> int:
        if step <= 0:
            return 0
        s = f"{step:.15g}"
        if "." not in s:
            return 0
        return len(s.rstrip("0").split(".")[1])

    class _RealDemoProvider:
        def __init__(self) -> None:
            self._client = _client if _client is not None else DemoReadOnlyClient(allow_real_network=True)
            self._guard = _guard if _guard is not None else DemoMarketPriceGuard(allow_real_network=True)
            # Private read-only GETs (wallet + positions): counted as they happen.
            # TASK-014CD_FIX1: capture each snapshot's request/response time so the
            # non-atomic skew between the two separate responses is provable, never
            # silently treated as a contradiction.
            # Wall-clock (UTC ISO, display) + monotonic (perf_counter, sub-ms) so the
            # measured separation is not collapsed to 0.0 by second-resolution strings.
            _ws, _wsm = time.time(), time.perf_counter()
            self._wallet = self._client.get_wallet_balance()
            _wr, _wrm = time.time(), time.perf_counter()
            self._wallet_get_count = 1
            _ps, _psm = time.time(), time.perf_counter()
            self._positions = self._client.get_open_positions()
            _pr, _prm = time.time(), time.perf_counter()
            self._positions_get_count = 1
            self._wallet_snapshot_started_at = _utc_iso(_ws)
            self._wallet_snapshot_received_at = _utc_iso(_wr)
            self._position_snapshot_started_at = _utc_iso(_ps)
            self._position_snapshot_received_at = _utc_iso(_pr)
            self._wallet_snapshot_received_epoch = _wr
            self._position_snapshot_received_epoch = _pr
            self._wallet_snapshot_received_monotonic = _wrm
            self._position_snapshot_received_monotonic = _prm
            # One public batch instrument-metadata GET (category=linear, paginated).
            self._raw_instruments = self._client.get_instruments_info()
            self._instrument_metadata_get_count = 1
            # TASK-014CE: authoritative account-mode evidence (one private read-only
            # GET /v5/account/info) + the BEFORE server-time bracket point (one public
            # GET /v5/market/time) captured immediately before any price collection.
            self._account_info = self._client.get_account_info()
            self._account_info_get_count = 1
            self._server_time_before = self._client.get_server_time()
            self._server_time_after = None
            self._server_time_get_count = 1
            # Risk-limit (margin-tier) evidence is fetched lazily per symbol (symbol-
            # specific GET; one HTTP request == one page, easiest to audit) and cached.
            self._risk_limit_cache: dict[str, list[dict[str, Any]]] = {}
            self._risk_limit_get_count = 0
            self._risk_limit_page_count = 0
            # Ticker GETs are counted lazily, once per distinct symbol (cached).
            self._price_cache: dict[str, float | None] = {}
            self._ticker_get_count = 0
            # TASK-014CD network-audit counters (request vs symbol vs cache) +
            # per-symbol price-observation evidence (local timestamps only).
            self._ticker_requested_count = 0      # total market_price() calls
            self._ticker_http_request_count = 0   # actual HTTP GETs (cache misses)
            self._ticker_cache_hit_count = 0      # repeated calls served from cache
            self._price_observation: dict[str, dict[str, Any]] = {}
            self._instruments: dict[str, InstrumentRules | None] = {}
            self._non_trading_count = 0
            self._malformed_count = 0
            for sym, snap in self._raw_instruments.items():
                if getattr(snap, "status", "Trading") != "Trading":
                    self._non_trading_count += 1
                    self._instruments[sym] = None
                    continue
                try:
                    rule = InstrumentRules(
                        symbol=sym,
                        qty_step=float(snap.qty_step),
                        min_qty=float(getattr(snap, "min_qty", 0)),
                        max_qty=float(getattr(snap, "max_qty", 0)),
                        tick_size=float(snap.tick_size),
                        min_notional=float(getattr(snap, "min_notional", 0)),
                        price_precision=_decimal_places(float(snap.tick_size)),
                        qty_precision=_decimal_places(float(snap.qty_step)),
                    )
                    ok, _ = rule.is_valid()
                    if not ok:
                        self._malformed_count += 1
                        self._instruments[sym] = None
                    else:
                        self._instruments[sym] = rule
                except (TypeError, ValueError):
                    self._malformed_count += 1
                    self._instruments[sym] = None

        def equity_usd(self) -> float:
            return float(self._wallet.equity_usd)

        def available_balance_usd(self) -> float:
            return float(self._wallet.available_balance_usd)

        def open_positions(self):
            # stop_price is normalized at this boundary: Bybit's missing stop (None / "") -> 0.0
            # (== missing stop, still fail-closed by the risk logic), never a fabricated price.
            return [DemoOpenPosition(symbol=p.symbol, side=p.side, quantity=float(p.quantity),
                                     entry_price=float(p.entry_price),
                                     stop_price=_normalize_stop_price(p.stop_price))
                    for p in self._positions]

        def account_risk_snapshot(self) -> dict:
            """Read-only account snapshot for portfolio feasibility. Per-position
            leverage may be reported, but the per-symbol INITIAL-MARGIN requirement
            (margin tiers) is NOT authoritatively readable from the read-only Demo
            metadata, so initial_margin_authoritative is False -> feasibility fails
            closed rather than assuming leverage."""
            return {
                "wallet_equity_usd": float(self._wallet.equity_usd),
                "available_balance_usd": float(self._wallet.available_balance_usd),
                "positions": [{"symbol": p.symbol, "side": p.side,
                               "quantity": float(p.quantity), "entry_price": float(p.entry_price),
                               "leverage": float(getattr(p, "leverage", 0) or 0)}
                              for p in self._positions],
                "leverage_authoritative": False,
                "initial_margin_authoritative": False,
            }

        def market_price(self, symbol: str):
            # Cache per distinct symbol so each ticker HTTP GET happens exactly once.
            self._ticker_requested_count += 1
            if symbol in self._price_cache:
                self._ticker_cache_hit_count += 1
                return self._price_cache[symbol]
            value: float | None = None
            req_start = time.time()
            try:
                prices = self._guard.fetch_market_prices([symbol])
                self._ticker_get_count += 1
                self._ticker_http_request_count += 1
                mp = prices.get(symbol)
                value = float(mp.realtime_market_price) if mp and mp.is_usable() else None
                # The guard's price_timestamp_utc is a LOCAL fetch time (NOT an
                # exchange/server timestamp); it is recorded as such here. No
                # authoritative exchange timestamp is surfaced by this path.
                local_ts = getattr(mp, "price_timestamp_utc", "") if mp else ""
            except Exception:  # noqa: BLE001
                value = None
                local_ts = ""
            resp_recv = time.time()
            self._price_observation[symbol] = {
                "price_source": "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
                "exchange_timestamp_ms": None,  # not surfaced by the read-only path
                "request_started_at_utc": _utc_iso(req_start),
                "response_received_at_utc": local_ts or _utc_iso(resp_recv),
                "response_received_epoch": resp_recv,
                "request_elapsed_ms": round((resp_recv - req_start) * 1000.0, 3),
            }
            self._price_cache[symbol] = value
            return value

        def price_observation(self, symbol: str) -> dict | None:
            return self._price_observation.get(symbol)

        def network_audit_counters(self) -> dict:
            priced = [s for s, v in self._price_cache.items() if v is not None]
            return {
                "ticker_http_request_count": self._ticker_http_request_count,
                "ticker_requested_symbol_count": self._ticker_requested_count,
                "ticker_unique_symbol_count": len(self._price_cache),
                "ticker_cache_hit_count": self._ticker_cache_hit_count,
                "priced_symbols": priced,
            }

        def margin_evidence(self) -> dict:
            """Authoritative read-only margin evidence from the already-fetched
            wallet + position responses. Absent fields stay None (never assumed)."""
            per = [{
                "symbol": p.symbol,
                "leverage": getattr(p, "leverage", None),
                "initial_margin": getattr(p, "initial_margin_usd", None),
                "maintenance_margin": getattr(p, "maintenance_margin_usd", None),
                "position_value": getattr(p, "position_value_usd", None),
                "mark_price": getattr(p, "mark_price", None),
                "liq_price": getattr(p, "liq_price", None),
            } for p in self._positions]
            return md.normalize_margin_evidence(
                margin_evidence_source=(
                    "DemoReadOnlyClient.get_wallet_balance() -> /v5/account/wallet-balance + "
                    "get_open_positions() -> /v5/position/list (private read-only GET)"),
                account_type=getattr(self._wallet, "account_type", None),
                # TASK-014CE: authoritative account marginMode from /v5/account/info
                # (now in the read-only allowlist). None when the response was absent.
                account_margin_mode=getattr(self._account_info, "margin_mode", None),
                wallet_equity=self._wallet.equity_usd,
                available_balance=self._wallet.available_balance_usd,
                total_initial_margin=getattr(self._wallet, "total_initial_margin_usd", None),
                total_maintenance_margin=getattr(self._wallet, "total_maintenance_margin_usd", None),
                account_initial_margin_rate=getattr(self._wallet, "account_im_rate", None),
                account_maintenance_margin_rate=getattr(self._wallet, "account_mm_rate", None),
                per_position=per,
                wallet_snapshot_request_started_at_utc=self._wallet_snapshot_started_at,
                wallet_snapshot_response_received_at_utc=self._wallet_snapshot_received_at,
                position_snapshot_request_started_at_utc=self._position_snapshot_started_at,
                position_snapshot_response_received_at_utc=self._position_snapshot_received_at,
                wallet_snapshot_response_received_monotonic=self._wallet_snapshot_received_monotonic,
                position_snapshot_response_received_monotonic=self._position_snapshot_received_monotonic,
                # Two separate HTTP responses -> never atomic; scope not proven.
                margin_snapshot_atomic=False, scope_proven_comparable=False)

        def account_mode_evidence(self) -> dict:
            """TASK-014CE: authoritative read-only account-mode evidence from the
            already-fetched /v5/account/info response. Absent fields stay None."""
            ai = self._account_info
            return ce.normalize_account_mode_evidence(
                margin_mode=getattr(ai, "margin_mode", None),
                unified_margin_status=getattr(ai, "unified_margin_status", None),
                updated_time=getattr(ai, "updated_time", None),
                is_master_trader=getattr(ai, "is_master_trader", None),
                spot_hedging_status=getattr(ai, "spot_hedging_status", None),
                request_started_at_utc=getattr(ai, "request_started_at_utc", None),
                response_received_at_utc=getattr(ai, "response_received_at_utc", None),
                request_elapsed_ms=getattr(ai, "request_elapsed_ms", None),
                response_envelope_time=getattr(ai, "response_envelope_time", None),
                response_present=getattr(ai, "response_present", False))

        def risk_limit_tiers(self, symbol: str) -> list[dict]:
            """TASK-014CE: authoritative public risk-limit tiers for one symbol
            (symbol-specific GET /v5/market/risk-limit, cached). One HTTP GET == one
            page for a symbol-specific lookup (easiest to audit)."""
            if symbol in self._risk_limit_cache:
                return self._risk_limit_cache[symbol]
            raw = self._client.get_risk_limit(symbol=symbol, category="linear")
            self._risk_limit_page_count += int(raw.pop("__page_count__", 1) or 1)
            self._risk_limit_get_count += int(raw.pop("__get_count__", 1) or 1)
            tiers = raw.get(symbol, [])
            self._risk_limit_cache[symbol] = tiers
            return tiers

        def exchange_clock_evidence(self, **window) -> dict:
            """TASK-014CE: capture the AFTER server-time bracket point now and build the
            exchange-clock evidence bracketing the price-collection window. The Bybit
            server time is NEVER labelled a per-symbol quote timestamp."""
            after = self._client.get_server_time()
            self._server_time_after = after
            self._server_time_get_count += 1
            before = self._server_time_before
            return ce.build_exchange_clock_evidence(
                before_time_second=getattr(before, "time_second", None),
                before_time_nano=getattr(before, "time_nano", None),
                before_local_request_started_at_utc=getattr(before, "request_started_at_utc", None),
                before_local_response_received_at_utc=getattr(before, "response_received_at_utc", None),
                before_local_monotonic_start=getattr(before, "request_started_monotonic", None),
                before_local_monotonic_end=getattr(before, "response_received_monotonic", None),
                before_response_envelope_time=getattr(before, "response_envelope_time", None),
                after_time_second=getattr(after, "time_second", None),
                after_time_nano=getattr(after, "time_nano", None),
                after_local_request_started_at_utc=getattr(after, "request_started_at_utc", None),
                after_local_response_received_at_utc=getattr(after, "response_received_at_utc", None),
                after_local_monotonic_start=getattr(after, "request_started_monotonic", None),
                after_local_monotonic_end=getattr(after, "response_received_monotonic", None),
                after_response_envelope_time=getattr(after, "response_envelope_time", None),
                # High-resolution local epochs for an auditable clock-offset estimate.
                before_local_request_epoch=getattr(before, "request_started_epoch", None),
                before_local_response_epoch=getattr(before, "response_received_epoch", None),
                after_local_request_epoch=getattr(after, "request_started_epoch", None),
                after_local_response_epoch=getattr(after, "response_received_epoch", None),
                **window)

        def account_network_counters(self) -> dict:
            """TASK-014CE: the new private/public read-only GET counters."""
            return {
                "account_info_private_read_only_get_count": self._account_info_get_count,
                "server_time_public_get_count": self._server_time_get_count,
                "risk_limit_public_get_count": self._risk_limit_get_count,
                "risk_limit_page_count": self._risk_limit_page_count,
            }

        def instrument_rule(self, symbol: str):
            return self._instruments.get(symbol)

        def instrument_rule_evidence(self, symbol: str) -> dict:
            """AUTHORITATIVE instrument-rule evidence for one symbol, derived ONLY
            from the real InstrumentRules snapshot (never inferred from any
            quantity string). qty_step / min_qty / max_qty / min_notional /
            tick_size come from the validated rule; status comes from the raw
            catalog snapshot."""
            snap = self._raw_instruments.get(symbol)
            rule = self._instruments.get(symbol)
            if snap is None:
                status = "MISSING"
            elif getattr(snap, "status", "Trading") != "Trading":
                status = "NON_TRADING"
            elif rule is None:
                status = "MALFORMED"
            else:
                status = "TRADING"
            ev = {
                "symbol": symbol, "rule_status": status,
                "instrument_rule_source":
                    "DemoReadOnlyClient.get_instruments_info() -> /v5/market/instruments-info (public GET, category=linear)",
                "market_price_source": "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
                "market_price": self.market_price(symbol),
            }
            if rule is not None:
                ev.update({
                    "qty_step": float(rule.qty_step), "min_qty": float(rule.min_qty),
                    "max_qty": float(rule.max_qty), "min_notional": float(rule.min_notional),
                    "tick_size": float(rule.tick_size),
                })
            return ev

        def match_targets(self, symbols) -> dict:
            """Classify the REQUESTED target symbols against the cached catalog.

            Distinct from the full catalog cache count: this reports how many of
            the actual lookup targets had valid / missing / non-Trading /
            malformed instrument rules."""
            requested = list(dict.fromkeys(s for s in symbols if s))
            matched = missing = non_trading = malformed = 0
            for s in requested:
                snap = self._raw_instruments.get(s)
                if snap is None:
                    missing += 1
                elif getattr(snap, "status", "Trading") != "Trading":
                    non_trading += 1
                elif self._instruments.get(s) is None:
                    malformed += 1
                else:
                    matched += 1
            return {
                "requested_target_symbol_count": len(requested),
                "matched_instrument_rule_count": matched,
                "missing_instrument_rule_count": missing,
                "non_trading_instrument_count": non_trading,
                "malformed_instrument_rule_count": malformed,
            }

        def audit(self) -> dict:
            valid_count = sum(1 for v in self._instruments.values() if v is not None)
            total_public = self._instrument_metadata_get_count + self._ticker_get_count
            total_private = self._wallet_get_count + self._positions_get_count
            return {
                "instrument_rule_source": "DemoReadOnlyClient.get_instruments_info() -> /v5/market/instruments-info (public GET, category=linear)",
                "market_price_source": "DemoMarketPriceGuard -> /v5/market/tickers (public GET, one per distinct symbol)",
                # Full catalog/cache count (separate from requested-target matches).
                "instrument_rule_cache_count": len(self._raw_instruments),
                "valid_instrument_rule_cache_count": valid_count,
                "catalog_non_trading_instrument_count": self._non_trading_count,
                "catalog_malformed_instrument_rule_count": self._malformed_count,
                # Real network accounting (actual calls, not expected).
                "instrument_metadata_public_get_count": self._instrument_metadata_get_count,
                "ticker_public_get_count": self._ticker_get_count,
                # TASK-014CD: request count is distinct from symbol/cache counts.
                "ticker_http_request_count": self._ticker_http_request_count,
                "ticker_requested_symbol_count": self._ticker_requested_count,
                "ticker_unique_symbol_count": len(self._price_cache),
                "ticker_cache_hit_count": self._ticker_cache_hit_count,
                "total_public_get_count": total_public,
                "wallet_private_read_only_get_count": self._wallet_get_count,
                "positions_private_read_only_get_count": self._positions_get_count,
                "total_private_read_only_get_count": total_private,
                "order_post_count": 0,
                "amend_post_count": 0,
                "cancel_post_count": 0,
                "live_endpoint_called": False,
            }

    try:
        return _RealDemoProvider()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Testable orchestrator (planner -> execution -> reporting -> advancement)
# ---------------------------------------------------------------------------


def _forward_fingerprint_of(plan: Any) -> str | None:
    """Best-effort forward/state artifact fingerprint from the planner evidence."""
    sv = getattr(plan, "sizing_verification", {}) or {}
    return (sv.get("evidence_bundle_fingerprint")
            or sv.get("state_artifact_fingerprint")
            or sv.get("config_source_fingerprint"))


def build_active_v1_review(*, provider: Any, plan: Any, pilot_id: str, date: str) -> dict[str, Any]:
    """Assemble the ACTIVE Strategy-native V1 portfolio review (Plan-only,
    non-dispatching) from the read-only provider + planner. Authoritative
    instrument-rule evidence and the account-risk snapshot come from the provider;
    nothing is inferred and nothing is sent."""
    try:
        open_positions = list(provider.open_positions()) if provider is not None else []
    except Exception:  # noqa: BLE001
        open_positions = []

    acct = provider.account_risk_snapshot() if hasattr(provider, "account_risk_snapshot") else {}
    wallet_equity = acct.get("wallet_equity_usd",
                             provider.equity_usd() if hasattr(provider, "equity_usd") else 0.0)
    available_balance = acct.get("available_balance_usd",
                                 provider.available_balance_usd()
                                 if hasattr(provider, "available_balance_usd") else 0.0)

    rule_evidence_by_symbol: dict[str, Any] = {}
    price_by_symbol: dict[str, Any] = {}
    for tp in getattr(plan, "target_positions", []) or []:
        sym = str(tp.get("symbol", "")).strip().upper()
        if not sym:
            continue
        if hasattr(provider, "instrument_rule_evidence"):
            try:
                rule_evidence_by_symbol[sym] = provider.instrument_rule_evidence(sym)
            except Exception:  # noqa: BLE001
                pass
        try:
            price_by_symbol[sym] = provider.market_price(sym)
        except Exception:  # noqa: BLE001
            pass

    # Legacy protected positions are valued at CURRENT MARK price (never entry price).
    # Fetch each legacy symbol's public ticker via the same market-price path. A
    # missing mark fails closed in the review (no fallback to entry price).
    legacy_mark_price_by_symbol: dict[str, Any] = {}
    legacy_symbols: list[str] = []
    for p in open_positions:
        sym = str(getattr(p, "symbol", "")).strip().upper()
        if sym and sym in v1.PROTECTED_SYMBOLS and sym not in legacy_mark_price_by_symbol:
            legacy_symbols.append(sym)
            try:
                legacy_mark_price_by_symbol[sym] = provider.market_price(sym)
            except Exception:  # noqa: BLE001
                legacy_mark_price_by_symbol[sym] = None

    # --- TASK-014CD authoritative margin evidence -----------------------------
    margin_evidence = provider.margin_evidence() if hasattr(provider, "margin_evidence") else None

    # --- TASK-014CD price-observation / freshness evidence (batch-built now) ---
    batch_built_at = time.time()
    freshness_snaps: list[dict[str, Any]] = []
    if hasattr(provider, "price_observation"):
        priced_syms = list(dict.fromkeys(list(price_by_symbol.keys()) + legacy_symbols))
        for sym in priced_syms:
            obs = provider.price_observation(sym) or {}
            price_val = price_by_symbol.get(sym, legacy_mark_price_by_symbol.get(sym))
            freshness_snaps.append(md.build_price_freshness_snapshot(
                symbol=sym, price=price_val,
                price_source=obs.get("price_source",
                                     "DemoMarketPriceGuard -> /v5/market/tickers (public GET)"),
                exchange_timestamp_ms=obs.get("exchange_timestamp_ms"),
                request_started_at_utc=obs.get("request_started_at_utc"),
                response_received_at_utc=obs.get("response_received_at_utc"),
                request_elapsed_ms=obs.get("request_elapsed_ms"),
                batch_built_at_utc=batch_built_at))
    price_freshness_evidence = md.build_price_freshness_evidence(freshness_snaps) \
        if freshness_snaps else None

    # --- TASK-014CD ticker-only network-audit (planner/ticker price phase) -----
    # Retained under the explicitly scoped name ticker_price_network_audit; it is NOT
    # the canonical network_audit (TASK-014CE_FIX1).
    ticker_price_network_audit = None
    strat_priced = legacy_priced = 0
    if hasattr(provider, "network_audit_counters"):
        ctr = provider.network_audit_counters()
        strat_priced = sum(1 for s in price_by_symbol if price_by_symbol.get(s) is not None)
        legacy_priced = sum(1 for s in legacy_symbols
                            if legacy_mark_price_by_symbol.get(s) is not None)
        ticker_price_network_audit = md.build_network_audit(
            ticker_http_request_count=ctr["ticker_http_request_count"],
            ticker_requested_symbol_count=ctr["ticker_requested_symbol_count"],
            ticker_unique_symbol_count=ctr["ticker_unique_symbol_count"],
            ticker_cache_hit_count=ctr["ticker_cache_hit_count"],
            strategy_target_priced_symbol_count=strat_priced,
            legacy_mark_priced_symbol_count=legacy_priced)

    # --- TASK-014CE authoritative account-mode / risk-tier / exchange-clock ----
    # Account margin mode from /v5/account/info (read-only). Per-action margin tiers
    # from /v5/market/risk-limit selected fail-closed on COMBINED projected exposure.
    account_mode_evidence = (provider.account_mode_evidence()
                             if hasattr(provider, "account_mode_evidence") else None)
    margin_mode = (account_mode_evidence or {}).get("margin_mode")

    # Existing same-symbol notional from strategy-managed (non-protected) positions.
    managed_same_symbol_notional: dict[str, float] = {}
    for p in open_positions:
        sym = str(getattr(p, "symbol", "")).strip().upper()
        if sym and sym not in v1.PROTECTED_SYMBOLS:
            try:
                managed_same_symbol_notional[sym] = abs(float(getattr(p, "quantity", 0) or 0)
                                                         * float(getattr(p, "entry_price", 0) or 0))
            except (TypeError, ValueError):
                pass

    per_action_projections: list[dict[str, Any]] = []
    risk_tier_status_counts: dict[str, int] = {}
    if hasattr(provider, "risk_limit_tiers"):
        for tp in getattr(plan, "target_positions", []) or []:
            sym = str(tp.get("symbol", "")).strip().upper()
            if not sym:
                continue
            try:
                tiers = provider.risk_limit_tiers(sym)
            except Exception:  # noqa: BLE001
                tiers = []
            proj = ce.project_action_margin(
                symbol=sym,
                projected_symbol_notional_usdt=abs(float(tp.get("target_notional", 0) or 0)),
                existing_same_symbol_notional_usdt=managed_same_symbol_notional.get(sym, 0),
                tiers=tiers, margin_mode=margin_mode)
            per_action_projections.append(proj)
            st = proj["risk_tier_selection_status"]
            risk_tier_status_counts[st] = risk_tier_status_counts.get(st, 0) + 1

    account_margin_model = ce.build_account_margin_model(
        account_mode_evidence=account_mode_evidence or ce.unavailable_account_mode_evidence(),
        per_action_projections=per_action_projections,
        observed_legacy_position_initial_margin_sum_usdt=(
            (margin_evidence or {}).get("observed_legacy_position_initial_margin_sum_usdt")),
        available_balance=available_balance) if per_action_projections or account_mode_evidence else None

    risk_limit_evidence = ({
        "source_endpoint": ce.EP_RISK_LIMIT,
        "environment": "bybit_demo",
        "margin_mode": margin_mode,
        "symbol_count": len(per_action_projections),
        "risk_tier_selection_status_counts": risk_tier_status_counts,
        "per_action_projections": per_action_projections,
    } if per_action_projections else None)

    # Exchange-clock evidence bracketing the (already completed) price collection.
    exchange_clock_evidence = None
    if hasattr(provider, "exchange_clock_evidence"):
        snaps_sorted = sorted(freshness_snaps, key=lambda s: str(s.get("symbol")))
        first = snaps_sorted[0] if snaps_sorted else {}
        last = snaps_sorted[-1] if snaps_sorted else {}
        exchange_clock_evidence = provider.exchange_clock_evidence(
            collection_window_started_at_utc=getattr(
                getattr(provider, "_server_time_before", None), "response_received_at_utc", None),
            collection_window_ended_at_utc=_utc_iso(batch_built_at),
            first_ticker_symbol=first.get("symbol"),
            first_ticker_observed_at_utc=first.get("local_observed_at_utc"),
            last_ticker_symbol=last.get("symbol"),
            last_ticker_observed_at_utc=last.get("local_observed_at_utc"))

    # ONE canonical complete-account network audit (distinct counter semantics). When
    # CE counters are available this becomes the canonical network_audit (total public =
    # instrument + ticker_http + server_time + risk_limit; total private = account_info +
    # wallet + positions). Otherwise the canonical block falls back to the ticker-only CD
    # audit (back-compatible).
    account_network_audit = None
    if hasattr(provider, "account_network_counters") and ticker_price_network_audit is not None:
        acct_ctr = provider.account_network_counters()
        prov_aud = provider.audit() if hasattr(provider, "audit") else {}
        account_network_audit = ce.build_account_network_audit(
            instrument_metadata_public_get_count=prov_aud.get("instrument_metadata_public_get_count", 0),
            ticker_http_request_count=ticker_price_network_audit["ticker_http_request_count"],
            ticker_requested_symbol_count=ticker_price_network_audit["ticker_requested_symbol_count"],
            ticker_unique_symbol_count=ticker_price_network_audit["ticker_unique_symbol_count"],
            ticker_cache_hit_count=ticker_price_network_audit["ticker_cache_hit_count"],
            server_time_public_get_count=acct_ctr["server_time_public_get_count"],
            risk_limit_public_get_count=acct_ctr["risk_limit_public_get_count"],
            risk_limit_page_count=acct_ctr["risk_limit_page_count"],
            account_info_private_read_only_get_count=acct_ctr["account_info_private_read_only_get_count"],
            wallet_private_read_only_get_count=prov_aud.get("wallet_private_read_only_get_count", 0),
            positions_private_read_only_get_count=prov_aud.get("positions_private_read_only_get_count", 0),
            strategy_target_priced_symbol_count=strat_priced,
            legacy_mark_priced_symbol_count=legacy_priced)

    # Canonical network_audit = complete-account CE block when present, else CD ticker.
    canonical_network_audit = (account_network_audit if account_network_audit is not None
                               else ticker_price_network_audit)

    return v1.build_strategy_native_review(
        plan=plan, open_positions=open_positions, pilot_id=pilot_id, run_date=date,
        artifact_fingerprint=_forward_fingerprint_of(plan),
        wallet_equity=wallet_equity, available_balance=available_balance,
        rule_evidence_by_symbol=rule_evidence_by_symbol, price_by_symbol=price_by_symbol,
        leverage_authoritative=bool(acct.get("leverage_authoritative", False)),
        initial_margin_authoritative=bool(acct.get("initial_margin_authoritative", False)),
        assumed_leverage=acct.get("assumed_leverage"),
        legacy_mark_price_by_symbol=legacy_mark_price_by_symbol,
        legacy_mark_price_source="DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
        # The read-only Demo market-price path does not surface an authoritative
        # exchange observation time, so price-freshness evidence is PARTIAL/UNAVAILABLE
        # and account-risk fails closed (no invented timestamp/freshness).
        price_freshness_status=v1.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE,
        margin_evidence=margin_evidence,
        price_freshness_evidence=price_freshness_evidence,
        network_audit=canonical_network_audit,
        account_mode_evidence=account_mode_evidence,
        risk_limit_evidence=risk_limit_evidence,
        exchange_clock_evidence=exchange_clock_evidence,
        account_margin_model=account_margin_model,
        account_network_audit=account_network_audit,
        ticker_price_network_audit=ticker_price_network_audit)


def orchestrate_gated_send(
    *,
    pilot_id: str,
    date: str,
    forward_result: Any,
    provider: Any,
    transport: Any = None,
    output_root: str | None = None,
    base_url: str = DEMO_BASE_URL,
    advance_on_success: bool = False,
    allow_notion_network: bool = False,
    allow_discord_network: bool = False,
    workbook_builder: Any = None,
    plan: Any = None,
) -> dict[str, Any]:
    """NON-dispatching native send surface. TASK-014CB_FIX.

    This NEVER dispatches an order and NEVER calls :func:`orchestrate_native_daily`
    or ``execute_daily_native``. It produces the full Plan-only execution review
    and then FAILS CLOSED with ``EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER``:
    real Demo execution is delegated to the existing, authoritative canonical
    one-shot tiny adapter chain (separate human review). No generic
    ``StrategyNativeAction`` is ever converted into an order payload here; the
    injected transport is intentionally never touched.
    """
    if plan is None:
        plan = planner.plan_strategy_native_actions(forward_result=forward_result, provider=provider)

    try:
        open_positions = list(provider.open_positions()) if provider is not None else []
    except Exception:  # noqa: BLE001
        open_positions = []

    gate_result = gate.evaluate_execution_gate(
        plan=plan, open_positions=open_positions, pilot_id=pilot_id, date=date,
        forward_fingerprint=_forward_fingerprint_of(plan), rule_provider=provider)

    # The native daily surface ALWAYS delegates real execution to the canonical
    # one-shot adapter. Zero dispatch, zero transport call, zero POST.
    return {
        "status": gate.EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER,
        "pilot_id": pilot_id, "date": date,
        "planner": plan.to_dict(),
        "execution_gate": gate_result.to_dict(),
        "plan_valid": gate_result.plan_valid,
        "execution_authorized": False,
        "execution_ready": False,
        "sender_reachable": False,
        "canonical_one_shot_adapter_required": True,
        "canonical_execution_packet_present": False,
        "send_path_refused": True,
        "native_dispatch_disabled": True,
        # Dispatcher call counts come from the non-dispatching architecture itself
        # (this function NEVER calls execute_daily_native or a transport), not from
        # any post-attempt inference.
        "execute_daily_native_called": False,
        "execute_daily_native_call_count": 0,
        "transport_sender_call_count": 0,
        "order_endpoint_called": False,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_endpoint_called": False,
        "live_trading_authorized": False,
        "pilot_advanced": False,
        "detail": ("native daily send is NOT a real execution dispatcher; the full V1 plan is "
                   "planning output only. Real Demo execution is delegated to the existing canonical "
                   "one-shot tiny adapter (SOLUSDT-locked, Market/IOC, single-shot, explicit Rick "
                   "authorization marker, Demo-only endpoint guard). No order dispatched."),
    }


def orchestrate_native_daily(
    *,
    pilot_id: str,
    date: str,
    forward_result: Any,
    provider: Any,
    transport: Any,
    output_root: str | None = None,
    base_url: str = DEMO_BASE_URL,
    finalize_reporting: bool = True,
    advance_on_success: bool = True,
    allow_notion_network: bool = False,
    allow_discord_network: bool = False,
    notion_sync: Any = None,
    discord_notify: Any = None,
    workbook_builder: Any = None,
    plan: Any = None,
) -> dict[str, Any]:
    """LOW-LEVEL execution mechanism. NOT the send path.

    This executes whatever actions it is given and is exercised directly only by
    mechanism tests. Production send MUST go through :func:`orchestrate_gated_send`,
    which guarantees at most one gate-authorized tiny action ever reaches here.

    Plan -> execute -> (on unambiguous) finalize reporting -> advance once.
    Advancement happens AT MOST once and only after the day is unambiguous AND
    Excel built OK. Refuses to execute unless V1 baseline sizing is verified."""
    if plan is None:
        plan = planner.plan_strategy_native_actions(forward_result=forward_result, provider=provider)
    # Fail closed: never execute while V1 baseline sizing or capital base is unproven.
    _refuse_statuses = (planner.STATUS_V1_BASELINE_SIZING_UNVERIFIED,
                        planner.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED,
                        planner.STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT)
    if not plan.available or not plan.sizing_verification.get("verified", False):
        return {"status": plan.status, "pilot_id": pilot_id, "date": date,
                "detail": plan.detail, "planner": plan.to_dict(),
                "send_refused": plan.status in _refuse_statuses,
                "live_trading_authorized": False}

    result = nx.execute_daily_native(pilot_id=pilot_id, date=date, actions=plan.actions,
                                     transport=transport, output_root=output_root, base_url=base_url)
    out = result.to_dict()
    out["planner"] = plan.to_dict()
    out["live_trading_authorized"] = False

    if result.day_verdict == nx.DAY_SUCCESS and finalize_reporting:
        rep = nrep.finalize_native_day(
            pilot_id=pilot_id, date=date, exec_result=out, output_root=output_root,
            allow_notion_network=allow_notion_network, allow_discord_network=allow_discord_network,
            notion_sync=notion_sync, discord_notify=discord_notify, workbook_builder=workbook_builder)
        out["reporting"] = rep
        if advance_on_success and rep.get("reporting_ok"):
            out["advancement"] = nx.advance_successful_day(
                pilot_id=pilot_id, date=date, day_verdict=result.day_verdict, output_root=output_root)
    return out


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _is_test_root(value: str | None) -> bool:
    if not value:
        return False
    low = value.replace("\\", "/").lower()
    return any(m in low for m in ("tmp", "temp", "pytest", "/t/", "test"))


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_demo_strategy_pilot_native_daily.py",
                                description="Strategy-native daily Bybit Demo execution "
                                            "(derives actions from the canonical source/planner).")
    p.add_argument("--pilot-id", required=True)
    p.add_argument("--date", required=True, help="Pilot run date YYYY-MM-DD")
    p.add_argument("--send-orders-to-demo", action="store_true",
                   help="produce the Plan-only execution review then FAIL CLOSED: the native surface "
                        "never dispatches; real Demo execution is delegated to the canonical one-shot adapter")
    p.add_argument("--reconcile-outputs-only", action="store_true",
                   help="retry Excel/Notion/Discord only; never plans or executes")
    p.add_argument("--advance-on-success", action="store_true",
                   help="advance the successful-day counter when the date is clean and Excel builds")
    p.add_argument("--allow-notion-network", action="store_true")
    p.add_argument("--allow-discord-network", action="store_true")
    p.add_argument("--test-output-root", default=None, help="TEST-ONLY output root")
    p.add_argument("--test-forward-source-root", default=None, help="TEST-ONLY forward source root")
    p.add_argument("--test-injected-actions-json", default=None,
                   help="TEST-ONLY injected action fixture; REFUSED in normal production mode")
    p.add_argument("--json-only", action="store_true")
    # TASK-014CH2: explicit opt-in, terminal Plan-only WebSocket-bound path. Reads a
    # caller-supplied public-WS evidence JSON (NO live WS collection), binds the REST
    # seed Plan, validates via the CH1 consumer, and writes exactly one canonical
    # WS-bound Plan wrapper. Stops before review / readiness / gate / execution.
    p.add_argument("--ws-bound-plan-only", action="store_true",
                   help="opt-in terminal Plan-only WebSocket-bound mode (no execution, no Pilot change)")
    p.add_argument("--ws-ticker-evidence-json", default=None,
                   help="path to the caller-supplied public-WS ticker evidence JSON (required for "
                        "--ws-bound-plan-only); no live WebSocket collection is performed")
    p.add_argument("--ws-bound-plan-output-json", default=None,
                   help="output path for the single canonical WS-bound Plan wrapper artifact "
                        "(required for --ws-bound-plan-only)")
    p.add_argument("--ws-binding-epoch-ns", type=int, default=None,
                   help="explicit binding epoch (ns) for deterministic runs; computed once if omitted")
    p.add_argument("--ws-binding-freshness-threshold-ms", type=int,
                   default=wsbpo.DEFAULT_FRESHNESS_THRESHOLD_MS,
                   help="strict binding-time freshness threshold (ms); defaults to and may not exceed "
                        "the producer strict maximum")
    # TASK-014CH3B2: explicit opt-in, terminal review-ONLY mode. Reviews an existing CH2
    # wrapper against an externally-preserved trusted anchor manifest + the original
    # source-WS evidence, and writes one race-safe review envelope. Historical binding-time
    # review only; no execution/readiness/gate/native-execution/Pilot/reporting/REST.
    p.add_argument("--ws-bound-plan-review-only", action="store_true",
                   help="opt-in terminal review-only mode (no execution, no Pilot change, no network)")
    p.add_argument("--ws-bound-plan-anchor-manifest-json", default=None,
                   help="path to the trusted external anchor-manifest JSON (required for review-only)")
    p.add_argument("--ws-bound-plan-anchor-manifest-sha256", default=None,
                   help="REQUIRED caller-owned expected anchor-manifest SHA256 (sha256:<64hex>); "
                        "never computed by the CLI from the manifest")
    p.add_argument("--ws-bound-plan-wrapper-json", default=None,
                   help="path to the existing CH2 wrapper JSON to review (required for review-only)")
    p.add_argument("--ws-bound-plan-review-output-json", default=None,
                   help="output path for the single review envelope (required for review-only)")
    # TASK-014: terminal, explicitly NON-SENDING dry-run preparation of the 50-order batch
    # from the three CH4A current-feasibility artifacts. No transport, no execution, no Pilot.
    p.add_argument("--prepare-from-current-feasibility-artifacts", dest="prepare_from_ch4a",
                   action="store_true",
                   help="opt-in terminal dry-run: build the 50 order payload previews from CH4A "
                        "artifacts (NO order is sent; no Pilot change; no network)")
    p.add_argument("--current-feasibility-review-json", default=None,
                   help="path to CH4A current_feasibility_review.json (prepare mode)")
    p.add_argument("--current-market-evidence-json", default=None,
                   help="path to CH4A current_market_evidence.json (prepare mode)")
    p.add_argument("--demo-account-evidence-json", default=None,
                   help="path to CH4A demo_account_evidence.json (prepare mode)")
    p.add_argument("--prepare-output-json", default=None,
                   help="optional no-clobber path to write the full 50-payload preview (prepare mode)")
    # TASK-014: explicit, execution-capable batch mode (separate from the non-sending prepare
    # mode). Real dispatch additionally requires --send-orders-to-demo + a date+payload-bound
    # manual authorization token + Demo credentials + Demo host. Reuses execute_daily_native().
    p.add_argument("--execute-prepared-demo-batch", dest="execute_prepared_demo_batch",
                   action="store_true",
                   help="opt-in EXECUTION-CAPABLE mode: dispatch the IMMUTABLE 50 payloads from "
                        "--prepared-batch-json (only with --send-orders-to-demo + matching token + "
                        "Demo credentials) via the existing execute_daily_native engine, after a "
                        "fresh CH4A re-validates those exact fixed payloads against current evidence")
    p.add_argument("--prepared-batch-json", dest="prepared_batch_json", default=None,
                   help="(execute mode) path to the IMMUTABLE prepared-batch artifact written by "
                        "--prepare-from-current-feasibility-artifacts; its exact 50 order bodies are "
                        "dispatched (fresh market prices NEVER regenerate the authorized quantities)")
    p.add_argument("--batch-authorization-token", dest="batch_authorization_token", default=None,
                   help="exact date+payload-bound manual authorization token "
                        "(CONFIRM_DEMO_NATIVE_BATCH_<YYYYMMDD>_<fingerprint16>) bound to the "
                        "immutable prepared-batch fingerprint")
    # CH4A trusted-anchor inputs forwarded VERBATIM to the existing current-feasibility runner,
    # which the execution mode invokes fresh (--allow-real-network) into the no-clobber
    # preflight dir below. These are NOT consumed directly; only CH4A's fresh outputs are read.
    p.add_argument("--review-artifact-json", dest="review_artifact_json", default=None,
                   help="(execute mode) CH4A trusted review-artifact JSON path")
    p.add_argument("--review-artifact-sha256", dest="review_artifact_sha256", default=None,
                   help="(execute mode) expected review-artifact sha256")
    p.add_argument("--anchor-manifest-json", dest="anchor_manifest_json", default=None,
                   help="(execute mode) CH4A trusted anchor-manifest JSON path")
    p.add_argument("--anchor-manifest-sha256", dest="anchor_manifest_sha256", default=None,
                   help="(execute mode) expected anchor-manifest sha256")
    p.add_argument("--wrapper-json", dest="wrapper_json", default=None,
                   help="(execute mode) CH4A trusted wrapper JSON path")
    p.add_argument("--strategy-symbols-json", dest="strategy_symbols_json", default=None,
                   help="(execute mode) CH4A trusted strategy-symbols JSON path")
    p.add_argument("--strategy-symbols-sha256", dest="strategy_symbols_sha256", default=None,
                   help="(execute mode) expected strategy-symbols sha256")
    p.add_argument("--ch4a-preflight-dir", dest="ch4a_preflight_dir", default=None,
                   help="(execute mode) NEW no-clobber directory for the fresh CH4A outputs")
    return p


def _build_ws_seed_plan_mapping(date: str, plan: Any) -> dict[str, Any]:
    """Build the REST seed Plan Mapping the WS binder expects, from the canonical
    planner result. The REST plan is ONLY a binding seed -- never a fallback Plan."""
    return {
        "date": date,
        "active_policy": wsbpo.EXPECTED_POLICY_ID,
        "strategy_native_review": {"active_strategy": wsbpo.EXPECTED_STRATEGY_ID},
        "planner": plan.to_dict(),
    }


def _run_ws_bound_plan_review_only(args: Any) -> int:
    """TASK-014CH3B2 terminal review-ONLY path. Reviews an existing CH2 wrapper against a
    trusted external anchor manifest + the original source-WS evidence and writes one
    race-safe review envelope. No execution / readiness / gate / native execution /
    sender / Pilot mutation / reconcile / Notion / Discord / REST. Reads NO Pilot state
    despite --pilot-id being syntactically present."""
    REVIEW_INPUT_READ_FAILED = "WS_BOUND_PLAN_REVIEW_INPUT_READ_FAILED"
    REVIEW_OUTPUT_EXISTS = "WS_BOUND_PLAN_REVIEW_OUTPUT_EXISTS"
    REVIEW_OUTPUT_FAILED = "WS_BOUND_PLAN_REVIEW_OUTPUT_FAILED"
    _CANON_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")

    def _summary(status: str, *, detail: str, exit_code: int,
                 result: Any = None, written: bool = False) -> int:
        out = {
            "status": status, "mode": "WS_BOUND_PLAN_REVIEW_ONLY", "detail": detail,
            "pilot_id": args.pilot_id, "date": args.date,
            "anchor_manifest_json": args.ws_bound_plan_anchor_manifest_json,
            "wrapper_json": args.ws_bound_plan_wrapper_json,
            "ws_ticker_evidence_json": args.ws_ticker_evidence_json,
            "review_output_json": args.ws_bound_plan_review_output_json,
            "review_artifact_written": written,
            # Terminal, never executable; no side effects.
            "execution_readiness": False, "readiness_called": False,
            "execution_gate_called": False, "native_execution_called": False,
            "pilot_advanced": False, "sender_reachable": False,
            "order_post_count": 0, "amend_post_count": 0, "cancel_post_count": 0,
            "live_order_post_count": 0, "notion_called": False, "discord_called": False,
            "live_trading_authorized": False, "rest_fallback_used": False,
        }
        if result is not None:
            env = result.review_artifact or {}
            totals = env.get("offline_exposure_totals", {}) if isinstance(env, dict) else {}
            out.update({
                "blockers": list(result.blockers),
                "anchor_manifest_sha256": result.anchor_manifest_sha256,
                "anchor_manifest_fingerprint": result.anchor_manifest_fingerprint,
                "wrapper_file_sha256": result.wrapper_file_sha256,
                "wrapper_logical_fingerprint": result.wrapper_logical_fingerprint,
                "canonical_bound_plan_fingerprint": result.canonical_bound_plan_fingerprint,
                "source_ws_file_sha256": result.source_ws_file_sha256,
                "source_ws_logical_fingerprint": result.source_ws_logical_fingerprint,
                "original_plan_fingerprint": result.original_plan_fingerprint,
                "run_date": result.run_date,
                "binding_epoch_ns": result.binding_epoch_ns,
                "freshness_threshold_ms": result.freshness_threshold_ms,
                "action_count": totals.get("action_count"),
                "long_count": totals.get("long_count"),
                "short_count": totals.get("short_count"),
                "gross_exposure_usd": totals.get("gross_exposure_usd"),
                "long_exposure_usd": totals.get("long_exposure_usd"),
                "short_absolute_exposure_usd": totals.get("short_absolute_exposure_usd"),
                "net_signed_exposure_usd": totals.get("net_signed_exposure_usd"),
                "offline_exposure_review_complete": result.offline_exposure_review_complete,
                "offline_margin_arithmetic_review_complete":
                    result.offline_margin_arithmetic_review_complete,
                "offline_projected_margin_rate_status": result.offline_projected_margin_rate_status,
                "offline_projected_margin_review_complete":
                    result.offline_projected_margin_review_complete,
                "account_margin_feasibility_status": result.account_margin_feasibility_status,
                "binding_time_freshness_verified": result.binding_time_freshness_verified,
                "current_market_freshness_status": result.current_market_freshness_status,
                "current_market_freshness_checked": result.current_market_freshness_checked,
            })
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return exit_code

    # --- Mode-conflict rejection (BEFORE any file read or provider/Pilot init) --
    incompatible = [n for n, v in (
        ("ws_bound_plan_only", args.ws_bound_plan_only),
        ("send_orders_to_demo", args.send_orders_to_demo),
        ("advance_on_success", args.advance_on_success),
        ("reconcile_outputs_only", args.reconcile_outputs_only),
        ("allow_notion_network", args.allow_notion_network),
        ("allow_discord_network", args.allow_discord_network),
        ("test_injected_actions_json", bool(args.test_injected_actions_json)),
        ("ws_bound_plan_output_json", bool(args.ws_bound_plan_output_json)),
    ) if v]
    if incompatible:
        return _summary(wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID,
                        detail=f"incompatible arguments for ws-bound-plan-review-only: {incompatible}",
                        exit_code=EXIT_INVALID)

    # --- Required inputs -------------------------------------------------------
    manifest_path = args.ws_bound_plan_anchor_manifest_json
    manifest_sha = args.ws_bound_plan_anchor_manifest_sha256
    wrapper_path = args.ws_bound_plan_wrapper_json
    source_path = args.ws_ticker_evidence_json
    output_path = args.ws_bound_plan_review_output_json
    for name, value in (("--ws-bound-plan-anchor-manifest-json", manifest_path),
                        ("--ws-bound-plan-anchor-manifest-sha256", manifest_sha),
                        ("--ws-bound-plan-wrapper-json", wrapper_path),
                        ("--ws-ticker-evidence-json", source_path),
                        ("--ws-bound-plan-review-output-json", output_path)):
        if not value:
            return _summary(wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID,
                            detail=f"{name} is required", exit_code=EXIT_INVALID)
    # Caller-owned expected manifest SHA must be canonical (never derived from the file).
    if not _CANON_SHA.match(str(manifest_sha)):
        return _summary(wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID,
                        detail="--ws-bound-plan-anchor-manifest-sha256 must be sha256:<64 lowercase hex>",
                        exit_code=EXIT_INVALID)

    # --- Path identity + occupied-output preflight (BEFORE any read) -----------
    norms = {label: os.path.normcase(os.path.realpath(p)) for label, p in (
        ("manifest", manifest_path), ("wrapper", wrapper_path),
        ("source", source_path), ("output", output_path))}
    if len(set(norms.values())) != 4:
        return _summary(wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID,
                        detail=f"manifest/wrapper/source/output paths must be pairwise distinct: {norms}",
                        exit_code=EXIT_INVALID)
    if os.path.lexists(output_path):
        return _summary(REVIEW_OUTPUT_EXISTS,
                        detail="--ws-bound-plan-review-output-json already exists; refusing to clobber",
                        exit_code=EXIT_INVALID)

    # --- Exact-byte reads (binary, once each; no parse/reserialize) ------------
    try:
        manifest_bytes = wsbpo.read_source_ws_bytes(manifest_path)
        wrapper_bytes = wsbpo.read_source_ws_bytes(wrapper_path)
        source_bytes = wsbpo.read_source_ws_bytes(source_path)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(REVIEW_INPUT_READ_FAILED, detail=str(exc), exit_code=EXIT_INPUT_FAILURE)

    # --- Pure CH3B1 review (exact bytes passed unchanged) ----------------------
    result = wsbpr.build_ws_bound_plan_review(
        anchor_manifest_bytes=manifest_bytes,
        expected_anchor_manifest_sha256=str(manifest_sha),
        wrapper_artifact_bytes=wrapper_bytes,
        source_ws_artifact_bytes=source_bytes)

    if result.status != wsbpr.WS_BOUND_PLAN_REVIEW_PASS:
        code = EXIT_INVALID if result.status == wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID else EXIT_BLOCKED
        return _summary(result.status, detail="review failed; terminal (no REST fallback)",
                        exit_code=code, result=result)

    # --- PASS invariants (fail closed before publication) ----------------------
    invariants_ok = (
        result.review_artifact is not None
        and result.offline_exposure_review_complete is True
        and result.offline_margin_arithmetic_review_complete is True
        and result.offline_projected_margin_rate_status == wsbpr.OFFLINE_PROJECTED_MARGIN_RATE_UNAVAILABLE
        and result.offline_projected_margin_review_complete is False
        and result.account_margin_feasibility_status == wsbpr.ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE
        and result.binding_time_freshness_verified is True
        and result.current_market_freshness_status == wsbpr.CURRENT_MARKET_FRESHNESS_NOT_EVALUATED
        and result.current_market_freshness_checked is False
        and result.execution_readiness is False
        and result.readiness_called is False and result.execution_gate_called is False
        and result.native_execution_called is False and result.pilot_advanced is False)
    if not invariants_ok:
        return _summary(wsbpr.WS_BOUND_PLAN_REVIEW_PROVENANCE_FAILED,
                        detail="PASS invariants inconsistent; refusing to publish",
                        exit_code=EXIT_BLOCKED, result=result)
    # Cross-check the operator-supplied --date against the trusted manifest run date.
    if str(args.date) != str(result.run_date):
        return _summary(wsbpr.WS_BOUND_PLAN_REVIEW_INPUT_INVALID,
                        detail=f"--date {args.date!r} != trusted manifest run_date {result.run_date!r}",
                        exit_code=EXIT_INVALID, result=result)

    # --- Publish one race-safe no-clobber review envelope (reuse CH2 writer) ----
    try:
        wsbpo.atomic_write_wrapper(output_path, result.review_artifact)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(REVIEW_OUTPUT_FAILED, detail=str(exc), exit_code=EXIT_INPUT_FAILURE,
                        result=result)

    return _summary(wsbpr.WS_BOUND_PLAN_REVIEW_PASS,
                    detail="review envelope written; terminal historical binding-time review only",
                    exit_code=EXIT_OK, result=result, written=True)


def _run_ws_bound_plan_only(args: Any, output_root: str | None) -> int:
    """TASK-014CH2 terminal Plan-only WS-bound path (no execution / readiness / gate /
    native execution / Pilot mutation / REST fallback)."""

    def _summary(status: str, *, detail: str, exit_code: int,
                 result: Any = None, output: str | None = None) -> int:
        out = {
            "status": status, "mode": "WS_BOUND_PLAN_ONLY", "detail": detail,
            "pilot_id": args.pilot_id, "date": args.date,
            "ws_ticker_evidence_json": args.ws_ticker_evidence_json,
            "ws_bound_plan_output_json": output,
            "execution_authorized": False, "execution_ready": False,
            "sender_reachable": False, "pilot_advanced": False,
            "order_post_count": 0, "amend_post_count": 0, "cancel_post_count": 0,
            "live_order_post_count": 0, "live_trading_authorized": False,
            "rest_fallback_used": False,
        }
        if result is not None:
            out.update({
                "blockers": list(result.blockers),
                "canonical_bound_plan_fingerprint": result.canonical_bound_plan_fingerprint,
                "source_ws_artifact_fingerprint": result.source_ws_artifact_fingerprint,
                "source_ws_artifact_sha256": result.source_ws_artifact_sha256,
                "original_plan_fingerprint": result.original_plan_fingerprint,
                "binding_epoch_ns": result.binding_epoch_ns,
                "freshness_threshold_ms": result.freshness_threshold_ms,
            })
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return exit_code

    # --- Mode-conflict validation (BEFORE any side effect: no reconcile, no Pilot,
    # no reporting, no provider, no read, no write) -----------------------------
    incompatible = [n for n, v in (
        ("send_orders_to_demo", args.send_orders_to_demo),
        ("advance_on_success", args.advance_on_success),
        ("reconcile_outputs_only", args.reconcile_outputs_only),
        ("allow_notion_network", args.allow_notion_network),
        ("allow_discord_network", args.allow_discord_network),
        ("test_injected_actions_json", bool(args.test_injected_actions_json)),
    ) if v]
    if incompatible:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                        detail=f"incompatible arguments for ws-bound-plan-only: {incompatible}",
                        exit_code=EXIT_INVALID)
    if not args.ws_ticker_evidence_json:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                        detail="--ws-ticker-evidence-json is required", exit_code=EXIT_INVALID)
    if not args.ws_bound_plan_output_json:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                        detail="--ws-bound-plan-output-json is required", exit_code=EXIT_INVALID)
    threshold = args.ws_binding_freshness_threshold_ms
    if not (isinstance(threshold, int) and not isinstance(threshold, bool)
            and 0 < threshold <= wsbpo.STRICT_MAX_FRESHNESS_THRESHOLD_MS):
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                        detail=f"invalid freshness threshold (1..{wsbpo.STRICT_MAX_FRESHNESS_THRESHOLD_MS})",
                        exit_code=EXIT_INVALID)
    if args.ws_binding_epoch_ns is not None:
        if not (isinstance(args.ws_binding_epoch_ns, int) and args.ws_binding_epoch_ns > 0):
            return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                            detail="--ws-binding-epoch-ns must be a positive integer",
                            exit_code=EXIT_INVALID)
        binding_epoch_ns = int(args.ws_binding_epoch_ns)
    else:
        # Computed EXACTLY ONCE at the script boundary; shared by binder + consumer.
        binding_epoch_ns = time.time_ns()

    # --- Input/output path separation + no-clobber (BEFORE provider / read) ----
    in_path = args.ws_ticker_evidence_json
    out_path = args.ws_bound_plan_output_json
    in_norm = os.path.normcase(os.path.realpath(in_path))
    out_norm = os.path.normcase(os.path.realpath(out_path))
    if in_norm == out_norm:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                        detail="--ws-ticker-evidence-json and --ws-bound-plan-output-json "
                               "resolve to the same path; the source artifact must not be overwritten",
                        exit_code=EXIT_INVALID)
    if os.path.lexists(out_path):  # lexists: also rejects a dangling-symlink destination
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_OUTPUT_EXISTS,
                        detail="--ws-bound-plan-output-json already exists; refusing to clobber "
                               "(use a fresh output path)", exit_code=EXIT_INVALID)

    # --- Build the REST seed Plan (upstream binding seed only) -----------------
    try:
        forward_result = fs.load_primary_forward_strategy_result(
            run_date=args.date, repo_root=ROOT, forward_source_root=args.test_forward_source_root)
    except fs.ForwardSourceError as exc:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                        detail=f"forward source invalid: {exc}", exit_code=EXIT_INPUT_FAILURE)
    provider = _build_production_provider()
    plan = planner.plan_strategy_native_actions(forward_result=forward_result, provider=provider)
    if not plan.available or not plan.sizing_verification.get("verified", False):
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID,
                        detail=f"REST seed plan unavailable/unverified: {plan.status}",
                        exit_code=EXIT_INVALID)
    seed_plan = _build_ws_seed_plan_mapping(args.date, plan)
    expected_symbols = [str(tp.get("symbol", "")).strip().upper()
                        for tp in plan.to_dict().get("target_positions", [])]

    # --- Read the caller-supplied source WS evidence (no live collection) ------
    try:
        src_bytes = wsbpo.read_source_ws_bytes(args.ws_ticker_evidence_json)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_SOURCE_READ_FAILED,
                        detail=str(exc), exit_code=EXIT_INPUT_FAILURE)
    try:
        src_artifact = wsbpo.parse_source_ws_artifact(src_bytes)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID,
                        detail=str(exc), exit_code=EXIT_INPUT_FAILURE)

    # --- Bind + validate (pure core); expose wrapper only on consumer PASS -----
    result = wsbpo.build_and_validate_ws_bound_plan_only(
        seed_plan=seed_plan, source_ws_artifact=src_artifact, source_ws_artifact_bytes=src_bytes,
        binding_epoch_ns=binding_epoch_ns, freshness_threshold_ms=threshold,
        expected_policy_id=wsbpo.EXPECTED_POLICY_ID, expected_strategy_id=wsbpo.EXPECTED_STRATEGY_ID,
        expected_run_date=args.date, expected_symbols=expected_symbols,
        source_ws_artifact_path=args.ws_ticker_evidence_json)

    if result.status == wsbpo.WS_BOUND_PLAN_ONLY_INPUT_INVALID:
        return _summary(result.status, detail="ws-bound-plan-only input invalid",
                        exit_code=EXIT_INVALID, result=result)
    if result.status == wsbpo.WS_BOUND_PLAN_ONLY_SOURCE_JSON_INVALID:
        return _summary(result.status, detail="source ws evidence bytes are not a JSON object",
                        exit_code=EXIT_INPUT_FAILURE, result=result)
    if result.status == wsbpo.WS_BOUND_PLAN_ONLY_BINDING_FAILED:
        return _summary(result.status, detail="WS binding did not produce a canonical bound plan",
                        exit_code=EXIT_BLOCKED, result=result)
    if not result.passed:  # CONSUMER_FAILED -- never falls back to the REST seed Plan
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_CONSUMER_FAILED,
                        detail="CH1 consumer rejected the bound plan; terminal (no REST fallback)",
                        exit_code=EXIT_BLOCKED, result=result)

    # --- Write exactly one canonical wrapper artifact (atomic) -----------------
    try:
        wsbpo.atomic_write_wrapper(args.ws_bound_plan_output_json, result.wrapper_artifact)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(wsbpo.WS_BOUND_PLAN_ONLY_OUTPUT_FAILED,
                        detail=str(exc), exit_code=EXIT_INPUT_FAILURE, result=result)

    return _summary(wsbpo.WS_BOUND_PLAN_ONLY_PASS,
                    detail="canonical WS-bound Plan wrapper written; terminal before execution",
                    exit_code=EXIT_OK, result=result, output=args.ws_bound_plan_output_json)


def _run_prepare_from_current_feasibility_artifacts(args: Any) -> int:
    """TASK-014 terminal DRY-RUN preparation. Reads ONLY the three CH4A artifacts
    (current_feasibility_review / current_market_evidence / demo_account_evidence) and builds
    the EXACT 50 order payload previews via ``nx.prepare_strategy_native_batch_dry_run``. It
    constructs no transport, never calls ``execute_daily_native`` / ``post_order_create``,
    writes no authorization marker, and never advances the Pilot.

    Conflicting flags are rejected before any artifact read, Pilot state read, provider
    construction, transport construction, or execution call."""
    incompatible = [n for n, v in (
        ("send_orders_to_demo", args.send_orders_to_demo),
        ("reconcile_outputs_only", args.reconcile_outputs_only),
        ("advance_on_success", args.advance_on_success),
        ("ws_bound_plan_only", args.ws_bound_plan_only),
        ("ws_bound_plan_review_only", args.ws_bound_plan_review_only),
    ) if v]
    if incompatible:
        print(json.dumps({"verdict": nx.BATCH_PREP_REJECTED,
                          "blockers": [f"incompatible_flag:{f}" for f in incompatible]},
                         ensure_ascii=False, sort_keys=True))
        return EXIT_INVALID

    required = {
        "--current-feasibility-review-json": args.current_feasibility_review_json,
        "--current-market-evidence-json": args.current_market_evidence_json,
        "--demo-account-evidence-json": args.demo_account_evidence_json,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        print(json.dumps({"verdict": nx.BATCH_PREP_REJECTED,
                          "blockers": [f"missing_arg:{k}" for k in missing]},
                         ensure_ascii=False, sort_keys=True))
        return EXIT_INVALID
    try:
        with open(args.current_feasibility_review_json, encoding="utf-8") as f:
            review = json.load(f)
        with open(args.current_market_evidence_json, encoding="utf-8") as f:
            market = json.load(f)
        with open(args.demo_account_evidence_json, encoding="utf-8") as f:
            account = json.load(f)
    except (OSError, ValueError) as exc:
        print(json.dumps({"verdict": nx.BATCH_PREP_REJECTED,
                          "blockers": [f"input_unreadable:{type(exc).__name__}"]},
                         ensure_ascii=False, sort_keys=True))
        return EXIT_INVALID

    current_actions = market.get("current_actions") if isinstance(market, Mapping) else None
    if not isinstance(current_actions, list):
        print(json.dumps({"verdict": nx.BATCH_PREP_REJECTED,
                          "blockers": ["market_evidence_missing_current_actions"]},
                         ensure_ascii=False, sort_keys=True))
        return EXIT_INVALID

    result = nx.prepare_strategy_native_batch_dry_run(
        feasibility_review=review, current_actions=current_actions,
        account_evidence=account, pilot_id=args.pilot_id, date=args.date)

    # Manual-authorization handshake: when PREPARED, authorize an IMMUTABLE ALLOCATION INTENT
    # (per-symbol side + target quote-notional + the fixed strategy capital-base snapshot used for
    # sizing), NOT immutable final quantities. The strategy capital base is the sum of the
    # strategy's own |target notionals| (price-independent weight x capital_base_usd, currently
    # V1_CAPITAL_BASE_USD == 10000, cross-validated from config + state artifact) -- account
    # equity / unrealized PnL never enters the sizing basis. Execution recomputes executable
    # quantities from these targets + fresh price, so the fingerprint/token stay stable when only
    # price moves. No automatic post-close compounding is implemented.
    if result.get("verdict") == nx.BATCH_PREP_PREPARED:
        _allocs, _capital = _allocations_from_market_targets(
            result.get("order_payloads", []), current_actions)
        if _allocs is None:
            result["verdict"] = nx.BATCH_PREP_REJECTED
            result["blockers"] = list(result.get("blockers", [])) + [
                "missing_target_signed_notional_usd"]
            result["order_payloads"] = []
        else:
            _capital_str = _runner_canon(_capital)
            for _p, _a in zip(result["order_payloads"], _allocs):
                _p["target_notional_usd"] = _a["target_notional_usd"]
            result["strategy_capital_base_usd"] = _capital_str
            _fp = allocation_intent_fingerprint(
                _allocs, pilot_id=args.pilot_id, date=args.date,
                strategy_capital_base_usd=_capital_str)
            result["payload_fingerprint"] = _fp
            result["allocation_intent_fingerprint"] = _fp
            result["expected_batch_authorization_token"] = expected_batch_authorization_token(
                args.date, _fp)

    if args.prepare_output_json:
        if os.path.lexists(args.prepare_output_json):
            print(json.dumps({"verdict": nx.BATCH_PREP_REJECTED,
                              "blockers": [f"output_exists:{args.prepare_output_json}"]},
                             ensure_ascii=False, sort_keys=True))
            return EXIT_INVALID
        with open(args.prepare_output_json, "w", encoding="utf-8") as f:
            json.dump(result, f, ensure_ascii=False, sort_keys=True)

    print(json.dumps(result, ensure_ascii=False, sort_keys=True))
    return EXIT_OK if result["verdict"] == nx.BATCH_PREP_PREPARED else EXIT_BLOCKED


# ---------------------------------------------------------------------------
# TASK-014: explicit, fail-closed, Demo-only batch EXECUTION wiring.
#
# Wires the canonical runner to the existing 50-order execute_daily_native() engine behind
# one manual authorization token that is BOTH date-bound and payload(fingerprint)-bound, so
# an old token can authorize neither a different day nor a different set of 50 order bodies.
# Every gate below runs BEFORE any transport is constructed; the engine is invoked at most
# once. No new sender / engine / artifact schema / authorization framework is introduced.
# ---------------------------------------------------------------------------

BATCH_AUTH_TOKEN_PREFIX = "CONFIRM_DEMO_NATIVE_BATCH_"

EXEC_BATCH_DISPATCHED = "DEMO_BATCH_DISPATCHED"
EXEC_BATCH_AMBIGUOUS = "DEMO_BATCH_AMBIGUOUS_FAIL_CLOSED"
EXEC_BATCH_REJECTED = "DEMO_BATCH_REJECTED_PRE_SEND"
EXEC_BATCH_ALREADY_ATTEMPTED = "DEMO_BATCH_ALREADY_ATTEMPTED_REQUIRES_RECONCILIATION"

# Durable exactly-once guard for ONE authorized allocation batch. The stable identity is
# (pilot_id, date, allocation_intent_fingerprint) -- a fresh-price / qty change NEVER changes
# it (the fingerprint is price-independent). The record lives inside the existing
# NativeExecutionStore output directory; it is claimed atomically (exclusive create + fsync)
# immediately BEFORE the first order send, so a crash after some orders were accepted -- or
# before the final summary was written -- still blocks every later invocation for that identity.
BATCH_ATTEMPT_FILENAME = "batch_attempt.json"
BATCH_ATTEMPT_SCHEMA = "demo_strategy_native_batch_attempt"
BATCH_ATTEMPT_SENDING = "SENDING_PHASE_ENTERED"


def _compact_date(date: str) -> str:
    return str(date).replace("-", "").strip()


def expected_batch_authorization_token(date: str, fingerprint: str) -> str:
    """Date-bound + intent-bound manual token (no secret); follows the existing
    CONFIRM_DEMO_*_<date>_<bound> convention. ``fingerprint`` is the price-independent
    allocation-intent fingerprint (see allocation_intent_fingerprint)."""
    return f"{BATCH_AUTH_TOKEN_PREFIX}{_compact_date(date)}_{fingerprint[:16]}"


def _runner_dec(value: Any) -> "Decimal | None":
    try:
        return Decimal(str(value))
    except (InvalidOperation, TypeError, ValueError):
        return None


def _runner_canon(value: Decimal) -> str:
    normalized = value.normalize()
    if normalized == 0:
        normalized = Decimal("0")
    return format(normalized, "f")


def _load_prepared_batch_artifact(path: str) -> Mapping[str, Any]:
    """Read the IMMUTABLE prepared-batch artifact written by the non-sending preparation mode.
    Raises ValueError if absent/unparseable/not an object."""
    if not path:
        raise ValueError("prepared_batch_json_not_supplied")
    if not os.path.isfile(path):
        raise ValueError(f"prepared_batch_json_missing:{path}")
    with open(path, encoding="utf-8") as f:
        artifact = json.load(f)
    if not isinstance(artifact, Mapping):
        raise ValueError("prepared_batch_json_not_object")
    return artifact


def allocation_intent_fingerprint(
    allocations: Sequence[Mapping[str, Any]], *, pilot_id: str, date: str,
    strategy_capital_base_usd: Any,
) -> str:
    """Deterministic SHA-256 over the IMMUTABLE allocation INTENT, which is PRICE-INDEPENDENT:
    pilot/date, the strategy capital-base snapshot (V1_CAPITAL_BASE_USD == 10000, cross-validated
    from config + state artifact; NOT account equity or unrealized PnL), and per symbol the side
    + target quote-notional. It binds WHAT to allocate (and against what capital base), NEVER the
    price-dependent executable quantity or order body -- so it stays stable when only fresh market
    price changes between preparation and execution."""
    canon = {
        "pilot_id": str(pilot_id), "date": str(date),
        "strategy_capital_base_usd": str(strategy_capital_base_usd),
        "allocations": sorted(
            ({"symbol": str(a["symbol"]).strip().upper(), "side": str(a["side"]),
              "target_notional_usd": str(a["target_notional_usd"])} for a in allocations),
            key=lambda d: d["symbol"]),
    }
    blob = json.dumps(canon, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode("utf-8")).hexdigest()


def _allocations_from_market_targets(
    payloads: Sequence[Mapping[str, Any]], market_rows: Sequence[Mapping[str, Any]],
) -> tuple[list[dict[str, Any]] | None, "Decimal | None"]:
    """Derive the per-symbol authorized allocation INTENT (symbol/side/|target notional|) and
    the strategy capital-base snapshot (= sum of |target notional|) from the strategy's own
    ``target_signed_notional_usd`` in the market evidence. The capital basis comes from the
    strategy targets (price-independent weight x capital_base_usd), NOT from account equity /
    unrealized PnL. Returns (None, None) when any target is missing."""
    target_by_symbol: dict[str, Decimal] = {}
    for r in (market_rows or []):
        if not isinstance(r, Mapping):
            continue
        sym = str(r.get("symbol", "")).strip().upper()
        t = _runner_dec(r.get("target_signed_notional_usd"))
        if sym and t is not None:
            target_by_symbol[sym] = t.copy_abs()
    allocations: list[dict[str, Any]] = []
    capital = Decimal("0")
    for p in payloads:
        sym = str(p.get("symbol", "")).strip().upper()
        tgt = target_by_symbol.get(sym)
        if tgt is None or tgt <= 0:
            return None, None
        allocations.append({"symbol": sym, "side": str(p.get("side", "")),
                            "target_notional_usd": _runner_canon(tgt)})
        capital += tgt
    return allocations, capital


def verify_immutable_prepared_artifact(
    artifact: Mapping[str, Any], *, pilot_id: str, date: str, token: str,
) -> tuple[bool, list[str], str, list[dict[str, Any]], str]:
    """Verify the supplied prepared-batch artifact authorizes THIS execution, WITHOUT any fresh
    market input. The authorization binds the IMMUTABLE allocation INTENT (per-symbol side +
    target quote-notional + strategy capital-base snapshot), recomputed from the artifact's own
    fields; the supplied token must bind that price-independent intent fingerprint + date.
    Executable quantities are NOT part of the artifact's authority (they are recomputed fresh).
    Returns (ok, blockers, intent_fingerprint, allocations, strategy_capital_base_usd)."""
    blockers: list[str] = []
    if str(artifact.get("verdict", "")) != nx.BATCH_PREP_PREPARED:
        blockers.append(f"artifact_verdict_not_prepared:{artifact.get('verdict')}")
    if str(artifact.get("pilot_id", "")) != str(pilot_id):
        blockers.append("artifact_pilot_id_mismatch")
    if str(artifact.get("date", "")) != str(date):
        blockers.append("artifact_date_mismatch")

    payloads = artifact.get("order_payloads") or []
    if not isinstance(payloads, list) or len(payloads) != nx.EXPECTED_BATCH_ORDER_COUNT:
        blockers.append(f"artifact_order_count_not_fifty:"
                        f"{len(payloads) if isinstance(payloads, list) else 'NA'}")
        return False, blockers, "", [], "0"

    seen_symbols: set[str] = set()
    buys = sells = 0
    allocations: list[dict[str, Any]] = []
    capital_sum = Decimal("0")
    for p in payloads:
        symbol = str(p.get("symbol", "")).strip().upper()
        if not symbol:
            blockers.append("artifact_empty_symbol")
        elif symbol in seen_symbols:
            blockers.append(f"artifact_duplicate_symbol:{symbol}")
        seen_symbols.add(symbol)
        side = str(p.get("side", ""))
        if side == "Buy":
            buys += 1
        elif side == "Sell":
            sells += 1
        target = _runner_dec(p.get("target_notional_usd"))
        if target is None or target <= 0:
            blockers.append(f"artifact_missing_target_notional:{symbol or '?'}")
            continue
        allocations.append({"symbol": symbol, "side": side,
                            "target_notional_usd": _runner_canon(target)})
        capital_sum += target

    if buys != nx.EXPECTED_BATCH_SIDE_COUNT or sells != nx.EXPECTED_BATCH_SIDE_COUNT:
        blockers.append(f"artifact_buy_sell_not_25_25:{buys}/{sells}")

    # The recorded strategy capital-base snapshot must equal the sum of the |target notionals|
    # it authorizes (no equity / unrealized-PnL leakage into the sizing basis).
    stored_capital = _runner_dec(artifact.get("strategy_capital_base_usd"))
    if stored_capital is None or stored_capital != capital_sum:
        blockers.append("artifact_capital_inconsistent_with_targets")

    # Recompute the price-independent intent fingerprint from the artifact's OWN capital + intent.
    capital_str = artifact.get("strategy_capital_base_usd")
    fingerprint = allocation_intent_fingerprint(
        allocations, pilot_id=pilot_id, date=date, strategy_capital_base_usd=capital_str)
    stored_fp = artifact.get("payload_fingerprint")
    if stored_fp is not None and str(stored_fp) != fingerprint:
        blockers.append("artifact_fingerprint_recompute_mismatch")
    expected_token = expected_batch_authorization_token(date, fingerprint)
    if token != expected_token:
        blockers.append("authorization_token_mismatch")

    return (not blockers), blockers, fingerprint, allocations, _runner_canon(capital_sum)


def build_executable_actions_from_authorized_intent(
    *, allocations: Sequence[Mapping[str, Any]], pilot_id: str, date: str,
    review: Mapping[str, Any], current_actions: Sequence[Mapping[str, Any]],
    account: Mapping[str, Any],
) -> tuple[bool, list[str], list[Any], dict[str, Any]]:
    """Recompute the FINAL executable quantity for each AUTHORIZED allocation from its IMMUTABLE
    target quote-notional + FRESH market price + current instrument rules, using the canonical
    floor-to-step rounding (``wb._floor_qty`` -- the same the whole pipeline uses). The
    authorized ``target_notional_usd`` is NEVER changed; only the executable quantity moves with
    price, so the resulting actual notional tracks the authorized target (it does NOT inflate
    with price). The recomputed actual notionals then feed the EXISTING margin-feasibility model
    (account equity / available balance / existing margin are SAFETY inputs only, never the
    sizing basis). Returns (ok, blockers, actions, evidence)."""
    review = review if isinstance(review, Mapping) else {}
    account = account if isinstance(account, Mapping) else {}
    rows_by_symbol = {str(r.get("symbol", "")).strip().upper(): r
                      for r in (current_actions or []) if isinstance(r, Mapping)}
    blockers: list[str] = []

    # --- Account-level fresh gates (same status constants CH4A / prepare require) ---
    if str(review.get("status", "")) != cf.CURRENT_FEASIBILITY_PASS:
        blockers.append(f"fresh_feasibility_not_pass:{review.get('status')}")
    if review.get("live_environment_denied") is False or account.get("live_environment_denied") is False:
        blockers.append("fresh_live_environment_not_denied")
    if str(account.get("target_leverage_evidence_status", "")) != cf.LEVERAGE_EVIDENCE_OK:
        blockers.append(f"fresh_leverage_evidence_not_ok:{account.get('target_leverage_evidence_status')}")
    overlaps = sorted(str(s).upper() for s in (account.get("strategy_position_overlaps") or []))
    if overlaps:
        blockers.append(f"fresh_strategy_position_overlap:{overlaps}")
    protected = {str(s).strip().upper() for s in (account.get("protected_positions") or [])}
    leverage_by_symbol = {str(k).strip().upper(): str(v)
                          for k, v in (account.get("target_configured_leverage_by_symbol") or {}).items()}

    actions: list[Any] = []
    fresh_market_actions: list[Any] = []
    target_gross = Decimal("0")
    actual_gross = Decimal("0")
    for a in allocations:
        symbol = str(a["symbol"]).strip().upper()
        side = str(a["side"])
        target = _runner_dec(a["target_notional_usd"])
        row = rows_by_symbol.get(symbol)
        if row is None:
            blockers.append(f"symbol_absent_from_fresh_evidence:{symbol or '?'}")
            continue
        if str(row.get("instrument_status", "")) != cf.ACCEPTED_INSTRUMENT_STATUS or row.get("trading") is not True:
            blockers.append(f"symbol_not_trading:{symbol}")
        if symbol in protected:
            blockers.append(f"fresh_protected_position_overlap:{symbol}")
        price = _runner_dec(row.get("current_price"))
        qty_step = _runner_dec(row.get("qty_step"))
        min_qty = _runner_dec(row.get("min_order_qty"))
        min_notional = _runner_dec(row.get("min_notional_value"))
        max_mkt = _runner_dec(row.get("max_market_order_qty"))
        if target is None or target <= 0:
            blockers.append(f"authorized_target_not_positive:{symbol}")
            continue
        if price is None or price <= 0:
            blockers.append(f"fresh_price_not_positive:{symbol}")
            continue
        target_gross += target
        # Canonical floor-to-step quantity from the AUTHORIZED target + FRESH price.
        qty = wb._floor_qty(target, price, qty_step)
        actual = qty * price
        if qty <= 0:
            blockers.append(f"zero_quantity_after_rounding:{symbol}")
            continue
        if min_qty is not None and min_qty >= 0 and qty < min_qty:
            blockers.append(f"below_min_order_qty:{symbol}")
        if min_notional is not None and actual < min_notional:
            blockers.append(f"below_min_notional:{symbol}")
        if max_mkt is not None and max_mkt > 0 and qty > max_mkt:
            blockers.append(f"above_max_market_order_qty:{symbol}")
        if qty_step is not None and qty_step > 0 and (qty % qty_step) != 0:
            blockers.append(f"qty_not_step_multiple:{symbol}")
        # Consistency: floor rounding never EXCEEDS the target and loses < one qty-step of
        # notional -> the executed allocation stays ~ the authorized target after exchange
        # rounding (this is the existing exchange boundary, not an arbitrary drift tolerance).
        if actual > target:
            blockers.append(f"actual_notional_exceeds_target:{symbol}")
        elif qty_step is not None and qty_step > 0 and (target - actual) >= (qty_step * price):
            blockers.append(f"rounding_inconsistent_with_target:{symbol}")
        if symbol not in leverage_by_symbol:
            blockers.append(f"fresh_leverage_missing:{symbol}")
        actual_gross += actual
        actions.append(nx.StrategyNativeAction(
            symbol=symbol, side=side, qty=_runner_canon(qty), intent=nx.INTENT_OPEN,
            reduce_only=False, notional_usdt=_runner_canon(actual), source_reference=symbol))
        fresh_market_actions.append(SimpleNamespace(symbol=symbol,
                                                    rounded_notional_usd=_runner_canon(actual)))

    # --- Aggregate margin feasibility on the RECOMPUTED notionals (reuse the existing model).
    # Account equity / available balance are SAFETY inputs here -- never the sizing basis. ---
    acct_standin = SimpleNamespace(
        ok=True,
        available_balance_usd=(review.get("available_balance_usd")
                               or account.get("available_balance_usd")),
        account_equity_usd=(review.get("account_equity_usd")
                            or account.get("account_equity_usd")),
        existing_initial_margin_usd=(review.get("existing_initial_margin_usd")
                                     or account.get("existing_initial_margin_usd")),
        target_leverage_evidence_status=str(account.get("target_leverage_evidence_status", "")),
        target_configured_leverage_by_symbol=leverage_by_symbol,
        target_leverage_missing_symbols=(),
        applicable_initial_margin_rate=None, margin_rate_source=None)
    market_standin = SimpleNamespace(actions=fresh_market_actions)
    margin = cf.evaluate_margin_feasibility(
        account_result=acct_standin, target_gross_notional_usd=cf.V1_GROSS_USD,
        market_result=market_standin,
        safety_headroom_fraction=cf.DEFAULT_SAFETY_HEADROOM_FRACTION,
        fees_buffer_usd=cf.DEFAULT_FEES_BUFFER_USD)
    if margin.status != cf.MARGIN_FEASIBILITY_PASS:
        blockers.append(f"fresh_margin_not_pass:{margin.status}")
        blockers.extend(f"margin_failure:{f}" for f in margin.failures)

    evidence = {
        "fresh_feasibility_status": review.get("status"),
        "authorized_target_gross_notional_usd": _runner_canon(target_gross),
        "executed_actual_gross_notional_usd": _runner_canon(actual_gross),
        "fresh_projected_total_initial_margin_usd": margin.projected_total_initial_margin_usd,
        "fresh_remaining_available_balance_usd": margin.remaining_available_balance_usd,
        "fresh_safety_headroom_usd": margin.safety_headroom_usd,
        "fresh_margin_feasibility_status": margin.status,
    }
    return (not blockers), blockers, actions, evidence


class FreshCh4aError(RuntimeError):
    """The in-command fresh CH4A read-only collection failed (non-zero exit / unreadable)."""


def _batch_attempt_path(store: Any):
    """Path of the durable batch-attempt guard, inside the existing NativeExecutionStore dir."""
    return store.dir / BATCH_ATTEMPT_FILENAME


def _read_batch_attempt(store: Any) -> dict[str, Any] | None:
    """Return the durable batch-attempt record for this (pilot, date) if one exists."""
    path = _batch_attempt_path(store)
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as fh:
        return json.load(fh)


def _claim_batch_attempt(store: Any, record: Mapping[str, Any]) -> bool:
    """Atomically CLAIM the durable batch-attempt guard. Returns True iff THIS call created it
    (caller may proceed to send); False if a record already exists (caller must fail closed).
    Uses exclusive create + fsync so the claim survives process / VPS restart and a crash after
    some orders were accepted but before the final summary was written."""
    store.dir.mkdir(parents=True, exist_ok=True)
    path = str(_batch_attempt_path(store))
    try:
        fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY)
    except FileExistsError:
        return False
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(json.dumps(dict(record), ensure_ascii=False, indent=2, sort_keys=True))
        fh.flush()
        os.fsync(fh.fileno())
    return True


def _finalize_batch_attempt(store: Any, **fields: Any) -> None:
    """Best-effort terminal annotation of the already-claimed guard (atomic). Never relaxes the
    guard: the SENDING record alone already blocks retries even if this update never runs."""
    try:
        record = _read_batch_attempt(store) or {}
        record.update(fields)
        store._atomic_write(_batch_attempt_path(store),
                            json.dumps(record, ensure_ascii=False, indent=2, sort_keys=True))
    except OSError:
        pass


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _utc_today() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d")


def _invoke_real_ch4a(argv: list[str]) -> int:
    """Call the EXISTING CH4A current-feasibility runner's main() (no duplication of its
    validation). Imported lazily to avoid import-time coupling."""
    import importlib
    ch4a = importlib.import_module("scripts.run_demo_strategy_current_feasibility")
    return ch4a.main(argv)


_CH4A_PREFLIGHT_FILES = {
    "review": "current_feasibility_review.json",
    "market": "current_market_evidence.json",
    "account": "demo_account_evidence.json",
    "summary": "current_feasibility_summary.json",
}


def _collect_fresh_ch4a(args: Any, *, invoke=None) -> tuple[Mapping[str, Any], list, Mapping[str, Any]]:
    """Run the EXISTING CH4A read-only current-feasibility flow EXACTLY ONCE with
    --allow-real-network into a fresh NO-CLOBBER preflight directory, require exit 0, and read
    ONLY the artifacts that run produced. Execution NEVER trusts pre-existing artifact files;
    arbitrary old --current-*-json paths (used by the non-sending prepare mode) are ignored."""
    invoke = invoke or _invoke_real_ch4a
    required = {
        "--review-artifact-json": args.review_artifact_json,
        "--review-artifact-sha256": args.review_artifact_sha256,
        "--anchor-manifest-json": args.anchor_manifest_json,
        "--anchor-manifest-sha256": args.anchor_manifest_sha256,
        "--wrapper-json": args.wrapper_json,
        "--strategy-symbols-json": args.strategy_symbols_json,
        "--strategy-symbols-sha256": args.strategy_symbols_sha256,
        "--ch4a-preflight-dir": args.ch4a_preflight_dir,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        raise ValueError("missing_ch4a_arg:" + ",".join(missing))
    preflight = args.ch4a_preflight_dir
    if os.path.lexists(preflight):
        raise ValueError("ch4a_preflight_dir_exists:" + str(preflight))
    os.makedirs(preflight)
    out = {k: os.path.join(preflight, v) for k, v in _CH4A_PREFLIGHT_FILES.items()}
    ch4a_argv = [
        "--current-market-demo-account-feasibility-read-only",
        "--review-artifact-json", args.review_artifact_json,
        "--review-artifact-sha256", args.review_artifact_sha256,
        "--anchor-manifest-json", args.anchor_manifest_json,
        "--anchor-manifest-sha256", args.anchor_manifest_sha256,
        "--wrapper-json", args.wrapper_json,
        "--strategy-symbols-json", args.strategy_symbols_json,
        "--strategy-symbols-sha256", args.strategy_symbols_sha256,
        "--market-evidence-output-json", out["market"],
        "--account-evidence-output-json", out["account"],
        "--feasibility-review-output-json", out["review"],
        "--summary-output-json", out["summary"],
        "--allow-real-network",
    ]
    # Capture CH4A's own printed JSON so it never contaminates the single final execution
    # summary on stdout. The exit status (return value) and the written artifacts are preserved.
    ch4a_stdout = io.StringIO()
    with contextlib.redirect_stdout(ch4a_stdout):
        rc = invoke(ch4a_argv)
    if rc != 0:
        raise FreshCh4aError(f"ch4a_exit_nonzero:{rc}")
    with open(out["review"], encoding="utf-8") as f:
        review = json.load(f)
    with open(out["market"], encoding="utf-8") as f:
        market = json.load(f)
    with open(out["account"], encoding="utf-8") as f:
        account = json.load(f)
    current_actions = market.get("current_actions") if isinstance(market, Mapping) else None
    if not isinstance(current_actions, list):
        raise ValueError("market_evidence_missing_current_actions")
    return review, current_actions, account


def _build_real_demo_transport(*, credentials: Any, env: Mapping[str, str] | None = None) -> Any:
    """Construct the REAL Demo transport from BYBIT_DEMO_* env credentials. Only ever called
    AFTER every authorization gate passes."""
    src = env if env is not None else os.environ
    return RealDemoOrderTransport(
        api_key=src.get("BYBIT_DEMO_API_KEY", "") or "",
        api_secret=src.get("BYBIT_DEMO_API_SECRET", "") or "",
        recv_window=credentials.recv_window)


def _run_execute_prepared_demo_batch(
    args: Any, *,
    collect_feasibility=None, build_transport=None, executor=None,
    env: Mapping[str, str] | None = None, base_url: str | None = None,
    today: str | None = None,
) -> int:
    """Explicit, fail-closed, Demo-only batch execution of an IMMUTABLE prepared batch.

    The authorized 50 order bodies come ONLY from --prepared-batch-json (the artifact the
    non-sending preparation mode wrote) and are NEVER regenerated from fresh market prices.
    Fresh CH4A still runs in-process immediately before dispatch, but solely to RE-VALIDATE
    those exact fixed payloads against current evidence (price / instrument rules / trading /
    leverage / balance); it never alters a quantity or the payload fingerprint. Transport is
    constructed only after BOTH the immutable-artifact authorization AND the fresh-feasibility
    validation pass. Injection seams (collect_feasibility / build_transport / executor / env /
    base_url / today) exist ONLY so the wiring is fully testable offline."""
    collect_feasibility = collect_feasibility or _collect_fresh_ch4a
    build_transport = build_transport or _build_real_demo_transport
    executor = executor or nx.execute_daily_native
    base_url = base_url or DEMO_BASE_URL
    today = today or _utc_today()
    output_root = args.test_output_root

    state: dict[str, Any] = {"transport_constructed": False, "executor_called": 0}

    def _reject(blocker: str, *, exit_code: int, extra: Mapping[str, Any] | None = None) -> int:
        out = {
            "status": EXEC_BATCH_REJECTED, "mode": "EXECUTE_PREPARED_DEMO_BATCH",
            "pilot_id": args.pilot_id, "date": args.date, "blockers": [blocker],
            "execution_authorized": False, "execution_batch_authorized": False,
            "transport_constructed": state["transport_constructed"],
            "execute_daily_native_called": state["executor_called"],
            "order_post_count": 0, "amend_post_count": 0, "cancel_post_count": 0,
            "live_order_post_count": 0, "live_trading_authorized": False,
            "pilot_advanced": False,
        }
        if extra:
            out.update(extra)
        print(json.dumps(out, ensure_ascii=False, sort_keys=True))
        return exit_code

    # --- 1. Required flags (execution + send) -------------------------------------------
    if not args.send_orders_to_demo:
        return _reject("missing_send_orders_to_demo_flag", exit_code=EXIT_INVALID)
    # --- 2. Mode conflicts (incl. Pilot-advancement, which this mode must never trigger) --
    conflicts = [n for n, v in (
        ("prepare_from_current_feasibility_artifacts", args.prepare_from_ch4a),
        ("ws_bound_plan_only", args.ws_bound_plan_only),
        ("ws_bound_plan_review_only", args.ws_bound_plan_review_only),
        ("reconcile_outputs_only", args.reconcile_outputs_only),
        ("advance_on_success", args.advance_on_success),
    ) if v]
    if conflicts:
        return _reject(f"incompatible_flag:{conflicts[0]}", exit_code=EXIT_INVALID)
    # --- 3. --date must equal the current UTC date (no stale-day execution) ---------------
    if str(args.date).strip() != str(today).strip():
        return _reject(f"execution_date_not_current_utc:{today}", exit_code=EXIT_INVALID)
    # --- 4. Token + immutable prepared-batch artifact must be supplied -------------------
    if not args.batch_authorization_token:
        return _reject("missing_authorization_token", exit_code=EXIT_INVALID)
    if not args.prepared_batch_json:
        return _reject("missing_prepared_batch_json", exit_code=EXIT_INVALID)
    # --- 5. Demo host only; live endpoint permanently rejected ---------------------------
    try:
        assert_demo_url(base_url + EP_ORDER_REALTIME)
        host_ok = host_of(base_url) == DEMO_HOST and base_url.startswith(DEMO_BASE_URL)
    except Exception:  # noqa: BLE001 -- any guard rejection denies the endpoint
        host_ok = False
    if not host_ok:
        return _reject("non_demo_base_url_or_live_endpoint", exit_code=EXIT_INVALID)
    # --- 6. Demo credentials present (presence only; never the secret value) -------------
    creds = load_demo_credentials(env)
    if not (creds.api_key_present and creds.api_secret_present):
        return _reject("demo_credentials_missing", exit_code=EXIT_INVALID)
    # --- 7. Load + verify the IMMUTABLE ALLOCATION INTENT artifact (no fresh input yet) ---
    try:
        artifact = _load_prepared_batch_artifact(args.prepared_batch_json)
    except (OSError, ValueError) as exc:
        return _reject(f"prepared_batch_artifact_unreadable:{type(exc).__name__}",
                       exit_code=EXIT_INPUT_FAILURE, extra={"detail": str(exc)})
    ok, art_blockers, fingerprint, allocations, capital = verify_immutable_prepared_artifact(
        artifact, pilot_id=args.pilot_id, date=args.date, token=args.batch_authorization_token)
    expected_token = expected_batch_authorization_token(args.date, fingerprint)
    token_extra = {"payload_fingerprint": fingerprint, "expected_authorization_token": expected_token,
                   "strategy_capital_base_usd": capital}
    if not ok:
        return _reject("prepared_artifact_authorization_failed", exit_code=EXIT_INVALID,
                       extra={**token_extra, "artifact_blockers": art_blockers})
    # --- 7b. Durable exactly-once guard READ: if this stable batch identity (pilot/date/intent
    #         fingerprint) already ENTERED the sending phase, fail closed now -- before fresh
    #         CH4A, transport, or any order dispatch. Survives restart / crash-after-send. ----
    store = nx.NativeExecutionStore(args.pilot_id, args.date, output_root)
    existing_attempt = _read_batch_attempt(store)
    if existing_attempt is not None:
        return _reject(EXEC_BATCH_ALREADY_ATTEMPTED, exit_code=EXIT_BLOCKED,
                       extra={**token_extra, "requires_reconciliation": True,
                              "prior_batch_attempt": existing_attempt})
    # --- 8. Run fresh CH4A INSIDE this command (read-only) for the feasibility evidence ---
    try:
        review, current_actions, account = collect_feasibility(args)
    except (OSError, ValueError, FreshCh4aError) as exc:
        return _reject(f"feasibility_recollection_failed:{type(exc).__name__}",
                       exit_code=EXIT_INPUT_FAILURE, extra={**token_extra, "detail": str(exc)})
    # --- 9. Recompute executable qty from the IMMUTABLE targets + fresh price, then validate
    #        feasibility of those recomputed allocations (targets NEVER change) ------------
    feas_ok, feas_blockers, actions, feas_evidence = build_executable_actions_from_authorized_intent(
        allocations=allocations, pilot_id=args.pilot_id, date=args.date,
        review=review, current_actions=current_actions, account=account)
    if not feas_ok:
        return _reject("fresh_feasibility_validation_failed", exit_code=EXIT_BLOCKED,
                       extra={**token_extra, "fresh_feasibility_blockers": feas_blockers,
                              **feas_evidence})
    # --- 10. Pilot state must be RUNNING + Demo-authorized + Live denied ------------------
    pstate = rd.PilotStateStore(args.pilot_id, output_root).read_state()
    if not (pstate is not None and pstate.get("lifecycle_state") == rd.RUNNING
            and pstate.get("order_execution_authorized") is True
            and pstate.get("live_trading_authorized") is False):
        return _reject("pilot_state_incompatible", exit_code=EXIT_BLOCKED, extra=token_extra)
    # --- 11. A prior ambiguous batch for this date must be reconciled first ---------------
    prior = store.read_state()
    if prior is not None and prior.get("day_verdict") == nx.DAY_AMBIGUOUS:
        return _reject("prior_ambiguous_requires_reconciliation", exit_code=EXIT_BLOCKED,
                       extra=token_extra)
    # --- 12. CLAIM the durable exactly-once guard ATOMICALLY -- the LAST step before the first
    #         possible order send. A pre-send rejection above never reaches here, so it never
    #         consumes the authorization; a concurrent racer that already claimed loses here. ---
    claimed = _claim_batch_attempt(store, {
        "schema": BATCH_ATTEMPT_SCHEMA, "pilot_id": args.pilot_id, "date": args.date,
        "allocation_intent_fingerprint": fingerprint,
        "strategy_capital_base_usd": capital,
        "status": BATCH_ATTEMPT_SENDING, "claimed_at_utc": _utc_now_iso(),
    })
    if not claimed:
        return _reject(EXEC_BATCH_ALREADY_ATTEMPTED, exit_code=EXIT_BLOCKED,
                       extra={**token_extra, "requires_reconciliation": True,
                              "prior_batch_attempt": _read_batch_attempt(store)})

    # ===== BOTH gates passed + guard claimed (immutable allocation-intent authorization + fresh
    # feasibility of the recomputed executable quantities): construct the transport and dispatch
    # ONCE. The dispatched bodies carry the freshly recomputed qty (target notional unchanged). =
    transport = build_transport(credentials=creds, env=env)
    state["transport_constructed"] = True
    result = executor(pilot_id=args.pilot_id, date=args.date, actions=actions,
                      transport=transport, output_root=output_root, base_url=base_url)
    state["executor_called"] += 1

    day_verdict = result.day_verdict
    # Pilot advancement is intentionally NOT performed here: it remains owned by the existing
    # reporting / Excel / daily-success workflow. --advance-on-success is rejected above.
    pilot_advanced = False

    if day_verdict == nx.DAY_SUCCESS:
        status, exit_code = EXEC_BATCH_DISPATCHED, EXIT_OK
    elif day_verdict == nx.DAY_AMBIGUOUS:
        status, exit_code = EXEC_BATCH_AMBIGUOUS, EXIT_AMBIGUOUS
    else:                                   # DAY_NOT_RUNNING / DAY_ENDPOINT -> fail closed
        status, exit_code = EXEC_BATCH_REJECTED, EXIT_BLOCKED

    # Terminal annotation of the durable guard (it already blocks retries regardless; this only
    # records the outcome for the reconciliation process). The guard is NEVER cleared here.
    _finalize_batch_attempt(store, status=status, day_verdict=day_verdict,
                            completed_at_utc=_utc_now_iso())

    out = {
        "status": status, "mode": "EXECUTE_PREPARED_DEMO_BATCH",
        "pilot_id": args.pilot_id, "date": args.date, "day_verdict": day_verdict,
        "blockers": [], "payload_fingerprint": fingerprint,
        "execution_authorized": True, "execution_batch_authorized": True,
        "transport_constructed": state["transport_constructed"],
        "execute_daily_native_called": state["executor_called"],
        "accepted_count": len(result.accepted), "rejected_count": len(result.rejected),
        "ambiguous_count": len(result.ambiguous),
        "sender_call_count": result.sender_call_count,
        "order_post_count": result.order_post_count,
        "amend_post_count": 0, "cancel_post_count": 0, "live_order_post_count": 0,
        "live_trading_authorized": False, "pilot_advanced": pilot_advanced,
        **feas_evidence,
    }
    print(json.dumps(out, ensure_ascii=False, sort_keys=True))
    return exit_code


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = args.test_output_root

    # TASK-014CH2 (+FIX1): explicit opt-in, terminal Plan-only WebSocket-bound path.
    # Dispatched as the FIRST branch -- before the test-injected check, the
    # reconcile/reporting branch, the RUNNING gate (PilotStateStore), provider
    # construction, REST seed planning, source read and output write -- so its
    # mode-conflict validation precedes every existing side-effecting branch. It
    # builds the REST seed Plan only as a binding seed, binds it to the caller-supplied
    # WS evidence, validates via the CH1 consumer, writes one fresh canonical wrapper,
    # and stops. No execution, review, readiness, gate, native execution, reporting,
    # Pilot mutation, or REST fallback.
    # TASK-014CH3B2: review-only is dispatched as the FIRST operational branch (before
    # the CH2 Plan-only branch, the test-injected check, reconcile/reporting, the RUNNING
    # gate / PilotStateStore, provider construction, and any source/output read), so its
    # mode-conflict + path preflight precede every side-effecting branch. It reviews an
    # existing wrapper offline and stops; no execution/readiness/gate/native-execution/
    # Pilot/reporting/REST.
    # TASK-014: terminal, NON-SENDING dry-run preparation from CH4A artifacts. Dispatched
    # among the first branches (before reconcile/reporting, the RUNNING gate / PilotStateStore,
    # provider construction, and any transport): it only reads the three supplied artifacts and
    # builds the 50 order payload previews. No transport, execute_daily_native, POST,
    # authorization marker, or Pilot advance is ever reached.
    if args.prepare_from_ch4a:
        return _run_prepare_from_current_feasibility_artifacts(args)

    # TASK-014: explicit, execution-capable batch dispatch. Every fail-closed gate (flags,
    # token, fingerprint, host, credentials, Pilot state, prep PASS) is checked BEFORE any
    # transport is constructed or any order is sent; execute_daily_native() runs at most once.
    if args.execute_prepared_demo_batch:
        return _run_execute_prepared_demo_batch(args)

    if args.ws_bound_plan_review_only:
        return _run_ws_bound_plan_review_only(args)

    if args.ws_bound_plan_only:
        return _run_ws_bound_plan_only(args, output_root)

    # The manually-supplied action JSON is a test-only injected fixture and is
    # REFUSED as a production source.
    if args.test_injected_actions_json and not _is_test_root(args.test_output_root):
        print(json.dumps({"status": "REFUSED_TEST_ONLY_OPTION",
                          "detail": "--test-injected-actions-json is refused outside a test root"}))
        return EXIT_INVALID

    # reconcile-outputs-only: no planner, no transport.
    if args.reconcile_outputs_only:
        rep = nrep.reconcile_outputs_only(
            pilot_id=args.pilot_id, date=args.date, output_root=output_root,
            allow_notion_network=args.allow_notion_network,
            allow_discord_network=args.allow_discord_network)
        print(json.dumps(rep, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_OK

    # RUNNING gate.
    state = rd.PilotStateStore(args.pilot_id, output_root).read_state()
    if state is None or state.get("lifecycle_state") != rd.RUNNING:
        print(json.dumps({"status": nx.DAY_NOT_RUNNING,
                          "detail": "Pilot not RUNNING; run --mode start first",
                          "live_trading_authorized": False}, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_BLOCKED

    # Authoritative Forward Record source.
    try:
        forward_result = fs.load_primary_forward_strategy_result(
            run_date=args.date, repo_root=ROOT, forward_source_root=args.test_forward_source_root)
    except fs.ForwardSourceError as exc:
        print(json.dumps({"status": "INPUT_FAILURE", "detail": f"forward source invalid: {exc}"},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_INPUT_FAILURE

    # Plan-only (default): derive + classify, send nothing.
    if not args.send_orders_to_demo:
        provider = _build_production_provider()
        provider_built = provider is not None
        plan = planner.plan_strategy_native_actions(forward_result=forward_result, provider=provider)
        plan_label = ("PLAN_ONLY_READ_ONLY_DEMO_NETWORK" if provider_built
                      else plan.status)

        rejected_reasons: dict[str, int] = {}
        for r in plan.rejected_signals:
            reason = r.get("reason", "unknown")
            rejected_reasons[reason] = rejected_reasons.get(reason, 0) + 1

        # Planner-phase audit snapshot (BEFORE the review prices legacy marks +
        # re-reads rule evidence). Its ticker counts reflect ONLY the initial Strategy
        # planner pricing; they are exposed as planner_ticker_* (TASK-014CD_FIX2).
        planner_phase_audit = provider.audit() if hasattr(provider, "audit") else {}

        # CORRECTED audit semantics: matched/missing/non-trading/malformed are
        # computed over the REQUESTED target symbols, NOT the full catalog cache.
        requested_target_symbols = [tp.get("symbol") for tp in plan.target_positions]
        _lookup_reasons = {"no_instrument_rule", "no_market_price",
                           "malformed_instrument_rule", "qty_floored_to_zero"}
        requested_target_symbols += [r.get("symbol") for r in plan.rejected_signals
                                     if r.get("reason") in _lookup_reasons]
        if hasattr(provider, "match_targets"):
            target_match = provider.match_targets(requested_target_symbols)
        else:
            target_match = {"requested_target_symbol_count": len(requested_target_symbols),
                            "matched_instrument_rule_count": 0, "missing_instrument_rule_count": 0,
                            "non_trading_instrument_count": 0, "malformed_instrument_rule_count": 0}

        # ACTIVE policy: Strategy-native V1 portfolio review (production-shaped,
        # multi-symbol, non-dispatching). Legacy protected positions are separated
        # and never block planning. The one-shot tiny gate is retained ONLY as an
        # isolated, non-authoritative review for visibility.
        strategy_native_review = (build_active_v1_review(
            provider=provider, plan=plan, pilot_id=args.pilot_id, date=args.date)
            if provider_built else None)
        # Post-review audit: stable fields are unchanged; the ticker counts now reflect
        # the COMPLETE account pricing (strategy + legacy). The canonical top-level
        # network counters are mirrored from strategy_native_review.network_audit.
        provider_audit = provider.audit() if hasattr(provider, "audit") else {}
        network_top = _canonical_network_top_level(
            review=strategy_native_review, planner_phase_audit=planner_phase_audit,
            instrument_metadata_get_count=provider_audit.get("instrument_metadata_public_get_count", 0))
        try:
            open_positions = list(provider.open_positions()) if provider_built else []
        except Exception:  # noqa: BLE001
            open_positions = []
        isolated_one_shot_review = gate.evaluate_execution_gate(
            plan=plan, open_positions=open_positions, pilot_id=args.pilot_id, date=args.date,
            forward_fingerprint=_forward_fingerprint_of(plan), rule_provider=provider).to_dict()

        out = {"status": plan_label if plan.available else plan.status,
               "pilot_id": args.pilot_id, "date": args.date, "planner": plan.to_dict(),
               "active_policy": v1.POLICY_ACTIVE_STRATEGY_NATIVE_V1,
               "strategy_native_policy_active": True,
               "strategy_native_review": strategy_native_review,
               # The one-shot SOLUSDT delegation gate is an ISOLATED test utility,
               # NOT the active V1 policy. Retained for visibility only.
               "isolated_one_shot_review": isolated_one_shot_review,
               "isolated_one_shot_review_is_authoritative": False,
               # TASK-014CD explicit top-level evidence statuses (Plan-only).
               "margin_model_status": (strategy_native_review or {}).get("margin_model_status"),
               "network_audit_status": (strategy_native_review or {}).get("network_audit_status"),
               "price_freshness_status": (strategy_native_review or {}).get("price_freshness_status"),
               # TASK-014CE explicit top-level account-mode / risk-tier / clock statuses.
               "account_margin_mode":
                   ((strategy_native_review or {}).get("account_mode_evidence") or {}).get("margin_mode"),
               "account_mode_evidence_status":
                   ((strategy_native_review or {}).get("account_mode_evidence") or {})
                   .get("account_mode_evidence_status"),
               "projected_margin_model_status":
                   (strategy_native_review or {}).get("projected_margin_model_status"),
               "exchange_clock_bracket_available":
                   ((strategy_native_review or {}).get("exchange_clock_evidence") or {})
                   .get("exchange_clock_bracket_available"),
               "per_symbol_exchange_quote_timestamp_available":
                   ((strategy_native_review or {}).get("exchange_clock_evidence") or {})
                   .get("per_symbol_exchange_quote_timestamp_available"),
               "execution_readiness_blockers":
                   (strategy_native_review or {}).get("execution_readiness_blockers"),
               "plan_valid": plan.available and bool(plan.sizing_verification.get("verified", False)),
               "execution_batch_present": bool(strategy_native_review),
               "execution_batch_authorized": False,
               "execution_authorized": False,
               "execution_ready": False,
               "sender_reachable": False,
               "native_dispatch_disabled": True,
               "send_path_refused": True,
               "detail": "plan preview only; the ACTIVE Strategy-native V1 portfolio review preserves the "
                         "full multi-symbol plan. Legacy protected positions are untouched and never block "
                         "V1 planning but count toward account-level feasibility. No order is dispatched "
                         "and no execution batch is authorized in this task.",
               "network_attempted": provider_built,
               "read_only_network": provider_built,
               "market_price_source": provider_audit.get("market_price_source", "unavailable"),
               "instrument_rule_source": provider_audit.get("instrument_rule_source", "unavailable"),
               # Full catalog cache count reported separately from requested matches.
               "instrument_rule_cache_count": provider_audit.get("instrument_rule_cache_count", 0),
               "requested_target_symbol_count": target_match["requested_target_symbol_count"],
               "matched_instrument_rule_count": target_match["matched_instrument_rule_count"],
               "missing_instrument_rule_count": target_match["missing_instrument_rule_count"],
               "non_trading_instrument_count": target_match["non_trading_instrument_count"],
               "malformed_instrument_rule_count": target_match["malformed_instrument_rule_count"],
               "rejected_reason_counts": rejected_reasons,
               # Real network accounting (actual calls, not expected).
               "instrument_metadata_public_get_count":
                   provider_audit.get("instrument_metadata_public_get_count", 0),
               # CD-only private read-only fallbacks; the canonical complete-account
               # counts in network_top (when present) override these (TASK-014CE_FIX1).
               "wallet_private_read_only_get_count":
                   provider_audit.get("wallet_private_read_only_get_count", 0),
               "positions_private_read_only_get_count":
                   provider_audit.get("positions_private_read_only_get_count", 0),
               "total_private_read_only_get_count":
                   provider_audit.get("total_private_read_only_get_count", 0),
               # ONE canonical complete-account network schema. The top-level counters
               # MIRROR strategy_native_review.network_audit (complete account: instrument
               # + ticker + server-time + risk-limit public GETs; account-info + wallet +
               # positions private GETs). The planner-only phase is planner_ticker_*.
               **network_top,
               # Explicit dispatcher call counts from the non-dispatching architecture.
               "execute_daily_native_called": False,
               "execute_daily_native_call_count": 0,
               "transport_sender_call_count": 0,
               "order_endpoint_called": False,
               "order_post_count": 0,
               "amend_post_count": 0,
               "cancel_post_count": 0,
               "live_endpoint_called": False,
               "live_trading_authorized": False}
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        if plan.status == planner.STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT:
            return EXIT_V1_CAPITAL_BASE_CONFLICT
        if plan.status == planner.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED:
            return EXIT_V1_CAPITAL_BASE_UNVERIFIED
        return EXIT_OK if plan.available else EXIT_PLANNER_UNAVAILABLE

    # --send-orders-to-demo: NON-dispatching. TASK-014CC.
    # The native surface produces the ACTIVE Strategy-native V1 portfolio review +
    # a production-shaped (multi-symbol) execution BATCH, then FAILS CLOSED: the
    # batch is NOT authorized in this task. It constructs NO order transport, calls
    # NO execute_daily_native, and dispatches nothing. A future task defines the
    # human authorization + staged Demo batch execution protocol.
    provider = _build_production_provider()
    plan = planner.plan_strategy_native_actions(forward_result=forward_result, provider=provider)
    if plan.status == planner.STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT:
        print(json.dumps({"status": planner.STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT,
                          "pilot_id": args.pilot_id, "date": args.date, "send_refused": True,
                          "detail": "V1 capital base sources disagree; no order sent",
                          "planner": plan.to_dict(), "live_trading_authorized": False},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_V1_CAPITAL_BASE_CONFLICT
    if plan.status == planner.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED:
        print(json.dumps({"status": planner.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED,
                          "pilot_id": args.pilot_id, "date": args.date, "send_refused": True,
                          "detail": "V1 capital base unresolvable; no order sent",
                          "planner": plan.to_dict(), "live_trading_authorized": False},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_V1_CAPITAL_BASE_UNVERIFIED

    review = build_active_v1_review(provider=provider, plan=plan,
                                    pilot_id=args.pilot_id, date=args.date)
    out = {
        "status": "STRATEGY_NATIVE_V1_EXECUTION_BATCH_NOT_AUTHORIZED",
        "pilot_id": args.pilot_id, "date": args.date,
        "active_policy": v1.POLICY_ACTIVE_STRATEGY_NATIVE_V1,
        "strategy_native_policy_active": True,
        "planner": plan.to_dict(),
        "strategy_native_review": review,
        "plan_valid": review["plan_valid"],
        "execution_batch_present": True,
        "execution_batch_authorized": False,
        "execution_authorized": False,
        "execution_ready": False,
        "sender_reachable": False,
        "native_dispatch_disabled": True,
        "send_path_refused": True,
        "execute_daily_native_called": False,
        "execute_daily_native_call_count": 0,
        "transport_sender_call_count": 0,
        "order_endpoint_called": False,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_endpoint_called": False,
        "live_trading_authorized": False,
        "detail": ("ACTIVE Strategy-native V1 portfolio: a production-shaped multi-symbol execution "
                   "batch was built for review but is NOT authorized in this task. No order dispatched; "
                   "no transport constructed; Live denied."),
    }
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_BLOCKED  # batch not authorized; native surface dispatches nothing


if __name__ == "__main__":
    raise SystemExit(main())
