"""
tests/forward_record/test_notion_sync.py
TASK-009: tests for sync_forward_validation_to_notion.py

Covers:
  - Dry-run never calls the network
  - Missing env vars -> NOTION_SYNC=SKIP exit 0
  - Empty/missing CSV -> NOTION_SYNC=SKIP exit 0
  - Safety self-check rejects forbidden imports
  - Payload mapping: numbers, checkboxes, dates, selects, rich text
  - validation_day_label / days_remaining helpers
  - find_existing_page filter shape (title vs date schema)
  - Missing required Notion properties -> reported by name
"""
from __future__ import annotations

import os
import subprocess
import sys
from pathlib import Path

from unittest import mock
import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Import the module under test
from scripts import sync_forward_validation_to_notion as sync  # noqa: E402


SCRIPT = ROOT / "scripts" / "sync_forward_validation_to_notion.py"
PYTHON = sys.executable


# ---------------------------------------------------------------------------
# Date helpers
# ---------------------------------------------------------------------------

class TestValidationDayLabel:
    def test_clock_start_is_day1(self):
        assert sync.validation_day_label(sync.CLOCK_START) == f"Day 1 / {sync.TOTAL_DAYS}"

    def test_day30(self):
        assert sync.validation_day_label(sync.VALIDATION_DAY30) == f"Day {sync.TOTAL_DAYS} / {sync.TOTAL_DAYS}"

    def test_review_day(self):
        assert sync.validation_day_label(sync.REVIEW_DATE) == "Review Day"

    def test_after_review(self):
        assert sync.validation_day_label("20260618") == "Post-Validation"

    def test_pre_clock(self):
        assert sync.validation_day_label("20260517") == "N/A (pre-clock)"

    def test_invalid(self):
        assert sync.validation_day_label("bad") == "N/A"


class TestDaysRemaining:
    def test_day1_29(self):
        assert sync.days_remaining(sync.CLOCK_START) == 29

    def test_day30_0(self):
        assert sync.days_remaining(sync.VALIDATION_DAY30) == 0

    def test_review_day_0(self):
        assert sync.days_remaining(sync.REVIEW_DATE) == 0

    def test_pre_clock_none(self):
        assert sync.days_remaining("20260517") is None

    def test_invalid_none(self):
        assert sync.days_remaining("bad") is None


# ---------------------------------------------------------------------------
# Record building & payload mapping
# ---------------------------------------------------------------------------

_SAMPLE_ROW = {
    "date":                   "20260518",
    "runner_status":          "REVIEW_READY",
    "data_source":            "cache_fallback",
    "safety_scan":            "PASS",
    "dry_run":                "True",
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status":    "FORBIDDEN",
    "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
    "FORBIDDEN_bybit_write":    "NOT_ATTEMPTED",
    "signal_count":           "50",
    "n_longs":                "25",
    "n_shorts":               "25",
    "daily_pnl_pct":          "0.0",
    "cumulative_pnl_pct":     "0.0",
    "max_dd_pct":             "0.0",
    "alerts_triggered":       "0",
    "review_006b_ready":      "False",
    "overlay_pass":           "True",
}


def _full_schema() -> dict[str, dict]:
    """English property names (original schema)."""
    return {
        "Date":                   {"type": "date"},
        "Validation Day":         {"type": "rich_text"},
        "Days Remaining":         {"type": "number"},
        "Runner Status":          {"type": "select"},
        "Data Source":            {"type": "rich_text"},
        "Safety Scan":            {"type": "select"},
        "Dry Run":                {"type": "checkbox"},
        "Paper Execution Status": {"type": "select"},
        "Live Trading Status":    {"type": "select"},
        "Signal Count":           {"type": "number"},
        "Daily PnL %":            {"type": "number"},
        "Cumulative PnL %":       {"type": "number"},
        "Max DD %":               {"type": "number"},
        "Alerts Triggered":       {"type": "number"},
        "Review Ready":           {"type": "checkbox"},
        "Notes":                  {"type": "rich_text"},
    }


