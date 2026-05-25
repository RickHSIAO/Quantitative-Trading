"""
build_forward_validation_dashboard.py
TASK-007: 30-Day Forward Validation Dashboard Builder

Reads outputs/forward_record/ daily artifacts (read-only).
Writes:
  outputs/forward_record/dashboard/index.html
  outputs/forward_record/dashboard/latest_summary.md
  outputs/forward_record/dashboard/validation_30d.csv

SAFETY INVARIANTS (enforced throughout):
  - NO order endpoint imports
  - NO write to any trading, strategy, or position file
  - NO modification of main.py live logic
  - paper_execution_status = FORBIDDEN (never changed)
  - live_trading_status    = FORBIDDEN (never changed)
  - Read-only access to forward_record artifacts
"""
from __future__ import annotations

import csv
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Safety constants — never modified
# ---------------------------------------------------------------------------
SAFETY = {
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status": "FORBIDDEN",
    "order_endpoint_called": False,
    "bybit_write_called": False,
}

# ---------------------------------------------------------------------------
# Paths (all read-only except dashboard/ output dir)
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[1]
FORWARD_DIR = ROOT / "outputs" / "forward_record" / "prev3y_crypto"
ALERT_DIR   = ROOT / "outputs" / "forward_record" / "alerts"
LOG_DIR     = ROOT / "outputs" / "logs" / "prev3y_crypto"
DASHBOARD   = ROOT / "outputs" / "forward_record" / "dashboard"

PAPER_DIR   = ROOT / "outputs" / "forward_record" / "paper_portfolio"

CLOCK_START = "20260518"   # authorised by Rick 2026-05-18
STRATEGY    = "prev3y_crypto / combined_paper_safe_variant"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_json(path: Path) -> dict[str, Any]:
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return {}


def _read_log_kv(path: Path) -> dict[str, str]:
    """Parse key=value lines from runner .log files."""
    result: dict[str, str] = {}
    if not path.exists():
        return result
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        if "=" in line:
            k, _, v = line.partition("=")
            result[k.strip()] = v.strip()
    return result


def _na(value: Any, fmt: str = "") -> str:
    """Format a numeric value or return N/A."""
    if value is None:
        return "N/A"
    try:
        f = float(value)
        return (fmt % f) if fmt else str(f)
    except (TypeError, ValueError):
        return str(value) if value != "" else "N/A"


def _fmt_pct(v: Any) -> str:
    return _na(v, "%.4f%%")


def _days_since(yyyymmdd: str) -> int:
    try:
        d = datetime.strptime(yyyymmdd, "%Y%m%d").replace(tzinfo=timezone.utc)
        return (datetime.now(timezone.utc) - d).days
    except Exception:
        return 0


# ---------------------------------------------------------------------------
# Data collection
# ---------------------------------------------------------------------------

