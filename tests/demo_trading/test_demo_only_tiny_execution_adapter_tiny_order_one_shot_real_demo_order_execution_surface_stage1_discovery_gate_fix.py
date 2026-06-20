"""TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1_DISCOVERY_GATE_FIX tests.

Focused discovery-gate tests for the Stage 1 real-demo execute surface.

The corrected contract for ``ORCH_MODE_EXECUTE_REAL_DEMO_ORDER`` requires
ALL of the following before any BM invocation:

    * ``ir_mode = bm_ir.MODE_DISCOVER``
    * explicit public read-only discovery opt-in
      (``allow_real_ir_get=True``)
    * CLI flag present:
      ``--i-understand-this-performs-one-public-read-only-instrument-rules-get``
    * ``explicit_real_demo_execute_flag=True``
    * exact real-demo marker
    * cap-escalation flag and exact cap-escalation marker
    * valid injected Demo credentials
    * Stage 1 fake BM sender present
    * all existing qty / wiring / notional safety checks pass

Fail-closed rules covered:

    1. real-demo + ``ir_pre_parsed_response`` rejected before any sender
       call (``STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED``).
    2. real-demo + CLI ``--ir-response-json-file`` (aka
       ``--ir-pre-parsed-response-json``) rejected before any sender call.
    3. real-demo + ``ir_mode != discover`` rejected
       (``STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED``).
    4. real-demo + discover without opt-in rejected pre-network
       (``STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED``).
    5. Readiness mode may still use offline / pre-parsed IR (regression).
    6. ``execute_with_fake_sender`` mode is backward compatible outside the
       real-demo path.
    7. No fallback from missing discovery to cached / pre-parsed rules.
    8. No real ``/v5/order/create`` endpoint call.
    9. No real order sent.

Happy-path coverage:

    * real-demo + discover + opt-in + injected ir_sender + fake BM sender
      reaches ``STATUS_OK_FAKE_SENDER_EXECUTED`` with
      ``actual_request_body_qty='0.1'`` sourced from
      ``CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY``.
    * Injected IR sender is called exactly once.
    * Fake BM sender is called exactly once.
    * ``read_only_network_attempted=True``, ``order_network_attempted=True``,
      ``network_attempted=True``, ``fake_sender_used=True``.
"""

from __future__ import annotations

import io
import json
import os
import sys
import tempfile
from types import SimpleNamespace

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


def _ir_sender_counting(counter: dict):
    def ir_sender(url: str) -> dict:
        counter["n"] = counter.get("n", 0) + 1
        counter.setdefault("urls", []).append(url)
        return {
            "http_status": 200,
            "json": _good_ir_response(),
            "raw_text": json.dumps(_good_ir_response()),
        }

    return ir_sender


def _bm_fake_sender_counting(counter: dict):
    def fake_sender(url, headers, body):
        counter["n"] = counter.get("n", 0) + 1
        counter.setdefault("calls", []).append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        return {
            "http_status": 200,
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {
                    "orderId": "fake-discovery-gate-1",
                    "orderLinkId": "l-d-1",
                },
            },
            "raw_text": "{}",
        }

    return fake_sender


def _bm_fake_sender_should_not_be_called():
    def fake_sender(url, headers, body):
        raise AssertionError(
            "BM fake sender must NEVER be called when the discovery gate "
            "rejects pre-network"
        )

    return fake_sender


def _ir_sender_should_not_be_called():
    def ir_sender(url: str) -> dict:
        raise AssertionError(
            "Injected IR sender must NEVER be called when the discovery "
            "gate rejects pre-network"
        )

    return ir_sender


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


def _real_demo_kwargs(**overrides):
    base = dict(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker=_REAL_DEMO_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        allow_real_ir_get=True,
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
    )
    base.update(overrides)
    return base


# ---------------------------------------------------------------------------
# 1. Constants and exports
# ---------------------------------------------------------------------------


def test_status_discovery_required_value():
    assert orc.STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED == (
        "ORCHESTRATION_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED"
    )


def test_status_read_only_opt_in_required_value():
    assert orc.STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED == (
        "ORCHESTRATION_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED"
    )


def test_new_discovery_gate_statuses_in_all():
    for name in (
        "STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED",
        "STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED",
    ):
        assert name in orc.__all__, name


# ---------------------------------------------------------------------------
# 2. Orchestrator: cached / pre-parsed IR forbidden in real-demo mode
# ---------------------------------------------------------------------------


def test_real_demo_with_pre_parsed_rejected_pre_network():
    """Cached IR is forbidden even when every other gate is satisfied."""

    bm_counter: dict = {}
    r = orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_pre_parsed_response=_good_ir_response(),
            ir_sender=_ir_sender_should_not_be_called(),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    assert r.status == orc.STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED
    assert r.real_demo_execute_requested is True
    assert r.network_attempted is False
    assert r.read_only_network_attempted is False
    assert r.order_network_attempted is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert bm_counter.get("n", 0) == 0


