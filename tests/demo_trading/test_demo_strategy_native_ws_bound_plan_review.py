"""TASK-014CH3B1 -- pure, offline WS-bound Plan review core.

Validates `src/demo_strategy_native_ws_bound_plan_review.py`: a trusted external anchor
manifest + exact CH2 wrapper bytes + exact source-WS bytes -> externally-anchored CH1
historical validation -> immutable V1 exposure review -> offline margin-arithmetic review
-> terminal review envelope. Offline fixtures only; no network/sender/Pilot.
"""
from __future__ import annotations

import copy
import dataclasses
import importlib.util
import json
import os
import time

import pytest

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb
from src import demo_strategy_native_ws_bound_plan_consumer as consumer
from src import demo_strategy_native_ws_bound_plan_review as rev

_HERE = os.path.dirname(os.path.abspath(__file__))
_CG = os.path.join(_HERE, "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_ch3b1", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)


# ---------------------------------------------------------------------------
# Fixture builders
# ---------------------------------------------------------------------------

def _signed_plan(rest_price="100.0"):
    plan = cg.build_plan(rest_price=rest_price)
    for tp in plan["planner"]["target_positions"]:
        if str(tp["side"]).strip().lower() == "short":
            tp["target_notional"] = "-200"
    return plan


def _seal_manifest(manifest: dict) -> tuple[bytes, str]:
    m = dict(manifest)
    m.pop("manifest_fingerprint", None)
    m["manifest_fingerprint"] = ws._fingerprint(m)
    raw = json.dumps(m).encode("utf-8")
    return raw, wb.compute_file_sha256(raw)


def _bundle(now=None, *, rest_price="100.0"):
    """Build a real CH2 wrapper + source bytes + a matching trusted anchor manifest."""
    now = now or time.time_ns()
    ws_art = cg.build_complete_ws_artifact(now_ns=now)
    source_bytes = json.dumps(ws_art).encode("utf-8")
    source_sha = wb.compute_file_sha256(source_bytes)
    plan = _signed_plan(rest_price=rest_price)
    epoch = now + 2_000_000
    threshold = wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS
    wrapper = wb.build_ws_bound_plan_artifact(
        plan_artifact=plan, ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=source_sha, binding_epoch_ns=epoch,
        binding_freshness_threshold_ms=threshold)
    assert wrapper["canonical_bound_plan"] is not None
    wrapper_bytes = json.dumps(wrapper).encode("utf-8")
    symbols = list(cg.STRATEGY_50)
    manifest = {
        "schema": rev.ANCHOR_MANIFEST_SCHEMA,
        "schema_version": rev.ANCHOR_MANIFEST_SCHEMA_VERSION,
        "policy_id": wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY,
        "strategy_id": wb.EXPECTED_STRATEGY_NAME,
        "run_date": cg.DATE,
        "original_plan_fingerprint": wb._fingerprint(plan),
        "source_ws_artifact_sha256": source_sha,
        "source_ws_artifact_fingerprint": ws._fingerprint(
            {k: v for k, v in ws_art.items() if k != "artifact_fingerprint"}),
        "canonical_bound_plan_fingerprint":
            wrapper["canonical_bound_plan"]["canonical_bound_plan_fingerprint"],
        "wrapper_fingerprint": wrapper["wrapper_fingerprint"],
        "binding_epoch_ns": epoch,
        "freshness_threshold_ms": threshold,
        "strategy_symbols": symbols,
        "expected_symbol_set_fingerprint":
            ws.canonical_strategy_symbol_set_fingerprint(symbols),
    }
    manifest_bytes, manifest_sha = _seal_manifest(manifest)
    return dict(
        manifest=manifest, manifest_bytes=manifest_bytes, manifest_sha=manifest_sha,
        wrapper=wrapper, wrapper_bytes=wrapper_bytes,
        ws_art=ws_art, source_bytes=source_bytes, source_sha=source_sha,
        plan=plan, epoch=epoch, threshold=threshold, symbols=symbols)


