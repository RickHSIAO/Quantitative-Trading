"""
tests/demo_trading/test_demo_tiny_position_lifecycle_mock.py
TASK-014V: Demo Tiny Isolated Position Lifecycle Mock tests (V1 - V40+).

Covers preview / mock_lifecycle / real_tiny_position_guard / fail_closed
paths, all 7 phases, 3 failure injection paths, 29 gates, payload-free
mock invariants, source-scan safety (no urlopen / no forbidden imports /
no secrets), report artifacts, and the invariant that TASK-014L sender
G20 (protected_entry_policy_missing) still blocks --execute-new-entry.
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

from src.demo_tiny_position_lifecycle_mock import (
    ALL_PHASES,
    BASE_URL_DEMO_REF,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyPositionLifecycleMock,
    EXISTING_POSITION_SYMBOLS,
    GATE_BALANCE_INSUFFICIENT,
    GATE_CLEANUP_FAILED,
    GATE_CONTRACT_MISSING,
    GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH,
    GATE_FINAL_AUDIT_DANGLING_POSITION,
    GATE_FINAL_AUDIT_EXISTING_TOUCHED,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_LIFECYCLE_DOC_MISSING,
    GATE_NOOP_PLAN_MISSING,
    GATE_NOOP_PLAN_NOT_READY,
    GATE_NOOP_PLAN_RECOMMENDED_PATH_MISMATCH,
    GATE_POST_FILL_AUDIT_FAILED,
    GATE_PREFLIGHT_FAILED,
    GATE_PRIOR_PROBE_FLIPPED_REAL,
    GATE_PROTECTED_VERIFY_MISMATCH,
    GATE_PROTECTION_ENTRY_PRICE_MISSING,
    GATE_PROTECTION_MISSING,
    GATE_PROTECTION_STOP_PRICE_MISSING,
    GATE_READONLY_SMOKE_MISSING,
    GATE_REAL_TINY_POSITION_NOT_IMPL,
    GATE_REALTIME_PRICE_GUARD_MISSING,
    GATE_RECONCILIATION_MISSING,
    GATE_REVIEW_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_STOP_ATTACH_FAILED,
    GATE_SYMBOL_COLLIDES_EXISTING_POSITION,
    GATE_TINY_ENTRY_ENVELOPE_INVALID,
    GATE_TINY_NOTIONAL_NOT_DEFINED,
    GATE_TINY_QTY_NOT_DEFINED,
    MOCK_CLEANUP_PREFIX,
    MOCK_ENTRY_PREFIX,
    MOCK_STOP_PREFIX,
    MODE_FAIL_CLOSED,
    MODE_MOCK_LIFECYCLE,
    MODE_PREVIEW,
    MODE_REAL_TINY_POSITION,
    ORDER_CREATE_PATH_REF,
    PHASE_0_PREFLIGHT,
    PHASE_1_TINY_ENTRY,
    PHASE_2_POST_FILL_AUDIT,
    PHASE_3_STOP_ATTACH,
    PHASE_4_PROTECTED_VERIFY,
    PHASE_5_CLEANUP,
    PHASE_6_FINAL_AUDIT,
    STATUS_FAIL_CLOSED,
    STATUS_MOCK_FAIL_CLOSED,
    STATUS_MOCK_SUCCESS,
    STATUS_PREVIEW_READY,
    STATUS_REAL_TINY_NOT_IMPLEMENTED,
    TinyPositionLifecycleResult,
    TRADING_STOP_PATH_REF,
)


_MODULE_PATH = ROOT / "src" / "demo_tiny_position_lifecycle_mock.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_tiny_position_lifecycle_mock.py"
_TEST_NOW    = datetime(2026, 6, 10, 12, 0, 0, tzinfo=timezone.utc)


# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

def _valid_readonly() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T10:00:00Z",
        "demo_runtime_verified":  True,
        "proof_strength":         "real_demo_runtime_verified",
        "equity_usd":             500.0,
        "available_balance_usd":  400.0,
    }


def _valid_reconciliation() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T10:05:00Z",
        "mode":                   "real_readonly",
        "demo_runtime_verified":  True,
        "open_positions_count":   5,
        "positions": [
            {"symbol": "ENAUSDT",   "side": "short", "quantity": 100.0, "entry_price": 0.5, "stop_price": 0.0},
            {"symbol": "TIAUSDT",   "side": "short", "quantity": 50.0,  "entry_price": 2.0, "stop_price": 0.0},
            {"symbol": "AIXBTUSDT", "side": "short", "quantity": 200.0, "entry_price": 0.3, "stop_price": 0.0},
            {"symbol": "POLYXUSDT", "side": "short", "quantity": 300.0, "entry_price": 0.2, "stop_price": 0.0},
            {"symbol": "EDUUSDT",   "side": "short", "quantity": 400.0, "entry_price": 0.4, "stop_price": 0.0},
        ],
        "new_entry_allowed":      False,
        "no_orders_sent":         True,
        "no_position_modified":   True,
        "order_endpoint_called":  False,
        "secret_value_observed":  False,
    }


def _valid_protection() -> dict:
    return {
        "timestamp_utc":                  "2026-06-10T11:00:00Z",
        "selected_symbol":                "SOLUSDT",
        "selected_side":                  "long",
        "selected_qty":                   12.3,
        "entry_reference_price":          64.87,
        "stop_price":                     61.63,
        "stop_order_side":                "Sell",
        "stop_trigger_direction":         "fall_below_entry",
        "realtime_price_guard_verified":  True,
        "review_fail_closed":             False,
        "protected_entry_status":         "PREVIEW_ONLY",
        "stop_loss_attach_required":      True,
        "stop_loss_endpoint_allowed":     False,
        "preview_only":                   True,
        "no_orders_sent":                 True,
        "order_endpoint_called":          False,
        "stop_endpoint_called":           False,
        "no_position_modified":           True,
        "no_live_endpoint":               True,
        "secret_value_observed":          False,
    }


def _valid_contract() -> dict:
    return {
        "timestamp_utc":          "2026-06-10T11:30:00Z",
        "mode":                   "preview",
        "selected_symbol":        "SOLUSDT",
        "stop_loss":              61.63,
        "path":                   "/v5/position/trading-stop",
        "method":                 "POST",
        "real_probe_allowed":     False,
        "real_probe_implemented": False,
        "stop_endpoint_called":   False,
        "order_endpoint_called":  False,
        "no_position_modified":   True,
        "no_live_endpoint":       True,
        "secret_value_observed":  False,
        "status":                 "TRADING_STOP_CONTRACT_PREVIEW_OK",
    }


def _valid_noop_plan() -> dict:
    return {
        "timestamp_utc":            "2026-06-10T11:45:00Z",
        "mode":                     "plan",
        "selected_symbol":          "SOLUSDT",
        "recommended_path":         "tiny_isolated_position_plan",
        "real_probe_allowed":       False,
        "real_noop_probe_implemented": False,
        "current_task_real_execution_allowed": False,
        "stop_endpoint_called":     False,
        "order_endpoint_called":    False,
        "no_position_modified":     True,
        "no_live_endpoint":         True,
        "secret_value_observed":    False,
        "g20_policy_still_in_place": True,
        "status":                   "NOOP_PROBE_PLAN_READY",
        "next_required_task":       "TASK-014V_tiny_isolated_demo_position_lifecycle_mock",
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


def _sim() -> DemoTinyPositionLifecycleMock:
    return DemoTinyPositionLifecycleMock()


_UNSET = object()


def _run(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    noop_plan=_UNSET, symbol=DEFAULT_SELECTED_SYMBOL,
    mock_lifecycle=False, allow_real=False,
    sim_stop_fail=False, sim_cleanup_fail=False, sim_existing_mismatch=False,
    _now=_TEST_NOW,
) -> TinyPositionLifecycleResult:
    return _sim().run_lifecycle(
        readonly_smoke=_valid_readonly()       if readonly   is _UNSET else readonly,
        reconciliation=_valid_reconciliation() if recon      is _UNSET else recon,
        protection=_valid_protection()         if protection is _UNSET else protection,
        contract=_valid_contract()             if contract   is _UNSET else contract,
        noop_plan=_valid_noop_plan()           if noop_plan  is _UNSET else noop_plan,
        symbol=symbol,
        mock_lifecycle=mock_lifecycle,
        allow_real_tiny_position=allow_real,
        _simulate_stop_attach_failure=sim_stop_fail,
        _simulate_cleanup_failure=sim_cleanup_fail,
        _simulate_existing_stop_mismatch=sim_existing_mismatch,
        _now=_now,
    )


# ===========================================================================
# V1: default preview SOLUSDT -> TINY_LIFECYCLE_PREVIEW_READY
# ===========================================================================

class TestV1PreviewReady:
    def test_preview_solusdt(self):
        r = _run(symbol="SOLUSDT")
        assert r.status == STATUS_PREVIEW_READY
        assert r.mode == MODE_PREVIEW
        assert r.selected_symbol == "SOLUSDT"
        assert r.real_execution_allowed is False
        assert r.real_tiny_position_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == (
            "TASK-014W_tiny_isolated_demo_position_real_execution_permission_gate"
        )


# ===========================================================================
# V2: missing readonly_smoke => FAIL_CLOSED + preflight failed
# ===========================================================================

class TestV2MissingReadonly:
    def test_none_readonly(self):
        r = _run(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.mode == MODE_FAIL_CLOSED
        assert r.failed_phase == PHASE_0_PREFLIGHT
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates
        assert GATE_PREFLIGHT_FAILED in r.blocked_gates

    def test_empty_readonly(self):
        r = _run(readonly={})
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


# ===========================================================================
# V3: missing reconciliation => FAIL_CLOSED
# ===========================================================================

class TestV3MissingReconciliation:
    def test_none_recon(self):
        r = _run(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert r.failed_phase == PHASE_0_PREFLIGHT
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


# ===========================================================================
# V4: missing protection => FAIL_CLOSED
# ===========================================================================

class TestV4MissingProtection:
    def test_none_protection(self):
        r = _run(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


# ===========================================================================
# V5: missing contract => FAIL_CLOSED
# ===========================================================================

class TestV5MissingContract:
    def test_none_contract(self):
        r = _run(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


# ===========================================================================
# V6: missing noop_plan => FAIL_CLOSED
# ===========================================================================

class TestV6MissingNoopPlan:
    def test_none_noop_plan(self):
        r = _run(noop_plan=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_NOOP_PLAN_MISSING in r.blocked_gates


# ===========================================================================
# V7: missing symbol => FAIL_CLOSED
# ===========================================================================

class TestV7MissingSymbol:
    def test_empty_symbol(self):
        r = _run(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# V8: symbol collides with existing positions => FAIL_CLOSED
# ===========================================================================

class TestV8SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_existing_symbol_blocks(self, sym):
        r = _run(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SYMBOL_COLLIDES_EXISTING_POSITION in r.blocked_gates


# ===========================================================================
# V9: realtime price guard missing
# ===========================================================================

class TestV9RealtimeGuardMissing:
    def test_no_guard(self):
        prot = _valid_protection()
        prot["realtime_price_guard_verified"] = False
        r = _run(protection=prot)
        assert GATE_REALTIME_PRICE_GUARD_MISSING in r.blocked_gates


# ===========================================================================
# V10: review fail-closed flag
# ===========================================================================

class TestV10ReviewFailClosed:
    def test_fail_closed_flag(self):
        prot = _valid_protection()
        prot["review_fail_closed"] = True
        r = _run(protection=prot)
        assert GATE_REVIEW_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# V11: contract claims real_probe_implemented => surfaced gate
# ===========================================================================

class TestV11PriorProbeFlipped:
    def test_prior_flipped(self):
        contract = _valid_contract()
        contract["real_probe_implemented"] = True
        r = _run(contract=contract)
        assert GATE_PRIOR_PROBE_FLIPPED_REAL in r.blocked_gates


# ===========================================================================
# V12: protection stop_price / entry_price missing
# ===========================================================================

class TestV12ProtectionPricesMissing:
    def test_stop_missing(self):
        prot = _valid_protection()
        prot["stop_price"] = 0.0
        r = _run(protection=prot)
        assert GATE_PROTECTION_STOP_PRICE_MISSING in r.blocked_gates

    def test_entry_missing(self):
        prot = _valid_protection()
        prot["entry_reference_price"] = 0.0
        r = _run(protection=prot)
        assert GATE_PROTECTION_ENTRY_PRICE_MISSING in r.blocked_gates


# ===========================================================================
# V13: noop_plan status not ready
# ===========================================================================

class TestV13NoopPlanStatusBad:
    def test_status_not_ready(self):
        plan = _valid_noop_plan()
        plan["status"] = "FAIL_CLOSED"
        r = _run(noop_plan=plan)
        assert GATE_NOOP_PLAN_NOT_READY in r.blocked_gates


# ===========================================================================
# V14: noop_plan recommended_path mismatch
# ===========================================================================

class TestV14NoopPlanRecommendedPathMismatch:
    def test_mismatch(self):
        plan = _valid_noop_plan()
        plan["recommended_path"] = "read_only_endpoint_research"
        r = _run(noop_plan=plan)
        assert GATE_NOOP_PLAN_RECOMMENDED_PATH_MISMATCH in r.blocked_gates


# ===========================================================================
# V15: balance insufficient
# ===========================================================================

class TestV15BalanceInsufficient:
    def test_low_balance(self):
        ro = _valid_readonly()
        ro["available_balance_usd"] = 0.01
        r = _run(readonly=ro)
        assert GATE_BALANCE_INSUFFICIENT in r.blocked_gates


# ===========================================================================
# V16: defense-in-depth gates always present in preview
# ===========================================================================

class TestV16DefenseInDepth:
    def test_existing_positions_gate_present(self):
        r = _run()
        assert GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH in r.blocked_gates
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates


# ===========================================================================
# V17: module defines >= 29 gate constants AND >= 21 general gate constants
# ===========================================================================

class TestV17GateCount:
    def test_module_defines_at_least_29_gate_constants(self):
        import src.demo_tiny_position_lifecycle_mock as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 29, (
            f"Module should define at least 29 GATE_ constants, "
            f"got {len(gate_names)}: {sorted(gate_names)}"
        )

    def test_preview_open_blockers_floor(self):
        r = _run()
        unique = set(r.blocked_gates)
        # Preview-mode floor:
        #   2 defense-in-depth (existing_positions_must_not_touch,
        #                       g20_policy_still_in_place)
        # All other gates are conditional on upstream contents.
        assert GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH in unique
        assert GATE_G20_POLICY_STILL_IN_PLACE in unique


# ===========================================================================
# V18: --allow-real-tiny-position returns REAL_TINY_POSITION_NOT_IMPLEMENTED
# ===========================================================================

class TestV18RealTinyGuard:
    def test_real_guard_returns_not_impl(self):
        r = _run(allow_real=True)
        assert r.status == STATUS_REAL_TINY_NOT_IMPLEMENTED
        assert r.mode == MODE_REAL_TINY_POSITION
        assert r.real_execution_allowed is True
        assert r.real_tiny_position_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert GATE_REAL_TINY_POSITION_NOT_IMPL in r.blocked_gates

    def test_real_guard_safety_invariants(self):
        r = _run(allow_real=True)
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True


# ===========================================================================
# V19: mock_lifecycle happy path -> MOCK_TINY_LIFECYCLE_SUCCESS
# ===========================================================================

class TestV19MockLifecycleSuccess:
    def test_all_phases_pass(self):
        r = _run(mock_lifecycle=True)
        assert r.status == STATUS_MOCK_SUCCESS
        assert r.mode == MODE_MOCK_LIFECYCLE
        assert r.failed_phase == ""
        for p in ALL_PHASES:
            assert p in r.phases
        assert r.phases[PHASE_0_PREFLIGHT]["preflight_ok"] is True
        assert r.phases[PHASE_1_TINY_ENTRY]["envelope_valid"] is True
        assert r.phases[PHASE_2_POST_FILL_AUDIT]["audit_ok"] is True
        assert r.phases[PHASE_3_STOP_ATTACH]["attach_ok"] is True
        assert r.phases[PHASE_4_PROTECTED_VERIFY]["match"] is True
        assert r.phases[PHASE_5_CLEANUP]["cleanup_ok"] is True
        assert r.phases[PHASE_6_FINAL_AUDIT]["dangling_tiny_position"] is False
        assert r.phases[PHASE_6_FINAL_AUDIT]["existing_positions_touched"] == []


# ===========================================================================
# V20: failure injection -- stop-attach failure
# ===========================================================================

class TestV20StopAttachFailure:
    def test_stop_attach_failure(self):
        r = _run(mock_lifecycle=True, sim_stop_fail=True)
        assert r.status == STATUS_MOCK_FAIL_CLOSED
        assert r.failed_phase == PHASE_3_STOP_ATTACH
        assert GATE_STOP_ATTACH_FAILED in r.blocked_gates
        assert r.phases[PHASE_3_STOP_ATTACH]["attach_ok"] is False
        assert r.phases[PHASE_3_STOP_ATTACH]["simulated_failure"] is True

    def test_safety_invariants_under_stop_failure(self):
        r = _run(mock_lifecycle=True, sim_stop_fail=True)
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True


# ===========================================================================
# V21: failure injection -- cleanup failure (dangling tiny position)
# ===========================================================================

class TestV21CleanupFailure:
    def test_cleanup_failure(self):
        r = _run(mock_lifecycle=True, sim_cleanup_fail=True)
        assert r.status == STATUS_MOCK_FAIL_CLOSED
        # Cleanup failure means phase 5 fails first.
        assert r.failed_phase == PHASE_5_CLEANUP
        assert GATE_CLEANUP_FAILED in r.blocked_gates
        assert r.dangling_tiny_position is True
        assert GATE_FINAL_AUDIT_DANGLING_POSITION in r.blocked_gates


# ===========================================================================
# V22: failure injection -- existing stop mismatch
# ===========================================================================

class TestV22ExistingStopMismatch:
    def test_existing_stop_mismatch(self):
        r = _run(mock_lifecycle=True, sim_existing_mismatch=True)
        assert r.status == STATUS_MOCK_FAIL_CLOSED
        assert r.failed_phase == PHASE_4_PROTECTED_VERIFY
        assert GATE_PROTECTED_VERIFY_MISMATCH in r.blocked_gates
        assert r.phases[PHASE_4_PROTECTED_VERIFY]["simulated_mismatch"] is True

    def test_existing_positions_still_untouched_under_mismatch(self):
        r = _run(mock_lifecycle=True, sim_existing_mismatch=True)
        assert r.existing_positions_touched == []
        assert GATE_FINAL_AUDIT_EXISTING_TOUCHED not in r.blocked_gates


# ===========================================================================
# V23: 7 phases listed in result.phases (mock_lifecycle) and result.phase_order
# ===========================================================================

class TestV23SevenPhases:
    def test_seven_phases_present(self):
        r = _run(mock_lifecycle=True)
        assert set(r.phases.keys()) == set(ALL_PHASES)
        assert r.phase_order == list(ALL_PHASES)

    def test_phase_constants_distinct(self):
        assert len(set(ALL_PHASES)) == 7


# ===========================================================================
# V24: phase envelopes carry zero endpoint_called flags
# ===========================================================================

class TestV24EnvelopesNeverCallEndpoint:
    def test_all_phase_endpoint_called_false(self):
        r = _run(mock_lifecycle=True)
        for phase_id, env in r.phases.items():
            assert env.get("endpoint_called", False) is False, (
                f"phase {phase_id} must not flag endpoint_called"
            )


# ===========================================================================
# V25: mock identifiers carry per-symbol deterministic prefixes
# ===========================================================================

class TestV25MockIdentifiers:
    def test_entry_id_prefix(self):
        r = _run(mock_lifecycle=True, symbol="SOLUSDT")
        assert r.mock_entry_order_link_id.startswith(
            f"{MOCK_ENTRY_PREFIX}SOLUSDT-"
        )
        assert r.mock_stop_envelope_id.startswith(
            f"{MOCK_STOP_PREFIX}SOLUSDT-"
        )
        assert r.mock_cleanup_order_link_id.startswith(
            f"{MOCK_CLEANUP_PREFIX}SOLUSDT-"
        )

    def test_envelope_carries_link_ids(self):
        r = _run(mock_lifecycle=True, symbol="SOLUSDT")
        assert r.phases[PHASE_1_TINY_ENTRY]["order_link_id"] == r.mock_entry_order_link_id
        assert r.phases[PHASE_3_STOP_ATTACH]["envelope_id"] == r.mock_stop_envelope_id
        assert r.phases[PHASE_5_CLEANUP]["order_link_id"] == r.mock_cleanup_order_link_id


# ===========================================================================
# V26: existing positions documented + never touched
# ===========================================================================

class TestV26ExistingPositionsNeverTouched:
    def test_existing_positions_listed(self):
        r = _run(mock_lifecycle=True)
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols

    def test_existing_positions_untouched_happy_path(self):
        r = _run(mock_lifecycle=True)
        assert r.existing_positions_touched == []
        assert r.existing_position_stop_snapshot_match is True
        assert GATE_FINAL_AUDIT_EXISTING_TOUCHED not in r.blocked_gates


# ===========================================================================
# V27: existing 5 demo positions documented in module constant
# ===========================================================================

class TestV27ExistingPositionConstant:
    def test_constant_matches_spec(self):
        assert set(EXISTING_POSITION_SYMBOLS) == {
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
        }


# ===========================================================================
# V28: report artifacts written (PREVIEW mode)
# ===========================================================================

class TestV28ReportPreview:
    def _setup(self, base: Path):
        ro_d    = base / "readonly";     ro_d.mkdir()
        recon_d = base / "recon";        recon_d.mkdir()
        prot_d  = base / "protection";   prot_d.mkdir()
        con_d   = base / "contract";     con_d.mkdir()
        noop_d  = base / "noop";         noop_d.mkdir()
        out_d   = base / "out"
        (ro_d    / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (recon_d / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d  / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d   / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        (noop_d  / "latest_trading_stop_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        return ro_d, recon_d, prot_d, con_d, noop_d, out_d

    def test_preview_writes_report(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=False, allow_real_tiny_position=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in out_d.iterdir())
            assert "latest_tiny_position_lifecycle_mock.json" in files
            assert "latest_tiny_position_lifecycle_mock.md"   in files
            ts_json = [n for n in files if n.endswith(".json") and not n.startswith("latest_")]
            ts_md   = [n for n in files if n.endswith(".md")   and not n.startswith("latest_")]
            assert len(ts_json) == 1
            assert len(ts_md)   == 1
            data = json.loads((out_d / "latest_tiny_position_lifecycle_mock.json").read_text(encoding="utf-8"))
            assert data["status"] == STATUS_PREVIEW_READY
            assert data["current_task_real_execution_allowed"] is False


# ===========================================================================
# V29: report artifacts (MOCK lifecycle success)
# ===========================================================================

class TestV29ReportMockSuccess(TestV28ReportPreview):
    def test_mock_success_report(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=True, allow_real_tiny_position=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads((out_d / "latest_tiny_position_lifecycle_mock.json").read_text(encoding="utf-8"))
            assert data["status"] == STATUS_MOCK_SUCCESS
            assert data["failed_phase"] == ""
            assert data["dangling_tiny_position"] is False
            assert data["existing_positions_touched"] == []


# ===========================================================================
# V30: report artifacts (REAL TINY GUARD)
# ===========================================================================

class TestV30ReportRealGuard(TestV28ReportPreview):
    def test_real_guard_report(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=False, allow_real_tiny_position=True,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads((out_d / "latest_tiny_position_lifecycle_mock.json").read_text(encoding="utf-8"))
            assert data["status"] == STATUS_REAL_TINY_NOT_IMPLEMENTED
            assert data["real_execution_allowed"] is True
            assert data["real_tiny_position_implemented"] is False
            assert GATE_REAL_TINY_POSITION_NOT_IMPL in data["blocked_gates"]
            md = (out_d / "latest_tiny_position_lifecycle_mock.md").read_text(encoding="utf-8")
            assert "REAL_TINY_POSITION_NOT_IMPLEMENTED" in md


# ===========================================================================
# V31: no secrets in report
# ===========================================================================

class TestV31NoSecretsInReport(TestV28ReportPreview):
    def test_no_secret_strings(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=True, allow_real_tiny_position=False,
                write_report=True,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads((out_d / "latest_tiny_position_lifecycle_mock.json").read_text(encoding="utf-8"))
            assert data["secret_value_observed"] is False
            md = (out_d / "latest_tiny_position_lifecycle_mock.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md


# ===========================================================================
# V32: no forbidden imports in module + CLI
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


class TestV32NoForbiddenImports:
    def test_module_imports(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli_imports(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# V33: no urllib/urlopen/socket/http.client in module or CLI source
# ===========================================================================

class TestV33NoNetworkTokensInSource:
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
# V34: no close-only / emergency-close / new-entry / probe coupling
# ===========================================================================

class TestV34NoSenderReuse:
    def test_no_close_only(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoCloseOnlySender"   not in code
            assert "demo_close_only_sender" not in code

    def test_no_emergency_close(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoEmergencyCloseSender"   not in code
            assert "demo_emergency_close_sender" not in code

    def test_no_new_entry_sender(self):
        for path in (_MODULE_PATH, _SCRIPT_PATH):
            code = _read_code_only(path)
            assert "DemoNewEntrySender"    not in code
            assert "demo_new_entry_sender" not in code

    def test_no_contract_probe_back_coupling(self):
        code = _read_code_only(_MODULE_PATH)
        assert "demo_trading_stop_contract_probe" not in code

    def test_no_noop_plan_back_coupling(self):
        code = _read_code_only(_MODULE_PATH)
        assert "demo_trading_stop_noop_probe_plan" not in code


# ===========================================================================
# V35: module does not open a socket at import time
# ===========================================================================

class TestV35NoSocketAtImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_tiny_position_lifecycle_mock as m; "
             "print('OK', m.STATUS_PREVIEW_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# V36: TASK-014L G20 is NOT lifted by this task
# ===========================================================================

class TestV36G20StillBlocks:
    def test_g20_constant_unchanged(self):
        from src.demo_new_entry_protection import G20_BLOCKED_GATE_NAME
        assert G20_BLOCKED_GATE_NAME == "protected_entry_policy_missing"

    def test_simulator_does_not_lift_g20(self):
        code = _read_code_only(_MODULE_PATH)
        assert "protected_entry_policy_missing" not in code
        assert "G20_BLOCKED_GATE_NAME"          not in code

    def test_result_records_g20_still_in_place(self):
        r = _run()
        assert r.g20_policy_still_in_place is True
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates


# ===========================================================================
# V37: safety invariants on result are all conservative
# ===========================================================================

class TestV37SafetyInvariants:
    def test_invariants_default_preview(self):
        r = _run()
        assert r.stop_endpoint_called  is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified  is True
        assert r.no_live_endpoint      is True
        assert r.no_orders_sent        is True
        assert r.no_batch_order        is True
        assert r.no_close_only_path    is True
        assert r.emergency_close_invoked is False
        assert r.secret_value_observed   is False

    def test_invariants_under_mock_lifecycle(self):
        r = _run(mock_lifecycle=True)
        assert r.stop_endpoint_called  is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified  is True
        assert r.no_live_endpoint      is True
        assert r.no_orders_sent        is True

    def test_path_refs_are_string_only(self):
        r = _run()
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.base_url_ref          == BASE_URL_DEMO_REF


# ===========================================================================
# V38: dataclass round-trip + immutability of nested phases dict
# ===========================================================================

class TestV38DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _run(mock_lifecycle=True)
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
            ("secret_value_observed",               False),
            ("g20_policy_still_in_place",           True),
            ("current_task_real_execution_allowed", False),
            ("real_tiny_position_implemented",      False),
            ("dangling_tiny_position",              False),
            ("existing_position_stop_snapshot_match", True),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"] == STATUS_MOCK_SUCCESS
        # to_dict() returns deep copies; mutating must not affect source.
        d["phases"][PHASE_1_TINY_ENTRY]["mutated"] = True
        assert "mutated" not in r.phases[PHASE_1_TINY_ENTRY]


# ===========================================================================
# V39: CLI exit codes
# ===========================================================================

class TestV39CLIExitCodes(TestV28ReportPreview):
    def test_missing_upstream_returns_1(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            base    = Path(td)
            ro_d    = base / "readonly";     ro_d.mkdir()
            recon_d = base / "recon";        recon_d.mkdir()
            prot_d  = base / "protection";   prot_d.mkdir()
            con_d   = base / "contract";     con_d.mkdir()
            noop_d  = base / "noop";         noop_d.mkdir()
            out_d   = base / "out"
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=False, allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_missing_symbol_returns_1(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="", mock_lifecycle=False, allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_collision_symbol_returns_1(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="ENAUSDT", mock_lifecycle=False, allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_preview_returns_0(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=False, allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_mock_success_returns_0(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=True, allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0

    def test_mock_fail_closed_returns_1(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=True, allow_real_tiny_position=False,
                simulate_stop_attach_failure=True,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 1

    def test_real_guard_returns_0(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=False, allow_real_tiny_position=True,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0


# ===========================================================================
# V40: trading_stop_path_ref / order_create_path_ref match canonical strings
# ===========================================================================

class TestV40PathRefs:
    def test_trading_stop_path_canonical(self):
        assert TRADING_STOP_PATH_REF == "/v5/position/trading-stop"

    def test_order_create_path_canonical(self):
        assert ORDER_CREATE_PATH_REF == "/v5/order/create"

    def test_base_url_canonical(self):
        assert BASE_URL_DEMO_REF == "https://api-demo.bybit.com"

    def test_no_call_expressions_in_module(self):
        code = _read_code_only(_MODULE_PATH)
        # The module must not perform any HTTP call expressions.
        assert "post(" not in code
        assert "session.post" not in code
        assert "session.get"  not in code


# ===========================================================================
# V41: noop_plan loader CLI also resolves legacy alias filename
# ===========================================================================

class TestV41NoopPlanLegacyAlias:
    def _setup_legacy(self, base: Path):
        ro_d    = base / "readonly";     ro_d.mkdir()
        recon_d = base / "recon";        recon_d.mkdir()
        prot_d  = base / "protection";   prot_d.mkdir()
        con_d   = base / "contract";     con_d.mkdir()
        noop_d  = base / "noop";         noop_d.mkdir()
        out_d   = base / "out"
        (ro_d    / "latest_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (recon_d / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d  / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d   / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
        # Write legacy alias only -- no primary.
        (noop_d  / "latest_noop_probe_plan.json").write_text(json.dumps(_valid_noop_plan()), encoding="utf-8")
        return ro_d, recon_d, prot_d, con_d, noop_d, out_d

    def test_legacy_alias_resolves(self):
        from scripts.preview_demo_tiny_position_lifecycle_mock import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, noop_d, out_d = self._setup_legacy(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", mock_lifecycle=False, allow_real_tiny_position=False,
                write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, noop_plan_dir=noop_d,
                output_dir=out_d, _now=_TEST_NOW,
            )
            assert rc == 0
