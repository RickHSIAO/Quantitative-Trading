"""TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH -- Stage 2 tests.

These tests verify that BM's *actual* HTTPS request body switches its
``qty`` from the invalid BL packet qty (``"0.01"``) to the authorized
cap-escalation candidate qty (``"0.1"``) only when ALL of the following
hold simultaneously:

    * an :class:`AuthorizedExecutionQtyWiringReport` is threaded through,
    * its ``resolution.status`` is ``WIRING_AUTHORIZED_CANDIDATE_QTY``,
    * its ``resolution.execution_qty_source`` is
      ``CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY``,
    * its ``resolution.execution_qty`` parses as a positive ``Decimal``,
    * its ``resolution.execution_notional_estimate`` parses as a positive
      ``Decimal`` and is <= ``MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT`` (20),
    * the demo-only environment / symbol / side / orderType / TIF /
      flags / credentials gates still all pass.

When any one of these fails, BM rejects pre-network with status
``WIRING_REQUIRED_NO_NETWORK`` and NEVER silently falls back to
``qty=0.01``.

The tests are pure offline: ``sender`` is always a fake; no real
network call is made.
"""

from __future__ import annotations

import hashlib
import hmac
import json
from decimal import Decimal

import pytest

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


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _no_env(monkeypatch) -> None:
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
    ):
        monkeypatch.delenv(name, raising=False)


def _ir_response(candidate_qty: str = "0.1") -> dict:
    return {
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


def _authorized_wiring(candidate_qty: str = "0.1", mark_price: str = "100"):
    ir = bm_ir.run_instrument_rules_discovery(
        mark_price=mark_price,
        pre_parsed_response=_ir_response(candidate_qty=candidate_qty),
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


def _unauthorized_wiring():
    """Build a wiring report whose status is NOT
    ``WIRING_AUTHORIZED_CANDIDATE_QTY`` -- by omitting the cap-escalation
    flag, the gate emits NOT_AUTHORIZED and the wiring follows.
    """
    ir = bm_ir.run_instrument_rules_discovery(
        mark_price="100", pre_parsed_response=_ir_response(),
    )
    request = bm_ce.EscalationAuthorizationRequest(
        proposed_qty="0.1",
        explicit_demo_min_qty_cap_authorization_flag=False,
        explicit_demo_min_qty_cap_authorization_marker="",
    )
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    return bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )


def _capture_sender(captured: dict):
    def sender(url, headers, body):
        captured["url"] = url
        captured["headers"] = dict(headers)
        captured["body"] = body
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":0,"retMsg":"OK","result":{"orderId":"demo-stage2"}}',
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "demo-stage2"},
            },
        }

    return sender


def _must_not_call_sender(url, headers, body):  # pragma: no cover
    raise AssertionError(f"sender invoked unexpectedly: url={url!r}")


def _creds():
    return bm.DemoCredentials(
        api_key="demo_key_stage2", api_secret="demo_secret_stage2"
    )


# ---------------------------------------------------------------------------
# 1. Public surface
# ---------------------------------------------------------------------------


def test_stage2_constants_exported():
    assert bm.STATUS_WIRING_REQUIRED_NO_NETWORK == "WIRING_REQUIRED_NO_NETWORK"
    assert bm.EXECUTE_BODY_QTY_SOURCE_BL_PACKET == "BL_PACKET_QTY"
    assert bm.EXECUTE_BODY_QTY_SOURCE_AUTHORIZED_CANDIDATE == (
        "CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY"
    )
    assert bm.EXECUTE_BODY_QTY_SOURCE_NONE == "NONE"
    assert bm.EXECUTE_BODY_QTY_SOURCE_REJECTED_NO_FALLBACK == (
        "REJECTED_NO_FALLBACK_TO_0_01"
    )
    assert bm.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT == Decimal("20")


# ---------------------------------------------------------------------------
# 2. Happy path -- body qty becomes 0.1 only when fully authorized
# ---------------------------------------------------------------------------


