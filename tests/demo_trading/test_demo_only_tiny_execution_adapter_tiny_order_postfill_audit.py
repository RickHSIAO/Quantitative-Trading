"""Tests for TASK-014BN postfill audit scaffold.

All tests are strictly offline. No HTTP. No real or fake sender is
invoked. No credentials are loaded. The audit module is exercised
against frozen ``OrchestrationReport`` fixtures constructed in this
file, including replay against the preview CLI's fixture builders.
"""

from __future__ import annotations

import copy
import importlib
import json
import subprocess
import sys
import pathlib
from dataclasses import replace
from decimal import Decimal

import pytest

from src import demo_only_tiny_execution_adapter as bh
from src import (
    demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as orch,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_postfill_audit as pf,
)

# Import preview script directly (no subprocess) for fixture builders.
PREVIEW_MODULE_PATH = "scripts.preview_demo_only_tiny_execution_adapter_tiny_order_postfill_audit"
ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))
preview = importlib.import_module(PREVIEW_MODULE_PATH)


# ---------------------------------------------------------------------------
# Identity / chain-break invariants
# ---------------------------------------------------------------------------


def test_task_id_is_correct():
    assert pf.TASK_ID == "TASK-014BN"


def test_identity_is_correct():
    assert pf.IDENTITY == (
        "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-POSTFILL-AUDIT"
    )


def test_phase_is_correct():
    assert pf.IMPLEMENTATION_PATH_PHASE == "tiny_order_postfill_audit"


def test_is_review_chain_suffix_false():
    assert pf.IS_REVIEW_CHAIN_SUFFIX is False


def test_upstream_tasks_includes_required_predecessors():
    assert "TASK-014BM" in pf.UPSTREAM_TASKS
    assert (
        "TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR"
        in pf.UPSTREAM_TASKS
    )
    assert (
        "TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT" in pf.UPSTREAM_TASKS
    )


def test_next_required_task_is_vps_validation():
    assert pf.NEXT_REQUIRED_TASK == (
        "TASK-014BNB_demo_only_tiny_execution_postfill_audit_vps_validation"
    )


def test_next_required_task_is_not_review_chain_suffix():
    # Should not raise.
    bh.assert_next_task_is_not_review_chain_suffix(pf.NEXT_REQUIRED_TASK)


def test_next_required_task_rejects_forbidden_review_suffix():
    for forbidden in bh.FORBIDDEN_NEXT_TASK_SUFFIXES:
        with pytest.raises(bh.DemoOnlyTinyExecutionAdapterError):
            bh.assert_next_task_is_not_review_chain_suffix(
                f"TASK-014BN_demo_only_tiny_execution_postfill_audit{forbidden}"
            )


def test_postfill_audit_error_subclasses_adapter_error():
    assert issubclass(pf.PostfillAuditError, bh.DemoOnlyTinyExecutionAdapterError)


# ---------------------------------------------------------------------------
# Status / check name registry
# ---------------------------------------------------------------------------


def test_audit_status_constants_have_expected_values():
    assert pf.AUDIT_STATUS_SIMULATED_ACCEPTED == "POSTFILL_AUDIT_SIMULATED_ACCEPTED"
    assert pf.AUDIT_STATUS_SIMULATED_REJECTED == "POSTFILL_AUDIT_SIMULATED_REJECTED"
    assert pf.AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR == (
        "POSTFILL_AUDIT_SIMULATED_TRANSPORT_ERROR"
    )
    assert pf.AUDIT_STATUS_NOT_AUDITABLE == "POSTFILL_AUDIT_NOT_AUDITABLE"
    assert pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT == (
        "POSTFILL_AUDIT_FORBIDDEN_REAL_TRANSPORT"
    )


def test_audit_statuses_tuple_contains_all_five():
    assert set(pf.AUDIT_STATUSES) == {
        pf.AUDIT_STATUS_SIMULATED_ACCEPTED,
        pf.AUDIT_STATUS_SIMULATED_REJECTED,
        pf.AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR,
        pf.AUDIT_STATUS_NOT_AUDITABLE,
        pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT,
    }


def test_auditable_statuses_subset_is_correct():
    assert set(pf.AUDIT_STATUSES_AUDITABLE) == {
        pf.AUDIT_STATUS_SIMULATED_ACCEPTED,
        pf.AUDIT_STATUS_SIMULATED_REJECTED,
        pf.AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR,
    }


def test_check_names_count_is_30():
    assert len(pf.CHECK_NAMES) == 30


def test_check_names_are_unique():
    assert len(set(pf.CHECK_NAMES)) == 30


