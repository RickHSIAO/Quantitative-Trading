"""TASK-014BY: Day-2 lifecycle dry-run tests (provenance, network gating, complete counters).

READY requires genuine production provenance AND a COMPLETE transport audit: real network runs
only under --allow-real-network; every network component (production provider + current-position
collector) must report counters that merge with zero mutating requests; the four Forward source
roles must all hash. Day-1 fingerprints are recomputed; no immutable Day-1 EDUUSDT identity
artifact exists, so an open EDUUSDT fails closed. Durable identity uses Decimal canonical strings.
The dry-run is side-effect-free.
"""
from __future__ import annotations

import importlib.util
import json
import os
from types import SimpleNamespace

import pytest

from src import demo_strategy_native_day2_lifecycle as d2
from src import demo_strategy_native_postfill_audit as au
from src import demo_strategy_pilot_action_planner as ap
from src import demo_strategy_pilot_forward_source as fs
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd
from src.demo_instrument_rules import round_qty_down

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crun = _load("crun_day2_test", "scripts/run_demo_strategy_pilot_native_daily.py")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
LIFE = "2026-07-01"
COMPACT = "20260701"
DAY1 = "2026-06-30"
POLICY = d2.LIFECYCLE_POLICY_FORWARD_RECONCILE
STRATEGY = fs.EXPECTED_STRATEGY_NAME
PROTECTED = sorted(nx.PROTECTED_SYMBOLS)
N = 50
SYMS = [f"S{i:02d}USDT" for i in range(N)]
SIDES_DISPLAY = ["Buy" if i < 25 else "Sell" for i in range(N)]
SIDES_LS = ["long" if i < 25 else "short" for i in range(N)]
MARK = "100"


def _source_artifacts(hashes=None):
    base = {
        "positions": {"path": f"/fwd/{COMPACT}_positions.parquet", "sha256": "sha256:" + "a" * 64},
        "forward_stats": {"path": f"/fwd/{COMPACT}_forward_stats.json", "sha256": "sha256:" + "b" * 64},
        "pnl": {"path": f"/fwd/{COMPACT}_pnl.json", "sha256": "sha256:" + "c" * 64},
        "forward_summary": {"path": "/fwd/forward_summary.json", "sha256": "sha256:" + "d" * 64}}
    if hashes:
        for r, h in hashes.items():
            base[r]["sha256"] = h
    return base


def _rc(ro=2, pub=1, mut=0):
    return {"private_read_only_request_count": ro, "public_read_only_request_count": pub,
            "private_mutating_request_count": mut}


def _components(provider=None, collector=None, drop=()):
    comps = {"production_forward_provider": provider if provider is not None else _rc(),
             "current_position_collector": collector if collector is not None else _rc()}
    for d in drop:
        comps[d] = None
    return comps


def _day1_payloads():
    return [{"symbol": SYMS[i], "side": SIDES_DISPLAY[i], "target_notional_usd": "200"}
            for i in range(N)]


DAY1_FP = crun.allocation_intent_fingerprint(_day1_payloads(), pilot_id=PILOT, date=DAY1,
                                             strategy_capital_base_usd="10000")


def _day1_audit_and_alloc(payloads=None, fp=DAY1_FP):
    payloads = payloads if payloads is not None else _day1_payloads()
    alloc = {"pilot_id": PILOT, "date": DAY1, "payload_fingerprint": fp,
             "allocation_intent_fingerprint": fp, "order_payloads": payloads,
             "strategy_capital_base_usd": "10000"}
    accepted = [{"identity": f"id{i}", "outcome": "RECONCILED", "final_status": "Filled"}
                for i in range(N)]
    state = {"pilot_id": PILOT, "date": DAY1, "day_verdict": au.DAY_SUCCESS, "proposed_count": 50,
             "accepted_count": 50, "rejected_count": 0, "ambiguous_count": 0,
             "sender_call_count": 50, "order_post_count": 50, "accepted": accepted}
    summary = {"pilot_id": PILOT, "date": DAY1, "payload_fingerprint": fp,
               "status": "DEMO_BATCH_DISPATCHED", "day_verdict": au.DAY_SUCCESS,
               "execute_daily_native_called": 1, "pilot_advanced": False,
               "live_trading_authorized": False, "blockers": [], "accepted_count": 50,
               "rejected_count": 0, "ambiguous_count": 0, "order_post_count": 50,
               "sender_call_count": 50}
    journal = ([{"event": "DAILY_EXECUTION_START"}]
               + [{"event": "ACTION_RECONCILED", "identity": f"id{i}"} for i in range(N)]
               + [{"event": "DAILY_EXECUTION_FINISHED"}])
    ledger = []
    for i in range(N):
        ledger += [{"identity": f"id{i}", "state": "ATTEMPTED"},
                   {"identity": f"id{i}", "state": "POST_RESPONSE_RECEIVED"},
                   {"identity": f"id{i}", "state": "RECONCILED"}]
    battempt = {"pilot_id": PILOT, "date": DAY1, "allocation_intent_fingerprint": fp,
                "status": "DEMO_BATCH_DISPATCHED", "day_verdict": au.DAY_SUCCESS}
    positions = [{"symbol": SYMS[i], "side": SIDES_DISPLAY[i], "size": "1"} for i in range(N)]
    positions += [{"symbol": "EDUUSDT", "side": "Sell", "size": "5"}]
    prov = {"page_count": 3, "termination_reason": "empty_cursor", "api_position_rows": 51,
            "nonzero_position_count": 51}
    counters = {"private_read_only_request_count": 4, "public_read_only_request_count": 0,
                "private_mutating_request_count": 0}
    src = {k: f"/abs/{k}" for k in au.REQUIRED_SOURCE_KEYS}
    audit = au.evaluate_post_fill_audit(
        pilot_id=PILOT, date=DAY1, expected_fingerprint=fp, allocation_intent_artifact=alloc,
        execution_summary=summary, execution_state=state, journal=journal, sent_ledger=ledger,
        batch_attempt=battempt, positions=positions, positions_provenance=prov,
        protected_symbols=PROTECTED, protected_symbols_source="x", network_counters=counters,
        intent_recomputed_fingerprint=fp, source_paths=src)
    return audit, alloc


def _intent(overrides=None, add=None, drop=None):
    """Immutable intent view: symbol / side / target_notional_usd only."""
    out = []
    for i in range(N):
        if drop and SYMS[i] in drop:
            continue
        a = {"symbol": SYMS[i], "side": SIDES_LS[i], "target_notional_usd": "200"}
        if overrides and SYMS[i] in overrides:
            a.update(overrides[SYMS[i]])
        out.append(a)
    if add:
        out.extend(add)
    return out


def _runtime(overrides=None, add=None, drop=None):
    """Volatile runtime translation: symbol / side / notional / price / qty_step / qty."""
    out = []
    for i in range(N):
        if drop and SYMS[i] in drop:
            continue
        r = {"symbol": SYMS[i], "side": SIDES_LS[i], "target_notional_usd": "200",
             "price_snapshot": "100", "qty_step": "0.001", "qty": "2"}
        if overrides and SYMS[i] in overrides:
            r.update(overrides[SYMS[i]])
        out.append(r)
    if add:
        out.extend(add)
    return out