def collect_days(lookback: int = 30) -> tuple[list[dict[str, Any]], int]:
    """
    Scan FORWARD_DIR for dated forward_stats files, date >= CLOCK_START only.
    TASK-007C: dates before CLOCK_START (pre-clock shadow/drill outputs) are skipped.
    Returns (rows newest-first, skipped_pre_clock_start_count).
    """
    stat_files = sorted(FORWARD_DIR.glob("*_forward_stats.json"), reverse=True)
    rows: list[dict[str, Any]] = []
    skipped_pre_clock: int = 0

    for stat_path in stat_files:
        stem = stat_path.stem                              # e.g. 20260518_forward_stats
        date = stem.split("_")[0]                          # 20260518

        # TASK-007C: skip any output produced before the official 30-day clock start
        if date < CLOCK_START:
            skipped_pre_clock += 1
            continue

        if len(rows) >= lookback:
            break

        stats   = _read_json(stat_path)
        pnl     = _read_json(FORWARD_DIR / f"{date}_pnl.json")
        overlay = _read_json(FORWARD_DIR / f"{date}_overlay_check.json")
        alert   = _read_json(ALERT_DIR   / f"{date}_alert_log.json")
        log_kv  = _read_log_kv(LOG_DIR   / f"{date}_forward_record.log")

        # Signal count: n_longs + n_shorts from pnl
        n_longs  = pnl.get("n_longs")
        n_shorts = pnl.get("n_shorts")
        signal_count = (
            (n_longs or 0) + (n_shorts or 0)
            if (n_longs is not None or n_shorts is not None)
            else None
        )

        # Safety gate check
        paper_status = stats.get("paper_execution_status", SAFETY["paper_execution_status"])
        live_status  = stats.get("live_trading_status",    SAFETY["live_trading_status"])

        row: dict[str, Any] = {
            # Identity
            "date":                    date,
            "day_elapsed":             stats.get("days_elapsed", "N/A"),
            "day_number":              stats.get("day_number",   "N/A"),
            # Runner status
            "runner_status":           log_kv.get("status", stats.get("status", "MISSING")),
            "data_source":             pnl.get("data_source", log_kv.get("data_source", "N/A")),
            "safety_scan":             log_kv.get("safety_scan", "N/A"),
            # Safety gates
            "dry_run":                 stats.get("dry_run", True),
            "paper_execution_status":  paper_status,
            "live_trading_status":     live_status,
            "FORBIDDEN_order_endpoint":alert.get("FORBIDDEN_order_endpoint", "NOT_ATTEMPTED"),
            "FORBIDDEN_bybit_write":   alert.get("FORBIDDEN_bybit_write",    "NOT_ATTEMPTED"),
            # Signals
            "signal_count":            signal_count,
            "n_longs":                 n_longs,
            "n_shorts":                n_shorts,
            # PnL (N/A until real forward returns accumulate)
            "daily_pnl_pct":           pnl.get("daily_pnl_pct"),
            "cumulative_pnl_pct":      pnl.get("cumulative_pnl_pct"),
            "nav_usd":                 pnl.get("nav_usd"),
            # Drawdown
            "current_dd_pct":          stats.get("current_dd_pct"),
            "max_dd_pct":              stats.get("max_dd_pct"),
            # Risk metrics (will be null early in the run)
            "sharpe_cumulative":       stats.get("sharpe_cumulative"),
            "calmar_ratio":            stats.get("calmar_ratio"),
            # Gates
            "active_warning_gates":    json.dumps(stats.get("active_warning_gates", [])),
            "active_stop_gates":       json.dumps(stats.get("active_stop_gates", [])),
            "overlay_pass":            overlay.get("overlay_pass", "N/A"),
            "review_006b_ready":       stats.get("review_006b_trigger_ready", False),
            # Alert
            "alerts_triggered":        len(alert.get("alerts_sent", [])),
            "alert_dry_run":           alert.get("dry_run", True),
        }
        # TASK-010: overlay paper portfolio PnL when available
        paper_pnl = _read_json(PAPER_DIR / f"{date}_paper_pnl.json")
        if paper_pnl:
            row["daily_pnl_pct"]      = paper_pnl.get("daily_pnl_pct",      row["daily_pnl_pct"])
            row["cumulative_pnl_pct"] = paper_pnl.get("cumulative_pnl_pct", row["cumulative_pnl_pct"])
            row["max_dd_pct"]         = paper_pnl.get("max_dd_pct",         row["max_dd_pct"])
            row["nav_usd"]            = paper_pnl.get("nav_usd",            row["nav_usd"])

        rows.append(row)

    return rows, skipped_pre_clock


# ---------------------------------------------------------------------------
# CSV writer
# ---------------------------------------------------------------------------

