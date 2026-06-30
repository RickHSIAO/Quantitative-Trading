"""TASK-014CH4A -- read-only CURRENT market + Demo-account feasibility.

Fully offline. Builds a REAL trusted CH3C2 input chain (canonical wrapper -> anchor
manifest -> CH3B1 review) from the audited CG fixtures, then drives the pure CH4A core
and the CLI with INJECTED fake transports. Proves: trusted-input pinning fails closed on
any SHA/lineage mismatch; current market evidence + current Decimal quantity recompute;
authenticated Demo-only account evidence with Live denied; the Decimal margin model;
and that NO order/sender/readiness/execution/Pilot path is ever reachable (all order
counters zero, execution never authorized).
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
from src import demo_strategy_native_ws_bound_plan_review as wsbpr
from src import demo_strategy_native_current_feasibility as cf

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))

_CG = os.path.join(_HERE, "test_demo_strategy_native_ws_price_binding_cg.py")
_spec = importlib.util.spec_from_file_location("_cg_helpers_ch4a", _CG)
cg = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(cg)

_SCRIPT = os.path.join(_ROOT, "scripts", "run_demo_strategy_current_feasibility.py")
_sspec = importlib.util.spec_from_file_location("crun_ch4a", _SCRIPT)
crun = importlib.util.module_from_spec(_sspec)
_sspec.loader.exec_module(crun)


# ---------------------------------------------------------------------------
# Trusted CH3C2 input chain (real wrapper -> manifest -> CH3B1 review)
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


def build_trusted_chain(now=None):
    """Return a dict of byte blobs + SHAs for the full trusted input chain."""
    now = now or 1_700_000_000_000_000_000
    ws_art = cg.build_complete_ws_artifact(now_ns=now)
    source_bytes = json.dumps(ws_art).encode("utf-8")
    source_sha = wb.compute_file_sha256(source_bytes)
    plan = _signed_plan()
    epoch = now + 2_000_000
    threshold = wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS
    wrapper = wb.build_ws_bound_plan_artifact(
        plan_artifact=plan, ws_artifact=ws_art, ws_artifact_path="ws.json",
        ws_artifact_sha256=source_sha, binding_epoch_ns=epoch,
        binding_freshness_threshold_ms=threshold)
    assert wrapper["canonical_bound_plan"] is not None
    wrapper_bytes = json.dumps(wrapper).encode("utf-8")
    symbols = sorted(cg.STRATEGY_50)
    manifest = {
        "schema": wsbpr.ANCHOR_MANIFEST_SCHEMA,
        "schema_version": wsbpr.ANCHOR_MANIFEST_SCHEMA_VERSION,
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

    review_res = wsbpr.build_ws_bound_plan_review(
        anchor_manifest_bytes=manifest_bytes,
        expected_anchor_manifest_sha256=manifest_sha,
        wrapper_artifact_bytes=wrapper_bytes,
        source_ws_artifact_bytes=source_bytes)
    assert review_res.status == wsbpr.WS_BOUND_PLAN_REVIEW_PASS
    review_bytes = json.dumps(review_res.review_artifact).encode("utf-8")
    review_sha = wb.compute_file_sha256(review_bytes)

    symbols_bytes = json.dumps(symbols).encode("utf-8")
    symbols_sha = wb.compute_file_sha256(symbols_bytes)
    return {
        "review_bytes": review_bytes, "review_sha": review_sha,
        "manifest_bytes": manifest_bytes, "manifest_sha": manifest_sha,
        "wrapper_bytes": wrapper_bytes,
        "symbols_bytes": symbols_bytes, "symbols_sha": symbols_sha,
        "symbols": symbols,
    }


def _trusted(c=None):
    c = c or build_trusted_chain()
    return cf.validate_trusted_inputs(
        review_artifact_bytes=c["review_bytes"],
        expected_review_artifact_sha256=c["review_sha"],
        anchor_manifest_bytes=c["manifest_bytes"],
        expected_anchor_manifest_sha256=c["manifest_sha"],
        wrapper_artifact_bytes=c["wrapper_bytes"],
        strategy_symbols_bytes=c["symbols_bytes"],
        expected_strategy_symbols_sha256=c["symbols_sha"])


# ---------------------------------------------------------------------------
# Fixture market + account evidence
# ---------------------------------------------------------------------------

_COLLECTION_NS = 2_000_000_000_000_000_000
_DEMO_TICKERS = "https://api-demo.bybit.com/v5/market/tickers"


def _market_record(symbol, *, price="100.0", age_ms=1, qty_step="0.001",
                   min_qty="0.001", min_notional="5", max_mkt="0",
                   status="Trading", trading=True, contract="LinearPerpetual",
                   settle="USDT", endpoint=_DEMO_TICKERS):
    return {
        "symbol": symbol, "current_price": price,
        "exchange_ts_ms": int(_COLLECTION_NS / 1_000_000) - age_ms,
        "local_received_epoch_ns": _COLLECTION_NS - age_ms * 1_000_000,
        "endpoint": endpoint, "instrument_status": status,
        "tick_size": "0.01", "qty_step": qty_step, "min_order_qty": min_qty,
        "min_notional_value": min_notional, "max_market_order_qty": max_mkt,
        "contract_type": contract, "settle_coin": settle, "trading": trading,
    }


def _market_records(symbols, **over):
    return [_market_record(s, **over) for s in symbols]


def _account_snapshot(symbols, *, equity="10000", available="9000",
                      rate="0.1", rate_source="trusted_projected_margin_evidence",
                      account_im_rate_context=None,
                      positions=None, demo=True, base_url="https://api-demo.bybit.com",
                      live_fallback=False, position_mode="one_way",
                      wallet_present=True, age_ms=1, existing_im="0"):
    return {
        "endpoint_family": "bybit_demo" if demo else "unknown",
        "demo_flag": demo, "base_url": base_url,
        "live_endpoint_fallback_detected": live_fallback,
        "account_mode": "demo", "margin_mode": "REGULAR_MARGIN",
        "position_mode": position_mode, "wallet_evidence_present": wallet_present,
        "account_equity_usd": equity, "available_balance_usd": available,
        "existing_initial_margin_usd": existing_im,
        "existing_maintenance_margin_usd": "0",
        "applicable_initial_margin_rate": rate, "margin_rate_source": rate_source,
        "account_im_rate_context": account_im_rate_context,
        "positions": positions if positions is not None else [],
        "snapshot_epoch_ns": _COLLECTION_NS - age_ms * 1_000_000,
    }


def _market(symbols, **over):
    return cf.evaluate_current_market_and_quantities(
        _market_records(symbols, **over), targets=_trusted().targets,
        collection_epoch_ns=_COLLECTION_NS)


# ===========================================================================
# 1. Trusted input validation
# ===========================================================================

def test_trusted_inputs_valid_chain_passes():
    r = _trusted()
    assert r.ok and r.status == "TRUSTED_INPUTS_OK"
    assert len(r.targets) == 50 and len(r.symbols) == 50
    longs = sum(1 for t in r.targets if t.side == "long")
    shorts = sum(1 for t in r.targets if t.side == "short")
    assert longs == 25 and shorts == 25
    assert all(abs(Decimal(t.target_signed_notional_usd)) == Decimal("200") for t in r.targets)


def test_trusted_review_sha_mismatch_fails():
    c = build_trusted_chain()
    c["review_sha"] = "sha256:" + "a" * 64
    r = _trusted(c)
    assert not r.ok and any("review_artifact_sha256_not_expected" in b for b in r.blockers)


def test_trusted_manifest_sha_mismatch_fails():
    c = build_trusted_chain()
    c["manifest_sha"] = "sha256:" + "b" * 64
    r = _trusted(c)
    assert not r.ok and any("anchor_manifest_sha256_not_expected" in b for b in r.blockers)


def test_trusted_symbols_sha_mismatch_fails():
    c = build_trusted_chain()
    c["symbols_sha"] = "sha256:" + "c" * 64
    r = _trusted(c)
    assert not r.ok and any("strategy_symbols_sha256_not_expected" in b for b in r.blockers)


def test_trusted_malformed_sha_fails():
    c = build_trusted_chain()
    c["review_sha"] = "not-a-sha"
    r = _trusted(c)
    assert not r.ok and any("expected_review_sha256_not_canonical" in b for b in r.blockers)


def test_trusted_wrapper_canonical_fingerprint_tamper_fails():
    c = build_trusted_chain()
    w = json.loads(c["wrapper_bytes"])
    w["canonical_bound_plan"]["canonical_bound_plan_fingerprint"] = "sha256:" + "0" * 64
    c["wrapper_bytes"] = json.dumps(w).encode("utf-8")
    r = _trusted(c)
    assert not r.ok


def test_trusted_review_not_pass_status_fails():
    c = build_trusted_chain()
    rev = json.loads(c["review_bytes"])
    rev["status"] = "WS_BOUND_PLAN_REVIEW_INPUT_INVALID"
    c["review_bytes"] = json.dumps(rev).encode("utf-8")
    c["review_sha"] = wb.compute_file_sha256(c["review_bytes"])
    r = _trusted(c)
    assert not r.ok and any("review_status_not_pass" in b for b in r.blockers)


def test_trusted_review_manifest_link_broken_fails():
    c = build_trusted_chain()
    rev = json.loads(c["review_bytes"])
    rev["anchor_manifest_sha256"] = "sha256:" + "d" * 64
    c["review_bytes"] = json.dumps(rev).encode("utf-8")
    c["review_sha"] = wb.compute_file_sha256(c["review_bytes"])
    r = _trusted(c)
    assert not r.ok and any("review_anchor_manifest_sha256_mismatch" in b for b in r.blockers)


# ===========================================================================
# 2. Current market evidence + quantity recomputation
# ===========================================================================

def test_market_fifty_fresh_symbols_pass():
    syms = _trusted().symbols
    m = _market(syms)
    assert m.ok and m.status == cf.MARKET_EVIDENCE_FRESH
    assert m.evaluated_symbol_count == 50 and m.long_count == 25 and m.short_count == 25
    assert m.quantity_all_valid is True
    # current sizing is recomputed from the CURRENT price, NOT the binding qty.
    a0 = m.actions[0]
    assert a0.rounded_quantity == "2"  # 200 / 100.0
    assert a0.rounded_notional_usd == "200"
    assert a0.binding_qty and a0.rounded_quantity != a0.binding_qty


def test_market_missing_symbol_blocks():
    syms = _trusted().symbols
    recs = _market_records(syms)[:-1]  # drop one
    m = cf.evaluate_current_market_and_quantities(
        recs, targets=_trusted().targets, collection_epoch_ns=_COLLECTION_NS)
    assert not m.ok and m.status == cf.MARKET_EVIDENCE_INCOMPLETE
    assert any("market_record_missing_symbol" in b for b in m.blockers)


def test_market_duplicate_symbol_blocks():
    syms = _trusted().symbols
    recs = _market_records(syms)
    recs.append(_market_record(syms[0]))  # duplicate
    m = cf.evaluate_current_market_and_quantities(
        recs, targets=_trusted().targets, collection_epoch_ns=_COLLECTION_NS)
    assert not m.ok
    assert any("market_record_duplicate_symbol" in b for b in m.blockers)


def test_market_stale_price_blocks():
    syms = _trusted().symbols
    m = _market(syms, age_ms=20_000)  # > 10_000 threshold
    assert not m.ok and m.status == cf.MARKET_EVIDENCE_STALE
    assert any("stale_evidence" in c
               for a in m.actions for c in a.quantity_validation_failures)


def test_market_non_trading_instrument_blocks():
    syms = _trusted().symbols
    m = _market(syms, status="PreLaunch", trading=False)
    assert not m.ok
    assert any("instrument_not_trading" in c
               for a in m.actions for c in a.quantity_validation_failures)


def test_market_unsupported_contract_type_blocks():
    syms = _trusted().symbols
    m = _market(syms, contract="InversePerpetual")
    assert not m.ok
    assert any("contract_type_unsupported" in c
               for a in m.actions for c in a.quantity_validation_failures)


def test_market_missing_instrument_rule_blocks():
    syms = _trusted().symbols
    recs = _market_records(syms)
    del recs[0]["qty_step"]
    m = cf.evaluate_current_market_and_quantities(
        recs, targets=_trusted().targets, collection_epoch_ns=_COLLECTION_NS)
    assert not m.ok
    assert any("missing_market_fields" in c or "qty_step_not_positive" in c
               for a in m.actions for c in a.quantity_validation_failures)


# --- quantity calculations -------------------------------------------------

def test_quantity_deterministic_decimal_and_step_rounding():
    syms = _trusted().symbols
    m = _market(syms, price="3.0", qty_step="0.1")
    # 200 / 3 = 66.666..., floored to 0.1 step -> 66.6
    a = m.actions[0]
    assert a.rounded_quantity == "66.6"
    assert a.rounded_notional_usd == "199.8"  # 66.6 * 3
    assert a.quantity_validation_status == cf.QTY_VALIDATION_OK


def test_quantity_below_min_order_qty_fails():
    syms = _trusted().symbols
    m = _market(syms, price="100.0", qty_step="0.001", min_qty="5")  # qty 2 < 5
    assert not m.ok
    assert any("below_min_order_qty" in c
               for a in m.actions for c in a.quantity_validation_failures)


def test_quantity_below_min_notional_fails():
    syms = _trusted().symbols
    m = _market(syms, price="100.0", min_notional="500")  # notional 200 < 500
    assert not m.ok
    assert any("below_min_notional" in c
               for a in m.actions for c in a.quantity_validation_failures)


def test_quantity_above_max_market_qty_fails():
    syms = _trusted().symbols
    m = _market(syms, price="100.0", qty_step="0.001", max_mkt="1")  # qty 2 > 1
    assert not m.ok
    assert any("above_max_market_order_qty" in c
               for a in m.actions for c in a.quantity_validation_failures)


def test_quantity_zero_after_rounding_fails():
    syms = _trusted().symbols
    # price huge + coarse step -> 200 / 1e6 floored to step 1 = 0
    m = _market(syms, price="1000000", qty_step="1", min_qty="0", min_notional="0")
    assert not m.ok
    assert any("zero_quantity_after_rounding" in c
               for a in m.actions for c in a.quantity_validation_failures)


def test_quantity_structure_invariants_preserved():
    syms = _trusted().symbols
    m = _market(syms)
    assert m.long_count == 25 and m.short_count == 25
    assert all(abs(Decimal(a.target_signed_notional_usd)) == Decimal("200") for a in m.actions)
    assert Decimal(m.total_target_gross_notional_usd) == Decimal("10000")


# ===========================================================================
# 3. Demo account evidence
# ===========================================================================

def test_account_demo_host_accepted():
    syms = _trusted().symbols
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms), target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    assert a.ok and a.demo_environment_verified and a.live_environment_denied


def test_account_live_host_rejected():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, base_url="https://api.bybit.com")
    a = cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    assert not a.ok
    assert any("demo_environment_not_verified" in b or "live_environment_not_denied" in b
               for b in a.blockers)


def test_account_missing_wallet_unavailable():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, wallet_present=False, equity=None, available=None)
    a = cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    assert a.status == cf.ACCOUNT_EVIDENCE_UNAVAILABLE


def test_account_stale_evidence_blocks():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, age_ms=10_000_000)  # ~10s old vs 60s? make huge
    snap["snapshot_epoch_ns"] = _COLLECTION_NS - 999_000_000_000  # ~999s old
    a = cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    assert not a.ok and any("account_evidence_stale" in b for b in a.blockers)


def test_account_malformed_position_blocks():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, positions=[{"symbol": "FOOUSDT", "side": "long",
                                               "size": "not-a-number"}])
    a = cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    assert not a.ok and any("position_size_unparseable" in b for b in a.blockers)


def test_account_position_mode_incompatible_blocks():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, position_mode="portfolio_margin")
    a = cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    assert not a.ok and any("position_mode_unsupported" in b for b in a.blockers)


def test_account_strategy_overlap_with_open_position_blocks():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, positions=[{"symbol": syms[0], "side": "long",
                                               "size": "1.0", "leverage": "1"}])
    a = cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    assert not a.ok
    assert any("strategy_target_overlaps_open_position" in b for b in a.blockers)


def test_account_protected_position_identified_from_snapshot():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, positions=[{"symbol": "ENAUSDT", "side": "long",
                                               "size": "3.0", "leverage": "1"}])
    a = cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    # ENAUSDT is a protected legacy position, not a strategy target -> identified, not overlap.
    assert "ENAUSDT" in a.protected_positions
    assert a.ok


def test_account_evidence_never_contains_secret_in_artifact():
    syms = _trusted().symbols
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms), target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    art = cf.build_account_evidence_artifact(
        account=a, collection_epoch_ns=_COLLECTION_NS, collected_at_utc="t",
        network_audit=cf.zeroed_network_audit())
    assert art["credential_leak_check"] == cf.CREDENTIAL_LEAK_CLEAR
    blob = json.dumps(art)
    for forbidden in ("api_key", "apikey", "secret", "x-bapi-sign"):
        assert forbidden not in blob.lower()


# ===========================================================================
# 4. Margin feasibility
# ===========================================================================

def _account_ok(syms, **over):
    return cf.evaluate_demo_account_evidence(
        _account_snapshot(syms, **over), target_symbols=syms,
        collection_epoch_ns=_COLLECTION_NS)


def test_margin_pass_with_independent_rate():
    syms = _trusted().symbols
    a = _account_ok(syms, available="9000", rate="0.1")
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_PASS
    assert mg.projected_additional_initial_margin_usd == "1000"  # 10000 * 0.1
    assert Decimal(mg.remaining_available_balance_usd) > 0


def test_margin_insufficient_balance_blocks():
    syms = _trusted().symbols
    a = _account_ok(syms, available="500", rate="0.1")
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_BLOCKED
    assert "insufficient_available_balance" in mg.failures


def test_margin_unknown_rate_unavailable_never_pass():
    syms = _trusted().symbols
    a = _account_ok(syms, rate=None, rate_source=None)
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_UNAVAILABLE
    assert "initial_margin_rate_unknown" in mg.failures
    assert mg.conservative_1x_envelope_usd == "10000"


def test_margin_safety_headroom_violation_blocks():
    syms = _trusted().symbols
    a = _account_ok(syms, available="1100", rate="0.1")  # remaining 95 < headroom 110
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_BLOCKED
    assert "safety_headroom_violation" in mg.failures


def test_margin_decimal_determinism():
    syms = _trusted().symbols
    a = _account_ok(syms, available="9000", rate="0.123")
    r1 = cf.evaluate_margin_feasibility(account_result=a, target_gross_notional_usd=cf.V1_GROSS_USD)
    r2 = cf.evaluate_margin_feasibility(account_result=a, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert r1 == r2
    assert r1.projected_additional_initial_margin_usd == "1230"  # 10000 * 0.123


# ===========================================================================
# 5. Top-level feasibility review + safety
# ===========================================================================

def _full_review(*, market_over=None, account_over=None):
    t = _trusted()
    syms = t.symbols
    m = cf.evaluate_current_market_and_quantities(
        _market_records(syms, **(market_over or {})), targets=t.targets,
        collection_epoch_ns=_COLLECTION_NS)
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms, **(account_over or {})), target_symbols=syms,
        collection_epoch_ns=_COLLECTION_NS)
    mg = cf.evaluate_margin_feasibility(account_result=a, target_gross_notional_usd=cf.V1_GROSS_USD)
    return cf.build_current_feasibility_review(
        trusted=t, market=m, account=a, margin=mg, collection_epoch_ns=_COLLECTION_NS,
        reviewed_at_utc="t", network_audit=cf.zeroed_network_audit())


def test_feasibility_pass_is_never_execution_ready():
    fr = _full_review()
    assert fr.status == cf.CURRENT_FEASIBILITY_PASS
    rev = fr.review_artifact
    for f in ("execution_readiness", "execution_authorized", "execution_batch_authorized",
              "readiness_called", "execution_gate_called", "native_execution_called",
              "sender_reachable", "pilot_advanced", "rest_fallback_used"):
        assert rev[f] is False
    for c in ("order_post_count", "amend_post_count", "cancel_post_count",
              "live_order_post_count"):
        assert rev[c] == 0
    assert rev["current_market_freshness_status"] == cf.MARKET_EVIDENCE_FRESH
    assert rev["current_market_freshness_checked"] is True
    assert rev["demo_environment_verified"] is True
    assert rev["live_environment_denied"] is True
    assert rev["artifact_fingerprint"] == wb._fingerprint(
        {k: v for k, v in rev.items() if k != "artifact_fingerprint"})


def test_feasibility_market_failure_propagates():
    fr = _full_review(market_over={"age_ms": 30_000})
    assert fr.status == cf.CURRENT_FEASIBILITY_MARKET_EVIDENCE_FAILED
    assert fr.review_artifact["execution_readiness"] is False


def test_feasibility_account_block_propagates():
    fr = _full_review(account_over={"base_url": "https://api.bybit.com"})
    assert fr.status == cf.CURRENT_FEASIBILITY_ACCOUNT_EVIDENCE_FAILED


def test_feasibility_unknown_rate_is_unavailable_not_pass():
    fr = _full_review(account_over={"rate": None, "rate_source": None})
    assert fr.status == cf.CURRENT_FEASIBILITY_UNAVAILABLE


# ===========================================================================
# 6. CLI wiring (injected fake transports; offline temp files)
# ===========================================================================

def _live_market_record(symbol, now_ns):
    return {
        "symbol": symbol, "current_price": "100.0",
        "exchange_ts_ms": int(now_ns / 1_000_000) - 1,
        "local_received_epoch_ns": now_ns - 1_000_000,
        "endpoint": _DEMO_TICKERS, "instrument_status": "Trading",
        "tick_size": "0.01", "qty_step": "0.001", "min_order_qty": "0.001",
        "min_notional_value": "5", "max_market_order_qty": "0",
        "contract_type": "LinearPerpetual", "settle_coin": "USDT", "trading": True,
    }


def _fake_market_provider(symbols, allow_real_network):
    # Anchored to real current time so freshness holds against the CLI's own epoch.
    assert allow_real_network is False
    now_ns = time.time_ns()
    audit = cf.zeroed_network_audit()
    audit["public_http_get_count"] = len(symbols)
    return [_live_market_record(s, now_ns) for s in symbols], audit


def _fake_account_provider(symbols, allow_real_network):
    assert allow_real_network is False
    now_ns = time.time_ns()
    audit = cf.zeroed_network_audit()
    audit["private_demo_http_get_count"] = 3
    snap = _account_snapshot(symbols)
    snap["snapshot_epoch_ns"] = now_ns - 1_000_000
    return snap, audit


def _write_inputs(tmp_path):
    c = build_trusted_chain()
    (tmp_path / "review.json").write_bytes(c["review_bytes"])
    (tmp_path / "manifest.json").write_bytes(c["manifest_bytes"])
    (tmp_path / "wrapper.json").write_bytes(c["wrapper_bytes"])
    (tmp_path / "symbols.json").write_bytes(c["symbols_bytes"])
    return c


def _argv(tmp_path, c, *, extra=None):
    argv = ["--current-market-demo-account-feasibility-read-only",
            "--review-artifact-json", str(tmp_path / "review.json"),
            "--review-artifact-sha256", c["review_sha"],
            "--anchor-manifest-json", str(tmp_path / "manifest.json"),
            "--anchor-manifest-sha256", c["manifest_sha"],
            "--wrapper-json", str(tmp_path / "wrapper.json"),
            "--strategy-symbols-json", str(tmp_path / "symbols.json"),
            "--strategy-symbols-sha256", c["symbols_sha"],
            "--market-evidence-output-json", str(tmp_path / "market.json"),
            "--account-evidence-output-json", str(tmp_path / "account.json"),
            "--feasibility-review-output-json", str(tmp_path / "review_out.json"),
            "--summary-output-json", str(tmp_path / "summary.json")]
    if extra:
        argv += extra
    return argv


def _run(tmp_path, c, **over):
    return crun.main(_argv(tmp_path, c, **over),
                     market_provider=_fake_market_provider,
                     account_provider=_fake_account_provider)


def test_cli_valid_writes_four_artifacts_and_passes(tmp_path, capsys):
    c = _write_inputs(tmp_path)
    rc = _run(tmp_path, c)
    assert rc == crun.EXIT_OK
    for name in ("market.json", "account.json", "review_out.json", "summary.json"):
        assert (tmp_path / name).exists()
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == cf.CURRENT_FEASIBILITY_PASS
    assert summary["execution_authorized"] is False
    assert summary["order_post_count"] == 0
    assert summary["network_audit"]["order_post_count"] == 0
    assert summary["network_audit"]["private_mutating_request_count"] == 0
    # the review artifact's recorded SHA equals the on-disk file SHA.
    review_bytes = (tmp_path / "review_out.json").read_bytes()
    assert summary["feasibility_review_artifact_sha256"] == wb.compute_file_sha256(review_bytes)
    # honest bundle completeness: all three core files exist + hashes match.
    assert summary["bundle_publication_status"] == cf.BUNDLE_COMPLETE
    assert summary["published_artifacts"]["market_evidence"] == \
        wb.compute_file_sha256((tmp_path / "market.json").read_bytes())


def test_cli_missing_mode_flag_rejected(tmp_path, capsys):
    c = _write_inputs(tmp_path)
    rc = crun.main([a for a in _argv(tmp_path, c)
                    if a != "--current-market-demo-account-feasibility-read-only"],
                   market_provider=_fake_market_provider,
                   account_provider=_fake_account_provider)
    assert rc == crun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == cf.CURRENT_FEASIBILITY_INPUT_INVALID


@pytest.mark.parametrize("flag", ["--send-orders-to-demo", "--advance-on-success",
                                  "--ws-bound-plan-only", "--execute"])
def test_cli_conflicting_execution_flag_rejected_before_side_effects(flag, tmp_path, capsys):
    c = _write_inputs(tmp_path)
    rc = _run(tmp_path, c, extra=[flag])
    assert rc == crun.EXIT_INVALID
    assert not (tmp_path / "market.json").exists()
    assert json.loads(capsys.readouterr().out)["status"] == cf.CURRENT_FEASIBILITY_INPUT_INVALID


def test_cli_review_sha_mismatch_rejected(tmp_path, capsys):
    c = _write_inputs(tmp_path)
    argv = _argv(tmp_path, c)
    i = argv.index("--review-artifact-sha256")
    argv[i + 1] = "sha256:" + "a" * 64
    rc = crun.main(argv, market_provider=_fake_market_provider,
                   account_provider=_fake_account_provider)
    assert rc == crun.EXIT_INVALID
    assert not (tmp_path / "market.json").exists()


def test_cli_input_output_alias_rejected(tmp_path, capsys):
    c = _write_inputs(tmp_path)
    argv = _argv(tmp_path, c)
    i = argv.index("--market-evidence-output-json")
    argv[i + 1] = str(tmp_path / "review.json")  # alias of an input
    rc = crun.main(argv, market_provider=_fake_market_provider,
                   account_provider=_fake_account_provider)
    assert rc == crun.EXIT_INVALID
    assert json.loads(capsys.readouterr().out)["status"] == cf.CURRENT_FEASIBILITY_INPUT_INVALID


def test_cli_preexisting_output_not_clobbered(tmp_path, capsys):
    c = _write_inputs(tmp_path)
    sentinel = b'{"sentinel": true}'
    (tmp_path / "summary.json").write_bytes(sentinel)
    rc = _run(tmp_path, c)
    assert rc == crun.EXIT_INVALID
    assert (tmp_path / "summary.json").read_bytes() == sentinel  # untouched


def test_cli_no_sender_or_pilot_modules_imported():
    # The CLI must not IMPORT any sender / readiness / execution / Pilot / risk module.
    import ast
    src = open(_SCRIPT, encoding="utf-8").read()
    imported: list[str] = []
    for node in ast.walk(ast.parse(src)):
        if isinstance(node, ast.Import):
            imported += [a.name for a in node.names]
        elif isinstance(node, ast.ImportFrom):
            imported.append(node.module or "")
            imported += [f"{node.module}.{a.name}" for a in node.names]
    blob = " ".join(imported)
    for forbidden in ("native_execution", "execution_gate", "pilot_store",
                      "pilot_readiness", "sender", "BybitExecutor", "src.risk",
                      "pilot_native_execution"):
        assert forbidden not in blob, (forbidden, imported)


def test_cli_no_order_endpoint_strings_in_sources():
    for path in (_SCRIPT,
                 os.path.join(_ROOT, "src", "demo_strategy_native_current_feasibility.py")):
        src = open(path, encoding="utf-8").read()
        for forbidden in ("/v5/order/create", "/v5/order/amend", "/v5/order/cancel",
                          "set-leverage", "set-margin-mode"):
            assert forbidden not in src, (path, forbidden)


# ===========================================================================
# CH4A_FIX1 -- position-mode evidence
# ===========================================================================

def test_position_mode_proven_one_way_passes():
    syms = _trusted().symbols
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms, position_mode="one_way"), target_symbols=syms,
        collection_epoch_ns=_COLLECTION_NS)
    assert a.ok and a.position_mode == "one_way"


def test_position_mode_proven_hedge_represented():
    syms = _trusted().symbols
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms, position_mode="hedge"), target_symbols=syms,
        collection_epoch_ns=_COLLECTION_NS)
    assert a.ok and a.position_mode == "hedge"


def test_position_mode_unknown_blocks():
    syms = _trusted().symbols
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms, position_mode=None), target_symbols=syms,
        collection_epoch_ns=_COLLECTION_NS)
    assert not a.ok and any("position_mode_unavailable" in b for b in a.blockers)


def test_provider_does_not_hardcode_position_mode_and_derives_from_positionidx():
    src = open(_SCRIPT, encoding="utf-8").read()
    # No hardcoded one-way default in the real account provider.
    assert '"position_mode": "one_way"' not in src
    assert "_derive_position_mode(" in src

    class _P:  # minimal positionIdx-bearing position stand-ins
        def __init__(self, idx, qty=1.0):
            self.position_idx = idx
            self.quantity = qty
    assert crun._derive_position_mode([_P(0), _P(0)]) == "one_way"
    assert crun._derive_position_mode([_P(0), _P(1)]) == "hedge"
    assert crun._derive_position_mode([]) is None           # no positions -> unprovable
    assert crun._derive_position_mode([_P(None)]) is None   # idx absent -> unprovable


# ===========================================================================
# CH4A_FIX1 -- protected-position semantics (all pre-existing positions protected)
# ===========================================================================

def test_unseen_preexisting_position_becomes_protected():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, positions=[
        {"symbol": "NEWCOINUSDT", "side": "long", "size": "2.0", "leverage": "1"}])
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    # Not in the historical list, not a strategy target -> still protected, no anchor match.
    assert "NEWCOINUSDT" in a.protected_positions
    assert "NEWCOINUSDT" not in a.historical_protected_anchor
    assert a.ok


def test_historical_protected_symbol_remains_protected_and_anchored():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, positions=[
        {"symbol": "ENAUSDT", "side": "long", "size": "3.0", "leverage": "1"}])
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    assert "ENAUSDT" in a.protected_positions
    assert "ENAUSDT" in a.historical_protected_anchor
    assert a.ok


def test_flat_positions_ignored_not_protected():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, positions=[
        {"symbol": "FLATUSDT", "side": "long", "size": "0", "leverage": "1"}])
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    assert a.protected_positions == ()
    assert a.open_position_count == 0
    assert a.ok


def test_all_nonzero_positions_protected_and_overlap_blocks():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, positions=[
        {"symbol": "NEWCOINUSDT", "side": "long", "size": "1.0", "leverage": "1"},
        {"symbol": syms[0], "side": "long", "size": "1.0", "leverage": "1"}])
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    assert set(a.protected_positions) == {"NEWCOINUSDT", syms[0]}  # both protected
    assert not a.ok
    assert any("strategy_target_overlaps_open_position" in b for b in a.blockers)


# ===========================================================================
# CH4A_FIX1 -- margin-rate semantics (accountIMRate is context, not projected rate)
# ===========================================================================

def test_account_im_rate_alone_is_unavailable_never_pass():
    syms = _trusted().symbols
    # accountIMRate supplied as the rate source -> rejected as account-level context.
    snap = _account_snapshot(syms, rate="0.1", rate_source="wallet.accountIMRate")
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    assert a.applicable_initial_margin_rate is None  # not used as projected rate
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_UNAVAILABLE
    assert "initial_margin_rate_unknown" in mg.failures


def test_account_im_rate_context_preserved_separately():
    syms = _trusted().symbols
    snap = _account_snapshot(syms, rate=None, rate_source=None,
                             account_im_rate_context="0.03")
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    assert a.account_im_rate_context == "0.03"
    assert a.applicable_initial_margin_rate is None


def test_injected_trusted_projected_margin_evidence_may_pass():
    syms = _trusted().symbols
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms, available="9000", rate="0.1",
                          rate_source="trusted_projected_margin_evidence"),
        target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_PASS


def test_insufficient_balance_blocked_with_valid_projected_evidence():
    syms = _trusted().symbols
    a = cf.evaluate_demo_account_evidence(
        _account_snapshot(syms, available="500", rate="0.1",
                          rate_source="trusted_projected_margin_evidence"),
        target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_BLOCKED


# ===========================================================================
# CH4A_FIX1 -- market evidence artifact is replayable (completeness)
# ===========================================================================

_REQUIRED_ROW_FIELDS = (
    "symbol", "side", "current_price", "exchange_ts_ms", "local_received_epoch_ns",
    "evidence_age_ms", "endpoint", "instrument_status", "contract_type", "settle_coin",
    "trading", "tick_size", "qty_step", "min_order_qty", "min_notional_value",
    "max_market_order_qty", "raw_quantity", "rounded_quantity", "rounded_notional_usd",
    "quantity_validation_status", "quantity_validation_failures",
)


def test_market_artifact_rows_retain_all_validated_evidence():
    t = _trusted()
    m = cf.evaluate_current_market_and_quantities(
        _market_records(t.symbols), targets=t.targets, collection_epoch_ns=_COLLECTION_NS)
    art = cf.build_market_evidence_artifact(
        trusted=t, market=m, collection_epoch_ns=_COLLECTION_NS, collected_at_utc="t",
        network_audit=cf.zeroed_network_audit())
    rows = art["current_actions"]
    assert len(rows) == 50
    for row in rows:
        for f in _REQUIRED_ROW_FIELDS:
            assert f in row, f
    # The validation is replayable: each row carries the exact price + rules that produced
    # the recomputed quantity.
    r0 = rows[0]
    assert r0["endpoint"] == _DEMO_TICKERS
    assert r0["evidence_age_ms"] is not None
    raw = (Decimal("200") / Decimal(r0["current_price"]))
    assert Decimal(r0["raw_quantity"]) == raw


# ===========================================================================
# CH4A_FIX1 -- honest bundle publication
# ===========================================================================

def test_cli_partial_publication_does_not_claim_complete_bundle(tmp_path, capsys, monkeypatch):
    c = _write_inputs(tmp_path)
    real_writer = crun.wsbpo.atomic_write_wrapper
    review_out = str(tmp_path / "review_out.json")

    def _failing(path, artifact):
        if str(path) == review_out:
            raise crun.wsbpo.WsBoundPlanOnlyError("simulated mid-bundle failure")
        return real_writer(path, artifact)

    monkeypatch.setattr(crun.wsbpo, "atomic_write_wrapper", _failing)
    rc = _run(tmp_path, c)
    assert rc == crun.EXIT_INPUT_FAILURE
    summary = json.loads(capsys.readouterr().out)
    assert summary["bundle_publication_status"] == cf.BUNDLE_INCOMPLETE
    assert summary["published_artifacts"]["feasibility_review"] is None
    assert not (tmp_path / "review_out.json").exists()  # no-clobber, atomic: never written
    # the two earlier core files were individually atomic and DO exist.
    assert (tmp_path / "market.json").exists() and (tmp_path / "account.json").exists()


# ===========================================================================
# CH4A_FIX2 -- Source A: EXACT per-symbol configured-leverage projected margin
# ===========================================================================

def _leverage_evidence(symbols, leverage="10", **over):
    """One per-symbol position/list leverage record per target (size-0 rows still carry
    the configured leverage)."""
    base = {s: {"symbol": s, "evidence_symbols": [s],
                "leverage_values": [str(leverage)], "position_idx_values": [0],
                "row_count": 1} for s in symbols}
    for s, patch in over.items():
        base[s] = {**base.get(s, {"symbol": s}), **patch}
    return base


def _account_with_leverage(syms, *, leverage="10", available="9000", lev_over=None, **over):
    snap = _account_snapshot(syms, available=available, rate=None, rate_source=None, **over)
    snap["target_leverage_evidence"] = _leverage_evidence(syms, leverage, **(lev_over or {}))
    return cf.evaluate_demo_account_evidence(
        snap, target_symbols=syms, collection_epoch_ns=_COLLECTION_NS)


def test_margin_per_symbol_leverage_passes_independently():
    t = _trusted(); syms = t.symbols
    m = _market(syms)  # price 100 -> rounded notional 200 per symbol
    a = _account_with_leverage(syms, leverage="10", available="9000")
    assert a.target_leverage_evidence_status == cf.LEVERAGE_EVIDENCE_OK
    assert len(a.target_configured_leverage_by_symbol) == 50
    mg = cf.evaluate_margin_feasibility(
        account_result=a, market_result=m, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_PASS
    assert mg.margin_basis == cf.MARGIN_BASIS_PER_SYMBOL
    assert mg.margin_rate_source == cf.PER_SYMBOL_LEVERAGE_RATE_SOURCE
    assert mg.projected_additional_initial_margin_usd == "1000"  # 50 * (200 / 10)
    assert len(mg.per_symbol_initial_margin) == 50
    r0 = mg.per_symbol_initial_margin[0]
    assert r0["configured_leverage"] == "10"
    assert r0["rounded_notional_usd"] == "200"
    assert r0["projected_initial_margin_usd"] == "20"


def test_margin_per_symbol_uses_leverage_not_account_rate():
    # An account-level/single rate must NOT influence the per-symbol projection.
    t = _trusted(); syms = t.symbols
    m = _market(syms)
    snap = _account_snapshot(syms, available="9000", rate="0.1",
                             rate_source="trusted_projected_margin_evidence")
    snap["target_leverage_evidence"] = _leverage_evidence(syms, "5")  # IM = 200/5 = 40 each
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    mg = cf.evaluate_margin_feasibility(
        account_result=a, market_result=m, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.margin_basis == cf.MARGIN_BASIS_PER_SYMBOL
    # 50 * 40 = 2000 (from leverage 5), NOT 1000 (which a 0.1 single rate would give).
    assert mg.projected_additional_initial_margin_usd == "2000"


def test_margin_per_symbol_missing_symbol_unavailable_lists_it():
    t = _trusted(); syms = t.symbols
    m = _market(syms)
    ev = _leverage_evidence(syms, "10")
    del ev[syms[3]]
    snap = _account_snapshot(syms, available="9000", rate=None, rate_source=None)
    snap["target_leverage_evidence"] = ev
    a = cf.evaluate_demo_account_evidence(snap, target_symbols=syms,
                                          collection_epoch_ns=_COLLECTION_NS)
    assert a.target_leverage_evidence_status == cf.LEVERAGE_EVIDENCE_UNAVAILABLE
    assert syms[3] in a.target_leverage_missing_symbols
    assert a.ok  # leverage coverage failure does NOT block the account
    mg = cf.evaluate_margin_feasibility(
        account_result=a, market_result=m, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_UNAVAILABLE
    assert f"leverage_missing:{syms[3]}" in mg.failures


@pytest.mark.parametrize("bad", [
    {"leverage_values": ["0"]},          # zero
    {"leverage_values": ["-3"]},         # negative
    {"leverage_values": ["abc"]},        # unparseable
    {"leverage_values": []},             # absent
    {"leverage_values": ["10", "20"]},   # ambiguous (disagreeing rows)
    {"evidence_symbols": ["OTHERUSDT"]}, # cross-symbol
])
def test_margin_per_symbol_invalid_leverage_unavailable(bad):
    t = _trusted(); syms = t.symbols
    m = _market(syms)
    a = _account_with_leverage(syms, leverage="10", lev_over={syms[0]: bad})
    assert a.target_leverage_evidence_status == cf.LEVERAGE_EVIDENCE_UNAVAILABLE
    assert syms[0] in a.target_leverage_missing_symbols
    mg = cf.evaluate_margin_feasibility(
        account_result=a, market_result=m, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_UNAVAILABLE
    assert f"leverage_missing:{syms[0]}" in mg.failures


def test_margin_per_symbol_insufficient_balance_blocks():
    t = _trusted(); syms = t.symbols
    m = _market(syms)
    a = _account_with_leverage(syms, leverage="1", available="9000")  # IM 200 each = 10000
    mg = cf.evaluate_margin_feasibility(
        account_result=a, market_result=m, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_BLOCKED
    assert "insufficient_available_balance" in mg.failures


def test_margin_one_rate_limited_symbol_blocks_partial_approval():
    # A single failed/rate-limited per-symbol read (empty evidence record, exactly what the
    # client emits on transport failure) must keep the whole 50-symbol batch UNAVAILABLE --
    # never a partial margin approval.
    t = _trusted(); syms = t.symbols
    m = _market(syms)
    a = _account_with_leverage(syms, leverage="10", lev_over={
        syms[7]: {"evidence_symbols": [], "leverage_values": [], "row_count": 0}})
    assert a.target_leverage_evidence_status == cf.LEVERAGE_EVIDENCE_UNAVAILABLE
    assert syms[7] in a.target_leverage_missing_symbols
    mg = cf.evaluate_margin_feasibility(
        account_result=a, market_result=m, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_UNAVAILABLE
    assert mg.status != cf.MARGIN_FEASIBILITY_PASS
    assert f"leverage_missing:{syms[7]}" in mg.failures


def test_margin_per_symbol_requires_market_notional():
    # Leverage evidence OK but no market result -> cannot project -> UNAVAILABLE.
    t = _trusted(); syms = t.symbols
    a = _account_with_leverage(syms, leverage="10")
    mg = cf.evaluate_margin_feasibility(
        account_result=a, market_result=None, target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_UNAVAILABLE
    assert "per_symbol_notional_unavailable" in mg.failures


def test_margin_per_symbol_determinism():
    t = _trusted(); syms = t.symbols
    m = _market(syms)
    a = _account_with_leverage(syms, leverage="7")
    r1 = cf.evaluate_margin_feasibility(account_result=a, market_result=m,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    r2 = cf.evaluate_margin_feasibility(account_result=a, market_result=m,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert r1 == r2


def test_no_leverage_evidence_falls_back_to_legacy_single_rate_path():
    # Backward compat: when no per-symbol evidence is supplied, the FIX1 path is unchanged.
    syms = _trusted().symbols
    a = _account_ok(syms, available="9000", rate="0.1")
    assert a.target_leverage_evidence_status == cf.LEVERAGE_EVIDENCE_NOT_SUPPLIED
    mg = cf.evaluate_margin_feasibility(account_result=a,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    assert mg.status == cf.MARGIN_FEASIBILITY_PASS
    assert mg.margin_basis == cf.MARGIN_BASIS_SINGLE_RATE


def test_account_artifact_records_per_symbol_leverage_evidence():
    t = _trusted(); syms = t.symbols
    a = _account_with_leverage(syms, leverage="10")
    art = cf.build_account_evidence_artifact(
        account=a, collection_epoch_ns=_COLLECTION_NS, collected_at_utc="t",
        network_audit=cf.zeroed_network_audit())
    assert art["target_leverage_evidence_status"] == cf.LEVERAGE_EVIDENCE_OK
    assert len(art["target_configured_leverage_by_symbol"]) == 50
    assert art["target_configured_leverage_by_symbol"][syms[0]] == "10"
    # fingerprint recomputes (artifact remains sealed/replayable).
    assert art["artifact_fingerprint"] == wb._fingerprint(
        {k: v for k, v in art.items() if k != "artifact_fingerprint"})


def test_review_artifact_records_per_symbol_margin_breakdown():
    t = _trusted(); syms = t.symbols
    m = _market(syms)
    a = _account_with_leverage(syms, leverage="10")
    mg = cf.evaluate_margin_feasibility(account_result=a, market_result=m,
                                        target_gross_notional_usd=cf.V1_GROSS_USD)
    fr = cf.build_current_feasibility_review(
        trusted=t, market=m, account=a, margin=mg, collection_epoch_ns=_COLLECTION_NS,
        reviewed_at_utc="t", network_audit=cf.zeroed_network_audit())
    assert fr.status == cf.CURRENT_FEASIBILITY_PASS
    rev = fr.review_artifact
    assert rev["margin_basis"] == cf.MARGIN_BASIS_PER_SYMBOL
    assert rev["account_margin_feasibility_status"] == cf.MARGIN_FEASIBILITY_PASS
    assert len(rev["per_symbol_initial_margin"]) == 50
    assert rev["target_leverage_evidence_status"] == cf.LEVERAGE_EVIDENCE_OK
    # still never execution-ready.
    assert rev["execution_readiness"] is False and rev["order_post_count"] == 0


def test_client_get_position_leverage_fixture_is_pure_and_no_setleverage():
    from src.demo_readonly_client import DemoReadOnlyClient
    c = DemoReadOnlyClient(allow_real_network=False)
    assert c.get_position_leverage(["BTCUSDT", "ETHUSDT"]) == {}  # fixture: no I/O
    src = open(os.path.join(_ROOT, "src", "demo_readonly_client.py"), encoding="utf-8").read()
    # the new evidence path must use the read-only position/list endpoint only.
    assert "get_position_leverage" in src
    assert "_EP_POSITIONS" in src


def test_provider_collects_per_symbol_leverage_evidence_source():
    src = open(_SCRIPT, encoding="utf-8").read()
    assert "get_position_leverage(" in src
    assert '"target_leverage_evidence"' in src


def _fake_account_provider_with_leverage(symbols, allow_real_network):
    assert allow_real_network is False
    now_ns = time.time_ns()
    audit = cf.zeroed_network_audit()
    audit["private_demo_http_get_count"] = 4 + len(symbols)
    snap = _account_snapshot(symbols, rate=None, rate_source=None)
    snap["snapshot_epoch_ns"] = now_ns - 1_000_000
    snap["target_leverage_evidence"] = _leverage_evidence(symbols, "10")
    return snap, audit


def test_cli_per_symbol_leverage_passes_and_writes_breakdown(tmp_path, capsys):
    c = _write_inputs(tmp_path)
    rc = crun.main(_argv(tmp_path, c),
                   market_provider=_fake_market_provider,
                   account_provider=_fake_account_provider_with_leverage)
    assert rc == crun.EXIT_OK
    summary = json.loads(capsys.readouterr().out)
    assert summary["status"] == cf.CURRENT_FEASIBILITY_PASS
    assert summary["account_margin_feasibility_status"] == cf.MARGIN_FEASIBILITY_PASS
    rev = json.loads((tmp_path / "review_out.json").read_bytes())
    assert rev["margin_basis"] == cf.MARGIN_BASIS_PER_SYMBOL
    assert rev["margin_rate_source"] == cf.PER_SYMBOL_LEVERAGE_RATE_SOURCE
    assert len(rev["per_symbol_initial_margin"]) == 50
    assert rev["projected_additional_initial_margin_usd"] == "1000"
    # safety posture intact.
    assert summary["execution_authorized"] is False
    assert summary["network_audit"]["private_mutating_request_count"] == 0