def _production(intent=None, runtime=None, signal_date=LIFE, strategy=STRATEGY, sources=None,
                loader_validation="PASS", counters=None, **extra):
    prod = {"strategy": strategy, "requested_run_date": LIFE, "signal_date": signal_date,
            "loader_validation": loader_validation,
            "source_artifacts": sources if sources is not None else _source_artifacts(),
            "network_audit_counters": counters if counters is not None else _rc(),
            "intent_allocations": intent if intent is not None else _intent(),
            "runtime_translation": runtime if runtime is not None else _runtime()}
    prod.update(extra)
    return prod


def _sealed(intent=None, signal_date=LIFE, source_id=STRATEGY, sources=None):
    return d2.seal_target_intent_artifact(
        pilot_id=PILOT, lifecycle_date=LIFE, signal_date=signal_date, source_identifier=source_id,
        source_artifacts=sources if sources is not None else _source_artifacts(),
        intent_allocations=intent if intent is not None else _intent())


def _current(overrides=None, drop=None, extra=None, include_edu=False, edu_side="short"):
    rows = []
    for i in range(N):
        if drop and SYMS[i] in drop:
            continue
        r = {"symbol": SYMS[i], "side": SIDES_LS[i], "size": "2", "mark_price": MARK,
             "position_idx": 0, "entry_price": "100", "unrealised_pnl": "1.5"}
        if overrides and SYMS[i] in overrides:
            r.update(overrides[SYMS[i]])
        rows.append(r)
    if include_edu:
        rows.append({"symbol": "EDUUSDT", "side": edu_side, "size": "5", "mark_price": "10",
                     "position_idx": 0, "entry_price": "9", "unrealised_pnl": "-2"})
    if extra:
        rows.extend(extra)
    return rows


def _prov(termination="empty_cursor"):
    return {"page_count": 3, "termination_reason": termination, "api_position_rows": 50,
            "nonzero_position_count": 50}


def _kw(**over):
    audit, alloc = _day1_audit_and_alloc()
    kw = dict(pilot_id=PILOT, lifecycle_date=LIFE, day1_date=DAY1, day1_fingerprint=DAY1_FP,
              lifecycle_policy=POLICY, day1_post_fill_audit=audit, day1_allocation_intent=alloc,
              sealed_target=_sealed(), production_target_recompute=_production(),
              current_positions=_current(), positions_provenance=_prov(),
              network_counter_components=_components(), protected_symbols=PROTECTED,
              protected_symbols_source="nx.PROTECTED_SYMBOLS")
    kw.update(over)
    return kw


def _plan(**over):
    return d2.build_day2_lifecycle_dry_run(**_kw(**over))


def _act(art, sym):
    return next(a for a in art["actions"] if a["symbol"] == sym)


# ============================================================ READY + classification

def test_all_hold_ready_full_provenance():
    art = _plan()
    assert art["verdict"] == d2.DRY_RUN_READY, art["blockers"]
    assert art["target_intent_evidence"]["production_strategy"] == STRATEGY
    assert {a["proposed_action"] for a in art["actions"]} == {"HOLD"}


def test_close_and_open_identities_distinct():
    ident = _plan()["exactly_once_identity_design"]
    assert ident["close_batch_identity"] != ident["open_batch_identity"]


def test_partial_close_estimate_nonzero():
    art = _plan(sealed_target=_sealed(_intent(drop={"S00USDT"})),
                production_target_recompute=_production(intent=_intent(drop={"S00USDT"}),
                                                        runtime=_runtime(drop={"S00USDT"})))
    assert _act(art, "S00USDT")["proposed_action"] == "CLOSE"
    assert _act(art, "S00USDT")["close_notional_estimate_usd"] == "200"


def test_increase_decrease_reverse():
    # INCREASE / DECREASE are driven by the RUNTIME qty (intent notional unchanged). The runtime
    # qty must satisfy floor(notional/price/step)*step, so the price is set accordingly:
    #   notional 200 / price 40  -> qty 5 (INCREASE from current 2)
    #   notional 200 / price 200 -> qty 1 (DECREASE from current 2)
    inc = _plan(production_target_recompute=_production(
        runtime=_runtime({"S00USDT": {"qty": "5", "price_snapshot": "40"}})))
    assert _act(inc, "S00USDT")["proposed_action"] == "INCREASE"
    dec = _plan(production_target_recompute=_production(
        runtime=_runtime({"S00USDT": {"qty": "1", "price_snapshot": "200"}})))
    assert _act(dec, "S00USDT")["proposed_action"] == "DECREASE"
    rev = _plan(sealed_target=_sealed(_intent({"S00USDT": {"side": "short"}})),
                production_target_recompute=_production(
                    intent=_intent({"S00USDT": {"side": "short"}}),
                    runtime=_runtime({"S00USDT": {"side": "short"}})),
                current_positions=_current({"S00USDT": {"side": "long"}}))
    a = _act(rev, "S00USDT")
    assert a["proposed_action"] == "REVERSE"
    assert a["close_notional_estimate_usd"] == "200" and a["open_notional_estimate_usd"] == "200"


# ============================================================ complete network counters

def test_merged_counters_sum_provider_and_collector():
    art = _plan(network_counter_components=_components(provider=_rc(ro=3, pub=2),
                                                      collector=_rc(ro=4, pub=1)))
    nac = art["network_audit_counters"]
    assert nac["private_read_only_request_count"] == 7        # 3 + 4
    assert nac["public_read_only_request_count"] == 3          # 2 + 1
    assert nac["private_mutating_request_count"] == 0
    assert set(nac["component_breakdown"]) == {"production_forward_provider", "current_position_collector"}


def test_provider_private_and_public_gets_counted():
    art = _plan(network_counter_components=_components(provider=_rc(ro=5, pub=6), collector=_rc()))
    bd = art["network_audit_counters"]["component_breakdown"]["production_forward_provider"]
    assert bd["private_read_only_request_count"] == 5 and bd["public_read_only_request_count"] == 6


def test_unaccounted_provider_component_blocked():
    art = _plan(network_counter_components=_components(drop=["production_forward_provider"]))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("unaccounted_network_component:production_forward_provider" in b for b in art["blockers"])


def test_unaccounted_collector_component_blocked():
    art = _plan(network_counter_components=_components(drop=["current_position_collector"]))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("unaccounted_network_component:current_position_collector" in b for b in art["blockers"])


def test_mutating_counter_blocked():
    art = _plan(network_counter_components=_components(provider=_rc(mut=1)))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("private_mutating_requests_detected" in b for b in art["blockers"])


def test_component_missing_a_counter_key_blocked():
    bad = {"private_read_only_request_count": 2, "public_read_only_request_count": 1}  # no mutating
    art = _plan(network_counter_components=_components(provider=bad))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("unaccounted_network_component" in b for b in art["blockers"])


# ============================================================ four source artifact roles