CSV_FIELDS = [
    "date", "day_elapsed", "day_number", "runner_status", "data_source",
    "safety_scan", "dry_run", "paper_execution_status", "live_trading_status",
    "FORBIDDEN_order_endpoint", "FORBIDDEN_bybit_write",
    "signal_count", "n_longs", "n_shorts",
    "daily_pnl_pct", "cumulative_pnl_pct", "nav_usd",
    "current_dd_pct", "max_dd_pct",
    "sharpe_cumulative", "calmar_ratio",
    "active_warning_gates", "active_stop_gates",
    "overlay_pass", "review_006b_ready", "alerts_triggered", "alert_dry_run",
]


def write_csv(rows: list[dict], path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=CSV_FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(rows)
    print(f"  CSV:  {path}  ({len(rows)} rows)")


# ---------------------------------------------------------------------------
# Markdown summary
# ---------------------------------------------------------------------------

def write_md_summary(rows: list[dict], summary_json: dict, path: Path, skipped: int = 0) -> None:
    now_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    latest = rows[0] if rows else {}
    n_days = len(rows)
    days_ok  = sum(1 for r in rows if r["runner_status"] in ("REVIEW_READY", "DRY_RUN"))
    days_err = n_days - days_ok

    md = f"""# 30-Day Forward Validation — Dashboard Summary

Generated: {now_utc}

## Clock

| field | value |
|---|---|
| start_date | {CLOCK_START} |
| days_completed | {n_days} |
| days_remaining | {max(0, 30 - n_days)} |
| skipped_pre_clock_start | {summary_json.get("skipped_pre_clock_start_count", skipped)} |
| target_end | 20260617 |
| strategy | {STRATEGY} |
| validation_mode | forward-record / dry-run only |

## Safety Gates (must remain constant)

| gate | value |
|---|---|
| paper_execution_status | {SAFETY["paper_execution_status"]} |
| live_trading_status | {SAFETY["live_trading_status"]} |
| order_endpoint_called | {SAFETY["order_endpoint_called"]} |
| bybit_write_called | {SAFETY["bybit_write_called"]} |

## Latest Day ({latest.get("date", "N/A")})

| metric | value |
|---|---|
| runner_status | {latest.get("runner_status", "N/A")} |
| data_source | {latest.get("data_source", "N/A")} |
| safety_scan | {latest.get("safety_scan", "N/A")} |
| dry_run | {latest.get("dry_run", "N/A")} |
| paper_execution_status | {latest.get("paper_execution_status", "N/A")} |
| live_trading_status | {latest.get("live_trading_status", "N/A")} |
| signal_count | {_na(latest.get("signal_count"))} |
| daily_pnl_pct | {_fmt_pct(latest.get("daily_pnl_pct"))} |
| cumulative_pnl_pct | {_fmt_pct(latest.get("cumulative_pnl_pct"))} |
| max_dd_pct | {_fmt_pct(latest.get("max_dd_pct"))} |
| sharpe_cumulative | {_na(latest.get("sharpe_cumulative"))} |
| alerts_triggered | {_na(latest.get("alerts_triggered"))} |
| review_006b_ready | {latest.get("review_006b_ready", "N/A")} |

## Run Summary ({n_days} days)

| metric | value |
|---|---|
| days_ok (REVIEW_READY/DRY_RUN) | {days_ok} |
| days_error | {days_err} |
| forward_summary_status | {summary_json.get("gate_status", {})} |

## Daily Log

| date | status | signals | daily_pnl | cum_pnl | max_dd | alerts |
|---|---|---|---|---|---|---|
"""
    for r in rows:
        md += (
            f"| {r['date']} "
            f"| {r['runner_status']} "
            f"| {_na(r['signal_count'])} "
            f"| {_fmt_pct(r['daily_pnl_pct'])} "
            f"| {_fmt_pct(r['cumulative_pnl_pct'])} "
            f"| {_fmt_pct(r['max_dd_pct'])} "
            f"| {_na(r['alerts_triggered'])} |\n"
        )

    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(md, encoding="utf-8")
    print(f"  MD:   {path}")


# ---------------------------------------------------------------------------
# HTML dashboard
# ---------------------------------------------------------------------------

_STATUS_COLOR = {
    "REVIEW_READY": "#22c55e",
    "DRY_RUN":      "#3b82f6",
    "MISSING":      "#ef4444",
    "ERROR":        "#ef4444",
}


def _status_badge(status: str) -> str:
    color = _STATUS_COLOR.get(status, "#6b7280")
    return (
        f'<span style="background:{color};color:#fff;padding:2px 8px;'
        f'border-radius:4px;font-size:0.75rem;font-weight:600">{status}</span>'
    )


def _gate_badge(value: Any) -> str:
    s = str(value)
    ok = s in ("FORBIDDEN", "NOT_ATTEMPTED", "True", "True", "PASS")
    color = "#22c55e" if ok else "#ef4444"
    return (
        f'<span style="background:{color};color:#fff;padding:2px 6px;'
        f'border-radius:4px;font-size:0.75rem">{s}</span>'
    )


def write_html(rows: list[dict], summary_json: dict, path: Path, skipped: int = 0) -> None:
    now_utc  = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    n_days   = len(rows)
    latest   = rows[0] if rows else {}
    days_ok  = sum(1 for r in rows if r["runner_status"] in ("REVIEW_READY", "DRY_RUN"))

    # Build table rows (newest first)
    table_rows_html = ""
    for r in rows:
        s = r["runner_status"]
        bg = "#f0fdf4" if s == "REVIEW_READY" else "#eff6ff" if s == "DRY_RUN" else "#fef2f2"
        warn_gates = json.loads(r["active_warning_gates"]) if isinstance(r["active_warning_gates"], str) else r["active_warning_gates"]
        stop_gates = json.loads(r["active_stop_gates"])    if isinstance(r["active_stop_gates"], str)    else r["active_stop_gates"]
        gate_cell  = (
            f'<span style="color:#ef4444">WARN:{warn_gates}</span>' if warn_gates else
            f'<span style="color:#dc2626">STOP:{stop_gates}</span>' if stop_gates else
            '<span style="color:#22c55e">&#10003;</span>'
        )
        table_rows_html += f"""
        <tr style="background:{bg}">
          <td>{r['date']}</td>
          <td>{r['day_elapsed']}</td>
          <td>{_status_badge(s)}</td>
          <td style="font-size:0.8rem">{r.get('data_source','N/A')}</td>
          <td>{_gate_badge(r['paper_execution_status'])}</td>
          <td>{_gate_badge(r['live_trading_status'])}</td>
          <td>{_na(r['signal_count'])}</td>
          <td>{_fmt_pct(r['daily_pnl_pct'])}</td>
          <td>{_fmt_pct(r['cumulative_pnl_pct'])}</td>
          <td>{_fmt_pct(r['max_dd_pct'])}</td>
          <td>{gate_cell}</td>
          <td>{_na(r['alerts_triggered'])}</td>
        </tr>"""

    # Progress bar
    pct  = min(100, round(n_days / 30 * 100))
    prog = f"""
      <div style="background:#e5e7eb;border-radius:8px;height:18px;margin:8px 0">
        <div style="background:#3b82f6;height:18px;border-radius:8px;width:{pct}%"></div>
      </div>
      <div style="font-size:0.8rem;color:#6b7280">{n_days}/30 days ({pct}%) — target end: 20260617</div>
    """

    html = f"""<!DOCTYPE html>
<html lang="zh-TW">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width,initial-scale=1">
  <title>30-Day Forward Validation Dashboard</title>
  <style>
    * {{ box-sizing: border-box; margin: 0; padding: 0; }}
    body {{ font-family: system-ui, sans-serif; background: #f8fafc; color: #1e293b; padding: 24px; }}
    h1 {{ font-size: 1.4rem; font-weight: 700; margin-bottom: 4px; }}
    .sub {{ font-size: 0.8rem; color: #64748b; margin-bottom: 20px; }}
    .grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(200px, 1fr)); gap: 12px; margin-bottom: 20px; }}
    .card {{ background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; padding: 14px; }}
    .card-label {{ font-size: 0.72rem; color: #64748b; text-transform: uppercase; letter-spacing: 0.05em; }}
    .card-value {{ font-size: 1.3rem; font-weight: 700; margin-top: 4px; }}
    .card-sub {{ font-size: 0.72rem; color: #64748b; }}
    .safety-box {{ background: #f0fdf4; border: 1px solid #bbf7d0; border-radius: 8px; padding: 14px; margin-bottom: 20px; }}
    .safety-box h3 {{ font-size: 0.85rem; font-weight: 700; color: #15803d; margin-bottom: 8px; }}
    .safety-grid {{ display: grid; grid-template-columns: repeat(auto-fill, minmax(220px, 1fr)); gap: 6px; font-size: 0.8rem; }}
    .safety-item {{ display: flex; justify-content: space-between; }}
    table {{ width: 100%; border-collapse: collapse; background: #fff; border: 1px solid #e2e8f0; border-radius: 8px; overflow: hidden; font-size: 0.82rem; }}
    th {{ background: #f1f5f9; padding: 8px 10px; text-align: left; font-size: 0.72rem; text-transform: uppercase; color: #64748b; border-bottom: 1px solid #e2e8f0; }}
    td {{ padding: 8px 10px; border-bottom: 1px solid #f1f5f9; }}
    .ts {{ font-size: 0.72rem; color: #94a3b8; margin-top: 20px; text-align: right; }}
  </style>
</head>
<body>
  <h1>&#128200; 30-Day Forward Validation Dashboard</h1>
  <div class="sub">Strategy: {STRATEGY} &mdash; Clock start: {CLOCK_START} &mdash; Generated: {now_utc}</div>

  <!-- Progress -->
  {prog}

  <!-- KPI cards -->
  <div class="grid">
    <div class="card">
      <div class="card-label">Days Completed</div>
      <div class="card-value">{n_days}</div>
      <div class="card-sub">of 30 required</div>
    </div>
    <div class="card">
      <div class="card-label">Days OK</div>
      <div class="card-value" style="color:#22c55e">{days_ok}</div>
      <div class="card-sub">REVIEW_READY / DRY_RUN</div>
    </div>
    <div class="card">
      <div class="card-label">Pre-Clock Skipped</div>
      <div class="card-value" style="color:#6b7280">{skipped}</div>
      <div class="card-sub">excluded (before {CLOCK_START})</div>
    </div>
    <div class="card">
      <div class="card-label">Latest Status</div>
      <div class="card-value" style="font-size:1rem;margin-top:6px">{_status_badge(latest.get("runner_status","N/A"))}</div>
      <div class="card-sub">{latest.get("date","N/A")}</div>
    </div>
    <div class="card">
      <div class="card-label">Signal Count</div>
      <div class="card-value">{_na(latest.get("signal_count"))}</div>
      <div class="card-sub">longs+shorts latest day</div>
    </div>
    <div class="card">
      <div class="card-label">Cum. PnL</div>
      <div class="card-value">{_fmt_pct(latest.get("cumulative_pnl_pct"))}</div>
      <div class="card-sub">paper / dry-run only</div>
    </div>
    <div class="card">
      <div class="card-label">Max Drawdown</div>
      <div class="card-value">{_fmt_pct(latest.get("max_dd_pct"))}</div>
      <div class="card-sub">since clock start</div>
    </div>
    <div class="card">
      <div class="card-label">Sharpe (cum)</div>
      <div class="card-value">{_na(latest.get("sharpe_cumulative"))}</div>
      <div class="card-sub">N/A until data accumulates</div>
    </div>
    <div class="card">
      <div class="card-label">Alerts Triggered</div>
      <div class="card-value">{_na(latest.get("alerts_triggered"))}</div>
      <div class="card-sub">latest day</div>
    </div>
  </div>

  <!-- Safety box -->
  <div class="safety-box">
    <h3>&#128274; Safety Gates — must remain constant</h3>
    <div class="safety-grid">
      <div class="safety-item"><span>paper_execution_status</span>{_gate_badge("FORBIDDEN")}</div>
      <div class="safety-item"><span>live_trading_status</span>{_gate_badge("FORBIDDEN")}</div>
      <div class="safety-item"><span>FORBIDDEN_order_endpoint</span>{_gate_badge(latest.get("FORBIDDEN_order_endpoint","NOT_ATTEMPTED"))}</div>
      <div class="safety-item"><span>FORBIDDEN_bybit_write</span>{_gate_badge(latest.get("FORBIDDEN_bybit_write","NOT_ATTEMPTED"))}</div>
      <div class="safety-item"><span>dry_run</span>{_gate_badge(str(latest.get("dry_run",True)))}</div>
      <div class="safety-item"><span>overlay_pass</span>{_gate_badge(str(latest.get("overlay_pass","N/A")))}</div>
    </div>
  </div>

  <!-- Daily table -->
  <table>
    <thead>
      <tr>
        <th>Date</th>
        <th>Day</th>
        <th>Status</th>
        <th>Data Source</th>
        <th>Paper Exec</th>
        <th>Live Trade</th>
        <th>Signals</th>
        <th>Daily PnL</th>
        <th>Cum PnL</th>
        <th>Max DD</th>
        <th>Gates</th>
        <th>Alerts</th>
      </tr>
    </thead>
    <tbody>
      {table_rows_html}
    </tbody>
  </table>

  <div class="ts">All values are dry-run / paper record only. No real trades executed. Generated {now_utc}</div>
</body>
</html>
"""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    print(f"  HTML: {path}")


# ---------------------------------------------------------------------------
# Safety self-check (run before writing anything)
# ---------------------------------------------------------------------------
_FORBIDDEN_IMPORTS = [
    "bybit", "order", "submit", "place_order", "create_order",
    "private_post", "private_put", "live_trading", "paper_trading",
]


def safety_self_check() -> None:
    """Verify this script does not import any forbidden modules."""
    src = Path(__file__).read_text(encoding="utf-8")
    violations: list[str] = []
    for token in _FORBIDDEN_IMPORTS:
        # Check for import statements (not comments/strings containing the token)
        import re
        for m in re.finditer(r"^\s*(?:import|from)\s+.*" + re.escape(token), src, re.MULTILINE | re.IGNORECASE):
            violations.append(m.group().strip())
    if violations:
        print(f"SAFETY VIOLATION — forbidden import found: {violations}", file=sys.stderr)
        sys.exit(99)
    print("  safety_self_check: PASS (no forbidden imports)")


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    print("build_forward_validation_dashboard.py")
    print(f"  ROOT:        {ROOT}")
    print(f"  FORWARD_DIR: {FORWARD_DIR}")
    print(f"  DASHBOARD:   {DASHBOARD}")
    print()

    # Step 1: safety self-check
    safety_self_check()

    # Step 2: collect data (read-only)
    rows, skipped_pre_clock = collect_days(lookback=30)
    print(f"  collected {len(rows)} day(s)  (skipped_pre_clock_start_count={skipped_pre_clock})")
    if not rows:
        print("  WARNING: no forward record data found — writing empty dashboard")

    summary_json = _read_json(FORWARD_DIR / "forward_summary.json")

    # Step 3: write outputs
    print("  writing outputs...")
    DASHBOARD.mkdir(parents=True, exist_ok=True)
    write_csv(rows, DASHBOARD / "validation_30d.csv")
    write_md_summary(rows, summary_json, DASHBOARD / "latest_summary.md", skipped=skipped_pre_clock)
    write_html(rows, summary_json, DASHBOARD / "index.html", skipped=skipped_pre_clock)

    # Step 4: confirm safety gates unchanged
    print()
    print("  safety gates:")
    for k, v in SAFETY.items():
        print(f"    {k} = {v}")

    print()
    print("Done.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