def test_authorized_wiring_switches_body_qty_to_zero_point_one(monkeypatch):
    _no_env(monkeypatch)
    captured: dict = {}
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=_capture_sender(captured),
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.final_status == bm.STATUS_EXECUTED_DEMO_ONLY
    assert report.body_qty_authorized_override is True
    assert report.actual_request_body_qty == "0.1"
    assert report.actual_request_body_qty_source == (
        bm.EXECUTE_BODY_QTY_SOURCE_AUTHORIZED_CANDIDATE
    )
    assert report.body_qty_rejection_reason == ""
    body_dict = json.loads(captured["body"].decode("utf-8"))
    assert body_dict["qty"] == "0.1"
    assert body_dict["symbol"] == "SOLUSDT"
    assert body_dict["side"] == "Buy"
    assert body_dict["orderType"] == "Market"
    assert body_dict["timeInForce"] == "IOC"


def test_authorized_wiring_plan_records_authorized_qty(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.plan is not None
    assert report.plan.actual_request_body_qty == "0.1"
    assert report.plan.actual_request_body_qty_source == (
        bm.EXECUTE_BODY_QTY_SOURCE_AUTHORIZED_CANDIDATE
    )
    assert report.plan.body_qty_authorized_override is True
    body_preview = dict(report.plan.body_preview)
    assert body_preview["qty"] == "0.1"


# ---------------------------------------------------------------------------
# 3. Fake-sender body / signing equality
# ---------------------------------------------------------------------------


def test_signed_body_string_equals_posted_body_bytes(monkeypatch):
    """The exact bytes posted must equal the bytes used to compute the
    signature: no whitespace, no key reordering, no re-serialization."""

    _no_env(monkeypatch)
    captured: dict = {}
    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=_capture_sender(captured),
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    body_bytes = captured["body"]
    headers = captured["headers"]
    timestamp = headers["X-BAPI-TIMESTAMP"]
    recv_window = headers["X-BAPI-RECV-WINDOW"]
    api_key = headers["X-BAPI-API-KEY"]
    pre_sign = (
        timestamp + api_key + recv_window + body_bytes.decode("utf-8")
    )
    expected = hmac.new(
        b"demo_secret_stage2", pre_sign.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert headers["X-BAPI-SIGN"] == expected
    assert len(headers["X-BAPI-SIGN"]) == 64
    assert headers["X-BAPI-SIGN-TYPE"] == "2"
    # Body must contain the authorized qty:
    assert b'"qty":"0.1"' in body_bytes or b'"qty": "0.1"' in body_bytes


# ---------------------------------------------------------------------------
# 4. Fail-closed: missing / rejected / over-cap / blank wiring
# ---------------------------------------------------------------------------


def test_missing_wiring_rejects_pre_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=_must_not_call_sender,
        # NO authorized_execution_qty_wiring -- fail closed.
    )
    assert report.final_status == bm.STATUS_WIRING_REQUIRED_NO_NETWORK
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False
    assert report.body_qty_authorized_override is False
    assert report.actual_request_body_qty_source == (
        bm.EXECUTE_BODY_QTY_SOURCE_BL_PACKET
    )
    assert report.body_qty_rejection_reason != ""


def test_unauthorized_wiring_rejects_pre_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=_must_not_call_sender,
        authorized_execution_qty_wiring=_unauthorized_wiring(),
    )
    assert report.final_status == bm.STATUS_WIRING_REQUIRED_NO_NETWORK
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.body_qty_authorized_override is False
    assert report.actual_request_body_qty_source == (
        bm.EXECUTE_BODY_QTY_SOURCE_REJECTED_NO_FALLBACK
    )
    assert report.actual_request_body_qty == ""


