"""TASK-014BM_MIN_QTY_FIX -- tests for demo-only SOLUSDT instrument rules.

Covers:
    * Identity / chain-break markers (TASK_ID / IDENTITY /
      IMPLEMENTATION_PATH_PHASE / IS_REVIEW_CHAIN_SUFFIX /
      NEXT_REQUIRED_TASK passes BH non-review-chain-suffix check).
    * Demo domain / read-only endpoint hard lock.
    * Category and symbol hard lock (rejects non-linear, non-SOLUSDT).
    * Live endpoint rejection.
    * URL builder rejects ``/v5/order/create`` and live tokens.
    * Parser parses minimal SOLUSDT linear instruments-info response
      (minOrderQty / qtyStep / minNotionalValue / maxMktOrderQty /
      tickSize).
    * Parser rejects responses without ``lotSizeFilter``.
    * Parser rejects responses whose symbol entry isn't SOLUSDT.
    * Candidate qty derived from minOrderQty/qtyStep aligns to qtyStep.
    * Candidate notional checks minNotionalValue and bumps qty if the
      minimum-quantity candidate alone is insufficient.
    * Candidate fails closed (TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN) when
      exchange minimum exceeds the tiny safety cap.
    * Confirms ``qty=0.01`` is invalid against the observed Bybit Demo
      minimum.
    * No order endpoint call during discovery (sentinel sender).
    * Discovery does not run BM's execute_demo_order path.
    * Discovery never reads any LIVE or DEMO secret name.
    * Source code does not import ``main`` / ``src.risk`` /
      ``src.executors.bybit`` / ``BybitExecutor`` references.
    * Source code does not import ``requests`` / ``pybit`` / ``aiohttp``
      / ``httpx`` / ``websocket``.
    * Source code never references ``/v5/order/create`` or live hosts.
    * BM ``ExecutionReport`` surfaces instrument-rules fields when an
      ``InstrumentRulesReport`` is passed via the new
      ``instrument_rules`` parameter, with the default still being
      a clean ``False`` / ``""`` set for existing call sites.
"""

from __future__ import annotations

import ast
import json
from decimal import Decimal
from pathlib import Path

import pytest

from src import demo_only_tiny_execution_adapter as bh
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
    assert bm_ir.TASK_ID == "TASK-014BM_MIN_QTY_FIX"
    assert (
        bm_ir.IDENTITY
        == "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-INSTRUMENT-RULES"
    )
    assert bm_ir.IMPLEMENTATION_PATH_PHASE == "tiny_order_instrument_rules"
    assert bm_ir.IS_REVIEW_CHAIN_SUFFIX is False
    assert (
        bm_ir.NEXT_REQUIRED_TASK
        == "TASK-014BN_demo_only_tiny_execution_postfill_audit"
    )


def test_next_required_task_passes_bh_non_review_chain_suffix_check():
    # Should not raise.
    bh.assert_next_task_is_not_review_chain_suffix(bm_ir.NEXT_REQUIRED_TASK)


def test_upstream_tasks_include_bm_and_bm_fix():
    assert bm_ir.UPSTREAM_TASKS == (
        "TASK-014BH",
        "TASK-014BM",
        "TASK-014BM_FIX",
    )


# ---------------------------------------------------------------------------
# Endpoint / category / symbol hard lock
# ---------------------------------------------------------------------------


def test_allowed_readonly_url_is_demo_only():
    assert (
        bm_ir.ALLOWED_READONLY_URL
        == "https://api-demo.bybit.com/v5/market/instruments-info"
    )
    assert bm_ir.ALLOWED_DEMO_HOST == "api-demo.bybit.com"
    assert bm_ir.ALLOWED_CATEGORY == "linear"
    assert bm_ir.ALLOWED_SYMBOL == "SOLUSDT"


def test_build_readonly_request_url_default():
    url = bm_ir.build_readonly_request_url()
    assert url.startswith(bm_ir.ALLOWED_READONLY_URL + "?")
    assert "category=linear" in url
    assert "symbol=SOLUSDT" in url


@pytest.mark.parametrize(
    "category",
    ["spot", "inverse", "option", "", "LINEAR", "linear "],
)
def test_build_readonly_request_url_rejects_non_linear(category):
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.build_readonly_request_url(category=category)


@pytest.mark.parametrize(
    "symbol",
    ["BTCUSDT", "ETHUSDT", "ENAUSDT", "AIXBTUSDT", "", "solusdt"],
)
def test_build_readonly_request_url_rejects_non_solusdt(symbol):
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.build_readonly_request_url(symbol=symbol)


