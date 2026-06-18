"""TASK-014BJ Stage 1 -- focused-core tests for the demo-only tiny
execution adapter endpoint guard integration module.

Exercises the BJ integration entry point (which itself consumes BH) and
verifies every required workorder scenario plus the static-source
safety invariants.
"""

from __future__ import annotations

import ast
import io
import json
import pathlib
import sys
import tokenize

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_only_tiny_execution_adapter as bh  # noqa: E402
from src import demo_only_tiny_execution_adapter_payload_dry_run as bi  # noqa: E402
from src import (  # noqa: E402
    demo_only_tiny_execution_adapter_endpoint_guard_integration as bj,
)

SRC_PATH = (
    ROOT
    / "src"
    / "demo_only_tiny_execution_adapter_endpoint_guard_integration.py"
)


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------


def test_task_id_is_bj():
    assert bj.TASK_ID == "TASK-014BJ"


def test_identity_is_endpoint_guard_integration():
    assert (
        bj.IDENTITY
        == "DEMO-ONLY-TINY-EXECUTION-ADAPTER-ENDPOINT-GUARD-INTEGRATION"
    )


def test_phase_is_endpoint_guard_integration():
    assert bj.IMPLEMENTATION_PATH_PHASE == "endpoint_guard_integration"


def test_is_not_review_chain_suffix():
    assert bj.IS_REVIEW_CHAIN_SUFFIX is False


def test_upstream_task_is_bi():
    assert bj.UPSTREAM_TASK == "TASK-014BI"


def test_next_required_task_does_not_end_in_review_chain_suffix():
    nxt = bj.NEXT_REQUIRED_TASK
    for suffix in (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ):
        assert not nxt.endswith(suffix), nxt
    # BJ's next step must be final demo-only pre-execution checklist or
    # explicit demo-only tiny order preparation (implementation path).
    assert (
        "final_pre_execution_checklist" in nxt
        or "tiny_order_preparation" in nxt
    ), nxt


def test_next_required_task_passes_bh_guard():
    bh.assert_next_task_is_not_review_chain_suffix(bj.NEXT_REQUIRED_TASK)


def test_bj_integration_contract_version_is_v1():
    assert (
        bj.INTEGRATION_CONTRACT_VERSION
        == "demo_only_tiny_execution_adapter_endpoint_guard_integration_v1"
    )


def test_bj_audit_response_status_marker_is_not_sent():
    assert bj.BJ_AUDIT_RESPONSE_STATUS_NOT_SENT == "DEMO_ONLY_TINY_BJ_NOT_SENT"


def test_guard_steps_cover_every_required_check():
    expected = {
        "environment",
        "symbol",
        "existing_positions",
        "side",
        "qty_cap",
        "notional_cap",
        "order_link_id_prefix",
        "endpoint_target",
    }
    assert set(bj.GUARD_STEPS) == expected


# ---------------------------------------------------------------------------
# Canonical case table
# ---------------------------------------------------------------------------


def test_default_integration_cases_include_required_coverage():
    cases = bj.default_integration_cases()
    ids = {c.case_id for c in cases}
    # Required scenarios from the BJ workorder.
    assert any("solusdt_buy_with_demo_endpoint" in i for i in ids)
    assert any("solusdt_sell" in i for i in ids)
    assert any("btcusdt_rejected" in i for i in ids)
    assert any("ethusdt_rejected" in i for i in ids)
    assert any("protected_enausdt" in i for i in ids)
    assert any("protected_tiausdt" in i for i in ids)
    assert any("protected_aixbtusdt" in i for i in ids)
    assert any("protected_polyxusdt" in i for i in ids)
    assert any("protected_eduusdt" in i for i in ids)
    assert any("protected_in_existing_positions" in i for i in ids)
    assert any("bybit_live_environment_rejected" in i for i in ids)
    assert any("live_endpoint_root_rejected" in i for i in ids)
    assert any("live_order_endpoint_rejected" in i for i in ids)
    assert any("live_websocket_endpoint_rejected" in i for i in ids)
    assert any("qty_cap_fail" in i for i in ids)
    assert any("notional_cap_fail" in i for i in ids)


def test_default_integration_cases_have_unique_ids():
    cases = bj.default_integration_cases()
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids))


# ---------------------------------------------------------------------------
# integrate_demo_only_tiny_request -- direct calls
# ---------------------------------------------------------------------------


def _ok_request(**overrides):
    base = dict(
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        mark_price="100",
    )
    base.update(overrides)
    return bj.IntegrationRequest(**base)


