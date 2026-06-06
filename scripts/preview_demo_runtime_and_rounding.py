"""
scripts/preview_demo_runtime_and_rounding.py
TASK-014B: Integrated Demo runtime probe + instrument rounding dry-run preview.

DRY RUN — NO ORDERS SENT.  No secrets loaded.  No exchange API called.

Usage:
  python3 scripts/preview_demo_runtime_and_rounding.py              # fixture (verified)
  python3 scripts/preview_demo_runtime_and_rounding.py --unverified # show fail-closed path
  python3 scripts/preview_demo_runtime_and_rounding.py --out FILE   # also write JSON
"""
from __future__ import annotations

import io
import json
import math
import sys
from pathlib import Path

# Ensure stdout handles box-drawing characters on Windows (cp950 terminals).
if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_runtime_probe import (
    DemoRuntimeProbeResult,
    probe_demo_runtime,
    make_fixture_proof,
)
from src.demo_instrument_rules import (
    InstrumentRules,
    RoundedProposal,
    apply_instrument_rules_to_proposal,
    STOP_RISK_TOLERANCE_USD,
)
from src.demo_portfolio_risk import (
    DemoOpenPosition,
    DemoSignalCandidate,
    DemoPortfolioSizingResult,
    compute_demo_portfolio_sizing,
    KELLY_MULTIPLIER,
    MAX_OPEN_POSITIONS, MAX_LONG_POSITIONS, MAX_SHORT_POSITIONS,
    MAX_GROSS_EXPOSURE_RATIO, MAX_NET_EXPOSURE_RATIO,
    MAX_TOTAL_STOP_RISK_PCT_EQUITY, MAX_SINGLE_TRADE_RISK_SHARE,
)

# ---------------------------------------------------------------------------
# Phase 2 fixture (equity=10,000, 3 open positions, 10 candidates)
# ---------------------------------------------------------------------------

FIXTURE: dict = {
    "equity_usd":                10_000.0,
    "available_balance_usd":      6_200.0,
    "full_kelly_fraction":        0.2634,
    "demo_environment_expected":  True,
    "open_positions": [
        {"symbol": "BYBIT:BTCUSDT.P",  "side": "long",
         "quantity": 0.022, "entry_price": 95_000.0, "stop_price": 89_000.0},
        {"symbol": "BYBIT:ETHUSDT.P",  "side": "long",
         "quantity": 0.60,  "entry_price":  3_500.0, "stop_price":  3_200.0},
        {"symbol": "BYBIT:SOLUSDT.P",  "side": "short",
         "quantity": 10.0,  "entry_price":    175.0,  "stop_price":    190.0},
    ],
    "candidates": [
        {"symbol": "BYBIT:AAVEUSDT.P",  "side": "long",  "entry_price":  85.0,  "stop_price":  78.0,  "score": 0.92},
        {"symbol": "BYBIT:BNBUSDT.P",   "side": "long",  "entry_price": 620.0,  "stop_price": 570.0,  "score": 0.88},
        {"symbol": "BYBIT:DOTUSDT.P",   "side": "short", "entry_price":   7.80, "stop_price":   8.50, "score": 0.81},
        {"symbol": "BYBIT:ADAUSDT.P",   "side": "short", "entry_price":   0.45, "stop_price":   0.49, "score": 0.75},
        {"symbol": "BYBIT:LINKUSDT.P",  "side": "long",  "entry_price":  14.50, "stop_price":  13.00, "score": 0.69},
        {"symbol": "BYBIT:ARBUSDT.P",   "side": "short", "entry_price":   0.80, "stop_price":   0.88, "score": 0.62},
        {"symbol": "BYBIT:NEARUSDT.P",  "side": "long",  "entry_price":   4.20, "stop_price":   3.80, "score": 0.55},
        {"symbol": "BYBIT:OPUSDT.P",    "side": "short", "entry_price":   1.60, "stop_price":   1.76, "score": 0.48},
        {"symbol": "BYBIT:APTUSDT.P",   "side": "long",  "entry_price":   9.50, "stop_price":   8.70, "score": 0.41},
        {"symbol": "BYBIT:FTMUSDT.P",   "side": "short", "entry_price":   0.55, "stop_price":   0.61, "score": 0.35},
    ],
}

