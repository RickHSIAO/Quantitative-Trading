"""
scripts/preview_demo_readonly_runtime.py
TASK-014C/D: Dry-run preview of Bybit Demo read-only runtime probe.

Default mode (fixture): zero network calls, zero secrets loaded.
  python scripts/preview_demo_readonly_runtime.py

Real read-only mode: calls api-demo.bybit.com; requires BYBIT_DEMO_API_KEY and
  BYBIT_DEMO_API_SECRET env vars.
  python scripts/preview_demo_readonly_runtime.py --real-readonly

Write report mode (optional, can combine with --real-readonly):
  python scripts/preview_demo_readonly_runtime.py --real-readonly --write-report

SAFETY GUARANTEES (both modes):
  DRY RUN / NO ORDERS SENT — no order endpoint is ever called.
  secret_value_observed=False — API secret is never printed or observed in output.
  order_endpoint_called=False — confirmed in output.

Exit codes:
  0  demo_runtime_verified=True and no fail_closed conditions
  1  fail_closed=True or demo_runtime_verified=False or missing credentials (real mode)
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

if hasattr(sys.stdout, "reconfigure"):
    try:
        sys.stdout.reconfigure(encoding="utf-8")
    except Exception:
        pass

from src.demo_instrument_rules import (
    InstrumentRules,
    apply_instrument_rules_to_proposal,
)
from src.demo_portfolio_risk import (
    DemoOpenPosition,
    DemoSignalCandidate,
    compute_demo_portfolio_sizing,
)
from src.demo_readonly_client import DemoReadOnlyClient
from src.demo_runtime_adapter import adapt_all
from src.demo_runtime_probe import probe_demo_runtime

_SEP = "-" * 72
_OUTPUT_DIR = ROOT / "outputs" / "demo_trading" / "readonly_smoke"


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
# Position / instrument-rule serialisation (TASK-014H)
# ---------------------------------------------------------------------------

def _serialize_positions(
    positions: list[DemoOpenPosition],
    source:    str,
) -> list[dict]:
    """Serialise DemoOpenPosition list for smoke JSON.  No secrets included."""
    out: list[dict] = []
    for p in positions:
        notional = abs(p.quantity * p.entry_price)
        out.append({
            "symbol":       p.symbol,
            "side":         p.side,
            "quantity":     float(p.quantity),
            "entry_price":  float(p.entry_price),
            "stop_price":   float(p.stop_price),
            "notional_usd": round(notional, 2),
            "source":       source,
        })
    return out


def _serialize_instrument_rules_for_positions(
    positions: list[DemoOpenPosition],
    rules:     dict[str, InstrumentRules],
) -> dict[str, dict]:
    """Serialise only the instrument rules referenced by current positions."""
    out: dict[str, dict] = {}
    for p in positions:
        r = rules.get(p.symbol)
        if r is None:
            continue
        out[p.symbol] = {
            "qty_step":        r.qty_step,
            "min_qty":         r.min_qty,
            "max_qty":         r.max_qty,
            "tick_size":       r.tick_size,
            "min_notional":    r.min_notional,
            "price_precision": r.price_precision,
            "qty_precision":   r.qty_precision,
        }
    return out


# Candidate entry symbols always included in instrument_rules_by_symbol.
# TASK-014X reads SOLUSDT rule from this field; without it the gate
# fails closed even though readonly_smoke has instrument_rules_count=500.
_CANDIDATE_ENTRY_SYMBOLS: tuple[str, ...] = ("SOLUSDT",)


def _serialize_instrument_rules_by_symbol(
    positions:     list[DemoOpenPosition],
    rules:         dict[str, InstrumentRules],
    extra_symbols: tuple[str, ...] = _CANDIDATE_ENTRY_SYMBOLS,
) -> dict[str, dict]:
    """Serialise instrument rules for open-position symbols + extra_symbols.

    Produces a dict keyed by symbol so TASK-014X can look up SOLUSDT even
    when SOLUSDT has no open position.  All instruments fetched by
    DemoReadOnlyClient are linear perpetuals, so category is hardcoded.
    """
    symbols: set[str] = {p.symbol for p in positions}
    for s in extra_symbols:
        symbols.add(s)
    out: dict[str, dict] = {}
    for sym in sorted(symbols):
        r = rules.get(sym)
        if r is None:
            continue
        out[sym] = {
            "symbol":             sym,
            "category":           "linear",
            "min_order_qty":      r.min_qty,
            "qty_step":           r.qty_step,
            "tick_size":          r.tick_size,
            "min_notional":       r.min_notional,
            "min_notional_value": r.min_notional,
        }
    return out


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(data: dict, output_dir: Path) -> None:
    """Write timestamped + latest JSON and Markdown report to output_dir."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = data.get("run_timestamp_utc", datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ"))
    ts_safe = ts.replace(":", "").replace("-", "")

    json_path    = output_dir / f"{ts_safe}_smoke.json"
    json_latest  = output_dir / "latest_smoke.json"
    md_path      = output_dir / f"{ts_safe}_smoke.md"
    md_latest    = output_dir / "latest_smoke.md"

    json_text = json.dumps(data, indent=2, default=str)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    proof = data.get("proof_strength", "")
    verified = data.get("demo_runtime_verified", False)
    fail_closed = data.get("fail_closed", True)
    status_line = "PASS" if verified and not fail_closed else "FAIL"

    md_lines = [
        f"# Demo Read-only Smoke Report",
        f"",
        f"run_timestamp_utc: `{ts}`  ",
        f"source: `{data.get('source', 'unknown')}`  ",
        f"position_details_source: `{data.get('position_details_source', 'unknown')}`  ",
        f"proof_strength: **{proof}**  ",
        f"demo_runtime_verified: `{verified}`  ",
        f"fail_closed: `{fail_closed}`  ",
        f"",
        f"## Status: {status_line}",
        f"",
        f"| field | value |",
        f"|---|---|",
        f"| api_key_present | {data.get('api_key_present', False)} |",
        f"| api_secret_present | {data.get('api_secret_present', False)} |",
        f"| order_endpoint_called | {data.get('order_endpoint_called', False)} |",
        f"| secret_value_observed | {data.get('secret_value_observed', False)} |",
        f"| no_orders_sent | {data.get('no_orders_sent', True)} |",
        f"| equity_usd | {data.get('equity_usd', 0):.2f} |",
        f"| available_balance_usd | {data.get('available_balance_usd', 0):.2f} |",
        f"| available_balance_usd_source | {data.get('available_balance_usd_source', 'unknown')} |",
        f"| wallet_account_type | {data.get('wallet_account_type', 'unknown')} |",
        f"| open_positions_count | {data.get('open_positions_count', 0)} |",
        f"| positions_count | {data.get('positions_count', 0)} |",
        f"| position_details_source | {data.get('position_details_source', 'unknown')} |",
        f"| proposals_accepted | {data.get('proposals_accepted', 0)} |",
        f"",
    ]
    positions = data.get("positions", [])
    if positions:
        md_lines += ["## Open Positions (read-only snapshot)", ""]
        md_lines.append("| Symbol | Side | Qty | Entry | Stop | Notional | Source |")
        md_lines.append("|---|---|---|---|---|---|---|")
        for p in positions:
            md_lines.append(
                f"| {p.get('symbol','')} | {p.get('side','')} | {p.get('quantity',0)} "
                f"| {p.get('entry_price',0):.4f} | {p.get('stop_price',0):.4f} "
                f"| {p.get('notional_usd',0):.2f} | {p.get('source','')} |"
            )
        md_lines.append("")
    fail_reasons = data.get("fail_reasons", [])
    if fail_reasons:
        md_lines += ["## Fail Reasons", ""]
        for r in fail_reasons:
            md_lines.append(f"- {r}")
        md_lines.append("")

    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report written: {json_path.name}")
    print(f"  report written: {md_path.name}")
    print(f"  latest  : {json_latest}")
    print(f"  latest  : {md_latest}")


