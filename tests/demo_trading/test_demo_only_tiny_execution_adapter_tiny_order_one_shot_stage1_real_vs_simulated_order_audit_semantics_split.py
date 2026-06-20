"""TASK-014BM_STAGE1_REAL_VS_SIMULATED_ORDER_AUDIT_SEMANTICS_SPLIT.

Focused Stage 1 tests for the new explicit simulated-vs-real order
activity audit split surfaced on :class:`OrchestrationReport`.

The orchestrator now exposes seven new audit fields::

    simulated_order_network_attempted
    simulated_order_endpoint_called
    simulated_order_sent
    real_order_network_attempted
    real_order_endpoint_called
    real_order_sent
    order_transport_kind   (NONE | FAKE_SENDER | REAL_DEMO_SENDER)

Stage 1 invariants checked by this module:

    * No code path ever emits ``order_transport_kind="REAL_DEMO_SENDER"``.
    * All real_order_* booleans are always False.
    * Every rejection / readiness path emits all six order booleans
      False and ``order_transport_kind="NONE"``.
    * A normal fake-sender return (including a nonzero Bybit ``retCode``)
      emits all three simulated_* True; only a sender exception leaves
      ``simulated_order_sent`` False.
    * Legacy ``order_network_attempted`` / ``order_endpoint_called``
      remain OR aggregates over the split fields. Legacy ``order_sent``
      preserves its prior business-outcome meaning (retCode==0 AND
      non-empty orderId) and is NOT an OR aggregate of the simulated/
      real ``*_sent`` fields.
    * Forbidden (``REAL_DEMO_SENDER``) and unknown transport-kinds are
      explicitly rejected by the orchestrator's fail-closed validator;
      they are never silently normalized to ``NONE`` or ``FAKE_SENDER``.
    * A fake sender that genuinely raises is reshaped by the orchestrator
      into the same safe network-error sentinel BM understands, so no
      uncaught exception leaks out of the public orchestration surface
      and the simulated facet records endpoint_called=True / sent=False.
"""

from __future__ import annotations

import io
import json
import sys

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


def _ir_sender_factory(response: dict):
    def ir_sender(url: str) -> dict:
        return {
            "http_status": 200,
            "json": response,
            "raw_text": json.dumps(response),
        }

    return ir_sender


def _fake_sender_ok_factory(captured: dict):
    def fake_sender(url, headers, body):
        captured.setdefault("calls", []).append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        return {
            "http_status": 200,
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "fake-split-1", "orderLinkId": "l-1"},
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


def _readiness(**overrides):
    kwargs = dict(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
    )
    kwargs.update(overrides)
    return orc.run_one_shot_authorized_execution_orchestration(**kwargs)


def _real_demo(*, fake_sender=None, captured=None, **overrides):
    if captured is None:
        captured = {}
    if fake_sender is None:
        fake_sender = _fake_sender_ok_factory(captured)
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
        bm_fake_sender=fake_sender,
    )
    kwargs.update(overrides)
    return captured, orc.run_one_shot_authorized_execution_orchestration(
        **kwargs
    )


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


def _assert_no_dispatch(report):
    assert report.simulated_order_network_attempted is False
    assert report.simulated_order_endpoint_called is False
    assert report.simulated_order_sent is False
    assert report.real_order_network_attempted is False
    assert report.real_order_endpoint_called is False
    assert report.real_order_sent is False
    assert report.order_transport_kind == orc.ORDER_TRANSPORT_KIND_NONE


def _assert_legacy_transport_aggregates(report):
    """Legacy transport-attempt fields are OR aggregates of the split.

    ``order_sent`` is *not* checked here -- it is a business-outcome
    field (see ``_assert_legacy_order_sent_is_business_outcome``).
    """

    assert report.order_network_attempted is bool(
        report.simulated_order_network_attempted
        or report.real_order_network_attempted
    )
    assert report.order_endpoint_called is bool(
        report.simulated_order_endpoint_called
        or report.real_order_endpoint_called
    )
    assert report.network_attempted is bool(
        report.read_only_network_attempted or report.order_network_attempted
    )


