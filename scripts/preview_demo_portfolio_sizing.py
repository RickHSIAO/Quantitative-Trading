"""
preview_demo_portfolio_sizing.py
TASK-014: Bybit Demo — batch portfolio Kelly sizing dry-run preview.

DRY RUN — NO ORDERS SENT. No secrets loaded. No Bybit API called.

Usage:
  python3 scripts/preview_demo_portfolio_sizing.py            # built-in fixture
  python3 scripts/preview_demo_portfolio_sizing.py --json IN  # load from JSON file
  python3 scripts/preview_demo_portfolio_sizing.py --out FILE # write JSON to FILE
"""
from __future__ import annotations

import json, math, sys, io
from pathlib import Path

# Ensure stdout can handle the box-drawing / check-mark characters on Windows.
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_portfolio_risk import (
    DemoOpenPosition, DemoSignalCandidate, DemoPortfolioSizingResult,
    compute_demo_portfolio_sizing,
    KELLY_MULTIPLIER, MAX_OPEN_POSITIONS, MAX_LONG_POSITIONS, MAX_SHORT_POSITIONS,
    MAX_GROSS_EXPOSURE_RATIO, MAX_NET_EXPOSURE_RATIO,
    MAX_TOTAL_STOP_RISK_PCT_EQUITY, MAX_SINGLE_TRADE_RISK_SHARE,
    MAX_SINGLE_POSITION_NOTIONAL_PCT,
)

# ---------------------------------------------------------------------------
# Canonical fixture: equity = 10,000, 3 open, 10 candidates
# full_kelly_fraction = 0.2634 (Crypto WR=56.9%, R=1.41 → f*≈26.3%)
# portfolio_budget = 10000 × 0.2634 × 0.4 = $1,053.60  (< 25% hard cap)
# ---------------------------------------------------------------------------
FIXTURE: dict = {
    "equity_usd":             10_000.0,
    "available_balance_usd":   6_200.0,
    "full_kelly_fraction":     0.2634,
    "demo_environment_expected": True,
    "open_positions": [
        {"symbol": "BYBIT:BTCUSDT.P", "side": "long",
         "quantity": 0.022, "entry_price": 95_000.0, "stop_price": 89_000.0},
        {"symbol": "BYBIT:ETHUSDT.P", "side": "long",
         "quantity": 0.60,  "entry_price":  3_500.0, "stop_price":  3_200.0},
        {"symbol": "BYBIT:SOLUSDT.P", "side": "short",
         "quantity": 10.0,  "entry_price":   175.0,  "stop_price":   190.0},
    ],
    "candidates": [
        {"symbol": "BYBIT:AAVEUSDT.P", "side": "long",  "entry_price":  85.0,  "stop_price":  78.0,  "score": 0.92},
        {"symbol": "BYBIT:BNBUSDT.P",  "side": "long",  "entry_price": 620.0,  "stop_price": 570.0,  "score": 0.88},
        {"symbol": "BYBIT:DOTUSDT.P",  "side": "short", "entry_price":   7.80, "stop_price":   8.50, "score": 0.81},
        {"symbol": "BYBIT:ADAUSDT.P",  "side": "short", "entry_price":   0.45, "stop_price":   0.49, "score": 0.75},
        {"symbol": "BYBIT:LINKUSDT.P", "side": "long",  "entry_price":  14.50, "stop_price":  13.00, "score": 0.69},
        {"symbol": "BYBIT:ARBUSDT.P",  "side": "short", "entry_price":   0.80, "stop_price":   0.88, "score": 0.62},
        {"symbol": "BYBIT:NEARUSDT.P", "side": "long",  "entry_price":   4.20, "stop_price":   3.80, "score": 0.55},
        {"symbol": "BYBIT:OPUSDT.P",   "side": "short", "entry_price":   1.60, "stop_price":   1.76, "score": 0.48},
        {"symbol": "BYBIT:APTUSDT.P",  "side": "long",  "entry_price":   9.50, "stop_price":   8.70, "score": 0.41},
        {"symbol": "BYBIT:FTMUSDT.P",  "side": "short", "entry_price":   0.55, "stop_price":   0.61, "score": 0.35},
    ],
}


def _load(path: str | None) -> dict:
    return json.loads(Path(path).read_text(encoding="utf-8")) if path else FIXTURE


def _build(data: dict):
    open_pos = [
        DemoOpenPosition(p["symbol"], p["side"], float(p["quantity"]),
                         float(p["entry_price"]), float(p["stop_price"]))
        for p in data.get("open_positions", [])
    ]
    cands = [
        DemoSignalCandidate(c["symbol"], c["side"], float(c["entry_price"]),
                            float(c["stop_price"]), float(c.get("score", 0.0)))
        for c in data.get("candidates", [])
    ]
    return open_pos, cands


