"""
send_forward_discord_summary.py
TASK-008 / TASK-008B / TASK-008C: Daily Discord Forward Validation Summary

Reads outputs/forward_record/dashboard/validation_30d.csv (newest row = today)
and sends a beautified Traditional Chinese summary to Discord.

Usage:
  python3 scripts/send_forward_discord_summary.py            # live send
  python3 scripts/send_forward_discord_summary.py --dry-run  # preview only

Environment:
  MONITOR_DISCORD_WEBHOOK_URL   Discord webhook URL (required for live send)

Exit / stdout tokens:
  DISCORD_NOTIFY=SKIP     env var not configured -> exits 0
  DISCORD_NOTIFY=DRY_RUN  --dry-run -> previews message, exits 0
  DISCORD_NOTIFY=PASS     message delivered -> exits 0
  DISCORD_NOTIFY=FAIL     send failed -> prints error, exits 1

SAFETY INVARIANTS:
  - NO order endpoint imports
  - NO bybit write API calls
  - NO live trading
  - Webhook URL from environment only (never hardcoded)
  - --dry-run: external_post_attempted = False
  - main.py live logic: NOT modified, NOT called
"""
from __future__ import annotations

import csv
import os
import re
import sys
from datetime import datetime, timedelta, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root on sys.path
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.monitor.channels.base import DefaultHttpClient       # noqa: E402
from apps.monitor.channels.redaction import redact_text        # noqa: E402

# ---------------------------------------------------------------------------
# Safety constants -- never modified
# ---------------------------------------------------------------------------
SAFETY = {
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status":    "FORBIDDEN",
    "order_endpoint_called":  False,
    "bybit_write_called":     False,
    "external_post_attempted": False,
}

# ---------------------------------------------------------------------------
# Clock constants
# ---------------------------------------------------------------------------
CLOCK_START = "20260518"   # Day 1, authorised by Rick 2026-05-18
TOTAL_DAYS  = 30
WEBHOOK_ENV = "MONITOR_DISCORD_WEBHOOK_URL"

# Derived: Day 30 = CLOCK_START + 29 days; Review day = CLOCK_START + 30 days
_D_START         = datetime.strptime(CLOCK_START, "%Y%m%d")
VALIDATION_DAY30 = (_D_START + timedelta(days=TOTAL_DAYS - 1)).strftime("%Y%m%d")
REVIEW_DATE      = (_D_START + timedelta(days=TOTAL_DAYS)).strftime("%Y%m%d")
CSV_PATH         = ROOT / "outputs" / "forward_record" / "dashboard" / "validation_30d.csv"

# ---------------------------------------------------------------------------
# Safety self-check
# ---------------------------------------------------------------------------
_FORBIDDEN_TOKENS = [
    "bybit", "place_order", "submit_order", "create_order",
    "cancel_order", "private_post", "private_put",
    "live_trading", "paper_trading", "set_leverage",
]


def safety_self_check() -> None:
    """Abort (exit 99) if this file imports any forbidden module."""
    src = Path(__file__).read_text(encoding="utf-8")
    violations: list[str] = []
    for token in _FORBIDDEN_TOKENS:
        for m in re.finditer(
            r"^\s*(?:import|from)\s+.*" + re.escape(token),
            src, re.MULTILINE | re.IGNORECASE
        ):
            violations.append(m.group().strip())
    if violations:
        print(f"SAFETY VIOLATION -- forbidden import: {violations}", file=sys.stderr)
        sys.exit(99)
    print("  safety_self_check: PASS")


# ---------------------------------------------------------------------------
# Data loading
# ---------------------------------------------------------------------------

def load_latest_row() -> dict[str, str] | None:
    if not CSV_PATH.exists():
        return None
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return dict(row)
    return None


def _na(value: str, fmt: str = "") -> str:
    if not value or value in ("", "None"):
        return "N/A"
    if fmt:
        try:
            return fmt % float(value)
        except (ValueError, TypeError):
            pass
    return value


def _fmt_pct(v: str) -> str:
    return _na(v, "%.4f%%")


# ---------------------------------------------------------------------------
# Date display helpers (TASK-008C)
# ---------------------------------------------------------------------------

_WEEKDAYS_ZH = ["一", "二", "三", "四", "五", "六", "日"]


