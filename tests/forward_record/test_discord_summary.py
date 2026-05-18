"""
tests/forward_record/test_discord_summary.py
TASK-008C: unit tests for send_forward_discord_summary helpers

Tests: fmt_date_display, validation_day_label, days_remaining_label,
       VALIDATION_DAY30, REVIEW_DATE, build_discord_message layout.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from scripts.send_forward_discord_summary import (  # noqa: E402
    CLOCK_START,
    REVIEW_DATE,
    TOTAL_DAYS,
    VALIDATION_DAY30,
    build_discord_message,
    days_remaining_label,
    fmt_date_display,
    validation_day_label,
)


# ---------------------------------------------------------------------------
# fmt_date_display
# ---------------------------------------------------------------------------

class TestFmtDateDisplay:
    def test_clock_start(self):
        assert fmt_date_display("20260518") == "2026/05/18（一）"

    def test_day_30(self):
        assert fmt_date_display("20260616") == "2026/06/16（二）"

    def test_review_date(self):
        assert fmt_date_display("20260617") == "2026/06/17（三）"

    def test_invalid_returns_input(self):
        assert fmt_date_display("bad") == "bad"

    def test_empty_returns_empty(self):
        assert fmt_date_display("") == ""


# ---------------------------------------------------------------------------
# validation_day_label
# ---------------------------------------------------------------------------

class TestValidationDayLabel:
    def test_day1_clock_start(self):
        assert validation_day_label(CLOCK_START) == f"第 1 / {TOTAL_DAYS} 天"

    def test_day2(self):
        assert validation_day_label("20260519") == f"第 2 / {TOTAL_DAYS} 天"

    def test_day30(self):
        assert validation_day_label(VALIDATION_DAY30) == f"第 {TOTAL_DAYS} / {TOTAL_DAYS} 天"

    def test_review_day_not_31(self):
        """20260617 must NOT show 第 31 / 30 天."""
        label = validation_day_label(REVIEW_DATE)
        assert label == "結算檢查日"
        assert "31" not in label

    def test_after_review_day(self):
        assert validation_day_label("20260618") == "驗證期後"

    def test_pre_clock(self):
        label = validation_day_label("20260517")
        assert "N/A" in label
        assert "clock start" in label

    def test_invalid(self):
        assert validation_day_label("bad") == "N/A"


# ---------------------------------------------------------------------------
# days_remaining_label
# ---------------------------------------------------------------------------

class TestDaysRemainingLabel:
    def test_day1_has_29_remaining(self):
        assert days_remaining_label(CLOCK_START) == "29"

    def test_day30_has_0_remaining(self):
        assert days_remaining_label(VALIDATION_DAY30) == "0"

    def test_review_day_is_0(self):
        assert days_remaining_label(REVIEW_DATE) == "0"

    def test_pre_clock_is_na(self):
        assert days_remaining_label("20260517") == "N/A"

    def test_invalid_is_na(self):
        assert days_remaining_label("bad") == "N/A"


# ---------------------------------------------------------------------------
# Derived constants
# ---------------------------------------------------------------------------

class TestDerivedConstants:
    def test_validation_day30(self):
        assert VALIDATION_DAY30 == "20260616"

    def test_review_date(self):
        assert REVIEW_DATE == "20260617"

    def test_clock_start(self):
        assert CLOCK_START == "20260518"


# ---------------------------------------------------------------------------
# build_discord_message layout
# ---------------------------------------------------------------------------

_SAMPLE_ROW = {
    "date":                   "20260518",
    "runner_status":          "REVIEW_READY",
    "data_source":            "cache_fallback",
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status":    "FORBIDDEN",
    "dry_run":                "True",
    "signal_count":           "50",
    "daily_pnl_pct":          "0.0",
    "cumulative_pnl_pct":     "0.0",
    "max_dd_pct":             "0.0",
    "FORBIDDEN_order_endpoint": "NOT_ATTEMPTED",
    "FORBIDDEN_bybit_write":    "NOT_ATTEMPTED",
}


class TestBuildDiscordMessage:
    def setup_method(self):
        self.msg = build_discord_message(_SAMPLE_ROW)

    def test_day1_label_present(self):
        assert "第 1 / 30 天" in self.msg

    def test_no_day_31_label(self):
        """第 31 / 30 天 must never appear for any valid validation day."""
        assert "31" not in self.msg or "第 31" not in self.msg

    def test_date_display_format(self):
        assert "2026/05/18" in self.msg

    def test_day30_date_shown(self):
        assert "2026/06/16" in self.msg

    def test_review_date_shown(self):
        assert "2026/06/17" in self.msg

    def test_safety_values_unchanged(self):
        assert "FORBIDDEN" in self.msg
        assert "NOT_ATTEMPTED" in self.msg
        assert "REVIEW_READY" in self.msg
        assert "True" in self.msg

    def test_no_live_orders_warning(self):
        assert "未送出任何真實訂單" in self.msg

    def test_no_webhook_url_in_message(self):
        assert "discord.com" not in self.msg.lower()
        assert "webhook" not in self.msg.lower()

    def test_review_date_row(self):
        """Message built for review date must show 結算檢查日."""
        review_row = dict(_SAMPLE_ROW)
        review_row["date"] = REVIEW_DATE
        msg = build_discord_message(review_row)
        assert "結算檢查日" in msg
        assert "31" not in msg or "/ 30" not in msg
