"""TASK-014CG_FIX1 -- canonical WebSocket-bound Plan-only artifact.

Proves the audit-rejected sidecar is corrected: a complete canonical revised
Plan-only artifact whose 50 active Strategy target-position prices ARE the exact
WebSocket-bound lastPrice, with mandatory authoritative strategy provenance,
mandatory recomputed symbol-source fingerprint, recomputable source-message
fingerprints, rebuilt price-dependent fields, and execution still unauthorized.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb

# Reuse the canonical CG fixtures/helpers.
_CG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

build_complete_ws_artifact = cg.build_complete_ws_artifact
build_plan = cg.build_plan
_auth_strategy_provenance = cg._auth_strategy_provenance
_refp = cg._refp
STRATEGY_50 = cg.STRATEGY_50
DATE = cg.DATE


def _wrap(plan, ws_art, *, now_ns):
    raw = json.dumps(ws_art).encode("utf-8")
    return wb.build_ws_bound_plan_artifact(
        plan_artifact=plan, ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=wb.compute_file_sha256(raw), binding_epoch_ns=now_ns)


def _complete(now=None):
    now = now or time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    return _wrap(build_plan(rest_price="100.0"), ws_art, now_ns=now + 2_000_000), ws_art


# --- canonical revised list -------------------------------------------------

def test_canonical_revised_fifty_target_positions_present():
    w, _ = _complete()
    cbp = w["canonical_bound_plan"]
    assert cbp is not None
    tps = cbp["planner"]["target_positions"]
    assert len(tps) == 50
    assert w["canonical_revised_action_count"] == 50


def test_all_active_prices_equal_ws_bound_lastprice():
    w, _ = _complete()
    for tp in w["canonical_bound_plan"]["planner"]["target_positions"]:
        assert tp["price"] == "100.5"
        assert tp["price"] == tp["price_evidence"]["selected_price"]
        assert tp["price_source"] == wb.WS_SOURCE_TYPE


def test_original_rest_price_audit_only():
    w, _ = _complete()
    for tp in w["canonical_bound_plan"]["planner"]["target_positions"]:
        assert tp["rest_planning_price"] == "100.0"   # audit-only ownership
        assert tp["price"] != tp["rest_planning_price"]
        # The WS timestamp belongs to the WS price evidence, never the REST price.
        assert "ts" not in str(tp["rest_planning_price"])


def test_input_plan_artifact_not_mutated():
    now = time.time_ns()
    plan = build_plan(rest_price="100.0")
    before = copy.deepcopy(plan)
    _wrap(plan, build_complete_ws_artifact(now_ns=now), now_ns=now + 2_000_000)
    assert plan == before  # deep-copied; never mutated


def test_deterministic_api_and_accessor():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    plan = build_plan(rest_price="100.0")
    w1 = _wrap(copy.deepcopy(plan), copy.deepcopy(ws_art), now_ns=now + 2_000_000)
    w2 = _wrap(copy.deepcopy(plan), copy.deepcopy(ws_art), now_ns=now + 2_000_000)
    assert w1["canonical_bound_plan_fingerprint"] == w2["canonical_bound_plan_fingerprint"]
    assert w1["wrapper_fingerprint"] == w2["wrapper_fingerprint"]
    actions = wb.canonical_bound_plan_actions(w1)
    assert len(actions) == 50
    assert all(a["price"] == a["price_evidence"]["selected_price"] for a in actions)


def test_composition_and_capital_preserved():
    w, _ = _complete()
    tps = w["canonical_bound_plan"]["planner"]["target_positions"]
    longs = [t for t in tps if t["side"] == "long"]
    shorts = [t for t in tps if t["side"] == "short"]
    assert len(longs) == 25 and len(shorts) == 25
    assert all(t["target_weight"] == "0.02" for t in longs)
    assert all(t["target_weight"] == "-0.02" for t in shorts)
    # Fixed capital + price-independent target notional preserved.
    assert all(t["target_notional"] == "200" for t in tps)


def test_quantity_recomputed_from_ws_price():
    w, _ = _complete()
    tp = w["canonical_bound_plan"]["planner"]["target_positions"][0]
    # 200 / 100.5 floored to 0.001 = 1.99.
    assert tp["qty"] == "1.99"
    assert tp["effective_notional"] is not None


def test_projected_margin_rebuilt_from_bound_plan():
    w, _ = _complete()
    rebuild = w["canonical_bound_plan"]["rebuilt_price_dependent_review"]
    assert rebuild["projected_margin_model_source"] == \
        "REBUILT_FROM_CANONICAL_BOUND_PLAN_WS_PRICES"
    # Strategy gross = 50 * 200 = 10000 (price-independent weight*capital).
    assert rebuild["strategy_gross_notional"] == "10000"
    assert "projected_margin_model" in rebuild


def test_action_fingerprint_includes_revised_price():
    w, _ = _complete()
    tp = w["canonical_bound_plan"]["planner"]["target_positions"][0]
    assert tp["action_fingerprint"].startswith("sha256:")
    assert w["canonical_bound_plan"]["canonical_bound_plan_fingerprint"].startswith("sha256:")


def test_freshness_complete_requires_canonical_list():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    # Drop one strategy record -> 49/50, no canonical bound plan, freshness false.
    ws_art["per_symbol_evidence"] = [r for r in ws_art["per_symbol_evidence"]
                                     if r["symbol"] != STRATEGY_50[0]]
    w = _wrap(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert w["execution_grade_freshness_complete"] is False


# --- mandatory strategy provenance -----------------------------------------

def test_ws_active_strategy_missing_fails_closed():
    now = time.time_ns()
    prov = _auth_strategy_provenance()
    prov["active_strategy"] = ""
    prov["strategy_provenance_status"] = ws.STRATEGY_SOURCE_PROVENANCE_MISSING
    ws_art = build_complete_ws_artifact(now_ns=now, strategy_source_provenance=prov)
    w = _wrap(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert w["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


def test_ws_active_strategy_mismatch_fails_closed():
    now = time.time_ns()
    prov = _auth_strategy_provenance(active_strategy="other_strategy_v9")
    ws_art = build_complete_ws_artifact(now_ns=now, strategy_source_provenance=prov)
    w = _wrap(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert "ws_active_strategy_incompatible" in \
        w["binding_audit"]["ws_artifact_compatibility"]["failures"]


def test_strategy_date_missing_fails_closed():
    now = time.time_ns()
    prov = _auth_strategy_provenance()
    prov["requested_strategy_date"] = ""
    ws_art = build_complete_ws_artifact(now_ns=now, strategy_source_provenance=prov)
    w = _wrap(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None


def test_strategy_date_mismatch_fails_closed():
    now = time.time_ns()
    prov = _auth_strategy_provenance(date="2026-01-01")
    ws_art = build_complete_ws_artifact(now_ns=now, strategy_source_provenance=prov)
    w = _wrap(build_plan(date=DATE), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert "ws_plan_strategy_date_mismatch" in \
        w["binding_audit"]["ws_artifact_compatibility"]["failures"]


def test_strategy_fingerprint_missing_fails_closed():
    now = time.time_ns()
    prov = _auth_strategy_provenance()
    prov["strategy_symbol_source_fingerprint"] = None
    ws_art = build_complete_ws_artifact(now_ns=now, strategy_source_provenance=prov)
    w = _wrap(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert "ws_strategy_symbol_source_fingerprint_absent" in \
        w["binding_audit"]["ws_artifact_compatibility"]["failures"]


def test_strategy_fingerprint_mismatch_fails_closed():
    now = time.time_ns()
    prov = _auth_strategy_provenance()
    prov["strategy_symbol_source_fingerprint"] = "sha256:" + "1" * 64
    ws_art = build_complete_ws_artifact(now_ns=now, strategy_source_provenance=prov)
    w = _wrap(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert "ws_strategy_symbol_source_fingerprint_mismatch" in \
        w["binding_audit"]["ws_artifact_compatibility"]["failures"]


def test_stored_and_recomputed_fingerprints_agree_on_complete():
    w, _ = _complete()
    comp = w["binding_audit"]["ws_artifact_compatibility"]
    assert comp["strategy_symbol_source_fingerprint_ws_stored"] == \
        comp["strategy_symbol_source_fingerprint_recomputed"]
    assert comp["status"] == wb.WS_ARTIFACT_COMPATIBILITY_OK


# --- schema version gate ----------------------------------------------------

def test_schema_version_one_only_rejected_for_canonical_binding():
    now = time.time_ns()
    # No strategy_source_provenance -> canonical_binding_schema_version is None (v1-only).
    ws_art = build_complete_ws_artifact(now_ns=now, strategy_source_provenance=None)
    assert ws_art["canonical_binding_schema_version"] is None
    w = _wrap(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert "ws_canonical_binding_schema_version_unsupported" in \
        w["binding_audit"]["ws_artifact_compatibility"]["failures"]


def test_new_schema_version_accepted():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    assert ws_art["canonical_binding_schema_version"] == ws.CANONICAL_BINDING_SCHEMA_VERSION
    w = _wrap(build_plan(), ws_art, now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is not None


# --- recomputable source-message fingerprint -------------------------------

def test_source_message_fingerprint_independently_recomputes():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    rec = ws_art["per_symbol_evidence"][0]
    recomputed = ws.canonical_source_message_fingerprint(
        symbol=rec["symbol"], topic=rec["topic"],
        selected_price_field=rec["selected_price_field"],
        selected_price=rec["selected_price"],
        source_message_type=rec["selected_price_source_message_type"],
        source_ts_ms=rec["selected_price_source_ts_ms"],
        source_cs=rec["selected_price_source_cs"],
        local_received_epoch_ns=rec["selected_price_source_local_received_epoch_ns"],
        local_received_at_utc=rec["selected_price_source_local_received_at_utc"],
        local_monotonic_received_ns=rec["selected_price_source_local_monotonic_received_ns"],
        connection_generation=rec["selected_price_source_connection_generation"])
    assert recomputed == rec["selected_price_source_message_fingerprint"]


def test_tampered_stored_source_message_fingerprint_fails_after_refingerprint():
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    rec = [r for r in ws_art["per_symbol_evidence"] if r["symbol"] == STRATEGY_50[0]][0]
    # Tamper ONLY the stored source-message fingerprint, keep the evidence
    # fingerprint consistent, and validly re-fingerprint the top-level artifact.
    rec["selected_price_source_message_fingerprint"] = "sha256:" + "2" * 64
    rec["evidence_fingerprint"] = wb._recompute_evidence_fingerprint(rec)
    w = _wrap(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    row = [b for b in w["binding_audit"]["per_action_bindings"]
           if b["action_symbol"] == STRATEGY_50[0]][0]
    assert row["binding_status"] == wb.WS_EVIDENCE_FINGERPRINT_MISMATCH
    assert w["canonical_bound_plan"] is None


@pytest.mark.parametrize("field", [
    "selected_price_source_ts_ms", "selected_price_source_cs", "selected_price",
    "selected_price_source_local_received_epoch_ns",
    "selected_price_source_connection_generation"])
def test_tampered_source_material_fails_closed(field):
    now = time.time_ns()
    ws_art = build_complete_ws_artifact(now_ns=now)
    rec = [r for r in ws_art["per_symbol_evidence"] if r["symbol"] == STRATEGY_50[0]][0]
    if field == "selected_price":
        rec[field] = "777.0"
    else:
        rec[field] = (rec[field] or 0) + 7
    # Re-fingerprint the top-level artifact only; the per-symbol material is now
    # inconsistent with its stored source-message fingerprint.
    w = _wrap(build_plan(), _refp(ws_art), now_ns=now + 2_000_000)
    assert w["canonical_bound_plan"] is None
    assert w["overall_binding_status"] == wb.WS_PLANNER_PRICE_BINDING_CONFLICT


# --- execution stays unauthorized on COMPLETE ------------------------------

def test_complete_resolves_three_blockers_retains_authorization():
    w, _ = _complete()
    assert wb.PRICE_FRESHNESS_EVIDENCE_PARTIAL in w["resolved_blockers"]
    assert wb.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE in w["resolved_blockers"]
    assert wb.WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS in w["resolved_blockers"]
    assert wb.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK in w["retained_blockers"]


def test_complete_does_not_authorize_execution():
    w, _ = _complete()
    assert w["execution_grade_freshness_complete"] is True
    assert w["execution_batch_authorized"] is False
    assert w["execution_ready"] is False
    assert w["sender_reachable"] is False
    assert w["execute_daily_native_call_count"] == 0
    assert w["transport_sender_call_count"] == 0
    assert w["order_post_count"] == 0
    assert w["amend_post_count"] == 0
    assert w["cancel_post_count"] == 0
    assert w["live_order_post_count"] == 0
    assert w["execution_authorization_marker_created"] is False
    na = w["binding_network_audit"]
    assert na == {"private_http_count": 0, "public_http_count": 0,
                  "websocket_connection_count": 0, "order_endpoint_count": 0}
    ws.assert_no_credentials(w, secret_values=["irrelevant-secret"])


# --- standalone offline fixture command ------------------------------------

def test_standalone_fixture_command_produces_canonical_fifty(tmp_path):
    script = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(
        os.path.abspath(__file__)))), "scripts",
        "generate_demo_strategy_ws_binding_fixture.py")
    spec = importlib.util.spec_from_file_location("gen_fixture", script)
    gen = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(gen)
    rc = gen.main(["--out-dir", str(tmp_path), "--binding-epoch-ns", str(time.time_ns())])
    assert rc == 0
    bound = json.loads((tmp_path / "canonical_bound_plan.json").read_text(encoding="utf-8"))
    assert bound["canonical_revised_action_count"] == 50
    assert bound["bound_action_count"] == 50
    assert bound["failed_action_count"] == 0
    assert bound["execution_grade_freshness_complete"] is True
    assert bound["execution_batch_authorized"] is False
    assert bound["order_post_count"] == 0
    tps = bound["canonical_bound_plan"]["planner"]["target_positions"]
    assert len(tps) == 50
    assert all(t["price"] == t["price_evidence"]["selected_price"] for t in tps)