def _assert_legacy_order_sent_is_business_outcome(report):
    """Legacy ``order_sent`` retains the prior accepted-order semantics:
    True iff Bybit returned ``retCode==0`` AND a non-empty ``orderId``."""

    expected = bool(
        report.bybit_ret_code == 0 and bool(report.bybit_order_id)
    )
    assert report.order_sent is expected


def _assert_legacy_aggregates(report):
    """Backwards-compatible wrapper for the no-dispatch / fake-sender
    scenarios used by older sections of this module."""

    _assert_legacy_transport_aggregates(report)
    _assert_legacy_order_sent_is_business_outcome(report)


# ---------------------------------------------------------------------------
# 1. Constants / exports
# ---------------------------------------------------------------------------


def test_order_transport_kind_constants_and_allowlist():
    assert orc.ORDER_TRANSPORT_KIND_NONE == "NONE"
    assert orc.ORDER_TRANSPORT_KIND_FAKE_SENDER == "FAKE_SENDER"
    assert orc.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER == "REAL_DEMO_SENDER"
    assert orc.ORDER_TRANSPORT_KINDS == (
        "NONE",
        "FAKE_SENDER",
        "REAL_DEMO_SENDER",
    )


def test_stage1_forbidden_kinds_contains_real_demo_sender():
    assert (
        orc.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER
        in orc.STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS
    )


def test_new_constants_exported_in_all():
    for name in (
        "ORDER_TRANSPORT_KIND_NONE",
        "ORDER_TRANSPORT_KIND_FAKE_SENDER",
        "ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER",
        "ORDER_TRANSPORT_KINDS",
        "STAGE1_FORBIDDEN_ORDER_TRANSPORT_KINDS",
    ):
        assert name in orc.__all__, name


# ---------------------------------------------------------------------------
# 2. No-dispatch paths -- all six order booleans False, transport NONE
# ---------------------------------------------------------------------------


def test_readiness_offline_split_no_dispatch():
    r = _readiness()
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_readiness_with_discover_ir_only():
    r = _readiness(
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_pre_parsed_response=None,
        ir_sender=_ir_sender_factory(_good_ir_response()),
        allow_real_ir_get=True,
    )
    assert r.read_only_network_attempted is True
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_unsupported_mode_no_dispatch_split():
    r = _readiness(mode="not_a_supported_mode")
    assert r.status == orc.STATUS_REJECTED_UNSUPPORTED_MODE
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_real_demo_missing_flag_no_dispatch_split():
    r = _readiness(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_authorization_marker=_REAL_DEMO_MARKER,
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_NOT_AUTHORIZED
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_real_demo_marker_mismatch_no_dispatch_split():
    r = _readiness(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker="WRONG",
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_MARKER_MISMATCH
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_real_demo_discovery_required_no_dispatch_split():
    r = _readiness(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker=_REAL_DEMO_MARKER,
    )
    assert r.status == orc.STATUS_REJECTED_REAL_DEMO_DISCOVERY_REQUIRED
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_real_demo_read_only_opt_in_required_no_dispatch_split():
    r = _readiness(
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker=_REAL_DEMO_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_pre_parsed_response=None,
        allow_real_ir_get=False,
        ir_sender=_ir_sender_factory(_good_ir_response()),
    )
    assert (
        r.status == orc.STATUS_REJECTED_REAL_DEMO_READ_ONLY_OPT_IN_REQUIRED
    )
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_real_demo_forbidden_stage1_no_dispatch_split():
    creds = bm.DemoCredentials(
        api_key="k", api_secret="s", recv_window="5000"
    )
    r = orc.run_one_shot_authorized_execution_orchestration(
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
        bm_fake_sender=None,
    )
    assert r.status == orc.STATUS_REJECTED_REAL_EXECUTE_FORBIDDEN_STAGE1
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


def test_real_demo_missing_credentials_no_dispatch_split():
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_CAP_MARKER,
        explicit_real_demo_execute_flag=True,
        explicit_real_demo_execute_authorization_marker=_REAL_DEMO_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        allow_real_ir_get=True,
        ir_sender=_ir_sender_factory(_good_ir_response()),
        bm_credentials=None,
        bm_fake_sender=_fake_sender_ok_factory({}),
    )
    assert r.status == orc.STATUS_REJECTED_MISSING_CREDENTIALS
    _assert_no_dispatch(r)
    _assert_legacy_aggregates(r)


# ---------------------------------------------------------------------------
# 3. Fake-sender dispatch -- simulated facet active, real facet always off
# ---------------------------------------------------------------------------


def test_fake_sender_executed_simulated_all_true():
    captured, r = _real_demo()
    assert r.status == orc.STATUS_OK_FAKE_SENDER_EXECUTED
    assert r.simulated_order_network_attempted is True
    assert r.simulated_order_endpoint_called is True
    assert r.simulated_order_sent is True
    assert r.real_order_network_attempted is False
    assert r.real_order_endpoint_called is False
    assert r.real_order_sent is False
    assert r.order_transport_kind == orc.ORDER_TRANSPORT_KIND_FAKE_SENDER
    # retCode==0 AND non-empty orderId -> business-outcome accepted -> legacy True.
    assert r.bybit_ret_code == 0
    assert r.bybit_order_id == "fake-split-1"
    assert r.order_sent is True
    assert r.order_endpoint_called is True
    _assert_legacy_aggregates(r)
    assert len(captured.get("calls", [])) == 1


def _fake_sender_empty_order_id_factory(captured: dict):
    def fake_sender(url, headers, body):
        captured.setdefault("calls", []).append(
            {"url": url, "headers": dict(headers), "body": body}
        )
        return {
            "http_status": 200,
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "", "orderLinkId": "l-empty"},
            },
            "raw_text": "{}",
        }

    return fake_sender


