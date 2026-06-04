"""
paper_portfolio_engine.py
TASK-010: Paper Portfolio PnL Simulation for 30-Day Forward Validation

Reads daily {date}_positions.parquet from:
  outputs/forward_record/prev3y_crypto/
Maintains paper portfolio state in:
  outputs/forward_record/paper_portfolio/state.json
  outputs/forward_record/paper_portfolio/daily_pnl.csv
  outputs/forward_record/paper_portfolio/trades.csv
  outputs/forward_record/paper_portfolio/{date}_paper_pnl.json

Usage:
  python3 scripts/paper_portfolio_engine.py --date YYYYMMDD
  python3 scripts/paper_portfolio_engine.py --date YYYYMMDD --dry-run
  python3 scripts/paper_portfolio_engine.py --rebuild  # reprocess all dates

Output tokens (parsed by run_forward_record_daily.sh):
  PAPER_PNL=DRY_RUN  --dry-run: preview only, no writes
  PAPER_PNL=SKIP     no parquet found for date
  PAPER_PNL=PASS     success
  PAPER_PNL=FAIL     error (non-fatal; daily runner continues)

SAFETY INVARIANTS:
  paper_execution_status = FORBIDDEN (never relaxed)
  live_trading_status    = FORBIDDEN (never relaxed)
  NO order endpoint imports or calls
  NO bybit / ccxt / private_post / place_order
"""
from __future__ import annotations

import csv
import json
import re
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

# ---------------------------------------------------------------------------
# Paths
# ---------------------------------------------------------------------------
ROOT        = Path(__file__).resolve().parents[1]
FORWARD_DIR = ROOT / "outputs" / "forward_record" / "prev3y_crypto"
PAPER_DIR   = ROOT / "outputs" / "forward_record" / "paper_portfolio"

STATE_PATH      = PAPER_DIR / "state.json"
DAILY_PNL_CSV   = PAPER_DIR / "daily_pnl.csv"
TRADES_CSV      = PAPER_DIR / "trades.csv"

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------
PAPER_EQUITY_INIT   = 10_000.0   # USDT
CLOCK_START         = "20260518"  # Day 1 of 30-day validation
STALE_RESET_DAYS    = 3            # gap (days) between last_processed and today that triggers stale-state reset

# Exposure caps (generous; strategy actually uses 25/25/50)
MAX_LONG_POSITIONS  = 30
MAX_SHORT_POSITIONS = 30
MAX_POSITIONS_TOTAL = 60

# TP / SL as percentage of entry (None = disabled)
# Momentum strategy typically uses signal-based exits, not fixed TP/SL.
TP_PCT = None   # e.g. 0.30 for +30%
SL_PCT = None   # e.g. -0.10 for -10%

SAFETY = {
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status":    "FORBIDDEN",
    "order_endpoint_called":  False,
    "bybit_write_called":     False,
}

DAILY_PNL_FIELDS = [
    "date", "nav_usd", "daily_pnl_usd", "daily_pnl_pct",
    "cumulative_pnl_pct", "max_dd_pct", "n_open", "n_entered", "n_exited",
]
TRADES_FIELDS = [
    "symbol", "side", "entry_date", "entry_px",
    "exit_date", "exit_px", "exit_reason",
    "position_usd", "pnl_usd", "pnl_pct",
]

# ---------------------------------------------------------------------------
# Safety self-check
# ---------------------------------------------------------------------------
# --- forbidden-import detector --- begin skip
_FORBIDDEN_TOKENS = [
    "bybit", "ccxt", "place_order", "create_order",
    "submit_order", "private_post", "private_put",
    "order_endpoint", "set_leverage", "cancel_order",
]
# --- forbidden-import detector --- end skip