def test_over_cap_wiring_rejects_pre_network(monkeypatch):
    """When the authorized notional would exceed the 20 USDT BM mirror,
    BM rejects pre-network even if the upstream gate authorized it."""

    _no_env(monkeypatch)
    # mark_price=1000, candidate_qty=0.1 -> notional=100 USDT > 20 cap.
    # The upstream gate uses MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT=20 too, so
    # it'll reject with GATE_OVER_CAP and the wiring follows. Either way
    # BM must NOT send.
    ir = bm_ir.run_instrument_rules_discovery(
        mark_price="1000",
        pre_parsed_response=_ir_response(candidate_qty="0.1"),
    )
    request = bm_ce.EscalationAuthorizationRequest(
        proposed_qty="0.1",
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=(
            bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
        ),
    )
    gate = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir, request=request
    )
    wiring = bm_wire.run_authorized_execution_qty_wiring(
        instrument_rules_report=ir, cap_escalation_report=gate
    )

    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=_must_not_call_sender,
        authorized_execution_qty_wiring=wiring,
    )
    assert report.final_status == bm.STATUS_WIRING_REQUIRED_NO_NETWORK
    assert report.order_sent is False
    assert report.body_qty_authorized_override is False
    assert report.actual_request_body_qty == ""


# ---------------------------------------------------------------------------
# 5. Never fall back to BL qty=0.01 on rejected paths
# ---------------------------------------------------------------------------


def test_rejected_paths_never_send_zero_point_zero_one_to_network(monkeypatch):
    """No rejected path may EVER reach the sender with qty=0.01.

    The sender is wired to fail loudly if invoked. We verify that for
    both "no wiring" and "unauthorized wiring", the sender is never
    called and the override flag stays False. The visibility surface
    on the None branch may still record the packet qty (0.01) for
    inspection, but that value MUST NOT leak into a network call --
    the pre-network rejection guarantees that.
    """

    _no_env(monkeypatch)
    for wiring_factory in (lambda: None, _unauthorized_wiring):
        wiring = wiring_factory()
        kwargs = dict(
            mode=bm.MODE_EXECUTE_DEMO_ORDER,
            execute_flag=True,
            confirm_flag=True,
            credentials=_creds(),
            sender=_must_not_call_sender,
        )
        if wiring is not None:
            kwargs["authorized_execution_qty_wiring"] = wiring
        report = bm.run_explicit_tiny_order_execution(**kwargs)
        assert report.final_status == bm.STATUS_WIRING_REQUIRED_NO_NETWORK
        assert report.order_sent is False
        assert report.network_attempted is False
        assert report.body_qty_authorized_override is False


def test_rejected_wiring_surfaces_empty_qty_no_fallback(monkeypatch):
    """When the wiring report is supplied but unauthorized, the surfaced
    actual_request_body_qty MUST be empty (the REJECTED_NO_FALLBACK
    source label exists precisely to refuse the 0.01 fallback)."""

    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=_must_not_call_sender,
        authorized_execution_qty_wiring=_unauthorized_wiring(),
    )
    assert report.actual_request_body_qty == ""
    assert report.actual_request_body_qty_source == (
        bm.EXECUTE_BODY_QTY_SOURCE_REJECTED_NO_FALLBACK
    )


# ---------------------------------------------------------------------------
# 6. Mode-by-mode: readiness / dry_run with no wiring keep packet qty
# ---------------------------------------------------------------------------


def test_readiness_without_wiring_keeps_packet_qty_for_visibility(monkeypatch):
    """Readiness mode never sends, so missing wiring is acceptable. The
    body_preview surfaces the BL packet qty (0.01) for inspection."""

    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    assert report.plan is not None
    assert report.plan.body_preview["qty"] == "0.01"
    assert report.actual_request_body_qty_source == (
        bm.EXECUTE_BODY_QTY_SOURCE_BL_PACKET
    )
    assert report.body_qty_authorized_override is False
    assert report.network_attempted is False


def test_dry_run_without_wiring_does_not_call_network(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_DRY_RUN)
    assert report.network_attempted is False
    assert report.order_sent is False
    assert report.body_qty_authorized_override is False


# ---------------------------------------------------------------------------
# 7. Missing flags / credentials still block before wiring check
# ---------------------------------------------------------------------------


