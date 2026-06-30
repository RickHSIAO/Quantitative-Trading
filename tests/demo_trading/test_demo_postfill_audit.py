"""TASK: machine-readable post-fill audit verdict + fail-closed audit-gated Pilot advancement.

Pure offline tests. The audit cross-checks ONE batch identity across the durable artifacts and the
completely-paginated position evidence, and cross-validates the per-order identity SETS (execution
state vs journal vs sent ledger). A PASS is only emitted when every condition holds. Advancement
re-validates the FULL artifact (schema + canonical digest + every evidence section) -- a minimal
forged PASS JSON cannot advance -- and reports advanced_now / already_counted / refused distinctly.
It never sends an order, calls execute_daily_native, or issues an exchange/network request.
"""
from __future__ import annotations

import json

import pytest

from src import demo_strategy_native_postfill_audit as au
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
DATE = "2026-06-30"
FP = "a0796affaf8c6be6e08827962a7ebc7b87dd929884ee76e86ba92d328e4f22a2"
PROTECTED = ["ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"]
N = 50

_SOURCE_PATHS = {k: f"/abs/{k}" for k in au.REQUIRED_SOURCE_KEYS}


def _syms():
    return [f"S{i:02d}USDT" for i in range(N)]


def _sides():
    return ["Buy" if i < 25 else "Sell" for i in range(N)]


def _kw(**over):
    """Full kwargs for a PASS scenario; override individual keys to drive FAIL cases."""
    syms, sides = _syms(), _sides()
    payloads = [{"symbol": syms[i], "side": sides[i], "target_notional_usd": "200"}
                for i in range(N)]
    accepted = [{"identity": f"id{i}", "outcome": "RECONCILED", "final_status": "Filled"}
                for i in range(N)]
    intent = {"pilot_id": PILOT, "date": DATE, "payload_fingerprint": FP,
              "allocation_intent_fingerprint": FP, "order_payloads": payloads,
              "strategy_capital_base_usd": "10000"}
    state = {"pilot_id": PILOT, "date": DATE, "day_verdict": au.DAY_SUCCESS,
             "proposed_count": 50, "accepted_count": 50, "rejected_count": 0,
             "ambiguous_count": 0, "sender_call_count": 50, "order_post_count": 50,
             "accepted": accepted}
    summary = {"pilot_id": PILOT, "date": DATE, "payload_fingerprint": FP,
               "status": "DEMO_BATCH_DISPATCHED", "day_verdict": au.DAY_SUCCESS,
               "execute_daily_native_called": 1, "pilot_advanced": False,
               "live_trading_authorized": False, "blockers": [], "accepted_count": 50,
               "rejected_count": 0, "ambiguous_count": 0, "order_post_count": 50,
               "sender_call_count": 50, "authorized_target_gross_notional_usd": "10000",
               "executed_actual_gross_notional_usd": "9951.274676"}
    journal = ([{"event": "DAILY_EXECUTION_START"}]
               + [{"event": "ACTION_RECONCILED", "identity": f"id{i}"} for i in range(N)]
               + [{"event": "DAILY_EXECUTION_FINISHED"}])
    ledger = []
    for i in range(N):
        ledger += [{"identity": f"id{i}", "state": "ATTEMPTED"},
                   {"identity": f"id{i}", "state": "POST_RESPONSE_RECEIVED"},
                   {"identity": f"id{i}", "state": "RECONCILED"}]
    battempt = {"pilot_id": PILOT, "date": DATE, "allocation_intent_fingerprint": FP,
                "status": "DEMO_BATCH_DISPATCHED", "day_verdict": au.DAY_SUCCESS}
    positions = [{"symbol": syms[i], "side": sides[i], "size": "1"} for i in range(N)]
    positions += [{"symbol": "EDUUSDT", "side": "Sell", "size": "5"}]
    provenance = {"page_count": 3, "termination_reason": "empty_cursor",
                  "api_position_rows": 51, "nonzero_position_count": 51}
    counters = {"private_read_only_request_count": 4, "public_read_only_request_count": 0,
                "private_mutating_request_count": 0}
    kw = dict(
        pilot_id=PILOT, date=DATE, expected_fingerprint=FP,
        allocation_intent_artifact=intent, execution_summary=summary, execution_state=state,
        journal=journal, sent_ledger=ledger, batch_attempt=battempt,
        positions=positions, positions_provenance=provenance,
        protected_symbols=PROTECTED, protected_symbols_source="cf._HISTORICAL_PROTECTED_SYMBOLS",
        network_counters=counters, intent_recomputed_fingerprint=FP,
        intent_structurally_valid=True, source_paths=_SOURCE_PATHS)
    kw.update(over)
    return kw