def test_run_discovery_rejects_non_linear():
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.run_instrument_rules_discovery(category="spot")


def test_run_discovery_rejects_non_solusdt():
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.run_instrument_rules_discovery(symbol="BTCUSDT")


def test_real_sender_refuses_non_readonly_url():
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir._real_public_get_via_urllib(
            "https://api.bybit.com/v5/market/instruments-info?category=linear&symbol=SOLUSDT"
        )


def test_real_sender_refuses_order_create_url():
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir._real_public_get_via_urllib(
            "https://api-demo.bybit.com/v5/order/create?category=linear&symbol=SOLUSDT"
        )


def test_forbidden_url_tokens_include_order_create_and_live_hosts():
    assert "/v5/order/create" in bm_ir.FORBIDDEN_URL_TOKENS
    assert "https://api.bybit.com" in bm_ir.FORBIDDEN_URL_TOKENS
    assert "https://api.bytick.com" in bm_ir.FORBIDDEN_URL_TOKENS


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _build_response(
    *,
    symbol: str = "SOLUSDT",
    min_order_qty: str = "0.1",
    qty_step: str = "0.1",
    min_notional_value: str = "5",
    max_mkt_order_qty: str | None = "1000",
    tick_size: str | None = "0.001",
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


def test_parse_instrument_rules_minimal():
    parsed = _build_response()
    rules = bm_ir.parse_instrument_rules(parsed)
    assert rules.symbol == "SOLUSDT"
    assert rules.min_order_qty == "0.1"
    assert rules.qty_step == "0.1"
    assert rules.min_notional_value == "5"
    assert rules.max_mkt_order_qty == "1000"
    assert rules.tick_size == "0.001"
    assert rules.source_endpoint == bm_ir.ALLOWED_READONLY_URL
    assert rules.source_query == {"category": "linear", "symbol": "SOLUSDT"}


def test_parse_instrument_rules_optional_fields_missing():
    parsed = _build_response(max_mkt_order_qty=None, tick_size=None)
    rules = bm_ir.parse_instrument_rules(parsed)
    assert rules.max_mkt_order_qty is None
    assert rules.tick_size is None


def test_parse_instrument_rules_rejects_missing_lot_size_filter():
    bad = {
        "retCode": 0,
        "result": {"list": [{"symbol": "SOLUSDT", "status": "Trading"}]},
    }
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.parse_instrument_rules(bad)


def test_parse_instrument_rules_rejects_missing_min_order_qty():
    bad = _build_response()
    del bad["result"]["list"][0]["lotSizeFilter"]["minOrderQty"]
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.parse_instrument_rules(bad)


def test_parse_instrument_rules_rejects_non_solusdt_entry():
    bad = _build_response(symbol="BTCUSDT")
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.parse_instrument_rules(bad)


def test_parse_instrument_rules_rejects_empty_list():
    bad = {"retCode": 0, "result": {"list": []}}
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.parse_instrument_rules(bad)


# ---------------------------------------------------------------------------
# Candidate qty computation
# ---------------------------------------------------------------------------


def test_candidate_aligns_to_qty_step():
    rules = bm_ir.parse_instrument_rules(
        _build_response(min_order_qty="0.1", qty_step="0.1", min_notional_value="0")
    )
    candidate = bm_ir.compute_candidate_tiny_qty(rules, mark_price="100")
    assert candidate.aligns_to_qty_step is True
    assert candidate.candidate_qty == "0.1"
    assert candidate.satisfies_min_order_qty is True


def test_candidate_bumps_qty_to_meet_min_notional():
    # minOrderQty=0.01 but minNotionalValue=5 USDT at mark=100 -> required
    # 0.05 SOL; qty_step=0.01 -> candidate 0.05.
    rules = bm_ir.parse_instrument_rules(
        _build_response(
            min_order_qty="0.01",
            qty_step="0.01",
            min_notional_value="5",
        )
    )
    candidate = bm_ir.compute_candidate_tiny_qty(rules, mark_price="100")
    assert candidate.candidate_qty == "0.05"
    assert Decimal(candidate.candidate_notional) >= Decimal("5")
    assert candidate.satisfies_min_notional_value is True
    assert candidate.aligns_to_qty_step is True
    assert candidate.within_tiny_qty_cap is True
    assert candidate.within_tiny_size_cap is True


def test_candidate_fails_closed_when_exchange_min_exceeds_tiny_cap():
    # Observed Bybit Demo current behaviour: minOrderQty likely >= 0.1 SOL,
    # which exceeds TINY_QTY_CAP_SOL=0.05 -> must fail closed.
    rules = bm_ir.parse_instrument_rules(
        _build_response(
            min_order_qty="0.1",
            qty_step="0.1",
            min_notional_value="5",
        )
    )
    candidate = bm_ir.compute_candidate_tiny_qty(rules, mark_price="100")
    assert candidate.status == bm_ir.STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN
    assert candidate.is_executable_under_tiny_caps is False
    assert candidate.within_tiny_qty_cap is False
    assert "fail closed" in candidate.reason.lower()


def test_candidate_confirms_qty_0_01_invalid_when_min_is_0_1():
    rules = bm_ir.parse_instrument_rules(
        _build_response(min_order_qty="0.1", qty_step="0.1", min_notional_value="5")
    )
    candidate = bm_ir.compute_candidate_tiny_qty(rules, mark_price="100")
    assert candidate.confirms_qty_0_01_invalid is True


def test_candidate_does_not_confirm_qty_0_01_invalid_when_min_is_0_001():
    rules = bm_ir.parse_instrument_rules(
        _build_response(
            min_order_qty="0.001",
            qty_step="0.001",
            min_notional_value="0",
        )
    )
    candidate = bm_ir.compute_candidate_tiny_qty(rules, mark_price="100")
    assert candidate.confirms_qty_0_01_invalid is False


def test_candidate_rules_not_loaded():
    candidate = bm_ir.compute_candidate_tiny_qty(None, mark_price="100")
    assert candidate.status == bm_ir.STATUS_CANDIDATE_RULES_NOT_LOADED
    assert candidate.is_executable_under_tiny_caps is False


def test_candidate_invalid_rules_negative_min_qty():
    rules = bm_ir.InstrumentRules(
        symbol="SOLUSDT",
        status="Trading",
        min_order_qty="-1",
        qty_step="0.1",
        min_notional_value="5",
        max_mkt_order_qty=None,
        tick_size=None,
        source_endpoint=bm_ir.ALLOWED_READONLY_URL,
        source_query={"category": "linear", "symbol": "SOLUSDT"},
    )
    candidate = bm_ir.compute_candidate_tiny_qty(rules, mark_price="100")
    assert candidate.status == bm_ir.STATUS_CANDIDATE_INVALID_RULES


def test_candidate_invalid_mark_price_when_min_notional_positive():
    rules = bm_ir.parse_instrument_rules(
        _build_response(min_order_qty="0.01", qty_step="0.01", min_notional_value="5")
    )
    candidate = bm_ir.compute_candidate_tiny_qty(rules, mark_price=None)
    assert candidate.status == bm_ir.STATUS_CANDIDATE_INVALID_MARK_PRICE


# ---------------------------------------------------------------------------
# Discovery flow (sender injection, sentinel)
# ---------------------------------------------------------------------------


def test_discovery_offline_default_no_network():
    report = bm_ir.run_instrument_rules_discovery()
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False
    assert report.discovery_status == bm_ir.STATUS_DISCOVERY_OFFLINE_NO_NETWORK
    assert report.rules is None
    assert report.candidate is not None
    assert (
        report.candidate.status
        == bm_ir.STATUS_CANDIDATE_RULES_NOT_LOADED
    )


def test_discovery_offline_with_pre_parsed_response():
    parsed = _build_response(min_order_qty="0.1", qty_step="0.1", min_notional_value="5")
    report = bm_ir.run_instrument_rules_discovery(
        mark_price="100", pre_parsed_response=parsed
    )
    assert report.network_attempted is False
    assert report.discovery_status == bm_ir.STATUS_DISCOVERY_OK
    assert report.rules is not None
    assert report.rules.min_order_qty == "0.1"
    assert report.candidate is not None
    assert (
        report.candidate.status
        == bm_ir.STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN
    )


def test_discovery_discover_mode_uses_injected_sender():
    captured: dict = {}

    def sender(url):
        captured["url"] = url
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": json.dumps(_build_response()),
            "json": _build_response(),
        }

    report = bm_ir.run_instrument_rules_discovery(
        mode=bm_ir.MODE_DISCOVER,
        mark_price="100",
        sender=sender,
    )
    assert captured["url"].startswith(bm_ir.ALLOWED_READONLY_URL + "?")
    assert captured["url"].endswith("category=linear&symbol=SOLUSDT")
    assert report.network_attempted is True
    assert report.order_endpoint_called is False
    assert report.order_sent is False
    assert report.discovery_status == bm_ir.STATUS_DISCOVERY_OK
    assert report.rules is not None
    assert report.rules.min_order_qty == "0.1"
    assert report.http_status == 200


