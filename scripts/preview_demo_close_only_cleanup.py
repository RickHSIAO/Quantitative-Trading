"""
scripts/preview_demo_close_only_cleanup.py
TASK-014F: Dry-run preview of Demo close-only cleanup plan.

Default mode (fixture): zero network calls, zero secrets loaded.
  python scripts/preview_demo_close_only_cleanup.py

Read from latest reconciliation report:
  python scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation

Write cleanup report:
  python scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation --write-report

Human confirmation gate (generates execute_ready=True when all checks pass):
  python scripts/preview_demo_close_only_cleanup.py --from-latest-reconciliation \\
      --confirm-token CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD

NOTE: execute_ready=True does NOT send any order.
      No sender is implemented in TASK-014F.
      no_orders_sent=True always.

SAFETY GUARANTEES (all modes):
  DRY RUN / NO ORDERS SENT    — no sender is implemented.
  NO POSITIONS MODIFIED       — purely observational.
  secret_value_observed       — always False.
  action_type                 — always MANUAL_CONFIRMATION_REQUIRED.

Exit codes:
  0  Plan generated; may or may not have execute_ready=True.
  1  Fail-closed: reconciliation file missing, unverified, or stale.
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

from src.demo_close_only_cleanup import (
    MAX_SNAPSHOT_AGE_HOURS,
    CleanupPlan,
    plan_cleanup,
)
from src.demo_portfolio_risk import DemoOpenPosition

_SEP = "-" * 72
_DEFAULT_RECONCILE_DIR = ROOT / "outputs" / "demo_trading" / "reconciliation"
_DEFAULT_CLEANUP_DIR   = ROOT / "outputs" / "demo_trading" / "close_only_cleanup"


# ---------------------------------------------------------------------------
# Fixture positions — approximates real Demo account state
# (1 long + 7 short: short_count > MAX_SHORT=5, cleanup_needed=True)
# ---------------------------------------------------------------------------

_FIXTURE_POSITIONS_LEGACY: list[DemoOpenPosition] = [
    DemoOpenPosition("BTCUSDT",  "long",  0.02,   67_000.0, 65_000.0),
    DemoOpenPosition("ETHUSDT",  "short", 0.50,    3_500.0,  3_700.0),
    DemoOpenPosition("BNBUSDT",  "short", 2.00,      600.0,    640.0),
    DemoOpenPosition("SOLUSDT",  "short", 5.00,      160.0,    175.0),
    DemoOpenPosition("XRPUSDT",  "short", 500.00,      0.62,     0.68),
    DemoOpenPosition("ADAUSDT",  "short", 800.00,      0.45,     0.49),
    DemoOpenPosition("DOTUSDT",  "short",  30.00,      7.80,     8.50),
    DemoOpenPosition("LINKUSDT", "short",  20.00,     14.50,    16.00),
]

# Clean fixture: 2 positions (1 long + 1 short), no cleanup needed
_FIXTURE_POSITIONS_CLEAN: list[DemoOpenPosition] = [
    DemoOpenPosition("BTCUSDT", "long",  0.05, 67_000.0, 65_000.0),
    DemoOpenPosition("ETHUSDT", "short", 0.30,  3_500.0,  3_700.0),
]


# ---------------------------------------------------------------------------
# Reconciliation JSON loader
# ---------------------------------------------------------------------------

def load_latest_reconciliation(reconcile_dir: Path) -> dict | None:
    """
    Load latest_reconciliation.json.
    Returns None if missing or unreadable.
    """
    path = reconcile_dir / "latest_reconciliation.json"
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def _positions_from_reconciliation(rec: dict) -> list[DemoOpenPosition]:
    """Convert reconciliation positions array to DemoOpenPosition list."""
    raw = rec.get("positions", []) or []
    out: list[DemoOpenPosition] = []
    for p in raw:
        out.append(DemoOpenPosition(
            symbol=str(p.get("symbol", "")),
            side=str(p.get("side", "")),
            quantity=float(p.get("quantity", 0.0) or 0.0),
            entry_price=float(p.get("entry_price", 0.0) or 0.0),
            stop_price=float(p.get("stop_price", 0.0) or 0.0),
        ))
    return out


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(plan: CleanupPlan, output_dir: Path, ts_utc: str) -> None:
    """Write timestamped + latest JSON and Markdown cleanup reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_safe = ts_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")
    json_path   = output_dir / f"{ts_safe}_close_only_cleanup.json"
    json_latest = output_dir / "latest_close_only_cleanup.json"
    md_path     = output_dir / f"{ts_safe}_close_only_cleanup.md"
    md_latest   = output_dir / "latest_close_only_cleanup.md"

    data = plan.to_dict(timestamp_utc=ts_utc)
    json_text = json.dumps(data, indent=2, default=str)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    status = "EXECUTE_READY" if plan.execute_ready else (
        "CLEANUP_NEEDED" if plan.cleanup_needed else "NO_CLEANUP_NEEDED"
    )
    md_lines = [
        "# Demo Close-only Cleanup Report",
        "",
        f"timestamp: `{ts_utc}`  ",
        f"mode: `{plan.mode}`  ",
        f"position_details_source: `{plan.position_details_source}`  ",
        f"source_position_details_is_real: `{plan.source_position_details_is_real}`  ",
        f"demo_runtime_verified: `{plan.demo_runtime_verified}`  ",
        f"proof_strength: **{plan.proof_strength}**  ",
        "",
        f"## Status: {status}",
        "",
        "## Cleanup Summary",
        "",
        "| metric | value |",
        "|---|---|",
        f"| cleanup_needed | {plan.cleanup_needed} |",
        f"| proposed_close_count | {plan.proposed_close_count} |",
        f"| current_short_count | {plan.current_short_count} / {plan.target_short_count} |",
        f"| current_long_count | {plan.current_long_count} / {plan.target_long_count} |",
        f"| current_open_count | {plan.current_open_count} / {plan.target_open_count} |",
        f"| equity_usd | {plan.equity_usd:.2f} |",
        f"| available_balance_usd | {plan.available_balance_usd:.2f} |",
        f"| snapshot_fresh | {plan.snapshot_fresh} |",
        "",
    ]
    if plan.cleanup_reasons:
        md_lines += ["## Cleanup Reasons", ""]
        for r in plan.cleanup_reasons:
            md_lines.append(f"- {r}")
        md_lines.append("")
    if plan.suggested_close_candidates:
        md_lines += ["## Suggested Close Candidates", ""]
        md_lines.append(
            "| Rank | Symbol | Side | Qty | Entry | Stop | Notional | StopRisk |"
        )
        md_lines.append("|---|---|---|---|---|---|---|---|")
        for c in sorted(plan.suggested_close_candidates, key=lambda x: x.close_rank):
            md_lines.append(
                f"| {c.close_rank} | {c.symbol} | {c.side} | {c.quantity} "
                f"| {c.entry_price:.2f} | {c.stop_price:.2f} "
                f"| {c.notional_usd:.2f} | {c.stop_risk_usd:.2f} |"
            )
        md_lines.append("")
    if plan.close_payload_previews:
        md_lines += ["## Close Payload Preview (PLANNING ONLY)", ""]
        for p in plan.close_payload_previews:
            md_lines += [
                f"### {p.symbol}",
                f"- side_to_close: `{p.side_to_close}`",
                f"- close_order_side: `{p.close_order_side}`",
                f"- qty: `{p.qty}`",
                f"- order_type: `{p.order_type}`",
                f"- reduce_only: `{p.reduce_only}`",
                f"- confirmation_required: `{p.confirmation_required}`",
                f"- no_orders_sent: `{p.no_orders_sent}`",
                "",
            ]
    md_lines += [
        "## Confirmation Gate",
        "",
        f"- confirmation_required: `{plan.confirmation_required}`",
        f"- confirm_token_expected_pattern: `{plan.confirm_token_expected_pattern}`",
        f"- confirm_token_valid: `{plan.confirm_token_valid}`",
        f"- execute_ready: `{plan.execute_ready}`",
        "",
        "## Safety Invariants",
        "",
        f"- action_type: `{plan.action_type}`",
        f"- no_orders_sent: `{plan.no_orders_sent}`",
        f"- no_position_modified: `{plan.no_position_modified}`",
        f"- order_endpoint_called: `{plan.order_endpoint_called}`",
        f"- secret_value_observed: `{plan.secret_value_observed}`",
        "",
        "> **IMPORTANT**: execute_ready=True does NOT send orders.",
        "> No sender is implemented. To send, implement TASK-014G.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report written: {json_path.name}")
    print(f"  report written: {md_path.name}")
    print(f"  latest  : {json_latest}")
    print(f"  latest  : {md_latest}")


