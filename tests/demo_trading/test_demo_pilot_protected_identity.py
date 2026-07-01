"""TASK-014CA(+FIX1/2/3): pre-Day-1 protected-position identity bootstrap tests.

Readiness is RE-DERIVED from the canonical classification (a flipped bootstrap_ready/execution_ready
never validates); continuity carries a full fingerprint+digest and is verdict-replayed from its
canonical evidence; per-page request provenance is formally validated; the continuity CLI validates
the formal allocation artifact BEFORE any network read. Evidence validity stays separate from
bootstrap readiness. Fully offline (no Bybit, no key, no Pilot state).
"""
from __future__ import annotations

import argparse
import copy
import importlib.util
import json
import os

import pytest

from src import demo_pilot_protected_identity_bootstrap as pib

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


cli = _load("pib_cli_test", "scripts/run_demo_pilot_protected_identity_snapshot.py")

PILOT = "BYBIT_DEMO_PILOT_7D_202607_V2"
RETIRED = "BYBIT_DEMO_PILOT_7D_202606_V1"
DAY1 = "2026-07-05"
GEN = "2026-07-05T00:00:00+00:00"
STRATEGY = [f"S{i:02d}USDT" for i in range(50)]
ZERO_SHA = "sha256:" + "0" * 64


# ------------------------------------------------------------------ fixture builders
def _pos(symbol, side, qty, position_idx, entry_price="100", leverage="2"):
    return {"symbol": symbol, "side": side, "qty": qty, "position_idx": position_idx,
            "entry_price": entry_price, "leverage": leverage}


def _edu(**over):
    row = _pos("EDUUSDT", "Sell", "1234", 2, entry_price="9", leverage="3")
    row.update(over)
    return row


def _page(page_number=1, cursor=False, nxt=False, raw=1, nz=1, endpoint="/v5/position/list",
          started="2026-07-05T00:00:00Z", received="2026-07-05T00:00:01Z", elapsed=12.3):
    return {"page_number": page_number, "endpoint": endpoint, "request_started_at_utc": started,
            "response_received_at_utc": received, "request_elapsed_ms": elapsed,
            "request_cursor_present": cursor, "response_next_cursor_present": nxt,
            "raw_row_count": raw, "nonzero_row_count": nz}


def _prov(positions, reason="empty_cursor", pages=None):
    n = len(positions)
    pages = [_page(raw=n, nz=n)] if pages is None else pages
    return {"termination_reason": reason, "page_count": len(pages), "api_position_rows": n,
            "nonzero_position_count": n, "position_page_request_evidence": pages}


def _ctr(ro=1, pub=0, mut=0):
    return {"private_read_only_request_count": ro, "public_read_only_request_count": pub,
            "private_mutating_request_count": mut}


def _components(ctr="default"):
    return {"protected_position_collector": _ctr() if ctr == "default" else ctr}


def _account(**over):
    a = {"account_mode": "demo", "demo_flag": True, "endpoint_family": "bybit_demo",
         "base_url_used": "https://api-demo.bybit.com", "live_endpoint_fallback_detected": False}
    a.update(over)
    return a


def _snapshot(positions=None, provenance=None, components="default", account=None,
              pilot_id=PILOT, day1_date=DAY1):
    positions = [_edu()] if positions is None else positions
    provenance = _prov(positions) if provenance is None else provenance
    return pib.build_pre_day1_protected_snapshot(
        pilot_id=pilot_id, day1_date=day1_date, positions=positions,
        positions_provenance=provenance,
        network_counter_components=_components() if components == "default" else components,
        account_evidence=_account() if account is None else account,
        source_endpoint="/v5/position/list", generated_at=GEN)


def _alloc(pilot_id=PILOT, day1_date=DAY1):
    allocs = [{"symbol": STRATEGY[i], "side": ("Buy" if i < 25 else "Sell"),
               "target_notional_usd": "200"} for i in range(50)]
    fp = pib._crun().allocation_intent_fingerprint(
        allocs, pilot_id=pilot_id, date=day1_date, strategy_capital_base_usd="10000")
    return {"pilot_id": pilot_id, "date": day1_date, "strategy_capital_base_usd": "10000",
            "order_payloads": allocs, "payload_fingerprint": fp,
            "allocation_intent_fingerprint": fp}


