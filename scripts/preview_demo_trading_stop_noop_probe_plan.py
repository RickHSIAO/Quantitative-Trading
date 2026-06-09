"""
scripts/preview_demo_trading_stop_noop_probe_plan.py
TASK-014U: Demo Trading-stop No-op Probe Design CLI.

Usage (PLAN — default, no network):
  python scripts/preview_demo_trading_stop_noop_probe_plan.py \\
    --from-latest-readonly \\
    --from-latest-reconciliation \\
    --from-latest-protection \\
    --from-latest-contract \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (REAL NO-OP PROBE GUARD — guarded; returns
       REAL_NOOP_PROBE_NOT_IMPLEMENTED):
  python scripts/preview_demo_trading_stop_noop_probe_plan.py \\
    --from-latest-readonly --from-latest-reconciliation \\
    --from-latest-protection --from-latest-contract \\
    --symbol SOLUSDT \\
    --allow-real-noop-probe \\
    [--write-report]

Reads:
  outputs/demo_trading/readonly_smoke/latest_smoke.json
      (legacy fallback: latest_readonly_smoke.json)
  outputs/demo_trading/reconciliation/latest_reconciliation.json
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json
  outputs/demo_trading/trading_stop_contract/latest_trading_stop_contract.json

Writes (when --write-report):
  outputs/demo_trading/trading_stop_noop_probe_plan/
      {ts}_noop_probe_plan.json
      {ts}_noop_probe_plan.md
      latest_noop_probe_plan.json
      latest_noop_probe_plan.md

IMPORTANT:
  - This is a DESIGN module.  No network at all.  Even with
    --allow-real-noop-probe + presence of all four upstream artifacts,
    the planner returns REAL_NOOP_PROBE_NOT_IMPLEMENTED.  Executing
    the real no-op probe is the subject of TASK-014V+.
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT
    lifted by this task.
  - The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) are NEVER touched.

Exit codes:
  0  plan produced (plan / real_noop_probe_not_implemented)
  1  any upstream artifact missing / symbol missing / fail-closed plan
"""
from __future__ import annotations

import argparse
import json
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

from src.demo_trading_stop_noop_probe_plan import (
    DEFAULT_SELECTED_SYMBOL,
    DemoTradingStopNoopProbePlanner,
    NoopProbePlanResult,
    STATUS_PLAN_READY,
    STATUS_REAL_NOOP_NOT_IMPL,
)

_SEP = "-" * 72
_DEFAULT_READONLY_DIR    = ROOT / "outputs" / "demo_trading" / "readonly_smoke"
_DEFAULT_RECON_DIR       = ROOT / "outputs" / "demo_trading" / "reconciliation"
_DEFAULT_PROTECTION_DIR  = ROOT / "outputs" / "demo_trading" / "new_entry_protection"
_DEFAULT_CONTRACT_DIR    = ROOT / "outputs" / "demo_trading" / "trading_stop_contract"
_DEFAULT_PLAN_DIR        = ROOT / "outputs" / "demo_trading" / "trading_stop_noop_probe_plan"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_latest_readonly(readonly_dir: Path) -> dict | None:
    # Primary filename written by the existing readonly-smoke scripts
    # (TASK-014C/D): latest_smoke.json.
    # Legacy fallback: latest_readonly_smoke.json (the name used in the
    # original TASK-014U spec before VPS verification caught the mismatch).
    primary  = readonly_dir / "latest_smoke.json"
    fallback = readonly_dir / "latest_readonly_smoke.json"
    result   = _load_json(primary)
    if result is None:
        result = _load_json(fallback)
    return result


def load_latest_reconciliation(recon_dir: Path) -> dict | None:
    return _load_json(recon_dir / "latest_reconciliation.json")


def load_latest_protection(protection_dir: Path) -> dict | None:
    return _load_json(protection_dir / "latest_new_entry_protection.json")


def load_latest_contract(contract_dir: Path) -> dict | None:
    return _load_json(contract_dir / "latest_trading_stop_contract.json")


