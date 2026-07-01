"""TASK-014CA(+FIX1): pre-Day-1 protected-position identity bootstrap tests.

Protected != every open position: only canonical PROTECTED_SYMBOLS enter the sealed identity; a
NEW Pilot's inherited 50 strategy positions BLOCK bootstrap. Identity is COMPOSITE
``(symbol, position_idx)``. Snapshot/binding fingerprints+digests are self-recomputed (a
qty/allocation tamper that only re-derives the outer digest still fails). Binding requires a FORMAL
allocation artifact validated by the production recompute (a raw SHA is not enough). Post-fill
continuity requires EXACT identity. Retired Pilots can never be repaired. Fully offline.
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


# ------------------------------------------------------------------ fixture builders
def _pos(symbol, side, qty, position_idx, entry_price="100", leverage="2"):
    return {"symbol": symbol, "side": side, "qty": qty, "position_idx": position_idx,
            "entry_price": entry_price, "leverage": leverage}


def _edu(**over):
    row = _pos("EDUUSDT", "Sell", "1234", 2, entry_price="9", leverage="3")
    row.update(over)
    return row


def _prov(positions, reason="empty_cursor", pages=1):
    n = len(positions)
    return {"termination_reason": reason, "page_count": pages,
            "api_position_rows": n, "nonzero_position_count": n}


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


def _binding(snapshot=None, allocation=None, pilot_id=PILOT, day1_date=DAY1):
    snapshot = _snapshot() if snapshot is None else snapshot
    allocation = _alloc(pilot_id, day1_date) if allocation is None else allocation
    return pib.build_day1_protected_binding(
        pilot_id=pilot_id, day1_date=day1_date, day1_allocation_artifact=allocation,
        snapshot_artifact=snapshot)


def _continuity(snapshot=None, binding=None, post_positions=None, post_prov=None,
                components="default", strategy_symbols=None, pilot_id=PILOT, day1_date=DAY1):
    snapshot = _snapshot() if snapshot is None else snapshot
    binding = _binding(snapshot) if binding is None else binding
    post_positions = [_edu()] if post_positions is None else post_positions
    post_prov = _prov(post_positions) if post_prov is None else post_prov
    return pib.verify_post_fill_protected_continuity(
        pilot_id=pilot_id, day1_date=day1_date, snapshot_artifact=snapshot,
        binding_artifact=binding, post_fill_positions=post_positions,
        post_fill_provenance=post_prov,
        network_counter_components=_components() if components == "default" else components,
        strategy_symbols=STRATEGY if strategy_symbols is None else strategy_symbols,
        generated_at="2026-07-05T23:00:00+00:00")


# ============================================================ A: 50 strategy + EDU ownership boundary
def test_a_fifty_strategy_plus_edu_blocks_ownership():
    positions = [_edu()] + [_pos(STRATEGY[i], "Buy", "1", 0) for i in range(50)]
    art = _snapshot(positions=positions)
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert art["protected_position_count"] == 1
    assert art["protected_symbol_set"] == ["EDUUSDT"]
    assert art["preexisting_nonprotected_position_count"] == 50
    assert "preexisting_nonprotected_positions_require_ownership_resolution" in art["blockers"]
    assert art["protected_position_snapshot_fingerprint"] == ""


# ============================================================ B: canonical protected filtering
def test_b_only_canonical_protected_enters_identity():
    art = _snapshot(positions=[_edu(), _pos("RANDUSDT", "Buy", "3", 0)])
    assert art["protected_symbol_set"] == ["EDUUSDT"]
    assert [r["symbol"] for r in art["preexisting_nonprotected_positions"]] == ["RANDUSDT"]
    edu = _snapshot(positions=[_edu()])
    assert edu["verdict"] == pib.SNAPSHOT_READY and edu["protected_position_count"] == 1


# ============================================================ C: hedge mode composite identity
def test_c_hedge_mode_positions_do_not_collide():
    art = _snapshot(positions=[_edu(side="Buy", qty="5", position_idx=1),
                               _edu(side="Sell", qty="7", position_idx=2)])
    assert art["verdict"] == pib.SNAPSHOT_READY
    rows = {(r["symbol"], r["position_idx"]): r["qty"] for r in art["canonical_protected_positions"]}
    assert rows == {("EDUUSDT", 1): "5", ("EDUUSDT", 2): "7"}
    assert art["position_mode_evidence"]["position_mode"] == "hedge"


# ============================================================ D: duplicate composite key
def test_d_duplicate_composite_key_blocks():
    art = _snapshot(positions=[_edu(qty="5", position_idx=2), _edu(qty="7", position_idx=2)])
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("duplicate_position_composite_key" in b for b in art["blockers"])


# ============================================================ E: snapshot fingerprint tamper
def test_e_snapshot_qty_tamper_with_outer_digest_still_blocks():
    snap = _snapshot()
    tampered = copy.deepcopy(snap)
    tampered["canonical_protected_positions"][0]["qty"] = "9999"
    tampered["protected_position_snapshot_digest"] = pib.canonical_protected_snapshot_digest(tampered)
    ok, reasons, _fp, _d = pib._snapshot_is_sealed(tampered)
    assert ok is False and "snapshot_fingerprint_mismatch" in reasons


# ============================================================ F: binding fingerprint tamper
def test_f_binding_allocation_tamper_with_outer_digest_still_blocks():
    b = _binding()
    tampered = copy.deepcopy(b)
    tampered["allocation_intent_fingerprint"] = "f" * 64
    tampered["binding_digest"] = pib.canonical_binding_digest(tampered)
    ok, reasons = pib._binding_is_sealed(
        tampered, b["protected_position_snapshot_fingerprint"], b["protected_position_snapshot_digest"])
    assert ok is False and "binding_fingerprint_mismatch" in reasons


# ============================================================ G: cross-pilot replay
def test_g_cross_pilot_binding_blocks():
    snap = _snapshot(pilot_id=PILOT)
    b = pib.build_day1_protected_binding(
        pilot_id="BYBIT_DEMO_PILOT_7D_202607_V9", day1_date=DAY1,
        day1_allocation_artifact=_alloc("BYBIT_DEMO_PILOT_7D_202607_V9", DAY1), snapshot_artifact=snap)
    assert b["verdict"] == pib.BINDING_BLOCKED
    assert "binding_pilot_id_mismatch" in b["blockers"]


# ============================================================ H: cross-date replay
def test_h_cross_date_binding_blocks():
    snap = _snapshot(day1_date=DAY1)
    b = pib.build_day1_protected_binding(
        pilot_id=PILOT, day1_date="2026-07-06",
        day1_allocation_artifact=_alloc(PILOT, "2026-07-06"), snapshot_artifact=snap)
    assert b["verdict"] == pib.BINDING_BLOCKED
    assert "binding_day1_date_mismatch" in b["blockers"]


# ============================================================ I: missing audit evidence
def test_i_missing_entry_price_blocks():
    p = _edu()
    del p["entry_price"]
    art = _snapshot(positions=[p])
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("protected_position_audit_incomplete" in b and "entry_price" in b for b in art["blockers"])


def test_i_missing_leverage_blocks():
    p = _edu()
    del p["leverage"]
    art = _snapshot(positions=[p])
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("protected_position_audit_incomplete" in b and "leverage" in b for b in art["blockers"])


def test_i_missing_account_mode_blocks():
    art = _snapshot(account=_account(account_mode=""))
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert "account_evidence_incomplete:account_mode" in art["blockers"]


# ============================================================ J: raw SHA is not a binding
def test_j_raw_sha_allocation_does_not_complete():
    fake = {"pilot_id": PILOT, "date": DAY1, "strategy_capital_base_usd": "10000",
            "allocation_intent_fingerprint": "a" * 64, "payload_fingerprint": "a" * 64,
            "order_payloads": []}   # no real payloads -> recompute cannot match
    b = _binding(allocation=fake)
    assert b["verdict"] == pib.BINDING_BLOCKED
    assert any("allocation_" in x for x in b["blockers"])


# ============================================================ K: valid sealed allocation -> COMPLETE
def test_k_valid_allocation_artifact_binding_complete():
    snap = _snapshot()
    b = _binding(snap)
    assert b["verdict"] == pib.BINDING_COMPLETE and b["execution_ready"] is True
    assert pib._HEX64_RE.match(b["allocation_intent_fingerprint"])
    assert pib._SHA256_RE.match(b["binding_fingerprint"])
    assert b["protected_position_snapshot_fingerprint"] == snap["protected_position_snapshot_fingerprint"]
    # self-recompute holds
    ok, reasons = pib._binding_is_sealed(
        b, snap["protected_position_snapshot_fingerprint"], snap["protected_position_snapshot_digest"])
    assert ok is True and reasons == []


# ============================================================ continuity
def test_continuity_pass_and_separate_counts():
    c = _continuity(post_positions=[_edu(), _pos(STRATEGY[0], "Buy", "0.5", 0)])
    assert c["protected_position_identity_continuity"] == "PASS"
    assert c["strategy_position_count"] == 1 and c["strategy_positions_present"] == [STRATEGY[0]]
    assert c["protected_position_count"] == 1 and c["protected_positions_present"] == ["EDUUSDT"]
    assert pib._SHA256_RE.match(c["post_fill_continuity_fingerprint"])


@pytest.mark.parametrize("over,code", [
    ({"side": "Buy"}, "protected_position_side_changed"),
    ({"qty": "1000"}, "protected_position_qty_changed"),
])
def test_continuity_blocks_on_identity_change(over, code):
    c = _continuity(post_positions=[_edu(**over)])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert any(code in b for b in c["blockers"])
    assert c["post_fill_continuity_fingerprint"] == ""


def test_continuity_blocks_on_position_idx_change():
    # a different position_idx is a different composite key -> sealed one missing + an extra one
    c = _continuity(post_positions=[_edu(position_idx=1)])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert any("protected_position_missing:EDUUSDT:2" in b for b in c["blockers"])


def test_continuity_blocks_on_extra_unauthorized_symbol():
    c = _continuity(post_positions=[_edu(), _pos("RANDUSDT", "Buy", "5", 0)])
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert "unauthorized_protected_position:RANDUSDT:0" in c["blockers"]


def test_continuity_network_mutation_blocks():
    c = _continuity(components=_components(_ctr(mut=1)))
    assert c["protected_position_identity_continuity"] == pib.CONTINUITY_BLOCKED
    assert any("private_mutating_requests_detected" in b for b in c["blockers"])


# ============================================================ retired pilot
def test_retired_pilot_cannot_bootstrap():
    art = _snapshot(pilot_id=RETIRED)
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("retired_pilot_cannot_bootstrap" in b for b in art["blockers"])


def test_retired_pilot_cannot_be_repaired_via_binding():
    good = _snapshot()
    b = pib.build_day1_protected_binding(
        pilot_id=RETIRED, day1_date="2026-06-30",
        day1_allocation_artifact=_alloc(RETIRED, "2026-06-30"), snapshot_artifact=good)
    assert b["verdict"] == pib.BINDING_BLOCKED
    assert any("retired_pilot_cannot_be_repaired" in x for x in b["blockers"])


# ============================================================ chain verifier + network + offline
def test_chain_verifier_accepts_valid_chain():
    snap, b, c = _snapshot(), None, None
    b = _binding(snap)
    c = _continuity(snap, b)
    cur = {("EDUUSDT", 2): {"symbol": "EDUUSDT", "side": "short", "qty": "1234", "position_idx": 2}}
    ok, reasons = pib.verify_day1_protected_identity_chain(
        pilot_id=PILOT, day1_date=DAY1, snapshot=snap, binding=b, continuity=c,
        current_protected_identities=cur, day1_allocation_intent=_alloc())
    assert ok is True and reasons == []


def test_chain_verifier_rejects_current_identity_mismatch():
    snap = _snapshot()
    b = _binding(snap)
    c = _continuity(snap, b)
    cur = {("EDUUSDT", 2): {"symbol": "EDUUSDT", "side": "short", "qty": "1", "position_idx": 2}}
    ok, reasons = pib.verify_day1_protected_identity_chain(
        pilot_id=PILOT, day1_date=DAY1, snapshot=snap, binding=b, continuity=c,
        current_protected_identities=cur)
    assert ok is False and any("current_protected_identity_mismatch" in r for r in reasons)


def test_snapshot_network_mutation_and_missing_counter_block():
    assert _snapshot(components=_components(_ctr(mut=1)))["verdict"] == pib.SNAPSHOT_BLOCKED
    assert _snapshot(components={"protected_position_collector": None})["verdict"] == pib.SNAPSHOT_BLOCKED


def test_pagination_incomplete_blocks():
    art = _snapshot(provenance=_prov([_edu()], reason="max_page_cap_exceeded"))
    assert art["verdict"] == pib.SNAPSHOT_BLOCKED
    assert any("pagination_incomplete" in b for b in art["blockers"])


# ============================================================ P: fully offline
def test_p_pure_core_is_offline(monkeypatch):
    import socket

    def _boom(*a, **k):
        raise AssertionError("network access attempted by pure core")

    monkeypatch.setattr(socket, "socket", _boom)
    snap = _snapshot()
    b = _binding(snap)
    _continuity(snap, b)
    assert snap["verdict"] == pib.SNAPSHOT_READY


# ============================================================ CLI
def test_cli_default_does_nothing(capsys):
    rc = cli.main([])
    out = json.loads(capsys.readouterr().out)
    assert out["blockers"] == ["no_mode_selected"] and rc == cli.EXIT_INVALID


def test_cli_network_not_authorized_blocks(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    rc = cli.main(["--capture-pre-day1-protected-snapshot", "--pilot-id", PILOT,
                   "--day1-date", DAY1, "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert "protected_snapshot_network_not_authorized" in data["blockers"]
    assert rc == cli.EXIT_BLOCKED and not out_path.exists()


def test_cli_refuses_overwrite(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    out_path.write_text("{}", encoding="utf-8")
    rc = cli.main(["--capture-pre-day1-protected-snapshot", "--pilot-id", PILOT,
                   "--day1-date", DAY1, "--artifact-output-json", str(out_path)])
    data = json.loads(capsys.readouterr().out)
    assert "artifact_output_exists_refuse_overwrite" in data["blockers"]
    assert rc == cli.EXIT_INVALID


def test_cli_capture_offline_provider_writes_artifact(tmp_path, capsys):
    out_path = tmp_path / "snap.json"
    provider = lambda: ([_edu()], _prov([_edu()]), _ctr(), _account())  # noqa: E731
    args = argparse.Namespace(pilot_id=PILOT, day1_date=DAY1,
                              artifact_output_json=str(out_path), allow_real_network=False,
                              capture_pre_day1_protected_snapshot=True)
    rc = cli.run_capture(args, snapshot_provider=provider)
    data = json.loads(capsys.readouterr().out)
    assert data["verdict"] == pib.SNAPSHOT_READY and rc == cli.EXIT_READY
    assert out_path.exists()
    on_disk = json.loads(out_path.read_text(encoding="utf-8"))
    assert on_disk["protected_position_snapshot_fingerprint"] == data["protected_position_snapshot_fingerprint"]
