"""TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR Stage 1 tests.

Focused tests for the demo-only one-shot orchestrator:

    * Identity / chain-break markers.
    * Locks, supported modes, status constants.
    * Readiness happy path: actual_request_body_qty=='0.1', no network.
    * Fake-sender happy path: body qty=='0.1', body bytes equal the
      signed prehash body string, X-BAPI-SIGN-TYPE=2, sender called
      exactly once.
    * Rejections: missing IR rules, invalid IR, missing/unauthorized
      cap gate, unauthorized wiring, missing credentials / fake sender,
      unsupported mode.
    * Hard block: real IR discover without injected sender raises
      OneShotAuthorizedExecutionOrchestratorError.
    * write_report emits 4 files; JSON round-trips.
    * Module never references main.py / src.risk / BybitExecutor and
      never reads any LIVE_ env var.
"""

from __future__ import annotations

import ast
import hashlib
import hmac
import io
import json
import tokenize
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


def _readiness(**overrides):
    kwargs = dict(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
    )
    kwargs.update(overrides)
    return orc.run_one_shot_authorized_execution_orchestration(**kwargs)


def _fake_sender_factory(captured: dict):
    def fake_sender(url, headers, body):
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


def _execute_fake(captured, **overrides):
    kwargs = dict(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=bm.DemoCredentials(
            api_key="key", api_secret="secret", recv_window="5000"
        ),
        bm_fake_sender=_fake_sender_factory(captured),
    )
    kwargs.update(overrides)
    return orc.run_one_shot_authorized_execution_orchestration(**kwargs)


# ---------------------------------------------------------------------------
# Identity / chain markers
# ---------------------------------------------------------------------------


def test_task_id_and_identity_constants():
    assert orc.TASK_ID == "TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR"
    assert orc.IDENTITY == (
        "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-"
        "ONE-SHOT-AUTHORIZED-EXECUTION-ORCHESTRATOR"
    )
    assert (
        orc.IMPLEMENTATION_PATH_PHASE
        == "tiny_order_one_shot_authorized_execution_orchestrator"
    )
    assert orc.IS_REVIEW_CHAIN_SUFFIX is False
    assert (
        orc.NEXT_REQUIRED_TASK
        == "TASK-014BN_demo_only_tiny_execution_postfill_audit"
    )


def test_next_required_task_passes_bh_non_review_chain_suffix_check():
    bh.assert_next_task_is_not_review_chain_suffix(orc.NEXT_REQUIRED_TASK)


def test_upstream_tasks():
    assert orc.UPSTREAM_TASKS == (
        "TASK-014BH",
        "TASK-014BM",
        "TASK-014BM_FIX",
        "TASK-014BM_MIN_QTY_FIX",
        "TASK-014BM_CAP_ESCALATION_GATE",
        "TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY",
        "TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH",
    )


def test_locks_match_solusdt_demo_market_buy_ioc():
    assert orc.ALLOWED_ENVIRONMENT == "bybit_demo"
    assert orc.ALLOWED_SYMBOL == "SOLUSDT"
    assert orc.ALLOWED_SIDE == "Buy"
    assert orc.ALLOWED_ORDER_TYPE == "Market"
    assert orc.ALLOWED_TIME_IN_FORCE == "IOC"
    assert orc.ALLOWED_MAX_ORDER_COUNT == 1
    assert orc.ALLOWED_CATEGORY == "linear"
    assert orc.EXPECTED_MIN_ORDER_QTY == "0.1"
    assert orc.EXPECTED_QTY_STEP == "0.1"
    assert orc.EXPECTED_INSTRUMENT_STATUS == "Trading"
    assert orc.EXPECTED_CANDIDATE_QTY == "0.1"
    assert orc.ORIGINAL_PACKET_QTY == "0.01"
    assert orc.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT == Decimal("20")


def test_supported_modes_only_three():
    # TASK-014BM_ONE_SHOT_REAL_DEMO_ORDER_EXECUTION_SURFACE_STAGE1 added
    # the isolated execute_real_demo_order mode. Stage 1 still hard-
    # refuses any real /v5/order/create call from that mode.
    assert orc.ORCH_SUPPORTED_MODES == (
        orc.ORCH_MODE_READINESS,
        orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        orc.ORCH_MODE_EXECUTE_REAL_DEMO_ORDER,
    )


