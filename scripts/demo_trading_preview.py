"""
demo_trading_preview.py
TASK-014: Bybit Demo Trading — dry-run sizing preview (NO orders sent).

Usage:
  python3 scripts/demo_trading_preview.py            # synthetic example with test data
  python3 scripts/demo_trading_preview.py --demo-live # attempt to read from Bybit Demo API

SAFETY INVARIANTS:
  - NO orders are placed by this script, ever.
  - Demo guard verified before any sizing computation.
  - Bybit API (if --demo-live) is READ-ONLY (get_account_info, get_positions only).
  - BYBIT_API_KEY / BYBIT_API_SECRET never printed.
"""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from apps.demo_trading.kelly_sizer import (
    OpenPosition, SignalCandidate, compute_portfolio_sizing,
)
from apps.demo_trading import config as cfg


SAFETY = {
    "paper_execution_status": "FORBIDDEN",
    "live_trading_status":    "FORBIDDEN",
    "order_endpoint_called":  False,
    "bybit_write_called":     False,
}


def _print_result(result) -> None:
    print()
    print("=" * 60)
    print("DEMO TRADING PORTFOLIO SIZING PREVIEW")
    print("=" * 60)
    print(f"  demo_guard_ok:       {result.demo_guard_ok}")
    print(f"  demo_guard_detail:   {result.demo_guard_detail}")
    print()
    print("  ── Portfolio State ──")
    print(f"  equity_usd:          ${result.equity_usd:,.2f}")
    print(f"  available_balance:   ${result.available_balance_usd:,.2f}")
    print(f"  n_open:              {result.n_open}  (long={result.n_long_open}, short={result.n_short_open})")
    print(f"  available_slots:     {result.available_slots}")
    print()
    print("  ── Kelly Risk Budget ──")
    print(f"  KELLY_MULTIPLIER:    {cfg.KELLY_MULTIPLIER:.0%} (portfolio-level)")
    print(f"  total_risk_budget:   ${result.total_risk_budget_usd:,.2f}")
    print(f"  existing_stop_risk:  ${result.existing_stop_risk_usd:,.2f}")
    print(f"  remaining_budget:    ${result.remaining_risk_budget_usd:,.2f}")
    per_slot = (result.remaining_risk_budget_usd / result.available_slots
                if result.available_slots > 0 else 0)
    print(f"  per_slot_risk:       ${per_slot:,.2f}  ({result.available_slots} slots)")
    print()
    print("  ── Exposure Before ──")
    gross_r = result.current_gross_notional / result.equity_usd if result.equity_usd > 0 else 0
    net_r   = abs(result.current_net_notional) / result.equity_usd if result.equity_usd > 0 else 0
    print(f"  gross_notional:      ${result.current_gross_notional:,.2f}  ({gross_r:.2%} of equity)")
    print(f"  net_notional:        ${result.current_net_notional:,.2f}  ({net_r:.2%} of equity)")
    print()
    print(f"  ── Proposals ({len(result.proposals)} candidates) ──")
    for p in result.proposals:
        status = "✓ ACCEPTED" if p.accepted else f"✗ REJECTED ({p.reject_reason})"
        notional_str = f"${p.proposed_notional_usd:,.2f}" if p.accepted else "-"
        print(f"  {p.symbol:20s} {p.side:5s}  stop={p.stop_distance_pct:.2%}  "
              f"notional={notional_str:>12s}  {status}")
    print()
    print("  ── Exposure After Proposals ──")
    print(f"  gross_notional:      ${result.proposed_gross_notional:,.2f}  "
          f"({result.proposed_gross_ratio:.2%} of equity) [cap: {cfg.MAX_GROSS_EXPOSURE_RATIO:.0%}]")
    print(f"  net_notional:        ${result.proposed_net_notional:,.2f}  "
          f"({result.proposed_net_ratio:.2%} of equity) [cap: {cfg.MAX_NET_EXPOSURE_RATIO:.0%}]")
    print()
    print(f"  ── Summary ──")
    print(f"  n_accepted: {result.n_accepted}   n_rejected: {result.n_rejected}")
    if result.reject_summary:
        for reason, count in sorted(result.reject_summary.items()):
            print(f"    rejected({count}): {reason}")
    print()
    print("  ── Safety Gates ──")
    for k, v in SAFETY.items():
        print(f"    {k} = {v}")
    print()
    print("  NOTE: This is a DRY-RUN PREVIEW ONLY. No orders have been placed.")
    print("=" * 60)