def _binding(snapshot=None, allocation=None, pilot_id=PILOT, day1_date=DAY1, alloc_sha=ZERO_SHA):
    snapshot = _snapshot() if snapshot is None else snapshot
    allocation = _alloc(pilot_id, day1_date) if allocation is None else allocation
    return pib.build_day1_protected_binding(
        pilot_id=pilot_id, day1_date=day1_date, day1_allocation_artifact=allocation,
        snapshot_artifact=snapshot, allocation_source_sha256=alloc_sha)


def _continuity(snapshot=None, binding=None, post_positions=None, post_prov=None,
                components="default", strategy_symbols=None, allocation=None):
    snapshot = _snapshot() if snapshot is None else snapshot
    allocation = _alloc() if allocation is None else allocation
    binding = _binding(snapshot, allocation) if binding is None else binding
    post_positions = [_edu()] if post_positions is None else post_positions
    post_prov = _prov(post_positions) if post_prov is None else post_prov
    return pib.verify_post_fill_protected_continuity(
        pilot_id=PILOT, day1_date=DAY1, snapshot_artifact=snapshot, binding_artifact=binding,
        post_fill_positions=post_positions, post_fill_provenance=post_prov,
        network_counter_components=_components() if components == "default" else components,
        strategy_symbols=STRATEGY if strategy_symbols is None else strategy_symbols,
        allocation_intent_fingerprint=allocation["allocation_intent_fingerprint"],
        allocation_artifact_source_sha256=ZERO_SHA, generated_at="2026-07-05T23:00:00+00:00")


def _fifty_plus_edu():
    return [_edu()] + [_pos(STRATEGY[i], "Buy", "1", 0) for i in range(50)]


def _reseal_snapshot(s):
    s["bootstrap_readiness_fingerprint"] = pib.canonical_bootstrap_readiness_fingerprint(s)
    s["protected_position_snapshot_fingerprint"] = pib.canonical_protected_snapshot_fingerprint(s)
    s["protected_position_snapshot_digest"] = pib.canonical_protected_snapshot_digest(s)
    return s


def _reseal_binding(b):
    b["binding_fingerprint"] = pib.canonical_binding_fingerprint(b)
    b["binding_digest"] = pib.canonical_binding_digest(b)
    return b


def _reseal_cont(c):
    c["post_fill_continuity_fingerprint"] = pib.canonical_continuity_fingerprint(c)
    c["post_fill_continuity_digest"] = pib.canonical_continuity_digest(c)
    return c


# ================================================= snapshot readiness derivation (forgery)
def test_1_forged_bootstrap_ready_blocks():
    s = _snapshot(positions=_fifty_plus_edu())
    t = copy.deepcopy(s)
    t["bootstrap_ready"] = True
    t["bootstrap_verdict"] = pib.BOOTSTRAP_READY
    t["readiness_blockers"] = []
    t["blockers"] = []
    _reseal_snapshot(t)   # even a full reseal cannot beat the derivation
    ok, reasons, *_ = pib._snapshot_is_sealed(t)
    assert ok is False and "snapshot_bootstrap_ready_derivation_mismatch" in reasons


def test_2_cleared_readiness_blockers_block():
    s = _snapshot(positions=_fifty_plus_edu())
    t = copy.deepcopy(s)
    t["readiness_blockers"] = []
    t["blockers"] = []
    _reseal_snapshot(t)
    ok, reasons, *_ = pib._snapshot_is_sealed(t)
    assert ok is False and "snapshot_readiness_blockers_derivation_mismatch" in reasons


def test_3_deleted_nonprotected_row_blocks():
    s = _snapshot(positions=_fifty_plus_edu())
    t = copy.deepcopy(s)
    t["preexisting_nonprotected_positions"].pop()
    t["all_observed_nonzero_positions"].pop()
    t["preexisting_nonprotected_position_count"] -= 1
    t["all_observed_nonzero_count"] -= 1
    _reseal_snapshot(t)   # pagination nonzero (51) no longer matches observed (50)
    ok, reasons, *_ = pib._snapshot_is_sealed(t)
    assert ok is False and "snapshot_pagination_nonzero_mismatch" in reasons


# ================================================= binding execution readiness (forgery)
def test_4_forged_binding_execution_ready_blocks():
    s = _snapshot(positions=_fifty_plus_edu())
    b = _binding(s)
    assert b["execution_ready"] is False
    t = copy.deepcopy(b)
    t["execution_ready"] = True
    _reseal_binding(t)
    ok, reasons = pib._binding_is_sealed(t, s)
    assert ok is False and "binding_execution_ready_mismatch" in reasons