# ---------------------------------------------------------------------------
# Readiness happy path
# ---------------------------------------------------------------------------


def test_readiness_happy_path_returns_actual_body_qty_0_1_no_network():
    r = _readiness()
    assert r.status == orc.STATUS_OK_READINESS_NO_NETWORK
    assert r.cap_gate_status == bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert r.wiring_status == bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY
    assert r.wiring_execution_qty_source == (
        bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert r.wiring_execution_qty == "0.1"
    assert r.candidate_qty == "0.1"
    assert r.qty_0_01_confirmed_invalid is True
    assert r.cap_escalated_demo_only is True
    assert r.original_packet_qty == "0.01"
    assert r.actual_request_body_qty == "0.1"
    assert r.actual_request_body_qty_source == (
        bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    assert r.body_qty_authorized_override is True
    assert r.network_attempted is False
    assert r.order_endpoint_called is False
    assert r.order_sent is False
    assert r.fake_sender_used is False
    assert r.sender_call_count == 0
    assert r.real_execute_disabled_stage1 is True


# ---------------------------------------------------------------------------
# Fake-sender execute happy path
# ---------------------------------------------------------------------------


def test_fake_sender_execute_emits_body_qty_0_1_with_correct_signature():
    captured: dict = {}
    r = _execute_fake(captured)
    assert r.status == orc.STATUS_OK_FAKE_SENDER_EXECUTED
    assert r.bm_final_status == bm.STATUS_EXECUTED_DEMO_ONLY
    assert r.network_attempted is True
    assert r.order_endpoint_called is True
    assert r.order_sent is True
    assert r.bybit_order_id == "fake-1"
    assert r.bybit_ret_code == 0
    assert r.fake_sender_used is True
    assert r.sender_call_count == 1

    body_bytes = captured["body"]
    assert isinstance(body_bytes, (bytes, bytearray))
    body_str = body_bytes.decode("utf-8")
    body_obj = json.loads(body_str)
    assert body_obj["qty"] == "0.1"
    assert body_obj["symbol"] == "SOLUSDT"
    assert body_obj["side"] == "Buy"
    assert body_obj["orderType"] == "Market"
    assert body_obj["timeInForce"] == "IOC"

    headers = captured["headers"]
    assert captured["url"] == bm.ALLOWED_DEMO_ENDPOINT_URL
    assert headers["X-BAPI-SIGN-TYPE"] == "2"
    prehash = (
        headers["X-BAPI-TIMESTAMP"]
        + headers["X-BAPI-API-KEY"]
        + headers["X-BAPI-RECV-WINDOW"]
        + body_str
    )
    expected = hmac.new(
        b"secret", prehash.encode("utf-8"), hashlib.sha256
    ).hexdigest()
    assert headers["X-BAPI-SIGN"] == expected


def test_fake_sender_called_at_most_once():
    """Defence-in-depth: orchestrator must never retry."""

    counter = {"n": 0}

    def counting_sender(url, headers, body):
        counter["n"] += 1
        return {
            "http_status": 200,
            "json": {
                "retCode": 0,
                "retMsg": "OK",
                "result": {"orderId": "x", "orderLinkId": "y"},
            },
            "raw_text": "{}",
        }

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
        bm_fake_sender=counting_sender,
    )
    assert counter["n"] == 1
    assert r.sender_call_count == 1


# ---------------------------------------------------------------------------
# Rejection: unsupported mode
# ---------------------------------------------------------------------------


def test_unsupported_mode_rejected_no_network():
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode="execute_demo_order",
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
    )
    assert r.status == orc.STATUS_REJECTED_UNSUPPORTED_MODE
    assert r.network_attempted is False
    assert r.bm_invoked is False


# ---------------------------------------------------------------------------
# Rejection: rules not loaded
# ---------------------------------------------------------------------------


