"""TASK-014CH1 -- pure offline consumer contract for the canonical WebSocket-bound
Strategy-native Plan artifact.

Validates ``src/demo_strategy_native_ws_bound_plan_consumer.py``: a valid canonical
50-action artifact passes; every tampered / mismatched / incomplete / stale / parity /
authorization case fails closed with the correct machine-readable code. All checks
are offline -- no real WebSocket, REST endpoint, exchange, sender or Pilot store.

The complete canonical wrapper is produced by the AUDITED production binder
(``demo_strategy_native_ws_price_binding.build_ws_bound_plan_artifact``) over the
existing offline CG fixtures, so the consumer is tested against real binder output.
"""
from __future__ import annotations

import copy
import importlib.util
import json
import os
import time
from decimal import Decimal

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb
from src import demo_strategy_native_ws_bound_plan_consumer as consumer

# Reuse the canonical CG fixtures/helpers (same pattern as the CG_FIX1 tests).
_CG = os.path.join(os.path.dirname(os.path.abspath(__file__)),
                   "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_ch1", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)


# ---------------------------------------------------------------------------
# Bundle + reseal helpers
# ---------------------------------------------------------------------------

def _signed_plan(rest_price: str = "100.0"):
    """Plan with the REAL producer's SIGNED target-notional convention: long +200,
    short -200 (cg.build_plan uses absolute 200, so flip the shorts)."""
    plan = cg.build_plan(rest_price=rest_price)
    for tp in plan["planner"]["target_positions"]:
        if str(tp["side"]).strip().lower() == "short":
            tp["target_notional"] = "-200"
    return plan


def _correct_bundle(now: int | None = None, *, stale: bool = False, offset: str = "0.0068"):
    """Build a real binder wrapper plus the matching correct caller expectations,
    including the actual source WS artifact used to create the bound wrapper."""
    now = now or time.time_ns()
    ws_art = cg.build_complete_ws_artifact(now_ns=now, offset=offset)
    plan = _signed_plan(rest_price="100.0")
    raw = json.dumps(ws_art).encode("utf-8")
    ws_sha = wb.compute_file_sha256(raw)
    epoch = now + (60_000_000_000 if stale else 2_000_000)
    w = wb.build_ws_bound_plan_artifact(
        plan_artifact=plan, ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=ws_sha, binding_epoch_ns=epoch)
    kw = dict(
        source_ws_artifact=ws_art,  # REQUIRED: the real source WS evidence artifact
        expected_policy_id=ws.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
        expected_strategy_id=ws.EXPECTED_STRATEGY_NAME,
        expected_run_date=cg.DATE,
        expected_original_plan_fingerprint=wb._fingerprint(plan),
        expected_ws_artifact_sha256=ws_sha,
        expected_ws_artifact_fingerprint=ws_art["artifact_fingerprint"],
        expected_binding_epoch_ns=epoch,
        expected_freshness_threshold_ms=wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS,
        expected_symbols=list(cg.STRATEGY_50),
    )
    return copy.deepcopy(w), kw


def _src_rec(kw, sym):
    return next(r for r in kw["source_ws_artifact"]["per_symbol_evidence"]
               if str(r["symbol"]).strip().upper() == str(sym).strip().upper())


def _reseal_source(kw):
    """Recompute the source WS artifact's own fingerprint (producer convention)."""
    src = kw["source_ws_artifact"]
    src["artifact_fingerprint"] = ws._fingerprint(
        {k: v for k, v in src.items() if k != "artifact_fingerprint"})
    return src["artifact_fingerprint"]


def _realign_source(w, kw):
    """After mutating the source WS artifact, re-anchor every fingerprint copy
    (source + wrapper + canonical + per-action + caller expectation) to it, so a test
    isolates the injected source defect rather than a trivial fingerprint mismatch."""
    fp = _reseal_source(kw)
    _set_all_ws_fingerprint(w, fp)
    _reseal_cbp(w)
    _reseal_wrapper(w)
    kw["expected_ws_artifact_fingerprint"] = fp