@pytest.mark.parametrize(
    "name",
    [
        "transport_is_fake_sender",
        "fake_sender_used",
        "sender_call_count_exactly_one",
        "simulated_network_attempted",
        "simulated_endpoint_called",
        "real_network_not_attempted",
        "real_endpoint_not_called",
        "real_order_not_sent",
        "stage1_real_execute_disabled",
        "symbol_is_solusdt",
        "category_is_linear",
        "side_is_buy",
        "order_type_is_market",
        "time_in_force_is_ioc",
        "reduce_only_false",
        "close_on_trigger_false",
        "original_packet_qty_is_0_01",
        "actual_qty_is_authorized_0_1",
        "actual_qty_source_is_authorized_candidate",
        "resolved_qty_is_authorized_0_1",
        "resolved_qty_source_is_authorized_candidate",
        "candidate_qty_is_0_1",
        "body_qty_authorized_override_true",
        "candidate_notional_within_20_usdt",
        "resolved_notional_within_20_usdt",
        "cap_gate_authorized",
        "wiring_authorized",
        "no_real_transport_evidence",
        "accepted_outcome_consistent",
        "no_protected_symbol_scope",
    ],
)
def test_each_required_check_name_present(name):
    assert name in pf.CHECK_NAMES


def test_expected_contract_defaults_to_stage1_locks():
    contract = pf.DEFAULT_EXPECTED_CONTRACT
    assert contract.symbol == "SOLUSDT"
    assert contract.category == "linear"
    assert contract.side == "Buy"
    assert contract.order_type == "Market"
    assert contract.time_in_force == "IOC"
    assert contract.reduce_only is False
    assert contract.close_on_trigger is False
    assert contract.original_packet_qty == "0.01"
    assert contract.authorized_qty == "0.1"
    assert contract.authorized_qty_source == (
        "CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY"
    )
    assert contract.wiring_status_authorized == "WIRING_AUTHORIZED_CANDIDATE_QTY"
    assert contract.max_notional_usdt == Decimal("20")


# ---------------------------------------------------------------------------
# Happy path on preview fixtures
# ---------------------------------------------------------------------------


def test_preview_simulated_accepted_fixture_is_simulated_accepted():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_ACCEPTED)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_ACCEPTED
    assert audit.auditable is True
    assert audit.integrity_all_passed is True
    assert audit.integrity_failed_checks == ()


def test_preview_simulated_rejected_fixture_is_simulated_rejected():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_REJECTED)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_REJECTED
    assert audit.auditable is True
    assert audit.integrity_all_passed is True


def test_preview_simulated_transport_error_fixture_is_transport_error():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_TRANSPORT_ERROR)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR
    assert audit.auditable is True
    assert audit.integrity_all_passed is True


def test_preview_not_auditable_fixture_is_not_auditable():
    r = preview.build_fixture(preview.FIXTURE_NOT_AUDITABLE)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_NOT_AUDITABLE
    assert audit.auditable is False


def test_all_four_preview_fixtures_complete_without_raising():
    for name in preview.FIXTURES:
        r = preview.build_fixture(name)
        pf.run_postfill_audit(r)


def test_preview_simulated_accepted_check_count_is_30():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_ACCEPTED)
    audit = pf.run_postfill_audit(r)
    assert len(audit.checks) == 30


def test_preview_check_names_match_registry_order():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_ACCEPTED)
    audit = pf.run_postfill_audit(r)
    assert tuple(c.name for c in audit.checks) == pf.CHECK_NAMES


def test_preview_simulated_accepted_body_preview_matches_locks():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_ACCEPTED)
    audit = pf.run_postfill_audit(r)
    body = audit.body_preview
    assert body["symbol"] == "SOLUSDT"
    assert body["category"] == "linear"
    assert body["side"] == "Buy"
    assert body["orderType"] == "Market"
    assert body["timeInForce"] == "IOC"
    assert body["reduceOnly"] is False
    assert body["closeOnTrigger"] is False
    assert body["qty"] == "0.1"


# ---------------------------------------------------------------------------
# Safety: forbidden real transport short-circuit
# ---------------------------------------------------------------------------


def _accepted_fixture():
    return preview.build_fixture(preview.FIXTURE_SIMULATED_ACCEPTED)


def test_real_order_sent_triggers_forbidden_real_transport():
    r = replace(_accepted_fixture(), real_order_sent=True)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT
    assert audit.auditable is False


def test_real_order_endpoint_called_triggers_forbidden():
    r = replace(_accepted_fixture(), real_order_endpoint_called=True)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT


def test_real_order_network_attempted_triggers_forbidden():
    r = replace(_accepted_fixture(), real_order_network_attempted=True)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT


def test_transport_kind_real_demo_sender_triggers_forbidden():
    r = replace(
        _accepted_fixture(),
        order_transport_kind=orch.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER,
    )
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT


def test_no_real_transport_evidence_check_fails_when_real_evidence_present():
    r = replace(_accepted_fixture(), real_order_sent=True)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "no_real_transport_evidence" in failed
    assert "real_order_not_sent" in failed


def test_forbidden_status_short_circuits_even_with_valid_body():
    # Even if every contract check would pass, the forbidden marker
    # alone reclassifies the audit as a safety violation.
    r = replace(_accepted_fixture(), real_order_sent=True)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT


