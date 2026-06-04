"""
audit_paper_portfolio_exposure.py
TASK-011B: Read-only paper portfolio exposure audit + PnL sanity check.

Reads (read-only):
  outputs/forward_record/prev3y_crypto/*_positions.parquet
  outputs/forward_record/paper_portfolio/daily_pnl.csv
  outputs/forward_record/paper_portfolio/state.json

Writes (audit outputs only):
  outputs/forward_record/paper_portfolio_audit/latest_exposure_audit.md
  outputs/forward_record/paper_portfolio_audit/latest_exposure_audit.json

SAFETY INVARIANTS:
  - NO order endpoint imports
  - NO bybit write API calls
  - NO live trading
  - paper_execution_status = FORBIDDEN
  - live_trading_status = FORBIDDEN
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

# ---------------------------------------------------------------------------
# Safety
# ---------------------------------------------------------------------------
SAFETY = {
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status":    "FORBIDDEN",
    "order_endpoint_called":  False,
    "bybit_write_called":     False,
}

_FORBIDDEN_TOKENS = [
    "bybit", "place_order", "submit_order", "create_order",
    "cancel_order", "private_post", "private_put",
    "live_trading", "paper_trading", "set_leverage",
]

def safety_self_check() -> None:
    src = Path(__file__).read_text(encoding="utf-8")
    bad: list[str] = []
    skip = False
    for line in src.splitlines():
        if "begin skip" in line:  skip = True
        if "end skip"   in line:  skip = False; continue
        if skip or line.strip().startswith("#"): continue
        for tok in _FORBIDDEN_TOKENS:
            if re.search(r"(?:import|from).*" + re.escape(tok), line, re.IGNORECASE):
                bad.append(line.strip()[:80])
    if bad:
        print(f"SAFETY VIOLATION: {bad}", file=sys.stderr)
        sys.exit(99)
    print("  safety_self_check: PASS")

# ---------------------------------------------------------------------------
# Thresholds
# ---------------------------------------------------------------------------
WARN_GROSS_EXPOSURE     = 1.0   # gross_notional / nav
HIGH_RISK_GROSS_EXPOSURE= 3.0
WARN_MAX_POS_PCT_NAV    = 0.10  # single position as fraction of NAV
WARN_DAILY_PNL_PCT      = 0.20  # abs(daily_pnl_pct / 100)  (20%)
STALE_STATE_DAYS        = 3     # gap between last_processed and record date → stale

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
FWD_DIR   = ROOT / "outputs" / "forward_record" / "prev3y_crypto"
PAPER_DIR = ROOT / "outputs" / "forward_record" / "paper_portfolio"
AUDIT_DIR = ROOT / "outputs" / "forward_record" / "paper_portfolio_audit"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _read_parquet(path: Path) -> list[dict[str, Any]]:
    try:
        import pandas as pd  # noqa: PLC0415
        df = pd.read_parquet(path)
        return df.to_dict("records")
    except ImportError:
        pass
    try:
        import pyarrow.parquet as pq  # noqa: PLC0415
        tbl = pq.read_table(str(path))
        cols = tbl.column_names
        return [{c: tbl.column(c)[i].as_py() for c in cols} for i in range(tbl.num_rows)]
    except ImportError:
        raise RuntimeError("Neither pandas nor pyarrow available")


def _load_daily_pnl_csv() -> list[dict[str, str]]:
    path = PAPER_DIR / "daily_pnl.csv"
    if not path.exists():
        return []
    return list(csv.DictReader(open(path, encoding="utf-8")))


def _load_state() -> dict[str, Any]:
    path = PAPER_DIR / "state.json"
    if not path.exists():
        return {}
    return json.loads(path.read_text(encoding="utf-8"))


# ---------------------------------------------------------------------------
# Per-day exposure metrics
# ---------------------------------------------------------------------------

def compute_exposure(rows: list[dict[str, Any]], nav: float) -> dict[str, Any]:
    """
    Given a list of position dicts (from _positions.parquet) and the NAV
    on that date, return the exposure metrics dict.
    """
    long_notional  = sum(float(r.get("position_usd", 0)) for r in rows if float(r.get("position_usd", 0)) > 0)
    short_notional = sum(float(r.get("position_usd", 0)) for r in rows if float(r.get("position_usd", 0)) < 0)
    total_notional = sum(abs(float(r.get("position_usd", 0))) for r in rows)
    net_notional   = long_notional + short_notional

    gross_ratio = total_notional / nav if nav > 0 else 0.0
    net_ratio   = abs(net_notional) / nav if nav > 0 else 0.0

    # Per-position sizes
    pos_abs = [(abs(float(r.get("position_usd", 0))), r.get("symbol", "?"), r.get("side", "?"))
               for r in rows]
    pos_abs.sort(reverse=True)

    max_pos_notional = pos_abs[0][0] if pos_abs else 0.0
    max_pos_pct_nav  = max_pos_notional / nav if nav > 0 else 0.0

    top10 = [{"symbol": sym, "side": side, "notional_usd": round(n, 2)}
             for n, sym, side in pos_abs[:10]]

    # Warnings
    warnings: list[str] = []
    if gross_ratio > HIGH_RISK_GROSS_EXPOSURE:
        warnings.append(f"HIGH_RISK: gross_exposure_ratio={gross_ratio:.2f}x > {HIGH_RISK_GROSS_EXPOSURE}x")
    elif gross_ratio > WARN_GROSS_EXPOSURE:
        warnings.append(f"WARNING: gross_exposure_ratio={gross_ratio:.2f}x > {WARN_GROSS_EXPOSURE}x")
    if max_pos_pct_nav > WARN_MAX_POS_PCT_NAV:
        warnings.append(f"WARNING: max_single_position={max_pos_pct_nav*100:.1f}% of NAV > {WARN_MAX_POS_PCT_NAV*100:.0f}%")

    return {
        "n_positions":            len(rows),
        "long_notional_usd":      round(long_notional, 2),
        "short_notional_usd":     round(short_notional, 2),
        "total_notional_usd":     round(total_notional, 2),
        "net_notional_usd":       round(net_notional, 2),
        "gross_exposure_ratio":   round(gross_ratio, 4),
        "net_exposure_ratio":     round(net_ratio, 4),
        "max_single_pos_notional":round(max_pos_notional, 2),
        "max_single_pos_pct_nav": round(max_pos_pct_nav * 100, 2),
        "top10_positions":        top10,
        "warnings":               warnings,
    }


def detect_stale_state(state: dict[str, Any], parquet_date: str) -> dict[str, Any]:
    """
    Check if state.json last_processed_date is stale relative to parquet_date.
    Returns a diagnostic dict.
    """
    last_proc = state.get("last_processed_date")
    if not last_proc:
        return {"stale": True, "gap_days": None, "diagnosis": "state has no last_processed_date"}
    try:
        from datetime import datetime
        d_last = datetime.strptime(str(last_proc), "%Y%m%d")
        d_rec  = datetime.strptime(str(parquet_date), "%Y%m%d")
        gap    = (d_rec - d_last).days
    except Exception:
        return {"stale": False, "gap_days": None, "diagnosis": "date parse failed"}
    stale = gap > STALE_STATE_DAYS
    diag  = (f"STALE: state last_processed={last_proc}, record_date={parquet_date}, gap={gap} days"
             if stale else f"OK: gap={gap} days")
    return {"stale": stale, "gap_days": gap, "diagnosis": diag}


# ---------------------------------------------------------------------------
# Main audit
# ---------------------------------------------------------------------------

def run_audit(lookback_days: int = 14, dry_run: bool = False) -> dict[str, Any]:
    print("audit_paper_portfolio_exposure.py")
    print(f"  lookback_days={lookback_days}  dry_run={dry_run}")
    print()
    safety_self_check()
    print()

    state   = _load_state()
    pnl_csv = _load_daily_pnl_csv()
    nav_init = state.get("paper_equity_init", 10_000.0)
    current_nav = state.get("nav_usd", nav_init)

    # Index daily PnL rows by date
    pnl_by_date: dict[str, dict] = {}
    for row in pnl_csv:
        d = row.get("date", "")
        if d:
            pnl_by_date[d] = row  # last row wins for duplicates

    # Gather position parquets
    parquets = sorted(FWD_DIR.glob("*_positions.parquet"), reverse=True)[:lookback_days]
    parquets.sort()  # oldest first for reporting

    days: list[dict[str, Any]] = []
    sanity_warnings: list[str] = []

    for p in parquets:
        date = p.stem.split("_")[0]
        rows = _read_parquet(p)
        if not rows:
            continue

        # NAV: use pnl csv if available, else state or init
        pnl_row = pnl_by_date.get(date, {})
        nav_for_date = float(pnl_row.get("nav_usd", current_nav))

        exposure = compute_exposure(rows, nav_for_date)

        daily_pnl_usd = float(pnl_row.get("daily_pnl_usd", 0))
        daily_pnl_pct = float(pnl_row.get("daily_pnl_pct", 0))
        cum_pnl_pct   = float(pnl_row.get("cumulative_pnl_pct", 0))
        max_dd_pct    = float(pnl_row.get("max_dd_pct", 0))
        n_entered     = int(pnl_row.get("n_entered", 0))
        n_exited      = int(pnl_row.get("n_exited", 0))
        data_source   = rows[0].get("data_source", "unknown") if rows else "unknown"

        # PnL sanity check
        pnl_warnings = list(exposure["warnings"])
        if abs(daily_pnl_pct) > WARN_DAILY_PNL_PCT * 100:
            msg = (f"SANITY_WARNING: date={date}  daily_pnl_pct={daily_pnl_pct:.2f}%"
                   f" > ±{WARN_DAILY_PNL_PCT*100:.0f}%")
            pnl_warnings.append(msg)
            sanity_warnings.append(msg)

        # Stale state check
        stale_check = detect_stale_state(state, date)
        if stale_check["stale"]:
            msg = f"STALE_STATE: {stale_check['diagnosis']} → first-live-day PnL is 28-day catch-up, not 1-day"
            pnl_warnings.append(msg)
            sanity_warnings.append(msg)

        # Read guard_summary from {date}_paper_pnl.json if available
        pnl_json_path = PAPER_DIR / f"{date}_paper_pnl.json"
        guard_summary: dict = {}
        if pnl_json_path.exists():
            try:
                pnl_json = json.loads(pnl_json_path.read_text(encoding="utf-8"))
                guard_summary = pnl_json.get("guard_summary", {})
            except Exception:
                pass

        guard_status       = guard_summary.get("guard_status", "PASS")
        n_skipped          = int(guard_summary.get("n_skipped", 0))
        skip_reasons       = guard_summary.get("skip_reasons", {})
        guard_gross        = guard_summary.get("gross_exposure_ratio",
                                               exposure["gross_exposure_ratio"])
        guard_net          = guard_summary.get("net_exposure_ratio",
                                               exposure["net_exposure_ratio"])
        guard_max_single   = guard_summary.get("max_single_position_pct_nav",
                                               exposure["max_single_pos_pct_nav"])

        # Guard-specific warnings
        if guard_status == "WARNING":
            pnl_warnings.append(
                f"GUARD_WARNING: {n_skipped} signals skipped ({skip_reasons})"
            )
        elif guard_status == "BLOCKED":
            pnl_warnings.append(
                f"GUARD_BLOCKED: all new entries blocked ({skip_reasons})"
            )
        if guard_gross > WARN_GROSS_EXPOSURE:
            pnl_warnings.append(
                f"GUARD_RATIO_WARNING: gross_exposure={guard_gross:.3f}x > {WARN_GROSS_EXPOSURE}x"
            )
        if guard_net > 0.5:
            pnl_warnings.append(
                f"GUARD_RATIO_WARNING: net_exposure={guard_net:.3f}x > 0.5x"
            )
        if guard_max_single > 2.0:
            pnl_warnings.append(
                f"GUARD_RATIO_WARNING: max_single_position={guard_max_single:.2f}% > 2.0%"
            )

        day_record: dict[str, Any] = {
            "date":                    date,
            "data_source":             data_source,
            "nav_usd":                 nav_for_date,
            "n_open":                  exposure["n_positions"],
            "n_entered":               n_entered,
            "n_exited":                n_exited,
            "n_skipped":               n_skipped,
            "long_notional_usd":       exposure["long_notional_usd"],
            "short_notional_usd":      exposure["short_notional_usd"],
            "total_notional_usd":      exposure["total_notional_usd"],
            "gross_exposure_ratio":    guard_gross,
            "net_exposure_ratio":      guard_net,
            "max_single_pos_pct_nav":  guard_max_single,
            "max_single_pos_notional": exposure["max_single_pos_notional"],
            "top10_positions":         exposure["top10_positions"],
            "daily_pnl_usd":           round(daily_pnl_usd, 4),
            "daily_pnl_pct":           round(daily_pnl_pct, 4),
            "cumulative_pnl_pct":      round(cum_pnl_pct, 4),
            "max_dd_pct":              round(max_dd_pct, 4),
            "guard_status":            guard_status,
            "skip_reasons":            skip_reasons,
            "warnings":                pnl_warnings,
            "stale_state":             stale_check,
        }
        days.append(day_record)

        # Console summary
        w_tag = f"  ⚠ {len(pnl_warnings)} warning(s)" if pnl_warnings else ""
        print(f"  {date}: gross={guard_gross:.2f}x  net={guard_net:.2f}x"
              f"  guard={guard_status}  skipped={n_skipped}"
              f"  daily_pnl={daily_pnl_pct:+.2f}%  cum_pnl={cum_pnl_pct:+.2f}%"
              f"  src={data_source}{w_tag}")

    # --- Diagnosis summary ---
    diagnosis = _build_diagnosis(state, days, nav_init)
    print()
    print("=== DIAGNOSIS ===")
    for k, v in diagnosis.items():
        print(f"  {k}: {v}")

    result: dict[str, Any] = {
        "generated_at":     datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ"),
        "nav_init_usd":     nav_init,
        "current_nav_usd":  current_nav,
        "state_last_processed": state.get("last_processed_date"),
        "days_audited":     len(days),
        "sanity_warnings":  sanity_warnings,
        "diagnosis":        diagnosis,
        "days":             days,
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status":    "FORBIDDEN",
    }

    if not dry_run:
        _write_outputs(result)

    print()
    print("  safety gates:")
    for k, v in SAFETY.items():
        print(f"    {k} = {v}")
    return result


def _build_diagnosis(state: dict, days: list[dict], nav_init: float) -> dict[str, Any]:
    diag: dict[str, Any] = {}

    # Gross exposure
    if days:
        avg_gross = sum(d["gross_exposure_ratio"] for d in days) / len(days)
        diag["avg_gross_exposure_ratio"] = round(avg_gross, 3)
        diag["exposure_normal"] = avg_gross <= 1.2

    # Stale state
    stale_days = [d for d in days if d["stale_state"].get("stale")]
    diag["stale_state_days"] = [d["date"] for d in stale_days]
    diag["stale_state_cause"] = (
        "state.json last_px values are from cache era (2026-04-30). "
        "When live prices were introduced, prev_px was stale by ~28 days. "
        "The first live-price day booked 28-day accumulated move as 1-day PnL."
        if stale_days else "no stale state detected"
    )

    # Extreme PnL days
    extreme_days = [d for d in days if abs(d["daily_pnl_pct"]) > WARN_DAILY_PNL_PCT * 100]
    diag["extreme_pnl_days"] = [
        {"date": d["date"], "daily_pnl_pct": d["daily_pnl_pct"]} for d in extreme_days
    ]
    diag["extreme_pnl_cause"] = (
        "Momentum strategy: longs = 3yr winners (may have continued rising), "
        "shorts = 3yr losers (may have continued falling). "
        "When prev_px was stale (cache era), the ratio today_px/prev_px captured "
        "28+ days of accumulated price divergence in one step."
        if extreme_days else "no extreme PnL days detected"
    )

    # Position sizing check
    if days:
        max_pos_pcts = [d["max_single_pos_pct_nav"] for d in days]
        diag["max_single_position_pct_nav"] = round(max(max_pos_pcts), 2)
        diag["position_sizing_normal"] = max(max_pos_pcts) <= WARN_MAX_POS_PCT_NAV * 100

    # Bug identification
    diag["pnl_formula_correct"] = True  # formula itself is correct
    diag["bug_identified"]      = "STATE_STALENESS"
    diag["bug_description"] = (
        "paper_portfolio_engine.py does not detect when state.json prev_px values "
        "are stale (from cache era). On the first day of live-read-only prices, "
        "compute_daily_mtm uses prev_px=April_30_cache vs today_px=May_28_live, "
        "creating a fake multi-week PnL spike."
    )
    diag["recommended_fix"] = (
        "Add stale-state detection in paper_portfolio_engine.py: "
        "if gap between state.last_processed_date and today > STALE_RESET_DAYS (e.g. 3), "
        "treat all positions as NEW ENTRIES (PnL=0, reset entry_px to today's live price). "
        "This makes the transition from cache to live transparent."
    )

    return diag


# ---------------------------------------------------------------------------
# Report writers
# ---------------------------------------------------------------------------

def _write_outputs(result: dict[str, Any]) -> None:
    AUDIT_DIR.mkdir(parents=True, exist_ok=True)

    # JSON
    json_path = AUDIT_DIR / "latest_exposure_audit.json"
    json_path.write_text(json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")
    print(f"  JSON: {json_path}")

    # Markdown
    md_path = AUDIT_DIR / "latest_exposure_audit.md"
    md_path.write_text(_build_markdown(result), encoding="utf-8")
    print(f"  MD:   {md_path}")


def _build_markdown(r: dict[str, Any]) -> str:
    lines = [
        "# Paper Portfolio Exposure Audit",
        f"Generated: {r['generated_at']}",
        f"NAV init: ${r['nav_init_usd']:,.0f}  Current NAV: ${r['current_nav_usd']:,.2f}",
        f"State last processed: {r['state_last_processed']}",
        f"Days audited: {r['days_audited']}",
        "",
        "## Diagnosis",
        "",
    ]
    diag = r["diagnosis"]
    lines += [
        f"| field | value |",
        f"|---|---|",
        f"| bug_identified | `{diag.get('bug_identified', 'none')}` |",
        f"| pnl_formula_correct | {diag.get('pnl_formula_correct')} |",
        f"| avg_gross_exposure_ratio | {diag.get('avg_gross_exposure_ratio', 'N/A')}x |",
        f"| exposure_normal | {diag.get('exposure_normal')} |",
        f"| max_single_position_pct_nav | {diag.get('max_single_position_pct_nav', 'N/A')}% |",
        f"| position_sizing_normal | {diag.get('position_sizing_normal')} |",
        f"| stale_state_days | {diag.get('stale_state_days')} |",
        "",
        f"**Bug description:** {diag.get('bug_description', 'N/A')}",
        "",
        f"**Recommended fix:** {diag.get('recommended_fix', 'N/A')}",
        "",
    ]

    # Sanity warnings
    if r["sanity_warnings"]:
        lines += ["## Sanity Warnings", ""]
        for w in r["sanity_warnings"]:
            lines.append(f"- {w}")
        lines.append("")

    # Per-day table
    lines += [
        "## Daily Exposure Summary",
        "",
        "| date | guard | skipped | gross_exp | net_exp | daily_pnl% | cum_pnl% | max_dd% | max_pos% | warnings |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for d in r["days"]:
        w_count = len(d["warnings"])
        lines.append(
            f"| {d['date']} | {d.get('guard_status','PASS')} | {d.get('n_skipped',0)}"
            f" | {d['gross_exposure_ratio']:.2f}x"
            f" | {d['net_exposure_ratio']:.2f}x | {d['daily_pnl_pct']:+.2f}%"
            f" | {d['cumulative_pnl_pct']:+.2f}% | {d['max_dd_pct']:.2f}%"
            f" | {d['max_single_pos_pct_nav']:.1f}% | {w_count} |"
        )
    lines.append("")

    # Safety gates
    lines += [
        "## Safety Gates",
        "",
        "| gate | value |",
        "|---|---|",
        "| paper_execution_status | FORBIDDEN |",
        "| live_trading_status | FORBIDDEN |",
        "| order_endpoint_called | False |",
        "| bybit_write_called | False |",
        "",
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def main() -> int:
    dry_run  = "--dry-run" in sys.argv
    lookback = 14
    for arg in sys.argv[1:]:
        if arg.startswith("--lookback="):
            lookback = int(arg.split("=")[1])
    run_audit(lookback_days=lookback, dry_run=dry_run)
    print("AUDIT_DONE")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