def _rebind_all_temporal(w, kw, *, ts_delta_ms, offset_seconds):
    """Consistently rebind EVERY bound action + its source record to a uniform source
    ts (= binding_ms + ts_delta_ms) under one authoritative artifact-global offset, and
    write the EXACT producer freshness as each stored binding_freshness, then realign
    all fingerprints. The clock offset is artifact-global, so all 50 must agree."""
    binding_ms = int(kw["expected_binding_epoch_ns"] / 1e6)
    new_ts = binding_ms + ts_delta_ms
    kw["source_ws_artifact"]["clock_offset_seconds"] = str(offset_seconds)
    for tp in w["canonical_bound_plan"]["planner"]["target_positions"]:
        rec = _src_rec(kw, tp["symbol"])
        rec["selected_price_source_ts_ms"] = new_ts
        rec["selected_price_ts_ms"] = new_ts
        rec["selected_price_source_message_fingerprint"] = ws.canonical_source_message_fingerprint(
            symbol=rec["symbol"], topic=rec["topic"],
            selected_price_field=rec["selected_price_field"], selected_price=rec["selected_price"],
            source_message_type=rec["selected_price_source_message_type"],
            source_ts_ms=rec["selected_price_source_ts_ms"],
            source_cs=rec["selected_price_source_cs"],
            local_received_epoch_ns=rec["selected_price_source_local_received_epoch_ns"],
            local_received_at_utc=rec["selected_price_source_local_received_at_utc"],
            local_monotonic_received_ns=rec["selected_price_source_local_monotonic_received_ns"],
            connection_generation=rec["selected_price_source_connection_generation"])
        rec["evidence_fingerprint"] = wb._recompute_evidence_fingerprint(rec)
        pe = tp["price_evidence"]
        pe["exchange_data_generated_ts_ms"] = new_ts
        _reseal_action_evidence(tp)  # recomputes pe smf (== rec smf) + action fingerprint
        tp["binding_freshness"] = wb._evaluate_binding_freshness(
            rec, binding_epoch_ns=kw["expected_binding_epoch_ns"],
            clock_offset_seconds=Decimal(str(offset_seconds)),
            threshold_ms=kw["expected_freshness_threshold_ms"],
            future_tolerance_ms=wb.DEFAULT_FUTURE_TOLERANCE_MS)
    _realign_source(w, kw)


def _reseal_action_evidence(tp):
    """Recompute a target's source-message + action fingerprints from its (mutated)
    price evidence, so a tamper test isolates the intended defect instead of only
    tripping the source-message / action fingerprint check."""
    pe = tp["price_evidence"]
    pe["source_message_fingerprint"] = consumer._recompute_source_message_fingerprint(
        tp["symbol"], pe)
    tp["action_fingerprint"] = consumer._recompute_action_fingerprint(tp, pe)


def _short_tp(w):
    return next(t for t in w["canonical_bound_plan"]["planner"]["target_positions"]
               if str(t["side"]).strip().lower() == "short")


def _long_tp(w):
    return next(t for t in w["canonical_bound_plan"]["planner"]["target_positions"]
               if str(t["side"]).strip().lower() == "long")


def _set_all_ws_fingerprint(w, value):
    w["source_ws_artifact_fingerprint"] = value
    cbp = w["canonical_bound_plan"]
    cbp["source_ws_artifact_fingerprint"] = value
    for tp in cbp["planner"]["target_positions"]:
        tp["price_evidence"]["source_artifact_fingerprint"] = value


def _reseal_cbp(w: dict) -> None:
    cbp = w["canonical_bound_plan"]
    cbp["canonical_bound_plan_fingerprint"] = \
        consumer._recompute_canonical_bound_plan_fingerprint(cbp)


def _reseal_wrapper(w: dict) -> None:
    body = {k: v for k, v in w.items() if k != "wrapper_fingerprint"}
    w["wrapper_fingerprint"] = wb._fingerprint(body)


def _validate(w, kw, **over):
    merged = dict(kw)
    merged.update(over)
    return consumer.validate_ws_bound_plan_artifact(w, **merged)


# ---------------------------------------------------------------------------
# Happy path
# ---------------------------------------------------------------------------

def test_valid_canonical_fifty_action_artifact_passes():
    w, kw = _correct_bundle()
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS
    assert r.passed is True
    assert r.failure_codes == ()
    assert r.provenance_verified is True
    assert r.canonical_plan_available is True
    assert r.execution_grade_freshness_complete is True
    assert len(r.validated_actions) == 50
    longs = [a for a in r.validated_actions if a.side == "long"]
    shorts = [a for a in r.validated_actions if a.side == "short"]
    assert len(longs) == 25 and len(shorts) == 25
    assert all(a.action_price_binding_status
               == wb.WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE for a in r.validated_actions)


def test_valid_artifact_round_trips_through_file_loader(tmp_path):
    w, kw = _correct_bundle()
    p = tmp_path / "bound.json"
    p.write_text(json.dumps(w, ensure_ascii=False, sort_keys=True), encoding="utf-8")
    loaded = consumer.load_ws_bound_plan_artifact(p)
    r = _validate(loaded, kw)
    assert r.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS
    assert len(r.validated_actions) == 50


def test_failed_result_never_exposes_validated_actions():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_policy_id="WRONG_POLICY")
    assert r.status != consumer.WS_BOUND_PLAN_CONSUMER_PASS
    assert r.validated_actions == ()
    assert r.canonical_plan_available is False
    assert r.execution_grade_freshness_complete is False