def test_fake_sender_retcode_zero_empty_order_id_simulated_sent_legacy_false():
    """retCode==0 with empty orderId: simulated transport completed but
    business outcome did not accept the order, so legacy order_sent
    stays False."""

    captured = {}
    _captured, r = _real_demo(
        captured=captured,
        fake_sender=_fake_sender_empty_order_id_factory(captured),
    )
    # BM still classifies retCode==0 + empty orderId as
    # STATUS_BYBIT_REJECTED_NO_ORDER_SENT (see bm._send_one_demo_order
    # and the dispatch branch on outcome.order_sent / order_id).
    assert r.status == orc.STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED
    assert r.bybit_ret_code == 0
    assert r.bybit_order_id == ""
    assert r.simulated_order_endpoint_called is True
    assert r.simulated_order_sent is True
    assert r.real_order_sent is False
    assert r.order_transport_kind == orc.ORDER_TRANSPORT_KIND_FAKE_SENDER
    assert r.order_sent is False
    _assert_legacy_aggregates(r)


def _fake_sender_raises_runtime_error(url, headers, body):
    raise RuntimeError("simulated fake sender exception")


def test_fake_sender_raises_exception_safely_reshaped_to_network_error():
    """TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 2):
    a fake sender that genuinely raises must not leak the exception out
    of the public orchestration surface. The orchestrator's counting
    wrapper reshapes it into the same network-error sentinel BM already
    understands, so the final status / audit fields stay safe and the
    sender call count stays exactly 1."""

    captured = {}

    def counting_raise_sender(url, headers, body):
        captured.setdefault("calls", []).append({"url": url})
        _fake_sender_raises_runtime_error(url, headers, body)

    _captured, r = _real_demo(
        captured=captured,
        fake_sender=counting_raise_sender,
    )
    assert r.status == orc.STATUS_REJECTED_BM_NETWORK_ERROR
    assert r.simulated_order_network_attempted is True
    assert r.simulated_order_endpoint_called is True
    assert r.simulated_order_sent is False
    assert r.real_order_network_attempted is False
    assert r.real_order_endpoint_called is False
    assert r.real_order_sent is False
    assert r.order_transport_kind == orc.ORDER_TRANSPORT_KIND_FAKE_SENDER
    assert r.order_sent is False
    assert r.sender_call_count == 1
    assert len(captured.get("calls", [])) == 1


