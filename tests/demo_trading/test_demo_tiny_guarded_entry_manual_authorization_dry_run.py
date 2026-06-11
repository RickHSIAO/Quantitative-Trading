"""
tests/demo_trading/test_demo_tiny_guarded_entry_manual_authorization_dry_run.py
TASK-014AK: Guarded Tiny Entry Manual Authorization Dry-run tests.

Covers authorization_dry_run_checklist / authorization_dry_run_approval /
real_entry_execution_guard / fail_closed paths; all 10 stages; 156+ gate
constants; 20-artifact preflight contract (the 19 from TASK-014AJ + AJ's
own entry_manual_authorization_design output); token-pattern matching
is simulated only, never validated as real authorization; 13-flag
required_human_confirmation_flags documentation never validated;
dry-run-only template (no sender adapter, signature_present False,
private_headers empty, send_allowed False); post-entry boundary
dry-run (stop attach separate manual authorization, cleanup separate
manual authorization); failure / abort dry-run (FAIL_CLOSED /
MANUAL_REVIEW_REQUIRED); documentation sync plan; status precedence;
source-scan safety (no urlopen / no forbidden imports / no signing /
no os.environ / no AA-AJ module reuse / no real sender); report
artifacts; forbidden-flag absence (--execute-real-* / --send-order /
--place-order / --real-run / --confirm-token); the invariant that
TASK-014L sender G20 (protected_entry_policy_missing) still blocks
--execute-new-entry and is NOT lifted here; next_required_task points
at TASK-014AL_guarded_entry_final_pre_execution_review.
"""
from __future__ import annotations

import ast
import json
import shutil
import subprocess
import sys
import tempfile
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
    """Repo-local scratch directory.

    The default ``tmp_path`` fixture targets the user's profile temp folder,
    which can hit Windows ACL / non-ASCII path issues in this environment.
    We allocate inside the repo's outputs/_test_scratch tree and clean up.
    """
    root = ROOT / "outputs" / "_test_scratch"
    root.mkdir(parents=True, exist_ok=True)
    d = root / f"ak_{uuid.uuid4().hex}"
    d.mkdir()
    try:
        yield d
    finally:
        shutil.rmtree(d, ignore_errors=True)

from src.demo_tiny_guarded_entry_manual_authorization_dry_run import (
    ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES,
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
    DRY_RUN_EXPECTED_CATEGORY,
    DRY_RUN_EXPECTED_CLOSE_ON_TRIGGER,
    DRY_RUN_EXPECTED_ENTRY_REFERENCE,
    DRY_RUN_EXPECTED_ENTRY_SIDE,
    DRY_RUN_EXPECTED_ESTIMATED_NOTIONAL,
    DRY_RUN_EXPECTED_EXISTING_COUNT,
    DRY_RUN_EXPECTED_MAX_NOTIONAL_USDT,
    DRY_RUN_EXPECTED_ORDER_TYPE,
    DRY_RUN_EXPECTED_POSITION_IDX,
    DRY_RUN_EXPECTED_QTY,
    DRY_RUN_EXPECTED_REDUCE_ONLY,
    DRY_RUN_EXPECTED_SL_TRIGGER_BY,
    DRY_RUN_EXPECTED_STOP_LOSS,
    DRY_RUN_EXPECTED_SYMBOL,
    DRY_RUN_EXPECTED_TPSL_MODE,
    DemoTinyGuardedEntryManualAuthorizationDryRun,
    ENTRY_DRY_RUN_ORDER_LINK_ID_PREFIXES,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    LIVE_ENDPOINT_DENYLIST,
    MODE_AUTHORIZATION_DRY_RUN_APPROVAL,
    MODE_AUTHORIZATION_DRY_RUN_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_ENTRY_EXECUTION_GUARD,
    ORDER_CREATE_PATH_REF,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    REQUIRED_HUMAN_CONFIRMATION_FLAGS,
    SAMPLE_TOKEN,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_MANUAL_AUTHORIZATION_DRY_RUN_SCOPE,
    STAGE_2_AUTHORIZATION_TOKEN_DRY_RUN,
    STAGE_3_REQUIRED_FLAGS_DRY_RUN,
    STAGE_4_PRE_EXECUTION_READINESS_DRY_RUN,
    STAGE_5_ENTRY_REQUEST_TEMPLATE_DRY_RUN,
    STAGE_6_POST_ENTRY_BOUNDARY_DRY_RUN,
    STAGE_7_FAILURE_AND_ABORT_DRY_RUN,
    STAGE_8_DOCUMENTATION_SYNC_REVIEW,
    STAGE_9_FINAL_MANUAL_AUTHORIZATION_DRY_RUN_VERDICT,
    STATUS_DRY_RUN_READY,
    STATUS_DRY_RUN_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_ENTRY_NOT_IMPL,
    TRADING_STOP_PATH_REF,
    TinyGuardedEntryManualAuthorizationDryRunResult,
    GATE_READONLY_SMOKE_MISSING,
    GATE_RECONCILIATION_MISSING,
    GATE_PROTECTION_MISSING,
    GATE_CONTRACT_MISSING,
    GATE_NOOP_PLAN_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_PERMISSION_GATE_MISSING,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_GUARDED_DESIGN_REVIEW_MISSING,
    GATE_GUARDED_ENTRY_ADAPTER_MISSING,
    GATE_GUARDED_STOP_ADAPTER_MISSING,
    GATE_GUARDED_CLEANUP_ADAPTER_MISSING,
    GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING,
    GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING,
    GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING,
    GATE_ENTRY_MANUAL_AUTH_DESIGN_STATUS_UNACCEPTABLE,
    GATE_ENTRY_MANUAL_AUTH_DESIGN_READINESS_EXECUTABLE,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_SELECTED_SYMBOL_NOT_SOLUSDT,
)