def _full_schema_zh() -> dict[str, dict]:
    """All-Chinese property names (TASK-009B)."""
    return {
        "日期":         {"type": "date"},
        "驗證日":       {"type": "rich_text"},
        "剩餘天數":     {"type": "number"},
        "執行狀態":     {"type": "select"},
        "資料來源":     {"type": "rich_text"},
        "安全掃描":     {"type": "select"},
        "模擬執行":     {"type": "checkbox"},
        "紙上執行狀態": {"type": "select"},
        "真實交易狀態": {"type": "select"},
        "訊號數":       {"type": "number"},
        "當日 PnL %":   {"type": "number"},
        "累計 PnL %":   {"type": "number"},
        "最大回撤 %":   {"type": "number"},
        "觸發警報數":   {"type": "number"},
        "可檢視":       {"type": "checkbox"},
        "備註":         {"type": "rich_text"},
    }


def _full_schema_mixed() -> dict[str, dict]:
    """Half-English, half-Chinese property names (TASK-009B)."""
    return {
        "日期":                   {"type": "date"},       # Chinese
        "Validation Day":         {"type": "rich_text"},  # English
        "剩餘天數":               {"type": "number"},     # Chinese
        "Runner Status":          {"type": "select"},     # English
        "資料來源":               {"type": "rich_text"},  # Chinese
        "Safety Scan":            {"type": "select"},     # English
        "模擬執行":               {"type": "checkbox"},   # Chinese
        "Paper Execution Status": {"type": "select"},     # English
        "真實交易狀態":           {"type": "select"},     # Chinese
        "Signal Count":           {"type": "number"},     # English
        "當日 PnL %":             {"type": "number"},     # Chinese
        "Cumulative PnL %":       {"type": "number"},     # English
        "最大回撤 %":             {"type": "number"},     # Chinese
        "Alerts Triggered":       {"type": "number"},     # English
        "可檢視":                 {"type": "checkbox"},   # Chinese
        "Notes":                  {"type": "rich_text"},  # English
    }


class TestBuildRecord:
    def test_basic_fields(self):
        rec = sync.build_record(_SAMPLE_ROW)
        assert rec["date_yyyymmdd"] == "20260518"
        assert rec["date_iso"] == "2026-05-18"
        assert rec["runner_status"] == "REVIEW_READY"
        assert rec["safety_scan"] == "PASS"

    def test_dry_run_bool(self):
        rec = sync.build_record(_SAMPLE_ROW)
        assert rec["dry_run"] is True

    def test_numbers_parsed(self):
        rec = sync.build_record(_SAMPLE_ROW)
        assert rec["signal_count"] == 50.0
        assert rec["daily_pnl_pct"] == 0.0
        assert rec["max_dd_pct"] == 0.0
        assert rec["alerts_triggered"] == 0.0

    def test_validation_day_in_record(self):
        rec = sync.build_record(_SAMPLE_ROW)
        assert rec["validation_day"] == f"Day 1 / {sync.TOTAL_DAYS}"
        assert rec["days_remaining"] == 29

    def test_notes_has_safety_tokens(self):
        rec = sync.build_record(_SAMPLE_ROW)
        assert "NOT_ATTEMPTED" in rec["notes"]
        assert "prev3y_crypto" in rec["notes"]

    def test_review_ready_false(self):
        rec = sync.build_record(_SAMPLE_ROW)
        assert rec["review_ready"] is False


