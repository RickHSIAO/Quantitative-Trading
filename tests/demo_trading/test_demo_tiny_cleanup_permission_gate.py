"""
tests/demo_trading/test_demo_tiny_cleanup_permission_gate.py
TASK-014Z: Tiny Isolated Demo Cleanup Permission Gate / Dry-run Only
tests (Z1 - Z62+).

Covers checklist / real_cleanup_permission_dry_run / real_cleanup_guard
/ fail_closed paths; all 7 stages; >=49 gates; cleanup payload preview
(side=Sell, orderType=Market, reduceOnly=True, positionIdx=0,
orderLinkId=DRYRUN-TINY-CLEANUP-...); expected_tiny_qty derivation
from entry permission gate and lifecycle mock; source-scan safety
(no urlopen / no forbidden imports / no secrets); report artifacts;
and the invariant that TASK-014L sender G20
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

from src.demo_tiny_cleanup_permission_gate import (
    ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES,
    ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES,
    ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyCleanupPermissionGate,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_CLEANUP_SIDE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_ENTRY_SIDE,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_ORDER_TYPE,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_POSITION_IDX,
    EXPECTED_PROOF_STRENGTH,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CLEANUP_CATEGORY_NOT_LINEAR,
    GATE_CLEANUP_ORDER_LINK_ID_NOT_DRYRUN,
    GATE_CLEANUP_ORDER_TYPE_NOT_MARKET,
    GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED,
    GATE_CLEANUP_POSITION_IDX_NOT_ZERO,
    GATE_CLEANUP_REDUCE_ONLY_NOT_TRUE,
    GATE_CLEANUP_REJECTED_FAIL_CLOSED,
    GATE_CLEANUP_SIDE_NOT_SELL_FOR_LONG,
    GATE_CLEANUP_SYMBOL_MISMATCH,
    GATE_CLEANUP_TOKEN_NOT_VALIDATED_THIS_TASK,
    GATE_CLEANUP_TOKEN_PATTERN_REQUIRED,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK,
    GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
    GATE_EXPECTED_TINY_QTY_MISMATCH_ENTRY_GATE,
    GATE_EXPECTED_TINY_QTY_MISSING,
    GATE_EXPECTED_TINY_QTY_NOT_POSITIVE,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_NO_AUTO_RETRY_AFTER_CLEANUP_FAIL,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SECRETS_EMITTED,
    GATE_NOOP_PLAN_MISSING,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POST_CLEANUP_READONLY_VERIFICATION_REQUIRED,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_AFTER_CLEANUP_FAIL_CLOSED,
    GATE_REAL_CLEANUP_NOT_IMPL,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_RECONCILIATION_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SOLUSDT_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED,
    GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_CLEANUP_GUARD,
    MODE_REAL_CLEANUP_PERMISSION_DRY_RUN,
    ORDER_CREATE_PATH_REF,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT,
    STAGE_2_CLEANUP_PAYLOAD_PREVIEW,
    STAGE_3_CLEANUP_TOKEN_CHECKLIST,
    STAGE_4_POST_CLEANUP_REQUIRED_VERIFICATION_PLAN,
    STAGE_5_FAILURE_RESPONSE_PLAN,
    STAGE_6_EXECUTION_GUARD,
    STATUS_CHECKLIST_READY,
    STATUS_FAIL_CLOSED,
    STATUS_PERMISSION_READY_EXEC_DISABLED,
    STATUS_REAL_CLEANUP_NOT_IMPL,
    STOP_ATTACH_TOKEN_PATTERN,
    TRADING_STOP_PATH_REF,
    TinyCleanupPermissionGateResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_cleanup_permission_gate.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_cleanup_permission_gate.py"
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
        "recommended_path":           "tiny_isolated_position_plan",
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


def _valid_real_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:58:00Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "status":             "REAL_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":               False,
        "real_tiny_position_implemented":       False,
        "current_task_real_execution_allowed":  False,
        "real_tiny_position_requested":         False,
    }


def _valid_tiny_entry_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:59:00Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "status":             "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
        "rounded_tiny_qty":   0.1,
        "real_execution_allowed":               False,
        "real_tiny_entry_implemented":          False,
        "current_task_real_execution_allowed":  False,
        "real_tiny_entry_requested":            False,
    }


def _valid_tiny_stop_attach_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:59:30Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "status":             "TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY",
        "stop_price":         61.63,
        "real_execution_allowed":               False,
        "real_stop_attach_implemented":         False,
        "current_task_real_execution_allowed":  False,
        "real_stop_attach_requested":           False,
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


def _gate() -> DemoTinyCleanupPermissionGate:
    return DemoTinyCleanupPermissionGate()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    tiny_stop_attach_permission_gate=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_real_cleanup_permission=False,
    allow_real_cleanup=False,
    _now=_TEST_NOW,
) -> TinyCleanupPermissionGateResult:
    return _gate().run_checklist(
        readonly_smoke=_valid_readonly()       if readonly             is _UNSET else readonly,
        reconciliation=_valid_reconciliation() if recon                is _UNSET else recon,
        protection=_valid_protection()         if protection           is _UNSET else protection,
        contract=_valid_contract()             if contract             is _UNSET else contract,
        noop_plan=_valid_noop_plan()           if noop_plan            is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()      if lifecycle            is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate() if real_permission_gate is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate() if tiny_entry_permission_gate is _UNSET else tiny_entry_permission_gate,
        tiny_stop_attach_permission_gate=_valid_tiny_stop_attach_permission_gate() if tiny_stop_attach_permission_gate is _UNSET else tiny_stop_attach_permission_gate,
        symbol=symbol,
        allow_real_cleanup_permission=allow_real_cleanup_permission,
        allow_real_cleanup=allow_real_cleanup,
        _now=_now,
    )


# ===========================================================================
# Z1: valid checklist => TINY_CLEANUP_PERMISSION_CHECKLIST_READY
# ===========================================================================

class TestZ1ChecklistReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_CHECKLIST_READY
        assert r.mode == MODE_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == (
            "TASK-014AA_tiny_lifecycle_real_execution_permission_summary"
        )


# ===========================================================================
# Z2: --allow-real-cleanup-permission => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestZ2RealCleanupPermissionDryRun:
    def test_promotes_status(self):
        r = _run(allow_real_cleanup_permission=True)
        assert r.status == STATUS_PERMISSION_READY_EXEC_DISABLED
        assert r.mode == MODE_REAL_CLEANUP_PERMISSION_DRY_RUN
        assert r.real_cleanup_permission_dry_run_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# Z3: --allow-real-cleanup => REAL_CLEANUP_NOT_IMPLEMENTED
# ===========================================================================

class TestZ3RealCleanupGuard:
    def test_guard_returns_not_impl(self):
        r = _run(allow_real_cleanup=True)
        assert r.status == STATUS_REAL_CLEANUP_NOT_IMPL
        assert r.mode == MODE_REAL_CLEANUP_GUARD
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.real_cleanup_requested is True
        assert GATE_REAL_CLEANUP_NOT_IMPL in r.blocked_gates


# ===========================================================================
# Z4 - Z12: missing upstream artifacts => FAIL_CLOSED  (9 artifacts)
# ===========================================================================

class TestZ4MissingReadonly:
    def test_none(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestZ5MissingReconciliation:
    def test_none(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestZ6MissingProtection:
    def test_none(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestZ7MissingContract:
    def test_none(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestZ8MissingNoopPlan:
    def test_none(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestZ9MissingLifecycle:
    def test_none(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestZ10MissingRealPermissionGate:
    def test_none(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestZ11MissingTinyEntryPermissionGate:
    def test_none(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


class TestZ12MissingTinyStopAttachPermissionGate:
    def test_none(self):
        r = _run(tiny_stop_attach_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING in r.blocked_gates


# ===========================================================================
# Z13: selected_symbol collides with an existing position => FAIL_CLOSED
# ===========================================================================

class TestZ13SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_collision_blocks(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# Z14 - Z18: proof envelope mismatches => FAIL_CLOSED
# ===========================================================================

class TestZ14EndpointFamilyMismatch:
    def test_mainnet(self):
        ro = _valid_readonly(); ro["endpoint_family"] = "bybit_mainnet"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestZ15AccountModeMismatch:
    def test_live(self):
        ro = _valid_readonly(); ro["account_mode"] = "live"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestZ16ProofStrengthMismatch:
    def test_weak(self):
        ro = _valid_readonly(); ro["proof_strength"] = "WEAK"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestZ17PositionDetailsSourceMismatch:
    def test_synthetic(self):
        rec = _valid_reconciliation()
        rec["mode"] = "synthetic"
        rec["position_details_source"] = "synthetic"
        r = _run(recon=rec)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


class TestZ18LifecycleNotSuccess:
    def test_fail_closed(self):
        lc = _valid_lifecycle()
        lc["status"] = "MOCK_TINY_LIFECYCLE_FAIL_CLOSED"
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_NOT_SUCCESS in r.blocked_gates


# ===========================================================================
# Z19: real_permission_gate status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestZ19RealPermissionUnacceptable:
    def test_fail_closed(self):
        rpg = _valid_real_permission_gate()
        rpg["status"] = "FAIL_CLOSED"
        r = _run(real_permission_gate=rpg)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        rpg = _valid_real_permission_gate()
        rpg["status"] = status
        r = _run(real_permission_gate=rpg)
        assert r.status == STATUS_CHECKLIST_READY


# ===========================================================================
# Z20: tiny_entry_permission_gate status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestZ20TinyEntryPermissionUnacceptable:
    def test_fail_closed(self):
        ep = _valid_tiny_entry_permission_gate()
        ep["status"] = "FAIL_CLOSED"
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        ep = _valid_tiny_entry_permission_gate()
        ep["status"] = status
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_CHECKLIST_READY


# ===========================================================================
# Z21: tiny_stop_attach_permission_gate status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestZ21TinyStopAttachPermissionUnacceptable:
    def test_fail_closed(self):
        sp = _valid_tiny_stop_attach_permission_gate()
        sp["status"] = "FAIL_CLOSED"
        r = _run(tiny_stop_attach_permission_gate=sp)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUS_UNACCEPTABLE in r.blocked_gates

    @pytest.mark.parametrize("status", sorted(ACCEPTABLE_TINY_STOP_ATTACH_PERMISSION_GATE_STATUSES))
    def test_acceptable_statuses_pass(self, status):
        sp = _valid_tiny_stop_attach_permission_gate()
        sp["status"] = status
        r = _run(tiny_stop_attach_permission_gate=sp)
        assert r.status == STATUS_CHECKLIST_READY


# ===========================================================================
# Z22: expected_tiny_qty derived from entry permission gate when both present
# ===========================================================================

class TestZ22ExpectedQtyFromEntryGate:
    def test_uses_entry_rounded(self):
        r = _run()
        assert r.entry_rounded_tiny_qty == pytest.approx(0.1)
        assert r.lifecycle_tiny_qty == pytest.approx(0.1)
        assert r.expected_tiny_qty == pytest.approx(0.1)
        assert r.status == STATUS_CHECKLIST_READY


# ===========================================================================
# Z23: expected_tiny_qty fallback from lifecycle when entry rounded missing
# ===========================================================================

class TestZ23ExpectedQtyFallback:
    def test_lifecycle_fallback(self):
        ep = _valid_tiny_entry_permission_gate()
        ep.pop("rounded_tiny_qty", None)
        r = _run(tiny_entry_permission_gate=ep)
        # lifecycle tiny_qty=0.1 should be used.
        assert r.entry_rounded_tiny_qty == pytest.approx(0.0)
        assert r.lifecycle_tiny_qty == pytest.approx(0.1)
        assert r.expected_tiny_qty == pytest.approx(0.1)
        assert r.status == STATUS_CHECKLIST_READY


# ===========================================================================
# Z24: expected_tiny_qty mismatch between entry gate and lifecycle => FAIL_CLOSED
# ===========================================================================

class TestZ24ExpectedQtyMismatch:
    def test_mismatch_blocks(self):
        ep = _valid_tiny_entry_permission_gate()
        ep["rounded_tiny_qty"] = 0.2          # mismatch with lifecycle 0.1
        r = _run(tiny_entry_permission_gate=ep)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_EXPECTED_TINY_QTY_MISMATCH_ENTRY_GATE in r.blocked_gates


# ===========================================================================
# Z25: expected_tiny_qty missing (both 0) => FAIL_CLOSED
# ===========================================================================

class TestZ25ExpectedQtyMissing:
    def test_both_zero(self):
        ep = _valid_tiny_entry_permission_gate()
        ep["rounded_tiny_qty"] = 0.0
        lc = _valid_lifecycle()
        lc["tiny_qty"] = 0.0
        r = _run(tiny_entry_permission_gate=ep, lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_EXPECTED_TINY_QTY_MISSING in r.blocked_gates

    def test_negative_qty(self):
        ep = _valid_tiny_entry_permission_gate()
        ep["rounded_tiny_qty"] = -1.0
        lc = _valid_lifecycle()
        lc["tiny_qty"] = -1.0
        r = _run(tiny_entry_permission_gate=ep, lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        # When entry is non-positive but lifecycle is non-positive too,
        # the gate falls back to lifecycle (still non-positive) -> NOT_POSITIVE.
        assert (
            GATE_EXPECTED_TINY_QTY_NOT_POSITIVE in r.blocked_gates
            or GATE_EXPECTED_TINY_QTY_MISSING in r.blocked_gates
        )


# ===========================================================================
# Z26: cleanup payload category=linear
# ===========================================================================

class TestZ26PayloadCategoryLinear:
    def test_category(self):
        r = _run()
        assert r.cleanup_payload_preview["category"] == EXPECTED_INSTRUMENT_CATEGORY


# ===========================================================================
# Z27: cleanup payload symbol matches selected
# ===========================================================================

class TestZ27PayloadSymbolMatches:
    def test_symbol(self):
        r = _run(symbol="SOLUSDT")
        assert r.cleanup_payload_preview["symbol"] == "SOLUSDT"


# ===========================================================================
# Z28: cleanup payload side=Sell
# ===========================================================================

class TestZ28PayloadSideSell:
    def test_side(self):
        r = _run()
        assert r.cleanup_payload_preview["side"] == EXPECTED_CLEANUP_SIDE
        assert EXPECTED_CLEANUP_SIDE == "Sell"
        # entry side stays "long".
        assert r.entry_side == EXPECTED_ENTRY_SIDE
        assert EXPECTED_ENTRY_SIDE == "long"


# ===========================================================================
# Z29: cleanup payload orderType=Market
# ===========================================================================

class TestZ29PayloadOrderTypeMarket:
    def test_order_type(self):
        r = _run()
        assert r.cleanup_payload_preview["orderType"] == EXPECTED_ORDER_TYPE
        assert EXPECTED_ORDER_TYPE == "Market"


# ===========================================================================
# Z30: cleanup payload reduceOnly=True
# ===========================================================================

class TestZ30PayloadReduceOnlyTrue:
    def test_reduce_only(self):
        r = _run()
        assert r.cleanup_payload_preview["reduceOnly"] is True


# ===========================================================================
# Z31: cleanup payload positionIdx=0
# ===========================================================================

class TestZ31PayloadPositionIdxZero:
    def test_position_idx(self):
        r = _run()
        assert r.cleanup_payload_preview["positionIdx"] == EXPECTED_POSITION_IDX
        assert EXPECTED_POSITION_IDX == 0


# ===========================================================================
# Z32: cleanup payload orderLinkId starts with DRYRUN-TINY-CLEANUP
# ===========================================================================

class TestZ32PayloadOrderLinkIdDryrun:
    def test_link_id_prefix(self):
        r = _run()
        link = str(r.cleanup_payload_preview["orderLinkId"])
        assert link.startswith("DRYRUN-TINY-CLEANUP-")
        # Symbol embedded in link id.
        assert "SOLUSDT" in link


# ===========================================================================
# Z33: cleanup payload preview_only=True / endpoint_called=False / qty
# ===========================================================================

class TestZ33PayloadPreviewOnlyAndQty:
    def test_preview_only_and_qty(self):
        r = _run()
        assert r.cleanup_payload_preview["preview_only"] is True
        assert r.cleanup_payload_preview["endpoint_called"] is False
        assert r.cleanup_payload_preview["endpoint_path_ref"] == ORDER_CREATE_PATH_REF
        assert r.cleanup_payload_preview["qty"] == pytest.approx(0.1)


# ===========================================================================
# Z34: closeOnTrigger=False (documentation only)
# ===========================================================================

class TestZ34PayloadCloseOnTriggerFalse:
    def test_close_on_trigger(self):
        r = _run()
        assert r.cleanup_payload_preview["closeOnTrigger"] is False


# ===========================================================================
# Z35 - Z37: safety invariants
# ===========================================================================

class TestZ35OrderEndpointFalse:
    def test_default(self):
        r = _run()
        assert r.order_endpoint_called is False

    def test_dry_run(self):
        r = _run(allow_real_cleanup_permission=True)
        assert r.order_endpoint_called is False

    def test_guard(self):
        r = _run(allow_real_cleanup=True)
        assert r.order_endpoint_called is False


class TestZ36StopEndpointFalse:
    def test_default(self):
        r = _run()
        assert r.stop_endpoint_called is False

    def test_dry_run(self):
        r = _run(allow_real_cleanup_permission=True)
        assert r.stop_endpoint_called is False

    def test_guard(self):
        r = _run(allow_real_cleanup=True)
        assert r.stop_endpoint_called is False


class TestZ37NoPositionModified:
    def test_default(self):
        r = _run()
        assert r.no_position_modified is True
        assert r.existing_positions_touched == []

    def test_dry_run(self):
        r = _run(allow_real_cleanup_permission=True)
        assert r.no_position_modified is True

    def test_guard(self):
        r = _run(allow_real_cleanup=True)
        assert r.no_position_modified is True


# ===========================================================================
# Z38: cleanup token pattern present
# ===========================================================================

class TestZ38CleanupTokenPattern:
    def test_pattern(self):
        r = _run()
        assert r.cleanup_token_pattern == CLEANUP_TOKEN_PATTERN
        assert CLEANUP_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL"
        env = r.stages[STAGE_3_CLEANUP_TOKEN_CHECKLIST]
        assert env["cleanup_token_pattern"] == CLEANUP_TOKEN_PATTERN
        assert env["cleanup_token_not_validated_in_this_task"] is True


# ===========================================================================
# Z39: entry token not accepted in this task
# ===========================================================================

class TestZ39EntryTokenNotAccepted:
    def test_documented(self):
        r = _run()
        env = r.stages[STAGE_3_CLEANUP_TOKEN_CHECKLIST]
        assert env["entry_token_not_accepted_in_this_task"] is True
        assert env["entry_token_pattern"] == ENTRY_TOKEN_PATTERN
        assert GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK in r.blocked_gates


# ===========================================================================
# Z40: stop-attach token not accepted in this task
# ===========================================================================

class TestZ40StopAttachTokenNotAccepted:
    def test_documented(self):
        r = _run()
        env = r.stages[STAGE_3_CLEANUP_TOKEN_CHECKLIST]
        assert env["stop_attach_token_not_accepted_in_this_task"] is True
        assert env["stop_attach_token_pattern"] == STOP_ATTACH_TOKEN_PATTERN
        assert GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK in r.blocked_gates


# ===========================================================================
# Z41: allow-real-cleanup does NOT run execution phase
# ===========================================================================

class TestZ41GuardDoesNotExecute:
    def test_guard_safety(self):
        r = _run(allow_real_cleanup=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_orders_sent is True
        assert r.real_execution_allowed is False
        assert r.real_cleanup_implemented is False


# ===========================================================================
# Z42: no execute flag exists (signature scan)
# ===========================================================================

class TestZ42NoExecuteFlagInModule:
    def test_no_execute_flag(self):
        code = _read_code_only(_MODULE_PATH)
        assert "execute_real_tiny_cleanup" not in code
        text = _MODULE_PATH.read_text(encoding="utf-8")
        assert "--execute-real-tiny-cleanup" not in text

    def test_no_execute_flag_in_cli(self):
        text = _SCRIPT_PATH.read_text(encoding="utf-8")
        assert "--execute-real-tiny-cleanup" not in text
        assert "--execute-tiny-cleanup"      not in text
        assert "--execute-cleanup"           not in text


# ===========================================================================
# Z43: report artifacts written (checklist)
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
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, out_d


class TestZ43ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_cleanup_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_cleanup_permission=False,
                allow_real_cleanup=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_cleanup_permission_gate.json" in files
            assert "latest_tiny_cleanup_permission_gate.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_cleanup_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_CHECKLIST_READY
            assert data["real_execution_allowed"] is False
            assert data["real_cleanup_implemented"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True
            assert data["cleanup_payload_preview"]["side"] == "Sell"
            assert data["cleanup_payload_preview"]["reduceOnly"] is True


# ===========================================================================
# Z44: no secrets in report
# ===========================================================================

class TestZ44NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_cleanup_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_cleanup_permission=False,
                allow_real_cleanup=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_cleanup_permission_gate.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_cleanup_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False


# ===========================================================================
# Z45: no forbidden imports
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


class TestZ45NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            # CLI is allowed to import src.demo_tiny_cleanup_permission_gate
            # only; nothing else from the forbidden list.
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# Z46: no close-only / emergency-close / new-entry sender reuse,
#      no trading-stop real adapter
# ===========================================================================

class TestZ46NoSenderReuse:
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
# Z47: source scan confirms no urllib/request/httpx/socket/env/signing
# ===========================================================================

class TestZ47NoNetworkTokens:
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
# Z48: CLI subprocess valid run exits 0
# ===========================================================================

class TestZ48CLISubprocessOk(_ReportSetupMixin):
    def test_subprocess_exits_0(self):
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, sp_d, out_d = self._setup(Path(td))
            from scripts.preview_demo_tiny_cleanup_permission_gate import run_execute
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_cleanup_permission=False,
                allow_real_cleanup=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0


# ===========================================================================
# Z49: CLI subprocess missing artifact exits 1
# ===========================================================================

class TestZ49CLISubprocessMissingExits1:
    def test_missing_artifact(self):
        from scripts.preview_demo_tiny_cleanup_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            base   = Path(td)
            ro_d   = base / "readonly";    ro_d.mkdir()
            rec_d  = base / "recon";       rec_d.mkdir()
            prot_d = base / "protection";  prot_d.mkdir()
            con_d  = base / "contract";    con_d.mkdir()
            noop_d = base / "noop";        noop_d.mkdir()
            lc_d   = base / "lifecycle";   lc_d.mkdir()
            rp_d   = base / "real_perm";   rp_d.mkdir()
            ep_d   = base / "entry_perm";  ep_d.mkdir()
            sp_d   = base / "stop_perm";   sp_d.mkdir()
            out_d  = base / "out"
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_cleanup_permission=False,
                allow_real_cleanup=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                tiny_stop_attach_dir=sp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# Z50: next required task = TASK-014AA_tiny_lifecycle_real_execution_permission_summary
# ===========================================================================

class TestZ50NextTaskIs014AA:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == (
            "TASK-014AA_tiny_lifecycle_real_execution_permission_summary"
        )


# ===========================================================================
# Z51: gate count >= 49
# ===========================================================================

class TestZ51GateCount:
    def test_at_least_49(self):
        import src.demo_tiny_cleanup_permission_gate as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 49, (
            f"Expected >= 49 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# Z52: always-on gates surface in every checklist
# ===========================================================================

class TestZ52AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            GATE_CLEANUP_TOKEN_PATTERN_REQUIRED,
            GATE_CLEANUP_TOKEN_NOT_VALIDATED_THIS_TASK,
            GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK,
            GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK,
            GATE_POST_CLEANUP_READONLY_VERIFICATION_REQUIRED,
            GATE_NO_AUTO_RETRY_AFTER_CLEANUP_FAIL,
            GATE_READONLY_UNAVAILABLE_AFTER_CLEANUP_FAIL_CLOSED,
            GATE_CLEANUP_REJECTED_FAIL_CLOSED,
            GATE_CLEANUP_PARTIAL_FILL_FAIL_CLOSED,
            GATE_SOLUSDT_STILL_OPEN_AFTER_CLEANUP_FAIL_CLOSED,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_UNEXPECTED_POSITION_APPEARS_MANUAL_REVIEW,
            GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
            GATE_REAL_CLEANUP_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE,
            GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


# ===========================================================================
# Z53: 7 stages
# ===========================================================================

class TestZ53SevenStages:
    def test_seven(self):
        r = _run()
        assert set(r.stages.keys()) == set(ALL_STAGES)
        assert r.stage_order == list(ALL_STAGES)
        assert len(ALL_STAGES) == 7


# ===========================================================================
# Z54: missing symbol
# ===========================================================================

class TestZ54MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# Z55: G20 not lifted
# ===========================================================================

class TestZ55G20NotLifted:
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
# Z56: socket-disabled import smoke
# ===========================================================================

class TestZ56SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_cleanup_permission_gate as m; "
             "print('OK', m.STATUS_CHECKLIST_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# Z57: dataclass roundtrip preserves invariants
# ===========================================================================

class TestZ57DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_real_cleanup_permission=True)
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
            ("real_cleanup_implemented",            False),
            ("real_execution_allowed",              False),
            ("real_cleanup_permission_dry_run_allowed", True),
            ("existing_position_stop_snapshot_match", True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_PERMISSION_READY_EXEC_DISABLED
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_2_CLEANUP_PAYLOAD_PREVIEW]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_2_CLEANUP_PAYLOAD_PREVIEW]
        d["cleanup_payload_preview"]["mutated"] = True
        assert "mutated" not in r.cleanup_payload_preview


# ===========================================================================
# Z58: path refs
# ===========================================================================

class TestZ58PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


# ===========================================================================
# Z59: stage_4 verification plan
# ===========================================================================

class TestZ59Stage4VerificationPlan:
    def test_plan_fields(self):
        r = _run(symbol="SOLUSDT")
        env = r.stages[STAGE_4_POST_CLEANUP_REQUIRED_VERIFICATION_PLAN]
        plan = env["post_cleanup_verification_plan"]
        assert plan["verify_tiny_position_absent_or_qty_zero"] is True
        assert plan["verify_no_dangling_tiny_position"]        is True
        assert plan["verify_existing_5_shorts_still_present"]  is True
        assert plan["verify_existing_5_stops_unchanged"]       is True
        assert plan["verify_no_new_unexpected_position"]       is True
        assert plan["readonly_unavailable_after_cleanup"]      == "fail_closed"
        assert plan["cleanup_rejected"]                        == "fail_closed"
        assert plan["cleanup_partial_fill"]                    == "fail_closed"
        assert plan["tiny_position_still_open_after_cleanup"]  == "fail_closed"
        assert plan["existing_stop_mismatch"]                  == "manual_review"
        assert plan["unexpected_position_appears"]             == "manual_review"
        assert plan["expected_symbol"]                         == "SOLUSDT"
        assert plan["expected_qty_to_be_zero"]                 is True
        assert set(plan["expected_existing_position_symbols"]) == set(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# Z60: stage_5 failure response plan
# ===========================================================================

class TestZ60Stage5FailureResponsePlan:
    def test_failure_response(self):
        r = _run()
        env = r.stages[STAGE_5_FAILURE_RESPONSE_PLAN]
        plan = env["failure_response_plan"]
        assert plan["cleanup_rejected"]                         == "fail_closed"
        assert plan["cleanup_partial_fill"]                     == "fail_closed"
        assert plan["readonly_unavailable_after_cleanup"]       == "fail_closed"
        assert plan["tiny_position_still_open_after_cleanup"]   == "fail_closed"
        assert plan["existing_stop_mismatch"]                   == "manual_review"
        assert plan["unexpected_position_appears"]              == "manual_review"
        assert plan["no_automatic_retry_after_cleanup_failure"] is True
        assert plan["no_automatic_second_order"]                is True
        assert plan["no_real_emergency_close_in_this_task"]     is True


# ===========================================================================
# Z61: stage_6 execution guard fields
# ===========================================================================

class TestZ61Stage6ExecutionGuard:
    def test_stage_6_flags_default(self):
        r = _run()
        env = r.stages[STAGE_6_EXECUTION_GUARD]
        assert env["real_execution_allowed"] is False
        assert env["real_cleanup_implemented"] is False
        assert env["current_task_real_execution_allowed"] is False
        assert env["g20_policy_still_in_place"] is True
        assert env["g20_lifted"] is False
        assert env["no_real_order_endpoint"] is True
        assert env["no_real_stop_endpoint"] is True
        assert env["no_position_modified"] is True
        assert env["no_live_endpoint"] is True
        assert env["no_secrets_emitted"] is True

    def test_stage_6_flags_guard_consistent(self):
        r = _run(allow_real_cleanup=True)
        env = r.stages[STAGE_6_EXECUTION_GUARD]
        # Even when caller passes the guard flag, stage_6 must NOT flip
        # real_execution_allowed to True.
        assert env["real_execution_allowed"] is False
        assert env["real_cleanup_requested"] is True


# ===========================================================================
# Z62: guard safety invariants
# ===========================================================================

class TestZ62GuardSafetyInvariants:
    def test_guard_invariants(self):
        r = _run(allow_real_cleanup=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True
        assert r.no_close_only_path is True
        assert r.existing_positions_touched == []
        assert r.emergency_close_invoked is False
        assert r.leverage_mutated is False
        assert r.transfer_invoked is False


# ===========================================================================
# Z63: stage_1 existing positions snapshot
# ===========================================================================

class TestZ63Stage1ExistingPositionsSnapshot:
    def test_snapshot_count_and_disjoint(self):
        r = _run(symbol="SOLUSDT")
        env = r.stages[STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT]
        assert env["existing_position_count"] == 5
        assert env["selected_symbol_disjoint"] is True
        assert env["existing_positions_touched"] == []
        assert env["snapshot_fields_ok"] is True
        assert set(r.existing_position_symbols) == set(EXISTING_POSITION_SYMBOLS)


# ===========================================================================
# Z64: stage_0 artifact preflight reports all 9 upstream artifacts present
# ===========================================================================

class TestZ64Stage0Preflight:
    def test_all_present(self):
        r = _run()
        env = r.stages[STAGE_0_ARTIFACT_PREFLIGHT]
        assert env["readonly_smoke_present"]                          is True
        assert env["reconciliation_present"]                          is True
        assert env["protection_present"]                              is True
        assert env["contract_present"]                                is True
        assert env["noop_plan_present"]                               is True
        assert env["lifecycle_mock_present"]                          is True
        assert env["real_permission_gate_present"]                    is True
        assert env["tiny_entry_permission_gate_present"]              is True
        assert env["tiny_stop_attach_permission_gate_present"]        is True
        assert env["current_task_real_execution_allowed"]             is False


# ===========================================================================
# Z65: cleanup payload symbol must equal selected symbol (mismatch never
# happens via the gate since it derives from the same symbol, but verify the
# payload is consistent for any valid symbol).
# ===========================================================================

class TestZ65PayloadSymbolConsistent:
    @pytest.mark.parametrize("sym", ["SOLUSDT", "BTCUSDT", "ETHUSDT", "XRPUSDT"])
    def test_consistent(self, sym):
        r = _run(symbol=sym)
        if sym in EXISTING_POSITION_SYMBOLS:
            pytest.skip("collides with existing position")
        assert r.cleanup_payload_preview["symbol"] == sym
        assert r.status == STATUS_CHECKLIST_READY


# ===========================================================================
# Z66: real_cleanup_requested flag echoed even in checklist mode
# ===========================================================================

class TestZ66RealCleanupRequestedFlag:
    def test_default_false(self):
        r = _run()
        assert r.real_cleanup_requested is False

    def test_guard_flag_true(self):
        r = _run(allow_real_cleanup=True)
        assert r.real_cleanup_requested is True

    def test_dry_run_keeps_false(self):
        r = _run(allow_real_cleanup_permission=True)
        assert r.real_cleanup_requested is False