_TEST_NOW = datetime(2026, 6, 12, 10, 0, 0, tzinfo=timezone.utc)

ROOT_PATH = ROOT
SRC_PATH = ROOT_PATH / "src" / "demo_tiny_guarded_entry_manual_authorization_dry_run.py"
PREVIEW_PATH = (
    ROOT_PATH / "scripts"
    / "preview_demo_tiny_guarded_entry_manual_authorization_dry_run.py"
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
        "selected_qty":           DRY_RUN_EXPECTED_QTY,
        "entry_reference_price":  DRY_RUN_EXPECTED_ENTRY_REFERENCE,
        "stop_price":             DRY_RUN_EXPECTED_STOP_LOSS,
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
        "tiny_qty":                  DRY_RUN_EXPECTED_QTY,
        "tiny_notional":             DRY_RUN_EXPECTED_ESTIMATED_NOTIONAL,
        "entry_reference_price":     DRY_RUN_EXPECTED_ENTRY_REFERENCE,
        "stop_price":                DRY_RUN_EXPECTED_STOP_LOSS,
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


def _dry_run() -> DemoTinyGuardedEntryManualAuthorizationDryRun:
    return DemoTinyGuardedEntryManualAuthorizationDryRun()


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
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_dry_run_approval=False,
    allow_real_entry_execution=False,
    _now=_TEST_NOW,
) -> TinyGuardedEntryManualAuthorizationDryRunResult:
    return _dry_run().run_checklist(
        readonly_smoke=_valid_readonly()                                         if readonly                       is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                                   if recon                          is _UNSET else recon,
        protection=_valid_protection()                                           if protection                     is _UNSET else protection,
        contract=_valid_contract()                                               if contract                       is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                             if noop_plan                      is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                                        if lifecycle                      is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()                       if real_permission_gate           is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate()           if tiny_entry_permission_gate     is _UNSET else tiny_entry_permission_gate,
        tiny_stop_permission_gate=_valid_tiny_stop_permission_gate()             if tiny_stop_permission_gate      is _UNSET else tiny_stop_permission_gate,
        tiny_cleanup_permission_gate=_valid_tiny_cleanup_permission_gate()       if tiny_cleanup_permission_gate   is _UNSET else tiny_cleanup_permission_gate,
        lifecycle_summary=_valid_lifecycle_summary()                             if lifecycle_summary              is _UNSET else lifecycle_summary,
        runner_design=_valid_runner_design()                                     if runner_design                  is _UNSET else runner_design,
        runner_dry_run=_valid_runner_dry_run()                                   if runner_dry_run                 is _UNSET else runner_dry_run,
        guarded_design_review=_valid_guarded_design_review()                     if guarded_design_review          is _UNSET else guarded_design_review,
        guarded_entry_adapter=_valid_guarded_entry_adapter()                     if guarded_entry_adapter          is _UNSET else guarded_entry_adapter,
        guarded_stop_adapter=_valid_guarded_stop_adapter()                       if guarded_stop_adapter           is _UNSET else guarded_stop_adapter,
        guarded_cleanup_adapter=_valid_guarded_cleanup_adapter()                 if guarded_cleanup_adapter        is _UNSET else guarded_cleanup_adapter,
        guarded_lifecycle_summary=_valid_guarded_lifecycle_summary()             if guarded_lifecycle_summary      is _UNSET else guarded_lifecycle_summary,
        entry_real_permission_review=_valid_entry_real_permission_review()       if entry_real_permission_review   is _UNSET else entry_real_permission_review,
        entry_manual_authorization_design=_valid_entry_manual_auth_design()      if entry_manual_authorization_design is _UNSET else entry_manual_authorization_design,
        symbol=symbol,
        allow_dry_run_approval=allow_dry_run_approval,
        allow_real_entry_execution=allow_real_entry_execution,
        _now=_now,
    )


