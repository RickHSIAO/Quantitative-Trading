"""
tests/demo_trading/test_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py
TASK-014AR: Guarded Tiny Entry Real Execution Adapter Implementation
            Design tests.

Covers implementation_design_checklist / implementation_design_approval /
real_entry_execution_guard / fail_closed paths; all 14 stages; 26-artifact
preflight contract (the 25 from TASK-014AP + AP's own
implementation_readiness_review output); 16 acceptable upstream status
frozensets; ~54 HARD_FAIL_GATES; deep-copy roundtrip via to_dict;
implementation-design-only template (no sender adapter, no `send` method,
signature_present False, private_headers empty, send_allowed False);
failure / abort design documented (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED);
documentation sync plan (commit hash documented only, NO auto-commit /
NO auto-push); status precedence; source-scan safety (AST + tokenize:
no urllib / requests / httpx / socket / http.client / hmac / hashlib /
dotenv / os.environ / sender / main / risk / BybitExecutor / pybit /
executable adapter `send` method / forbidden flags / AA-AP module reuse /
auto-git); report artifacts; forbidden-flag absence (--execute-real-* /
--send-order / --place-order / --real-run / --confirm-token /
--auto-commit / --git-commit / --auto-push / --git-push); G20 never
lifted; 5 protected positions never touched; next_required_task =
TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run.
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
    d = root / f"aq_{uuid.uuid4().hex}"
    d.mkdir()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)


from src.demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design import (
    ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES,
    ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES,
    ACCEPTABLE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_STATUSES,
    ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES,
    ACCEPTABLE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUSES,
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
    CONSUMED_DESIGN_CONTRACT_VERSION,
    CONSUMED_DRY_RUN_CONTRACT_VERSION,
    CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION,
    CONSUMED_READINESS_CONTRACT_VERSION,
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
    DemoTinyGuardedEntryRealExecutionAdapterStaticSkeletonDesign,
    ENDPOINT_PATH_REF,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    STATIC_SKELETON_DESIGN_AUTHORIZATION_RESULT,
    STATIC_SKELETON_DESIGN_CONCLUSION,
    LIVE_ENDPOINT_DENYLIST,
    MODE_FAIL_CLOSED,
    MODE_IMPLEMENTATION_DESIGN_APPROVAL,
    MODE_IMPLEMENTATION_DESIGN_CHECKLIST,
    MODE_REAL_ENTRY_EXEC_GUARD,
    NEXT_REQUIRED_TASK,
    ORDER_CREATE_PATH_REF,
    ORDER_LINK_ID_PREFIX,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_IMPLEMENTATION_DESIGN_SCOPE,
    STAGE_2_STATIC_MODULE_BOUNDARY_DESIGN,
    STAGE_3_REQUEST_CONSTRUCTION_DESIGN,
    STAGE_4_TRANSPORT_AND_ENDPOINT_DESIGN,
    STAGE_5_SECRET_AND_SIGNING_DESIGN,
    STAGE_6_RESPONSE_AND_ERROR_HANDLING_DESIGN,
    STAGE_7_MANUAL_APPROVAL_AND_AUTHORIZATION_DESIGN,
    STAGE_8_STOP_CLEANUP_HANDOFF_DESIGN,
    STAGE_9_RISK_IDEMPOTENCY_AND_AUDIT_DESIGN,
    STAGE_10_FORBIDDEN_IMPLEMENTATION_SURFACE_DESIGN,
    STAGE_11_FAILURE_AND_ABORT_IMPLEMENTATION_DESIGN,
    STAGE_12_DOCUMENTATION_SYNC_REVIEW,
    STAGE_13_FINAL_IMPLEMENTATION_DESIGN_VERDICT,
    STATUS_FAIL_CLOSED,
    STATUS_IMPLEMENTATION_DESIGN_READY,
    STATUS_IMPLEMENTATION_DESIGN_READY_EXEC_DISABLED,
    STATUS_REAL_ENTRY_NOT_IMPL,
    TRADING_STOP_PATH_REF,
    TinyGuardedEntryRealExecutionAdapterStaticSkeletonDesignResult,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_ADAPTER_DESIGN_EXECUTION_INCLUDED,
    GATE_ENTRY_ADAPTER_DESIGN_GRANTS_EXECUTION,
    GATE_ENTRY_ADAPTER_DESIGN_IMPLEMENTATION_INCLUDED,
    GATE_ENTRY_ADAPTER_DESIGN_MISSING,
    GATE_ENTRY_ADAPTER_DESIGN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_ADAPTER_DRY_RUN_ADAPTER_GRANTS_EXECUTION,
    GATE_ENTRY_ADAPTER_DRY_RUN_EXECUTION_INCLUDED,
    GATE_ENTRY_ADAPTER_DRY_RUN_GRANTS_EXECUTION,
    GATE_ENTRY_ADAPTER_DRY_RUN_IMPLEMENTATION_INCLUDED,
    GATE_ENTRY_ADAPTER_DRY_RUN_MISSING,
    GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT,
    GATE_ENTRY_ADAPTER_DRY_RUN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_CONCLUSION_MISMATCH,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_EXECUTION_INCLUDED,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_GRANTS_EXECUTION,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_IMPLEMENTATION_INCLUDED,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_MISSING,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_RESPONSE_STATUS_UNACCEPTABLE,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_SEND_ALLOWED,
    GATE_ENTRY_IMPLEMENTATION_DESIGN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_CONCLUSION_MISMATCH,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_EXECUTION_INCLUDED,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_GRANTS_EXECUTION,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_IMPLEMENTATION_INCLUDED,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_MISSING,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_RESPONSE_STATUS_UNACCEPTABLE,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_SEND_ALLOWED,
    GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUS_UNACCEPTABLE,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING,
    GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED,
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
SRC_PATH = (
    ROOT_PATH / "src"
    / "demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py"
)
PREVIEW_PATH = (
    ROOT_PATH / "scripts"
    / "preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design.py"
)


# ===========================================================================
# Upstream fixture helpers (26)
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


def _valid_entry_adapter_design() -> dict:
    return {
        "timestamp_utc":                "2026-06-12T11:59:59.99995Z",
        "mode":                         "adapter_design_checklist",
        "selected_symbol":              "SOLUSDT",
        "status":                       "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY",
        "adapter_name":                 ADAPTER_NAME,
        "adapter_contract_version":     "design_only_v1",
        "adapter_grants_execution":     False,
        "adapter_implementation_included": False,
        "adapter_execution_included":   False,
        "approval_gate_grants_execution": False,
        "adapter_design_only":          True,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_real_execution_adapter_design": True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
        "no_secrets_loaded":                   True,
        "no_auto_git_operations":              True,
        "expected_commit_hash":         "0000000000000000000000000000000000000000",
        "next_required_task":           "TASK-014AO_guarded_entry_real_execution_adapter_dry_run",
    }


def _valid_entry_adapter_dry_run() -> dict:
    return {
        "timestamp_utc":                "2026-06-12T11:59:59.999995Z",
        "mode":                         "dry_run_checklist",
        "selected_symbol":              "SOLUSDT",
        "status":                       "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DRY_RUN_READY",
        "adapter_name":                 ADAPTER_NAME,
        "adapter_contract_version":     "dry_run_v1",
        "consumed_design_contract_version": "design_only_v1",
        "dry_run_grants_execution":     False,
        "adapter_grants_execution":     False,
        "adapter_implementation_included": False,
        "adapter_execution_included":   False,
        "no_send_method":               True,
        "adapter_dry_run_only":         True,
        "approval_gate_grants_execution": False,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_real_execution_adapter_dry_run": True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
        "no_secrets_loaded":                   True,
        "no_auto_git_operations":              True,
        "expected_commit_hash":         "0000000000000000000000000000000000000000",
        "audit_artifacts": {
            "response_status": "ADAPTER_DRY_RUN_NOT_SENT",
        },
        "forbidden_execution_surface_dry_run": {
            "no_send_method": True,
        },
        "next_required_task":           "TASK-014AP_guarded_entry_real_execution_adapter_implementation_readiness_review",
    }


def _valid_entry_implementation_readiness_review() -> dict:
    """The 26th (newest) upstream artifact: TASK-014AP's output."""
    return {
        "timestamp_utc":                "2026-06-12T11:59:59.9999995Z",
        "mode":                         "readiness_review_checklist",
        "selected_symbol":              "SOLUSDT",
        "status":                       "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_READINESS_REVIEW_READY",
        "adapter_name":                 ADAPTER_NAME,
        "adapter_contract_version":     "readiness_review_v1",
        "consumed_dry_run_contract_version": "dry_run_v1",
        "consumed_design_contract_version": "design_only_v1",
        "readiness_review_grants_execution": False,
        "adapter_implementation_included": False,
        "adapter_execution_included":   False,
        "send_allowed":                 False,
        "implementation_readiness_conclusion": "READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION",
        "readiness_review_only":        True,
        "real_execution_allowed":              False,
        "real_entry_implemented":              False,
        "guarded_entry_real_execution_adapter_implementation_readiness_review": True,
        "current_task_real_execution_allowed": False,
        "g20_policy_still_in_place":           True,
        "g20_lifted":                          False,
        "no_secrets_loaded":                   True,
        "no_auto_git_operations":              True,
        "expected_commit_hash":         "0000000000000000000000000000000000000000",
        "audit_artifacts": {
            "response_status": "READINESS_REVIEW_NOT_SENT",
        },
        "final_implementation_readiness_verdict": {
            "implementation_readiness_conclusion": "READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION",
            "readiness_review_grants_execution": False,
            "adapter_implementation_included": False,
            "adapter_execution_included": False,
            "send_allowed": False,
        },
        "next_required_task":           "TASK-014AR_guarded_entry_real_execution_adapter_implementation_design",
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


def _design() -> DemoTinyGuardedEntryRealExecutionAdapterStaticSkeletonDesign:
    return DemoTinyGuardedEntryRealExecutionAdapterStaticSkeletonDesign()


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
    entry_adapter_design=_UNSET,
    entry_adapter_dry_run=_UNSET,
    entry_implementation_readiness_review=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    expected_commit_hash="",
    current_commit_hash="",
    allow_implementation_design=False,
    allow_real_entry_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedEntryRealExecutionAdapterStaticSkeletonDesignResult:
    return _design().run_design(
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
        entry_adapter_design=_valid_entry_adapter_design()                        if entry_adapter_design                  is _UNSET else entry_adapter_design,
        entry_adapter_dry_run=_valid_entry_adapter_dry_run()                      if entry_adapter_dry_run                 is _UNSET else entry_adapter_dry_run,
        entry_implementation_readiness_review=_valid_entry_implementation_readiness_review() if entry_implementation_readiness_review is _UNSET else entry_implementation_readiness_review,
        symbol=symbol,
        expected_commit_hash=expected_commit_hash,
        current_commit_hash=current_commit_hash,
        allow_implementation_design=allow_implementation_design,
        allow_real_entry_execution=allow_real_entry_execution,
        _now=_now,
    )


# ===========================================================================
# AQ1-AQ4: Status modes
# ===========================================================================

class TestAQ1ImplementationDesignReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_IMPLEMENTATION_DESIGN_READY
        assert r.mode == MODE_IMPLEMENTATION_DESIGN_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.failed_stage == ""
        from src.demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design import _HARD_FAIL_GATES
        assert not any(g in _HARD_FAIL_GATES for g in r.blocked_gates)
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.guarded_entry_real_execution_adapter_implementation_design is True
        assert r.implementation_design_only is True
        assert r.adapter_implementation_included is False
        assert r.adapter_execution_included is False
        assert r.dry_run_grants_execution is False
        assert r.adapter_grants_execution is False
        assert r.approval_gate_grants_execution is False
        assert r.readiness_review_grants_execution is False
        assert r.implementation_design_grants_execution is False
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True
        assert r.next_required_task == NEXT_REQUIRED_TASK


class TestAQ2ImplementationDesignApproval:
    def test_approval_yields_exec_disabled(self):
        r = _run(symbol="SOLUSDT", allow_implementation_design=True)
        assert r.status == STATUS_IMPLEMENTATION_DESIGN_READY_EXEC_DISABLED
        assert r.mode == MODE_IMPLEMENTATION_DESIGN_APPROVAL
        assert r.implementation_design_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.implementation_design_conclusion == STATIC_SKELETON_DESIGN_CONCLUSION
        assert r.g20_lifted is False


class TestAQ3RealEntryExecutionGuard:
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


class TestAQ4FailClosedWrongSymbol:
    def test_wrong_symbol_fails_closed(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AQ5-AQ30: 26 missing-artifact gates
# ===========================================================================

class TestAQ5MissingReadonly:
    def test_missing_readonly_blocked(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAQ6MissingReconciliation:
    def test_missing_recon_blocked(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAQ7MissingProtection:
    def test_missing_protection_blocked(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAQ8MissingContract:
    def test_missing_contract_blocked(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAQ9MissingNoopPlan:
    def test_missing_noop_plan_blocked(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAQ10MissingLifecycle:
    def test_missing_lifecycle_blocked(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAQ11MissingRealPermissionGate:
    def test_missing_real_perm_blocked(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAQ12MissingTinyEntryPermissionGate:
    def test_missing_tiny_entry_perm_blocked(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAQ13MissingTinyStopPermissionGate:
    def test_missing_tiny_stop_perm_blocked(self):
        r = _run(tiny_stop_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAQ14MissingTinyCleanupPermissionGate:
    def test_missing_tiny_cleanup_perm_blocked(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAQ15MissingLifecycleSummary:
    def test_missing_lifecycle_summary_blocked(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAQ16MissingRunnerDesign:
    def test_missing_runner_design_blocked(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAQ17MissingRunnerDryRun:
    def test_missing_runner_dry_run_blocked(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAQ18MissingGuardedDesignReview:
    def test_missing_guarded_design_review_blocked(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAQ19MissingGuardedEntryAdapter:
    def test_missing_guarded_entry_adapter_blocked(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAQ20MissingGuardedStopAdapter:
    def test_missing_guarded_stop_adapter_blocked(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


class TestAQ21MissingGuardedCleanupAdapter:
    def test_missing_guarded_cleanup_adapter_blocked(self):
        r = _run(guarded_cleanup_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in r.blocked_gates


class TestAQ22MissingGuardedLifecycleSummary:
    def test_missing_guarded_lifecycle_summary_blocked(self):
        r = _run(guarded_lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAQ23MissingEntryRealPermissionReview:
    def test_missing_entry_real_perm_review_blocked(self):
        r = _run(entry_real_permission_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING in r.blocked_gates


class TestAQ24MissingEntryManualAuthDesign:
    def test_missing_entry_manual_auth_design_blocked(self):
        r = _run(entry_manual_authorization_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING in r.blocked_gates


class TestAQ25MissingEntryManualAuthDryRun:
    def test_missing_entry_manual_auth_dry_run_blocked(self):
        r = _run(entry_manual_authorization_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DRY_RUN_MISSING in r.blocked_gates


class TestAQ26MissingEntryFinalPreExecutionReview:
    def test_missing_entry_final_pre_execution_review_blocked(self):
        r = _run(entry_final_pre_execution_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_FINAL_PRE_EXECUTION_REVIEW_MISSING in r.blocked_gates


class TestAQ27MissingEntryManualApprovalGate:
    def test_missing_entry_manual_approval_gate_blocked(self):
        r = _run(entry_manual_approval_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_MISSING in r.blocked_gates


class TestAQ28MissingEntryAdapterDesign:
    def test_missing_entry_adapter_design_blocked(self):
        r = _run(entry_adapter_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DESIGN_MISSING in r.blocked_gates


class TestAQ29MissingEntryAdapterDryRun:
    def test_missing_entry_adapter_dry_run_blocked(self):
        r = _run(entry_adapter_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DRY_RUN_MISSING in r.blocked_gates


class TestAQ30MissingEntryImplementationReadinessReview:
    """The 26th (newest) upstream artifact: TASK-014AP's output."""
    def test_missing_entry_implementation_readiness_review_blocked(self):
        r = _run(entry_implementation_readiness_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_MISSING in r.blocked_gates


# ===========================================================================
# AQ31-AQ34: Endpoint / account / symbol invariants
# ===========================================================================

class TestAQ31EndpointFamilyMismatch:
    def test_wrong_endpoint_family_blocked(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAQ32AccountModeMismatch:
    def test_wrong_account_mode_blocked(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAQ33WrongSymbol:
    def test_wrong_symbol_blocked(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


class TestAQ34SolusdtAlreadyExists:
    def test_solusdt_exists_triggers_fail_closed_gate(self):
        bad = _valid_reconciliation()
        bad["positions"].append({
            "symbol": "SOLUSDT", "side": "long", "quantity": 0.1,
            "entry_price": 64.4, "stop_price": 61.18,
        })
        r = _run(recon=bad)
        assert GATE_SOLUSDT_EXISTS_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# AQ35-AQ38: AM manual-approval-gate acceptance gates (4)
# ===========================================================================

class TestAQ35EntryManualApprovalGateStatusUnacceptable:
    def test_unacceptable_status_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["status"] = "SOMETHING_UNEXPECTED"
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_STATUS_UNACCEPTABLE in r.blocked_gates


class TestAQ36EntryManualApprovalGateGrantsExecution:
    def test_grants_execution_true_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["approval_grants_execution"] = True
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_GRANTS_EXECUTION in r.blocked_gates


class TestAQ37EntryManualApprovalGatePhraseAlreadyValidated:
    def test_phrase_validated_true_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["exact_phrase_validated"] = True
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_PHRASE_ALREADY_VALIDATED in r.blocked_gates


class TestAQ38EntryManualApprovalGateInputsAlreadyValidated:
    def test_inputs_validated_true_blocked(self):
        bad = _valid_entry_manual_approval_gate()
        bad["approval_inputs_validated"] = True
        r = _run(entry_manual_approval_gate=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_APPROVAL_GATE_INPUTS_ALREADY_VALIDATED in r.blocked_gates


# ===========================================================================
# AQ39-AQ42: AN adapter-design acceptance gates (4)
# ===========================================================================

class TestAQ39EntryAdapterDesignStatusUnacceptable:
    def test_unacceptable_status_blocked(self):
        bad = _valid_entry_adapter_design()
        bad["status"] = "SOMETHING_UNEXPECTED"
        r = _run(entry_adapter_design=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DESIGN_STATUS_UNACCEPTABLE in r.blocked_gates


class TestAQ40EntryAdapterDesignGrantsExecution:
    def test_grants_execution_true_blocked(self):
        bad = _valid_entry_adapter_design()
        bad["adapter_grants_execution"] = True
        r = _run(entry_adapter_design=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DESIGN_GRANTS_EXECUTION in r.blocked_gates


class TestAQ41EntryAdapterDesignImplementationIncluded:
    def test_implementation_included_blocked(self):
        bad = _valid_entry_adapter_design()
        bad["adapter_implementation_included"] = True
        r = _run(entry_adapter_design=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DESIGN_IMPLEMENTATION_INCLUDED in r.blocked_gates


class TestAQ42EntryAdapterDesignExecutionIncluded:
    def test_execution_included_blocked(self):
        bad = _valid_entry_adapter_design()
        bad["adapter_execution_included"] = True
        r = _run(entry_adapter_design=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DESIGN_EXECUTION_INCLUDED in r.blocked_gates


# ===========================================================================
# AQ43-AQ48: AO adapter-dry-run acceptance gates (6)
# ===========================================================================

class TestAQ43EntryAdapterDryRunStatusUnacceptable:
    def test_unacceptable_status_blocked(self):
        bad = _valid_entry_adapter_dry_run()
        bad["status"] = "SOMETHING_UNEXPECTED"
        r = _run(entry_adapter_dry_run=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DRY_RUN_STATUS_UNACCEPTABLE in r.blocked_gates


class TestAQ44EntryAdapterDryRunGrantsExecution:
    def test_dry_run_grants_execution_true_blocked(self):
        bad = _valid_entry_adapter_dry_run()
        bad["dry_run_grants_execution"] = True
        r = _run(entry_adapter_dry_run=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DRY_RUN_GRANTS_EXECUTION in r.blocked_gates


class TestAQ45EntryAdapterDryRunAdapterGrantsExecution:
    def test_adapter_grants_execution_true_blocked(self):
        bad = _valid_entry_adapter_dry_run()
        bad["adapter_grants_execution"] = True
        r = _run(entry_adapter_dry_run=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DRY_RUN_ADAPTER_GRANTS_EXECUTION in r.blocked_gates


class TestAQ46EntryAdapterDryRunImplementationIncluded:
    def test_implementation_included_blocked(self):
        bad = _valid_entry_adapter_dry_run()
        bad["adapter_implementation_included"] = True
        r = _run(entry_adapter_dry_run=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DRY_RUN_IMPLEMENTATION_INCLUDED in r.blocked_gates


class TestAQ47EntryAdapterDryRunExecutionIncluded:
    def test_execution_included_blocked(self):
        bad = _valid_entry_adapter_dry_run()
        bad["adapter_execution_included"] = True
        r = _run(entry_adapter_dry_run=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DRY_RUN_EXECUTION_INCLUDED in r.blocked_gates


class TestAQ48EntryAdapterDryRunSendMethodPresent:
    def test_no_send_method_false_blocked(self):
        bad = _valid_entry_adapter_dry_run()
        bad["no_send_method"] = False
        r = _run(entry_adapter_dry_run=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT in r.blocked_gates


# ===========================================================================
# AQ49-AQ55: AP implementation-readiness-review acceptance gates (7, NEW)
# ===========================================================================

class TestAQ49EntryImplementationReadinessReviewStatusUnacceptable:
    def test_unacceptable_status_blocked(self):
        bad = _valid_entry_implementation_readiness_review()
        bad["status"] = "SOMETHING_UNEXPECTED"
        r = _run(entry_implementation_readiness_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUS_UNACCEPTABLE in r.blocked_gates


class TestAQ50EntryImplementationReadinessReviewGrantsExecution:
    def test_readiness_review_grants_execution_true_blocked(self):
        bad = _valid_entry_implementation_readiness_review()
        bad["readiness_review_grants_execution"] = True
        r = _run(entry_implementation_readiness_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_GRANTS_EXECUTION in r.blocked_gates


class TestAQ51EntryImplementationReadinessReviewImplementationIncluded:
    def test_implementation_included_blocked(self):
        bad = _valid_entry_implementation_readiness_review()
        bad["adapter_implementation_included"] = True
        r = _run(entry_implementation_readiness_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_IMPLEMENTATION_INCLUDED in r.blocked_gates


class TestAQ52EntryImplementationReadinessReviewExecutionIncluded:
    def test_execution_included_blocked(self):
        bad = _valid_entry_implementation_readiness_review()
        bad["adapter_execution_included"] = True
        r = _run(entry_implementation_readiness_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_EXECUTION_INCLUDED in r.blocked_gates


class TestAQ53EntryImplementationReadinessReviewSendAllowed:
    def test_send_allowed_true_blocked(self):
        bad = _valid_entry_implementation_readiness_review()
        bad["send_allowed"] = True
        r = _run(entry_implementation_readiness_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_SEND_ALLOWED in r.blocked_gates


class TestAQ54EntryImplementationReadinessReviewConclusionMismatch:
    def test_conclusion_mismatch_blocked(self):
        bad = _valid_entry_implementation_readiness_review()
        bad["implementation_readiness_conclusion"] = "SOMETHING_ELSE"
        bad["final_implementation_readiness_verdict"] = {
            "implementation_readiness_conclusion": "SOMETHING_ELSE",
            "readiness_review_grants_execution": False,
            "adapter_implementation_included": False,
            "adapter_execution_included": False,
            "send_allowed": False,
        }
        r = _run(entry_implementation_readiness_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_CONCLUSION_MISMATCH in r.blocked_gates


class TestAQ55EntryImplementationReadinessReviewResponseStatusUnacceptable:
    def test_response_status_mismatch_blocked(self):
        bad = _valid_entry_implementation_readiness_review()
        bad["audit_artifacts"] = {"response_status": "SOMETHING_ELSE"}
        r = _run(entry_implementation_readiness_review=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_RESPONSE_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AQ56: Stage presence + order (14 stages)
# ===========================================================================

class TestAQ56StageOrder:
    def test_stages_present_in_order(self):
        r = _run()
        assert r.stage_order == list(ALL_STAGES)
        assert r.stage_order == [
            STAGE_0_ARTIFACT_PREFLIGHT,
            STAGE_1_IMPLEMENTATION_DESIGN_SCOPE,
            STAGE_2_STATIC_MODULE_BOUNDARY_DESIGN,
            STAGE_3_REQUEST_CONSTRUCTION_DESIGN,
            STAGE_4_TRANSPORT_AND_ENDPOINT_DESIGN,
            STAGE_5_SECRET_AND_SIGNING_DESIGN,
            STAGE_6_RESPONSE_AND_ERROR_HANDLING_DESIGN,
            STAGE_7_MANUAL_APPROVAL_AND_AUTHORIZATION_DESIGN,
            STAGE_8_STOP_CLEANUP_HANDOFF_DESIGN,
            STAGE_9_RISK_IDEMPOTENCY_AND_AUDIT_DESIGN,
            STAGE_10_FORBIDDEN_IMPLEMENTATION_SURFACE_DESIGN,
            STAGE_11_FAILURE_AND_ABORT_IMPLEMENTATION_DESIGN,
            STAGE_12_DOCUMENTATION_SYNC_REVIEW,
            STAGE_13_FINAL_IMPLEMENTATION_DESIGN_VERDICT,
        ]
        for stage_id in r.stage_order:
            assert stage_id in r.stages
            assert "summary" in r.stages[stage_id]

    def test_fourteen_stages(self):
        assert len(ALL_STAGES) == 14


# ===========================================================================
# AQ57: Deep-copy roundtrip + to_dict
# ===========================================================================

class TestAQ57DictRoundtrip:
    def test_to_dict_is_json_serializable(self):
        r = _run()
        d = r.to_dict()
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["status"] == STATUS_IMPLEMENTATION_DESIGN_READY
        assert parsed["selected_symbol"] == "SOLUSDT"
        assert parsed["g20_lifted"] is False
        assert parsed["real_entry_implemented"] is False
        assert parsed["implementation_design_only"] is True
        assert parsed["guarded_entry_real_execution_adapter_implementation_design"] is True
        assert parsed["next_required_task"] == NEXT_REQUIRED_TASK

    def test_to_dict_is_deep_copied(self):
        r = _run()
        d1 = r.to_dict()
        d2 = r.to_dict()
        d1["stages"]["mutated"] = True
        assert "mutated" not in d2["stages"]
        d1["existing_position_symbols"].append("FAKE")
        assert "FAKE" not in d2["existing_position_symbols"]


# ===========================================================================
# AQ58-AQ63: Source-scan safety
# ===========================================================================

class TestAQ58NoForbiddenImports:
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
            # AA-AP module reuse forbidden
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
            "src.demo_tiny_guarded_entry_real_execution_adapter_design",
            "src.demo_tiny_guarded_entry_real_execution_adapter_dry_run",
            "src.demo_tiny_guarded_entry_real_execution_adapter_implementation_readiness_review",
        }
        assert not (bad & forbidden), f"forbidden imports leaked: {bad & forbidden}"


class TestAQ59NoNetworkSymbols:
    def test_no_socket_or_urlopen_or_http_client_in_code(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "urlopen", "Request", "HTTPSConnection", "HTTPConnection",
            "socket.socket", "ssl.create_default_context",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAQ60NoEnvOrDotenvReads:
    def test_no_environ_or_dotenv_calls(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "os.environ", "environ", "getenv",
            "load_dotenv", "dotenv_values",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAQ61NoSigningTokens:
    def test_no_hmac_or_signature_construction(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "hmac.new", "hashlib.sha256", "hashlib.sha512",
            "X-BAPI-SIGN", "X-BAPI-API-KEY",
            "BybitExecutor(",
            "pybit.unified_trading", "HTTP(",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAQ62NoRealSenderInvocation:
    def test_no_order_or_stop_endpoint_call(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "place_order", "submit_order", "send_order",
            "set_trading_stop", "amend_order", "cancel_order",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAQ63PathRefsAreStringConstants:
    def test_endpoint_paths_only_appear_as_string_constants(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        assert ORDER_CREATE_PATH_REF in text
        assert TRADING_STOP_PATH_REF in text
        code_tokens = _read_code_only(SRC_PATH)
        assert ORDER_CREATE_PATH_REF not in code_tokens
        assert TRADING_STOP_PATH_REF not in code_tokens


# ===========================================================================
# AQ64: No auto-git in src module
# ===========================================================================

class TestAQ64NoAutoGitInSrc:
    def test_no_subprocess_or_git_calls(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "subprocess.run", "subprocess.Popen", "subprocess.call",
            "subprocess.check_output", "subprocess.check_call",
            "os.system", "git.Repo",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into src"


# ===========================================================================
# AQ65-AQ74: Forbidden flag absence in preview
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


class TestAQ65NoExecuteRealEntryFlag:
    def test_preview_has_no_execute_real_entry_flag(self):
        assert "--execute-real-entry" not in _preview_add_argument_lines()


class TestAQ66NoSendOrderFlag:
    def test_preview_has_no_send_order_flag(self):
        assert "--send-order" not in _preview_add_argument_lines()


class TestAQ67NoPlaceOrderFlag:
    def test_preview_has_no_place_order_flag(self):
        assert "--place-order" not in _preview_add_argument_lines()


class TestAQ68NoRealRunFlag:
    def test_preview_has_no_real_run_flag(self):
        assert "--real-run" not in _preview_add_argument_lines()


class TestAQ69NoConfirmTokenFlag:
    def test_preview_has_no_confirm_token_flag(self):
        assert "--confirm-token" not in _preview_add_argument_lines()


class TestAQ70NoExecuteTinyEntryFlag:
    def test_preview_has_no_execute_tiny_entry_flag(self):
        assert "--execute-tiny-entry" not in _preview_add_argument_lines()


class TestAQ71NoAutoCommitFlag:
    def test_preview_has_no_auto_commit_flag(self):
        assert "--auto-commit" not in _preview_add_argument_lines()


class TestAQ72NoGitCommitFlag:
    def test_preview_has_no_git_commit_flag(self):
        assert "--git-commit" not in _preview_add_argument_lines()


class TestAQ73NoAutoPushFlag:
    def test_preview_has_no_auto_push_flag(self):
        assert "--auto-push" not in _preview_add_argument_lines()


class TestAQ74NoGitPushFlag:
    def test_preview_has_no_git_push_flag(self):
        assert "--git-push" not in _preview_add_argument_lines()


# ===========================================================================
# AQ75: Forbidden flag absence in src too
# ===========================================================================

class TestAQ75NoForbiddenFlagsInSrc:
    def test_src_has_no_real_execute_flag_parsing(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "--execute-real-entry", "--send-order", "--place-order",
            "--real-run", "--execute-tiny-entry",
            "--auto-commit", "--git-commit", "--auto-push", "--git-push",
        ):
            assert forbidden not in text, f"{forbidden} leaked into src"


# ===========================================================================
# AQ76: 5 protected positions never appear as "touched"
# ===========================================================================

class TestAQ76ProtectedPositionsUntouched:
    def test_existing_positions_touched_is_empty(self):
        r = _run()
        assert r.existing_positions_touched == []
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym not in r.existing_positions_touched

    def test_no_position_modified_flag(self):
        r = _run()
        assert r.no_position_modified is True


# ===========================================================================
# AQ77: G20 never lifted (any mode)
# ===========================================================================

class TestAQ77G20NotLifted:
    def test_g20_not_lifted_in_checklist(self):
        r = _run()
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_approval(self):
        r = _run(allow_implementation_design=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_real_entry_guard(self):
        r = _run(allow_real_entry_execution=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True


# ===========================================================================
# AQ78: Safety invariants set
# ===========================================================================

class TestAQ78SafetyInvariants:
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
# AQ79: Adapter contract identity exposed
# ===========================================================================

class TestAQ79AdapterContractIdentity:
    def test_adapter_name_and_versions(self):
        r = _run()
        assert r.adapter_name == ADAPTER_NAME
        assert r.adapter_contract_version == ADAPTER_CONTRACT_VERSION
        assert r.consumed_readiness_contract_version == CONSUMED_READINESS_CONTRACT_VERSION
        assert r.consumed_dry_run_contract_version == CONSUMED_DRY_RUN_CONTRACT_VERSION
        assert r.consumed_design_contract_version == CONSUMED_DESIGN_CONTRACT_VERSION
        assert r.order_link_id_prefix == ORDER_LINK_ID_PREFIX
        assert ADAPTER_NAME == "GuardedTinyEntryRealExecutionAdapter"
        assert ADAPTER_CONTRACT_VERSION == "static_skeleton_design_v1"
        assert CONSUMED_READINESS_CONTRACT_VERSION == "readiness_review_v1"
        assert CONSUMED_DRY_RUN_CONTRACT_VERSION == "dry_run_v1"
        assert CONSUMED_DESIGN_CONTRACT_VERSION == "design_only_v1"
        assert ADAPTER_RESPONSE_STATUS == "STATIC_SKELETON_DESIGN_NOT_SENT"
        assert ORDER_LINK_ID_PREFIX == "STATIC_SKELETON_DESIGN_TINY_ENTRY_"


# ===========================================================================
# AQ80: next_required_task points at TASK-014AR
# ===========================================================================

class TestAQ80NextRequiredTask:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == NEXT_REQUIRED_TASK
        assert NEXT_REQUIRED_TASK == "TASK-014AS_guarded_entry_real_execution_adapter_static_skeleton_dry_run"


# ===========================================================================
# AQ81: Status precedence
# ===========================================================================

class TestAQ81StatusPrecedence:
    def test_fail_closed_overrides_real_entry_guard(self):
        r = _run(readonly=None, allow_real_entry_execution=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_fail_closed_overrides_approval(self):
        r = _run(readonly=None, allow_implementation_design=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_real_entry_guard_takes_priority_over_approval(self):
        r = _run(allow_implementation_design=True, allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL


# ===========================================================================
# AQ82: Acceptable status whitelists are frozen (16 frozensets)
# ===========================================================================

class TestAQ82AcceptableStatusFrozensets:
    def test_entry_implementation_readiness_review_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_READINESS_REVIEW_READY" \
            in ACCEPTABLE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUSES

    def test_entry_adapter_dry_run_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DRY_RUN_READY" \
            in ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES

    def test_entry_adapter_design_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY" \
            in ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES

    def test_entry_manual_approval_gate_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY" \
            in ACCEPTABLE_ENTRY_MANUAL_APPROVAL_GATE_STATUSES

    def test_all_sixteen_whitelists_are_frozen(self):
        whitelists = (
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
            ACCEPTABLE_ENTRY_ADAPTER_DESIGN_STATUSES,
            ACCEPTABLE_ENTRY_ADAPTER_DRY_RUN_STATUSES,
            ACCEPTABLE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUSES,
        )
        assert len(whitelists) == 16
        for fs in whitelists:
            assert isinstance(fs, frozenset)


# ===========================================================================
# AQ83: Expected upstream invariants exposed
# ===========================================================================

class TestAQ83ExpectedUpstreamInvariants:
    def test_expected_constants(self):
        assert EXPECTED_ENDPOINT_FAMILY == "bybit_demo"
        assert EXPECTED_ACCOUNT_MODE == "demo"
        assert EXPECTED_PROOF_STRENGTH == "STRONG"
        assert EXPECTED_POSITION_DETAILS_SOURCE == "real_readonly"
        assert EXPECTED_LIFECYCLE_STATUS == "MOCK_TINY_LIFECYCLE_SUCCESS"
        assert EXPECTED_INSTRUMENT_CATEGORY == "linear"


# ===========================================================================
# AQ84: Endpoint allow/deny lists
# ===========================================================================

class TestAQ84EndpointAllowDenyLists:
    def test_demo_allowlist(self):
        assert BASE_URL_DEMO_REF in DEMO_ENDPOINT_ALLOWLIST
        assert BASE_URL_LIVE_REF not in DEMO_ENDPOINT_ALLOWLIST

    def test_live_denylist(self):
        assert BASE_URL_LIVE_REF in LIVE_ENDPOINT_DENYLIST
        assert BASE_URL_DEMO_REF not in LIVE_ENDPOINT_DENYLIST


# ===========================================================================
# AQ85: Forbidden log fields documented
# ===========================================================================

class TestAQ85ForbiddenLogFields:
    def test_forbidden_log_fields_documented(self):
        assert "api_key_value" in FORBIDDEN_LOG_FIELDS
        assert "api_secret_value" in FORBIDDEN_LOG_FIELDS
        assert "signature_value" in FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AQ86: Design expected values for documentation
# ===========================================================================

class TestAQ86DesignExpectedValues:
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
        assert ORDER_LINK_ID_PREFIX.startswith("STATIC_SKELETON_DESIGN_TINY_ENTRY")


# ===========================================================================
# AQ87: Upstream statuses captured in result (incl. NEW AP readiness fields)
# ===========================================================================

class TestAQ87UpstreamStatusCapture:
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
        assert r.upstream_entry_manual_auth_design_status \
            == "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY"
        assert r.upstream_entry_manual_auth_dry_run_status \
            == "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DRY_RUN_READY"
        assert r.upstream_entry_final_pre_execution_review_status \
            == "TINY_GUARDED_ENTRY_FINAL_PRE_EXECUTION_REVIEW_READY"
        assert r.upstream_entry_manual_approval_gate_status \
            == "TINY_GUARDED_ENTRY_REAL_EXECUTION_MANUAL_APPROVAL_GATE_READY"
        assert r.upstream_entry_manual_approval_gate_approval_grants_execution is False
        assert r.upstream_entry_manual_approval_gate_exact_phrase_validated is False
        assert r.upstream_entry_manual_approval_gate_approval_inputs_validated is False
        assert r.upstream_entry_adapter_design_status \
            == "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DESIGN_READY"
        assert r.upstream_entry_adapter_design_grants_execution is False
        assert r.upstream_entry_adapter_design_implementation_included is False
        assert r.upstream_entry_adapter_design_execution_included is False
        assert r.upstream_entry_adapter_dry_run_status \
            == "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DRY_RUN_READY"
        assert r.upstream_entry_adapter_dry_run_dry_run_grants_execution is False
        assert r.upstream_entry_adapter_dry_run_adapter_grants_execution is False
        assert r.upstream_entry_adapter_dry_run_adapter_implementation_included is False
        assert r.upstream_entry_adapter_dry_run_adapter_execution_included is False
        assert r.upstream_entry_adapter_dry_run_no_send_method is True
        assert r.upstream_entry_adapter_dry_run_response_status == "ADAPTER_DRY_RUN_NOT_SENT"
        assert r.upstream_entry_implementation_readiness_review_status \
            == "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_READINESS_REVIEW_READY"
        assert r.upstream_entry_implementation_readiness_review_grants_execution is False
        assert r.upstream_entry_implementation_readiness_review_implementation_included is False
        assert r.upstream_entry_implementation_readiness_review_execution_included is False
        assert r.upstream_entry_implementation_readiness_review_send_allowed is False
        assert r.upstream_entry_implementation_readiness_review_conclusion \
            == "READY_FOR_IMPLEMENTATION_DESIGN_NOT_EXECUTION"
        assert r.upstream_entry_implementation_readiness_review_response_status \
            == "READINESS_REVIEW_NOT_SENT"


# ===========================================================================
# AQ88: CLI subprocess exit codes
# ===========================================================================

class TestAQ88CLIExitCodes:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(PREVIEW_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        out_lower = result.stdout.lower()
        assert (
            "implementation" in out_lower
            or "design" in out_lower
            or "adapter" in out_lower
        )

    def test_missing_artifacts_exits_one(self, repo_tmp_path):
        empty = repo_tmp_path / "empty"
        empty.mkdir()
        from scripts.preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design import (
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
            entry_adapter_design_dir=empty,
            entry_adapter_dry_run_dir=empty,
            entry_implementation_readiness_review_dir=empty,
            output_dir=repo_tmp_path / "out",
        )
        assert rc == 1


# ===========================================================================
# AQ89: run_execute writes JSON + MD reports
# ===========================================================================

class TestAQ89ReportArtifacts:
    def test_write_report_creates_files(self, repo_tmp_path):
        from scripts.preview_demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design import (
            _write_report,
        )
        r = _run()
        out_dir = repo_tmp_path / "out"
        _write_report(r, out_dir)
        base = "tiny_guarded_entry_real_execution_adapter_static_skeleton_design"
        latest_json = out_dir / f"latest_{base}.json"
        latest_md   = out_dir / f"latest_{base}.md"
        assert latest_json.exists()
        assert latest_md.exists()
        parsed = json.loads(latest_json.read_text(encoding="utf-8"))
        assert parsed["status"] == STATUS_IMPLEMENTATION_DESIGN_READY
        md_text = latest_md.read_text(encoding="utf-8")
        assert "TASK-014AR" in md_text
        assert ADAPTER_NAME in md_text


# ===========================================================================
# AQ90: real_execution_allowed never True regardless of inputs
# ===========================================================================

class TestAQ90RealExecutionNeverAllowed:
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
# AQ91: Existing position symbols documented in result
# ===========================================================================

class TestAQ91ExistingPositionSymbols:
    def test_existing_position_symbols_reflect_recon(self):
        r = _run()
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols


# ===========================================================================
# AQ92: Expected commit hash documented (never validated as match)
# ===========================================================================

class TestAQ92ExpectedCommitHashDocumentedOnly:
    def test_expected_commit_hash_stored_in_result(self):
        r = _run(expected_commit_hash="abc123def4567890")
        assert r.expected_commit_hash == "abc123def4567890"

    def test_current_commit_hash_stored_in_result(self):
        r = _run(current_commit_hash="fedcba9876543210")
        assert r.current_commit_hash == "fedcba9876543210"

    def test_design_does_not_invoke_git_subprocess(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "subprocess.run", "subprocess.Popen", "subprocess.check_output",
            "subprocess.call", "git rev-parse",
        ):
            assert forbidden not in code_tokens


# ===========================================================================
# AQ93: All 14 stages have non-empty summaries
# ===========================================================================

class TestAQ93StagePayloads:
    def test_stages_have_summaries(self):
        r = _run()
        for stage_id in r.stage_order:
            env = r.stages[stage_id]
            assert "summary" in env
            assert isinstance(env["summary"], str)
            assert env["summary"] != ""


# ===========================================================================
# AQ94: final_implementation_design_verdict completeness
# ===========================================================================

class TestAQ94FinalVerdictCompleteness:
    def test_verdict_contains_required_fields(self):
        r = _run()
        v = r.final_implementation_design_verdict
        assert v["implementation_design_allowed"] is False
        assert v["real_entry_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_entry_implemented"] is False
        assert v["guarded_entry_real_execution_adapter_implementation_design"] is True
        assert v["implementation_design_only"] is True
        assert v["adapter_implementation_included"] is False
        assert v["adapter_execution_included"] is False
        assert v["dry_run_grants_execution"] is False
        assert v["adapter_grants_execution"] is False
        assert v["approval_gate_grants_execution"] is False
        assert v["readiness_review_grants_execution"] is False
        assert v["implementation_design_grants_execution"] is False
        assert v["entry_execution_included"] is False
        assert v["stop_execution_included"] is False
        assert v["cleanup_execution_included"] is False
        assert v["full_lifecycle_execution_included"] is False
        assert v["current_task_real_execution_allowed"] is False
        assert v["implementation_design_conclusion"] == STATIC_SKELETON_DESIGN_CONCLUSION
        assert v["implementation_design_authorization_result"] == STATIC_SKELETON_DESIGN_AUTHORIZATION_RESULT
        assert v["g20_policy_still_in_place"] is True
        assert v["g20_lifted"] is False


# ===========================================================================
# AQ95: audit_artifacts sanitized + response_status
# ===========================================================================

class TestAQ95AuditArtifactsSanitized:
    def test_audit_artifacts_response_and_sanitization(self):
        r = _run()
        aud = r.audit_artifacts
        assert aud.get("response_status") == ADAPTER_RESPONSE_STATUS
        assert aud.get("response_from_exchange") is False
        assert aud.get("sanitized") is True
        assert aud.get("no_secrets") is True


# ===========================================================================
# AQ96: Documentation sync review names next task TASK-014AR
# ===========================================================================

class TestAQ96DocumentationSyncNextTaskAR:
    def test_documentation_sync_points_at_ar(self):
        r = _run()
        ds = r.documentation_sync_review
        assert ds.get("next_required_task") == NEXT_REQUIRED_TASK
        assert ds.get("documentation_only_plan") is True
        assert ds.get("markdown_read_in_this_module") is False


# ===========================================================================
# AQ97: Hard-fail gates count
# ===========================================================================

class TestAQ97HardFailGatesCount:
    def test_hard_fail_gates_include_all_26_missing_and_ap_acceptance(self):
        from src.demo_tiny_guarded_entry_real_execution_adapter_static_skeleton_design import _HARD_FAIL_GATES
        assert GATE_READONLY_SMOKE_MISSING in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_MISSING in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_STATUS_UNACCEPTABLE in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_GRANTS_EXECUTION in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_IMPLEMENTATION_INCLUDED in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_EXECUTION_INCLUDED in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_SEND_ALLOWED in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_CONCLUSION_MISMATCH in _HARD_FAIL_GATES
        assert GATE_ENTRY_IMPLEMENTATION_READINESS_REVIEW_RESPONSE_STATUS_UNACCEPTABLE in _HARD_FAIL_GATES
        assert GATE_ENTRY_ADAPTER_DRY_RUN_MISSING in _HARD_FAIL_GATES
        assert GATE_ENTRY_ADAPTER_DRY_RUN_SEND_METHOD_PRESENT in _HARD_FAIL_GATES
        assert GATE_SOLUSDT_EXISTS_FAIL_CLOSED in _HARD_FAIL_GATES
        # ~50-55 gates: at least 50
        assert len(_HARD_FAIL_GATES) >= 50


# ===========================================================================
# AQ98: Order link id prefix and adapter contract version
# ===========================================================================

class TestAQ98OrderLinkIdPrefix:
    def test_order_link_id_prefix_starts_with_static_skeleton_design(self):
        assert ORDER_LINK_ID_PREFIX.startswith("STATIC_SKELETON_DESIGN_TINY_ENTRY")
        r = _run()
        assert r.order_link_id_prefix == ORDER_LINK_ID_PREFIX

    def test_consumed_contract_versions(self):
        assert CONSUMED_READINESS_CONTRACT_VERSION == "readiness_review_v1"
        assert CONSUMED_DRY_RUN_CONTRACT_VERSION == "dry_run_v1"
        assert CONSUMED_DESIGN_CONTRACT_VERSION == "design_only_v1"


# ===========================================================================
# AQ99: Implementation design scope dict captured
# ===========================================================================

class TestAQ99ImplementationDesignScope:
    def test_scope_flags(self):
        r = _run()
        s = r.implementation_design_scope
        assert s["guarded_entry_real_execution_adapter_implementation_design"] is True
        assert s["implementation_design_only"] is True
        assert s["adapter_implementation_included"] is False
        assert s["adapter_execution_included"] is False
        assert s["entry_execution_included"] is False
        assert s["stop_execution_included"] is False
        assert s["cleanup_execution_included"] is False
        assert s["full_lifecycle_execution_included"] is False
        assert s["real_entry_implemented"] is False
        assert s["real_execution_allowed"] is False
        assert s["dry_run_grants_execution"] is False
        assert s["adapter_grants_execution"] is False
        assert s["approval_gate_grants_execution"] is False
        assert s["readiness_review_grants_execution"] is False
        assert s["implementation_design_grants_execution"] is False
        assert s["send_allowed"] is False
        assert s["order_endpoint_called"] is False
        assert s["stop_endpoint_called"] is False
        assert s["no_position_modified"] is True
        assert s["no_secrets_loaded"] is True
        assert s["g20_policy_still_in_place"] is True
        assert s["g20_lifted"] is False
        assert s["next_required_task"] == NEXT_REQUIRED_TASK


# ===========================================================================
# AQ100: Preview has no forbidden imports / no auto-git
# ===========================================================================

class TestAQ100PreviewNoForbiddenImports:
    def test_preview_no_urllib_requests_httpx(self):
        tree = ast.parse(PREVIEW_PATH.read_text(encoding="utf-8"))
        bad: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    bad.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                bad.add(node.module or "")
        forbidden = {
            "urllib", "urllib.request", "requests", "httpx",
            "http", "http.client", "socket", "ssl",
            "hmac", "hashlib", "dotenv", "pybit",
            "main", "src.risk", "src.bybit_executor",
        }
        assert not (bad & forbidden), f"preview leaked forbidden imports: {bad & forbidden}"


class TestAQ101PreviewNoAutoGit:
    def test_preview_no_subprocess_or_git_calls(self):
        code_tokens = _read_code_only(PREVIEW_PATH)
        for forbidden in (
            "subprocess.run", "subprocess.Popen", "subprocess.call",
            "os.system", "git.Repo",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into preview"
        for flag in ("--auto-commit", "--git-commit", "--auto-push", "--git-push"):
            assert flag not in code_tokens, f"{flag} leaked into preview code"


# ===========================================================================
# AQ102: Result dataclass fields exposed
# ===========================================================================

class TestAQ102ResultDataclassFields:
    def test_result_has_required_fields(self):
        r = _run()
        assert hasattr(r, "timestamp_utc")
        assert hasattr(r, "mode")
        assert hasattr(r, "status")
        assert hasattr(r, "selected_symbol")
        assert hasattr(r, "stages")
        assert hasattr(r, "stage_order")
        assert hasattr(r, "implementation_design_scope")
        assert hasattr(r, "static_module_boundary_design")
        assert hasattr(r, "request_construction_design")
        assert hasattr(r, "transport_and_endpoint_design")
        assert hasattr(r, "secret_and_signing_design")
        assert hasattr(r, "response_and_error_handling_design")
        assert hasattr(r, "manual_approval_and_authorization_design")
        assert hasattr(r, "stop_cleanup_handoff_design")
        assert hasattr(r, "risk_idempotency_and_audit_design")
        assert hasattr(r, "forbidden_implementation_surface_design")
        assert hasattr(r, "failure_and_abort_implementation_design")
        assert hasattr(r, "documentation_sync_review")
        assert hasattr(r, "final_implementation_design_verdict")
        assert hasattr(r, "audit_artifacts")
        assert hasattr(r, "next_required_task")
        assert hasattr(r, "blocked_gates")


# ===========================================================================
# AQ103: Static module boundary design captured
# ===========================================================================

class TestAQ103StaticModuleBoundaryDesign:
    def test_static_module_boundary_non_empty(self):
        r = _run()
        smb = r.static_module_boundary_design
        assert isinstance(smb, dict)
        assert len(smb) > 0


# ===========================================================================
# AQ104: Request construction design captured
# ===========================================================================

class TestAQ104RequestConstructionDesign:
    def test_request_construction_non_empty(self):
        r = _run()
        rc = r.request_construction_design
        assert isinstance(rc, dict)
        assert len(rc) > 0


# ===========================================================================
# AQ105: Transport and endpoint design captured
# ===========================================================================

class TestAQ105TransportAndEndpointDesign:
    def test_transport_endpoint_non_empty(self):
        r = _run()
        te = r.transport_and_endpoint_design
        assert isinstance(te, dict)
        assert len(te) > 0


# ===========================================================================
# AQ106: Secret and signing design captured
# ===========================================================================

class TestAQ106SecretAndSigningDesign:
    def test_secret_signing_non_empty(self):
        r = _run()
        ss = r.secret_and_signing_design
        assert isinstance(ss, dict)
        assert len(ss) > 0


# ===========================================================================
# AQ107: Response/error handling design captured
# ===========================================================================

class TestAQ107ResponseAndErrorHandlingDesign:
    def test_response_error_non_empty(self):
        r = _run()
        re_design = r.response_and_error_handling_design
        assert isinstance(re_design, dict)
        assert len(re_design) > 0


# ===========================================================================
# AQ108: Manual approval and authorization design captured
# ===========================================================================

class TestAQ108ManualApprovalAndAuthorizationDesign:
    def test_manual_approval_design_non_empty(self):
        r = _run()
        ma = r.manual_approval_and_authorization_design
        assert isinstance(ma, dict)
        assert len(ma) > 0


# ===========================================================================
# AQ109: Stop / cleanup handoff design captured
# ===========================================================================

class TestAQ109StopCleanupHandoffDesign:
    def test_stop_cleanup_handoff_non_empty(self):
        r = _run()
        sc = r.stop_cleanup_handoff_design
        assert isinstance(sc, dict)
        assert len(sc) > 0


# ===========================================================================
# AQ110: Risk / idempotency / audit design captured
# ===========================================================================

class TestAQ110RiskIdempotencyAndAuditDesign:
    def test_risk_idempotency_audit_non_empty(self):
        r = _run()
        ri = r.risk_idempotency_and_audit_design
        assert isinstance(ri, dict)
        assert len(ri) > 0


# ===========================================================================
# AQ111: Forbidden implementation surface design captured
# ===========================================================================

class TestAQ111ForbiddenImplementationSurfaceDesign:
    def test_forbidden_surface_non_empty(self):
        r = _run()
        fs = r.forbidden_implementation_surface_design
        assert isinstance(fs, dict)
        assert len(fs) > 0


# ===========================================================================
# AQ112: Failure / abort implementation design captured
# ===========================================================================

class TestAQ112FailureAndAbortImplementationDesign:
    def test_failure_abort_non_empty(self):
        r = _run()
        fa = r.failure_and_abort_implementation_design
        assert isinstance(fa, dict)
        assert len(fa) > 0


# ===========================================================================
# AQ113: Src module is self-contained (no imports of demo modules)
# ===========================================================================

class TestAQ113SrcSelfContained:
    def test_src_only_imports_stdlib(self):
        tree = ast.parse(SRC_PATH.read_text(encoding="utf-8"))
        modules: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    modules.add(alias.name.split(".")[0])
            elif isinstance(node, ast.ImportFrom):
                if node.module:
                    modules.add(node.module.split(".")[0])
        # Only stdlib + __future__ allowed.
        for mod in modules:
            assert mod in {
                "__future__", "dataclasses", "datetime", "typing",
            }, f"unexpected import: {mod}"


# ===========================================================================
# AQ114: SOLUSDT absent stays clean
# ===========================================================================

class TestAQ114SolusdtAbsent:
    def test_solusdt_not_in_existing_default(self):
        r = _run()
        assert "SOLUSDT" not in r.existing_position_symbols


# ===========================================================================
# AQ115: Protected symbols present in recon
# ===========================================================================

class TestAQ115ProtectedSymbolsPresent:
    def test_all_five_protected_symbols_present(self):
        r = _run()
        for sym in ("ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"):
            assert sym in r.existing_position_symbols


# ===========================================================================
# AQ116: Approval-gate readiness unchanged (still not authorized)
# ===========================================================================

class TestAQ116ApprovalGateReadinessUnchanged:
    def test_approval_gate_grants_execution_false_under_design_approval(self):
        r = _run(allow_implementation_design=True)
        assert r.approval_gate_grants_execution is False
        assert r.readiness_review_grants_execution is False
        assert r.implementation_design_grants_execution is False


# ===========================================================================
# AQ117: Real-entry guard readiness unchanged
# ===========================================================================

class TestAQ117RealEntryGuardReadinessUnchanged:
    def test_real_entry_guard_does_not_grant_execution(self):
        r = _run(allow_real_entry_execution=True)
        assert r.approval_gate_grants_execution is False
        assert r.readiness_review_grants_execution is False
        assert r.implementation_design_grants_execution is False
        assert r.dry_run_grants_execution is False
        assert r.adapter_grants_execution is False


# ===========================================================================
# AQ118: AP readiness review nested verdict conclusion accepted
# ===========================================================================

class TestAQ118APReadinessReviewNestedVerdictConclusion:
    def test_nested_verdict_conclusion_accepted_when_top_missing(self):
        ok = _valid_entry_implementation_readiness_review()
        # Remove top-level conclusion to force fallback to nested verdict.
        ok.pop("implementation_readiness_conclusion", None)
        # Nested verdict still has the correct conclusion.
        r = _run(entry_implementation_readiness_review=ok)
        assert r.status == STATUS_IMPLEMENTATION_DESIGN_READY


# ===========================================================================
# AQ119: SOLUSDT exists with real-entry flag still fails closed
# ===========================================================================

class TestAQ119SolusdtExistsWithRealEntryFlag:
    def test_solusdt_exists_blocks_even_with_real_entry_flag(self):
        bad = _valid_reconciliation()
        bad["positions"].append({
            "symbol": "SOLUSDT", "side": "long", "quantity": 0.1,
            "entry_price": 64.4, "stop_price": 61.18,
        })
        r = _run(recon=bad, allow_real_entry_execution=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SOLUSDT_EXISTS_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# AQ120: Implementation design conclusion is correct exact string
# ===========================================================================

class TestAQ120ImplementationDesignConclusion:
    def test_conclusion_constant_value(self):
        assert STATIC_SKELETON_DESIGN_CONCLUSION == "STATIC_SKELETON_DESIGN_READY_NOT_EXECUTABLE"
        r = _run()
        assert r.implementation_design_conclusion == STATIC_SKELETON_DESIGN_CONCLUSION

    def test_authorization_result_documented_only(self):
        assert STATIC_SKELETON_DESIGN_AUTHORIZATION_RESULT == "DOCUMENTED_ONLY_NOT_AUTHORIZED"
        r = _run()
        assert r.implementation_design_authorization_result == STATIC_SKELETON_DESIGN_AUTHORIZATION_RESULT


# ===========================================================================
# AQ121: Endpoint path ref documented
# ===========================================================================

class TestAQ121EndpointPathRef:
    def test_endpoint_path_ref_value(self):
        assert ENDPOINT_PATH_REF == "/v5/order/create"
        r = _run()
        assert r.endpoint_path_ref == ENDPOINT_PATH_REF


# ===========================================================================
# AR122: AQ implementation-design upstream contract identity declared
# (TASK-014AR forward-declarations consumed by TASK-014AS dry-run)
# ===========================================================================

class TestAR122ConsumedImplementationDesignContractVersion:
    def test_consumed_implementation_design_contract_version_value(self):
        assert CONSUMED_IMPLEMENTATION_DESIGN_CONTRACT_VERSION == "implementation_design_v1"


class TestAR123AcceptableEntryImplementationDesignStatuses:
    def test_acceptable_entry_implementation_design_statuses_is_frozenset(self):
        assert isinstance(ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES, frozenset)
        assert len(ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES) > 0

    def test_acceptable_entry_implementation_design_statuses_documents_aq_outputs(self):
        assert (
            "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_IMPLEMENTATION_DESIGN_READY"
            in ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES
        )
        assert (
            "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
            in ACCEPTABLE_ENTRY_IMPLEMENTATION_DESIGN_STATUSES
        )


class TestAR124AQAcceptanceGateIdentifiersDeclared:
    """The eight AQ-acceptance gate identifiers are forward-declared in the
    static-skeleton-design module so that TASK-014AS can wire them into the
    skeleton dry-run. Each identifier must be a non-empty snake_case string
    that begins with `entry_implementation_design_`."""

    def test_gate_identifiers_are_well_formed_strings(self):
        gates = (
            GATE_ENTRY_IMPLEMENTATION_DESIGN_MISSING,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_STATUS_UNACCEPTABLE,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_GRANTS_EXECUTION,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_IMPLEMENTATION_INCLUDED,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_EXECUTION_INCLUDED,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_SEND_ALLOWED,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_CONCLUSION_MISMATCH,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_RESPONSE_STATUS_UNACCEPTABLE,
        )
        assert len(gates) == 8
        for g in gates:
            assert isinstance(g, str)
            assert g.startswith("entry_implementation_design_")
            assert g == g.lower()
            assert " " not in g

    def test_gate_identifiers_are_unique(self):
        gates = {
            GATE_ENTRY_IMPLEMENTATION_DESIGN_MISSING,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_STATUS_UNACCEPTABLE,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_GRANTS_EXECUTION,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_IMPLEMENTATION_INCLUDED,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_EXECUTION_INCLUDED,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_SEND_ALLOWED,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_CONCLUSION_MISMATCH,
            GATE_ENTRY_IMPLEMENTATION_DESIGN_RESPONSE_STATUS_UNACCEPTABLE,
        }
        assert len(gates) == 8