def fmt_date_display(yyyymmdd: str) -> str:
    """
    Format YYYYMMDD for human-readable Discord display.
    20260518 -> "2026/05/18（一）"
    Returns the input unchanged if parsing fails.
    """
    try:
        d = datetime.strptime(yyyymmdd, "%Y%m%d")
        wd = _WEEKDAYS_ZH[d.weekday()]
        return f"{d.year}/{d.month:02d}/{d.day:02d}\uff08{wd}\uff09"
    except (ValueError, TypeError):
        return yyyymmdd


def validation_day_label(date: str) -> str:
    """
    Return human-friendly validation-day label for a YYYYMMDD date.
      CLOCK_START          -> "第 1 / 30 天"
      CLOCK_START + 29d    -> "第 30 / 30 天"
      CLOCK_START + 30d    -> "結算檢查日"
      after review day     -> "驗證期後"
      before CLOCK_START   -> "N/A（clock start 前）"
    """
    try:
        d_run   = datetime.strptime(date,        "%Y%m%d")
        d_start = datetime.strptime(CLOCK_START, "%Y%m%d")
        delta   = (d_run - d_start).days
    except (ValueError, TypeError):
        return "N/A"
    if delta < 0:
        return "N/A\uff08clock start \u524d\uff09"
    if delta < TOTAL_DAYS:
        return f"\u7b2c {delta + 1} / {TOTAL_DAYS} \u5929"
    if delta == TOTAL_DAYS:
        return "\u7d50\u7b97\u6aa2\u67e5\u65e5"
    return "\u9a57\u8b49\u671f\u5f8c"


def days_remaining_label(date: str) -> str:
    """
    Return remaining days string for a YYYYMMDD date.
      Before CLOCK_START   -> "N/A"
      Within 30-day window -> "29", "28", ..., "0"
      Review day or after  -> "0"
    """
    try:
        d_run   = datetime.strptime(date,        "%Y%m%d")
        d_start = datetime.strptime(CLOCK_START, "%Y%m%d")
        delta   = (d_run - d_start).days
    except (ValueError, TypeError):
        return "N/A"
    if delta < 0:
        return "N/A"
    return str(max(0, TOTAL_DAYS - (delta + 1)))


# ---------------------------------------------------------------------------
# Message formatting (TASK-008C: beautified, Traditional Chinese)
# ---------------------------------------------------------------------------

DIVIDER = "\u2500" * 36


def build_discord_message(row: dict[str, str]) -> str:
    now_utc      = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    date         = row.get("date", "N/A")
    status       = row.get("runner_status", "N/A")
    data_src     = row.get("data_source", "N/A")
    paper_status = row.get("paper_execution_status", "FORBIDDEN")
    live_status  = row.get("live_trading_status",    "FORBIDDEN")
    dry_run_val  = _na(row.get("dry_run", "True"))
    signals      = _na(row.get("signal_count", ""))
    daily_pnl    = _fmt_pct(row.get("daily_pnl_pct", ""))
    cum_pnl      = _fmt_pct(row.get("cumulative_pnl_pct", ""))
    max_dd       = _fmt_pct(row.get("max_dd_pct", ""))
    forbidden_ep = _na(row.get("FORBIDDEN_order_endpoint", "NOT_ATTEMPTED"))
    forbidden_bw = _na(row.get("FORBIDDEN_bybit_write",    "NOT_ATTEMPTED"))

    date_disp    = fmt_date_display(date)
    day_lbl      = validation_day_label(date)
    remaining    = days_remaining_label(date)
    day30_disp   = fmt_date_display(VALIDATION_DAY30)
    review_disp  = fmt_date_display(REVIEW_DATE)

    parts = [
        "\U0001f4ca **30 \u5929\u6b63\u5f0f\u9a57\u8b49\uff5c\u6bcf\u65e5\u6230\u5831**",
        DIVIDER,
        "**\U0001f5d3 \u65e5\u671f\u8207\u9032\u5ea6**",
        f"\U0001f5d3 \u65e5\u671f\uff1a{date_disp}",
        f"\U0001f4cd \u9032\u5ea6\uff1a{day_lbl}",
        f"\u23f3 \u5269\u9918\uff1a{remaining} \u5929",
        f"\U0001f3af \u7b2c 30 \u5929\uff1a{day30_disp}",
        f"\U0001f4cc \u7d50\u7b97\u6aa2\u67e5\u65e5\uff1a{review_disp}",
        DIVIDER,
        "**\U0001f4cb \u7b56\u7565\u8207\u72c0\u614b**",
        f"\U0001f4cc \u7b56\u7565\uff1a`prev3y_crypto / combined_paper_safe_variant`",
        f"\u2699\ufe0f \u57f7\u884c\u72c0\u614b\uff1a`{status}`",
        f"\U0001f4be \u8cc7\u6599\u4f86\u6e90\uff1a`{data_src}`",
        DIVIDER,
        "**\U0001f512 \u5b89\u5168\u9598\u9580**\uff08machine-readable \u539f\u59cb\u503c\uff09",
        f"  paper_execution_status\uff1a`{paper_status}`",
        f"  live_trading_status\uff1a`{live_status}`",
        f"  FORBIDDEN_order_endpoint\uff1a`{forbidden_ep}`",
        f"  FORBIDDEN_bybit_write\uff1a`{forbidden_bw}`",
        f"  dry_run\uff1a`{dry_run_val}`",
        DIVIDER,
        "**\U0001f4c8 \u7d19\u4e0a\u7e3e\u6548**\uff08dry-run / paper \u6a21\u64ec\uff0c\u975e\u771f\u5be6\u640d\u76ca\uff09",
        f"  \u4fe1\u865f\u6578\uff1a{signals}",
        f"  \u7576\u65e5 PnL\uff1a{daily_pnl}",
        f"  \u7d2f\u8a08 PnL\uff1a{cum_pnl}",
        f"  \u6700\u5927\u56de\u64a4\uff1a{max_dd}",
        DIVIDER,
        "\u26a0\ufe0f **\u672a\u9001\u51fa\u4efb\u4f55\u771f\u5be6\u8a02\u55ae\u3002\u9019\u53ea\u662f dry-run / paper record\u3002**",
        f"\U0001f552 \u7522\u751f\u6642\u9593\uff08UTC\uff09\uff1a{now_utc}",
    ]
    sep = "\n"
    return sep.join(parts)