def test_real_demo_with_offline_ir_mode_rejected_pre_network():
    """``ir_mode=offline`` is forbidden for real-demo."""

    bm_counter: dict = {}
    r = orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_mode=bm_ir.MODE_OFFLINE,
            allow_real_ir_get=True,
            ir_sender=_ir_sender_should_not_be_called(),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    assert r.status == orc.STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED
    assert r.network_attempted is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert bm_counter.get("n", 0) == 0


def test_real_demo_pre_parsed_rejection_does_not_call_ir_or_bm_sender():
    """Pre-flight rejection happens BEFORE any sender callable runs."""

    ir_counter: dict = {}
    bm_counter: dict = {}
    r = orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_pre_parsed_response=_good_ir_response(),
            ir_sender=_ir_sender_counting(ir_counter),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    assert r.status == orc.STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED
    assert ir_counter.get("n", 0) == 0
    assert bm_counter.get("n", 0) == 0


# ---------------------------------------------------------------------------
# 3. Orchestrator: discover without public-read opt-in rejected pre-network
# ---------------------------------------------------------------------------


def test_real_demo_discover_without_opt_in_rejected_pre_network():
    ir_counter: dict = {}
    bm_counter: dict = {}
    r = orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            allow_real_ir_get=False,
            ir_sender=_ir_sender_counting(ir_counter),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    assert r.status == (
        orc.STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED
    )
    assert r.real_demo_execute_requested is True
    assert r.network_attempted is False
    assert r.read_only_network_attempted is False
    assert r.order_network_attempted is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert ir_counter.get("n", 0) == 0
    assert bm_counter.get("n", 0) == 0


def test_real_demo_opt_in_rejection_distinct_reason():
    r = orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            allow_real_ir_get=False,
            ir_sender=_ir_sender_counting({}),
            bm_fake_sender=_bm_fake_sender_should_not_be_called(),
        )
    )
    assert "opt-in" in r.reason or "public read-only" in r.reason


def test_real_demo_pre_parsed_rejection_distinct_reason():
    r = orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_pre_parsed_response=_good_ir_response(),
            bm_fake_sender=_bm_fake_sender_should_not_be_called(),
        )
    )
    assert "discover" in r.reason or "cached" in r.reason or "pre-parsed" in r.reason


# ---------------------------------------------------------------------------
# 4. Orchestrator: happy path -- discover + opt-in + injected IR + fake BM
# ---------------------------------------------------------------------------


def test_real_demo_full_discovery_chain_success():
    ir_counter: dict = {}
    bm_counter: dict = {}
    r = orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_sender=_ir_sender_counting(ir_counter),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    assert r.status == orc.STATUS_OK_FAKE_SENDER_EXECUTED
    assert r.real_demo_execute_requested is True
    assert r.real_demo_execute_authorized is True
    assert r.real_demo_authorization_marker_match is True
    assert r.credentials_source == orc.CREDENTIALS_SOURCE_INJECTED
    assert r.read_only_network_attempted is True
    assert r.order_network_attempted is True
    assert r.network_attempted is True
    assert r.fake_sender_used is True
    assert r.sender_call_count == 1
    assert r.actual_request_body_qty == "0.1"
    assert r.actual_request_body_qty_source == (
        bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert ir_counter.get("n", 0) == 1
    assert bm_counter.get("n", 0) == 1


def test_real_demo_ir_sender_called_exactly_once():
    ir_counter: dict = {}
    bm_counter: dict = {}
    orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_sender=_ir_sender_counting(ir_counter),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    assert ir_counter.get("n", 0) == 1


def test_real_demo_bm_fake_sender_called_exactly_once():
    ir_counter: dict = {}
    bm_counter: dict = {}
    orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_sender=_ir_sender_counting(ir_counter),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    assert bm_counter.get("n", 0) == 1


def test_real_demo_ir_sender_receives_only_allowed_url():
    ir_counter: dict = {}
    bm_counter: dict = {}
    orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_sender=_ir_sender_counting(ir_counter),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    urls = ir_counter.get("urls", [])
    assert len(urls) == 1
    url = urls[0]
    assert "/v5/market/instruments-info" in url
    assert "category=linear" in url
    assert "symbol=SOLUSDT" in url
    assert "/v5/order/create" not in url
    assert "api.bybit.com" not in url


def test_real_demo_no_real_order_endpoint_reachable():
    """`/v5/order/create` is not in any sender call URL."""

    bm_counter: dict = {}
    orc.run_one_shot_authorized_execution_orchestration(
        **_real_demo_kwargs(
            ir_sender=_ir_sender_counting({}),
            bm_fake_sender=_bm_fake_sender_counting(bm_counter),
        )
    )
    calls = bm_counter.get("calls", [])
    # The fake sender DOES receive a v5/order/create-shaped URL — but it's
    # the demo /v5/order/create on api-demo.bybit.com, dispatched to the
    # fake (no real network call). Confirm there's no live host.
    for call in calls:
        assert "https://api.bybit.com" not in call["url"]
        assert "https://api.bytick.com" not in call["url"]
        assert "wss://" not in call["url"]


# ---------------------------------------------------------------------------
# 5. Readiness mode still supports offline/pre-parsed IR
# ---------------------------------------------------------------------------


def test_readiness_offline_pre_parsed_still_supported():
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        ir_mode=bm_ir.MODE_OFFLINE,
        ir_pre_parsed_response=_good_ir_response(),
    )
    assert r.status == orc.STATUS_OK_READINESS_NO_NETWORK
    assert r.order_endpoint_called is False
    assert r.order_sent is False