# ---------------------------------------------------------------------------
# Fixture instrument rules for every candidate symbol
# ---------------------------------------------------------------------------

FIXTURE_INSTRUMENT_RULES: dict[str, InstrumentRules] = {
    "BYBIT:AAVEUSDT.P": InstrumentRules(
        symbol="BYBIT:AAVEUSDT.P",
        qty_step=0.1,    min_qty=0.1,    max_qty=0.0,
        tick_size=0.01,  min_notional=5.0,
        price_precision=2, qty_precision=1,
    ),
    "BYBIT:BNBUSDT.P": InstrumentRules(
        symbol="BYBIT:BNBUSDT.P",
        qty_step=0.01,   min_qty=0.01,   max_qty=0.0,
        tick_size=0.01,  min_notional=5.0,
        price_precision=2, qty_precision=2,
    ),
    "BYBIT:DOTUSDT.P": InstrumentRules(
        symbol="BYBIT:DOTUSDT.P",
        qty_step=0.1,    min_qty=0.1,    max_qty=0.0,
        tick_size=0.001, min_notional=5.0,
        price_precision=3, qty_precision=1,
    ),
    "BYBIT:ADAUSDT.P": InstrumentRules(
        symbol="BYBIT:ADAUSDT.P",
        qty_step=1.0,    min_qty=1.0,    max_qty=0.0,
        tick_size=0.0001,min_notional=5.0,
        price_precision=4, qty_precision=0,
    ),
    "BYBIT:LINKUSDT.P": InstrumentRules(
        symbol="BYBIT:LINKUSDT.P",
        qty_step=0.1,    min_qty=0.1,    max_qty=0.0,
        tick_size=0.001, min_notional=5.0,
        price_precision=3, qty_precision=1,
    ),
    "BYBIT:ARBUSDT.P": InstrumentRules(
        symbol="BYBIT:ARBUSDT.P",
        qty_step=1.0,    min_qty=1.0,    max_qty=0.0,
        tick_size=0.0001,min_notional=5.0,
        price_precision=4, qty_precision=0,
    ),
    "BYBIT:NEARUSDT.P": InstrumentRules(
        symbol="BYBIT:NEARUSDT.P",
        qty_step=0.1,    min_qty=0.1,    max_qty=0.0,
        tick_size=0.001, min_notional=5.0,
        price_precision=3, qty_precision=1,
    ),
    "BYBIT:OPUSDT.P": InstrumentRules(
        symbol="BYBIT:OPUSDT.P",
        qty_step=1.0,    min_qty=1.0,    max_qty=0.0,
        tick_size=0.0001,min_notional=5.0,
        price_precision=4, qty_precision=0,
    ),
    "BYBIT:APTUSDT.P": InstrumentRules(
        symbol="BYBIT:APTUSDT.P",
        qty_step=0.1,    min_qty=0.1,    max_qty=0.0,
        tick_size=0.001, min_notional=5.0,
        price_precision=3, qty_precision=1,
    ),
    "BYBIT:FTMUSDT.P": InstrumentRules(
        symbol="BYBIT:FTMUSDT.P",
        qty_step=1.0,    min_qty=1.0,    max_qty=0.0,
        tick_size=0.0001,min_notional=5.0,
        price_precision=4, qty_precision=0,
    ),
}


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _f(v: float, dec: int = 2) -> str:
    try:
        fv = float(v)
        return "---" if not math.isfinite(fv) else f"${fv:,.{dec}f}"
    except Exception:
        return str(v)


def _build_phase2(data: dict):
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


# ---------------------------------------------------------------------------
# Print functions
# ---------------------------------------------------------------------------

def _print_probe(pr: DemoRuntimeProbeResult) -> None:
    W = 72
    print()
    print("  ── Demo Runtime Probe ──")
    print(f"  demo_config_expected          : {pr.demo_config_expected}")
    print(f"  demo_runtime_verified         : {pr.demo_runtime_verified}")
    print(f"  endpoint_family               : {pr.endpoint_family or '(none)'}")
    print(f"  account_mode                  : {pr.account_mode or '(none)'}")
    print(f"  fail_closed                   : {pr.fail_closed}")
    if pr.failure_reason:
        print(f"  failure_reason                : {pr.failure_reason}")
    print(f"  no_orders_sent                : {pr.no_orders_sent}")
    print(f"  secrets_loaded                : {pr.secrets_loaded}")
    print(f"  private_order_endpoint_called : {pr.private_order_endpoint_called}")


