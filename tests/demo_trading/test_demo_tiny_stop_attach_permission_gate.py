"""
tests/demo_trading/test_demo_tiny_stop_attach_permission_gate.py
TASK-014Y: Tiny Isolated Demo Stop Attach Permission Gate / Dry-run Only
tests (Y1 - Y60+).

Covers checklist / real_stop_permission_dry_run / real_stop_attach_guard
/ fail_closed paths; all 7 stages; 49 gates; stop-payload preview
(tpslMode=Full, slTriggerBy=MarkPrice, positionIdx=0); tick alignment;
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

from src.demo_tiny_stop_attach_permission_gate import (
    ACCEPTABLE_REAL_PERMISSION_GATE_STATUSES,
    ACCEPTABLE_TINY_ENTRY_PERMISSION_GATE_STATUSES,
    ALL_STAGES,
    BASE_URL_DEMO_REF,
    CLEANUP_TOKEN_PATTERN,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyStopAttachPermissionGate,
    ENTRY_TOKEN_PATTERN,
    EXISTING_POSITION_SYMBOLS,
    EXPECTED_ACCOUNT_MODE,
    EXPECTED_ENDPOINT_FAMILY,
    EXPECTED_INSTRUMENT_CATEGORY,
    EXPECTED_LIFECYCLE_STATUS,
    EXPECTED_NOOP_RECOMMENDED_PATH,
    EXPECTED_POSITION_DETAILS_SOURCE,
    EXPECTED_POSITION_IDX,
    EXPECTED_PROOF_STRENGTH,
    EXPECTED_SL_TRIGGER_BY,
    EXPECTED_TPSL_MODE,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK,
    GATE_CONTRACT_MISSING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK,
    GATE_G20_NOT_LIFTED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_INSTRUMENT_CATEGORY_NOT_LINEAR,
    GATE_INSTRUMENT_RULE_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_LIFECYCLE_MOCK_NOT_SUCCESS,
    GATE_NO_AUTO_CLEANUP_AFTER_STOP_ATTACH,
    GATE_NO_LIVE_ENDPOINT,
    GATE_NO_POSITION_MODIFIED,
    GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
    GATE_NO_REAL_ORDER_ENDPOINT,
    GATE_NO_REAL_STOP_ENDPOINT,
    GATE_NO_SECRETS_EMITTED,
    GATE_NOOP_PLAN_MISSING,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_POSITION_MISSING_AFTER_STOP_FAIL_CLOSED,
    GATE_POST_STOP_ATTACH_READONLY_VERIFICATION_REQUIRED,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_UNAVAILABLE_AFTER_STOP_FAIL_CLOSED,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_REAL_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_REAL_STOP_ATTACH_NOT_IMPL,
    GATE_RECONCILIATION_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_ATTACH_TOKEN_NOT_VALIDATED_THIS_TASK,
    GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED,
    GATE_STOP_PRICE_MISMATCH_AFTER_ATTACH_FAIL_CLOSED,
    GATE_STOP_PRICE_MISSING,
    GATE_STOP_PRICE_NOT_ALIGNED_WITH_TICK,
    GATE_STOP_PRICE_NOT_POSITIVE,
    GATE_STOP_RESPONSE_NOT_OK_FAIL_CLOSED,
    GATE_TICK_SIZE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_STATUS_UNACCEPTABLE,
    GATE_TPSL_MODE_MISMATCH_AFTER_ATTACH_MANUAL_REVIEW,
    MODE_CHECKLIST,
    MODE_FAIL_CLOSED,
    MODE_REAL_STOP_ATTACH_GUARD,
    MODE_REAL_STOP_PERMISSION_DRY_RUN,
    ORDER_CREATE_PATH_REF,
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_EXISTING_POSITION_PRE_SNAPSHOT,
    STAGE_2_STOP_PAYLOAD_PREVIEW,
    STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST,
    STAGE_4_POST_STOP_ATTACH_REQUIRED_VERIFICATION_PLAN,
    STAGE_5_FAILURE_RESPONSE_PLAN,
    STAGE_6_EXECUTION_GUARD,
    STATUS_CHECKLIST_READY,
    STATUS_FAIL_CLOSED,
    STATUS_PERMISSION_READY_EXEC_DISABLED,
    STATUS_REAL_STOP_ATTACH_NOT_IMPL,
    STOP_ATTACH_TOKEN_PATTERN,
    TRADING_STOP_PATH_REF,
    TinyStopAttachPermissionGateResult,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_stop_attach_permission_gate.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_stop_attach_permission_gate.py"
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


def _valid_tiny_entry_permission_gate() -> dict:
    return {
        "timestamp_utc":      "2026-06-10T11:59:00Z",
        "mode":               "checklist",
        "selected_symbol":    "SOLUSDT",
        "status":             "TINY_ENTRY_PERMISSION_CHECKLIST_READY",
        "real_execution_allowed":               False,
        "real_tiny_entry_implemented":          False,
        "current_task_real_execution_allowed":  False,
        "real_tiny_entry_requested":            False,
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


def _gate() -> DemoTinyStopAttachPermissionGate:
    return DemoTinyStopAttachPermissionGate()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, lifecycle=_UNSET, real_permission_gate=_UNSET,
    tiny_entry_permission_gate=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL,
    allow_real_stop_permission=False,
    allow_real_tiny_stop_attach=False,
    _now=_TEST_NOW,
) -> TinyStopAttachPermissionGateResult:
    return _gate().run_checklist(
        readonly_smoke=_valid_readonly()       if readonly             is _UNSET else readonly,
        reconciliation=_valid_reconciliation() if recon                is _UNSET else recon,
        protection=_valid_protection()         if protection           is _UNSET else protection,
        contract=_valid_contract()             if contract             is _UNSET else contract,
        noop_plan=_valid_noop_plan()           if noop_plan            is _UNSET else noop_plan,
        lifecycle_mock=_valid_lifecycle()      if lifecycle            is _UNSET else lifecycle,
        real_permission_gate=_valid_real_permission_gate() if real_permission_gate is _UNSET else real_permission_gate,
        tiny_entry_permission_gate=_valid_tiny_entry_permission_gate() if tiny_entry_permission_gate is _UNSET else tiny_entry_permission_gate,
        symbol=symbol,
        allow_real_stop_permission=allow_real_stop_permission,
        allow_real_tiny_stop_attach=allow_real_tiny_stop_attach,
        _now=_now,
    )


# ===========================================================================
# Y1: valid checklist => TINY_STOP_ATTACH_PERMISSION_CHECKLIST_READY
# ===========================================================================

class TestY1ChecklistReady:
    def test_checklist_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_CHECKLIST_READY
        assert r.mode == MODE_CHECKLIST
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == (
            "TASK-014Z_tiny_isolated_demo_cleanup_permission_gate"
        )


# ===========================================================================
# Y2: --allow-real-stop-permission => READY_BUT_EXECUTION_DISABLED
# ===========================================================================

class TestY2RealStopPermissionDryRun:
    def test_promotes_status(self):
        r = _run(allow_real_stop_permission=True)
        assert r.status == STATUS_PERMISSION_READY_EXEC_DISABLED
        assert r.mode == MODE_REAL_STOP_PERMISSION_DRY_RUN
        assert r.real_stop_permission_dry_run_allowed is True
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False
        assert r.current_task_real_execution_allowed is False


# ===========================================================================
# Y3: --allow-real-tiny-stop-attach => REAL_STOP_ATTACH_NOT_IMPLEMENTED
# ===========================================================================

class TestY3RealStopAttachGuard:
    def test_guard_returns_not_impl(self):
        r = _run(allow_real_tiny_stop_attach=True)
        assert r.status == STATUS_REAL_STOP_ATTACH_NOT_IMPL
        assert r.mode == MODE_REAL_STOP_ATTACH_GUARD
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.real_stop_attach_requested is True
        assert GATE_REAL_STOP_ATTACH_NOT_IMPL in r.blocked_gates


# ===========================================================================
# Y4 - Y11: missing upstream artifacts => FAIL_CLOSED  (8 artifacts)
# ===========================================================================

class TestY4MissingReadonly:
    def test_none(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


class TestY5MissingReconciliation:
    def test_none(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


class TestY6MissingProtection:
    def test_none(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


class TestY7MissingContract:
    def test_none(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


class TestY8MissingNoopPlan:
    def test_none(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


class TestY9MissingLifecycle:
    def test_none(self):
        r = _run(lifecycle=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_MISSING in r.blocked_gates


class TestY10MissingRealPermissionGate:
    def test_none(self):
        r = _run(real_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_REAL_PERMISSION_GATE_MISSING in r.blocked_gates


class TestY11MissingTinyEntryPermissionGate:
    def test_none(self):
        r = _run(tiny_entry_permission_gate=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TINY_ENTRY_PERMISSION_GATE_MISSING in r.blocked_gates


# ===========================================================================
# Y12: selected_symbol collides with an existing position => FAIL_CLOSED
# ===========================================================================

class TestY12SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_collision_blocks(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_COLLIDES_EXISTING in r.blocked_gates


# ===========================================================================
# Y13 - Y17: proof envelope mismatches => FAIL_CLOSED
# ===========================================================================

class TestY13EndpointFamilyMismatch:
    def test_mainnet(self):
        ro = _valid_readonly(); ro["endpoint_family"] = "bybit_mainnet"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO in r.blocked_gates


class TestY14AccountModeMismatch:
    def test_live(self):
        ro = _valid_readonly(); ro["account_mode"] = "live"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_ACCOUNT_MODE_NOT_DEMO in r.blocked_gates


class TestY15ProofStrengthMismatch:
    def test_weak(self):
        ro = _valid_readonly(); ro["proof_strength"] = "WEAK"
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROOF_STRENGTH_NOT_STRONG in r.blocked_gates


class TestY16PositionDetailsSourceMismatch:
    def test_synthetic(self):
        rec = _valid_reconciliation()
        rec["mode"] = "synthetic"
        rec["position_details_source"] = "synthetic"
        r = _run(recon=rec)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY in r.blocked_gates


class TestY17LifecycleNotSuccess:
    def test_fail_closed(self):
        lc = _valid_lifecycle()
        lc["status"] = "MOCK_TINY_LIFECYCLE_FAIL_CLOSED"
        r = _run(lifecycle=lc)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_LIFECYCLE_MOCK_NOT_SUCCESS in r.blocked_gates


# ===========================================================================
# Y18: real permission gate status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestY18RealPermissionUnacceptable:
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
# Y19: tiny_entry_permission_gate status unacceptable => FAIL_CLOSED
# ===========================================================================

class TestY19TinyEntryPermissionUnacceptable:
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
# Y20 - Y22: instrument-rule fields missing / category mismatch
# ===========================================================================

class TestY20InstrumentRuleMissing:
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


class TestY21InstrumentCategoryNotLinear:
    def test_spot_rejected(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0]["category"] = "spot"
        ro["instrument_rules"] = rules
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_INSTRUMENT_CATEGORY_NOT_LINEAR in r.blocked_gates


class TestY22TickSizeMissing:
    def test_missing(self):
        ro = _valid_readonly()
        rules = _valid_instrument_rules()
        rules[0].pop("tick_size")
        ro["instrument_rules"] = rules
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TICK_SIZE_MISSING in r.blocked_gates


# ===========================================================================
# Y23 - Y25: stop_price validation
# ===========================================================================

class TestY23StopPriceMissing:
    def test_missing(self):
        prot = _valid_protection(); prot.pop("stop_price")
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PRICE_MISSING in r.blocked_gates


class TestY24StopPriceNotPositive:
    def test_zero(self):
        prot = _valid_protection(); prot["stop_price"] = 0.0
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PRICE_NOT_POSITIVE in r.blocked_gates

    def test_negative(self):
        prot = _valid_protection(); prot["stop_price"] = -1.0
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PRICE_NOT_POSITIVE in r.blocked_gates


class TestY25StopPriceNotAlignedWithTick:
    def test_misaligned(self):
        # tick_size 0.01, stop_price 61.625 -> not aligned to tick.
        prot = _valid_protection(); prot["stop_price"] = 61.625
        r = _run(protection=prot)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_STOP_PRICE_NOT_ALIGNED_WITH_TICK in r.blocked_gates

    def test_aligned(self):
        # tick_size 0.01, stop_price 61.63 -> exact multiple -> aligned.
        r = _run()
        assert r.status == STATUS_CHECKLIST_READY
        assert r.stop_price_aligned_with_tick is True


# ===========================================================================
# Y26 - Y29: stop payload preview fields (tpslMode=Full,
# slTriggerBy=MarkPrice, positionIdx=0, category=linear)
# ===========================================================================

class TestY26PayloadCategoryLinear:
    def test_category(self):
        r = _run()
        assert r.stop_payload_preview["category"] == EXPECTED_INSTRUMENT_CATEGORY


class TestY27PayloadTpslModeFull:
    def test_tpsl_mode(self):
        r = _run()
        assert r.stop_payload_preview["tpslMode"] == EXPECTED_TPSL_MODE
        assert EXPECTED_TPSL_MODE == "Full"


class TestY28PayloadSlTriggerByMarkPrice:
    def test_trigger_by(self):
        r = _run()
        assert r.stop_payload_preview["slTriggerBy"] == EXPECTED_SL_TRIGGER_BY
        assert EXPECTED_SL_TRIGGER_BY == "MarkPrice"


class TestY29PayloadPositionIdxZeroAndPreviewOnly:
    def test_position_idx_and_preview_only(self):
        r = _run()
        assert r.stop_payload_preview["positionIdx"] == EXPECTED_POSITION_IDX
        assert r.stop_payload_preview["preview_only"] is True
        assert r.stop_payload_preview["endpoint_called"] is False
        assert r.stop_payload_preview["endpoint_path_ref"] == TRADING_STOP_PATH_REF
        assert r.stop_payload_preview["stopLoss"] == pytest.approx(61.63)
        assert r.stop_payload_preview["symbol"] == "SOLUSDT"


# ===========================================================================
# Y30 - Y32: safety invariants
# ===========================================================================

class TestY30OrderEndpointFalse:
    def test_default(self):
        r = _run()
        assert r.order_endpoint_called is False

    def test_dry_run(self):
        r = _run(allow_real_stop_permission=True)
        assert r.order_endpoint_called is False

    def test_guard(self):
        r = _run(allow_real_tiny_stop_attach=True)
        assert r.order_endpoint_called is False


class TestY31StopEndpointFalse:
    def test_default(self):
        r = _run()
        assert r.stop_endpoint_called is False

    def test_dry_run(self):
        r = _run(allow_real_stop_permission=True)
        assert r.stop_endpoint_called is False

    def test_guard(self):
        r = _run(allow_real_tiny_stop_attach=True)
        assert r.stop_endpoint_called is False


class TestY32NoPositionModified:
    def test_default(self):
        r = _run()
        assert r.no_position_modified is True
        assert r.existing_positions_touched == []

    def test_dry_run(self):
        r = _run(allow_real_stop_permission=True)
        assert r.no_position_modified is True

    def test_guard(self):
        r = _run(allow_real_tiny_stop_attach=True)
        assert r.no_position_modified is True


# ===========================================================================
# Y33: stop-attach token pattern present
# ===========================================================================

class TestY33StopAttachTokenPattern:
    def test_pattern(self):
        r = _run()
        assert r.stop_attach_token_pattern == STOP_ATTACH_TOKEN_PATTERN
        assert STOP_ATTACH_TOKEN_PATTERN == "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"
        env = r.stages[STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST]
        assert env["stop_attach_token_pattern"] == STOP_ATTACH_TOKEN_PATTERN
        assert env["stop_attach_token_not_validated_in_this_task"] is True


# ===========================================================================
# Y34: entry token not accepted in this task
# ===========================================================================

class TestY34EntryTokenNotAccepted:
    def test_documented(self):
        r = _run()
        env = r.stages[STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST]
        assert env["entry_token_not_accepted_in_this_task"] is True
        assert env["entry_token_pattern"] == ENTRY_TOKEN_PATTERN
        assert GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK in r.blocked_gates


# ===========================================================================
# Y35: cleanup token not accepted in this task
# ===========================================================================

class TestY35CleanupTokenNotAccepted:
    def test_documented(self):
        r = _run()
        env = r.stages[STAGE_3_STOP_ATTACH_TOKEN_CHECKLIST]
        assert env["cleanup_token_not_accepted_in_this_task"] is True
        assert env["cleanup_token_pattern"] == CLEANUP_TOKEN_PATTERN
        assert GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK in r.blocked_gates


# ===========================================================================
# Y36: allow-real-tiny-stop-attach does NOT run execution phase
# ===========================================================================

class TestY36GuardDoesNotExecute:
    def test_guard_safety(self):
        r = _run(allow_real_tiny_stop_attach=True)
        assert r.order_endpoint_called is False
        assert r.stop_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_orders_sent is True
        assert r.real_execution_allowed is False
        assert r.real_stop_attach_implemented is False


# ===========================================================================
# Y37: no execute flag exists (signature scan)
# ===========================================================================

class TestY37NoExecuteFlagInModule:
    def test_no_execute_flag(self):
        code = _read_code_only(_MODULE_PATH)
        assert "execute_real_tiny_stop" not in code
        assert "--execute-real-tiny-stop" not in _MODULE_PATH.read_text(encoding="utf-8")

    def test_no_execute_flag_in_cli(self):
        # CLI must not advertise an --execute-* tiny-stop-attach flag.
        text = _SCRIPT_PATH.read_text(encoding="utf-8")
        assert "--execute-real-tiny-stop-attach" not in text
        assert "--execute-tiny-stop-attach"      not in text
        assert "--execute-stop-attach"           not in text


# ===========================================================================
# Y38: report artifacts written (checklist)
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
        out_d  = base / "out"
        (ro_d   / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (rec_d  / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d  / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        (lc_d   / "latest_tiny_position_lifecycle_mock.json").write_text(json.dumps(_valid_lifecycle()), encoding="utf-8")
        (rp_d   / "latest_tiny_position_real_permission_gate.json").write_text(json.dumps(_valid_real_permission_gate()), encoding="utf-8")
        (ep_d   / "latest_tiny_entry_permission_gate.json").write_text(json.dumps(_valid_tiny_entry_permission_gate()), encoding="utf-8")
        return ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, out_d


class TestY38ReportChecklist(_ReportSetupMixin):
    def test_writes_report(self):
        from scripts.preview_demo_tiny_stop_attach_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_stop_permission=False,
                allow_real_tiny_stop_attach=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_stop_attach_permission_gate.json" in files
            assert "latest_tiny_stop_attach_permission_gate.md"   in files
            data = json.loads(
                (out_d / "latest_tiny_stop_attach_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["status"] == STATUS_CHECKLIST_READY
            assert data["real_execution_allowed"] is False
            assert data["real_stop_attach_implemented"] is False
            assert data["order_endpoint_called"] is False
            assert data["stop_endpoint_called"] is False
            assert data["no_position_modified"] is True


# ===========================================================================
# Y39: no secrets in report
# ===========================================================================

class TestY39NoSecretsInReport(_ReportSetupMixin):
    def test_no_secrets(self):
        from scripts.preview_demo_tiny_stop_attach_permission_gate import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_stop_permission=False,
                allow_real_tiny_stop_attach=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            md = (out_d / "latest_tiny_stop_attach_permission_gate.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md
            data = json.loads(
                (out_d / "latest_tiny_stop_attach_permission_gate.json").read_text(encoding="utf-8")
            )
            assert data["secret_value_observed"] is False


# ===========================================================================
# Y40: no forbidden imports
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


class TestY40NoForbiddenImports:
    def test_module(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            # CLI is allowed to import src.demo_tiny_stop_attach_permission_gate
            # only; nothing else from the forbidden list.
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# Y41: no close-only sender reuse
# ===========================================================================

class TestY41NoSenderReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"     not in code
            assert "demo_close_only_sender"  not in code


# ===========================================================================
# Y42: no emergency close sender called
# ===========================================================================

class TestY42NoEmergencyClose:
    def test_no_emergency_close(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoEmergencyCloseSender" not in code
            assert "demo_emergency_close_sender" not in code


# ===========================================================================
# Y43: no new-entry sender real execution called
# ===========================================================================

class TestY43NoNewEntrySender:
    def test_no_new_entry_sender(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoNewEntrySender"    not in code
            assert "demo_new_entry_sender" not in code


# ===========================================================================
# Y44: no trading-stop real adapter called
# ===========================================================================

class TestY44NoTradingStopRealAdapter:
    def test_no_trading_stop(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoTradingStopContractProbe" not in code
            assert "demo_trading_stop_contract_probe" not in code


# ===========================================================================
# Y45: source scan confirms no urllib/request/httpx/socket
# ===========================================================================

class TestY45NoNetworkTokens:
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
# Y46: CLI subprocess valid run exits 0
# ===========================================================================

class TestY46CLISubprocessOk(_ReportSetupMixin):
    def test_subprocess_exits_0(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        with tempfile.TemporaryDirectory() as td:
            ro_d, rec_d, prot_d, con_d, noop_d, lc_d, rp_d, ep_d, out_d = self._setup(Path(td))
            from scripts.preview_demo_tiny_stop_attach_permission_gate import run_execute
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_stop_permission=False,
                allow_real_tiny_stop_attach=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0


# ===========================================================================
# Y47: CLI subprocess missing artifact exits 1
# ===========================================================================

class TestY47CLISubprocessMissingExits1:
    def test_missing_artifact(self):
        from scripts.preview_demo_tiny_stop_attach_permission_gate import run_execute
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
            out_d  = base / "out"
            rc = run_execute(
                symbol="SOLUSDT",
                allow_real_stop_permission=False,
                allow_real_tiny_stop_attach=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=rec_d,
                protection_dir=prot_d, contract_dir=con_d,
                noop_plan_dir=noop_d, lifecycle_dir=lc_d,
                real_permission_dir=rp_d, tiny_entry_dir=ep_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1


# ===========================================================================
# Y48: next required task = TASK-014Z_cleanup
# ===========================================================================

class TestY48NextTaskIs014Z:
    def test_next_required_task(self):
        r = _run()
        assert r.next_required_task == (
            "TASK-014Z_tiny_isolated_demo_cleanup_permission_gate"
        )


# ===========================================================================
# Y49: gate count >= 49
# ===========================================================================

class TestY49GateCount:
    def test_at_least_49(self):
        import src.demo_tiny_stop_attach_permission_gate as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 49, (
            f"Expected >= 49 GATE_ constants, got {len(gate_names)}: "
            f"{sorted(gate_names)}"
        )


# ===========================================================================
# Y50: always-on gates surface in every checklist
# ===========================================================================

class TestY50AlwaysOnGates:
    def test_always_on_present(self):
        r = _run()
        unique = set(r.blocked_gates)
        for g in (
            GATE_STOP_ATTACH_TOKEN_PATTERN_REQUIRED,
            GATE_STOP_ATTACH_TOKEN_NOT_VALIDATED_THIS_TASK,
            GATE_ENTRY_TOKEN_NOT_ACCEPTED_THIS_TASK,
            GATE_CLEANUP_TOKEN_NOT_ACCEPTED_THIS_TASK,
            GATE_POST_STOP_ATTACH_READONLY_VERIFICATION_REQUIRED,
            GATE_NO_AUTO_CLEANUP_AFTER_STOP_ATTACH,
            GATE_READONLY_UNAVAILABLE_AFTER_STOP_FAIL_CLOSED,
            GATE_STOP_RESPONSE_NOT_OK_FAIL_CLOSED,
            GATE_STOP_PRICE_MISMATCH_AFTER_ATTACH_FAIL_CLOSED,
            GATE_TPSL_MODE_MISMATCH_AFTER_ATTACH_MANUAL_REVIEW,
            GATE_POSITION_MISSING_AFTER_STOP_FAIL_CLOSED,
            GATE_NO_REAL_EMERGENCY_CLOSE_THIS_TASK,
            GATE_REAL_STOP_ATTACH_NOT_IMPL,
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
# Y51: 7 stages
# ===========================================================================

class TestY51SevenStages:
    def test_seven(self):
        r = _run()
        assert set(r.stages.keys()) == set(ALL_STAGES)
        assert r.stage_order == list(ALL_STAGES)
        assert len(ALL_STAGES) == 7


# ===========================================================================
# Y52: missing symbol
# ===========================================================================

class TestY52MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# Y53: G20 not lifted
# ===========================================================================

class TestY53G20NotLifted:
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
# Y54: socket-disabled import smoke
# ===========================================================================

class TestY54SocketDisabledImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_stop_attach_permission_gate as m; "
             "print('OK', m.STATUS_CHECKLIST_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# Y55: dataclass roundtrip preserves invariants
# ===========================================================================

class TestY55DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(allow_real_stop_permission=True)
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
            ("real_stop_attach_implemented",        False),
            ("real_execution_allowed",              False),
            ("real_stop_permission_dry_run_allowed", True),
            ("existing_position_stop_snapshot_match", True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_PERMISSION_READY_EXEC_DISABLED
        # Deep-copy: mutating returned dict must not affect source.
        d["stages"][STAGE_2_STOP_PAYLOAD_PREVIEW]["mutated"] = True
        assert "mutated" not in r.stages[STAGE_2_STOP_PAYLOAD_PREVIEW]


# ===========================================================================
# Y56: path refs
# ===========================================================================

class TestY56PathRefs:
    def test_path_refs(self):
        r = _run()
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


# ===========================================================================
# Y57: stage_4 verification plan
# ===========================================================================

class TestY57Stage4VerificationPlan:
    def test_plan_fields(self):
        r = _run()
        env = r.stages[STAGE_4_POST_STOP_ATTACH_REQUIRED_VERIFICATION_PLAN]
        plan = env["post_stop_attach_verification_plan"]
        assert plan["verify_position_still_exists"]        is True
        assert plan["verify_stop_price_matches_submitted"] is True
        assert plan["verify_tpsl_mode_full_preserved"]     is True
        assert plan["verify_sl_trigger_by_mark_price"]     is True
        assert plan["verify_position_qty_unchanged"]       is True
        assert plan["verify_existing_positions_untouched"] is True
        assert plan["readonly_unavailable_after_stop"]     == "fail_closed"
        assert plan["stop_response_not_ok"]                == "fail_closed"
        assert plan["stop_price_mismatch_after_attach"]    == "fail_closed"
        assert plan["tpsl_mode_mismatch_after_attach"]     == "manual_review"
        assert plan["position_missing_after_stop_attach"]  == "fail_closed"
        assert plan["expected_tpsl_mode"]                  == EXPECTED_TPSL_MODE
        assert plan["expected_sl_trigger_by"]              == EXPECTED_SL_TRIGGER_BY
        assert plan["expected_position_idx"]               == EXPECTED_POSITION_IDX


# ===========================================================================
# Y58: stage_5 failure response plan
# ===========================================================================

class TestY58Stage5FailureResponsePlan:
    def test_failure_response(self):
        r = _run()
        env = r.stages[STAGE_5_FAILURE_RESPONSE_PLAN]
        plan = env["failure_response_plan"]
        assert plan["readonly_unavailable_after_stop"]    == "fail_closed"
        assert plan["stop_response_not_ok"]               == "fail_closed"
        assert plan["stop_price_mismatch_after_attach"]   == "fail_closed"
        assert plan["tpsl_mode_mismatch_after_attach"]    == "manual_review"
        assert plan["position_missing_after_stop_attach"] == "fail_closed"
        assert plan["no_real_emergency_close_in_this_task"] is True
        assert plan["no_auto_cleanup_after_stop_attach"]    is True


# ===========================================================================
# Y59: stage_6 execution guard fields
# ===========================================================================

class TestY59Stage6ExecutionGuard:
    def test_stage_6_flags_default(self):
        r = _run()
        env = r.stages[STAGE_6_EXECUTION_GUARD]
        assert env["real_execution_allowed"] is False
        assert env["real_stop_attach_implemented"] is False
        assert env["current_task_real_execution_allowed"] is False
        assert env["g20_policy_still_in_place"] is True
        assert env["g20_lifted"] is False
        assert env["no_real_order_endpoint"] is True
        assert env["no_real_stop_endpoint"] is True
        assert env["no_position_modified"] is True
        assert env["no_live_endpoint"] is True
        assert env["no_secrets_emitted"] is True

    def test_stage_6_flags_guard_consistent(self):
        r = _run(allow_real_tiny_stop_attach=True)
        env = r.stages[STAGE_6_EXECUTION_GUARD]
        # Even when caller passes the guard flag, stage_6 must NOT flip
        # real_execution_allowed to True.
        assert env["real_execution_allowed"] is False
        assert env["real_stop_attach_requested"] is True


# ===========================================================================
# Y60: instrument_rules_by_symbol (VPS real-readonly format)
# ===========================================================================

def _valid_rules_by_symbol() -> dict:
    return {
        "SOLUSDT": {
            "symbol":             "SOLUSDT",
            "category":           "linear",
            "min_order_qty":      0.1,
            "qty_step":           0.1,
            "tick_size":          0.01,
            "min_notional":       5.0,
            "min_notional_value": 5.0,
        }
    }


def _readonly_by_sym(**override) -> dict:
    base = {
        "timestamp_utc":         "2026-06-10T10:00:00Z",
        "endpoint_family":       EXPECTED_ENDPOINT_FAMILY,
        "account_mode":          EXPECTED_ACCOUNT_MODE,
        "proof_strength":        EXPECTED_PROOF_STRENGTH,
        "demo_runtime_verified": True,
        "equity_usd":            500.0,
        "available_balance_usd": 400.0,
        "instrument_rules_by_symbol": _valid_rules_by_symbol(),
    }
    base.update(override)
    return base


class TestY60InstrumentRulesBySymbolDictReady:
    """VPS format: instrument_rules_by_symbol (no instrument_rules list) -> READY."""

    def test_checklist_ready(self):
        r = _run(readonly=_readonly_by_sym())
        assert r.status == STATUS_CHECKLIST_READY
        assert r.instrument_rule_summary["rule_present"] is True
        assert r.instrument_rule_summary["tick_size"] == pytest.approx(0.01)
        assert r.stop_price > 0.0
        assert r.stop_price_aligned_with_tick is True
        assert r.order_endpoint_called  is False
        assert r.stop_endpoint_called   is False
        assert r.no_position_modified   is True


class TestY61InstrumentRulesBySymbolMissingSOLUSDT:
    """instrument_rules_by_symbol present but SOLUSDT missing -> FAIL_CLOSED."""

    def test_solusdt_absent(self):
        ro = _readonly_by_sym(instrument_rules_by_symbol={})
        r = _run(readonly=ro)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_INSTRUMENT_RULE_MISSING in r.blocked_gates
        assert r.instrument_rule_summary["rule_present"] is False


class TestY62InstrumentRulesBySymbolMissingTickSize:
    """instrument_rules_by_symbol SOLUSDT missing tick_size -> FAIL_CLOSED."""

    def test_missing_tick_size(self):
        rules = dict(_valid_rules_by_symbol())
        rules["SOLUSDT"] = {k: v for k, v in rules["SOLUSDT"].items() if k != "tick_size"}
        r = _run(readonly=_readonly_by_sym(instrument_rules_by_symbol=rules))
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_TICK_SIZE_MISSING in r.blocked_gates


# ===========================================================================
# Y63: guard safety invariants
# ===========================================================================

class TestY63GuardSafetyInvariants:
    def test_guard_invariants(self):
        r = _run(allow_real_tiny_stop_attach=True)
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True
        assert r.existing_positions_touched == []
