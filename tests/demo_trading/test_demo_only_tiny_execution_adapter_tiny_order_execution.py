"""TASK-014BM Stage 1 tests -- demo-only tiny execution adapter explicit
tiny order execution.

These tests verify that the BM execution module:
    * carries the correct chain-break identity markers,
    * points the next required task at a non-review-chain successor,
    * defaults to readiness mode -- no network, no order, no secret read,
    * never calls the network without BOTH the explicit execute flag and
      the explicit confirmation flag,
    * produces a clean MISSING_DEMO_CREDENTIALS report when demo
      credentials are absent (instead of falling back to live credentials
      or failing the task),
    * rejects every forbidden symbol / environment / endpoint before
      touching the network,
    * builds at most one order (no retry, no loop, no scheduler),
    * never calls a stop / take-profit endpoint,
    * never attaches a stop-loss or take-profit,
    * never imports BybitExecutor / main / src.risk,
    * never reads any LIVE-named secret env var,
    * never modifies main.py / src/risk.py / BybitExecutor live behavior.

When credentials and an injected fake sender are provided, the tests
verify the gated send path actually constructs exactly one HTTPS POST,
signs it with Bybit V5 HMAC-SHA256, and only targets the single allowed
demo endpoint URL.

The tests are pure offline: no real network call is made; the only
``urlopen`` invocation possible is short-circuited through the
``sender`` injection.
"""

from __future__ import annotations

import ast
import io
import json
import sys
import tokenize
from dataclasses import FrozenInstanceError
from decimal import Decimal
from pathlib import Path

import pytest

from src import demo_only_tiny_execution_adapter as bh
from src import (
    demo_only_tiny_execution_adapter_endpoint_guard_integration as bj,
)
from src import (
    demo_only_tiny_execution_adapter_final_pre_execution_checklist as bk,
)
from src import demo_only_tiny_execution_adapter_payload_dry_run as bi
from src import demo_only_tiny_execution_adapter_tiny_order_preparation as bl
from src import demo_only_tiny_execution_adapter_tiny_order_execution as bm
from src import (
    demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring as bm_wire,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as bm_ce,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
)


def _authorized_wiring(candidate_qty: str = "0.1", mark_price: str = "100"):
    """Stage 2 helper: build a real ESCALATION_AUTHORIZED wiring report.

    TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH makes the
    actual request body switch to the authorized candidate qty (0.1)
    only when a fully authorized wiring report is threaded through.
    Without it BM fails closed pre-network. This helper drives the real
    BM_MIN_QTY_FIX + BM_CAP_ESCALATION_GATE upstreams so the body qty
    switches from the invalid BL packet qty (0.01) to 0.1.
    """

    ir_response = {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "symbol": "SOLUSDT",
                    "status": "Trading",
                    "lotSizeFilter": {
                        "minOrderQty": candidate_qty,
                        "qtyStep": candidate_qty,
                        "minNotionalValue": "5",
                        "maxMktOrderQty": "12000",
                    },
                    "priceFilter": {"tickSize": "0.010"},
                }
            ]
        },
    }
    ir = bm_ir.run_instrument_rules_discovery(
        mark_price=mark_price, pre_parsed_response=ir_response
    )
    request = bm_ce.EscalationAuthorizationRequest(
        proposed_qty=candidate_qty,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=(
            bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
        ),
    )
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    return bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------


def test_bm_identity_markers():
    assert bm.TASK_ID == "TASK-014BM"
    assert bm.IDENTITY == "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-EXECUTION"
    assert bm.IMPLEMENTATION_PATH_PHASE == "tiny_order_execution"
    assert bm.IS_REVIEW_CHAIN_SUFFIX is False
    assert bm.UPSTREAM_TASKS == (
        "TASK-014BH",
        "TASK-014BI",
        "TASK-014BJ",
        "TASK-014BK",
        "TASK-014BL",
    )


def test_bm_next_required_task_is_not_review_chain_suffix():
    for suffix in (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ):
        assert not bm.NEXT_REQUIRED_TASK.endswith(suffix)
    bh.assert_next_task_is_not_review_chain_suffix(bm.NEXT_REQUIRED_TASK)