# ---------------------------------------------------------------------------
# Loader errors
# ---------------------------------------------------------------------------

def test_loader_rejects_missing_file(tmp_path):
    with pytest.raises(consumer.WsBoundPlanConsumerError):
        consumer.load_ws_bound_plan_artifact(tmp_path / "nope.json")


def test_loader_rejects_non_object_json(tmp_path):
    p = tmp_path / "bad.json"
    p.write_text("[1, 2, 3]", encoding="utf-8")
    with pytest.raises(consumer.WsBoundPlanConsumerError):
        consumer.load_ws_bound_plan_artifact(p)


# ---------------------------------------------------------------------------
# Schema / fingerprint integrity
# ---------------------------------------------------------------------------

def test_unsupported_schema_version_fails_closed():
    w, kw = _correct_bundle()
    w["schema_version"] = 99
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_SCHEMA_INVALID


def test_null_canonical_plan_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"] = None
    w["overall_binding_status"] = wb.WS_PLANNER_PRICE_BINDING_PARTIAL
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_INCOMPLETE
    assert r.canonical_plan_available is False


def test_tampered_wrapper_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    w["wrapper_fingerprint"] = "sha256:" + "0" * 64
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_WRAPPER_FINGERPRINT_MISMATCH


def test_tampered_canonical_plan_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"]["canonical_bound_plan_fingerprint"] = "sha256:" + "1" * 64
    _reseal_wrapper(w)  # wrapper recomputes; only the cbp fingerprint is wrong
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_FINGERPRINT_MISMATCH


# ---------------------------------------------------------------------------
# Per-action consistency (independent recomputation)
# ---------------------------------------------------------------------------

def test_tampered_action_price_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"]["planner"]["target_positions"][0]["price"] = "999.0"
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_tampered_rounded_quantity_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"]["planner"]["target_positions"][0]["qty"] = "7"
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_tampered_effective_notional_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"]["planner"]["target_positions"][0]["effective_notional"] = "1.23"
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_tampered_per_symbol_evidence_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    tp = w["canonical_bound_plan"]["planner"]["target_positions"][0]
    tp["price_evidence"]["source_message_fingerprint"] = "sha256:" + "2" * 64
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)  # source unchanged -> bound evidence no longer matches source
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_wrong_source_message_fingerprint_material_fails_closed():
    w, kw = _correct_bundle()
    tp = w["canonical_bound_plan"]["planner"]["target_positions"][0]
    # Tamper underlying source material but keep the stored fingerprint -> recompute differs.
    tp["price_evidence"]["cross_sequence"] = (tp["price_evidence"]["cross_sequence"] or 0) + 7
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)  # diverges from the unchanged source record
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


# ---------------------------------------------------------------------------
# Caller-supplied ground-truth mismatches
# ---------------------------------------------------------------------------

def test_wrong_expected_original_plan_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_original_plan_fingerprint="sha256:" + "9" * 64)
    assert r.status == consumer.WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH


def test_wrong_expected_ws_artifact_sha256_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_ws_artifact_sha256="sha256:" + "9" * 64)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_wrong_policy_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_policy_id="SOME_OTHER_POLICY")
    assert r.status == consumer.WS_BOUND_PLAN_PROVENANCE_MISMATCH


def test_wrong_strategy_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_strategy_id="some_other_strategy_v9")
    assert r.status == consumer.WS_BOUND_PLAN_PROVENANCE_MISMATCH


def test_wrong_date_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_run_date="1999-01-01")
    assert r.status == consumer.WS_BOUND_PLAN_PROVENANCE_MISMATCH


# ---------------------------------------------------------------------------
# Symbol set / structure
# ---------------------------------------------------------------------------

def test_missing_symbol_fails_closed():
    w, kw = _correct_bundle()
    tps = w["canonical_bound_plan"]["planner"]["target_positions"]
    del tps[0]
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_SYMBOL_SET_MISMATCH


def test_extra_symbol_fails_closed():
    w, kw = _correct_bundle()
    # Caller expects 49; the artifact (and source) carry the full 50 -> one is extra.
    # The symbol-set mismatch surfaces (the source gate also rejects the 49-set, which
    # is the higher-priority WS_ARTIFACT identity failure).
    r = _validate(w, kw, expected_symbols=list(cg.STRATEGY_50)[:-1])
    _assert_failed(r)
    assert consumer.WS_BOUND_PLAN_SYMBOL_SET_MISMATCH in r.failure_codes


def test_duplicate_symbol_fails_closed():
    w, kw = _correct_bundle()
    tps = w["canonical_bound_plan"]["planner"]["target_positions"]
    tps[1]["symbol"] = tps[0]["symbol"]
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert consumer.WS_BOUND_PLAN_DUPLICATE_SYMBOL in r.failure_codes