# ===========================================================================
# AK1-AK4: Status modes
# ===========================================================================

class TestAK1DryRunReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_DRY_RUN_READY
        assert r.mode == MODE_AUTHORIZATION_DRY_RUN_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.failed_stage == ""
        # blocked_gates documents the safety gates that remain in place even
        # when the dry-run checklist is ready (e.g. G20 not lifted, no live
        # endpoint, no secrets emitted).  None of those are HARD_FAIL gates.
        from src.demo_tiny_guarded_entry_manual_authorization_dry_run import _HARD_FAIL_GATES
        assert not any(g in _HARD_FAIL_GATES for g in r.blocked_gates)
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.guarded_entry_manual_authorization_dry_run is True
        assert r.authorization_dry_run_only is True
        assert r.token_validation_simulated is True
        assert r.token_validated is False
        assert r.real_token_validated is False
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True
        assert r.next_required_task == "TASK-014AL_guarded_entry_final_pre_execution_review"


class TestAK2DryRunApproval:
    def test_dry_run_approval_yields_exec_disabled(self):
        r = _run(symbol="SOLUSDT", allow_dry_run_approval=True)
        assert r.status == STATUS_DRY_RUN_READY_EXEC_DISABLED
        assert r.mode == MODE_AUTHORIZATION_DRY_RUN_APPROVAL
        assert r.dry_run_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.g20_lifted is False


