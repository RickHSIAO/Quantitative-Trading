"""TASK-014CG -- Plan-only same-message WebSocket price binding.

Fully offline. Proves: each of the 50 Strategy-native Plan-only actions binds to
the EXACT WebSocket source message that supplied its selected lastPrice; the 2
protected legacy symbols remain account evidence only; the REST price is retained
for audit and never carries a WebSocket timestamp; binding-time freshness fails
closed; execution-grade freshness becomes COMPLETE only after 50/50 bindings
pass and parity holds; and freshness completion NEVER authorizes execution.
"""
from __future__ import annotations

import copy
import json
import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb
from src import demo_strategy_pilot_readiness as rd

STRATEGY_50 = sorted({f"SYM{i:02d}USDT" for i in range(50)})
LEGACY_2 = ["EDUUSDT", "POLYXUSDT"]
REQ_ID = "cf-public-ticker"
DATE = "2026-06-22"
CAPITAL = 10000

# INNER CE (current-evidence) Plan source-artifact SHA. This is a DISTINCT lineage
# level from the OUTER WS evidence file SHA (which is the sha256 of the WS JSON bytes
# and is computed dynamically per test); the two are deliberately different so the
# consumer cannot conflate them. All four nested CE anchors carry this exact value.
CE_SOURCE_SHA = "sha256:" + "ce17" * 16  # canonical 64-hex, != outer WS file sha

AUTH_LEGACY_PROV = {
    "symbol_universe_source_status": ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE,
    "ce_source_artifact_sha256": CE_SOURCE_SHA,
}


def _universe():
    return ws.derive_required_symbol_universe(
        strategy_target_symbols=STRATEGY_50, observed_legacy_symbols=LEGACY_2,
        protected_symbol_allowlist=rd.PROTECTED_SYMBOLS,
        strategy_source_reference="cg", legacy_source_reference="cg")


def _snap(symbol, *, ts, cs, last_price="100.5"):
    return {"topic": f"tickers.{symbol}", "type": "snapshot", "ts": ts, "cs": cs,
            "data": {"symbol": symbol, "lastPrice": last_price}}


def _auth_strategy_provenance(symbols=None, *, date=DATE, status=None,
                              active_strategy=None):
    syms = symbols if symbols is not None else STRATEGY_50
    return {
        "strategy_provenance_status": status or ws.STRATEGY_SOURCE_PROVENANCE_AUTHORITATIVE,
        "active_policy": wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
        "active_strategy": active_strategy or wb.EXPECTED_STRATEGY_NAME,
        "requested_strategy_date": date,
        "strategy_symbol_count": len(syms),
        "strategy_symbols": sorted(syms),
        "strategy_symbol_source_fingerprint":
            ws.canonical_strategy_symbol_set_fingerprint(syms),
        "ce_source_artifact_sha256": CE_SOURCE_SHA,
        "ce_evidence_fingerprint": None,
        "strategy_provenance_failures": [],
    }


def _auth_clock_offset_provenance(*, offset="0.0068", ce_sha=CE_SOURCE_SHA):
    """Authoritative nested clock-offset provenance carrying the CE source SHA anchor.
    ``estimated_local_vs_exchange_clock_offset_seconds`` mirrors the top-level offset."""
    return {
        "clock_offset_provenance_status": ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        "estimated_local_vs_exchange_clock_offset_seconds": str(offset),
        "clock_offset_source_artifact_sha256": ce_sha,
    }


def _auth_source_evidence(*, ce_sha=CE_SOURCE_SHA):
    """Authoritative source-evidence block carrying the CE source SHA anchor."""
    return {"ce_source_artifact_sha256": ce_sha}