def test_bm_execution_constants_strict():
    assert bm.ALLOWED_DEMO_ENDPOINT_HOST == "api-demo.bybit.com"
    assert bm.ALLOWED_DEMO_ENDPOINT_URL == (
        "https://api-demo.bybit.com/v5/order/create"
    )
    assert bm.ALLOWED_DEMO_CATEGORY == "linear"
    assert bm.MAX_ORDER_COUNT == 1
    assert bm.EXECUTE_FLAG_NAME == "--execute-demo-order"
    assert bm.CONFIRM_FLAG_NAME == (
        "--i-understand-this-sends-one-bybit-demo-order"
    )
    assert bm.DEMO_API_KEY_ENV == "BYBIT_DEMO_API_KEY"
    assert bm.DEMO_API_SECRET_ENV == "BYBIT_DEMO_API_SECRET"
    assert bm.DEMO_RECV_WINDOW_ENV == "BYBIT_DEMO_RECV_WINDOW"
    assert bm.DEMO_SCOPED_ENV_NAMES == (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    )
    assert bm.SUPPORTED_MODES == (
        "dry_run",
        "readiness",
        "execute_demo_order",
    )
    assert len(bm.GATE_NAMES) == 16
    assert bm.PRE_NETWORK_GATE_NAMES == bm.GATE_NAMES[:13]
    assert bm.EXECUTE_GATE_NAMES == bm.GATE_NAMES[13:]


# ---------------------------------------------------------------------------
# Default mode (no network, no order)
# ---------------------------------------------------------------------------


def _no_env(monkeypatch):
    for k in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
    ):
        monkeypatch.delenv(k, raising=False)


def test_default_mode_is_readiness_and_does_not_call_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution()
    assert report.mode == bm.MODE_DRY_RUN  # default keyword arg is dry_run
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_DRY_RUN_OK_NO_NETWORK
    assert report.live_endpoint_denied is True


def test_readiness_mode_passes_pre_network_gates_without_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    assert report.mode == bm.MODE_READINESS
    assert report.all_pre_network_gates_passed is True
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_READINESS_OK_NO_NETWORK
    assert report.plan is not None
    assert report.plan.symbol == "SOLUSDT"
    assert report.plan.qty == "0.01"
    assert report.plan.order_type == "Market"
    assert report.plan.time_in_force == "IOC"
    assert report.plan.reduce_only is False
    assert report.plan.close_on_trigger is False
    assert report.plan.max_order_count == 1
    assert report.plan.endpoint_target == bm.ALLOWED_DEMO_ENDPOINT_URL


def test_dry_run_mode_does_not_call_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_DRY_RUN)
    assert report.mode == bm.MODE_DRY_RUN
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_DRY_RUN_OK_NO_NETWORK


# ---------------------------------------------------------------------------
# Execute mode -- flag and credential gating
# ---------------------------------------------------------------------------


def test_execute_mode_without_any_flag_does_not_call_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=False,
        confirm_flag=False,
    )
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_GATE_REJECTED_NO_NETWORK


def test_execute_mode_missing_confirm_flag_does_not_call_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=False,
    )
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_GATE_REJECTED_NO_NETWORK


def test_execute_mode_missing_execute_flag_does_not_call_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=False,
        confirm_flag=True,
    )
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_GATE_REJECTED_NO_NETWORK


def test_execute_mode_with_flags_but_missing_creds_returns_missing_creds(
    monkeypatch,
):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
    )
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_MISSING_DEMO_CREDENTIALS
    assert report.demo_credentials_present is False


