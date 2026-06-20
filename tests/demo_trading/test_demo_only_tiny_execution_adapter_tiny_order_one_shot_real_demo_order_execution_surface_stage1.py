"""TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1 tests.

Focused Stage 1 tests for the isolated real-demo-order execution
surface introduced by
``ORCH_MODE_EXECUTE_REAL_DEMO_ORDER``. Stage 1 hard contract:

    * The new mode is recognised as a public surface.
    * The new mode requires both an explicit
      ``explicit_real_demo_execute_flag`` and the exact
      ``EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER``.
    * The full chain (instrument rules -> cap-escalation gate ->
      authorized wiring -> BM exact-body signing) runs only after the
      pre-flight authorization gate passes.
    * The actual request body qty is sourced ONLY from the cap
      escalation authorized candidate qty -- never from the BL packet
      ``0.01`` fallback.
    * A real ``/v5/order/create`` call is **unreachable** in Stage 1.
      The orchestrator's `_invoke_bm` refuses to run the real send
      path; instead, offline validation is performed by injecting a
      callable ``bm_fake_sender``.
    * The 20 USDT notional cap and ``MAX_ORDER_COUNT=1`` are immutable.
    * The CLI default invocation cannot reach the order endpoint.
    * The CLI explicitly refuses any real-sender configuration.
"""

from __future__ import annotations

import hashlib
import hmac
import io
import json
import sys
from decimal import Decimal

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


_CAP_MARKER = bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
_REAL_DEMO_MARKER = orc.EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER


def _ir_sender_factory(response: dict):
    """Build a discover-mode IR sender returning the given parsed response."""

    def ir_sender(url: str) -> dict:
        return {
            "http_status": 200,
            "json": response,
            "raw_text": json.dumps(response),
        }

    return ir_sender


def _good_ir_response() -> dict:
    return {
        "retCode": 0,
        "retMsg": "OK",
        "result": {
            "list": [
                {
                    "symbol": "SOLUSDT",
                    "status": "Trading",
                    "lotSizeFilter": {
                        "minOrderQty": "0.1",
                        "qtyStep": "0.1",
                        "minNotionalValue": "5",
                        "maxMktOrderQty": "12000",
                    },
                    "priceFilter": {"tickSize": "0.010"},
                }
            ]
        },
    }


def _fake_sender_factory(captured: dict):
    def fake_sender(url, headers, body):
        captured.setdefault("calls", []).append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        return {
            "http_status": 200,
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "fake-real-demo-1", "orderLinkId": "l-1"},
            },
            "raw_text": "{}",
        }

    return fake_sender


def _fake_sender_bybit_reject_factory(captured: dict):
    def fake_sender(url, headers, body):
        captured.setdefault("calls", []).append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        return {
            "http_status": 200,
            "json": {
                "retCode": 10004,
                "retMsg": "auth failed (fake)",
                "result": {},
            },
            "raw_text": "{}",
        }

    return fake_sender


def _fake_sender_network_error_factory(captured: dict):
    def fake_sender(url, headers, body):
        captured.setdefault("calls", []).append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        return {
            "_network_error": True,
            "_error_repr": "URLError: simulated",
        }

    return fake_sender


def _run(*, mode, **overrides):
    kwargs = dict(
        mark_price="100",
        mode=mode,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
    )
    kwargs.update(overrides)
    return orc.run_one_shot_authorized_execution_orchestration(**kwargs)


def _real_demo_run(**overrides):
    """Run real-demo mode with the discovery-gate-fix contract.

    Defaults: ir_mode=discover, allow_real_ir_get=True, injected ir_sender
    returning the good SOLUSDT response. No cached / pre-parsed IR is passed.
    Real-demo-execute flag + exact marker are set. A fake BM sender captures
    the exact-body request so we can verify qty / signature.
    """

    captured: dict = {}
    creds = bm.DemoCredentials(
        api_key="key-demo", api_secret="secret-demo", recv_window="5000"
    )
    kwargs = dict(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker=_REAL_DEMO_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        allow_real_ir_get=True,
        ir_sender=_ir_sender_factory(_good_ir_response()),
        bm_credentials=creds,
        bm_fake_sender=_fake_sender_factory(captured),
    )
    kwargs.update(overrides)
    return captured, orc.run_one_shot_authorized_execution_orchestration(**kwargs)


def _capture_cli_output(argv):
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
# 1. Constants: new mode, marker, statuses
# ---------------------------------------------------------------------------


