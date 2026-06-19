"""TASK-014BM_CAP_ESCALATION_GATE -- tests for demo-only SOLUSDT cap escalation gate.

Covers:
    * Identity / chain-break markers.
    * Default gate rejects (no authorization).
    * Authorization marker + flag required together to authorize.
    * Authorization rejected when candidate_notional > 20 USDT cap.
    * Rejects non-SOLUSDT, non-demo environment, non-Buy side,
      non-Market order_type, non-IOC TIF.
    * Rejects protected symbols.
    * Rejects reduce_only / close_on_trigger / stop_loss / take_profit.
    * Rejects max_order_count != 1.
    * Rejects proposed_qty != candidate_qty.
    * Rejects live endpoint hint.
    * No order endpoint call, no order sent.
    * No live secret env name in non-docstring source.
    * No third-party HTTP imports, no main / src.risk / BybitExecutor.
    * Report writer emits 4 files; JSON round-trip works.
    * BM ExecutionReport default keeps the 6 new cap-escalation fields
      at safe defaults.
    * BM ExecutionReport surfaces cap-escalation fields when a
      ``CapEscalationGateReport`` is passed via the new
      ``cap_escalation`` kwarg.
"""

from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src import demo_only_tiny_execution_adapter as bh
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
# Identity / chain-break markers
# ---------------------------------------------------------------------------


def test_task_id_and_identity_constants():
    assert bm_ce.TASK_ID == "TASK-014BM_CAP_ESCALATION_GATE"
    assert (
        bm_ce.IDENTITY
        == "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-CAP-ESCALATION-GATE"
    )
    assert bm_ce.IMPLEMENTATION_PATH_PHASE == "tiny_order_cap_escalation_gate"
    assert bm_ce.IS_REVIEW_CHAIN_SUFFIX is False
    assert (
        bm_ce.NEXT_REQUIRED_TASK
        == "TASK-014BN_demo_only_tiny_execution_postfill_audit"
    )


def test_next_required_task_passes_bh_non_review_chain_suffix_check():
    bh.assert_next_task_is_not_review_chain_suffix(bm_ce.NEXT_REQUIRED_TASK)


def test_upstream_tasks():
    assert bm_ce.UPSTREAM_TASKS == (
        "TASK-014BH",
        "TASK-014BM",
        "TASK-014BM_FIX",
        "TASK-014BM_MIN_QTY_FIX",
    )


def test_immutable_locks():
    assert bm_ce.ALLOWED_ENVIRONMENT == "bybit_demo"
    assert bm_ce.ALLOWED_SYMBOL == "SOLUSDT"
    assert bm_ce.ALLOWED_SIDE == "Buy"
    assert bm_ce.ALLOWED_ORDER_TYPE == "Market"
    assert bm_ce.ALLOWED_TIME_IN_FORCE == "IOC"
    assert bm_ce.ALLOWED_MAX_ORDER_COUNT == 1
    assert bm_ce.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT == Decimal("20")


