"""TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY -- tests for authorized execution qty wiring.

Covers:
    * Identity / chain-break / upstream task markers.
    * Default fail-closed when instrument rules report is missing.
    * Default fail-closed when cap-escalation gate report is missing.
    * ESCALATION_AUTHORIZED -> wiring resolves execution_qty=candidate_qty.
    * ESCALATION_NOT_AUTHORIZED -> wiring keeps execution_qty empty
      (no silent fallback to qty=0.01 for execute mode).
    * ESCALATION_REJECTED_NOTIONAL_OVER_CAP -> wiring rejects.
    * ESCALATION_NOT_REQUIRED -> WIRING_NOT_REQUIRED_ORIGINAL_PASSES.
    * BM ``ExecutionReport`` surfaces the new 6 wiring fields when the
      ``authorized_execution_qty_wiring`` kwarg is supplied, and keeps
      them at safe defaults otherwise.
    * Network / order surface invariants: no order endpoint call, no
      order sent, no urllib import, no third-party HTTP clients, no
      main / src.risk / BybitExecutor / live secret env names referenced.
    * Global ``TINY_QTY_CAP_SOL`` / ``TINY_SIZE_CAP_USDT`` /
      ``PROTECTED_SYMBOLS`` invariants are not mutated by the wiring.
    * Report writer emits 4 files; JSON round-trip works.
"""

from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src import demo_only_tiny_execution_adapter as bh
from src import (
    demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring as bm_wire,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as bm_ce,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_execution as bm,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _build_response(
    *,
    symbol: str = "SOLUSDT",
    min_order_qty: str = "0.1",
    qty_step: str = "0.1",
    min_notional_value: str = "5",
    max_mkt_order_qty: str | None = "12000",
    tick_size: str | None = "0.010",
    status: str = "Trading",
) -> dict:
    entry: dict = {
        "symbol": symbol,
        "status": status,
        "lotSizeFilter": {
            "minOrderQty": min_order_qty,
            "qtyStep": qty_step,
            "minNotionalValue": min_notional_value,
        },
    }
    if max_mkt_order_qty is not None:
        entry["lotSizeFilter"]["maxMktOrderQty"] = max_mkt_order_qty
    if tick_size is not None:
        entry["priceFilter"] = {"tickSize": tick_size}
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {"list": [entry]},
    }


def _ir_report(mark_price: str = "100", **kwargs) -> bm_ir.InstrumentRulesReport:
    parsed = _build_response(**kwargs)
    return bm_ir.run_instrument_rules_discovery(
        mark_price=mark_price, pre_parsed_response=parsed
    )


def _authorized_request(
    candidate_qty: str = "0.1",
    *,
    flag: bool = True,
    marker_ok: bool = True,
    **overrides,
) -> bm_ce.EscalationAuthorizationRequest:
    return bm_ce.EscalationAuthorizationRequest(
        proposed_qty=candidate_qty,
        explicit_demo_min_qty_cap_authorization_flag=flag,
        explicit_demo_min_qty_cap_authorization_marker=(
            bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
            if marker_ok
            else ""
        ),
        **overrides,
    )


def _gate_report(
    *,
    mark_price: str = "100",
    ir_kwargs: dict | None = None,
    request: bm_ce.EscalationAuthorizationRequest | None = None,
    notional_cap: Decimal | str | None = None,
) -> bm_ce.CapEscalationGateReport:
    ir = _ir_report(mark_price=mark_price, **(ir_kwargs or {}))
    return bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=request,
        max_demo_min_qty_notional_cap_usdt=notional_cap,
    )


# ---------------------------------------------------------------------------
# Identity / chain-break / upstream
# ---------------------------------------------------------------------------


def test_task_id_and_identity_constants():
    assert bm_wire.TASK_ID == "TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY"
    assert bm_wire.IDENTITY == (
        "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-AUTHORIZED-EXECUTION-QTY-WIRING"
    )
    assert (
        bm_wire.IMPLEMENTATION_PATH_PHASE
        == "tiny_order_authorized_execution_qty_wiring"
    )
    assert bm_wire.IS_REVIEW_CHAIN_SUFFIX is False
    assert (
        bm_wire.NEXT_REQUIRED_TASK
        == "TASK-014BN_demo_only_tiny_execution_postfill_audit"
    )


def test_next_required_task_passes_bh_non_review_chain_suffix_check():
    bh.assert_next_task_is_not_review_chain_suffix(bm_wire.NEXT_REQUIRED_TASK)