def test_execute_mode_with_flags_and_creds_sends_via_injected_sender(
    monkeypatch,
):
    _no_env(monkeypatch)
    calls: list[tuple[str, dict, bytes]] = []

    def fake_sender(url, headers, body):
        calls.append((url, dict(headers), body))
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":0,"retMsg":"OK","result":{"orderId":"demo-xyz-1"}}',
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "demo-xyz-1"},
            },
        }

    creds = bm.DemoCredentials(api_key="demo_key_x", api_secret="demo_secret_x")
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=fake_sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.final_status == bm.STATUS_EXECUTED_DEMO_ONLY
    assert report.network_attempted is True
    assert report.order_endpoint_called is True
    assert report.order_sent is True
    assert report.bybit_order_id == "demo-xyz-1"
    assert report.bybit_ret_code == 0
    assert len(calls) == 1
    # ONE and only ONE call.
    sent_url, sent_headers, sent_body = calls[0]
    assert sent_url == bm.ALLOWED_DEMO_ENDPOINT_URL
    assert sent_url.startswith("https://api-demo.bybit.com/")
    assert "X-BAPI-API-KEY" in sent_headers
    assert sent_headers["X-BAPI-API-KEY"] == "demo_key_x"
    assert "X-BAPI-SIGN" in sent_headers
    assert sent_headers["Content-Type"] == "application/json"
    body_dict = json.loads(sent_body.decode("utf-8"))
    assert body_dict["category"] == "linear"
    assert body_dict["symbol"] == "SOLUSDT"
    assert body_dict["side"] == "Buy"
    assert body_dict["qty"] == "0.1"
    assert body_dict["orderType"] == "Market"
    assert body_dict["timeInForce"] == "IOC"
    assert body_dict["reduceOnly"] is False
    assert body_dict["closeOnTrigger"] is False
    assert body_dict["orderLinkId"].startswith("DEMO_ONLY_TINY_BH_")


def test_execute_mode_with_flags_and_creds_handles_network_error(monkeypatch):
    _no_env(monkeypatch)

    def fake_sender(url, headers, body):
        return {
            "_network_error": True,
            "_error_repr": "ConnectionError('boom')",
            "http_status": None,
            "raw_text": "",
            "json": None,
        }

    creds = bm.DemoCredentials(api_key="demo_key_x", api_secret="demo_secret_x")
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=fake_sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.final_status == bm.STATUS_NETWORK_ERROR_DEMO_ONLY
    assert report.order_sent is False


def test_execute_mode_only_one_call_to_sender(monkeypatch):
    _no_env(monkeypatch)
    counter = {"n": 0}

    def fake_sender(url, headers, body):
        counter["n"] += 1
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":0,"retMsg":"OK","result":{"orderId":"demo-id"}}',
            "json": {"retCode": 0, "retMsg": "OK", "result": {"orderId": "demo-id"}},
        }

    creds = bm.DemoCredentials(api_key="k", api_secret="s")
    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=fake_sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert counter["n"] == 1


# ---------------------------------------------------------------------------
# Pre-network rejection scenarios -- never touch network
# ---------------------------------------------------------------------------


def _sender_must_not_be_called(url, headers, body):  # pragma: no cover
    raise AssertionError(f"sender invoked unexpectedly: url={url!r}")


def test_bybit_live_environment_rejected_before_network(monkeypatch):
    _no_env(monkeypatch)

    # Force-bypass BL to test BM's own environment gate.
    bad_packet = bl.PreparationPacket(
        task_id="TASK-014BL",
        upstream_tasks=bl.UPSTREAM_TASKS,
        target_future_task=bl.TARGET_FUTURE_TASK,
        environment="bybit_live",
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        mark_price="100",
        notional_estimate="1",
        order_type="Market",
        reduce_only=False,
        time_in_force="IOC",
        order_link_id="DEMO_ONLY_TINY_BH_SOLUSDT_OFFLINE_BUILD",
        order_link_id_prefix=bh.ORDER_LINK_ID_PREFIX,
        audit_response_status=bl.BL_AUDIT_RESPONSE_STATUS_NOT_SENT,
        packet_is_not_execution_authorization=True,
        payload_audit={
            "_demo_only_audit_response_status": (
                bh.AUDIT_RESPONSE_STATUS_NOT_SENT
            ),
        },
        preparation_contract_version=bl.PREPARATION_CONTRACT_VERSION,
        generated_at_utc="2026-06-18T00:00:00Z",
    )
    gates = bm._evaluate_gates(
        packet=bad_packet,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    env_gate = next(g for g in gates if g.name == "environment_is_bybit_demo")
    assert env_gate.passed is False
    assert "bybit_live" in env_gate.reason


@pytest.mark.parametrize(
    "live_url",
    [
        "https://api.bybit.com/v5/order/create",
        "https://api.bytick.com/v5/order/create",
        "wss://stream.bybit.com/v5/public/linear",
    ],
)
def test_live_endpoint_rejected_before_network(monkeypatch, live_url):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        endpoint_target=live_url,
        sender=_sender_must_not_be_called,
    )
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.final_status == bm.STATUS_GATE_REJECTED_NO_NETWORK
    endpoint_gate = next(
        g for g in report.gates if g.name == "endpoint_target_demo_only"
    )
    assert endpoint_gate.passed is False


