"""
tests/demo_trading/test_demo_tiny_lifecycle_guarded_runner_design_review.py
TASK-014AD: Tiny Lifecycle Real Execution Guarded Runner Design Review
tests (AD1 - AD73+).

Covers design_review_checklist / guarded_design_approval_dry_run /
real_runner_execution_guard / fail_closed paths; all 9 stages; 97 gate
constants; W/X/Y/Z/AA/AB/AC readiness matrix; future guarded command
catalogue (entry-only / stop-attach-only / cleanup-only, no full
lifecycle single command); manual token-per-step authorization model;
required confirmation flags (--i-understand-this-is-demo-real-execution
/ --max-notional-usdt 10 / --expected-existing-position-count 5 /
--expected-existing-symbols ...); demo endpoint allowlist + live
endpoint denylist; pre/post readonly contract; failure and abort
review (FAIL_CLOSED / MANUAL_REVIEW_REQUIRED with no auto retry /
auto cleanup / auto emergency_close); status precedence; source-scan
safety (no urlopen / no forbidden imports / no signing / no
os.environ); report artifacts; forbidden-flag absence
(--execute-real-* / --send-order / --place-order / --real-run); the
invariant that TASK-014L sender G20 (protected_entry_policy_missing)
still blocks --execute-new-entry and is NOT lifted here; and the
13-artifact preflight contract (10 baseline + 014AA lifecycle summary
+ 014AB runner design + 014AC runner dry-run).
"""
from __future__ import annotations

import ast
import json
import os
import subprocess
import sys
import tempfile
import tokenize
from datetime import datetime, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_tiny_lifecycle_guarded_runner_design_review import (
    ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES,
    ACCEPTABLE_RUNNER_DESIGN_STATUSES,
    ACCEPTABLE_RUNNER_DRY_RUN_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    BASE_URL_LIVE_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DEMO_ENDPOINT_ALLOWLIST,
    DemoTinyLifecycleGuardedRunnerDesignReview,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    FORBIDDEN_LOG_FIELDS,
    FORBIDDEN_SINGLE_LIFECYCLE_COMMAND,
    FUTURE_GUARDED_COMMANDS,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_AA_ACCEPTABLE,
    GATE_AB_ACCEPTABLE,
    GATE_AC_ACCEPTABLE,
    GATE_CLEANUP_ONLY_COMMAND_REQUIRED,
    GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
    GATE_CONTRACT_MISSING,
    GATE_DEMO_ENDPOINT_ALLOWLIST,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_ONLY_COMMAND_REQUIRED,
    GATE_ENTRY_TOKEN_PATTERN_PRESENT,
    GATE_EXISTING_FIVE_POSITIONS_UNCHANGED,
    GATE_EXISTING_POSITION_TOUCHED_MANUAL_REVIEW,
    GATE_EXPECTED_EXISTING_SYMBOLS_REQUIRED,
    GATE_FRESH_READONLY_PRE_CHECK_REQUIRED,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_GUARDED_DESIGN_REVIEW_ONLY,
    GATE_GUARDED_RUNNER_NOT_IMPLEMENTED,
    GATE_HUMAN_STOP_BETWEEN_STEPS_REQUIRED,
    GATE_ISOLATED_OUTPUT_DIR_REQUIRED,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_LIVE_ENDPOINT_DENYLIST,
    GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
    GATE_MAX_NOTIONAL_CAP_REQUIRED,
    GATE_MISMATCH_MANUAL_REVIEW,
    GATE_NO_AUTO_CLEANUP,
    GATE_NO_AUTO_EMERGENCY_CLOSE,
    GATE_NO_AUTO_NEXT_STEP,
    GATE_NO_AUTO_RETRY,
    GATE_NO_AUTOMATIC_CLEANUP,
    GATE_NO_AUTOMATIC_EMERGENCY_CLOSE,
    GATE_NO_AUTOMATIC_NEXT_STEP,
    GATE_NO_AUTOMATIC_RETRY,
    GATE_NO_BACKGROUND_LOOP,
    GATE_NO_BACKGROUND_WORKER,
    GATE_NO_CRON,
    GATE_NO_DAEMON,
    GATE_NO_DISCORD_TRIGGER,
    GATE_NO_ENDPOINT_INVOKED,
    GATE_NO_FALLBACK_ENDPOINT,
    GATE_NO_FULL_LIFECYCLE_SINGLE_COMMAND,
    GATE_NO_G20_LIFT,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_NOTION_TRIGGER,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_POSITION_MODIFIED_SCOPE,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SCHEDULER,
    GATE_NO_SECRETS_EMITTED,
    GATE_NO_SECRETS_LOADED,
    GATE_NOOP_PLAN_MISSING,
    GATE_ONE_COMMAND_ONE_STEP,
    GATE_PARTIAL_FILL_FAIL_CLOSED,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POST_CLEANUP_REQUIRED,
    GATE_POST_ENTRY_REQUIRED,
    GATE_POST_READONLY_REQUIRED,
    GATE_POST_STOP_REQUIRED,
    GATE_PRE_CHECK_REQUIRED,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_READINESS_NOT_EXECUTABLE,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAIL_FAIL_CLOSED_FAILURE,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_REAL_EXECUTION_NOT_ALLOWED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_RUNNER_EXECUTION_NOT_IMPL,
    GATE_REAL_RUNNER_NOT_IMPLEMENTED,
    GATE_RECONCILIATION_MISSING,
    GATE_REQUEST_REJECTED_FAIL_CLOSED,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_RUNNER_DRY_RUN_STATUS_UNACCEPTABLE,
    GATE_SECOND_CONFIRMATION_REQUIRED,
    GATE_SECRET_EMISSION_FAIL_CLOSED,
    GATE_SECRETS_NOT_READ,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_ONLY_COMMAND_REQUIRED,
    GATE_STOP_TOKEN_PATTERN_PRESENT,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
    GATE_TOKEN_INCLUDES_DATE_POLICY,
    GATE_TOKEN_INCLUDES_SYMBOL,
    GATE_TOKEN_PER_STEP,
    GATE_TOKENS_NOT_VALIDATED,
    GATE_W_ACCEPTABLE,
    GATE_X_ACCEPTABLE,
    GATE_Y_ACCEPTABLE,
    GATE_Z_ACCEPTABLE,
    MODE_DESIGN_REVIEW_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_GUARDED_DESIGN_APPROVAL_DRY_RUN,
    MODE_REAL_RUNNER_EXECUTION_GUARD,
    ORDER_CREATE_PATH_REF,
    READINESS_CONCLUSION_NOT_EXECUTABLE,
    REQUIRED_CONFIRMATION_FLAGS,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_REVIEW_SCOPE,
    STAGE_2_READINESS_MATRIX,
    STAGE_3_GUARDED_RUNNER_MINIMUM_REQUIREMENTS,
    STAGE_4_MANUAL_AUTHORIZATION_MODEL,
    STAGE_5_ENVIRONMENT_ISOLATION_REVIEW,
    STAGE_6_PRE_POST_READONLY_CONTRACT,
    STAGE_7_FAILURE_AND_ABORT_REVIEW,
    STAGE_8_FINAL_GUARDED_DESIGN_VERDICT,
    STATUS_DESIGN_REVIEW_READY,
    STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_RUNNER_NOT_IMPL,
    STOP_ATTACH_TOKEN_PATTERN,
    TRADING_STOP_PATH_REF,
    TinyLifecycleGuardedRunnerDesignReviewResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_lifecycle_guarded_runner_design_review.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_lifecycle_guarded_runner_design_review.py"
_TEST_NOW    = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

def _valid_readonly() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T10:00:00Z",
        "endpoint_family":        EXPECTED_ENDPOINT_FAMILY,
        "account_mode":           EXPECTED_ACCOUNT_MODE,
        "proof_strength":         EXPECTED_PROOF_STRENGTH,
        "demo_runtime_verified":  True,
        "equity_usd":             500.0,
        "available_balance_usd":  400.0,
    }