def safety_self_check() -> None:
    """Exit 99 if this script imports any forbidden module."""
    src   = Path(__file__).read_text(encoding="utf-8")
    skip  = False
    bad: list[str] = []
    for line in src.splitlines():
        if "begin skip" in line:
            skip = True
        if "end skip" in line:
            skip = False
            continue
        if skip:
            continue
        s = line.strip()
        if s.startswith("#"):
            continue
        for tok in _FORBIDDEN_TOKENS:
            if re.search(r"(?:import|from).*" + re.escape(tok), s, re.IGNORECASE):
                bad.append(s[:80])
    if bad:
        print(f"SAFETY VIOLATION: {bad}", file=sys.stderr)
        sys.exit(99)
    print("  safety_self_check: PASS")


# ---------------------------------------------------------------------------
# Parquet reader  (pandas preferred; falls back to pyarrow)
# ---------------------------------------------------------------------------

def _read_parquet(path: Path) -> list[dict[str, Any]]:
    """Return list of row dicts from a parquet file."""
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
        rows = []
        for i in range(tbl.num_rows):
            rows.append({c: tbl.column(c)[i].as_py() for c in cols})
        return rows
    except ImportError:
        raise RuntimeError("Neither pandas nor pyarrow is installed")


def load_positions_parquet(date: str) -> list[dict[str, Any]] | None:
    """Load {date}_positions.parquet. Returns None if not found."""
    path = FORWARD_DIR / f"{date}_positions.parquet"
    if not path.exists():
        return None
    rows = _read_parquet(path)
    return rows


# ---------------------------------------------------------------------------
# State management
# ---------------------------------------------------------------------------

def _make_initial_state() -> dict[str, Any]:
    return {
        "paper_equity_init":     PAPER_EQUITY_INIT,
        "nav_usd":               PAPER_EQUITY_INIT,
        "peak_nav_usd":          PAPER_EQUITY_INIT,
        "last_processed_date":   None,
        "positions":             [],
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status":    "FORBIDDEN",
    }


def load_state() -> dict[str, Any]:
    if STATE_PATH.exists():
        try:
            return json.loads(STATE_PATH.read_text(encoding="utf-8"))
        except Exception:
            pass
    return _make_initial_state()