def _review(b, *, manifest_bytes=None, manifest_sha=None, wrapper_bytes=None, source_bytes=None):
    return rev.build_ws_bound_plan_review(
        anchor_manifest_bytes=manifest_bytes if manifest_bytes is not None else b["manifest_bytes"],
        expected_anchor_manifest_sha256=manifest_sha if manifest_sha is not None else b["manifest_sha"],
        wrapper_artifact_bytes=wrapper_bytes if wrapper_bytes is not None else b["wrapper_bytes"],
        source_ws_artifact_bytes=source_bytes if source_bytes is not None else b["source_bytes"])


def _remanifest(b, **overrides):
    m = dict(b["manifest"])
    m.update(overrides)
    raw, sha = _seal_manifest(m)
    return raw, sha


def _assert_failed(r):
    assert r.status != rev.WS_BOUND_PLAN_REVIEW_PASS
    assert r.passed is False
    assert r.review_artifact is None
    assert r.review_rows == ()
    assert r.offline_exposure_review_complete is False
    assert r.offline_margin_arithmetic_review_complete is False
    assert r.offline_projected_margin_review_complete is False
    assert r.execution_readiness is False
    assert r.readiness_called is False and r.execution_gate_called is False
    assert r.native_execution_called is False and r.pilot_advanced is False


# ===========================================================================
# Happy path
# ===========================================================================

def test_valid_review_passes():
    b = _bundle()
    r = _review(b)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_PASS
    assert len(r.review_rows) == 50
    longs = [a for a in r.review_rows if a.side == "long"]
    shorts = [a for a in r.review_rows if a.side == "short"]
    assert len(longs) == 25 and len(shorts) == 25
    assert all(a.target_notional == "200" and a.target_weight == "0.02" for a in longs)
    assert all(a.target_notional == "-200" and a.target_weight == "-0.02" for a in shorts)
    # active prices are the WS-bound price (100.5), never the REST seed price (100.0).
    assert all(a.price == "100.5" for a in r.review_rows)


def test_pass_offline_margin_and_freshness_semantics():
    b = _bundle()
    r = _review(b)
    assert r.offline_exposure_review_complete is True
    assert r.offline_margin_arithmetic_review_complete is True
    assert r.offline_projected_margin_rate_status == rev.OFFLINE_PROJECTED_MARGIN_RATE_UNAVAILABLE
    assert r.offline_projected_margin_review_complete is False
    assert r.account_margin_feasibility_status == rev.ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE
    assert r.binding_time_freshness_verified is True
    assert r.current_market_freshness_status == rev.CURRENT_MARKET_FRESHNESS_NOT_EVALUATED
    assert r.current_market_freshness_checked is False
    assert r.execution_readiness is False


def test_pass_exposure_totals_and_envelope_no_plan():
    b = _bundle()
    r = _review(b)
    env = r.review_artifact
    assert env["offline_exposure_totals"] == {
        "action_count": 50, "long_count": 25, "short_count": 25,
        "long_exposure_usd": "5000", "short_absolute_exposure_usd": "5000",
        "gross_exposure_usd": "10000", "net_signed_exposure_usd": "0"}
    # envelope references identities, never embeds the wrapper / canonical Plan.
    assert "canonical_bound_plan" not in env and "planner" not in env
    assert env["wrapper_file_sha256"] == wb.compute_file_sha256(b["wrapper_bytes"])
    assert env["expected_canonical_bound_plan_fingerprint"] == \
        env["recomputed_canonical_bound_plan_fingerprint"]
    assert env["anchor_manifest_sha256"] == b["manifest_sha"]
    assert env["execution_readiness"] is False and env["pilot_advanced"] is False


def test_result_is_frozen():
    r = _review(_bundle())
    with pytest.raises(dataclasses.FrozenInstanceError):
        r.status = "x"  # type: ignore[misc]