def test_new_mode_constant_value():
    assert orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER == "execute_real_demo_order"


def test_new_mode_is_in_supported_modes():
    assert (
        orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER in orc.ORCH_SUPPORTED_MODES
    )


def test_new_marker_constant_value():
    assert orc.EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER == (
        "DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1"
    )


def test_new_marker_distinct_from_cap_marker():
    assert (
        orc.EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER
        != bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER
    )


def test_new_status_not_authorized_value():
    assert orc.STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED == (
        "ORCHESTRATION_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED"
    )


def test_new_status_marker_mismatch_value():
    assert orc.STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH == (
        "ORCHESTRATION_REJECTED_REAL_EXECUTE_MARKER_MISMATCH"
    )


def test_real_execute_forbidden_status_still_exists():
    assert orc.STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1 == (
        "ORCHESTRATION_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1"
    )


def test_credentials_source_constants():
    assert orc.CREDENTIALS_SOURCE_INJECTED == "injected_demo_credentials"
    assert orc.CREDENTIALS_SOURCE_NONE == "none"


def test_new_exports_in_all():
    for name in (
        "ORCH_MODE_EXECUTE_REAL_DEMO_ORDER",
        "EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER",
        "STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED",
        "STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH",
        "STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1",
        "CREDENTIALS_SOURCE_INJECTED",
        "CREDENTIALS_SOURCE_NONE",
    ):
        assert name in orc.__all__, name


# ---------------------------------------------------------------------------
# 2. Pre-flight gate: missing flag / wrong marker rejected pre-network
# ---------------------------------------------------------------------------