def _print_result(r: NoopProbePlanResult) -> None:
    print(f"  mode                              : {r.mode}")
    print(f"  selected_symbol                   : {r.selected_symbol or '(none)'}")
    print(f"  existing_position_symbols         : {r.existing_position_symbols}")
    print(f"  recommended_path                  : {r.recommended_path}")
    print(f"  real_probe_allowed                : {r.real_probe_allowed}")
    print(f"  real_noop_probe_implemented       : {r.real_noop_probe_implemented}")
    print(f"  current_task_real_execution_allowed: {r.current_task_real_execution_allowed}")
    print(f"  trading_stop_path_ref             : {r.trading_stop_path_ref}  (NOT invoked)")
    print(f"  order_create_path_ref             : {r.order_create_path_ref}  (NOT invoked)")
    print(f"  base_url_ref                      : {r.base_url_ref}")
    print(f"  stop_endpoint_called              : {r.stop_endpoint_called}")
    print(f"  order_endpoint_called             : {r.order_endpoint_called}")
    print(f"  no_position_modified              : {r.no_position_modified}")
    print(f"  no_live_endpoint                  : {r.no_live_endpoint}")
    print(f"  no_orders_sent                    : {r.no_orders_sent}")
    print(f"  no_batch_order                    : {r.no_batch_order}")
    print(f"  no_close_only_path                : {r.no_close_only_path}")
    print(f"  emergency_close_invoked           : {r.emergency_close_invoked}")
    print(f"  secret_value_observed             : {r.secret_value_observed}")
    print(f"  g20_policy_still_in_place         : {r.g20_policy_still_in_place}")
    print(f"  status                            : {r.status}")
    if r.blocked_gates:
        print(f"  blocked_gates ({len(r.blocked_gates)}):")
        for g in r.blocked_gates:
            print(f"    - {g}")
    print("  plan_comparison_summary:")
    for row in r.plan_comparison_summary:
        print(f"    - path_id     : {row['path_id']}")
        print(f"      label       : {row['label']}")
        print(f"      recommended : {row['recommended']}")
        print(f"      touches_existing_positions : {row['touches_existing_positions']}")
        print(f"      estimated_risk             : {row['estimated_risk']}")