@pytest.mark.parametrize("role", list(d2.REQUIRED_SOURCE_ROLES))
def test_sealed_missing_source_role_blocked(role):
    sources = _source_artifacts()
    del sources[role]
    art = _plan(sealed_target=_sealed(sources=sources))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("sealed_source_artifact_role_missing" in b for b in art["blockers"])


def test_source_artifact_hash_format_invalid_blocked():
    art = _plan(sealed_target=_sealed(sources=_source_artifacts({"positions": "not-a-hash"})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("sealed_source_artifact_hash_invalid:positions" in b for b in art["blockers"])


def test_sealed_vs_production_source_hash_mismatch_blocked():
    art = _plan(sealed_target=_sealed(sources=_source_artifacts({"pnl": "sha256:" + "e" * 64})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("source_artifact_hash_mismatch:pnl" in b for b in art["blockers"])


def test_production_extra_source_role_blocked():
    sources = _source_artifacts()
    sources["extra_role"] = {"path": "/x", "sha256": "sha256:" + "f" * 64}
    art = _plan(production_target_recompute=_production(sources=sources))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("production_source_artifact_role_unexpected" in b for b in art["blockers"])


# ==================================================== v2 intent / runtime separation provenance

def test_runtime_qty_differs_from_seal_time_still_passes_provenance():
    # T1 sealed intent (symbol/side/notional). T2 production runtime has a DIFFERENT qty; because
    # the immutable intent is unchanged, provenance PASSES and the runtime qty is used.
    sealed = _sealed()
    # T2: a slightly different price legitimately yields a different valid qty (200/100.5 -> 1.99).
    ok, reasons, tbs, _sd, _rfp = d2.verify_production_target_provenance(
        sealed_target=sealed,
        production_recompute=_production(
            runtime=_runtime({"S00USDT": {"qty": "1.99", "price_snapshot": "100.5"}})),
        pilot_id=PILOT, lifecycle_date=LIFE)
    assert ok, reasons
    assert str(tbs["S00USDT"]["qty"]) == "1.99"     # runtime qty from THIS run is used


def test_intent_fingerprint_independent_of_price_and_qty():
    fp_a = d2.target_intent_fingerprint(pilot_id=PILOT, lifecycle_date=LIFE, signal_date=LIFE,
                                        source_identifier=STRATEGY, intent_allocations=_intent())
    # add price/qty/qty_step noise to the intent rows -> fingerprint must be unchanged
    noisy = [dict(a, qty="9", qty_step="0.5", price_snapshot="137") for a in _intent()]
    fp_b = d2.target_intent_fingerprint(pilot_id=PILOT, lifecycle_date=LIFE, signal_date=LIFE,
                                        source_identifier=STRATEGY, intent_allocations=noisy)
    assert fp_a == fp_b


def test_runtime_fingerprint_changes_with_price_and_qty():
    def rfp(runtime):
        return d2.verify_production_target_provenance(
            sealed_target=_sealed(), production_recompute=_production(runtime=runtime),
            pilot_id=PILOT, lifecycle_date=LIFE)[4]
    base = rfp(_runtime())
    diff_qty = rfp(_runtime({"S00USDT": {"qty": "1.99"}}))
    diff_price = rfp(_runtime({"S00USDT": {"price_snapshot": "137"}}))
    assert len({base, diff_qty, diff_price}) == 3


def test_runtime_change_changes_lifecycle_plan_fingerprint():
    a = _plan()["lifecycle_plan_fingerprint"]
    # A different (still valid) runtime sizing: 200/133.33 floors to qty 1.5.
    b = _plan(production_target_recompute=_production(
        runtime=_runtime({"S00USDT": {"qty": "1.5", "price_snapshot": "133.33"}})))[
        "lifecycle_plan_fingerprint"]
    assert a and b and a != b


def test_intent_notional_mismatch_blocked():
    art = _plan(production_target_recompute=_production(
        intent=_intent({"S00USDT": {"target_notional_usd": "999"}}),
        runtime=_runtime({"S00USDT": {"target_notional_usd": "999"}})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("target_target_notional_usd_mismatch_production:S00USDT" in b for b in art["blockers"])


def test_v1_target_artifact_rejected():
    v1 = _sealed()
    v1["schema_version"] = d2.TARGET_SCHEMA_VERSION_V1
    v1[d2.TARGET_DIGEST_FIELD] = d2.canonical_target_digest(v1)   # re-seal to isolate schema check
    art = _plan(sealed_target=v1)
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("unsupported_target_intent_schema_version" in b for b in art["blockers"])


def test_loader_validation_not_pass_blocks():
    art = _plan(production_target_recompute=_production(loader_validation="",
                                                       runner_status="OK", safety_scan="PASS"))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("production_loader_validation_not_pass" in b for b in art["blockers"])


def test_sealed_intent_duplicate_symbol_blocked():
    dup = _intent() + [{"symbol": "S00USDT", "side": "long", "target_notional_usd": "200"}]
    art = _plan(sealed_target=_sealed(dup))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("sealed_target_intent_duplicate_symbol:S00USDT" in b for b in art["blockers"])


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "0", None])
def test_runtime_invalid_qty_blocked(bad):
    art = _plan(production_target_recompute=_production(runtime=_runtime({"S00USDT": {"qty": bad}})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("production_target_runtime_invalid_qty:S00USDT" in b for b in art["blockers"])


@pytest.mark.parametrize("field", ["price_snapshot", "qty_step"])
def test_runtime_invalid_price_or_step_blocked(field):
    art = _plan(production_target_recompute=_production(runtime=_runtime({"S00USDT": {field: "0"}})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any(f"production_target_runtime_invalid_{field}:S00USDT" in b for b in art["blockers"])


# ============================================== FIX1: runtime qty = floor(notional/price/step)*step

def _verify_single(notional, price, step, qty, side="long"):
    intent = [{"symbol": "ABCUSDT", "side": side, "target_notional_usd": notional}]
    runtime = [{"symbol": "ABCUSDT", "side": side, "target_notional_usd": notional,
                "price_snapshot": price, "qty_step": step, "qty": qty}]
    return d2.verify_production_target_provenance(
        sealed_target=_sealed(intent),
        production_recompute=_production(intent=intent, runtime=runtime),
        pilot_id=PILOT, lifecycle_date=LIFE)


def _rt_mismatch(reasons):
    return any("runtime_qty_rounding_mismatch:ABCUSDT" in r for r in reasons)


def test_arith_exact_valid_sizing_passes():                                    # (A)
    ok, reasons, tbs, _sd, _rfp = _verify_single("200", "100", "0.001", "2")
    assert ok, reasons
    assert str(tbs["ABCUSDT"]["qty"]) == "2"


def test_arith_positive_but_wrong_qty_blocked():                               # (B)
    ok, reasons, *_ = _verify_single("200", "100", "0.001", "1.999")
    assert not ok and _rt_mismatch(reasons)


def test_arith_floor_to_step_boundary():                                       # (C)
    assert _verify_single("200", "137", "0.01", "1.45")[0]                     # exact floor -> PASS
    ok_hi, reasons_hi, *_ = _verify_single("200", "137", "0.01", "1.46")
    assert not ok_hi and _rt_mismatch(reasons_hi)                              # one step high -> BLOCK


def test_arith_fine_precision_no_float_artifact():                            # (D)
    assert _verify_single("1", "3", "0.001", "0.333")[0]
    ok_hi, reasons_hi, *_ = _verify_single("1", "3", "0.001", "0.334")
    assert not ok_hi and _rt_mismatch(reasons_hi)


@pytest.mark.parametrize("qty", ["1.454", "1.446"])
def test_arith_off_grid_qty_within_half_step_blocked(qty):                     # FIX2 (A, B)
    # 1.454 / 1.446 round to the nearest step 1.45 but are NOT on the 0.01 grid -> must BLOCK
    # (no nearest-step tolerance).
    ok, reasons, *_ = _verify_single("200", "137", "0.01", qty)
    assert not ok
    assert any("runtime_qty_not_on_step_grid:ABCUSDT" in r for r in reasons)
    assert _rt_mismatch(reasons)


def test_arith_off_grid_fine_step_blocked():                                   # FIX2 (D)
    ok, reasons, *_ = _verify_single("1", "3", "0.001", "0.3334")
    assert not ok and any("runtime_qty_not_on_step_grid:ABCUSDT" in r for r in reasons)


def test_arith_raw_planner_float_artifact_rejected_by_validator():
    # A raw float-artifact qty reaching the validator directly is NOT silently accepted.
    ok, reasons, *_ = _verify_single("6", "20", "0.1", str(3 * 0.1))   # 0.30000000000000004
    assert not ok and any("runtime_qty_not_on_step_grid:ABCUSDT" in r for r in reasons)


def test_resolver_canonicalizes_planner_float_qty(tmp_path, monkeypatch):      # FIX2 (E)
    root = _seed_forward_files(tmp_path)
    tps = [{"symbol": "ABCUSDT", "side": "long", "target_notional": "6",
            "qty": 3 * 0.1, "qty_step": "0.1", "price": "20"}]   # planner float 0.30000000000000004
    _patch_chain(monkeypatch, plan=_real_plan(target_positions=tps))
    args = _args(tmp_path)
    args.forward_source_root = root
    prod = d2run.resolve_production_forward_target(
        args, provider=SimpleNamespace(network_audit_counters=lambda: _rc()))
    assert prod["runtime_translation"][0]["qty"] == "0.3"     # canonical step-grid, not the artifact
    reasons, _ = d2._validate_runtime_translation(prod["runtime_translation"], "production_target")
    assert not any("runtime_qty" in r for r in reasons)      # validates exactly


def test_runtime_fingerprint_stable_across_float_representation():              # FIX2 (F)
    # The resolver canonicalizes the helper's float-artifact qty to "0.3"; the runtime fingerprint
    # over the canonical value equals the fingerprint over a clean "0.3" -> no artifact drift.
    intent = [{"symbol": "ABCUSDT", "side": "long", "target_notional_usd": "6"}]
    sealed = _sealed(intent)
    canon = d2run._verified_canonical_step_grid_qty(
        round_qty_down(6 / 20, 0.1), "6", "20", "0.1", "ABCUSDT")
    assert canon == "0.3"

    def rt_fp(qty_str):
        rt = [{"symbol": "ABCUSDT", "side": "long", "target_notional_usd": "6",
               "price_snapshot": "20", "qty_step": "0.1", "qty": qty_str}]
        ok, reasons, _tbs, _sd, rfp = d2.verify_production_target_provenance(
            sealed_target=sealed, production_recompute=_production(intent=intent, runtime=rt),
            pilot_id=PILOT, lifecycle_date=LIFE)
        assert ok, reasons
        return rfp

    assert rt_fp(canon) == rt_fp("0.3")


# ============================================ FIX3: verify raw planner qty before serialization

def _resolve_qty(tmp_path, monkeypatch, raw_qty, notional="200", price="137", step="0.01"):
    """Resolve a single target with an EXPLICIT raw planner qty (no helper substitution)."""
    root = _seed_forward_files(tmp_path)
    tps = [{"symbol": "ABCUSDT", "side": "long", "target_notional": notional, "qty": raw_qty,
            "qty_step": step, "price": price}]
    _patch_chain(monkeypatch, plan=_real_plan(target_positions=tps))
    args = _args(tmp_path)
    args.forward_source_root = root
    return d2run.resolve_production_forward_target(
        args, provider=SimpleNamespace(network_audit_counters=lambda: _rc()))


def test_resolver_accepts_qty_equal_to_formal_helper(tmp_path, monkeypatch):   # FIX3 (A)
    raw = round_qty_down(200 / 137, 0.01)          # the FORMAL helper output
    prod = _resolve_qty(tmp_path, monkeypatch, raw)
    rt = prod["runtime_translation"][0]
    assert rt["qty"] == "1.45"
    reasons, _ = d2._validate_runtime_translation(prod["runtime_translation"], "production_target")
    assert not any("runtime_qty" in r for r in reasons)


@pytest.mark.parametrize("bad", ["1.454", "1.446", "1.46"])
def test_resolver_blocks_qty_not_matching_helper(tmp_path, monkeypatch, bad):  # FIX3 (B, C, D)
    with pytest.raises(fs.ForwardSourceError, match="production_planner_qty_formula_mismatch"):
        _resolve_qty(tmp_path, monkeypatch, bad)


def test_resolver_accepts_real_helper_float_artifact(tmp_path, monkeypatch):   # FIX3 (E)
    raw = round_qty_down(6 / 20, 0.1)              # 0.30000000000000004 straight from the helper
    assert raw != 0.3                              # genuinely a float artifact
    prod = _resolve_qty(tmp_path, monkeypatch, raw, notional="6", price="20", step="0.1")
    assert prod["runtime_translation"][0]["qty"] == "0.3"
    reasons, _ = d2._validate_runtime_translation(prod["runtime_translation"], "production_target")
    assert not any("runtime_qty" in r for r in reasons)


def test_resolver_blocks_qty_near_but_not_equal_to_helper(tmp_path, monkeypatch):  # FIX3 (F)
    raw = round_qty_down(200 / 137, 0.01) + 1e-12  # infinitesimally off -> still must BLOCK
    with pytest.raises(fs.ForwardSourceError, match="production_planner_qty_formula_mismatch"):
        _resolve_qty(tmp_path, monkeypatch, raw)


def test_resolver_cross_time_each_qty_verified_by_helper(tmp_path, monkeypatch):  # FIX3 (G)
    t1 = _resolve_qty(tmp_path / "t1", monkeypatch, round_qty_down(200 / 100, 0.001),
                      notional="200", price="100", step="0.001")
    t2 = _resolve_qty(tmp_path / "t2", monkeypatch, round_qty_down(200 / 137, 0.01),
                      notional="200", price="137", step="0.01")
    assert t1["runtime_translation"][0]["qty"] == "2"
    assert t2["runtime_translation"][0]["qty"] == "1.45"
    sealed = _sealed_from_production(t1)   # same intent + source hashes as t1 (== t2, same content)

    def ok_fp(prod):
        ok, reasons, tbs, _sd, rfp = d2.verify_production_target_provenance(
            sealed_target=sealed, production_recompute=prod, pilot_id=PILOT, lifecycle_date=LIFE)
        assert ok, reasons
        return rfp, tbs
    fp1, _tbs1 = ok_fp(t1)
    fp2, tbs2 = ok_fp(t2)
    assert fp1 != fp2                                        # different runtime -> different fp
    assert str(tbs2["ABCUSDT"]["qty"]) == "1.45"             # lifecycle uses T2 qty


def test_resolver_no_nearest_round_acceptance_of_unverified_qty(tmp_path, monkeypatch):  # FIX3 (H)
    # 1.454 rounds to the nearest step 1.45 but is NOT the helper output -> must NOT be accepted.
    with pytest.raises(fs.ForwardSourceError, match="production_planner_qty_formula_mismatch"):
        _resolve_qty(tmp_path, monkeypatch, "1.454")


# ============================================ FIX4: lifecycle v2 evidence artifact contract

def test_lifecycle_schema_version_is_v2():                                     # FIX4 (A)
    assert d2.SCHEMA_VERSION == "demo_strategy_native_day2_lifecycle_dry_run_v2"
    assert _plan()["schema_version"] == "demo_strategy_native_day2_lifecycle_dry_run_v2"


def test_top_level_uses_target_intent_fingerprint_name():                      # FIX4 (B)
    art = _plan()
    assert art["target_intent_fingerprint"] == _sealed()[d2.TARGET_FINGERPRINT_FIELD]
    assert "target_allocation_intent_fingerprint" not in art
    assert "target_allocation_intent_fingerprint" not in art["exactly_once_identity_design"]


def test_target_intent_fp_change_changes_plan_and_batch_identities():          # FIX4 (C)
    base = _plan()
    alt = _plan(sealed_target=_sealed(_intent({"S00USDT": {"target_notional_usd": "300"}})),
                production_target_recompute=_production(
                    intent=_intent({"S00USDT": {"target_notional_usd": "300"}}),
                    runtime=_runtime({"S00USDT": {"target_notional_usd": "300", "qty": "3"}})))
    assert base["target_intent_fingerprint"] != alt["target_intent_fingerprint"]
    assert base["lifecycle_plan_fingerprint"] != alt["lifecycle_plan_fingerprint"]
    bi, ai = base["exactly_once_identity_design"], alt["exactly_once_identity_design"]
    assert bi["close_batch_identity"] != ai["close_batch_identity"]
    assert bi["open_batch_identity"] != ai["open_batch_identity"]


def test_target_intent_evidence_complete():                                    # FIX4 (D)
    ev = _plan()["target_intent_evidence"]
    assert ev["validated"] is True
    assert ev["schema_version"] == d2.TARGET_SCHEMA_VERSION
    assert ev["target_intent_fingerprint"] == _sealed()[d2.TARGET_FINGERPRINT_FIELD]
    assert ev["target_digest"] == _sealed()[d2.TARGET_DIGEST_FIELD]
    assert ev["strategy_capital_base_usd"] == "10000"
    assert ev["source_artifacts_match_production"] is True
    assert set(ev["source_artifacts"]) == set(d2.REQUIRED_SOURCE_ROLES)
    for role in d2.REQUIRED_SOURCE_ROLES:
        assert d2._SHA256_RE.match(ev["source_artifacts"][role]["sha256"])
        assert ev["source_artifacts"][role]["path"]


def test_runtime_translation_evidence_complete():                             # FIX4 (E)
    art = _plan()
    ev = art["runtime_translation_evidence"]
    assert ev is not None and ev["validated"] is True
    assert ev["source"] == "formal_production_recompute_current_run"
    assert ev["runtime_translation_fingerprint"] == art["runtime_translation_fingerprint"]
    assert ev["target_intent_fingerprint"] == art["target_intent_fingerprint"]
    assert ev["runtime_symbol_count"] == N == len(ev["canonical_runtime_translation"])
    row = ev["canonical_runtime_translation"][0]
    assert set(row) == {"symbol", "side", "target_notional_usd", "price_snapshot", "qty_step", "qty"}
    # rows are exactly the canonical rows the fingerprint was computed over
    assert ev["canonical_runtime_translation"] == d2._canon_runtime_translation(_runtime())


def test_runtime_evidence_and_plan_fp_change_with_runtime():                   # FIX4 (F)
    base = _plan()
    alt = _plan(production_target_recompute=_production(
        runtime=_runtime({"S00USDT": {"price_snapshot": "40", "qty": "5"}})))   # 200/40 -> 5
    assert (base["runtime_translation_evidence"]["runtime_translation_fingerprint"]
            != alt["runtime_translation_evidence"]["runtime_translation_fingerprint"])
    assert base["runtime_translation_fingerprint"] != alt["runtime_translation_fingerprint"]
    assert base["lifecycle_plan_fingerprint"] != alt["lifecycle_plan_fingerprint"]


def test_evidence_present_and_fail_closed_on_invalid_provenance():             # FIX4 (G)
    art = _plan(sealed_target=_sealed(sources=_source_artifacts({"pnl": "sha256:" + "e" * 64})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    tev = art["target_intent_evidence"]
    rev = art["runtime_translation_evidence"]
    assert tev is not None and rev is not None
    assert tev["validated"] is False and rev["validated"] is False
    assert tev["validation_reasons"] and rev["validation_reasons"]
    assert tev["target_intent_fingerprint"] == "" and tev["source_artifacts_match_production"] is False
    assert rev["runtime_translation_fingerprint"] == "" and rev["canonical_runtime_translation"] == []


def test_edu_blocker_preserved_with_valid_evidence():                         # FIX4 (H)
    art = _plan(current_positions=_current(include_edu=True))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert "day1_eduusdt_position_identity_evidence_unavailable" in art["blockers"]
    # provenance itself PASSED, so the evidence objects are validated even though the plan is blocked
    assert art["target_intent_evidence"]["validated"] is True
    assert art["runtime_translation_evidence"]["validated"] is True


def test_network_accounting_regression_in_v2_artifact():                      # FIX4 (I)
    art = _plan(network_counter_components=_components(provider=_rc(ro=3, pub=2),
                                                      collector=_rc(ro=4, pub=1)))
    nac = art["network_audit_counters"]
    assert nac["private_mutating_request_count"] == 0
    assert set(nac["component_breakdown"]) == {"production_forward_provider", "current_position_collector"}
    assert _plan(network_counter_components=_components(provider=_rc(mut=1)))["verdict"] == d2.DRY_RUN_BLOCKED


def test_arith_short_uses_positive_magnitude():                                # (E)
    ok, reasons, *_ = _verify_single("200", "137", "0.01", "1.45", side="short")
    assert ok, reasons
    assert not _verify_single("200", "137", "0.01", "1.46", side="short")[0]


def test_arith_cross_time_each_qty_matches_its_own_price():                    # (F)
    # Same immutable intent (notional 200); different prices -> different valid qty; both PASS.
    ok1, r1, tbs1, *_ = _verify_single("200", "100", "0.001", "2")
    ok2, r2, tbs2, *_ = _verify_single("200", "137", "0.01", "1.45")
    assert ok1 and ok2, (r1, r2)
    assert str(tbs1["ABCUSDT"]["qty"]) == "2" and str(tbs2["ABCUSDT"]["qty"]) == "1.45"
    # A T2 qty that matched T1's price but NOT T2's price must fail.
    assert not _verify_single("200", "137", "0.01", "2")[0]


def test_arith_lifecycle_uses_current_runtime_qty_not_sealed():               # (G)
    # The sealed intent carries NO qty; the lifecycle target qty comes from the current runtime.
    intent = _intent({"S00USDT": {"target_notional_usd": "200"}})
    art = _plan(sealed_target=_sealed(intent),
                production_target_recompute=_production(
                    intent=intent,
                    runtime=_runtime({"S00USDT": {"qty": "5", "price_snapshot": "40"}})))
    assert art["verdict"] == d2.DRY_RUN_READY, art["blockers"]
    assert _act(art, "S00USDT")["proposed_action"] == "INCREASE"   # target qty 5 > current 2
    assert "qty" not in art["target_intent_fingerprint"]   # intent fp is not a qty carrier


def test_intent_notional_non_finite_blocked():
    art = _plan(sealed_target=_sealed(_intent({"S00USDT": {"target_notional_usd": "NaN"}})),
                production_target_recompute=_production(
                    intent=_intent({"S00USDT": {"target_notional_usd": "NaN"}}),
                    runtime=_runtime({"S00USDT": {"target_notional_usd": "NaN"}})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("intent_invalid_notional:S00USDT" in b for b in art["blockers"])


def test_unknown_lifecycle_policy_blocked():
    assert _plan(lifecycle_policy="JUST_HOLD")["verdict"] == d2.DRY_RUN_BLOCKED


# ============================================================ EDUUSDT identity unavailable

def test_open_eduusdt_blocks_no_immutable_identity_evidence():
    art = _plan(current_positions=_current(include_edu=True))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert "day1_eduusdt_position_identity_evidence_unavailable" in art["blockers"]


def test_no_manual_edu_side_input_on_builder():
    import inspect
    assert "day1_protected_evidence" not in set(
        inspect.signature(d2.build_day2_lifecycle_dry_run).parameters)


# ============================================================ Day-1 fingerprint recompute

def test_day1_payload_side_changed_keeping_fingerprint_blocked():
    payloads = _day1_payloads()
    payloads[0]["side"] = "Sell"
    audit, _ = _day1_audit_and_alloc()
    alloc = {"pilot_id": PILOT, "date": DAY1, "payload_fingerprint": DAY1_FP,
             "allocation_intent_fingerprint": DAY1_FP, "order_payloads": payloads,
             "strategy_capital_base_usd": "10000"}
    art = _plan(day1_post_fill_audit=audit, day1_allocation_intent=alloc)
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("day1_fingerprint_recompute_mismatch" in b for b in art["blockers"])


def test_missing_day1_symbol_blocked():
    art = _plan(current_positions=_current(drop={"S00USDT"}))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("missing_day1_strategy_symbol:S00USDT" in b for b in art["blockers"])


def test_missing_mark_price_field_blocked():
    art = _plan(current_positions=_current({"S00USDT": {"mark_price": None}}))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("current_position_evidence_incomplete:S00USDT" in b for b in art["blockers"])


def test_high_precision_qty_not_mangled():
    # A high-precision CURRENT position qty must survive canonicalization (no float round-trip)
    # in the snapshot record; the runtime sizing stays the default valid qty.
    hp = "1.123456789012345678"
    art = _plan(current_positions=_current({"S00USDT": {"size": hp}}))
    assert _act(art, "S00USDT")["current_qty"] == hp


# ============================================================ production resolver

d2run = _load("d2_runner_test", "scripts/run_demo_pilot_day2_lifecycle.py")


def _seed_forward_files(tmp_path, omit=()):
    root = tmp_path / "fwd"
    primary = root / fs.PRIMARY_RUN_KEY
    primary.mkdir(parents=True)
    files = {"positions": f"{COMPACT}_positions.parquet", "forward_stats": f"{COMPACT}_forward_stats.json",
             "pnl": f"{COMPACT}_pnl.json", "forward_summary": "forward_summary.json"}
    for role, name in files.items():
        if role in omit:
            continue
        (primary / name).write_text("seed", encoding="utf-8")
    return str(root)


def _fake_loader(run_date, repo_root, forward_source_root):
    return SimpleNamespace(strategy_name=STRATEGY, requested_run_date=run_date,
                           market_data_date=run_date)


def _target_positions(n=N):
    # PlannerResult keeps direction in the SIGN of target_notional (long > 0, short < 0) and
    # carries the runtime price used for sizing.
    return [{"symbol": SYMS[i], "side": SIDES_LS[i],
             "target_notional": ("200" if i < 25 else "-200"), "qty": "2", "qty_step": "0.001",
             "price": "100"} for i in range(n)]


def _real_plan(target_positions=None, status=None, verified=True):
    """Build the REAL PlannerResult (with the canonical ``target_positions`` field, NOT a made-up
    ``targets``) so the resolver is exercised against the actual dataclass contract."""
    return ap.PlannerResult(
        status=status if status is not None else ap.STATUS_PLANNED, actions=[],
        target_positions=target_positions if target_positions is not None else _target_positions(),
        current_positions=[], rejected_signals=[], sizing_verification={"verified": verified})


def _patch_chain(monkeypatch, plan=None):
    monkeypatch.setattr(d2run.fs, "load_primary_forward_strategy_result",
                        lambda *, run_date, repo_root, forward_source_root:
                        _fake_loader(run_date, repo_root, forward_source_root))
    monkeypatch.setattr(d2run.planner, "plan_strategy_native_actions",
                        lambda *, forward_result, provider: plan if plan is not None else _real_plan())


def test_resolve_production_forward_target_four_roles_pass(tmp_path, monkeypatch):
    root = _seed_forward_files(tmp_path)
    _patch_chain(monkeypatch)
    args = _args(tmp_path)
    args.forward_source_root = root
    prod = d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
        network_audit_counters=lambda: _rc()))
    assert set(prod["source_artifacts"]) == set(d2.REQUIRED_SOURCE_ROLES)
    for role in d2.REQUIRED_SOURCE_ROLES:
        assert d2._SHA256_RE.match(prod["source_artifacts"][role]["sha256"])
    assert prod["loader_validation"] == "PASS" and prod["network_audit_counters"] == _rc()
    assert "runner_status" not in prod and "safety_scan" not in prod


@pytest.mark.parametrize("omit", list(d2.REQUIRED_SOURCE_ROLES))
def test_resolver_missing_source_role_raises(tmp_path, monkeypatch, omit):
    root = _seed_forward_files(tmp_path, omit={omit})
    _patch_chain(monkeypatch)
    args = _args(tmp_path)
    args.forward_source_root = root
    with pytest.raises(fs.ForwardSourceError):
        d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
            network_audit_counters=lambda: _rc()))


def test_resolver_without_authorization_no_provider_no_network(tmp_path, monkeypatch):
    # provider=None + allow_real_network False -> must raise BEFORE building provider or touching net.
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))

    class _NoProv:
        def _build_production_provider(self):
            raise AssertionError("provider must not be built without authorization")
    monkeypatch.setattr(d2run, "_load_daily_runner", lambda: _NoProv())
    args = _args(tmp_path)          # allow_real_network defaults False
    with pytest.raises(fs.ForwardSourceError, match="network_not_authorized"):
        d2run.resolve_production_forward_target(args)


def test_resolver_with_authorization_builds_provider_once(tmp_path, monkeypatch):
    root = _seed_forward_files(tmp_path)
    _patch_chain(monkeypatch)
    builds = {"n": 0}
    fake_provider = SimpleNamespace(network_audit_counters=lambda: _rc())

    class _Runner:
        def _build_production_provider(self):
            builds["n"] += 1
            return fake_provider
    monkeypatch.setattr(d2run, "_load_daily_runner", lambda: _Runner())
    args = _args(tmp_path)
    args.allow_real_network = True
    args.forward_source_root = root
    prod = d2run.resolve_production_forward_target(args)   # provider=None -> builds
    assert builds["n"] == 1 and prod["network_audit_counters"] == _rc()


def test_resolver_planner_unverified_raises(tmp_path, monkeypatch):
    # sizing_verification.verified=False (real PlannerResult) -> fail closed before target loop.
    _seed_forward_files(tmp_path)
    _patch_chain(monkeypatch, plan=_real_plan(verified=False))
    args = _args(tmp_path)
    args.forward_source_root = str(tmp_path / "fwd")
    with pytest.raises(fs.ForwardSourceError):
        d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
            network_audit_counters=lambda: _rc()))


def test_resolver_planner_unavailable_raises(tmp_path, monkeypatch):
    # status != STATUS_PLANNED -> PlannerResult.available is False -> fail closed.
    _seed_forward_files(tmp_path)
    _patch_chain(monkeypatch, plan=_real_plan(status=ap.STATUS_PLANNER_UNAVAILABLE))
    args = _args(tmp_path)
    args.forward_source_root = str(tmp_path / "fwd")
    with pytest.raises(fs.ForwardSourceError):
        d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
            network_audit_counters=lambda: _rc()))


def test_resolver_reads_target_positions_not_targets(tmp_path, monkeypatch):
    # Regression for TASK-014BY_FIX2: the REAL PlannerResult has no ``targets`` attribute; the
    # resolver must read ``target_positions``. If it read plan.targets this would AttributeError.
    root = _seed_forward_files(tmp_path)
    tps = _target_positions(3)
    _patch_chain(monkeypatch, plan=_real_plan(target_positions=tps))
    assert not hasattr(ap.PlannerResult(status=ap.STATUS_PLANNED, actions=[], target_positions=[],
                                        current_positions=[], rejected_signals=[],
                                        sizing_verification={}), "targets")
    args = _args(tmp_path)
    args.forward_source_root = root
    prod = d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
        network_audit_counters=lambda: _rc()))
    assert len(prod["intent_allocations"]) == 3 and len(prod["runtime_translation"]) == 3
    a0 = prod["intent_allocations"][0]
    assert a0["symbol"] == "S00USDT" and a0["side"] == "long" and a0["target_notional_usd"] == "200"
    assert "qty" not in a0 and "qty_step" not in a0 and "price_snapshot" not in a0   # intent only
    r0 = prod["runtime_translation"][0]
    assert r0["qty"] == "2" and r0["qty_step"] == "0.001" and r0["price_snapshot"] == "100"


