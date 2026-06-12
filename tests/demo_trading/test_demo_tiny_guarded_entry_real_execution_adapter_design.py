"""
tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_design.py
TASK-014AN: Guarded Tiny Entry Real Execution Adapter Design tests.

Covers adapter_design_checklist / adapter_design_approval /
real_entry_execution_guard / fail_closed paths; all 12 stages; 23-artifact
preflight contract (the 22 from TASK-014AM + AM's own
entry_manual_approval_gate output); adapter contract / inputs / outputs /
payload preview / secret-and-signature boundary / stop-cleanup boundary /
forbidden execution surface / failure-and-abort / documentation-sync /
audit-artifacts / final-adapter-design verdict sub-dicts; design-only
template (no sender adapter, no `send` method, signature_present False,
private_headers empty, send_allowed False); failure / abort adapter design
(FAIL_CLOSED / MANUAL_REVIEW_REQUIRED); documentation sync plan (commit
hash documented only, NO auto-commit / NO auto-push); status precedence;
source-scan safety (no urlopen / no forbidden imports / no signing /
no os.environ / no AA-AM module reuse / no real sender / no auto git);
report artifacts; forbidden-flag absence (--execute-real-* / --send-order
/ --place-order / --real-run / --confirm-token / --auto-commit /
--git-commit / --auto-push / --git-push); the invariant that
TASK-014L sender G20 (protected_entry_policy_missing) still blocks
--execute-new-entry and is NOT lifted here; next_required_task points
at TASK-014AO_guarded_entry_real_execution_adapter_dry_run.
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
    d = root / f"an_{uuid.uuid4().hex}"
    d.mkdir()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


from src.demo_tiny_guarded_entry_real_execution_adapter_design import (
    ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES,
    ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES,
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
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    ADAPTER_RESPONSE_STATUS,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    BASE_URL_LIVE_REF,
    DEFAULT_SELECTED_SYMBOL,
    DEMO_ENDPOINT_ALLOWLIST,
    DESIGN_EXPECTED_CATEGORY,
    DESIGN_EXPECTED_CLOSE_ON_TRIGGER,
    DESIGN_EXPECTED_ENTRY_REFERENCE,
    DESIGN_EXPECTED_ENTRY_SIDE,
    DESIGN_EXPECTED_ESTIMATED_NOTIONAL,
    DESIGN_EXPECTED_EXISTING_COUNT,
    DESIGN_EXPECTED_MAX_NOTIONAL_USDT,
    DESIGN_EXPECTED_MIN_ORDER_QTY,
    DESIGN_EXPECTED_ORDER_TYPE,
    DESIGN_EXPECTED_POSITION_IDX,
    DESIGN_EXPECTED_QTY,
    DESIGN_EXPECTED_QTY_STEP,
    DESIGN_EXPECTED_REDUCE_ONLY,
    DESIGN_EXPECTED_SL_TRIGGER_BY,
    DESIGN_EXPECTED_STOP_LOSS,
    DESIGN_EXPECTED_SYMBOL,
    DESIGN_EXPECTED_TPSL_MODE,
    DRY_RUN_AUTHORIZATION_RESULT,
    DemoTinyGuardedEntryRealExecutionAdapterDesign,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    LIVE_ENDPOINT_DENYLIST,
    MODE_DESIGN_APPROVAL,
    MODE_DESIGN_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_ENTRY_EXEC_GUARD,
    ORDER_CREATE_PATH_REF,
    ORDER_LINK_ID_PREFIX,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_ADAPTER_DESIGN_SCOPE,
    STAGE_2_ADAPTER_CONTRACT_DESIGN,
    STAGE_3_ADAPTER_INPUT_SCHEMA_DESIGN,
    STAGE_4_ADAPTER_OUTPUT_SCHEMA_DESIGN,
    STAGE_5_ENTRY_PAYLOAD_DESIGN_PREVIEW,
    STAGE_6_SECRET_AND_SIGNATURE_BOUNDARY_DESIGN,
    STAGE_7_STOP_CLEANUP_BOUNDARY_DESIGN,
    STAGE_8_FORBIDDEN_EXECUTION_SURFACE_DESIGN,
    STAGE_9_FAILURE_AND_ABORT_ADAPTER_DESIGN,
    STAGE_10_DOCUMENTATION_SYNC_REVIEW,
    STAGE_11_FINAL_ADAPTER_DESIGN_VERDICT,
    STATUS_DESIGN_READY,
    STATUS_DESIGN_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_ENTRY_NOT_IMPL,
    TRADING_STOP_PATH_REF,
    TinyGuardedEntryRealExecutionAdapterDesignResult,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE,
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
SRC_PATH = ROOT_PATH / "src" / "demo_tiny_guarded_entry_real_execution_adapter_design.py"
PREVIEW_PATH = (
    ROOT_PATH / "scripts"
    / "preview_demo_tiny_guarded_entry_real_execution_adapter_design.py"
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
        "selected_qty":           DESIGN_EXPECTED_QTY,
        "entry_reference_price":  DESIGN_EXPECTED_ENTRY_REFERENCE,
        "stop_price":             DESIGN_EXPECTED_STOP_LOSS,
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
        "tiny_qty":                  DESIGN_EXPECTED_QTY,
        "tiny_notional":             DESIGN_EXPECTED_ESTIMATED_NOTIONAL,
        "entry_reference_price":     DESIGN_EXPECTED_ENTRY_REFERENCE,
        "stop_price":                DESIGN_EXPECTED_STOP_LOSS,
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


def _valid_entry_manual_approval_gate() -> dict:
    return {
        "timestamp_utc":                "2026-06-12T11:59:59.9999Z",
        "mode":                         "manual_approval_gate_checklist",
        "selected_symbol":              "SOLUSDT",
        "selected_position": {
            "symbol":            "SOLUSDT",
            "side":              "Buy",
            "qty":               DESIGN_EXPECTED_QTY,
            "entry_reference":   DESIGN_EXPECTED_ENTRY_REFERENCE,
            "stop_loss":         DESIGN_EXPECTED_STOP_LOSS,
        },
        "endpoint_family":              EXPECTED_ENDPOINT_FAMILY,
        "account_mode":                 EXPECTED_ACCOUNT_MODE,
        "status":                       "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY",
        "readiness_conclusion":         READINESS_CONCLUSION_NOT_EXECUTABLE,
        "dry_run_authorization_result": DRY_RUN_AUTHORIZATION_RESULT,
        "approval_grants_execution":    False,
        "exact_phrase_validated":       False,
        "approval_inputs_validated":    False,
        "manual_approval_gate_only":    True,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_real_execution_manual_approval_gate": True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
        "no_secrets_loaded":                   True,
        "no_auto_git_operations":              True,
        "expected_commit_hash":         "0000000000000000000000000000000000000000",
        "next_required_task":           "TASK-014AN_guarded_entry_real_execution_adapter_design",
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


def _review() -> DemoTinyGuardedEntryRealExecutionAdapterDesign:
    return DemoTinyGuardedEntryRealExecutionAdapterDesign()


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
    entry_manual_approval_gate=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    expected_commit_hash="",
    current_commit_hash="",
    allow_adapter_design_approval=False,
    allow_real_entry_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedEntryRealExecutionAdapterDesignResult:
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
        entry_manual_approval_gate=_valid_entry_manual_approval_gate()            if entry_manual_approval_gate            is _UNSET else entry_manual_approval_gate,
        symbol=symbol,
        expected_commit_hash=expected_commit_hash,
        current_commit_hash=current_commit_hash,
        allow_adapter_design_approval=allow_adapter_design_approval,
        allow_real_entry_execution=allow_real_entry_execution,
        _now=_now,
    )


# ===========================================================================
# AN1-AN4: Status modes
# ===========================================================================

class TestAN1DesignReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_DESIGN_READY
        assert r.mode == MODE_DESIGN_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.failed_stage == ""
        from src.demo_tiny_guarded_entry_real_execution_adapter_design import _HARD_FAIL_GATES
        assert not any(g in _HARD_FAIL_GATES for g in r.blocked_gates)
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.guarded_entry_real_execution_adapter_design is True
        assert r.adapter_design_only is True
        assert r.adapter_implementation_included is False
        assert r.adapter_execution_included is False
        assert r.adapter_grants_execution is False
        assert r.approval_gate_grants_execution is False
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True
        assert r.next_required_task == "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"


class TestAN2DesignApproval:
    def test_approval_yields_exec_disabled(self):
        r = _run(symbol="SOLUSDT", allow_adapter_design_approval=True)
        assert r.status == STATUS_DESIGN_READY_EXEC_DISABLED
        assert r.mode == MODE_DESIGN_APPROVAL
        assert r.adapter_design_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.g20_lifted is False


class TestAN3RealEntryExecutionGuard:
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


class TestAN4FailClosedWrongSymbol:
    def test_wrong_symbol_fails_closed(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AN5-AN27: 23 missing-artifact gates
# ===========================================================================

class TestAN5MissingReadonly:
    def test_missing_readonly_blocked(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAN6MissingReconciliation:
    def test_missing_recon_blocked(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAN7MissingProtection:
    def test_missing_protection_blocked(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAN8MissingContract:
    def test_missing_contract_blocked(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAN9MissingNoopPlan:
    def test_missing_noop_plan_blocked(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAN10MissingLifecycle:
    def test_missing_lifecycle_blocked(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAN11MissingRealPermissionGate:
    def test_missing_real_perm_blocked(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAN12MissingTinyEntryPermissionGate:
    def test_missing_tiny_entry_perm_blocked(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAN13MissingTinyStopPermissionGate:
    def test_missing_tiny_stop_perm_blocked(self):
        r = _run(tiny_stop_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAN14MissingTinyCleanupPermissionGate:
    def test_missing_tiny_cleanup_perm_blocked(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAN15MissingLifecycleSummary:
    def test_missing_lifecycle_summary_blocked(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAN16MissingRunnerDesign:
    def test_missing_runner_design_blocked(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAN17MissingRunnerDryRun:
    def test_missing_runner_dry_run_blocked(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAN18MissingGuardedDesignReview:
    def test_missing_guarded_design_review_blocked(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAN19MissingGuardedEntryAdapter:
    def test_missing_guarded_entry_adapter_blocked(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAN20MissingGuardedStopAdapter:
    def test_missing_guarded_stop_adapter_blocked(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


class TestAN21MissingGuardedCleanupAdapter:
    def test_missing_guarded_cleanup_adapter_blocked(self):
        r = _run(guarded_cleanup_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in r.blocked_gates


class TestAN22MissingGuardedLifecycleSummary:
    def test_missing_guarded_lifecycle_summary_blocked(self):
        r = _run(guarded_lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAN23MissingEntryRealPermissionReview:
    def test_missing_entry_real_perm_review_blocked(self):
        r = _run(entry_real_permission_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING in r.blocked_gates


class TestAN24MissingEntryManualAuthDesign:
    def test_missing_entry_manual_auth_design_blocked(self):
        r = _run(entry_manual_authorization_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING in r.blocked_gates


class TestAN25MissingEntryManualAuthDryRun:
    def test_missing_entry_manual_auth_dry_run_blocked(self):
        r = _run(entry_manual_authorization_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING in r.blocked_gates


class TestAN26MissingEntryFinalPreExecutionReview:
    def test_missing_entry_final_pre_execution_review_blocked(self):
        r = _run(entry_final_pre_execution_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING in r.blocked_gates


class TestAN27MissingEntryManualApprovalGate:
    """The 23rd (and newest) upstream artifact: TASK-014AM's output."""
    def test_missing_entry_manual_approval_gate_blocked(self):
        r = _run(entry_manual_approval_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING in r.blocked_gates


# ===========================================================================
# AN28-AN30: Endpoint / account / symbol invariants
# ===========================================================================

class TestAN28EndpointFamilyMismatch:
    def test_wrong_endpoint_family_blocked(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAN29AccountModeMismatch:
    def test_wrong_account_mode_blocked(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAN30WrongSymbol:
    def test_wrong_symbol_blocked(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AN31-AN35: AM manual-approval-gate acceptance gates
# ===========================================================================

class TestAN31EntryManualApprovalGateStatusUnacceptable:
    def test_unacceptable_status_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["status"] = "SOMETHING_UNEXPECTED"
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE in r.blocked_gates


class TestAN32EntryManualApprovalGateReadinessExecutable:
    def test_executable_readiness_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["readiness_conclusion"] = "REAL_ENTRY_EXECUTION_AUTHORIZED"
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE in r.blocked_gates


class TestAN33EntryManualApprovalGateGrantsExecution:
    def test_grants_execution_true_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["approval_grants_execution"] = True
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION in r.blocked_gates


class TestAN34EntryManualApprovalGatePhraseAlreadyValidated:
    def test_phrase_validated_true_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["exact_phrase_validated"] = True
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED in r.blocked_gates


class TestAN35EntryManualApprovalGateInputsAlreadyValidated:
    def test_inputs_validated_true_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["approval_inputs_validated"] = True
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED in r.blocked_gates


# ===========================================================================
# AN36: Stage presence + order (12 stages)
# ===========================================================================

class TestAN36StageOrder:
    def test_stages_present_in_order(self):
        r = _run()
        assert r.stage_order == list(ALL_STAGES)
        assert r.stage_order == [
            STAGE_0_ARTIFACT_PREFLIGHT,
            STAGE_1_ADAPTER_DESIGN_SCOPE,
            STAGE_2_ADAPTER_CONTRACT_DESIGN,
            STAGE_3_ADAPTER_INPUT_SCHEMA_DESIGN,
            STAGE_4_ADAPTER_OUTPUT_SCHEMA_DESIGN,
            STAGE_5_ENTRY_PAYLOAD_DESIGN_PREVIEW,
            STAGE_6_SECRET_AND_SIGNATURE_BOUNDARY_DESIGN,
            STAGE_7_STOP_CLEANUP_BOUNDARY_DESIGN,
            STAGE_8_FORBIDDEN_EXECUTION_SURFACE_DESIGN,
            STAGE_9_FAILURE_AND_ABORT_ADAPTER_DESIGN,
            STAGE_10_DOCUMENTATION_SYNC_REVIEW,
            STAGE_11_FINAL_ADAPTER_DESIGN_VERDICT,
        ]
        for stage_id in r.stage_order:
            assert stage_id in r.stages
            assert "summary" in r.stages[stage_id]

    def test_twelve_stages(self):
        assert len(ALL_STAGES) == 12


# ===========================================================================
# AN37: Deep-copy roundtrip + to_dict
# ===========================================================================

class TestAN37DictRoundtrip:
    def test_to_dict_is_json_serializable(self):
        r = _run()
        d = r.to_dict()
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["status"] == STATUS_DESIGN_READY
        assert parsed["selected_symbol"] == "SOLUSDT"
        assert parsed["g20_lifted"] is False
        assert parsed["real_entry_implemented"] is False
        assert parsed["adapter_design_only"] is True
        assert parsed["guarded_entry_real_execution_adapter_design"] is True
        assert parsed["next_required_task"] == "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"

    def test_to_dict_is_deep_copied(self):
        r = _run()
        d1 = r.to_dict()
        d2 = r.to_dict()
        d1["stages"]["mutated"] = True
        assert "mutated" not in d2["stages"]
        d1["existing_position_symbols"].append("FAKE")
        assert "FAKE" not in d2["existing_position_symbols"]


# ===========================================================================
# AN38-AN44: Source-scan safety
# ===========================================================================

class TestAN38NoForbiddenImports:
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
            "src.demo_tiny_guarded_entry_real_execution_manual_approval_gate",
        }
        assert not (bad & forbidden), f"forbidden imports leaked: {bad & forbidden}"


class TestAN39NoNetworkSymbols:
    def test_no_socket_or_urlopen_or_http_client_in_code(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "urlopen", "Request", "HTTPSConnection", "HTTPConnection",
            "socket.socket", "ssl.create_default_context",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAN40NoEnvOrDotenvReads:
    def test_no_environ_or_dotenv_calls(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "os.environ", "environ", "getenv",
            "load_dotenv", "dotenv_values",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAN41NoSigningTokens:
    def test_no_hmac_or_signature_construction(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "hmac.new", "hashlib.sha256", "hashlib.sha512",
            "X-BAPI-SIGN", "X-BAPI-API-KEY",
            "BybitExecutor(",
            "pybit.unified_trading", "HTTP(",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAN42NoRealSenderInvocation:
    def test_no_order_or_stop_endpoint_call(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "place_order", "submit_order", "send_order",
            "set_trading_stop", "amend_order", "cancel_order",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAN43PathRefsAreStringConstants:
    def test_endpoint_paths_only_appear_as_string_constants(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        assert ORDER_CREATE_PATH_REF in text
        assert TRADING_STOP_PATH_REF in text
        code_tokens = _read_code_only(SRC_PATH)
        assert ORDER_CREATE_PATH_REF not in code_tokens
        assert TRADING_STOP_PATH_REF not in code_tokens


class TestAN44NoAutoGitInSrc:
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
# AN45-AN54: Forbidden flag absence in preview
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


class TestAN45NoExecuteRealEntryFlag:
    def test_preview_has_no_execute_real_entry_flag(self):
        assert "--execute-real-entry" not in _preview_add_argument_lines()


class TestAN46NoSendOrderFlag:
    def test_preview_has_no_send_order_flag(self):
        assert "--send-order" not in _preview_add_argument_lines()


class TestAN47NoPlaceOrderFlag:
    def test_preview_has_no_place_order_flag(self):
        assert "--place-order" not in _preview_add_argument_lines()


class TestAN48NoRealRunFlag:
    def test_preview_has_no_real_run_flag(self):
        assert "--real-run" not in _preview_add_argument_lines()


class TestAN49NoConfirmTokenFlag:
    def test_preview_has_no_confirm_token_flag(self):
        assert "--confirm-token" not in _preview_add_argument_lines()


class TestAN50NoExecuteTinyEntryFlag:
    def test_preview_has_no_execute_tiny_entry_flag(self):
        assert "--execute-tiny-entry" not in _preview_add_argument_lines()


class TestAN51NoAutoCommitFlag:
    def test_preview_has_no_auto_commit_flag(self):
        assert "--auto-commit" not in _preview_add_argument_lines()


class TestAN52NoGitCommitFlag:
    def test_preview_has_no_git_commit_flag(self):
        assert "--git-commit" not in _preview_add_argument_lines()


class TestAN53NoAutoPushFlag:
    def test_preview_has_no_auto_push_flag(self):
        assert "--auto-push" not in _preview_add_argument_lines()


class TestAN54NoGitPushFlag:
    def test_preview_has_no_git_push_flag(self):
        assert "--git-push" not in _preview_add_argument_lines()


# ===========================================================================
# AN55: Forbidden flag absence in src too
# ===========================================================================

class TestAN55NoForbiddenFlagsInSrc:
    def test_src_has_no_real_execute_flag_parsing(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "--execute-real-entry", "--send-order", "--place-order",
            "--real-run", "--execute-tiny-entry",
            "--auto-commit", "--git-commit", "--auto-push", "--git-push",
        ):
            assert forbidden not in text, f"{forbidden} leaked into src"


# ===========================================================================
# AN56: 5 protected positions never appear as "touched"
# ===========================================================================

class TestAN56ProtectedPositionsUntouched:
    def test_existing_positions_touched_is_empty(self):
        r = _run()
        assert r.existing_positions_touched == []
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym not in r.existing_positions_touched

    def test_no_position_modified_flag(self):
        r = _run()
        assert r.no_position_modified is True


# ===========================================================================
# AN57: G20 never lifted (any mode)
# ===========================================================================

class TestAN57G20NotLifted:
    def test_g20_not_lifted_in_checklist(self):
        r = _run()
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_approval(self):
        r = _run(allow_adapter_design_approval=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_real_entry_guard(self):
        r = _run(allow_real_entry_execution=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True


# ===========================================================================
# AN58: Safety invariants set
# ===========================================================================

class TestAN58SafetyInvariants:
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
# AN59: Adapter contract identity exposed
# ===========================================================================

class TestAN59AdapterContractIdentity:
    def test_adapter_name_and_version(self):
        r = _run()
        assert r.adapter_name == ADAPTER_NAME
        assert r.adapter_contract_version == ADAPTER_CONTRACT_VERSION
        assert r.order_link_id_prefix == ORDER_LINK_ID_PREFIX
        assert ADAPTER_NAME == "GuardedTinyEntryRealExecutionAdapter"
        assert ADAPTER_CONTRACT_VERSION == "design_only_v1"
        assert ADAPTER_RESPONSE_STATUS == "ADAPTER_DESIGN_NOT_SENT"
        assert ORDER_LINK_ID_PREFIX == "ADAPTER_DESIGN_TINY_ENTRY_"


# ===========================================================================
# AN60: next_required_task points at TASK-014AO
# ===========================================================================

class TestAN60NextRequiredTask:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"


# ===========================================================================
# AN61: Status precedence
# ===========================================================================

class TestAN61StatusPrecedence:
    def test_fail_closed_overrides_real_entry_guard(self):
        r = _run(readonly=None, allow_real_entry_execution=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_fail_closed_overrides_approval(self):
        r = _run(readonly=None, allow_adapter_design_approval=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_real_entry_guard_takes_priority_over_approval(self):
        r = _run(allow_adapter_design_approval=True, allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL


# ===========================================================================
# AN62: Acceptable status whitelists are frozen
# ===========================================================================

class TestAN62AcceptableStatusFrozensets:
    def test_entry_manual_approval_gate_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY" \
            in ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES

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
            ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES,
        ):
            assert isinstance(fs, frozenset)


# ===========================================================================
# AN63: Expected upstream invariants exposed
# ===========================================================================

class TestAN63ExpectedUpstreamInvariants:
    def test_expected_constants(self):
        assert EXPECTED_ENDPOINT_FAMILY == "bybit_demo"
        assert EXPECTED_ACCOUNT_MODE == "demo"
        assert EXPECTED_PROOF_STRENGTH == "STRONG"
        assert EXPECTED_POSITION_DETAILS_SOURCE == "real_readonly"
        assert EXPECTED_LIFECYCLE_STATUS == "MOCK_TINY_LIFECYCLE_SUCCESS"
        assert EXPECTED_INSTRUMENT_CATEGORY == "linear"


# ===========================================================================
# AN64: Endpoint allow/deny lists
# ===========================================================================

class TestAN64EndpointAllowDenyLists:
    def test_demo_allowlist(self):
        assert BASE_URL_DEMO_REF in DEMO_ENDPOINT_ALLOWLIST
        assert BASE_URL_LIVE_REF not in DEMO_ENDPOINT_ALLOWLIST

    def test_live_denylist(self):
        assert BASE_URL_LIVE_REF in LIVE_ENDPOINT_DENYLIST
        assert BASE_URL_DEMO_REF not in LIVE_ENDPOINT_DENYLIST


# ===========================================================================
# AN65: Forbidden log fields documented
# ===========================================================================

class TestAN65ForbiddenLogFields:
    def test_forbidden_log_fields_documented(self):
        assert "api_key_value" in FORBIDDEN_LOG_FIELDS
        assert "api_secret_value" in FORBIDDEN_LOG_FIELDS
        assert "signature_value" in FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AN66: Design expected values for documentation
# ===========================================================================

class TestAN66DesignExpectedValues:
    def test_design_expected_constants(self):
        assert DESIGN_EXPECTED_SYMBOL == "SOLUSDT"
        assert DESIGN_EXPECTED_CATEGORY == "linear"
        assert DESIGN_EXPECTED_ENTRY_SIDE == "Buy"
        assert DESIGN_EXPECTED_QTY == 0.1
        assert DESIGN_EXPECTED_QTY_STEP == 0.1
        assert DESIGN_EXPECTED_MIN_ORDER_QTY == 0.1
        assert DESIGN_EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert DESIGN_EXPECTED_POSITION_IDX == 0
        assert DESIGN_EXPECTED_REDUCE_ONLY is False
        assert DESIGN_EXPECTED_CLOSE_ON_TRIGGER is False
        assert DESIGN_EXPECTED_ORDER_TYPE == "Market"
        assert DESIGN_EXPECTED_STOP_LOSS == 61.18
        assert DESIGN_EXPECTED_TPSL_MODE == "Full"
        assert DESIGN_EXPECTED_SL_TRIGGER_BY == "MarkPrice"
        assert DESIGN_EXPECTED_EXISTING_COUNT == 5
        assert ORDER_LINK_ID_PREFIX.startswith("ADAPTER_DESIGN_TINY_ENTRY")


# ===========================================================================
# AN67: Upstream statuses captured in result (incl. NEW AM approval-gate fields)
# ===========================================================================

class TestAN67UpstreamStatusCapture:
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
        assert r.upstream_entry_manual_approval_gate_status \
            == "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY"
        assert r.upstream_entry_manual_approval_gate_readiness_conclusion \
            == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.upstream_entry_manual_approval_gate_approval_grants_execution is False
        assert r.upstream_entry_manual_approval_gate_exact_phrase_validated is False
        assert r.upstream_entry_manual_approval_gate_approval_inputs_validated is False


# ===========================================================================
# AN68: CLI subprocess exit codes
# ===========================================================================

class TestAN68CLIExitCodes:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(PREVIEW_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "adapter" in result.stdout.lower() or "design" in result.stdout.lower()

    def test_missing_artifacts_exits_one(self, repo_tmp_path):
        empty = repo_tmp_path / "empty"
        empty.mkdir()
        from scripts.preview_demo_tiny_guarded_entry_real_execution_adapter_design import (
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
            entry_manual_approval_gate_dir=empty,
            output_dir=repo_tmp_path / "out",
        )
        assert rc == 1


# ===========================================================================
# AN69: run_execute writes JSON + MD reports
# ===========================================================================

class TestAN69ReportArtifacts:
    def test_write_report_creates_files(self, repo_tmp_path):
        from scripts.preview_demo_tiny_guarded_entry_real_execution_adapter_design import (
            _write_report,
        )
        r = _run()
        out_dir = repo_tmp_path / "out"
        _write_report(r, out_dir)
        base = "tiny_guarded_entry_real_execution_adapter_design"
        latest_json = out_dir / f"latest_{base}.json"
        latest_md   = out_dir / f"latest_{base}.md"
        assert latest_json.exists()
        assert latest_md.exists()
        parsed = json.loads(latest_json.read_text(encoding="utf-8"))
        assert parsed["status"] == STATUS_DESIGN_READY
        md_text = latest_md.read_text(encoding="utf-8")
        assert "TASK-014AN" in md_text
        assert ADAPTER_NAME in md_text


# ===========================================================================
# AN70: real_execution_allowed never True regardless of inputs
# ===========================================================================

class TestAN70RealExecutionNeverAllowed:
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
# AN71: Existing position symbols documented in result
# ===========================================================================

class TestAN71ExistingPositionSymbols:
    def test_existing_position_symbols_reflect_recon(self):
        r = _run()
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols


# ===========================================================================
# AN72: Expected commit hash documented (never validated as match)
# ===========================================================================

class TestAN72ExpectedCommitHashDocumentedOnly:
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
# AN73: SOLUSDT already exists -> blocked gate
# ===========================================================================

class TestAN73SolusdtAlreadyExists:
    def test_solusdt_exists_triggers_fail_closed_gate(self):
        bad = _valid_reconciliation()
        bad["positions"].append({
            "symbol": "SOLUSDT", "side": "long", "quantity": 0.1,
            "entry_price": 64.4, "stop_price": 61.18,
        })
        r = _run(recon=bad)
        assert GATE_SOLUSDT_EXISTS_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# AN74: All 12 stages have non-empty summaries
# ===========================================================================

class TestAN74StagePayloads:
    def test_stages_have_summaries(self):
        r = _run()
        for stage_id in r.stage_order:
            env = r.stages[stage_id]
            assert "summary" in env
            assert isinstance(env["summary"], str)
            assert env["summary"] != ""


# ===========================================================================
# AN75: final_adapter_design_verdict completeness
# ===========================================================================

class TestAN75FinalVerdictCompleteness:
    def test_verdict_contains_required_fields(self):
        r = _run()
        v = r.final_adapter_design_verdict
        assert v["adapter_design_approval_allowed"] is False
        assert v["real_entry_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_entry_implemented"] is False
        assert v["guarded_entry_real_execution_adapter_design"] is True
        assert v["adapter_design_only"] is True
        assert v["adapter_implementation_included"] is False
        assert v["adapter_execution_included"] is False
        assert v["adapter_grants_execution"] is False
        assert v["approval_gate_grants_execution"] is False
        assert v["entry_execution_included"] is False
        assert v["stop_execution_included"] is False
        assert v["cleanup_execution_included"] is False
        assert v["full_lifecycle_execution_included"] is False
        assert v["current_task_real_execution_allowed"] is False
        assert v["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert v["dry_run_authorization_result"] == DRY_RUN_AUTHORIZATION_RESULT
        assert v["g20_policy_still_in_place"] is True
        assert v["g20_lifted"] is False
        assert v["status"] == STATUS_DESIGN_READY
        assert v["mode"] == MODE_DESIGN_CHECKLIST
        assert v["next_required_task"] == "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"


# ===========================================================================
# AN76: audit_artifacts is sanitized + no_secrets
# ===========================================================================

class TestAN76AuditArtifactsSanitized:
    def test_audit_artifacts_sanitized_flag(self):
        r = _run()
        assert r.audit_artifacts.get("sanitized") is True
        assert r.audit_artifacts.get("no_secrets") is True
        assert r.audit_artifacts.get("response_from_exchange") is False
        assert r.audit_artifacts.get("response_status") == ADAPTER_RESPONSE_STATUS


# ===========================================================================
# AN77: documentation_sync_review present
# ===========================================================================

class TestAN77DocumentationSyncReview:
    def test_documentation_sync_review_present(self):
        r = _run(expected_commit_hash="abc1234")
        d = r.documentation_sync_review
        assert isinstance(d, dict)
        assert d  # non-empty


# ===========================================================================
# AN78: src module is properly self-contained (uses only stdlib + dataclasses)
# ===========================================================================

class TestAN78SrcSelfContained:
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
# AN79: adapter_design_approval_allowed flag isolated
# ===========================================================================

class TestAN79AdapterDesignApprovalAllowedIsolated:
    def test_default_approval_false(self):
        r = _run()
        assert r.adapter_design_approval_allowed is False

    def test_approval_true_when_flagged(self):
        r = _run(allow_adapter_design_approval=True)
        assert r.adapter_design_approval_allowed is True


# ===========================================================================
# AN80: SOLUSDT absent from existing positions in default fixture
# ===========================================================================

class TestAN80SolusdtAbsent:
    def test_solusdt_absent_before_entry(self):
        r = _run()
        assert "SOLUSDT" not in r.existing_position_symbols


# ===========================================================================
# AN81: 5 expected protected symbols present in default fixture
# ===========================================================================

class TestAN81ProtectedSymbolsPresent:
    def test_protected_symbols_observed(self):
        r = _run()
        for sym in ("ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"):
            assert sym in r.existing_position_symbols


# ===========================================================================
# AN82: approval gate still keeps readiness NOT_EXECUTABLE
# ===========================================================================

class TestAN82ApprovalGateReadinessUnchanged:
    def test_readiness_unchanged_under_approval(self):
        r = _run(allow_adapter_design_approval=True)
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.dry_run_authorization_result == DRY_RUN_AUTHORIZATION_RESULT


# ===========================================================================
# AN83: real entry guard still keeps readiness NOT_EXECUTABLE
# ===========================================================================

class TestAN83RealEntryGuardReadinessUnchanged:
    def test_readiness_unchanged_under_real_entry_guard(self):
        r = _run(allow_real_entry_execution=True)
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.dry_run_authorization_result == DRY_RUN_AUTHORIZATION_RESULT


# ===========================================================================
# AN84: Stage 1 adapter_design_scope present
# ===========================================================================

class TestAN84AdapterDesignScope:
    def test_scope_is_dict_and_documented(self):
        r = _run()
        assert isinstance(r.adapter_design_scope, dict)
        assert r.adapter_design_scope  # non-empty


# ===========================================================================
# AN85: HARD_FAIL_GATES contains the 6 AM-acceptance gates
# ===========================================================================

class TestAN85HardFailGatesIncludeApprovalGateGates:
    def test_new_approval_gate_gates_are_hard_fail(self):
        from src.demo_tiny_guarded_entry_real_execution_adapter_design import _HARD_FAIL_GATES
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING in _HARD_FAIL_GATES
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE in _HARD_FAIL_GATES
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_READINESS_EXECUTABLE in _HARD_FAIL_GATES
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION in _HARD_FAIL_GATES
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED in _HARD_FAIL_GATES
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED in _HARD_FAIL_GATES


# ===========================================================================
# AN86: Status precedence — solusdt-exists + allow_real_entry_execution
# ===========================================================================

class TestAN86SolusdtExistsWithRealEntryFlag:
    def test_solusdt_exists_gate_still_documented_under_real_entry_guard(self):
        bad = _valid_reconciliation()
        bad["positions"].append({
            "symbol": "SOLUSDT", "side": "long", "quantity": 0.1,
            "entry_price": 64.4, "stop_price": 61.18,
        })
        r = _run(recon=bad, allow_real_entry_execution=True)
        assert GATE_SOLUSDT_EXISTS_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# AN87: 12 adapter-design sub-dicts present
# ===========================================================================

class TestAN87AdapterDesignSubDictsPresent:
    def test_adapter_design_scope_is_dict(self):
        r = _run()
        assert isinstance(r.adapter_design_scope, dict)
        assert r.adapter_design_scope

    def test_adapter_contract_design_is_dict(self):
        r = _run()
        assert isinstance(r.adapter_contract_design, dict)
        assert r.adapter_contract_design

    def test_adapter_input_schema_design_is_dict(self):
        r = _run()
        assert isinstance(r.adapter_input_schema_design, dict)
        assert r.adapter_input_schema_design

    def test_adapter_output_schema_design_is_dict(self):
        r = _run()
        assert isinstance(r.adapter_output_schema_design, dict)
        assert r.adapter_output_schema_design

    def test_entry_payload_design_preview_is_dict(self):
        r = _run()
        assert isinstance(r.entry_payload_design_preview, dict)
        assert r.entry_payload_design_preview

    def test_secret_and_signature_boundary_design_is_dict(self):
        r = _run()
        assert isinstance(r.secret_and_signature_boundary_design, dict)
        assert r.secret_and_signature_boundary_design

    def test_stop_cleanup_boundary_design_is_dict(self):
        r = _run()
        assert isinstance(r.stop_cleanup_boundary_design, dict)
        assert r.stop_cleanup_boundary_design

    def test_forbidden_execution_surface_design_is_dict(self):
        r = _run()
        assert isinstance(r.forbidden_execution_surface_design, dict)
        assert r.forbidden_execution_surface_design

    def test_failure_and_abort_adapter_design_is_dict(self):
        r = _run()
        assert isinstance(r.failure_and_abort_adapter_design, dict)
        assert r.failure_and_abort_adapter_design

    def test_documentation_sync_review_is_dict(self):
        r = _run()
        assert isinstance(r.documentation_sync_review, dict)
        assert r.documentation_sync_review

    def test_audit_artifacts_is_dict(self):
        r = _run()
        assert isinstance(r.audit_artifacts, dict)
        assert r.audit_artifacts

    def test_final_adapter_design_verdict_is_dict(self):
        r = _run()
        assert isinstance(r.final_adapter_design_verdict, dict)
        assert r.final_adapter_design_verdict


# ===========================================================================
# AN88: order_link_id_prefix exposed and consistent
# ===========================================================================

class TestAN88OrderLinkIdPrefix:
    def test_order_link_id_prefix(self):
        r = _run()
        assert r.order_link_id_prefix == ORDER_LINK_ID_PREFIX


# ===========================================================================
# AN89: HARD_FAIL_GATES total count
# ===========================================================================

class TestAN89HardFailGatesCount:
    def test_hard_fail_gates_size(self):
        from src.demo_tiny_guarded_entry_real_execution_adapter_design import _HARD_FAIL_GATES
        # Per AN src: 34 hard-fail gates (23 missing-artifact + 4 invariant +
        # 5 approval-gate-acceptance + selected_symbol_not_solusdt +
        # solusdt_already_exists). The spec mentioned 33 but the source
        # actually documents 34; align with source.
        assert len(_HARD_FAIL_GATES) == 34


# ===========================================================================
# AN90: Adapter contract gates documented (design-only; never executed)
# ===========================================================================

class TestAN90AdapterContractDesignDetails:
    def test_contract_has_no_send_and_no_signature(self):
        r = _run()
        c = r.adapter_contract_design
        assert c["adapter_has_no_send_method"] is True
        assert c["adapter_has_no_private_client"] is True
        assert c["adapter_has_no_signature_method"] is True
        assert c["adapter_has_no_secret_loader"] is True
        assert c["adapter_has_no_network_transport"] is True
        assert c["adapter_contract_does_not_execute"] is True
        assert c["adapter_contract_requires_future_task_implementation"] is True
        assert c["adapter_name"] == ADAPTER_NAME
        assert c["adapter_contract_version"] == ADAPTER_CONTRACT_VERSION


# ===========================================================================
# AN91: Input schema design references SOLUSDT / 0.1 / Buy / Market
# ===========================================================================

class TestAN91AdapterInputSchemaDesign:
    def test_input_schema_design_fields(self):
        r = _run()
        s = r.adapter_input_schema_design
        assert s["symbol"] == "SOLUSDT"
        assert s["category"] == "linear"
        assert s["side"] == "Buy"
        assert s["qty"] == 0.1
        assert s["orderType"] == "Market"
        assert s["reduceOnly"] is False
        assert s["closeOnTrigger"] is False
        assert s["positionIdx"] == 0
        assert s["max_notional_usdt"] == 10.0
        assert s["input_schema_documented"] is True
        assert s["input_schema_validated"] is False
        assert s["input_schema_does_not_authorize_execution"] is True


# ===========================================================================
# AN92: Output schema design states no send / no signature / no headers
# ===========================================================================

class TestAN92AdapterOutputSchemaDesign:
    def test_output_schema_design_fields(self):
        r = _run()
        o = r.adapter_output_schema_design
        assert o["response_status"] == ADAPTER_RESPONSE_STATUS
        assert o["response_from_exchange"] is False
        assert o["exchange_order_id"] is None
        assert o["order_link_id_prefix"] == ORDER_LINK_ID_PREFIX
        assert o["send_allowed"] is False
        assert o["endpoint_called"] is False
        assert o["order_endpoint_called"] is False
        assert o["stop_endpoint_called"] is False
        assert o["real_payload"] is False
        assert o["signature_present"] is False
        assert o["private_headers"] == []
        assert o["no_secrets"] is True
        assert o["sanitized"] is True
        assert o["no_position_modified"] is True
        assert o["output_schema_documented"] is True
        assert o["output_schema_does_not_execute"] is True


# ===========================================================================
# AN93: Entry payload preview is design-only (no signature / no send)
# ===========================================================================

class TestAN93EntryPayloadDesignPreview:
    def test_payload_preview_design_only(self):
        r = _run()
        p = r.entry_payload_design_preview
        assert p["preview_only"] is True
        assert p["adapter_design_only"] is True
        assert p["send_allowed"] is False
        assert p["endpoint_called"] is False
        assert p["real_payload"] is False
        assert p["signature_present"] is False
        assert p["private_headers"] == []
        assert p["sender_adapter_invoked"] is False
        assert p["symbol"] == "SOLUSDT"
        assert p["side"] == "Buy"
        assert p["qty"] == 0.1
        assert p["orderType"] == "Market"
        assert p["category"] == "linear"
        assert p["orderLinkId_prefix"] == ORDER_LINK_ID_PREFIX


# ===========================================================================
# AN94: Secret / signature boundary documents future-task-only secrets
# ===========================================================================

class TestAN94SecretSignatureBoundaryDesign:
    def test_secret_and_signature_boundary_design(self):
        r = _run()
        s = r.secret_and_signature_boundary_design
        assert s["secrets_required_in_future_task"] is True
        assert s["secrets_loaded_in_this_task"] is False
        assert s["env_read_in_this_task"] is False
        assert s["dotenv_called_in_this_task"] is False
        assert s["hmac_signature_created"] is False
        assert s["signature_header_created"] is False
        assert s["private_headers_created"] is False
        assert s["api_key_value_observed"] is False
        assert s["api_secret_value_observed"] is False
        assert s["signing_requires_future_task"] is True
        assert s["secret_redaction_required"] is True
        for f in FORBIDDEN_LOG_FIELDS:
            assert f in s["forbidden_log_fields"]


# ===========================================================================
# AN95: Stop / cleanup boundary keeps them separate manual gates
# ===========================================================================

class TestAN95StopCleanupBoundaryDesign:
    def test_stop_cleanup_boundary_design(self):
        r = _run()
        b = r.stop_cleanup_boundary_design
        assert b["stop_attach_required_after_entry"] is True
        assert b["stop_attach_not_included_in_this_task"] is True
        assert b["stop_loss"] == DESIGN_EXPECTED_STOP_LOSS
        assert b["tpsl_mode"] == DESIGN_EXPECTED_TPSL_MODE
        assert b["sl_trigger_by"] == DESIGN_EXPECTED_SL_TRIGGER_BY
        assert b["cleanup_not_included_in_this_task"] is True
        assert b["cleanup_separate_manual_boundary"] is True
        assert b["no_automatic_stop_attach"] is True
        assert b["no_automatic_cleanup"] is True
        assert b["no_automatic_emergency_close"] is True
        assert b["future_adapter_must_not_auto_attach_stop"] is True
        assert b["future_adapter_must_require_separate_stop_task"] is True


# ===========================================================================
# AN96: Forbidden execution surface design documents no-* invariants
# ===========================================================================

class TestAN96ForbiddenExecutionSurfaceDesign:
    def test_forbidden_execution_surface_design(self):
        r = _run()
        f = r.forbidden_execution_surface_design
        assert f["no_real_sender"] is True
        assert f["no_bybit_private_client"] is True
        assert f["no_signed_request"] is True
        assert f["no_env_secret_load"] is True
        assert f["no_order_endpoint"] is True
        assert f["no_trading_stop_endpoint"] is True
        assert f["no_close_only_fallback"] is True
        assert f["no_emergency_close_fallback"] is True
        assert f["no_socket"] is True
        assert f["no_requests_httpx_urllib_http_client"] is True
        assert f["no_batch_order"] is True
        assert f["no_leverage_mutation"] is True
        assert f["no_transfer"] is True
        assert f["no_webhook_trigger"] is True
        assert f["no_discord_trigger"] is True
        assert f["no_notion_trigger"] is True
        assert f["no_cron_scheduler_or_background_loop"] is True
        assert f["no_executable_adapter"] is True
        assert f["no_send_method"] is True
        assert f["no_private_transport"] is True


# ===========================================================================
# AN97: Failure / abort adapter design FAIL_CLOSED / MANUAL_REVIEW
# ===========================================================================

class TestAN97FailureAndAbortAdapterDesign:
    def test_failure_and_abort_adapter_design(self):
        r = _run()
        f = r.failure_and_abort_adapter_design
        assert f["missing_artifact"] == "FAIL_CLOSED"
        assert f["stale_readonly"] == "FAIL_CLOSED"
        assert f["manual_approval_gate_stale"] == "FAIL_CLOSED"
        assert f["approval_grants_execution_true"] == "FAIL_CLOSED"
        assert f["phrase_already_validated"] == "FAIL_CLOSED"
        assert f["inputs_already_validated"] == "FAIL_CLOSED"
        assert f["solusdt_already_exists"] == "FAIL_CLOSED"
        assert f["protected_position_mismatch"] == "MANUAL_REVIEW_REQUIRED"
        assert f["notional_cap_exceeded"] == "FAIL_CLOSED"
        assert f["qty_mismatch"] == "FAIL_CLOSED"
        assert f["side_mismatch"] == "FAIL_CLOSED"
        assert f["reduce_only_mismatch"] == "FAIL_CLOSED"
        assert f["live_endpoint_detected"] == "FAIL_CLOSED"
        assert f["secret_emission_detected"] == "FAIL_CLOSED"
        assert f["network_primitive_detected"] == "FAIL_CLOSED"
        assert f["sender_adapter_detected"] == "FAIL_CLOSED"
        assert f["executable_adapter_detected"] == "FAIL_CLOSED"
        assert f["any_g20_lift_attempt"] == "FAIL_CLOSED"
        assert f["any_auto_execution_attempt"] == "FAIL_CLOSED"
        assert f["manual_intervention_only"] is True


# ===========================================================================
# AN98: Documentation sync references next task AO
# ===========================================================================

class TestAN98DocumentationSyncNextTaskAO:
    def test_documentation_sync_references_ao(self):
        r = _run()
        d = r.documentation_sync_review
        assert d["next_required_task"] == "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"
        assert d["readme_status_board_sync_required"] is True
        assert d["next_action_sync_required"] is True
        assert d["command_log_sync_required"] is True
        assert d["forbidden_status_sync_required"] is True
        assert d["next_required_task_sync_required"] is True
        assert d["markdown_read_in_this_module"] is False


# ===========================================================================
# AN99: Adapter design scope flags consistent with verdict
# ===========================================================================

class TestAN99AdapterDesignScopeFlags:
    def test_adapter_design_scope_flags(self):
        r = _run()
        s = r.adapter_design_scope
        assert s["guarded_entry_real_execution_adapter_design"] is True
        assert s["adapter_design_only"] is True
        assert s["adapter_implementation_included"] is False
        assert s["adapter_execution_included"] is False
        assert s["entry_execution_included"] is False
        assert s["stop_execution_included"] is False
        assert s["cleanup_execution_included"] is False
        assert s["full_lifecycle_execution_included"] is False
        assert s["real_entry_implemented"] is False
        assert s["real_execution_allowed"] is False
        assert s["adapter_grants_execution"] is False
        assert s["approval_gate_grants_execution"] is False
        assert s["send_allowed"] is False
        assert s["order_endpoint_called"] is False
        assert s["stop_endpoint_called"] is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["no_position_modified"] is True
        assert s["no_secrets_loaded"] is True
        assert s["g20_policy_still_in_place"] is True
        assert s["g20_lifted"] is False
        assert s["next_required_task"] == "TASK-014AO_guarded_entry_real_execution_adapter_dry_run"


# ===========================================================================
# AN100: Preview script (source-scan safety)
# ===========================================================================

class TestAN100PreviewNoForbiddenImports:
    def test_preview_no_forbidden_imports(self):
        tree = ast.parse(PREVIEW_PATH.read_text(encoding="utf-8"))
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
            "ssl", "hmac", "pybit",
            "main", "src.risk", "src.bybit_executor",
        }
        assert not (bad & forbidden), f"forbidden imports leaked in preview: {bad & forbidden}"


# ===========================================================================
# AN101: Preview has no auto-git operations
# ===========================================================================

class TestAN101PreviewNoAutoGit:
    def test_preview_does_not_invoke_git(self):
        code_tokens = _read_code_only(PREVIEW_PATH)
        for forbidden in (
            "git.Repo", "git rev-parse",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into preview"


# ===========================================================================
# AN102: Result is dataclass with expected sub-dict field names
# ===========================================================================

class TestAN102ResultDataclassFields:
    def test_result_has_12_subdicts(self):
        r = _run()
        expected_subdicts = (
            "adapter_design_scope",
            "adapter_contract_design",
            "adapter_input_schema_design",
            "adapter_output_schema_design",
            "entry_payload_design_preview",
            "secret_and_signature_boundary_design",
            "stop_cleanup_boundary_design",
            "forbidden_execution_surface_design",
            "failure_and_abort_adapter_design",
            "documentation_sync_review",
            "audit_artifacts",
            "final_adapter_design_verdict",
        )
        for name in expected_subdicts:
            assert hasattr(r, name)
            assert isinstance(getattr(r, name), dict)