# ---------------------------------------------------------------------------
# Discord send
# ---------------------------------------------------------------------------

def send_summary(message: str, webhook_url: str) -> tuple[bool, str]:
    """POST message to Discord. Returns (success, detail)."""
    client = DefaultHttpClient()
    payload = {"content": message}
    try:
        result = client.post_json(webhook_url, payload, timeout_seconds=15)
    except Exception as exc:
        return False, f"exception: {exc.__class__.__name__}: {exc}"
    if 200 <= result.status_code < 300:
        return True, f"HTTP {result.status_code}"
    return False, f"HTTP {result.status_code}: {result.text[:200]}"


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    dry_run = "--dry-run" in sys.argv
    print("send_forward_discord_summary.py")
    print(f"  dry_run={dry_run}")
    print()

    safety_self_check()

    row = load_latest_row()
    if row is None:
        print(f"  WARNING: {CSV_PATH} not found or empty")
        print("  DISCORD_NOTIFY=SKIP (no data)")
        return 0

    date = row.get("date", "")
    print(f"  latest row: date={date}")
    print(f"  day label:  {validation_day_label(date)}")

    message = build_discord_message(row)

    if dry_run:
        print()
        print("  === MESSAGE PREVIEW ===")
        for line in message.splitlines():
            print(f"  {line}")
        print("  === END PREVIEW ===")
        print()
        print("  DISCORD_NOTIFY=DRY_RUN (no POST attempted)")
        print()
        print("  safety gates:")
        for k, v in SAFETY.items():
            print(f"    {k} = {v}")
        return 0

    webhook_url = os.environ.get(WEBHOOK_ENV, "").strip()
    if not webhook_url:
        print(f"  {WEBHOOK_ENV} not set in environment")
        print("  DISCORD_NOTIFY=SKIP")
        return 0

    SAFETY["external_post_attempted"] = True
    redacted_url = redact_text(webhook_url)
    print(f"  sending to Discord ({redacted_url}) ...")
    success, detail = send_summary(message, webhook_url)

    if success:
        print(f"  DISCORD_NOTIFY=PASS ({detail})")
        print()
        print("  safety gates:")
        for k, v in SAFETY.items():
            print(f"    {k} = {v}")
        return 0

    safe_detail = redact_text(detail, [webhook_url])
    print(f"  DISCORD_NOTIFY=FAIL ({safe_detail})", file=sys.stderr)
    print(f"  DISCORD_NOTIFY=FAIL ({safe_detail})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
