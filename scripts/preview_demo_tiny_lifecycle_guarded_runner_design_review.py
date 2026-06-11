"""
scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py
TASK-014AD: Tiny Lifecycle Real Execution Guarded Runner Design Review CLI.

Usage (DESIGN REVIEW CHECKLIST --- default, no network, no implementation):
  python scripts/preview_demo_tiny_lifecycle_guarded_runner_design_review.py \\
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
    --from-latest-runner-design \\
    --from-latest-runner-dry-run \\
    --symbol SOLUSDT \\
    [--write-report]

Usage (GUARDED DESIGN APPROVAL DRY RUN --- design-only, no execution):
  ... --allow-guarded-design-approval

Usage (REAL RUNNER EXECUTION GUARD --- always returns
       REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED, no socket opened,
       no real runner implemented, no guarded runner implemented):
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
  outputs/demo_trading/tiny_lifecycle_runner_design/latest_tiny_lifecycle_runner_design.json
  outputs/demo_trading/tiny_lifecycle_runner_dry_run/latest_tiny_lifecycle_runner_dry_run.json

Writes (when --write-report):
  outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/
      {ts}_tiny_lifecycle_guarded_runner_design_review.json
      {ts}_tiny_lifecycle_guarded_runner_design_review.md
      latest_tiny_lifecycle_guarded_runner_design_review.json
      latest_tiny_lifecycle_guarded_runner_design_review.md

IMPORTANT:
  - TASK-014AD produces a DESIGN REVIEW artifact only.  No guarded
    runner, no real runner is implemented.  No endpoint is invoked.
    No network, no socket, no environment-variable reads, no signing,
    no order send.
  - Even with --allow-guarded-design-approval the review only emits a
    sanitized design-review report.  Readiness conclusion is fixed at
    DESIGN_REVIEW_READY_NOT_EXECUTABLE.
  - Even with --allow-real-runner-execution the review returns
    REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED (no socket opened).
  - No --execute-real-* / --send-order / --place-order / --real-run
    flag is exposed by this CLI.
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT
    lifted by this task.
  - The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) are NEVER touched.
  - /v5/order/create is NEVER invoked from this CLI.
  - /v5/position/trading-stop is NEVER invoked from this CLI.
  - No close-only sender / no emergency-close sender / no new-entry
    sender real execution path is invoked.

Exit codes:
  0  design_review_ready / design_review_ready_exec_disabled /
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

from src.demo_tiny_lifecycle_guarded_runner_design_review import (
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyLifecycleGuardedRunnerDesignReview,
    TinyLifecycleGuardedRunnerDesignReviewResult,
    STATUS_DESIGN_REVIEW_READY,
    STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED,
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
_DEFAULT_RUNNER_DESIGN_DIR   = (
    ROOT / "outputs" / "demo_trading" / "tiny_lifecycle_runner_design"
)
_DEFAULT_RUNNER_DRY_RUN_DIR  = (
    ROOT / "outputs" / "demo_trading" / "tiny_lifecycle_runner_dry_run"
)
_DEFAULT_OUTPUT_DIR          = (
    ROOT / "outputs" / "demo_trading" / "tiny_lifecycle_guarded_runner_design_review"
)


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


def load_latest_runner_design(runner_design_dir: Path) -> dict | None:
    return _load_json(
        runner_design_dir / "latest_tiny_lifecycle_runner_design.json"
    )


def load_latest_runner_dry_run(runner_dry_run_dir: Path) -> dict | None:
    return _load_json(
        runner_dry_run_dir / "latest_tiny_lifecycle_runner_dry_run.json"
    )


def _print_result(r: TinyLifecycleGuardedRunnerDesignReviewResult) -> None:
    print(f"  timestamp_utc                              : {r.timestamp_utc}")
    print(f"  mode                                       : {r.mode}")
    print(f"  selected_symbol                            : {r.selected_symbol or '(none)'}")
    print(f"  existing_position_symbols                  : {r.existing_position_symbols}")
    print(f"  entry_token_pattern                        : {r.entry_token_pattern}")
    print(f"  stop_attach_token_pattern                  : {r.stop_attach_token_pattern}")
    print(f"  cleanup_token_pattern                      : {r.cleanup_token_pattern}")
    print(f"  required_confirmation_flags ({len(r.required_confirmation_flags)}):")
    for f in r.required_confirmation_flags:
        print(f"    - {f}")
    print(f"  future_guarded_commands ({len(r.future_guarded_commands)}):")
    for c in r.future_guarded_commands:
        print(f"    - {c}")
    print(f"  guarded_design_approval_allowed            : {r.guarded_design_approval_allowed}")
    print(f"  real_runner_execution_requested            : {r.real_runner_execution_requested}")
    print(f"  real_execution_allowed                     : {r.real_execution_allowed}")
    print(f"  real_runner_implemented                    : {r.real_runner_implemented}")
    print(f"  guarded_runner_implemented                 : {r.guarded_runner_implemented}")
    print(f"  guarded_runner_design_review               : {r.guarded_runner_design_review}")
    print(f"  current_task_real_execution_allowed        : {r.current_task_real_execution_allowed}")
    print(f"  readiness_conclusion                       : {r.readiness_conclusion}")
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
    print(f"  no_secrets_loaded                          : {r.no_secrets_loaded}")
    print(f"  secret_value_observed                      : {r.secret_value_observed}")
    print(f"  g20_policy_still_in_place                  : {r.g20_policy_still_in_place}")
    print(f"  g20_lifted                                 : {r.g20_lifted}")
    print(f"  existing_positions_touched                 : {r.existing_positions_touched}")
    print(f"  upstream_lifecycle_summary_status          : {r.upstream_lifecycle_summary_status}")
    print(f"  upstream_runner_design_status              : {r.upstream_runner_design_status}")
    print(f"  upstream_runner_dry_run_status             : {r.upstream_runner_dry_run_status}")
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
    r: TinyLifecycleGuardedRunnerDesignReviewResult,
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
    base = "tiny_lifecycle_guarded_runner_design_review"
    json_path   = output_dir / f"{ts_safe}_{base}.json"
    json_latest = output_dir / f"latest_{base}.json"
    md_path     = output_dir / f"{ts_safe}_{base}.md"
    md_latest   = output_dir / f"latest_{base}.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines: list[str] = [
        "# Tiny Lifecycle Guarded Runner Design Review (TASK-014AD)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        f"failed_stage: `{r.failed_stage or '(none)'}`  ",
        f"readiness_conclusion: `{r.readiness_conclusion}`  ",
        "",
        "## Final Design Review",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol or '(none)'} |",
        f"| existing_position_symbols | {', '.join(r.existing_position_symbols) or '(none)'} |",
        f"| guarded_design_approval_allowed | {r.guarded_design_approval_allowed} |",
        f"| real_runner_execution_requested | {r.real_runner_execution_requested} |",
        f"| real_execution_allowed | {r.real_execution_allowed} |",
        f"| real_runner_implemented | {r.real_runner_implemented} |",
        f"| guarded_runner_implemented | {r.guarded_runner_implemented} |",
        f"| guarded_runner_design_review | {r.guarded_runner_design_review} |",
        f"| current_task_real_execution_allowed | {r.current_task_real_execution_allowed} |",
        f"| readiness_conclusion | {r.readiness_conclusion} |",
        f"| upstream_lifecycle_summary_status | {r.upstream_lifecycle_summary_status} |",
        f"| upstream_runner_design_status | {r.upstream_runner_design_status} |",
        f"| upstream_runner_dry_run_status | {r.upstream_runner_dry_run_status} |",
        f"| next_required_task | {r.next_required_task} |",
        "",
        "## Required Confirmation Flags (documented, never validated by this task)",
        "",
    ]
    for i, flag in enumerate(r.required_confirmation_flags, start=1):
        md_lines.append(f"{i}. `{flag}`")
    md_lines += [
        "",
        "## Future Guarded Command Set (single-step only)",
        "",
    ]
    for i, cmd in enumerate(r.future_guarded_commands, start=1):
        md_lines.append(f"{i}. `{cmd}`")
    md_lines += [
        "",
        "## Review Scope",
        "",
        "```json",
        json.dumps(r.review_scope, indent=2),
        "```",
        "",
        "## Readiness Matrix (W / X / Y / Z / AA / AB / AC)",
        "",
        "```json",
        json.dumps(r.readiness_matrix, indent=2),
        "```",
        "",
        "## Guarded Runner Minimum Requirements (3 single-step commands)",
        "",
        "```json",
        json.dumps(r.guarded_runner_minimum_requirements, indent=2),
        "```",
        "",
        "## Manual Authorization Model",
        "",
        "```json",
        json.dumps(r.manual_authorization_model, indent=2),
        "```",
        "",
        "## Environment Isolation Review",
        "",
        "```json",
        json.dumps(r.environment_isolation_review, indent=2),
        "```",
        "",
        "## Pre/Post Readonly Contract",
        "",
        "```json",
        json.dumps(r.pre_post_readonly_contract, indent=2),
        "```",
        "",
        "## Failure and Abort Review",
        "",
        "```json",
        json.dumps(r.failure_and_abort_review, indent=2),
        "```",
        "",
        "## Final Guarded Design Verdict",
        "",
        "```json",
        json.dumps(r.final_guarded_design_verdict, indent=2),
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
        f"- no_secrets_loaded: `{r.no_secrets_loaded}`",
        f"- secret_value_observed: `{r.secret_value_observed}`",
        f"- g20_policy_still_in_place: `{r.g20_policy_still_in_place}`",
        f"- g20_lifted: `{r.g20_lifted}`",
        f"- existing_positions_touched: `{r.existing_positions_touched}`",
        "",
        "> TASK-014AD is a DESIGN-REVIEW module.  It NEVER opens a socket,",
        "> NEVER invokes /v5/order/create, NEVER invokes",
        "> /v5/position/trading-stop, NEVER modifies any position, NEVER",
        "> invokes the close-only sender, NEVER invokes the emergency-close",
        "> sender, NEVER invokes the new-entry sender's real execution path,",
        "> NEVER reads environment variables / secrets, NEVER signs any",
        "> request, NEVER implements a guarded runner, NEVER implements a",
        "> real runner, and NEVER lifts TASK-014L sender G20",
        "> (protected_entry_policy_missing).",
        "> The 5 existing demo positions are NEVER touched.",
        "> Even with --allow-guarded-design-approval the review is only",
        "> a design artifact (readiness_conclusion remains",
        "> DESIGN_REVIEW_READY_NOT_EXECUTABLE).",
        "> Even with --allow-real-runner-execution this task returns",
        "> REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED (no socket opened).",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:                          str  = DEFAULT_SELECTED_SYMBOL,
    allow_guarded_design_approval:   bool = False,
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
    runner_design_dir:               Path | None = None,
    runner_dry_run_dir:              Path | None = None,
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
    _design_dir        = runner_design_dir     or _DEFAULT_RUNNER_DESIGN_DIR
    _dry_run_dir       = runner_dry_run_dir    or _DEFAULT_RUNNER_DRY_RUN_DIR
    _out_dir           = output_dir            or _DEFAULT_OUTPUT_DIR

    print(_SEP)
    if allow_real_runner_execution:
        print("REAL RUNNER EXECUTION GUARD --- NO NETWORK --- REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED")
    elif allow_guarded_design_approval:
        print("GUARDED DESIGN APPROVAL DRY RUN --- NO NETWORK --- design-only")
    else:
        print("DESIGN REVIEW CHECKLIST --- NO NETWORK --- design-only")
    print("TASK-014AD: Tiny Lifecycle Real Execution Guarded Runner Design Review")
    print(_SEP)

    readonly               = load_latest_readonly(_ro_dir)
    reconciliation         = load_latest_reconciliation(_recon_dir)
    protection             = load_latest_protection(_protect_dir)
    contract               = load_latest_contract(_contract_dir)
    noop_plan              = load_latest_noop_plan(_noop_dir)
    lifecycle              = load_latest_lifecycle(_lifecycle_dir)
    real_permission_gate   = load_latest_real_permission(_real_perm_dir)
    tiny_entry_perm_gate   = load_latest_tiny_entry_permission(_entry_perm_dir)
    tiny_stop_perm_gate    = load_latest_tiny_stop_attach_permission(_stop_perm_dir)
    tiny_cleanup_perm_gate = load_latest_tiny_cleanup_permission(_cleanup_perm_dir)
    lifecycle_summary      = load_latest_lifecycle_summary(_summary_dir)
    runner_design          = load_latest_runner_design(_design_dir)
    runner_dry_run         = load_latest_runner_dry_run(_dry_run_dir)

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
    if runner_design is None:
        missing.append(
            str(_design_dir / "latest_tiny_lifecycle_runner_design.json")
        )
    if runner_dry_run is None:
        missing.append(
            str(_dry_run_dir / "latest_tiny_lifecycle_runner_dry_run.json")
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
    print(f"  runner_design_src       : {_design_dir / 'latest_tiny_lifecycle_runner_design.json'}")
    print(f"  runner_dry_run_src      : {_dry_run_dir / 'latest_tiny_lifecycle_runner_dry_run.json'}")

    gate    = DemoTinyLifecycleGuardedRunnerDesignReview()
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
        runner_design=runner_design,
        runner_dry_run=runner_dry_run,
        symbol=symbol,
        allow_guarded_design_approval=allow_guarded_design_approval,
        allow_real_runner_execution=allow_real_runner_execution,
        _now=_now,
    )

    print()
    _print_result(result)
    print(_SEP)

    if write_report:
        _write_report(result, _out_dir)

    if result.status in (
        STATUS_DESIGN_REVIEW_READY,
        STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED,
        STATUS_REAL_RUNNER_NOT_IMPL,
    ):
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Tiny lifecycle guarded runner DESIGN REVIEW ONLY. "
            "No network, no live endpoint, no orders / positions modified, "
            "no guarded runner implemented, no real runner implemented, "
            "no close-only sender, no emergency-close sender, no new-entry "
            "sender real execution.  Even with --allow-guarded-design-approval "
            "this only emits a design-review artifact; even with "
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
    parser.add_argument("--from-latest-runner-design", action="store_true",
                        help=("Read tiny lifecycle runner design JSON "
                              "(TASK-014AB artifact) from "
                              "outputs/.../tiny_lifecycle_runner_design/."))
    parser.add_argument("--from-latest-runner-dry-run", action="store_true",
                        help=("Read tiny lifecycle runner dry-run JSON "
                              "(TASK-014AC artifact) from "
                              "outputs/.../tiny_lifecycle_runner_dry_run/."))
    parser.add_argument("--symbol", default=DEFAULT_SELECTED_SYMBOL,
                        metavar="SYMBOL",
                        help=("Symbol to design-review against.  MUST NOT be "
                              "in the 5 existing demo position symbols "
                              "(ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / "
                              "EDUUSDT)."))
    parser.add_argument("--allow-guarded-design-approval", action="store_true",
                        help=("Promote envelope to "
                              "guarded_design_approval_dry_run.  Even with "
                              "this flag, TASK-014AD only emits a design-"
                              "review report (readiness_conclusion stays "
                              "DESIGN_REVIEW_READY_NOT_EXECUTABLE).  No "
                              "execution, no implementation."))
    parser.add_argument("--allow-real-runner-execution", action="store_true",
                        help=("Guarded flag for a hypothetical future real "
                              "tiny lifecycle runner execution.  TASK-014AD "
                              "returns REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED "
                              "even when this flag is set (no socket opened, "
                              "no runner implemented)."))
    parser.add_argument("--write-report", action="store_true",
                        help=("Write JSON + Markdown report to "
                              "outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/."))
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        allow_guarded_design_approval=args.allow_guarded_design_approval,
        allow_real_runner_execution=args.allow_real_runner_execution,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