# ---------------------------------------------------------------------------
# Display helpers
# ---------------------------------------------------------------------------

def _hdr(title: str) -> None:
    pad = max(0, 60 - len(title))
    print(f"\n{'=' * 5} {title} {'=' * pad}")


def _print_plan(plan: CleanupPlan) -> None:
    _hdr("Cleanup Summary")
    print(f"  cleanup_needed         : {plan.cleanup_needed}")
    print(f"  proposed_close_count   : {plan.proposed_close_count}")
    print(f"  current_short_count    : {plan.current_short_count} / {plan.target_short_count}")
    print(f"  current_long_count     : {plan.current_long_count} / {plan.target_long_count}")
    print(f"  current_open_count     : {plan.current_open_count} / {plan.target_open_count}")
    print(f"  equity_usd             : ${plan.equity_usd:,.2f}")
    print(f"  available_balance_usd  : ${plan.available_balance_usd:,.2f}")
    print(f"  snapshot_fresh         : {plan.snapshot_fresh}")
    print(f"  demo_runtime_verified  : {plan.demo_runtime_verified}")
    print(f"  proof_strength         : {plan.proof_strength}")

    if plan.cleanup_reasons:
        _hdr("Cleanup Reasons")
        for r in plan.cleanup_reasons:
            print(f"  - {r}")

    if plan.suggested_close_candidates:
        _hdr("Suggested Close Candidates (PLANNING ONLY)")
        print(
            f"  {'Rank':<5} {'Symbol':<12} {'Side':<6} {'Qty':>10} "
            f"{'Entry':>10} {'Stop':>10} {'Notional':>10} {'StopRisk':>9}"
        )
        for c in sorted(plan.suggested_close_candidates, key=lambda x: x.close_rank):
            print(
                f"  {c.close_rank:<5} {c.symbol:<12} {c.side:<6} {c.quantity:>10.4f} "
                f"{c.entry_price:>10,.2f} {c.stop_price:>10,.2f} "
                f"{c.notional_usd:>10,.2f} {c.stop_risk_usd:>9,.2f}"
            )

    if plan.close_payload_previews:
        _hdr("Close Payload Preview (PLANNING ONLY — no orders sent)")
        for p in plan.close_payload_previews:
            print(f"  {p.symbol}:")
            print(f"    close_order_side  : {p.close_order_side}")
            print(f"    qty               : {p.qty}")
            print(f"    order_type        : {p.order_type}")
            print(f"    reduce_only       : {p.reduce_only}")
            print(f"    category          : {p.category}")
            print(f"    position_idx      : {p.position_idx}")
            print(f"    snapshot_hash     : {p.source_position_snapshot_hash}")
            print(f"    confirmation_req  : {p.confirmation_required}")
            print(f"    no_orders_sent    : {p.no_orders_sent}")

    _hdr("Confirmation Gate")
    print(f"  confirmation_required        : {plan.confirmation_required}")
    print(f"  confirm_token_pattern        : {plan.confirm_token_expected_pattern}")
    print(f"  confirm_token_valid          : {plan.confirm_token_valid}")
    print(f"  position_details_source      : {plan.position_details_source}")
    print(f"  source_position_details_is_real: {plan.source_position_details_is_real}")
    print(f"  execute_ready                : {plan.execute_ready}")
    if not plan.execute_ready:
        gates = []
        if not plan.cleanup_needed:
            gates.append("cleanup_needed=False")
        if not plan.snapshot_fresh:
            gates.append("snapshot_stale")
        if not plan.confirm_token_valid:
            gates.append("token_invalid_or_missing")
        if not plan.demo_runtime_verified:
            gates.append("demo_not_verified")
        if not plan.source_position_details_is_real:
            gates.append("position_details_source_not_real_readonly")
        print(f"  blocked_gates                : {gates}")

    _hdr("Safety Invariants")
    print("  DRY RUN / NO ORDERS SENT     : TRUE")
    print("  NO POSITIONS MODIFIED        : TRUE")
    print(f"  action_type                  : {plan.action_type}")
    print(f"  no_orders_sent               : {plan.no_orders_sent}")
    print(f"  no_position_modified         : {plan.no_position_modified}")
    print(f"  order_endpoint_called        : {plan.order_endpoint_called}")
    print(f"  secret_value_observed        : {plan.secret_value_observed}")
    if plan.execute_ready:
        print()
        print("  NOTE: execute_ready=True but NO ORDERS SENT.")
        print("  To send, implement TASK-014G close-only sender.")