def save_state(state: dict[str, Any], dry_run: bool = False) -> None:
    if dry_run:
        return
    PAPER_DIR.mkdir(parents=True, exist_ok=True)
    STATE_PATH.write_text(
        json.dumps(state, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )


# ---------------------------------------------------------------------------
# Daily MTM PnL computation
# ---------------------------------------------------------------------------

def _pos_key(row: dict) -> str:
    return f"{row['symbol']}|{row['side']}"


def compute_daily_mtm(
    state: dict[str, Any],
    today_rows: list[dict[str, Any]],
) -> dict[str, Any]:
    """
    Compare today's parquet rows against yesterday's state positions.
    Returns a result dict with daily_pnl_usd, entered, exited, and
    the updated positions list.
    """
    prev_pos: dict[str, dict] = {
        _pos_key(p): p for p in state.get("positions", [])
    }
    today_map: dict[str, dict] = {}
    for row in today_rows:
        px = row.get("hypothetical_fill_px")
        if px is None or px == 0:
            continue
        today_map[_pos_key(row)] = {
            "symbol":       row["symbol"],
            "side":         row["side"],
            "last_px":      float(px),
            "position_usd": float(row.get("position_usd", 0.0)),
            "weight":       float(row.get("weight", 0.0)),
        }

    daily_pnl_usd = 0.0
    entered: list[dict] = []
    exited:  list[dict] = []
    new_positions: list[dict] = []

    # --- Positions present in today's parquet ---
    for key, today_row in today_map.items():
        if key in prev_pos:
            prev        = prev_pos[key]
            prev_px     = float(prev.get("last_px", today_row["last_px"]))
            today_px    = today_row["last_px"]
            pos_usd     = today_row["position_usd"]
            if prev_px > 0:
                px_return   = today_px / prev_px - 1.0
                pnl_usd     = pos_usd * px_return
                daily_pnl_usd += pnl_usd
            entry_date  = prev.get("entry_date")
            entry_px    = prev.get("entry_px", today_row["last_px"])
            # Check TP / SL
            exit_reason = _check_tp_sl(entry_px, today_px, today_row["side"])
            if exit_reason:
                exit_usd = pos_usd
                exit_pnl = exit_usd * (today_px / entry_px - 1.0) if entry_px else 0.0
                exited.append({
                    "symbol":      today_row["symbol"],
                    "side":        today_row["side"],
                    "entry_date":  entry_date,
                    "entry_px":    entry_px,
                    "exit_px":     today_px,
                    "exit_reason": exit_reason,
                    "position_usd": abs(pos_usd),
                    "pnl_usd":     exit_pnl,
                })
            else:
                new_positions.append({
                    "symbol":      today_row["symbol"],
                    "side":        today_row["side"],
                    "entry_date":  entry_date,
                    "entry_px":    entry_px,
                    "last_px":     today_px,
                    "position_usd": today_row["position_usd"],
                    "weight":      today_row["weight"],
                })
        else:
            # New position: entry day, no PnL
            entered.append({
                "symbol":      today_row["symbol"],
                "side":        today_row["side"],
                "entry_date":  None,   # filled below
                "entry_px":    today_row["last_px"],
                "last_px":     today_row["last_px"],
                "position_usd": today_row["position_usd"],
                "weight":      today_row["weight"],
            })
            new_positions.append(entered[-1])

    # --- Positions in yesterday but not today: exited (no TP/SL, just dropped)
    for key, prev in prev_pos.items():
        if key not in today_map:
            entry_px = float(prev.get("entry_px", prev.get("last_px", 0)))
            last_px  = float(prev.get("last_px", entry_px))
            pos_usd  = float(prev.get("position_usd", 0))
            pnl_usd  = pos_usd * (last_px / entry_px - 1.0) if entry_px > 0 else 0.0
            exited.append({
                "symbol":      prev["symbol"],
                "side":        prev["side"],
                "entry_date":  prev.get("entry_date"),
                "entry_px":    entry_px,
                "exit_px":     last_px,
                "exit_reason": "dropped_from_signal",
                "position_usd": abs(pos_usd),
                "pnl_usd":     pnl_usd,
            })

    return {
        "daily_pnl_usd": daily_pnl_usd,
        "new_positions":  new_positions,
        "entered":        entered,
        "exited":         exited,
    }


def _check_tp_sl(entry_px: float, today_px: float, side: str) -> str | None:
    """Return "TP" / "SL" if today_px crosses the configured threshold, else None."""
    if TP_PCT is None and SL_PCT is None:
        return None
    if entry_px <= 0:
        return None
    ret = today_px / entry_px - 1.0
    if side == "long":
        if TP_PCT is not None and ret >= TP_PCT:
            return "TP"
        if SL_PCT is not None and ret <= SL_PCT:
            return "SL"
    else:  # short
        if TP_PCT is not None and ret <= -TP_PCT:
            return "TP"
        if SL_PCT is not None and ret >= -SL_PCT:
            return "SL"
    return None


# ---------------------------------------------------------------------------
# Exposure validation
# ---------------------------------------------------------------------------

def check_exposure(positions: list[dict]) -> list[str]:
    """Return list of warning strings if any exposure cap is exceeded."""
    warnings: list[str] = []
    n_long  = sum(1 for p in positions if p.get("side") == "long")
    n_short = sum(1 for p in positions if p.get("side") == "short")
    n_total = len(positions)
    if n_long > MAX_LONG_POSITIONS:
        warnings.append(f"long positions {n_long} > cap {MAX_LONG_POSITIONS}")
    if n_short > MAX_SHORT_POSITIONS:
        warnings.append(f"short positions {n_short} > cap {MAX_SHORT_POSITIONS}")
    if n_total > MAX_POSITIONS_TOTAL:
        warnings.append(f"total positions {n_total} > cap {MAX_POSITIONS_TOTAL}")
    return warnings


# ---------------------------------------------------------------------------
# State update
# ---------------------------------------------------------------------------

def update_state(
    state: dict[str, Any],
    daily_pnl_usd: float,
    new_positions: list[dict],
    date: str,
) -> dict[str, Any]:
    """Update nav, peak, max_dd; return updated state."""
    new_nav  = state["nav_usd"] + daily_pnl_usd
    peak     = max(state["peak_nav_usd"], new_nav)
    max_dd   = (peak - new_nav) / peak * 100.0 if peak > 0 else 0.0
    # Tag entered positions with today's date
    for pos in new_positions:
        if pos.get("entry_date") is None:
            pos["entry_date"] = date
    state["nav_usd"]             = new_nav
    state["peak_nav_usd"]        = peak
    state["positions"]           = new_positions
    state["last_processed_date"] = date
    state["max_dd_pct"]          = max_dd
    return state


# ---------------------------------------------------------------------------
# CSV writers
# ---------------------------------------------------------------------------

def _ensure_csv(path: Path, fields: list[str]) -> None:
    if not path.exists():
        path.parent.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=fields).writeheader()