def test_explicit_authorization_marker_and_flag_name():
    assert bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME == (
        "--i-understand-demo-solusdt-exchange-min-qty-exceeds-old-tiny-cap"
    )
    assert bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER == (
        "DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1"
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


# ---------------------------------------------------------------------------
# Default gate rejects
# ---------------------------------------------------------------------------


def test_default_request_with_min_qty_rules_rejects_no_authorization():
    ir = _ir_report()
    request = bm_ce.EscalationAuthorizationRequest(proposed_qty="0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    d = report.decision
    assert d.status == bm_ce.STATUS_ESCALATION_NOT_AUTHORIZED
    assert d.authorized is False
    assert d.original_tiny_cap_passed is False
    assert d.exchange_min_qty_cap_escalation_required is True
    assert d.explicit_demo_min_qty_cap_authorized is False
    assert d.cap_escalated_demo_only is False


def test_no_request_supplied_defaults_to_fail_closed():
    ir = _ir_report()
    report = bm_ce.run_cap_escalation_gate(instrument_rules_report=ir)
    # No proposed_qty by default => qty mismatch.
    assert report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_QTY_MISMATCH
    assert report.decision.authorized is False
    assert report.decision.cap_escalated_demo_only is False


def test_no_instrument_rules_supplied_fails_closed():
    request = bm_ce.EscalationAuthorizationRequest(proposed_qty="0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=None, request=request
    )
    assert (
        report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_RULES_NOT_LOADED
    )
    assert report.decision.authorized is False
    assert report.decision.cap_escalated_demo_only is False


def test_authorization_flag_alone_without_marker_rejects():
    ir = _ir_report()
    request = _authorized_request(flag=True, marker_ok=False)
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert report.decision.status == bm_ce.STATUS_ESCALATION_NOT_AUTHORIZED
    assert report.decision.authorized is False


def test_marker_alone_without_flag_rejects():
    ir = _ir_report()
    request = _authorized_request(flag=False, marker_ok=True)
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert report.decision.status == bm_ce.STATUS_ESCALATION_NOT_AUTHORIZED
    assert report.decision.authorized is False


# ---------------------------------------------------------------------------
# Authorization success / notional cap
# ---------------------------------------------------------------------------


def test_authorization_allows_candidate_qty_when_notional_within_cap():
    ir = _ir_report(mark_price="100")  # candidate 0.1 * 100 = 10 USDT
    request = _authorized_request("0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    d = report.decision
    assert d.status == bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert d.authorized is True
    assert d.original_tiny_cap_passed is False
    assert d.exchange_min_qty_cap_escalation_required is True
    assert d.explicit_demo_min_qty_cap_authorized is True
    assert d.cap_escalated_demo_only is True
    assert d.candidate_qty == "0.1"
    assert Decimal(d.candidate_notional) == Decimal("10.0")
    assert d.max_demo_min_qty_notional_cap_usdt == "20"


def test_authorization_rejects_when_candidate_notional_over_cap():
    # mark_price=250 -> candidate 0.1 * 250 = 25 USDT > 20 cap
    ir = _ir_report(mark_price="250")
    request = _authorized_request("0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    d = report.decision
    assert d.status == bm_ce.STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP
    assert d.authorized is False
    assert d.explicit_demo_min_qty_cap_authorized is True
    assert d.cap_escalated_demo_only is False


def test_authorization_rejects_when_custom_notional_cap_exceeded():
    ir = _ir_report(mark_price="100")  # candidate notional 10
    request = _authorized_request("0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=request,
        max_demo_min_qty_notional_cap_usdt=Decimal("5"),
    )
    assert (
        report.decision.status
        == bm_ce.STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP
    )
    assert report.decision.authorized is False


def test_invalid_notional_cap_falls_back_to_default():
    ir = _ir_report(mark_price="100")
    request = _authorized_request("0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir,
        request=request,
        max_demo_min_qty_notional_cap_usdt="not-a-number",
    )
    # Default 20 cap allows it.
    assert report.decision.status == bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert report.decision.max_demo_min_qty_notional_cap_usdt == "20"


def test_escalation_not_required_when_original_tiny_cap_passes():
    # minOrderQty=0.01 with min_notional=0 → candidate 0.01 fits cap.
    ir = _ir_report(
        mark_price="100",
        min_order_qty="0.01",
        qty_step="0.01",
        min_notional_value="0",
    )
    request = _authorized_request("0.01")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    d = report.decision
    assert d.status == bm_ce.STATUS_ESCALATION_NOT_REQUIRED
    assert d.authorized is False  # no escalation to grant
    assert d.original_tiny_cap_passed is True
    assert d.exchange_min_qty_cap_escalation_required is False
    assert d.cap_escalated_demo_only is False


# ---------------------------------------------------------------------------
# Lock rejections
# ---------------------------------------------------------------------------


def test_rejects_wrong_symbol():
    ir = _ir_report()
    request = _authorized_request("0.1", symbol="BTCUSDT")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_WRONG_SYMBOL
    )
    assert report.decision.authorized is False


def test_rejects_wrong_environment():
    ir = _ir_report()
    request = _authorized_request("0.1", environment="bybit_live")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status
        == bm_ce.STATUS_ESCALATION_REJECTED_WRONG_ENVIRONMENT
    )
    assert report.decision.authorized is False


def test_rejects_wrong_side():
    ir = _ir_report()
    request = _authorized_request("0.1", side="Sell")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_WRONG_SIDE
    assert report.decision.authorized is False


def test_rejects_non_market_order_type():
    ir = _ir_report()
    request = _authorized_request("0.1", order_type="Limit")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status
        == bm_ce.STATUS_ESCALATION_REJECTED_DISALLOWED_ORDER_TYPE
    )


def test_rejects_non_ioc_tif():
    ir = _ir_report()
    request = _authorized_request("0.1", time_in_force="GTC")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_DISALLOWED_TIF
    )


def test_rejects_max_order_count_above_one():
    ir = _ir_report()
    request = _authorized_request("0.1", max_order_count=2)
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status
        == bm_ce.STATUS_ESCALATION_REJECTED_MAX_ORDER_COUNT
    )


def test_rejects_qty_mismatch():
    ir = _ir_report()  # candidate 0.1
    request = _authorized_request("0.2")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_QTY_MISMATCH
    )
    assert report.decision.authorized is False


def test_rejects_empty_qty():
    ir = _ir_report()
    request = _authorized_request("")  # empty
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_QTY_MISMATCH
    )


