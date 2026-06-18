"""TASK-014BK Stage 1 tests -- demo-only tiny execution adapter final
pre-execution checklist.

These tests verify that the BK checklist:
    * carries the correct chain-break identity markers,
    * aggregates the BH/BI/BJ safety proofs into one ``all_passed``
      report,
    * applies the required static-source invariants to BH/BI/BJ
      (no network imports, no secret reads, no send/post_order/submit_order
      surfaces, no main/src.risk imports, no src.executors.bybit imports,
      BI+BJ consume BH directly, BH chain-break literals present),
    * surfaces BH/BJ runtime invariants (allowed environment, allowed
      symbol, protected symbols, live endpoint denylist, tiny caps,
      NOT_SENT markers, BJ GUARD_STEPS),
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


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------


def test_bk_identity_markers():
    assert bk.TASK_ID == "TASK-014BK"
    assert bk.IDENTITY == (
        "DEMO-ONLY-TINY-EXECUTION-ADAPTER-FINAL-PRE-EXECUTION-CHECKLIST"
    )
    assert bk.IMPLEMENTATION_PATH_PHASE == "final_pre_execution_checklist"
    assert bk.IS_REVIEW_CHAIN_SUFFIX is False
    assert bk.UPSTREAM_TASKS == ("TASK-014BH", "TASK-014BI", "TASK-014BJ")


def test_bk_next_required_task_is_not_review_chain_suffix():
    for suffix in (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ):
        assert not bk.NEXT_REQUIRED_TASK.endswith(suffix)
    # And BH's runtime guard agrees.
    bh.assert_next_task_is_not_review_chain_suffix(bk.NEXT_REQUIRED_TASK)


def test_bk_next_required_task_points_at_explicit_demo_only_followup():
    # Must explicitly mention demo_only_tiny_order (preparation /
    # authorization / execution), NOT review_chain language.
    label = bk.NEXT_REQUIRED_TASK.lower()
    assert "demo_only_tiny_order" in label
    assert "review" not in label


def test_bk_checklist_contract_version():
    assert bk.CHECKLIST_CONTRACT_VERSION == (
        "demo_only_tiny_execution_adapter_final_pre_execution_checklist_v1"
    )


def test_bk_report_name_and_default_output_dir():
    assert bk.REPORT_NAME == (
        "demo_only_tiny_execution_adapter_final_pre_execution_checklist"
    )
    assert bk.DEFAULT_OUTPUT_DIR == (
        Path("outputs/demo_trading") / bk.REPORT_NAME
    )


def test_bk_forbidden_review_chain_suffixes_match_bh():
    assert set(bk.FORBIDDEN_REVIEW_CHAIN_SUFFIXES) == set(
        bh.FORBIDDEN_NEXT_TASK_SUFFIXES
    )


# ---------------------------------------------------------------------------
# Checklist runner -- aggregate outcome
# ---------------------------------------------------------------------------


@pytest.fixture(scope="module")
def report():
    return bk.run_final_pre_execution_checklist()


def test_checklist_all_passed(report):
    failures = [it for it in report.items if not it.passed]
    assert report.all_passed, (
        f"checklist failed; failures: {[(it.item_id, it.detail) for it in failures]!r}"
    )
    assert report.failed_items == 0
    assert report.passed_items == report.total_items


def test_checklist_covers_required_categories(report):
    cats = {it.category for it in report.items}
    required = {"identity", "bh_runtime", "bj_runtime", "static_source", "cross_module"}
    assert required.issubset(cats)


def test_checklist_includes_bi_and_bj_aggregate_runs(report):
    item_ids = {it.item_id for it in report.items}
    assert "bk_item_12_bi_dry_run_all_match" in item_ids
    assert "bk_item_13_bj_integration_all_match" in item_ids
    assert "bk_item_14_happy_path_payload_carries_both_markers" in item_ids


def test_checklist_includes_static_source_for_each_upstream(report):
    for prefix in ("bh", "bi", "bj"):
        for suffix in (
            "no_network_import",
            "no_secret_read",
            "no_send_methods",
            "no_main_or_risk_import",
            "no_executor_import",
            "chain_break_literals",
        ):
            wanted = f"bk_item_static_{prefix}_{suffix}"
            assert any(it.item_id == wanted for it in report.items), wanted


def test_checklist_bi_and_bj_consume_bh_directly(report):
    consume_items = {
        it.item_id: it
        for it in report.items
        if it.item_id.endswith("_consumes_bh_directly")
    }
    assert "bk_item_static_bi_consumes_bh_directly" in consume_items
    assert "bk_item_static_bj_consumes_bh_directly" in consume_items
    for it in consume_items.values():
        assert it.passed, it.detail


def test_checklist_report_summary_fields(report):
    assert report.task_id == "TASK-014BK"
    assert report.is_review_chain_suffix is False
    assert report.bh_identity == bh.IDENTITY
    assert report.bi_identity == bi.IDENTITY
    assert report.bj_identity == bj.IDENTITY
    assert report.bh_allowed_environment == "bybit_demo"
    assert report.bh_allowed_symbol == "SOLUSDT"
    assert set(report.bh_protected_symbols) == {
        "AIXBTUSDT",
        "EDUUSDT",
        "ENAUSDT",
        "POLYXUSDT",
        "TIAUSDT",
    }
    assert report.bh_tiny_size_cap_usdt == "5"
    assert report.bh_tiny_qty_cap_sol == "0.05"
    assert {
        "https://api.bybit.com",
        "https://api.bytick.com",
        "wss://stream.bybit.com",
        "wss://stream.bytick.com",
    }.issubset(set(report.bh_live_endpoint_denylist))
    assert report.bh_audit_response_status_not_sent == "DEMO_ONLY_TINY_BH_NOT_SENT"
    assert report.bj_audit_response_status_not_sent == "DEMO_ONLY_TINY_BJ_NOT_SENT"


def test_checklist_aggregate_counts_match_upstream(report):
    bi_count = len(bi.default_cases()) + len(bi.LIVE_ENDPOINT_CASES)
    bj_count = len(bj.default_integration_cases())
    assert report.bi_dry_run_total_cases == bi_count
    assert report.bj_integration_total_cases == bj_count
    assert report.bi_dry_run_all_match is True
    assert report.bj_integration_all_match is True


# ---------------------------------------------------------------------------
# Frozen dataclass safety
# ---------------------------------------------------------------------------


def test_checklist_item_is_frozen():
    item = bk.ChecklistItem(
        item_id="x",
        category="x",
        description="x",
        passed=True,
        detail="x",
    )
    with pytest.raises(Exception):
        item.passed = False  # type: ignore[misc]


def test_checklist_report_is_frozen(report):
    with pytest.raises(Exception):
        report.all_passed = False  # type: ignore[misc]


# ---------------------------------------------------------------------------
# Negative-control proofs for static-source helpers
# ---------------------------------------------------------------------------


def test_no_network_import_helper_flags_synthetic_network_module(tmp_path):
    """A synthetic module that imports `requests` must fail the check."""

    src_path = tmp_path / "synthetic_network.py"
    src_path.write_text(
        "import requests\n\nVALUE = 1\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        synthetic = __import__("synthetic_network")
        passed, detail = bk._check_no_network_import(synthetic)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("synthetic_network", None)
    assert passed is False
    assert "requests" in detail


def test_no_secret_read_helper_flags_synthetic_getenv(tmp_path):
    src_path = tmp_path / "synthetic_secret.py"
    src_path.write_text(
        "import os\nVAL = os.getenv('X')\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        synthetic = __import__("synthetic_secret")
        passed, detail = bk._check_no_secret_read(synthetic)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("synthetic_secret", None)
    assert passed is False
    assert "getenv" in detail


def test_no_send_methods_helper_flags_synthetic_place_order(tmp_path):
    src_path = tmp_path / "synthetic_send.py"
    src_path.write_text(
        "def place_order():\n    return None\n",
        encoding="utf-8",
    )
    sys.path.insert(0, str(tmp_path))
    try:
        synthetic = __import__("synthetic_send")
        passed, detail = bk._check_no_send_methods(synthetic)
    finally:
        sys.path.remove(str(tmp_path))
        sys.modules.pop("synthetic_send", None)
    assert passed is False
    assert "place_order" in detail


# ---------------------------------------------------------------------------
# Cross-module untouchability
# ---------------------------------------------------------------------------


def test_bybit_executor_not_loaded_after_bk_import():
    bad = [m for m in sys.modules if m == "src.executors.bybit" or m.startswith("src.executors.bybit.")]
    assert bad == []


def test_bh_bi_bj_module_files_untouched_by_bk():
    bh_src = Path(bh.__file__).read_text(encoding="utf-8")
    assert 'AUDIT_RESPONSE_STATUS_NOT_SENT = "DEMO_ONLY_TINY_BH_NOT_SENT"' in bh_src
    assert 'ALLOWED_SYMBOL = "SOLUSDT"' in bh_src
    bj_src = Path(bj.__file__).read_text(encoding="utf-8")
    assert 'BJ_AUDIT_RESPONSE_STATUS_NOT_SENT = "DEMO_ONLY_TINY_BJ_NOT_SENT"' in bj_src
    bi_src = Path(bi.__file__).read_text(encoding="utf-8")
    assert 'TASK_ID = "TASK-014BI"' in bi_src


def test_bk_source_has_no_network_import():
    src = Path(bk.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    imports = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imports.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imports.add(node.module)
    for bad in bk.FORBIDDEN_NETWORK_MODULES:
        assert bad not in imports, f"BK source imports forbidden {bad!r}"
        for m in imports:
            assert not m.startswith(bad + "."), f"BK imports {m!r}"


def test_bk_source_has_no_secret_read_tokens():
    src = Path(bk.__file__).read_text(encoding="utf-8")
    tokens = list(tokenize.generate_tokens(io.StringIO(src).readline))
    names = {t.string for t in tokens if t.type == tokenize.NAME}
    for bad in bk.FORBIDDEN_SECRET_NAMES:
        assert bad not in names, f"BK source contains forbidden token {bad!r}"


def test_bk_source_has_no_send_function_defs_or_calls():
    src = Path(bk.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            assert node.name != "send"
            assert node.name not in bk.FORBIDDEN_SEND_TOKENS
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            assert node.func.attr != "send"
            assert node.func.attr not in bk.FORBIDDEN_SEND_TOKENS


def test_bk_source_does_not_import_main_or_src_risk():
    src = Path(bk.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod not in {"main", "src.risk"}
            for bad in ("main", "src.risk"):
                assert not mod.startswith(bad + "."), mod
        if isinstance(node, ast.Import):
            for alias in node.names:
                assert alias.name not in {"main", "src.risk"}


def test_bk_source_does_not_import_bybit_executor():
    src = Path(bk.__file__).read_text(encoding="utf-8")
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            assert mod != "src.executors.bybit"
            assert not mod.startswith("src.executors.bybit.")


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------


def test_write_report_emits_four_files(tmp_path, report):
    out_dir = tmp_path / "bk_report"
    paths = bk.write_report(report, output_dir=out_dir)

    assert set(paths.keys()) == {
        "latest_json",
        "latest_md",
        "timestamped_json",
        "timestamped_md",
    }
    for path in paths.values():
        assert path.exists() and path.stat().st_size > 0

    # latest_* file names follow the BK convention.
    assert paths["latest_json"].name == f"latest_{bk.REPORT_NAME}.json"
    assert paths["latest_md"].name == f"latest_{bk.REPORT_NAME}.md"


def test_report_json_round_trip(tmp_path, report):
    out_dir = tmp_path / "bk_rt"
    paths = bk.write_report(report, output_dir=out_dir)
    parsed = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert parsed["task_id"] == "TASK-014BK"
    assert parsed["is_review_chain_suffix"] is False
    assert parsed["all_passed"] is True
    assert parsed["total_items"] == report.total_items
    assert parsed["next_required_task"] == bk.NEXT_REQUIRED_TASK
    assert "items" in parsed and len(parsed["items"]) == report.total_items


def test_report_markdown_contains_summary_and_chain_break_markers(tmp_path, report):
    out_dir = tmp_path / "bk_md"
    paths = bk.write_report(report, output_dir=out_dir)
    md = paths["latest_md"].read_text(encoding="utf-8")
    assert "TASK-014BK" in md
    assert "DEMO-ONLY-TINY-EXECUTION-ADAPTER-FINAL-PRE-EXECUTION-CHECKLIST" in md
    assert "is_review_chain_suffix: `False`" in md
    assert "all_passed: `True`" in md
    assert bk.NEXT_REQUIRED_TASK in md
    assert "DEMO_ONLY_TINY_BH_NOT_SENT" in md
    assert "DEMO_ONLY_TINY_BJ_NOT_SENT" in md


# ---------------------------------------------------------------------------
# Defensive runtime checks (re-asserted directly, not via the report)
# ---------------------------------------------------------------------------


def test_bh_review_chain_guard_rejects_each_forbidden_suffix():
    for suffix in bk.FORBIDDEN_REVIEW_CHAIN_SUFFIXES:
        with pytest.raises(bh.DemoOnlyTinyExecutionAdapterError):
            bh.assert_next_task_is_not_review_chain_suffix(
                f"TASK-9999_label{suffix}"
            )


def test_bj_guard_steps_are_eight_canonical():
    assert bj.GUARD_STEPS == (
        "environment",
        "symbol",
        "existing_positions",
        "side",
        "qty_cap",
        "notional_cap",
        "order_link_id_prefix",
        "endpoint_target",
    )


def test_happy_path_payload_audit_carries_both_not_sent_markers():
    request = bj.IntegrationRequest(
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        mark_price="100",
        endpoint_target="https://api-demo.bybit.com/v5/order/create",
    )
    result = bj.integrate_demo_only_tiny_request(request)
    assert result.ok is True
    audit = dict(result.payload_audit or {})
    assert audit["_demo_only_audit_response_status"] == "DEMO_ONLY_TINY_BH_NOT_SENT"
    assert (
        audit["_demo_only_bj_audit_response_status"]
        == "DEMO_ONLY_TINY_BJ_NOT_SENT"
    )
    assert audit["_demo_only_bj_endpoint_target_validated"] is True
    assert (
        audit["_demo_only_bj_integration_contract_version"]
        == bj.INTEGRATION_CONTRACT_VERSION
    )