def append_daily_pnl_row(
    date: str,
    state: dict[str, Any],
    daily_pnl_usd: float,
    n_entered: int,
    n_exited: int,
    dry_run: bool = False,
) -> dict[str, Any]:
    """Build and optionally write the daily_pnl.csv row. Returns the row dict."""
    init   = state["paper_equity_init"]
    nav    = state["nav_usd"]
    pct_d  = daily_pnl_usd / init * 100.0 if init > 0 else 0.0
    cum    = (nav - init) / init * 100.0   if init > 0 else 0.0
    max_dd = state.get("max_dd_pct", 0.0)
    row = {
        "date":             date,
        "nav_usd":          round(nav, 4),
        "daily_pnl_usd":    round(daily_pnl_usd, 4),
        "daily_pnl_pct":    round(pct_d, 6),
        "cumulative_pnl_pct": round(cum, 6),
        "max_dd_pct":       round(-abs(max_dd), 6),
        "n_open":           len(state["positions"]),
        "n_entered":        n_entered,
        "n_exited":         n_exited,
    }
    if not dry_run:
        _ensure_csv(DAILY_PNL_CSV, DAILY_PNL_FIELDS)
        with open(DAILY_PNL_CSV, "a", newline="", encoding="utf-8") as f:
            csv.DictWriter(f, fieldnames=DAILY_PNL_FIELDS).writerow(row)
    return row


def append_trades(
    exited: list[dict],
    date: str,
    dry_run: bool = False,
) -> None:
    """Append completed trades to trades.csv."""
    if not exited:
        return
    if not dry_run:
        _ensure_csv(TRADES_CSV, TRADES_FIELDS)
        with open(TRADES_CSV, "a", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, fieldnames=TRADES_FIELDS, extrasaction="ignore")
            for trade in exited:
                trade["exit_date"] = date
                trade["pnl_pct"]   = round(
                    trade["pnl_usd"] / trade["position_usd"] * 100.0
                    if trade["position_usd"] else 0.0, 4
                )
                w.writerow(trade)


# ---------------------------------------------------------------------------
# Per-day paper PnL JSON (read by dashboard builder)
# ---------------------------------------------------------------------------