def test_5_cleared_binding_readiness_blockers_block():
    s = _snapshot(positions=_fifty_plus_edu())
    b = _binding(s)
    t = copy.deepcopy(b)
    t["readiness_blockers"] = []
    _reseal_binding(t)
    ok, reasons = pib._binding_is_sealed(t, s)
    assert ok is False and "binding_readiness_blockers_mismatch" in reasons


def test_6_snapshot_not_ready_binding_never_execution_ready():
    s = _snapshot(positions=_fifty_plus_edu())
    b = _binding(s)
    ok, reasons = pib._binding_is_sealed(b, s, require_execution_ready=True)
    assert ok is False and "binding_not_execution_ready" in reasons


# ================================================= continuity integrity + replay
def test_7_continuity_mutating_outer_digest_only_blocks():
    c = _continuity()
    t = copy.deepcopy(c)
    t["network_audit_counters"]["private_mutating_request_count"] = 1
    t["post_fill_continuity_digest"] = pib.canonical_continuity_digest(t)   # NOT the fingerprint
    ok, reasons = pib._continuity_is_sealed(t, _snapshot(), _binding())
    assert ok is False and "continuity_fingerprint_mismatch" in reasons


def test_8_continuity_incomplete_pagination_pass_blocks():
    c = _continuity()
    t = copy.deepcopy(c)
    t["pagination_evidence"]["termination_reason"] = "max_page_cap_exceeded"
    _reseal_cont(t)
    ok, reasons = pib._continuity_is_sealed(t, _snapshot(), _binding())
    assert ok is False and "continuity_semantic_replay_blocked" in reasons


def test_9_continuity_flipped_pass_blocks():
    bad = _continuity(post_positions=[_edu(qty="1")])   # genuinely BLOCKED
    t = copy.deepcopy(bad)
    t["continuity_pass"] = True
    t["verdict"] = "PASS"
    t["blockers"] = []
    _reseal_cont(t)
    ok, reasons = pib._continuity_is_sealed(t, _snapshot(), _binding())
    assert ok is False and "continuity_semantic_replay_blocked" in reasons


def test_10_continuity_modified_edu_blocks():
    c = _continuity()
    t = copy.deepcopy(c)
    t["canonical_post_fill_positions"][0]["qty"] = "9"
    _reseal_cont(t)
    ok, reasons = pib._continuity_is_sealed(t, _snapshot(), _binding())
    assert ok is False


# ================================================= page request evidence validation
def test_11_page_count_row_count_mismatch_blocks():
    prov = _prov([_edu()])
    prov["page_count"] = 2   # but only one timing row
    art = _snapshot(provenance=prov)
    assert art["snapshot_evidence_valid"] is False
    assert any("page_evidence_count_mismatch" in b for b in art["evidence_blockers"])


def test_12_page_row_totals_mismatch_blocks():
    prov = _prov([_edu()], pages=[_page(raw=5, nz=5)])   # raw sum 5 != api_position_rows 1
    art = _snapshot(provenance=prov)
    assert art["snapshot_evidence_valid"] is False
    assert any("page_raw_row_total_mismatch" in b for b in art["evidence_blockers"])


def test_13_final_next_cursor_true_blocks():
    prov = _prov([_edu()], pages=[_page(nxt=True)])
    art = _snapshot(provenance=prov)
    assert art["snapshot_evidence_valid"] is False
    assert any("final_page_next_cursor_present" in b for b in art["evidence_blockers"])


def test_14_negative_elapsed_and_missing_timestamp_block():
    a = _snapshot(provenance=_prov([_edu()], pages=[_page(elapsed=-1.0)]))
    assert a["snapshot_evidence_valid"] is False
    assert any("request_elapsed_invalid" in b for b in a["evidence_blockers"])
    b = _snapshot(provenance=_prov([_edu()], pages=[_page(started="")]))
    assert b["snapshot_evidence_valid"] is False
    assert any("request_started_missing" in x for x in b["evidence_blockers"])


# ================================================= continuity CLI allocation-before-network
class _Provider:
    def __init__(self):
        self.called = False

    def __call__(self):
        self.called = True
        return ([_edu()], _prov([_edu()]), _ctr())


def _write(tmp_path, name, obj):
    p = tmp_path / name
    p.write_text(json.dumps(obj), encoding="utf-8")
    return str(p)


def _sha_of(path):
    import hashlib
    with open(path, "rb") as fh:
        return "sha256:" + hashlib.sha256(fh.read()).hexdigest()


