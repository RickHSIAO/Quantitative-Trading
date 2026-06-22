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


def _build_production_provider():
    """Build the canonical account/market provider from the existing read-only
    Demo client + market guard + instrument rules. Fails closed (returns None) if
    real reads are unavailable. Runs ONLY on the VPS under explicit authorization.

    Instrument metadata is fetched via the canonical DemoReadOnlyClient.get_instruments_info()
    public read-only GET (/v5/market/instruments-info, category=linear). The data is
    batch-loaded once per run and cached in _instruments. No API secret is required for
    this endpoint; pagination is handled by the client."""
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
            self._client = DemoReadOnlyClient(allow_real_network=True)
            self._guard = DemoMarketPriceGuard(allow_real_network=True)
            self._wallet = self._client.get_wallet_balance()
            self._positions = self._client.get_open_positions()
            self._raw_instruments = self._client.get_instruments_info()
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
            self._public_get_count = 1

        def equity_usd(self) -> float:
            return float(self._wallet.equity_usd)

        def available_balance_usd(self) -> float:
            return float(self._wallet.available_balance_usd)

        def open_positions(self):
            return [DemoOpenPosition(symbol=p.symbol, side=p.side, quantity=float(p.quantity),
                                     entry_price=float(p.entry_price), stop_price=float(p.stop_price))
                    for p in self._positions]

        def market_price(self, symbol: str):
            try:
                prices = self._guard.fetch_market_prices([symbol])
                mp = prices.get(symbol)
                return float(mp.realtime_market_price) if mp and mp.is_usable() else None
            except Exception:  # noqa: BLE001
                return None

        def instrument_rule(self, symbol: str):
            return self._instruments.get(symbol)

        def audit(self) -> dict:
            valid_count = sum(1 for v in self._instruments.values() if v is not None)
            return {
                "instrument_rule_source": "DemoReadOnlyClient.get_instruments_info() -> /v5/market/instruments-info (public GET, category=linear)",
                "market_price_source": "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
                "instrument_rule_cache_count": len(self._raw_instruments),
                "valid_instrument_rule_count": valid_count,
                "non_trading_instrument_count": self._non_trading_count,
                "malformed_instrument_rule_count": self._malformed_count,
                "public_market_get_count": self._public_get_count,
            }

    try:
        return _RealDemoProvider()
    except Exception:  # noqa: BLE001
        return None


# ---------------------------------------------------------------------------
# Testable orchestrator (planner -> execution -> reporting -> advancement)
# ---------------------------------------------------------------------------


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
    """Plan -> execute -> (on unambiguous) finalize reporting -> advance once.

    Pure orchestration over injected planner inputs / transport / reporting deps
    so it is fully testable offline. Advancement happens AT MOST once and only
    after the day is unambiguous AND Excel built OK. Refuses to execute unless V1
    baseline sizing is verified."""
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
                   help="actually send eligible orders to Bybit DEMO (else plan-only, no network)")
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
        target_count = plan.sizing_verification.get("target_symbol_count", 0)
        matched = provider_audit.get("valid_instrument_rule_count", 0) if provider_audit else 0

        out = {"status": plan_label if plan.available else plan.status,
               "pilot_id": args.pilot_id, "date": args.date, "planner": plan.to_dict(),
               "detail": "plan preview only; pass --send-orders-to-demo to execute on Bybit Demo",
               "network_attempted": provider_built,
               "read_only_network": provider_built,
               "market_price_source": provider_audit.get("market_price_source", "unavailable"),
               "instrument_rule_source": provider_audit.get("instrument_rule_source", "unavailable"),
               "instrument_rule_cache_count": provider_audit.get("instrument_rule_cache_count", 0),
               "requested_target_symbol_count": len(plan.target_positions) + len(plan.rejected_signals),
               "matched_instrument_rule_count": matched,
               "missing_instrument_rule_count": rejected_reasons.get("no_instrument_rule", 0),
               "non_trading_instrument_count": provider_audit.get("non_trading_instrument_count", 0),
               "malformed_instrument_rule_count": provider_audit.get("malformed_instrument_rule_count", 0),
               "rejected_reason_counts": rejected_reasons,
               "public_market_get_count": provider_audit.get("public_market_get_count", 0),
               "private_read_only_get_count": 2 if provider_built else 0,
               "order_endpoint_called": False,
               "order_post_count": 0,
               "live_endpoint_called": False,
               "live_trading_authorized": False}
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        if plan.status == planner.STATUS_V1_BASELINE_CAPITAL_BASE_CONFLICT:
            return EXIT_V1_CAPITAL_BASE_CONFLICT
        if plan.status == planner.STATUS_V1_BASELINE_CAPITAL_BASE_UNVERIFIED:
            return EXIT_V1_CAPITAL_BASE_UNVERIFIED
        return EXIT_OK if plan.available else EXIT_PLANNER_UNAVAILABLE

    # Authorized Demo execution.
    creds = load_demo_credentials(os.environ)
    if not creds.usable:
        print(json.dumps({"status": "BLOCKED", "detail": "Demo credentials absent; cannot send"},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_BLOCKED
    provider = _build_production_provider()

    # Pre-verify V1 baseline sizing + capital base BEFORE constructing the order
    # transport. The send path REFUSES while either is unverified or conflicting.
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
    if plan.status == planner.STATUS_V1_BASELINE_SIZING_UNVERIFIED \
            or not plan.sizing_verification.get("verified", False):
        print(json.dumps({"status": planner.STATUS_V1_BASELINE_SIZING_UNVERIFIED,
                          "pilot_id": args.pilot_id, "date": args.date, "send_refused": True,
                          "detail": "first Demo execution blocked until V1 baseline sizing parity is "
                                    "verified; no order sent", "planner": plan.to_dict(),
                          "live_trading_authorized": False},
                         ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_V1_SIZING_UNVERIFIED
    if not plan.available:
        print(json.dumps({"status": plan.status, "detail": plan.detail, "planner": plan.to_dict(),
                          "live_trading_authorized": False}, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_PLANNER_UNAVAILABLE

    transport = RealDemoOrderTransport(api_key=os.environ.get("BYBIT_DEMO_API_KEY", ""),
                                       api_secret=os.environ.get("BYBIT_DEMO_API_SECRET", ""),
                                       recv_window=creds.recv_window)
    out = orchestrate_native_daily(
        pilot_id=args.pilot_id, date=args.date, forward_result=forward_result, provider=provider,
        transport=transport, output_root=output_root, advance_on_success=args.advance_on_success,
        allow_notion_network=args.allow_notion_network, allow_discord_network=args.allow_discord_network,
        plan=plan)
    print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    if out.get("status") == planner.STATUS_PLANNER_UNAVAILABLE:
        return EXIT_PLANNER_UNAVAILABLE
    return EXIT_AMBIGUOUS if out.get("day_verdict") == nx.DAY_AMBIGUOUS else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