def write_paper_pnl_json(
    date: str,
    state: dict[str, Any],
    pnl_row: dict[str, Any],
    dry_run: bool = False,
) -> None:
    """Write outputs/forward_record/paper_portfolio/{date}_paper_pnl.json."""
    payload = {
        "date":                date,
        "nav_usd":             state["nav_usd"],
        "daily_pnl_usd":       pnl_row["daily_pnl_usd"],
        "daily_pnl_pct":       pnl_row["daily_pnl_pct"],
        "cumulative_pnl_pct":  pnl_row["cumulative_pnl_pct"],
        "max_dd_pct":          pnl_row["max_dd_pct"],
        "n_open":              pnl_row["n_open"],
        "n_entered":           pnl_row["n_entered"],
        "n_exited":            pnl_row["n_exited"],
        "paper_equity_init":   state["paper_equity_init"],
        "paper_execution_status": "FORBIDDEN",
        "live_trading_status":    "FORBIDDEN",
    }
    if not dry_run:
        PAPER_DIR.mkdir(parents=True, exist_ok=True)
        out = PAPER_DIR / f"{date}_paper_pnl.json"
        out.write_text(json.dumps(payload, indent=2, ensure_ascii=False),
                       encoding="utf-8")


# ---------------------------------------------------------------------------
# Rebuild mode: list all available dates in chronological order
# ---------------------------------------------------------------------------

def list_available_dates() -> list[str]:
    """Return sorted YYYYMMDD strings for which a positions.parquet exists."""
    dates = []
    for p in FORWARD_DIR.glob("*_positions.parquet"):
        stem = p.stem  # e.g. "20260518_positions"
        date = stem.split("_")[0]
        if re.match(r"^\d{8}$", date) and date >= CLOCK_START:
            dates.append(date)
    return sorted(dates)


# ---------------------------------------------------------------------------
# Process one date
# ---------------------------------------------------------------------------

def _maybe_reset_stale_state(state: dict[str, Any], date: str) -> dict[str, Any]:
    """
    TASK-011B: If state.last_processed_date is more than STALE_RESET_DAYS before
    `date`, the prev_px values in state are stale (e.g. cache-era April 30 prices).
    Reset positions list to empty so compute_daily_mtm treats all today's positions
    as new entries (PnL=0, entry_px=today_live_price).
    The NAV, peak, and max_dd are preserved — only prev_px is invalidated.
    """
    last_proc = state.get("last_processed_date")
    if not last_proc:
        return state
    try:
        from datetime import datetime as _dt
        d_last = _dt.strptime(str(last_proc), "%Y%m%d")
        d_now  = _dt.strptime(str(date),      "%Y%m%d")
        gap    = (d_now - d_last).days
    except Exception:
        return state
    if gap > STALE_RESET_DAYS:
        print(f"  STALE_STATE_RESET: gap={gap}d > {STALE_RESET_DAYS}d — "
              f"clearing prev_px to avoid {gap}-day catch-up PnL spike")
        state = dict(state)
        state["positions"] = []   # forces all positions to be treated as new entries
    return state


def process_date(date: str, state: dict, dry_run: bool) -> dict[str, Any]:
    """
    Process one date: load parquet, compute MTM, update state, write outputs.
    Returns result dict with status info.
    """
    rows = load_positions_parquet(date)
    if rows is None:
        return {"status": "SKIP", "reason": f"no parquet for {date}"}

    # TASK-011B: detect stale state (cache-era prev_px used against live prices).
    # If the gap between state.last_processed_date and today exceeds STALE_RESET_DAYS,
    # treat ALL positions as new entries (PnL=0) and reseed last_px from today's data.
    # This prevents the "28-day catch-up" spike on the first live-price run.
    state = _maybe_reset_stale_state(state, date)

    mtm = compute_daily_mtm(state, rows)
    state = update_state(state, mtm["daily_pnl_usd"], mtm["new_positions"], date)

    pnl_row = append_daily_pnl_row(
        date, state, mtm["daily_pnl_usd"],
        len(mtm["entered"]), len(mtm["exited"]), dry_run
    )
    append_trades(mtm["exited"], date, dry_run)
    write_paper_pnl_json(date, state, pnl_row, dry_run)

    warnings = check_exposure(state["positions"])
    for w in warnings:
        print(f"  WARNING: {w}")

    return {
        "status":             "PASS",
        "date":               date,
        "nav_usd":            state["nav_usd"],
        "daily_pnl_usd":      pnl_row["daily_pnl_usd"],
        "daily_pnl_pct":      pnl_row["daily_pnl_pct"],
        "cumulative_pnl_pct": pnl_row["cumulative_pnl_pct"],
        "max_dd_pct":         pnl_row["max_dd_pct"],
        "n_open":             pnl_row["n_open"],
        "n_entered":          len(mtm["entered"]),
        "n_exited":           len(mtm["exited"]),
        "state":              state,
    }