def _valid_reconciliation() -> dict:
    return {
        "timestamp_utc":           "2026-06-10T10:05:00Z",
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
        "timestamp_utc":          "2026-06-10T11:00:00Z",
        "selected_symbol":        "SOLUSDT",
        "selected_side":          "long",
        "selected_qty":           12.2,
        "entry_reference_price":  64.87,
        "stop_price":             61.63,
        "protected_entry_status": "PREVIEW_ONLY",
        "preview_only":           True,
    }


def _valid_contract() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:30:00Z",
        "mode":               "preview",
        "selected_symbol":    "SOLUSDT",
        "path":               TRADING_STOP_PATH_REF,
        "method":             "POST",
        "real_probe_allowed": False,
        "status":             "TRADING_STOP_CONTRACT_PREVIEW_OK",
    }


def _valid_noop_plan() -> dict:
    return {
        "timestamp_utc":     "2026-06-10T11:45:00Z",
        "mode":              "plan",
        "selected_symbol":   "SOLUSDT",
        "recommended_path":  "real_tiny_position_with_stop_lifecycle",
        "status":            "NOOP_PROBE_PLAN_READY",
    }


def _valid_lifecycle() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:55:00Z",
        "mode":                      "mock_lifecycle",
        "selected_symbol":           "SOLUSDT",
        "side":                      "long",
        "tiny_qty":                  0.1,
        "tiny_notional":             6.487,
        "entry_reference_price":     64.87,
        "stop_price":                61.63,
        "status":                    "MOCK_TINY_LIFECYCLE_SUCCESS",
        "failed_phase":              "",
        "dangling_tiny_position":    False,
        "existing_positions_touched": [],
    }


def _valid_real_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:58:00Z",
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
        "timestamp_utc":             "2026-06-10T11:59:00Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
        "rounded_tiny_qty":          0.1,
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_tiny_stop_attach_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:59:30Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
        "stop_price":                61.63,
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_tiny_cleanup_permission_gate() -> dict:
    return {
        "timestamp_utc":             "2026-06-10T11:59:45Z",
        "mode":                      "checklist",
        "selected_symbol":           "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":                    "TINY_CLEANUP_PERMISSION_CHECKLIST_READY",
        "expected_tiny_qty":         0.1,
        "cleanup_side":              "Sell",
        "real_execution_allowed":              False,
        "current_task_real_execution_allowed": False,
    }


def _valid_lifecycle_summary() -> dict:
    return {
        "timestamp_utc":                  "2026-06-10T11:59:55Z",
        "mode":                           "checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY",
        "expected_entry_reference_price": 64.87,
        "real_execution_allowed":              False,
        "real_lifecycle_runner_implemented":   False,
        "current_task_real_execution_allowed": False,
    }


def _valid_runner_design() -> dict:
    return {
        "timestamp_utc":                  "2026-06-10T11:59:58Z",
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
        "timestamp_utc":                  "2026-06-10T11:59:59Z",
        "mode":                           "dry_run_checklist",
        "selected_symbol":                "SOLUSDT",
        "status":                         "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY",
        "real_execution_allowed":              False,
        "real_runner_implemented":             False,
        "current_task_real_execution_allowed": False,
        "dry_run_trace_complete":              True,
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


def _gate() -> DemoTinyLifecycleGuardedRunnerDesignReview:
    return DemoTinyLifecycleGuardedRunnerDesignReview()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    tiny_stop_attach_permission_gate=_UNSET,
    tiny_cleanup_permission_gate=_UNSET,
    lifecycle_summary=_UNSET,
    runner_design=_UNSET,
    runner_dry_run=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_guarded_design_approval=False,
    allow_real_runner_execution=False,
    _now=_TEST_NOW,
) -> TinyLifecycleGuardedRunnerDesignReviewResult:
    return _gate().run_checklist(
        readonly_smoke=_valid_readonly()                               if readonly             is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                         if recon                is _UNSET else recon,
        protection=_valid_protection()                                 if protection           is _UNSET else protection,
        contract=_valid_contract()                                     if contract             is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                   if noop_plan            is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                              if lifecycle            is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()             if real_permission_gate is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate() if tiny_entry_permission_gate is _UNSET else tiny_entry_permission_gate,
        tiny_stop_attach_permission_gate=_valid_tiny_stop_attach_permission_gate() if tiny_stop_attach_permission_gate is _UNSET else tiny_stop_attach_permission_gate,
        tiny_cleanup_permission_gate=_valid_tiny_cleanup_permission_gate() if tiny_cleanup_permission_gate is _UNSET else tiny_cleanup_permission_gate,
        lifecycle_summary=_valid_lifecycle_summary()                   if lifecycle_summary    is _UNSET else lifecycle_summary,
        runner_design=_valid_runner_design()                           if runner_design        is _UNSET else runner_design,
        runner_dry_run=_valid_runner_dry_run()                         if runner_dry_run       is _UNSET else runner_dry_run,
        symbol=symbol,
        allow_guarded_design_approval=allow_guarded_design_approval,
        allow_real_runner_execution=allow_real_runner_execution,
        _now=_now,
    )


# ===========================================================================
# AD1: valid design review => DESIGN_REVIEW_READY
# ===========================================================================

class TestAD1DesignReviewReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_DESIGN_REVIEW_READY
        assert r.mode == MODE_DESIGN_REVIEW_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.guarded_runner_implemented is False
        assert r.guarded_runner_design_review is True
        assert r.current_task_real_execution_allowed is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert r.next_required_task == (
            "TASK-014AE_guarded_entry_only_dry_run_adapter"
        )


# ===========================================================================
# AD2: --allow-guarded-design-approval => DESIGN_REVIEW_READY_EXEC_DISABLED
# ===========================================================================

class TestAD2GuardedDesignApprovalDryRun:
    def test_approval(self):
        r = _run(allow_guarded_design_approval=True)
        assert r.status == STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED
        assert r.mode == MODE_GUARDED_DESIGN_APPROVAL_DRY_RUN
        assert r.guarded_design_approval_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.guarded_runner_implemented is False
        assert r.readiness_conclusion == READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AD3: --allow-real-runner-execution => REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAD3RealRunnerExecutionGuard:
    def test_guard(self):
        r = _run(allow_real_runner_execution=True)
        assert r.status == STATUS_REAL_RUNNER_NOT_IMPL
        assert r.mode == MODE_REAL_RUNNER_EXECUTION_GUARD
        assert r.real_runner_execution_requested is True
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.guarded_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.no_position_modified is True


# ===========================================================================
# AD4-AD16: 13 missing upstream artifacts each => FAIL_CLOSED
# ===========================================================================

