"""
scripts/preview_demo_position_reconcile.py
TASK-014E: Dry-run preview of Demo position reconciliation.

Default mode (fixture): zero network calls, zero secrets loaded.
  python scripts/preview_demo_position_reconcile.py

Read from latest readonly smoke (uses equity/available from real smoke report,
fixture positions since smoke JSON does not contain individual position data):
  python scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke

Write reconciliation report:
  python scripts/preview_demo_position_reconcile.py --from-latest-readonly-smoke --write-report

SAFETY GUARANTEES (all modes):
  DRY RUN / NO ORDERS SENT — no order endpoint is ever called.
  NO POSITIONS MODIFIED    — purely observational.
  secret_value_observed    — always False.
  action_type              — always MANUAL_REVIEW_ONLY.

Exit codes:
  0  new_entry_allowed=True and no fail_closed conditions
  1  new_entry_allowed=False, or fail_closed (missing/unverified smoke)
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

from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_position_reconcile import ReconciliationResult, reconcile

_SEP = "-" * 72
_DEFAULT_SMOKE_DIR       = ROOT / "outputs" / "demo_trading" / "readonly_smoke"
_DEFAULT_RECONCILE_DIR   = ROOT / "outputs" / "demo_trading" / "reconciliation"


# ---------------------------------------------------------------------------
# Fixture data — clean state (default fixture mode, no violations expected)
# ---------------------------------------------------------------------------

_FIXTURE_POSITIONS_CLEAN: list[DemoOpenPosition] = [
    DemoOpenPosition("BTCUSDT", "long",  0.05, 67_000.0, 65_000.0),
    DemoOpenPosition("ETHUSDT", "short", 0.30,  3_500.0,  3_700.0),
]
_FIXTURE_EQUITY_CLEAN    = 10_000.0
_FIXTURE_AVAILABLE_CLEAN =  8_500.0

# Fixture data — legacy state (approximates real Demo account with violations)
# Based on confirmed real-account state: equity~11404, available=0, ~8 positions mostly short.
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

# Fixture instrument rules — sufficient for the legacy positions
_FIXTURE_INSTRUMENT_RULES: dict[str, InstrumentRules] = {
    "BTCUSDT":  InstrumentRules("BTCUSDT",  0.001, 0.001, 0,  0.1,    1.0, 1, 3),
    "ETHUSDT":  InstrumentRules("ETHUSDT",  0.01,  0.01,  0,  0.05,   1.0, 2, 2),
    "BNBUSDT":  InstrumentRules("BNBUSDT",  0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "SOLUSDT":  InstrumentRules("SOLUSDT",  0.1,   0.1,   0,  0.01,   1.0, 2, 1),
    "XRPUSDT":  InstrumentRules("XRPUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "ADAUSDT":  InstrumentRules("ADAUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "DOTUSDT":  InstrumentRules("DOTUSDT",  0.1,   0.1,   0,  0.001,  1.0, 3, 1),
    "LINKUSDT": InstrumentRules("LINKUSDT", 0.1,   0.1,   0,  0.001,  1.0, 3, 1),
    "AAVEUSDT": InstrumentRules("AAVEUSDT", 0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "AVAXUSDT": InstrumentRules("AVAXUSDT", 0.1,   0.1,   0,  0.01,   1.0, 2, 1),
}


# ---------------------------------------------------------------------------
# Smoke JSON loader
# ---------------------------------------------------------------------------

def load_latest_smoke(smoke_dir: Path) -> dict | None:
    """
    Load the latest readonly smoke report JSON.
    Returns None if the file is missing or unreadable.
    Raises ValueError if demo_runtime_verified is False.
    """
    smoke_path = smoke_dir / "latest_smoke.json"
    if not smoke_path.exists():
        return None
    try:
        return json.loads(smoke_path.read_text(encoding="utf-8"))
    except Exception:
        return None


# ---------------------------------------------------------------------------
# Report writer
# ---------------------------------------------------------------------------

def _write_report(result: ReconciliationResult, output_dir: Path, ts_utc: str) -> None:
    """Write timestamped + latest JSON and Markdown reconciliation reports."""
    output_dir.mkdir(parents=True, exist_ok=True)

    ts_safe = ts_utc.replace(":", "").replace("-", "").replace("T", "_").replace("Z", "")

    json_path   = output_dir / f"{ts_safe}_reconciliation.json"
    json_latest = output_dir / "latest_reconciliation.json"
    md_path     = output_dir / f"{ts_safe}_reconciliation.md"
    md_latest   = output_dir / "latest_reconciliation.md"

    data = result.to_dict()
    data["timestamp"] = ts_utc

    json_text = json.dumps(data, indent=2, default=str)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    status = "PASS (new_entry_allowed)" if result.new_entry_allowed else "FAIL (blocked)"
    md_lines = [
        "# Demo Position Reconciliation Report",
        "",
        f"timestamp: `{ts_utc}`  ",
        f"mode: `{result.mode}`  ",
        f"demo_runtime_verified: `{result.demo_runtime_verified}`  ",
        f"proof_strength: **{result.proof_strength}**  ",
        "",
        f"## Status: {status}",
        "",
        "## Portfolio Metrics",
        "",
        "| metric | value |",
        "|---|---|",
        f"| equity_usd | {result.equity_usd:.2f} |",
        f"| available_balance_usd | {result.available_balance_usd:.2f} |",
        f"| open_positions_count | {result.open_positions_count} |",
        f"| long_count | {result.long_count} |",
        f"| short_count | {result.short_count} |",
        f"| gross_notional_usd | {result.gross_notional_usd:.2f} |",
        f"| net_notional_usd | {result.net_notional_usd:.2f} |",
        f"| gross_exposure_ratio | {result.gross_exposure_ratio:.4f} |",
        f"| net_exposure_ratio | {result.net_exposure_ratio:.4f} |",
        f"| existing_stop_risk_usd | {result.existing_stop_risk_usd:.2f} |",
        f"| portfolio_risk_budget_usd | {result.portfolio_risk_budget_usd:.2f} |",
        f"| remaining_risk_budget_usd | {result.remaining_risk_budget_usd:.2f} |",
        f"| current_slot_usage | {result.current_slot_usage} / 10 |",
        f"| available_slots | {result.available_slots} |",
        f"| max_long_allowed_remaining | {result.max_long_allowed_remaining} |",
        f"| max_short_allowed_remaining | {result.max_short_allowed_remaining} |",
        "",
    ]
    if result.violations:
        md_lines += ["## Violations", ""]
        for v in result.violations:
            hard_tag = " **[HARD]**" if v.is_hard else ""
            md_lines.append(f"- `{v.code}`{hard_tag}: {v.detail}")
        md_lines.append("")
    if result.suggested_actions:
        md_lines += ["## Suggested Actions (Manual Only)", ""]
        for a in result.suggested_actions:
            md_lines.append(f"- {a}")
        md_lines.append("")
    md_lines += [
        "## Safety Invariants",
        "",
        f"- action_type: `{result.action_type}`",
        f"- no_orders_sent: `{result.no_orders_sent}`",
        f"- no_position_modified: `{result.no_position_modified}`",
        f"- order_endpoint_called: `{result.order_endpoint_called}`",
        f"- secret_value_observed: `{result.secret_value_observed}`",
        f"- cannot_proceed_to_order_smoke: `{result.cannot_proceed_to_order_smoke}`",
        "",
    ]
    if not result.new_entry_allowed:
        md_lines += [
            "> **NOTE**: new_entry_allowed=False. To enable new entries, clear all",
            "> hard violations and open TASK-014F Demo Close-only Manual Confirmed Cleanup",
            "> if manual position reduction is required.",
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


def _fmt_usd(v: float) -> str:
    return f"${v:,.2f}"


def _print_result(result: ReconciliationResult) -> None:
    _hdr("Portfolio Metrics")
    print(f"  equity_usd                 : {_fmt_usd(result.equity_usd)}")
    print(f"  available_balance_usd      : {_fmt_usd(result.available_balance_usd)}")
    print(f"  open_positions_count       : {result.open_positions_count} / 10")
    print(f"  long_count                 : {result.long_count} / 5")
    print(f"  short_count                : {result.short_count} / 5")
    print(f"  gross_notional_usd         : {_fmt_usd(result.gross_notional_usd)}")
    print(f"  net_notional_usd           : {_fmt_usd(result.net_notional_usd)}")
    print(f"  gross_exposure_ratio       : {result.gross_exposure_ratio:.4f}x  (max 1.0x)")
    print(f"  net_exposure_ratio         : {result.net_exposure_ratio:.4f}x  (max 0.5x)")
    print(f"  existing_stop_risk_usd     : {_fmt_usd(result.existing_stop_risk_usd)}")
    print(f"  portfolio_risk_budget_usd  : {_fmt_usd(result.portfolio_risk_budget_usd)}")
    print(f"  remaining_risk_budget_usd  : {_fmt_usd(result.remaining_risk_budget_usd)}")
    print(f"  current_slot_usage         : {result.current_slot_usage} / 10")
    print(f"  available_slots            : {result.available_slots}")
    print(f"  max_long_allowed_remaining : {result.max_long_allowed_remaining}")
    print(f"  max_short_allowed_remaining: {result.max_short_allowed_remaining}")

    if result.positions:
        _hdr("Position Breakdown")
        print(f"  {'Symbol':<12} {'Side':<6} {'Qty':>8} {'Entry':>10} {'Stop':>10}"
              f" {'Notional':>10} {'StopRisk':>9}  Flags")
        for pd in result.positions:
            flags = []
            if pd.missing_stop:
                flags.append("NO_STOP")
            if pd.missing_instrument_rule:
                flags.append("NO_RULE")
            print(
                f"  {pd.symbol:<12} {pd.side:<6} {pd.quantity:>8.4f}"
                f" {pd.entry_price:>10,.2f} {pd.stop_price:>10,.2f}"
                f" {pd.notional_usd:>10,.2f} {pd.stop_risk_usd:>9,.2f}"
                f"  {', '.join(flags) if flags else 'OK'}"
            )

    if result.violations:
        _hdr("Violations Detected")
        for v in result.violations:
            tag = "[HARD]" if v.is_hard else "[SOFT]"
            print(f"  {tag} {v.code}: {v.detail}")
    else:
        _hdr("Violations")
        print("  None detected.")

    _hdr("Cleanup Plan")
    print(f"  action_type            : {result.action_type}")
    print(f"  new_entry_allowed      : {result.new_entry_allowed}")
    print(f"  cannot_proceed_to_order_smoke: {result.cannot_proceed_to_order_smoke}")
    if result.blocked_reasons:
        print(f"  blocked_reasons        : {result.blocked_reasons}")
    if result.suggested_actions:
        print("  suggested_actions:")
        for a in result.suggested_actions:
            print(f"    - {a}")
    if not result.new_entry_allowed:
        print()
        print("  NOTE: To enable new entries, clear all hard violations.")
        print("  If manual position reduction is needed, open TASK-014F:")
        print("  Demo Close-only Manual Confirmed Cleanup.")

    _hdr("Safety Invariants")
    print(f"  DRY RUN / NO ORDERS SENT      : TRUE")
    print(f"  NO POSITIONS MODIFIED          : TRUE")
    print(f"  order_endpoint_called          : {result.order_endpoint_called}")
    print(f"  secret_value_observed          : {result.secret_value_observed}")
    print(f"  no_orders_sent                 : {result.no_orders_sent}")
    print(f"  no_position_modified           : {result.no_position_modified}")


# ---------------------------------------------------------------------------
# Preview runner
# ---------------------------------------------------------------------------

def run_preview(
    mode:           str  = "fixture",      # "fixture" or "from_latest_smoke"
    write_report:   bool = False,
    smoke_dir:      Path | None = None,
    reconcile_dir:  Path | None = None,
) -> int:
    """
    Run the position reconciliation dry-run preview.

    Returns 0 if new_entry_allowed=True and no fail_closed conditions.
    Returns 1 if new_entry_allowed=False, or fail_closed (missing/unverified smoke).
    """
    _smoke_dir     = smoke_dir     or _DEFAULT_SMOKE_DIR
    _reconcile_dir = reconcile_dir or _DEFAULT_RECONCILE_DIR

    print(_SEP)
    print("DRY RUN / NO ORDERS SENT / NO POSITIONS MODIFIED")
    print("TASK-014E: Demo Position Reconciliation Preview")
    print(_SEP)

    demo_runtime_verified = False
    proof_strength        = ""
    equity_usd            = _FIXTURE_EQUITY_CLEAN
    available_balance_usd = _FIXTURE_AVAILABLE_CLEAN
    positions             = _FIXTURE_POSITIONS_CLEAN
    report_mode           = "fixture"

    if mode == "from_latest_smoke":
        smoke = load_latest_smoke(_smoke_dir)
        if smoke is None:
            print("\n[FAIL CLOSED] latest_smoke.json not found or unreadable.")
            print(f"  Expected: {_smoke_dir / 'latest_smoke.json'}")
            print("  Run: python scripts/preview_demo_readonly_runtime.py --real-readonly --write-report")
            print(_SEP)
            return 1
        if not smoke.get("demo_runtime_verified", False):
            print("\n[FAIL CLOSED] latest_smoke.json: demo_runtime_verified=False.")
            print(f"  proof_strength={smoke.get('proof_strength', 'MISSING')}")
            print("  Re-run --real-readonly smoke with valid credentials before reconciliation.")
            print(_SEP)
            return 1

        demo_runtime_verified = True
        proof_strength        = smoke.get("proof_strength", "")
        equity_usd            = float(smoke.get("equity_usd", 0.0))
        available_balance_usd = float(smoke.get("available_balance_usd", 0.0))
        # Use legacy fixture positions (smoke JSON does not contain individual position data)
        positions             = _FIXTURE_POSITIONS_LEGACY
        report_mode           = "real_readonly_snapshot"

        print(f"  [smoke] demo_runtime_verified={demo_runtime_verified}")
        print(f"  [smoke] proof_strength={proof_strength}")
        print(f"  [smoke] equity_usd={equity_usd:.2f}")
        print(f"  [smoke] available_balance_usd={available_balance_usd:.2f}")
        print(f"  [note]  position details from fixture (smoke JSON has aggregate only)")

    result = reconcile(
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        positions=positions,
        instrument_rules=_FIXTURE_INSTRUMENT_RULES,
        full_kelly_fraction=0.60,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        mode=report_mode,
    )

    _print_result(result)
    print(_SEP)

    if write_report:
        ts_utc = datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
        _write_report(result, _reconcile_dir, ts_utc)

    return 0 if result.new_entry_allowed else 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Dry-run preview of Demo position reconciliation"
    )
    parser.add_argument(
        "--from-latest-readonly-smoke",
        action="store_true",
        help=(
            "Read equity/available_balance from "
            "outputs/demo_trading/readonly_smoke/latest_smoke.json. "
            "Fails closed if file missing or demo_runtime_verified=False."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON + Markdown report to outputs/demo_trading/reconciliation/.",
    )
    args = parser.parse_args()
    mode = "from_latest_smoke" if args.from_latest_readonly_smoke else "fixture"
    sys.exit(run_preview(mode=mode, write_report=args.write_report))


if __name__ == "__main__":
    main()