def test_review_is_deterministic():
    b = _bundle()
    r1 = _review(b)
    r2 = _review(b)
    assert r1.review_artifact["review_rows_fingerprint"] == r2.review_artifact["review_rows_fingerprint"]
    assert r1.canonical_bound_plan_fingerprint == r2.canonical_bound_plan_fingerprint


# ===========================================================================
# Manifest trust root
# ===========================================================================

def test_wrong_external_manifest_sha_fails():
    b = _bundle()
    r = _review(b, manifest_sha="sha256:" + "0" * 64)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH


def test_non_canonical_expected_manifest_sha_fails():
    b = _bundle()
    r = _review(b, manifest_sha="not-canonical")
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_malformed_manifest_bytes_fails():
    b = _bundle()
    raw = b"{not valid json"
    r = _review(b, manifest_bytes=raw, manifest_sha=wb.compute_file_sha256(raw))
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_non_object_manifest_bytes_fails():
    b = _bundle()
    raw = b"[1,2,3]"
    r = _review(b, manifest_bytes=raw, manifest_sha=wb.compute_file_sha256(raw))
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_manifest_fingerprint_mismatch_fails():
    b = _bundle()
    m = dict(b["manifest"])
    m["manifest_fingerprint"] = "sha256:" + "1" * 64  # wrong; do not reseal
    raw = json.dumps(m).encode("utf-8")
    r = _review(b, manifest_bytes=raw, manifest_sha=wb.compute_file_sha256(raw))
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH


def test_missing_required_manifest_field_fails():
    b = _bundle()
    m = dict(b["manifest"])
    m.pop("binding_epoch_ns")
    raw, sha = _seal_manifest(m)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


@pytest.mark.parametrize("field,value", [
    ("policy_id", "OTHER_POLICY"),
    ("strategy_id", "other_strategy"),
])
def test_wrong_fixed_identity_fails(field, value):
    b = _bundle()
    raw, sha = _remanifest(b, **{field: value})
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_wrong_run_date_fails_at_consumer():
    b = _bundle()
    raw, sha = _remanifest(b, run_date="2099-01-01")
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED


def test_malformed_original_plan_fingerprint_fails():
    b = _bundle()
    raw, sha = _remanifest(b, original_plan_fingerprint="nope")
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_omitted_invalid_epoch_fails():
    b = _bundle()
    raw, sha = _remanifest(b, binding_epoch_ns=0)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


@pytest.mark.parametrize("bad", [0, -1, rev.STRICT_MAX_FRESHNESS_THRESHOLD_MS + 1, "x"])
def test_invalid_threshold_fails(bad):
    b = _bundle()
    raw, sha = _remanifest(b, freshness_threshold_ms=bad)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_wrong_symbol_count_fails():
    b = _bundle()
    raw, sha = _remanifest(b, strategy_symbols=list(cg.STRATEGY_50)[:-1])
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_duplicate_symbol_fails():
    b = _bundle()
    dup = list(cg.STRATEGY_50)
    dup[1] = dup[0]
    raw, sha = _remanifest(b, strategy_symbols=dup)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_wrong_expected_symbol_set_fingerprint_fails():
    b = _bundle()
    raw, sha = _remanifest(b, expected_symbol_set_fingerprint="sha256:" + "2" * 64)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_wrong_external_symbols_set_fails():
    # 50 unique but a different set than the wrapper -> CH1 symbol-set mismatch.
    b = _bundle()
    other = [f"OTHER{i:02d}USDT" for i in range(50)]
    raw, sha = _remanifest(
        b, strategy_symbols=other,
        expected_symbol_set_fingerprint=ws.canonical_strategy_symbol_set_fingerprint(other))
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED


# ===========================================================================
# Source / wrapper identity vs external anchors
# ===========================================================================

def test_wrong_external_source_sha_fails():
    b = _bundle()
    raw, sha = _remanifest(b, source_ws_artifact_sha256="sha256:" + "3" * 64)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH


def test_wrong_external_source_fingerprint_fails():
    b = _bundle()
    raw, sha = _remanifest(b, source_ws_artifact_fingerprint="sha256:" + "4" * 64)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH


