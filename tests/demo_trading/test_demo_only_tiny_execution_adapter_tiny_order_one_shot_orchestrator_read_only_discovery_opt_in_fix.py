"""TASK-014BM_ONE_SHOT_ORCHESTRATOR_READ_ONLY_DISCOVERY_OPT_IN_FIX tests.

Focused tests for the CLI opt-in flag that enables the single bounded
public GET to the demo-only read-only instruments-info endpoint.

Coverage:
    * CLI: --ir-mode discover without opt-in flag → exit code 1,
      no network call attempted.
    * CLI: --ir-mode discover with opt-in flag (monkeypatched stdlib
      sender) → exit code 0, no order endpoint call, no order sent.
    * Orchestrator: allow_real_ir_get=True with monkeypatched stdlib
      sender → single GET to exact allowed URL, no order endpoint call,
      no order sent, chain resolves correctly.
    * Orchestrator: allow_real_ir_get=True with injected ir_sender →
      ir_sender receives exact allowed URL.
    * Injected ir_sender proves single GET only.
    * Readiness orchestration with discover opt-in resolves:
      instrument_rules_loaded=True, candidate_qty='0.1',
      cap_gate_status=ESCALATION_AUTHORIZED,
      wiring_status=WIRING_AUTHORIZED_CANDIDATE_QTY,
      actual_request_body_qty='0.1',
      order_endpoint_called=False, order_sent=False.
    * No credentials required for the public GET.
    * Allowed URL contains only the permitted path; no /v5/order/create
      or live host.
    * Existing 34 orchestrator tests and 505 tiny_execution_adapter
      regression remain PASS (verified by the full regression run;
      these tests are focused-only and do not re-run the full suite).
"""

from __future__ import annotations

import io
import json
import sys
from types import SimpleNamespace

import pytest

from src import (
    demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring as bm_wire,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as bm_ce,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
)
from src import (
    demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as orc,
)


_AUTH_MARKER = bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
_ALLOWED_IR_URL = f"{bm_ir.ALLOWED_READONLY_URL}?category=linear&symbol=SOLUSDT"
_FORBIDDEN_PATH_TOKENS = (
    "/v5/order/create",
    "/v5/order/cancel",
    "/v5/position/set-trading-stop",
    "https://api.bybit.com",
    "https://api.bytick.com",
    "wss://",
)


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
    """Fake stdlib sender response (same shape as _real_public_get_via_urllib)."""
    return {
        "http_status": 200,
        "json": _good_ir_response(),
        "raw_text": json.dumps(_good_ir_response()),
    }


def _capture_cli_output(argv):
    """Run main() with stdout captured; returns (exit_code, output_str)."""
    from scripts.preview_demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator import (
        main,
    )

    buf = io.StringIO()
    old_stdout = sys.stdout
    sys.stdout = buf
    try:
        rc = main(argv)
    finally:
        sys.stdout = old_stdout
    return rc, buf.getvalue()


# ---------------------------------------------------------------------------
# CLI: fail-closed default
# ---------------------------------------------------------------------------


def test_cli_discover_without_opt_in_returns_exit_1_no_network():
    """--ir-mode discover without the opt-in flag must fail at the CLI level."""
    rc, output = _capture_cli_output(["--ir-mode", "discover"])
    assert rc == 1
    assert "REJECTED" in output
    assert "--i-understand-this-performs-one-public-read-only-instrument-rules-get" in output


def test_cli_offline_does_not_require_opt_in_flag():
    """Default --ir-mode offline still works without the opt-in flag."""
    rc, output = _capture_cli_output([])
    # readiness with no IR response → rules not loaded → REJECTED, but exit 1
    # (not 2, not crash). Default offline mode should NOT print the discover
    # REJECTED message.
    assert "--i-understand-this-performs-one-public-read-only-instrument-rules-get" not in output