def test_resolver_allocations_map_each_target_position(tmp_path, monkeypatch):
    root = _seed_forward_files(tmp_path)
    tps = [{"symbol": "abcusdt", "side": "short", "target_notional": "-137.5", "qty": "1.25",
            "qty_step": "0.01", "price": "110"},
           {"symbol": "XYZUSDT", "side": "long", "target_notional": "200", "qty": "2",
            "qty_step": "0.001", "price": "100"}]
    _patch_chain(monkeypatch, plan=_real_plan(target_positions=tps))
    args = _args(tmp_path)
    args.forward_source_root = root
    prod = d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
        network_audit_counters=lambda: _rc()))
    assert [a["symbol"] for a in prod["intent_allocations"]] == ["ABCUSDT", "XYZUSDT"]
    assert prod["intent_allocations"][0]["side"] == "short"
    assert prod["intent_allocations"][0]["target_notional_usd"] == "137.5"          # magnitude
    rt0 = prod["runtime_translation"][0]
    assert rt0["qty"] == "1.25" and rt0["qty_step"] == "0.01" and rt0["price_snapshot"] == "110"


def _resolve_single(tmp_path, monkeypatch, side, target_notional, qty=None, price="100",
                    step="0.001"):
    root = _seed_forward_files(tmp_path)
    if qty is None:   # default to the FORMAL helper output so the resolver's qty check passes
        try:
            qty = round_qty_down(abs(float(target_notional)) / float(price), float(step))
        except (TypeError, ValueError):
            qty = "2"     # invalid-notional tests: qty is irrelevant (notional blocks first)
    tps = [{"symbol": "ABCUSDT", "side": side, "target_notional": target_notional, "qty": qty,
            "qty_step": step, "price": price}]
    _patch_chain(monkeypatch, plan=_real_plan(target_positions=tps))
    args = _args(tmp_path)
    args.forward_source_root = root
    return d2run.resolve_production_forward_target(
        args, provider=SimpleNamespace(network_audit_counters=lambda: _rc()))