class TestBuildPropertyPayload:
    def test_all_required_keys_present_english(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema())
        # English schema -> all keys are canonical English names
        for name in sync.EXPECTED_PROPERTIES:
            assert name in props, f"missing prop: {name}"

    def test_date_iso_format(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema())
        assert props["Date"]["date"]["start"] == "2026-05-18"

    def test_number_fields(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema())
        assert props["Signal Count"]["number"] == 50.0
        assert props["Days Remaining"]["number"] == 29
        assert props["Max DD %"]["number"] == 0.0

    def test_checkbox_fields(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema())
        assert props["Dry Run"]["checkbox"] is True
        assert props["Review Ready"]["checkbox"] is False

    def test_select_fields(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema())
        assert props["Runner Status"]["select"]["name"] == "REVIEW_READY"
        assert props["Paper Execution Status"]["select"]["name"] == "FORBIDDEN"
        assert props["Live Trading Status"]["select"]["name"] == "FORBIDDEN"

    def test_rich_text_fields(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema())
        assert "Day 1" in props["Validation Day"]["rich_text"][0]["text"]["content"]
        assert "cache_fallback" in props["Data Source"]["rich_text"][0]["text"]["content"]
        assert "NOT_ATTEMPTED" in props["Notes"]["rich_text"][0]["text"]["content"]

    def test_date_property_as_title(self):
        schema = _full_schema()
        schema["Date"] = {"type": "title"}
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, schema)
        # When Date is title, value is YYYYMMDD string
        assert props["Date"]["title"][0]["text"]["content"] == "20260518"


class TestCheckRequiredProperties:
    def test_full_schema_no_missing(self):
        missing = sync.check_required_properties(_full_schema())
        assert missing == []

    def test_partial_schema_reports_missing(self):
        schema = _full_schema()
        del schema["Notes"]
        del schema["Validation Day"]
        missing = sync.check_required_properties(schema)
        # Each entry is "'canonical' (accepted: En | Zh)"
        assert any("Notes" in m for m in missing)
        assert any("Validation Day" in m for m in missing)

    def test_missing_entry_shows_both_aliases(self):
        schema = _full_schema()
        del schema["Notes"]
        missing = sync.check_required_properties(schema)
        assert len(missing) == 1
        assert "Notes" in missing[0]
        assert "備註" in missing[0]          # Chinese alias must appear
        assert "accepted:" in missing[0]

    def test_empty_schema_lists_all(self):
        missing = sync.check_required_properties({})
        assert len(missing) == len(sync.EXPECTED_PROPERTIES)
        for canonical in sync.EXPECTED_PROPERTIES:
            assert any(canonical in m for m in missing)


# ---------------------------------------------------------------------------
# Subprocess-level behaviour (no network)
# ---------------------------------------------------------------------------

class TestSubprocessBehaviour:
    def _run(self, args, env_extra=None):
        env = dict(os.environ)
        # Always strip any inherited secrets / db id
        env.pop("NOTION_TOKEN", None)
        env.pop("NOTION_FORWARD_VALIDATION_DATABASE_ID", None)
        if env_extra:
            env.update(env_extra)
        return subprocess.run(
            [PYTHON, str(SCRIPT), *args],
            capture_output=True,
            text=True,
            env=env,
            cwd=str(ROOT),
        )

    def test_dry_run_no_env_exit_0(self):
        result = self._run(["--dry-run"])
        assert result.returncode == 0
        assert "NOTION_SYNC=DRY_RUN" in result.stdout

    def test_dry_run_prints_payload_preview(self):
        result = self._run(["--dry-run"])
        assert result.returncode == 0
        assert "ROW" in result.stdout  # preview section header (TASK-013: was "PAYLOAD PREVIEW")
        assert "Runner Status" in result.stdout

    def test_dry_run_safety_self_check_pass(self):
        result = self._run(["--dry-run"])
        assert "safety_self_check: PASS" in result.stdout

    def test_dry_run_no_secret_leak(self):
        # Set a fake token; dry-run must NOT call network and must not echo token
        result = self._run(
            ["--dry-run"],
            env_extra={
                                "NOTION_TOKEN": "secret_FAKE_TOKEN_DO_NOT_LEAK",
                "NOTION_FORWARD_VALIDATION_DATABASE_ID": "fake_db_id",
            },
        )
        assert result.returncode == 0
        assert "secret_FAKE_TOKEN_DO_NOT_LEAK" not in result.stdout
        assert "secret_FAKE_TOKEN_DO_NOT_LEAK" not in result.stderr

    def test_live_missing_token_skip(self):
        result = self._run(
            [],
            env_extra={"NOTION_FORWARD_VALIDATION_DATABASE_ID": "fake_db_id"},
        )
        assert result.returncode == 0
        assert "NOTION_SYNC=SKIP" in result.stdout

    def test_live_missing_db_id_skip(self):
        result = self._run(
            [],
            env_extra={"NOTION_TOKEN": "secret_FAKE_TOKEN"},
        )
        assert result.returncode == 0
        assert "NOTION_SYNC=SKIP" in result.stdout

    def test_live_missing_both_skip(self):
        result = self._run([])
        assert result.returncode == 0
        assert "NOTION_SYNC=SKIP" in result.stdout