def test_discovery_discover_mode_network_error_marks_no_order():
    def sender(url):
        return {
            "_network_error": True,
            "_error_repr": "URLError(reason='boom')",
            "http_status": None,
            "raw_text": "",
            "json": None,
        }

    report = bm_ir.run_instrument_rules_discovery(
        mode=bm_ir.MODE_DISCOVER,
        mark_price="100",
        sender=sender,
    )
    assert report.network_attempted is True
    assert report.order_endpoint_called is False
    assert report.order_sent is False
    assert report.discovery_status == bm_ir.STATUS_DISCOVERY_NETWORK_ERROR


def test_discovery_discover_mode_non_zero_retcode():
    def sender(url):
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": '{"retCode":10003,"retMsg":"API key invalid"}',
            "json": {"retCode": 10003, "retMsg": "API key invalid", "result": {}},
        }

    report = bm_ir.run_instrument_rules_discovery(
        mode=bm_ir.MODE_DISCOVER,
        mark_price="100",
        sender=sender,
    )
    assert report.discovery_status == bm_ir.STATUS_DISCOVERY_BYBIT_NON_ZERO_RETCODE
    assert report.bybit_ret_code == 10003
    assert report.rules is None


def test_discovery_sender_sentinel_no_order_endpoint_called():
    """Sender must never receive the order-create URL."""

    called_urls: list[str] = []

    def sender(url):
        called_urls.append(url)
        assert "/v5/order/create" not in url
        assert "api.bybit.com" not in url
        assert "api.bytick.com" not in url
        return {
            "_network_error": False,
            "http_status": 200,
            "raw_text": json.dumps(_build_response()),
            "json": _build_response(),
        }

    bm_ir.run_instrument_rules_discovery(
        mode=bm_ir.MODE_DISCOVER, mark_price="100", sender=sender
    )
    assert len(called_urls) == 1