def test_wrong_long_short_count_fails_closed():
    w, kw = _correct_bundle()
    tps = w["canonical_bound_plan"]["planner"]["target_positions"]
    a_long = next(t for t in tps if t["side"] == "long")
    a_long["side"] = "short"  # 24 long / 26 short
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_SYMBOL_SET_MISMATCH
    assert any("long_short" in b for b in r.blockers)


# ---------------------------------------------------------------------------
# Completeness / parity / freshness
# ---------------------------------------------------------------------------

def test_incomplete_binding_fails_closed():
    w, kw = _correct_bundle()
    w["overall_binding_status"] = wb.WS_PLANNER_PRICE_BINDING_PARTIAL
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_INCOMPLETE


def test_stale_freshness_fails_closed():
    # A binding epoch far past the WS evidence timestamps yields all-stale actions,
    # no canonical bound plan, and stale status counts -> the consumer reports STALE.
    w, kw = _correct_bundle(stale=True)
    assert w["canonical_bound_plan"] is None
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_STALE


def test_parity_failure_fails_closed():
    w, kw = _correct_bundle()
    w["binding_parity_status"] = wb.WS_PLANNER_BINDING_PARITY_FAIL
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_PARITY_FAIL


# ---------------------------------------------------------------------------
# Authorization must remain false / zero
# ---------------------------------------------------------------------------

def test_authorization_boolean_true_fails_closed():
    w, kw = _correct_bundle()
    w["execution_batch_authorized"] = True
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_AUTHORIZATION_PRESENT


def test_order_post_count_above_zero_fails_closed():
    w, kw = _correct_bundle()
    w["order_post_count"] = 1
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_AUTHORIZATION_PRESENT


# ===========================================================================
# FIX1 -- total fail-closed behaviour, evidence integrity, V1 semantics
# ===========================================================================

def _assert_failed(r):
    assert r.status != consumer.WS_BOUND_PLAN_CONSUMER_PASS
    assert r.passed is False
    assert r.validated_actions == ()
    assert r.canonical_plan_available is False
    assert r.execution_grade_freshness_complete is False


def _first_tp(w):
    return w["canonical_bound_plan"]["planner"]["target_positions"][0]


# --- malformed qty_step -----------------------------------------------------

def test_missing_qty_step_fails_closed():
    w, kw = _correct_bundle()
    del _first_tp(w)["qty_step"]
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_non_numeric_qty_step_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["qty_step"] = "abc"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_zero_qty_step_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["qty_step"] = "0"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_negative_qty_step_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["qty_step"] = "-0.001"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


# --- malformed action numerics / evidence ----------------------------------

def test_missing_price_evidence_fails_closed():
    w, kw = _correct_bundle()
    del _first_tp(w)["price_evidence"]
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    # No price evidence -> the action cannot be proven to belong to the source record.
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("price_evidence_absent" in b for b in r.blockers)


def test_malformed_numeric_price_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["price"] = "not-a-number"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_malformed_quantity_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["qty"] = "xyz"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_malformed_effective_notional_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["effective_notional"] = "??"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_malformed_source_message_field_type_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["price_evidence"]["cross_sequence"] = {"unexpected": "dict"}
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("cross_sequence" in b for b in r.blockers)


# --- per-symbol fingerprints ------------------------------------------------

def test_tampered_action_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["action_fingerprint"] = "sha256:" + "3" * 64
    _reseal_wrapper(w)  # action_fingerprint is not part of the cbp fp material
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("action_fingerprint_mismatch" in b for b in r.blockers)


def test_per_symbol_source_artifact_fingerprint_mismatch_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["price_evidence"]["source_artifact_fingerprint"] = "sha256:" + "4" * 64
    _reseal_wrapper(w)  # not part of cbp fp material
    r = _validate(w, kw)
    _assert_failed(r)
    assert consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH in r.failure_codes


# --- provenance cross-field -------------------------------------------------

def test_wrapper_vs_canonical_ws_fingerprint_mismatch_fails_closed():
    w, kw = _correct_bundle()
    w["source_ws_artifact_fingerprint"] = "sha256:" + "5" * 64
    _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_tampered_canonical_original_plan_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"]["original_plan_fingerprint"] = "sha256:" + "6" * 64
    _reseal_cbp(w); _reseal_wrapper(w)
    # Caller-supplied expected value remains the real one -> mismatch.
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH


def test_symbol_set_fingerprint_mismatch_fails_closed():
    w, kw = _correct_bundle()
    w["strategy_identity"]["strategy_symbol_source_fingerprint"] = "sha256:" + "7" * 64
    _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_SYMBOL_SET_MISMATCH
    assert any("symbol_source_fingerprint_mismatch" in b for b in r.blockers)


# --- Strategy-native V1 semantics ------------------------------------------