# ---------------------------------------------------------------------------
# Safety self-check
# ---------------------------------------------------------------------------

class TestSafetyTokens:
    def test_no_forbidden_imports_in_source(self):
        src = SCRIPT.read_text(encoding="utf-8")
        import re

        for token in sync._FORBIDDEN_TOKENS:
            pattern = r"^\s*(?:import|from)\s+.*" + re.escape(token)
            assert not re.search(
                pattern, src, re.MULTILINE | re.IGNORECASE
            ), f"forbidden import of {token!r} found"

    def test_safety_dict_invariants(self):
        assert sync.SAFETY["paper_execution_status"] == "FORBIDDEN"
        assert sync.SAFETY["live_trading_status"] == "FORBIDDEN"
        assert sync.SAFETY["order_endpoint_called"] is False
        assert sync.SAFETY["bybit_write_called"] is False


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

class TestUtilityHelpers:
    def test_to_number_handles_blank(self):
        assert sync._to_number("") is None
        assert sync._to_number("N/A") is None
        assert sync._to_number(None) is None

    def test_to_number_parses_float(self):
        assert sync._to_number("3.14") == 3.14
        assert sync._to_number("50") == 50.0

    def test_to_bool_truthy(self):
        assert sync._to_bool("True") is True
        assert sync._to_bool("true") is True
        assert sync._to_bool("1") is True

    def test_to_bool_falsy(self):
        assert sync._to_bool("False") is False
        assert sync._to_bool("0") is False

    def test_iso_date(self):
        assert sync._iso_date("20260518") == "2026-05-18"
        assert sync._iso_date("bad") is None


# ---------------------------------------------------------------------------
# TASK-009B: bilingual (Chinese / mixed) property support
# ---------------------------------------------------------------------------

class TestPropertyAliases:
    def test_all_canonical_names_covered(self):
        """Every EXPECTED_PROPERTIES entry must have an alias entry."""
        for name in sync.EXPECTED_PROPERTIES:
            assert name in sync.PROPERTY_ALIASES, f"no alias for {name!r}"

    def test_each_entry_has_two_aliases(self):
        for canonical, aliases in sync.PROPERTY_ALIASES.items():
            assert len(aliases) >= 2, f"{canonical!r} has fewer than 2 aliases"

    def test_first_alias_is_english(self):
        for canonical, aliases in sync.PROPERTY_ALIASES.items():
            assert aliases[0] == canonical, (
                f"first alias of {canonical!r} must be the canonical name"
            )