def test_non_demo_endpoint_other_host_rejected_before_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        endpoint_target="https://example.com/v5/order/create",
        sender=_sender_must_not_be_called,
    )
    assert report.network_attempted is False
    assert report.final_status == bm.STATUS_GATE_REJECTED_NO_NETWORK


def _packet_with(symbol="SOLUSDT", qty="0.01", reduce_only=False):
    return bl.PreparationPacket(
        task_id="TASK-014BL",
        upstream_tasks=bl.UPSTREAM_TASKS,
        target_future_task=bl.TARGET_FUTURE_TASK,
        environment=bh.ALLOWED_ENVIRONMENT,
        symbol=symbol,
        side="Buy",
        qty=qty,
        mark_price="100",
        notional_estimate="1",
        order_type="Market",
        reduce_only=reduce_only,
        time_in_force="IOC",
        order_link_id="DEMO_ONLY_TINY_BH_SOLUSDT_OFFLINE_BUILD",
        order_link_id_prefix=bh.ORDER_LINK_ID_PREFIX,
        audit_response_status=bl.BL_AUDIT_RESPONSE_STATUS_NOT_SENT,
        packet_is_not_execution_authorization=True,
        payload_audit={
            "_demo_only_audit_response_status": (
                bh.AUDIT_RESPONSE_STATUS_NOT_SENT
            ),
        },
        preparation_contract_version=bl.PREPARATION_CONTRACT_VERSION,
        generated_at_utc="2026-06-18T00:00:00Z",
    )