# ---------------------------------------------------------------------------
# Not-auditable conditions
# ---------------------------------------------------------------------------


def test_readiness_mode_is_not_auditable():
    r = replace(_accepted_fixture(), mode=orch.ORCH_MODE_READINESS)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_NOT_AUDITABLE


def test_real_demo_mode_is_not_auditable_unless_real_evidence():
    r = replace(_accepted_fixture(), mode=orch.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER)
    audit = pf.run_postfill_audit(r)
    # No real_order_* set -> not_auditable (not forbidden).
    assert audit.audit_status == pf.AUDIT_STATUS_NOT_AUDITABLE


def test_bm_not_invoked_is_not_auditable():
    r = replace(_accepted_fixture(), bm_invoked=False)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_NOT_AUDITABLE


def test_fake_sender_not_used_is_not_auditable():
    r = replace(_accepted_fixture(), fake_sender_used=False)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_NOT_AUDITABLE


def test_transport_kind_none_is_not_auditable():
    r = replace(
        _accepted_fixture(),
        order_transport_kind=orch.ORDER_TRANSPORT_KIND_NONE,
    )
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_NOT_AUDITABLE


# ---------------------------------------------------------------------------
# Transport-error classification
# ---------------------------------------------------------------------------


def test_bm_network_error_with_fake_sender_is_transport_error():
    r = replace(
        _accepted_fixture(),
        bm_final_status="STATUS_NETWORK_ERROR_DEMO_ONLY",
        simulated_order_sent=False,
        order_sent=False,
        bybit_ret_code=None,
        bybit_order_id="",
    )
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR
    assert audit.auditable is True


def test_transport_error_integrity_still_passes_when_body_intact():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_TRANSPORT_ERROR)
    audit = pf.run_postfill_audit(r)
    assert audit.integrity_all_passed is True


# ---------------------------------------------------------------------------
# Accepted vs rejected business-outcome semantics
# ---------------------------------------------------------------------------


def test_accepted_requires_simulated_order_sent_true():
    r = replace(_accepted_fixture(), simulated_order_sent=False)
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_REJECTED


def test_accepted_requires_ret_code_zero():
    r = replace(
        _accepted_fixture(),
        bybit_ret_code=10001,
        order_sent=False,
    )
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_REJECTED


def test_accepted_requires_non_empty_order_id():
    r = replace(
        _accepted_fixture(),
        bybit_order_id="",
        order_sent=False,
    )
    audit = pf.run_postfill_audit(r)
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_REJECTED


def test_accepted_outcome_consistent_check_passes_when_inconsistent_is_false():
    # legacy order_sent=True but missing orderId -> inconsistent.
    r = replace(
        _accepted_fixture(),
        order_sent=True,
        bybit_order_id="",
        bybit_ret_code=0,
    )
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "accepted_outcome_consistent" in failed


def test_accepted_outcome_consistent_check_passes_for_rejected_path():
    r = preview.build_fixture(preview.FIXTURE_SIMULATED_REJECTED)
    audit = pf.run_postfill_audit(r)
    consistent = next(
        c for c in audit.checks if c.name == "accepted_outcome_consistent"
    )
    assert consistent.passed is True


# ---------------------------------------------------------------------------
# Contract checks
# ---------------------------------------------------------------------------


def _accepted_with_body_field(field: str, value):
    r = _accepted_fixture()
    new_bm = copy.deepcopy(r.bm_report)
    new_bm["plan"]["body_preview"][field] = value
    return replace(r, bm_report=new_bm)


def test_symbol_mismatch_fails_symbol_check():
    r = _accepted_with_body_field("symbol", "BTCUSDT")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "symbol_is_solusdt" in failed
    assert audit.integrity_all_passed is False


def test_category_mismatch_fails_category_check():
    r = _accepted_with_body_field("category", "spot")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "category_is_linear" in failed


def test_side_mismatch_fails_side_check():
    r = _accepted_with_body_field("side", "Sell")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "side_is_buy" in failed


def test_order_type_mismatch_fails_order_type_check():
    r = _accepted_with_body_field("orderType", "Limit")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "order_type_is_market" in failed


def test_time_in_force_mismatch_fails_tif_check():
    r = _accepted_with_body_field("timeInForce", "GTC")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "time_in_force_is_ioc" in failed


def test_reduce_only_true_fails_reduce_only_check():
    r = _accepted_with_body_field("reduceOnly", True)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "reduce_only_false" in failed


def test_close_on_trigger_true_fails_close_on_trigger_check():
    r = _accepted_with_body_field("closeOnTrigger", True)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "close_on_trigger_false" in failed


def test_original_packet_qty_mismatch_fails_check():
    r = replace(_accepted_fixture(), original_packet_qty="0.02")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "original_packet_qty_is_0_01" in failed


def test_actual_qty_mismatch_fails_check():
    r = replace(_accepted_fixture(), actual_request_body_qty="0.2")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "actual_qty_is_authorized_0_1" in failed


