"""
tests/demo_trading/test_demo_tiny_lifecycle_real_execution_summary.py
TASK-014AA: Tiny Lifecycle Real Execution Permission Summary tests
(AA1 - AA41+).

Covers checklist / real_lifecycle_summary_dry_run /
real_lifecycle_execution_guard / fail_closed paths; all 7 stages;
>=55 gates; cross-artifact consistency checks (selected symbol /
entry side / cleanup side / tiny qty / stop price / entry reference
price / instrument category / existing position symbols / 3 payload
previews / lifecycle recommended path / contract endpoint path);
fixed 8-step real-lifecycle sequence; 3 distinct manual approval
tokens (entry / stop_attach / cleanup); failure-response matrix;
source-scan safety (no urlopen / no forbidden imports / no secrets);
report artifacts; and the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry and
is NOT lifted here.
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

from src.demo_tiny_lifecycle_real_execution_summary import (
    ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES,
    ACCEPTABLE_TINY_CLEANUP_PERMISSION_GATE_STATUSES,
    ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES,
    ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyLifecycleRealExecutionSummary,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_CLEANUP_SIDE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_ENTRY_ORDER_SIDE,
    EXPECTED_ENTRY_SIDE,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_NOOP_RECOMMENDED_PATH,
    EXPECTED_ORDER_TYPE,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_POSITION_IDX,
    EXPECTED_PROOF_STRENGTH,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CLEANUP_PAYLOAD_PREVIEW_INCONSISTENT,
    GATE_CLEANUP_REJECTED_FAIL_CLOSED,
    GATE_CLEANUP_SIDE_INCONSISTENT,
    GATE_CLEANUP_TOKEN_PATTERN_REQUIRED,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_PARTIAL_FILL_FAIL_CLOSED,
    GATE_ENTRY_PAYLOAD_PREVIEW_INCONSISTENT,
    GATE_ENTRY_REFERENCE_PRICE_INCONSISTENT,
    GATE_ENTRY_REJECTED_FAIL_CLOSED,
    GATE_ENTRY_SIDE_INCONSISTENT,
    GATE_ENTRY_TOKEN_PATTERN_REQUIRED,
    GATE_EXISTING_POSITION_SYMBOLS_INCONSISTENT,
    GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
    GATE_EXPECTED_ENDPOINT_PATH_INCONSISTENT,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_INSTRUMENT_CATEGORY_INCONSISTENT,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_LIFECYCLE_RECOMMENDED_PATH_INCONSISTENT,
    GATE_MANUAL_APPROVAL_REQUIRED_PER_STAGE,
    GATE_NO_AUTO_RETRY_AFTER_ANY_FAILURE,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SECRETS_EMITTED,
    GATE_NO_TOKEN_VALIDATED_IN_THIS_TASK,
    GATE_NOOP_PLAN_MISSING,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_BETWEEN_STEPS_FAIL_CLOSED,
    GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL,
    GATE_REAL_LIFECYCLE_RUNNER_NOT_YET_DESIGNED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_RECONCILIATION_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_INCONSISTENT,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_ATTACH_REJECTED_FAIL_CLOSED,
    GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED,
    GATE_STOP_PAYLOAD_PREVIEW_INCONSISTENT,
    GATE_STOP_PRICE_INCONSISTENT,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_TINY_CLEANUP_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TINY_POSITION_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED,
    GATE_TINY_QTY_INCONSISTENT,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TOKENS_MUST_BE_DISTINCT_PER_STEP,
    GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW,
    GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_LIFECYCLE_EXECUTION_GUARD,
    MODE_REAL_LIFECYCLE_SUMMARY_DRY_RUN,
    ORDER_CREATE_PATH_REF,
    REAL_LIFECYCLE_STEPS,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_LIFECYCLE_PLAN_CONSISTENCY,
    STAGE_2_EXISTING_POSITION_SAFETY_REVIEW,
    STAGE_3_EXECUTION_SEQUENCE_REVIEW,
    STAGE_4_MANUAL_APPROVAL_MATRIX,
    STAGE_5_FAILURE_RESPONSE_MATRIX,
    STAGE_6_FINAL_READINESS_VERDICT,
    STATUS_FAIL_CLOSED,
    STATUS_REAL_LIFECYCLE_NOT_IMPL,
    STATUS_SUMMARY_READY,
    STATUS_SUMMARY_READY_EXEC_DISABLED,
    STOP_ATTACH_TOKEN_PATTERN,
    TRADING_STOP_PATH_REF,
    TinyLifecycleRealExecutionSummaryResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_lifecycle_real_execution_summary.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_lifecycle_real_execution_summary.py"
_TEST_NOW    = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
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
        "timestamp_utc":          "2026-06-10T10:05:00Z",
        "mode":                   EXPECTED_POSITION_DETAILS_SOURCE,
        "position_details_source": EXPECTED_POSITION_DETAILS_SOURCE,
        "open_positions_count":   5,
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
        "timestamp_utc":                  "2026-06-10T11:00:00Z",
        "selected_symbol":                "SOLUSDT",
        "selected_side":                  "long",
        "selected_qty":                   12.2,
        "entry_reference_price":          64.87,
        "stop_price":                     61.63,
        "protected_entry_status":         "PREVIEW_ONLY",
        "preview_only":                   True,
    }


def _valid_contract() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T11:30:00Z",
        "mode":                   "preview",
        "selected_symbol":        "SOLUSDT",
        "path":                   TRADING_STOP_PATH_REF,
        "method":                 "POST",
        "real_probe_allowed":     False,
        "status":                 "TRADING_STOP_CONTRACT_PREVIEW_OK",
    }


def _valid_noop_plan() -> dict:
    return {
        "timestamp_utc":              "2026-06-10T11:45:00Z",
        "mode":                       "plan",
        "selected_symbol":            "SOLUSDT",
        "recommended_path":           EXPECTED_NOOP_RECOMMENDED_PATH,
        "status":                     "NOOP_PROBE_PLAN_READY",
    }


def _valid_lifecycle() -> dict:
    return {
        "timestamp_utc":              "2026-06-10T11:55:00Z",
        "mode":                       "mock_lifecycle",
        "selected_symbol":            "SOLUSDT",
        "side":                       "long",
        "tiny_qty":                   0.1,
        "tiny_notional":              6.487,
        "entry_reference_price":      64.87,
        "stop_price":                 61.63,
        "status":                     EXPECTED_LIFECYCLE_STATUS,
        "failed_phase":               "",
        "dangling_tiny_position":     False,
        "existing_positions_touched": [],
    }


def _valid_real_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:58:00Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":             "REAL_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":               False,
        "real_tiny_position_implemented":       False,
        "current_task_real_execution_allowed":  False,
        "real_tiny_position_requested":         False,
    }


def _valid_entry_payload_preview() -> dict:
    return {
        "preview_only":       True,
        "category":           EXPECTED_INSTRUMENT_CATEGORY,
        "symbol":             "SOLUSDT",
        "side":               EXPECTED_ENTRY_ORDER_SIDE,
        "orderType":          EXPECTED_ORDER_TYPE,
        "qty":                0.1,
        "positionIdx":        EXPECTED_POSITION_IDX,
        "orderLinkId":        "DRYRUN-TINY-ENTRY-SOLUSDT-20260610",
        "endpoint_path_ref":  ORDER_CREATE_PATH_REF,
        "endpoint_called":    False,
    }


def _valid_tiny_entry_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:59:00Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":             "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
        "rounded_tiny_qty":   0.1,
        "entry_payload_preview": _valid_entry_payload_preview(),
        "real_execution_allowed":               False,
        "real_tiny_entry_implemented":          False,
        "current_task_real_execution_allowed":  False,
        "real_tiny_entry_requested":            False,
    }


def _valid_stop_payload_preview() -> dict:
    return {
        "preview_only":       True,
        "category":           EXPECTED_INSTRUMENT_CATEGORY,
        "symbol":             "SOLUSDT",
        "stopLoss":           61.63,
        "tpslMode":           "Full",
        "slTriggerBy":        "MarkPrice",
        "positionIdx":        EXPECTED_POSITION_IDX,
        "endpoint_path_ref":  TRADING_STOP_PATH_REF,
        "endpoint_called":    False,
    }


def _valid_tiny_stop_attach_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:59:30Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":             "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
        "stop_price":         61.63,
        "stop_payload_preview": _valid_stop_payload_preview(),
        "real_execution_allowed":               False,
        "real_stop_attach_implemented":         False,
        "current_task_real_execution_allowed":  False,
        "real_stop_attach_requested":           False,
    }


def _valid_cleanup_payload_preview() -> dict:
    return {
        "preview_only":       True,
        "category":           EXPECTED_INSTRUMENT_CATEGORY,
        "symbol":             "SOLUSDT",
        "side":               EXPECTED_CLEANUP_SIDE,
        "orderType":          EXPECTED_ORDER_TYPE,
        "qty":                0.1,
        "reduceOnly":         True,
        "closeOnTrigger":     False,
        "positionIdx":        EXPECTED_POSITION_IDX,
        "orderLinkId":        "DRYRUN-TINY-CLEANUP-SOLUSDT-20260610",
        "endpoint_path_ref":  ORDER_CREATE_PATH_REF,
        "endpoint_called":    False,
    }


def _valid_tiny_cleanup_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:59:45Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "existing_position_symbols": list(EXISTING_POSITION_SYMBOLS),
        "status":             "TINY_CLEANUP_PERMISSION_CHECKLIST_READY",
        "expected_tiny_qty":  0.1,
        "cleanup_side":       EXPECTED_CLEANUP_SIDE,
        "cleanup_payload_preview": _valid_cleanup_payload_preview(),
        "real_execution_allowed":               False,
        "real_cleanup_implemented":             False,
        "current_task_real_execution_allowed":  False,
        "real_cleanup_requested":               False,
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


def _gate() -> DemoTinyLifecycleRealExecutionSummary:
    return DemoTinyLifecycleRealExecutionSummary()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    tiny_stop_attach_permission_gate=_UNSET,
    tiny_cleanup_permission_gate=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_real_lifecycle_summary=False,
    allow_real_lifecycle_execution=False,
    _now=_TEST_NOW,
) -> TinyLifecycleRealExecutionSummaryResult:
    return _gate().run_checklist(
        readonly_smoke=_valid_readonly()                            if readonly             is _UNSET else readonly,
        reconciliation=_valid_reconciliation()                      if recon                is _UNSET else recon,
        protection=_valid_protection()                              if protection           is _UNSET else protection,
        contract=_valid_contract()                                  if contract             is _UNSET else contract,
        noop_plan=_valid_noop_plan()                                if noop_plan            is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()                           if lifecycle            is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate()          if real_permission_gate is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate() if tiny_entry_permission_gate is _UNSET else tiny_entry_permission_gate,
        tiny_stop_attach_permission_gate=_valid_tiny_stop_attach_permission_gate() if tiny_stop_attach_permission_gate is _UNSET else tiny_stop_attach_permission_gate,
        tiny_cleanup_permission_gate=_valid_tiny_cleanup_permission_gate() if tiny_cleanup_permission_gate is _UNSET else tiny_cleanup_permission_gate,
        symbol=symbol,
        allow_real_lifecycle_summary=allow_real_lifecycle_summary,
        allow_real_lifecycle_execution=allow_real_lifecycle_execution,
        _now=_now,
    )


# ===========================================================================
# AA1: valid checklist => TINY_LIFECYCLE_PERMISSION_SUMMARY_READY
# ===========================================================================

class TestAA1ChecklistReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_SUMMARY_READY
        assert r.mode == MODE_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_lifecycle_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == (
            "TASK-014AB_tiny_lifecycle_real_execution_runner_design_or_manual_approval"
        )


# ===========================================================================
# AA2: --allow-real-lifecycle-summary => SUMMARY_READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestAA2RealLifecycleSummaryDryRun:
    def test_promotes_status(self):
        r = _run(allow_real_lifecycle_summary=True)
        assert r.status == STATUS_SUMMARY_READY_EXEC_DISABLED
        assert r.mode == MODE_REAL_LIFECYCLE_SUMMARY_DRY_RUN
        assert r.real_lifecycle_summary_dry_run_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_lifecycle_runner_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# AA3: --allow-real-lifecycle-execution => REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED
# ===========================================================================

class TestAA3RealLifecycleExecutionGuard:
    def test_guard_returns_not_impl(self):
        r = _run(allow_real_lifecycle_execution=True)
        assert r.status == STATUS_REAL_LIFECYCLE_NOT_IMPL
        assert r.mode == MODE_REAL_LIFECYCLE_EXECUTION_GUARD
        assert r.real_execution_allowed is False
        assert r.real_lifecycle_runner_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.real_lifecycle_execution_requested is True
        assert GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL in r.blocked_gates


# ===========================================================================
# AA4 - AA13: missing upstream artifacts => FAIL_CLOSED  (10 artifacts)
# ===========================================================================

class TestAA4MissingReadonly:
    def test_none(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestAA5MissingReconciliation:
    def test_none(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestAA6MissingProtection:
    def test_none(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestAA7MissingContract:
    def test_none(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestAA8MissingNoopPlan:
    def test_none(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestAA9MissingLifecycle:
    def test_none(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestAA10MissingRealPermissionGate:
    def test_none(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAA11MissingTinyEntryPermissionGate:
    def test_none(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAA12MissingTinyStopAttachPermissionGate:
    def test_none(self):
        r = _run(tiny_stop_attach_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING in r.blocked_gates


class TestAA13MissingTinyCleanupPermissionGate:
    def test_none(self):
        r = _run(tiny_cleanup_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING in r.blocked_gates


# ===========================================================================
# AA14: selected_symbol collides with an existing position => FAIL_CLOSED
# ===========================================================================

class TestAA14SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_collision_blocks(self, sym):
        # Adjust upstream gate symbols to match so we test the collision path
        # cleanly (otherwise selected_symbol_inconsistent also fires).
        rpg = _valid_real_permission_gate();   rpg["selected_symbol"] = sym
        ep  = _valid_tiny_entry_permission_gate();  ep["selected_symbol"] = sym
        sp  = _valid_tiny_stop_attach_permission_gate(); sp["selected_symbol"] = sym
        cp  = _valid_tiny_cleanup_permission_gate(); cp["selected_symbol"] = sym
        prot = _valid_protection(); prot["selected_symbol"] = sym
        con  = _valid_contract();   con["selected_symbol"] = sym
        noop = _valid_noop_plan();  noop["selected_symbol"] = sym
        lc   = _valid_lifecycle();  lc["selected_symbol"] = sym
        r = _run(
            symbol=sym, protection=prot, contract=con, noop_plan=noop,
            lifecycle=lc, real_permission_gate=rpg,
            tiny_entry_permission_gate=ep, tiny_stop_attach_permission_gate=sp,
            tiny_cleanup_permission_gate=cp,
        )
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# AA15 - AA19: proof envelope mismatches => FAIL_CLOSED
# ===========================================================================

class TestAA15EndpointFamilyMismatch:
    def test_mainnet(self):
        ro = _valid_readonly(); ro["endpoint_family"] = "bybit_mainnet"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestAA16AccountModeMismatch:
    def test_live(self):
        ro = _valid_readonly(); ro["account_mode"] = "live"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestAA17ProofStrengthMismatch:
    def test_weak(self):
        ro = _valid_readonly(); ro["proof_strength"] = "WEAK"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestAA18PositionDetailsSourceMismatch:
    def test_synthetic(self):
        rec = _valid_reconciliation()
        rec["mode"] = "synthetic"
        rec["position_details_source"] = "synthetic"
        r = _run(recon=rec)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


class TestAA19LifecycleNotSuccess:
    def test_fail_closed(self):
        lc = _valid_lifecycle()
        lc["status"] = "MOCK_TINY_LIFECYCLE_FAIL_CLOSED"
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_NOT_SUCCESS in r.blocked_gates


# ===========================================================================
# AA20 - AA23: upstream gate status unacceptable => FAIL_CLOSED  (4 gates)
# ===========================================================================

class TestAA20RealPermissionUnacceptable:
    def test_fail_closed(self):
        rpg = _valid_real_permission_gate()
        rpg["status"] = "FAIL_CLOSED"
        r = _run(real_permission_gate=rpg)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        rpg = _valid_real_permission_gate(); rpg["status"] = status
        r = _run(real_permission_gate=rpg)
        assert r.status == STATUS_SUMMARY_READY


class TestAA21TinyEntryPermissionUnacceptable:
    def test_fail_closed(self):
        ep = _valid_tiny_entry_permission_gate()
        ep["status"] = "FAIL_CLOSED"
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        ep = _valid_tiny_entry_permission_gate(); ep["status"] = status
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_SUMMARY_READY


class TestAA22TinyStopAttachPermissionUnacceptable:
    def test_fail_closed(self):
        sp = _valid_tiny_stop_attach_permission_gate()
        sp["status"] = "FAIL_CLOSED"
        r = _run(tiny_stop_attach_permission_gate=sp)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        sp = _valid_tiny_stop_attach_permission_gate(); sp["status"] = status
        r = _run(tiny_stop_attach_permission_gate=sp)
        assert r.status == STATUS_SUMMARY_READY


class TestAA23TinyCleanupPermissionUnacceptable:
    def test_fail_closed(self):
        cp = _valid_tiny_cleanup_permission_gate()
        cp["status"] = "FAIL_CLOSED"
        r = _run(tiny_cleanup_permission_gate=cp)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_CLEANUP_PERMISSION_GATE_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_TINY_CLEANUP_PERMISSION_GATE_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        cp = _valid_tiny_cleanup_permission_gate(); cp["status"] = status
        r = _run(tiny_cleanup_permission_gate=cp)
        assert r.status == STATUS_SUMMARY_READY


# ===========================================================================
# AA24 - AA31: cross-artifact consistency checks
# ===========================================================================

class TestAA24SelectedSymbolInconsistent:
    def test_protection_disagrees(self):
        prot = _valid_protection(); prot["selected_symbol"] = "BTCUSDT"
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_INCONSISTENT in r.blocked_gates


class TestAA25EntrySideInconsistent:
    def test_protection_short(self):
        prot = _valid_protection(); prot["selected_side"] = "short"
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_SIDE_INCONSISTENT in r.blocked_gates


class TestAA26CleanupSideInconsistent:
    def test_cleanup_side_buy(self):
        cp = _valid_tiny_cleanup_permission_gate()
        cp["cleanup_side"] = "Buy"
        payload = _valid_cleanup_payload_preview(); payload["side"] = "Buy"
        cp["cleanup_payload_preview"] = payload
        r = _run(tiny_cleanup_permission_gate=cp)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CLEANUP_SIDE_INCONSISTENT in r.blocked_gates


class TestAA27TinyQtyInconsistent:
    def test_entry_payload_qty_disagrees(self):
        ep = _valid_tiny_entry_permission_gate()
        payload = _valid_entry_payload_preview(); payload["qty"] = 0.5
        ep["entry_payload_preview"] = payload
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_QTY_INCONSISTENT in r.blocked_gates


class TestAA28StopPriceInconsistent:
    def test_protection_disagrees(self):
        prot = _valid_protection(); prot["stop_price"] = 50.00
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PRICE_INCONSISTENT in r.blocked_gates


class TestAA29EntryReferencePriceInconsistent:
    def test_lifecycle_disagrees(self):
        lc = _valid_lifecycle(); lc["entry_reference_price"] = 100.0
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REFERENCE_PRICE_INCONSISTENT in r.blocked_gates


class TestAA30InstrumentCategoryInconsistent:
    def test_entry_payload_category_wrong(self):
        ep = _valid_tiny_entry_permission_gate()
        payload = _valid_entry_payload_preview(); payload["category"] = "spot"
        ep["entry_payload_preview"] = payload
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_INSTRUMENT_CATEGORY_INCONSISTENT in r.blocked_gates


class TestAA31ExistingPositionSymbolsInconsistent:
    def test_real_perm_has_different_list(self):
        rpg = _valid_real_permission_gate()
        rpg["existing_position_symbols"] = ["FOOUSDT", "BARUSDT"]
        r = _run(real_permission_gate=rpg)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_EXISTING_POSITION_SYMBOLS_INCONSISTENT in r.blocked_gates


# ===========================================================================
# AA32 - AA34: payload preview consistency
# ===========================================================================

class TestAA32EntryPayloadPreviewInconsistent:
    def test_not_preview_only(self):
        ep = _valid_tiny_entry_permission_gate()
        payload = _valid_entry_payload_preview(); payload["preview_only"] = False
        ep["entry_payload_preview"] = payload
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_PAYLOAD_PREVIEW_INCONSISTENT in r.blocked_gates


class TestAA33StopPayloadPreviewInconsistent:
    def test_not_preview_only(self):
        sp = _valid_tiny_stop_attach_permission_gate()
        payload = _valid_stop_payload_preview(); payload["preview_only"] = False
        sp["stop_payload_preview"] = payload
        r = _run(tiny_stop_attach_permission_gate=sp)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PAYLOAD_PREVIEW_INCONSISTENT in r.blocked_gates


class TestAA34CleanupPayloadPreviewInconsistent:
    def test_reduce_only_false(self):
        cp = _valid_tiny_cleanup_permission_gate()
        payload = _valid_cleanup_payload_preview(); payload["reduceOnly"] = False
        cp["cleanup_payload_preview"] = payload
        r = _run(tiny_cleanup_permission_gate=cp)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CLEANUP_PAYLOAD_PREVIEW_INCONSISTENT in r.blocked_gates


# ===========================================================================
# AA35: lifecycle recommended path inconsistent
# ===========================================================================

class TestAA35LifecycleRecommendedPathInconsistent:
    def test_wrong_path(self):
        noop = _valid_noop_plan(); noop["recommended_path"] = "abort_demo_trading"
        r = _run(noop_plan=noop)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_RECOMMENDED_PATH_INCONSISTENT in r.blocked_gates


# ===========================================================================
# AA36: contract endpoint path inconsistent
# ===========================================================================

class TestAA36ContractEndpointPathInconsistent:
    def test_wrong_path(self):
        con = _valid_contract(); con["path"] = "/v5/order/create"
        r = _run(contract=con)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_EXPECTED_ENDPOINT_PATH_INCONSISTENT in r.blocked_gates


# ===========================================================================
# AA37: stage_3 fixed 8-step execution sequence review
# ===========================================================================

class TestAA37ExecutionSequenceReview:
    def test_8_steps(self):
        r = _run()
        assert r.real_lifecycle_steps == list(REAL_LIFECYCLE_STEPS)
        assert len(r.real_lifecycle_steps) == 8
        env = r.stages[STAGE_3_EXECUTION_SEQUENCE_REVIEW]
        plan = env["execution_sequence_plan"]
        assert plan["step_count"] == 8
        assert plan["steps"] == list(REAL_LIFECYCLE_STEPS)
        assert plan["preview_only"] is True
        assert plan["order_endpoint_called"] is False
        assert plan["stop_endpoint_called"] is False
        assert plan["real_lifecycle_runner_implemented"] is False
        assert plan["real_execution_allowed"] is False
        assert plan["no_endpoint_invoked_in_this_task"] is True
        # Fixed sequence: entry -> stop -> cleanup with readonly between.
        assert plan["steps"][1] == "real_tiny_entry"
        assert plan["steps"][3] == "real_stop_attach"
        assert plan["steps"][5] == "real_cleanup"

    def test_step_payload_refs_present(self):
        r = _run()
        plan = r.stages[STAGE_3_EXECUTION_SEQUENCE_REVIEW]["execution_sequence_plan"]
        refs = plan["step_payload_refs"]
        assert refs["real_tiny_entry"]["preview_only"] is True
        assert refs["real_stop_attach"]["preview_only"] is True
        assert refs["real_cleanup"]["preview_only"] is True

    def test_step_endpoint_refs_documented(self):
        r = _run()
        plan = r.stages[STAGE_3_EXECUTION_SEQUENCE_REVIEW]["execution_sequence_plan"]
        eps = plan["step_endpoint_refs"]
        assert eps["real_tiny_entry"]  == ORDER_CREATE_PATH_REF
        assert eps["real_stop_attach"] == TRADING_STOP_PATH_REF
        assert eps["real_cleanup"]     == ORDER_CREATE_PATH_REF


# ===========================================================================
# AA38: stage_4 manual approval matrix (3 distinct tokens)
# ===========================================================================

class TestAA38ManualApprovalMatrix:
    def test_three_distinct_tokens(self):
        r = _run()
        env = r.stages[STAGE_4_MANUAL_APPROVAL_MATRIX]
        m = env["manual_approval_matrix"]
        assert m["entry_token_pattern"]      == ENTRY_TOKEN_PATTERN
        assert m["stop_attach_token_pattern"] == STOP_ATTACH_TOKEN_PATTERN
        assert m["cleanup_token_pattern"]    == CLEANUP_TOKEN_PATTERN
        # Must be 3 distinct patterns.
        assert len({
            ENTRY_TOKEN_PATTERN,
            STOP_ATTACH_TOKEN_PATTERN,
            CLEANUP_TOKEN_PATTERN,
        }) == 3
        assert m["tokens_must_be_distinct_per_step"] is True
        assert m["tokens_validated_in_this_task"] is False
        assert m["real_lifecycle_runner_not_yet_designed"] is True

    def test_always_on_manual_approval_gates(self):
        r = _run()
        for g in (
            GATE_ENTRY_TOKEN_PATTERN_REQUIRED,
            GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED,
            GATE_CLEANUP_TOKEN_PATTERN_REQUIRED,
            GATE_TOKENS_MUST_BE_DISTINCT_PER_STEP,
            GATE_NO_TOKEN_VALIDATED_IN_THIS_TASK,
            GATE_MANUAL_APPROVAL_REQUIRED_PER_STAGE,
            GATE_REAL_LIFECYCLE_RUNNER_NOT_YET_DESIGNED,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# AA39: stage_5 failure response matrix
# ===========================================================================

class TestAA39FailureResponseMatrix:
    def test_matrix_fields(self):
        r = _run()
        env = r.stages[STAGE_5_FAILURE_RESPONSE_MATRIX]
        m = env["failure_response_matrix"]
        assert m["entry_rejected"]                       == "fail_closed"
        assert m["stop_attach_rejected"]                 == "fail_closed"
        assert m["cleanup_rejected"]                     == "fail_closed"
        assert m["entry_partial_fill"]                   == "fail_closed"
        assert m["cleanup_partial_fill"]                 == "fail_closed"
        assert m["readonly_unavailable_between_steps"]   == "fail_closed"
        assert m["tiny_position_still_open_after_cleanup"] == "fail_closed"
        assert m["existing_stop_mismatch"]               == "manual_review"
        assert m["unexpected_position_appears"]          == "manual_review"
        assert m["no_automatic_retry_after_any_failure"] is True
        assert m["no_real_emergency_close_in_this_task"] is True
        assert set(m["expected_existing_position_symbols"]) == set(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# AA40: stage_6 final readiness verdict (all guard flags False)
# ===========================================================================

class TestAA40FinalReadinessVerdict:
    def test_default_flags(self):
        r = _run()
        env = r.stages[STAGE_6_FINAL_READINESS_VERDICT]
        assert env["real_execution_allowed"]                  is False
        assert env["real_lifecycle_runner_implemented"]       is False
        assert env["current_task_real_execution_allowed"]     is False
        assert env["g20_policy_still_in_place"]               is True
        assert env["g20_lifted"]                              is False
        assert env["no_real_order_endpoint"]                  is True
        assert env["no_real_stop_endpoint"]                   is True
        assert env["no_position_modified"]                    is True
        assert env["no_live_endpoint"]                        is True
        assert env["no_secrets_emitted"]                      is True
        assert env["status"] == STATUS_SUMMARY_READY

    def test_guard_does_not_flip_real_execution(self):
        r = _run(allow_real_lifecycle_execution=True)
        env = r.stages[STAGE_6_FINAL_READINESS_VERDICT]
        assert env["real_execution_allowed"] is False
        assert env["real_lifecycle_execution_requested"] is True
        assert env["status"] == STATUS_REAL_LIFECYCLE_NOT_IMPL


# ===========================================================================
# AA41: 7 stages built
# ===========================================================================

class TestAA41SevenStages:
    def test_seven(self):
        r = _run()
        assert set(r.stages.keys()) == set(ALL_STAGES)
        assert r.stage_order == list(ALL_STAGES)
        assert len(ALL_STAGES) == 7


# ===========================================================================
# AA42: missing symbol
# ===========================================================================

class TestAA42MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# AA43: G20 not lifted
# ===========================================================================

class TestAA43G20NotLifted:
    def test_g20_unchanged_constant(self):
        from src.demo_new_entry_protection import G20_BLOCKED_GATE_NAME
        assert G20_BLOCKED_GATE_NAME == "protected_entry_policy_missing"

    def test_module_does_not_reference_g20(self):
        code = _read_code_only(_MODULE_PATH)
        assert "protected_entry_policy_missing" not in code
        assert "G20_BLOCKED_GATE_NAME"          not in code

    def test_result_records_g20_in_place(self):
        r = _run()
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
        assert GATE_G20_NOT_LIFTED in r.blocked_gates


# ===========================================================================
# AA44: socket-disabled import smoke
# ===========================================================================

class TestAA44SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_lifecycle_real_execution_summary as m; "
             "print('OK', m.STATUS_SUMMARY_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# AA45: dataclass roundtrip with deep-copy
# ===========================================================================

class TestAA45DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_real_lifecycle_summary=True)
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
            ("secret_value_observed",               False),
            ("g20_policy_still_in_place",           True),
            ("g20_lifted",                          False),
            ("current_task_real_execution_allowed", False),
            ("real_lifecycle_runner_implemented",   False),
            ("real_execution_allowed",              False),
            ("real_lifecycle_summary_dry_run_allowed", True),
            ("existing_position_stop_snapshot_match", True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_SUMMARY_READY_EXEC_DISABLED
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_3_EXECUTION_SEQUENCE_REVIEW]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_3_EXECUTION_SEQUENCE_REVIEW]
        d["cleanup_payload_preview"]["mutated"] = True
        assert "mutated" not in r.cleanup_payload_preview
        d["entry_payload_preview"]["mutated"] = True
        assert "mutated" not in r.entry_payload_preview
        d["stop_payload_preview"]["mutated"] = True
        assert "mutated" not in r.stop_payload_preview


# ===========================================================================
# AA46: path refs
# ===========================================================================

class TestAA46PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


# ===========================================================================
# AA47: safety invariants
# ===========================================================================

class TestAA47SafetyInvariants:
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
        assert r.secret_value_observed is False
        assert r.existing_positions_touched == []

    def test_dry_run(self):
        r = _run(allow_real_lifecycle_summary=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True

    def test_guard(self):
        r = _run(allow_real_lifecycle_execution=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.real_execution_allowed is False


# ===========================================================================
# AA48: gate count >= 55
# ===========================================================================

class TestAA48GateCount:
    def test_at_least_55(self):
        import src.demo_tiny_lifecycle_real_execution_summary as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 55, (
            f"Expected >= 55 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# AA49: always-on gates surface in every checklist
# ===========================================================================

class TestAA49AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            GATE_ENTRY_TOKEN_PATTERN_REQUIRED,
            GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED,
            GATE_CLEANUP_TOKEN_PATTERN_REQUIRED,
            GATE_TOKENS_MUST_BE_DISTINCT_PER_STEP,
            GATE_NO_TOKEN_VALIDATED_IN_THIS_TASK,
            GATE_MANUAL_APPROVAL_REQUIRED_PER_STAGE,
            GATE_REAL_LIFECYCLE_RUNNER_NOT_YET_DESIGNED,
            GATE_ENTRY_REJECTED_FAIL_CLOSED,
            GATE_STOP_ATTACH_REJECTED_FAIL_CLOSED,
            GATE_CLEANUP_REJECTED_FAIL_CLOSED,
            GATE_ENTRY_PARTIAL_FILL_FAIL_CLOSED,
            GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED,
            GATE_READONLY_UNAVAILABLE_BETWEEN_STEPS_FAIL_CLOSED,
            GATE_TINY_POSITION_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW,
            GATE_NO_AUTO_RETRY_AFTER_ANY_FAILURE,
            GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
            GATE_REAL_LIFECYCLE_EXECUTION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


# ===========================================================================
# AA50: no forbidden imports
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


class TestAA50NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# AA51: no sender reuse
# ===========================================================================

class TestAA51NoSenderReuse:
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

    def test_no_trading_stop_real_adapter(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTradingStopContractProbe"     not in code
            assert "demo_trading_stop_contract_probe" not in code


# ===========================================================================
# AA52: no network/env/signing tokens
# ===========================================================================

class TestAA52NoNetworkTokens:
    def test_no_net_tokens(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            for tok in ("urllib", "urlopen", "httpx",
                        "requests.", "http.client", "socket.",
                        "session.post", "session.get"):
                assert tok not in code, (
                    f"Network token {tok!r} present in {path.name}"
                )

    def test_no_env_or_signing(self):
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
# AA53: no execute flag exists
# ===========================================================================

class TestAA53NoExecuteFlag:
    def test_no_execute_flag_in_module(self):
        code = _read_code_only(_MODULE_PATH)
        assert "execute_real_lifecycle" not in code
        text = _MODULE_PATH.read_text(encoding="utf-8")
        assert "--execute-real-lifecycle" not in text

    def test_no_execute_flag_in_cli(self):
        text = _SCRIPT_PATH.read_text(encoding="utf-8")
        assert "--execute-real-lifecycle" not in text
        assert "--execute-tiny-lifecycle" not in text
        assert "--execute-lifecycle"      not in text


# ===========================================================================
# AA54: token patterns surfaced + 3 distinct
# ===========================================================================

class TestAA54TokenPatterns:
    def test_three_patterns(self):
        r = _run()
        assert r.entry_token_pattern       == ENTRY_TOKEN_PATTERN
        assert r.stop_attach_token_pattern == STOP_ATTACH_TOKEN_PATTERN
        assert r.cleanup_token_pattern     == CLEANUP_TOKEN_PATTERN
        # All three distinct.
        assert len({r.entry_token_pattern, r.stop_attach_token_pattern, r.cleanup_token_pattern}) == 3


# ===========================================================================
# AA55: stage_2 existing positions safety review
# ===========================================================================

class TestAA55Stage2ExistingPositionsSafetyReview:
    def test_snapshot(self):
        r = _run(symbol="SOLUSDT")
        env = r.stages[STAGE_2_EXISTING_POSITION_SAFETY_REVIEW]
        assert env["existing_position_count"] == 5
        assert env["selected_symbol_disjoint"] is True
        assert env["existing_positions_touched"] == []
        assert env["snapshot_fields_ok"] is True
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# AA56: stage_0 artifact preflight reports all 10 upstream artifacts present
# ===========================================================================

class TestAA56Stage0PreflightAllPresent:
    def test_all_present(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["readonly_smoke_present"]                       is True
        assert env["reconciliation_present"]                       is True
        assert env["protection_present"]                           is True
        assert env["contract_present"]                             is True
        assert env["noop_plan_present"]                            is True
        assert env["lifecycle_mock_present"]                       is True
        assert env["real_permission_gate_present"]                 is True
        assert env["tiny_entry_permission_gate_present"]           is True
        assert env["tiny_stop_attach_permission_gate_present"]     is True
        assert env["tiny_cleanup_permission_gate_present"]         is True
        assert env["current_task_real_execution_allowed"]          is False


# ===========================================================================
# AA57: stage_1 lifecycle plan consistency populates canonical values
# ===========================================================================

class TestAA57Stage1Consistency:
    def test_canonical_values(self):
        r = _run()
        env = r.stages[STAGE_1_LIFECYCLE_PLAN_CONSISTENCY]
        assert env["selected_symbol_consistent"] is True
        assert env["entry_side_consistent"] is True
        assert env["cleanup_side_consistent"] is True
        assert env["tiny_qty_consistent"] is True
        assert env["stop_price_consistent"] is True
        assert env["entry_reference_price_consistent"] is True
        assert env["instrument_category_consistent"] is True
        assert env["existing_position_symbols_consistent"] is True
        assert env["entry_payload_preview_consistent"] is True
        assert env["stop_payload_preview_consistent"] is True
        assert env["cleanup_payload_preview_consistent"] is True
        assert env["noop_recommended_path_observed"] == EXPECTED_NOOP_RECOMMENDED_PATH
        assert env["contract_path_observed"] == TRADING_STOP_PATH_REF
        assert env["expected_tiny_qty"] == pytest.approx(0.1)
        assert env["expected_stop_price"] == pytest.approx(61.63)
        assert env["expected_entry_reference_price"] == pytest.approx(64.87)


# ===========================================================================
# AA58: report artifacts written (checklist)
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
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d, out_d


class TestAA58ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_lifecycle_real_execution_summary import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_lifecycle_summary=False,
                allow_real_lifecycle_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_lifecycle_real_execution_summary.json" in files
            assert "latest_tiny_lifecycle_real_execution_summary.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_real_execution_summary.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_SUMMARY_READY
            assert data["real_execution_allowed"] is False
            assert data["real_lifecycle_runner_implemented"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True
            assert data["expected_tiny_qty"] == pytest.approx(0.1)
            assert data["expected_stop_price"] == pytest.approx(61.63)
            assert data["real_lifecycle_steps"] == list(REAL_LIFECYCLE_STEPS)


# ===========================================================================
# AA59: no secrets in report
# ===========================================================================

class TestAA59NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_lifecycle_real_execution_summary import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_lifecycle_summary=False,
                allow_real_lifecycle_execution=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_lifecycle_real_execution_summary.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_lifecycle_real_execution_summary.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False


# ===========================================================================
# AA60: CLI subprocess valid run exits 0 + missing artifact exits 1
# ===========================================================================

class TestAA60CLISubprocess(_ReportSetupMixin):
    def test_subprocess_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, cp_d, out_d = self._setup(Path(td))
            from scripts.preview_demo_tiny_lifecycle_real_execution_summary import run_execute
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_lifecycle_summary=False,
                allow_real_lifecycle_execution=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d, tiny_cleanup_dir=cp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_subprocess_missing_exits_1(self):
        from scripts.preview_demo_tiny_lifecycle_real_execution_summary import run_execute
        with tempfile.TemporaryDirectory() as td:
            base = Path(td)
            for sub in ("readonly", "recon", "protection", "contract", "noop",
                        "lifecycle", "real_perm", "entry_perm", "stop_perm",
                        "cleanup_perm"):
                (base / sub).mkdir()
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_lifecycle_summary=False,
                allow_real_lifecycle_execution=False,
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
                output_dir=base / "out", _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# AA61: next_required_task points at TASK-014AB
# ===========================================================================

class TestAA61NextTaskIs014AB:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == (
            "TASK-014AB_tiny_lifecycle_real_execution_runner_design_or_manual_approval"
        )


# ===========================================================================
# AA62: upstream gate statuses echoed
# ===========================================================================

class TestAA62UpstreamStatusesEchoed:
    def test_echoed(self):
        r = _run()
        assert r.upstream_real_permission_status == "REAL_PERMISSION_CHECKLIST_READY"
        assert r.upstream_tiny_entry_permission_status == "TINY_ENTRY_PERMISSION_CHECKLIST_READY"
        assert r.upstream_tiny_stop_attach_permission_status == "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY"
        assert r.upstream_tiny_cleanup_permission_status == "TINY_CLEANUP_PERMISSION_CHECKLIST_READY"
