"""TASK: two-mode post-fill audit runner wiring (offline).

Stage 1 (--run-postfill-audit) is read-only: it writes the audit artifact and must NOT create or
mutate Pilot state or call any sender. Stage 2 (--advance-after-audit) advances the Pilot only from
a completed PASS artifact, idempotently. Position evidence is injected (no real network); the
allocation-intent fingerprint is recomputed through the REAL runner verification.
"""
from __future__ import annotations

import importlib.util
import json
import os

import pytest

from src import demo_strategy_native_postfill_audit as au
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))


def _load(name, rel):
    spec = importlib.util.spec_from_file_location(name, os.path.join(_ROOT, rel))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


crun = _load("crun_pfa_test", "scripts/run_demo_strategy_pilot_native_daily.py")
pfa = _load("pfa_runner_test", "scripts/run_demo_pilot_postfill_audit.py")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
DATE = "2026-06-30"
N = 50


def _intent_artifact():
    syms = [f"S{i:02d}USDT" for i in range(N)]
    sides = ["Buy" if i < 25 else "Sell" for i in range(N)]
    allocs = [{"symbol": syms[i], "side": sides[i], "target_notional_usd": "200"}
              for i in range(N)]
    fp = crun.allocation_intent_fingerprint(allocs, pilot_id=PILOT, date=DATE,
                                            strategy_capital_base_usd="10000")
    payloads = [{"symbol": syms[i], "side": sides[i], "target_notional_usd": "200",
                 "qty": "2", "order_link_id": f"L{i}"} for i in range(N)]
    art = {"verdict": nx.BATCH_PREP_PREPARED, "pilot_id": PILOT, "date": DATE,
           "order_payloads": payloads, "strategy_capital_base_usd": "10000",
           "payload_fingerprint": fp, "allocation_intent_fingerprint": fp,
           "expected_batch_authorization_token":
               crun.expected_batch_authorization_token(DATE, fp)}
    return art, fp, syms, sides