def test_optional_wrapper_fingerprint_mismatch_fails():
    b = _bundle()
    raw, sha = _remanifest(b, wrapper_fingerprint="sha256:" + "5" * 64)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH


def test_wrong_external_canonical_fingerprint_fails():
    b = _bundle()
    raw, sha = _remanifest(b, canonical_bound_plan_fingerprint="sha256:" + "6" * 64)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    # CH1 cross-checks the canonical fp anchor; either canonical-mismatch or consumer-failed.
    assert r.status in (rev.WS_BOUND_PLAN_REVIEW_CANONICAL_MISMATCH,
                        rev.WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED)


def test_mutually_resealed_wrapper_source_rejected_by_unchanged_manifest():
    b = _bundle()
    other = _bundle(now=time.time_ns() + 10 ** 9)  # internally valid, different fingerprints
    r = _review(b, wrapper_bytes=other["wrapper_bytes"], source_bytes=other["source_bytes"])
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH


def test_invalid_wrapper_bytes_fails():
    b = _bundle()
    r = _review(b, wrapper_bytes=b"{nope")
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_non_object_source_bytes_fails():
    b = _bundle()
    raw = b"[1,2,3]"
    # keep manifest source anchors as-is; bytes parse to non-object -> input invalid first
    r = _review(b, source_bytes=raw)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


# ===========================================================================
# Exposure / margin tamper (resealed so CH1 + anchors pass; review must catch)
# ===========================================================================

def _resealed_bundle(mutate_cbp):
    """Build a bundle whose canonical bound Plan is mutated, with the wrapper's own
    fingerprints + the manifest canonical/wrapper anchors RESEALED to remain internally
    consistent -- so the defect is caught by the review's independent recompute, not by
    an outer fingerprint mismatch. State per test whether CH1 or CH3 rejects."""
    b = _bundle()
    wrapper = copy.deepcopy(b["wrapper"])
    cbp = wrapper["canonical_bound_plan"]
    mutate_cbp(cbp)
    cbp["canonical_bound_plan_fingerprint"] = \
        consumer._recompute_canonical_bound_plan_fingerprint(cbp)
    wrapper["wrapper_fingerprint"] = consumer._recompute_wrapper_fingerprint(wrapper)
    wrapper_bytes = json.dumps(wrapper).encode("utf-8")
    raw, sha = _remanifest(
        b, canonical_bound_plan_fingerprint=cbp["canonical_bound_plan_fingerprint"],
        wrapper_fingerprint=wrapper["wrapper_fingerprint"])
    return b, wrapper_bytes, raw, sha


def test_qty_tamper_caught_by_consumer():
    # Tamper qty so qty/effective consistency breaks; CH1 catches it first (ACTION),
    # surfaced here as CONSUMER_FAILED -- still terminal, no envelope.
    b, wbytes, raw, sha = _resealed_bundle(
        lambda cbp: cbp["planner"]["target_positions"][0].__setitem__("qty", "7"))
    r = _review(b, manifest_bytes=raw, manifest_sha=sha, wrapper_bytes=wbytes)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED


# ===========================================================================
# FIX1 -- immutable helper boundary, margin-rate failure semantics, validation
# ===========================================================================

def test_pass_without_optional_wrapper_fingerprint():
    b = _bundle()
    raw, sha = _remanifest(b, wrapper_fingerprint=None)  # optional anchor omitted
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_PASS


def test_exposure_helper_receives_only_frozen(monkeypatch):
    captured = {}
    orig = rev._exposure_check

    def spy(rows, provenance):
        captured["rows"] = rows
        captured["prov"] = provenance
        return orig(rows, provenance)

    monkeypatch.setattr(rev, "_exposure_check", spy)
    r = _review(_bundle())
    assert r.passed
    assert isinstance(captured["rows"], tuple)
    assert all(isinstance(x, rev.WsBoundPlanReviewAction) for x in captured["rows"])
    assert isinstance(captured["prov"], tuple)
    assert all(isinstance(x, rev.WsBoundPlanReviewPriceProvenance) for x in captured["prov"])
    assert not isinstance(captured["prov"], dict)