def _cont_args(tmp_path, snapshot, binding, allocation, out="cont.json"):
    snap_p = _write(tmp_path, "snap.json", snapshot)
    bind_p = _write(tmp_path, "binding.json", binding)
    alloc_p = _write(tmp_path, "alloc.json", allocation)
    return argparse.Namespace(
        pilot_id=PILOT, day1_date=DAY1, protected_snapshot_json=snap_p, protected_binding_json=bind_p,
        day1_allocation_intent_json=alloc_p, artifact_output_json=str(tmp_path / out),
        allow_real_network=False, capture_pre_day1_protected_snapshot=False,
        build_day1_protected_binding=False, verify_post_fill_protected_continuity=True), alloc_p


def test_15_continuity_cli_tampered_allocation_blocks_before_network(tmp_path, capsys):
    snap = _snapshot()
    alloc = _alloc()
    alloc_p = _write(tmp_path, "alloc.json", alloc)
    binding = _binding(snap, alloc, alloc_sha=_sha_of(alloc_p))
    tampered = copy.deepcopy(alloc)
    tampered["order_payloads"][0]["side"] = ("Sell" if tampered["order_payloads"][0]["side"] == "Buy" else "Buy")
    args, ap = _cont_args(tmp_path, snap, binding, tampered)
    provider = _Provider()
    rc = cli.run_verify_continuity(args, positions_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert rc == cli.EXIT_BLOCKED and provider.called is False
    assert any("allocation" in b for b in data["blockers"])


def test_16_continuity_cli_allocation_sha_mismatch_blocks(tmp_path, capsys):
    snap = _snapshot()
    alloc = _alloc()
    binding = _binding(snap, alloc, alloc_sha="sha256:" + "e" * 64)   # wrong recorded sha
    args, ap = _cont_args(tmp_path, snap, binding, alloc)
    provider = _Provider()
    rc = cli.run_verify_continuity(args, positions_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert rc == cli.EXIT_BLOCKED and provider.called is False
    assert "continuity_allocation_source_sha256_mismatch" in data["blockers"]


def test_17_continuity_cli_cross_pilot_allocation_blocks(tmp_path, capsys):
    snap = _snapshot()
    alloc = _alloc()
    alloc_p = _write(tmp_path, "alloc.json", alloc)
    binding = _binding(snap, alloc, alloc_sha=_sha_of(alloc_p))
    cross = _alloc(pilot_id="BYBIT_DEMO_PILOT_7D_202607_V9")
    args, ap = _cont_args(tmp_path, snap, binding, cross)
    provider = _Provider()
    rc = cli.run_verify_continuity(args, positions_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert rc == cli.EXIT_BLOCKED and provider.called is False
    assert "allocation_pilot_id_mismatch" in data["blockers"]


# ================================================= carried-over core coverage
def test_51_position_valid_evidence_not_ready():
    art = _snapshot(positions=_fifty_plus_edu())
    assert art["snapshot_evidence_valid"] is True and art["bootstrap_ready"] is False
    assert pib._SHA256_RE.match(art["protected_position_snapshot_fingerprint"])
    assert art["protected_position_count"] == 1 and art["preexisting_nonprotected_position_count"] == 50
    ok, reasons, _fp, _d, ready = pib._snapshot_is_sealed(art)
    assert ok is True and ready is False


def test_empty_account_valid_and_ready():
    art = _snapshot(positions=[], provenance=_prov([], pages=[_page(raw=0, nz=0)]))
    assert art["snapshot_evidence_valid"] is True and art["bootstrap_ready"] is True
    assert art["canonical_protected_positions"] == []
    ok, *_ = pib._snapshot_is_sealed(art)
    assert ok is True


def test_incomplete_pagination_evidence_invalid():
    art = _snapshot(provenance=_prov([_edu()], reason="max_page_cap_exceeded"))
    assert art["snapshot_evidence_valid"] is False
    assert art["protected_position_snapshot_fingerprint"] == ""


def test_only_canonical_protected_enters_identity():
    art = _snapshot(positions=[_edu(), _pos("RANDUSDT", "Buy", "3", 0)])
    assert art["protected_symbol_set"] == ["EDUUSDT"]
    assert [r["symbol"] for r in art["preexisting_nonprotected_positions"]] == ["RANDUSDT"]


def test_hedge_mode_positions_do_not_collide():
    art = _snapshot(positions=[_edu(side="Buy", qty="5", position_idx=1),
                               _edu(side="Sell", qty="7", position_idx=2)],
                    provenance=_prov([1, 2], pages=[_page(raw=2, nz=2)]))
    rows = {(r["symbol"], r["position_idx"]): r["qty"] for r in art["canonical_protected_positions"]}
    assert rows == {("EDUUSDT", 1): "5", ("EDUUSDT", 2): "7"}


def test_duplicate_composite_key_blocks():
    art = _snapshot(positions=[_edu(qty="5", position_idx=2), _edu(qty="7", position_idx=2)],
                    provenance=_prov([1, 2], pages=[_page(raw=2, nz=2)]))
    assert art["snapshot_evidence_valid"] is False
    assert any("duplicate_position_composite_key" in b for b in art["evidence_blockers"])


def test_no_duplicate_protected_position_arrays():
    art = _snapshot()
    assert "protected_positions" not in art
    assert art["protected_positions_summary"] == {"count": 1, "symbols": ["EDUUSDT"]}


def test_snapshot_qty_tamper_with_outer_digest_still_blocks():
    snap = _snapshot()
    t = copy.deepcopy(snap)
    t["canonical_protected_positions"][0]["qty"] = "9999"
    t["protected_position_snapshot_digest"] = pib.canonical_protected_snapshot_digest(t)
    ok, reasons, *_ = pib._snapshot_is_sealed(t)
    assert ok is False and "snapshot_fingerprint_mismatch" in reasons


def test_missing_entry_price_blocks_evidence():
    p = _edu()
    del p["entry_price"]
    art = _snapshot(positions=[p])
    assert art["snapshot_evidence_valid"] is False
    assert any("audit_incomplete" in b and "entry_price" in b for b in art["evidence_blockers"])


def test_raw_sha_allocation_does_not_complete():
    fake = {"pilot_id": PILOT, "date": DAY1, "strategy_capital_base_usd": "10000",
            "allocation_intent_fingerprint": "a" * 64, "payload_fingerprint": "a" * 64,
            "order_payloads": []}
    b = _binding(allocation=fake)
    assert b["binding_evidence_valid"] is False


def test_valid_allocation_binding_execution_ready():
    snap = _snapshot()
    b = _binding(snap)
    assert b["binding_evidence_valid"] is True and b["execution_ready"] is True
    ok, reasons = pib._binding_is_sealed(b, snap)
    assert ok is True and reasons == []


def test_continuity_pass_and_counts_and_timing():
    c = _continuity(post_positions=[_edu(), _pos(STRATEGY[0], "Buy", "0.5", 0)],
                    post_prov=_prov([1, 2], pages=[_page(raw=2, nz=2)]))
    assert c["protected_position_identity_continuity"] == "PASS"
    assert c["strategy_position_count"] == 1 and c["protected_position_count"] == 1
    assert len(c["position_page_request_evidence"]) == 1
    ok, reasons = pib._continuity_is_sealed(c, _snapshot(), _binding())
    assert ok is True and reasons == []


def test_continuity_empty_protected_set_pass():
    snap = _snapshot(positions=[], provenance=_prov([], pages=[_page(raw=0, nz=0)]))
    b = _binding(snap)
    c = _continuity(snapshot=snap, binding=b, post_positions=[_pos(STRATEGY[0], "Buy", "1", 0)])
    assert c["protected_position_identity_continuity"] == "PASS" and c["protected_position_count"] == 0
    ok, _ = pib._continuity_is_sealed(c, snap, b)
    assert ok is True


def test_retired_pilot_cannot_bootstrap_or_repair():
    assert _snapshot(pilot_id=RETIRED)["snapshot_evidence_valid"] is False
    b = pib.build_day1_protected_binding(
        pilot_id=RETIRED, day1_date="2026-06-30",
        day1_allocation_artifact=_alloc(RETIRED, "2026-06-30"), snapshot_artifact=_snapshot())
    assert b["binding_evidence_valid"] is False


def test_chain_verifier_accepts_valid_edu_chain():
    snap = _snapshot()
    b = _binding(snap)
    c = _continuity(snap, b)
    cur = {("EDUUSDT", 2): {"symbol": "EDUUSDT", "side": "short", "qty": "1234", "position_idx": 2}}
    ok, reasons = pib.verify_day1_protected_identity_chain(
        pilot_id=PILOT, day1_date=DAY1, snapshot=snap, binding=b, continuity=c,
        current_protected_identities=cur, day1_allocation_intent=_alloc())
    assert ok is True and reasons == []


def test_snapshot_network_mutation_blocks():
    assert _snapshot(components=_components(_ctr(mut=1)))["snapshot_evidence_valid"] is False


def test_pure_core_is_offline(monkeypatch):
    import socket
    monkeypatch.setattr(socket, "socket",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("socket opened")))
    snap = _snapshot()
    b = _binding(snap)
    _continuity(snap, b)
    assert snap["snapshot_evidence_valid"] is True


# ================================================= CLI: modes, no-clobber, offline binding
def test_cli_default_does_nothing(capsys):
    rc = cli.main([])
    out = json.loads(capsys.readouterr().out)
    assert out["blockers"] == ["no_mode_selected"] and rc == cli.EXIT_INVALID


def test_cli_mutually_exclusive_modes(capsys):
    rc = cli.main(["--capture-pre-day1-protected-snapshot", "--build-day1-protected-binding"])
    out = json.loads(capsys.readouterr().out)
    assert any("mutually_exclusive_modes" in b for b in out["blockers"]) and rc == cli.EXIT_INVALID


def test_cli_capture_offline_provider_includes_timing(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    provider = lambda: ([_edu()], _prov([_edu()]), _ctr(), _account())  # noqa: E731
    args = argparse.Namespace(
        pilot_id=PILOT, day1_date=DAY1, artifact_output_json=str(out_path), allow_real_network=False,
        capture_pre_day1_protected_snapshot=True, build_day1_protected_binding=False,
        verify_post_fill_protected_continuity=False)
    rc = cli.run_capture(args, snapshot_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert data["bootstrap_ready"] is True and rc == cli.EXIT_OK
    assert len(data["position_page_request_evidence"]) == 1


def test_cli_build_binding_fully_offline(tmp_path, monkeypatch, capsys):
    import socket
    monkeypatch.setattr(socket, "socket",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("socket opened")))
    snap_path = _write(tmp_path, "snap.json", _snapshot())
    alloc_path = _write(tmp_path, "alloc.json", _alloc())
    out_path = tmp_path / "binding.json"
    rc = cli.main(["--build-day1-protected-binding", "--pilot-id", PILOT, "--day1-date", DAY1,
                   "--protected-snapshot-json", snap_path,
                   "--day1-allocation-intent-json", alloc_path,
                   "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert data["binding_evidence_valid"] is True and data["execution_ready"] is True
    assert rc == cli.EXIT_OK and out_path.exists()
    assert data["allocation_artifact_source_sha256"].startswith("sha256:")


def test_cli_continuity_full_offline_pass(tmp_path, capsys):
    snap = _snapshot()
    alloc = _alloc()
    alloc_path = _write(tmp_path, "alloc.json", alloc)
    binding = _binding(snap, alloc, alloc_sha=_sha_of(alloc_path))
    args, _ = _cont_args(tmp_path, snap, binding, alloc)
    provider = _Provider()
    rc = cli.run_verify_continuity(args, positions_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert data["protected_position_identity_continuity"] == "PASS" and rc == cli.EXIT_OK
    assert provider.called is True and len(data["position_page_request_evidence"]) == 1


def test_cli_all_modes_refuse_overwrite(tmp_path, capsys):
    out_path = tmp_path / "exists.json"
    out_path.write_text("{}", encoding="utf-8")
    snap_path = _write(tmp_path, "snap.json", _snapshot())
    alloc_path = _write(tmp_path, "alloc.json", _alloc())
    bind_path = _write(tmp_path, "binding.json", _binding())
    calls = [
        ["--capture-pre-day1-protected-snapshot", "--pilot-id", PILOT, "--day1-date", DAY1,
         "--artifact-output-json", str(out_path)],
        ["--build-day1-protected-binding", "--pilot-id", PILOT, "--day1-date", DAY1,
         "--protected-snapshot-json", snap_path, "--day1-allocation-intent-json", alloc_path,
         "--artifact-output-json", str(out_path)],
        ["--verify-post-fill-protected-continuity", "--pilot-id", PILOT, "--day1-date", DAY1,
         "--protected-snapshot-json", snap_path, "--protected-binding-json", bind_path,
         "--day1-allocation-intent-json", alloc_path, "--artifact-output-json", str(out_path)],
    ]
    for argv in calls:
        rc = cli.main(argv)
        data = json.loads(capsys.readouterr().out)
        assert "artifact_output_exists_refuse_overwrite" in data["blockers"] and rc == cli.EXIT_INVALID