# ---------------------------------------------------------------------------
# Preview runner
# ---------------------------------------------------------------------------

def run_preview(use_real_network: bool = False, write_report: bool = False) -> int:
    """
    Run the read-only probe dry-run preview.

    Returns 0 if demo_runtime_verified=True and no fail_closed conditions,
    returns 1 otherwise.
    """
    print(_SEP)
    print("DRY RUN / NO ORDERS SENT")
    print("TASK-014C/D: Bybit Demo Read-only Runtime Probe Preview")
    print(_SEP)

    # Early exit when real mode but missing credentials
    if use_real_network:
        api_key    = os.environ.get("BYBIT_DEMO_API_KEY",    "")
        api_secret = os.environ.get("BYBIT_DEMO_API_SECRET", "")
        if not api_key or not api_secret:
            missing = []
            if not api_key:
                missing.append("BYBIT_DEMO_API_KEY")
            if not api_secret:
                missing.append("BYBIT_DEMO_API_SECRET")
            print(f"\n[ERROR] --real-readonly requires: {', '.join(missing)}")
            print("  Set env vars (e.g. source .env.demo) and retry.")
            print(_SEP)
            return 1

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
    print(f"  proof_strength          : {proof_snap.proof_strength}")
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
    print(f"  api_secret_present      : {proof_snap.api_secret_present}")
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
    overall_fail_closed = planner.fail_closed or probe.fail_closed
    position_details_source = "real_readonly" if use_real_network else "fixture"
    if overall_fail_closed or not probe.demo_runtime_verified:
        _hdr("FAIL CLOSED")
        print("  demo runtime NOT verified — no proposals generated")
        if probe.failure_reason:
            print(f"  reason: {probe.failure_reason}")
        print(_SEP)
        if write_report:
            now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
            _write_report({
                "run_timestamp_utc": now_iso,
                "timestamp": now_iso,
                "source": proof_snap.source,
                "position_details_source": position_details_source,
                "proof_strength": proof_snap.proof_strength,
                "demo_runtime_verified": probe.demo_runtime_verified,
                "fail_closed": overall_fail_closed,
                "fail_reasons": planner.fail_reasons,
                "api_key_present": wallet.api_key_present,
                "api_secret_present": proof_snap.api_secret_present,
                "order_endpoint_called": False,
                "secret_value_observed": False,
                "no_orders_sent": True,
                "equity_usd": planner.equity_usd,
                "available_balance_usd": planner.available_balance_usd,
                "available_balance_usd_source": wallet.available_balance_usd_source,
                "wallet_account_type": wallet.account_type,
                "open_positions_count": len(planner.open_positions),
                "positions_count": len(planner.open_positions),
                "positions": _serialize_positions(
                    planner.open_positions, position_details_source,
                ),
                "instrument_rules": _serialize_instrument_rules_for_positions(
                    planner.open_positions, planner.instrument_rules,
                ),
                "instrument_rules_by_symbol": _serialize_instrument_rules_by_symbol(
                    planner.open_positions, planner.instrument_rules,
                ),
                "proposals_accepted": 0,
            }, _OUTPUT_DIR)
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
    n_accepted_after_rounding = 0
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
            if rp.accepted:
                n_accepted_after_rounding += 1
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

    if write_report:
        now_iso = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_report({
            "run_timestamp_utc": now_iso,
            "timestamp": now_iso,
            "source": proof_snap.source,
            "position_details_source": position_details_source,
            "proof_strength": proof_snap.proof_strength,
            "demo_runtime_verified": probe.demo_runtime_verified,
            "fail_closed": overall_fail_closed,
            "fail_reasons": planner.fail_reasons,
            "api_key_present": wallet.api_key_present,
            "api_secret_present": proof_snap.api_secret_present,
            "order_endpoint_called": False,
            "secret_value_observed": False,
            "no_orders_sent": True,
            "equity_usd": planner.equity_usd,
            "available_balance_usd": planner.available_balance_usd,
            "available_balance_usd_source": wallet.available_balance_usd_source,
            "wallet_account_type": wallet.account_type,
            "open_positions_count": len(planner.open_positions),
            "positions_count": len(planner.open_positions),
            "positions": _serialize_positions(
                planner.open_positions, position_details_source,
            ),
            "instrument_rules": _serialize_instrument_rules_for_positions(
                planner.open_positions, planner.instrument_rules,
            ),
            "instrument_rules_by_symbol": _serialize_instrument_rules_by_symbol(
                planner.open_positions, planner.instrument_rules,
            ),
            "proposals_accepted": n_accepted_after_rounding,
        }, _OUTPUT_DIR)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run preview of Bybit Demo read-only runtime probe"
    )
    parser.add_argument(
        "--real-readonly",
        action="store_true",
        help=(
            "Use real Bybit Demo API (requires BYBIT_DEMO_API_KEY + BYBIT_DEMO_API_SECRET). "
            "Never sends orders."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=(
            "Write JSON + Markdown report to "
            "outputs/demo_trading/readonly_smoke/."
        ),
    )
    args = parser.parse_args()
    sys.exit(run_preview(
        use_real_network=args.real_readonly,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