def test_margin_helper_receives_only_frozen_scalars(monkeypatch):
    captured = {}
    orig = rev._margin_arithmetic_check

    def spy(rows, margin_inputs):
        captured["rows"] = rows
        captured["margin"] = margin_inputs
        return orig(rows, margin_inputs)

    monkeypatch.setattr(rev, "_margin_arithmetic_check", spy)
    r = _review(_bundle())
    assert r.passed
    assert isinstance(captured["rows"], tuple)
    assert isinstance(captured["margin"], rev.WsBoundPlanReviewMarginInputs)
    assert not isinstance(captured["margin"], dict)


def test_extracted_projections_have_no_container_references():
    b = _bundle()
    parsed = json.loads(b["wrapper_bytes"])
    provenance, margin_inputs, problems = rev._extract_frozen_projections(parsed)
    assert problems == []
    assert isinstance(provenance, tuple) and len(provenance) == 50
    for p in provenance:
        assert isinstance(p, rev.WsBoundPlanReviewPriceProvenance)
        for value in dataclasses.astuple(p):
            assert not isinstance(value, (dict, list))
    assert isinstance(margin_inputs, rev.WsBoundPlanReviewMarginInputs)
    for value in dataclasses.astuple(margin_inputs):
        assert not isinstance(value, (dict, list))


def test_review_rows_have_no_container_references():
    r = _review(_bundle())
    for row in r.review_rows:
        for value in dataclasses.astuple(row):
            assert not isinstance(value, (dict, list))


def test_lowercase_manifest_symbol_fails():
    b = _bundle()
    syms = list(cg.STRATEGY_50)
    syms[0] = syms[0].lower()
    raw, sha = _remanifest(
        b, strategy_symbols=syms,
        expected_symbol_set_fingerprint=ws.canonical_strategy_symbol_set_fingerprint(syms))
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_whitespace_padded_manifest_symbol_fails():
    b = _bundle()
    syms = list(cg.STRATEGY_50)
    syms[0] = " " + syms[0] + " "
    raw, sha = _remanifest(
        b, strategy_symbols=syms,
        expected_symbol_set_fingerprint=ws.canonical_strategy_symbol_set_fingerprint(syms))
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


@pytest.mark.parametrize("bad_date", ["2026-13-40", "2026-06-31", "20260622", "2026-6-2", "not-a-date"])
def test_invalid_calendar_date_fails(bad_date):
    b = _bundle()
    raw, sha = _remanifest(b, run_date=bad_date)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_malformed_source_json_fails_deterministically():
    b = _bundle()
    r = _review(b, source_bytes=b"{not valid json")
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_INPUT_INVALID


def test_wrong_external_canonical_fingerprint_precise_status():
    b = _bundle()
    raw, sha = _remanifest(b, canonical_bound_plan_fingerprint="sha256:" + "9" * 64)
    r = _review(b, manifest_bytes=raw, manifest_sha=sha)
    _assert_failed(r)
    # CH1 takes no canonical-fp input; CH3 pins it -> precise CANONICAL_MISMATCH.
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_CANONICAL_MISMATCH


def test_missing_wrapper_embedded_gross_caught_by_ch3_margin():
    # CH1 fp covers strategy_gross_notional but not its presence/value; CH3 requires it.
    b, wbytes, raw, sha = _resealed_bundle(
        lambda cbp: cbp["rebuilt_price_dependent_review"].pop("strategy_gross_notional", None))
    r = _review(b, manifest_bytes=raw, manifest_sha=sha, wrapper_bytes=wbytes)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_MARGIN_ARITHMETIC_FAILED
    assert r.offline_projected_margin_rate_status == rev.OFFLINE_PROJECTED_MARGIN_RATE_NOT_EVALUATED