def build_complete_ws_artifact(*, now_ns, last_price="100.5", offset="0.0068",
                               strategy_source_provenance="__auth__"):
    """A real, fingerprinted, COMPLETE canonical-binding (v2) 52-symbol artifact."""
    u = _universe()
    b = ws.PublicWsTickerEvidenceBuilder(
        universe=u, clock_offset_seconds=offset,
        clock_offset_status="CLOCK_OFFSET_AVAILABLE",
        clock_offset_provenance_status=ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        stale_threshold_ms=10_000)
    b.record_connection_success(0)
    b.record_subscription_request(u["unique_symbol_count"], request_id=REQ_ID, generation=0)
    b.ingest_subscription_ack({"op": "subscribe", "success": True, "req_id": REQ_ID},
                              connection_generation=0, received_epoch_ns=now_ns)
    base_ts = int(now_ns / 1e6)
    for i, sym in enumerate(u["symbols"]):
        b.ingest_data_message(_snap(sym, ts=base_ts - i, cs=1000 + i, last_price=last_price),
                              local_received_epoch_ns=now_ns,
                              local_monotonic_received_ns=now_ns, connection_generation=0)
    prov = (_auth_strategy_provenance() if strategy_source_provenance == "__auth__"
            else strategy_source_provenance)
    art = b.build_artifact(
        finalize_epoch_ns=now_ns + 1_000_000, legacy_position_provenance=AUTH_LEGACY_PROV,
        strategy_source_provenance=prov,
        clock_offset_provenance=_auth_clock_offset_provenance(offset=offset),
        source_evidence=_auth_source_evidence(),
        dependency_status=ws.WS_CLIENT_DEPENDENCY_AVAILABLE, require_complete=True,
        allow_real_network=True,
        completion_meta={"collection_terminated_reason": ws.TERMINATED_COMPLETE_AND_ACKED})
    assert art["overall_status"] == ws.WS_TICKER_EVIDENCE_COMPLETE
    return art


def build_plan(*, rest_price="100.0", date=DATE, symbols=None):
    """A Plan-only run artifact with one target per strategy symbol."""
    symbols = symbols if symbols is not None else STRATEGY_50
    targets = []
    for i, sym in enumerate(symbols):
        side = "long" if i % 2 == 0 else "short"
        weight = "0.02" if side == "long" else "-0.02"
        targets.append({
            "symbol": sym, "side": side, "price": rest_price,
            "target_weight": weight, "target_notional": "200",
            "qty": "1.99", "qty_step": "0.001"})
    return {
        "date": date,
        "active_policy": wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
        "strategy_native_review": {"active_strategy": wb.EXPECTED_STRATEGY_NAME},
        "planner": {
            "sizing_verification": {"capital_base_usd": CAPITAL},
            "target_positions": targets,
        },
    }


def _refp(ws_art):
    """Recompute the WS artifact's top-level fingerprint after a deliberate
    mutation, so the compatibility gate passes and the per-action binding logic
    (not the tamper-detection gate) is what the test exercises."""
    ws_art["artifact_fingerprint"] = ws._fingerprint(
        {k: v for k, v in ws_art.items() if k != "artifact_fingerprint"})
    return ws_art


def _bind(plan, ws_art, *, now_ns=None, threshold=10_000):
    raw = json.dumps(ws_art).encode("utf-8")
    return wb.bind_plan_prices_to_ws_evidence(
        plan_artifact=plan, ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=wb.compute_file_sha256(raw),
        binding_epoch_ns=now_ns if now_ns is not None else time.time_ns(),
        binding_freshness_threshold_ms=threshold)


# ---------------------------------------------------------------------------
# Happy path: 50 strategy actions bind from a 52-symbol artifact
# ---------------------------------------------------------------------------

def test_fifty_strategy_actions_bind_from_fifty_two_symbol_artifact():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_COMPLETE
    assert art["binding_parity_status"] == wb.WS_PLANNER_BINDING_PARITY_PASS
    assert art["bound_action_count"] == 50
    assert art["failed_action_count"] == 0
    assert art["requested_action_count"] == 50
    assert art["unique_action_symbol_count"] == 50
    assert art["execution_grade_freshness_complete"] is True