def _verdict(**over):
    return au.evaluate_post_fill_audit(**_kw(**over))


def _pass_artifact():
    art = _verdict()
    assert art["verdict"] == au.POST_FILL_AUDIT_PASS, art["blockers"]
    return art


def _fail(over, fragment):
    art = au.evaluate_post_fill_audit(**_kw(**over))
    assert art["verdict"] == au.POST_FILL_AUDIT_FAIL
    assert any(fragment in b for b in art["blockers"]), (fragment, art["blockers"])


# ============================================================ audit evaluation

def test_full_evidence_passes_with_digest():
    art = _verdict()
    assert art["verdict"] == au.POST_FILL_AUDIT_PASS and art["blockers"] == []
    assert art["audit_digest"] == au.canonical_audit_digest(art)
    assert art["paginated_position_evidence"]["nonzero_position_count"] == 51
    assert art["paginated_position_evidence"]["total_buy"] == 25
    assert art["paginated_position_evidence"]["total_sell"] == 26
    assert art["allowed_preexisting_protected_symbols"] == ["EDUUSDT"]
    assert art["identity_set_checks"]["journal_identity_set_matches_execution"] is True
    assert art["identity_set_checks"]["ledger_identity_set_matches_execution"] is True


def test_pass_never_emitted_with_blockers():
    art = _verdict(network_counters={"private_read_only_request_count": 4,
                                     "private_mutating_request_count": 1})
    assert art["blockers"] and art["verdict"] == au.POST_FILL_AUDIT_FAIL


def test_proposed_not_50_fails():
    st = _kw()["execution_state"]; st["proposed_count"] = 49
    _fail({"execution_state": st}, "proposed_count_not_50")


def test_accepted_not_50_fails():
    st = _kw()["execution_state"]; st["accepted_count"] = 49
    _fail({"execution_state": st}, "accepted_count_not_50")


def test_rejected_gt_0_fails():
    st = _kw()["execution_state"]; st["rejected_count"] = 1
    _fail({"execution_state": st}, "rejected_count_not_0")


def test_ambiguous_gt_0_fails():
    st = _kw()["execution_state"]; st["ambiguous_count"] = 1
    _fail({"execution_state": st}, "ambiguous_count_not_0")


def test_filled_under_50_fails():
    st = _kw()["execution_state"]; st["accepted"][0]["final_status"] = "New"
    _fail({"execution_state": st}, "filled_final_status_not_50")


def test_accepted_outcome_not_reconciled_fails():
    st = _kw()["execution_state"]; st["accepted"][0]["outcome"] = "AMBIGUOUS"
    _fail({"execution_state": st}, "accepted_outcome_not_all_reconciled")


def test_empty_accepted_identity_fails():
    st = _kw()["execution_state"]; st["accepted"][0]["identity"] = ""
    _fail({"execution_state": st}, "execution_state_empty_accepted_identity")


def test_duplicate_execution_identity_fails():
    st = _kw()["execution_state"]
    st["accepted"][1]["identity"] = st["accepted"][0]["identity"]
    _fail({"execution_state": st}, "unique_execution_identities_not_50")