def test_fake_sender_bybit_retcode_nonzero_simulated_all_true():
    captured = {}
    _captured, r = _real_demo(
        captured=captured,
        fake_sender=_fake_sender_bybit_reject_factory(captured),
    )
    assert r.status == orc.STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED
    assert r.bybit_ret_code == 10004
    assert r.bybit_order_id == ""
    # A nonzero retCode is still a *normal return* from the simulated
    # transport: the body was sent, Bybit replied, just with a business
    # rejection. The simulated_* facet records the transport, not the
    # business outcome.
    assert r.simulated_order_network_attempted is True
    assert r.simulated_order_endpoint_called is True
    assert r.simulated_order_sent is True
    assert r.real_order_network_attempted is False
    assert r.real_order_endpoint_called is False
    assert r.real_order_sent is False
    assert r.order_transport_kind == orc.ORDER_TRANSPORT_KIND_FAKE_SENDER
    # TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 1):
    # legacy ``order_sent`` preserves business-outcome semantics. A
    # nonzero retCode is not an accepted order, so legacy stays False
    # even while simulated_order_sent is True.
    assert r.order_sent is False
    assert r.order_endpoint_called is True
    _assert_legacy_aggregates(r)


def test_fake_sender_network_error_simulated_sent_false():
    captured = {}
    _captured, r = _real_demo(
        captured=captured,
        fake_sender=_fake_sender_network_error_factory(captured),
    )
    assert r.status == orc.STATUS_REJECTED_BM_NETWORK_ERROR
    # A simulated network error means the body was *not* sent -- the
    # transport raised before the response was received. Endpoint was
    # contacted (we tried to call it), so endpoint_called remains True.
    assert r.simulated_order_network_attempted is True
    assert r.simulated_order_endpoint_called is True
    assert r.simulated_order_sent is False
    assert r.real_order_network_attempted is False
    assert r.real_order_endpoint_called is False
    assert r.real_order_sent is False
    assert r.order_transport_kind == orc.ORDER_TRANSPORT_KIND_FAKE_SENDER
    _assert_legacy_aggregates(r)


# ---------------------------------------------------------------------------
# 3b. Forbidden / unknown transport-kind -- fail-closed validator
# ---------------------------------------------------------------------------


def test_validator_rejects_real_demo_sender_transport_kind():
    """TASK-014BM_STAGE1_AUDIT_SEMANTICS_SPLIT_CORRECTION (Correction 3):
    Stage 1 must never silently normalize REAL_DEMO_SENDER to NONE /
    FAKE_SENDER. The validator raises an explicit safety exception."""

    import pytest

    with pytest.raises(orc.OneShotAuthorizedExecutionOrchestratorError):
        orc._validate_stage1_order_transport_kind(
            orc.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER
        )


def test_validator_rejects_unknown_transport_kind():
    import pytest

    with pytest.raises(orc.OneShotAuthorizedExecutionOrchestratorError):
        orc._validate_stage1_order_transport_kind("SOMETHING_ELSE")


def test_validator_accepts_none_and_fake_sender():
    # Must not raise.
    orc._validate_stage1_order_transport_kind(orc.ORDER_TRANSPORT_KIND_NONE)
    orc._validate_stage1_order_transport_kind(
        orc.ORDER_TRANSPORT_KIND_FAKE_SENDER
    )


def test_rejection_report_builder_fail_closed_on_real_demo_sender():
    """If a future caller ever tries to construct a rejection report
    with the forbidden transport-kind, the builder must raise rather
    than silently emit a misleading NONE."""

    import pytest

    with pytest.raises(orc.OneShotAuthorizedExecutionOrchestratorError):
        orc._build_rejection_report(
            mode=orc.ORCH_MODE_READINESS,
            status=orc.STATUS_OK_READINESS_NO_NETWORK,
            reason="forced",
            order_transport_kind=orc.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER,
        )


def test_rejection_report_builder_fail_closed_on_unknown_transport_kind():
    import pytest

    with pytest.raises(orc.OneShotAuthorizedExecutionOrchestratorError):
        orc._build_rejection_report(
            mode=orc.ORCH_MODE_READINESS,
            status=orc.STATUS_OK_READINESS_NO_NETWORK,
            reason="forced",
            order_transport_kind="MYSTERY",
        )


# ---------------------------------------------------------------------------
# 4. Cross-cutting invariants
# ---------------------------------------------------------------------------


