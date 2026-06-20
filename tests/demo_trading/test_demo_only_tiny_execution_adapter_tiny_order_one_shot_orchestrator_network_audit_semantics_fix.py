"""TASK-014BM_ONE_SHOT_ORCHESTRATOR_NETWORK_AUDIT_SEMANTICS_FIX tests.

Focused tests verifying the three explicit immutable network audit fields:

    read_only_network_attempted
        True only when a real public instrument-rules GET was attempted
        (inject ir_sender or allow_real_ir_get=True with MODE_DISCOVER).

    order_network_attempted
        True only when BM attempts an order network call (fake sender path).

    network_attempted
        Aggregate OR of the two fields above.

Coverage:
    * Offline readiness: all three network fields False.
    * Discover path (monkeypatched stdlib): read_only=True, order=False,
      aggregate=True.
    * Discover path (injected ir_sender): read_only=True, order=False,
      aggregate=True.
    * Fake BM sender execute path: order=True, aggregate=True.
    * Exact one read-only GET counted (injected sender).
    * No order endpoint call in discover+readiness.
    * No order sent in discover+readiness.
    * Reason string no longer says "no network attempted" after public GET.
    * Reason string says "no network attempted" for offline readiness.
    * to_dict() exposes all three new network fields.
    * JSON report contains all three new network fields.
    * Markdown rendering contains all three new network fields.
    * Rejection after IR (cap gate) carries correct read_only field.
    * Aggregate is always OR of the two sub-fields.
"""

from __future__ import annotations

import io
import json
import shutil
import sys
import tempfile

import pytest

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
from src import (
    demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as orc,
)


_AUTH_MARKER = bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER


def _good_ir_response(
    *,
    symbol: str = "SOLUSDT",
    status: str = "Trading",
    min_order_qty: str = "0.1",
    qty_step: str = "0.1",
) -> dict:
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "symbol": symbol,
                    "status": status,
                    "lotSizeFilter": {
                        "minOrderQty": min_order_qty,
                        "qtyStep": qty_step,
                        "minNotionalValue": "5",
                        "maxMktOrderQty": "12000",
                    },
                    "priceFilter": {"tickSize": "0.010"},
                }
            ]
        },
    }


def _stdlib_ok_response() -> dict:
    return {
        "http_status": 200,
        "json": _good_ir_response(),
        "raw_text": json.dumps(_good_ir_response()),
    }


def _offline_readiness(**overrides):
    kwargs = dict(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
    )
    kwargs.update(overrides)
    return orc.run_one_shot_authorized_execution_orchestration(**kwargs)


def _fake_sender_factory(captured: dict | None = None):
    def fake_sender(url, headers, body):
        if captured is not None:
            captured["url"] = url
            captured["headers"] = dict(headers)
            captured["body"] = body
        return {
            "http_status": 200,
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "fake-1", "orderLinkId": "l-1"},
            },
            "raw_text": "{}",
        }

    return fake_sender


def _execute_fake(**overrides):
    kwargs = dict(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=bm.DemoCredentials(
            api_key="key", api_secret="secret", recv_window="5000"
        ),
        bm_fake_sender=_fake_sender_factory(),
    )
    kwargs.update(overrides)
    return orc.run_one_shot_authorized_execution_orchestration(**kwargs)


# ---------------------------------------------------------------------------
# 1. Offline readiness: all three network fields False
# ---------------------------------------------------------------------------


def test_offline_readiness_all_three_network_fields_false():
    r = _offline_readiness()
    assert r.read_only_network_attempted is False
    assert r.order_network_attempted is False
    assert r.network_attempted is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False


def test_offline_readiness_network_attempted_is_aggregate_or():
    r = _offline_readiness()
    assert r.network_attempted == (
        r.read_only_network_attempted or r.order_network_attempted
    )


# ---------------------------------------------------------------------------
# 2. Discover path using monkeypatched stdlib sender
# ---------------------------------------------------------------------------


def test_discover_stdlib_read_only_true_order_false_aggregate_true(
    monkeypatch,
):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert r.read_only_network_attempted is True
    assert r.order_network_attempted is False
    assert r.network_attempted is True
    assert r.order_endpoint_called is False
    assert r.order_sent is False


def test_discover_stdlib_aggregate_is_or_of_sub_fields(monkeypatch):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert r.network_attempted == (
        r.read_only_network_attempted or r.order_network_attempted
    )


# ---------------------------------------------------------------------------
# 3. Injected IR sender path
# ---------------------------------------------------------------------------


def test_injected_ir_sender_read_only_true_order_false_aggregate_true():
    calls: list[str] = []

    def ir_sender(url: str) -> dict:
        calls.append(url)
        return _stdlib_ok_response()

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=ir_sender,
    )
    assert r.read_only_network_attempted is True
    assert r.order_network_attempted is False
    assert r.network_attempted is True
    assert r.order_endpoint_called is False
    assert r.order_sent is False


def test_injected_ir_sender_counted_exactly_once():
    counter = {"n": 0}

    def ir_sender(url: str) -> dict:
        counter["n"] += 1
        return _stdlib_ok_response()

    orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=ir_sender,
    )
    assert counter["n"] == 1


