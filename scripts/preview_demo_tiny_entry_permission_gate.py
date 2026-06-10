"""
scripts/preview_demo_tiny_entry_permission_gate.py
TASK-014X: Tiny Isolated Demo Entry Permission Gate / Dry-run Only CLI.

Usage (CHECKLIST --- default, no network, envelope-only):
  python scripts/preview_demo_tiny_entry_permission_gate.py \\
    --from-latest-readonly \\
    --from-latest-reconciliation \\
    --from-latest-protection \\
    --from-latest-contract \\
    --from-latest-noop-plan \\
    --from-latest-lifecycle \\
    --from-latest-real-permission \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (REAL ENTRY PERMISSION DRY RUN --- envelope-only):
  ... --allow-real-entry-permission

Usage (REAL TINY ENTRY GUARD --- always returns
       REAL_TINY_ENTRY_NOT_IMPLEMENTED, no socket opened):
  ... --allow-real-tiny-entry

Reads:
  outputs/demo_trading/readonly_smoke/latest_smoke.json
      (legacy fallback: latest_readonly_smoke.json)
  outputs/demo_trading/reconciliation/latest_reconciliation.json
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json
  outputs/demo_trading/trading_stop_contract/latest_trading_stop_contract.json
  outputs/demo_trading/trading_stop_noop_probe_plan/latest_trading_stop_noop_probe_plan.json
      (legacy fallback: latest_noop_probe_plan.json)
  outputs/demo_trading/tiny_position_lifecycle_mock/latest_tiny_position_lifecycle_mock.json
  outputs/demo_trading/tiny_position_real_permission_gate/latest_tiny_position_real_permission_gate.json

Writes (when --write-report):
  outputs/demo_trading/tiny_entry_permission_gate/
      {ts}_tiny_entry_permission_gate.json
      {ts}_tiny_entry_permission_gate.md
      latest_tiny_entry_permission_gate.json
      latest_tiny_entry_permission_gate.md

IMPORTANT:
  - This is a PERMISSION GATE module.  No network at all.  Even with
    --allow-real-entry-permission, the gate only emits a checklist
    report and never executes anything.  Even with
    --allow-real-tiny-entry, the gate returns
    REAL_TINY_ENTRY_NOT_IMPLEMENTED.  Real entry execution is reserved
    for a future task.
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT
    lifted by this task.
  - The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) are NEVER touched.
  - The strategy-sized qty (12.2 SOL) MUST NOT be reused as a real
    tiny qty; tiny notional cap is 10 USDT.

Exit codes:
  0  checklist_ready / permission_ready_exec_disabled /
     real_tiny_entry_not_implemented
  1  fail_closed / missing upstream / missing symbol
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

from src.demo_tiny_entry_permission_gate import (
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyEntryPermissionGate,
    TinyEntryPermissionGateResult,
    STATUS_CHECKLIST_READY,
    STATUS_PERMISSION_READY_EXEC_DISABLED,
    STATUS_REAL_TINY_ENTRY_NOT_IMPL,
)

_SEP = "-" * 72
_DEFAULT_READONLY_DIR        = ROOT / "outputs" / "demo_trading" / "readonly_smoke"
_DEFAULT_RECON_DIR           = ROOT / "outputs" / "demo_trading" / "reconciliation"
_DEFAULT_PROTECTION_DIR      = ROOT / "outputs" / "demo_trading" / "new_entry_protection"
_DEFAULT_CONTRACT_DIR        = ROOT / "outputs" / "demo_trading" / "trading_stop_contract"
_DEFAULT_NOOP_PLAN_DIR       = ROOT / "outputs" / "demo_trading" / "trading_stop_noop_probe_plan"
_DEFAULT_LIFECYCLE_DIR       = ROOT / "outputs" / "demo_trading" / "tiny_position_lifecycle_mock"
_DEFAULT_REAL_PERMISSION_DIR = ROOT / "outputs" / "demo_trading" / "tiny_position_real_permission_gate"
_DEFAULT_OUTPUT_DIR          = ROOT / "outputs" / "demo_trading" / "tiny_entry_permission_gate"


def _load_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except Exception:
        return None


def load_latest_readonly(readonly_dir: Path) -> dict | None:
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


def load_latest_noop_plan(noop_plan_dir: Path) -> dict | None:
    primary  = noop_plan_dir / "latest_trading_stop_noop_probe_plan.json"
    fallback = noop_plan_dir / "latest_noop_probe_plan.json"
    result   = _load_json(primary)
    if result is None:
        result = _load_json(fallback)
    return result


def load_latest_lifecycle(lifecycle_dir: Path) -> dict | None:
    return _load_json(lifecycle_dir / "latest_tiny_position_lifecycle_mock.json")


def load_latest_real_permission(real_permission_dir: Path) -> dict | None:
    return _load_json(
        real_permission_dir / "latest_tiny_position_real_permission_gate.json"
    )


def _print_result(r: TinyEntryPermissionGateResult) -> None:
    print(f"  mode                                : {r.mode}")
    print(f"  selected_symbol                     : {r.selected_symbol or '(none)'}")
    print(f"  existing_position_symbols           : {r.existing_position_symbols}")
    print(f"  original_tiny_qty                   : {r.original_tiny_qty}")
    print(f"  rounded_tiny_qty                    : {r.rounded_tiny_qty}")
    print(f"  entry_reference_price               : {r.entry_reference_price}")
    print(f"  estimated_tiny_notional             : {r.estimated_tiny_notional}")
    print(f"  tiny_notional_cap_usdt              : {r.tiny_notional_cap_usdt}")
    print(f"  within_tiny_notional_cap            : {r.within_tiny_notional_cap}")
    print(f"  strategy_full_size_qty_ref          : {r.strategy_full_size_qty_ref}")
    print(f"  instrument_rule_summary             : {r.instrument_rule_summary}")
    print(f"  entry_payload_preview               : {r.entry_payload_preview}")
    print(f"  entry_token_pattern                 : {r.entry_token_pattern}")
    print(f"  post_entry_verification_plan        : {r.post_entry_verification_plan}")
    print(f"  real_entry_permission_dry_run_allowed: {r.real_entry_permission_dry_run_allowed}")
    print(f"  real_execution_allowed              : {r.real_execution_allowed}")
    print(f"  real_tiny_entry_implemented         : {r.real_tiny_entry_implemented}")
    print(f"  current_task_real_execution_allowed : {r.current_task_real_execution_allowed}")
    print(f"  real_tiny_entry_requested           : {r.real_tiny_entry_requested}")
    print(f"  trading_stop_path_ref               : {r.trading_stop_path_ref}  (NOT invoked)")
    print(f"  order_create_path_ref               : {r.order_create_path_ref}  (NOT invoked)")
    print(f"  base_url_ref                        : {r.base_url_ref}")
    print(f"  stop_endpoint_called                : {r.stop_endpoint_called}")
    print(f"  order_endpoint_called               : {r.order_endpoint_called}")
    print(f"  no_position_modified                : {r.no_position_modified}")
    print(f"  no_live_endpoint                    : {r.no_live_endpoint}")
    print(f"  no_orders_sent                      : {r.no_orders_sent}")
    print(f"  no_batch_order                      : {r.no_batch_order}")
    print(f"  no_close_only_path                  : {r.no_close_only_path}")
    print(f"  emergency_close_invoked             : {r.emergency_close_invoked}")
    print(f"  leverage_mutated                    : {r.leverage_mutated}")
    print(f"  transfer_invoked                    : {r.transfer_invoked}")
    print(f"  secret_value_observed               : {r.secret_value_observed}")
    print(f"  g20_policy_still_in_place           : {r.g20_policy_still_in_place}")
    print(f"  g20_lifted                          : {r.g20_lifted}")
    print(f"  existing_positions_touched          : {r.existing_positions_touched}")
    print(f"  failed_stage                        : {r.failed_stage or '(none)'}")
    print(f"  status                              : {r.status}")
    if r.blocked_gates:
        print(f"  blocked_gates ({len(r.blocked_gates)}):")
        for g in r.blocked_gates:
            print(f"    - {g}")
    print("  stages:")
    for stage_id in r.stage_order:
        env = r.stages.get(stage_id)
        if env is None:
            print(f"    - {stage_id}: (not built)")
            continue
        summary = env.get("summary", "")
        print(f"    - {stage_id}: {summary}")


def _write_report(
    r: TinyEntryPermissionGateResult,
    output_dir: Path,
) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = (
        r.timestamp_utc
        .replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        .replace("Z", "")
    )
    json_path   = output_dir / f"{ts_safe}_tiny_entry_permission_gate.json"
    json_latest = output_dir / "latest_tiny_entry_permission_gate.json"
    md_path     = output_dir / f"{ts_safe}_tiny_entry_permission_gate.md"
    md_latest   = output_dir / "latest_tiny_entry_permission_gate.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines: list[str] = [
        "# Tiny Isolated Demo Entry Permission Gate (TASK-014X)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        f"failed_stage: `{r.failed_stage or '(none)'}`  ",
        "",
        "## Selection",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol or '(none)'} |",
        f"| existing_position_symbols | {', '.join(r.existing_position_symbols) or '(none)'} |",
        f"| original_tiny_qty | {r.original_tiny_qty} |",
        f"| rounded_tiny_qty | {r.rounded_tiny_qty} |",
        f"| entry_reference_price | {r.entry_reference_price} |",
        f"| estimated_tiny_notional | {r.estimated_tiny_notional} |",
        f"| tiny_notional_cap_usdt | {r.tiny_notional_cap_usdt} |",
        f"| within_tiny_notional_cap | {r.within_tiny_notional_cap} |",
        f"| strategy_full_size_qty_ref | {r.strategy_full_size_qty_ref} |",
        f"| entry_token_pattern | {r.entry_token_pattern} |",
        f"| real_entry_permission_dry_run_allowed | {r.real_entry_permission_dry_run_allowed} |",
        f"| real_execution_allowed | {r.real_execution_allowed} |",
        f"| real_tiny_entry_implemented | {r.real_tiny_entry_implemented} |",
        f"| current_task_real_execution_allowed | {r.current_task_real_execution_allowed} |",
        f"| real_tiny_entry_requested | {r.real_tiny_entry_requested} |",
        f"| next_required_task | {r.next_required_task} |",
        "",
        "## Instrument Rule Summary",
        "",
        "```json",
        json.dumps(r.instrument_rule_summary, indent=2),
        "```",
        "",
        "## Entry Payload Preview (NEVER sent)",
        "",
        "```json",
        json.dumps(r.entry_payload_preview, indent=2),
        "```",
        "",
        "## Post-entry Required Verification Plan",
        "",
        "```json",
        json.dumps(r.post_entry_verification_plan, indent=2),
        "```",
        "",
        "## Stages",
        "",
    ]
    for stage_id in r.stage_order:
        env = r.stages.get(stage_id)
        if env is None:
            md_lines += [
                f"### Stage: `{stage_id}`",
                "",
                "- (not built)",
                "",
            ]
            continue
        md_lines += [
            f"### Stage: `{stage_id}`",
            "",
            f"_Summary_: {env.get('summary', '')}",
            "",
            "```json",
            json.dumps(env, indent=2),
            "```",
            "",
        ]

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
        f"- leverage_mutated: `{r.leverage_mutated}`",
        f"- transfer_invoked: `{r.transfer_invoked}`",
        f"- secret_value_observed: `{r.secret_value_observed}`",
        f"- g20_policy_still_in_place: `{r.g20_policy_still_in_place}`",
        f"- g20_lifted: `{r.g20_lifted}`",
        f"- existing_position_stop_snapshot_match: `{r.existing_position_stop_snapshot_match}`",
        f"- existing_positions_touched: `{r.existing_positions_touched}`",
        "",
        "> TASK-014X is a PERMISSION GATE.  It NEVER opens a socket,",
        "> NEVER invokes /v5/order/create, NEVER invokes",
        "> /v5/position/trading-stop, NEVER modifies any position, and",
        "> NEVER lifts TASK-014L sender G20 (protected_entry_policy_missing).",
        "> The 5 existing demo positions are NEVER touched.",
        "> The strategy-sized qty (12.2 SOL) MUST NOT be reused as a",
        "> real tiny qty; the tiny notional cap is 10 USDT.",
        "> Real tiny-entry execution is reserved for a future task;",
        "> even with --allow-real-tiny-entry this task returns",
        "> REAL_TINY_ENTRY_NOT_IMPLEMENTED.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:                          str  = DEFAULT_SELECTED_SYMBOL,
    allow_real_entry_permission:     bool = False,
    allow_real_tiny_entry:           bool = False,
    write_report:                    bool = False,
    readonly_dir:                    Path | None = None,
    reconciliation_dir:              Path | None = None,
    protection_dir:                  Path | None = None,
    contract_dir:                    Path | None = None,
    noop_plan_dir:                   Path | None = None,
    lifecycle_dir:                   Path | None = None,
    real_permission_dir:             Path | None = None,
    output_dir:                      Path | None = None,
    _now:                            datetime | None = None,
) -> int:
    _ro_dir            = readonly_dir         or _DEFAULT_READONLY_DIR
    _recon_dir         = reconciliation_dir   or _DEFAULT_RECON_DIR
    _protect_dir       = protection_dir       or _DEFAULT_PROTECTION_DIR
    _contract_dir      = contract_dir         or _DEFAULT_CONTRACT_DIR
    _noop_dir          = noop_plan_dir        or _DEFAULT_NOOP_PLAN_DIR
    _lifecycle_dir     = lifecycle_dir        or _DEFAULT_LIFECYCLE_DIR
    _real_perm_dir     = real_permission_dir  or _DEFAULT_REAL_PERMISSION_DIR
    _out_dir           = output_dir           or _DEFAULT_OUTPUT_DIR

    print(_SEP)
    if allow_real_tiny_entry:
        print("REAL TINY ENTRY GUARD --- NO NETWORK --- REAL_TINY_ENTRY_NOT_IMPLEMENTED")
    elif allow_real_entry_permission:
        print("REAL ENTRY PERMISSION DRY RUN --- NO NETWORK --- envelope-only")
    else:
        print("CHECKLIST --- NO NETWORK --- envelope-only")
    print("TASK-014X: Tiny Isolated Demo Entry Permission Gate / Dry-run Only")
    print(_SEP)

    readonly             = load_latest_readonly(_ro_dir)
    reconciliation       = load_latest_reconciliation(_recon_dir)
    protection           = load_latest_protection(_protect_dir)
    contract             = load_latest_contract(_contract_dir)
    noop_plan            = load_latest_noop_plan(_noop_dir)
    lifecycle            = load_latest_lifecycle(_lifecycle_dir)
    real_permission_gate = load_latest_real_permission(_real_perm_dir)

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
    if noop_plan is None:
        missing.append(
            str(_noop_dir / "latest_trading_stop_noop_probe_plan.json")
            + "  (and fallback latest_noop_probe_plan.json)"
        )
    if lifecycle is None:
        missing.append(str(_lifecycle_dir / "latest_tiny_position_lifecycle_mock.json"))
    if real_permission_gate is None:
        missing.append(
            str(_real_perm_dir / "latest_tiny_position_real_permission_gate.json")
        )

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

    print(f"\n  symbol                : {symbol}")
    print(f"  readonly_src          : {_ro_dir / 'latest_smoke.json'} (primary)")
    print(f"  reconciliation_src    : {_recon_dir / 'latest_reconciliation.json'}")
    print(f"  protection_src        : {_protect_dir / 'latest_new_entry_protection.json'}")
    print(f"  contract_src          : {_contract_dir / 'latest_trading_stop_contract.json'}")
    print(f"  noop_plan_src         : {_noop_dir / 'latest_trading_stop_noop_probe_plan.json'} (primary)")
    print(f"  lifecycle_src         : {_lifecycle_dir / 'latest_tiny_position_lifecycle_mock.json'}")
    print(f"  real_permission_src   : {_real_perm_dir / 'latest_tiny_position_real_permission_gate.json'}")

    gate    = DemoTinyEntryPermissionGate()
    result  = gate.run_checklist(
        readonly_smoke=readonly,
        reconciliation=reconciliation,
        protection=protection,
        contract=contract,
        noop_plan=noop_plan,
        lifecycle_mock=lifecycle,
        real_permission_gate=real_permission_gate,
        symbol=symbol,
        allow_real_entry_permission=allow_real_entry_permission,
        allow_real_tiny_entry=allow_real_tiny_entry,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _out_dir)

    if result.status in (
        STATUS_CHECKLIST_READY,
        STATUS_PERMISSION_READY_EXEC_DISABLED,
        STATUS_REAL_TINY_ENTRY_NOT_IMPL,
    ):
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Tiny isolated demo entry PERMISSION GATE / DRY-RUN ONLY.  No "
            "network, no live endpoint, no orders / positions modified, "
            "no real trading-stop call.  Even with "
            "--allow-real-entry-permission this only emits a checklist; "
            "even with --allow-real-tiny-entry it returns "
            "REAL_TINY_ENTRY_NOT_IMPLEMENTED."
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
    parser.add_argument("--from-latest-noop-plan", action="store_true",
                        help="Read no-op plan JSON from outputs/.../trading_stop_noop_probe_plan/.")
    parser.add_argument("--from-latest-lifecycle", action="store_true",
                        help="Read lifecycle mock JSON from outputs/.../tiny_position_lifecycle_mock/.")
    parser.add_argument("--from-latest-real-permission", action="store_true",
                        help="Read real permission gate JSON from outputs/.../tiny_position_real_permission_gate/.")
    parser.add_argument("--symbol", default=DEFAULT_SELECTED_SYMBOL,
                        metavar="SYMBOL",
                        help=("Symbol to plan against.  MUST NOT be in the "
                              "5 existing demo position symbols (ENAUSDT / "
                              "TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT)."))
    parser.add_argument("--allow-real-entry-permission", action="store_true",
                        help=("Promote envelope to entry_permission_dry_run.  "
                              "Even with this flag, TASK-014X only emits a "
                              "checklist report.  No execution."))
    parser.add_argument("--allow-real-tiny-entry", action="store_true",
                        help=("Guarded flag for a hypothetical future real "
                              "tiny entry.  TASK-014X returns "
                              "REAL_TINY_ENTRY_NOT_IMPLEMENTED even when "
                              "this flag is set (no socket opened)."))
    parser.add_argument("--write-report", action="store_true",
                        help=("Write JSON + Markdown report to "
                              "outputs/demo_trading/tiny_entry_permission_gate/."))
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        allow_real_entry_permission=args.allow_real_entry_permission,
        allow_real_tiny_entry=args.allow_real_tiny_entry,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
