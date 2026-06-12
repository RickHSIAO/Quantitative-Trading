"""
tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py
TASK-014AM: Guarded Tiny Entry Real Execution Manual Approval Gate tests.

Covers manual_approval_gate_checklist / manual_approval_gate_approval /
real_entry_execution_guard / fail_closed paths; all 11 stages; 22-artifact
preflight contract (the 21 from TASK-014AL + AL's own
entry_final_pre_execution_review output); token-pattern matching
is documented only, never validated as real authorization; exact approval
phrase is documented only, never validated; 12-item required manual
approval inputs documented but never parsed; manual-approval-gate-only
template (no sender adapter, signature_present False,
private_headers empty, send_allowed False); post-entry boundary
manual approval gate (stop attach separate manual gate, cleanup separate
manual gate); failure / abort manual gate (FAIL_CLOSED /
MANUAL_REVIEW_REQUIRED); documentation sync plan (commit hash documented
only, NO auto-commit / NO auto-push); status precedence; source-scan
safety (no urlopen / no forbidden imports / no signing / no os.environ /
no AA-AL module reuse / no real sender / no auto git); report
artifacts; forbidden-flag absence (--execute-real-* / --send-order /
--place-order / --real-run / --confirm-token / --auto-commit /
--git-commit / --auto-push / --git-push); the invariant that
TASK-014L sender G20 (protected_entry_policy_missing) still blocks
--execute-new-entry and is NOT lifted here; next_required_task points
at TASK-014AN_guarded_entry_real_execution_adapter_design.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tokenize
import uuid
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))


@pytest.fixture
def repo_tmp_path():
    """Repo-local scratch directory (avoids Windows ACL / non-ASCII path issues)."""
    root = ROOT / "outputs" / "_test_scratch"
    root.mkdir(parents=True, exist_ok=True)
    d = root / f"am_{uuid.uuid4().hex}"
    d.mkdir()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


from src.demo_tiny_guarded_entry_real_execution_manual_approval_gate import (
    ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES,
    ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES,
    ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES,
    ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES,
    ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES,
    ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES,
    ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES,
    ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES,
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_RUNNER_DESIGN_STATUSES,
    ACCEPTABLE_RUNNER_DRY_RUN_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    BASE_URL_LIVE_REF,
    DEFAULT_SELECTED_SYMBOL,
    DEMO_ENDPOINT_ALLOWLIST,
    DRY_RUN_AUTHORIZATION_RESULT,
    DemoTinyGuardedEntryRealExecutionManualApprovalGate,
    ENTRY_TOKEN_PATTERN,
    EXACT_APPROVAL_PHRASE,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    GATE_EXPECTED_CATEGORY,
    GATE_EXPECTED_CLOSE_ON_TRIGGER,
    GATE_EXPECTED_ENTRY_REFERENCE,
    GATE_EXPECTED_ENTRY_SIDE,
    GATE_EXPECTED_ESTIMATED_NOTIONAL,
    GATE_EXPECTED_EXISTING_COUNT,
    GATE_EXPECTED_MAX_NOTIONAL_USDT,
    GATE_EXPECTED_MIN_ORDER_QTY,
    GATE_EXPECTED_ORDER_TYPE,
    GATE_EXPECTED_POSITION_IDX,
    GATE_EXPECTED_QTY,
    GATE_EXPECTED_QTY_STEP,
    GATE_EXPECTED_REDUCE_ONLY,
    GATE_EXPECTED_SL_TRIGGER_BY,
    GATE_EXPECTED_STOP_LOSS,
    GATE_EXPECTED_SYMBOL,
    GATE_EXPECTED_TPSL_MODE,
    LIVE_ENDPOINT_DENYLIST,
    MODE_FAIL_CLOSED,
    MODE_GATE_APPROVAL,
    MODE_GATE_CHECKLIST,
    MODE_REAL_ENTRY_EXEC_GUARD,
    ORDER_CREATE_PATH_REF,
    ORDER_LINK_ID_PREFIX,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    REQUIRED_CONFIRM_FLAGS,
    REQUIRED_MANUAL_APPROVAL_INPUTS,
    SAMPLE_TOKEN,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_MANUAL_APPROVAL_GATE_SCOPE,
    STAGE_2_MANUAL_APPROVAL_TOKEN_GATE,
    STAGE_3_REQUIRED_MANUAL_APPROVAL_INPUTS,
    STAGE_4_APPROVAL_GATE_READINESS_REVIEW,
    STAGE_5_ENTRY_PAYLOAD_APPROVAL_PREVIEW,
    STAGE_6_STOP_CLEANUP_MANUAL_GATE_REVIEW,
    STAGE_7_FORBIDDEN_EXECUTION_SURFACE_REVIEW,
    STAGE_8_FAILURE_AND_ABORT_MANUAL_GATE,
    STAGE_9_DOCUMENTATION_SYNC_REVIEW,
    STAGE_10_FINAL_MANUAL_APPROVAL_GATE_VERDICT,
    STATUS_FAIL_CLOSED,
    STATUS_GATE_READY,
    STATUS_GATE_READY_EXEC_DISABLED,
    STATUS_REAL_ENTRY_NOT_IMPL,
    TRADING_STOP_PATH_REF,
    TinyGuardedEntryRealExecutionManualApprovalGateResult,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE,
    GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING,
    GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING,
    GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING,
    GATE_GUARDED_CLEANUP_ADAPTER_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING,
    GATE_GUARDED_STOP_ADAPTER_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_NOOP_PLAN_MISSING,
    GATE_PROTECTION_MISSING,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_RECONCILIATION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
    GATE_SOLUSDT_EXISTS_FAIL_CLOSED,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_PERMISSION_GATE_MISSING,
)

_TEST_NOW = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)

ROOT_PATH = ROOT
SRC_PATH = ROOT_PATH / "src" / "demo_tiny_guarded_entry_real_execution_manual_approval_gate.py"
PREVIEW_PATH = (
    ROOT_PATH / "scripts"
    / "preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate.py"
)


# ===========================================================================
# Fixtures
# ===========================================================================

def _valid_readonly() -> dict:
    return {
        "timestamp_utc":          "2026-06-12T10:00:00Z",
        "endpoint_family":        EXPECTED_ENDPOINT_FAMILY,
        "account_mode":           EXPECTED_ACCOUNT_MODE,
        "proof_strength":         EXPECTED_PROOF_STRENGTH,
        "demo_runtime_verified":  True,
        "equity_usd":             500.0,
        "available_balance_usd":  400.0,
    }


def _valid_reconciliation() -> dict:
    return {
        "timestamp_utc":           "2026-06-12T10:05:00Z",
        "mode":                    EXPECTED_POSITION_DETAILS_SOURCE,
        "position_details_source": EXPECTED_POSITION_DETAILS_SOURCE,
        "open_positions_count":    5,
        "positions": [
            {"symbol": "ENAUSDT",   "side": "short", "quantity": 100.0, "entry_price": 0.5, "stop_price": 0.0},
            {"symbol": "TIAUSDT",   "side": "short", "quantity": 50.0,  "entry_price": 2.0, "stop_price": 0.0},
            {"symbol": "AIXBTUSDT", "side": "short", "quantity": 200.0, "entry_price": 0.3, "stop_price": 0.0},
            {"symbol": "POLYXUSDT", "side": "short", "quantity": 300.0, "entry_price": 0.2, "stop_price": 0.0},
            {"symbol": "EDUUSDT",   "side": "short", "quantity": 400.0, "entry_price": 0.4, "stop_price": 0.0},
        ],
    }


def _valid_protection() -> dict:
    return {
        "timestamp_utc":          "2026-06-12T11:00:00Z",
        "selected_symbol":        "SOLUSDT",
        "selected_side":          "long",
        "selected_qty":           GATE_EXPECTED_QTY,
        "entry_reference_price":  GATE_EXPECTED_ENTRY_REFERENCE,
        "stop_price":             GATE_EXPECTED_STOP_LOSS,
        "protected_entry_status": "PREVIEW_ONLY",
        "preview_only":           True,
    }


def _valid_contract() -> dict:
    return {
        "timestamp_utc":      "2026-06-12T11:30:00Z",
        "mode":               "preview",
        "selected_symbol":    "SOLUSDT",
        "path":               TRADING_STOP_PATH_REF,
        "method":             "POST",
        "real_probe_allowed": False,
        "status":             "TRADING_STOP_CONTRACT_PREVIEW_OK",
    }


def _valid_noop_plan() -> dict:
    return {
        "timestamp_utc":     "2026-06-12T11:45:00Z",
        "mode":              "plan",
        "selected_symbol":   "SOLUSDT",
        "recommended_path":  "real_tiny_position_with_stop_lifecycle",
        "status":            "NOOP_PROBE_PLAN_READY",
    }


def _valid_lifecycle() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:55:00Z",
        "mode":                      "mock_lifecycle",
        "selected_symbol":           "SOLUSDT",
        "side":                      "long",
        "tiny_qty":                  GATE_EXPECTED_QTY,
        "tiny_notional":             GATE_EXPECTED_ESTIMATED_NOTIONAL,
        "entry_reference_price":     GATE_EXPECTED_ENTRY_REFERENCE,
        "stop_price":                GATE_EXPECTED_STOP_LOSS,
        "status":                    EXPECTED_LIFECYCLE_STATUS,
        "failed_phase":              "",
        "dangling_tiny_position":    False,
        "existing_positions_touched": [],
    }


def _valid_real_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:58:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "REAL_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":              False,
        "real_tiny_position_implemented":      False,
        "current_task_real_execution_allowed": False,
    }


def _valid_tiny_entry_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:58:30Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
        "entry_side":                "Buy",
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_tiny_stop_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:58:45Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_tiny_cleanup_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_CLEANUP_PERMISSION_CHECKLIST_READY",
        "cleanup_side":              "Sell",
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_lifecycle_summary() -> dict:
    return {
        "timestamp_utc":                  "2026-06-12T11:59:55Z",
        "mode":                           "checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY",
        "real_execution_allowed":              False,
        "real_lifecycle_runner_implemented":   False,
        "current_task_real_execution_allowed": False,
    }


def _valid_runner_design() -> dict:
    return {
        "timestamp_utc":                  "2026-06-12T11:59:58Z",
        "mode":                           "design_checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_RUNNER_DESIGN_READY",
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_runner_dry_run() -> dict:
    return {
        "timestamp_utc":                  "2026-06-12T11:59:59Z",
        "mode":                           "dry_run_checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY",
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_design_review() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:59.5Z",
        "mode":                      "design_review_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_entry_adapter() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:59.7Z",
        "mode":                      "entry_adapter_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_dry_run_adapter":       True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_stop_adapter() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:59.8Z",
        "mode":                      "stop_adapter_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_stop_attach_implemented":        False,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_cleanup_adapter() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:59.9Z",
        "mode":                      "cleanup_adapter_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_cleanup_implemented":            False,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_guarded_lifecycle_summary() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:59.95Z",
        "mode":                      "summary_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "guarded_lifecycle_dry_run_summary":   True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_entry_real_permission_review() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:59.99Z",
        "mode":                      "permission_review_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_real_permission_review": True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_entry_manual_auth_design() -> dict:
    return {
        "timestamp_utc":             "2026-06-12T11:59:59.995Z",
        "mode":                      "authorization_design_checklist",
        "selected_symbol":           "SOLUSDT",
        "status":                    "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY",
        "readiness_conclusion":      READINESS_CONCLUSION_NOT_EXECUTABLE,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_manual_authorization_design": True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_entry_manual_auth_dry_run() -> dict:
    return {
        "timestamp_utc":                "2026-06-12T11:59:59.999Z",
        "mode":                         "authorization_dry_run_checklist",
        "selected_symbol":              "SOLUSDT",
        "status":                       "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY",
        "readiness_conclusion":         READINESS_CONCLUSION_NOT_EXECUTABLE,
        "dry_run_authorization_result": DRY_RUN_AUTHORIZATION_RESULT,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_manual_authorization_dry_run": True,
        "authorization_dry_run_only":          True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _valid_entry_final_pre_execution_review() -> dict:
    return {
        "timestamp_utc":                "2026-06-12T11:59:59.9995Z",
        "mode":                         "final_pre_execution_review_checklist",
        "selected_symbol":              "SOLUSDT",
        "status":                       "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY",
        "readiness_conclusion":         READINESS_CONCLUSION_NOT_EXECUTABLE,
        "dry_run_authorization_result": DRY_RUN_AUTHORIZATION_RESULT,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_final_pre_execution_review": True,
        "final_pre_execution_review_only":     True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
    }


def _read_code_only(path: Path) -> str:
    tokens: list[str] = []
    with open(path, "rb") as fh:
        for tok in tokenize.tokenize(fh.readline):
            if tok.type in (
                tokenize.STRING, tokenize.COMMENT,
                tokenize.ENCODING, tokenize.NEWLINE, tokenize.NL,
                tokenize.INDENT, tokenize.DEDENT, tokenize.ENDMARKER,
            ):
                continue
            tokens.append(tok.string)
    return " ".join(tokens)


def _review() -> DemoTinyGuardedEntryRealExecutionManualApprovalGate:
    return DemoTinyGuardedEntryRealExecutionManualApprovalGate()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    tiny_stop_permission_gate=_UNSET,
    tiny_cleanup_permission_gate=_UNSET,
    lifecycle_summary=_UNSET,
    runner_design=_UNSET,
    runner_dry_run=_UNSET,
    guarded_design_review=_UNSET,
    guarded_entry_adapter=_UNSET,
    guarded_stop_adapter=_UNSET,
    guarded_cleanup_adapter=_UNSET,
    guarded_lifecycle_summary=_UNSET,
    entry_real_permission_review=_UNSET,
    entry_manual_authorization_design=_UNSET,
    entry_manual_authorization_dry_run=_UNSET,
    entry_final_pre_execution_review=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    expected_commit_hash="",
    current_commit_hash="",
    allow_approval_gate=False,
    allow_real_entry_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedEntryRealExecutionManualApprovalGateResult:
    return _review().run_review(
        readonly_smoke=_valid_readonly()                                          if readonly                              is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                                    if recon                                 is _UNSET else recon,
        protection=_valid_protection()                                            if protection                            is _UNSET else protection,
        contract=_valid_contract()                                                if contract                              is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                              if noop_plan                             is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                                         if lifecycle                             is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()                        if real_permission_gate                  is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate()            if tiny_entry_permission_gate            is _UNSET else tiny_entry_permission_gate,
        tiny_stop_permission_gate=_valid_tiny_stop_permission_gate()              if tiny_stop_permission_gate             is _UNSET else tiny_stop_permission_gate,
        tiny_cleanup_permission_gate=_valid_tiny_cleanup_permission_gate()        if tiny_cleanup_permission_gate          is _UNSET else tiny_cleanup_permission_gate,
        lifecycle_summary=_valid_lifecycle_summary()                              if lifecycle_summary                     is _UNSET else lifecycle_summary,
        runner_design=_valid_runner_design()                                      if runner_design                         is _UNSET else runner_design,
        runner_dry_run=_valid_runner_dry_run()                                    if runner_dry_run                        is _UNSET else runner_dry_run,
        guarded_design_review=_valid_guarded_design_review()                      if guarded_design_review                 is _UNSET else guarded_design_review,
        guarded_entry_adapter=_valid_guarded_entry_adapter()                      if guarded_entry_adapter                 is _UNSET else guarded_entry_adapter,
        guarded_stop_adapter=_valid_guarded_stop_adapter()                        if guarded_stop_adapter                  is _UNSET else guarded_stop_adapter,
        guarded_cleanup_adapter=_valid_guarded_cleanup_adapter()                  if guarded_cleanup_adapter               is _UNSET else guarded_cleanup_adapter,
        guarded_lifecycle_summary=_valid_guarded_lifecycle_summary()              if guarded_lifecycle_summary             is _UNSET else guarded_lifecycle_summary,
        entry_real_permission_review=_valid_entry_real_permission_review()        if entry_real_permission_review          is _UNSET else entry_real_permission_review,
        entry_manual_authorization_design=_valid_entry_manual_auth_design()       if entry_manual_authorization_design     is _UNSET else entry_manual_authorization_design,
        entry_manual_authorization_dry_run=_valid_entry_manual_auth_dry_run()     if entry_manual_authorization_dry_run    is _UNSET else entry_manual_authorization_dry_run,
        entry_final_pre_execution_review=_valid_entry_final_pre_execution_review() if entry_final_pre_execution_review     is _UNSET else entry_final_pre_execution_review,
        symbol=symbol,
        expected_commit_hash=expected_commit_hash,
        current_commit_hash=current_commit_hash,
        allow_approval_gate=allow_approval_gate,
        allow_real_entry_execution=allow_real_entry_execution,
        _now=_now,
    )


# ===========================================================================
# AM1-AM4: Status modes
# ===========================================================================

class TestAM1GateReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_GATE_READY
        assert r.mode == MODE_GATE_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.failed_stage == ""
        from src.demo_tiny_guarded_entry_real_execution_manual_approval_gate import _HARD_FAIL_GATES
        assert not any(g in _HARD_FAIL_GATES for g in r.blocked_gates)
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.guarded_entry_real_execution_manual_approval_gate is True
        assert r.manual_approval_gate_only is True
        assert r.token_validation_simulated is True
        assert r.token_validated is False
        assert r.real_token_validated is False
        assert r.exact_phrase_validated is False
        assert r.approval_inputs_validated is False
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True
        assert r.next_required_task == "TASK-014AN_guarded_entry_real_execution_adapter_design"


class TestAM2GateApproval:
    def test_approval_gate_yields_exec_disabled(self):
        r = _run(symbol="SOLUSDT", allow_approval_gate=True)
        assert r.status == STATUS_GATE_READY_EXEC_DISABLED
        assert r.mode == MODE_GATE_APPROVAL
        assert r.approval_gate_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.g20_lifted is False


class TestAM3RealEntryExecutionGuard:
    def test_allow_real_entry_returns_not_implemented(self):
        r = _run(symbol="SOLUSDT", allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL
        assert r.mode == MODE_REAL_ENTRY_EXEC_GUARD
        assert r.real_entry_execution_requested is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.no_orders_sent is True
        assert r.no_position_modified is True
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.g20_lifted is False


class TestAM4FailClosedWrongSymbol:
    def test_wrong_symbol_fails_closed(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AM5-AM26: 22 missing-artifact gates
# ===========================================================================

class TestAM5MissingReadonly:
    def test_missing_readonly_blocked(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAM6MissingReconciliation:
    def test_missing_recon_blocked(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAM7MissingProtection:
    def test_missing_protection_blocked(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAM8MissingContract:
    def test_missing_contract_blocked(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAM9MissingNoopPlan:
    def test_missing_noop_plan_blocked(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAM10MissingLifecycle:
    def test_missing_lifecycle_blocked(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAM11MissingRealPermissionGate:
    def test_missing_real_perm_blocked(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAM12MissingTinyEntryPermissionGate:
    def test_missing_tiny_entry_perm_blocked(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAM13MissingTinyStopPermissionGate:
    def test_missing_tiny_stop_perm_blocked(self):
        r = _run(tiny_stop_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAM14MissingTinyCleanupPermissionGate:
    def test_missing_tiny_cleanup_perm_blocked(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAM15MissingLifecycleSummary:
    def test_missing_lifecycle_summary_blocked(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAM16MissingRunnerDesign:
    def test_missing_runner_design_blocked(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAM17MissingRunnerDryRun:
    def test_missing_runner_dry_run_blocked(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAM18MissingGuardedDesignReview:
    def test_missing_guarded_design_review_blocked(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAM19MissingGuardedEntryAdapter:
    def test_missing_guarded_entry_adapter_blocked(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAM20MissingGuardedStopAdapter:
    def test_missing_guarded_stop_adapter_blocked(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


class TestAM21MissingGuardedCleanupAdapter:
    def test_missing_guarded_cleanup_adapter_blocked(self):
        r = _run(guarded_cleanup_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in r.blocked_gates


class TestAM22MissingGuardedLifecycleSummary:
    def test_missing_guarded_lifecycle_summary_blocked(self):
        r = _run(guarded_lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAM23MissingEntryRealPermissionReview:
    def test_missing_entry_real_perm_review_blocked(self):
        r = _run(entry_real_permission_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING in r.blocked_gates


class TestAM24MissingEntryManualAuthDesign:
    def test_missing_entry_manual_auth_design_blocked(self):
        r = _run(entry_manual_authorization_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING in r.blocked_gates


class TestAM25MissingEntryManualAuthDryRun:
    def test_missing_entry_manual_auth_dry_run_blocked(self):
        r = _run(entry_manual_authorization_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING in r.blocked_gates


class TestAM26MissingEntryFinalPreExecutionReview:
    """The 22nd (and newest) upstream artifact: TASK-014AL's output."""
    def test_missing_entry_final_pre_execution_review_blocked(self):
        r = _run(entry_final_pre_execution_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING in r.blocked_gates


# ===========================================================================
# AM27-AM29: Endpoint / account / symbol invariants
# ===========================================================================

class TestAM27EndpointFamilyMismatch:
    def test_wrong_endpoint_family_blocked(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAM28AccountModeMismatch:
    def test_wrong_account_mode_blocked(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAM29WrongSymbol:
    def test_wrong_symbol_blocked(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AM30-AM32: AL final-review status + readiness + authorization-result acceptance
# ===========================================================================

class TestAM30EntryFinalPreExecutionReviewStatusUnacceptable:
    def test_unacceptable_final_review_status_blocked(self):
        bad = _valid_entry_final_pre_execution_review()
        bad["status"] = "SOMETHING_UNEXPECTED"
        r = _run(entry_final_pre_execution_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE in r.blocked_gates


class TestAM31EntryFinalPreExecutionReviewReadinessExecutable:
    def test_executable_readiness_blocked(self):
        bad = _valid_entry_final_pre_execution_review()
        bad["readiness_conclusion"] = "REAL_ENTRY_EXECUTION_AUTHORIZED"
        r = _run(entry_final_pre_execution_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE in r.blocked_gates


class TestAM32EntryFinalPreExecutionReviewResultNotDocumentedOnly:
    def test_unexpected_authorization_result_blocked(self):
        bad = _valid_entry_final_pre_execution_review()
        bad["dry_run_authorization_result"] = "REAL_ENTRY_AUTHORIZED"
        r = _run(entry_final_pre_execution_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY in r.blocked_gates


# ===========================================================================
# AM33: Stage presence + order (11 stages)
# ===========================================================================

class TestAM33StageOrder:
    def test_stages_present_in_order(self):
        r = _run()
        assert r.stage_order == list(ALL_STAGES)
        assert r.stage_order == [
            STAGE_0_ARTIFACT_PREFLIGHT,
            STAGE_1_MANUAL_APPROVAL_GATE_SCOPE,
            STAGE_2_MANUAL_APPROVAL_TOKEN_GATE,
            STAGE_3_REQUIRED_MANUAL_APPROVAL_INPUTS,
            STAGE_4_APPROVAL_GATE_READINESS_REVIEW,
            STAGE_5_ENTRY_PAYLOAD_APPROVAL_PREVIEW,
            STAGE_6_STOP_CLEANUP_MANUAL_GATE_REVIEW,
            STAGE_7_FORBIDDEN_EXECUTION_SURFACE_REVIEW,
            STAGE_8_FAILURE_AND_ABORT_MANUAL_GATE,
            STAGE_9_DOCUMENTATION_SYNC_REVIEW,
            STAGE_10_FINAL_MANUAL_APPROVAL_GATE_VERDICT,
        ]
        for stage_id in r.stage_order:
            assert stage_id in r.stages
            assert "summary" in r.stages[stage_id]

    def test_eleven_stages(self):
        assert len(ALL_STAGES) == 11


# ===========================================================================
# AM34: Deep-copy roundtrip + to_dict
# ===========================================================================

class TestAM34DictRoundtrip:
    def test_to_dict_is_json_serializable(self):
        r = _run()
        d = r.to_dict()
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["status"] == STATUS_GATE_READY
        assert parsed["selected_symbol"] == "SOLUSDT"
        assert parsed["g20_lifted"] is False
        assert parsed["real_entry_implemented"] is False
        assert parsed["manual_approval_gate_only"] is True
        assert parsed["guarded_entry_real_execution_manual_approval_gate"] is True
        assert parsed["next_required_task"] == "TASK-014AN_guarded_entry_real_execution_adapter_design"

    def test_to_dict_is_deep_copied(self):
        r = _run()
        d1 = r.to_dict()
        d2 = r.to_dict()
        d1["stages"]["mutated"] = True
        assert "mutated" not in d2["stages"]
        d1["existing_position_symbols"].append("FAKE")
        assert "FAKE" not in d2["existing_position_symbols"]


# ===========================================================================
# AM35-AM41: Source-scan safety
# ===========================================================================

class TestAM35NoForbiddenImports:
    def test_module_no_forbidden_imports(self):
        tree = ast.parse(SRC_PATH.read_text(encoding="utf-8"))
        bad: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bad.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                bad.add(node.module or "")
        forbidden = {
            "urllib", "urllib.request", "urllib.parse",
            "requests", "httpx", "http", "http.client", "socket",
            "ssl", "hashlib", "hmac", "secrets", "os.path",
            "dotenv", "pybit",
            "main", "src.risk", "src.bybit_executor",
            "src.demo_tiny_position_lifecycle_mock",
            "src.demo_tiny_position_real_permission_gate",
            "src.demo_tiny_entry_permission_gate",
            "src.demo_tiny_stop_attach_permission_gate",
            "src.demo_tiny_cleanup_permission_gate",
            "src.demo_tiny_lifecycle_real_execution_summary",
            "src.demo_tiny_lifecycle_runner_design",
            "src.demo_tiny_lifecycle_runner_dry_run",
            "src.demo_tiny_lifecycle_guarded_runner_design_review",
            "src.demo_tiny_guarded_entry_dry_run_adapter",
            "src.demo_tiny_guarded_stop_attach_dry_run_adapter",
            "src.demo_tiny_guarded_cleanup_dry_run_adapter",
            "src.demo_tiny_guarded_lifecycle_dry_run_summary",
            "src.demo_tiny_guarded_entry_real_permission_review",
            "src.demo_tiny_guarded_entry_manual_authorization_design",
            "src.demo_tiny_guarded_entry_manual_authorization_dry_run",
            "src.demo_tiny_guarded_entry_final_pre_execution_review",
        }
        assert not (bad & forbidden), f"forbidden imports leaked: {bad & forbidden}"


class TestAM36NoNetworkSymbols:
    def test_no_socket_or_urlopen_or_http_client_in_code(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "urlopen", "Request", "HTTPSConnection", "HTTPConnection",
            "socket.socket", "ssl.create_default_context",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAM37NoEnvOrDotenvReads:
    def test_no_environ_or_dotenv_calls(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "os.environ", "environ", "getenv",
            "load_dotenv", "dotenv_values",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAM38NoSigningTokens:
    def test_no_hmac_or_signature_construction(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "hmac.new", "hashlib.sha256", "hashlib.sha512",
            "X-BAPI-SIGN", "X-BAPI-API-KEY",
            "BybitExecutor(",
            "pybit.unified_trading", "HTTP(",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAM39NoRealSenderInvocation:
    def test_no_order_or_stop_endpoint_call(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "place_order", "submit_order", "send_order",
            "set_trading_stop", "amend_order", "cancel_order",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAM40PathRefsAreStringConstants:
    def test_endpoint_paths_only_appear_as_string_constants(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        assert ORDER_CREATE_PATH_REF in text
        assert TRADING_STOP_PATH_REF in text
        code_tokens = _read_code_only(SRC_PATH)
        assert ORDER_CREATE_PATH_REF not in code_tokens
        assert TRADING_STOP_PATH_REF not in code_tokens


class TestAM41NoAutoGitInSrc:
    """No automatic git operations from src module."""
    def test_no_subprocess_or_git_calls(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "subprocess.run", "subprocess.Popen", "subprocess.call",
            "subprocess.check_output", "subprocess.check_call",
            "os.system", "git.Repo",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into src"


# ===========================================================================
# AM42-AM51: Forbidden flag absence in preview
# ===========================================================================

def _preview_add_argument_lines() -> str:
    """Return only the lines inside add_argument() calls of the preview CLI."""
    text = PREVIEW_PATH.read_text(encoding="utf-8")
    out: list[str] = []
    in_call = False
    depth = 0
    for line in text.splitlines():
        if "add_argument(" in line:
            in_call = True
            depth = line.count("(") - line.count(")")
            out.append(line)
            if depth <= 0:
                in_call = False
            continue
        if in_call:
            out.append(line)
            depth += line.count("(") - line.count(")")
            if depth <= 0:
                in_call = False
    return "\n".join(out)


class TestAM42NoExecuteRealEntryFlag:
    def test_preview_has_no_execute_real_entry_flag(self):
        assert "--execute-real-entry" not in _preview_add_argument_lines()


class TestAM43NoSendOrderFlag:
    def test_preview_has_no_send_order_flag(self):
        assert "--send-order" not in _preview_add_argument_lines()


class TestAM44NoPlaceOrderFlag:
    def test_preview_has_no_place_order_flag(self):
        assert "--place-order" not in _preview_add_argument_lines()


class TestAM45NoRealRunFlag:
    def test_preview_has_no_real_run_flag(self):
        assert "--real-run" not in _preview_add_argument_lines()


class TestAM46NoConfirmTokenFlag:
    def test_preview_has_no_confirm_token_flag(self):
        assert "--confirm-token" not in _preview_add_argument_lines()


class TestAM47NoExecuteTinyEntryFlag:
    def test_preview_has_no_execute_tiny_entry_flag(self):
        assert "--execute-tiny-entry" not in _preview_add_argument_lines()


class TestAM48NoAutoCommitFlag:
    def test_preview_has_no_auto_commit_flag(self):
        assert "--auto-commit" not in _preview_add_argument_lines()


class TestAM49NoGitCommitFlag:
    def test_preview_has_no_git_commit_flag(self):
        assert "--git-commit" not in _preview_add_argument_lines()


class TestAM50NoAutoPushFlag:
    def test_preview_has_no_auto_push_flag(self):
        assert "--auto-push" not in _preview_add_argument_lines()


class TestAM51NoGitPushFlag:
    def test_preview_has_no_git_push_flag(self):
        assert "--git-push" not in _preview_add_argument_lines()


# ===========================================================================
# AM52: Forbidden flag absence in src too
# ===========================================================================

class TestAM52NoForbiddenFlagsInSrc:
    def test_src_has_no_real_execute_flag_parsing(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "--execute-real-entry", "--send-order", "--place-order",
            "--real-run", "--execute-tiny-entry",
            "--auto-commit", "--git-commit", "--auto-push", "--git-push",
        ):
            assert forbidden not in text, f"{forbidden} leaked into src"


# ===========================================================================
# AM53: 5 protected positions never appear as "touched"
# ===========================================================================

class TestAM53ProtectedPositionsUntouched:
    def test_existing_positions_touched_is_empty(self):
        r = _run()
        assert r.existing_positions_touched == []
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym not in r.existing_positions_touched

    def test_no_position_modified_flag(self):
        r = _run()
        assert r.no_position_modified is True


# ===========================================================================
# AM54: G20 never lifted (any mode)
# ===========================================================================

class TestAM54G20NotLifted:
    def test_g20_not_lifted_in_checklist(self):
        r = _run()
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_approval(self):
        r = _run(allow_approval_gate=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_real_entry_guard(self):
        r = _run(allow_real_entry_execution=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True


# ===========================================================================
# AM55: Safety invariants set
# ===========================================================================

class TestAM55SafetyInvariants:
    def test_invariants(self):
        r = _run()
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True
        assert r.no_batch_order is True
        assert r.no_close_only_path is True
        assert r.emergency_close_invoked is False
        assert r.leverage_mutated is False
        assert r.transfer_invoked is False
        assert r.no_secrets_loaded is True
        assert r.secret_value_observed is False


# ===========================================================================
# AM56: Token pattern documented + simulated
# ===========================================================================

class TestAM56TokenPattern:
    def test_pattern_is_documented_and_simulated_only(self):
        r = _run()
        assert r.entry_token_pattern == ENTRY_TOKEN_PATTERN
        assert r.sample_token == SAMPLE_TOKEN
        assert r.token_validation_simulated is True
        assert r.token_validated is False
        assert r.real_token_validated is False
        assert r.dry_run_authorization_result == DRY_RUN_AUTHORIZATION_RESULT


# ===========================================================================
# AM57: Exact phrase + required inputs documented but never validated
# ===========================================================================

class TestAM57ExactPhraseAndApprovalInputsDocumented:
    def test_exact_phrase_documented_never_validated(self):
        r = _run()
        assert r.exact_approval_phrase == EXACT_APPROVAL_PHRASE
        assert r.exact_phrase_validated is False

    def test_approval_inputs_documented_never_validated(self):
        r = _run()
        assert r.approval_inputs_validated is False
        assert isinstance(r.required_manual_approval_inputs, dict)

    def test_required_inputs_count_is_12(self):
        assert len(REQUIRED_MANUAL_APPROVAL_INPUTS) == 12

    def test_required_confirm_flags_count_is_11(self):
        assert len(REQUIRED_CONFIRM_FLAGS) == 11

    def test_approval_phrase_mentions_solusdt_buy_and_no_order(self):
        assert "SOLUSDT" in EXACT_APPROVAL_PHRASE
        assert "BUY" in EXACT_APPROVAL_PHRASE
        assert "NO ORDER MAY BE SENT" in EXACT_APPROVAL_PHRASE
        assert "TASK-014AM" in EXACT_APPROVAL_PHRASE


# ===========================================================================
# AM58: next_required_task points at TASK-014AN
# ===========================================================================

class TestAM58NextRequiredTask:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == "TASK-014AN_guarded_entry_real_execution_adapter_design"


# ===========================================================================
# AM59: Status precedence
# ===========================================================================

class TestAM59StatusPrecedence:
    def test_fail_closed_overrides_real_entry_guard(self):
        r = _run(readonly=None, allow_real_entry_execution=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_fail_closed_overrides_approval(self):
        r = _run(readonly=None, allow_approval_gate=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_real_entry_guard_takes_priority_over_approval(self):
        r = _run(allow_approval_gate=True, allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL


# ===========================================================================
# AM60: Acceptable status whitelists are frozen
# ===========================================================================

class TestAM60AcceptableStatusFrozensets:
    def test_entry_final_pre_execution_review_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY" \
            in ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES

    def test_entry_manual_auth_dry_run_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY" \
            in ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES

    def test_entry_manual_auth_design_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY" \
            in ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES

    def test_entry_real_permission_review_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY" \
            in ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES

    def test_all_whitelists_are_frozen(self):
        for fs in (
            ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
            ACCEPTABLE_RUNNER_DESIGN_STATUSES,
            ACCEPTABLE_RUNNER_DRY_RUN_STATUSES,
            ACCEPTABLE_GUARDED_DESIGN_REVIEW_STATUSES,
            ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES,
            ACCEPTABLE_GUARDED_STOP_ADAPTER_STATUSES,
            ACCEPTABLE_GUARDED_CLEANUP_ADAPTER_STATUSES,
            ACCEPTABLE_GUARDED_LIFECYCLE_SUMMARY_STATUSES,
            ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES,
            ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES,
            ACCEPTABLE_ENTRY_MANUAL_AUTH_DRY_RUN_STATUSES,
            ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES,
        ):
            assert isinstance(fs, frozenset)


# ===========================================================================
# AM61: Expected upstream invariants exposed
# ===========================================================================

class TestAM61ExpectedUpstreamInvariants:
    def test_expected_constants(self):
        assert EXPECTED_ENDPOINT_FAMILY == "bybit_demo"
        assert EXPECTED_ACCOUNT_MODE == "demo"
        assert EXPECTED_PROOF_STRENGTH == "STRONG"
        assert EXPECTED_POSITION_DETAILS_SOURCE == "real_readonly"
        assert EXPECTED_LIFECYCLE_STATUS == "MOCK_TINY_LIFECYCLE_SUCCESS"
        assert EXPECTED_INSTRUMENT_CATEGORY == "linear"


# ===========================================================================
# AM62: Endpoint allow/deny lists
# ===========================================================================

class TestAM62EndpointAllowDenyLists:
    def test_demo_allowlist(self):
        assert BASE_URL_DEMO_REF in DEMO_ENDPOINT_ALLOWLIST
        assert BASE_URL_LIVE_REF not in DEMO_ENDPOINT_ALLOWLIST

    def test_live_denylist(self):
        assert BASE_URL_LIVE_REF in LIVE_ENDPOINT_DENYLIST
        assert BASE_URL_DEMO_REF not in LIVE_ENDPOINT_DENYLIST


# ===========================================================================
# AM63: Forbidden log fields documented
# ===========================================================================

class TestAM63ForbiddenLogFields:
    def test_forbidden_log_fields_documented(self):
        assert "api_key_value" in FORBIDDEN_LOG_FIELDS
        assert "api_secret_value" in FORBIDDEN_LOG_FIELDS
        assert "signature_value" in FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AM64: Gate expected values for documentation
# ===========================================================================

class TestAM64GateExpectedValues:
    def test_gate_expected_constants(self):
        assert GATE_EXPECTED_SYMBOL == "SOLUSDT"
        assert GATE_EXPECTED_CATEGORY == "linear"
        assert GATE_EXPECTED_ENTRY_SIDE == "Buy"
        assert GATE_EXPECTED_QTY == 0.1
        assert GATE_EXPECTED_QTY_STEP == 0.1
        assert GATE_EXPECTED_MIN_ORDER_QTY == 0.1
        assert GATE_EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert GATE_EXPECTED_POSITION_IDX == 0
        assert GATE_EXPECTED_REDUCE_ONLY is False
        assert GATE_EXPECTED_CLOSE_ON_TRIGGER is False
        assert GATE_EXPECTED_ORDER_TYPE == "Market"
        assert GATE_EXPECTED_STOP_LOSS == 61.18
        assert GATE_EXPECTED_TPSL_MODE == "Full"
        assert GATE_EXPECTED_SL_TRIGGER_BY == "MarkPrice"
        assert GATE_EXPECTED_EXISTING_COUNT == 5
        assert ORDER_LINK_ID_PREFIX.startswith("APPROVAL_GATE_TINY_ENTRY")


# ===========================================================================
# AM65: Upstream statuses captured in result (incl. NEW AL final-review field)
# ===========================================================================

class TestAM65UpstreamStatusCapture:
    def test_upstream_statuses_propagated(self):
        r = _run()
        assert r.upstream_lifecycle_summary_status == "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY"
        assert r.upstream_runner_design_status == "TINY_LIFECYCLE_RUNNER_DESIGN_READY"
        assert r.upstream_runner_dry_run_status == "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY"
        assert r.upstream_guarded_design_review_status == "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY"
        assert r.upstream_guarded_entry_adapter_status == "TINY_GUARDED_ENTRY_DRY_RUN_ADAPTER_READY"
        assert r.upstream_guarded_stop_adapter_status == "TINY_GUARDED_STOP_ATTACH_DRY_RUN_ADAPTER_READY"
        assert r.upstream_guarded_cleanup_adapter_status == "TINY_GUARDED_CLEANUP_DRY_RUN_ADAPTER_READY"
        assert r.upstream_guarded_lifecycle_summary_status == "TINY_GUARDED_LIFECYCLE_DRY_RUN_SUMMARY_READY"
        assert r.upstream_entry_real_permission_review_status == "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY"
        assert r.upstream_entry_manual_auth_design_status == "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY"
        assert r.upstream_entry_manual_auth_dry_run_status \
            == "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY"
        assert r.upstream_entry_final_pre_execution_review_status \
            == "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY"
        assert r.upstream_entry_final_pre_execution_review_readiness_conclusion \
            == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.upstream_entry_final_pre_execution_review_authorization_result \
            == DRY_RUN_AUTHORIZATION_RESULT


# ===========================================================================
# AM66: CLI subprocess exit codes
# ===========================================================================

class TestAM66CLIExitCodes:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(PREVIEW_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "approval" in result.stdout.lower() or "gate" in result.stdout.lower()

    def test_missing_artifacts_exits_one(self, repo_tmp_path):
        empty = repo_tmp_path / "empty"
        empty.mkdir()
        from scripts.preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate import (
            run_execute,
        )
        rc = run_execute(
            symbol="SOLUSDT",
            readonly_dir=empty, reconciliation_dir=empty, protection_dir=empty,
            contract_dir=empty, noop_plan_dir=empty, lifecycle_dir=empty,
            real_permission_dir=empty, tiny_entry_dir=empty, tiny_stop_dir=empty,
            tiny_cleanup_dir=empty, lifecycle_summary_dir=empty,
            runner_design_dir=empty, runner_dry_run_dir=empty,
            guarded_design_review_dir=empty, guarded_entry_adapter_dir=empty,
            guarded_stop_adapter_dir=empty, guarded_cleanup_adapter_dir=empty,
            guarded_lifecycle_summary_dir=empty,
            entry_real_permission_review_dir=empty,
            entry_manual_auth_design_dir=empty,
            entry_manual_auth_dry_run_dir=empty,
            entry_final_pre_execution_review_dir=empty,
            output_dir=repo_tmp_path / "out",
        )
        assert rc == 1


# ===========================================================================
# AM67: run_execute writes JSON + MD reports
# ===========================================================================

class TestAM67ReportArtifacts:
    def test_write_report_creates_files(self, repo_tmp_path):
        from scripts.preview_demo_tiny_guarded_entry_real_execution_manual_approval_gate import (
            _write_report,
        )
        r = _run()
        out_dir = repo_tmp_path / "out"
        _write_report(r, out_dir)
        base = "tiny_guarded_entry_real_execution_manual_approval_gate"
        latest_json = out_dir / f"latest_{base}.json"
        latest_md   = out_dir / f"latest_{base}.md"
        assert latest_json.exists()
        assert latest_md.exists()
        parsed = json.loads(latest_json.read_text(encoding="utf-8"))
        assert parsed["status"] == STATUS_GATE_READY
        md_text = latest_md.read_text(encoding="utf-8")
        assert "TASK-014AM" in md_text
        assert ENTRY_TOKEN_PATTERN in md_text
        assert EXACT_APPROVAL_PHRASE in md_text


# ===========================================================================
# AM68: real_execution_allowed never True regardless of inputs
# ===========================================================================

class TestAM68RealExecutionNeverAllowed:
    def test_real_execution_allowed_false_even_with_real_entry_flag(self):
        r = _run(allow_real_entry_execution=True)
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.entry_execution_included is False
        assert r.stop_execution_included is False
        assert r.cleanup_execution_included is False
        assert r.full_lifecycle_execution_included is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# AM69: Existing position symbols documented in result
# ===========================================================================

class TestAM69ExistingPositionSymbols:
    def test_existing_position_symbols_reflect_recon(self):
        r = _run()
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols


# ===========================================================================
# AM70: Sample token shape (simulated, never used as authorization)
# ===========================================================================

class TestAM70SampleTokenMatchesPattern:
    def test_sample_token_has_expected_shape(self):
        parts = SAMPLE_TOKEN.split("_")
        assert parts[0] == "CONFIRM"
        assert parts[1] == "DEMO"
        assert parts[2] == "TINY"
        assert parts[3] == "ENTRY"
        assert parts[-1] == "SOLUSDT"
        assert parts[-2].isdigit()
        assert len(parts[-2]) == 8


# ===========================================================================
# AM71: Pattern only documented in code, not used to validate
# ===========================================================================

class TestAM71TokenNeverValidated:
    def test_pattern_appears_in_code_as_string_constant_only(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        assert ENTRY_TOKEN_PATTERN in text
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in ("re.match", "re.fullmatch", "re.compile"):
            assert forbidden not in code_tokens, f"{forbidden} suggests token validation"


# ===========================================================================
# AM72: Expected commit hash documented (never validated as match)
# ===========================================================================

class TestAM72ExpectedCommitHashDocumentedOnly:
    def test_expected_commit_hash_stored_in_result(self):
        r = _run(expected_commit_hash="abc123def4567890")
        assert r.expected_commit_hash == "abc123def4567890"

    def test_current_commit_hash_stored_in_result(self):
        r = _run(current_commit_hash="fedcba9876543210")
        assert r.current_commit_hash == "fedcba9876543210"

    def test_review_does_not_invoke_git_subprocess(self):
        """The review must NEVER call git itself; current_commit_hash is documented only."""
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "subprocess.run", "subprocess.Popen", "subprocess.check_output",
            "subprocess.call", "git rev-parse",
        ):
            assert forbidden not in code_tokens


# ===========================================================================
# AM73: SOLUSDT already exists -> blocked gate
# ===========================================================================

class TestAM73SolusdtAlreadyExists:
    def test_solusdt_exists_triggers_fail_closed_gate(self):
        bad = _valid_reconciliation()
        bad["positions"].append({
            "symbol": "SOLUSDT", "side": "long", "quantity": 0.1,
            "entry_price": 64.4, "stop_price": 61.18,
        })
        r = _run(recon=bad)
        assert GATE_SOLUSDT_EXISTS_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# AM74: All 11 stages have non-empty summaries
# ===========================================================================

class TestAM74StagePayloads:
    def test_stages_have_summaries(self):
        r = _run()
        for stage_id in r.stage_order:
            env = r.stages[stage_id]
            assert "summary" in env
            assert isinstance(env["summary"], str)
            assert env["summary"] != ""


# ===========================================================================
# AM75: final_manual_approval_gate_verdict completeness
# ===========================================================================

class TestAM75FinalVerdictCompleteness:
    def test_verdict_contains_required_fields(self):
        r = _run()
        v = r.final_manual_approval_gate_verdict
        assert v["approval_gate_allowed"] is False
        assert v["real_entry_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_entry_implemented"] is False
        assert v["guarded_entry_real_execution_manual_approval_gate"] is True
        assert v["manual_approval_gate_only"] is True
        assert v["token_validation_simulated"] is True
        assert v["token_validated"] is False
        assert v["real_token_validated"] is False
        assert v["exact_phrase_validated"] is False
        assert v["approval_inputs_validated"] is False
        assert v["entry_execution_included"] is False
        assert v["stop_execution_included"] is False
        assert v["cleanup_execution_included"] is False
        assert v["full_lifecycle_execution_included"] is False
        assert v["current_task_real_execution_allowed"] is False
        assert v["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert v["dry_run_authorization_result"] == DRY_RUN_AUTHORIZATION_RESULT
        assert v["g20_policy_still_in_place"] is True
        assert v["g20_lifted"] is False
        assert v["status"] == STATUS_GATE_READY
        assert v["mode"] == MODE_GATE_CHECKLIST
        assert v["next_required_task"] == "TASK-014AN_guarded_entry_real_execution_adapter_design"


# ===========================================================================
# AM76: audit_artifacts is sanitized + no_secrets
# ===========================================================================

class TestAM76AuditArtifactsSanitized:
    def test_audit_artifacts_sanitized_flag(self):
        r = _run()
        assert r.audit_artifacts.get("sanitized") is True
        assert r.audit_artifacts.get("no_secrets") is True
        assert r.audit_artifacts.get("response_from_exchange") is False
        assert r.audit_artifacts.get("response_status") == "APPROVAL_GATE_NOT_SENT"


# ===========================================================================
# AM77: documentation_sync_review present
# ===========================================================================

class TestAM77DocumentationSyncReview:
    def test_documentation_sync_review_present(self):
        r = _run(expected_commit_hash="abc1234")
        d = r.documentation_sync_review
        assert isinstance(d, dict)
        assert d  # non-empty


# ===========================================================================
# AM78: src module is properly self-contained (uses only stdlib + dataclasses)
# ===========================================================================

class TestAM78SrcSelfContained:
    def test_only_stdlib_imports(self):
        tree = ast.parse(SRC_PATH.read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        allowed = {
            "__future__", "copy", "dataclasses", "datetime",
            "typing", "collections", "json", "math", "re",
        }
        leaked = modules - allowed
        assert not leaked, f"unexpected imports: {leaked}"


# ===========================================================================
# AM79: approval_gate_allowed flag isolated
# ===========================================================================

class TestAM79ApprovalGateAllowedIsolated:
    def test_default_approval_gate_false(self):
        r = _run()
        assert r.approval_gate_allowed is False

    def test_approval_gate_true_when_flagged(self):
        r = _run(allow_approval_gate=True)
        assert r.approval_gate_allowed is True


# ===========================================================================
# AM80: SOLUSDT absent from existing positions in default fixture
# ===========================================================================

class TestAM80SolusdtAbsent:
    def test_solusdt_absent_before_entry(self):
        r = _run()
        assert "SOLUSDT" not in r.existing_position_symbols


# ===========================================================================
# AM81: 5 expected protected symbols present in default fixture
# ===========================================================================

class TestAM81ProtectedSymbolsPresent:
    def test_protected_symbols_observed(self):
        r = _run()
        for sym in ("ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"):
            assert sym in r.existing_position_symbols


# ===========================================================================
# AM82: approval gate still keeps readiness NOT_EXECUTABLE
# ===========================================================================

class TestAM82ApprovalGateReadinessUnchanged:
    def test_readiness_unchanged_under_approval(self):
        r = _run(allow_approval_gate=True)
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.dry_run_authorization_result == DRY_RUN_AUTHORIZATION_RESULT


# ===========================================================================
# AM83: real entry guard still keeps readiness NOT_EXECUTABLE
# ===========================================================================

class TestAM83RealEntryGuardReadinessUnchanged:
    def test_readiness_unchanged_under_real_entry_guard(self):
        r = _run(allow_real_entry_execution=True)
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.dry_run_authorization_result == DRY_RUN_AUTHORIZATION_RESULT


# ===========================================================================
# AM84: Stage 1 manual_approval_gate_scope present
# ===========================================================================

class TestAM84ManualApprovalGateScope:
    def test_scope_is_dict_and_documented(self):
        r = _run()
        assert isinstance(r.manual_approval_gate_scope, dict)
        assert r.manual_approval_gate_scope  # non-empty


# ===========================================================================
# AM85: HARD_FAIL_GATES contains the 4 new entry_final_pre_execution_review gates
# ===========================================================================

class TestAM85HardFailGatesIncludeNewFinalReviewGates:
    def test_new_final_review_gates_are_hard_fail(self):
        from src.demo_tiny_guarded_entry_real_execution_manual_approval_gate import _HARD_FAIL_GATES
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING in _HARD_FAIL_GATES
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUS_UNACCEPTABLE in _HARD_FAIL_GATES
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READINESS_EXECUTABLE in _HARD_FAIL_GATES
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_RESULT_NOT_DOCUMENTED_ONLY in _HARD_FAIL_GATES


# ===========================================================================
# AM86: Status precedence — solusdt-exists + allow_real_entry_execution
# ===========================================================================

class TestAM86SolusdtExistsWithRealEntryFlag:
    def test_solusdt_exists_gate_still_documented_under_real_entry_guard(self):
        bad = _valid_reconciliation()
        bad["positions"].append({
            "symbol": "SOLUSDT", "side": "long", "quantity": 0.1,
            "entry_price": 64.4, "stop_price": 61.18,
        })
        r = _run(recon=bad, allow_real_entry_execution=True)
        assert GATE_SOLUSDT_EXISTS_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# AM87: Manual approval token / phrase / inputs sub-dicts present
# ===========================================================================

class TestAM87ManualApprovalSubDictsPresent:
    def test_manual_approval_token_gate_is_dict(self):
        r = _run()
        assert isinstance(r.manual_approval_token_gate, dict)
        assert r.manual_approval_token_gate

    def test_required_manual_approval_inputs_is_dict(self):
        r = _run()
        assert isinstance(r.required_manual_approval_inputs, dict)
        assert r.required_manual_approval_inputs

    def test_approval_gate_readiness_review_is_dict(self):
        r = _run()
        assert isinstance(r.approval_gate_readiness_review, dict)
        assert r.approval_gate_readiness_review

    def test_entry_payload_approval_preview_is_dict(self):
        r = _run()
        assert isinstance(r.entry_payload_approval_preview, dict)
        assert r.entry_payload_approval_preview

    def test_stop_cleanup_manual_gate_review_is_dict(self):
        r = _run()
        assert isinstance(r.stop_cleanup_manual_gate_review, dict)
        assert r.stop_cleanup_manual_gate_review

    def test_forbidden_execution_surface_review_is_dict(self):
        r = _run()
        assert isinstance(r.forbidden_execution_surface_review, dict)
        assert r.forbidden_execution_surface_review

    def test_failure_and_abort_manual_gate_is_dict(self):
        r = _run()
        assert isinstance(r.failure_and_abort_manual_gate, dict)
        assert r.failure_and_abort_manual_gate


# ===========================================================================
# AM88: order_link_id_prefix exposed and consistent
# ===========================================================================

class TestAM88OrderLinkIdPrefix:
    def test_order_link_id_prefix(self):
        r = _run()
        assert r.order_link_id_prefix == ORDER_LINK_ID_PREFIX
        assert "APPROVAL_GATE_TINY_ENTRY" in r.order_link_id_prefix