class TestAD4MissingReadonly:
    def test_fail_closed(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAD5MissingReconciliation:
    def test_fail_closed(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAD6MissingProtection:
    def test_fail_closed(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAD7MissingContract:
    def test_fail_closed(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAD8MissingNoopPlan:
    def test_fail_closed(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAD9MissingLifecycle:
    def test_fail_closed(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAD10MissingRealPermissionGate:
    def test_fail_closed(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAD11MissingTinyEntryPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAD12MissingTinyStopAttachPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_stop_attach_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAD13MissingTinyCleanupPermissionGate:
    def test_fail_closed(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAD14MissingLifecycleSummary:
    def test_fail_closed(self):
        r = _run(lifecycle_summary=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_SUMMARY_MISSING in r.blocked_gates


class TestAD15MissingRunnerDesign:
    def test_fail_closed(self):
        r = _run(runner_design=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DESIGN_MISSING in r.blocked_gates


class TestAD16MissingRunnerDryRun:
    def test_fail_closed(self):
        r = _run(runner_dry_run=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_MISSING in r.blocked_gates


# ===========================================================================
# AD17: selected symbol collides with existing demo position
# ===========================================================================

class TestAD17SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_fail_closed(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# AD18-AD21: upstream invariant mismatches
# ===========================================================================

class TestAD18EndpointFamilyMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["endpoint_family"] = "bybit_live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAD19AccountModeMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["account_mode"] = "live"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAD20ProofStrengthMismatch:
    def test_fail_closed(self):
        bad = _valid_readonly()
        bad["proof_strength"] = "WEAK"
        r = _run(readonly=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAD21PositionDetailsSourceMismatch:
    def test_fail_closed(self):
        bad = _valid_reconciliation()
        bad["position_details_source"] = "mock"
        bad["mode"] = "mock"
        r = _run(recon=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# AD22: runner_dry_run status unacceptable
# ===========================================================================

class TestAD22RunnerDryRunStatusUnacceptable:
    def test_fail_closed(self):
        bad = _valid_runner_dry_run()
        bad["status"] = "SOMETHING_ELSE"
        r = _run(runner_dry_run=bad)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RUNNER_DRY_RUN_STATUS_UNACCEPTABLE in r.blocked_gates


# ===========================================================================
# AD23: missing --symbol
# ===========================================================================

class TestAD23MissingSymbol:
    def test_fail_closed(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AD24: 9 stages present
# ===========================================================================

class TestAD249Stages:
    def test_stage_count(self):
        r = _run()
        assert len(r.stages) == 9
        assert r.stage_order == list(ALL_STAGES)
        for stage_id in ALL_STAGES:
            assert stage_id in r.stages
            assert r.stages[stage_id]["stage"] == stage_id


# ===========================================================================
# AD25: review scope content
# ===========================================================================

class TestAD25ReviewScope:
    def test_scope_flags(self):
        r = _run()
        s = r.review_scope
        assert s["guarded_runner_design_review"] is True
        assert s["real_runner_implemented"] is False
        assert s["guarded_runner_implemented"] is False
        assert s["real_execution_allowed"] is False
        assert s["order_endpoint_called"] is False
        assert s["stop_endpoint_called"] is False
        assert s["no_endpoint_invoked_in_this_task"] is True
        assert s["no_position_modified"] is True
        assert s["no_secrets_loaded"] is True
        assert s["g20_policy_still_in_place"] is True
        assert s["g20_lifted"] is False
        assert s["next_required_task"] == "TASK-014AE_guarded_entry_only_dry_run_adapter"


# ===========================================================================
# AD26: readiness matrix W/X/Y/Z/AA/AB/AC + conclusion
# ===========================================================================

class TestAD26ReadinessMatrix:
    def test_all_acceptable(self):
        r = _run()
        m = r.readiness_matrix
        assert m["w_real_permission_gate_acceptable"] is True
        assert m["x_tiny_entry_permission_gate_acceptable"] is True
        assert m["y_tiny_stop_attach_permission_gate_acceptable"] is True
        assert m["z_tiny_cleanup_permission_gate_acceptable"] is True
        assert m["aa_tiny_lifecycle_summary_acceptable"] is True
        assert m["ab_runner_design_acceptable"] is True
        assert m["ac_runner_dry_run_acceptable"] is True
        assert m["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert m["readiness_conclusion_not_executable"] is True
        assert m["ready_to_execute"] is False

    def test_all_seven_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_W_ACCEPTABLE, GATE_X_ACCEPTABLE, GATE_Y_ACCEPTABLE,
                  GATE_Z_ACCEPTABLE, GATE_AA_ACCEPTABLE, GATE_AB_ACCEPTABLE,
                  GATE_AC_ACCEPTABLE, GATE_READINESS_NOT_EXECUTABLE):
            assert g in blocked


# ===========================================================================
# AD27: readiness_conclusion never READY_TO_EXECUTE
# ===========================================================================

class TestAD27ReadinessConclusion:
    def test_default(self):
        r = _run()
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"
        assert r.readiness_conclusion != "READY_TO_EXECUTE"

    def test_with_approval(self):
        r = _run(allow_guarded_design_approval=True)
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"

    def test_with_real_guard(self):
        r = _run(allow_real_runner_execution=True)
        assert r.readiness_conclusion == "DESIGN_REVIEW_READY_NOT_EXECUTABLE"

    def test_value_never_executable(self):
        assert READINESS_CONCLUSION_NOT_EXECUTABLE == (
            "DESIGN_REVIEW_READY_NOT_EXECUTABLE"
        )
        assert "READY_TO_EXECUTE" not in READINESS_CONCLUSION_NOT_EXECUTABLE


# ===========================================================================
# AD28: guarded runner minimum requirements (3 commands + forbidden full)
# ===========================================================================

class TestAD28GuardedRunnerMinimumRequirements:
    def test_three_future_commands(self):
        r = _run()
        req = r.guarded_runner_minimum_requirements
        assert req["future_guarded_commands"] == [
            "guarded_entry_only",
            "guarded_stop_attach_only",
            "guarded_cleanup_only",
        ]
        assert req["forbidden_single_lifecycle_command"] == "guarded_full_lifecycle"
        assert req["entry_only_command_required"] is True
        assert req["stop_only_command_required"] is True
        assert req["cleanup_only_command_required"] is True
        assert req["no_full_lifecycle_single_command"] is True

    def test_per_step_requirements(self):
        r = _run()
        ps = r.guarded_runner_minimum_requirements["per_step_requirements"]
        for key in ("matching_symbol", "matching_qty", "matching_side",
                    "fresh_readonly_pre_check", "fresh_artifact_timestamp",
                    "manual_token", "second_confirmation_flag",
                    "explicit_current_date", "isolated_output_directory",
                    "post_readonly_verification", "human_stop_between_steps"):
            assert ps[key] is True

    def test_no_auto_anything(self):
        r = _run()
        req = r.guarded_runner_minimum_requirements
        assert req["no_auto_next_step"] is True
        assert req["no_auto_retry"] is True
        assert req["no_auto_cleanup"] is True
        assert req["no_auto_emergency_close"] is True
        assert req["no_background_loop"] is True

    def test_gates_all_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_ENTRY_ONLY_COMMAND_REQUIRED,
                  GATE_STOP_ONLY_COMMAND_REQUIRED,
                  GATE_CLEANUP_ONLY_COMMAND_REQUIRED,
                  GATE_NO_FULL_LIFECYCLE_SINGLE_COMMAND,
                  GATE_FRESH_READONLY_PRE_CHECK_REQUIRED,
                  GATE_POST_READONLY_REQUIRED,
                  GATE_ISOLATED_OUTPUT_DIR_REQUIRED,
                  GATE_HUMAN_STOP_BETWEEN_STEPS_REQUIRED,
                  GATE_NO_AUTO_NEXT_STEP, GATE_NO_AUTO_RETRY,
                  GATE_NO_AUTO_CLEANUP, GATE_NO_AUTO_EMERGENCY_CLOSE,
                  GATE_NO_BACKGROUND_LOOP):
            assert g in blocked


# ===========================================================================
# AD29: manual authorization model
# ===========================================================================

class TestAD29ManualAuthorizationModel:
    def test_token_patterns(self):
        r = _run()
        m = r.manual_authorization_model
        assert m["entry_token_pattern"] == ENTRY_TOKEN_PATTERN
        assert m["stop_attach_token_pattern"] == STOP_ATTACH_TOKEN_PATTERN
        assert m["cleanup_token_pattern"] == CLEANUP_TOKEN_PATTERN
        assert m["token_per_step"] is True
        assert m["token_includes_date_policy"] is True
        assert m["token_includes_symbol"] is True
        assert m["token_format_not_authorization"] is True
        assert m["tokens_not_validated_in_this_task"] is True

    def test_required_flags(self):
        r = _run()
        m = r.manual_authorization_model
        assert m["required_confirmation_flags"] == list(REQUIRED_CONFIRMATION_FLAGS)
        assert m["second_confirmation_required"] is True
        assert m["max_notional_cap_required"] is True
        assert m["expected_existing_position_count"] == 5
        assert m["expected_existing_symbols"] == list(EXISTING_POSITION_SYMBOLS)
        assert m["expected_existing_symbols_required"] is True

    def test_gates_all_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_ENTRY_TOKEN_PATTERN_PRESENT,
                  GATE_STOP_TOKEN_PATTERN_PRESENT,
                  GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
                  GATE_TOKEN_PER_STEP, GATE_TOKEN_INCLUDES_DATE_POLICY,
                  GATE_TOKEN_INCLUDES_SYMBOL,
                  GATE_SECOND_CONFIRMATION_REQUIRED,
                  GATE_MAX_NOTIONAL_CAP_REQUIRED,
                  GATE_EXPECTED_EXISTING_SYMBOLS_REQUIRED,
                  GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
                  GATE_TOKENS_NOT_VALIDATED):
            assert g in blocked


# ===========================================================================
# AD30: environment isolation review
# ===========================================================================

class TestAD30EnvironmentIsolationReview:
    def test_allowlist_denylist(self):
        r = _run()
        e = r.environment_isolation_review
        assert e["demo_endpoint_allowlist"] == [BASE_URL_DEMO_REF]
        assert e["live_endpoint_denylist"] == [BASE_URL_LIVE_REF]
        assert e["no_fallback_endpoint"] is True

    def test_no_background(self):
        r = _run()
        e = r.environment_isolation_review
        assert e["one_command_one_step"] is True
        assert e["no_daemon"] is True
        assert e["no_cron"] is True
        assert e["no_scheduler"] is True
        assert e["no_background_worker"] is True
        assert e["no_discord_trigger"] is True
        assert e["no_notion_trigger"] is True

    def test_secrets_policy(self):
        r = _run()
        e = r.environment_isolation_review
        assert e["secrets_only_in_future_real_step"] is True
        assert e["secrets_not_in_report"] is True
        assert e["secrets_not_read_in_this_task"] is True
        assert e["forbidden_log_fields"] == list(FORBIDDEN_LOG_FIELDS)

    def test_gates_all_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_DEMO_ENDPOINT_ALLOWLIST, GATE_LIVE_ENDPOINT_DENYLIST,
                  GATE_NO_FALLBACK_ENDPOINT, GATE_ONE_COMMAND_ONE_STEP,
                  GATE_NO_DAEMON, GATE_NO_CRON, GATE_NO_SCHEDULER,
                  GATE_NO_BACKGROUND_WORKER, GATE_NO_DISCORD_TRIGGER,
                  GATE_NO_NOTION_TRIGGER, GATE_SECRETS_NOT_READ):
            assert g in blocked


# ===========================================================================
# AD31: pre/post readonly contract
# ===========================================================================

class TestAD31PrePostReadonlyContract:
    def test_pre_check(self):
        r = _run()
        c = r.pre_post_readonly_contract
        pre = c["pre_check"]
        assert pre["account_mode_demo"] is True
        assert pre["endpoint_family_bybit_demo"] is True
        assert pre["existing_five_positions_unchanged"] is True
        assert pre["selected_symbol_absent_before_entry"] is True
        assert pre["selected_symbol_present_before_stop"] is True
        assert pre["selected_symbol_present_before_cleanup"] is True

    def test_post_entry_stop_cleanup(self):
        r = _run()
        c = r.pre_post_readonly_contract
        assert c["post_entry"]["selected_symbol_position_appears"] is True
        assert c["post_entry"]["qty_equals_expected_tiny_qty"] is True
        assert c["post_entry"]["side_equals_long"] is True
        assert c["post_stop"]["selected_symbol_stop_loss_equals_expected"] is True
        assert c["post_cleanup"]["selected_symbol_absent_or_zero"] is True
        assert c["post_cleanup"]["existing_five_positions_unchanged"] is True

    def test_failure_routing(self):
        r = _run()
        c = r.pre_post_readonly_contract
        assert c["readonly_unavailable_fail_closed"] is True
        assert c["mismatch_manual_review"] is True
        assert c["existing_five_positions_unchanged_requirement"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_PRE_CHECK_REQUIRED, GATE_POST_ENTRY_REQUIRED,
                  GATE_POST_STOP_REQUIRED, GATE_POST_CLEANUP_REQUIRED,
                  GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
                  GATE_MISMATCH_MANUAL_REVIEW,
                  GATE_EXISTING_FIVE_POSITIONS_UNCHANGED):
            assert g in blocked


# ===========================================================================
# AD32: failure and abort review
# ===========================================================================

class TestAD32FailureAndAbortReview:
    def test_fail_closed_paths(self):
        r = _run()
        f = r.failure_and_abort_review
        assert f["request_rejected"] == "FAIL_CLOSED"
        assert f["partial_fill"] == "FAIL_CLOSED"
        assert f["readonly_unavailable"] == "FAIL_CLOSED"
        assert f["selected_symbol_mismatch"] == "FAIL_CLOSED"
        assert f["existing_position_touched"] == "MANUAL_REVIEW_REQUIRED"
        assert f["live_endpoint_detected"] == "FAIL_CLOSED"
        assert f["secret_emission_detected"] == "FAIL_CLOSED"

    def test_no_automatic(self):
        r = _run()
        f = r.failure_and_abort_review
        assert f["no_automatic_retry"] is True
        assert f["no_automatic_cleanup"] is True
        assert f["no_automatic_emergency_close"] is True
        assert f["no_automatic_next_step"] is True
        assert f["manual_intervention_only"] is True

    def test_gates_present(self):
        r = _run()
        blocked = set(r.blocked_gates)
        for g in (GATE_REQUEST_REJECTED_FAIL_CLOSED,
                  GATE_PARTIAL_FILL_FAIL_CLOSED,
                  GATE_READONLY_UNAVAIL_FAIL_CLOSED_FAILURE,
                  GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED,
                  GATE_EXISTING_POSITION_TOUCHED_MANUAL_REVIEW,
                  GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
                  GATE_SECRET_EMISSION_FAIL_CLOSED,
                  GATE_NO_AUTOMATIC_RETRY, GATE_NO_AUTOMATIC_CLEANUP,
                  GATE_NO_AUTOMATIC_EMERGENCY_CLOSE,
                  GATE_NO_AUTOMATIC_NEXT_STEP):
            assert g in blocked


# ===========================================================================
# AD33: final guarded design verdict
# ===========================================================================

class TestAD33FinalGuardedDesignVerdict:
    def test_default(self):
        r = _run()
        v = r.final_guarded_design_verdict
        assert v["guarded_design_approval_allowed"] is False
        assert v["real_runner_execution_requested"] is False
        assert v["real_execution_allowed"] is False
        assert v["real_runner_implemented"] is False
        assert v["guarded_runner_implemented"] is False
        assert v["guarded_runner_design_review"] is True
        assert v["current_task_real_execution_allowed"] is False
        assert v["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        assert v["g20_policy_still_in_place"] is True
        assert v["g20_lifted"] is False
        assert v["no_real_order_endpoint"] is True
        assert v["no_real_stop_endpoint"] is True
        assert v["no_position_modified"] is True
        assert v["no_live_endpoint"] is True
        assert v["no_secrets_loaded"] is True
        assert v["no_secrets_emitted"] is True
        assert v["order_endpoint_called"] is False
        assert v["stop_endpoint_called"] is False
        assert v["status"] == STATUS_DESIGN_REVIEW_READY
        assert v["mode"] == MODE_DESIGN_REVIEW_CHECKLIST
        assert v["next_required_task"] == "TASK-014AE_guarded_entry_only_dry_run_adapter"

    def test_approval(self):
        r = _run(allow_guarded_design_approval=True)
        assert r.final_guarded_design_verdict["status"] == STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED
        assert r.final_guarded_design_verdict["mode"] == MODE_GUARDED_DESIGN_APPROVAL_DRY_RUN

    def test_guard(self):
        r = _run(allow_real_runner_execution=True)
        v = r.final_guarded_design_verdict
        assert v["status"] == STATUS_REAL_RUNNER_NOT_IMPL
        assert v["mode"] == MODE_REAL_RUNNER_EXECUTION_GUARD
        assert v["real_runner_execution_requested"] is True
        assert v["real_execution_allowed"] is False


# ===========================================================================
# AD34: g20 still in place (not lifted)
# ===========================================================================

class TestAD34G20NotLifted:
    def test_g20_invariants(self):
        for kw in ({}, {"allow_guarded_design_approval": True},
                   {"allow_real_runner_execution": True}):
            r = _run(**kw)
            assert r.g20_policy_still_in_place is True
            assert r.g20_lifted is False
            assert GATE_G20_NOT_LIFTED in r.blocked_gates
            assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
            assert GATE_NO_G20_LIFT in r.blocked_gates


# ===========================================================================
# AD35: socket-disabled import smoke
# ===========================================================================

class TestAD35SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_lifecycle_guarded_runner_design_review as m; "
             "print('OK', m.STATUS_DESIGN_REVIEW_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# AD36: dataclass roundtrip with deep-copy
# ===========================================================================

class TestAD36DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_guarded_design_approval=True)
        d = r.to_dict()
        for key, expected in (
            ("order_endpoint_called",               False),
            ("stop_endpoint_called",                False),
            ("no_position_modified",                True),
            ("no_live_endpoint",                    True),
            ("no_orders_sent",                      True),
            ("no_batch_order",                      True),
            ("no_close_only_path",                  True),
            ("emergency_close_invoked",             False),
            ("leverage_mutated",                    False),
            ("transfer_invoked",                    False),
            ("no_secrets_loaded",                   True),
            ("secret_value_observed",               False),
            ("g20_policy_still_in_place",           True),
            ("g20_lifted",                          False),
            ("current_task_real_execution_allowed", False),
            ("real_runner_implemented",             False),
            ("guarded_runner_implemented",          False),
            ("guarded_runner_design_review",       True),
            ("real_execution_allowed",              False),
            ("guarded_design_approval_allowed",     True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED
        assert d["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_2_READINESS_MATRIX]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_2_READINESS_MATRIX]
        d["review_scope"]["mutated"] = True
        assert "mutated" not in r.review_scope
        d["readiness_matrix"]["mutated"] = True
        assert "mutated" not in r.readiness_matrix
        d["manual_authorization_model"]["mutated"] = True
        assert "mutated" not in r.manual_authorization_model


# ===========================================================================
# AD37: path refs
# ===========================================================================

class TestAD37PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF
        assert r.base_url_ref != BASE_URL_LIVE_REF


# ===========================================================================
# AD38: safety invariants on dataclass (default / approval / guard)
# ===========================================================================

class TestAD38SafetyInvariants:
    def test_default(self):
        r = _run()
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True
        assert r.no_batch_order is True
        assert r.no_close_only_path is True
        assert r.emergency_close_invoked is False
        assert r.leverage_mutated is False
        assert r.transfer_invoked is False
        assert r.no_secrets_loaded is True
        assert r.secret_value_observed is False
        assert r.existing_positions_touched == []

    def test_approval(self):
        r = _run(allow_guarded_design_approval=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_secrets_loaded is True

    def test_guard(self):
        r = _run(allow_real_runner_execution=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.real_execution_allowed is False
        assert r.guarded_runner_implemented is False
        assert r.real_runner_implemented is False


# ===========================================================================
# AD39: gate count >= 97
# ===========================================================================

class TestAD39GateCount:
    def test_at_least_97(self):
        import src.demo_tiny_lifecycle_guarded_runner_design_review as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 97, (
            f"Expected >= 97 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# AD40: always-on gates surface in every checklist (>= 70 total surfaced)
# ===========================================================================

class TestAD40AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            # review scope
            GATE_GUARDED_DESIGN_REVIEW_ONLY,
            GATE_REAL_RUNNER_NOT_IMPLEMENTED,
            GATE_GUARDED_RUNNER_NOT_IMPLEMENTED,
            GATE_REAL_EXECUTION_NOT_ALLOWED,
            GATE_NO_ENDPOINT_INVOKED,
            GATE_NO_POSITION_MODIFIED_SCOPE,
            GATE_NO_SECRETS_LOADED,
            GATE_NO_G20_LIFT,
            # readiness
            GATE_W_ACCEPTABLE, GATE_X_ACCEPTABLE, GATE_Y_ACCEPTABLE,
            GATE_Z_ACCEPTABLE, GATE_AA_ACCEPTABLE, GATE_AB_ACCEPTABLE,
            GATE_AC_ACCEPTABLE, GATE_READINESS_NOT_EXECUTABLE,
            # guarded requirements
            GATE_ENTRY_ONLY_COMMAND_REQUIRED,
            GATE_STOP_ONLY_COMMAND_REQUIRED,
            GATE_CLEANUP_ONLY_COMMAND_REQUIRED,
            GATE_NO_FULL_LIFECYCLE_SINGLE_COMMAND,
            GATE_FRESH_READONLY_PRE_CHECK_REQUIRED,
            GATE_POST_READONLY_REQUIRED,
            GATE_ISOLATED_OUTPUT_DIR_REQUIRED,
            GATE_HUMAN_STOP_BETWEEN_STEPS_REQUIRED,
            GATE_NO_AUTO_NEXT_STEP, GATE_NO_AUTO_RETRY,
            GATE_NO_AUTO_CLEANUP, GATE_NO_AUTO_EMERGENCY_CLOSE,
            GATE_NO_BACKGROUND_LOOP,
            # manual auth
            GATE_ENTRY_TOKEN_PATTERN_PRESENT,
            GATE_STOP_TOKEN_PATTERN_PRESENT,
            GATE_CLEANUP_TOKEN_PATTERN_PRESENT,
            GATE_TOKEN_PER_STEP, GATE_TOKEN_INCLUDES_DATE_POLICY,
            GATE_TOKEN_INCLUDES_SYMBOL,
            GATE_SECOND_CONFIRMATION_REQUIRED,
            GATE_MAX_NOTIONAL_CAP_REQUIRED,
            GATE_EXPECTED_EXISTING_SYMBOLS_REQUIRED,
            GATE_TOKEN_FORMAT_NOT_AUTHORIZATION,
            GATE_TOKENS_NOT_VALIDATED,
            # environment isolation
            GATE_DEMO_ENDPOINT_ALLOWLIST, GATE_LIVE_ENDPOINT_DENYLIST,
            GATE_NO_FALLBACK_ENDPOINT, GATE_ONE_COMMAND_ONE_STEP,
            GATE_NO_DAEMON, GATE_NO_CRON, GATE_NO_SCHEDULER,
            GATE_NO_BACKGROUND_WORKER, GATE_NO_DISCORD_TRIGGER,
            GATE_NO_NOTION_TRIGGER, GATE_SECRETS_NOT_READ,
            # readonly contract
            GATE_PRE_CHECK_REQUIRED, GATE_POST_ENTRY_REQUIRED,
            GATE_POST_STOP_REQUIRED, GATE_POST_CLEANUP_REQUIRED,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_MISMATCH_MANUAL_REVIEW,
            GATE_EXISTING_FIVE_POSITIONS_UNCHANGED,
            # failure policy
            GATE_REQUEST_REJECTED_FAIL_CLOSED,
            GATE_PARTIAL_FILL_FAIL_CLOSED,
            GATE_READONLY_UNAVAIL_FAIL_CLOSED_FAILURE,
            GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED,
            GATE_EXISTING_POSITION_TOUCHED_MANUAL_REVIEW,
            GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED,
            GATE_SECRET_EMISSION_FAIL_CLOSED,
            GATE_NO_AUTOMATIC_RETRY, GATE_NO_AUTOMATIC_CLEANUP,
            GATE_NO_AUTOMATIC_EMERGENCY_CLOSE,
            GATE_NO_AUTOMATIC_NEXT_STEP,
            # execution guard
            GATE_REAL_RUNNER_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT, GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED, GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE, GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


# ===========================================================================
# AD41: no forbidden imports
# ===========================================================================

_FORBIDDEN_IMPORTS = (
    "urllib", "requests", "httpx", "socket", "http.client", "http",
    "pybit",
    "main",
    "src.risk",
    "src.bybit_executor",
    "BybitExecutor",
    "src.demo_new_entry_sender",
    "src.demo_close_only_sender",
    "src.demo_emergency_close_sender",
    "src.demo_protected_new_entry_orchestrator",
    "src.demo_trading_stop_contract_probe",
    "src.demo_trading_stop_noop_probe_plan",
    "src.demo_tiny_position_lifecycle_mock",
    "src.demo_tiny_position_real_permission_gate",
    "src.demo_tiny_entry_permission_gate",
    "src.demo_tiny_stop_attach_permission_gate",
    "src.demo_tiny_cleanup_permission_gate",
    "src.demo_tiny_lifecycle_real_execution_summary",
    "src.demo_tiny_lifecycle_runner_design",
    "src.demo_tiny_lifecycle_runner_dry_run",
)


def _collect_imports(path: Path) -> set[str]:
    tree = ast.parse(path.read_text(encoding="utf-8"))
    out: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                out.add(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                out.add(node.module)
    return out


class TestAD41NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# AD42: no sender reuse (no close-only / emergency-close / new-entry / runner)
# ===========================================================================

class TestAD42NoSenderReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"     not in code
            assert "demo_close_only_sender"  not in code

    def test_no_emergency_close(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoEmergencyCloseSender"    not in code
            assert "demo_emergency_close_sender" not in code

    def test_no_new_entry_sender(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoNewEntrySender"    not in code
            assert "demo_new_entry_sender" not in code

    def test_no_runner_dry_run_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRunnerDryRun" not in code

    def test_no_runner_design_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRunnerDesign" not in code

    def test_no_summary_module_reuse(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTinyLifecycleRealExecutionSummary" not in code


# ===========================================================================
# AD43: no network tokens in code
# ===========================================================================

class TestAD43NoNetworkTokens:
    def test_no_net_tokens(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            for tok in ("urllib", "urlopen", "httpx",
                        "requests.", "http.client", "socket.",
                        "session.post", "session.get"):
                assert tok not in code, (
                    f"Network token {tok!r} present in {path.name}"
                )


# ===========================================================================
# AD44: no env/signing
# ===========================================================================

class TestAD44NoEnvOrSigning:
    def test_module(self):
        code = _read_code_only(_MODULE_PATH)
        assert "os.environ" not in code
        assert "getenv"     not in code
        assert "dotenv"     not in code
        assert "hmac"       not in code.lower()
        assert "hashlib"    not in code.lower()
        assert "BYBIT_API"  not in code
        assert "API_KEY"    not in code
        assert "API_SECRET" not in code


# ===========================================================================
# AD45: forbidden flags absent (--execute-real-* / --send-order /
# --place-order / --real-run)
# ===========================================================================

class TestAD45NoForbiddenFlags:
    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-cleanup",
        "--execute-real-runner",
        "--send-order",
        "--place-order",
        "--real-run",
    ])
    def test_flag_absent_in_module(self, flag):
        code = _read_code_only(_MODULE_PATH)
        assert flag not in code

    @pytest.mark.parametrize("flag", [
        "--execute-real-lifecycle",
        "--execute-real-entry",
        "--execute-real-stop",
        "--execute-real-cleanup",
        "--execute-real-runner",
        "--send-order",
        "--place-order",
        "--real-run",
    ])
    def test_flag_absent_in_cli(self, flag):
        code = _read_code_only(_SCRIPT_PATH)
        assert flag not in code

    def test_flag_token_absent_in_module(self):
        code = _read_code_only(_MODULE_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_cleanup",
                      "execute_real_runner", "send_order", "place_order"):
            assert ident not in code

    def test_flag_token_absent_in_cli(self):
        code = _read_code_only(_SCRIPT_PATH)
        for ident in ("execute_real_lifecycle", "execute_real_entry",
                      "execute_real_stop", "execute_real_cleanup",
                      "execute_real_runner", "send_order", "place_order"):
            assert ident not in code


# ===========================================================================
# AD46: token patterns surfaced + 3 distinct
# ===========================================================================

class TestAD46TokenPatterns:
    def test_three_patterns(self):
        r = _run()
        assert r.entry_token_pattern       == ENTRY_TOKEN_PATTERN
        assert r.stop_attach_token_pattern == STOP_ATTACH_TOKEN_PATTERN
        assert r.cleanup_token_pattern     == CLEANUP_TOKEN_PATTERN
        assert len({
            r.entry_token_pattern,
            r.stop_attach_token_pattern,
            r.cleanup_token_pattern,
        }) == 3

    def test_token_structure(self):
        assert ENTRY_TOKEN_PATTERN.startswith("CONFIRM_DEMO_TINY_")
        assert STOP_ATTACH_TOKEN_PATTERN.startswith("CONFIRM_DEMO_TINY_")
        assert CLEANUP_TOKEN_PATTERN.startswith("CONFIRM_DEMO_TINY_")
        assert "YYYYMMDD" in ENTRY_TOKEN_PATTERN
        assert "YYYYMMDD" in STOP_ATTACH_TOKEN_PATTERN
        assert "YYYYMMDD" in CLEANUP_TOKEN_PATTERN
        assert "SYMBOL" in ENTRY_TOKEN_PATTERN
        assert "SYMBOL" in STOP_ATTACH_TOKEN_PATTERN
        assert "SYMBOL" in CLEANUP_TOKEN_PATTERN


# ===========================================================================
# AD47: stage_0 artifact preflight reports all 13 upstream artifacts present
# ===========================================================================

class TestAD47Stage0PreflightAllPresent:
    def test_all_present(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["readonly_smoke_present"]                   is True
        assert env["reconciliation_present"]                   is True
        assert env["protection_present"]                       is True
        assert env["contract_present"]                         is True
        assert env["noop_plan_present"]                        is True
        assert env["lifecycle_mock_present"]                   is True
        assert env["real_permission_gate_present"]             is True
        assert env["tiny_entry_permission_gate_present"]       is True
        assert env["tiny_stop_attach_permission_gate_present"] is True
        assert env["tiny_cleanup_permission_gate_present"]     is True
        assert env["lifecycle_summary_present"]                is True
        assert env["runner_design_present"]                    is True
        assert env["runner_dry_run_present"]                   is True
        assert env["current_task_real_execution_allowed"]      is False


# ===========================================================================
# AD48-AD50: CLI / report helpers + tests
# ===========================================================================

class _ReportSetupMixin:
    def _setup(self, base: Path):
        ro_d   = base / "readonly";    ro_d.mkdir()
        rec_d  = base / "recon";       rec_d.mkdir()
        prot_d = base / "protection";  prot_d.mkdir()
        con_d  = base / "contract";    con_d.mkdir()
        noop_d = base / "noop";        noop_d.mkdir()
        lc_d   = base / "lifecycle";   lc_d.mkdir()
        rp_d   = base / "real_perm";   rp_d.mkdir()
        ep_d   = base / "entry_perm";  ep_d.mkdir()
        sp_d   = base / "stop_perm";   sp_d.mkdir()
        cp_d   = base / "cleanup_perm"; cp_d.mkdir()
        sum_d  = base / "summary";     sum_d.mkdir()
        des_d  = base / "design";      des_d.mkdir()
        dry_d  = base / "dry_run";     dry_d.mkdir()
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        (rp_d   / "latest_tiny_position_real_permission_gate.json").write_text(json.dumps(_valid_real_permission_gate()), encoding="utf-8")
        (ep_d   / "latest_tiny_entry_permission_gate.json").write_text(json.dumps(_valid_tiny_entry_permission_gate()), encoding="utf-8")
        (sp_d   / "latest_tiny_stop_attach_permission_gate.json").write_text(json.dumps(_valid_tiny_stop_attach_permission_gate()), encoding="utf-8")
        (cp_d   / "latest_tiny_cleanup_permission_gate.json").write_text(json.dumps(_valid_tiny_cleanup_permission_gate()), encoding="utf-8")
        (sum_d  / "latest_tiny_lifecycle_real_execution_summary.json").write_text(json.dumps(_valid_lifecycle_summary()), encoding="utf-8")
        (des_d  / "latest_tiny_lifecycle_runner_design.json").write_text(json.dumps(_valid_runner_design()), encoding="utf-8")
        (dry_d  / "latest_tiny_lifecycle_runner_dry_run.json").write_text(json.dumps(_valid_runner_dry_run()), encoding="utf-8")
        return (ro_d, rec_d, prot_d, con_d, noop_d, lc_d,
                rp_d, ep_d, sp_d, cp_d, sum_d, des_d, dry_d, out_d)


class TestAD48ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_lifecycle_guarded_runner_design_review import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d,
             sum_d, des_d, dry_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_guarded_design_approval=False,
                allow_real_runner_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_lifecycle_guarded_runner_design_review.json" in files
            assert "latest_tiny_lifecycle_guarded_runner_design_review.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_guarded_runner_design_review.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_DESIGN_REVIEW_READY
            assert data["real_execution_allowed"] is False
            assert data["real_runner_implemented"] is False
            assert data["guarded_runner_implemented"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True
            assert data["readiness_conclusion"] == READINESS_CONCLUSION_NOT_EXECUTABLE
            assert data["future_guarded_commands"] == list(FUTURE_GUARDED_COMMANDS)
            assert data["required_confirmation_flags"] == list(REQUIRED_CONFIRMATION_FLAGS)


class TestAD49NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_lifecycle_guarded_runner_design_review import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d,
             sum_d, des_d, dry_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_guarded_design_approval=False,
                allow_real_runner_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_lifecycle_guarded_runner_design_review.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_guarded_runner_design_review.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False
            assert data["no_secrets_loaded"] is True


class TestAD50CLIExitCodes(_ReportSetupMixin):
    def test_subprocess_exits_0(self):
        from scripts.preview_demo_tiny_lifecycle_guarded_runner_design_review import run_execute
        with tempfile.TemporaryDirectory() as td:
            (ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d,
             sum_d, des_d, dry_d, out_d) = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_guarded_design_approval=False,
                allow_real_runner_execution=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                lifecycle_summary_dir=sum_d,
                runner_design_dir=des_d,
                runner_dry_run_dir=dry_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_subprocess_missing_exits_1(self):
        from scripts.preview_demo_tiny_lifecycle_guarded_runner_design_review import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for sub in ("readonly", "recon", "protection", "contract", "noop",
                        "lifecycle", "real_perm", "entry_perm", "stop_perm",
                        "cleanup_perm", "summary", "design", "dry_run"):
                (base / sub).mkdir()
            rc = run_execute(
                symbol="SOLUSDT",
                allow_guarded_design_approval=False,
                allow_real_runner_execution=False,
                write_report=False,
                readonly_dir=base / "readonly",
                reconciliation_dir=base / "recon",
                protection_dir=base / "protection",
                contract_dir=base / "contract",
                noop_plan_dir=base / "noop",
                lifecycle_dir=base / "lifecycle",
                real_permission_dir=base / "real_perm",
                tiny_entry_dir=base / "entry_perm",
                tiny_stop_attach_dir=base / "stop_perm",
                tiny_cleanup_dir=base / "cleanup_perm",
                lifecycle_summary_dir=base / "summary",
                runner_design_dir=base / "design",
                runner_dry_run_dir=base / "dry_run",
                output_dir=base / "out", _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# AD51: next_required_task points at TASK-014AE
# ===========================================================================

class TestAD51NextTaskIs014AE:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == "TASK-014AE_guarded_entry_only_dry_run_adapter"

    def test_next_required_task_under_approval(self):
        r = _run(allow_guarded_design_approval=True)
        assert r.next_required_task == "TASK-014AE_guarded_entry_only_dry_run_adapter"

    def test_next_required_task_under_guard(self):
        r = _run(allow_real_runner_execution=True)
        assert r.next_required_task == "TASK-014AE_guarded_entry_only_dry_run_adapter"


# ===========================================================================
# AD52: upstream lifecycle summary status echoed
# ===========================================================================

class TestAD52UpstreamSummaryStatusEchoed:
    def test_echoed(self):
        r = _run()
        assert r.upstream_lifecycle_summary_status == "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY"


# ===========================================================================
# AD53: upstream runner design status echoed
# ===========================================================================

class TestAD53UpstreamRunnerDesignStatusEchoed:
    def test_echoed(self):
        r = _run()
        assert r.upstream_runner_design_status == "TINY_LIFECYCLE_RUNNER_DESIGN_READY"


# ===========================================================================
# AD54: upstream runner dry-run status echoed
# ===========================================================================

class TestAD54UpstreamRunnerDryRunStatusEchoed:
    def test_echoed(self):
        r = _run()
        assert r.upstream_runner_dry_run_status == "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY"


# ===========================================================================
# AD55: status promotion vs. fail-closed precedence
# ===========================================================================

class TestAD55StatusPrecedence:
    def test_hard_fail_beats_approval(self):
        r = _run(readonly=None, allow_guarded_design_approval=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_hard_fail_beats_execution_guard(self):
        r = _run(runner_dry_run=None, allow_real_runner_execution=True)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED

    def test_guard_beats_approval(self):
        # If both flags set, real-runner-execution-guard takes precedence
        # over approval (both surface execution-disabled forms; guard wins).
        r = _run(allow_guarded_design_approval=True,
                 allow_real_runner_execution=True)
        assert r.status == STATUS_REAL_RUNNER_NOT_IMPL
        assert r.mode == MODE_REAL_RUNNER_EXECUTION_GUARD


# ===========================================================================
# AD56: review scope flags (sub-keys)
# ===========================================================================

class TestAD56ReviewScopeFlags:
    def test_no_endpoint_invoked(self):
        r = _run()
        assert r.review_scope["no_endpoint_invoked_in_this_task"] is True
        assert r.review_scope["order_endpoint_called"] is False
        assert r.review_scope["stop_endpoint_called"] is False


# ===========================================================================
# AD57: ACCEPTABLE_*_STATUSES whitelists each contain 3 statuses
# ===========================================================================

class TestAD57AcceptableWhitelists:
    def test_summary_three(self):
        assert len(ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES) == 3
        assert "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY" in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES

    def test_runner_design_three(self):
        assert len(ACCEPTABLE_RUNNER_DESIGN_STATUSES) == 3
        assert "TINY_LIFECYCLE_RUNNER_DESIGN_READY" in ACCEPTABLE_RUNNER_DESIGN_STATUSES

    def test_runner_dry_run_three(self):
        assert len(ACCEPTABLE_RUNNER_DRY_RUN_STATUSES) == 3
        assert "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY" in ACCEPTABLE_RUNNER_DRY_RUN_STATUSES


# ===========================================================================
# AD58: runner_dry_run_status_acceptable list sorted in stage_0
# ===========================================================================

class TestAD58RunnerDryRunStatusAcceptableSurfaced:
    def test_sorted_list_surfaced(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["runner_dry_run_status_acceptable"] == sorted(
            ACCEPTABLE_RUNNER_DRY_RUN_STATUSES
        )


# ===========================================================================
# AD59: existing 5 positions never touched even with all flags set
# ===========================================================================

class TestAD59ExistingPositionsNotTouched:
    def test_default(self):
        r = _run()
        assert r.existing_positions_touched == []
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)

    def test_with_approval(self):
        r = _run(allow_guarded_design_approval=True)
        assert r.existing_positions_touched == []

    def test_with_real_execution_guard(self):
        r = _run(allow_real_runner_execution=True)
        assert r.existing_positions_touched == []


# ===========================================================================
# AD60: blocked_gates deduplicated
# ===========================================================================

class TestAD60BlockedGatesDeduped:
    def test_no_duplicates(self):
        r = _run()
        assert len(r.blocked_gates) == len(set(r.blocked_gates))


# ===========================================================================
# AD61: 4 required confirmation flags (exact match for required strings)
# ===========================================================================

class TestAD61RequiredConfirmationFlags:
    def test_four_flags(self):
        assert len(REQUIRED_CONFIRMATION_FLAGS) == 4

    def test_specific_flags(self):
        assert "--i-understand-this-is-demo-real-execution" in REQUIRED_CONFIRMATION_FLAGS
        assert any("--max-notional-usdt" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-existing-position-count" in f for f in REQUIRED_CONFIRMATION_FLAGS)
        assert any("--expected-existing-symbols" in f for f in REQUIRED_CONFIRMATION_FLAGS)

    def test_max_notional_value(self):
        # The advisory cap is 10 USDT for the future guarded entry adapter.
        assert "--max-notional-usdt 10" in REQUIRED_CONFIRMATION_FLAGS

    def test_expected_position_count(self):
        assert "--expected-existing-position-count 5" in REQUIRED_CONFIRMATION_FLAGS


# ===========================================================================
# AD62: future_guarded_commands == 3 (entry/stop/cleanup only)
# ===========================================================================

class TestAD62FutureGuardedCommands:
    def test_three_commands(self):
        assert len(FUTURE_GUARDED_COMMANDS) == 3
        assert FUTURE_GUARDED_COMMANDS == (
            "guarded_entry_only",
            "guarded_stop_attach_only",
            "guarded_cleanup_only",
        )

    def test_surfaced(self):
        r = _run()
        assert r.future_guarded_commands == list(FUTURE_GUARDED_COMMANDS)


# ===========================================================================
# AD63: forbidden single-lifecycle command
# ===========================================================================

class TestAD63ForbiddenFullLifecycleCommand:
    def test_forbidden_token(self):
        assert FORBIDDEN_SINGLE_LIFECYCLE_COMMAND == "guarded_full_lifecycle"

    def test_forbidden_not_in_future_commands(self):
        assert FORBIDDEN_SINGLE_LIFECYCLE_COMMAND not in FUTURE_GUARDED_COMMANDS

    def test_surfaced_in_requirements(self):
        r = _run()
        req = r.guarded_runner_minimum_requirements
        assert req["forbidden_single_lifecycle_command"] == FORBIDDEN_SINGLE_LIFECYCLE_COMMAND
        assert req["no_full_lifecycle_single_command"] is True


# ===========================================================================
# AD64: demo endpoint allowlist + live denylist
# ===========================================================================

class TestAD64EndpointAllowlistDenylist:
    def test_constants(self):
        assert DEMO_ENDPOINT_ALLOWLIST == ("https://api-demo.bybit.com",)
        assert BASE_URL_LIVE_REF in tuple(LIVE_DENY for LIVE_DENY in
            ("https://api.bybit.com",))
        assert BASE_URL_DEMO_REF == "https://api-demo.bybit.com"
        assert BASE_URL_LIVE_REF == "https://api.bybit.com"

    def test_review_surfaced(self):
        r = _run()
        e = r.environment_isolation_review
        assert "https://api-demo.bybit.com" in e["demo_endpoint_allowlist"]
        assert "https://api.bybit.com" in e["live_endpoint_denylist"]


# ===========================================================================
# AD65: real_execution_allowed always False regardless of any flag combo
# ===========================================================================

class TestAD65RealExecutionAllowedAlwaysFalse:
    @pytest.mark.parametrize("approval,guard", [
        (False, False), (True, False), (False, True), (True, True),
    ])
    def test_always_false(self, approval, guard):
        r = _run(allow_guarded_design_approval=approval,
                 allow_real_runner_execution=guard)
        assert r.real_execution_allowed is False
        assert r.real_runner_implemented is False
        assert r.guarded_runner_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# AD66: hard-fail set has at least 20 gates
# ===========================================================================

class TestAD66HardFailGatesCount:
    def test_at_least_twenty(self):
        from src.demo_tiny_lifecycle_guarded_runner_design_review import (
            _HARD_FAIL_GATES,
        )
        assert len(_HARD_FAIL_GATES) >= 20


# ===========================================================================
# AD67: stage_order == ALL_STAGES (9 stages in order)
# ===========================================================================

class TestAD67StageOrder:
    def test_order(self):
        r = _run()
        assert r.stage_order == [
            STAGE_0_ARTIFACT_PREFLIGHT, STAGE_1_REVIEW_SCOPE,
            STAGE_2_READINESS_MATRIX,
            STAGE_3_GUARDED_RUNNER_MINIMUM_REQUIREMENTS,
            STAGE_4_MANUAL_AUTHORIZATION_MODEL,
            STAGE_5_ENVIRONMENT_ISOLATION_REVIEW,
            STAGE_6_PRE_POST_READONLY_CONTRACT,
            STAGE_7_FAILURE_AND_ABORT_REVIEW,
            STAGE_8_FINAL_GUARDED_DESIGN_VERDICT,
        ]
        assert len(r.stage_order) == 9


# ===========================================================================
# AD68: REQUIRED_CONFIRMATION_FLAGS contains demo-real-execution flag
# ===========================================================================

class TestAD68RequiredConfirmationFlagsValue:
    def test_demo_real_execution_required(self):
        # The first confirmation flag is the strong opt-in.
        assert REQUIRED_CONFIRMATION_FLAGS[0] == "--i-understand-this-is-demo-real-execution"


# ===========================================================================
# AD69: 13-artifact preflight contract - all 13 must be present
# ===========================================================================

class TestAD6913ArtifactPreflightContract:
    @pytest.mark.parametrize("kw", [
        {"readonly": None}, {"recon": None}, {"protection": None},
        {"contract": None}, {"noop_plan": None}, {"lifecycle": None},
        {"real_permission_gate": None},
        {"tiny_entry_permission_gate": None},
        {"tiny_stop_attach_permission_gate": None},
        {"tiny_cleanup_permission_gate": None},
        {"lifecycle_summary": None}, {"runner_design": None},
        {"runner_dry_run": None},
    ])
    def test_each_missing_fails_closed(self, kw):
        r = _run(**kw)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT


# ===========================================================================
# AD70: stage_8 final guarded design verdict mirrors result.status / mode
# ===========================================================================

class TestAD70Stage8MirrorsResult:
    def test_status_match(self):
        r = _run()
        v = r.stages[STAGE_8_FINAL_GUARDED_DESIGN_VERDICT]["final_guarded_design_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode

    def test_status_match_approval(self):
        r = _run(allow_guarded_design_approval=True)
        v = r.stages[STAGE_8_FINAL_GUARDED_DESIGN_VERDICT]["final_guarded_design_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode

    def test_status_match_guard(self):
        r = _run(allow_real_runner_execution=True)
        v = r.stages[STAGE_8_FINAL_GUARDED_DESIGN_VERDICT]["final_guarded_design_verdict"]
        assert v["status"] == r.status
        assert v["mode"] == r.mode


# ===========================================================================
# AD71: live URL never surfaces in any envelope's allowlist
# ===========================================================================

class TestAD71LiveURLNotInAllowlist:
    def test_demo_only(self):
        r = _run()
        e = r.environment_isolation_review
        assert BASE_URL_LIVE_REF not in e["demo_endpoint_allowlist"]
        assert BASE_URL_LIVE_REF in e["live_endpoint_denylist"]


# ===========================================================================
# AD72: pre_post_readonly_contract requires existing_five_positions_unchanged
# ===========================================================================

class TestAD72ExistingFivePositionsUnchanged:
    def test_pre_check(self):
        r = _run()
        c = r.pre_post_readonly_contract
        assert c["pre_check"]["existing_five_positions_unchanged"] is True
        assert c["post_cleanup"]["existing_five_positions_unchanged"] is True
        assert c["existing_five_positions_unchanged_requirement"] is True


# ===========================================================================
# AD73: runner_dry_run from REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED is accepted
# ===========================================================================

class TestAD73RunnerDryRunRealRunnerNotImplAccepted:
    def test_real_runner_not_impl_status_accepted(self):
        dry_run = _valid_runner_dry_run()
        dry_run["status"] = "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED"
        r = _run(runner_dry_run=dry_run)
        assert r.status == STATUS_DESIGN_REVIEW_READY
        assert r.upstream_runner_dry_run_status == "REAL_RUNNER_EXECUTION_NOT_IMPL" + "EMENTED"

    def test_execution_disabled_status_accepted(self):
        dry_run = _valid_runner_dry_run()
        dry_run["status"] = "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY_BUT_EXECUTION_DISABLED"
        r = _run(runner_dry_run=dry_run)
        assert r.status == STATUS_DESIGN_REVIEW_READY
