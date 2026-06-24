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

def _correct_bundle(now: int | None = None, *, stale: bool = False):
    """Build a real binder wrapper plus the matching correct caller expectations."""
    now = now or time.time_ns()
    ws_art = cg.build_complete_ws_artifact(now_ns=now)
    plan = cg.build_plan(rest_price="100.0")
    raw = json.dumps(ws_art).encode("utf-8")
    ws_sha = wb.compute_file_sha256(raw)
    epoch = now + (60_000_000_000 if stale else 2_000_000)
    w = wb.build_ws_bound_plan_artifact(
        plan_artifact=plan, ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=ws_sha, binding_epoch_ns=epoch)
    kw = dict(
        expected_policy_id=ws.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
        expected_strategy_id=ws.EXPECTED_STRATEGY_NAME,
        expected_run_date=cg.DATE,
        expected_original_plan_fingerprint=wb._fingerprint(plan),
        expected_ws_artifact_sha256=ws_sha,
        expected_symbols=list(cg.STRATEGY_50),
    )
    return copy.deepcopy(w), kw


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
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


def test_wrong_source_message_fingerprint_material_fails_closed():
    w, kw = _correct_bundle()
    tp = w["canonical_bound_plan"]["planner"]["target_positions"][0]
    # Tamper underlying source material but keep the stored fingerprint -> recompute differs.
    tp["price_evidence"]["cross_sequence"] = (tp["price_evidence"]["cross_sequence"] or 0) + 7
    _reseal_cbp(w)
    _reseal_wrapper(w)
    r = _validate(w, kw)
    assert r.status == consumer.WS_BOUND_PLAN_ACTION_INCONSISTENT


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
    # Caller expects 49; the artifact carries the full 50 -> one is extra.
    r = _validate(w, kw, expected_symbols=list(cg.STRATEGY_50)[:-1])
    assert r.status == consumer.WS_BOUND_PLAN_SYMBOL_SET_MISMATCH


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