def test_journal_missing_one_reconciled_fails():
    j = [e for e in _kw()["journal"]
         if not (e.get("event") == "ACTION_RECONCILED" and e.get("identity") == "id0")]
    _fail({"journal": j}, "journal_reconciled_not_50")


def test_journal_duplicate_identity_fails():
    # 50 ACTION_RECONCILED events but one identity duplicated -> only 49 unique.
    j = _kw()["journal"]
    for e in j:
        if e.get("event") == "ACTION_RECONCILED" and e.get("identity") == "id1":
            e["identity"] = "id0"
    _fail({"journal": j}, "journal_unique_reconciled_identities_not_50")


def test_journal_identity_set_mismatch_fails():
    j = _kw()["journal"]
    for e in j:
        if e.get("event") == "ACTION_RECONCILED" and e.get("identity") == "id0":
            e["identity"] = "ghost"
    _fail({"journal": j}, "journal_identity_set_mismatch_execution")


def test_ledger_attempted_duplicate_identity_fails():
    led = _kw()["sent_ledger"]
    seen = 0
    for e in led:
        if e.get("state") == "ATTEMPTED" and e.get("identity") == "id1":
            e["identity"] = "id0"; seen += 1
    assert seen == 1
    _fail({"sent_ledger": led}, "ledger_attempted_unique_identities_not_50")


def test_ledger_post_response_duplicate_identity_fails():
    led = _kw()["sent_ledger"]
    for e in led:
        if e.get("state") == "POST_RESPONSE_RECEIVED" and e.get("identity") == "id1":
            e["identity"] = "id0"
    _fail({"sent_ledger": led}, "ledger_post_response_received_unique_identities_not_50")


def test_ledger_identity_set_mismatch_fails():
    led = _kw()["sent_ledger"]
    for e in led:
        if e.get("state") == "RECONCILED" and e.get("identity") == "id0":
            e["identity"] = "ghost"
    _fail({"sent_ledger": led}, "ledger_identity_set_mismatch_execution")


def test_batch_fingerprint_mismatch_fails():
    ba = _kw()["batch_attempt"]; ba["allocation_intent_fingerprint"] = "deadbeef"
    _fail({"batch_attempt": ba}, "batch_attempt_fingerprint_mismatch")


def test_batch_attempt_day_verdict_mismatch_fails():
    ba = _kw()["batch_attempt"]; ba["day_verdict"] = "REJECT_AMBIGUOUS_REQUIRES_RECONCILIATION"
    _fail({"batch_attempt": ba}, "batch_attempt_day_verdict_not_success")


def test_summary_status_mismatch_fails():
    su = _kw()["execution_summary"]; su["status"] = "DEMO_BATCH_AMBIGUOUS_FAIL_CLOSED"
    _fail({"execution_summary": su}, "execution_summary_status_not_dispatched")


def test_summary_pilot_advanced_true_fails():
    su = _kw()["execution_summary"]; su["pilot_advanced"] = True
    _fail({"execution_summary": su}, "execution_summary_pilot_advanced_not_false")


def test_summary_missing_field_fails():
    su = _kw()["execution_summary"]; del su["status"]
    _fail({"execution_summary": su}, "execution_summary_missing_field:status")


def test_missing_strategy_position_fails():
    pos = [p for p in _kw()["positions"] if p["symbol"] != "S00USDT"]
    _fail({"positions": pos}, "missing_strategy_symbols")


def test_strategy_side_mismatch_fails():
    pos = _kw()["positions"]; pos[0]["side"] = "Sell"   # S00USDT authorized Buy
    _fail({"positions": pos}, "strategy_side_mismatch")


def test_eduusdt_allowed_with_protected_evidence():
    art = _verdict()
    assert art["verdict"] == au.POST_FILL_AUDIT_PASS
    assert "EDUUSDT" in art["allowed_preexisting_protected_symbols"]