def test_rules_not_loaded_rejected_no_network():
    r = _readiness(ir_pre_parsed_response=None)
    assert r.status == orc.STATUS_REJECTED_RULES_NOT_LOADED
    assert r.instrument_rules_loaded is False
    assert r.network_attempted is False
    assert r.bm_invoked is False
    assert r.actual_request_body_qty == ""


def test_rules_wrong_symbol_rejected():
    bad = _good_ir_response(symbol="BTCUSDT")
    r = _readiness(ir_pre_parsed_response=bad)
    # BTCUSDT will fail symbol-lock parsing inside instrument_rules
    # (filtered out), so the candidate is not built.
    assert r.status in (
        orc.STATUS_REJECTED_RULES_INVALID,
        orc.STATUS_REJECTED_RULES_NOT_LOADED,
    )
    assert r.bm_invoked is False
    assert r.network_attempted is False


def test_rules_wrong_status_rejected():
    bad = _good_ir_response(status="Halted")
    r = _readiness(ir_pre_parsed_response=bad)
    assert r.status == orc.STATUS_REJECTED_RULES_INVALID
    assert r.bm_invoked is False
    assert r.network_attempted is False


def test_rules_wrong_min_order_qty_rejected():
    bad = _good_ir_response(min_order_qty="0.2", qty_step="0.2")
    r = _readiness(ir_pre_parsed_response=bad)
    assert r.status == orc.STATUS_REJECTED_RULES_INVALID
    assert r.bm_invoked is False


# ---------------------------------------------------------------------------
# Rejection: cap gate not authorized
# ---------------------------------------------------------------------------


def test_cap_gate_unauthorized_when_flag_missing():
    r = _readiness(explicit_demo_min_qty_cap_authorization_flag=False)
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert r.cap_gate_status != bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert r.bm_invoked is False
    assert r.actual_request_body_qty == ""


def test_cap_gate_unauthorized_when_marker_missing():
    r = _readiness(explicit_demo_min_qty_cap_authorization_marker="")
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert r.cap_gate_status != bm_ce.STATUS_ESCALATION_AUTHORIZED
    assert r.bm_invoked is False


def test_cap_gate_unauthorized_when_marker_wrong():
    r = _readiness(
        explicit_demo_min_qty_cap_authorization_marker="not-the-marker"
    )
    assert r.status == orc.STATUS_REJECTED_CAP_GATE_NOT_AUTHORIZED
    assert r.bm_invoked is False


# ---------------------------------------------------------------------------
# Rejection: missing credentials / fake sender
# ---------------------------------------------------------------------------


def test_execute_with_fake_sender_missing_credentials_rejected_no_network():
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=None,
        bm_fake_sender=lambda url, h, b: None,
    )
    assert r.status == orc.STATUS_REJECTED_MISSING_CREDENTIALS
    assert r.network_attempted is False
    assert r.bm_invoked is False
    assert r.order_sent is False


def test_execute_with_fake_sender_missing_fake_sender_rejected_no_network():
    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
        bm_fake_sender=None,
    )
    assert r.status == orc.STATUS_REJECTED_MISSING_FAKE_SENDER
    assert r.network_attempted is False
    assert r.bm_invoked is False
    assert r.order_sent is False


# ---------------------------------------------------------------------------
# Rejection: real IR discover without injected sender
# ---------------------------------------------------------------------------


def test_real_ir_discover_without_sender_raises_orchestrator_error():
    with pytest.raises(orc.OneShotAuthorizedExecutionOrchestratorError):
        orc.run_one_shot_authorized_execution_orchestration(
            mark_price="100",
            mode=orc.ORCH_MODE_READINESS,
            explicit_demo_min_qty_cap_authorization_flag=True,
            explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
            ir_mode=bm_ir.MODE_DISCOVER,
            ir_sender=None,
        )


def test_real_ir_discover_with_explicit_optin_uses_injected_sender():
    response = {
        "http_status": 200,
        "json": _good_ir_response(),
        "raw_text": "{}",
    }

    def ir_sender(url):
        return response

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_READINESS,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_mode=bm_ir.MODE_DISCOVER,
        ir_sender=ir_sender,
    )
    assert r.status == orc.STATUS_OK_READINESS_READ_ONLY_NETWORK
    assert r.actual_request_body_qty == "0.1"


