"""scripts/generate_demo_strategy_ws_binding_fixture.py
TASK-014CG_FIX1: standalone OFFLINE canonical-binding fixture generator + validator.

Produces, with NO network and NO credentials, a self-consistent set of canonical
fixtures and runs the production binder over them:

  * a canonical 50-action Plan-only fixture (25 long / 25 short, +/-0.02 weights,
    fixed 10000-USDT capital);
  * a canonical NEW-VERSION (canonical_binding_schema_version=2) 52-symbol public
    WebSocket evidence fixture (50 Strategy symbols + EDUUSDT/POLYXUSDT) carrying
    authoritative active policy/strategy/date/symbol-source-fingerprint provenance
    and recomputable per-symbol source-message fingerprints;
  * the canonical bound Plan artifact (50 target positions priced at the exact
    WebSocket-bound lastPrice).

It proves 50/50 COMPLETE, zero network counts and zero order/amend/cancel/live.
It imports no order/transport sender and opens no socket.

    python scripts/generate_demo_strategy_ws_binding_fixture.py \
        --out-dir <outside-repository-temp-directory>
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_public_ws_ticker_evidence as ws  # noqa: E402
from src import demo_strategy_native_ws_price_binding as wb  # noqa: E402
from src import demo_strategy_pilot_readiness as rd  # noqa: E402

STRATEGY_50 = sorted({f"SYM{i:02d}USDT" for i in range(50)})
LEGACY_2 = ["EDUUSDT", "POLYXUSDT"]
DATE = "2026-06-22"
REQ_ID = "cf-public-ticker"
SYNTHETIC_CE_SHA = "sha256:" + "0" * 64


def build_ws_fixture(now_ns: int, *, last_price: str = "100.5") -> dict:
    universe = ws.derive_required_symbol_universe(
        strategy_target_symbols=STRATEGY_50, observed_legacy_symbols=LEGACY_2,
        protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        strategy_source_reference="cg_fix1_fixture", legacy_source_reference="cg_fix1_fixture")
    b = ws.PublicWsTickerEvidenceBuilder(
        universe=universe, clock_offset_seconds="0.0068",
        clock_offset_status="CLOCK_OFFSET_AVAILABLE",
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        stale_threshold_ms=10_000)
    b.record_connection_success(0)
    b.record_subscription_request(52, request_id=REQ_ID, generation=0)
    b.ingest_subscription_ack({"op": "subscribe", "success": True, "req_id": REQ_ID},
                              connection_generation=0, received_epoch_ns=now_ns)
    base = int(now_ns / 1e6)
    for i, sym in enumerate(universe["symbols"]):
        b.ingest_data_message(
            {"topic": f"tickers.{sym}", "type": "snapshot", "ts": base - i, "cs": 1000 + i,
             "data": {"symbol": sym, "lastPrice": last_price}},
            local_received_epoch_ns=now_ns, local_monotonic_received_ns=now_ns,
            connection_generation=0)
    strategy_source_provenance = {
        "strategy_provenance_status": ws.STRATEGY_SOURCE_PROVENANCE_AUTHORITATIVE,
        "active_policy": ws.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
        "active_strategy": ws.EXPECTED_STRATEGY_NAME,
        "requested_strategy_date": DATE,
        "strategy_symbol_count": 50,
        "strategy_symbols": STRATEGY_50,
        "strategy_symbol_source_fingerprint":
            ws.canonical_strategy_symbol_set_fingerprint(STRATEGY_50),
        "ce_source_artifact_sha256": SYNTHETIC_CE_SHA,
        "ce_evidence_fingerprint": None,
        "strategy_provenance_failures": [],
    }
    return b.build_artifact(
        finalize_epoch_ns=now_ns + 1_000_000,
        legacy_position_provenance={
            "symbol_universe_source_status": ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE},
        strategy_source_provenance=strategy_source_provenance,
        dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE, require_complete=True,
        allow_real_network=True,
        completion_meta={"collection_terminated_reason": ws.TERMINATED_COMPLETE_AND_ACKED})


def build_plan_fixture(*, rest_price: str = "100.0") -> dict:
    targets = []
    for i, sym in enumerate(STRATEGY_50):
        side = "long" if i % 2 == 0 else "short"
        weight = "0.02" if side == "long" else "-0.02"
        targets.append({"symbol": sym, "side": side, "price": rest_price,
                        "target_weight": weight, "target_notional": "200",
                        "qty": "2", "qty_step": "0.001"})
    actions = [{"symbol": t["symbol"], "side": "Buy" if t["side"] == "long" else "Sell",
                "qty": "2", "intent": "OPEN", "reduce_only": False,
                "notional_usdt": "200", "action_seq": i}
               for i, t in enumerate(targets)]
    return {"date": DATE, "active_policy": ws.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
            "strategy_native_policy_active": True,
            "strategy_native_review": {"active_strategy": ws.EXPECTED_STRATEGY_NAME},
            "planner": {"status": "STRATEGY_NATIVE_ACTIONS_PLANNED",
                        "action_count": len(actions), "actions": actions,
                        "sizing_verification": {"capital_base_usd": 10000,
                                                "sizing_mode": "V1_BASELINE_TARGET_WEIGHT_TRANSLATION"},
                        "target_positions": targets}}


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(
        description="TASK-014CG_FIX1 offline canonical-binding fixture generator.")
    ap.add_argument("--out-dir", required=True,
                    help="Output directory (use a path OUTSIDE the repository).")
    ap.add_argument("--binding-epoch-ns", default=None,
                    help="Deterministic binding epoch (ns); default = a near-now value.")
    args = ap.parse_args(argv)

    os.makedirs(args.out_dir, exist_ok=True)
    now_ns = int(args.binding_epoch_ns) if args.binding_epoch_ns else time.time_ns()
    # The WS evidence ts are anchored slightly before the binding epoch (fresh).
    ws_now_ns = now_ns - 1_000_000

    ws_fixture = build_ws_fixture(ws_now_ns)
    plan_fixture = build_plan_fixture()

    plan_path = os.path.join(args.out_dir, "plan_fixture.json")
    ws_path = os.path.join(args.out_dir, "ws_evidence_fixture.json")
    bound_path = os.path.join(args.out_dir, "canonical_bound_plan.json")

    with open(plan_path, "w", encoding="utf-8") as fh:
        json.dump(plan_fixture, fh, ensure_ascii=False, indent=2, sort_keys=True)
    ws_bytes = json.dumps(ws_fixture, ensure_ascii=False, indent=2, sort_keys=True).encode("utf-8")
    with open(ws_path, "wb") as fh:
        fh.write(ws_bytes)

    wrapper = wb.build_ws_bound_plan_artifact(
        plan_artifact=plan_fixture, ws_artifact=ws_fixture, ws_artifact_path=ws_path,
        ws_artifact_sha256=wb.compute_file_sha256(ws_bytes), binding_epoch_ns=now_ns)
    with open(bound_path, "w", encoding="utf-8") as fh:
        json.dump(wrapper, fh, ensure_ascii=False, indent=2, sort_keys=True)

    cbp = wrapper.get("canonical_bound_plan") or {}
    tps = (cbp.get("planner") or {}).get("target_positions") or []
    all_ws_priced = all(
        tp.get("price") == (tp.get("price_evidence") or {}).get("selected_price")
        for tp in tps) and len(tps) == 50
    na = wrapper["binding_network_audit"]
    summary = {
        "plan_fixture": plan_path,
        "ws_evidence_fixture": ws_path,
        "canonical_bound_plan": bound_path,
        "overall_binding_status": wrapper["overall_binding_status"],
        "wrapper_parity_status": wrapper["wrapper_parity_status"],
        "canonical_revised_action_count": wrapper["canonical_revised_action_count"],
        "bound_action_count": wrapper["bound_action_count"],
        "failed_action_count": wrapper["failed_action_count"],
        "all_50_active_prices_are_ws_bound": all_ws_priced,
        "execution_grade_freshness_complete": wrapper["execution_grade_freshness_complete"],
        "execution_batch_authorized": wrapper["execution_batch_authorized"],
        "execution_ready": wrapper["execution_ready"],
        "sender_reachable": wrapper["sender_reachable"],
        "order_post_count": wrapper["order_post_count"],
        "amend_post_count": wrapper["amend_post_count"],
        "cancel_post_count": wrapper["cancel_post_count"],
        "live_order_post_count": wrapper["live_order_post_count"],
        "binding_network_audit": na,
        "canonical_bound_plan_fingerprint": wrapper["canonical_bound_plan_fingerprint"],
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2, sort_keys=True))

    ok = (wrapper["canonical_revised_action_count"] == 50
          and wrapper["bound_action_count"] == 50
          and wrapper["failed_action_count"] == 0
          and all_ws_priced
          and wrapper["execution_grade_freshness_complete"] is True
          and wrapper["execution_batch_authorized"] is False
          and wrapper["order_post_count"] == 0
          and na == {"private_http_count": 0, "public_http_count": 0,
                     "websocket_connection_count": 0, "order_endpoint_count": 0})
    return 0 if ok else 1


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