def test_upstream_tasks_include_cap_escalation_gate_and_min_qty_fix():
    assert bm_wire.UPSTREAM_TASKS == (
        "TASK-014BH",
        "TASK-014BM",
        "TASK-014BM_FIX",
        "TASK-014BM_MIN_QTY_FIX",
        "TASK-014BM_CAP_ESCALATION_GATE",
    )


def test_immutable_locks():
    assert bm_wire.ALLOWED_ENVIRONMENT == "bybit_demo"
    assert bm_wire.ALLOWED_SYMBOL == "SOLUSDT"
    assert bm_wire.ALLOWED_SIDE == "Buy"
    assert bm_wire.ALLOWED_ORDER_TYPE == "Market"
    assert bm_wire.ALLOWED_TIME_IN_FORCE == "IOC"
    assert bm_wire.ALLOWED_MAX_ORDER_COUNT == 1
    assert bm_wire.ORIGINAL_PACKET_QTY == "0.01"
    assert bm_wire.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT == Decimal("20")


# ---------------------------------------------------------------------------
# Default fail-closed paths
# ---------------------------------------------------------------------------


def test_missing_instrument_rules_report_rejects_no_fallback():
    gate = _gate_report(request=_authorized_request("0.1"))
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=None, cap_escalation_report=gate
    )
    r = report.resolution
    assert r.status == bm_wire.STATUS_WIRING_REJECTED_RULES_NOT_LOADED
    assert r.execution_qty_source == bm_wire.EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
    assert r.execution_qty == ""
    assert r.execution_notional_estimate == ""
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert report.network_attempted is False
    assert report.order_endpoint_called is False


def test_missing_cap_escalation_report_rejects_no_fallback():
    ir = _ir_report()
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=None
    )
    r = report.resolution
    assert r.status == bm_wire.STATUS_WIRING_REJECTED_GATE_MISSING
    assert r.execution_qty_source == bm_wire.EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
    assert r.execution_qty == ""
    assert r.execution_notional_estimate == ""
    assert r.cap_gate_status == ""


def test_both_missing_still_rejects_rules_not_loaded_first():
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=None, cap_escalation_report=None
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_REJECTED_RULES_NOT_LOADED
    )
    assert report.resolution.execution_qty == ""


# ---------------------------------------------------------------------------
# Authorized path
# ---------------------------------------------------------------------------


def test_authorized_wires_execution_qty_to_candidate_qty():
    ir = _ir_report(mark_price="100")
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=_authorized_request("0.1"),
    )
    assert gate.decision.status == bm_ce.STATUS_ESCALATION_AUTHORIZED

    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    r = report.resolution
    assert r.status == bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY
    assert (
        r.execution_qty_source
        == bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert r.execution_qty == "0.1"
    assert Decimal(r.execution_notional_estimate) == Decimal("10.0")
    assert r.cap_gate_status == bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert r.cap_escalated_demo_only is True
    assert r.explicit_demo_min_qty_cap_authorized is True
    assert r.original_packet_qty == "0.01"
    assert r.qty_0_01_confirmed_invalid is True
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert report.allowed_environment == "bybit_demo"
    assert report.allowed_symbol == "SOLUSDT"
    assert report.cap_gate_status == bm_ce.STATUS_ESCALATION_AUTHORIZED


def test_not_authorized_does_not_fall_back_to_0_01():
    ir = _ir_report()
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=bm_ce.EscalationAuthorizationRequest(proposed_qty="0.1"),
    )
    assert gate.decision.status == bm_ce.STATUS_ESCALATION_NOT_AUTHORIZED

    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    r = report.resolution
    assert r.status == bm_wire.STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE
    assert (
        r.execution_qty_source
        == bm_wire.EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
    )
    assert r.execution_qty == ""
    assert r.execution_notional_estimate == ""
    # Original packet qty surfaces visibly but is NOT the execution qty.
    assert r.original_packet_qty == "0.01"
    assert r.qty_0_01_confirmed_invalid is True


def test_over_cap_rejects_wiring():
    ir = _ir_report(mark_price="250")  # 0.1 * 250 = 25 > 20 cap
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=_authorized_request("0.1"),
    )
    assert gate.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP

    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    r = report.resolution
    assert r.status == bm_wire.STATUS_WIRING_REJECTED_GATE_OVER_CAP
    assert (
        r.execution_qty_source
        == bm_wire.EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
    )
    assert r.execution_qty == ""