# ---------------------------------------------------------------------------
# Main
# ---------------------------------------------------------------------------

def main() -> int:
    dry_run = "--dry-run" in sys.argv
    rebuild  = "--rebuild"  in sys.argv

    print("paper_portfolio_engine.py")
    print(f"  dry_run={dry_run}  rebuild={rebuild}")
    print()

    safety_self_check()

    # ---- Determine dates to process ----
    if rebuild:
        dates = list_available_dates()
        if not dates:
            print("  PAPER_PNL=SKIP (no parquet files found)")
            return 0
        print(f"  rebuild mode: processing {len(dates)} dates: {dates[0]} .. {dates[-1]}")
        # Reset state for a clean rebuild
        state = _make_initial_state()
        # Clear existing paper_portfolio outputs
        if not dry_run:
            for f in [STATE_PATH, DAILY_PNL_CSV, TRADES_CSV]:
                if f.exists():
                    f.unlink()
            for f in PAPER_DIR.glob("*_paper_pnl.json"):
                f.unlink()
    else:
        # Single-date mode
        date_arg = None
        for arg in sys.argv[1:]:
            if re.match(r"^\d{8}$", arg):
                date_arg = arg
                break
            if arg.startswith("--date"):
                # --date YYYYMMDD or --date=YYYYMMDD
                parts = arg.split("=", 1)
                if len(parts) == 2:
                    date_arg = parts[1]
                elif sys.argv.index(arg) + 1 < len(sys.argv):
                    date_arg = sys.argv[sys.argv.index(arg) + 1]
        if date_arg is None:
            # Try today in Asia/Taipei
            try:
                from datetime import datetime  # noqa: PLC0415
                import zoneinfo  # noqa: PLC0415
                date_arg = datetime.now(
                    zoneinfo.ZoneInfo("Asia/Taipei")
                ).strftime("%Y%m%d")
            except Exception:
                date_arg = datetime.utcnow().strftime("%Y%m%d")
        dates = [date_arg]
        state = load_state()

    last_result: dict[str, Any] = {}

    for date in dates:
        print(f"  processing date: {date}")
        result = process_date(date, state, dry_run)
        last_result = result

        if result["status"] == "SKIP":
            print(f"  PAPER_PNL=SKIP ({result['reason']})")
            continue

        state = result["state"]
        print(f"  nav_usd={result['nav_usd']:.4f}")
        print(f"  daily_pnl_pct={result['daily_pnl_pct']:.4f}%")
        print(f"  cumulative_pnl_pct={result['cumulative_pnl_pct']:.4f}%")
        print(f"  max_dd_pct={result['max_dd_pct']:.4f}%")
        print(f"  n_open={result['n_open']}  entered={result['n_entered']}  exited={result['n_exited']}")

    if dry_run:
        print()
        print("  PAPER_PNL=DRY_RUN (no files written)")
        print()
        print("  safety gates:")
        for k, v in SAFETY.items():
            print(f"    {k} = {v}")
        return 0

    # Persist state (only after all dates processed)
    if last_result.get("status") == "PASS":
        save_state(state)
        print()
        print(f"  PAPER_PNL=PASS")
        print()
        print("  safety gates:")
        for k, v in SAFETY.items():
            print(f"    {k} = {v}")
    elif last_result.get("status") == "SKIP":
        pass  # already printed above
    else:
        print("  PAPER_PNL=SKIP (nothing processed)")

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
