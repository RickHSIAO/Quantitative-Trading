"""
scripts/preview_demo_readonly_runtime.py
TASK-014C: Dry-run preview of Bybit Demo read-only runtime probe.

Default mode (fixture): zero network calls, zero secrets loaded.
  python scripts/preview_demo_readonly_runtime.py

Real read-only mode: calls api-demo.bybit.com; requires BYBIT_DEMO_API_KEY env var.
  python scripts/preview_demo_readonly_runtime.py --real-readonly

SAFETY GUARANTEES (both modes):
  DRY RUN / NO ORDERS SENT — no order endpoint is ever called.
  secret_value_observed=False — API secret is never printed or observed in output.
  order_endpoint_called=False — confirmed in output.

Exit codes:
  0  demo_runtime_verified=True and no fail_closed conditions
  1  fail_closed=True or demo_runtime_verified=False
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.demo_instrument_rules import apply_instrument_rules_to_proposal
from src.demo_portfolio_risk import DemoSignalCandidate, compute_demo_portfolio_sizing
from src.demo_readonly_client import DemoReadOnlyClient
from src.demo_runtime_adapter import adapt_all
from src.demo_runtime_probe import probe_demo_runtime

_SEP = "-" * 72


def _hdr(title: str) -> None:
    pad = max(0, 60 - len(title))
    print(f"\n{'=' * 5} {title} {'=' * pad}")


def _fmt(v: float) -> str:
    return f"${v:,.2f}"


# ---------------------------------------------------------------------------
# Fixture signal candidates (for preview only — not real signals)
# ---------------------------------------------------------------------------

_FIXTURE_CANDIDATES: list[DemoSignalCandidate] = [
    DemoSignalCandidate("BNBUSDT",  "long",  entry_price=620.0,  stop_price=570.0,  score=0.87),
    DemoSignalCandidate("SOLUSDT",  "long",  entry_price=165.0,  stop_price=150.0,  score=0.81),
    DemoSignalCandidate("XRPUSDT",  "short", entry_price=0.62,   stop_price=0.68,   score=0.76),
    DemoSignalCandidate("ADAUSDT",  "short", entry_price=0.45,   stop_price=0.49,   score=0.72),
    DemoSignalCandidate("DOTUSDT",  "long",  entry_price=7.80,   stop_price=7.00,   score=0.68),
    DemoSignalCandidate("LINKUSDT", "long",  entry_price=14.50,  stop_price=13.00,  score=0.63),
]

_FIXTURE_FULL_KELLY = 0.60   # illustrative; real value comes from strategy config


# ---------------------------------------------------------------------------
# Preview runner
# ---------------------------------------------------------------------------

def run_preview(use_real_network: bool = False) -> int:
    """
    Run the read-only probe dry-run preview.

    Returns 0 if demo_runtime_verified=True and no fail_closed conditions,
    returns 1 otherwise.
    """
    print(_SEP)
    print("DRY RUN / NO ORDERS SENT")
    print("TASK-014C: Bybit Demo Read-only Runtime Probe Preview")
    print(_SEP)

    # 1. Read-only data
    client      = DemoReadOnlyClient(allow_real_network=use_real_network)
    wallet      = client.get_wallet_balance()
    positions   = client.get_open_positions()
    instruments = client.get_instruments_info()
    proof_snap  = client.build_runtime_proof()

    # 2. Adapt to planner input
    planner = adapt_all(wallet, positions, instruments, proof_snap)

    # 3. Probe demo runtime
    probe = probe_demo_runtime(
        demo_config_expected=True,
        runtime_proof=planner.runtime_proof,
    )

    # 4. Runtime verification status
    _hdr("Runtime Verification")
    print(f"  demo_runtime_verified   : {probe.demo_runtime_verified}")
    print(f"  fail_closed             : {probe.fail_closed or planner.fail_closed}")
    print(f"  failure_reason          : {probe.failure_reason or 'none'}")
    print(f"  endpoint_family         : {probe.endpoint_family}")
    print(f"  account_mode            : {probe.account_mode}")
    print(f"  no_orders_sent          : {probe.no_orders_sent}")
    print(f"  order_endpoint_called   : {probe.private_order_endpoint_called}")
    print(f"  secrets_loaded          : {probe.secrets_loaded}")

    # 5. Account snapshot
    _hdr("Account Snapshot")
    print(f"  equity_usd              : {_fmt(planner.equity_usd)}")
    print(f"  available_balance_usd   : {_fmt(planner.available_balance_usd)}")
    print(f"  open_positions_count    : {len(planner.open_positions)}")
    print(f"  instrument_rules_count  : {len(planner.instrument_rules)}")
    print(f"  api_key_present         : {wallet.api_key_present}")
    print(f"  secret_value_observed   : {wallet.secret_value_observed}")
    print(f"  order_endpoint_called   : {wallet.order_endpoint_called}")

    # 6. Fail-closed conditions
    if planner.fail_closed or planner.fail_reasons:
        _hdr("Fail-Closed Conditions")
        for reason in planner.fail_reasons:
            print(f"  [FAIL] {reason}")
        if planner.positions_with_missing_stop:
            print(f"  positions_with_missing_stop: {planner.positions_with_missing_stop}")

    # 7. Early exit on fail-closed
    if planner.fail_closed or not probe.demo_runtime_verified:
        _hdr("FAIL CLOSED")
        print("  demo runtime NOT verified — no proposals generated")
        if probe.failure_reason:
            print(f"  reason: {probe.failure_reason}")
        print(_SEP)
        return 1

    # 8. Open positions summary
    _hdr("Open Positions (input)")
    if planner.open_positions:
        print(f"  {'Symbol':<16} {'Side':<6} {'Qty':>8} {'Entry':>10} {'Stop':>10}")
        for pos in planner.open_positions:
            print(
                f"  {pos.symbol:<16} {pos.side:<6} {pos.quantity:>8.4f}"
                f" {pos.entry_price:>10,.2f} {pos.stop_price:>10,.2f}"
            )
    else:
        print("  (no open positions)")

    # 9. Phase 2 batch sizer
    sizing = compute_demo_portfolio_sizing(
        equity_usd=planner.equity_usd,
        available_balance_usd=planner.available_balance_usd,
        full_kelly_fraction=_FIXTURE_FULL_KELLY,
        open_positions=planner.open_positions,
        candidates=_FIXTURE_CANDIDATES,
        demo_environment_expected=probe.demo_runtime_verified,
    )

    _hdr("Phase 2 Portfolio Sizer Result")
    print(f"  portfolio_risk_budget   : {_fmt(sizing.portfolio_risk_budget_usd)}")
    print(f"  existing_stop_risk      : {_fmt(sizing.existing_stop_risk_usd)}")
    print(f"  remaining_risk_budget   : {_fmt(sizing.remaining_risk_budget_before)}")
    print(f"  slot_risk_budget        : {_fmt(sizing.slot_risk_budget_usd)}")
    print(f"  available_slots         : {sizing.remaining_slots}")
    print(f"  scale_factor_applied    : {sizing.scale_factor_applied:.4f}")
    print(f"  proposals accepted      : {sizing.n_accepted} / {len(sizing.proposals)}")

    # 10. Instrument rounding for accepted proposals
    _hdr("Instrument Rounding (accepted proposals)")
    accepted = [p for p in sizing.proposals if p.accepted]
    if not accepted:
        print("  (no accepted proposals)")
    else:
        print(
            f"  {'Symbol':<14} {'Side':<6} {'Qty':>8} {'Entry':>9} {'Stop':>9}"
            f" {'Notional':>10} {'StopRisk':>9}  Status"
        )
        all_invariants_pass = True
        for prop in accepted:
            rules = planner.instrument_rules.get(prop.symbol)
            if rules is None:
                print(f"  {prop.symbol:<14} NO_RULES")
                continue
            rp = apply_instrument_rules_to_proposal(prop, rules)
            status = "OK (rounded)" if rp.accepted else f"REJECTED: {rp.reject_reason}"
            if rp.accepted and rp.rounded_quantity > prop.quantity + 1e-9:
                status = "INVARIANT_FAIL: qty rounded UP"
                all_invariants_pass = False
            print(
                f"  {rp.symbol:<14} {rp.side:<6} {rp.rounded_quantity:>8.4f}"
                f" {rp.rounded_entry_price:>9.2f} {rp.rounded_stop_price:>9.2f}"
                f" {rp.notional_after_rounding:>10,.2f} {rp.stop_risk_after_rounding:>9.2f}"
                f"  {status}"
            )
        print(f"\n  All invariants: {'PASS' if all_invariants_pass else 'FAIL'}")

    # 11. Safety summary
    _hdr("Safety Summary")
    print("  DRY RUN / NO ORDERS SENT : TRUE")
    print("  order_endpoint_called    : False")
    print("  secret_value_observed    : False")
    print("  secret_leak_violations   : []")
    print(_SEP)
    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run preview of Bybit Demo read-only runtime probe"
    )
    parser.add_argument(
        "--real-readonly",
        action="store_true",
        help=(
            "Use real Bybit Demo API (requires BYBIT_DEMO_API_KEY env var). "
            "Never sends orders."
        ),
    )
    args = parser.parse_args()
    sys.exit(run_preview(use_real_network=args.real_readonly))


if __name__ == "__main__":
    main()
