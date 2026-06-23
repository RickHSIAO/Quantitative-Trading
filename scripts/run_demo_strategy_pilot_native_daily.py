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
import hashlib
import hmac
import json
import os
import sys
import time
import urllib.parse
import urllib.request
from typing import Any, Mapping

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_strategy_pilot_action_planner as planner  # noqa: E402
from src import demo_strategy_pilot_execution_gate as gate  # noqa: E402 (ISOLATED one-shot test utility)
from src import demo_strategy_native_v1_portfolio as v1  # noqa: E402 (ACTIVE V1 policy)
from src import demo_strategy_native_margin_freshness_audit as md  # noqa: E402 (TASK-014CD evidence)
from src import demo_strategy_pilot_forward_source as fs  # noqa: E402
from src import demo_strategy_pilot_native_execution as nx  # noqa: E402
from src import demo_strategy_pilot_native_reporting as nrep  # noqa: E402
from src import demo_strategy_pilot_readiness as rd  # noqa: E402
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
            _ws = time.time()
            self._wallet = self._client.get_wallet_balance()
            _wr = time.time()
            self._wallet_get_count = 1
            _ps = time.time()
            self._positions = self._client.get_open_positions()
            _pr = time.time()
            self._positions_get_count = 1
            self._wallet_snapshot_started_at = _utc_iso(_ws)
            self._wallet_snapshot_received_at = _utc_iso(_wr)
            self._position_snapshot_started_at = _utc_iso(_ps)
            self._position_snapshot_received_at = _utc_iso(_pr)
            self._wallet_snapshot_received_epoch = _wr
            self._position_snapshot_received_epoch = _pr
            # One public batch instrument-metadata GET (category=linear, paginated).
            self._raw_instruments = self._client.get_instruments_info()
            self._instrument_metadata_get_count = 1
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
            return [DemoOpenPosition(symbol=p.symbol, side=p.side, quantity=float(p.quantity),
                                     entry_price=float(p.entry_price), stop_price=float(p.stop_price))
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
                account_margin_mode=None,  # /v5/account/info not in allowed read-only paths
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
                # Two separate HTTP responses -> never atomic; scope not proven.
                margin_snapshot_atomic=False, scope_proven_comparable=False)

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

    # --- TASK-014CD network-audit counts (request vs symbol vs cache) ---------
    network_audit = None
    if hasattr(provider, "network_audit_counters"):
        ctr = provider.network_audit_counters()
        strat_priced = sum(1 for s in price_by_symbol if price_by_symbol.get(s) is not None)
        legacy_priced = sum(1 for s in legacy_symbols
                            if legacy_mark_price_by_symbol.get(s) is not None)
        network_audit = md.build_network_audit(
            ticker_http_request_count=ctr["ticker_http_request_count"],
            ticker_requested_symbol_count=ctr["ticker_requested_symbol_count"],
            ticker_unique_symbol_count=ctr["ticker_unique_symbol_count"],
            ticker_cache_hit_count=ctr["ticker_cache_hit_count"],
            strategy_target_priced_symbol_count=strat_priced,
            legacy_mark_priced_symbol_count=legacy_priced)

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
        network_audit=network_audit)


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
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = args.test_output_root

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

        provider_audit = provider.audit() if hasattr(provider, "audit") else {}

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
               "ticker_public_get_count": provider_audit.get("ticker_public_get_count", 0),
               # TASK-014CD: request count distinct from symbol/cache counts.
               "ticker_http_request_count": provider_audit.get("ticker_http_request_count", 0),
               "ticker_requested_symbol_count": provider_audit.get("ticker_requested_symbol_count", 0),
               "ticker_unique_symbol_count": provider_audit.get("ticker_unique_symbol_count", 0),
               "ticker_cache_hit_count": provider_audit.get("ticker_cache_hit_count", 0),
               "total_public_get_count": provider_audit.get("total_public_get_count", 0),
               "wallet_private_read_only_get_count":
                   provider_audit.get("wallet_private_read_only_get_count", 0),
               "positions_private_read_only_get_count":
                   provider_audit.get("positions_private_read_only_get_count", 0),
               "total_private_read_only_get_count":
                   provider_audit.get("total_private_read_only_get_count", 0),
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