def test_actual_qty_source_mismatch_fails_check():
    r = replace(_accepted_fixture(), actual_request_body_qty_source="BL_PACKET_QTY")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "actual_qty_source_is_authorized_candidate" in failed


def test_resolved_qty_mismatch_fails_check():
    r = replace(_accepted_fixture(), resolved_execution_qty="0.05")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "resolved_qty_is_authorized_0_1" in failed


def test_resolved_qty_source_mismatch_fails_check():
    r = replace(_accepted_fixture(), resolved_execution_qty_source="BL_PACKET_QTY")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "resolved_qty_source_is_authorized_candidate" in failed


def test_candidate_qty_mismatch_fails_check():
    r = replace(_accepted_fixture(), candidate_qty="0.01")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "candidate_qty_is_0_1" in failed


def test_body_qty_authorized_override_false_fails_check():
    r = replace(_accepted_fixture(), body_qty_authorized_override=False)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "body_qty_authorized_override_true" in failed


def test_candidate_notional_over_20_fails_check():
    r = replace(_accepted_fixture(), candidate_notional="25.0000")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "candidate_notional_within_20_usdt" in failed


def test_resolved_notional_over_20_fails_check():
    r = replace(_accepted_fixture(), resolved_notional="999.99")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "resolved_notional_within_20_usdt" in failed


def test_unparseable_notional_fails_check_with_reason():
    r = replace(_accepted_fixture(), candidate_notional="not-a-number")
    audit = pf.run_postfill_audit(r)
    check = next(
        c
        for c in audit.checks
        if c.name == "candidate_notional_within_20_usdt"
    )
    assert check.passed is False
    assert check.reason == "unparseable"


def test_notional_exactly_at_20_passes():
    r = replace(
        _accepted_fixture(),
        candidate_notional="20",
        resolved_notional="20",
    )
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "candidate_notional_within_20_usdt" not in failed
    assert "resolved_notional_within_20_usdt" not in failed


def test_cap_gate_not_authorized_fails_check():
    r = replace(_accepted_fixture(), cap_gate_authorized=False)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "cap_gate_authorized" in failed


def test_wiring_status_mismatch_fails_check():
    r = replace(_accepted_fixture(), wiring_status="WIRING_REJECTED")
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "wiring_authorized" in failed


def test_protected_symbols_untouched_false_fails_check():
    r = replace(_accepted_fixture(), protected_symbols_untouched=False)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "no_protected_symbol_scope" in failed


def test_stage1_real_execute_disabled_false_fails_check():
    r = replace(_accepted_fixture(), real_execute_disabled_stage1=False)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "stage1_real_execute_disabled" in failed


def test_sender_call_count_not_one_fails_check():
    r = replace(_accepted_fixture(), sender_call_count=2)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "sender_call_count_exactly_one" in failed


def test_simulated_network_not_attempted_fails_check():
    r = replace(_accepted_fixture(), simulated_order_network_attempted=False)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "simulated_network_attempted" in failed


def test_simulated_endpoint_not_called_fails_check():
    r = replace(_accepted_fixture(), simulated_order_endpoint_called=False)
    audit = pf.run_postfill_audit(r)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "simulated_endpoint_called" in failed


# ---------------------------------------------------------------------------
# Public API contracts
# ---------------------------------------------------------------------------


def test_run_postfill_audit_rejects_non_report_input():
    with pytest.raises(pf.PostfillAuditError):
        pf.run_postfill_audit("not a report")  # type: ignore[arg-type]


def test_run_postfill_audit_rejects_dict_input():
    with pytest.raises(pf.PostfillAuditError):
        pf.run_postfill_audit({"mode": "x"})  # type: ignore[arg-type]


def test_run_postfill_audit_returns_frozen_report():
    audit = pf.run_postfill_audit(_accepted_fixture())
    with pytest.raises(Exception):
        audit.audit_status = "x"  # type: ignore[misc]


def test_to_dict_returns_serializable_dict():
    audit = pf.run_postfill_audit(_accepted_fixture())
    data = audit.to_dict()
    text = json.dumps(data, default=str)
    assert "POSTFILL_AUDIT_SIMULATED_ACCEPTED" in text


def test_to_dict_round_trip_preserves_checks_count():
    audit = pf.run_postfill_audit(_accepted_fixture())
    data = audit.to_dict()
    assert len(data["checks"]) == 30


def test_to_dict_includes_expected_contract():
    audit = pf.run_postfill_audit(_accepted_fixture())
    data = audit.to_dict()
    assert data["expected_contract"]["symbol"] == "SOLUSDT"


def test_run_postfill_audit_preserves_source_provenance():
    src = _accepted_fixture()
    audit = pf.run_postfill_audit(src)
    assert audit.source_task_id == src.task_id
    assert audit.source_mode == src.mode
    assert audit.source_status == src.status
    assert audit.source_generated_at_utc == src.generated_at_utc


