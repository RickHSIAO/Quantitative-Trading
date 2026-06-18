"""TASK-014BI Stage 1 — focused-core tests for the demo-only tiny
execution adapter payload dry-run module.

These tests exercise the BI module (which itself consumes BH) and
verify every guard rejection / happy-path / static-source safety
invariant required by the BI workorder.
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

SRC_PATH = ROOT / "src" / "demo_only_tiny_execution_adapter_payload_dry_run.py"


# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------


def test_task_id_is_bi():
    assert bi.TASK_ID == "TASK-014BI"


def test_identity_is_payload_dry_run():
    assert bi.IDENTITY == "DEMO-ONLY-TINY-EXECUTION-ADAPTER-PAYLOAD-DRY-RUN"


def test_phase_is_offline_payload_dry_run():
    assert bi.IMPLEMENTATION_PATH_PHASE == "offline_payload_dry_run"


def test_is_not_review_chain_suffix():
    assert bi.IS_REVIEW_CHAIN_SUFFIX is False


def test_upstream_task_is_bh():
    assert bi.UPSTREAM_TASK == "TASK-014BH"


def test_next_required_task_does_not_end_in_review_chain_suffix():
    nxt = bi.NEXT_REQUIRED_TASK
    for suffix in (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    ):
        assert not nxt.endswith(suffix), nxt
    # BI's next step must be endpoint_guard_integration or final
    # pre-execution checklist — both implementation-path, not review.
    assert (
        "endpoint_guard_integration" in nxt
        or "final_pre_execution_checklist" in nxt
    ), nxt


def test_next_required_task_passes_bh_guard():
    bh.assert_next_task_is_not_review_chain_suffix(bi.NEXT_REQUIRED_TASK)


# ---------------------------------------------------------------------------
# Canonical case table
# ---------------------------------------------------------------------------


def test_default_cases_includes_required_coverage():
    cases = bi.default_cases()
    ids = {c.case_id for c in cases}
    # Each guard rejection path required by the BI workorder must have a
    # named case here.
    assert any("solusdt_buy" in i for i in ids)
    assert any("solusdt_sell" in i for i in ids)
    assert any("btcusdt" in i for i in ids)
    assert any("ethusdt" in i for i in ids)
    assert any("protected_enausdt" in i for i in ids)
    assert any("protected_tiausdt" in i for i in ids)
    assert any("protected_aixbtusdt" in i for i in ids)
    assert any("protected_polyxusdt" in i for i in ids)
    assert any("protected_eduusdt" in i for i in ids)
    assert any("qty_above_cap" in i for i in ids)
    assert any("notional_above_cap" in i for i in ids)


def test_default_cases_have_unique_ids():
    cases = bi.default_cases()
    ids = [c.case_id for c in cases]
    assert len(ids) == len(set(ids))


def test_live_endpoint_cases_cover_known_live_hosts():
    urls = {url for url, _label in bi.LIVE_ENDPOINT_CASES}
    assert any(u.startswith("https://api.bybit.com") for u in urls)
    assert any(u.startswith("https://api.bytick.com") for u in urls)
    assert any(u.startswith("wss://stream.bybit.com") for u in urls)


# ---------------------------------------------------------------------------
# run_dry_run — happy path
# ---------------------------------------------------------------------------


def test_run_dry_run_all_cases_match_expectation():
    report = bi.run_dry_run()
    assert report.all_match_expectation is True
    assert report.unexpected_outcomes == 0


def test_run_dry_run_summary_counts_consistent():
    report = bi.run_dry_run()
    assert report.total_cases == len(report.outcomes)
    assert (
        report.built_cases + report.rejected_cases
        == report.total_cases
    )


def test_run_dry_run_includes_live_endpoint_check_outcomes():
    report = bi.run_dry_run()
    live_ids = [
        o.case_id for o in report.outcomes
        if o.case_id.startswith("bi_live_endpoint_")
    ]
    assert len(live_ids) == len(bi.LIVE_ENDPOINT_CASES)
    # every live endpoint must have been rejected
    for o in report.outcomes:
        if o.case_id.startswith("bi_live_endpoint_"):
            assert o.actual == "rejected"
            assert o.matches_expectation is True


def test_run_dry_run_built_solusdt_payload_is_marked_not_sent():
    report = bi.run_dry_run()
    built = [o for o in report.outcomes if o.actual == "built"]
    assert built, "expected at least one built happy-path payload"
    for o in built:
        audit = o.payload_audit
        assert audit is not None
        assert audit["symbol"] == "SOLUSDT"
        assert audit["_demo_only_audit_response_status"] == "DEMO_ONLY_TINY_BH_NOT_SENT"
        assert audit["_demo_only_is_review_chain_suffix"] is False
        assert audit["_demo_only_implementation_path_task"] == "TASK-014BH"


# ---------------------------------------------------------------------------
# Individual guard cases
# ---------------------------------------------------------------------------


def _outcome_by_id(report, case_id):
    for o in report.outcomes:
        if o.case_id == case_id:
            return o
    raise AssertionError(f"case_id {case_id!r} not in report")


def test_btcusdt_case_rejected_with_only_solusdt_message():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_08_btcusdt_rejected")
    assert o.actual == "rejected"
    assert "only 'SOLUSDT'" in o.rejection_reason


def test_ethusdt_case_rejected_with_only_solusdt_message():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_09_ethusdt_rejected")
    assert o.actual == "rejected"
    assert "only 'SOLUSDT'" in o.rejection_reason


@pytest.mark.parametrize(
    "case_id,protected",
    [
        ("bi_case_10_protected_enausdt", "ENAUSDT"),
        ("bi_case_11_protected_tiausdt", "TIAUSDT"),
        ("bi_case_12_protected_aixbtusdt", "AIXBTUSDT"),
        ("bi_case_13_protected_polyxusdt", "POLYXUSDT"),
        ("bi_case_14_protected_eduusdt", "EDUUSDT"),
    ],
)
def test_each_protected_symbol_is_rejected(case_id, protected):
    report = bi.run_dry_run()
    o = _outcome_by_id(report, case_id)
    assert o.actual == "rejected"
    assert protected in o.rejection_reason
    assert "protected position" in o.rejection_reason


def test_protected_symbol_in_existing_positions_rejected():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_15_protected_in_existing")
    assert o.actual == "rejected"
    assert "ENAUSDT" in o.rejection_reason


def test_non_demo_environment_rejected():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_16_non_demo_environment")
    assert o.actual == "rejected"
    assert "bybit_live" in o.rejection_reason


def test_tiny_qty_cap_pass():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_03_solusdt_qty_cap_edge")
    assert o.actual == "built"
    assert o.payload_audit is not None
    assert o.payload_audit["qty"] == "0.05"


def test_tiny_qty_cap_fail():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_05_qty_above_cap")
    assert o.actual == "rejected"
    assert "tiny cap" in o.rejection_reason


def test_tiny_notional_cap_pass():
    # case_01 builds 0.01 SOL @ 100 = 1 USDT
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_01_solusdt_buy_tiny")
    assert o.actual == "built"


def test_tiny_notional_cap_fail():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_07_notional_above_cap")
    assert o.actual == "rejected"
    assert "exceeds tiny size cap" in o.rejection_reason


def test_valid_solusdt_buy_payload_dry_run():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_01_solusdt_buy_tiny")
    assert o.actual == "built"
    assert o.payload_audit is not None
    assert o.payload_audit["side"] == "Buy"


def test_valid_solusdt_sell_payload_dry_run():
    report = bi.run_dry_run()
    o = _outcome_by_id(report, "bi_case_02_solusdt_sell_tiny")
    assert o.actual == "built"
    assert o.payload_audit is not None
    assert o.payload_audit["side"] == "Sell"


def test_live_endpoint_rejected_for_each_live_url():
    report = bi.run_dry_run()
    for o in report.outcomes:
        if not o.case_id.startswith("bi_live_endpoint_"):
            continue
        assert o.actual == "rejected"
        assert "live denylist" in o.rejection_reason


# ---------------------------------------------------------------------------
# write_report — JSON + Markdown, latest_* + timestamped
# ---------------------------------------------------------------------------


def test_write_report_creates_four_files(tmp_path):
    report = bi.run_dry_run()
    paths = bi.write_report(report, output_dir=tmp_path)
    assert set(paths.keys()) == {
        "latest_json", "latest_md", "timestamped_json", "timestamped_md",
    }
    for path in paths.values():
        assert path.exists()
        assert path.stat().st_size > 0


def test_write_report_json_is_round_trippable(tmp_path):
    report = bi.run_dry_run()
    paths = bi.write_report(report, output_dir=tmp_path)
    data = json.loads(paths["latest_json"].read_text(encoding="utf-8"))
    assert data["task_id"] == "TASK-014BI"
    assert data["upstream_task"] == "TASK-014BH"
    assert data["is_review_chain_suffix"] is False
    assert data["all_match_expectation"] is True
    assert data["bh_allowed_symbol"] == "SOLUSDT"
    assert "ENAUSDT" in data["bh_protected_symbols"]


def test_write_report_md_contains_summary_and_outcomes(tmp_path):
    report = bi.run_dry_run()
    paths = bi.write_report(report, output_dir=tmp_path)
    md = paths["latest_md"].read_text(encoding="utf-8")
    assert "TASK-014BI" in md
    assert "DEMO-ONLY-TINY-EXECUTION-ADAPTER-PAYLOAD-DRY-RUN" in md
    assert "next_required_task" in md
    assert "endpoint_guard_integration" in md
    assert "## Outcomes" in md
    # at least one happy-path row and one rejection row
    assert "bi_case_01_solusdt_buy_tiny" in md
    assert "bi_case_08_btcusdt_rejected" in md


def test_write_report_md_does_not_mention_review_chain_suffix(tmp_path):
    report = bi.run_dry_run()
    paths = bi.write_report(report, output_dir=tmp_path)
    md = paths["latest_md"].read_text(encoding="utf-8")
    # The report explicitly states is_review_chain_suffix=False — that
    # line is the only place "review_chain_suffix" should appear, so
    # nothing should describe BI as a chain suffix.
    forbidden = (
        "_readiness_review",
        "_final_pre_execution_review",
        "_manual_authorization_review",
    )
    for f in forbidden:
        # These suffixes may legitimately appear inside the BG-archive
        # description in other docs, but BI's own report must not name
        # itself with them.
        assert f"BI{f}" not in md
        assert f"TASK-014BI{f}" not in md


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


def _src_tokens() -> list[tokenize.TokenInfo]:
    return list(tokenize.generate_tokens(io.StringIO(_read_src()).readline))


def test_bi_source_imports_no_network_library():
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
    assert leaked == [], f"BI module must not import network libs; leaked: {leaked}"


def test_bi_source_does_not_import_bybit_executor():
    imports = _src_imports()
    for mod in imports:
        assert "src.executors.bybit" not in mod
        assert "BybitExecutor" not in mod


def test_bi_source_does_not_read_environment_secrets():
    tokens = _src_tokens()
    forbidden_names = {"getenv", "environ", "load_dotenv"}
    for tok in tokens:
        if tok.type == tokenize.NAME and tok.string in forbidden_names:
            pytest.fail(
                f"BI module must not reference env/secret reader {tok.string!r}"
            )


def test_bi_source_does_not_define_or_call_send_method():
    src = _read_src()
    assert "def send" not in src
    assert ".send(" not in src
    assert "place_order" not in src
    assert "post_order" not in src
    assert "submit_order" not in src


def test_bi_source_does_not_import_main_or_risk():
    imports = _src_imports()
    for mod in imports:
        assert mod != "main"
        assert mod != "src.risk"
        assert not mod.startswith("src.risk.")


def test_bi_source_consumes_bh_module_directly():
    # Detect both `from src.demo_only_tiny_execution_adapter import ...`
    # and `from src import demo_only_tiny_execution_adapter as bh` shapes.
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
        "BI module must consume BH directly; "
        f"got imports={imported_modules} from_names={imported_from_names}"
    )


def test_bi_source_marks_implementation_path_phase():
    src = _read_src()
    assert 'IMPLEMENTATION_PATH_PHASE = "offline_payload_dry_run"' in src
    assert "IS_REVIEW_CHAIN_SUFFIX = False" in src


# ---------------------------------------------------------------------------
# Cross-module untouchability
# ---------------------------------------------------------------------------


def test_bybit_executor_not_loaded_by_bi_import():
    assert "src.executors.bybit" not in sys.modules


def test_bh_module_still_marks_no_review_chain_suffix():
    # BI imports BH; ensure BH's chain-break markers are still in place.
    assert bh.IS_REVIEW_CHAIN_SUFFIX is False
    assert bh.TASK_ID == "TASK-014BH"


def test_run_dry_run_does_not_mutate_default_cases():
    snapshot = tuple(c.case_id for c in bi.default_cases())
    bi.run_dry_run()
    after = tuple(c.case_id for c in bi.default_cases())
    assert snapshot == after