def test_real_demo_without_flag_rejects_pre_network():
    r = _run(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_authorization_marker=_REAL_DEMO_MARKER,
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED
    assert r.network_attempted is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert r.real_demo_execute_requested is True
    assert r.real_demo_execute_authorized is False


def test_real_demo_without_marker_rejects_pre_network():
    r = _run(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_flag=True,
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH
    assert r.real_demo_authorization_marker_match is False
    assert r.real_demo_execute_authorized is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False


def test_real_demo_with_wrong_marker_rejects_pre_network():
    r = _run(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker="WRONG_MARKER",
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH
    assert r.real_demo_authorization_marker_match is False


def test_real_demo_with_cap_marker_only_rejects():
    """Cap-marker is NOT the real-demo marker."""
    r = _run(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker=_CAP_MARKER,
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH


# ---------------------------------------------------------------------------
# 3. Missing cap-escalation auth still rejects under real-demo mode
# ---------------------------------------------------------------------------


def test_real_demo_missing_cap_gate_flag_rejects():
    captured, r = _real_demo_run(
        explicit_demo_min_qty_cap_authorization_flag=False,
    )
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert captured.get("calls", []) == []
    assert r.order_endpoint_called is False


def test_real_demo_wrong_cap_marker_rejects():
    captured, r = _real_demo_run(
        explicit_demo_min_qty_cap_authorization_marker="WRONG_CAP_MARKER",
    )
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert captured.get("calls", []) == []


# ---------------------------------------------------------------------------
# 4. Stage 1 hard refusal of real sender
# ---------------------------------------------------------------------------


def test_real_demo_no_fake_sender_no_creds_rejects_missing_credentials():
    _captured, r = _real_demo_run(
        bm_credentials=None,
        bm_fake_sender=None,
    )
    assert r.status == orc.STATUS_REJECTED_MISSING_CREDENTIALS
    assert r.credentials_source == orc.CREDENTIALS_SOURCE_NONE
    assert r.order_endpoint_called is False
    assert r.order_sent is False


def test_real_demo_with_creds_but_no_fake_sender_refused_stage1():
    _captured, r = _real_demo_run(
        bm_fake_sender=None,
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1
    assert r.credentials_source == orc.CREDENTIALS_SOURCE_INJECTED
    assert r.order_endpoint_called is False
    assert r.order_sent is False


# ---------------------------------------------------------------------------
# 5. Offline validation via fake sender: chain wires authorized qty 0.1
# ---------------------------------------------------------------------------


def test_real_demo_fake_sender_executes_with_qty_0_1():
    captured, r = _real_demo_run()
    assert r.status == orc.STATUS_OK_FAKE_SENDER_EXECUTED
    assert r.real_demo_execute_requested is True
    assert r.real_demo_execute_authorized is True
    assert r.real_demo_authorization_marker_match is True
    assert r.credentials_source == orc.CREDENTIALS_SOURCE_INJECTED
    assert r.actual_request_body_qty == "0.1"
    assert r.resolved_execution_qty == "0.1"
    assert r.resolved_execution_qty_source == (
        bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert r.actual_request_body_qty_source == (
        bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert r.bybit_order_id == "fake-real-demo-1"
    assert r.bybit_ret_code == 0
    assert r.bybit_ret_msg == "OK"
    assert r.final_status == orc.STATUS_OK_FAKE_SENDER_EXECUTED


def test_real_demo_fake_sender_called_at_most_once():
    captured, r = _real_demo_run()
    assert r.sender_call_count == 1
    assert len(captured.get("calls", [])) == 1


def test_real_demo_actual_body_qty_is_not_0_01():
    captured, r = _real_demo_run()
    body = captured["calls"][0]["body"]
    body_str = body.decode("utf-8") if isinstance(body, bytes) else body
    obj = json.loads(body_str)
    assert obj["qty"] == "0.1"
    assert obj["qty"] != "0.01"
    assert r.actual_request_body_qty != "0.01"


def test_real_demo_body_locks_symbol_side_type_tif_category():
    captured, _ = _real_demo_run()
    body = captured["calls"][0]["body"]
    body_str = body.decode("utf-8") if isinstance(body, bytes) else body
    obj = json.loads(body_str)
    assert obj["symbol"] == "SOLUSDT"
    assert obj["side"] == "Buy"
    assert obj["orderType"] == "Market"
    assert obj["timeInForce"] == "IOC"
    assert obj["category"] == "linear"
    assert obj.get("reduceOnly") is False
    assert obj.get("closeOnTrigger") is False


# ---------------------------------------------------------------------------
# 6. Exact-body signing preserved (X-BAPI-SIGN-TYPE=2, HMAC-SHA256)
# ---------------------------------------------------------------------------


def test_real_demo_sign_type_header_is_2():
    captured, _ = _real_demo_run()
    headers = captured["calls"][0]["headers"]
    assert headers.get("X-BAPI-SIGN-TYPE") == "2"


def test_real_demo_signature_matches_hmac_sha256_of_exact_body():
    captured, _ = _real_demo_run()
    call = captured["calls"][0]
    headers = call["headers"]
    body = call["body"]
    body_str = body.decode("utf-8") if isinstance(body, bytes) else body
    timestamp = headers["X-BAPI-TIMESTAMP"]
    api_key = headers["X-BAPI-API-KEY"]
    recv_window = headers["X-BAPI-RECV-WINDOW"]
    prehash = (timestamp + api_key + recv_window + body_str).encode("utf-8")
    expected = hmac.new(
        b"secret-demo", prehash, hashlib.sha256
    ).hexdigest()
    assert headers["X-BAPI-SIGN"] == expected


def test_real_demo_transmitted_body_equals_signed_body():
    """The exact UTF-8 bytes signed must equal the bytes transmitted."""
    captured, _ = _real_demo_run()
    call = captured["calls"][0]
    body = call["body"]
    body_str = body.decode("utf-8") if isinstance(body, bytes) else body
    headers = call["headers"]
    timestamp = headers["X-BAPI-TIMESTAMP"]
    api_key = headers["X-BAPI-API-KEY"]
    recv_window = headers["X-BAPI-RECV-WINDOW"]
    prehash = (timestamp + api_key + recv_window + body_str).encode("utf-8")
    sig = hmac.new(b"secret-demo", prehash, hashlib.sha256).hexdigest()
    assert headers["X-BAPI-SIGN"] == sig
    assert isinstance(body, (bytes, bytearray))


# ---------------------------------------------------------------------------
# 7. Notional / cap enforcement
# ---------------------------------------------------------------------------


def test_real_demo_resolved_notional_under_20_usdt():
    """At mark=100, qty=0.1 -> notional=10 (<= 20)."""
    captured, r = _real_demo_run(mark_price="100")
    # resolved_notional is taken from wiring resolution; ensure it's <= 20.
    assert Decimal(r.resolved_notional) <= Decimal("20")


def test_real_demo_over_20_usdt_notional_rejects_pre_network():
    """At mark=300, qty=0.1 -> notional=30, exceeding the 20 USDT cap.

    The cap-escalation gate must refuse, so order_endpoint_called=False.
    Discovery still runs (read-only) but BM is never invoked.
    """
    captured, r = _real_demo_run(mark_price="300")
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert captured.get("calls", []) == []
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    # IR discover GET ran (read-only) but no order endpoint was called.
    assert r.order_network_attempted is False


def test_max_demo_min_qty_notional_cap_constant_unchanged():
    assert orc.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT == Decimal("20")


def test_max_order_count_constant_unchanged():
    assert orc.ALLOWED_MAX_ORDER_COUNT == 1


# ---------------------------------------------------------------------------
# 8. Fake-sender failures fail closed
# ---------------------------------------------------------------------------


def test_real_demo_fake_sender_bybit_reject_fails_closed():
    captured: dict = {}
    _captured, r = _real_demo_run(
        bm_fake_sender=_fake_sender_bybit_reject_factory(captured),
    )
    assert r.status == orc.STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED
    assert r.order_sent is False
    assert r.bybit_ret_code == 10004
    assert r.bybit_ret_msg == "auth failed (fake)"


def test_real_demo_fake_sender_network_error_fails_closed():
    captured: dict = {}
    _captured, r = _real_demo_run(
        bm_fake_sender=_fake_sender_network_error_factory(captured),
    )
    assert r.status == orc.STATUS_REJECTED_BM_NETWORK_ERROR
    assert r.order_sent is False


# ---------------------------------------------------------------------------
# 9. Wrong symbol / status / qty in IR rejects pre-network
# ---------------------------------------------------------------------------


def test_real_demo_wrong_ir_symbol_rejects():
    bad_ir = _good_ir_response()
    bad_ir["result"]["list"][0]["symbol"] = "BTCUSDT"
    captured, r = _real_demo_run(
        ir_sender=_ir_sender_factory(bad_ir),
    )
    assert r.status in (
        orc.STATUS_REJECTED_RULES_INVALID,
        orc.STATUS_REJECTED_RULES_NOT_LOADED,
    )
    assert captured.get("calls", []) == []


def test_real_demo_wrong_ir_min_order_qty_rejects():
    bad_ir = _good_ir_response()
    bad_ir["result"]["list"][0]["lotSizeFilter"]["minOrderQty"] = "1.0"
    captured, r = _real_demo_run(
        ir_sender=_ir_sender_factory(bad_ir),
    )
    assert r.status in (
        orc.STATUS_REJECTED_RULES_INVALID,
        orc.STATUS_REJECTED_RULES_NOT_LOADED,
        orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED,
    )
    assert captured.get("calls", []) == []


# ---------------------------------------------------------------------------
# 10. Default invocation path cannot reach the order endpoint
# ---------------------------------------------------------------------------


def test_default_readiness_invocation_never_reaches_order_endpoint():
    """Default mode is readiness; no order endpoint call ever."""
    r = _run(mode=orc.ORCH_MODE_READINESS)
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert r.real_demo_execute_requested is False
    assert r.real_demo_execute_authorized is False


def test_readiness_default_marker_audit_fields_safe():
    r = _run(mode=orc.ORCH_MODE_READINESS)
    assert r.real_demo_execute_requested is False
    assert r.real_demo_execute_authorized is False
    assert r.real_demo_authorization_marker_match is False


# ---------------------------------------------------------------------------
# 11. CLI: refuses real-sender, refuses missing flag/marker, refuses
# default real-mode invocation
# ---------------------------------------------------------------------------


def test_cli_default_does_not_call_order_endpoint():
    rc, output = _capture_cli_output(
        [
            "--explicit-demo-min-qty-cap-authorization-flag",
            "--authorization-marker",
            _CAP_MARKER,
        ]
    )
    assert "order_endpoint_called=False" in output
    assert "order_sent=False" in output


def test_cli_real_demo_mode_without_flag_rejected():
    rc, output = _capture_cli_output(
        [
            "--mode",
            "execute_real_demo_order",
        ]
    )
    assert rc == 1
    assert "REJECTED" in output
    assert "explicit-real-demo-order-flag" in output


def test_cli_real_demo_mode_without_marker_rejected():
    rc, output = _capture_cli_output(
        [
            "--mode",
            "execute_real_demo_order",
            "--explicit-real-demo-order-flag",
        ]
    )
    assert rc == 1
    assert "real-demo-authorization-marker" in output


def test_cli_real_demo_mode_without_fake_sender_opt_in_refuses_real_send():
    """CLI refuses to dispatch any real sender. Stage 1 lock.

    The discovery-gate-fix requires --ir-mode discover + the explicit
    public-read opt-in before we can even reach the fake-sender opt-in
    check, so this test pre-satisfies the IR gates.
    """
    rc, output = _capture_cli_output(
        [
            "--mode",
            "execute_real_demo_order",
            "--explicit-real-demo-order-flag",
            "--real-demo-authorization-marker",
            _REAL_DEMO_MARKER,
            "--ir-mode",
            "discover",
            "--i-understand-this-performs-one-public-read-only-instrument-rules-get",
        ]
    )
    assert rc == 2
    assert "Stage 1 forbids" in output or "fake sender" in output.lower()
    assert "ORCHESTRATION_OK_FAKE_SENDER_EXECUTED" not in output


def test_cli_real_demo_mode_without_fake_sender_path_rejected():
    rc, output = _capture_cli_output(
        [
            "--mode",
            "execute_real_demo_order",
            "--explicit-real-demo-order-flag",
            "--real-demo-authorization-marker",
            _REAL_DEMO_MARKER,
            "--ir-mode",
            "discover",
            "--i-understand-this-performs-one-public-read-only-instrument-rules-get",
            "--stage1-allow-fake-sender-execute-mode",
        ]
    )
    assert rc == 2
    assert "fake-sender-import-path" in output


def test_cli_real_demo_full_offline_validation_ok(monkeypatch):
    """The full Stage 1 CLI opt-in path runs offline validation.

    Per TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX,
    real-demo mode REQUIRES a fresh public read-only IR discovery and forbids
    cached / pre-parsed IR. We monkeypatch the stdlib IR sender so no external
    network call is made by the test.
    """

    def fake_stdlib(url: str) -> dict:
        return {
            "http_status": 200,
            "json": _good_ir_response(),
            "raw_text": json.dumps(_good_ir_response()),
        }

    monkeypatch.setattr(bm_ir, "_real_public_get_via_urllib", fake_stdlib)

    fake_module = (
        "tests.demo_trading.fixtures_orchestrator_fake_senders:ok_sender"
    )

    rc, output = _capture_cli_output(
        [
            "--mode",
            "execute_real_demo_order",
            "--explicit-real-demo-order-flag",
            "--real-demo-authorization-marker",
            _REAL_DEMO_MARKER,
            "--explicit-demo-min-qty-cap-authorization-flag",
            "--authorization-marker",
            _CAP_MARKER,
            "--ir-mode",
            "discover",
            "--i-understand-this-performs-one-public-read-only-instrument-rules-get",
            "--stage1-allow-fake-sender-execute-mode",
            "--fake-sender-import-path",
            fake_module,
            "--fake-api-key",
            "k",
            "--fake-api-secret",
            "s",
        ]
    )

    assert rc == 0, output
    assert "ORCHESTRATION_OK_FAKE_SENDER_EXECUTED" in output
    assert "actual_request_body_qty='0.1'" in output
    assert "order_sent=True" in output
    # The Stage 1 sender is a TEST-injected fake. The "real" endpoint was
    # never reached.
    assert "real_demo_execute_authorized=True" in output
    assert "read_only_network_attempted=True" in output
    assert "order_network_attempted=True" in output


# ---------------------------------------------------------------------------
# 12. No live endpoint / live credential reads
# ---------------------------------------------------------------------------


def test_module_source_does_not_reference_live_url():
    import inspect

    src = inspect.getsource(orc)
    assert "api.bybit.com" not in src.replace("api-demo.bybit.com", "")


def test_module_source_does_not_reference_bybit_live_env():
    import inspect

    src = inspect.getsource(orc)
    # No reference to live secret env vars
    assert "BYBIT_LIVE_API_KEY" not in src
    assert "BYBIT_LIVE_API_SECRET" not in src


def test_module_source_does_not_import_main_or_executor():
    """Docstrings/comments may discuss these names; tokens must not."""

    import inspect
    import io as _io
    import tokenize

    src = inspect.getsource(orc)
    forbidden = ("BybitExecutor", "src.risk")
    tokens = tokenize.generate_tokens(_io.StringIO(src).readline)
    for tok in tokens:
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            continue
        for needle in forbidden:
            assert needle not in tok.string, (needle, tok.string)