# --- FIX3: signed planner notional -> positive Day-2 target magnitude ---

def test_short_signed_notional_normalized_to_positive_magnitude(tmp_path, monkeypatch):
    prod = _resolve_single(tmp_path, monkeypatch, "short", "-200")
    a = prod["intent_allocations"][0]
    assert a["side"] == "short" and a["target_notional_usd"] == "200"
    assert prod["runtime_translation"][0]["target_notional_usd"] == "200"


def test_long_notional_preserved_positive(tmp_path, monkeypatch):
    prod = _resolve_single(tmp_path, monkeypatch, "long", "200")
    assert prod["intent_allocations"][0]["target_notional_usd"] == "200"


def test_notional_magnitude_is_decimal_exact(tmp_path, monkeypatch):
    prod = _resolve_single(tmp_path, monkeypatch, "short", "-137.5000")
    tn = prod["intent_allocations"][0]["target_notional_usd"]
    assert tn == "137.5" and "999" not in tn and "137.4" not in tn


def _sealed_from_production(prod):
    return d2.seal_target_intent_artifact(
        pilot_id=PILOT, lifecycle_date=LIFE, signal_date=prod["signal_date"],
        source_identifier=prod["strategy"], source_artifacts=prod["source_artifacts"],
        intent_allocations=prod["intent_allocations"])


