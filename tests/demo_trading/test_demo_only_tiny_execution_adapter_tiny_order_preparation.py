"""TASK-014BL Stage 1 tests -- demo-only tiny execution adapter tiny
order preparation.

These tests verify that the BL preparation module:
    * carries the correct chain-break identity markers,
    * points the next required task at the explicit demo-only tiny
      order execution successor (NOT another review-chain suffix),
    * builds the offline preparation packet via BJ's guarded entry,
    * embeds the BK checklist + BJ integration summaries in the
      ``PreparationReport``,
    * layers the BL audit markers on top of the BH+BJ audit dict and
      explicitly declares the packet is NOT an execution authorization,
    * applies the required static-source safety invariants (no network
      imports, no secret reads, no send/post_order/submit_order
      surfaces, no main/src.risk imports, no src.executors.bybit
      imports, consumes BH/BI/BJ/BK directly, BH chain-break literals
      present),
    * rejects forbidden requests (non-SOLUSDT symbols, protected
      positions, tiny-cap violations, live endpoint targets,
      bybit_live environment),
    * writes JSON + Markdown report files (latest_* + timestamped) that
      round-trip,
    * does NOT touch main.py / src/risk.py / BybitExecutor / G20 sender.

The tests are pure offline: nothing imports a network library, nothing
opens a socket, no order is built into anything sender-shaped.
"""

from __future__ import annotations

import ast
import io
import json
import sys
import tokenize
from dataclasses import FrozenInstanceError
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


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------


def test_bl_identity_markers():
    assert bl.TASK_ID == "TASK-014BL"
    assert bl.IDENTITY == (
        "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-PREPARATION"
    )
    assert bl.IMPLEMENTATION_PATH_PHASE == "tiny_order_preparation"
    assert bl.IS_REVIEW_CHAIN_SUFFIX is False
    assert bl.UPSTREAM_TASKS == (
        "TASK-014BH",
        "TASK-014BI",
        "TASK-014BJ",
        "TASK-014BK",
    )


def test_bl_next_required_task_is_not_review_chain_suffix():
    for suffix in (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ):
        assert not bl.NEXT_REQUIRED_TASK.endswith(suffix)
    bh.assert_next_task_is_not_review_chain_suffix(bl.NEXT_REQUIRED_TASK)


def test_bl_next_required_task_points_at_explicit_demo_only_execution():
    label = bl.NEXT_REQUIRED_TASK.lower()
    assert "demo_only" in label
    assert "tiny_order_execution" in label
    assert "review" not in label
    assert bl.TARGET_FUTURE_TASK == bl.NEXT_REQUIRED_TASK


def test_bl_preparation_contract_version():
    assert bl.PREPARATION_CONTRACT_VERSION == (
        "demo_only_tiny_execution_adapter_tiny_order_preparation_v1"
    )


def test_bl_audit_response_status_not_sent():
    assert (
        bl.BL_AUDIT_RESPONSE_STATUS_NOT_SENT
        == "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"
    )


def test_bl_default_request_constants():
    assert bl.DEFAULT_SYMBOL == "SOLUSDT"
    assert bl.DEFAULT_SIDE in {"Buy", "Sell"}
    assert bl.DEFAULT_ORDER_TYPE == "Market"
    assert bl.DEFAULT_TIME_IN_FORCE == "IOC"
    assert bl.DEFAULT_REDUCE_ONLY is False
    assert bl.DEFAULT_DEMO_ENDPOINT.startswith("https://api-demo.bybit.com")


def test_bl_packet_note_states_not_execution_authorization():
    note = bl.PACKET_IS_NOT_EXECUTION_AUTHORIZATION_NOTE
    assert "PREPARATION ONLY" in note
    assert "NOT authorize execution" in note
    assert bl.TARGET_FUTURE_TASK in note


# ---------------------------------------------------------------------------
# Aggregate run_tiny_order_preparation
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def report():
    return bl.run_tiny_order_preparation()


def test_run_preparation_all_passed(report):
    assert report.all_passed is True
    assert report.bk_checklist_all_passed is True
    assert report.bj_integration_ok is True
    assert report.bj_integration_rejection_step == ""
    assert report.bj_integration_rejection_reason == ""


def test_run_preparation_identity_fields(report):
    assert report.task_id == "TASK-014BL"
    assert report.identity == bl.IDENTITY
    assert report.phase == bl.IMPLEMENTATION_PATH_PHASE
    assert report.upstream_tasks == bl.UPSTREAM_TASKS
    assert report.next_required_task == bl.NEXT_REQUIRED_TASK
    assert report.target_future_task == bl.TARGET_FUTURE_TASK
    assert report.is_review_chain_suffix is False
    assert report.preparation_contract_version == bl.PREPARATION_CONTRACT_VERSION