def test_wrong_wrapper_embedded_gross_fails():
    b, wbytes, raw, sha = _resealed_bundle(
        lambda cbp: cbp["rebuilt_price_dependent_review"].__setitem__("strategy_gross_notional", "9999"))
    r = _review(b, manifest_bytes=raw, manifest_sha=sha, wrapper_bytes=wbytes)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_MARGIN_ARITHMETIC_FAILED


def test_non_null_wrapper_applicable_account_rate_fails():
    b, wbytes, raw, sha = _resealed_bundle(
        lambda cbp: cbp["rebuilt_price_dependent_review"]["projected_margin_model"].__setitem__(
            "applicable_initial_margin_rate", "0.05"))
    r = _review(b, manifest_bytes=raw, manifest_sha=sha, wrapper_bytes=wbytes)
    _assert_failed(r)
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_MARGIN_ARITHMETIC_FAILED


def test_failure_result_uses_dedicated_margin_rate_not_evaluated():
    r = _review(_bundle(), manifest_sha="sha256:" + "0" * 64)  # MANIFEST_MISMATCH
    _assert_failed(r)
    assert r.offline_projected_margin_rate_status == rev.OFFLINE_PROJECTED_MARGIN_RATE_NOT_EVALUATED


def test_pass_full_field_invariants():
    r = _review(_bundle())
    assert r.status == rev.WS_BOUND_PLAN_REVIEW_PASS
    longs = [a for a in r.review_rows if a.side == "long"]
    shorts = [a for a in r.review_rows if a.side == "short"]
    assert len(r.review_rows) == 50 and len(longs) == 25 and len(shorts) == 25
    assert all(a.target_notional == "-200" for a in shorts)
    t = r.review_artifact["offline_exposure_totals"]
    assert (t["gross_exposure_usd"], t["long_exposure_usd"],
            t["short_absolute_exposure_usd"], t["net_signed_exposure_usd"]) == \
        ("10000", "5000", "5000", "0")
    assert r.binding_time_freshness_verified is True
    assert r.current_market_freshness_status == rev.CURRENT_MARKET_FRESHNESS_NOT_EVALUATED
    assert r.offline_projected_margin_rate_status == rev.OFFLINE_PROJECTED_MARGIN_RATE_UNAVAILABLE
    assert r.offline_projected_margin_review_complete is False
    assert r.account_margin_feasibility_status == rev.ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE
    assert r.execution_readiness is False


# ===========================================================================
# Static / safety properties
# ===========================================================================

def test_module_has_no_forbidden_imports():
    import ast
    import src.demo_strategy_native_ws_bound_plan_review as m
    src_text = open(m.__file__, encoding="utf-8").read()
    tree = ast.parse(src_text)
    top_modules: set[str] = set()
    src_leaves: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                top_modules.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            top_modules.add((node.module or "").split(".")[0])
            if (node.module or "") == "src":
                for n in node.names:
                    src_leaves.add(n.name)
    # No network / os / time / wall-clock-capable stdlib imports in the pure core.
    assert not (top_modules & {"os", "time", "socket", "requests", "urllib", "http",
                               "asyncio", "ssl", "websocket", "websockets"}), top_modules
    # No runner / readiness / gate / execution / sender / Pilot / reporting imports.
    assert not (src_leaves & {
        "demo_strategy_pilot_readiness", "demo_strategy_pilot_execution_gate",
        "demo_strategy_pilot_native_execution", "demo_strategy_pilot_native_reporting",
        "demo_strategy_pilot_lifecycle", "demo_strategy_pilot_store",
        "demo_strategy_pilot_daily_runner"}), src_leaves
    # Precise runtime/endpoint tokens that never legitimately appear as substrings.
    for tok in ("execute_daily_native", "evaluate_execution_gate", "PilotStateStore",
                "advance_successful_day", "run_demo_strategy_pilot_native_daily",
                "api-demo.bybit", "wss://", "https://", "/v5/"):
        assert tok not in src_text, tok