class TestAK3RealEntryExecutionGuard:
    def test_allow_real_entry_returns_not_implemented(self):
        r = _run(symbol="SOLUSDT", allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL
        assert r.mode == MODE_REAL_ENTRY_EXECUTION_GUARD
        assert r.real_entry_execution_requested is True
        assert r.real_execution_allowed is False
        assert r.real_entry_implemented is False
        assert r.no_orders_sent is True
        assert r.no_position_modified is True
        assert r.send_allowed is False
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.g20_lifted is False


class TestAK4FailClosedWrongSymbol:
    def test_wrong_symbol_fails_closed(self):
        # Empty symbol is permitted (defaults documented elsewhere); a
        # non-empty wrong symbol must hard-fail because SOLUSDT is the only
        # supported demo tiny entry symbol.
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AK5-AK24: 20 missing-artifact gates
# ===========================================================================

class TestAK5MissingReadonly:
    def test_missing_readonly_blocked(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAK6MissingReconciliation:
    def test_missing_recon_blocked(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAK7MissingProtection:
    def test_missing_protection_blocked(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAK8MissingContract:
    def test_missing_contract_blocked(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAK9MissingNoopPlan:
    def test_missing_noop_plan_blocked(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAK10MissingLifecycle:
    def test_missing_lifecycle_blocked(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAK11MissingRealPermissionGate:
    def test_missing_real_perm_blocked(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAK12MissingTinyEntryPermissionGate:
    def test_missing_tiny_entry_perm_blocked(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAK13MissingTinyStopPermissionGate:
    def test_missing_tiny_stop_perm_blocked(self):
        r = _run(tiny_stop_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAK14MissingTinyCleanupPermissionGate:
    def test_missing_tiny_cleanup_perm_blocked(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAK15MissingLifecycleSummary:
    def test_missing_lifecycle_summary_blocked(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAK16MissingRunnerDesign:
    def test_missing_runner_design_blocked(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAK17MissingRunnerDryRun:
    def test_missing_runner_dry_run_blocked(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


class TestAK18MissingGuardedDesignReview:
    def test_missing_guarded_design_review_blocked(self):
        r = _run(guarded_design_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_DESIGN_REVIEW_MISSING in r.blocked_gates


class TestAK19MissingGuardedEntryAdapter:
    def test_missing_guarded_entry_adapter_blocked(self):
        r = _run(guarded_entry_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_ENTRY_ADAPTER_MISSING in r.blocked_gates


class TestAK20MissingGuardedStopAdapter:
    def test_missing_guarded_stop_adapter_blocked(self):
        r = _run(guarded_stop_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_STOP_ADAPTER_MISSING in r.blocked_gates


class TestAK21MissingGuardedCleanupAdapter:
    def test_missing_guarded_cleanup_adapter_blocked(self):
        r = _run(guarded_cleanup_adapter=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_CLEANUP_ADAPTER_MISSING in r.blocked_gates


class TestAK22MissingGuardedLifecycleSummary:
    def test_missing_guarded_lifecycle_summary_blocked(self):
        r = _run(guarded_lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_GUARDED_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAK23MissingEntryRealPermissionReview:
    def test_missing_entry_real_perm_review_blocked(self):
        r = _run(entry_real_permission_review=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REAL_PERMISSION_REVIEW_MISSING in r.blocked_gates


class TestAK24MissingEntryManualAuthDesign:
    def test_missing_entry_manual_auth_design_blocked(self):
        r = _run(entry_manual_authorization_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DESIGN_MISSING in r.blocked_gates


# ===========================================================================
# AK25: Endpoint invariants
# ===========================================================================

class TestAK25EndpointFamilyMismatch:
    def test_wrong_endpoint_family_blocked(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAK26AccountModeMismatch:
    def test_wrong_account_mode_blocked(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAK27WrongSymbol:
    def test_wrong_symbol_blocked(self):
        r = _run(symbol="BTCUSDT")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_NOT_SOLUSDT in r.blocked_gates


# ===========================================================================
# AK28: AJ design status acceptance
# ===========================================================================

class TestAK28EntryManualAuthDesignStatusUnacceptable:
    def test_unacceptable_design_status_blocked(self):
        bad = _valid_entry_manual_auth_design()
        bad["status"] = "SOMETHING_UNEXPECTED"
        r = _run(entry_manual_authorization_design=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DESIGN_STATUS_UNACCEPTABLE in r.blocked_gates


class TestAK29EntryManualAuthDesignReadinessExecutable:
    def test_executable_readiness_blocked(self):
        bad = _valid_entry_manual_auth_design()
        bad["readiness_conclusion"] = "REAL_ENTRY_EXECUTION_AUTHORIZED"
        r = _run(entry_manual_authorization_design=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_MANUAL_AUTH_DESIGN_READINESS_EXECUTABLE in r.blocked_gates


# ===========================================================================
# AK30: Stage presence + order
# ===========================================================================

class TestAK30StageOrder:
    def test_stages_present_in_order(self):
        r = _run()
        assert r.stage_order == list(ALL_STAGES)
        assert r.stage_order == [
            STAGE_0_ARTIFACT_PREFLIGHT,
            STAGE_1_MANUAL_AUTHORIZATION_DRY_RUN_SCOPE,
            STAGE_2_AUTHORIZATION_TOKEN_DRY_RUN,
            STAGE_3_REQUIRED_FLAGS_DRY_RUN,
            STAGE_4_PRE_EXECUTION_READINESS_DRY_RUN,
            STAGE_5_ENTRY_REQUEST_TEMPLATE_DRY_RUN,
            STAGE_6_POST_ENTRY_BOUNDARY_DRY_RUN,
            STAGE_7_FAILURE_AND_ABORT_DRY_RUN,
            STAGE_8_DOCUMENTATION_SYNC_REVIEW,
            STAGE_9_FINAL_MANUAL_AUTHORIZATION_DRY_RUN_VERDICT,
        ]
        for stage_id in r.stage_order:
            assert stage_id in r.stages
            assert "summary" in r.stages[stage_id]


# ===========================================================================
# AK31: Deep-copy roundtrip + to_dict
# ===========================================================================

class TestAK31DictRoundtrip:
    def test_to_dict_is_json_serializable(self):
        r = _run()
        d = r.to_dict()
        text = json.dumps(d)
        parsed = json.loads(text)
        assert parsed["status"] == STATUS_DRY_RUN_READY
        assert parsed["selected_symbol"] == "SOLUSDT"
        assert parsed["g20_lifted"] is False
        assert parsed["real_entry_implemented"] is False
        assert parsed["authorization_dry_run_only"] is True
        assert parsed["next_required_task"] == "TASK-014AL_guarded_entry_final_pre_execution_review"

    def test_to_dict_is_deep_copied(self):
        r = _run()
        d1 = r.to_dict()
        d2 = r.to_dict()
        d1["stages"]["mutated"] = True
        assert "mutated" not in d2["stages"]
        d1["existing_position_symbols"].append("FAKE")
        assert "FAKE" not in d2["existing_position_symbols"]


# ===========================================================================
# AK32-AK37: Source-scan safety (no forbidden imports / network / env / signing)
# ===========================================================================

class TestAK32NoForbiddenImports:
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
        }
        assert not (bad & forbidden), f"forbidden imports leaked: {bad & forbidden}"


class TestAK33NoNetworkSymbols:
    def test_no_socket_or_urlopen_or_http_client_in_code(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "urlopen", "Request", "HTTPSConnection", "HTTPConnection",
            "socket.socket", "ssl.create_default_context",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAK34NoEnvOrDotenvReads:
    def test_no_environ_or_dotenv_calls(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "os.environ", "environ", "getenv",
            "load_dotenv", "dotenv_values",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAK35NoSigningTokens:
    def test_no_hmac_or_signature_construction(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "hmac.new", "hashlib.sha256", "hashlib.sha512",
            "X-BAPI-SIGN", "X-BAPI-API-KEY",
            "BybitExecutor(",
            "pybit.unified_trading", "HTTP(",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAK36NoRealSenderInvocation:
    def test_no_order_or_stop_endpoint_call(self):
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in (
            "place_order", "submit_order", "send_order",
            "set_trading_stop", "amend_order", "cancel_order",
        ):
            assert forbidden not in code_tokens, f"{forbidden} leaked into code"


class TestAK37PathRefsAreStringConstants:
    def test_endpoint_paths_only_appear_as_string_constants(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        assert ORDER_CREATE_PATH_REF in text
        assert TRADING_STOP_PATH_REF in text
        code_tokens = _read_code_only(SRC_PATH)
        assert ORDER_CREATE_PATH_REF not in code_tokens
        assert TRADING_STOP_PATH_REF not in code_tokens


# ===========================================================================
# AK38-AK43: Forbidden flag absence in preview script
# ===========================================================================

def _preview_add_argument_lines() -> str:
    """Return only the lines inside add_argument() calls of the preview CLI.

    This isolates the actual argparse-registered flags from any docstring /
    comment text that may mention forbidden flag *names* in negative form
    (e.g. "No --send-order flag is exposed by this CLI").
    """
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


class TestAK38NoExecuteRealEntryFlag:
    def test_preview_has_no_execute_real_entry_flag(self):
        assert "--execute-real-entry" not in _preview_add_argument_lines()


class TestAK39NoSendOrderFlag:
    def test_preview_has_no_send_order_flag(self):
        assert "--send-order" not in _preview_add_argument_lines()


class TestAK40NoPlaceOrderFlag:
    def test_preview_has_no_place_order_flag(self):
        assert "--place-order" not in _preview_add_argument_lines()


class TestAK41NoRealRunFlag:
    def test_preview_has_no_real_run_flag(self):
        assert "--real-run" not in _preview_add_argument_lines()


class TestAK42NoConfirmTokenFlag:
    def test_preview_has_no_confirm_token_flag(self):
        assert "--confirm-token" not in _preview_add_argument_lines()


class TestAK43NoExecuteTinyEntryFlag:
    def test_preview_has_no_execute_tiny_entry_flag(self):
        assert "--execute-tiny-entry" not in _preview_add_argument_lines()


# ===========================================================================
# AK44: Forbidden flag absence in src module too
# ===========================================================================

class TestAK44NoForbiddenFlagsInSrc:
    def test_src_has_no_real_execute_flag_parsing(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        for forbidden in (
            "--execute-real-entry", "--send-order", "--place-order",
            "--real-run", "--execute-tiny-entry",
        ):
            assert forbidden not in text, f"{forbidden} leaked into src"


# ===========================================================================
# AK45: 5 protected positions never appear as "touched"
# ===========================================================================

class TestAK45ProtectedPositionsUntouched:
    def test_existing_positions_touched_is_empty(self):
        r = _run()
        assert r.existing_positions_touched == []
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym not in r.existing_positions_touched

    def test_no_position_modified_flag(self):
        r = _run()
        assert r.no_position_modified is True


# ===========================================================================
# AK46: G20 never lifted (any mode)
# ===========================================================================

class TestAK46G20NotLifted:
    def test_g20_not_lifted_in_checklist(self):
        r = _run()
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_approval(self):
        r = _run(allow_dry_run_approval=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True

    def test_g20_not_lifted_in_real_entry_guard(self):
        r = _run(allow_real_entry_execution=True)
        assert r.g20_lifted is False
        assert r.g20_policy_still_in_place is True


# ===========================================================================
# AK47: Safety invariants set
# ===========================================================================

class TestAK47SafetyInvariants:
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
# AK48: Token pattern present but never validated
# ===========================================================================

class TestAK48TokenPattern:
    def test_pattern_is_documented_and_simulated_only(self):
        r = _run()
        assert r.entry_token_pattern == ENTRY_TOKEN_PATTERN
        assert r.sample_token == SAMPLE_TOKEN
        assert r.token_validation_simulated is True
        assert r.token_validated is False
        assert r.real_token_validated is False
        assert r.dry_run_authorization_result == DRY_RUN_AUTHORIZATION_RESULT


# ===========================================================================
# AK49: Required confirmation flags documented but never validated
# ===========================================================================

class TestAK49RequiredFlagsDocumentedNotValidated:
    def test_required_flags_doc_count_is_13(self):
        assert len(REQUIRED_HUMAN_CONFIRMATION_FLAGS) == 13

    def test_required_flags_documented_in_result(self):
        r = _run()
        assert isinstance(r.required_flags_dry_run, dict)
        # Sanity: dry-run-only template means flag count is 13 documented flags.
        assert len(REQUIRED_HUMAN_CONFIRMATION_FLAGS) == 13


# ===========================================================================
# AK50: next_required_task points at TASK-014AL
# ===========================================================================

class TestAK50NextRequiredTask:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == "TASK-014AL_guarded_entry_final_pre_execution_review"


# ===========================================================================
# AK51: Status precedence (FAIL_CLOSED > REAL_ENTRY_NOT_IMPL > APPROVAL > CHECKLIST)
# ===========================================================================

class TestAK51StatusPrecedence:
    def test_fail_closed_overrides_real_entry_guard(self):
        r = _run(readonly=None, allow_real_entry_execution=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_fail_closed_overrides_approval(self):
        r = _run(readonly=None, allow_dry_run_approval=True)
        assert r.status == STATUS_FAIL_CLOSED

    def test_real_entry_guard_takes_priority_over_approval(self):
        r = _run(allow_dry_run_approval=True, allow_real_entry_execution=True)
        assert r.status == STATUS_REAL_ENTRY_NOT_IMPL


# ===========================================================================
# AK52: Acceptable status whitelists are frozen / contain expected values
# ===========================================================================

class TestAK52AcceptableStatusFrozensets:
    def test_entry_manual_auth_design_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_MANUAL_AUTHORIZATION_DESIGN_READY" \
            in ACCEPTABLE_ENTRY_MANUAL_AUTH_DESIGN_STATUSES

    def test_entry_real_permission_review_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES, frozenset)
        assert "TINY_GUARDED_ENTRY_REAL_PERMISSION_REVIEW_READY" \
            in ACCEPTABLE_ENTRY_REAL_PERMISSION_REVIEW_STATUSES

    def test_guarded_entry_adapter_statuses_frozen(self):
        assert isinstance(ACCEPTABLE_GUARDED_ENTRY_ADAPTER_STATUSES, frozenset)

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
        ):
            assert isinstance(fs, frozenset)


# ===========================================================================
# AK53: Expected upstream invariants exposed
# ===========================================================================

class TestAK53ExpectedUpstreamInvariants:
    def test_expected_constants(self):
        assert EXPECTED_ENDPOINT_FAMILY == "bybit_demo"
        assert EXPECTED_ACCOUNT_MODE == "demo"
        assert EXPECTED_PROOF_STRENGTH == "STRONG"
        assert EXPECTED_POSITION_DETAILS_SOURCE == "real_readonly"
        assert EXPECTED_LIFECYCLE_STATUS == "MOCK_TINY_LIFECYCLE_SUCCESS"
        assert EXPECTED_INSTRUMENT_CATEGORY == "linear"


# ===========================================================================
# AK54: Endpoint allow/deny lists
# ===========================================================================

class TestAK54EndpointAllowDenyLists:
    def test_demo_allowlist(self):
        assert BASE_URL_DEMO_REF in DEMO_ENDPOINT_ALLOWLIST
        assert BASE_URL_LIVE_REF not in DEMO_ENDPOINT_ALLOWLIST

    def test_live_denylist(self):
        assert BASE_URL_LIVE_REF in LIVE_ENDPOINT_DENYLIST
        assert BASE_URL_DEMO_REF not in LIVE_ENDPOINT_DENYLIST


# ===========================================================================
# AK55: Forbidden log fields documented (so they CAN be checked downstream)
# ===========================================================================

class TestAK55ForbiddenLogFields:
    def test_forbidden_log_fields_documented(self):
        assert "api_key_value" in FORBIDDEN_LOG_FIELDS
        assert "api_secret_value" in FORBIDDEN_LOG_FIELDS
        assert "signature_value" in FORBIDDEN_LOG_FIELDS


# ===========================================================================
# AK56: Dry-run expected values for documentation
# ===========================================================================

class TestAK56DryRunExpectedValues:
    def test_dry_run_expected_constants(self):
        assert DRY_RUN_EXPECTED_SYMBOL == "SOLUSDT"
        assert DRY_RUN_EXPECTED_CATEGORY == "linear"
        assert DRY_RUN_EXPECTED_ENTRY_SIDE == "Buy"
        assert DRY_RUN_EXPECTED_QTY == 0.1
        assert DRY_RUN_EXPECTED_MAX_NOTIONAL_USDT == 10.0
        assert DRY_RUN_EXPECTED_POSITION_IDX == 0
        assert DRY_RUN_EXPECTED_REDUCE_ONLY is False
        assert DRY_RUN_EXPECTED_CLOSE_ON_TRIGGER is False
        assert DRY_RUN_EXPECTED_ORDER_TYPE == "Market"
        assert DRY_RUN_EXPECTED_STOP_LOSS == 61.18
        assert DRY_RUN_EXPECTED_TPSL_MODE == "Full"
        assert DRY_RUN_EXPECTED_SL_TRIGGER_BY == "MarkPrice"
        assert DRY_RUN_EXPECTED_EXISTING_COUNT == 5


# ===========================================================================
# AK57: Order-link-id prefix documented (template only, never sent)
# ===========================================================================

class TestAK57OrderLinkIdPrefix:
    def test_dry_run_prefix_documented(self):
        assert len(ENTRY_DRY_RUN_ORDER_LINK_ID_PREFIXES) >= 1
        for p in ENTRY_DRY_RUN_ORDER_LINK_ID_PREFIXES:
            assert "DRYRUN" in p or "MANUAL" in p or "AUTH" in p


# ===========================================================================
# AK58: Upstream statuses captured in result
# ===========================================================================

class TestAK58UpstreamStatusCapture:
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
        assert r.upstream_entry_manual_auth_design_readiness_conclusion \
            == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AK59: CLI subprocess exit codes
# ===========================================================================

class TestAK59CLIExitCodes:
    def test_help_exits_zero(self):
        result = subprocess.run(
            [sys.executable, str(PREVIEW_PATH), "--help"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        assert result.returncode == 0
        assert "manual" in result.stdout.lower() or "dry" in result.stdout.lower()

    def test_missing_artifacts_exits_one(self, repo_tmp_path):
        empty = repo_tmp_path / "empty"
        empty.mkdir()
        # Point every upstream dir at an empty location => all missing.
        from scripts.preview_demo_tiny_guarded_entry_manual_authorization_dry_run import (
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
            output_dir=repo_tmp_path / "out",
        )
        assert rc == 1


# ===========================================================================
# AK60: run_execute writes JSON + MD reports
# ===========================================================================

class TestAK60ReportArtifacts:
    def test_write_report_creates_files(self, repo_tmp_path):
        from scripts.preview_demo_tiny_guarded_entry_manual_authorization_dry_run import (
            _write_report,
        )
        r = _run()
        out_dir = repo_tmp_path / "out"
        _write_report(r, out_dir)
        latest_json = out_dir / "latest_tiny_guarded_entry_manual_authorization_dry_run.json"
        latest_md   = out_dir / "latest_tiny_guarded_entry_manual_authorization_dry_run.md"
        assert latest_json.exists()
        assert latest_md.exists()
        parsed = json.loads(latest_json.read_text(encoding="utf-8"))
        assert parsed["status"] == STATUS_DRY_RUN_READY
        md_text = latest_md.read_text(encoding="utf-8")
        assert "TASK-014AK" in md_text
        assert ENTRY_TOKEN_PATTERN in md_text


# ===========================================================================
# AK61: real_execution_allowed never True regardless of inputs
# ===========================================================================

class TestAK61RealExecutionNeverAllowed:
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
# AK62: Existing position symbols documented in result
# ===========================================================================

class TestAK62ExistingPositionSymbols:
    def test_existing_position_symbols_reflect_recon(self):
        r = _run()
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols


# ===========================================================================
# AK63: Sample token matches pattern (simulated, never used)
# ===========================================================================

class TestAK63SampleTokenMatchesPattern:
    def test_sample_token_has_expected_shape(self):
        # CONFIRM_DEMO_TINY_ENTRY_{YYYYMMDD}_SOLUSDT
        parts = SAMPLE_TOKEN.split("_")
        assert parts[0] == "CONFIRM"
        assert parts[1] == "DEMO"
        assert parts[2] == "TINY"
        assert parts[3] == "ENTRY"
        assert parts[-1] == "SOLUSDT"
        assert parts[-2].isdigit()
        assert len(parts[-2]) == 8


# ===========================================================================
# AK64: Pattern only documented in code, not used to validate
# ===========================================================================

class TestAK64TokenNeverValidated:
    def test_pattern_appears_in_code_as_string_constant_only(self):
        text = SRC_PATH.read_text(encoding="utf-8")
        assert ENTRY_TOKEN_PATTERN in text
        # No regex-based validation of real tokens
        code_tokens = _read_code_only(SRC_PATH)
        for forbidden in ("re.match", "re.fullmatch", "re.compile"):
            assert forbidden not in code_tokens, f"{forbidden} suggests token validation"