def test_full_provenance_pass_with_long_and_short(tmp_path, monkeypatch):
    root = _seed_forward_files(tmp_path)
    _patch_chain(monkeypatch)                          # default 50: 25 long (+200), 25 short (-200)
    args = _args(tmp_path)
    args.forward_source_root = root
    prod = d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
        network_audit_counters=lambda: _rc()))
    assert all(float(a["target_notional_usd"]) > 0 for a in prod["intent_allocations"])
    sealed = _sealed_from_production(prod)
    ok, reasons, _tbs, _sd, _rfp = d2.verify_production_target_provenance(
        sealed_target=sealed, production_recompute=prod, pilot_id=PILOT, lifecycle_date=LIFE)
    assert ok, reasons


@pytest.mark.parametrize("bad", [None, "", "NaN", "Infinity", "0", "not-a-number"])
def test_invalid_notional_never_passes_via_abs(tmp_path, monkeypatch, bad):
    prod = _resolve_single(tmp_path, monkeypatch, "long", bad)
    sealed = d2.seal_target_intent_artifact(
        pilot_id=PILOT, lifecycle_date=LIFE, signal_date=prod["signal_date"],
        source_identifier=prod["strategy"], source_artifacts=prod["source_artifacts"],
        intent_allocations=[{"symbol": "ABCUSDT", "side": "long", "target_notional_usd": "200"}])
    ok, reasons, _tbs, _sd, _rfp = d2.verify_production_target_provenance(
        sealed_target=sealed, production_recompute=prod, pilot_id=PILOT, lifecycle_date=LIFE)
    assert not ok
    assert any("production_target_intent_invalid_notional:ABCUSDT" in r for r in reasons)


