"""TASK-014BX -- production strategy-native daily Bybit Demo execution command.

Pipeline for one Pilot date:
    1. read the RUNNING Pilot state (execution-authorized; Live denied);
    2. load + validate the authoritative Primary Forward Record result for the
       date (fails closed on missing/stale/shadow/mismatched evidence);
    3. load the strategy's OWN desired actions for the date (strategy-native
       symbol/side/qty/intent/reduce-only) -- this command never invents or caps
       sizing; absent strategy actions fail closed;
    4. run all hard-safety / endpoint / protected-symbol / idempotency checks;
    5. send eligible orders ONLY to Bybit Demo (only under --send-orders-to-demo);
    6. reconcile every submission to an unambiguous exchange state;
    7. record proposed / accepted / rejected actions, order ids, fills, fees, and
       request/response fingerprints in append-only ledgers;
    8. evaluate whether the date counts as a successful Pilot day and advance the
       counter AT MOST once; COMPLETED after exactly 7 accepted dates.

Default mode is a NO-NETWORK plan preview that sends nothing. Real Demo orders
are sent ONLY when --send-orders-to-demo is supplied AND the Pilot is RUNNING.
Live trading is never enabled. Notion/Discord delivery is recorded separately;
a delivery failure never re-runs strategy execution.

Reuses the Demo-only endpoint guard and signed transport verbatim from the
single-real-demo-order adapter; imports neither main, src.risk nor BybitExecutor.
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

from src import demo_strategy_pilot_native_execution as nx  # noqa: E402
from src import demo_strategy_pilot_readiness as rd  # noqa: E402
from src import demo_strategy_pilot_forward_source as fs  # noqa: E402
from src.demo_only_tiny_execution_adapter_single_real_demo_order import (  # noqa: E402
    DEMO_BASE_URL, DEMO_HOST, EP_ORDER_REALTIME, EP_ORDER_HISTORY,
    RealDemoHttpTransport, assert_demo_url, host_of, load_demo_credentials,
    _NoRedirectHandler,
)

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3
EXIT_AMBIGUOUS = 6


def _load_actions(path: str) -> list[nx.StrategyNativeAction]:
    with open(path, "r", encoding="utf-8") as fh:
        raw = json.load(fh)
    items = raw.get("actions", raw) if isinstance(raw, Mapping) else raw
    actions: list[nx.StrategyNativeAction] = []
    for i, a in enumerate(items or []):
        actions.append(nx.StrategyNativeAction(
            symbol=str(a.get("symbol", "")).upper(),
            side=str(a.get("side", "")),
            qty=str(a.get("qty", "0")),
            intent=str(a.get("intent", nx.INTENT_OPEN)),
            reduce_only=bool(a.get("reduce_only", False)),
            notional_usdt=str(a.get("notional_usdt", "")),
            position_idx=int(a.get("position_idx", 0)),
            record_category=str(a.get("record_category", "STRATEGY_PILOT")),
            action_seq=int(a.get("action_seq", i)),
            source_reference=str(a.get("source_reference", "")),
        ))
    return actions


class RealDemoOrderTransport:
    """Real Bybit DEMO transport: signed POST create + signed GET reconcile.

    Demo host only (the guard rejects any other host). Holds the Demo secret
    privately; the secret is never returned, printed, or serialized. Constructed
    ONLY when the operator passes --send-orders-to-demo.
    """

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
            "X-BAPI-TIMESTAMP": ts, "X-BAPI-RECV-WINDOW": self._recv_window,
        })
        with self._opener.open(req, timeout=10) as resp:
            if host_of(resp.geturl()) != DEMO_HOST:
                raise RuntimeError("reconcile response host mismatch")
            return json.loads(resp.read().decode("utf-8"))

    def reconcile(self, *, order_link_id: str) -> dict[str, Any]:
        resp = self._signed_get(EP_ORDER_REALTIME,
                                {"category": "linear", "orderLinkId": order_link_id})
        item = (resp.get("result") or {}).get("list") or []
        if item:
            return resp
        return self._signed_get(EP_ORDER_HISTORY,
                               {"category": "linear", "orderLinkId": order_link_id})


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(prog="run_demo_strategy_pilot_native_daily.py",
                                description="Strategy-native daily Bybit Demo execution.")
    p.add_argument("--pilot-id", required=True)
    p.add_argument("--date", required=True, help="Pilot run date YYYY-MM-DD")
    p.add_argument("--strategy-actions-json", required=True,
                   help="path to the strategy's OWN desired actions for the date")
    p.add_argument("--send-orders-to-demo", action="store_true",
                   help="actually send eligible orders to Bybit DEMO (else plan-only, no network)")
    p.add_argument("--advance-on-success", action="store_true",
                   help="advance the successful-day counter when the date is clean")
    p.add_argument("--test-output-root", default=None, help="TEST-ONLY output root")
    p.add_argument("--test-forward-source-root", default=None, help="TEST-ONLY forward source root")
    p.add_argument("--json-only", action="store_true")
    return p


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    output_root = args.test_output_root

    # 1. RUNNING gate.
    state = rd.PilotStateStore(args.pilot_id, output_root).read_state()
    if state is None or state.get("lifecycle_state") != rd.RUNNING:
        out = {"status": nx.DAY_NOT_RUNNING, "detail": "Pilot not RUNNING; run --mode start first",
               "live_trading_authorized": False}
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_BLOCKED

    # 2. Authoritative Forward Record source gate.
    try:
        fs.load_primary_forward_strategy_result(
            run_date=args.date, repo_root=ROOT,
            forward_source_root=args.test_forward_source_root)
    except fs.ForwardSourceError as exc:
        out = {"status": "INPUT_FAILURE", "detail": f"forward source invalid: {exc}"}
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_INPUT_FAILURE

    # 3. Strategy-native actions (the strategy's OWN desired actions; never invented).
    try:
        actions = _load_actions(args.strategy_actions_json)
    except (OSError, json.JSONDecodeError, ValueError) as exc:
        out = {"status": "INPUT_FAILURE", "detail": f"unable to load strategy actions: {exc}"}
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_INPUT_FAILURE

    # 4/5. Choose transport. Default is plan-only with NO network.
    if args.send_orders_to_demo:
        creds = load_demo_credentials(os.environ)
        if not creds.usable:
            out = {"status": "BLOCKED", "detail": "Demo credentials absent; cannot send"}
            print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
            return EXIT_BLOCKED
        transport = RealDemoOrderTransport(
            api_key=os.environ.get("BYBIT_DEMO_API_KEY", ""),
            api_secret=os.environ.get("BYBIT_DEMO_API_SECRET", ""),
            recv_window=creds.recv_window)
        result = nx.execute_daily_native(pilot_id=args.pilot_id, date=args.date, actions=actions,
                                         transport=transport, output_root=output_root)
    else:
        # Plan-only: classify, send nothing.
        proposed = [{**nx.classify_action(a).to_dict(),
                     "order_link_id": a.order_link_id(args.pilot_id, args.date)} for a in actions]
        out = {"status": "PLAN_ONLY_NO_NETWORK", "pilot_id": args.pilot_id, "date": args.date,
               "proposed_count": len(proposed), "proposed": proposed,
               "detail": "plan preview only; pass --send-orders-to-demo to execute on Bybit Demo",
               "live_trading_authorized": False}
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return EXIT_OK

    out = result.to_dict()
    out["live_trading_authorized"] = False

    # 8/10/11. Successful-day advancement (only when clean and requested).
    if args.advance_on_success:
        adv = nx.advance_successful_day(pilot_id=args.pilot_id, date=args.date,
                                        day_verdict=result.day_verdict, output_root=output_root)
        out["advancement"] = adv

    if args.json_only or True:
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
    return EXIT_AMBIGUOUS if result.day_verdict == nx.DAY_AMBIGUOUS else EXIT_OK


if __name__ == "__main__":
    raise SystemExit(main())