def test_non_callable_ir_sender_raises_orchestrator_error():
    with pytest.raises(orc.OneShotAuthorizedExecutionOrchestratorError):
        orc.run_one_shot_authorized_execution_orchestration(
            mark_price="100",
            mode=orc.ORCH_MODE_READINESS,
            explicit_demo_min_qty_cap_authorization_flag=True,
            explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
            ir_pre_parsed_response=_good_ir_response(),
            ir_sender="not-callable",  # type: ignore[arg-type]
        )


# ---------------------------------------------------------------------------
# Bybit fake reject -> orchestrator surfaces BM_BYBIT_NOT_EXECUTED
# ---------------------------------------------------------------------------


def test_fake_sender_bybit_reject_surfaces_bm_bybit_not_executed():
    def bad_sender(url, headers, body):
        return {
            "http_status": 200,
            "json": {"retCode": 10004, "retMsg": "Error sign"},
            "raw_text": "{}",
        }

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
        bm_fake_sender=bad_sender,
    )
    assert r.status == orc.STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED
    assert r.bm_final_status == bm.STATUS_BYBIT_REJECTED_NO_ORDER_SENT
    assert r.order_endpoint_called is True
    assert r.order_sent is False
    assert r.sender_call_count == 1


def test_fake_sender_network_error_surfaces_bm_network_error():
    def err_sender(url, headers, body):
        return {
            "_network_error": True,
            "_error_repr": "URLError: simulated",
        }

    r = orc.run_one_shot_authorized_execution_orchestration(
        mark_price="100",
        mode=orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        explicit_demo_min_qty_cap_authorization_flag=True,
        explicit_demo_min_qty_cap_authorization_marker=_AUTH_MARKER,
        ir_pre_parsed_response=_good_ir_response(),
        bm_credentials=bm.DemoCredentials(
            api_key="k", api_secret="s", recv_window="5000"
        ),
        bm_fake_sender=err_sender,
    )
    assert r.status == orc.STATUS_REJECTED_BM_NETWORK_ERROR
    assert r.bm_final_status == bm.STATUS_NETWORK_ERROR_DEMO_ONLY
    assert r.order_sent is False


# ---------------------------------------------------------------------------
# Static-source guarantees
# ---------------------------------------------------------------------------


_ORCH_SRC = Path(orc.__file__).read_text(encoding="utf-8")