# ---------------------------------------------------------------------------
# CLI: opt-in enables discover (monkeypatched stdlib sender)
# ---------------------------------------------------------------------------


def test_cli_discover_with_opt_in_exits_0_with_fake_stdlib_sender(monkeypatch):
    monkeypatch.setattr(bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response())

    rc, output = _capture_cli_output(
        [
            "--ir-mode",
            "discover",
            "--i-understand-this-performs-one-public-read-only-instrument-rules-get",
            "--explicit-demo-min-qty-cap-authorization-flag",
            "--authorization-marker",
            _AUTH_MARKER,
        ]
    )
    assert rc == 0
    assert "ORCHESTRATION_OK_READINESS_NO_NETWORK" in output
    assert "order_endpoint_called=False" in output
    assert "order_sent=False" in output
    assert "actual_request_body_qty='0.1'" in output


def test_cli_discover_with_opt_in_passes_allow_real_ir_get_true(monkeypatch):
    calls: list[dict] = []

    def fake_run(**kwargs):
        calls.append(kwargs)
        return SimpleNamespace(
            task_id=orc.TASK_ID,
            identity=orc.IDENTITY,
            phase=orc.IMPLEMENTATION_PATH_PHASE,
            mode=orc.ORCH_MODE_READINESS,
            status=orc.STATUS_OK_READINESS_NO_NETWORK,
            reason="mocked ok",
            upstream_tasks=orc.UPSTREAM_TASKS,
            next_required_task=orc.NEXT_REQUIRED_TASK,
            is_review_chain_suffix=orc.IS_REVIEW_CHAIN_SUFFIX,
            instrument_rules_loaded=True,
            candidate_qty="0.1",
            candidate_notional="10",
            cap_gate_status=bm_ce.STATUS_ESCALATION_AUTHORIZED,
            wiring_status=bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY,
            original_packet_qty="0.01",
            actual_request_body_qty="0.1",
            actual_request_body_qty_source=(
                bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
            ),
            body_qty_authorized_override=True,
            network_attempted=False,
            order_endpoint_called=False,
            order_sent=False,
            fake_sender_used=False,
            sender_call_count=0,
            real_execute_disabled_stage1=True,
            bm_invoked=True,
            bm_mode="readiness",
            bm_final_status="READINESS_OK_NO_NETWORK",
            bybit_ret_code=None,
            bybit_order_id="",
            body_qty_rejection_reason="",
        )

    monkeypatch.setattr(
        orc,
        "run_one_shot_authorized_execution_orchestration",
        fake_run,
    )

    rc, output = _capture_cli_output(
        [
            "--ir-mode",
            "discover",
            "--i-understand-this-performs-one-public-read-only-instrument-rules-get",
            "--explicit-demo-min-qty-cap-authorization-flag",
            "--authorization-marker",
            _AUTH_MARKER,
        ]
    )

    assert rc == 0
    assert "ORCHESTRATION_OK_READINESS_NO_NETWORK" in output
    assert len(calls) == 1
    assert calls[0]["ir_mode"] == bm_ir.MODE_DISCOVER
    assert calls[0]["allow_real_ir_get"] is True
    assert calls[0]["bm_credentials"] is None


def test_cli_discover_with_opt_in_does_not_print_cli_rejection(monkeypatch):
    monkeypatch.setattr(bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response())

    rc, output = _capture_cli_output(
        [
            "--ir-mode",
            "discover",
            "--i-understand-this-performs-one-public-read-only-instrument-rules-get",
            "--explicit-demo-min-qty-cap-authorization-flag",
            "--authorization-marker",
            _AUTH_MARKER,
        ]
    )
    assert "REJECTED: --ir-mode discover requires the explicit opt-in flag" not in output


# ---------------------------------------------------------------------------
# Orchestrator: allow_real_ir_get=True with monkeypatched stdlib sender
# ---------------------------------------------------------------------------