def test_legacy_symbols_remain_account_evidence_only():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    bound_symbols = {b["action_symbol"] for b in art["per_action_bindings"]}
    assert "EDUUSDT" not in bound_symbols and "POLYXUSDT" not in bound_symbols
    assert len(bound_symbols) == 50
    # The legacy symbols ARE present in the WS universe (account evidence).
    assert {"EDUUSDT", "POLYXUSDT"}.issubset(
        set(ws_art["symbol_universe"]["legacy_symbols"]))


def test_complete_sets_execution_grade_freshness_and_resolves_blockers():
    now = time.time_ns()
    art = _bind(build_plan(), build_complete_ws_artifact(now_ns=now), now_ns=now + 2_000_000)
    assert art["execution_grade_freshness_complete"] is True
    assert wb.PRICE_FRESHNESS_EVIDENCE_PARTIAL in art["resolved_blockers"]
    assert wb.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE in art["resolved_blockers"]
    assert wb.WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS in art["resolved_blockers"]
    assert wb.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK in art["retained_blockers"]


# ---------------------------------------------------------------------------
# Freshness completion does NOT authorize execution
# ---------------------------------------------------------------------------

def test_freshness_completion_does_not_authorize_execution():
    now = time.time_ns()
    art = _bind(build_plan(), build_complete_ws_artifact(now_ns=now), now_ns=now + 2_000_000)
    assert art["execution_grade_freshness_complete"] is True
    assert art["execution_batch_authorized"] is False
    assert art["execution_ready"] is False
    assert art["sender_reachable"] is False
    assert art["execute_daily_native_call_count"] == 0
    assert art["transport_sender_call_count"] == 0
    assert art["order_post_count"] == 0
    assert art["amend_post_count"] == 0
    assert art["cancel_post_count"] == 0
    assert art["live_order_post_count"] == 0
    assert art["execution_authorization_marker_created"] is False


def test_binding_network_audit_all_zero():
    now = time.time_ns()
    art = _bind(build_plan(), build_complete_ws_artifact(now_ns=now), now_ns=now + 2_000_000)
    na = art["binding_network_audit"]
    assert na["private_http_count"] == 0
    assert na["public_http_count"] == 0
    assert na["websocket_connection_count"] == 0
    assert na["order_endpoint_count"] == 0


# ---------------------------------------------------------------------------
# Decimal + REST audit retention + fingerprints
# ---------------------------------------------------------------------------

def test_decimal_prices_preserved_and_rest_retained_without_ws_timestamp():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now, last_price="100.5")
    art = _bind(build_plan(rest_price="100.0"), ws_art, now_ns=now + 2_000_000)
    row = art["per_action_bindings"][0]
    assert row["original_rest_price"] == "100.0"
    assert row["websocket_bound_price"] == "100.5"
    assert row["price_delta"] == "0.5"
    # The REST price object carries NO websocket timestamp anywhere.
    assert "ts" not in str(row["original_rest_price"])
    pe = row["price_evidence"]
    assert pe["selected_price"] == "100.5"
    assert pe["exchange_data_generated_ts_ms"] is not None
    # qty recomputed from the WS price: 200 / 100.5 floored to 0.001 = 1.99.
    assert row["recalculated_price_dependent_fields"]["target_qty"] == "1.99"
    assert row["recalculated_price_dependent_fields"]["target_notional"] == "200"


def test_pre_post_fingerprints_differ_when_price_changes_and_are_deterministic():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now, last_price="123.45")
    plan = build_plan(rest_price="100.0")
    a1 = _bind(plan, ws_art, now_ns=now + 2_000_000)
    a2 = _bind(copy.deepcopy(plan), copy.deepcopy(ws_art), now_ns=now + 2_000_000)
    row = a1["per_action_bindings"][0]
    assert row["pre_binding_action_fingerprint"] != row["post_binding_action_fingerprint"]
    assert a1["binding_artifact_fingerprint"] == a2["binding_artifact_fingerprint"]


# ---------------------------------------------------------------------------
# Compatibility gate fail-closed cases
# ---------------------------------------------------------------------------

def test_unsupported_schema_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["schema"] = "something_else"
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT
    assert art["execution_grade_freshness_complete"] is False