def _f(v, pre="$", dec=2):
    try:
        fv = float(v)
        if not math.isfinite(fv):
            return str(v)
        return f"{pre}{fv:,.{dec}f}"
    except Exception:
        return str(v)


def print_result(r: DemoPortfolioSizingResult) -> None:
    eq = r.equity_usd
    W  = 72

    def bar(): print("  " + "─" * W)

    print()
    print("╔" + "═" * W + "╗")
    print("║  DEMO TRADING — PORTFOLIO SIZING DRY RUN / NO ORDERS SENT" + " " * (W - 57) + "║")
    print("╚" + "═" * W + "╝")

    print("\n  ── Environment ──")
    print(f"  demo_environment_expected : {r.demo_environment_expected}")
    print("  ⚠  Phase 3 note: runtime API-level environment probe not yet wired ⚠")

    print("\n  ── Portfolio Inputs ──")
    print(f"  equity_usd                : {_f(eq)}")
    print(f"  available_balance_usd     : {_f(r.available_balance_usd)}")
    print(f"  full_kelly_fraction       : {r.full_kelly_fraction:.4f} "
          f"({r.full_kelly_fraction:.2%})")
    print(f"  kelly_multiplier          : {r.kelly_multiplier}  "
          "(portfolio-level — applied ONCE to whole portfolio, not per trade)")

    print("\n  ── Kelly Risk Budget ──")
    print(f"  portfolio_raw_kelly_budget_usd  : {_f(r.portfolio_raw_kelly_budget_usd)}"
          f"  (equity × {r.full_kelly_fraction:.4f} × {r.kelly_multiplier})")
    print(f"  absolute_hard_cap_usd          : {_f(r.absolute_hard_cap_usd)}"
          f"  ({MAX_TOTAL_STOP_RISK_PCT_EQUITY:.0%} of equity)")
    cap_tag = "  ← CAP APPLIED" if r.hard_cap_applied else ""
    print(f"  portfolio_risk_budget_usd      : {_f(r.portfolio_risk_budget_usd)}"
          f"{cap_tag}")
    print(f"  existing_stop_risk_usd         : {_f(r.existing_stop_risk_usd)}")
    print(f"  remaining_risk_budget_before   : {_f(r.remaining_risk_budget_before)}")
    print(f"  remaining_slots                : {r.remaining_slots}")
    print(f"  slot_risk_budget_usd           : {_f(r.slot_risk_budget_usd)}"
          f"  (remaining / slots)")
    print(f"  MAX_SINGLE_TRADE_RISK_SHARE    : {MAX_SINGLE_TRADE_RISK_SHARE:.0%}"
          f"  per candidate cap: {_f(r.portfolio_risk_budget_usd * MAX_SINGLE_TRADE_RISK_SHARE)}")
    if r.scale_factor_applied < 1.0:
        print(f"  ⚠ scale_factor_applied         : {r.scale_factor_applied:.6f}"
              "  (preliminary total exceeded remaining budget)")

    print("\n  ── Position Limits ──")
    print(f"  MAX_OPEN={MAX_OPEN_POSITIONS}  MAX_LONG={MAX_LONG_POSITIONS}  "
          f"MAX_SHORT={MAX_SHORT_POSITIONS}")
    print(f"  current: n_open={r.n_open}  n_long={r.n_long_open}  "
          f"n_short={r.n_short_open}  slots_left={r.remaining_slots}")

    print("\n  ── Current Exposure ──")
    print(f"  gross : {_f(r.current_gross_notional)}"
          f"  ({r.current_gross_ratio:.2%})  [cap: {MAX_GROSS_EXPOSURE_RATIO:.0%}]")
    print(f"  net   : {_f(r.current_net_notional)}"
          f"  ({r.current_net_ratio:.2%})  [cap: {MAX_NET_EXPOSURE_RATIO:.0%}]")

    bar()
    col = (f"  {'Rank':<4} {'Symbol':<22} {'Side':<6} {'Score':>6} "
           f"{'Stop%':>6} {'DesiredRisk':>11} {'SlotBudget':>10} "
           f"{'AllocRisk':>9} {'Notional':>10} {'Qty':>9}  Status")
    print(col)
    bar()
    for p in r.proposals:
        if p.accepted:
            status = "✓ OK"
            notional = _f(p.proposed_notional_usd)
            qty      = f"{p.quantity:.5f}"
            alloc    = _f(p.allocated_stop_risk_usd)
        else:
            status   = f"✗ {p.reject_reason}"
            notional = alloc = qty = "—"
        print(
            f"  {p.rank:<4} {p.symbol:<22} {p.side:<6} {p.score:>6.3f} "
            f"{p.stop_distance_pct:>5.2%} "
            f"{_f(p.candidate_desired_risk_usd, pre='$', dec=2):>11} "
            f"{_f(p.slot_risk_budget_usd, pre='$', dec=2):>10} "
            f"{alloc:>9} {notional:>10} {qty:>9}  {status}"
        )
    bar()

    print("\n  ── Proposed Exposure After ──")
    print(f"  gross : {_f(r.proposed_gross_notional)}"
          f"  ({r.proposed_gross_ratio:.2%})  [cap: {MAX_GROSS_EXPOSURE_RATIO:.0%}]")
    print(f"  net   : {_f(r.proposed_net_notional)}"
          f"  ({r.proposed_net_ratio:.2%})  [cap: {MAX_NET_EXPOSURE_RATIO:.0%}]")
    print(f"  proposed_new_stop_risk_usd    : {_f(r.proposed_new_stop_risk_usd)}")
    print(f"  remaining_risk_budget_after   : {_f(r.remaining_risk_budget_after)}")

    # ── Invariant checks ──
    print("\n  ── Invariant Verification ──")
    inv_ok = True
    def _chk(name, cond, got, limit):
        nonlocal inv_ok
        tag = "✓" if cond else "✗ VIOLATED"
        if not cond: inv_ok = False
        print(f"  {tag} {name}: {got:.4f} {'<=' if cond else '>'} {limit}")

    _chk("existing+proposed <= budget",
         r.existing_stop_risk_usd + r.proposed_new_stop_risk_usd
         <= r.portfolio_risk_budget_usd + 1e-6,
         r.existing_stop_risk_usd + r.proposed_new_stop_risk_usd,
         r.portfolio_risk_budget_usd)
    _chk("gross_ratio <= cap", r.proposed_gross_ratio <= MAX_GROSS_EXPOSURE_RATIO + 1e-6,
         r.proposed_gross_ratio, MAX_GROSS_EXPOSURE_RATIO)
    _chk("net_ratio <= cap", r.proposed_net_ratio <= MAX_NET_EXPOSURE_RATIO + 1e-6,
         r.proposed_net_ratio, MAX_NET_EXPOSURE_RATIO)
    accepted = [p for p in r.proposals if p.accepted]
    n_al = len(accepted)
    n_ll = sum(1 for p in accepted if p.side == "long")
    n_sl = n_al - n_ll
    _chk("accepted_total <= 10", n_al <= MAX_OPEN_POSITIONS, float(n_al), float(MAX_OPEN_POSITIONS))
    _chk("accepted_long <= 5",   n_ll <= MAX_LONG_POSITIONS,  float(n_ll), float(MAX_LONG_POSITIONS))
    _chk("accepted_short <= 5",  n_sl <= MAX_SHORT_POSITIONS, float(n_sl), float(MAX_SHORT_POSITIONS))
    if inv_ok:
        print("  All invariants: PASS")
    else:
        print("  ⚠ INVARIANT FAILURE — review sizing logic")

    print(f"\n  ── Summary ──")
    print(f"  accepted={r.n_accepted}  rejected={r.n_rejected}")
    if r.reject_summary:
        for reason, count in sorted(r.reject_summary.items()):
            print(f"    ✗ {count}× {reason}")
    if r.warnings:
        print()
        for w in r.warnings:
            print(f"  ⚠ [{w.code}] {w.message}")
    print()
    print("  ══ DRY RUN COMPLETE — NO ORDERS SENT ══")
    print()


def main() -> int:
    args     = sys.argv[1:]
    json_in  = args[args.index("--json") + 1] if "--json" in args else None
    out_path = args[args.index("--out")  + 1] if "--out"  in args else None

    data = _load(json_in)
    open_pos, cands = _build(data)

    result = compute_demo_portfolio_sizing(
        equity_usd=float(data["equity_usd"]),
        available_balance_usd=float(data["available_balance_usd"]),
        full_kelly_fraction=float(data["full_kelly_fraction"]),
        open_positions=open_pos,
        candidates=cands,
        demo_environment_expected=bool(data.get("demo_environment_expected", True)),
    )
    print_result(result)

    if out_path:
        Path(out_path).write_text(
            json.dumps(result.to_dict(), indent=2, ensure_ascii=False),
            encoding="utf-8",
        )
        print(f"  JSON written to: {out_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