def test_missing_execute_flag_blocks_before_wiring_check(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=False,
        confirm_flag=True,
        credentials=_creds(),
        sender=_must_not_call_sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.final_status == bm.STATUS_GATE_REJECTED_NO_NETWORK
    assert report.order_sent is False


def test_missing_credentials_blocks_before_wiring_check(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        sender=_must_not_call_sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.final_status == bm.STATUS_MISSING_DEMO_CREDENTIALS
    assert report.order_sent is False


# ---------------------------------------------------------------------------
# 8. retCode mapping under authorized override qty
# ---------------------------------------------------------------------------


def test_retcode_nonzero_with_authorized_qty_maps_to_rejected_no_order_sent(
    monkeypatch,
):
    """Even with authorized qty=0.1, a non-zero Bybit retCode must NEVER
    be reported as EXECUTED_DEMO_ONLY."""

    _no_env(monkeypatch)

    def sender(url, headers, body):
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":10004,"retMsg":"Error sign!","result":{}}',
            "json": {
                "retCode": 10004,
                "retMsg": "Error sign!",
                "result": {},
            },
        }

    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.final_status == bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT
    assert report.order_sent is False
    assert report.bybit_ret_code == 10004
    # Body still contained authorized qty even though Bybit rejected:
    assert report.actual_request_body_qty == "0.1"
    assert report.body_qty_authorized_override is True


def test_retcode_zero_empty_order_id_with_authorized_qty_not_executed(
    monkeypatch,
):
    _no_env(monkeypatch)

    def sender(url, headers, body):
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":0,"retMsg":"OK","result":{"orderId":""}}',
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": ""},
            },
        }

    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert report.final_status == bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT
    assert report.order_sent is False


# ---------------------------------------------------------------------------
# 9. Only one sender call ever -- no retry under authorized override
# ---------------------------------------------------------------------------


def test_authorized_override_still_sends_at_most_one_call(monkeypatch):
    _no_env(monkeypatch)
    counter = {"n": 0}

    def sender(url, headers, body):
        counter["n"] += 1
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":0,"retMsg":"OK","result":{"orderId":"oid"}}',
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "oid"},
            },
        }

    bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=sender,
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    assert counter["n"] == 1


# ---------------------------------------------------------------------------
# 10. Internal helper -- _derive_body_qty_from_wiring boundary cases
# ---------------------------------------------------------------------------


def test_derive_body_qty_from_wiring_none_returns_packet_fallback():
    qty, source, override, reason = bm._derive_body_qty_from_wiring(
        None, packet_qty="0.01"
    )
    assert qty == "0.01"
    assert source == bm.EXECUTE_BODY_QTY_SOURCE_BL_PACKET
    assert override is False
    assert reason


def test_derive_body_qty_from_wiring_authorized_returns_candidate():
    wiring = _authorized_wiring()
    qty, source, override, reason = bm._derive_body_qty_from_wiring(
        wiring, packet_qty="0.01"
    )
    assert qty == "0.1"
    assert source == bm.EXECUTE_BODY_QTY_SOURCE_AUTHORIZED_CANDIDATE
    assert override is True
    assert reason == ""


def test_derive_body_qty_from_wiring_unauthorized_no_fallback():
    wiring = _unauthorized_wiring()
    qty, source, override, reason = bm._derive_body_qty_from_wiring(
        wiring, packet_qty="0.01"
    )
    assert qty == ""
    assert source == bm.EXECUTE_BODY_QTY_SOURCE_REJECTED_NO_FALLBACK
    assert override is False
    assert reason


# ---------------------------------------------------------------------------
# 11. Plan / Report defaulted-field backward compatibility
# ---------------------------------------------------------------------------


def test_report_to_dict_includes_stage2_fields(monkeypatch):
    _no_env(monkeypatch)
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_EXECUTE_DEMO_ORDER,
        execute_flag=True,
        confirm_flag=True,
        credentials=_creds(),
        sender=_capture_sender({}),
        authorized_execution_qty_wiring=_authorized_wiring(),
    )
    d = report.to_dict()
    assert d["actual_request_body_qty"] == "0.1"
    assert d["actual_request_body_qty_source"] == (
        bm.EXECUTE_BODY_QTY_SOURCE_AUTHORIZED_CANDIDATE
    )
    assert d["body_qty_authorized_override"] is True
    assert d["body_qty_rejection_reason"] == ""