# ---------------------------------------------------------------------------
# Protected symbols / live endpoint / TP-SL / reduce_only
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "protected", sorted(bh.PROTECTED_SYMBOLS)
)
def test_rejects_protected_symbols(protected: str):
    ir = _ir_report()
    request = _authorized_request("0.1", symbol=protected)
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status
        == bm_ce.STATUS_ESCALATION_REJECTED_PROTECTED_SYMBOL
    )
    assert report.decision.authorized is False


@pytest.mark.parametrize(
    "endpoint_hint",
    [
        "https://api.bybit.com/v5/order/create",
        "https://api.bytick.com/v5/market/instruments-info",
        "https://api-demo.bybit.com/v5/order/create",
        "wss://stream.bybit.com",
    ],
)
def test_rejects_live_endpoint_hint(endpoint_hint: str):
    ir = _ir_report()
    request = _authorized_request("0.1", endpoint_url_hint=endpoint_hint)
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status
        == bm_ce.STATUS_ESCALATION_REJECTED_LIVE_ENDPOINT
    )
    assert report.decision.authorized is False


def test_rejects_reduce_only():
    ir = _ir_report()
    request = _authorized_request("0.1", reduce_only=True)
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_REDUCE_ONLY
    )


def test_rejects_close_on_trigger():
    ir = _ir_report()
    request = _authorized_request("0.1", close_on_trigger=True)
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert (
        report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_REDUCE_ONLY
    )


def test_rejects_stop_loss():
    ir = _ir_report()
    request = _authorized_request("0.1", stop_loss="50")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_TPSL


def test_rejects_take_profit():
    ir = _ir_report()
    request = _authorized_request("0.1", take_profit="200")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert report.decision.status == bm_ce.STATUS_ESCALATION_REJECTED_TPSL


# ---------------------------------------------------------------------------
# Surface invariants
# ---------------------------------------------------------------------------