def _print_rounding(
    sizing: DemoPortfolioSizingResult,
    rounded: list[RoundedProposal],
) -> None:
    W = 72
    accepted_rounded = [r for r in rounded if r.accepted]
    rejected_rounded = [r for r in rounded if not r.accepted]

    print("\n  ── Phase-2 Proposals Before Rounding ──")
    print(f"  accepted={sizing.n_accepted}  rejected={sizing.n_rejected}")

    print("\n  ── Instrument Rounding Results ──")
    bar = "  " + "-" * W
    print(bar)
    hdr = (f"  {'Rk':<3} {'Symbol':<22} {'Side':<6} "
           f"{'OrigQty':>9} {'RndQty':>9} "
           f"{'RndEntry':>9} {'RndStop':>9} "
           f"{'Notional':>10} {'StopRisk':>9}  Status")
    print(hdr)
    print(bar)

    for r in sorted(rounded, key=lambda x: x.rank):
        if r.accepted:
            status = "OK (rounded)"
            rq     = f"{r.rounded_quantity:.6g}"
            re     = f"{r.rounded_entry_price:.6g}"
            rs_p   = f"{r.rounded_stop_price:.6g}"
            na     = _f(r.notional_after_rounding)
            sr     = _f(r.stop_risk_after_rounding)
        else:
            status = f"REJECT: {r.reject_reason}"
            rq = re = rs_p = na = sr = "---"
        oq = f"{r.original_quantity:.6g}"
        print(
            f"  {r.rank:<3} {r.symbol:<22} {r.side:<6} "
            f"{oq:>9} {rq:>9} "
            f"{re:>9} {rs_p:>9} "
            f"{na:>10} {sr:>9}  {status}"
        )
    print(bar)

    print(f"\n  accepted after rounding : {len(accepted_rounded)}")
    print(f"  rejected by instrument  : {len(rejected_rounded)}")
    if rejected_rounded:
        for r in rejected_rounded:
            print(f"    - {r.symbol}: {r.reject_reason}")

    # Invariant verification
    print("\n  ── Invariant Verification (after rounding) ──")
    inv_ok = True

    def _chk(name: str, cond: bool, got: float, limit: float) -> None:
        nonlocal inv_ok
        tag = "OK" if cond else "VIOLATED"
        if not cond:
            inv_ok = False
        print(f"  [{tag}] {name}: {got:.6f} <= {limit}")

    # Stop-risk invariants per accepted rounded proposal
    all_stop_risk_ok = True
    for r in accepted_rounded:
        if r.stop_risk_after_rounding > r.original_stop_risk_usd + STOP_RISK_TOLERANCE_USD:
            all_stop_risk_ok = False
    print(f"  [{'OK' if all_stop_risk_ok else 'VIOLATED'}] "
          f"per-position stop_risk_after <= original (tolerance {STOP_RISK_TOLERANCE_USD})")
    if not all_stop_risk_ok:
        inv_ok = False

    all_qty_down = all(r.rounded_quantity <= r.original_quantity + 1e-12
                       for r in accepted_rounded)
    print(f"  [{'OK' if all_qty_down else 'VIOLATED'}] "
          f"per-position rounded_qty <= original_qty")
    if not all_qty_down:
        inv_ok = False

    print(f"\n  All invariants: {'PASS' if inv_ok else 'FAIL'}")


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def run_preview(
    use_fixture_proof: bool = True,
    demo_config_expected: bool = True,
    data: dict | None = None,
    out_path: str | None = None,
) -> int:
    """
    Run integrated runtime probe + rounding dry-run preview.
    Returns 0 on success, 1 if fail-closed or any hard error.
    """
    if data is None:
        data = FIXTURE

    W = 72
    print()
    print("+" + "=" * W + "+")
    print("|  DEMO TRADING - RUNTIME PROBE + INSTRUMENT ROUNDING DRY RUN" + " " * (W - 60) + "|")
    print("|  NO ORDERS SENT  |  NO SECRETS LOADED  |  NO API CALLS" + " " * (W - 53) + "|")
    print("+" + "=" * W + "+")

    # ── 1. Demo runtime probe ─────────────────────────────────────────────
    proof = make_fixture_proof() if use_fixture_proof else None
    probe_result = probe_demo_runtime(demo_config_expected, proof)
    _print_probe(probe_result)

    if not probe_result.demo_runtime_verified:
        print()
        print("  ** FAIL CLOSED: demo runtime NOT verified **")
        print(f"  reason: {probe_result.failure_reason}")
        print()
        print("  ++ DRY RUN ABORTED -- FAIL CLOSED -- NO ORDERS SENT ++")
        print()
        return 1

    # ── 2. Phase 2 portfolio sizing ───────────────────────────────────────
    open_pos, cands = _build_phase2(data)
    sizing = compute_demo_portfolio_sizing(
        equity_usd=float(data["equity_usd"]),
        available_balance_usd=float(data["available_balance_usd"]),
        full_kelly_fraction=float(data["full_kelly_fraction"]),
        open_positions=open_pos,
        candidates=cands,
        demo_environment_expected=bool(data.get("demo_environment_expected", True)),
    )

    print("\n  ── Phase-2 Kelly Risk Budget ──")
    print(f"  equity_usd                     : {_f(sizing.equity_usd)}")
    print(f"  full_kelly_fraction            : {sizing.full_kelly_fraction:.4f} "
          f"({sizing.full_kelly_fraction:.2%})")
    print(f"  kelly_multiplier               : {sizing.kelly_multiplier}  "
          "(portfolio-level, applied ONCE)")
    print(f"  portfolio_raw_kelly_budget_usd : {_f(sizing.portfolio_raw_kelly_budget_usd)}")
    print(f"  absolute_hard_cap_usd          : {_f(sizing.absolute_hard_cap_usd)}")
    print(f"  portfolio_risk_budget_usd      : {_f(sizing.portfolio_risk_budget_usd)}")
    print(f"  existing_stop_risk_usd         : {_f(sizing.existing_stop_risk_usd)}")
    print(f"  remaining_risk_budget_before   : {_f(sizing.remaining_risk_budget_before)}")
    print(f"  remaining_slots                : {sizing.remaining_slots}")
    print(f"  slot_risk_budget_usd           : {_f(sizing.slot_risk_budget_usd)}")

    # ── 3. Apply instrument rounding to accepted proposals ────────────────
    rounded: list[RoundedProposal] = []
    for p in sizing.proposals:
        if p.accepted:
            rules = FIXTURE_INSTRUMENT_RULES.get(p.symbol)
            rp = apply_instrument_rules_to_proposal(p, rules)
            rounded.append(rp)

    _print_rounding(sizing, rounded)

    # ── 4. Output JSON if requested ───────────────────────────────────────
    if out_path:
        payload = {
            "probe":   {k: v for k, v in probe_result.__dict__.items()},
            "sizing":  sizing.to_dict(),
            "rounded": [
                {
                    "symbol":                   r.symbol,
                    "side":                     r.side,
                    "score":                    r.score,
                    "rank":                     r.rank,
                    "original_quantity":        round(r.original_quantity, 8),
                    "rounded_quantity":         round(r.rounded_quantity,  8),
                    "original_entry_price":     r.original_entry_price,
                    "rounded_entry_price":      r.rounded_entry_price,
                    "original_stop_price":      r.original_stop_price,
                    "rounded_stop_price":       r.rounded_stop_price,
                    "notional_after_rounding":  round(r.notional_after_rounding, 4),
                    "stop_risk_after_rounding": round(r.stop_risk_after_rounding, 4),
                    "accepted":                 r.accepted,
                    "reject_reason":            r.reject_reason,
                }
                for r in rounded
            ],
            "no_orders_sent": True,
            "dry_run":        True,
        }
        Path(out_path).write_text(
            json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8"
        )
        print(f"\n  JSON written to: {out_path}")

    print()
    print("  ++ DRY RUN COMPLETE -- NO ORDERS SENT ++")
    print()
    return 0


def main() -> int:
    args        = sys.argv[1:]
    unverified  = "--unverified" in args
    out_path    = args[args.index("--out") + 1] if "--out" in args else None
    return run_preview(
        use_fixture_proof=not unverified,
        out_path=out_path,
    )


if __name__ == "__main__":
    raise SystemExit(main())