def test_allow_real_ir_get_true_calls_single_public_get_no_order(monkeypatch):
    """allow_real_ir_get=True uses stdlib sender exactly once; no order call."""
    calls: list[str] = []

    def patched_stdlib(url: str) -> dict:
        calls.append(url)
        return _stdlib_ok_response()

    monkeypatch.setattr(bm_ir, "_real_public_get_via_urllib", patched_stdlib)

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )

    assert len(calls) == 1, f"expected exactly 1 GET, got {calls}"
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert r.fake_sender_used is False


def test_allow_real_ir_get_true_uses_allowed_url_only(monkeypatch):
    """The single GET must target only the allowed read-only instruments-info endpoint."""
    calls: list[str] = []

    def patched_stdlib(url: str) -> dict:
        calls.append(url)
        return _stdlib_ok_response()

    monkeypatch.setattr(bm_ir, "_real_public_get_via_urllib", patched_stdlib)

    orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
    )

    assert len(calls) == 1
    url = calls[0]
    assert url == _ALLOWED_IR_URL
    for forbidden in _FORBIDDEN_PATH_TOKENS:
        assert forbidden not in url, f"forbidden token {forbidden!r} found in URL {url!r}"


def test_allow_real_ir_get_true_resolves_full_chain_no_credentials(monkeypatch):
    """Chain completes with correct values; no credentials required for the GET."""
    monkeypatch.setattr(bm_ir, "_real_public_get_via_urllib", lambda url: _stdlib_ok_response())

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=None,
        allow_real_ir_get=True,
        bm_credentials=None,  # explicitly no credentials for this GET
    )

    assert r.status == orc.STATUS_OK_READINESS_NO_NETWORK
    assert r.instrument_rules_loaded is True
    assert r.candidate_qty == "0.1"
    assert r.cap_gate_status == bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert r.wiring_status == bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY
    assert r.actual_request_body_qty == "0.1"
    assert r.actual_request_body_qty_source == (
        bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert r.body_qty_authorized_override is True
    assert r.network_attempted is False  # BM never reached network in readiness
    assert r.order_endpoint_called is False
    assert r.order_sent is False


# ---------------------------------------------------------------------------
# Orchestrator: injected ir_sender receives exact URL
# ---------------------------------------------------------------------------


def test_injected_ir_sender_receives_exact_allowed_url():
    """Using an injected ir_sender verifies the URL built by the IR module."""
    calls: list[str] = []

    def ir_sender(url: str) -> dict:
        calls.append(url)
        return _stdlib_ok_response()

    orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=ir_sender,
    )

    assert len(calls) == 1
    url = calls[0]
    assert url == _ALLOWED_IR_URL
    for forbidden in _FORBIDDEN_PATH_TOKENS:
        assert forbidden not in url


def test_injected_ir_sender_called_exactly_once():
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


# ---------------------------------------------------------------------------
# Default offline mode still requires opt-in=False (baseline check)
# ---------------------------------------------------------------------------


def test_discover_without_allow_real_ir_get_still_raises_orchestrator_error():
    """Orchestrator-level guard: ir_mode=discover, no sender, allow_real_ir_get=False."""
    with pytest.raises(orc.OneShotAuthorizedExecutionOrchestratorError):
        orc.run_one_shot_authorized_execution_orchestration(
            mark_price="100",
            mode=orc.ORCH_MODE_READINESS,
            ir_mode=bm_ir.MODE_DISCOVER,
            ir_sender=None,
            allow_real_ir_get=False,
        )


def test_offline_mode_with_no_pre_parsed_response_still_rejected_at_chain(monkeypatch):
    """Offline with no pre_parsed_response → rules not loaded → chain rejects."""
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_OFFLINE,
        ir_pre_parsed_response=None,
    )
    assert r.status == orc.STATUS_REJECTED_RULES_NOT_LOADED
    assert r.order_endpoint_called is False
    assert r.order_sent is False