class TestResolveSchemaNames:
    def test_english_schema_resolves_to_english(self):
        resolved = sync.resolve_schema_names(_full_schema())
        assert resolved["Date"] == "Date"
        assert resolved["Validation Day"] == "Validation Day"
        assert resolved["Notes"] == "Notes"

    def test_chinese_schema_resolves_to_chinese(self):
        resolved = sync.resolve_schema_names(_full_schema_zh())
        assert resolved["Date"] == "日期"
        assert resolved["Validation Day"] == "驗證日"
        assert resolved["Notes"] == "備註"

    def test_mixed_schema_resolves_correctly(self):
        resolved = sync.resolve_schema_names(_full_schema_mixed())
        assert resolved["Date"] == "日期"
        assert resolved["Validation Day"] == "Validation Day"
        assert resolved["Notes"] == "Notes"

    def test_both_present_prefers_chinese(self):
        schema = _full_schema()
        schema["日期"] = {"type": "date"}
        resolved = sync.resolve_schema_names(schema)
        assert resolved["Date"] == "日期"

    def test_absent_canonical_maps_to_itself(self):
        resolved = sync.resolve_schema_names({})
        assert resolved["Date"] == "Date"


class TestCheckRequiredPropertiesBilingual:
    def test_chinese_schema_no_missing(self):
        missing = sync.check_required_properties(_full_schema_zh())
        assert missing == []

    def test_mixed_schema_no_missing(self):
        missing = sync.check_required_properties(_full_schema_mixed())
        assert missing == []

    def test_missing_chinese_prop_shows_both_aliases(self):
        schema = _full_schema_zh()
        del schema["備註"]
        missing = sync.check_required_properties(schema)
        assert len(missing) == 1
        assert "Notes" in missing[0]
        assert "備註" in missing[0]

    def test_empty_schema_reports_all(self):
        missing = sync.check_required_properties({})
        assert len(missing) == len(sync.EXPECTED_PROPERTIES)
        for canonical in sync.EXPECTED_PROPERTIES:
            assert any(canonical in m for m in missing)


class TestBuildPropertyPayloadBilingual:
    def test_chinese_schema_keys_are_chinese(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema_zh())
        assert "日期" in props
        assert "驗證日" in props
        assert "備註" in props
        assert "Date" not in props
        assert "Notes" not in props

    def test_chinese_schema_date_value(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema_zh())
        assert props["日期"]["date"]["start"] == "2026-05-18"

    def test_chinese_schema_numbers(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema_zh())
        assert props["訊號數"]["number"] == 50.0
        assert props["剩餘天數"]["number"] == 29

    def test_chinese_schema_checkboxes(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema_zh())
        assert props["模擬執行"]["checkbox"] is True
        assert props["可檢視"]["checkbox"] is False

    def test_chinese_schema_selects(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema_zh())
        assert props["執行狀態"]["select"]["name"] == "REVIEW_READY"
        assert props["紙上執行狀態"]["select"]["name"] == "FORBIDDEN"
        assert props["真實交易狀態"]["select"]["name"] == "FORBIDDEN"

    def test_mixed_schema_uses_resolved_keys(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema_mixed())
        assert "日期" in props
        assert "Validation Day" in props
        assert "Date" not in props

    def test_all_required_keys_present_chinese(self):
        rec = sync.build_record(_SAMPLE_ROW)
        props = sync.build_property_payload(rec, _full_schema_zh())
        zh_values = set(sync.PROPERTY_ALIASES[c][1] for c in sync.EXPECTED_PROPERTIES)
        for zh in zh_values:
            assert zh in props, f"missing Chinese prop: {zh}"


class TestFindExistingPageFilter:
    """Verify that find_existing_page uses the resolved (possibly Chinese) property name."""

    def _run(self, schema, expected_prop_name, ptype="date"):
        captured = {}

        def fake_request(method, path, token, body=None, timeout=15):
            captured["body"] = body
            return {"results": []}

        original = sync._notion_request
        sync._notion_request = fake_request
        try:
            rec = sync.build_record(_SAMPLE_ROW)
            sync.find_existing_page("tok", "db", rec, schema)
        finally:
            sync._notion_request = original
        return captured.get("body", {})

    def test_english_date_filter_uses_english_name(self):
        schema = _full_schema()
        body = self._run(schema, "Date")
        assert body["filter"]["property"] == "Date"

    def test_chinese_date_filter_uses_chinese_name(self):
        schema = _full_schema_zh()
        body = self._run(schema, "日期")
        assert body["filter"]["property"] == "日期"

    def test_mixed_date_filter_uses_chinese_name(self):
        schema = _full_schema_mixed()
        body = self._run(schema, "日期")
        assert body["filter"]["property"] == "日期"