def test_escalation_not_required_when_original_tiny_cap_passes():
    ir = _ir_report(
        mark_price="100",
        min_order_qty="0.01",
        qty_step="0.01",
        min_notional_value="0",
    )
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=_authorized_request("0.01"),
    )
    assert gate.decision.status == bm_ce.STATUS_ESCALATION_NOT_REQUIRED

    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    r = report.resolution
    assert r.status == bm_wire.STATUS_WIRING_NOT_REQUIRED_ORIGINAL_PASSES
    assert r.execution_qty_source == bm_wire.EXECUTION_QTY_SOURCE_NONE
    # Wiring is not required, so execution_qty stays empty -- BM will
    # plan against the unchanged BL packet qty (which the original tiny
    # cap path already accepts).
    assert r.execution_qty == ""


def test_qty_mismatch_in_gate_blocks_wiring():
    ir = _ir_report()
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=_authorized_request("0.05"),  # != candidate_qty 0.1
    )
    assert gate.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_QTY_MISMATCH

    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    r = report.resolution
    assert r.status == bm_wire.STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE
    assert r.execution_qty == ""


# ---------------------------------------------------------------------------
# BM ExecutionReport integration
# ---------------------------------------------------------------------------


def test_bm_execution_report_default_keeps_wiring_fields_at_safe_defaults():
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS, existing_positions=()
    )
    assert report.wiring_loaded is False
    assert report.wiring_status == ""
    assert report.original_packet_qty == ""
    assert report.execution_qty_source == ""
    assert report.execution_qty_resolved == ""
    assert report.execution_notional_estimate_resolved == ""
    # ExecutionReport.to_dict() includes all 6 new fields.
    d = report.to_dict()
    for key in (
        "wiring_loaded",
        "wiring_status",
        "original_packet_qty",
        "execution_qty_source",
        "execution_qty_resolved",
        "execution_notional_estimate_resolved",
    ):
        assert key in d, key


def test_bm_execution_report_surfaces_authorized_wiring_fields():
    ir = _ir_report(mark_price="100")
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=_authorized_request("0.1"),
    )
    wiring = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )

    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS,
        existing_positions=(),
        instrument_rules=ir,
        cap_escalation=gate,
        authorized_execution_qty_wiring=wiring,
    )
    assert report.wiring_loaded is True
    assert report.wiring_status == bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY
    assert report.original_packet_qty == "0.01"
    assert (
        report.execution_qty_source
        == bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert report.execution_qty_resolved == "0.1"
    assert Decimal(report.execution_notional_estimate_resolved) == Decimal("10.0")
    # The new fields never trip the order surface.
    assert report.order_endpoint_called is False
    assert report.order_sent is False
    assert report.network_attempted is False


def test_bm_execution_report_surfaces_rejected_wiring_with_no_execution_qty():
    ir = _ir_report()
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=bm_ce.EscalationAuthorizationRequest(proposed_qty="0.1"),
    )
    wiring = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS,
        existing_positions=(),
        instrument_rules=ir,
        cap_escalation=gate,
        authorized_execution_qty_wiring=wiring,
    )
    assert report.wiring_loaded is True
    assert (
        report.wiring_status
        == bm_wire.STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE
    )
    assert (
        report.execution_qty_source
        == bm_wire.EXECUTION_QTY_SOURCE_REJECTED_NO_FALLBACK
    )
    assert report.execution_qty_resolved == ""
    assert report.execution_notional_estimate_resolved == ""


# ---------------------------------------------------------------------------
# Network / order surface invariants
# ---------------------------------------------------------------------------


_WIRING_SOURCE_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring.py"
)


def _iter_string_constants_excluding_docstrings(tree: ast.AST):
    """Yield string-constant nodes that are NOT module/class/function docstrings."""

    docstring_node_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)
        ):
            body = getattr(node, "body", None) or []
            if (
                body
                and isinstance(body[0], ast.Expr)
                and isinstance(body[0].value, ast.Constant)
                and isinstance(body[0].value.value, str)
            ):
                docstring_node_ids.add(id(body[0].value))
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.Constant)
            and isinstance(node.value, str)
            and id(node) not in docstring_node_ids
        ):
            yield node


def test_source_imports_no_network_or_third_party_clients():
    src = _WIRING_SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    banned = {
        "requests",
        "pybit",
        "aiohttp",
        "httpx",
        "websocket",
        "websockets",
        "urllib",
        "urllib.request",
        "http.client",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in banned, alias.name
        elif isinstance(node, ast.ImportFrom):
            assert node.module not in banned, node.module


def test_source_does_not_reference_main_risk_or_bybit_executor():
    src = _WIRING_SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    forbidden_attr = {"BybitExecutor"}
    forbidden_module = {
        "main",
        "src.risk",
        "src.executors.bybit",
    }
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id not in forbidden_attr, node.id
        if isinstance(node, ast.Attribute):
            assert node.attr not in forbidden_attr, node.attr
        if isinstance(node, ast.ImportFrom):
            assert node.module not in forbidden_module, node.module
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden_module, alias.name


def test_source_does_not_access_os_environ_or_getenv():
    src = _WIRING_SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in {"environ", "getenv"}
            ):
                pytest.fail(
                    f"unexpected os.{node.attr} reference in wiring module"
                )


