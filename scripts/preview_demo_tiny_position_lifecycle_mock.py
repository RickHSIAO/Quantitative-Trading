"""
scripts/preview_demo_tiny_position_lifecycle_mock.py
TASK-014V: Demo Tiny Isolated Position Lifecycle Mock CLI.

Usage (PREVIEW --- default, no network, envelope-only):
  python scripts/preview_demo_tiny_position_lifecycle_mock.py \\
    --from-latest-readonly \\
    --from-latest-reconciliation \\
    --from-latest-protection \\
    --from-latest-contract \\
    --from-latest-noop-plan \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (MOCK LIFECYCLE --- runs 7 in-memory phases):
  python scripts/preview_demo_tiny_position_lifecycle_mock.py \\
    --from-latest-readonly --from-latest-reconciliation \\
    --from-latest-protection --from-latest-contract \\
    --from-latest-noop-plan \\
    --symbol SOLUSDT \\
    --mock-lifecycle \\
    [--simulate-stop-attach-failure] \\
    [--simulate-cleanup-failure] \\
    [--simulate-existing-stop-mismatch] \\
    [--write-report]

Usage (REAL TINY POSITION GUARD --- always returns
       REAL_TINY_POSITION_NOT_IMPLEMENTED):
  python scripts/preview_demo_tiny_position_lifecycle_mock.py \\
    --from-latest-readonly --from-latest-reconciliation \\
    --from-latest-protection --from-latest-contract \\
    --from-latest-noop-plan \\
    --symbol SOLUSDT \\
    --allow-real-tiny-position \\
    [--write-report]

Reads:
  outputs/demo_trading/readonly_smoke/latest_smoke.json
      (legacy fallback: latest_readonly_smoke.json)
  outputs/demo_trading/reconciliation/latest_reconciliation.json
  outputs/demo_trading/new_entry_protection/latest_new_entry_protection.json
  outputs/demo_trading/trading_stop_contract/latest_trading_stop_contract.json
  outputs/demo_trading/trading_stop_noop_probe_plan/latest_trading_stop_noop_probe_plan.json
      (legacy fallback: latest_noop_probe_plan.json)

Writes (when --write-report):
  outputs/demo_trading/tiny_position_lifecycle_mock/
      {ts}_tiny_position_lifecycle_mock.json
      {ts}_tiny_position_lifecycle_mock.md
      latest_tiny_position_lifecycle_mock.json
      latest_tiny_position_lifecycle_mock.md

IMPORTANT:
  - This is a MOCK module.  No network at all.  Even with
    --allow-real-tiny-position + presence of all five upstream
    artifacts, the simulator returns REAL_TINY_POSITION_NOT_IMPLEMENTED.
    Executing the real tiny position lifecycle is the subject of
    TASK-014W+.
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT
    lifted by this task.
  - The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) are NEVER touched.

Exit codes:
  0  preview / mock_success / real_tiny_not_implemented
  1  fail_closed / mock_fail_closed / missing upstream / missing symbol
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

from src.demo_tiny_position_lifecycle_mock import (
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyPositionLifecycleMock,
    TinyPositionLifecycleResult,
    STATUS_PREVIEW_READY,
    STATUS_MOCK_SUCCESS,
    STATUS_MOCK_FAIL_CLOSED,
    STATUS_REAL_TINY_NOT_IMPLEMENTED,
)

_SEP = "-" * 72
_DEFAULT_READONLY_DIR    = ROOT / "outputs" / "demo_trading" / "readonly_smoke"
_DEFAULT_RECON_DIR       = ROOT / "outputs" / "demo_trading" / "reconciliation"
_DEFAULT_PROTECTION_DIR  = ROOT / "outputs" / "demo_trading" / "new_entry_protection"
_DEFAULT_CONTRACT_DIR    = ROOT / "outputs" / "demo_trading" / "trading_stop_contract"
_DEFAULT_NOOP_PLAN_DIR   = ROOT / "outputs" / "demo_trading" / "trading_stop_noop_probe_plan"
_DEFAULT_OUTPUT_DIR      = ROOT / "outputs" / "demo_trading" / "tiny_position_lifecycle_mock"


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


def _print_result(r: TinyPositionLifecycleResult) -> None:
    print(f"  mode                              : {r.mode}")
    print(f"  selected_symbol                   : {r.selected_symbol or '(none)'}")
    print(f"  existing_position_symbols         : {r.existing_position_symbols}")
    print(f"  tiny_qty                          : {r.tiny_qty}")
    print(f"  tiny_notional                     : {r.tiny_notional}")
    print(f"  entry_reference_price             : {r.entry_reference_price}")
    print(f"  stop_price                        : {r.stop_price}")
    print(f"  tiny_side                         : {r.tiny_side or '(none)'}")
    print(f"  mock_entry_order_link_id          : {r.mock_entry_order_link_id or '(none)'}")
    print(f"  mock_stop_envelope_id             : {r.mock_stop_envelope_id or '(none)'}")
    print(f"  mock_cleanup_order_link_id        : {r.mock_cleanup_order_link_id or '(none)'}")
    print(f"  real_execution_allowed            : {r.real_execution_allowed}")
    print(f"  real_tiny_position_implemented    : {r.real_tiny_position_implemented}")
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
    print(f"  dangling_tiny_position            : {r.dangling_tiny_position}")
    print(f"  existing_position_stop_snapshot_match: {r.existing_position_stop_snapshot_match}")
    print(f"  existing_positions_touched        : {r.existing_positions_touched}")
    print(f"  failed_phase                      : {r.failed_phase or '(none)'}")
    print(f"  status                            : {r.status}")
    if r.blocked_gates:
        print(f"  blocked_gates ({len(r.blocked_gates)}):")
        for g in r.blocked_gates:
            print(f"    - {g}")
    print("  phases:")
    for phase_id in r.phase_order:
        env = r.phases.get(phase_id)
        if env is None:
            print(f"    - {phase_id}: (not run)")
            continue
        summary = env.get("summary", "")
        print(f"    - {phase_id}: {summary}")


def _write_report(r: TinyPositionLifecycleResult, output_dir: Path) -> None:
    output_dir.mkdir(parents=True, exist_ok=True)
    ts_safe = (
        r.timestamp_utc
        .replace(":", "")
        .replace("-", "")
        .replace("T", "_")
        .replace("Z", "")
    )
    json_path    = output_dir / f"{ts_safe}_tiny_position_lifecycle_mock.json"
    json_latest  = output_dir / "latest_tiny_position_lifecycle_mock.json"
    md_path      = output_dir / f"{ts_safe}_tiny_position_lifecycle_mock.md"
    md_latest    = output_dir / "latest_tiny_position_lifecycle_mock.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines: list[str] = [
        "# Demo Tiny Isolated Position Lifecycle Mock (TASK-014V)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        f"failed_phase: `{r.failed_phase or '(none)'}`  ",
        "",
        "## Selection",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol or '(none)'} |",
        f"| existing_position_symbols | {', '.join(r.existing_position_symbols) or '(none)'} |",
        f"| tiny_qty | {r.tiny_qty} |",
        f"| tiny_notional | {r.tiny_notional} |",
        f"| entry_reference_price | {r.entry_reference_price} |",
        f"| stop_price | {r.stop_price} |",
        f"| tiny_side | {r.tiny_side or '(none)'} |",
        f"| mock_entry_order_link_id | `{r.mock_entry_order_link_id or '(none)'}` |",
        f"| mock_stop_envelope_id | `{r.mock_stop_envelope_id or '(none)'}` |",
        f"| mock_cleanup_order_link_id | `{r.mock_cleanup_order_link_id or '(none)'}` |",
        f"| real_execution_allowed | {r.real_execution_allowed} |",
        f"| real_tiny_position_implemented | {r.real_tiny_position_implemented} |",
        f"| current_task_real_execution_allowed | {r.current_task_real_execution_allowed} |",
        f"| next_required_task | {r.next_required_task} |",
        "",
        "## Phases",
        "",
    ]
    for phase_id in r.phase_order:
        env = r.phases.get(phase_id)
        if env is None:
            md_lines += [
                f"### Phase: `{phase_id}`",
                "",
                "- (not run)",
                "",
            ]
            continue
        md_lines += [
            f"### Phase: `{phase_id}`",
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
        f"- secret_value_observed: `{r.secret_value_observed}`",
        f"- g20_policy_still_in_place: `{r.g20_policy_still_in_place}`",
        f"- dangling_tiny_position: `{r.dangling_tiny_position}`",
        f"- existing_position_stop_snapshot_match: `{r.existing_position_stop_snapshot_match}`",
        f"- existing_positions_touched: `{r.existing_positions_touched}`",
        "",
        "> This lifecycle mock NEVER opens a socket.",
        "> /v5/position/trading-stop and /v5/order/create are documented",
        "> string references; neither is invoked.",
        "> The 5 existing demo positions are NEVER touched.",
        "> Real tiny-position execution is deliberately not implemented in",
        "> TASK-014V; the real-execution permission gate is the subject of",
        "> TASK-014W.",
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
    symbol:                          str  = DEFAULT_SELECTED_SYMBOL,
    mock_lifecycle:                  bool = False,
    allow_real_tiny_position:        bool = False,
    simulate_stop_attach_failure:    bool = False,
    simulate_cleanup_failure:        bool = False,
    simulate_existing_stop_mismatch: bool = False,
    write_report:                    bool = False,
    readonly_dir:                    Path | None = None,
    reconciliation_dir:              Path | None = None,
    protection_dir:                  Path | None = None,
    contract_dir:                    Path | None = None,
    noop_plan_dir:                   Path | None = None,
    output_dir:                      Path | None = None,
    _now:                            datetime | None = None,
) -> int:
    _ro_dir       = readonly_dir       or _DEFAULT_READONLY_DIR
    _recon_dir    = reconciliation_dir or _DEFAULT_RECON_DIR
    _protect_dir  = protection_dir     or _DEFAULT_PROTECTION_DIR
    _contract_dir = contract_dir       or _DEFAULT_CONTRACT_DIR
    _noop_dir     = noop_plan_dir      or _DEFAULT_NOOP_PLAN_DIR
    _out_dir      = output_dir         or _DEFAULT_OUTPUT_DIR

    print(_SEP)
    if allow_real_tiny_position:
        print("REAL TINY POSITION GUARD --- NO NETWORK --- REAL_TINY_POSITION_NOT_IMPLEMENTED")
    elif mock_lifecycle:
        print("MOCK LIFECYCLE --- NO NETWORK --- 7-phase in-memory simulation")
    else:
        print("PREVIEW --- NO NETWORK --- envelope-only")
    print("TASK-014V: Demo Tiny Isolated Position Lifecycle Mock")
    print(_SEP)

    readonly       = load_latest_readonly(_ro_dir)
    reconciliation = load_latest_reconciliation(_recon_dir)
    protection     = load_latest_protection(_protect_dir)
    contract       = load_latest_contract(_contract_dir)
    noop_plan      = load_latest_noop_plan(_noop_dir)

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
    print(f"  noop_plan_src      : {_noop_dir / 'latest_trading_stop_noop_probe_plan.json'} (primary)")

    sim = DemoTinyPositionLifecycleMock()
    result  = sim.run_lifecycle(
        readonly_smoke=readonly,
        reconciliation=reconciliation,
        protection=protection,
        contract=contract,
        noop_plan=noop_plan,
        symbol=symbol,
        mock_lifecycle=mock_lifecycle,
        allow_real_tiny_position=allow_real_tiny_position,
        _simulate_stop_attach_failure=simulate_stop_attach_failure,
        _simulate_cleanup_failure=simulate_cleanup_failure,
        _simulate_existing_stop_mismatch=simulate_existing_stop_mismatch,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _out_dir)

    if result.status in (
        STATUS_PREVIEW_READY,
        STATUS_MOCK_SUCCESS,
        STATUS_REAL_TINY_NOT_IMPLEMENTED,
    ):
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Demo tiny isolated position lifecycle MOCK --- preview / "
            "mock_lifecycle / real_tiny_position_guard.  No network, no "
            "live endpoint, no orders / positions modified, no real "
            "trading-stop call.  Even with --allow-real-tiny-position "
            "the simulator returns REAL_TINY_POSITION_NOT_IMPLEMENTED."
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
    parser.add_argument("--symbol", default=DEFAULT_SELECTED_SYMBOL,
                        metavar="SYMBOL",
                        help=("Symbol to plan against.  MUST NOT be in the "
                              "5 existing demo position symbols (ENAUSDT / "
                              "TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT)."))
    parser.add_argument("--mock-lifecycle", action="store_true",
                        help=("Run all 7 in-memory phases.  No network."))
    parser.add_argument("--simulate-stop-attach-failure", action="store_true",
                        help="Inject phase-3 stop-attach failure.")
    parser.add_argument("--simulate-cleanup-failure", action="store_true",
                        help="Inject phase-5 cleanup failure.")
    parser.add_argument("--simulate-existing-stop-mismatch", action="store_true",
                        help="Inject phase-4 stop snapshot mismatch.")
    parser.add_argument("--allow-real-tiny-position", action="store_true",
                        help=("Guarded flag for the future real tiny "
                              "position lifecycle.  TASK-014V returns "
                              "REAL_TINY_POSITION_NOT_IMPLEMENTED even "
                              "when this flag is set (no socket opened)."))
    parser.add_argument("--write-report", action="store_true",
                        help=("Write JSON + Markdown report to "
                              "outputs/demo_trading/tiny_position_lifecycle_mock/."))
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        mock_lifecycle=args.mock_lifecycle,
        allow_real_tiny_position=args.allow_real_tiny_position,
        simulate_stop_attach_failure=args.simulate_stop_attach_failure,
        simulate_cleanup_failure=args.simulate_cleanup_failure,
        simulate_existing_stop_mismatch=args.simulate_existing_stop_mismatch,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