def test_stage1_never_emits_real_demo_sender_transport():
    """Across every Stage 1 scenario the orchestrator never reports the
    REAL_DEMO_SENDER transport kind. real_order_* fields stay False."""

    scenarios = []
    scenarios.append(_readiness())
    scenarios.append(
        _readiness(
            ir_mode=bm_ir.MODE_DISCOVER,
            ir_pre_parsed_response=None,
            ir_sender=_ir_sender_factory(_good_ir_response()),
            allow_real_ir_get=True,
        )
    )
    scenarios.append(_readiness(mode="not_a_supported_mode"))
    scenarios.append(_real_demo()[1])
    captured = {}
    scenarios.append(
        _real_demo(
            captured=captured,
            fake_sender=_fake_sender_bybit_reject_factory(captured),
        )[1]
    )
    captured2 = {}
    scenarios.append(
        _real_demo(
            captured=captured2,
            fake_sender=_fake_sender_network_error_factory(captured2),
        )[1]
    )
    for r in scenarios:
        assert (
            r.order_transport_kind
            != orc.ORDER_TRANSPORT_KIND_REAL_DEMO_SENDER
        )
        assert r.real_order_network_attempted is False
        assert r.real_order_endpoint_called is False
        assert r.real_order_sent is False


def test_legacy_aggregate_formula_across_scenarios():
    """Legacy transport-attempt fields are OR aggregates of the split.
    Legacy ``order_sent`` retains its prior business-outcome semantics
    (retCode==0 AND non-empty orderId) and is NOT an OR aggregate."""

    scenarios = [
        _readiness(),
        _readiness(
            ir_mode=bm_ir.MODE_DISCOVER,
            ir_pre_parsed_response=None,
            ir_sender=_ir_sender_factory(_good_ir_response()),
            allow_real_ir_get=True,
        ),
        _real_demo()[1],
    ]
    captured = {}
    scenarios.append(
        _real_demo(
            captured=captured,
            fake_sender=_fake_sender_bybit_reject_factory(captured),
        )[1]
    )
    captured2 = {}
    scenarios.append(
        _real_demo(
            captured=captured2,
            fake_sender=_fake_sender_network_error_factory(captured2),
        )[1]
    )
    for r in scenarios:
        _assert_legacy_aggregates(r)


# ---------------------------------------------------------------------------
# 5. CLI stdout + markdown / to_dict serialization
# ---------------------------------------------------------------------------


def test_cli_stdout_prints_new_audit_fields():
    """The CLI must surface every new field on every run, even when the
    orchestrator rejects pre-network (here: default offline IR with no
    pre-parsed response). The audit fields print unconditionally."""

    _rc, output = _capture_cli_output(
        [
            "--explicit-demo-min-qty-cap-authorization-flag",
            "--authorization-marker",
            _CAP_MARKER,
        ]
    )
    assert "order_transport_kind='NONE'" in output
    assert "simulated_order_network_attempted=False" in output
    assert "simulated_order_endpoint_called=False" in output
    assert "simulated_order_sent=False" in output
    assert "real_order_network_attempted=False" in output
    assert "real_order_endpoint_called=False" in output
    assert "real_order_sent=False" in output


def test_to_dict_payload_includes_all_seven_split_fields():
    captured, r = _real_demo()
    payload = r.to_dict()
    for key in (
        "simulated_order_network_attempted",
        "simulated_order_endpoint_called",
        "simulated_order_sent",
        "real_order_network_attempted",
        "real_order_endpoint_called",
        "real_order_sent",
        "order_transport_kind",
    ):
        assert key in payload, key
    assert payload["order_transport_kind"] == "FAKE_SENDER"
    assert payload["simulated_order_network_attempted"] is True
    assert payload["simulated_order_endpoint_called"] is True
    assert payload["simulated_order_sent"] is True
    assert payload["real_order_network_attempted"] is False
    assert payload["real_order_endpoint_called"] is False
    assert payload["real_order_sent"] is False


def test_markdown_render_includes_simulated_vs_real_section():
    captured, r = _real_demo()
    md = orc._render_markdown(r)
    assert "## Order activity audit (simulated vs real)" in md
    assert "order_transport_kind=`FAKE_SENDER`" in md
    assert "simulated_order_network_attempted=True" in md
    assert "simulated_order_endpoint_called=True" in md
    assert "simulated_order_sent=True" in md
    assert "real_order_network_attempted=False" in md
    assert "real_order_endpoint_called=False" in md
    assert "real_order_sent=False" in md