def test_planner_fixture_keeps_signed_strategy_contract():
    # The planner contract is UNCHANGED: long +200, short -200. Only the resolver OUTPUT is abs.
    tps = _target_positions()
    assert tps[0]["side"] == "long" and tps[0]["target_notional"] == "200"
    assert tps[25]["side"] == "short" and tps[25]["target_notional"] == "-200"


# --- FIX4: a REAL provider's complete counters are not flagged unaccounted by Day-2 ---

def test_day2_real_provider_counters_not_unaccounted():
    class _Client:
        def get_wallet_balance(self):
            return SimpleNamespace(equity_usd=1e4, available_balance_usd=1e4)

        def get_open_positions(self):
            return []

        def get_instruments_info(self):
            return {}

        def get_account_info(self):
            return SimpleNamespace()

        def get_server_time(self):
            return SimpleNamespace()

        def network_audit_counters(self):
            return {"private_read_only_request_count": 3, "public_read_only_request_count": 2,
                    "private_mutating_request_count": 0}

    class _MP:
        realtime_market_price = 100.0
        price_timestamp_utc = ""

        def is_usable(self):
            return True

    class _Guard:
        def fetch_market_prices(self, symbols):
            return {s: _MP() for s in symbols}

    provider = crun._build_production_provider(_client=_Client(), _guard=_Guard())
    provider.market_price("BTCUSDT")
    prov_ctr = provider.network_audit_counters()
    assert prov_ctr is not None
    art = _plan(network_counter_components=_components(provider=prov_ctr))
    assert not any("unaccounted_network_component:production_forward_provider" in b
                   for b in art["blockers"])
    assert art["network_audit_counters"]["private_read_only_request_count"] == 5   # 3 + collector 2