# ===========================================================================
# TASK-013: Historical backfill tests
# ===========================================================================

def _make_csv(tmp_path, rows: list[dict]) -> Path:
    """Write a minimal validation_30d.csv to tmp_path."""
    import csv as _csv
    fields = ["date", "runner_status", "data_source", "safety_scan", "dry_run",
              "paper_execution_status", "live_trading_status", "signal_count",
              "daily_pnl_pct", "cumulative_pnl_pct", "max_dd_pct",
              "FORBIDDEN_order_endpoint", "FORBIDDEN_bybit_write",
              "alerts_triggered", "review_006b_ready", "n_longs", "n_shorts",
              "overlay_pass"]
    p = tmp_path / "validation_30d.csv"
    with open(p, "w", newline="", encoding="utf-8") as f:
        w = _csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        w.writeheader()
        for row in rows:
            w.writerow({**{k: "" for k in fields}, **row})
    return p


_ROWS_3 = [
    {"date": "20260520", "runner_status": "REVIEW_READY", "daily_pnl_pct": "1.23",
     "paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"},
    {"date": "20260519", "runner_status": "REVIEW_READY", "daily_pnl_pct": "0.50",
     "paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"},
    {"date": "20260518", "runner_status": "REVIEW_READY", "daily_pnl_pct": "0.00",
     "paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN"},
]


class TestLoadHelpers:
    """Test load_all_rows() and load_row_by_date() (TASK-013)."""

    def test_load_all_rows_returns_all(self, tmp_path):
        csv_p = _make_csv(tmp_path, _ROWS_3)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            rows = sync.load_all_rows()
        assert len(rows) == 3

    def test_load_all_rows_empty_csv(self, tmp_path):
        csv_p = _make_csv(tmp_path, [])
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            rows = sync.load_all_rows()
        assert rows == []

    def test_load_all_rows_missing_file(self, tmp_path):
        with mock.patch.object(sync, "CSV_PATH", tmp_path / "no_such.csv"):
            rows = sync.load_all_rows()
        assert rows == []

    def test_load_row_by_date_found(self, tmp_path):
        csv_p = _make_csv(tmp_path, _ROWS_3)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            row = sync.load_row_by_date("20260519")
        assert row is not None
        assert row["date"] == "20260519"
        assert row["daily_pnl_pct"] == "0.50"

    def test_load_row_by_date_not_found(self, tmp_path):
        csv_p = _make_csv(tmp_path, _ROWS_3)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            row = sync.load_row_by_date("20260528")
        assert row is None

    def test_load_row_by_date_missing_file(self, tmp_path):
        with mock.patch.object(sync, "CSV_PATH", tmp_path / "no_such.csv"):
            row = sync.load_row_by_date("20260518")
        assert row is None


class TestParseCli:
    """Test _parse_cli() argument parsing (TASK-013)."""

    def _run(self, argv):
        with mock.patch("sys.argv", ["script.py"] + argv):
            return sync._parse_cli()

    def test_no_args_defaults(self):
        dry_run, sync_all, date_arg = self._run([])
        assert dry_run is False
        assert sync_all is False
        assert date_arg is None

    def test_dry_run_flag(self):
        dry_run, _, _ = self._run(["--dry-run"])
        assert dry_run is True

    def test_all_flag(self):
        _, sync_all, _ = self._run(["--all"])
        assert sync_all is True

    def test_date_space_form(self):
        _, _, date_arg = self._run(["--date", "20260528"])
        assert date_arg == "20260528"

    def test_date_equals_form(self):
        _, _, date_arg = self._run(["--date=20260528"])
        assert date_arg == "20260528"

    def test_date_plus_dry_run(self):
        dry_run, _, date_arg = self._run(["--date", "20260528", "--dry-run"])
        assert dry_run is True
        assert date_arg == "20260528"

    def test_all_plus_dry_run(self):
        dry_run, sync_all, _ = self._run(["--all", "--dry-run"])
        assert dry_run is True
        assert sync_all is True