def test_eduusdt_without_protected_evidence_fails():
    no_edu = [s for s in PROTECTED if s != "EDUUSDT"]
    _fail({"protected_symbols": no_edu}, "unauthorized_unexpected_open_symbols")


def test_second_unexpected_symbol_fails():
    pos = _kw()["positions"] + [{"symbol": "RANDOMUSDT", "side": "Buy", "size": "1"}]
    _fail({"positions": pos}, "unauthorized_unexpected_open_symbols")


def test_duplicate_open_position_symbol_fails():
    pos = _kw()["positions"] + [{"symbol": "S00USDT", "side": "Buy", "size": "1"}]
    _fail({"positions": pos}, "duplicate_open_position_symbols")


def test_mutating_request_fails():
    _fail({"network_counters": {"private_read_only_request_count": 4,
                                "private_mutating_request_count": 2}},
          "private_mutating_requests_detected")


def test_incomplete_pagination_fails():
    prov = {"page_count": 1, "termination_reason": "max_page_cap_exceeded",
            "api_position_rows": 20, "nonzero_position_count": 20}
    _fail({"positions_provenance": prov}, "position_pagination_incomplete")


def test_intent_fingerprint_recompute_mismatch_fails():
    _fail({"intent_recomputed_fingerprint": "deadbeef"},
          "allocation_intent_recomputed_fingerprint_mismatch")


def test_execute_daily_native_called_not_one_fails():
    su = _kw()["execution_summary"]; su["execute_daily_native_called"] = 2
    _fail({"execution_summary": su}, "execute_daily_native_called_not_1")


def test_live_trading_authorized_true_fails():
    su = _kw()["execution_summary"]; su["live_trading_authorized"] = True
    _fail({"execution_summary": su}, "execution_summary_live_trading_authorized_not_false")


# ============================================================ advancement re-validation

def _running_pilot(output_root):
    rd.PilotStateStore(PILOT, output_root).write_state({
        "pilot_id": PILOT, "lifecycle_state": rd.RUNNING,
        "order_execution_authorized": True, "live_trading_authorized": False,
        "completed_successful_days": 0, "successful_dates": [],
        "target_successful_days": rd.TARGET_SUCCESSFUL_DAYS,
        "remaining_successful_days": rd.TARGET_SUCCESSFUL_DAYS, "event_count": 0,
    })


def _advance(art, root, **over):
    kw = dict(audit_artifact=art, pilot_id=PILOT, date=DATE, expected_fingerprint=FP,
              output_root=root)
    kw.update(over)
    return au.gate_and_advance_pilot(**kw)