def test_wrong_target_weight_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["target_weight"] = "0.03"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("target_weight_not_pm_0.02" in b for b in r.blockers)


def test_zero_target_weight_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["target_weight"] = "0"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("target_weight_zero" in b for b in r.blockers)


def test_side_weight_direction_mismatch_fails_closed():
    w, kw = _correct_bundle()
    tp = next(t for t in w["canonical_bound_plan"]["planner"]["target_positions"]
              if t["side"] == "long")
    tp["target_weight"] = "-0.02"  # long but negative weight
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("side_weight_mismatch" in b for b in r.blockers)


def test_target_notional_mismatch_fails_closed():
    w, kw = _correct_bundle()
    _first_tp(w)["target_notional"] = "500"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_v1_capital_base_not_10000_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"]["planner"]["sizing_verification"]["capital_base_usd"] = 5000
    _reseal_wrapper(w)  # sizing_verification is not part of the cbp fp material
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("v1_capital_base_not_10000" in b for b in r.blockers)


# --- total fail-closed on arbitrary / nested-wrong-type input --------------

def test_arbitrary_malformed_mapping_does_not_raise():
    w, kw = _correct_bundle()
    r = consumer.validate_ws_bound_plan_artifact(
        {"a": 1, "b": [1, 2, {"c": 3}], "schema": "garbage"}, **kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_SCHEMA_INVALID


def test_nested_wrong_json_types_do_not_raise():
    w, kw = _correct_bundle()
    art = {
        "schema": wb.SCHEMA_NAME, "schema_version": wb.SCHEMA_VERSION,
        "task_id": wb.TASK_ID, "binding_mode": wb.BINDING_MODE_PLAN_ONLY,
        "wrapper_fingerprint": None,
        "overall_binding_status": 12345,
        "canonical_bound_plan": ["not", "a", "map"],
        "binding_audit": "oops-not-a-map",
        "strategy_identity": 999,
        "source_ws_artifact_sha256": {"nested": True},
        "binding_network_audit": [1, 2, 3],
    }
    r = consumer.validate_ws_bound_plan_artifact(art, **kw)  # must not raise
    _assert_failed(r)


def test_empty_mapping_does_not_raise():
    w, kw = _correct_bundle()
    r = consumer.validate_ws_bound_plan_artifact({}, **kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_SCHEMA_INVALID


# ===========================================================================
# FIX2 -- signed V1 notional + externally-anchored WS provenance + evidence
# ===========================================================================

def test_signed_pass_long_plus200_short_minus200():
    w, kw = _correct_bundle()
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS
    longs = [a for a in r.validated_actions if a.side == "long"]
    shorts = [a for a in r.validated_actions if a.side == "short"]
    assert all(a.target_weight == "0.02" and a.target_notional == "200" for a in longs)
    assert all(a.target_weight == "-0.02" and a.target_notional == "-200" for a in shorts)


def test_short_with_positive_notional_fails_closed():
    w, kw = _correct_bundle()
    _short_tp(w)["target_notional"] = "200"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("side_notional_mismatch" in b for b in r.blockers)


def test_long_with_negative_notional_fails_closed():
    w, kw = _correct_bundle()
    _long_tp(w)["target_notional"] = "-200"
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("side_notional_mismatch" in b for b in r.blockers)


def test_weight_notional_sign_mismatch_fails_closed():
    w, kw = _correct_bundle()
    tp = _long_tp(w)
    tp["target_weight"] = "-0.02"  # long, +200 notional, but negative weight
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT
    assert any("weight_notional_mismatch" in b for b in r.blockers)
    assert any("side_weight_mismatch" in b for b in r.blockers)


# --- externally-anchored WS artifact fingerprint ---------------------------

def test_wrong_caller_ws_artifact_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_ws_artifact_fingerprint="sha256:" + "a" * 64)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_wrapper_and_canonical_ws_fp_changed_together_caller_unchanged_fails_closed():
    w, kw = _correct_bundle()
    _set_all_ws_fingerprint(w, "sha256:" + "b" * 64)  # internally consistent new value
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)  # caller expectation unchanged -> must fail
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_per_symbol_source_artifact_fp_changed_with_layers_caller_unchanged_fails_closed():
    w, kw = _correct_bundle()
    # Move every layer's WS fingerprint together to a consistent value; the caller
    # anchor still rejects it (per-action provenance must equal the external truth).
    new = "sha256:" + "c" * 64
    _set_all_ws_fingerprint(w, new)
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("source_artifact_fingerprint_not_expected" in b for b in r.blockers)


# --- required execution-grade evidence fields ------------------------------