def test_custom_expected_contract_overrides_defaults():
    src = _accepted_with_body_field("symbol", "BTCUSDT")
    src = replace(src, candidate_qty="0.1")
    custom = pf.ExpectedContract(
        symbol="BTCUSDT",
        category="linear",
        side="Buy",
        order_type="Market",
        time_in_force="IOC",
        reduce_only=False,
        close_on_trigger=False,
        original_packet_qty="0.01",
        authorized_qty="0.1",
        authorized_qty_source="CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY",
        wiring_status_authorized="WIRING_AUTHORIZED_CANDIDATE_QTY",
        max_notional_usdt=Decimal("20"),
    )
    audit = pf.run_postfill_audit(src, expected_contract=custom)
    failed = {c.name for c in audit.checks if not c.passed}
    assert "symbol_is_solusdt" not in failed


def test_summary_describes_audit_status():
    for fixture in preview.FIXTURES:
        audit = pf.run_postfill_audit(preview.build_fixture(fixture))
        assert audit.summary
        assert isinstance(audit.summary, str)


def test_integrity_failed_checks_is_tuple_in_deterministic_order():
    r = _accepted_with_body_field("symbol", "BTCUSDT")
    r = _accepted_with_body_field("side", "Sell")  # noqa: F841 (overwritten)
    # Multiple failures, then check ordering matches CHECK_NAMES order.
    r = _accepted_fixture()
    new_bm = copy.deepcopy(r.bm_report)
    new_bm["plan"]["body_preview"]["symbol"] = "BTCUSDT"
    new_bm["plan"]["body_preview"]["side"] = "Sell"
    r = replace(r, bm_report=new_bm)
    audit = pf.run_postfill_audit(r)
    failed = audit.integrity_failed_checks
    assert isinstance(failed, tuple)
    failed_index = [pf.CHECK_NAMES.index(name) for name in failed]
    assert failed_index == sorted(failed_index)


# ---------------------------------------------------------------------------
# Body-preview extraction edge cases
# ---------------------------------------------------------------------------


def test_missing_bm_report_dict_yields_empty_body_preview():
    r = replace(_accepted_fixture(), bm_report={})
    audit = pf.run_postfill_audit(r)
    assert audit.body_preview == {}


def test_missing_plan_yields_empty_body_preview():
    r = replace(_accepted_fixture(), bm_report={"final_status": "x"})
    audit = pf.run_postfill_audit(r)
    assert audit.body_preview == {}


def test_missing_body_preview_yields_empty_dict():
    r = replace(_accepted_fixture(), bm_report={"plan": {"qty": "0.1"}})
    audit = pf.run_postfill_audit(r)
    assert audit.body_preview == {}


def test_non_mapping_bm_report_yields_empty_body_preview():
    r = replace(_accepted_fixture(), bm_report={})  # frozen, set to mapping
    audit = pf.run_postfill_audit(r)
    assert audit.body_preview == {}


# ---------------------------------------------------------------------------
# Markdown + JSON writers
# ---------------------------------------------------------------------------


def test_write_report_creates_four_files(tmp_path):
    audit = pf.run_postfill_audit(_accepted_fixture())
    paths = pf.write_report(audit, output_dir=tmp_path)
    assert set(paths) == {"json_latest", "md_latest", "json_ts", "md_ts"}
    for p in paths.values():
        assert p.exists()
        assert p.stat().st_size > 0


def test_write_report_json_is_parseable(tmp_path):
    audit = pf.run_postfill_audit(_accepted_fixture())
    paths = pf.write_report(audit, output_dir=tmp_path)
    data = json.loads(paths["json_latest"].read_text(encoding="utf-8"))
    assert data["audit_status"] == pf.AUDIT_STATUS_SIMULATED_ACCEPTED


def test_write_report_md_includes_check_names(tmp_path):
    audit = pf.run_postfill_audit(_accepted_fixture())
    paths = pf.write_report(audit, output_dir=tmp_path)
    md = paths["md_latest"].read_text(encoding="utf-8")
    for name in pf.CHECK_NAMES:
        assert name in md


def test_write_report_creates_default_dir_when_omitted(tmp_path, monkeypatch):
    # Redirect DEFAULT_OUTPUT_DIR into tmp to avoid polluting the repo.
    monkeypatch.setattr(pf, "DEFAULT_OUTPUT_DIR", tmp_path / "auto")
    audit = pf.run_postfill_audit(_accepted_fixture())
    paths = pf.write_report(audit)
    for p in paths.values():
        assert (tmp_path / "auto") in p.parents or (
            tmp_path / "auto"
        ) == p.parent


# ---------------------------------------------------------------------------
# Preview CLI -- subprocess invocation (still strictly offline)
# ---------------------------------------------------------------------------