def test_run_preparation_upstream_identities(report):
    assert report.bh_identity == bh.IDENTITY
    assert report.bi_identity == bi.IDENTITY
    assert report.bj_identity == bj.IDENTITY
    assert report.bk_identity == bk.IDENTITY


def test_run_preparation_bk_checklist_counts_match(report):
    checklist = bk.run_final_pre_execution_checklist()
    assert report.bk_checklist_total_items == checklist.total_items
    assert report.bk_checklist_passed_items == checklist.passed_items
    assert report.bk_checklist_failed_items == checklist.failed_items


# ---------------------------------------------------------------------------
# PreparationPacket invariants
# ---------------------------------------------------------------------------


def test_packet_is_frozen(report):
    assert report.packet is not None
    with pytest.raises(FrozenInstanceError):
        report.packet.symbol = "BTCUSDT"  # type: ignore[misc]


def test_packet_request_fields_match_defaults(report):
    pkt = report.packet
    assert pkt is not None
    assert pkt.task_id == "TASK-014BL"
    assert pkt.upstream_tasks == bl.UPSTREAM_TASKS
    assert pkt.target_future_task == bl.TARGET_FUTURE_TASK
    assert pkt.environment == "bybit_demo"
    assert pkt.symbol == "SOLUSDT"
    assert pkt.side == bl.DEFAULT_SIDE
    assert pkt.qty == bl.DEFAULT_QTY
    assert pkt.mark_price == bl.DEFAULT_MARK_PRICE
    assert pkt.order_type == "Market"
    assert pkt.reduce_only is False
    assert pkt.time_in_force == "IOC"
    assert pkt.order_link_id.startswith(bh.ORDER_LINK_ID_PREFIX)
    assert pkt.order_link_id_prefix == bh.ORDER_LINK_ID_PREFIX


def test_packet_notional_estimate_matches(report):
    pkt = report.packet
    assert pkt is not None
    assert pkt.notional_estimate is not None
    # qty 0.01 * mark 100 = 1
    from decimal import Decimal

    assert Decimal(pkt.notional_estimate) == Decimal("1")
    # Stays well under BH tiny notional cap.
    assert Decimal(pkt.notional_estimate) <= bh.TINY_SIZE_CAP_USDT


def test_packet_is_explicitly_not_execution_authorization(report):
    pkt = report.packet
    assert pkt is not None
    assert pkt.packet_is_not_execution_authorization is True
    assert pkt.audit_response_status == "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"


def test_packet_audit_carries_all_three_marker_layers(report):
    pkt = report.packet
    assert pkt is not None
    audit = pkt.payload_audit
    # BH layer
    assert (
        audit["_demo_only_audit_response_status"]
        == bh.AUDIT_RESPONSE_STATUS_NOT_SENT
        == "DEMO_ONLY_TINY_BH_NOT_SENT"
    )
    assert audit["_demo_only_environment"] == "bybit_demo"
    # BJ layer
    assert (
        audit["_demo_only_bj_audit_response_status"]
        == bj.BJ_AUDIT_RESPONSE_STATUS_NOT_SENT
        == "DEMO_ONLY_TINY_BJ_NOT_SENT"
    )
    assert audit["_demo_only_bj_endpoint_target_validated"] is True
    assert (
        audit["_demo_only_bj_integration_contract_version"]
        == bj.INTEGRATION_CONTRACT_VERSION
    )
    # BL layer
    assert (
        audit["_demo_only_bl_audit_response_status"]
        == "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"
    )
    assert audit["_demo_only_bl_target_future_task"] == bl.TARGET_FUTURE_TASK
    assert (
        audit["_demo_only_bl_authorization_is_not_execution_authorization"]
        is True
    )
    assert (
        audit["_demo_only_bl_preparation_contract_version"]
        == bl.PREPARATION_CONTRACT_VERSION
    )
    assert audit["_demo_only_bl_implementation_path_task"] == "TASK-014BL"
    assert audit["_demo_only_bl_is_review_chain_suffix"] is False


def test_packet_audit_keeps_solusdt_and_market_ioc(report):
    pkt = report.packet
    assert pkt is not None
    audit = pkt.payload_audit
    assert audit["symbol"] == "SOLUSDT"
    assert audit["orderType"] == "Market"
    assert audit["timeInForce"] == "IOC"
    assert audit["reduceOnly"] is False
    assert audit["orderLinkId"].startswith("DEMO_ONLY_TINY_BH_")