def _evidence_case(mutate):
    # Tampering the bound action's price evidence (while the source WS artifact is
    # unchanged) makes the action no longer BELONG to the source record -> the
    # source-membership cross-validation reports WS_ARTIFACT_MISMATCH (the precise
    # FIX4 outcome). The malformed-field blockers are still recorded.
    w, kw = _correct_bundle()
    pe = _first_tp(w)["price_evidence"]
    mutate(pe)
    _reseal_wrapper(w)  # evidence fields (except smf) are not in the cbp fp material
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    return r


def test_missing_topic_fails_closed():
    r = _evidence_case(lambda pe: pe.pop("topic", None))
    assert any("topic" in b for b in r.blockers)


def test_wrong_topic_for_symbol_fails_closed():
    r = _evidence_case(lambda pe: pe.__setitem__("topic", "tickers.WRONGUSDT"))
    assert any("evidence_topic_invalid" in b for b in r.blockers)


def test_missing_selected_price_field_fails_closed():
    r = _evidence_case(lambda pe: pe.pop("selected_price_field", None))
    assert any("selected_price_field" in b for b in r.blockers)


def test_wrong_selected_price_field_fails_closed():
    r = _evidence_case(lambda pe: pe.__setitem__("selected_price_field", "markPrice"))
    assert any("selected_price_field" in b for b in r.blockers)


def test_missing_exchange_timestamp_fails_closed():
    r = _evidence_case(lambda pe: pe.pop("exchange_data_generated_ts_ms", None))
    assert any("exchange_data_generated_ts_ms" in b for b in r.blockers)


def test_missing_local_received_timestamp_fails_closed():
    r = _evidence_case(lambda pe: pe.pop("local_received_at_utc", None))
    assert any("local_received_at_utc" in b for b in r.blockers)


def test_missing_local_monotonic_timestamp_fails_closed():
    r = _evidence_case(lambda pe: pe.pop("local_monotonic_received_ns", None))
    assert any("local_monotonic_received_ns" in b for b in r.blockers)


def test_missing_connection_generation_fails_closed():
    r = _evidence_case(lambda pe: pe.pop("connection_generation", None))
    assert any("connection_generation" in b for b in r.blockers)


def test_missing_message_type_fails_closed():
    r = _evidence_case(lambda pe: pe.pop("message_type", None))
    assert any("message_type" in b for b in r.blockers)


def test_required_evidence_field_wrong_json_type_fails_closed():
    r = _evidence_case(lambda pe: pe.__setitem__("local_received_epoch_ns", "not-an-int"))
    assert any("local_received_epoch_ns" in b for b in r.blockers)


# ===========================================================================
# FIX3 -- temporal / freshness integrity
# ===========================================================================

def test_valid_passes_with_caller_temporal_anchors():
    w, kw = _correct_bundle()
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS
    assert r.execution_grade_freshness_complete is True
    assert len(r.validated_actions) == 50


def test_stale_evidence_with_stored_fresh_retained_fails_closed():
    # Offset-free age looks fresh, but the authoritative +20s clock offset makes the
    # EXACT producer age exceed the strict threshold. Every stored FRESH field is
    # retained; the consumer recomputes with the authoritative offset and rejects it.
    w, kw = _correct_bundle()
    kw["source_ws_artifact"]["clock_offset_seconds"] = "20"
    _realign_source(w, kw)
    assert w["execution_grade_freshness_complete"] is True  # stored field retained
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    assert r.execution_grade_freshness_complete is False    # consumer overrides it


def test_offset_free_future_but_exact_offset_adjusted_valid_passes():
    # Source ts is 6s AFTER binding (offset-free age = -6s, would look "future"), but a
    # +6s authoritative offset brings the EXACT age to ~0 -> valid / FRESH -> PASS.
    w, kw = _correct_bundle()
    _rebind_all_temporal(w, kw, ts_delta_ms=6000, offset_seconds="6")
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS


def test_evidence_timestamp_later_than_binding_fails_closed():
    # A large negative authoritative offset places the estimated-exchange binding time
    # before the evidence -> EXACT age is in the future beyond the tolerance.
    w, kw = _correct_bundle()
    kw["source_ws_artifact"]["clock_offset_seconds"] = "-20"
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    assert any("future" in b for b in r.blockers)


def test_binding_epoch_changed_in_canonical_caller_unchanged_fails_closed():
    w, kw = _correct_bundle()
    w["canonical_bound_plan"]["binding_epoch_ns"] = kw["expected_binding_epoch_ns"] + 5_000_000
    _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)  # caller epoch unchanged -> anchor mismatch
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    assert any("canonical_binding_epoch_not_expected" in b for b in r.blockers)


def test_wrong_caller_binding_epoch_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_binding_epoch_ns=kw["expected_binding_epoch_ns"] + 999_999_999)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE


def test_threshold_above_strict_max_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw,
                  expected_freshness_threshold_ms=consumer.STRICT_MAX_FRESHNESS_THRESHOLD_MS + 1)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    assert any("strict_max" in b for b in r.blockers)