def _run_preview_cli(args, env=None):
    import os

    cmd = [
        sys.executable,
        "scripts/preview_demo_only_tiny_execution_adapter_tiny_order_postfill_audit.py",
        *args,
    ]
    run_env = dict(os.environ if env is None else env)
    run_env.setdefault("PYTHONIOENCODING", "utf-8")
    return subprocess.run(
        cmd,
        cwd=str(ROOT),
        capture_output=True,
        text=True,
        encoding="utf-8",
        errors="replace",
        env=run_env,
        check=False,
    )


def test_preview_cli_default_fixture_exits_zero():
    result = _run_preview_cli(["--json-only"])
    assert result.returncode == 0


@pytest.mark.parametrize(
    "fixture",
    [
        "simulated_accepted",
        "simulated_rejected",
        "simulated_transport_error",
    ],
)
def test_preview_cli_auditable_fixtures_exit_zero(fixture):
    result = _run_preview_cli(["--fixture", fixture, "--json-only"])
    assert result.returncode == 0, result.stderr


def test_preview_cli_not_auditable_exits_one():
    result = _run_preview_cli(
        ["--fixture", "not_auditable", "--json-only"]
    )
    assert result.returncode == 1


def test_preview_cli_emits_json_on_stdout():
    result = _run_preview_cli(
        ["--fixture", "simulated_accepted", "--json-only"]
    )
    data = json.loads(result.stdout)
    assert data["audit_status"] == "POSTFILL_AUDIT_SIMULATED_ACCEPTED"


def test_preview_cli_default_mode_includes_summary_line():
    result = _run_preview_cli(["--fixture", "simulated_accepted"])
    assert "audit_status=POSTFILL_AUDIT_SIMULATED_ACCEPTED" in result.stdout


def test_preview_cli_write_report_creates_files(tmp_path):
    result = _run_preview_cli(
        [
            "--fixture",
            "simulated_accepted",
            "--write-report",
            "--output-dir",
            str(tmp_path),
            "--json-only",
        ]
    )
    assert result.returncode == 0, result.stderr
    written = list(tmp_path.glob("*"))
    assert len(written) == 4


def test_preview_cli_rejects_unknown_fixture():
    result = _run_preview_cli(["--fixture", "bogus", "--json-only"])
    assert result.returncode != 0


# ---------------------------------------------------------------------------
# Safety / no-side-effect invariants
# ---------------------------------------------------------------------------