def test_source_does_not_reference_live_secret_env_names():
    src = _WIRING_SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    forbidden_strings = {
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
    }
    for node in _iter_string_constants_excluding_docstrings(tree):
        assert (
            node.value not in forbidden_strings
        ), f"unexpected secret env name reference {node.value!r}"


def test_source_does_not_reference_order_create_or_live_hosts():
    src = _WIRING_SOURCE_PATH.read_text(encoding="utf-8")
    tree = ast.parse(src)
    # Each forbidden token may legitimately appear at most once as a
    # *string-constant* outside of docstrings -- namely, as an entry in
    # the FORBIDDEN_URL_TOKENS denylist. Anywhere else (any other string
    # literal, any attribute access, any URL constructor) is a contract
    # violation.
    for token in bm_wire.FORBIDDEN_URL_TOKENS:
        hits = [
            node
            for node in _iter_string_constants_excluding_docstrings(tree)
            if node.value == token
        ]
        assert len(hits) <= 1, token
    # api-demo.bybit.com is NEVER referenced by this wiring module.
    for node in _iter_string_constants_excluding_docstrings(tree):
        assert "api-demo.bybit.com" not in node.value


# ---------------------------------------------------------------------------
# Invariants on shared BH constants
# ---------------------------------------------------------------------------


def test_wiring_does_not_mutate_global_tiny_caps():
    # Run the wiring on the authorized path...
    ir = _ir_report(mark_price="100")
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=_authorized_request("0.1"),
    )
    bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    # ...and confirm BH globals are still at their original values.
    assert bh.TINY_QTY_CAP_SOL == Decimal("0.05")
    assert bh.TINY_SIZE_CAP_USDT == Decimal("5")
    assert bh.TINY_QTY_STEP_SOL == Decimal("0.01")
    assert bh.PROTECTED_SYMBOLS == frozenset(
        {"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"}
    )


# ---------------------------------------------------------------------------
# Report writer round-trip
# ---------------------------------------------------------------------------


def test_report_writer_emits_4_files_and_round_trips():
    import shutil

    ir = _ir_report()
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=_authorized_request("0.1"),
    )
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )
    # Use a project-local tmp dir to side-step Windows mixed-locale
    # pytest tmp_path issues. Cleaned up at the end.
    out_root = Path(__file__).resolve().parents[2] / "outputs" / "_test_tmp_bm_wiring"
    if out_root.exists():
        shutil.rmtree(out_root)
    out_root.mkdir(parents=True, exist_ok=True)
    try:
        paths = bm_wire.write_report(report, output_dir=out_root)
        assert set(paths.keys()) == {
            "latest_json",
            "latest_md",
            "stamped_json",
            "stamped_md",
        }
        for path in paths.values():
            assert path.exists()
        payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
        assert payload["task_id"] == "TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY"
        assert (
            payload["resolution"]["status"]
            == bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY
        )
        assert payload["resolution"]["execution_qty"] == "0.1"
        assert payload["order_endpoint_called"] is False
        assert payload["order_sent"] is False
        assert payload["network_attempted"] is False
    finally:
        shutil.rmtree(out_root, ignore_errors=True)


# ---------------------------------------------------------------------------
# Side / protected symbol locks (defense-in-depth against tampered gate)
# ---------------------------------------------------------------------------