def test_discovery_unsupported_mode():
    with pytest.raises(bm_ir.InstrumentRulesDiscoveryError):
        bm_ir.run_instrument_rules_discovery(mode="execute_demo_order")


# ---------------------------------------------------------------------------
# Static source-code invariants
# ---------------------------------------------------------------------------


_SRC_PATH = (
    Path(__file__).resolve().parents[2]
    / "src"
    / "demo_only_tiny_execution_adapter_tiny_order_instrument_rules.py"
)
_SRC = _SRC_PATH.read_text(encoding="utf-8")


def test_source_does_not_import_third_party_http_clients():
    tree = ast.parse(_SRC)
    forbidden = {"requests", "pybit", "aiohttp", "httpx", "websocket"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name.split(".")[0] not in forbidden
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "").split(".")[0] not in forbidden


def test_source_does_not_import_main_or_risk_or_executor():
    tree = ast.parse(_SRC)
    forbidden = {"main", "src.risk", "src.executors.bybit"}
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in forbidden
        elif isinstance(node, ast.ImportFrom):
            assert (node.module or "") not in forbidden


def test_source_has_no_bybit_executor_reference():
    tree = ast.parse(_SRC)
    for node in ast.walk(tree):
        if isinstance(node, ast.Name):
            assert node.id != "BybitExecutor"
        if isinstance(node, ast.Attribute):
            assert node.attr != "BybitExecutor"


def test_source_does_not_mention_order_create_path():
    # Allowed: it appears only as a forbidden token entry inside the
    # FORBIDDEN_URL_TOKENS tuple. There must be no string literal that
    # *constructs* an order-create URL.
    forbidden_url = "https://api-demo.bybit.com/v5/order/create"
    assert forbidden_url not in _SRC
    forbidden_live = "https://api.bybit.com/v5/order/create"
    assert forbidden_live not in _SRC


def _iter_string_constants_excluding_docstrings(tree: ast.AST):
    """Yield string Constant nodes that are NOT module/class/function
    docstrings."""
    docstring_node_ids: set[int] = set()
    for node in ast.walk(tree):
        if isinstance(
            node, (ast.Module, ast.FunctionDef, ast.AsyncFunctionDef, ast.ClassDef)
        ):
            body = getattr(node, "body", [])
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