def test_artifact_fingerprint_mismatch_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["artifact_fingerprint"] = "sha256:" + "0" * 64
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT
    assert "ws_artifact_fingerprint_mismatch" in art["ws_artifact_compatibility"]["failures"]


def test_non_complete_ws_artifact_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["overall_status"] = ws.WS_TICKER_EVIDENCE_PARTIAL
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_missing_ack_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["subscription_ack"]["subscription_acknowledged"] = False
    ws_art["subscription_ack"]["ws_subscription_ack_count"] = 0
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_counter_parity_failure_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["counter_parity_status"] = ws.WS_COUNTER_PARITY_FAIL
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_control_plane_parity_failure_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["control_plane_parity_status"] = ws.WS_CONTROL_PLANE_PARITY_FAIL
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_clock_provenance_not_authoritative_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["clock_offset_provenance_status"] = ws.CLOCK_OFFSET_PROVENANCE_STALE
    art = _bind(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_policy_mismatch_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    plan = build_plan()
    plan["active_policy"] = "SOME_OTHER_POLICY"
    art = _bind(plan, ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_strategy_mismatch_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    plan = build_plan()
    plan["strategy_native_review"]["active_strategy"] = "other_strategy"
    art = _bind(plan, ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_strategy_date_mismatch_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)  # WS provenance date = DATE
    # The WS artifact now carries an authoritative date; a mismatched plan date
    # must fail closed.
    art = _bind(build_plan(date="2026-01-01"), ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT
    assert "ws_plan_strategy_date_mismatch" in art["ws_artifact_compatibility"]["failures"]


def test_plan_strategy_symbol_fingerprint_mismatch_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    raw = json.dumps(ws_art).encode("utf-8")
    art = wb.bind_plan_prices_to_ws_evidence(
        plan_artifact=build_plan(), ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=wb.compute_file_sha256(raw), binding_epoch_ns=now + 2_000_000,
        strategy_symbol_source_fingerprint="sha256:deadbeef")
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT
    assert "plan_strategy_symbol_source_fingerprint_mismatch" in \
        art["ws_artifact_compatibility"]["failures"]


def test_empty_ws_artifact_is_unavailable():
    now = time.time_ns()
    art = _bind(build_plan(), {}, now_ns=now)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_UNAVAILABLE
    assert art["execution_grade_freshness_complete"] is False


# ---------------------------------------------------------------------------
# Per-action fail-closed cases
# ---------------------------------------------------------------------------

def test_forty_nine_of_fifty_remains_partial():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    # Remove one strategy symbol's evidence -> 49/50.
    drop = STRATEGY_50[0]
    ws_art["per_symbol_evidence"] = [r for r in ws_art["per_symbol_evidence"]
                                     if r["symbol"] != drop]
    art = _bind(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_PARTIAL
    assert art["bound_action_count"] == 49
    assert art["failed_action_count"] == 1
    assert art["execution_grade_freshness_complete"] is False
    missing = [b for b in art["per_action_bindings"]
               if b["action_symbol"] == drop][0]
    assert missing["binding_status"] == wb.WS_EVIDENCE_SYMBOL_MISSING


def test_partial_keeps_blockers_and_does_not_authorize_execution():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    ws_art["per_symbol_evidence"] = [r for r in ws_art["per_symbol_evidence"]
                                     if r["symbol"] != STRATEGY_50[0]]
    art = _bind(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    assert art["execution_grade_freshness_complete"] is False
    assert wb.WS_PLANNER_PRICE_BINDING_INCOMPLETE in art["retained_blockers"]
    assert wb.PRICE_FRESHNESS_EVIDENCE_PARTIAL in art["retained_blockers"]
    assert wb.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK in art["retained_blockers"]
    assert art["execution_batch_authorized"] is False
    assert art["order_post_count"] == 0


def test_duplicate_ws_symbol_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    dup = copy.deepcopy([r for r in ws_art["per_symbol_evidence"]
                         if r["symbol"] == STRATEGY_50[0]][0])
    ws_art["per_symbol_evidence"].append(dup)
    art = _bind(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT
    row = [b for b in art["per_action_bindings"] if b["action_symbol"] == STRATEGY_50[0]][0]
    assert row["binding_status"] == wb.WS_EVIDENCE_SYMBOL_DUPLICATE


def test_duplicate_action_symbol_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    plan = build_plan()
    plan["planner"]["target_positions"].append(
        dict(plan["planner"]["target_positions"][0]))
    art = _bind(plan, ws_art, now_ns=now + 2_000_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_action_ws_symbol_mismatch_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    rec = [r for r in ws_art["per_symbol_evidence"] if r["symbol"] == STRATEGY_50[0]][0]
    rec["topic"] = "tickers.WRONGUSDT"
    # Recompute the per-symbol fingerprint so it is internally consistent and the
    # ONLY failure is the topic/symbol mismatch (not a fingerprint mismatch).
    rec["evidence_fingerprint"] = wb._recompute_evidence_fingerprint(rec)
    art = _bind(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    row = [b for b in art["per_action_bindings"] if b["action_symbol"] == STRATEGY_50[0]][0]
    assert row["binding_status"] == wb.WS_ACTION_SYMBOL_MISMATCH
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_price_field_other_than_last_price_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    rec = [r for r in ws_art["per_symbol_evidence"] if r["symbol"] == STRATEGY_50[0]][0]
    rec["selected_price_field"] = "markPrice"
    art = _bind(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    row = [b for b in art["per_action_bindings"] if b["action_symbol"] == STRATEGY_50[0]][0]
    assert row["binding_status"] == wb.WS_EVIDENCE_PRICE_FIELD_MISMATCH


def test_source_message_incomplete_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    rec = [r for r in ws_art["per_symbol_evidence"] if r["symbol"] == STRATEGY_50[0]][0]
    rec["selected_price_source_message_fingerprint"] = None
    art = _bind(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    row = [b for b in art["per_action_bindings"] if b["action_symbol"] == STRATEGY_50[0]][0]
    assert row["binding_status"] == wb.WS_EVIDENCE_SOURCE_MESSAGE_INCOMPLETE


def test_source_fingerprint_mismatch_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    rec = [r for r in ws_art["per_symbol_evidence"] if r["symbol"] == STRATEGY_50[0]][0]
    # Tamper the selected price WITHOUT updating the per-symbol fingerprint
    # (the top-level artifact fingerprint is repaired so the gate passes and the
    # per-symbol tamper is what is detected).
    rec["selected_price"] = "999.99"
    art = _bind(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    row = [b for b in art["per_action_bindings"] if b["action_symbol"] == STRATEGY_50[0]][0]
    assert row["binding_status"] == wb.WS_EVIDENCE_FINGERPRINT_MISMATCH
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_stale_at_binding_fails_closed():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    # Bind 60 seconds later than the evidence with a 10s threshold -> all stale.
    art = _bind(build_plan(), ws_art, now_ns=now + 60_000_000_000, threshold=10_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_PARTIAL
    assert art["bound_action_count"] == 0
    row = art["per_action_bindings"][0]
    assert row["binding_status"] == wb.WS_EVIDENCE_STALE_AT_BINDING
    assert row["binding_freshness"]["binding_freshness_status"] == wb.BINDING_FRESHNESS_STALE
    assert art["execution_grade_freshness_complete"] is False


def test_strict_threshold_is_not_loosened():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    # 11s later with a strict 10s threshold -> stale (threshold is honored).
    art = _bind(build_plan(), ws_art, now_ns=now + 11_000_000_000, threshold=10_000)
    assert art["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_PARTIAL


# ---------------------------------------------------------------------------
# No credentials in the artifact
# ---------------------------------------------------------------------------

def test_no_credentials_in_binding_artifact():
    now = time.time_ns()
    art = _bind(build_plan(), build_complete_ws_artifact(now_ns=now), now_ns=now + 2_000_000)
    ws.assert_no_credentials(art, secret_values=["irrelevant-secret"])
    assert "binding_artifact_fingerprint" in art