# ---------------------------------------------------------------------------
# Direct build_preparation_packet entry
# ---------------------------------------------------------------------------


def test_build_preparation_packet_happy_path():
    packet = bl.build_preparation_packet()
    assert packet.symbol == "SOLUSDT"
    assert packet.environment == "bybit_demo"
    assert packet.audit_response_status == "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"
    assert packet.packet_is_not_execution_authorization is True


@pytest.mark.parametrize(
    "symbol",
    ["BTCUSDT", "ETHUSDT", "DOGEUSDT"],
)
def test_build_preparation_packet_rejects_non_solusdt(symbol):
    with pytest.raises(bl.TinyOrderPreparationError):
        bl.build_preparation_packet(symbol=symbol)


@pytest.mark.parametrize(
    "symbol",
    ["ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"],
)
def test_build_preparation_packet_rejects_protected_symbols(symbol):
    with pytest.raises(bl.TinyOrderPreparationError):
        bl.build_preparation_packet(symbol=symbol)


def test_build_preparation_packet_rejects_protected_in_existing_positions():
    with pytest.raises(bl.TinyOrderPreparationError):
        bl.build_preparation_packet(
            existing_positions=("TIAUSDT", "ADAUSDT"),
        )


def test_build_preparation_packet_rejects_live_endpoint():
    with pytest.raises(bl.TinyOrderPreparationError):
        bl.build_preparation_packet(
            endpoint_target="https://api.bybit.com/v5/order/create",
        )


def test_build_preparation_packet_rejects_qty_over_cap():
    with pytest.raises(bl.TinyOrderPreparationError):
        bl.build_preparation_packet(qty="1.0", mark_price="100")


def test_build_preparation_packet_rejects_notional_over_cap():
    # qty 0.04 SOL * mark 200 USDT = 8 USDT > 5 USDT BH cap
    with pytest.raises(bl.TinyOrderPreparationError):
        bl.build_preparation_packet(qty="0.04", mark_price="200")


def test_build_preparation_packet_rejects_non_demo_environment():
    with pytest.raises(bl.TinyOrderPreparationError):
        bl.build_preparation_packet(environment="bybit_live")


# ---------------------------------------------------------------------------
# Static-source safety invariants on BL itself
# ---------------------------------------------------------------------------


def _bl_source_text() -> str:
    return Path(bl.__file__).read_text(encoding="utf-8")


def _bl_imported_modules() -> set[str]:
    tree = ast.parse(_bl_source_text())
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
                for alias in node.names:
                    imported.add(f"{node.module}.{alias.name}")
    return imported


def test_bl_source_has_no_network_imports():
    imports = _bl_imported_modules()
    for bad in (
        "requests",
        "urllib",
        "urllib3",
        "http",
        "socket",
        "ssl",
        "pybit",
        "websocket",
        "websockets",
        "aiohttp",
        "httpx",
    ):
        hits = [m for m in imports if m == bad or m.startswith(bad + ".")]
        assert not hits, f"BL must not import {bad}: {hits!r}"


def test_bl_source_has_no_secret_reads():
    tokens = list(
        tokenize.generate_tokens(io.StringIO(_bl_source_text()).readline)
    )
    names = {t.string for t in tokens if t.type == tokenize.NAME}
    for forbidden in ("getenv", "environ", "load_dotenv", "dotenv_values"):
        assert forbidden not in names, (
            f"BL must not use secret-reading token {forbidden!r}"
        )


def test_bl_source_has_no_send_surfaces():
    tree = ast.parse(_bl_source_text())
    bad: list[str] = []
    forbidden = {"place_order", "post_order", "submit_order"}
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name in forbidden or node.name == "send":
                bad.append(f"def {node.name}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "send" or node.func.attr in forbidden:
                bad.append(f".{node.func.attr}(call)")
    assert not bad, f"BL must not define/call send-like surfaces: {bad!r}"


def test_bl_source_does_not_import_main_or_risk_or_executor():
    imports = _bl_imported_modules()
    for forbidden in ("main", "src.risk", "src.executors.bybit"):
        hits = [
            m
            for m in imports
            if m == forbidden or m.startswith(forbidden + ".")
        ]
        assert not hits, f"BL must not import {forbidden}: {hits!r}"


def test_bl_source_consumes_upstream_modules_directly():
    imports = _bl_imported_modules()
    required = {
        "src.demo_only_tiny_execution_adapter",
        "src.demo_only_tiny_execution_adapter_payload_dry_run",
        "src.demo_only_tiny_execution_adapter_endpoint_guard_integration",
        "src.demo_only_tiny_execution_adapter_final_pre_execution_checklist",
    }
    missing = required - imports
    assert not missing, f"BL must import upstream modules directly: missing={missing!r}"


def test_bl_source_declares_chain_break_literals():
    tree = ast.parse(_bl_source_text())
    has_false = False
    has_phase = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "IS_REVIEW_CHAIN_SUFFIX"
                    and isinstance(node.value, ast.Constant)
                    and node.value.value is False
                ):
                    has_false = True
                if (
                    isinstance(target, ast.Name)
                    and target.id == "IMPLEMENTATION_PATH_PHASE"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and node.value.value
                ):
                    has_phase = True
    assert has_false, "BL must declare IS_REVIEW_CHAIN_SUFFIX = False at module scope"
    assert has_phase, "BL must declare a non-empty IMPLEMENTATION_PATH_PHASE literal"