def _write_report(r: NoopProbePlanResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = (
        r.timestamp_utc
        .replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        .replace("Z", "")
    )
    json_path   = output_dir / f"{ts_safe}_noop_probe_plan.json"
    json_latest = output_dir / "latest_noop_probe_plan.json"
    md_path     = output_dir / f"{ts_safe}_noop_probe_plan.md"
    md_latest   = output_dir / "latest_noop_probe_plan.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines: list[str] = [
        "# Demo Trading-stop No-op Probe Plan (TASK-014U)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        "",
        "## Selection",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol or '(none)'} |",
        f"| existing_position_symbols | {', '.join(r.existing_position_symbols) or '(none)'} |",
        f"| recommended_path | {r.recommended_path} |",
        f"| real_probe_allowed | {r.real_probe_allowed} |",
        f"| real_noop_probe_implemented | {r.real_noop_probe_implemented} |",
        f"| current_task_real_execution_allowed | {r.current_task_real_execution_allowed} |",
        f"| next_required_task | {r.next_required_task} |",
        "",
        "## Plan Comparison",
        "",
        "| path_id | label | recommended | touches_existing_positions | estimated_risk |",
        "|---|---|---|---|---|",
    ]
    for row in r.plan_comparison_summary:
        md_lines.append(
            f"| `{row['path_id']}` | {row['label']} | "
            f"{row['recommended']} | {row['touches_existing_positions']} | "
            f"{row['estimated_risk']} |"
        )
    md_lines.append("")

    for path_id, plan in r.plans.items():
        md_lines += [
            f"### Plan: `{path_id}`",
            "",
            f"**Label**: {plan['label']}  ",
            f"**Recommended**: {plan['recommended']}  ",
            f"**Touches existing positions**: {plan['touches_existing_positions']}  ",
            f"**Estimated risk**: {plan['estimated_risk']}  ",
            f"**Next task pointer**: `{plan['next_task_pointer']}`",
            "",
            f"_Summary_: {plan['summary']}",
            "",
            "**Required preconditions:**",
            "",
        ]
        for pre in plan.get("required_preconditions", []):
            md_lines.append(f"  - {pre}")
        md_lines += [
            "",
            "**Open blockers in this task:**",
            "",
        ]
        for g in plan.get("open_blockers_in_this_task", []):
            md_lines.append(f"  - `{g}`")
        md_lines.append("")

    md_lines += [
        "## Blocked Gates",
        "",
    ]
    if r.blocked_gates:
        for g in r.blocked_gates:
            md_lines.append(f"- `{g}`")
    else:
        md_lines.append("- (none)")
    md_lines.append("")

    md_lines += [
        "## Safety Invariants",
        "",
        f"- trading_stop_path_ref: `{r.trading_stop_path_ref}` (NOT invoked)",
        f"- order_create_path_ref: `{r.order_create_path_ref}` (NOT invoked)",
        f"- base_url_ref: `{r.base_url_ref}` (informational only)",
        f"- stop_endpoint_called: `{r.stop_endpoint_called}`",
        f"- order_endpoint_called: `{r.order_endpoint_called}`",
        f"- no_position_modified: `{r.no_position_modified}`",
        f"- no_live_endpoint: `{r.no_live_endpoint}`",
        f"- no_orders_sent: `{r.no_orders_sent}`",
        f"- no_batch_order: `{r.no_batch_order}`",
        f"- no_close_only_path: `{r.no_close_only_path}`",
        f"- emergency_close_invoked: `{r.emergency_close_invoked}`",
        f"- secret_value_observed: `{r.secret_value_observed}`",
        f"- g20_policy_still_in_place: `{r.g20_policy_still_in_place}`",
        "",
        "> This planner NEVER opens a socket.",
        "> /v5/position/trading-stop and /v5/order/create are documented",
        "> string references; neither is invoked.",
        "> The 5 existing demo positions are NEVER touched.",
        "> Real no-op probe execution is deliberately not implemented in",
        "> TASK-014U; the tiny isolated position lifecycle mock is the",
        "> subject of TASK-014V.",
        "> TASK-014L sender G20 (protected_entry_policy_missing) is NOT",
        "> lifted by this task.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:                 str  = DEFAULT_SELECTED_SYMBOL,
    allow_real_noop_probe:  bool = False,
    write_report:           bool = False,
    readonly_dir:           Path | None = None,
    reconciliation_dir:     Path | None = None,
    protection_dir:         Path | None = None,
    contract_dir:           Path | None = None,
    plan_dir:               Path | None = None,
    _now:                   datetime | None = None,
) -> int:
    _ro_dir       = readonly_dir       or _DEFAULT_READONLY_DIR
    _recon_dir    = reconciliation_dir or _DEFAULT_RECON_DIR
    _protect_dir  = protection_dir     or _DEFAULT_PROTECTION_DIR
    _contract_dir = contract_dir       or _DEFAULT_CONTRACT_DIR
    _plan_dir     = plan_dir           or _DEFAULT_PLAN_DIR

    print(_SEP)
    if allow_real_noop_probe:
        print("REAL NO-OP PROBE GUARD — NO NETWORK — REAL_NOOP_PROBE_NOT_IMPLEMENTED")
    else:
        print("PLAN — NO NETWORK — DESIGN ONLY")
    print("TASK-014U: Demo Trading-stop No-op Probe Plan")
    print(_SEP)

    readonly       = load_latest_readonly(_ro_dir)
    reconciliation = load_latest_reconciliation(_recon_dir)
    protection     = load_latest_protection(_protect_dir)
    contract       = load_latest_contract(_contract_dir)

    missing: list[str] = []
    if readonly is None:
        missing.append(
            str(_ro_dir / "latest_smoke.json")
            + "  (and fallback latest_readonly_smoke.json)"
        )
    if reconciliation is None:
        missing.append(str(_recon_dir / "latest_reconciliation.json"))
    if protection is None:
        missing.append(str(_protect_dir / "latest_new_entry_protection.json"))
    if contract is None:
        missing.append(str(_contract_dir / "latest_trading_stop_contract.json"))

    if missing:
        print("\n[FAIL CLOSED] Missing upstream artifact(s):")
        for path in missing:
            print(f"  - {path}")
        print(_SEP)
        return 1

    if not symbol:
        print("\n[FAIL CLOSED] --symbol is required.")
        print(_SEP)
        return 1

    print(f"\n  symbol             : {symbol}")
    print(f"  readonly_src       : {_ro_dir / 'latest_smoke.json'} (primary)")
    print(f"  reconciliation_src : {_recon_dir / 'latest_reconciliation.json'}")
    print(f"  protection_src     : {_protect_dir / 'latest_new_entry_protection.json'}")
    print(f"  contract_src       : {_contract_dir / 'latest_trading_stop_contract.json'}")

    planner = DemoTradingStopNoopProbePlanner()
    result  = planner.design_plan(
        readonly_smoke=readonly,
        reconciliation=reconciliation,
        protection=protection,
        contract=contract,
        symbol=symbol,
        allow_real_noop_probe=allow_real_noop_probe,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _plan_dir)

    if result.status in (STATUS_PLAN_READY, STATUS_REAL_NOOP_NOT_IMPL):
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Demo trading-stop no-op probe DESIGN plan — design only "
            "(no network, no live endpoint, no orders / positions "
            "modified, no real trading-stop call).  Returns "
            "REAL_NOOP_PROBE_NOT_IMPLEMENTED under "
            "--allow-real-noop-probe."
        ),
    )
    parser.add_argument("--from-latest-readonly", action="store_true",
                        help="Read readonly_smoke JSON from outputs/.../readonly_smoke/.")
    parser.add_argument("--from-latest-reconciliation", action="store_true",
                        help="Read reconciliation JSON from outputs/.../reconciliation/.")
    parser.add_argument("--from-latest-protection", action="store_true",
                        help="Read protection JSON from outputs/.../new_entry_protection/.")
    parser.add_argument("--from-latest-contract", action="store_true",
                        help="Read contract JSON from outputs/.../trading_stop_contract/.")
    parser.add_argument("--symbol", default=DEFAULT_SELECTED_SYMBOL,
                        metavar="SYMBOL",
                        help=("Symbol to plan against.  MUST NOT be in the "
                              "5 existing demo position symbols (ENAUSDT / "
                              "TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT)."))
    parser.add_argument("--allow-real-noop-probe", action="store_true",
                        help=("Guarded flag for the future real no-op "
                              "probe.  TASK-014U returns "
                              "REAL_NOOP_PROBE_NOT_IMPLEMENTED even when "
                              "this flag is set (no socket opened)."))
    parser.add_argument("--write-report", action="store_true",
                        help=("Write JSON + Markdown report to "
                              "outputs/demo_trading/trading_stop_noop_probe_plan/."))
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        allow_real_noop_probe=args.allow_real_noop_probe,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