# ============================================================ runner safety

def _write_inputs(tmp_path):
    audit, alloc = _day1_audit_and_alloc()
    (tmp_path / "audit.json").write_text(json.dumps(audit), encoding="utf-8")
    (tmp_path / "alloc.json").write_text(json.dumps(alloc), encoding="utf-8")
    (tmp_path / "target.json").write_text(json.dumps(_sealed()), encoding="utf-8")


def _args(tmp_path):
    return d2run.build_parser().parse_args([
        "--day2-lifecycle-dry-run", "--pilot-id", PILOT, "--lifecycle-date", LIFE,
        "--day1-date", DAY1, "--day1-fingerprint", DAY1_FP, "--lifecycle-policy", POLICY,
        "--output-root", str(tmp_path / "out"),
        "--day1-post-fill-audit-json", str(tmp_path / "audit.json"),
        "--day1-allocation-intent-json", str(tmp_path / "alloc.json"),
        "--target-intent-artifact-json", str(tmp_path / "target.json"),
        "--artifact-output-json", str(tmp_path / "day2.json")])


def _provider():
    return lambda: (_current(), _prov(), _rc())


def test_runner_ready_with_injected_resolver_and_merged_counters(tmp_path, capsys):
    _write_inputs(tmp_path)
    rc = d2run.run_day2_lifecycle_dry_run(
        _args(tmp_path), position_provider=_provider(),
        forward_target_resolver=lambda: _production(counters=_rc(ro=3, pub=0)))
    assert rc == d2run.EXIT_READY
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == d2.DRY_RUN_READY
    assert out["network_audit_counters"]["private_read_only_request_count"] == 5   # 3 + 2


def test_runner_without_authorization_blocks_no_network(tmp_path, capsys, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))

    class _NoProv:
        def _build_production_provider(self):
            raise AssertionError("provider must not be built")
    monkeypatch.setattr(d2run, "_load_daily_runner", lambda: _NoProv())
    _write_inputs(tmp_path)
    rc = d2run.run_day2_lifecycle_dry_run(_args(tmp_path))   # no injection, no --allow-real-network
    assert rc == d2run.EXIT_BLOCKED
    out = json.loads(capsys.readouterr().out)
    assert any("network_not_authorized" in b for b in out["blockers"])


def test_dry_run_no_sender_execute_pilot_or_batch_attempt(tmp_path, capsys, monkeypatch):
    def _boom(*a, **k):
        raise AssertionError("dry-run must not send / execute / open a network socket")
    import urllib.request
    monkeypatch.setattr(nx, "execute_daily_native", _boom)
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    _write_inputs(tmp_path)
    out_root = str(tmp_path / "out")
    d2run.run_day2_lifecycle_dry_run(_args(tmp_path), position_provider=_provider(),
                                     forward_target_resolver=lambda: _production())
    capsys.readouterr()
    store = nx.NativeExecutionStore(PILOT, LIFE, out_root)
    assert not (store.dir / "batch_attempt.json").exists()
    assert not (store.dir / "execution_state.json").exists()
    assert rd.PilotStateStore(PILOT, out_root).read_state() is None


def test_dry_run_does_not_advance_running_pilot(tmp_path, capsys):
    out_root = str(tmp_path / "out")
    rd.PilotStateStore(PILOT, out_root).write_state({
        "pilot_id": PILOT, "lifecycle_state": rd.RUNNING, "order_execution_authorized": True,
        "live_trading_authorized": False, "completed_successful_days": 1,
        "successful_dates": [DAY1], "target_successful_days": rd.TARGET_SUCCESSFUL_DAYS,
        "remaining_successful_days": 6, "event_count": 1})
    _write_inputs(tmp_path)
    d2run.run_day2_lifecycle_dry_run(_args(tmp_path), position_provider=_provider(),
                                     forward_target_resolver=lambda: _production())
    st = rd.PilotStateStore(PILOT, out_root).read_state()
    assert st["completed_successful_days"] == 1 and st["successful_dates"] == [DAY1]