def _synthetic_demo() -> None:
    """Illustrative example: 10k equity, 3 open positions, 4 new candidates."""
    print("demo_trading_preview.py  [synthetic example mode]")
    print()

    open_positions = [
        OpenPosition("BYBIT:BTCUSDT.P", "long",   2_000.0,  95_000.0, 90_000.0),
        OpenPosition("BYBIT:ETHUSDT.P", "long",   1_500.0,  3_500.0,  3_200.0),
        OpenPosition("BYBIT:SOLUSDT.P", "short", -1_000.0,  170.0,    185.0),
    ]
    candidates = [
        SignalCandidate("BYBIT:AAVEUSDT.P", "long",   80.0,   74.0,  score=0.85),
        SignalCandidate("BYBIT:BNBUSDT.P",  "long",  620.0,  570.0,  score=0.72),
        SignalCandidate("BYBIT:DOTUSDT.P",  "short",  7.50,   8.20,  score=0.68),
        SignalCandidate("BYBIT:ADAUSDT.P",  "short",  0.42,   0.46,  score=0.55),
    ]

    result = compute_portfolio_sizing(
        equity_usd=10_000.0,
        available_balance_usd=5_800.0,
        open_positions=open_positions,
        candidates=candidates,
        demo_flag=True,
        testnet_flag=False,
    )
    _print_result(result)


def _live_demo_preview() -> None:
    """Read equity/positions from Bybit Demo API (read-only) then size candidates."""
    print("demo_trading_preview.py  [live demo API mode]")
    print()
    try:
        import config as app_config
        from src.executors.bybit import BybitExecutor
    except ImportError as e:
        print(f"  ERROR: Cannot import required modules: {e}")
        sys.exit(1)

    demo_flag    = getattr(app_config, "BYBIT_DEMO",    False)
    testnet_flag = getattr(app_config, "BYBIT_TESTNET", False)

    print(f"  BYBIT_DEMO={demo_flag}  BYBIT_TESTNET={testnet_flag}")
    if not demo_flag:
        print("  ERROR: BYBIT_DEMO is not True — refusing to connect")
        sys.exit(1)

    try:
        ex = BybitExecutor()
        acct = ex.get_account_info()
        equity    = acct.get("equity",    0.0)
        available = acct.get("available", 0.0)
        raw_positions = ex.get_positions()
    except Exception as e:
        print(f"  ERROR reading from Bybit Demo API: {e}")
        sys.exit(1)

    open_positions: list[OpenPosition] = []
    for raw in raw_positions:
        size = float(raw.get("size", 0))
        if size == 0:
            continue
        side_raw  = raw.get("side", "")
        side      = "long" if side_raw == "Buy" else "short"
        sym_raw   = raw.get("symbol", "")
        symbol    = f"BYBIT:{sym_raw}.P" if not sym_raw.startswith("BYBIT:") else sym_raw
        avg_price = float(raw.get("avgPrice", 0))
        sl_price  = float(raw.get("stopLoss", 0))
        notional  = size * avg_price * (1 if side == "long" else -1)
        if sl_price > 0 and avg_price > 0:
            open_positions.append(OpenPosition(symbol, side, notional, avg_price, sl_price))

    print(f"  equity:    ${equity:,.2f}")
    print(f"  available: ${available:,.2f}")
    print(f"  open:      {len(open_positions)} positions (with valid SL)")
    print()
    print("  No candidates provided — showing sizing capacity only.")

    result = compute_portfolio_sizing(
        equity_usd=equity,
        available_balance_usd=available,
        open_positions=open_positions,
        candidates=[],
        demo_flag=demo_flag,
        testnet_flag=testnet_flag,
    )
    _print_result(result)


def main() -> int:
    if "--demo-live" in sys.argv:
        _live_demo_preview()
    else:
        _synthetic_demo()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