@pytest.mark.parametrize("bad", [0, -1, 1.5, "10", True, None])
def test_bad_binding_epoch_format_fails_closed(bad):
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_binding_epoch_ns=bad)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE


@pytest.mark.parametrize("bad", [0, -5, 2.5, "10000", True, None])
def test_bad_threshold_format_fails_closed(bad):
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_freshness_threshold_ms=bad)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE


# --- UTC timestamp semantics ------------------------------------------------

def _temporal_evidence_case(mutate):
    w, kw = _correct_bundle()
    tp = _first_tp(w)
    mutate(tp["price_evidence"])
    _reseal_action_evidence(tp); _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    return r


def test_invalid_iso_timestamp_fails_closed():
    r = _temporal_evidence_case(lambda pe: pe.__setitem__("local_received_at_utc", "not-a-date"))
    assert any("local_received_at_utc_invalid" in b for b in r.blockers)


def test_naive_iso_timestamp_fails_closed():
    r = _temporal_evidence_case(
        lambda pe: pe.__setitem__("local_received_at_utc", "2026-06-22T12:00:00.000000"))
    assert any("local_received_at_utc_naive" in b for b in r.blockers)


def test_non_utc_timestamp_fails_closed():
    r = _temporal_evidence_case(
        lambda pe: pe.__setitem__("local_received_at_utc", "2026-06-22T12:00:00.000000+05:00"))
    assert any("local_received_at_utc_non_utc" in b for b in r.blockers)


def test_iso_timestamp_epoch_ns_mismatch_fails_closed():
    w, kw = _correct_bundle()
    tp = _first_tp(w)
    pe = tp["price_evidence"]
    # Valid UTC ISO string, but a different instant than local_received_epoch_ns.
    pe["local_received_at_utc"] = ws._iso_from_epoch_ns(pe["local_received_epoch_ns"]
                                                        + 3_600_000_000_000)  # +1h
    _reseal_action_evidence(tp); _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    assert any("utc_epoch_instant_mismatch" in b for b in r.blockers)


# --- message semantics ------------------------------------------------------

def test_unsupported_message_type_fails_closed():
    w, kw = _correct_bundle()
    tp = _first_tp(w)
    tp["price_evidence"]["message_type"] = "heartbeat"  # not snapshot/delta
    _reseal_action_evidence(tp); _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)  # source unchanged -> bound message type no longer matches source
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("message_type" in b for b in r.blockers)


# --- malformed caller-supplied expected values ------------------------------

def test_malformed_expected_ws_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_ws_artifact_fingerprint="deadbeef")
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_malformed_expected_ws_sha256_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_ws_artifact_sha256="sha256:nothex")
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_malformed_expected_original_plan_fingerprint_fails_closed():
    w, kw = _correct_bundle()
    r = _validate(w, kw, expected_original_plan_fingerprint="not-canonical")
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH


# ===========================================================================
# FIX4 -- source WS artifact cross-validation + authoritative-offset freshness
# ===========================================================================

def test_valid_bound_plan_plus_source_ws_artifact_passes():
    w, kw = _correct_bundle()
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_CONSUMER_PASS
    assert len(r.validated_actions) == 50
    assert r.execution_grade_freshness_complete is True


def test_positive_clock_offset_passes():
    w, kw = _correct_bundle(offset="0.0068")
    assert _validate(w, kw).status == consumer.WS_BOUND_PLAN_CONSUMER_PASS


def test_negative_clock_offset_passes():
    w, kw = _correct_bundle(offset="-0.0068")
    assert _validate(w, kw).status == consumer.WS_BOUND_PLAN_CONSUMER_PASS


# --- authoritative clock offset --------------------------------------------

def test_source_clock_offset_field_tampered_fails_closed():
    # Small offset change keeps the exact age under threshold, but the stored age was
    # computed with the original offset -> exact recomputation disagrees -> STALE.
    w, kw = _correct_bundle()
    kw["source_ws_artifact"]["clock_offset_seconds"] = "0.5"
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    assert any("stored_age_differs_from_authoritative_recompute" in b for b in r.blockers)


def test_duplicated_clock_offset_fields_disagree_fails_closed():
    w, kw = _correct_bundle()
    kw["source_ws_artifact"]["clock_offset_provenance"] = {
        "clock_offset_provenance_status": ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE,
        "estimated_local_vs_exchange_clock_offset_seconds": "9.999",  # != top-level
    }
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("clock_offset_duplicate_fields_disagree" in b for b in r.blockers)


def test_clock_offset_provenance_not_authoritative_fails_closed():
    w, kw = _correct_bundle()
    kw["source_ws_artifact"]["clock_offset_provenance_status"] = \
        ws.CLOCK_OFFSET_PROVENANCE_STALE
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


# --- source artifact identity ----------------------------------------------