def test_readiness_discover_with_opt_in_still_supported(monkeypatch):
    """Readiness with discover + opt-in remains a public surface."""

    def fake_stdlib(url: str) -> dict:
        return {
            "http_status": 200,
            "json": _good_ir_response(),
            "raw_text": json.dumps(_good_ir_response()),
        }

    monkeypatch.setattr(bm_ir, "_real_public_get_via_urllib", fake_stdlib)

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        allow_real_ir_get=True,
    )
    assert r.status == orc.STATUS_OK_READINESS_READ_ONLY_NETWORK
    assert r.order_endpoint_called is False
    assert r.order_sent is False


# ---------------------------------------------------------------------------
# 6. execute_with_fake_sender outside real-demo mode is unchanged
# ---------------------------------------------------------------------------


def test_execute_with_fake_sender_still_accepts_pre_parsed_ir():
    """Backward-compat: the discovery gate only applies to real-demo mode."""

    bm_counter: dict = {}
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        ir_mode=bm_ir.MODE_OFFLINE,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
        bm_fake_sender=_bm_fake_sender_counting(bm_counter),
    )
    assert r.status == orc.STATUS_OK_FAKE_SENDER_EXECUTED
    assert r.actual_request_body_qty == "0.1"
    assert bm_counter.get("n", 0) == 1


# ---------------------------------------------------------------------------
# 7. CLI: rejection paths
# ---------------------------------------------------------------------------


def test_cli_real_demo_with_pre_parsed_ir_path_rejected():
    """CLI must refuse --ir-pre-parsed-response-json for real-demo mode."""

    tmp_dir = tempfile.mkdtemp(prefix="orc_discovery_gate_")
    ir_path = os.path.join(tmp_dir, "ir.json")
    with open(ir_path, "w", encoding="utf-8") as f:
        json.dump(_good_ir_response(), f)

    try:
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
                "--ir-pre-parsed-response-json",
                ir_path,
            ]
        )
    finally:
        try:
            os.remove(ir_path)
            os.rmdir(tmp_dir)
        except OSError:
            pass

    assert rc == 1
    assert "REJECTED" in output
    assert "ir-pre-parsed-response-json" in output or "cached" in output


def test_cli_real_demo_with_offline_ir_mode_rejected():
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
        ]
    )
    assert rc == 1
    assert "REJECTED" in output
    assert "ir-mode discover" in output or "ir-mode" in output


def test_cli_real_demo_discover_without_opt_in_rejected():
    """Either generic CLI guard or the real-demo-specific guard refuses."""

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
        ]
    )
    assert rc == 1
    assert "REJECTED" in output
    assert (
        "--i-understand-this-performs-one-public-read-only-instrument-rules-get"
        in output
    )


# ---------------------------------------------------------------------------
# 8. CLI: full happy path with monkeypatched stdlib IR sender
# ---------------------------------------------------------------------------


def test_cli_real_demo_full_discovery_chain_ok(monkeypatch):
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
    assert "read_only_network_attempted=True" in output
    assert "order_network_attempted=True" in output
    assert "real_demo_execute_authorized=True" in output


# ---------------------------------------------------------------------------
# 9. Default safety / regression
# ---------------------------------------------------------------------------


def test_cli_default_invocation_unchanged():
    rc, output = _capture_cli_output(
        [
            "--explicit-demo-min-qty-cap-authorization-flag",
            "--authorization-marker",
            _CAP_MARKER,
        ]
    )
    assert "order_endpoint_called=False" in output
    assert "order_sent=False" in output


def test_default_orchestration_does_not_request_real_demo():
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
    )
    assert r.real_demo_execute_requested is False
    assert r.real_demo_execute_authorized is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False