def test_valid_solusdt_demo_endpoint_guard_integration_pass():
    req = _ok_request(endpoint_target="https://api-demo.bybit.com/v5/order/create")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is True
    assert result.endpoint_target_validated is True
    assert result.payload_audit is not None
    audit = dict(result.payload_audit)
    assert audit["symbol"] == "SOLUSDT"
    assert audit["_demo_only_audit_response_status"] == "DEMO_ONLY_TINY_BH_NOT_SENT"
    assert audit["_demo_only_bj_audit_response_status"] == "DEMO_ONLY_TINY_BJ_NOT_SENT"
    assert audit["_demo_only_bj_integration_contract_version"] == (
        "demo_only_tiny_execution_adapter_endpoint_guard_integration_v1"
    )
    assert audit["_demo_only_bj_endpoint_target_validated"] is True
    # Every guard step must have been reached and passed.
    passed_steps = {d.step for d in result.decisions if d.passed}
    assert set(bj.GUARD_STEPS).issubset(passed_steps)


def test_valid_solusdt_no_endpoint_target_still_passes():
    req = _ok_request()
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is True
    assert result.endpoint_target_validated is False
    audit = dict(result.payload_audit or {})
    assert audit["_demo_only_bj_endpoint_target_validated"] is False
    assert audit["_demo_only_bj_endpoint_target"] is None


def test_btcusdt_rejected_at_symbol_step():
    req = _ok_request(symbol="BTCUSDT")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "symbol"
    assert "only 'SOLUSDT'" in result.rejection_reason


def test_ethusdt_rejected_at_symbol_step():
    req = _ok_request(symbol="ETHUSDT")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "symbol"
    assert "only 'SOLUSDT'" in result.rejection_reason


@pytest.mark.parametrize(
    "protected",
    ["ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"],
)
def test_each_protected_symbol_rejected_at_symbol_step(protected):
    req = _ok_request(symbol=protected)
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "symbol"
    assert "protected position" in result.rejection_reason
    assert protected in result.rejection_reason


def test_protected_in_existing_positions_rejected():
    req = _ok_request(existing_positions=("TIAUSDT", "ADAUSDT"))
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "existing_positions"
    assert "TIAUSDT" in result.rejection_reason


def test_bybit_live_environment_rejected():
    req = _ok_request(environment="bybit_live")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "environment"
    assert "bybit_live" in result.rejection_reason


def test_live_endpoint_root_rejected_at_endpoint_step():
    req = _ok_request(endpoint_target="https://api.bybit.com")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "endpoint_target"
    assert "live denylist" in result.rejection_reason


def test_live_order_endpoint_rejected_at_endpoint_step():
    req = _ok_request(
        endpoint_target="https://api.bybit.com/v5/order/create"
    )
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "endpoint_target"
    assert "live denylist" in result.rejection_reason


def test_live_mirror_order_endpoint_rejected_at_endpoint_step():
    req = _ok_request(
        endpoint_target="https://api.bytick.com/v5/order/create"
    )
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "endpoint_target"
    assert "live denylist" in result.rejection_reason


def test_live_websocket_endpoint_rejected_at_endpoint_step():
    req = _ok_request(
        endpoint_target="wss://stream.bybit.com/v5/public/linear"
    )
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "endpoint_target"
    assert "live denylist" in result.rejection_reason


def test_qty_cap_fail_at_qty_step():
    req = _ok_request(qty="0.10", mark_price=None)
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "qty_cap"
    assert "tiny cap" in result.rejection_reason


def test_notional_cap_fail_at_notional_step():
    req = _ok_request(qty="0.05", mark_price="150")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "notional_cap"
    assert "exceeds tiny size cap" in result.rejection_reason


def test_unknown_side_rejected_at_side_step():
    req = _ok_request(side="Hold")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "side"
    assert "side 'Hold' not allowed" in result.rejection_reason


def test_custom_order_link_id_missing_prefix_rejected():
    req = _ok_request(order_link_id="ARBITRARY_ID_NO_PREFIX")
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is False
    assert result.rejection_step == "order_link_id_prefix"
    assert "must start with" in result.rejection_reason


def test_built_payload_remains_marked_not_sent():
    req = _ok_request()
    result = bj.integrate_demo_only_tiny_request(req)
    assert result.ok is True
    audit = dict(result.payload_audit or {})
    assert audit["_demo_only_audit_response_status"] == "DEMO_ONLY_TINY_BH_NOT_SENT"
    assert audit["_demo_only_bj_audit_response_status"] == "DEMO_ONLY_TINY_BJ_NOT_SENT"


