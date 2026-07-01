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


def _allocs(overrides=None, add=None, drop=None):
    out = []
    for i in range(N):
        if drop and SYMS[i] in drop:
            continue
        a = {"symbol": SYMS[i], "side": SIDES_LS[i], "target_notional_usd": "200",
             "qty": "2", "qty_step": "0.001"}
        if overrides and SYMS[i] in overrides:
            a.update(overrides[SYMS[i]])
        out.append(a)
    if add:
        out.extend(add)
    return out


def _production(allocs=None, signal_date=LIFE, strategy=STRATEGY, sources=None,
                loader_validation="PASS", counters=None, **extra):
    prod = {"strategy": strategy, "requested_run_date": LIFE, "signal_date": signal_date,
            "loader_validation": loader_validation,
            "source_artifacts": sources if sources is not None else _source_artifacts(),
            "network_audit_counters": counters if counters is not None else _rc(),
            "allocations": allocs if allocs is not None else _allocs()}
    prod.update(extra)
    return prod


def _sealed(allocs=None, signal_date=LIFE, source_id=STRATEGY, sources=None):
    return d2.seal_target_intent_artifact(
        pilot_id=PILOT, lifecycle_date=LIFE, signal_date=signal_date, source_identifier=source_id,
        source_artifacts=sources if sources is not None else _source_artifacts(),
        allocations=allocs if allocs is not None else _allocs())


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
    art = _plan(sealed_target=_sealed(_allocs(drop={"S00USDT"})),
                production_target_recompute=_production(_allocs(drop={"S00USDT"})))
    assert _act(art, "S00USDT")["proposed_action"] == "CLOSE"
    assert _act(art, "S00USDT")["close_notional_estimate_usd"] == "200"


def test_increase_decrease_reverse():
    inc = _plan(sealed_target=_sealed(_allocs({"S00USDT": {"qty": "5"}})),
                production_target_recompute=_production(_allocs({"S00USDT": {"qty": "5"}})))
    assert _act(inc, "S00USDT")["proposed_action"] == "INCREASE"
    dec = _plan(sealed_target=_sealed(_allocs({"S00USDT": {"qty": "1"}})),
                production_target_recompute=_production(_allocs({"S00USDT": {"qty": "1"}})))
    assert _act(dec, "S00USDT")["proposed_action"] == "DECREASE"
    rev = _plan(sealed_target=_sealed(_allocs({"S00USDT": {"side": "short"}})),
                production_target_recompute=_production(_allocs({"S00USDT": {"side": "short"}})),
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


# ============================================================ provenance / allocation validation (kept)

def test_recompute_vs_sealed_differ_one_qty_blocked():
    art = _plan(production_target_recompute=_production(_allocs({"S00USDT": {"qty": "7"}})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("target_qty_mismatch_production:S00USDT" in b for b in art["blockers"])


def test_loader_validation_not_pass_blocks():
    art = _plan(production_target_recompute=_production(loader_validation="",
                                                       runner_status="OK", safety_scan="PASS"))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("production_loader_validation_not_pass" in b for b in art["blockers"])


def test_sealed_duplicate_symbol_blocked():
    dup = _allocs() + [{"symbol": "S00USDT", "side": "long", "target_notional_usd": "200",
                        "qty": "2", "qty_step": "0.001"}]
    art = _plan(sealed_target=_sealed(dup))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("sealed_target_duplicate_symbol:S00USDT" in b for b in art["blockers"])


@pytest.mark.parametrize("bad", ["NaN", "Infinity", "0"])
def test_invalid_qty_blocked(bad):
    art = _plan(sealed_target=_sealed(_allocs({"S00USDT": {"qty": bad}})),
                production_target_recompute=_production(_allocs({"S00USDT": {"qty": bad}})))
    assert art["verdict"] == d2.DRY_RUN_BLOCKED
    assert any("invalid_qty:S00USDT" in b for b in art["blockers"])


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
    hp = "1.123456789012345678"
    art = _plan(current_positions=_current({"S00USDT": {"size": hp}}),
                sealed_target=_sealed(_allocs({"S00USDT": {"qty": hp}})),
                production_target_recompute=_production(_allocs({"S00USDT": {"qty": hp}})))
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
    return [{"symbol": SYMS[i], "side": SIDES_LS[i], "target_notional": "200", "qty": "2",
             "qty_step": "0.001"} for i in range(n)]


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
    assert len(prod["allocations"]) == 3                       # one per target_positions row
    a0 = prod["allocations"][0]
    assert a0["symbol"] == "S00USDT" and a0["side"] == "long"
    assert a0["target_notional_usd"] == "200" and a0["qty"] == "2" and a0["qty_step"] == "0.001"


def test_resolver_allocations_map_each_target_position(tmp_path, monkeypatch):
    root = _seed_forward_files(tmp_path)
    tps = [{"symbol": "abcusdt", "side": "short", "target_notional": "137.5", "qty": "1.25",
            "qty_step": "0.01"},
           {"symbol": "XYZUSDT", "side": "long", "target_notional": "200", "qty": "2",
            "qty_step": "0.001"}]
    _patch_chain(monkeypatch, plan=_real_plan(target_positions=tps))
    args = _args(tmp_path)
    args.forward_source_root = root
    prod = d2run.resolve_production_forward_target(args, provider=SimpleNamespace(
        network_audit_counters=lambda: _rc()))
    assert [a["symbol"] for a in prod["allocations"]] == ["ABCUSDT", "XYZUSDT"]   # upper-cased
    assert prod["allocations"][0]["side"] == "short"
    assert prod["allocations"][0]["target_notional_usd"] == "137.5"
    assert prod["allocations"][0]["qty"] == "1.25" and prod["allocations"][0]["qty_step"] == "0.01"


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
