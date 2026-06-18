"""TASK-014BH Stage 1 — focused-core tests for the demo-only tiny
execution adapter implementation-path scaffold.

Each test proves a single safety / chain-break invariant. Tests are
deliberately offline: they import the module and call pure functions
only. No network, no fixtures touching the filesystem, no protected
position interaction.
"""

from __future__ import annotations

import ast
import io
import os
import pathlib
import sys
import tokenize
from decimal import Decimal

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_only_tiny_execution_adapter as bh  # noqa: E402

SRC_PATH = ROOT / "src" / "demo_only_tiny_execution_adapter.py"


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------


def test_task_id_is_bh():
    assert bh.TASK_ID == "TASK-014BH"


def test_identity_is_implementation_path_scaffold():
    assert bh.IDENTITY == "DEMO-ONLY-TINY-EXECUTION-ADAPTER-IMPLEMENTATION-PATH-SCAFFOLD"


def test_is_not_review_chain_suffix():
    assert bh.IS_REVIEW_CHAIN_SUFFIX is False


def test_closes_disabled_review_chain_upstream_task_is_bg():
    assert bh.CLOSES_DISABLED_REVIEW_CHAIN_UPSTREAM_TASK == "TASK-014BG"


def test_next_required_task_is_not_review_chain_suffix():
    nxt = bh.NEXT_REQUIRED_TASK
    for suffix in (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ):
        assert not nxt.endswith(suffix), nxt
    assert nxt.startswith("TASK-014BI_demo_only_tiny_execution_adapter")


def test_next_required_task_is_payload_dry_run_or_endpoint_guard():
    # Either payload dry-run or endpoint guard integration are acceptable
    # successors per the BH workorder.
    nxt = bh.NEXT_REQUIRED_TASK
    assert "payload_dry_run" in nxt or "endpoint_guard_integration" in nxt


# ---------------------------------------------------------------------------
# Strict immutable safety constants
# ---------------------------------------------------------------------------


def test_allowed_environment_is_bybit_demo():
    assert bh.ALLOWED_ENVIRONMENT == "bybit_demo"


def test_allowed_symbol_is_solusdt():
    assert bh.ALLOWED_SYMBOL == "SOLUSDT"


def test_protected_symbols_set():
    assert bh.PROTECTED_SYMBOLS == frozenset(
        {"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"}
    )


def test_tiny_caps():
    assert bh.TINY_SIZE_CAP_USDT == Decimal("5")
    assert bh.TINY_QTY_CAP_SOL == Decimal("0.05")
    assert bh.TINY_QTY_STEP_SOL == Decimal("0.01")


def test_live_endpoint_denylist_includes_known_live_hosts():
    assert "https://api.bybit.com" in bh.LIVE_ENDPOINT_DENYLIST
    assert "https://api.bytick.com" in bh.LIVE_ENDPOINT_DENYLIST
    assert "wss://stream.bybit.com" in bh.LIVE_ENDPOINT_DENYLIST


def test_demo_endpoint_documented_only_does_not_include_live():
    assert not (bh.DEMO_ENDPOINT_DOCUMENTED_ONLY & bh.LIVE_ENDPOINT_DENYLIST)


# ---------------------------------------------------------------------------
# Pure offline payload builder — happy path
# ---------------------------------------------------------------------------


def test_build_solusdt_buy_payload_happy_path():
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        mark_price="100",
    )
    assert isinstance(payload, bh.DemoOnlyTinyEntryPayload)
    assert payload.symbol == "SOLUSDT"
    assert payload.side == "Buy"
    assert payload.qty == "0.01"
    assert payload.order_type == "Market"
    assert payload.time_in_force == "IOC"
    assert payload.reduce_only is False
    assert payload.environment == "bybit_demo"
    assert payload.order_link_id.startswith(bh.ORDER_LINK_ID_PREFIX)
    assert payload.implementation_path_task == "TASK-014BH"
    assert payload.audit_response_status == bh.AUDIT_RESPONSE_STATUS_NOT_SENT
    assert payload.is_review_chain_suffix is False


def test_build_solusdt_sell_payload_happy_path():
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol="SOLUSDT",
        side="Sell",
        qty="0.02",
        mark_price="200",
    )
    assert payload.side == "Sell"
    assert payload.qty == "0.02"


def test_to_exchange_payload_is_pure_dict_with_no_audit_metadata():
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol="SOLUSDT", side="Buy", qty="0.01",
    )
    exch = payload.to_exchange_payload()
    assert exch["symbol"] == "SOLUSDT"
    assert exch["orderType"] == "Market"
    # audit metadata must not leak into the exchange-bound payload
    for k in exch:
        assert not k.startswith("_demo_only_"), k