def _tampered_gate(
    *,
    status: str = bm_ce.STATUS_ESCALATION_AUTHORIZED,
    cap_escalated_demo_only: bool = True,
    explicit: bool = True,
    candidate_qty: str = "0.1",
    candidate_notional: str = "10",
    environment: str = "bybit_demo",
    symbol: str = "SOLUSDT",
    side: str = "Buy",
    proposed_qty: str = "0.1",
    original_passed: bool = False,
) -> bm_ce.CapEscalationGateReport:
    """Build a synthetic gate report directly to exercise wiring locks."""

    decision = bm_ce.EscalationAuthorizationDecision(
        status=status,
        authorized=(status == bm_ce.STATUS_ESCALATION_AUTHORIZED),
        original_tiny_cap_passed=original_passed,
        exchange_min_qty_cap_escalation_required=not original_passed,
        explicit_demo_min_qty_cap_authorized=explicit,
        cap_escalated_demo_only=cap_escalated_demo_only,
        candidate_qty=candidate_qty,
        candidate_notional=candidate_notional,
        proposed_qty=proposed_qty,
        mark_price_used="100",
        tiny_qty_cap_sol="0.05",
        tiny_size_cap_usdt="5",
        max_demo_min_qty_notional_cap_usdt="20",
        environment=environment,
        symbol=symbol,
        side=side,
        order_type="Market",
        time_in_force="IOC",
        max_order_count=1,
        reason="synthetic",
    )
    request = bm_ce.EscalationAuthorizationRequest(
        proposed_qty=proposed_qty,
        environment=environment,
        symbol=symbol,
        side=side,
    )
    return bm_ce.CapEscalationGateReport(
        task_id=bm_ce.TASK_ID,
        identity=bm_ce.IDENTITY,
        phase=bm_ce.IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=bm_ce.UPSTREAM_TASKS,
        next_required_task=bm_ce.NEXT_REQUIRED_TASK,
        is_review_chain_suffix=bm_ce.IS_REVIEW_CHAIN_SUFFIX,
        cap_escalation_gate_contract_version=(
            bm_ce.CAP_ESCALATION_GATE_CONTRACT_VERSION
        ),
        allowed_environment=bm_ce.ALLOWED_ENVIRONMENT,
        allowed_symbol=bm_ce.ALLOWED_SYMBOL,
        allowed_side=bm_ce.ALLOWED_SIDE,
        allowed_order_type=bm_ce.ALLOWED_ORDER_TYPE,
        allowed_time_in_force=bm_ce.ALLOWED_TIME_IN_FORCE,
        allowed_max_order_count=bm_ce.ALLOWED_MAX_ORDER_COUNT,
        explicit_authorization_flag_name=(
            bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME
        ),
        explicit_authorization_marker=(
            bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
        ),
        max_demo_min_qty_notional_cap_usdt="20",
        network_attempted=False,
        order_endpoint_called=False,
        order_sent=False,
        instrument_rules_loaded=True,
        instrument_rules_discovery_status="DISCOVERY_OK_OFFLINE",
        request=request,
        decision=decision,
        generated_at_utc="2026-06-19T00:00:00+00:00",
    )


def test_tampered_gate_with_wrong_environment_is_rejected_by_wiring():
    ir = _ir_report()
    tampered = _tampered_gate(environment="bybit_live")
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=tampered
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_REJECTED_WRONG_ENVIRONMENT
    )
    assert report.resolution.execution_qty == ""


@pytest.mark.parametrize("symbol", sorted(bh.PROTECTED_SYMBOLS))
def test_tampered_gate_with_protected_symbol_is_rejected_by_wiring(symbol):
    ir = _ir_report()
    tampered = _tampered_gate(symbol=symbol)
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=tampered
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_REJECTED_PROTECTED_SYMBOL
    )
    assert report.resolution.execution_qty == ""


def test_tampered_gate_with_wrong_symbol_is_rejected_by_wiring():
    ir = _ir_report()
    tampered = _tampered_gate(symbol="BTCUSDT")
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=tampered
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_REJECTED_WRONG_SYMBOL
    )
    assert report.resolution.execution_qty == ""


def test_tampered_gate_with_wrong_side_is_rejected_by_wiring():
    ir = _ir_report()
    tampered = _tampered_gate(side="Sell")
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=tampered
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_REJECTED_WRONG_SIDE
    )
    assert report.resolution.execution_qty == ""


def test_tampered_gate_with_qty_mismatch_is_rejected_by_wiring():
    ir = _ir_report()
    tampered = _tampered_gate(proposed_qty="0.05")
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=tampered
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_REJECTED_QTY_MISMATCH
    )
    assert report.resolution.execution_qty == ""


def test_tampered_gate_with_invalid_candidate_is_rejected_by_wiring():
    ir = _ir_report()
    tampered = _tampered_gate(candidate_qty="", candidate_notional="")
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=tampered
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_REJECTED_CANDIDATE_INVALID
    )
    assert report.resolution.execution_qty == ""


def test_tampered_gate_authorized_but_not_demo_only_is_rejected_by_wiring():
    ir = _ir_report()
    tampered = _tampered_gate(cap_escalated_demo_only=False)
    report = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=tampered
    )
    assert (
        report.resolution.status == bm_wire.STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE
    )
    assert report.resolution.execution_qty == ""