def test_module_does_not_import_main_or_risk_or_bybit_executor():
    tree = ast.parse(_ORCH_SRC)
    forbidden = {"main", "src.risk", "src.executors.bybit"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden, alias.name
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod not in forbidden, mod


def test_module_does_not_reference_bybit_executor_class():
    # Docstrings/comments are allowed to discuss these names ("we do
    # NOT import BybitExecutor"); only non-string, non-comment tokens
    # are checked.
    forbidden = ("BybitExecutor", "src.risk", "main.py")
    tokens = tokenize.generate_tokens(io.StringIO(_ORCH_SRC).readline)
    for tok in tokens:
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            continue
        for needle in forbidden:
            assert needle not in tok.string, (needle, tok.string)


def test_module_never_reads_live_named_env_var_in_code():
    """Allow docstring/comment mentions of LIVE; forbid `BYBIT_LIVE` in code."""

    forbidden_in_code = ("BYBIT_LIVE_API_KEY", "BYBIT_LIVE_API_SECRET")
    tokens = tokenize.generate_tokens(io.StringIO(_ORCH_SRC).readline)
    for tok in tokens:
        if tok.type == tokenize.STRING:
            # Skip docstring-style references to LIVE.
            continue
        if tok.type == tokenize.COMMENT:
            continue
        for forbidden in forbidden_in_code:
            assert forbidden not in tok.string


def test_module_never_constructs_live_endpoint_url_constants():
    assert "https://api.bybit.com" not in _ORCH_SRC
    assert "https://api.bytick.com" not in _ORCH_SRC


def test_module_only_allowed_demo_endpoint_used_via_bm():
    # The orchestrator never embeds the demo endpoint URL string itself
    # in executable code; all sender-bound URLs come from BM/bm_ir.
    tokens = tokenize.generate_tokens(io.StringIO(_ORCH_SRC).readline)
    for tok in tokens:
        if tok.type in (tokenize.STRING, tokenize.COMMENT):
            continue
        assert "api-demo.bybit.com" not in tok.string


# ---------------------------------------------------------------------------
# write_report
# ---------------------------------------------------------------------------


def test_write_report_emits_four_files_and_json_round_trips(tmp_path):
    r = _readiness()
    paths = orc.write_report(r, output_dir=tmp_path)
    assert set(paths.keys()) == {"json_latest", "md_latest", "json_ts", "md_ts"}
    for key, p in paths.items():
        assert p.exists(), key
    json_obj = json.loads(paths["json_latest"].read_text(encoding="utf-8"))
    assert json_obj["task_id"] == orc.TASK_ID
    assert json_obj["status"] == orc.STATUS_OK_READINESS_NO_NETWORK
    assert json_obj["actual_request_body_qty"] == "0.1"
    assert json_obj["actual_request_body_qty_source"] == (
        bm_wire.EXECUTION_QTY_SOURCE_CAP_ESCALATION_AUTHORIZED
    )
    md = paths["md_latest"].read_text(encoding="utf-8")
    assert orc.TASK_ID in md
    assert "actual_request_body_qty" in md


# ---------------------------------------------------------------------------
# Report immutability + to_dict
# ---------------------------------------------------------------------------


def test_orchestration_report_is_frozen():
    from dataclasses import FrozenInstanceError

    r = _readiness()
    with pytest.raises(FrozenInstanceError):
        r.status = "MUTATED"  # type: ignore[misc]


def test_to_dict_exposes_required_surfaces():
    r = _readiness()
    d = r.to_dict()
    for required in (
        "instrument_rules_loaded",
        "candidate_qty",
        "candidate_notional",
        "cap_gate_status",
        "wiring_status",
        "original_packet_qty",
        "actual_request_body_qty",
        "actual_request_body_qty_source",
        "body_qty_authorized_override",
        "network_attempted",
        "order_endpoint_called",
        "order_sent",
    ):
        assert required in d, required


# ---------------------------------------------------------------------------
# No-fallback contract
# ---------------------------------------------------------------------------


def test_no_fallback_to_zero_point_zero_one_on_any_rejection():
    """Every rejection branch must surface actual_request_body_qty != '0.01'."""

    cases = [
        # rules not loaded
        _readiness(ir_pre_parsed_response=None),
        # invalid rules
        _readiness(ir_pre_parsed_response=_good_ir_response(status="Halted")),
        # cap gate not authorized
        _readiness(explicit_demo_min_qty_cap_authorization_flag=False),
        # cap gate marker wrong
        _readiness(
            explicit_demo_min_qty_cap_authorization_marker="not-the-marker"
        ),
    ]
    for r in cases:
        # Either empty string (no body planned) or the authorized 0.1;
        # NEVER the invalid 0.01 packet qty.
        assert r.actual_request_body_qty != "0.01"
        # network must never be attempted
        assert r.network_attempted is False
        assert r.order_endpoint_called is False
        assert r.order_sent is False


# ---------------------------------------------------------------------------
# Defensive: protected symbols snapshot
# ---------------------------------------------------------------------------


def test_protected_symbols_untouched_flag_is_true_in_happy_path():
    r = _readiness()
    assert r.protected_symbols_untouched is True


def test_tiny_caps_unchanged_snapshot():
    r = _readiness()
    assert r.tiny_qty_cap_sol == format(bh.TINY_QTY_CAP_SOL, "f")
    assert r.tiny_size_cap_usdt == format(bh.TINY_SIZE_CAP_USDT, "f")
    assert r.max_demo_min_qty_notional_cap_usdt == format(
        orc.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT, "f"
    )