def test_integration_request_is_frozen_dataclass():
    req = _ok_request()
    with pytest.raises(Exception):
        req.symbol = "BTCUSDT"  # type: ignore[misc]


def test_integration_result_is_frozen_dataclass():
    req = _ok_request()
    result = bj.integrate_demo_only_tiny_request(req)
    with pytest.raises(Exception):
        result.ok = False  # type: ignore[misc]


def test_guard_integration_error_inherits_bh_base():
    assert issubclass(bj.GuardIntegrationError, bh.DemoOnlyTinyExecutionAdapterError)


# ---------------------------------------------------------------------------
# run_integration_dry_run -- aggregate report
# ---------------------------------------------------------------------------


def test_run_integration_dry_run_all_cases_match_expectation():
    report = bj.run_integration_dry_run()
    assert report.all_match_expectation is True
    assert report.unexpected_outcomes == 0


def test_run_integration_dry_run_summary_counts_consistent():
    report = bj.run_integration_dry_run()
    assert report.total_cases == len(report.outcomes)
    assert (
        report.ok_cases + report.rejected_cases == report.total_cases
    )


def test_run_integration_dry_run_has_ok_and_rejected_cases():
    report = bj.run_integration_dry_run()
    assert report.ok_cases >= 2
    assert report.rejected_cases >= 14


def _outcome_by_id(report, case_id):
    for o in report.outcomes:
        if o.case_id == case_id:
            return o
    raise AssertionError(f"case_id {case_id!r} not in report")


def test_report_includes_bh_identity_snapshot():
    report = bj.run_integration_dry_run()
    assert report.bh_identity == bh.IDENTITY
    assert report.bh_allowed_environment == "bybit_demo"
    assert report.bh_allowed_symbol == "SOLUSDT"
    assert set(report.bh_protected_symbols) == {
        "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
    }


def test_report_protected_in_existing_positions_outcome():
    report = bj.run_integration_dry_run()
    o = _outcome_by_id(
        report, "bj_case_10_protected_in_existing_positions"
    )
    assert o.actual == "rejected"
    assert o.rejection_step == "existing_positions"


def test_report_qty_cap_fail_outcome():
    report = bj.run_integration_dry_run()
    o = _outcome_by_id(report, "bj_case_15_qty_cap_fail")
    assert o.actual == "rejected"
    assert o.rejection_step == "qty_cap"


def test_report_notional_cap_fail_outcome():
    report = bj.run_integration_dry_run()
    o = _outcome_by_id(report, "bj_case_16_notional_cap_fail")
    assert o.actual == "rejected"
    assert o.rejection_step == "notional_cap"


def test_report_live_websocket_endpoint_outcome():
    report = bj.run_integration_dry_run()
    o = _outcome_by_id(report, "bj_case_14_live_websocket_endpoint_rejected")
    assert o.actual == "rejected"
    assert o.rejection_step == "endpoint_target"
    assert "live denylist" in o.rejection_reason


def test_report_solusdt_happy_path_outcome_has_audit():
    report = bj.run_integration_dry_run()
    o = _outcome_by_id(
        report, "bj_case_01_solusdt_buy_with_demo_endpoint"
    )
    assert o.actual == "ok"
    assert o.payload_audit is not None
    assert o.payload_audit["_demo_only_bj_endpoint_target_validated"] is True


def test_run_integration_dry_run_does_not_mutate_default_cases():
    snapshot = tuple(c.case_id for c in bj.default_integration_cases())
    bj.run_integration_dry_run()
    after = tuple(c.case_id for c in bj.default_integration_cases())
    assert snapshot == after


# ---------------------------------------------------------------------------
# write_report -- JSON + Markdown, latest_* + timestamped
# ---------------------------------------------------------------------------


def test_write_report_creates_four_files(tmp_path):
    report = bj.run_integration_dry_run()
    paths = bj.write_report(report, output_dir=tmp_path)
    assert set(paths.keys()) == {
        "latest_json", "latest_md", "timestamped_json", "timestamped_md",
    }
    for path in paths.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_write_report_json_round_trip(tmp_path):
    report = bj.run_integration_dry_run()
    paths = bj.write_report(report, output_dir=tmp_path)
    data = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert data["task_id"] == "TASK-014BJ"
    assert data["upstream_task"] == "TASK-014BI"
    assert data["is_review_chain_suffix"] is False
    assert data["all_match_expectation"] is True
    assert data["bh_allowed_symbol"] == "SOLUSDT"
    assert "ENAUSDT" in data["bh_protected_symbols"]
    assert data["bj_audit_response_status_not_sent"] == "DEMO_ONLY_TINY_BJ_NOT_SENT"