def test_pass_audit_first_advance_reports_advanced_now(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    res = _advance(_pass_artifact(), root)
    assert res["advanced_now"] is True and res["already_counted"] is False
    assert res["refused"] is False and res["completed_successful_days"] == 1
    st = rd.PilotStateStore(PILOT, root).read_state()
    assert st["completed_successful_days"] == 1 and st["remaining_successful_days"] == 6
    assert st["lifecycle_state"] == rd.RUNNING and st["target_successful_days"] == 7
    assert st["successful_dates"] == [DATE]


def test_duplicate_advance_reports_already_counted_not_advanced_now(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    art = _pass_artifact()
    r1 = _advance(art, root)
    r2 = _advance(art, root)
    assert r1["advanced_now"] is True
    assert r2["advanced_now"] is False and r2["already_counted"] is True and r2["refused"] is False
    st = rd.PilotStateStore(PILOT, root).read_state()
    assert st["completed_successful_days"] == 1 and st["successful_dates"] == [DATE]


def test_minimal_forged_pass_json_refused(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    forged = {"verdict": au.POST_FILL_AUDIT_PASS, "pilot_id": PILOT, "date": DATE,
              "allocation_intent_fingerprint": FP, "blockers": []}
    res = _advance(forged, root)
    assert res["refused"] is True and res["advanced_now"] is False
    assert "audit_digest_missing" in res["refusal_reasons"]
    assert rd.PilotStateStore(PILOT, root).read_state()["completed_successful_days"] == 0


def test_missing_schema_version_refused(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    art = _pass_artifact(); del art["schema_version"]
    res = _advance(art, root)
    assert res["refused"] is True and "schema_version_invalid" in res["refusal_reasons"]


def test_wrong_environment_refused(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    art = _pass_artifact()
    art["environment"] = "BYBIT_LIVE"
    art["audit_digest"] = au.canonical_audit_digest(art)   # re-seal to isolate the env check
    res = _advance(art, root)
    assert res["refused"] is True and "environment_not_demo" in res["refusal_reasons"]


def test_digest_mismatch_refused(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    art = _pass_artifact()
    art["generated_at"] = "tampered-after-sealing"        # digest no longer matches
    res = _advance(art, root)
    assert res["refused"] is True and "audit_digest_mismatch" in res["refusal_reasons"]


def test_missing_evidence_section_refused(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    art = _pass_artifact()
    del art["identity_set_checks"]
    art["audit_digest"] = au.canonical_audit_digest(art)  # re-seal to isolate the missing section
    res = _advance(art, root)
    assert res["refused"] is True and "missing_section:identity_set_checks" in res["refusal_reasons"]


def test_incomplete_source_evidence_refused(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    art = _pass_artifact()
    art["source_paths"] = {k: "" for k in au.REQUIRED_SOURCE_KEYS}
    art["audit_digest"] = au.canonical_audit_digest(art)
    res = _advance(art, root)
    assert res["refused"] is True and "source_evidence_incomplete" in res["refusal_reasons"]


def test_fail_verdict_does_not_advance(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    fail = _verdict(network_counters={"private_read_only_request_count": 4,
                                      "private_mutating_request_count": 1})
    res = _advance(fail, root)
    assert res["refused"] is True
    assert rd.PilotStateStore(PILOT, root).read_state()["completed_successful_days"] == 0


def test_fingerprint_mismatch_does_not_advance(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    res = _advance(_pass_artifact(), root, expected_fingerprint="deadbeef")
    assert res["refused"] is True and "fingerprint_mismatch" in res["refusal_reasons"]
    assert rd.PilotStateStore(PILOT, root).read_state()["completed_successful_days"] == 0


def test_pilot_id_mismatch_does_not_advance(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    res = _advance(_pass_artifact(), root, pilot_id="OTHER_PILOT")
    assert res["refused"] is True and "pilot_id_mismatch" in res["refusal_reasons"]


def test_date_mismatch_does_not_advance(tmp_path):
    root = str(tmp_path / "out"); _running_pilot(root)
    res = _advance(_pass_artifact(), root, date="2026-07-01")
    assert res["refused"] is True and "date_mismatch" in res["refusal_reasons"]


def test_advance_never_calls_sender_execute_or_network(tmp_path, monkeypatch):
    # If the advancement stage tries to initialize/call a sender, execute_daily_native, or open a
    # network socket, these patched stand-ins raise and the test fails immediately.
    import urllib.request

    def _boom(*a, **k):
        raise AssertionError("advancement must not call sender / execute / network")

    monkeypatch.setattr(nx, "execute_daily_native", _boom)
    monkeypatch.setattr(urllib.request, "urlopen", _boom)
    root = str(tmp_path / "out"); _running_pilot(root)
    res = _advance(_pass_artifact(), root)        # uses the REAL advance_successful_day
    assert res["advanced_now"] is True
    assert rd.PilotStateStore(PILOT, root).read_state()["completed_successful_days"] == 1


def test_advance_makes_no_exchange_mutating_request(tmp_path, monkeypatch):
    import urllib.request
    monkeypatch.setattr(urllib.request, "urlopen",
                        lambda *a, **k: (_ for _ in ()).throw(AssertionError("no network")))
    root = str(tmp_path / "out"); _running_pilot(root)
    res = _advance(_pass_artifact(), root)
    assert res["advanced_now"] is True and res["refused"] is False