class TestSelectRows:
    """Test _select_rows() row selection logic (TASK-013)."""

    def _patch(self, tmp_path):
        return _make_csv(tmp_path, _ROWS_3)

    def test_default_returns_latest_row(self, tmp_path):
        csv_p = self._patch(tmp_path)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            rows, mode = sync._select_rows(sync_all=False, date_arg=None)
        assert len(rows) == 1
        assert rows[0]["date"] == "20260520"   # first row in CSV = newest
        assert mode == "latest"

    def test_all_returns_all_rows(self, tmp_path):
        csv_p = self._patch(tmp_path)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            rows, mode = sync._select_rows(sync_all=True, date_arg=None)
        assert len(rows) == 3
        assert mode == "all"

    def test_date_returns_specific_row(self, tmp_path):
        csv_p = self._patch(tmp_path)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            rows, mode = sync._select_rows(sync_all=False, date_arg="20260519")
        assert len(rows) == 1
        assert rows[0]["date"] == "20260519"
        assert "20260519" in mode

    def test_date_not_found_returns_empty(self, tmp_path):
        csv_p = self._patch(tmp_path)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            rows, mode = sync._select_rows(sync_all=False, date_arg="20260599")
        assert rows == []
        assert "20260599" in mode

    def test_date_takes_priority_over_all(self, tmp_path):
        """When both --date and --all given, --date wins (checked via _parse_cli priority)."""
        csv_p = self._patch(tmp_path)
        with mock.patch.object(sync, "CSV_PATH", csv_p):
            rows, mode = sync._select_rows(sync_all=True, date_arg="20260518")
        assert len(rows) == 1
        assert rows[0]["date"] == "20260518"