def test_write_report_md_contents(tmp_path):
    report = bj.run_integration_dry_run()
    paths = bj.write_report(report, output_dir=tmp_path)
    md = paths["latest_md"].read_text(encoding="utf-8")
    assert "TASK-014BJ" in md
    assert "DEMO-ONLY-TINY-EXECUTION-ADAPTER-ENDPOINT-GUARD-INTEGRATION" in md
    assert "next_required_task" in md
    assert "final_pre_execution_checklist" in md
    assert "## Outcomes" in md
    assert "bj_case_01_solusdt_buy_with_demo_endpoint" in md
    assert "bj_case_03_btcusdt_rejected" in md


# ---------------------------------------------------------------------------
# Static-source safety invariants
# ---------------------------------------------------------------------------


def _read_src() -> str:
    return SRC_PATH.read_text(encoding="utf-8")


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


def _src_tokens():
    return list(tokenize.generate_tokens(io.StringIO(_read_src()).readline))


def test_bj_source_imports_no_network_library():
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
    assert leaked == [], (
        f"BJ module must not import network libs; leaked: {leaked}"
    )


def test_bj_source_does_not_import_bybit_executor():
    imports = _src_imports()
    for mod in imports:
        assert "src.executors.bybit" not in mod
        assert "BybitExecutor" not in mod


def test_bj_source_does_not_read_environment_secrets():
    tokens = _src_tokens()
    forbidden_names = {"getenv", "environ", "load_dotenv"}
    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string in forbidden_names:
            pytest.fail(
                f"BJ module must not reference env/secret reader "
                f"{tok.string!r}"
            )


def test_bj_source_does_not_define_or_call_send_method():
    src = _read_src()
    assert "def send" not in src
    assert ".send(" not in src
    assert "place_order" not in src
    assert "post_order" not in src
    assert "submit_order" not in src


def test_bj_source_does_not_import_main_or_risk():
    imports = _src_imports()
    for mod in imports:
        assert mod != "main"
        assert mod != "src.risk"
        assert not mod.startswith("src.risk.")


def test_bj_source_consumes_bh_module_directly():
    tree = ast.parse(_read_src())
    imported_modules: list[str] = []
    imported_from_names: list[tuple[str, list[str]]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for a in node.names:
                imported_modules.append(a.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported_from_names.append(
                    (node.module, [a.name for a in node.names])
                )
                imported_modules.append(node.module)
    consumes_bh = (
        "src.demo_only_tiny_execution_adapter" in imported_modules
        or any(
            module == "src" and "demo_only_tiny_execution_adapter" in names
            for module, names in imported_from_names
        )
    )
    assert consumes_bh, (
        "BJ module must consume BH directly; "
        f"got imports={imported_modules} from_names={imported_from_names}"
    )


def test_bj_source_marks_implementation_path_phase():
    src = _read_src()
    assert 'IMPLEMENTATION_PATH_PHASE = "endpoint_guard_integration"' in src
    assert "IS_REVIEW_CHAIN_SUFFIX = False" in src


def test_bj_source_marks_next_required_task_final_pre_execution_checklist():
    src = _read_src()
    assert "final_pre_execution_checklist" in src


# ---------------------------------------------------------------------------
# Cross-module untouchability
# ---------------------------------------------------------------------------


def test_bybit_executor_not_loaded_by_bj_import():
    assert "src.executors.bybit" not in sys.modules


def test_bh_markers_intact_after_bj_import():
    assert bh.IS_REVIEW_CHAIN_SUFFIX is False
    assert bh.TASK_ID == "TASK-014BH"


def test_bi_markers_intact_after_bj_import():
    assert bi.IS_REVIEW_CHAIN_SUFFIX is False
    assert bi.TASK_ID == "TASK-014BI"


def test_main_module_not_imported_by_bj_load():
    # Loading BJ must not pull in main.py.
    assert "main" not in sys.modules or sys.modules["main"].__file__ != str(
        ROOT / "main.py"
    )


def test_src_risk_not_imported_by_bj_load():
    assert "src.risk" not in sys.modules