def test_source_ws_artifact_fingerprint_wrong_fails_closed():
    w, kw = _correct_bundle()
    kw["source_ws_artifact"]["artifact_fingerprint"] = "sha256:" + "0" * 64  # not resealed
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


def test_caller_fingerprint_matches_wrapper_but_not_source_fails_closed():
    w, kw = _correct_bundle()
    other = cg.build_complete_ws_artifact(now_ns=time.time_ns() + 10 ** 9)  # different fp
    kw["source_ws_artifact"] = other
    r = _validate(w, kw)  # caller fp == wrapper, but != supplied source artifact
    _assert_failed(r)
    assert consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH in r.failure_codes


# --- per-action membership vs source record --------------------------------

def test_action_source_ts_changed_membership_fails_closed():
    w, kw = _correct_bundle()
    tp = _first_tp(w)
    tp["price_evidence"]["exchange_data_generated_ts_ms"] += 123  # diverge from source
    _reseal_action_evidence(tp); _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)  # source WS artifact unchanged
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("source_record_mismatch:exchange_ts_ms" in b for b in r.blockers)


def test_action_selected_price_changed_membership_fails_closed():
    w, kw = _correct_bundle()
    tp = _first_tp(w)
    tp["price_evidence"]["selected_price"] = "123.45"
    tp["price"] = "123.45"
    tp["price_decimal"] = "123.45"
    _reseal_action_evidence(tp); _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)  # source WS artifact unchanged
    _assert_failed(r)
    assert consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH in r.failure_codes


def test_action_smf_recomputed_over_invented_evidence_fails_closed():
    # The bound action's source-message fingerprint is internally consistent (recomputed
    # over invented evidence) but does not match the unchanged source artifact record.
    w, kw = _correct_bundle()
    tp = _first_tp(w)
    tp["price_evidence"]["cross_sequence"] += 999
    _reseal_action_evidence(tp); _reseal_cbp(w); _reseal_wrapper(w)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


# --- source record fingerprint integrity -----------------------------------

def test_source_record_evidence_fingerprint_tampered_fails_closed():
    w, kw = _correct_bundle()
    rec = _src_rec(kw, _first_tp(w)["symbol"])
    rec["evidence_fingerprint"] = "sha256:" + "e" * 64
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("source_evidence_fingerprint_mismatch" in b for b in r.blockers)


def test_source_record_source_message_fingerprint_tampered_fails_closed():
    w, kw = _correct_bundle()
    rec = _src_rec(kw, _first_tp(w)["symbol"])
    rec["selected_price_source_message_fingerprint"] = "sha256:" + "d" * 64
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("source_message_fingerprint" in b for b in r.blockers)


# --- source symbol set ------------------------------------------------------

def test_duplicate_source_symbol_fails_closed():
    w, kw = _correct_bundle()
    rec = _src_rec(kw, _first_tp(w)["symbol"])
    kw["source_ws_artifact"]["per_symbol_evidence"].append(copy.deepcopy(rec))
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("duplicate_source_symbols" in b for b in r.blockers)


def test_missing_strategy_source_symbol_fails_closed():
    w, kw = _correct_bundle()
    sym = _first_tp(w)["symbol"]
    pse = kw["source_ws_artifact"]["per_symbol_evidence"]
    kw["source_ws_artifact"]["per_symbol_evidence"] = [
        r for r in pse if str(r["symbol"]).strip().upper() != str(sym).strip().upper()]
    _realign_source(w, kw)
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH
    assert any("source_symbol_missing" in b for b in r.blockers)


# --- wrong source record fields --------------------------------------------

@pytest.mark.parametrize("field,value", [
    ("selected_price_source_message_type", "delta"),
    ("topic", "tickers.WRONGUSDT"),
    ("selected_price_source_cs", 999_999),
    ("selected_price_source_connection_generation", 7),
])
def test_wrong_source_record_field_fails_closed(field, value):
    w, kw = _correct_bundle()
    rec = _src_rec(kw, _first_tp(w)["symbol"])
    rec[field] = value
    _realign_source(w, kw)
    r = _validate(w, kw)  # source record diverges from the bound action's evidence
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH


# --- stored age vs exact recomputation -------------------------------------

def test_stored_age_differs_from_exact_recompute_fails_closed():
    w, kw = _correct_bundle()
    bf = _first_tp(w)["binding_freshness"]
    bf["evidence_age_at_binding_ms"] = float(bf["evidence_age_at_binding_ms"]) + 1234.5
    _reseal_wrapper(w)  # binding_freshness is not part of the cbp fp material
    r = _validate(w, kw)
    _assert_failed(r)
    assert r.status == consumer.WS_BOUND_PLAN_STALE
    assert any("stored_age_differs_from_authoritative_recompute" in b for b in r.blockers)
