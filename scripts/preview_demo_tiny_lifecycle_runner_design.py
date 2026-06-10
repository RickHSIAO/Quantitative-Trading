"""
scripts/preview_demo_tiny_lifecycle_runner_design.py
TASK-014AB: Tiny Lifecycle Real Execution Runner DESIGN CLI.

Usage (DESIGN CHECKLIST --- default, no network, no implementation):
  python scripts/preview_demo_tiny_lifecycle_runner_design.py \\
    --from-latest-readonly \\
    --from-latest-reconciliation \\
    --from-latest-protection \\
    --from-latest-contract \\
    --from-latest-noop-plan \\
    --from-latest-lifecycle \\
    --from-latest-real-permission \\
    --from-latest-tiny-entry-permission \\
    --from-latest-tiny-stop-permission \\
    --from-latest-tiny-cleanup-permission \\
    --from-latest-lifecycle-summary \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (RUNNER DESIGN APPROVAL DRY RUN --- envelope-only):
  ... --allow-runner-design-approval

Usage (REAL RUNNER EXECUTION GUARD --- always returns
       REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED, no socket opened,
       no runner implemented):
  ... --allow-real-runner-execution

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
  outputs/demo_trading/tiny_entry_permission_gate/latest_tiny_entry_permission_gate.json
  outputs/demo_trading/tiny_stop_attach_permission_gate/latest_tiny_stop_attach_permission_gate.json
  outputs/demo_trading/tiny_cleanup_permission_gate/latest_tiny_cleanup_permission_gate.json
  outputs/demo_trading/tiny_lifecycle_real_execution_summary/latest_tiny_lifecycle_real_execution_summary.json

Writes (when --write-report):
  outputs/demo_trading/tiny_lifecycle_runner_design/
      {ts}_tiny_lifecycle_runner_design.json
      {ts}_tiny_lifecycle_runner_design.md
      latest_tiny_lifecycle_runner_design.json
      latest_tiny_lifecycle_runner_design.md

IMPORTANT:
  - TASK-014AB writes a runner DESIGN document only.  No real runner is
    implemented and no endpoint is invoked.  No network, no socket,
    no environment-variable reads, no signing, no order send.
  - Even with --allow-runner-design-approval the gate only emits a
    sanitized design report.
  - Even with --allow-real-runner-execution the gate returns
    REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED (no socket opened).
  - The forbidden flags --execute-real-lifecycle / --execute-real-entry
    / --execute-real-stop / --execute-real-cleanup are deliberately
    NOT exposed by this CLI.
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT
    lifted by this task.
  - The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) are NEVER touched.
  - /v5/order/create is NEVER invoked from this CLI.
  - /v5/position/trading-stop is NEVER invoked from this CLI.
  - No close-only sender / no emergency-close sender is invoked.

Exit codes:
  0  design_ready / design_ready_exec_disabled /
     real_runner_execution_not_implemented
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

from src.demo_tiny_lifecycle_runner_design import (
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyLifecycleRunnerDesign,
    TinyLifecycleRunnerDesignResult,
    STATUS_DESIGN_READY,
    STATUS_DESIGN_READY_EXEC_DISABLED,
    STATUS_REAL_RUNNER_NOT_IMPL,
)

_SEP = "-" * 72
_DEFAULT_READONLY_DIR        = ROOT / "outputs" / "demo_trading" / "readonly_smoke"
_DEFAULT_RECON_DIR           = ROOT / "outputs" / "demo_trading" / "reconciliation"
_DEFAULT_PROTECTION_DIR      = ROOT / "outputs" / "demo_trading" / "new_entry_protection"
_DEFAULT_CONTRACT_DIR        = ROOT / "outputs" / "demo_trading" / "trading_stop_contract"
_DEFAULT_NOOP_PLAN_DIR       = ROOT / "outputs" / "demo_trading" / "trading_stop_noop_probe_plan"
_DEFAULT_LIFECYCLE_DIR       = ROOT / "outputs" / "demo_trading" / "tiny_position_lifecycle_mock"
_DEFAULT_REAL_PERMISSION_DIR = ROOT / "outputs" / "demo_trading" / "tiny_position_real_permission_gate"
_DEFAULT_TINY_ENTRY_DIR      = ROOT / "outputs" / "demo_trading" / "tiny_entry_permission_gate"
_DEFAULT_TINY_STOP_DIR       = ROOT / "outputs" / "demo_trading" / "tiny_stop_attach_permission_gate"
_DEFAULT_TINY_CLEANUP_DIR    = ROOT / "outputs" / "demo_trading" / "tiny_cleanup_permission_gate"
_DEFAULT_LIFECYCLE_SUMMARY_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_lifecycle_real_execution_summary"
)
_DEFAULT_OUTPUT_DIR          = ROOT / "outputs" / "demo_trading" / "tiny_lifecycle_runner_design"


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


def load_latest_tiny_entry_permission(tiny_entry_dir: Path) -> dict | None:
    return _load_json(
        tiny_entry_dir / "latest_tiny_entry_permission_gate.json"
    )


def load_latest_tiny_stop_attach_permission(tiny_stop_dir: Path) -> dict | None:
    return _load_json(
        tiny_stop_dir / "latest_tiny_stop_attach_permission_gate.json"
    )


def load_latest_tiny_cleanup_permission(tiny_cleanup_dir: Path) -> dict | None:
    return _load_json(
        tiny_cleanup_dir / "latest_tiny_cleanup_permission_gate.json"
    )


def load_latest_lifecycle_summary(lifecycle_summary_dir: Path) -> dict | None:
    return _load_json(
        lifecycle_summary_dir / "latest_tiny_lifecycle_real_execution_summary.json"
    )


def _print_result(r: TinyLifecycleRunnerDesignResult) -> None:
    print(f"  timestamp_utc                              : {r.timestamp_utc}")
    print(f"  mode                                       : {r.mode}")
    print(f"  selected_symbol                            : {r.selected_symbol or '(none)'}")
    print(f"  existing_position_symbols                  : {r.existing_position_symbols}")
    print(f"  entry_token_pattern                        : {r.entry_token_pattern}")
    print(f"  stop_attach_token_pattern                  : {r.stop_attach_token_pattern}")
    print(f"  cleanup_token_pattern                      : {r.cleanup_token_pattern}")
    print(f"  runner_states ({len(r.runner_states)}):")
    for s in r.runner_states:
        print(f"    - {s}")
    print(f"  required_audit_artifacts ({len(r.required_audit_artifacts)}):")
    for a in r.required_audit_artifacts:
        print(f"    - {a}")
    print(f"  entry_payload_preview                      : {r.entry_payload_preview}")
    print(f"  stop_payload_preview                       : {r.stop_payload_preview}")
    print(f"  cleanup_payload_preview                    : {r.cleanup_payload_preview}")
    print(f"  expected_entry_reference_price             : {r.expected_entry_reference_price}")
    print(f"  runner_design_approval_allowed             : {r.runner_design_approval_allowed}")
    print(f"  real_runner_execution_requested            : {r.real_runner_execution_requested}")
    print(f"  real_execution_allowed                     : {r.real_execution_allowed}")
    print(f"  real_runner_implemented                    : {r.real_runner_implemented}")
    print(f"  current_task_real_execution_allowed        : {r.current_task_real_execution_allowed}")
    print(f"  order_create_path_ref                      : {r.order_create_path_ref}  (NOT invoked)")
    print(f"  trading_stop_path_ref                      : {r.trading_stop_path_ref}  (NOT invoked)")
    print(f"  base_url_ref                               : {r.base_url_ref}")
    print(f"  order_endpoint_called                      : {r.order_endpoint_called}")
    print(f"  stop_endpoint_called                       : {r.stop_endpoint_called}")
    print(f"  no_position_modified                       : {r.no_position_modified}")
    print(f"  no_live_endpoint                           : {r.no_live_endpoint}")
    print(f"  no_orders_sent                             : {r.no_orders_sent}")
    print(f"  no_batch_order                             : {r.no_batch_order}")
    print(f"  no_close_only_path                         : {r.no_close_only_path}")
    print(f"  emergency_close_invoked                    : {r.emergency_close_invoked}")
    print(f"  leverage_mutated                           : {r.leverage_mutated}")
    print(f"  transfer_invoked                           : {r.transfer_invoked}")
    print(f"  secret_value_observed                      : {r.secret_value_observed}")
    print(f"  g20_policy_still_in_place                  : {r.g20_policy_still_in_place}")
    print(f"  g20_lifted                                 : {r.g20_lifted}")
    print(f"  existing_positions_touched                 : {r.existing_positions_touched}")
    print(f"  upstream_lifecycle_summary_status          : {r.upstream_lifecycle_summary_status}")
    print(f"  failed_stage                               : {r.failed_stage or '(none)'}")
    print(f"  status                                     : {r.status}")
    print(f"  next_required_task                         : {r.next_required_task}")
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
    r: TinyLifecycleRunnerDesignResult,
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
    json_path   = output_dir / f"{ts_safe}_tiny_lifecycle_runner_design.json"
    json_latest = output_dir / "latest_tiny_lifecycle_runner_design.json"
    md_path     = output_dir / f"{ts_safe}_tiny_lifecycle_runner_design.md"
    md_latest   = output_dir / "latest_tiny_lifecycle_runner_design.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines: list[str] = [
        "# Tiny Lifecycle Real Execution Runner Design (TASK-014AB)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        f"failed_stage: `{r.failed_stage or '(none)'}`  ",
        "",
        "## Final Design",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol or '(none)'} |",
        f"| existing_position_symbols | {', '.join(r.existing_position_symbols) or '(none)'} |",
        f"| entry_token_pattern | {r.entry_token_pattern} |",
        f"| stop_attach_token_pattern | {r.stop_attach_token_pattern} |",
        f"| cleanup_token_pattern | {r.cleanup_token_pattern} |",
        f"| expected_entry_reference_price | {r.expected_entry_reference_price} |",
        f"| upstream_lifecycle_summary_status | {r.upstream_lifecycle_summary_status} |",
        f"| runner_design_approval_allowed | {r.runner_design_approval_allowed} |",
        f"| real_runner_execution_requested | {r.real_runner_execution_requested} |",
        f"| real_execution_allowed | {r.real_execution_allowed} |",
        f"| real_runner_implemented | {r.real_runner_implemented} |",
        f"| current_task_real_execution_allowed | {r.current_task_real_execution_allowed} |",
        f"| next_required_task | {r.next_required_task} |",
        "",
        "## Runner State Machine (18 states, design-only)",
        "",
    ]
    for i, state in enumerate(r.runner_states, start=1):
        md_lines.append(f"{i}. `{state}`")
    md_lines += [
        "",
        "## Required Per-Step Audit Artifacts (11 slots)",
        "",
    ]
    for i, art in enumerate(r.required_audit_artifacts, start=1):
        md_lines.append(f"{i}. `{art}`")
    md_lines += [
        "",
        "## Runner Design Scope",
        "",
        "```json",
        json.dumps(r.runner_design_scope, indent=2),
        "```",
        "",
        "## State Machine Design",
        "",
        "```json",
        json.dumps(r.state_machine_design, indent=2),
        "```",
        "",
        "## Manual Approval Contract",
        "",
        "```json",
        json.dumps(r.manual_approval_contract, indent=2),
        "```",
        "",
        "## Execution Payload Contract (preview-only, NEVER converted)",
        "",
        "```json",
        json.dumps(r.execution_payload_contract, indent=2),
        "```",
        "",
        "## Entry Payload Preview (NEVER sent)",
        "",
        "```json",
        json.dumps(r.entry_payload_preview, indent=2),
        "```",
        "",
        "## Stop Payload Preview (NEVER sent)",
        "",
        "```json",
        json.dumps(r.stop_payload_preview, indent=2),
        "```",
        "",
        "## Cleanup Payload Preview (NEVER sent)",
        "",
        "```json",
        json.dumps(r.cleanup_payload_preview, indent=2),
        "```",
        "",
        "## Abort / Fail-Closed Policy",
        "",
        "```json",
        json.dumps(r.abort_and_fail_closed_policy, indent=2),
        "```",
        "",
        "## Observability and Audit Design",
        "",
        "```json",
        json.dumps(r.observability_and_audit_design, indent=2),
        "```",
        "",
        "## Final Design Verdict",
        "",
        "```json",
        json.dumps(r.final_design_verdict, indent=2),
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
        f"- order_create_path_ref: `{r.order_create_path_ref}` (NOT invoked)",
        f"- trading_stop_path_ref: `{r.trading_stop_path_ref}` (NOT invoked)",
        f"- base_url_ref: `{r.base_url_ref}` (informational only)",
        f"- order_endpoint_called: `{r.order_endpoint_called}`",
        f"- stop_endpoint_called: `{r.stop_endpoint_called}`",
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
        f"- existing_positions_touched: `{r.existing_positions_touched}`",
        "",
        "> TASK-014AB is a RUNNER DESIGN module.  It NEVER opens a socket,",
        "> NEVER invokes /v5/order/create, NEVER invokes",
        "> /v5/position/trading-stop, NEVER modifies any position, NEVER",
        "> invokes the close-only sender, NEVER invokes the emergency-close",
        "> sender, NEVER reads environment variables / secrets, NEVER signs",
        "> any request, and NEVER lifts TASK-014L sender G20",
        "> (protected_entry_policy_missing).",
        "> The 5 existing demo positions are NEVER touched.",
        "> Real runner execution is reserved for a future task",
        "> (TASK-014AC dry-run runner implementation design); even with",
        "> --allow-real-runner-execution this task returns",
        "> REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED.",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:                          str  = DEFAULT_SELECTED_SYMBOL,
    allow_runner_design_approval:    bool = False,
    allow_real_runner_execution:     bool = False,
    write_report:                    bool = False,
    readonly_dir:                    Path | None = None,
    reconciliation_dir:              Path | None = None,
    protection_dir:                  Path | None = None,
    contract_dir:                    Path | None = None,
    noop_plan_dir:                   Path | None = None,
    lifecycle_dir:                   Path | None = None,
    real_permission_dir:             Path | None = None,
    tiny_entry_dir:                  Path | None = None,
    tiny_stop_attach_dir:            Path | None = None,
    tiny_cleanup_dir:                Path | None = None,
    lifecycle_summary_dir:           Path | None = None,
    output_dir:                      Path | None = None,
    _now:                            datetime | None = None,
) -> int:
    _ro_dir            = readonly_dir          or _DEFAULT_READONLY_DIR
    _recon_dir         = reconciliation_dir    or _DEFAULT_RECON_DIR
    _protect_dir       = protection_dir        or _DEFAULT_PROTECTION_DIR
    _contract_dir      = contract_dir          or _DEFAULT_CONTRACT_DIR
    _noop_dir          = noop_plan_dir         or _DEFAULT_NOOP_PLAN_DIR
    _lifecycle_dir     = lifecycle_dir         or _DEFAULT_LIFECYCLE_DIR
    _real_perm_dir     = real_permission_dir   or _DEFAULT_REAL_PERMISSION_DIR
    _entry_perm_dir    = tiny_entry_dir        or _DEFAULT_TINY_ENTRY_DIR
    _stop_perm_dir     = tiny_stop_attach_dir  or _DEFAULT_TINY_STOP_DIR
    _cleanup_perm_dir  = tiny_cleanup_dir      or _DEFAULT_TINY_CLEANUP_DIR
    _summary_dir       = lifecycle_summary_dir or _DEFAULT_LIFECYCLE_SUMMARY_DIR
    _out_dir           = output_dir            or _DEFAULT_OUTPUT_DIR

    print(_SEP)
    if allow_real_runner_execution:
        print("REAL RUNNER EXECUTION GUARD --- NO NETWORK --- REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED")
    elif allow_runner_design_approval:
        print("RUNNER DESIGN APPROVAL DRY RUN --- NO NETWORK --- envelope-only")
    else:
        print("DESIGN CHECKLIST --- NO NETWORK --- envelope-only")
    print("TASK-014AB: Tiny Lifecycle Real Execution Runner Design / Manual Approval")
    print(_SEP)

    readonly             = load_latest_readonly(_ro_dir)
    reconciliation       = load_latest_reconciliation(_recon_dir)
    protection           = load_latest_protection(_protect_dir)
    contract             = load_latest_contract(_contract_dir)
    noop_plan            = load_latest_noop_plan(_noop_dir)
    lifecycle            = load_latest_lifecycle(_lifecycle_dir)
    real_permission_gate = load_latest_real_permission(_real_perm_dir)
    tiny_entry_perm_gate = load_latest_tiny_entry_permission(_entry_perm_dir)
    tiny_stop_perm_gate  = load_latest_tiny_stop_attach_permission(_stop_perm_dir)
    tiny_cleanup_perm_gate = load_latest_tiny_cleanup_permission(_cleanup_perm_dir)
    lifecycle_summary    = load_latest_lifecycle_summary(_summary_dir)

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
    if tiny_entry_perm_gate is None:
        missing.append(
            str(_entry_perm_dir / "latest_tiny_entry_permission_gate.json")
        )
    if tiny_stop_perm_gate is None:
        missing.append(
            str(_stop_perm_dir / "latest_tiny_stop_attach_permission_gate.json")
        )
    if tiny_cleanup_perm_gate is None:
        missing.append(
            str(_cleanup_perm_dir / "latest_tiny_cleanup_permission_gate.json")
        )
    if lifecycle_summary is None:
        missing.append(
            str(_summary_dir / "latest_tiny_lifecycle_real_execution_summary.json")
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

    print(f"\n  symbol                  : {symbol}")
    print(f"  readonly_src            : {_ro_dir / 'latest_smoke.json'} (primary)")
    print(f"  reconciliation_src      : {_recon_dir / 'latest_reconciliation.json'}")
    print(f"  protection_src          : {_protect_dir / 'latest_new_entry_protection.json'}")
    print(f"  contract_src            : {_contract_dir / 'latest_trading_stop_contract.json'}")
    print(f"  noop_plan_src           : {_noop_dir / 'latest_trading_stop_noop_probe_plan.json'} (primary)")
    print(f"  lifecycle_src           : {_lifecycle_dir / 'latest_tiny_position_lifecycle_mock.json'}")
    print(f"  real_permission_src     : {_real_perm_dir / 'latest_tiny_position_real_permission_gate.json'}")
    print(f"  tiny_entry_perm_src     : {_entry_perm_dir / 'latest_tiny_entry_permission_gate.json'}")
    print(f"  tiny_stop_perm_src      : {_stop_perm_dir / 'latest_tiny_stop_attach_permission_gate.json'}")
    print(f"  tiny_cleanup_perm_src   : {_cleanup_perm_dir / 'latest_tiny_cleanup_permission_gate.json'}")
    print(f"  lifecycle_summary_src   : {_summary_dir / 'latest_tiny_lifecycle_real_execution_summary.json'}")

    gate    = DemoTinyLifecycleRunnerDesign()
    result  = gate.run_checklist(
        readonly_smoke=readonly,
        reconciliation=reconciliation,
        protection=protection,
        contract=contract,
        noop_plan=noop_plan,
        lifecycle_mock=lifecycle,
        real_permission_gate=real_permission_gate,
        tiny_entry_permission_gate=tiny_entry_perm_gate,
        tiny_stop_attach_permission_gate=tiny_stop_perm_gate,
        tiny_cleanup_permission_gate=tiny_cleanup_perm_gate,
        lifecycle_summary=lifecycle_summary,
        symbol=symbol,
        allow_runner_design_approval=allow_runner_design_approval,
        allow_real_runner_execution=allow_real_runner_execution,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _out_dir)

    if result.status in (
        STATUS_DESIGN_READY,
        STATUS_DESIGN_READY_EXEC_DISABLED,
        STATUS_REAL_RUNNER_NOT_IMPL,
    ):
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Tiny lifecycle real-execution RUNNER DESIGN / MANUAL APPROVAL. "
            "No network, no live endpoint, no orders / positions modified, "
            "no real runner implemented, no close-only sender, no "
            "emergency-close sender.  Even with --allow-runner-design-approval "
            "this only emits a checklist; even with "
            "--allow-real-runner-execution it returns "
            "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED."
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
    parser.add_argument("--from-latest-tiny-entry-permission", action="store_true",
                        help="Read tiny entry permission gate JSON from outputs/.../tiny_entry_permission_gate/.")
    parser.add_argument("--from-latest-tiny-stop-permission", action="store_true",
                        help="Read tiny stop-attach permission gate JSON from outputs/.../tiny_stop_attach_permission_gate/.")
    parser.add_argument("--from-latest-tiny-cleanup-permission", action="store_true",
                        help="Read tiny cleanup permission gate JSON from outputs/.../tiny_cleanup_permission_gate/.")
    parser.add_argument("--from-latest-lifecycle-summary", action="store_true",
                        help=("Read tiny lifecycle real execution summary JSON "
                              "(TASK-014AA artifact) from "
                              "outputs/.../tiny_lifecycle_real_execution_summary/."))
    parser.add_argument("--symbol", default=DEFAULT_SELECTED_SYMBOL,
                        metavar="SYMBOL",
                        help=("Symbol to plan against.  MUST NOT be in the "
                              "5 existing demo position symbols (ENAUSDT / "
                              "TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT)."))
    parser.add_argument("--allow-runner-design-approval", action="store_true",
                        help=("Promote envelope to runner_design_approval_dry_run.  "
                              "Even with this flag, TASK-014AB only emits a "
                              "checklist / design report.  No execution, no "
                              "implementation."))
    parser.add_argument("--allow-real-runner-execution", action="store_true",
                        help=("Guarded flag for a hypothetical future real "
                              "tiny lifecycle runner execution.  TASK-014AB "
                              "returns REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED "
                              "even when this flag is set (no socket opened, "
                              "no runner implemented)."))
    parser.add_argument("--write-report", action="store_true",
                        help=("Write JSON + Markdown report to "
                              "outputs/demo_trading/tiny_lifecycle_runner_design/."))
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        allow_runner_design_approval=args.allow_runner_design_approval,
        allow_real_runner_execution=args.allow_real_runner_execution,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