# ---------------------------------------------------------------------------
# Cross-module sanity
# ---------------------------------------------------------------------------


def test_bl_does_not_load_bybit_executor():
    loaded = [
        m
        for m in sys.modules
        if m == "src.executors.bybit"
        or m.startswith("src.executors.bybit.")
    ]
    assert loaded == [], (
        f"BL must not cause src.executors.bybit to load: {loaded!r}"
    )


def test_bk_checklist_still_all_passed_under_bl():
    # Defence-in-depth: BL must not weaken or fail BK invariants.
    checklist = bk.run_final_pre_execution_checklist()
    failures = [it for it in checklist.items if not it.passed]
    assert checklist.all_passed is True, f"BK failures: {failures!r}"


def test_packet_audit_qty_within_tiny_cap(report):
    from decimal import Decimal

    pkt = report.packet
    assert pkt is not None
    assert Decimal(pkt.qty) <= bh.TINY_QTY_CAP_SOL


# ---------------------------------------------------------------------------
# Report writer round-trip
# ---------------------------------------------------------------------------


def test_write_report_creates_four_files_and_round_trips(tmp_path, report):
    out_dir = tmp_path / "bl_write_probe"
    paths = bl.write_report(report, output_dir=out_dir)
    assert set(paths.keys()) == {
        "latest_json",
        "latest_md",
        "timestamped_json",
        "timestamped_md",
    }
    for p in paths.values():
        assert p.exists()
        assert p.stat().st_size > 0

    # JSON round-trip with packet preserved.
    loaded = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert loaded["task_id"] == "TASK-014BL"
    assert loaded["all_passed"] is True
    assert loaded["target_future_task"] == bl.TARGET_FUTURE_TASK
    assert loaded["bl_audit_response_status_not_sent"] == (
        "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"
    )
    assert loaded["packet"] is not None
    assert loaded["packet"]["symbol"] == "SOLUSDT"
    assert loaded["packet"]["packet_is_not_execution_authorization"] is True
    assert (
        loaded["packet"]["payload_audit"]["_demo_only_bl_audit_response_status"]
        == "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED"
    )

    md_text = paths["latest_md"].read_text(encoding="utf-8")
    assert "TASK-014BL" in md_text
    assert "tiny_order_preparation" in md_text
    assert "NOT_SENT_PREPARED_ONLY_NOT_EXECUTED" in md_text
    assert bl.TARGET_FUTURE_TASK in md_text
    assert "PREPARATION ONLY" in md_text


# ---------------------------------------------------------------------------
# Default output directory contract
# ---------------------------------------------------------------------------


def test_bl_default_output_dir_under_outputs_demo_trading():
    assert bl.DEFAULT_OUTPUT_DIR == Path(
        "outputs/demo_trading"
    ) / "demo_only_tiny_execution_adapter_tiny_order_preparation"
    assert bl.REPORT_NAME == (
        "demo_only_tiny_execution_adapter_tiny_order_preparation"
    )


# ---------------------------------------------------------------------------
# Frozen dataclass enforcement on report
# ---------------------------------------------------------------------------


def test_preparation_report_is_frozen(report):
    with pytest.raises(FrozenInstanceError):
        report.all_passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Defence-in-depth: BH chain-break suffix guard still rejects every
# forbidden review-chain suffix.
# ---------------------------------------------------------------------------


@pytest.mark.parametrize(
    "suffix",
    [
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ],
)
def test_bh_chain_break_guard_still_rejects_forbidden_suffix(suffix):
    probe = f"TASK-9999_some_label{suffix}"
    with pytest.raises(bh.DemoOnlyTinyExecutionAdapterError):
        bh.assert_next_task_is_not_review_chain_suffix(probe)


def test_bh_chain_break_guard_accepts_bl_pointer():
    bh.assert_next_task_is_not_review_chain_suffix(bl.NEXT_REQUIRED_TASK)