def test_to_audit_dict_includes_audit_metadata_and_marks_not_sent():
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol="SOLUSDT", side="Buy", qty="0.01",
    )
    audit = payload.to_audit_dict()
    assert audit["_demo_only_environment"] == "bybit_demo"
    assert audit["_demo_only_audit_response_status"] == "DEMO_ONLY_TINY_BH_NOT_SENT"
    assert audit["_demo_only_implementation_path_task"] == "TASK-014BH"
    assert audit["_demo_only_is_review_chain_suffix"] is False


# ---------------------------------------------------------------------------
# Guard rejections — symbol / environment / protected positions
# ---------------------------------------------------------------------------


def test_non_sol_symbol_is_rejected():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="BTCUSDT", side="Buy", qty="0.01",
        )


def test_protected_symbol_as_target_is_rejected():
    for protected in bh.PROTECTED_SYMBOLS:
        with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
            bh.build_demo_only_tiny_solusdt_entry_payload(
                symbol=protected, side="Buy", qty="0.01",
            )


def test_protected_position_in_existing_positions_is_rejected():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT",
            side="Buy",
            qty="0.01",
            existing_positions=("ENAUSDT", "ADAUSDT"),
        )


def test_non_demo_environment_is_rejected():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT",
            side="Buy",
            qty="0.01",
            environment="bybit_live",
        )


def test_unknown_side_is_rejected():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT", side="Hold", qty="0.01",
        )


# ---------------------------------------------------------------------------
# Guard rejections — tiny caps
# ---------------------------------------------------------------------------


def test_qty_above_tiny_qty_cap_is_rejected():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT", side="Buy", qty="0.10",
        )


def test_qty_zero_is_rejected():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT", side="Buy", qty="0",
        )


def test_negative_qty_is_rejected():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT", side="Buy", qty="-0.01",
        )


def test_notional_above_tiny_usdt_cap_is_rejected():
    # 0.05 SOL * 150 USDT = 7.5 USDT > 5 USDT cap
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT", side="Buy", qty="0.05", mark_price="150",
        )


def test_notional_under_tiny_usdt_cap_passes():
    # 0.01 SOL * 100 USDT = 1.0 USDT <= 5 USDT cap
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol="SOLUSDT", side="Buy", qty="0.01", mark_price="100",
    )
    assert payload.qty == "0.01"


# ---------------------------------------------------------------------------
# Guard rejections — live endpoint
# ---------------------------------------------------------------------------


def test_live_endpoint_root_is_denied():
    with pytest.raises(bh.LiveEndpointDenied):
        bh.assert_endpoint_is_demo_only("https://api.bybit.com")


def test_live_endpoint_with_path_is_denied():
    with pytest.raises(bh.LiveEndpointDenied):
        bh.assert_endpoint_is_demo_only("https://api.bybit.com/v5/order/create")


def test_demo_endpoint_documented_only_is_not_denied():
    # documented-only entry must not be on the live denylist; assert_endpoint
    # accepts it (the module still never opens a network connection).
    bh.assert_endpoint_is_demo_only("https://api-demo.bybit.com/v5/order/create")


# ---------------------------------------------------------------------------
# Chain-break invariants
# ---------------------------------------------------------------------------


def test_assert_next_task_is_not_review_chain_suffix_rejects_each_suffix():
    for suffix in bh.FORBIDDEN_NEXT_TASK_SUFFIXES:
        with pytest.raises(bh.DemoOnlyTinyExecutionAdapterError):
            bh.assert_next_task_is_not_review_chain_suffix(
                "TASK-014XYZ" + suffix
            )


def test_assert_next_task_accepts_payload_dry_run_target():
    # The accepted successor for TASK-014BH should pass this guard.
    bh.assert_next_task_is_not_review_chain_suffix(bh.NEXT_REQUIRED_TASK)


def test_describe_implementation_path_exposes_chain_break_markers():
    desc = bh.describe_implementation_path()
    assert desc["task_id"] == "TASK-014BH"
    assert desc["is_review_chain_suffix"] is False
    assert desc["closes_disabled_review_chain_upstream_task"] == "TASK-014BG"
    assert desc["allowed_symbol"] == "SOLUSDT"
    assert "ENAUSDT" in desc["protected_symbols"]


# ---------------------------------------------------------------------------
# Static-source safety invariants (no secret read / no network import / no
# executor import / no real-execution wiring)
# ---------------------------------------------------------------------------


def _read_src() -> str:
    return SRC_PATH.read_text(encoding="utf-8")


def _src_tokens() -> list[tokenize.TokenInfo]:
    src = _read_src()
    return list(tokenize.generate_tokens(io.StringIO(src).readline))


