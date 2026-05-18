"""
send_forward_discord_summary.py
TASK-008 / TASK-008B: Daily Discord Forward Validation Summary (繁體中文)

Reads outputs/forward_record/dashboard/validation_30d.csv (newest row = today)
and sends a Chinese-language summary to Discord via MONITOR_DISCORD_WEBHOOK_URL.

Usage:
  python3 scripts/send_forward_discord_summary.py            # live send
  python3 scripts/send_forward_discord_summary.py --dry-run  # preview only, no POST

Environment:
  MONITOR_DISCORD_WEBHOOK_URL   Discord webhook URL (required for live send)

Exit / stdout tokens:
  DISCORD_NOTIFY=SKIP     env var not configured -> exits 0
  DISCORD_NOTIFY=DRY_RUN  --dry-run -> previews message, exits 0
  DISCORD_NOTIFY=PASS     message delivered -> exits 0
  DISCORD_NOTIFY=FAIL     send failed -> prints error, exits 1

SAFETY INVARIANTS (enforced throughout):
  - NO order endpoint imports
  - NO bybit write API calls
  - NO live trading
  - Webhook URL sourced from environment only (never hardcoded)
  - --dry-run: external_post_attempted = False
  - main.py live logic: NOT modified, NOT called
"""
from __future__ import annotations

import csv
import os
import re
import sys
from datetime import datetime, timezone
from pathlib import Path

# ---------------------------------------------------------------------------
# Project root on sys.path (mirrors other scripts in this repo)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# Reuse existing safe HTTP client and redaction utilities
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
    "external_post_attempted": False,   # updated to True only on live send
}

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
DASHBOARD   = ROOT / "outputs" / "forward_record" / "dashboard"
CSV_PATH    = DASHBOARD / "validation_30d.csv"
CLOCK_START = "20260518"
TARGET_END  = "20260617"
TOTAL_DAYS  = 30

# Webhook env var -- consistent with existing monitor infrastructure
WEBHOOK_ENV = "MONITOR_DISCORD_WEBHOOK_URL"

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
    """Read validation_30d.csv and return the newest row (first data row)."""
    if not CSV_PATH.exists():
        return None
    with open(CSV_PATH, newline="", encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for row in reader:
            return dict(row)   # newest-first; return first data row
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
# Day count helper (TASK-008B)
# ---------------------------------------------------------------------------

def _human_day(date: str) -> str:
    """
    Convert YYYYMMDD to human-friendly day label.
    CLOCK_START (20260518) -> "第 1 / 30 天"
    CLOCK_START+1 day      -> "第 2 / 30 天"
    Before CLOCK_START     -> "N/A (clock start 前)"
    """
    try:
        d_run   = datetime.strptime(date,        "%Y%m%d").replace(tzinfo=timezone.utc)
        d_start = datetime.strptime(CLOCK_START, "%Y%m%d").replace(tzinfo=timezone.utc)
        delta = (d_run - d_start).days
        if delta < 0:
            return "N/A (clock start 前)"
        return f"第 {delta + 1} / {TOTAL_DAYS} 天"
    except (ValueError, TypeError):
        return "N/A"


def _days_remaining(date: str) -> str:
    """Remaining days in 30-day clock after the given date."""
    try:
        d_run   = datetime.strptime(date,        "%Y%m%d").replace(tzinfo=timezone.utc)
        d_start = datetime.strptime(CLOCK_START, "%Y%m%d").replace(tzinfo=timezone.utc)
        delta   = (d_run - d_start).days
        if delta < 0:
            return "N/A"
        return str(max(0, TOTAL_DAYS - (delta + 1)))
    except (ValueError, TypeError):
        return "N/A"


# ---------------------------------------------------------------------------
# Message formatting (繁體中文, TASK-008B)
# ---------------------------------------------------------------------------

DIVIDER = "─" * 36


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
    day_label    = _human_day(date)
    remaining    = _days_remaining(date)

    parts = [
        "📊 **30 天正式驗證 — 每日摘要**",
        f"策略：`prev3y_crypto / combined_paper_safe_variant`",
        DIVIDER,
        f"**日期：** {date}　｜　**進度：** {day_label}",
        f"**執行狀態：** `{status}`",
        f"**資料來源：** `{data_src}`",
        DIVIDER,
        "🔒 **安全闘門**（machine-readable 原始値）",
        f"  paper_execution_status：`{paper_status}`",
        f"  live_trading_status：`{live_status}`",
        f"  FORBIDDEN_order_endpoint：`{_na(row.get('FORBIDDEN_order_endpoint','NOT_ATTEMPTED'))}`",
        f"  FORBIDDEN_bybit_write：`{_na(row.get('FORBIDDEN_bybit_write','NOT_ATTEMPTED'))}`",
        f"  dry_run：`{dry_run_val}`",
        DIVIDER,
        "📈 **績效（dry-run / paper 模擬，非真實損益）**",
        f"  信號數：{signals}",
        f"  當日 PnL：{daily_pnl}",
        f"  累計 PnL：{cum_pnl}",
        f"  最大回撤：{max_dd}",
        DIVIDER,
        "📅 **驗證時鐘**",
        f"  開始日期：{CLOCK_START}　｜　目標結束：{TARGET_END}",
        f"  今日進度：{day_label}　｜　剩餘天數：{remaining} 天",
        DIVIDER,
        "⚠️ **未送出任何真實訂單。這只是 dry-run / paper record。**",
        f"產生時間（UTC）：{now_utc}",
    ]
    return "\n".join(parts)


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

    # Step 1: safety self-check
    safety_self_check()

    # Step 2: load latest dashboard row
    row = load_latest_row()
    if row is None:
        print(f"  WARNING: {CSV_PATH} not found or empty")
        print("  DISCORD_NOTIFY=SKIP (no data)")
        return 0

    print(f"  latest row: date={row.get('date','?')}")
    print(f"  day label:  {_human_day(row.get('date',''))}")

    # Step 3: build message
    message = build_discord_message(row)

    # Step 4: dry-run -- preview only, no POST
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

    # Step 5: check webhook env var
    webhook_url = os.environ.get(WEBHOOK_ENV, "").strip()
    if not webhook_url:
        print(f"  {WEBHOOK_ENV} not set in environment")
        print("  DISCORD_NOTIFY=SKIP")
        return 0

    # Step 6: live send
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

    # Failure: redact webhook URL from error detail before logging
    safe_detail = redact_text(detail, [webhook_url])
    print(f"  DISCORD_NOTIFY=FAIL ({safe_detail})", file=sys.stderr)
    print(f"  DISCORD_NOTIFY=FAIL ({safe_detail})")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
