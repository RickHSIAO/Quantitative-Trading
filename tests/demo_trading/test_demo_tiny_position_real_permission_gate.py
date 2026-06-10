"""
tests/demo_trading/test_demo_tiny_position_real_permission_gate.py
TASK-014W: Demo Tiny Isolated Position Real Execution Permission Gate
tests (W1 - W45+).

Covers checklist / real_permission_gate_dry_run /
real_tiny_position_guard / fail_closed paths; all 6 stages; 41 gates;
payload-free envelope invariants; source-scan safety (no urlopen /
no forbidden imports / no secrets); report artifacts; and the
invariant that TASK-014L sender G20 (protected_entry_policy_missing)
still blocks --execute-new-entry and is NOT lifted here.
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

from src.demo_tiny_position_real_permission_gate import (
    ALL_STAGES,
    APPROVAL_TOKEN_PATTERNS,
    BASE_URL_DEMO_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyPositionRealPermissionGate,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_NOOP_RECOMMENDED_PATH,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CLEANUP_FAIL_MANUAL_REVIEW,
    GATE_CLEANUP_TOKEN_REQUIRED_FUTURE,
    GATE_CONTRACT_MISSING,
    GATE_CURRENT_TASK_REAL_EXECUTION_BLOCKED,
    GATE_DRY_RUN_REPORT_REQUIRED_PER_STEP,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_OK_STOP_FAIL_EMERGENCY_PREVIEW,
    GATE_ENTRY_REFERENCE_PRICE_NOT_POSITIVE,
    GATE_ENTRY_TOKEN_REQUIRED_FUTURE,
    GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_INSTRUMENT_MIN_STEP_UNVERIFIED,
    GATE_LEVERAGE_MUTATION_FORBIDDEN,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_NO_AUTO_NEXT_STEP_AFTER_FAILURE,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SECRETS_EMITTED,
    GATE_NOOP_PLAN_MISSING,
    GATE_NOOP_RECOMMENDED_PATH_MISMATCH,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
    GATE_READONLY_VERIFICATION_REQUIRED_PER_STEP,
    GATE_REAL_TINY_POSITION_NOT_IMPL,
    GATE_RECONCILIATION_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_ATTACH_TOKEN_REQUIRED_FUTURE,
    GATE_STOP_PRICE_NOT_POSITIVE,
    GATE_THREE_STEP_APPROVAL_REQUIRED,
    GATE_TINY_NOTIONAL_OVER_CAP,
    GATE_TINY_QTY_NOT_POSITIVE,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_PERMISSION_GATE_DRY_RUN,
    MODE_REAL_TINY_POSITION_GUARD,
    ORDER_CREATE_PATH_REF,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_SNAPSHOT,
    STAGE_2_TINY_RISK_CAP,
    STAGE_3_THREE_STEP_MANUAL_APPROVAL,
    STAGE_4_FAILURE_RESPONSE,
    STAGE_5_REAL_EXECUTION_GUARD,
    STATUS_CHECKLIST_READY,
    STATUS_FAIL_CLOSED,
    STATUS_GATE_READY_EXEC_DISABLED,
    STATUS_REAL_TINY_NOT_IMPLEMENTED,
    STOP_ATTACH_TOKEN_PATTERN,
    STRATEGY_FULL_SIZE_QTY_REF,
    TINY_NOTIONAL_CAP_USDT,
    TRADING_STOP_PATH_REF,
    TinyPositionRealPermissionGateResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_position_real_permission_gate.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_position_real_permission_gate.py"
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
        "path":                   "/v5/position/trading-stop",
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
        "tiny_qty":                   0.1,
        "tiny_notional":              6.487,
        "entry_reference_price":      64.87,
        "stop_price":                 61.63,
        "status":                     EXPECTED_LIFECYCLE_STATUS,
        "failed_phase":               "",
        "dangling_tiny_position":     False,
        "existing_positions_touched": [],
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


def _gate() -> DemoTinyPositionRealPermissionGate:
    return DemoTinyPositionRealPermissionGate()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, symbol=DEFAULT_SELECTED_SYMBOL,
    allow_real_permission_gate=False,
    allow_real_tiny_position=False,
    _now=_TEST_NOW,
) -> TinyPositionRealPermissionGateResult:
    return _gate().run_checklist(
        readonly_smoke=_valid_readonly()       if readonly   is _UNSET else readonly,
        reconciliation=_valid_reconciliation() if recon      is _UNSET else recon,
        protection=_valid_protection()         if protection is _UNSET else protection,
        contract=_valid_contract()             if contract   is _UNSET else contract,
        noop_plan=_valid_noop_plan()           if noop_plan  is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()      if lifecycle  is _UNSET else lifecycle,
        symbol=symbol,
        allow_real_permission_gate=allow_real_permission_gate,
        allow_real_tiny_position=allow_real_tiny_position,
        _now=_now,
    )


# ===========================================================================
# W1: default checklist SOLUSDT -> REAL_PERMISSION_CHECKLIST_READY
# ===========================================================================

class TestW1ChecklistReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_CHECKLIST_READY
        assert r.mode == MODE_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_tiny_position_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == (
            "TASK-014X_tiny_isolated_demo_entry_permission_gate"
        )


# ===========================================================================
# W2: missing readonly_smoke => FAIL_CLOSED + stage_0 failed
# ===========================================================================

class TestW2MissingReadonly:
    def test_none_readonly(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates

    def test_empty_readonly(self):
        r = _run(readonly={})
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


# ===========================================================================
# W3: missing reconciliation => FAIL_CLOSED
# ===========================================================================

class TestW3MissingReconciliation:
    def test_none_recon(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.failed_stage == STAGE_0_ARTIFACT_PREFLIGHT
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


# ===========================================================================
# W4: missing protection => FAIL_CLOSED
# ===========================================================================

class TestW4MissingProtection:
    def test_none_protection(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


# ===========================================================================
# W5: missing contract => FAIL_CLOSED
# ===========================================================================

class TestW5MissingContract:
    def test_none_contract(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


# ===========================================================================
# W6: missing noop_plan => FAIL_CLOSED
# ===========================================================================

class TestW6MissingNoopPlan:
    def test_none_noop_plan(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


# ===========================================================================
# W7: missing lifecycle_mock => FAIL_CLOSED
# ===========================================================================

class TestW7MissingLifecycle:
    def test_none_lifecycle(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


# ===========================================================================
# W8: missing symbol => FAIL_CLOSED
# ===========================================================================

class TestW8MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# W9: symbol collides with existing positions => FAIL_CLOSED
# ===========================================================================

class TestW9SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_existing_symbol_blocks(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# W10: endpoint_family mismatch
# ===========================================================================

class TestW10EndpointFamilyMismatch:
    def test_wrong_family(self):
        ro = _valid_readonly()
        ro["endpoint_family"] = "bybit_mainnet"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


# ===========================================================================
# W11: account_mode mismatch
# ===========================================================================

class TestW11AccountModeMismatch:
    def test_wrong_mode(self):
        ro = _valid_readonly()
        ro["account_mode"] = "live"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


# ===========================================================================
# W12: proof_strength mismatch
# ===========================================================================

class TestW12ProofStrengthMismatch:
    def test_weak_proof(self):
        ro = _valid_readonly()
        ro["proof_strength"] = "WEAK"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


# ===========================================================================
# W13: position_details_source mismatch
# ===========================================================================

class TestW13PositionDetailsSourceMismatch:
    def test_wrong_source(self):
        rec = _valid_reconciliation()
        rec["mode"] = "synthetic"
        rec["position_details_source"] = "synthetic"
        r = _run(recon=rec)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


# ===========================================================================
# W14: noop recommended_path mismatch
# ===========================================================================

class TestW14NoopRecommendedPathMismatch:
    def test_mismatch(self):
        plan = _valid_noop_plan()
        plan["recommended_path"] = "read_only_endpoint_research"
        r = _run(noop_plan=plan)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_RECOMMENDED_PATH_MISMATCH in r.blocked_gates


# ===========================================================================
# W15: lifecycle_mock status not success => FAIL_CLOSED
# ===========================================================================

class TestW15LifecycleNotSuccess:
    def test_lifecycle_fail_closed(self):
        lc = _valid_lifecycle()
        lc["status"] = "MOCK_TINY_LIFECYCLE_FAIL_CLOSED"
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_NOT_SUCCESS in r.blocked_gates


# ===========================================================================
# W16: tiny_qty / tiny_notional reflect upstream lifecycle_mock
# ===========================================================================

class TestW16TinyRiskFieldsFromLifecycle:
    def test_fields_propagate(self):
        r = _run()
        assert r.tiny_qty == 0.1
        assert abs(r.tiny_notional - 6.487) < 1e-9
        assert r.entry_reference_price == 64.87
        assert r.stop_price == 61.63
        assert r.within_tiny_notional_cap is True
        assert r.tiny_notional_cap_usdt == TINY_NOTIONAL_CAP_USDT


# ===========================================================================
# W17: tiny_notional over cap => FAIL_CLOSED
# ===========================================================================

class TestW17TinyNotionalOverCap:
    def test_over_cap(self):
        lc = _valid_lifecycle()
        lc["tiny_qty"]      = 1.0
        lc["tiny_notional"] = 100.0  # well over 10 USDT cap
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_NOTIONAL_OVER_CAP in r.blocked_gates


# ===========================================================================
# W18: entry_reference_price = 0 => FAIL_CLOSED
# ===========================================================================

class TestW18EntryPriceZero:
    def test_entry_zero(self):
        prot = _valid_protection()
        prot["entry_reference_price"] = 0.0
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENTRY_REFERENCE_PRICE_NOT_POSITIVE in r.blocked_gates


# ===========================================================================
# W19: stop_price = 0 => FAIL_CLOSED
# ===========================================================================

class TestW19StopPriceZero:
    def test_stop_zero(self):
        prot = _valid_protection()
        prot["stop_price"] = 0.0
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PRICE_NOT_POSITIVE in r.blocked_gates


# ===========================================================================
# W20: tiny_qty defaults to 0.1 when missing from lifecycle but entry > 0
# ===========================================================================

class TestW20TinyQtyDefault:
    def test_default_qty(self):
        lc = _valid_lifecycle()
        lc.pop("tiny_qty", None)
        lc.pop("tiny_notional", None)
        r = _run(lifecycle=lc)
        # tiny_qty defaults to 0.1; tiny_notional = 0.1 * entry_ref = 6.487
        assert r.tiny_qty == 0.1
        assert abs(r.tiny_notional - 6.487) < 1e-9
        assert r.within_tiny_notional_cap is True


# ===========================================================================
# W21: strategy_full_size_qty_ref = 12.2 always documented & flagged not reusable
# ===========================================================================

class TestW21StrategyFullSizeQtyRef:
    def test_constant(self):
        assert STRATEGY_FULL_SIZE_QTY_REF == 12.2

    def test_result_records(self):
        r = _run()
        assert r.strategy_full_size_qty_ref == 12.2
        env = r.stages[STAGE_2_TINY_RISK_CAP]
        assert env["strategy_full_size_qty_ref"] == 12.2
        assert env["strategy_full_size_qty_must_not_be_reused"] is True


# ===========================================================================
# W22: module defines >= 41 gate constants
# ===========================================================================

class TestW22GateCount:
    def test_module_defines_at_least_41_gates(self):
        import src.demo_tiny_position_real_permission_gate as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 41, (
            f"Module should define at least 41 GATE_ constants, "
            f"got {len(gate_names)}: {sorted(gate_names)}"
        )


# ===========================================================================
# W23: always-on gates surface in checklist (defense in depth)
# ===========================================================================

class TestW23AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            GATE_INSTRUMENT_MIN_STEP_UNVERIFIED,
            GATE_LEVERAGE_MUTATION_FORBIDDEN,
            GATE_THREE_STEP_APPROVAL_REQUIRED,
            GATE_ENTRY_TOKEN_REQUIRED_FUTURE,
            GATE_STOP_ATTACH_TOKEN_REQUIRED_FUTURE,
            GATE_CLEANUP_TOKEN_REQUIRED_FUTURE,
            GATE_DRY_RUN_REPORT_REQUIRED_PER_STEP,
            GATE_READONLY_VERIFICATION_REQUIRED_PER_STEP,
            GATE_NO_AUTO_NEXT_STEP_AFTER_FAILURE,
            GATE_ENTRY_OK_STOP_FAIL_EMERGENCY_PREVIEW,
            GATE_CLEANUP_FAIL_MANUAL_REVIEW,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_READONLY_UNAVAILABLE_FAIL_CLOSED,
            GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
            GATE_REAL_TINY_POSITION_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_G20_NOT_LIFTED,
            GATE_CURRENT_TASK_REAL_EXECUTION_BLOCKED,
            GATE_G20_POLICY_STILL_IN_PLACE,
            GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


# ===========================================================================
# W24: --allow-real-permission-gate => GATE_READY_EXEC_DISABLED
# ===========================================================================

class TestW24RealPermissionGateDryRun:
    def test_promotes_status(self):
        r = _run(allow_real_permission_gate=True)
        assert r.status == STATUS_GATE_READY_EXEC_DISABLED
        assert r.mode == MODE_REAL_PERMISSION_GATE_DRY_RUN
        assert r.real_permission_gate_dry_run_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_tiny_position_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# W25: --allow-real-tiny-position => REAL_TINY_POSITION_NOT_IMPLEMENTED
# ===========================================================================

class TestW25RealTinyGuard:
    def test_real_guard_returns_not_impl(self):
        r = _run(allow_real_tiny_position=True)
        assert r.status == STATUS_REAL_TINY_NOT_IMPLEMENTED
        assert r.mode == MODE_REAL_TINY_POSITION_GUARD
        assert r.real_execution_allowed is False
        assert r.real_tiny_position_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.real_tiny_position_requested is True
        assert GATE_REAL_TINY_POSITION_NOT_IMPL in r.blocked_gates

    def test_safety_invariants_under_real_guard(self):
        r = _run(allow_real_tiny_position=True)
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True


# ===========================================================================
# W26: 6 stages present + stage_order matches ALL_STAGES
# ===========================================================================

class TestW26SixStagesPresent:
    def test_six_stages(self):
        r = _run()
        assert set(r.stages.keys()) == set(ALL_STAGES)
        assert r.stage_order == list(ALL_STAGES)

    def test_stage_constants_distinct(self):
        assert len(set(ALL_STAGES)) == 6


# ===========================================================================
# W27: stage envelopes carry zero endpoint_called flags
# ===========================================================================

class TestW27EnvelopesNeverCallEndpoint:
    def test_all_stage_endpoint_called_false(self):
        r = _run()
        for stage_id, env in r.stages.items():
            assert env.get("endpoint_called", False) is False, (
                f"stage {stage_id} must not flag endpoint_called"
            )


# ===========================================================================
# W28: approval token patterns (3 distinct, documented only)
# ===========================================================================

class TestW28ApprovalTokenPatterns:
    def test_three_distinct(self):
        assert len(set(APPROVAL_TOKEN_PATTERNS)) == 3
        assert ENTRY_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"
        assert STOP_ATTACH_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"
        assert CLEANUP_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL"

    def test_result_records_patterns(self):
        r = _run()
        assert r.approval_token_patterns == list(APPROVAL_TOKEN_PATTERNS)
        assert r.three_step_approval_required is True

    def test_stage_3_envelope_carries_future_tasks(self):
        r = _run()
        env = r.stages[STAGE_3_THREE_STEP_MANUAL_APPROVAL]
        assert env["step_a_entry"]["token_pattern"] == ENTRY_TOKEN_PATTERN
        assert env["step_b_stop_attach"]["token_pattern"] == STOP_ATTACH_TOKEN_PATTERN
        assert env["step_c_cleanup"]["token_pattern"] == CLEANUP_TOKEN_PATTERN
        assert "TASK-014X" in env["step_a_entry"]["future_task"]
        assert "TASK-014Y" in env["step_b_stop_attach"]["future_task"]
        assert "TASK-014Z" in env["step_c_cleanup"]["future_task"]
        assert env["no_token_validation_in_this_task"] is True


# ===========================================================================
# W29: existing 5 demo positions documented + never touched
# ===========================================================================

class TestW29ExistingPositionsDocumented:
    def test_constant_matches_spec(self):
        assert set(EXISTING_POSITION_SYMBOLS) == {
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
        }

    def test_existing_position_symbols_in_result(self):
        r = _run()
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols
        assert r.existing_positions_touched == []
        assert r.existing_position_stop_snapshot_match is True


# ===========================================================================
# W30: stage_0 envelope documents 6 upstream artifact presence
# ===========================================================================

class TestW30Stage0Envelope:
    def test_stage_0_fields(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        for fld in (
            "readonly_smoke_present", "reconciliation_present",
            "protection_present", "contract_present",
            "noop_plan_present", "lifecycle_mock_present",
            "endpoint_family_observed", "endpoint_family_expected",
            "account_mode_observed", "account_mode_expected",
            "proof_strength_observed", "proof_strength_expected",
            "position_details_source_observed", "position_details_source_expected",
            "noop_recommended_path_observed", "noop_recommended_path_expected",
            "lifecycle_status_observed", "lifecycle_status_expected",
            "selected_symbol",
        ):
            assert fld in env, f"stage_0 field {fld} missing"
        assert env["readonly_smoke_present"] is True
        assert env["lifecycle_mock_present"] is True


# ===========================================================================
# W31: report artifacts (CHECKLIST mode)
# ===========================================================================

class TestW31ReportChecklist:
    def _setup(self, base: Path):
        ro_d   = base / "readonly";    ro_d.mkdir()
        rec_d  = base / "recon";       rec_d.mkdir()
        prot_d = base / "protection";  prot_d.mkdir()
        con_d  = base / "contract";    con_d.mkdir()
        noop_d = base / "noop";        noop_d.mkdir()
        lc_d   = base / "lifecycle";   lc_d.mkdir()
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d

    def test_checklist_writes_report(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_position_real_permission_gate.json" in files
            assert "latest_tiny_position_real_permission_gate.md"   in files
            ts_json = [n for n in files if n.endswith(".json") and not n.startswith("latest_")]
            ts_md   = [n for n in files if n.endswith(".md")   and not n.startswith("latest_")]
            assert len(ts_json) == 1
            assert len(ts_md)   == 1
            data = json.loads(
                (out_d / "latest_tiny_position_real_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_CHECKLIST_READY
            assert data["current_task_real_execution_allowed"] is False


# ===========================================================================
# W32: report artifacts (PERMISSION_GATE_DRY_RUN mode)
# ===========================================================================

class TestW32ReportPermissionGateDryRun(TestW31ReportChecklist):
    def test_dry_run_report(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=True,
                allow_real_tiny_position=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads(
                (out_d / "latest_tiny_position_real_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_GATE_READY_EXEC_DISABLED
            assert data["mode"] == MODE_REAL_PERMISSION_GATE_DRY_RUN
            assert data["real_permission_gate_dry_run_allowed"] is True
            assert data["real_execution_allowed"] is False


# ===========================================================================
# W33: report artifacts (REAL_TINY_GUARD mode)
# ===========================================================================

class TestW33ReportRealGuard(TestW31ReportChecklist):
    def test_real_guard_report(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=True,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads(
                (out_d / "latest_tiny_position_real_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_REAL_TINY_NOT_IMPLEMENTED
            assert data["real_execution_allowed"] is False
            assert data["real_tiny_position_implemented"] is False
            assert data["real_tiny_position_requested"] is True
            assert GATE_REAL_TINY_POSITION_NOT_IMPL in data["blocked_gates"]
            md = (out_d / "latest_tiny_position_real_permission_gate.md").read_text(encoding="utf-8")
            assert "REAL_TINY_POSITION_NOT_IMPLEMENTED" in md


# ===========================================================================
# W34: no secrets in report
# ===========================================================================

class TestW34NoSecretsInReport(TestW31ReportChecklist):
    def test_no_secret_strings(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads(
                (out_d / "latest_tiny_position_real_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False
            md = (out_d / "latest_tiny_position_real_permission_gate.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md


# ===========================================================================
# W35: no forbidden imports in module + CLI
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


class TestW35NoForbiddenImports:
    def test_module_imports(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli_imports(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            # CLI may import src.demo_tiny_position_real_permission_gate but
            # NOT any of the listed forbidden modules.
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# W36: no urllib / urlopen / socket / http.client / env / signing in source
# ===========================================================================

class TestW36NoNetworkTokensInSource:
    def test_no_network_tokens(self):
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
# W37: no sender / orchestrator / probe / lifecycle back-coupling
# ===========================================================================

class TestW37NoSenderReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"     not in code
            assert "demo_close_only_sender"  not in code

    def test_no_emergency_close(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoEmergencyCloseSender"     not in code
            assert "demo_emergency_close_sender"  not in code

    def test_no_new_entry_sender(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoNewEntrySender"      not in code
            assert "demo_new_entry_sender"   not in code

    def test_no_orchestrator_back_coupling(self):
        code = _read_code_only(_MODULE_PATH)
        assert "demo_protected_new_entry_orchestrator" not in code

    def test_no_contract_probe_back_coupling(self):
        code = _read_code_only(_MODULE_PATH)
        assert "demo_trading_stop_contract_probe" not in code

    def test_no_noop_plan_back_coupling(self):
        code = _read_code_only(_MODULE_PATH)
        assert "demo_trading_stop_noop_probe_plan" not in code

    def test_no_lifecycle_mock_back_coupling(self):
        code = _read_code_only(_MODULE_PATH)
        assert "demo_tiny_position_lifecycle_mock" not in code


# ===========================================================================
# W38: module does not open a socket at import time
# ===========================================================================

class TestW38NoSocketAtImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_position_real_permission_gate as m; "
             "print('OK', m.STATUS_CHECKLIST_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# W39: TASK-014L G20 is NOT lifted by this task
# ===========================================================================

class TestW39G20StillBlocks:
    def test_g20_constant_unchanged(self):
        from src.demo_new_entry_protection import G20_BLOCKED_GATE_NAME
        assert G20_BLOCKED_GATE_NAME == "protected_entry_policy_missing"

    def test_gate_does_not_reference_g20_literal(self):
        code = _read_code_only(_MODULE_PATH)
        assert "protected_entry_policy_missing" not in code
        assert "G20_BLOCKED_GATE_NAME"          not in code

    def test_result_records_g20_still_in_place(self):
        r = _run()
        assert r.g20_policy_still_in_place is True
        assert r.g20_lifted is False
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates
        assert GATE_G20_NOT_LIFTED in r.blocked_gates


# ===========================================================================
# W40: safety invariants conservative across all modes
# ===========================================================================

class TestW40SafetyInvariants:
    def test_invariants_default_checklist(self):
        r = _run()
        assert r.stop_endpoint_called  is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified  is True
        assert r.no_live_endpoint      is True
        assert r.no_orders_sent        is True
        assert r.no_batch_order        is True
        assert r.no_close_only_path    is True
        assert r.emergency_close_invoked is False
        assert r.leverage_mutated      is False
        assert r.transfer_invoked      is False
        assert r.secret_value_observed is False

    def test_invariants_under_dry_run(self):
        r = _run(allow_real_permission_gate=True)
        assert r.stop_endpoint_called  is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified  is True
        assert r.no_live_endpoint      is True

    def test_invariants_under_real_guard(self):
        r = _run(allow_real_tiny_position=True)
        assert r.stop_endpoint_called  is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified  is True

    def test_path_refs_are_string_only(self):
        r = _run()
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


# ===========================================================================
# W41: dataclass to_dict round-trip + deep-copy of stages dict
# ===========================================================================

class TestW41DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_real_permission_gate=True)
        d = r.to_dict()
        for key, expected in (
            ("stop_endpoint_called",                False),
            ("order_endpoint_called",               False),
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
            ("real_tiny_position_implemented",      False),
            ("real_execution_allowed",              False),
            ("real_permission_gate_dry_run_allowed", True),
            ("existing_position_stop_snapshot_match", True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_GATE_READY_EXEC_DISABLED
        # to_dict() returns deep copies; mutating must not affect source.
        d["stages"][STAGE_3_THREE_STEP_MANUAL_APPROVAL]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_3_THREE_STEP_MANUAL_APPROVAL]


# ===========================================================================
# W42: CLI exit codes
# ===========================================================================

class TestW42CLIExitCodes(TestW31ReportChecklist):
    def test_missing_upstream_returns_1(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            base   = Path(td)
            ro_d   = base / "readonly";    ro_d.mkdir()
            rec_d  = base / "recon";       rec_d.mkdir()
            prot_d = base / "protection";  prot_d.mkdir()
            con_d  = base / "contract";    con_d.mkdir()
            noop_d = base / "noop";        noop_d.mkdir()
            lc_d   = base / "lifecycle";   lc_d.mkdir()
            out_d  = base / "out"
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_missing_symbol_returns_1(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_collision_symbol_returns_1(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="ENAUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_checklist_returns_0(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_dry_run_returns_0(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=True,
                allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_real_guard_returns_0(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=True,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_lifecycle_fail_closed_returns_1(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup(Path(td))
            # Overwrite lifecycle with non-success status.
            bad = _valid_lifecycle()
            bad["status"] = "MOCK_TINY_LIFECYCLE_FAIL_CLOSED"
            (lc_d / "latest_tiny_position_lifecycle_mock.json").write_text(
                json.dumps(bad), encoding="utf-8",
            )
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# W43: noop_plan loader CLI also resolves legacy alias filename
# ===========================================================================

class TestW43NoopPlanLegacyAlias:
    def _setup_legacy(self, base: Path):
        ro_d   = base / "readonly";    ro_d.mkdir()
        rec_d  = base / "recon";       rec_d.mkdir()
        prot_d = base / "protection";  prot_d.mkdir()
        con_d  = base / "contract";    con_d.mkdir()
        noop_d = base / "noop";        noop_d.mkdir()
        lc_d   = base / "lifecycle";   lc_d.mkdir()
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        # Write legacy alias only -- no primary.
        (noop_d / "latest_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d

    def test_legacy_alias_resolves(self):
        from scripts.preview_demo_tiny_position_real_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, out_d = self._setup_legacy(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_permission_gate=False,
                allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0


# ===========================================================================
# W44: tiny_notional_cap = 10 USDT (frozen constant)
# ===========================================================================

class TestW44TinyNotionalCap:
    def test_cap_constant(self):
        assert TINY_NOTIONAL_CAP_USDT == 10.0

    def test_within_cap_default(self):
        r = _run()
        # Default fixtures: 0.1 * 64.87 = 6.487 < 10 -> within cap.
        assert r.within_tiny_notional_cap is True

    def test_just_over_cap_fails(self):
        lc = _valid_lifecycle()
        lc["tiny_qty"]      = 0.2
        lc["tiny_notional"] = 11.0
        r = _run(lifecycle=lc)
        assert r.within_tiny_notional_cap is False
        assert GATE_TINY_NOTIONAL_OVER_CAP in r.blocked_gates
        assert r.status == STATUS_FAIL_CLOSED


# ===========================================================================
# W45: stage_4 failure response envelope documents four fail-closed paths
# ===========================================================================

class TestW45Stage4FailureResponse:
    def test_four_failure_paths_documented(self):
        r = _run()
        env = r.stages[STAGE_4_FAILURE_RESPONSE]
        for fld in (
            "entry_ok_stop_fail",
            "stop_attach_ok_cleanup_fail",
            "existing_stop_mismatch",
            "readonly_verification_unavailable",
        ):
            assert fld in env, f"stage_4 field {fld} missing"
            assert env[fld].get("status") == "fail_closed"
        assert env["no_real_emergency_close_in_this_task"] is True


# ===========================================================================
# W46: stage_5 execution guard envelope flags are conservative
# ===========================================================================

class TestW46Stage5ExecutionGuard:
    def test_stage_5_flags(self):
        r = _run(allow_real_permission_gate=True)
        env = r.stages[STAGE_5_REAL_EXECUTION_GUARD]
        assert env["real_permission_gate_dry_run_allowed"] is True
        assert env["real_execution_allowed"] is False
        assert env["real_tiny_position_implemented"] is False
        assert env["current_task_real_execution_allowed"] is False
        assert env["g20_policy_still_in_place"] is True
        assert env["g20_lifted"] is False
        assert env["no_real_order_endpoint"] is True
        assert env["no_real_stop_endpoint"] is True
        assert env["no_position_modified"] is True
        assert env["no_live_endpoint"] is True
        assert env["no_secrets_emitted"] is True


# ===========================================================================
# W47: stage_1 envelope snapshots 5 existing demo shorts
# ===========================================================================

class TestW47Stage1Snapshot:
    def test_five_existing_documented(self):
        r = _run()
        env = r.stages[STAGE_1_EXISTING_POSITION_SNAPSHOT]
        assert env["existing_position_count"] == 5
        syms = {row["symbol"] for row in env["existing_positions_snapshot"]}
        assert syms == set(EXISTING_POSITION_SYMBOLS)
        assert env["snapshot_fields_ok"] is True
        assert env["selected_symbol_disjoint"] is True
        assert env["post_run_stop_match_required"] is True
        assert env["mismatch_action"] == "fail_closed_manual_review"