def test_injected_ir_sender_aggregate_is_or(monkeypatch):
    def ir_sender(url: str) -> dict:
        return _stdlib_ok_response()

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=ir_sender,
    )
    assert r.network_attempted == (
        r.read_only_network_attempted or r.order_network_attempted
    )


# ---------------------------------------------------------------------------
# 4. Fake BM sender execute path: order_network_attempted=True
# ---------------------------------------------------------------------------


def test_fake_bm_sender_order_network_attempted_true():
    r = _execute_fake()
    assert r.order_network_attempted is True
    assert r.network_attempted is True
    assert r.fake_sender_used is True


def test_fake_bm_sender_offline_ir_read_only_false():
    r = _execute_fake()  # default: offline ir_pre_parsed_response
    assert r.read_only_network_attempted is False
    assert r.order_network_attempted is True
    assert r.network_attempted is True


def test_fake_bm_sender_with_injected_ir_both_network_fields_true():
    def ir_sender(url: str) -> dict:
        return _stdlib_ok_response()

    r = _execute_fake(
        ir_pre_parsed_response=None,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=ir_sender,
    )
    assert r.read_only_network_attempted is True
    assert r.order_network_attempted is True
    assert r.network_attempted is True


def test_fake_bm_sender_aggregate_is_or():
    r = _execute_fake()
    assert r.network_attempted == (
        r.read_only_network_attempted or r.order_network_attempted
    )


# ---------------------------------------------------------------------------
# 5. No order endpoint call in discover+readiness
# ---------------------------------------------------------------------------


def test_discover_readiness_no_order_endpoint_called(monkeypatch):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert r.order_endpoint_called is False


def test_discover_readiness_no_order_sent(monkeypatch):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert r.order_sent is False


# ---------------------------------------------------------------------------
# 6. Reason string semantics
# ---------------------------------------------------------------------------


def test_reason_after_public_get_does_not_say_no_network_attempted(
    monkeypatch,
):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert "no network attempted" not in r.reason


def test_reason_after_public_get_describes_read_only_get(monkeypatch):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert "read-only" in r.reason.lower() or "instrument-rules" in r.reason


def test_reason_after_public_get_says_no_order_network_call(monkeypatch):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert "no order network" in r.reason.lower()


def test_reason_offline_readiness_still_says_no_network_attempted():
    r = _offline_readiness()
    assert "no network attempted" in r.reason


# ---------------------------------------------------------------------------
# 7. to_dict() and JSON report expose all three new fields
# ---------------------------------------------------------------------------


def test_to_dict_exposes_all_three_network_fields():
    r = _offline_readiness()
    d = r.to_dict()
    assert "read_only_network_attempted" in d
    assert "order_network_attempted" in d
    assert "network_attempted" in d
    assert d["read_only_network_attempted"] is False
    assert d["order_network_attempted"] is False
    assert d["network_attempted"] is False


def test_json_report_contains_three_network_fields():
    tmp = tempfile.mkdtemp()
    try:
        r = _offline_readiness()
        paths = orc.write_report(r, output_dir=tmp)
        obj = json.loads(paths["json_latest"].read_text(encoding="utf-8"))
        assert "read_only_network_attempted" in obj
        assert "order_network_attempted" in obj
        assert "network_attempted" in obj
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


def test_json_report_discover_path_has_correct_values(monkeypatch):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    tmp = tempfile.mkdtemp()
    try:
        paths = orc.write_report(r, output_dir=tmp)
        obj = json.loads(paths["json_latest"].read_text(encoding="utf-8"))
        assert obj["read_only_network_attempted"] is True
        assert obj["order_network_attempted"] is False
        assert obj["network_attempted"] is True
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 8. Markdown rendering
# ---------------------------------------------------------------------------


def test_markdown_report_contains_all_three_network_fields():
    tmp = tempfile.mkdtemp()
    try:
        r = _offline_readiness()
        paths = orc.write_report(r, output_dir=tmp)
        md = paths["md_latest"].read_text(encoding="utf-8")
        assert "read_only_network_attempted" in md
        assert "order_network_attempted" in md
        assert "network_attempted" in md
        assert "order_endpoint_called" in md
        assert "order_sent" in md
    finally:
        shutil.rmtree(tmp, ignore_errors=True)


# ---------------------------------------------------------------------------
# 9. Rejection after IR (cap gate) carries correct read_only field
# ---------------------------------------------------------------------------


def test_cap_gate_rejection_after_discover_carries_read_only_true(monkeypatch):
    monkeypatch.setattr(
        bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response()
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=False,  # cap gate will reject
        explicit_demo_min_qty_cap_authorization_marker="",
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert r.read_only_network_attempted is True
    assert r.order_network_attempted is False
    assert r.network_attempted is True
    assert r.order_endpoint_called is False
    assert r.order_sent is False


def test_cap_gate_rejection_offline_all_network_fields_false():
    r = _offline_readiness(
        explicit_demo_min_qty_cap_authorization_flag=False,
        explicit_demo_min_qty_cap_authorization_marker="",
    )
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert r.read_only_network_attempted is False
    assert r.order_network_attempted is False
    assert r.network_attempted is False