class TestMainBehaviourTask013:
    """Integration-level tests for main() with new CLI args (TASK-013)."""

    # Full synthetic schema (all 16 required English properties)
    _FULL_SCHEMA = {k: {"type": v} for k, v in {
        "Date": "date", "Validation Day": "rich_text", "Days Remaining": "number",
        "Runner Status": "select", "Data Source": "rich_text", "Safety Scan": "select",
        "Dry Run": "checkbox", "Paper Execution Status": "select",
        "Live Trading Status": "select", "Signal Count": "number",
        "Daily PnL %": "number", "Cumulative PnL %": "number",
        "Max DD %": "number", "Alerts Triggered": "number",
        "Review Ready": "checkbox", "Notes": "rich_text",
    }.items()}

    def _run_main(self, argv, tmp_path, rows=None):
        csv_p = _make_csv(tmp_path, rows or _ROWS_3)
        captured = []

        def fake_upsert(token, db_id, record, schema):
            captured.append(record["date_yyyymmdd"])
            return ("updated", "page-id-123")

        with (mock.patch("sys.argv", ["script.py"] + argv),
              mock.patch.object(sync, "CSV_PATH", csv_p),
              mock.patch.object(sync, "fetch_database_schema",
                                return_value=self._FULL_SCHEMA),
              mock.patch.object(sync, "upsert_page", side_effect=fake_upsert),
              mock.patch.dict("os.environ", {
                  sync.NOTION_TOKEN_ENV: "secret_test_token_xxx",
                  sync.NOTION_DB_ID_ENV: "db-test-id",
              })):
            rc = sync.main()
        return rc, captured

    def test_default_syncs_only_latest(self, tmp_path):
        rc, upserted = self._run_main([], tmp_path)
        assert rc == 0
        assert len(upserted) == 1
        assert upserted[0] == "20260520"  # first CSV row = latest

    def test_all_syncs_all_rows(self, tmp_path):
        rc, upserted = self._run_main(["--all"], tmp_path)
        assert rc == 0
        assert len(upserted) == 3

    def test_date_syncs_only_that_date(self, tmp_path):
        rc, upserted = self._run_main(["--date", "20260519"], tmp_path)
        assert rc == 0
        assert upserted == ["20260519"]

    def test_date_not_in_csv_returns_skip(self, tmp_path, capsys):
        csv_p = _make_csv(tmp_path, _ROWS_3)
        with (mock.patch("sys.argv", ["script.py", "--date", "20260599"]),
              mock.patch.object(sync, "CSV_PATH", csv_p)):
            rc = sync.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert "NOTION_SYNC=SKIP" in out

    def test_dry_run_does_not_call_upsert(self, tmp_path):
        csv_p = _make_csv(tmp_path, _ROWS_3)
        called = []
        with (mock.patch("sys.argv", ["script.py", "--dry-run"]),
              mock.patch.object(sync, "CSV_PATH", csv_p),
              mock.patch.object(sync, "upsert_page", side_effect=lambda *a, **k: called.append(1))):
            sync.main()
        assert called == [], "dry_run must not call upsert_page"

    def test_all_dry_run_previews_all_rows(self, tmp_path, capsys):
        csv_p = _make_csv(tmp_path, _ROWS_3)
        with (mock.patch("sys.argv", ["script.py", "--all", "--dry-run"]),
              mock.patch.object(sync, "CSV_PATH", csv_p)):
            rc = sync.main()
        out = capsys.readouterr().out
        assert rc == 0
        assert "NOTION_SYNC=DRY_RUN" in out
        assert "selected_rows=3" in out

    def test_no_token_leak_in_output(self, tmp_path, capsys):
        csv_p = _make_csv(tmp_path, _ROWS_3)
        secret = "secret_very_secret_token_xyz"
        with (mock.patch("sys.argv", ["script.py", "--dry-run"]),
              mock.patch.object(sync, "CSV_PATH", csv_p),
              mock.patch.dict("os.environ", {sync.NOTION_TOKEN_ENV: secret})):
            sync.main()
        out = capsys.readouterr().out
        assert secret not in out, "NOTION_TOKEN must not appear in stdout"

    def test_output_shows_selected_processed_counts(self, tmp_path, capsys):
        rc, _ = self._run_main(["--all"], tmp_path)
        out = capsys.readouterr().out
        assert "selected_rows=3" in out
        assert "processed_rows=3" in out
        assert "created_count=" in out
        assert "updated_count=" in out

    def test_chinese_alias_schema_still_accepted(self, tmp_path):
        """TASK-009B Chinese alias support must survive TASK-013 refactor."""
        schema_zh = {
            "日期": {"type": "date"}, "驗證日": {"type": "rich_text"},
            "剩餘天數": {"type": "number"}, "執行狀態": {"type": "select"},
            "資料來源": {"type": "rich_text"}, "安全掃描": {"type": "select"},
            "模擬執行": {"type": "checkbox"}, "紙上執行狀態": {"type": "select"},
            "真實交易狀態": {"type": "select"}, "訊號數": {"type": "number"},
            "當日 PnL %": {"type": "number"}, "累計 PnL %": {"type": "number"},
            "最大回撤 %": {"type": "number"}, "觸發警報數": {"type": "number"},
            "可檢視": {"type": "checkbox"}, "備註": {"type": "rich_text"},
        }
        resolved = sync.resolve_schema_names(schema_zh)
        assert resolved["Date"]            == "日期"
        assert resolved["Validation Day"]  == "驗證日"
        assert resolved["Days Remaining"]  == "剩餘天數"