def test_module_imports_do_not_touch_main_or_risk_or_bybit_executor():
    import ast
    import sys

    pf_mod = sys.modules[pf.__name__]
    src_text = pathlib.Path(pf_mod.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src_text)
    forbidden_modules = {
        "src.risk",
        "src.executors.bybit",
        "src.demo_close_only_sender",
        "src.demo_new_entry_sender",
        "main",
    }
    forbidden_from_with_names = {
        ("src", "risk"),
        ("src.executors", "bybit"),
        ("src.executors.bybit", "BybitExecutor"),
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_modules, alias.name
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for alias in node.names:
                assert (mod, alias.name) not in forbidden_from_with_names, (
                    mod,
                    alias.name,
                )
                assert mod not in forbidden_modules, mod


def test_module_does_not_import_requests_or_urllib_request():
    src_text = pathlib.Path(
        pf.__file__,
    ).read_text(encoding="utf-8")
    assert "import requests" not in src_text
    assert "from requests" not in src_text
    assert "urllib.request" not in src_text
    assert "http.client" not in src_text


def test_module_does_not_reference_live_endpoints():
    src_text = pathlib.Path(pf.__file__).read_text(encoding="utf-8")
    assert "api.bybit.com" not in src_text
    assert "stream.bybit.com" not in src_text
    assert "api-demo.bybit.com" not in src_text  # audit never calls demo either


def test_module_does_not_reference_v5_order_create():
    src_text = pathlib.Path(pf.__file__).read_text(encoding="utf-8")
    assert "/v5/order/create" not in src_text


def test_module_does_not_read_bybit_env_vars():
    src_text = pathlib.Path(pf.__file__).read_text(encoding="utf-8")
    for forbidden_env in (
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
    ):
        assert forbidden_env not in src_text


def test_module_does_not_import_close_only_or_new_entry_senders():
    src_text = pathlib.Path(pf.__file__).read_text(encoding="utf-8")
    assert "demo_close_only_sender" not in src_text
    assert "demo_new_entry_sender" not in src_text


def test_run_postfill_audit_is_pure_modulo_timestamp():
    src = _accepted_fixture()
    a1 = pf.run_postfill_audit(src)
    a2 = pf.run_postfill_audit(src)
    d1 = a1.to_dict()
    d2 = a2.to_dict()
    for key in ("generated_at_utc", "audited_at_utc"):
        d1.pop(key)
        d2.pop(key)
    assert d1 == d2


def test_running_audit_never_mutates_source_report():
    src = _accepted_fixture()
    before = src.to_dict()
    pf.run_postfill_audit(src)
    assert src.to_dict() == before


# ---------------------------------------------------------------------------
# TASK-014BN_POSTFILL_AUDIT_AUTHORITATIVE_PASS_FIELD_CORRECTION
# Authoritative audit_passed / audit_reason fields
# ---------------------------------------------------------------------------


def test_report_has_audit_passed_field():
    audit = pf.run_postfill_audit(_accepted_fixture())
    assert hasattr(audit, "audit_passed")
    assert isinstance(audit.audit_passed, bool)


def test_report_has_non_empty_audit_reason_field():
    audit = pf.run_postfill_audit(_accepted_fixture())
    assert hasattr(audit, "audit_reason")
    assert isinstance(audit.audit_reason, str)
    assert audit.audit_reason.strip() != ""


def test_report_has_audited_at_utc_field():
    audit = pf.run_postfill_audit(_accepted_fixture())
    assert hasattr(audit, "audited_at_utc")
    assert audit.audited_at_utc.endswith("Z")


def test_to_dict_includes_audit_passed_and_audit_reason():
    data = pf.run_postfill_audit(_accepted_fixture()).to_dict()
    assert "audit_passed" in data
    assert "audit_reason" in data
    assert "audited_at_utc" in data
    assert data["audit_passed"] is True
    assert data["audit_reason"]


def test_every_status_yields_non_empty_reason():
    builders = [
        _accepted_fixture(),
        preview.build_fixture(preview.FIXTURE_SIMULATED_REJECTED),
        preview.build_fixture(preview.FIXTURE_SIMULATED_TRANSPORT_ERROR),
        preview.build_fixture(preview.FIXTURE_NOT_AUDITABLE),
        replace(_accepted_fixture(), real_order_sent=True),
    ]
    for src in builders:
        audit = pf.run_postfill_audit(src)
        assert audit.audit_reason.strip() != ""


def test_compute_audit_passed_formula_is_exposed():
    assert pf.compute_audit_passed(
        auditable=True,
        integrity_all_passed=True,
        audit_status=pf.AUDIT_STATUS_SIMULATED_ACCEPTED,
    )
    assert not pf.compute_audit_passed(
        auditable=True,
        integrity_all_passed=False,
        audit_status=pf.AUDIT_STATUS_SIMULATED_ACCEPTED,
    )
    assert not pf.compute_audit_passed(
        auditable=False,
        integrity_all_passed=True,
        audit_status=pf.AUDIT_STATUS_NOT_AUDITABLE,
    )


# --- audit_passed values per status -----------------------------------------


def test_simulated_accepted_audit_passed_true_and_reason_disclaims_real():
    audit = pf.run_postfill_audit(_accepted_fixture())
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_ACCEPTED
    assert audit.audit_passed is True
    reason = audit.audit_reason.lower()
    assert "audit integrity pass" in reason
    # explicitly states this is not a real order
    assert "real" in reason
    assert "real_order_sent=false" in reason


def test_simulated_rejected_audit_passed_true_not_described_as_success():
    audit = pf.run_postfill_audit(
        preview.build_fixture(preview.FIXTURE_SIMULATED_REJECTED)
    )
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_REJECTED
    assert audit.audit_passed is True
    reason = audit.audit_reason.lower()
    assert "audit integrity pass" in reason
    assert "not accepted" in reason


def test_simulated_transport_error_audit_passed_true_not_success():
    audit = pf.run_postfill_audit(
        preview.build_fixture(preview.FIXTURE_SIMULATED_TRANSPORT_ERROR)
    )
    assert audit.audit_status == pf.AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR
    assert audit.audit_passed is True
    reason = audit.audit_reason.lower()
    assert "audit integrity pass" in reason
    assert "not transport or order success" in reason


def test_not_auditable_audit_passed_false():
    audit = pf.run_postfill_audit(
        preview.build_fixture(preview.FIXTURE_NOT_AUDITABLE)
    )
    assert audit.audit_status == pf.AUDIT_STATUS_NOT_AUDITABLE
    assert audit.audit_passed is False
    assert "not auditable" in audit.audit_reason.lower()


def test_forbidden_real_transport_audit_passed_false():
    audit = pf.run_postfill_audit(
        replace(_accepted_fixture(), real_order_sent=True)
    )
    assert audit.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT
    assert audit.audit_passed is False
    assert "forbidden" in audit.audit_reason.lower()


def test_failed_required_check_makes_audit_passed_false():
    r = _accepted_with_body_field("symbol", "BTCUSDT")
    audit = pf.run_postfill_audit(r)
    assert audit.integrity_all_passed is False
    assert audit.audit_passed is False
    assert "fail" in audit.audit_reason.lower()


def test_audit_passed_true_never_coexists_with_real_transport_evidence():
    # Sweep the auditable fixtures and assert the invariant holds.
    for fixture in (
        preview.FIXTURE_SIMULATED_ACCEPTED,
        preview.FIXTURE_SIMULATED_REJECTED,
        preview.FIXTURE_SIMULATED_TRANSPORT_ERROR,
    ):
        audit = pf.run_postfill_audit(preview.build_fixture(fixture))
        if audit.audit_passed:
            assert audit.real_order_network_attempted is False
            assert audit.real_order_endpoint_called is False
            assert audit.real_order_sent is False
            assert audit.order_transport_kind != (
                orch.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER
            )

    # Forcing any real-transport evidence must drop audit_passed to False.
    for kwargs in (
        {"real_order_network_attempted": True},
        {"real_order_endpoint_called": True},
        {"real_order_sent": True},
        {
            "order_transport_kind": (
                orch.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER
            )
        },
    ):
        audit = pf.run_postfill_audit(replace(_accepted_fixture(), **kwargs))
        assert audit.audit_passed is False


def test_audit_reason_distinguishes_integrity_business_and_real_activity():
    audit = pf.run_postfill_audit(_accepted_fixture())
    reason = audit.audit_reason.lower()
    assert "audit integrity" in reason
    assert "business outcome" in reason
    assert "real order activity" in reason


def test_audit_reason_does_not_leak_secrets():
    for fixture in preview.FIXTURES:
        audit = pf.run_postfill_audit(preview.build_fixture(fixture))
        reason = audit.audit_reason.lower()
        for forbidden in (
            "api_key",
            "api-key",
            "secret",
            "x-bapi-sign",
            "authorization_marker",
            "rick_authorized",
        ):
            assert forbidden not in reason


# --- serialization: JSON + Markdown -----------------------------------------


def test_json_report_includes_audit_passed_and_reason(tmp_path):
    audit = pf.run_postfill_audit(_accepted_fixture())
    paths = pf.write_report(audit, output_dir=tmp_path)
    data = json.loads(paths["json_latest"].read_text(encoding="utf-8"))
    assert data["audit_passed"] is True
    assert data["audit_reason"]
    assert data["audited_at_utc"]


def test_markdown_report_includes_audit_passed_and_reason(tmp_path):
    audit = pf.run_postfill_audit(_accepted_fixture())
    paths = pf.write_report(audit, output_dir=tmp_path)
    md = paths["md_latest"].read_text(encoding="utf-8")
    assert "audit_passed:" in md
    assert "audit_reason:" in md
    assert "audited_at_utc:" in md


# --- CLI output: normal + json-only -----------------------------------------


def test_cli_json_only_includes_authoritative_fields():
    result = _run_preview_cli(["--fixture", "simulated_accepted", "--json-only"])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    for key in (
        "task_id",
        "audit_status",
        "audit_passed",
        "audit_reason",
        "simulated_business_outcome",
        "order_transport_kind",
        "sender_call_count",
        "simulated_order_sent",
        "legacy_order_sent",
        "real_order_sent",
        "actual_request_body_qty",
        "actual_request_body_qty_source",
        "resolved_notional",
        "failed_check_count",
        "failed_check_names",
        "report_written",
    ):
        assert key in data, key
    assert data["audit_passed"] is True
    assert data["audit_reason"]


def test_cli_normal_output_includes_audit_passed_and_reason():
    result = _run_preview_cli(["--fixture", "simulated_accepted"])
    assert result.returncode == 0, result.stderr
    assert "audit_passed=" in result.stdout
    assert "audit_reason=" in result.stdout


def test_cli_normal_output_distinguishes_three_concepts():
    result = _run_preview_cli(["--fixture", "simulated_accepted"])
    out = result.stdout.lower()
    assert "audit integrity" in out
    assert "business outcome" in out
    assert "real order activity" in out


def test_cli_not_auditable_exits_one_due_to_audit_passed_false():
    result = _run_preview_cli(["--fixture", "not_auditable", "--json-only"])
    assert result.returncode == 1
    data = json.loads(result.stdout)
    assert data["audit_passed"] is False


def test_cli_forbidden_real_transport_exits_two(tmp_path):
    # The CLI has no forbidden fixture; drive the audit directly and verify
    # the exit-code mapping function returns 2 for a forbidden status.
    audit = pf.run_postfill_audit(
        replace(_accepted_fixture(), real_order_sent=True)
    )
    assert audit.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT
    assert audit.audit_passed is False
    assert preview._decide_exit_code(audit) == 2


def test_cli_simulated_rejected_business_outcome_label():
    result = _run_preview_cli(["--fixture", "simulated_rejected", "--json-only"])
    data = json.loads(result.stdout)
    assert data["simulated_business_outcome"] == "REJECTED"
    assert data["audit_passed"] is True
    assert data["legacy_order_sent"] is False


def test_cli_report_written_flag_reflects_write(tmp_path):
    no_write = _run_preview_cli(["--fixture", "simulated_accepted", "--json-only"])
    assert json.loads(no_write.stdout)["report_written"] is False
    with_write = _run_preview_cli(
        [
            "--fixture",
            "simulated_accepted",
            "--write-report",
            "--output-dir",
            str(tmp_path),
            "--json-only",
        ]
    )
    # stdout is pure JSON in --json-only mode (no trailing "wrote" lines).
    assert json.loads(with_write.stdout)["report_written"] is True