# ---------------------------------------------------------------------------
# Preview runner
# ---------------------------------------------------------------------------

def run_preview(
    mode:           str  = "fixture",
    confirm_token:  str  = "",
    write_report:   bool = False,
    reconcile_dir:  Path | None = None,
    cleanup_dir:    Path | None = None,
    max_snapshot_age_hours: float = MAX_SNAPSHOT_AGE_HOURS,
) -> int:
    """
    Run the close-only cleanup dry-run preview.

    Returns 0 on success (plan generated, may have execute_ready=True).
    Returns 1 on fail-closed (missing/unverified/stale reconciliation).
    """
    _reconcile_dir = reconcile_dir or _DEFAULT_RECONCILE_DIR
    _cleanup_dir   = cleanup_dir   or _DEFAULT_CLEANUP_DIR

    print(_SEP)
    print("DRY RUN / NO ORDERS SENT / NO POSITIONS MODIFIED")
    print("TASK-014F: Demo Close-only Cleanup Preview")
    print(_SEP)

    equity_usd              = 10_000.0
    available_balance_usd   = 8_500.0
    positions               = _FIXTURE_POSITIONS_CLEAN
    demo_runtime_verified   = False
    proof_strength          = ""
    snapshot_timestamp      = ""
    report_mode             = "fixture"
    position_details_source = "fixture"

    if mode == "from_latest_reconciliation":
        rec = load_latest_reconciliation(_reconcile_dir)
        if rec is None:
            print("\n[FAIL CLOSED] latest_reconciliation.json not found or unreadable.")
            print(f"  Expected: {_reconcile_dir / 'latest_reconciliation.json'}")
            print("  Run: python scripts/preview_demo_position_reconcile.py --write-report")
            print(_SEP)
            return 1
        if not rec.get("demo_runtime_verified", False):
            print("\n[FAIL CLOSED] latest_reconciliation.json: demo_runtime_verified=False.")
            print(f"  proof_strength={rec.get('proof_strength', 'MISSING')}")
            print("  Re-run readonly smoke before reconciliation.")
            print(_SEP)
            return 1

        rec_source = str(rec.get("position_details_source", ""))
        rec_positions = rec.get("positions", None)
        # TASK-014H: reconciliation MUST have real positions; no fallback.
        if rec_source == "real_readonly":
            if not isinstance(rec_positions, list) or not rec_positions:
                print("\n[FAIL CLOSED] real_readonly reconciliation missing positions list.")
                print("  reason=missing_real_position_details")
                print(_SEP)
                return 1
            position_details_source = "real_readonly"
            positions               = _positions_from_reconciliation(rec)
        elif rec_source == "fixture":
            if not isinstance(rec_positions, list):
                print("\n[FAIL CLOSED] reconciliation positions list missing.")
                print(_SEP)
                return 1
            position_details_source = "fixture"
            positions               = (
                _positions_from_reconciliation(rec)
                if rec_positions
                else _FIXTURE_POSITIONS_CLEAN
            )
        else:
            print("\n[FAIL CLOSED] reconciliation missing position_details_source.")
            print("  reason=missing_real_position_details")
            print(_SEP)
            return 1

        snapshot_timestamp    = rec.get("timestamp", "")
        demo_runtime_verified = True
        proof_strength        = rec.get("proof_strength", "")
        equity_usd            = float(rec.get("equity_usd", 0.0))
        available_balance_usd = float(rec.get("available_balance_usd", 0.0))
        report_mode           = "from_latest_reconciliation"

        print(f"  [reconciliation] demo_runtime_verified={demo_runtime_verified}")
        print(f"  [reconciliation] proof_strength={proof_strength}")
        print(f"  [reconciliation] equity_usd={equity_usd:.2f}")
        print(f"  [reconciliation] available_balance_usd={available_balance_usd:.2f}")
        print(f"  [reconciliation] snapshot_timestamp={snapshot_timestamp}")
        print(f"  [reconciliation] position_details_source={position_details_source}")
        print(f"  [reconciliation] positions_loaded={len(positions)}")

        # Staleness pre-check for early exit
        from src.demo_close_only_cleanup import _check_snapshot_freshness
        fresh, age = _check_snapshot_freshness(snapshot_timestamp, max_snapshot_age_hours)
        if not fresh:
            age_str = f"{age:.1f}h" if age is not None else "unknown"
            print(f"\n[FAIL CLOSED] Reconciliation snapshot is stale: age={age_str}.")
            print(f"  Re-run reconciliation to refresh before requesting cleanup.")
            print(_SEP)
            return 1

    plan = plan_cleanup(
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        positions=positions,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        mode=report_mode,
        confirm_token=confirm_token,
        snapshot_timestamp_utc=snapshot_timestamp,
        max_snapshot_age_hours=max_snapshot_age_hours,
        position_details_source=position_details_source,
    )

    _print_plan(plan)
    print(_SEP)

    if write_report:
        ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_report(plan, _cleanup_dir, ts_utc)

    return 0


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run preview of Demo close-only cleanup plan"
    )
    parser.add_argument(
        "--from-latest-reconciliation",
        action="store_true",
        help=(
            "Read equity/proof state from "
            "outputs/demo_trading/reconciliation/latest_reconciliation.json. "
            "Fails closed if missing, unverified, or stale."
        ),
    )
    parser.add_argument(
        "--confirm-token",
        default="",
        metavar="TOKEN",
        help=(
            "Human confirmation token. Pattern: CONFIRM_DEMO_CLOSE_ONLY_YYYYMMDD. "
            "Required for execute_ready=True. No orders are sent even with valid token."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown report to outputs/demo_trading/close_only_cleanup/.",
    )
    args = parser.parse_args()
    mode = "from_latest_reconciliation" if args.from_latest_reconciliation else "fixture"
    sys.exit(run_preview(
        mode=mode,
        confirm_token=args.confirm_token,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