def test_report_never_calls_order_endpoint_or_sends_order():
    ir = _ir_report()
    request = _authorized_request("0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False


def test_global_tiny_caps_untouched_by_gate():
    # The gate must not mutate BH's TINY_QTY_CAP_SOL / TINY_SIZE_CAP_USDT.
    before_qty = bh.TINY_QTY_CAP_SOL
    before_size = bh.TINY_SIZE_CAP_USDT
    ir = _ir_report()
    request = _authorized_request("0.1")
    bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    assert bh.TINY_QTY_CAP_SOL == before_qty == Decimal("0.05")
    assert bh.TINY_SIZE_CAP_USDT == before_size == Decimal("5")


def test_protected_symbols_unchanged():
    assert bh.PROTECTED_SYMBOLS == frozenset(
        {"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"}
    )


# ---------------------------------------------------------------------------
# AST static-source safety scan
# ---------------------------------------------------------------------------


def _module_source() -> str:
    return Path(bm_ce.__file__).read_text(encoding="utf-8")


def _module_ast() -> ast.AST:
    return ast.parse(_module_source())


def _iter_string_constants_excluding_docstrings(tree: ast.AST):
    docstring_node_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(node, (ast.Module, ast.ClassDef, ast.FunctionDef, ast.AsyncFunctionDef)):
            body = getattr(node, "body", None)
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


def test_source_does_not_import_third_party_http_clients():
    tree = _module_ast()
    forbidden = {"requests", "pybit", "aiohttp", "httpx", "websocket", "websockets"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                top = alias.name.split(".")[0]
                assert top not in forbidden, (
                    f"forbidden import: {alias.name}"
                )
        elif isinstance(node, ast.ImportFrom):
            top = (node.module or "").split(".")[0]
            assert top not in forbidden, (
                f"forbidden from-import: {node.module}"
            )


def test_source_does_not_import_main_risk_or_bybit_executor():
    tree = _module_ast()
    forbidden_prefixes = ("main", "src.risk", "src.executors.bybit")
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            module = node.module or ""
            for prefix in forbidden_prefixes:
                assert not module.startswith(prefix), (
                    f"forbidden from-import: {module}"
                )
        elif isinstance(node, ast.Import):
            for alias in node.names:
                for prefix in forbidden_prefixes:
                    assert not alias.name.startswith(prefix), (
                        f"forbidden import: {alias.name}"
                    )


def test_source_does_not_reference_bybit_executor_or_os_env_access():
    tree = _module_ast()
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id != "BybitExecutor", (
                "must not reference BybitExecutor"
            )
        if isinstance(node, ast.Attribute):
            full = ast.dump(node)
            # ``os.environ`` access (read or write).
            if (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in {"environ", "getenv"}
            ):
                raise AssertionError(
                    f"forbidden os env access in source: {full}"
                )


def test_source_does_not_reference_live_or_demo_secret_env_names_in_code():
    tree = _module_ast()
    forbidden_names = {
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
    }
    for node in _iter_string_constants_excluding_docstrings(tree):
        text = node.value
        for forbidden in forbidden_names:
            assert forbidden not in text, (
                f"forbidden secret env name found in code literal: {text!r}"
            )


def test_source_does_not_reference_order_create_or_live_hosts():
    src = _module_source()
    # The denylist constants are themselves source mentions, so we restrict
    # the scan to literal *usages* by checking the source minus the
    # FORBIDDEN_URL_TOKENS tuple declaration.
    forbidden_in_code = (
        "api.bybit.com",
        "api.bytick.com",
        "wss://stream.bybit.com",
        "wss://stream.bytick.com",
    )
    # All such tokens should only appear inside the FORBIDDEN_URL_TOKENS
    # tuple (denylist). Count occurrences; each token must appear at most
    # once (the denylist entry).
    for token in forbidden_in_code:
        assert src.count(token) <= 1, (
            f"token {token!r} appears more than once in source"
        )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def test_report_writer_emits_four_files_with_json_roundtrip(tmp_path):
    ir = _ir_report()
    request = _authorized_request("0.1")
    report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    paths = bm_ce.write_report(report, output_dir=tmp_path)
    assert set(paths.keys()) == {
        "latest_json",
        "latest_md",
        "timestamped_json",
        "timestamped_md",
    }
    for p in paths.values():
        assert p.exists()
    parsed = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert parsed["task_id"] == "TASK-014BM_CAP_ESCALATION_GATE"
    assert parsed["decision"]["status"] == bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert parsed["decision"]["cap_escalated_demo_only"] is True
    md_text = paths["latest_md"].read_text(encoding="utf-8")
    assert "TASK-014BM_CAP_ESCALATION_GATE" in md_text
    assert "cap_escalated_demo_only" in md_text


# ---------------------------------------------------------------------------
# BM ExecutionReport surfaces cap-escalation fields
# ---------------------------------------------------------------------------


def test_bm_execution_report_default_omits_cap_escalation_fields(monkeypatch):
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    ):
        monkeypatch.delenv(name, raising=False)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    assert report.original_tiny_cap_passed is False
    assert report.exchange_min_qty_cap_escalation_required is False
    assert report.explicit_demo_min_qty_cap_authorized is False
    assert report.cap_escalated_demo_only is False
    assert report.cap_escalation_status == ""
    assert report.max_demo_min_qty_notional_cap_usdt == ""
    # No network was attempted.
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False


def test_bm_execution_report_surfaces_cap_escalation_decision(monkeypatch):
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    ):
        monkeypatch.delenv(name, raising=False)
    ir = _ir_report(mark_price="100")
    request = _authorized_request("0.1")
    ce_report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS,
        instrument_rules=ir,
        cap_escalation=ce_report,
    )
    assert report.cap_escalation_status == bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert report.original_tiny_cap_passed is False
    assert report.exchange_min_qty_cap_escalation_required is True
    assert report.explicit_demo_min_qty_cap_authorized is True
    assert report.cap_escalated_demo_only is True
    assert report.max_demo_min_qty_notional_cap_usdt == "20"
    # BM still must not have called the network in readiness mode.
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False


def test_bm_execution_report_surfaces_unauthorized_decision(monkeypatch):
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    ):
        monkeypatch.delenv(name, raising=False)
    ir = _ir_report(mark_price="100")
    request = bm_ce.EscalationAuthorizationRequest(proposed_qty="0.1")
    ce_report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS,
        instrument_rules=ir,
        cap_escalation=ce_report,
    )
    assert report.cap_escalation_status == bm_ce.STATUS_ESCALATION_NOT_AUTHORIZED
    assert report.exchange_min_qty_cap_escalation_required is True
    assert report.explicit_demo_min_qty_cap_authorized is False
    assert report.cap_escalated_demo_only is False


def test_to_dict_round_trip_includes_all_new_fields():
    ir = _ir_report()
    request = _authorized_request("0.1")
    ce_report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    d = ce_report.to_dict()
    # The full set of decision fields surfaces in to_dict().
    for key in (
        "status",
        "authorized",
        "original_tiny_cap_passed",
        "exchange_min_qty_cap_escalation_required",
        "explicit_demo_min_qty_cap_authorized",
        "cap_escalated_demo_only",
        "candidate_qty",
        "candidate_notional",
        "proposed_qty",
        "mark_price_used",
        "tiny_qty_cap_sol",
        "tiny_size_cap_usdt",
        "max_demo_min_qty_notional_cap_usdt",
        "environment",
        "symbol",
        "side",
        "order_type",
        "time_in_force",
        "max_order_count",
        "reason",
    ):
        assert key in d["decision"], f"missing decision field {key}"
    parsed = json.loads(json.dumps(d, sort_keys=True))
    assert parsed["task_id"] == "TASK-014BM_CAP_ESCALATION_GATE"