def test_source_does_not_reference_live_or_demo_secret_env_names_in_code():
    """The module must never read any live or demo secret env name in
    executable code. Docstring mentions (explicit denials of those
    names) are allowed and in fact part of the safety contract."""

    tree = ast.parse(_SRC)
    forbidden_secret_names = {
        "BYBIT_API_KEY",
        "BYBIT_API_SECRET",
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    }
    for node in _iter_string_constants_excluding_docstrings(tree):
        for name in forbidden_secret_names:
            assert name not in node.value, (
                f"non-docstring string literal contains secret env name "
                f"{name!r}: {node.value!r}"
            )
    # And os.environ / os.getenv must not be invoked at all.
    for node in ast.walk(tree):
        if isinstance(node, ast.Attribute):
            assert not (
                isinstance(node.value, ast.Name)
                and node.value.id == "os"
                and node.attr in {"environ", "getenv"}
            )


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def test_write_report_emits_four_files(tmp_path):
    parsed = _build_response()
    report = bm_ir.run_instrument_rules_discovery(
        mark_price="100", pre_parsed_response=parsed
    )
    paths = bm_ir.write_report(report, output_dir=tmp_path)
    assert set(paths.keys()) == {
        "latest_json",
        "latest_md",
        "timestamped_json",
        "timestamped_md",
    }
    for key, path in paths.items():
        assert path.exists()
        assert path.stat().st_size > 0
    parsed_json = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert parsed_json["task_id"] == "TASK-014BM_MIN_QTY_FIX"
    assert parsed_json["allowed_readonly_url"] == bm_ir.ALLOWED_READONLY_URL
    assert parsed_json["rules"]["symbol"] == "SOLUSDT"
    assert parsed_json["candidate"]["status"] in (
        bm_ir.STATUS_CANDIDATE_OK,
        bm_ir.STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN,
    )
    md_text = paths["latest_md"].read_text(encoding="utf-8")
    assert "TASK-014BM_MIN_QTY_FIX" in md_text
    assert "minOrderQty" in md_text


# ---------------------------------------------------------------------------
# BM ExecutionReport surfacing (existing call sites unchanged)
# ---------------------------------------------------------------------------


def test_bm_execution_report_default_omits_instrument_rules(monkeypatch):
    """Calling BM without instrument_rules must leave the new fields at
    their safe defaults."""
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    ):
        monkeypatch.delenv(name, raising=False)
    report = bm.run_explicit_tiny_order_execution(mode=bm.MODE_READINESS)
    assert report.instrument_rules_loaded is False
    assert report.instrument_rules_discovery_status == ""
    assert report.instrument_rules_min_order_qty == ""
    assert report.instrument_rules_qty_step == ""
    assert report.instrument_rules_min_notional_value == ""
    assert report.computed_candidate_qty == ""
    assert report.computed_candidate_notional == ""
    assert report.candidate_is_executable_under_tiny_caps is False
    assert report.qty_0_01_confirmed_invalid is False
    # BM should not have called the network.
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False


def test_bm_execution_report_surfaces_instrument_rules(monkeypatch):
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    ):
        monkeypatch.delenv(name, raising=False)
    parsed = _build_response(
        min_order_qty="0.1", qty_step="0.1", min_notional_value="5"
    )
    ir_report = bm_ir.run_instrument_rules_discovery(
        mark_price="100", pre_parsed_response=parsed
    )
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS, instrument_rules=ir_report
    )
    assert report.instrument_rules_loaded is True
    assert report.instrument_rules_discovery_status == bm_ir.STATUS_DISCOVERY_OK
    assert report.instrument_rules_min_order_qty == "0.1"
    assert report.instrument_rules_qty_step == "0.1"
    assert report.instrument_rules_min_notional_value == "5"
    # Exchange minimum exceeds tiny cap → candidate not executable.
    assert report.candidate_is_executable_under_tiny_caps is False
    assert report.qty_0_01_confirmed_invalid is True
    assert report.computed_candidate_qty != ""
    assert report.network_attempted is False
    assert report.order_endpoint_called is False
    assert report.order_sent is False


def test_bm_execution_report_with_executable_candidate(monkeypatch):
    for name in (
        "BYBIT_DEMO_API_KEY",
        "BYBIT_DEMO_API_SECRET",
        "BYBIT_DEMO_RECV_WINDOW",
    ):
        monkeypatch.delenv(name, raising=False)
    # minOrderQty=0.01 with qty_step=0.01 and min_notional=0 → candidate 0.01
    parsed = _build_response(
        min_order_qty="0.01", qty_step="0.01", min_notional_value="0"
    )
    ir_report = bm_ir.run_instrument_rules_discovery(
        mark_price="100", pre_parsed_response=parsed
    )
    report = bm.run_explicit_tiny_order_execution(
        mode=bm.MODE_READINESS, instrument_rules=ir_report
    )
    assert report.candidate_is_executable_under_tiny_caps is True
    assert report.qty_0_01_confirmed_invalid is False
    assert report.computed_candidate_qty == "0.01"