@pytest.mark.parametrize("bad_symbol", ["BTCUSDT", "ETHUSDT", "DOGEUSDT"])
def test_non_solusdt_packet_rejected_before_network(bad_symbol):
    pkt = _packet_with(symbol=bad_symbol)
    gates = bm._evaluate_gates(
        packet=pkt,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    sym_gate = next(g for g in gates if g.name == "symbol_is_solusdt")
    assert sym_gate.passed is False


@pytest.mark.parametrize(
    "protected",
    ["ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"],
)
def test_protected_symbol_packet_rejected_before_network(protected):
    pkt = _packet_with(symbol=protected)
    gates = bm._evaluate_gates(
        packet=pkt,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    prot_gate = next(
        g for g in gates if g.name == "protected_symbols_not_in_scope"
    )
    assert prot_gate.passed is False


@pytest.mark.parametrize(
    "protected_existing",
    ["ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"],
)
def test_protected_existing_position_rejected_before_network(
    monkeypatch, protected_existing
):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        existing_positions=(protected_existing, "ADAUSDT"),
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        sender=_sender_must_not_be_called,
    )
    assert report.network_attempted is False
    assert report.protected_symbols_untouched is False
    assert report.final_status == bm.STATUS_GATE_REJECTED_NO_NETWORK


@pytest.mark.parametrize("bad_qty", ["0.02", "0.05", "0.1", "1.0"])
def test_qty_above_tiny_entry_cap_rejected_before_network(bad_qty):
    pkt = _packet_with(qty=bad_qty)
    gates = bm._evaluate_gates(
        packet=pkt,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    qty_gate = next(g for g in gates if g.name == "qty_within_tiny_cap")
    assert qty_gate.passed is False


def test_reduce_only_true_packet_rejected():
    pkt = _packet_with(reduce_only=True)
    gates = bm._evaluate_gates(
        packet=pkt,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    ro_gate = next(g for g in gates if g.name == "reduce_only_false")
    assert ro_gate.passed is False


def test_bl_packet_missing_rejected():
    gates = bm._evaluate_gates(
        packet=None,
        bl_all_passed=False,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    loaded_gate = next(g for g in gates if g.name == "bl_packet_loaded")
    passed_gate = next(g for g in gates if g.name == "bl_packet_all_passed")
    assert loaded_gate.passed is False
    assert passed_gate.passed is False


def test_bl_packet_not_marked_non_execution_authorization_rejected():
    pkt = bl.PreparationPacket(
        task_id="TASK-014BL",
        upstream_tasks=bl.UPSTREAM_TASKS,
        target_future_task=bl.TARGET_FUTURE_TASK,
        environment=bh.ALLOWED_ENVIRONMENT,
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        mark_price="100",
        notional_estimate="1",
        order_type="Market",
        reduce_only=False,
        time_in_force="IOC",
        order_link_id="DEMO_ONLY_TINY_BH_SOLUSDT_OFFLINE_BUILD",
        order_link_id_prefix=bh.ORDER_LINK_ID_PREFIX,
        audit_response_status=bl.BL_AUDIT_RESPONSE_STATUS_NOT_SENT,
        packet_is_not_execution_authorization=False,  # tampered
        payload_audit={
            "_demo_only_audit_response_status": (
                bh.AUDIT_RESPONSE_STATUS_NOT_SENT
            ),
        },
        preparation_contract_version=bl.PREPARATION_CONTRACT_VERSION,
        generated_at_utc="2026-06-18T00:00:00Z",
    )
    gates = bm._evaluate_gates(
        packet=pkt,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    gate = next(
        g for g in gates if g.name == "packet_marked_not_execution_authorization"
    )
    assert gate.passed is False


def test_bl_packet_audit_without_bh_marker_rejected():
    pkt = bl.PreparationPacket(
        task_id="TASK-014BL",
        upstream_tasks=bl.UPSTREAM_TASKS,
        target_future_task=bl.TARGET_FUTURE_TASK,
        environment=bh.ALLOWED_ENVIRONMENT,
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        mark_price="100",
        notional_estimate="1",
        order_type="Market",
        reduce_only=False,
        time_in_force="IOC",
        order_link_id="DEMO_ONLY_TINY_BH_SOLUSDT_OFFLINE_BUILD",
        order_link_id_prefix=bh.ORDER_LINK_ID_PREFIX,
        audit_response_status=bl.BL_AUDIT_RESPONSE_STATUS_NOT_SENT,
        packet_is_not_execution_authorization=True,
        payload_audit={},  # missing BH marker
        preparation_contract_version=bl.PREPARATION_CONTRACT_VERSION,
        generated_at_utc="2026-06-18T00:00:00Z",
    )
    gates = bm._evaluate_gates(
        packet=pkt,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    gate = next(g for g in gates if g.name == "packet_audit_status_from_bh")
    assert gate.passed is False


def test_unsupported_mode_raises():
    with pytest.raises(bm.ExplicitTinyOrderExecutionError):
        bm.run_explicit_tiny_order_execution(mode="live_trading")


def test_order_count_locked_to_one_gate_always_passes():
    pkt = _packet_with()
    gates = bm._evaluate_gates(
        packet=pkt,
        bl_all_passed=True,
        existing_positions=(),
        endpoint_target=bm.ALLOWED_DEMO_ENDPOINT_URL,
        execute_flag=True,
        confirm_flag=True,
        credentials=bm.DemoCredentials(api_key="k", api_secret="s"),
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
    )
    gate = next(g for g in gates if g.name == "order_count_locked_to_one")
    assert gate.passed is True
    assert bm.MAX_ORDER_COUNT == 1


# ---------------------------------------------------------------------------
# Credential loading -- demo-scoped only
# ---------------------------------------------------------------------------


def test_load_demo_credentials_from_explicit_env():
    creds = bm.load_demo_credentials_from_env(
        env={
            "BYBIT_DEMO_API_KEY": "demo_k",
            "BYBIT_DEMO_API_SECRET": "demo_s",
            "BYBIT_DEMO_RECV_WINDOW": "7500",
        }
    )
    assert creds.api_key == "demo_k"
    assert creds.api_secret == "demo_s"
    assert creds.recv_window == "7500"
    assert creds.present is True


def test_load_demo_credentials_missing_returns_not_present():
    creds = bm.load_demo_credentials_from_env(env={})
    assert creds.present is False
    assert creds.api_key == ""
    assert creds.api_secret == ""


def test_load_demo_credentials_does_not_read_live_env_names():
    # Even when LIVE-named env vars are present, BM must ignore them.
    creds = bm.load_demo_credentials_from_env(
        env={
            "BYBIT_API_KEY": "live_k_must_never_be_used",
            "BYBIT_API_SECRET": "live_s_must_never_be_used",
        }
    )
    assert creds.present is False
    assert creds.api_key == ""
    assert creds.api_secret == ""


# ---------------------------------------------------------------------------
# Sender hard rejection of non-demo URL
# ---------------------------------------------------------------------------


def test_real_sender_refuses_non_demo_url():
    with pytest.raises(bm.ExplicitTinyOrderExecutionError):
        bm._real_sender_via_urllib(
            "https://api.bybit.com/v5/order/create",
            {"Content-Type": "application/json"},
            b"{}",
        )


def test_send_one_demo_order_refuses_non_demo_plan():
    creds = bm.DemoCredentials(api_key="k", api_secret="s")
    pkt = _packet_with()
    plan = bm.build_execution_plan(
        pkt, endpoint_target="https://api.bybit.com/v5/order/create"
    )
    # plan endpoint != ALLOWED -- internal send refuses.
    with pytest.raises(bm.ExplicitTinyOrderExecutionError):
        bm._send_one_demo_order(plan, creds, sender=_sender_must_not_be_called)


# ---------------------------------------------------------------------------
# Frozen dataclasses
# ---------------------------------------------------------------------------


def test_execution_plan_is_frozen():
    pkt = _packet_with()
    plan = bm.build_execution_plan(pkt)
    with pytest.raises(FrozenInstanceError):
        plan.symbol = "BTCUSDT"  # type: ignore[misc]


def test_execution_report_is_frozen(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    with pytest.raises(FrozenInstanceError):
        report.final_status = "TAMPERED"  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Static-source safety invariants on the BM module itself
# ---------------------------------------------------------------------------


def _bm_source() -> str:
    return Path(bm.__file__).read_text(encoding="utf-8")


def _bm_tree() -> ast.AST:
    return ast.parse(_bm_source())


def _bm_source_without_docstrings() -> str:
    """Return BM source with module/class/function docstrings stripped.

    Docstrings legitimately *describe* the forbidden names (e.g.
    ``BYBIT_API_KEY``, ``src.risk``, ``BybitExecutor``); those mentions
    are documentation, not references. The static-source safety checks
    care only about *executable* references, so we strip docstrings
    before scanning.
    """

    tree = _bm_tree()
    docstring_spans: list[tuple[int, int]] = []
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", None)
            if not body:
                continue
            first = body[0]
            if (
                isinstance(first, ast.Expr)
                and isinstance(first.value, ast.Constant)
                and isinstance(first.value.value, str)
            ):
                docstring_spans.append(
                    (first.value.lineno, first.value.end_lineno)
                )
    src = _bm_source()
    lines = src.splitlines(keepends=True)
    keep: list[str] = []
    for idx, line in enumerate(lines, start=1):
        if any(start <= idx <= end for start, end in docstring_spans):
            continue
        keep.append(line)
    return "".join(keep)


def _bm_imports() -> set[str]:
    tree = _bm_tree()
    mods: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                mods.add(n.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                mods.add(node.module.split(".")[0])
    return mods


def test_bm_does_not_import_forbidden_network_libraries():
    forbidden = {
        "requests",
        "pybit",
        "aiohttp",
        "httpx",
        "websocket",
        "websockets",
    }
    imported = _bm_imports()
    assert imported.isdisjoint(forbidden), imported & forbidden


def test_bm_does_not_import_main_or_risk_or_executors():
    tree = _bm_tree()
    imports_full: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                imports_full.add(n.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports_full.add(node.module)
                for n in node.names:
                    imports_full.add(f"{node.module}.{n.name}")
    forbidden = {
        "main",
        "src.risk",
        "src.executors",
        "src.executors.bybit",
    }
    for f in forbidden:
        for imp in imports_full:
            assert not (imp == f or imp.startswith(f + ".")), (
                f"BM must not import {imp!r} (matched forbidden {f!r})"
            )
    # And no executable reference to BybitExecutor in any AST Name node.
    src_names = {
        n.id for n in ast.walk(tree) if isinstance(n, ast.Name)
    } | {
        n.attr for n in ast.walk(tree) if isinstance(n, ast.Attribute)
    }
    assert "BybitExecutor" not in src_names


def test_bm_does_not_reference_live_credential_env_names():
    """BM code must never name BYBIT_API_KEY / BYBIT_API_SECRET (live)."""

    src = _bm_source_without_docstrings()
    forbidden_live = ("BYBIT_API_KEY", "BYBIT_API_SECRET")
    for name in forbidden_live:
        assert name not in src, f"BM must not reference live env name {name!r}"


def test_bm_does_not_call_stop_or_trading_stop_endpoint():
    src = _bm_source_without_docstrings()
    for forbidden in (
        "set-trading-stop",
        "v5/position/trading-stop",
        "v5/order/stop",
        "trading_stop",
    ):
        assert forbidden not in src, f"BM must not reference {forbidden!r}"


def test_bm_does_not_attach_stop_loss_or_take_profit():
    src = _bm_source_without_docstrings()
    # The exchange field names that would attach SL/TP. BM code must not
    # contain them.
    for forbidden in (
        "stopLoss",
        "takeProfit",
        "tpslMode",
        "tpOrderType",
        "slOrderType",
    ):
        assert forbidden not in src, f"BM must not set {forbidden!r}"


def test_bm_has_no_retry_loop_or_scheduler():
    src = _bm_source_without_docstrings()
    forbidden = (
        "schedule.every",
        "apscheduler",
        "BackgroundScheduler",
        "BlockingScheduler",
        "time.sleep",
        "for retry in range",
        "while True",
        "while not",
    )
    for tok in forbidden:
        assert tok not in src, f"BM must not contain {tok!r}"


def test_bm_imports_all_five_upstreams_directly():
    src = _bm_source()
    for mod_name in (
        "demo_only_tiny_execution_adapter ",
        "demo_only_tiny_execution_adapter_payload_dry_run ",
        "demo_only_tiny_execution_adapter_endpoint_guard_integration ",
        "demo_only_tiny_execution_adapter_final_pre_execution_checklist ",
        "demo_only_tiny_execution_adapter_tiny_order_preparation ",
    ):
        assert mod_name in src, f"BM must import {mod_name!r} (as upstream)"


def test_bm_chain_break_literals_present_in_source():
    src = _bm_source()
    assert 'TASK_ID = "TASK-014BM"' in src
    assert 'IS_REVIEW_CHAIN_SUFFIX = False' in src
    assert (
        'IMPLEMENTATION_PATH_PHASE = "tiny_order_execution"' in src
    )
    assert 'NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"' in src


def test_bm_only_demo_scoped_env_names_referenced_in_source():
    src = _bm_source()
    assert "BYBIT_DEMO_API_KEY" in src
    assert "BYBIT_DEMO_API_SECRET" in src
    # Confirm DEMO_SCOPED_ENV_NAMES literal stays canonical.
    assert "DEMO_SCOPED_ENV_NAMES" in src


# ---------------------------------------------------------------------------
# Cross-module: BybitExecutor / main / src.risk not imported by BM upstream chain
# ---------------------------------------------------------------------------


def test_bybit_executor_module_not_loaded_by_bm_import():
    assert "src.executors.bybit" not in sys.modules
    # Loading BM does not pull in any executor.
    from src import (
        demo_only_tiny_execution_adapter_tiny_order_execution as bm_reloaded,
    )

    assert bm_reloaded is bm
    assert "src.executors.bybit" not in sys.modules


def test_main_and_risk_not_loaded_by_bm_import():
    assert "main" not in sys.modules
    assert "src.risk" not in sys.modules


# ---------------------------------------------------------------------------
# BH chain-break guard accepts BM's NEXT_REQUIRED_TASK
# ---------------------------------------------------------------------------


def test_bh_chain_break_guard_accepts_bm_pointer():
    bh.assert_next_task_is_not_review_chain_suffix(bm.NEXT_REQUIRED_TASK)


@pytest.mark.parametrize(
    "forbidden_suffix",
    [
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ],
)
def test_bh_chain_break_guard_rejects_review_chain_suffixes_under_bm(
    forbidden_suffix,
):
    bad = "TASK-014BN_demo_only_tiny_execution_postfill_audit" + forbidden_suffix
    with pytest.raises(bh.DemoOnlyTinyExecutionAdapterError):
        bh.assert_next_task_is_not_review_chain_suffix(bad)


# ---------------------------------------------------------------------------
# Upstream still passes under BM
# ---------------------------------------------------------------------------


def test_bk_checklist_still_passes_under_bm():
    checklist = bk.run_final_pre_execution_checklist()
    assert checklist.all_passed is True


def test_bl_preparation_still_passes_under_bm():
    report = bl.run_tiny_order_preparation()
    assert report.all_passed is True
    assert report.packet is not None
    assert report.packet.symbol == "SOLUSDT"


# ---------------------------------------------------------------------------
# Report writer + Markdown content
# ---------------------------------------------------------------------------


def test_write_report_emits_four_files_and_round_trips(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    out = tmp_path / "bm_out"
    paths = bm.write_report(report, output_dir=out)
    assert set(paths) == {
        "latest_json",
        "latest_md",
        "timestamped_json",
        "timestamped_md",
    }
    for p in paths.values():
        assert p.exists()
        assert p.stat().st_size > 0
    # JSON round-trips.
    payload = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert payload["task_id"] == "TASK-014BM"
    assert payload["phase"] == "tiny_order_execution"
    assert payload["final_status"] == bm.STATUS_READINESS_OK_NO_NETWORK
    assert payload["max_order_count"] == 1
    md = paths["latest_md"].read_text(encoding="utf-8")
    assert "TASK-014BM" in md
    assert "tiny_order_execution" in md
    assert "READINESS_OK_NO_NETWORK" in md
    assert "max_order_count" in md
    assert "live_endpoint_denied" in md


def test_write_report_includes_plan_block_when_plan_built(tmp_path, monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    paths = bm.write_report(report, output_dir=tmp_path / "bm")
    md = paths["latest_md"].read_text(encoding="utf-8")
    assert "## Plan" in md
    assert "symbol: `SOLUSDT`" in md
    assert "qty: `0.01`" in md
    assert "order_type: `Market`" in md
    assert "time_in_force: `IOC`" in md
    assert "reduce_only: `False`" in md
    assert "endpoint_target: `https://api-demo.bybit.com/v5/order/create`" in md


# ---------------------------------------------------------------------------
# Body preview shape -- single demo order only
# ---------------------------------------------------------------------------


def test_body_preview_shape_for_default_packet(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    assert report.plan is not None
    body = dict(report.plan.body_preview)
    # Exactly the fields a single demo order needs -- no stop/TP fields.
    assert set(body) == {
        "category",
        "symbol",
        "side",
        "orderType",
        "qty",
        "timeInForce",
        "reduceOnly",
        "closeOnTrigger",
        "orderLinkId",
    }
    assert body["category"] == "linear"
    assert body["symbol"] == "SOLUSDT"
    assert body["side"] == "Buy"
    assert body["qty"] == "0.01"
    assert body["orderType"] == "Market"
    assert body["timeInForce"] == "IOC"
    assert body["reduceOnly"] is False
    assert body["closeOnTrigger"] is False
    assert body["orderLinkId"].startswith("DEMO_ONLY_TINY_BH_")


# ---------------------------------------------------------------------------
# Sender signature -- includes Bybit V5 HMAC headers
# ---------------------------------------------------------------------------


def test_signed_request_headers_include_bybit_v5_envelope(monkeypatch):
    _no_env(monkeypatch)
    captured: dict = {}

    def fake_sender(url, headers, body):
        captured["url"] = url
        captured["headers"] = dict(headers)
        captured["body"] = body
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":0,"retMsg":"OK","result":{"orderId":"oid"}}',
            "json": {"retCode": 0, "retMsg": "OK", "result": {"orderId": "oid"}},
        }

    creds = bm.DemoCredentials(
        api_key="kkk", api_secret="sss", recv_window="5000"
    )
    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=creds,
        sender=fake_sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    headers = captured["headers"]
    assert headers["X-BAPI-API-KEY"] == "kkk"
    assert "X-BAPI-TIMESTAMP" in headers
    assert headers["X-BAPI-RECV-WINDOW"] == "5000"
    assert "X-BAPI-SIGN" in headers
    assert len(headers["X-BAPI-SIGN"]) == 64  # SHA-256 hex