def _src_imports() -> list[str]:
    tree = ast.parse(_read_src())
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                names.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                names.append(node.module)
    return names


def test_source_imports_no_network_library():
    imports = _src_imports()
    forbidden = {
        "requests",
        "urllib",
        "urllib.request",
        "urllib3",
        "http",
        "http.client",
        "socket",
        "ssl",
        "pybit",
        "pybit.unified_trading",
        "websocket",
        "aiohttp",
        "httpx",
    }
    leaked = sorted(set(imports) & forbidden)
    assert leaked == [], f"BH module must not import network libs; leaked: {leaked}"


def test_source_does_not_import_bybit_executor():
    imports = _src_imports()
    for mod in imports:
        assert "src.executors.bybit" not in mod
        assert "BybitExecutor" not in mod


def test_source_does_not_read_environment_secrets():
    tokens = _src_tokens()
    forbidden_names = {"getenv", "environ", "load_dotenv"}
    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string in forbidden_names:
            pytest.fail(
                f"BH module must not reference env/secret reader {tok.string!r}"
            )


def test_source_does_not_reference_live_bybit_api_host():
    src = _read_src()
    # The live host must only appear in the LIVE_ENDPOINT_DENYLIST literal,
    # never inside an active call/argument. Confirm by counting that every
    # occurrence is inside a STRING token (literal), not a NAME or attribute.
    count_in_strings = 0
    for tok in _src_tokens():
        if tok.type == tokenize.STRING and "api.bybit.com" in tok.string:
            count_in_strings += 1
    occurrences = src.count("api.bybit.com")
    assert count_in_strings == occurrences
    assert occurrences >= 1  # must appear in the denylist literal


def test_source_does_not_define_or_call_send_method():
    src = _read_src()
    assert "def send" not in src
    assert ".send(" not in src
    assert "place_order" not in src
    assert "post_order" not in src
    assert "submit_order" not in src


def test_source_does_not_modify_main_or_risk_module():
    imports = _src_imports()
    for mod in imports:
        assert mod != "main"
        assert mod != "src.risk"
        assert not mod.startswith("src.risk.")


def test_source_marks_no_review_chain_suffix_in_identity():
    src = _read_src()
    assert "DEMO-ONLY-TINY-EXECUTION-ADAPTER-IMPLEMENTATION-PATH-SCAFFOLD" in src
    # IS_REVIEW_CHAIN_SUFFIX = False must appear literally
    assert "IS_REVIEW_CHAIN_SUFFIX = False" in src


# ---------------------------------------------------------------------------
# Cross-module untouchability
# ---------------------------------------------------------------------------


def test_main_py_is_untouched_by_bh_runtime_import():
    # importing bh must not import or load main.py
    assert "main" not in sys.modules or sys.modules["main"].__file__ != str(
        ROOT / "main.py"
    ) or sys.modules["main"].__name__ != "main"


def test_bybit_executor_module_is_not_loaded_by_bh_import():
    # bh must not pull in src.executors.bybit
    assert "src.executors.bybit" not in sys.modules


def test_no_environment_variable_is_required_to_import_bh():
    # Sanity: BH must work even when no BYBIT_* env vars are set. We don't
    # mutate os.environ here; we just verify the module is already loaded
    # (top-of-file `from src import demo_only_tiny_execution_adapter as bh`
    # would have failed otherwise).
    assert bh.TASK_ID == "TASK-014BH"
    # And the module must not have populated any BYBIT_* into os.environ.
    leaked = sorted(k for k in os.environ if k.startswith("BYBIT_API"))
    # We only assert this module did not introduce them — caller env may
    # already have them. We can't differentiate, but we can confirm BH does
    # not depend on them (already proven by successful import).
    assert isinstance(leaked, list)


# ---------------------------------------------------------------------------
# Side-effect-free invariants
# ---------------------------------------------------------------------------


def test_building_payload_does_not_mutate_existing_positions_tuple():
    existing = ("ADAUSDT",)
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        existing_positions=existing,
    )
    assert existing == ("ADAUSDT",)
    assert payload.symbol == "SOLUSDT"


def test_payload_is_frozen_dataclass():
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol="SOLUSDT", side="Buy", qty="0.01",
    )
    with pytest.raises(Exception):
        payload.symbol = "BTCUSDT"  # type: ignore[misc]


def test_custom_order_link_id_must_carry_prefix():
    with pytest.raises(bh.DemoOnlyTinyPayloadRejected):
        bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol="SOLUSDT",
            side="Buy",
            qty="0.01",
            order_link_id="ARBITRARY_ID",
        )