def _write_artifacts(tmp_path):
    art, fp, syms, sides = _intent_artifact()
    accepted = [{"identity": f"id{i}", "outcome": "RECONCILED", "final_status": "Filled"}
                for i in range(N)]
    state = {"pilot_id": PILOT, "date": DATE, "day_verdict": nx.DAY_SUCCESS,
             "proposed_count": 50, "accepted_count": 50, "rejected_count": 0,
             "ambiguous_count": 0, "sender_call_count": 50, "order_post_count": 50,
             "accepted": accepted}
    summary = {"pilot_id": PILOT, "date": DATE, "payload_fingerprint": fp,
               "status": "DEMO_BATCH_DISPATCHED", "day_verdict": nx.DAY_SUCCESS,
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
    battempt = {"pilot_id": PILOT, "date": DATE, "allocation_intent_fingerprint": fp,
                "status": "DEMO_BATCH_DISPATCHED", "day_verdict": nx.DAY_SUCCESS}

    d = tmp_path
    paths = {}
    for name, obj in [("intent", art), ("summary", summary), ("state", state),
                      ("battempt", battempt)]:
        p = d / f"{name}.json"
        p.write_text(json.dumps(obj), encoding="utf-8")
        paths[name] = str(p)
    jpath = d / "journal.jsonl"
    jpath.write_text("\n".join(json.dumps(e) for e in journal), encoding="utf-8")
    lpath = d / "ledger.jsonl"
    lpath.write_text("\n".join(json.dumps(e) for e in ledger), encoding="utf-8")
    paths["journal"] = str(jpath)
    paths["ledger"] = str(lpath)

    positions = [{"symbol": syms[i], "side": sides[i], "size": "1"} for i in range(N)]
    positions += [{"symbol": "EDUUSDT", "side": "Sell", "size": "5"}]
    provider = lambda: (positions, {"page_count": 3, "termination_reason": "empty_cursor",
                                    "api_position_rows": 51, "nonzero_position_count": 51},
                        {"private_read_only_request_count": 3,
                         "public_read_only_request_count": 0,
                         "private_mutating_request_count": 0})
    return paths, fp, provider


def _audit_args(tmp_path, fp, out_root):
    return pfa.build_parser().parse_args([
        "--run-postfill-audit", "--pilot-id", PILOT, "--date", DATE,
        "--allocation-intent-fingerprint", fp, "--output-root", out_root,
        "--audit-output-json", str(tmp_path / "post_fill_audit.json")])


def _set_args(args, paths):
    args.allocation_intent_json = paths["intent"]
    args.execution_summary_json = paths["summary"]
    args.execution_state_json = paths["state"]
    args.execution_journal_jsonl = paths["journal"]
    args.sent_ledger_jsonl = paths["ledger"]
    args.batch_attempt_json = paths["battempt"]


def test_audit_mode_writes_pass_artifact_without_touching_pilot(tmp_path, capsys):
    out_root = str(tmp_path / "out")
    paths, fp, provider = _write_artifacts(tmp_path)
    args = _audit_args(tmp_path, fp, out_root)
    _set_args(args, paths)

    rc = pfa.run_postfill_audit(args, position_provider=provider)
    assert rc == pfa.EXIT_PASS
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == au.POST_FILL_AUDIT_PASS
    assert out["allocation_intent_fingerprint"] == fp
    # Atomic artifact written and parseable.
    written = json.loads((tmp_path / "post_fill_audit.json").read_text(encoding="utf-8"))
    assert written["verdict"] == au.POST_FILL_AUDIT_PASS
    # Stage 1 must NOT create or advance Pilot state.
    assert rd.PilotStateStore(PILOT, out_root).read_state() is None


def test_audit_mode_rerun_replaces_artifact_atomically(tmp_path, capsys):
    out_root = str(tmp_path / "out")
    paths, fp, provider = _write_artifacts(tmp_path)
    args = _audit_args(tmp_path, fp, out_root)
    _set_args(args, paths)
    pfa.run_postfill_audit(args, position_provider=provider)
    capsys.readouterr()
    pfa.run_postfill_audit(args, position_provider=provider)   # safe re-run
    out2 = json.loads(capsys.readouterr().out)
    assert out2["verdict"] == au.POST_FILL_AUDIT_PASS
    # Exactly one canonical artifact, no leftover .tmp.
    assert (tmp_path / "post_fill_audit.json").exists()
    assert not (tmp_path / "post_fill_audit.json.tmp").exists()


def test_audit_then_advance_two_stage_idempotent(tmp_path, capsys):
    out_root = str(tmp_path / "out")
    rd.PilotStateStore(PILOT, out_root).write_state({
        "pilot_id": PILOT, "lifecycle_state": rd.RUNNING,
        "order_execution_authorized": True, "live_trading_authorized": False,
        "completed_successful_days": 0, "successful_dates": [],
        "target_successful_days": rd.TARGET_SUCCESSFUL_DAYS,
        "remaining_successful_days": rd.TARGET_SUCCESSFUL_DAYS, "event_count": 0})
    paths, fp, provider = _write_artifacts(tmp_path)
    audit_args = _audit_args(tmp_path, fp, out_root)
    _set_args(audit_args, paths)
    pfa.run_postfill_audit(audit_args, position_provider=provider)
    capsys.readouterr()

    adv_args = pfa.build_parser().parse_args([
        "--advance-after-audit", "--pilot-id", PILOT, "--date", DATE,
        "--allocation-intent-fingerprint", fp, "--output-root", out_root,
        "--audit-artifact-json", str(tmp_path / "post_fill_audit.json")])
    rc1 = pfa.advance_after_audit(adv_args)
    assert rc1 == pfa.EXIT_PASS
    st1 = rd.PilotStateStore(PILOT, out_root).read_state()
    assert st1["completed_successful_days"] == 1 and st1["remaining_successful_days"] == 6
    capsys.readouterr()
    # Idempotent second advance.
    pfa.advance_after_audit(adv_args)
    st2 = rd.PilotStateStore(PILOT, out_root).read_state()
    assert st2["completed_successful_days"] == 1 and st2["successful_dates"] == [DATE]


def test_advance_refused_when_audit_failed(tmp_path, capsys):
    out_root = str(tmp_path / "out")
    rd.PilotStateStore(PILOT, out_root).write_state({
        "pilot_id": PILOT, "lifecycle_state": rd.RUNNING,
        "order_execution_authorized": True, "live_trading_authorized": False,
        "completed_successful_days": 0, "successful_dates": [],
        "target_successful_days": rd.TARGET_SUCCESSFUL_DAYS,
        "remaining_successful_days": rd.TARGET_SUCCESSFUL_DAYS, "event_count": 0})
    fail_art = {"verdict": au.POST_FILL_AUDIT_FAIL, "pilot_id": PILOT, "date": DATE,
                "allocation_intent_fingerprint": "fp", "blockers": ["x"]}
    apath = tmp_path / "fail_audit.json"
    apath.write_text(json.dumps(fail_art), encoding="utf-8")
    adv_args = pfa.build_parser().parse_args([
        "--advance-after-audit", "--pilot-id", PILOT, "--date", DATE,
        "--allocation-intent-fingerprint", "fp", "--output-root", out_root,
        "--audit-artifact-json", str(apath)])
    rc = pfa.advance_after_audit(adv_args)
    assert rc == pfa.EXIT_FAIL
    assert rd.PilotStateStore(PILOT, out_root).read_state()["completed_successful_days"] == 0
