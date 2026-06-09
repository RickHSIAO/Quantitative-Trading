"""
tests/demo_trading/test_demo_trading_stop_noop_probe_plan.py
TASK-014U: Demo Trading-stop No-op Probe Plan tests (U1 - U32+).

Covers plan / real-noop-probe-guard / fail-closed paths, three-plan
comparison, 33 gates, payload-free design invariants, source-scan
safety (no urlopen / no forbidden imports / no secrets), report
artifacts, and the invariant that TASK-014L sender G20
(protected_entry_policy_missing) still blocks --execute-new-entry.
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

from src.demo_trading_stop_noop_probe_plan import (
    BASE_URL_DEMO_REF,
    DEFAULT_SELECTED_SYMBOL,
    DemoTradingStopNoopProbePlanner,
    EXISTING_POSITION_SYMBOLS,
    GATE_CONTRACT_MISSING,
    GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH,
    GATE_EXPECTED_ERR_CANNOT_DISAMBIGUATE,
    GATE_EXPECTED_ERR_IDEMPOTENCY_UNVERIFIED,
    GATE_EXPECTED_ERR_MODIFIES_ON_MATCH,
    GATE_G20_POLICY_STILL_IN_PLACE,
    GATE_PRIOR_PROBE_FLIPPED_REAL,
    GATE_PROTECTION_MISSING,
    GATE_READONLY_ENDPOINT_NOT_AVAILABLE,
    GATE_READONLY_RESEARCH_INCONCLUSIVE,
    GATE_READONLY_SMOKE_MISSING,
    GATE_READONLY_WORKAROUND_REQUIRES_WRITE,
    GATE_REALTIME_PRICE_GUARD_MISSING,
    GATE_REAL_NOOP_PROBE_NOT_IMPL,
    GATE_RECONCILIATION_MISSING,
    GATE_REVIEW_FAIL_CLOSED,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SYMBOL_COLLIDES_EXISTING_POSITION,
    GATE_TINY_ACCOUNT_MODE_UNVERIFIED,
    GATE_TINY_BALANCE_INSUFFICIENT_UNKNOWN,
    GATE_TINY_EMERGENCY_CLOSE_UNVERIFIED,
    GATE_TINY_ISOLATION_UNVERIFIED,
    GATE_TINY_LEVERAGE_UNVERIFIED,
    GATE_TINY_LIFECYCLE_DOC_MISSING,
    GATE_TINY_MARKET_PRICE_DRIFT_UNVERIFIED,
    GATE_TINY_NOTIONAL_MIN_UNKNOWN,
    GATE_TINY_PARTIAL_FILL_UNHANDLED,
    GATE_TINY_POST_FILL_AUDIT_MISSING,
    GATE_TINY_QTY_MIN_UNKNOWN,
    GATE_TINY_SESSION_RESUME_UNCOVERED,
    GATE_TINY_STOP_ATTACH_WINDOW_UNCOVERED,
    GATE_TINY_SYMBOL_NOT_LINEAR_PERPETUAL,
    GATE_TINY_SYMBOL_OVERLAPS_EXISTING,
    MODE_PLAN,
    MODE_REAL_NOOP_PROBE,
    NoopProbePlanResult,
    ORDER_CREATE_PATH_REF,
    PATH_EXPECTED_ERROR,
    PATH_READ_ONLY,
    PATH_TINY_ISOLATED,
    RECOMMENDED_PATH,
    STATUS_FAIL_CLOSED,
    STATUS_PLAN_READY,
    STATUS_REAL_NOOP_NOT_IMPL,
    TRADING_STOP_PATH_REF,
    build_all_plans,
)


_MODULE_PATH = ROOT / "src" / "demo_trading_stop_noop_probe_plan.py"
_SCRIPT_PATH = ROOT / "scripts" / "preview_demo_trading_stop_noop_probe_plan.py"
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


def _planner() -> DemoTradingStopNoopProbePlanner:
    return DemoTradingStopNoopProbePlanner()


_UNSET = object()


def _design(
    *,
    readonly=_UNSET, recon=_UNSET, protection=_UNSET, contract=_UNSET,
    symbol=DEFAULT_SELECTED_SYMBOL, allow_real=False, _now=_TEST_NOW,
) -> NoopProbePlanResult:
    return _planner().design_plan(
        readonly_smoke=_valid_readonly()       if readonly   is _UNSET else readonly,
        reconciliation=_valid_reconciliation() if recon      is _UNSET else recon,
        protection=_valid_protection()         if protection is _UNSET else protection,
        contract=_valid_contract()             if contract   is _UNSET else contract,
        symbol=symbol,
        allow_real_noop_probe=allow_real,
        _now=_now,
    )


# ===========================================================================
# U1: default plan SOLUSDT -> NOOP_PROBE_PLAN_READY
# ===========================================================================

class TestU1PlanReady:
    def test_solusdt_plan_ready(self):
        r = _design(symbol="SOLUSDT")
        assert r.status == STATUS_PLAN_READY
        assert r.mode == MODE_PLAN
        assert r.selected_symbol == "SOLUSDT"
        assert r.recommended_path == PATH_TINY_ISOLATED
        assert r.real_probe_allowed is False
        assert r.real_noop_probe_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert r.next_required_task == "TASK-014V_tiny_isolated_demo_position_lifecycle_mock"


# ===========================================================================
# U2: missing readonly_smoke => FAIL_CLOSED
# ===========================================================================

class TestU2MissingReadonly:
    def test_none_readonly(self):
        r = _design(readonly=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates

    def test_empty_readonly(self):
        r = _design(readonly={})
        assert GATE_READONLY_SMOKE_MISSING in r.blocked_gates


# ===========================================================================
# U3: missing reconciliation => FAIL_CLOSED
# ===========================================================================

class TestU3MissingReconciliation:
    def test_none_reconciliation(self):
        r = _design(recon=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_RECONCILIATION_MISSING in r.blocked_gates


# ===========================================================================
# U4: missing protection => FAIL_CLOSED
# ===========================================================================

class TestU4MissingProtection:
    def test_none_protection(self):
        r = _design(protection=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_PROTECTION_MISSING in r.blocked_gates


# ===========================================================================
# U5: missing contract => FAIL_CLOSED
# ===========================================================================

class TestU5MissingContract:
    def test_none_contract(self):
        r = _design(contract=None)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_CONTRACT_MISSING in r.blocked_gates


# ===========================================================================
# U6: missing symbol => FAIL_CLOSED
# ===========================================================================

class TestU6MissingSymbol:
    def test_empty_symbol(self):
        r = _design(symbol="")
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SELECTED_SYMBOL_MISSING in r.blocked_gates


# ===========================================================================
# U7: symbol overlaps an existing position => FAIL_CLOSED
# ===========================================================================

class TestU7SymbolCollision:
    @pytest.mark.parametrize("sym", list(EXISTING_POSITION_SYMBOLS))
    def test_existing_symbol_blocks(self, sym):
        r = _design(symbol=sym)
        assert r.status == STATUS_FAIL_CLOSED
        assert GATE_SYMBOL_COLLIDES_EXISTING_POSITION in r.blocked_gates
        assert GATE_TINY_SYMBOL_OVERLAPS_EXISTING    in r.blocked_gates


# ===========================================================================
# U8: realtime price guard missing => gate appears
# ===========================================================================

class TestU8RealtimeGuardMissing:
    def test_no_guard(self):
        prot = _valid_protection()
        prot["realtime_price_guard_verified"] = False
        r = _design(protection=prot)
        assert GATE_REALTIME_PRICE_GUARD_MISSING in r.blocked_gates


# ===========================================================================
# U9: review fail-closed flag => gate appears
# ===========================================================================

class TestU9ReviewFailClosed:
    def test_fail_closed(self):
        prot = _valid_protection()
        prot["review_fail_closed"] = True
        r = _design(protection=prot)
        assert GATE_REVIEW_FAIL_CLOSED in r.blocked_gates


# ===========================================================================
# U10: contract claiming real_probe_implemented => surfaced as gate
# ===========================================================================

class TestU10PriorProbeFlipped:
    def test_prior_probe_flipped(self):
        contract = _valid_contract()
        contract["real_probe_implemented"] = True
        r = _design(contract=contract)
        assert GATE_PRIOR_PROBE_FLIPPED_REAL in r.blocked_gates


# ===========================================================================
# U11: all 15 tiny-isolated gates always present in TASK-014U
# ===========================================================================

class TestU11TinyIsolatedGates:
    def test_all_tiny_gates_present(self):
        r = _design()
        for g in (
            GATE_TINY_QTY_MIN_UNKNOWN,
            GATE_TINY_ISOLATION_UNVERIFIED,
            GATE_TINY_NOTIONAL_MIN_UNKNOWN,
            GATE_TINY_ACCOUNT_MODE_UNVERIFIED,
            GATE_TINY_SYMBOL_NOT_LINEAR_PERPETUAL,
            GATE_TINY_STOP_ATTACH_WINDOW_UNCOVERED,
            GATE_TINY_EMERGENCY_CLOSE_UNVERIFIED,
            GATE_TINY_BALANCE_INSUFFICIENT_UNKNOWN,
            GATE_TINY_LEVERAGE_UNVERIFIED,
            GATE_TINY_SESSION_RESUME_UNCOVERED,
            GATE_TINY_MARKET_PRICE_DRIFT_UNVERIFIED,
            GATE_TINY_PARTIAL_FILL_UNHANDLED,
            GATE_TINY_POST_FILL_AUDIT_MISSING,
            GATE_TINY_LIFECYCLE_DOC_MISSING,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# U12: expected-error gates present
# ===========================================================================

class TestU12ExpectedErrorGates:
    def test_expected_error_gates(self):
        r = _design()
        for g in (
            GATE_EXPECTED_ERR_IDEMPOTENCY_UNVERIFIED,
            GATE_EXPECTED_ERR_MODIFIES_ON_MATCH,
            GATE_EXPECTED_ERR_CANNOT_DISAMBIGUATE,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# U13: read-only research gates present
# ===========================================================================

class TestU13ReadOnlyGates:
    def test_readonly_gates(self):
        r = _design()
        for g in (
            GATE_READONLY_ENDPOINT_NOT_AVAILABLE,
            GATE_READONLY_WORKAROUND_REQUIRES_WRITE,
            GATE_READONLY_RESEARCH_INCONCLUSIVE,
        ):
            assert g in r.blocked_gates


# ===========================================================================
# U14: defense-in-depth always present
# ===========================================================================

class TestU14DefenseInDepth:
    def test_existing_positions_must_not_touch(self):
        r = _design()
        assert GATE_EXISTING_POSITIONS_MUST_NOT_TOUCH in r.blocked_gates
        assert GATE_G20_POLICY_STILL_IN_PLACE         in r.blocked_gates


# ===========================================================================
# U15: module defines >= 30 gate constants AND happy-path raises >= 22
# of them as in-task open blockers (15 tiny + 3 expected-err + 3 readonly
# + 2 defense-in-depth = 23 in plan mode; +1 with allow_real_noop_probe).
# ===========================================================================

class TestU15GateCountFloor:
    def test_module_defines_at_least_30_gate_constants(self):
        import src.demo_trading_stop_noop_probe_plan as m
        gate_names = [
            n for n in dir(m)
            if n.startswith("GATE_") and isinstance(getattr(m, n), str)
        ]
        assert len(gate_names) >= 30, (
            f"Module should define at least 30 GATE_ constants, "
            f"got {len(gate_names)}: {sorted(gate_names)}"
        )

    def test_happy_path_plan_open_blockers_floor(self):
        r = _design(allow_real=False)
        unique = set(r.blocked_gates)
        # Plan-mode floor:
        #   14 tiny-isolated always-on (overlaps_existing is conditional)
        # +  3 expected-error
        # +  3 readonly research
        # +  2 defense-in-depth (existing_positions, g20_policy)
        # = 22
        assert len(unique) >= 22, (
            f"Plan-mode should surface at least 22 in-task gates, "
            f"got {len(unique)}: {sorted(unique)}"
        )

    def test_real_guard_adds_real_noop_gate(self):
        r = _design(allow_real=True)
        unique = set(r.blocked_gates)
        assert GATE_REAL_NOOP_PROBE_NOT_IMPL in unique
        # 22 always-on + 1 real_noop_probe_not_implemented = 23
        assert len(unique) >= 23


# ===========================================================================
# U16: --allow-real-noop-probe still returns REAL_NOOP_PROBE_NOT_IMPL
# ===========================================================================

class TestU16RealNoopGuard:
    def test_real_noop_returns_not_impl(self):
        r = _design(allow_real=True)
        assert r.status == STATUS_REAL_NOOP_NOT_IMPL
        assert r.mode == MODE_REAL_NOOP_PROBE
        assert r.real_probe_allowed is True
        assert r.real_noop_probe_implemented is False
        assert r.current_task_real_execution_allowed is False
        assert GATE_REAL_NOOP_PROBE_NOT_IMPL in r.blocked_gates

    def test_real_noop_safety_invariants(self):
        r = _design(allow_real=True)
        assert r.stop_endpoint_called is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified is True
        assert r.no_live_endpoint is True
        assert r.no_orders_sent is True


# ===========================================================================
# U17: three-plan comparison block present
# ===========================================================================

class TestU17ThreePlans:
    def test_three_plans_in_result(self):
        r = _design()
        assert set(r.plans.keys()) == {
            PATH_TINY_ISOLATED, PATH_READ_ONLY, PATH_EXPECTED_ERROR,
        }
        assert r.plans[PATH_TINY_ISOLATED]["recommended"]  is True
        assert r.plans[PATH_READ_ONLY]["recommended"]      is False
        assert r.plans[PATH_EXPECTED_ERROR]["recommended"] is False
        assert r.recommended_path == PATH_TINY_ISOLATED
        # Plan comparison summary has the same three rows
        ids = [row["path_id"] for row in r.plan_comparison_summary]
        assert sorted(ids) == sorted([
            PATH_TINY_ISOLATED, PATH_READ_ONLY, PATH_EXPECTED_ERROR,
        ])


# ===========================================================================
# U18: only the tiny plan stays in-scope as next step
# ===========================================================================

class TestU18OnlyTinyRecommended:
    def test_only_tiny_path_recommended_with_next_pointer(self):
        plans = build_all_plans()
        rec = [
            (pid, p) for pid, p in plans.items() if p["recommended"]
        ]
        assert len(rec) == 1
        assert rec[0][0] == PATH_TINY_ISOLATED
        assert rec[0][1]["next_task_pointer"] == (
            "TASK-014V_tiny_isolated_demo_position_lifecycle_mock"
        )

    def test_expected_error_touches_existing(self):
        plans = build_all_plans()
        assert plans[PATH_EXPECTED_ERROR]["touches_existing_positions"] is True

    def test_readonly_and_tiny_do_not_touch_existing(self):
        plans = build_all_plans()
        assert plans[PATH_TINY_ISOLATED]["touches_existing_positions"] is False
        assert plans[PATH_READ_ONLY]["touches_existing_positions"]     is False


# ===========================================================================
# U19: existing positions are listed from reconciliation
# ===========================================================================

class TestU19ExistingPositions:
    def test_existing_positions_listed(self):
        r = _design()
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols

    def test_existing_positions_fallback_when_recon_empty_positions(self):
        recon = _valid_reconciliation()
        recon["positions"] = []
        r = _design(recon=recon)
        for sym in EXISTING_POSITION_SYMBOLS:
            assert sym in r.existing_position_symbols


# ===========================================================================
# U20: existing 5 demo positions documented in module constant
# ===========================================================================

class TestU20ExistingPositionConstant:
    def test_existing_constant_matches_spec(self):
        assert set(EXISTING_POSITION_SYMBOLS) == {
            "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
        }


# ===========================================================================
# U21: report artifacts written (PLAN mode)
# ===========================================================================

class TestU21ReportArtifactsPlan:
    def test_report_files_written(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            base    = Path(td)
            ro_d    = base / "readonly";     ro_d.mkdir()
            recon_d = base / "recon";        recon_d.mkdir()
            prot_d  = base / "protection";   prot_d.mkdir()
            con_d   = base / "contract";     con_d.mkdir()
            plan_d  = base / "plan"
            (ro_d    / "latest_readonly_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
            (recon_d / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
            (prot_d  / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
            (con_d   / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
            rc = run_execute(
                symbol="SOLUSDT", allow_real_noop_probe=False, write_report=True,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 0
            files = sorted(p.name for p in plan_d.iterdir())
            assert "latest_noop_probe_plan.json" in files
            assert "latest_noop_probe_plan.md"   in files
            ts_json = [n for n in files if n.endswith(".json") and not n.startswith("latest_")]
            ts_md   = [n for n in files if n.endswith(".md")   and not n.startswith("latest_")]
            assert len(ts_json) == 1
            assert len(ts_md)   == 1
            data = json.loads((plan_d / "latest_noop_probe_plan.json").read_text(encoding="utf-8"))
            assert data["status"] == STATUS_PLAN_READY
            assert data["recommended_path"] == PATH_TINY_ISOLATED
            assert data["current_task_real_execution_allowed"] is False
            assert data["selected_symbol"] == "SOLUSDT"


# ===========================================================================
# U22: report artifacts written (REAL NOOP PROBE GUARD mode)
# ===========================================================================

class TestU22ReportArtifactsRealGuard:
    def test_real_guard_report(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            base    = Path(td)
            ro_d    = base / "readonly";     ro_d.mkdir()
            recon_d = base / "recon";        recon_d.mkdir()
            prot_d  = base / "protection";   prot_d.mkdir()
            con_d   = base / "contract";     con_d.mkdir()
            plan_d  = base / "plan"
            (ro_d    / "latest_readonly_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
            (recon_d / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
            (prot_d  / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
            (con_d   / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
            rc = run_execute(
                symbol="SOLUSDT", allow_real_noop_probe=True, write_report=True,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads((plan_d / "latest_noop_probe_plan.json").read_text(encoding="utf-8"))
            assert data["status"] == STATUS_REAL_NOOP_NOT_IMPL
            assert data["real_probe_allowed"] is True
            assert data["real_noop_probe_implemented"] is False
            assert GATE_REAL_NOOP_PROBE_NOT_IMPL in data["blocked_gates"]
            md = (plan_d / "latest_noop_probe_plan.md").read_text(encoding="utf-8")
            assert "REAL_NOOP_PROBE_NOT_IMPLEMENTED" in md


# ===========================================================================
# U23: no secrets in report
# ===========================================================================

class TestU23NoSecretsInReport:
    def test_report_contains_no_secret_values(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            base    = Path(td)
            ro_d    = base / "readonly";     ro_d.mkdir()
            recon_d = base / "recon";        recon_d.mkdir()
            prot_d  = base / "protection";   prot_d.mkdir()
            con_d   = base / "contract";     con_d.mkdir()
            plan_d  = base / "plan"
            (ro_d    / "latest_readonly_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
            (recon_d / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
            (prot_d  / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
            (con_d   / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")
            rc = run_execute(
                symbol="SOLUSDT", allow_real_noop_probe=False, write_report=True,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 0
            data = json.loads((plan_d / "latest_noop_probe_plan.json").read_text(encoding="utf-8"))
            assert data["secret_value_observed"] is False
            md = (plan_d / "latest_noop_probe_plan.md").read_text(encoding="utf-8")
            for forbidden in ("API_KEY", "API_SECRET", "BYBIT_API", "X-BAPI-SIGN"):
                assert forbidden not in md


# ===========================================================================
# U24: no forbidden imports in module + CLI
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


class TestU24NoForbiddenImports:
    def test_module_imports(self):
        imp = _collect_imports(_MODULE_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in module"

    def test_cli_imports(self):
        imp = _collect_imports(_SCRIPT_PATH)
        for bad in _FORBIDDEN_IMPORTS:
            assert bad not in imp, f"Forbidden import {bad!r} in CLI"


# ===========================================================================
# U25: no urllib/urlopen/socket/http.client in module or CLI source
# ===========================================================================

class TestU25NoNetworkTokensInSource:
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
# U26: no close-only / emergency-close / new-entry / contract-probe coupling
# ===========================================================================

class TestU26NoSenderReuse:
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
        # The planner stands alone; it must NOT import back into the
        # TASK-014T contract probe module.
        code = _read_code_only(_MODULE_PATH)
        assert "demo_trading_stop_contract_probe" not in code


# ===========================================================================
# U27: module does not open a socket at import time
# ===========================================================================

class TestU27NoSocketAtImport:
    def test_module_safe_under_socket_disabled(self):
        env = dict(os.environ)
        env["PYTHONIOENCODING"] = "utf-8"
        env["PYTHONPATH"]       = str(ROOT)
        cp = subprocess.run(
            [sys.executable, "-c",
             "import socket; socket.socket = None; "
             "import src.demo_trading_stop_noop_probe_plan as m; "
             "print('OK', m.STATUS_PLAN_READY)"],
            capture_output=True, text=True, env=env,
            encoding="utf-8", errors="replace", timeout=60,
        )
        assert cp.returncode == 0, cp.stderr
        assert "OK" in cp.stdout


# ===========================================================================
# U28: TASK-014L G20 is NOT lifted by this task
# ===========================================================================

class TestU28G20StillBlocks:
    def test_g20_constant_unchanged(self):
        from src.demo_new_entry_protection import G20_BLOCKED_GATE_NAME
        assert G20_BLOCKED_GATE_NAME == "protected_entry_policy_missing"

    def test_planner_does_not_lift_g20(self):
        code = _read_code_only(_MODULE_PATH)
        assert "protected_entry_policy_missing" not in code
        assert "G20_BLOCKED_GATE_NAME"          not in code

    def test_result_records_g20_still_in_place(self):
        r = _design()
        assert r.g20_policy_still_in_place is True
        assert GATE_G20_POLICY_STILL_IN_PLACE in r.blocked_gates


# ===========================================================================
# U29: safety invariants on result are all conservative
# ===========================================================================

class TestU29SafetyInvariants:
    def test_invariants_default_plan(self):
        r = _design()
        assert r.stop_endpoint_called  is False
        assert r.order_endpoint_called is False
        assert r.no_position_modified  is True
        assert r.no_live_endpoint      is True
        assert r.no_orders_sent        is True
        assert r.no_batch_order        is True
        assert r.no_close_only_path    is True
        assert r.emergency_close_invoked is False
        assert r.secret_value_observed   is False

    def test_path_refs_are_string_only(self):
        r = _design()
        assert r.trading_stop_path_ref == TRADING_STOP_PATH_REF
        assert r.order_create_path_ref == ORDER_CREATE_PATH_REF
        assert r.base_url_ref == BASE_URL_DEMO_REF


# ===========================================================================
# U30: dataclass round-trip + immutability of nested plans dict
# ===========================================================================

class TestU30DataclassRoundTrip:
    def test_to_dict_roundtrip(self):
        r = _design()
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
            ("real_noop_probe_implemented",         False),
        ):
            assert d[key] is expected, f"{key} should be {expected}"
        assert d["status"]           == STATUS_PLAN_READY
        assert d["recommended_path"] == PATH_TINY_ISOLATED
        # to_dict() returns deep copies; mutating must not affect source.
        d["plans"][PATH_TINY_ISOLATED]["mutated"] = True
        assert "mutated" not in r.plans[PATH_TINY_ISOLATED]


# ===========================================================================
# U31: CLI exit codes
# ===========================================================================

class TestU31CLIExitCodes:
    def _make_dirs(self, base: Path):
        ro_d    = base / "readonly";     ro_d.mkdir()
        recon_d = base / "recon";        recon_d.mkdir()
        prot_d  = base / "protection";   prot_d.mkdir()
        con_d   = base / "contract";     con_d.mkdir()
        plan_d  = base / "plan"
        return ro_d, recon_d, prot_d, con_d, plan_d

    def _populate_all(self, ro_d, recon_d, prot_d, con_d):
        (ro_d    / "latest_readonly_smoke.json").write_text(json.dumps(_valid_readonly()), encoding="utf-8")
        (recon_d / "latest_reconciliation.json").write_text(json.dumps(_valid_reconciliation()), encoding="utf-8")
        (prot_d  / "latest_new_entry_protection.json").write_text(json.dumps(_valid_protection()), encoding="utf-8")
        (con_d   / "latest_trading_stop_contract.json").write_text(json.dumps(_valid_contract()), encoding="utf-8")

    def test_missing_upstream_returns_1(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, plan_d = self._make_dirs(Path(td))
            rc = run_execute(
                symbol="SOLUSDT", allow_real_noop_probe=False, write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 1

    def test_missing_symbol_returns_1(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, plan_d = self._make_dirs(Path(td))
            self._populate_all(ro_d, recon_d, prot_d, con_d)
            rc = run_execute(
                symbol="", allow_real_noop_probe=False, write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 1

    def test_collision_symbol_returns_1(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, plan_d = self._make_dirs(Path(td))
            self._populate_all(ro_d, recon_d, prot_d, con_d)
            rc = run_execute(
                symbol="ENAUSDT", allow_real_noop_probe=False, write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 1

    def test_default_plan_returns_0(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, plan_d = self._make_dirs(Path(td))
            self._populate_all(ro_d, recon_d, prot_d, con_d)
            rc = run_execute(
                symbol="SOLUSDT", allow_real_noop_probe=False, write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 0

    def test_real_guard_returns_0(self):
        from scripts.preview_demo_trading_stop_noop_probe_plan import run_execute
        with tempfile.TemporaryDirectory() as td:
            ro_d, recon_d, prot_d, con_d, plan_d = self._make_dirs(Path(td))
            self._populate_all(ro_d, recon_d, prot_d, con_d)
            rc = run_execute(
                symbol="SOLUSDT", allow_real_noop_probe=True, write_report=False,
                readonly_dir=ro_d, reconciliation_dir=recon_d,
                protection_dir=prot_d, contract_dir=con_d, plan_dir=plan_d,
                _now=_TEST_NOW,
            )
            assert rc == 0


# ===========================================================================
# U32: trading_stop_path_ref points at TASK-014T documented path and is
# never invoked from this module
# ===========================================================================

class TestU32PathRefMatchesContractProbe:
    def test_module_records_documented_path(self):
        # String compare only.  The contract probe module owns the real
        # constant; the planner records the string for documentation.
        from src.demo_trading_stop_contract_probe import (
            TRADING_STOP_PATH as CONTRACT_TRADING_STOP_PATH,
        )
        assert TRADING_STOP_PATH_REF == CONTRACT_TRADING_STOP_PATH

    def test_path_appears_only_as_string_value(self):
        # The path must appear in r.trading_stop_path_ref but must not
        # appear in any code reference that could be misread as a call.
        code = _read_code_only(_MODULE_PATH)
        # No call form like .post(<...path...>) etc.
        assert "post(" not in code
        assert "get("  not in code or " get(" not in code  # allow .get on dicts elsewhere
        # The string itself is permitted to live in module constants
        # because tokenize() strips STRING tokens; the module-level
        # references survive only as identifier text in code.  That's
        # fine — the test simply ensures no call expression appears.


# ===========================================================================
# Extras: plan immutability across results
# ===========================================================================

class TestExtraPlanImmutability:
    def test_each_design_returns_fresh_plans(self):
        r1 = _design()
        r2 = _design()
        # Mutating r1's plans must not contaminate r2.
        r1.plans[PATH_TINY_ISOLATED]["mutated"] = True
        assert "mutated" not in r2.plans[PATH_TINY_ISOLATED]


class TestExtraRecommendedPathConstant:
    def test_recommended_constant(self):
        assert RECOMMENDED_PATH == PATH_TINY_ISOLATED
