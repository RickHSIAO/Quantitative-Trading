"""
tests/demo_trading/test_demo_tiny_entry_permission_gate.py
TASK-014X: Tiny Isolated Demo Entry Permission Gate / Dry-run Only
tests (X1 - X49+).

Covers checklist / real_entry_permission_dry_run / real_tiny_entry_guard
/ fail_closed paths; all 7 stages; 53 gates; instrument min/step rounding;
payload-only entry preview; source-scan safety (no urlopen / no forbidden
imports / no secrets); report artifacts; and the invariant that TASK-014L
sender G20 (protected_entry_policy_missing) still blocks --execute-new-entry
and is NOT lifted here.
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

from src.demo_tiny_entry_permission_gate import (
    ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_MIN_NOTIONAL_FALLBACK,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyEntryPermissionGate,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_NOOP_RECOMMENDED_PATH,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_PROOF_STRENGTH,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_TOKEN_NOT_VALIDATED_THIS_TASK,
    GATE_ENTRY_TOKEN_PATTERN_REQUIRED,
    GATE_ESTIMATED_NOTIONAL_OVER_CAP,
    GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_INSTRUMENT_CATEGORY_NOT_LINEAR,
    GATE_INSTRUMENT_RULE_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_MIN_NOTIONAL_MISSING,
    GATE_MIN_ORDER_QTY_MISSING,
    GATE_NAKED_TINY_WINDOW_MUST_BE_TIME_BOXED,
    GATE_NO_AUTO_STOP_ATTACH_AFTER_ENTRY,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SECRETS_EMITTED,
    GATE_NOOP_PLAN_MISSING,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POSITION_MISSING_AFTER_ENTRY_FAIL_CLOSED,
    GATE_POST_ENTRY_READONLY_VERIFICATION_REQUIRED,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_QTY_MISMATCH_AFTER_ENTRY_FAIL_CLOSED,
    GATE_QTY_STEP_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_AFTER_ENTRY_FAIL_CLOSED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_REAL_TINY_ENTRY_NOT_IMPL,
    GATE_RECONCILIATION_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK,
    GATE_STRATEGY_FULL_SIZE_QTY_REUSED,
    GATE_TICK_SIZE_MISSING,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_ENTRY_PERMISSION_DRY_RUN,
    MODE_REAL_TINY_ENTRY_GUARD,
    ORDER_CREATE_PATH_REF,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT,
    STAGE_2_INSTRUMENT_MIN_STEP_CHECK,
    STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW,
    STAGE_4_ENTRY_TOKEN_CHECKLIST,
    STAGE_5_POST_ENTRY_REQUIRED_VERIFICATION_PLAN,
    STAGE_6_EXECUTION_GUARD,
    STATUS_CHECKLIST_READY,
    STATUS_FAIL_CLOSED,
    STATUS_PERMISSION_READY_EXEC_DISABLED,
    STATUS_REAL_TINY_ENTRY_NOT_IMPL,
    STOP_ATTACH_TOKEN_PATTERN,
    STRATEGY_FULL_SIZE_QTY_REF,
    TINY_NOTIONAL_CAP_USDT,
    TRADING_STOP_PATH_REF,
    TinyEntryPermissionGateResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_entry_permission_gate.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_entry_permission_gate.py"
_TEST_NOW    = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _valid_instrument_rules() -> list[dict]:
    return [
        {
            "symbol":             "SOLUSDT",
            "category":           "linear",
            "min_order_qty":      0.1,
            "qty_step":           0.1,
            "tick_size":          0.01,
            "min_notional_value": 5.0,
        },
    ]


def _valid_readonly() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T10:00:00Z",
        "endpoint_family":        EXPECTED_ENDPOINT_FAMILY,
        "account_mode":           EXPECTED_ACCOUNT_MODE,
        "proof_strength":         EXPECTED_PROOF_STRENGTH,
        "demo_runtime_verified":  True,
        "equity_usd":             500.0,
        "available_balance_usd":  400.0,
        "instrument_rules":       _valid_instrument_rules(),
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


def _gate() -> DemoTinyEntryPermissionGate:
    return DemoTinyEntryPermissionGate()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_real_entry_permission=False,
    allow_real_tiny_entry=False,
    _now=_TEST_NOW,
) -> TinyEntryPermissionGateResult:
    return _gate().run_checklist(
        readonly_smoke=_valid_readonly()       if readonly             is _UNSET else readonly,
        reconciliation=_valid_reconciliation() if recon                is _UNSET else recon,
        protection=_valid_protection()         if protection           is _UNSET else protection,
        contract=_valid_contract()             if contract             is _UNSET else contract,
        noop_plan=_valid_noop_plan()           if noop_plan            is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()      if lifecycle            is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate() if real_permission_gate is _UNSET else real_permission_gate,
        symbol=symbol,
        allow_real_entry_permission=allow_real_entry_permission,
        allow_real_tiny_entry=allow_real_tiny_entry,
        _now=_now,
    )


# ===========================================================================
# X1: valid checklist => TINY_ENTRY_PERMISSION_CHECKLIST_READY
# ===========================================================================

class TestX1ChecklistReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_CHECKLIST_READY
        assert r.mode == MODE_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_tiny_entry_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == (
            "TASK-014Y_tiny_isolated_demo_stop_attach_permission_gate"
        )


# ===========================================================================
# X2: --allow-real-entry-permission => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestX2RealEntryPermissionDryRun:
    def test_promotes_status(self):
        r = _run(allow_real_entry_permission=True)
        assert r.status == STATUS_PERMISSION_READY_EXEC_DISABLED
        assert r.mode == MODE_REAL_ENTRY_PERMISSION_DRY_RUN
        assert r.real_entry_permission_dry_run_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_tiny_entry_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# X3: --allow-real-tiny-entry => REAL_TINY_ENTRY_NOT_IMPLEMENTED
# ===========================================================================

class TestX3RealTinyEntryGuard:
    def test_guard_returns_not_impl(self):
        r = _run(allow_real_tiny_entry=True)
        assert r.status == STATUS_REAL_TINY_ENTRY_NOT_IMPL
        assert r.mode == MODE_REAL_TINY_ENTRY_GUARD
        assert r.real_execution_allowed is False
        assert r.real_tiny_entry_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.real_tiny_entry_requested is True
        assert GATE_REAL_TINY_ENTRY_NOT_IMPL in r.blocked_gates


# ===========================================================================
# X4 - X10: missing upstream artifacts => FAIL_CLOSED
# ===========================================================================

class TestX4MissingReadonly:
    def test_none(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestX5MissingReconciliation:
    def test_none(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestX6MissingProtection:
    def test_none(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestX7MissingContract:
    def test_none(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestX8MissingNoopPlan:
    def test_none(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestX9MissingLifecycle:
    def test_none(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestX10MissingRealPermissionGate:
    def test_none(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


# ===========================================================================
# X11: selected_symbol collides with an existing position => FAIL_CLOSED
# ===========================================================================

class TestX11SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_collision_blocks(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# X12 - X16: proof envelope mismatches => FAIL_CLOSED
# ===========================================================================

class TestX12EndpointFamilyMismatch:
    def test_mainnet(self):
        ro = _valid_readonly(); ro["endpoint_family"] = "bybit_mainnet"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestX13AccountModeMismatch:
    def test_live(self):
        ro = _valid_readonly(); ro["account_mode"] = "live"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestX14ProofStrengthMismatch:
    def test_weak(self):
        ro = _valid_readonly(); ro["proof_strength"] = "WEAK"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestX15PositionDetailsSourceMismatch:
    def test_synthetic(self):
        rec = _valid_reconciliation()
        rec["mode"] = "synthetic"
        rec["position_details_source"] = "synthetic"
        r = _run(recon=rec)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


class TestX16LifecycleNotSuccess:
    def test_fail_closed(self):
        lc = _valid_lifecycle()
        lc["status"] = "MOCK_TINY_LIFECYCLE_FAIL_CLOSED"
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_NOT_SUCCESS in r.blocked_gates


# ===========================================================================
# X17: real permission gate status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestX17RealPermissionUnacceptable:
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
# X18 - X21: instrument-rule fields missing => FAIL_CLOSED
# ===========================================================================

class TestX18InstrumentRuleMissing:
    def test_rules_absent(self):
        ro = _valid_readonly(); ro.pop("instrument_rules", None)
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_INSTRUMENT_RULE_MISSING in r.blocked_gates

    def test_other_symbol_only(self):
        ro = _valid_readonly()
        ro["instrument_rules"] = [{"symbol": "BTCUSDT", "category": "linear",
                                   "min_order_qty": 0.001, "qty_step": 0.001,
                                   "tick_size": 0.5, "min_notional_value": 5.0}]
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_INSTRUMENT_RULE_MISSING in r.blocked_gates


class TestX19MissingMinOrderQty:
    def test_missing(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0].pop("min_order_qty")
        ro["instrument_rules"] = rules
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_MIN_ORDER_QTY_MISSING in r.blocked_gates


class TestX20MissingQtyStep:
    def test_missing(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0].pop("qty_step")
        ro["instrument_rules"] = rules
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_QTY_STEP_MISSING in r.blocked_gates


class TestX21MissingTickSize:
    def test_missing(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0].pop("tick_size")
        ro["instrument_rules"] = rules
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TICK_SIZE_MISSING in r.blocked_gates


# ===========================================================================
# X22: qty rounding (below min => rounded up; aligned to step)
# ===========================================================================

class TestX22QtyRoundingBelowMin:
    def test_round_up_to_min(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0]["min_order_qty"] = 0.5
        rules[0]["qty_step"]      = 0.5
        ro["instrument_rules"] = rules
        # entry ref 64.87; 0.5 SOL => notional 32.4 USDT, over cap
        # Make tiny entry survive cap by using a low-price symbol setup
        # Instead, use a tiny lifecycle qty under min to test the round-up.
        lc = _valid_lifecycle(); lc["tiny_qty"] = 0.05
        prot = _valid_protection(); prot["entry_reference_price"] = 1.0
        prot["stop_price"] = 0.5
        r = _run(readonly=ro, lifecycle=lc, protection=prot)
        # candidate=max(0.05, 0.5)=0.5 → notional 0.5 < min_notional 5 → bump
        # needed=5/1.0=5 SOL → aligned to step 0.5 → 5.0; notional 5.0 within cap.
        assert r.rounded_tiny_qty == pytest.approx(5.0, rel=1e-9)
        assert r.estimated_tiny_notional == pytest.approx(5.0, rel=1e-9)
        assert r.within_tiny_notional_cap is True


# ===========================================================================
# X23: aligned with qty_step
# ===========================================================================

class TestX23QtyAlignedWithStep:
    def test_aligned(self):
        r = _run()
        # default rules: min_order_qty=0.1, qty_step=0.1 => rounded=0.1
        step = r.instrument_rule_summary["qty_step"]
        n = round(r.rounded_tiny_qty / step)
        assert abs(n * step - r.rounded_tiny_qty) < 1e-9


# ===========================================================================
# X24: notional bumped up to min_notional
# ===========================================================================

class TestX24NotionalBumpedToMin:
    def test_bumped(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0]["min_notional_value"] = 8.0
        ro["instrument_rules"] = rules
        # default tiny_qty=0.1, entry=64.87 → notional=6.487 < 8 →
        # needed qty = 8/64.87 ≈ 0.1233; round up to step 0.1 → 0.2
        # final notional = 0.2 * 64.87 = 12.974 → OVER CAP 10 → FAIL CLOSED
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ESTIMATED_NOTIONAL_OVER_CAP in r.blocked_gates

    def test_bumped_under_cap(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        # min_notional=7; qty_step=0.1; price=64.87
        # needed = 7/64.87 ≈ 0.1079 → round up → 0.2 → notional 12.97 over cap
        # Use smaller qty_step 0.01 instead so we can stay just above 7 below 10
        rules[0]["min_notional_value"] = 7.0
        rules[0]["qty_step"]           = 0.01
        rules[0]["min_order_qty"]      = 0.01
        ro["instrument_rules"] = rules
        lc = _valid_lifecycle(); lc["tiny_qty"] = 0.01
        # candidate=0.01 → notional 0.65 < 7 → needed 7/64.87≈0.108 → round up to 0.11 → notional ≈ 7.135 within cap.
        r = _run(readonly=ro, lifecycle=lc)
        assert r.status == STATUS_CHECKLIST_READY
        assert r.rounded_tiny_qty == pytest.approx(0.11, abs=1e-9)
        assert r.estimated_tiny_notional == pytest.approx(0.11 * 64.87, rel=1e-9)
        assert r.within_tiny_notional_cap is True


# ===========================================================================
# X25: notional above 10 USDT cap => fail closed
# ===========================================================================

class TestX25NotionalOverCap:
    def test_over_cap(self):
        ro = _valid_readonly()
        lc = _valid_lifecycle(); lc["tiny_qty"] = 1.0  # 1*64.87 = 64.87 USDT
        r = _run(readonly=ro, lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ESTIMATED_NOTIONAL_OVER_CAP in r.blocked_gates


# ===========================================================================
# X26: strategy-sized qty 12.2 SOL is rejected
# ===========================================================================

class TestX26StrategyQtyReuseRejected:
    def test_12_2_rejected(self):
        lc = _valid_lifecycle()
        lc["tiny_qty"] = 12.2
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STRATEGY_FULL_SIZE_QTY_REUSED in r.blocked_gates


# ===========================================================================
# X27 - X30: entry payload preview fields
# ===========================================================================

class TestX27PayloadSideBuy:
    def test_side(self):
        r = _run()
        assert r.entry_payload_preview["side"] == "Buy"


class TestX28PayloadReduceOnlyFalse:
    def test_reduce_only(self):
        r = _run()
        assert r.entry_payload_preview["reduceOnly"] is False


class TestX29PayloadPositionIdxZero:
    def test_position_idx(self):
        r = _run()
        assert r.entry_payload_preview["positionIdx"] == 0


class TestX30PayloadPreviewOnly:
    def test_preview_only(self):
        r = _run()
        assert r.entry_payload_preview["preview_only"] is True
        assert r.entry_payload_preview["endpoint_called"] is False
        assert r.entry_payload_preview["orderLinkId"].startswith("DRYRUN-TINY-ENTRY")


# ===========================================================================
# X31 - X33: safety invariants
# ===========================================================================

class TestX31OrderEndpointFalse:
    def test_default(self):
        r = _run()
        assert r.order_endpoint_called is False

    def test_dry_run(self):
        r = _run(allow_real_entry_permission=True)
        assert r.order_endpoint_called is False

    def test_guard(self):
        r = _run(allow_real_tiny_entry=True)
        assert r.order_endpoint_called is False


class TestX32StopEndpointFalse:
    def test_default(self):
        r = _run()
        assert r.stop_endpoint_called is False

    def test_dry_run(self):
        r = _run(allow_real_entry_permission=True)
        assert r.stop_endpoint_called is False

    def test_guard(self):
        r = _run(allow_real_tiny_entry=True)
        assert r.stop_endpoint_called is False


class TestX33NoPositionModified:
    def test_default(self):
        r = _run()
        assert r.no_position_modified is True
        assert r.existing_positions_touched == []

    def test_dry_run(self):
        r = _run(allow_real_entry_permission=True)
        assert r.no_position_modified is True

    def test_guard(self):
        r = _run(allow_real_tiny_entry=True)
        assert r.no_position_modified is True


# ===========================================================================
# X34: entry token pattern present
# ===========================================================================

class TestX34EntryTokenPattern:
    def test_pattern(self):
        r = _run()
        assert r.entry_token_pattern == ENTRY_TOKEN_PATTERN
        env = r.stages[STAGE_4_ENTRY_TOKEN_CHECKLIST]
        assert env["entry_token_pattern"] == ENTRY_TOKEN_PATTERN


# ===========================================================================
# X35: stop attach token not accepted in this task
# ===========================================================================

class TestX35StopAttachTokenNotAccepted:
    def test_documented(self):
        r = _run()
        env = r.stages[STAGE_4_ENTRY_TOKEN_CHECKLIST]
        assert env["stop_attach_token_not_accepted_in_this_task"] is True
        assert env["stop_attach_token_pattern"] == STOP_ATTACH_TOKEN_PATTERN
        assert GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK in r.blocked_gates


# ===========================================================================
# X36: cleanup token not accepted in this task
# ===========================================================================

class TestX36CleanupTokenNotAccepted:
    def test_documented(self):
        r = _run()
        env = r.stages[STAGE_4_ENTRY_TOKEN_CHECKLIST]
        assert env["cleanup_token_not_accepted_in_this_task"] is True
        assert env["cleanup_token_pattern"] == CLEANUP_TOKEN_PATTERN
        assert GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK in r.blocked_gates


# ===========================================================================
# X37: allow-real-tiny-entry does NOT run execution phase
# ===========================================================================

class TestX37GuardDoesNotExecute:
    def test_guard_safety(self):
        r = _run(allow_real_tiny_entry=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_orders_sent is True
        assert r.real_execution_allowed is False
        assert r.real_tiny_entry_implemented is False


# ===========================================================================
# X38: no execute flag exists (signature scan)
# ===========================================================================

class TestX38NoExecuteFlagInModule:
    def test_no_execute_flag(self):
        code = _read_code_only(_MODULE_PATH)
        assert "execute_real_tiny_entry" not in code
        assert "--execute-real-tiny-entry" not in _MODULE_PATH.read_text(encoding="utf-8")

    def test_no_execute_flag_in_cli(self):
        # CLI must not advertise an --execute-* tiny-entry flag.
        text = _SCRIPT_PATH.read_text(encoding="utf-8")
        assert "--execute-real-tiny-entry" not in text
        assert "--execute-tiny-entry"     not in text


# ===========================================================================
# X39: report artifacts written (checklist)
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
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        (rp_d   / "latest_tiny_position_real_permission_gate.json").write_text(json.dumps(_valid_real_permission_gate()), encoding="utf-8")
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, out_d


class TestX39ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_entry_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_entry_permission=False,
                allow_real_tiny_entry=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_entry_permission_gate.json" in files
            assert "latest_tiny_entry_permission_gate.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_entry_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_CHECKLIST_READY
            assert data["real_execution_allowed"] is False
            assert data["real_tiny_entry_implemented"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True


# ===========================================================================
# X40: no secrets in report
# ===========================================================================

class TestX40NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_entry_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_entry_permission=False,
                allow_real_tiny_entry=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_entry_permission_gate.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_entry_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False


# ===========================================================================
# X41: no import main.py / src/risk.py / BybitExecutor
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


class TestX41NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            # CLI is allowed to import src.demo_tiny_entry_permission_gate;
            # nothing else from the forbidden list.
            if bad == "src.demo_tiny_position_real_permission_gate":
                # CLI does not depend on that module at all (only loads its JSON).
                pass
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# X42: no close-only sender reuse
# ===========================================================================

class TestX42NoSenderReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"     not in code
            assert "demo_close_only_sender"  not in code


# ===========================================================================
# X43: no emergency close sender called
# ===========================================================================

class TestX43NoEmergencyClose:
    def test_no_emergency_close(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoEmergencyCloseSender" not in code
            assert "demo_emergency_close_sender" not in code


# ===========================================================================
# X44: no new-entry sender real execution called
# ===========================================================================

class TestX44NoNewEntrySender:
    def test_no_new_entry_sender(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoNewEntrySender"    not in code
            assert "demo_new_entry_sender" not in code


# ===========================================================================
# X45: no trading-stop real adapter called
# ===========================================================================

class TestX45NoTradingStopRealAdapter:
    def test_no_trading_stop(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTradingStopContractProbe" not in code
            assert "demo_trading_stop_contract_probe" not in code


# ===========================================================================
# X46: source scan confirms no urllib/request/httpx/socket
# ===========================================================================

class TestX46NoNetworkTokens:
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
# X47: CLI subprocess valid run exits 0
# ===========================================================================

class TestX47CLISubprocessOk(_ReportSetupMixin):
    def test_subprocess_exits_0(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, out_d = self._setup(Path(td))
            # Smoke-test via run_execute (subprocess would still hit no
            # network).  Provide isolated dirs to avoid touching live
            # outputs/.
            from scripts.preview_demo_tiny_entry_permission_gate import run_execute
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_entry_permission=False,
                allow_real_tiny_entry=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0


# ===========================================================================
# X48: CLI subprocess missing artifact exits 1
# ===========================================================================

class TestX48CLISubprocessMissingExits1:
    def test_missing_artifact(self):
        from scripts.preview_demo_tiny_entry_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            base   = Path(td)
            ro_d   = base / "readonly";    ro_d.mkdir()
            rec_d  = base / "recon";       rec_d.mkdir()
            prot_d = base / "protection";  prot_d.mkdir()
            con_d  = base / "contract";    con_d.mkdir()
            noop_d = base / "noop";        noop_d.mkdir()
            lc_d   = base / "lifecycle";   lc_d.mkdir()
            rp_d   = base / "real_perm";   rp_d.mkdir()
            out_d  = base / "out"
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_entry_permission=False,
                allow_real_tiny_entry=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# X49: next task is TASK-014Y
# ===========================================================================

class TestX49NextTaskIs014Y:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == (
            "TASK-014Y_tiny_isolated_demo_stop_attach_permission_gate"
        )


# ===========================================================================
# Auxiliary: gate count, always-on gates, sym missing, stage order,
# socket-disabled import, dataclass roundtrip, G20 invariants, etc.
# ===========================================================================

class TestX50GateCount:
    def test_at_least_53(self):
        import src.demo_tiny_entry_permission_gate as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 53, (
            f"Expected >= 53 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


class TestX51AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            GATE_ENTRY_TOKEN_PATTERN_REQUIRED,
            GATE_ENTRY_TOKEN_NOT_VALIDATED_THIS_TASK,
            GATE_STOP_ATTACH_TOKEN_NOT_ACCEPTED_THIS_TASK,
            GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK,
            GATE_POST_ENTRY_READONLY_VERIFICATION_REQUIRED,
            GATE_NO_AUTO_STOP_ATTACH_AFTER_ENTRY,
            GATE_READONLY_UNAVAILABLE_AFTER_ENTRY_FAIL_CLOSED,
            GATE_POSITION_MISSING_AFTER_ENTRY_FAIL_CLOSED,
            GATE_QTY_MISMATCH_AFTER_ENTRY_FAIL_CLOSED,
            GATE_EXISTING_STOP_MISMATCH_MANUAL_REVIEW,
            GATE_NAKED_TINY_WINDOW_MUST_BE_TIME_BOXED,
            GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
            GATE_REAL_TINY_ENTRY_NOT_IMPL,
            GATE_NO_REAL_ORDER_ENDPOINT,
            GATE_NO_REAL_STOP_ENDPOINT,
            GATE_NO_POSITION_MODIFIED,
            GATE_G20_NOT_LIFTED,
            GATE_G20_POLICY_STILL_IN_PLACE,
            GATE_NO_LIVE_ENDPOINT,
            GATE_NO_SECRETS_EMITTED,
        ):
            assert g in unique, f"always-on gate missing: {g}"


class TestX52SevenStages:
    def test_seven(self):
        r = _run()
        assert set(r.stages.keys()) == set(ALL_STAGES)
        assert r.stage_order == list(ALL_STAGES)
        assert len(ALL_STAGES) == 7


class TestX53MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


class TestX54G20NotLifted:
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


class TestX55SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_entry_permission_gate as m; "
             "print('OK', m.STATUS_CHECKLIST_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


class TestX56DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_real_entry_permission=True)
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
            ("real_tiny_entry_implemented",         False),
            ("real_execution_allowed",              False),
            ("real_entry_permission_dry_run_allowed", True),
            ("existing_position_stop_snapshot_match", True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_PERMISSION_READY_EXEC_DISABLED
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_3_TINY_ENTRY_PAYLOAD_PREVIEW]


class TestX57PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


class TestX58Stage5VerificationPlan:
    def test_plan_fields(self):
        r = _run()
        env = r.stages[STAGE_5_POST_ENTRY_REQUIRED_VERIFICATION_PLAN]
        plan = env["post_entry_verification_plan"]
        assert plan["verify_position_exists"] is True
        assert plan["verify_side_equals_long"] is True
        assert plan["verify_qty_equals_rounded_tiny_qty"] is True
        assert plan["verify_entry_price_positive"] is True
        assert plan["naked_tiny_window_time_boxed"] is True
        assert plan["readonly_unavailable_after_entry"] == "fail_closed"
        assert plan["position_missing_after_entry"]     == "fail_closed"
        assert plan["qty_mismatch_after_entry"]         == "fail_closed"
        assert plan["existing_stop_mismatch"]           == "manual_review"


class TestX59Stage6ExecutionGuard:
    def test_stage_6_flags_default(self):
        r = _run()
        env = r.stages[STAGE_6_EXECUTION_GUARD]
        assert env["real_execution_allowed"] is False
        assert env["real_tiny_entry_implemented"] is False
        assert env["current_task_real_execution_allowed"] is False
        assert env["g20_policy_still_in_place"] is True
        assert env["g20_lifted"] is False
        assert env["no_real_order_endpoint"] is True
        assert env["no_real_stop_endpoint"] is True
        assert env["no_position_modified"] is True
        assert env["no_live_endpoint"] is True
        assert env["no_secrets_emitted"] is True

    def test_stage_6_flags_guard_consistent(self):
        r = _run(allow_real_tiny_entry=True)
        env = r.stages[STAGE_6_EXECUTION_GUARD]
        # Even when caller passes the guard flag, stage_6 must NOT flip
        # real_execution_allowed to True.
        assert env["real_execution_allowed"] is False
        assert env["real_tiny_entry_requested"] is True


class TestX60InstrumentCategoryNotLinear:
    def test_spot_rejected(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0]["category"] = "spot"
        ro["instrument_rules"] = rules
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_INSTRUMENT_CATEGORY_NOT_LINEAR in r.blocked_gates


class TestX61MinNotionalMissing:
    def test_missing(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0].pop("min_notional_value")
        ro["instrument_rules"] = rules
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_MIN_NOTIONAL_MISSING in r.blocked_gates


class TestX62InstrumentRulesAsDict:
    def test_dict_form_resolves(self):
        ro = _valid_readonly()
        ro["instrument_rules"] = {
            "SOLUSDT": _valid_instrument_rules()[0],
        }
        r = _run(readonly=ro)
        assert r.status == STATUS_CHECKLIST_READY
        assert r.instrument_rule_summary["rule_present"] is True


class TestX63GuardSafetyInvariants:
    def test_guard_invariants(self):
        r = _run(allow_real_tiny_entry=True)
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True
        assert r.existing_positions_touched == []
