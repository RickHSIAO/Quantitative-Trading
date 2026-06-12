"""
scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py
TASK-014AN: Guarded Tiny Entry Real Execution Adapter Design CLI.

Usage (ADAPTER DESIGN CHECKLIST --- default, no network,
       no implementation):
  python scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_design.py \\
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
    --from-latest-guarded-design-review \\
    --from-latest-guarded-entry-adapter \\
    --from-latest-guarded-stop-adapter \\
    --from-latest-guarded-cleanup-adapter \\
    --from-latest-guarded-lifecycle-summary \\
    --from-latest-entry-real-permission-review \\
    --from-latest-entry-manual-auth-design \\
    --from-latest-entry-manual-auth-dry-run \\
    --from-latest-entry-final-pre-execution-review \\
    --from-latest-entry-manual-approval-gate \\
    --symbol SOLUSDT \\
    [--expected-commit-hash <hash>] \\
    [--write-report]

Usage (ADAPTER DESIGN APPROVAL --- design-only, no execution):
  ... --allow-adapter-design-approval

Usage (REAL ENTRY EXECUTION GUARD --- always returns
       REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened,
       no real entry sender implemented, no adapter `send` method):
  ... --allow-real-entry-execution

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
  outputs/demo_trading/tiny_lifecycle_guarded_runner_design_review/latest_tiny_lifecycle_guarded_runner_design_review.json
  outputs/demo_trading/tiny_guarded_entry_dry_run_adapter/latest_tiny_guarded_entry_dry_run_adapter.json
  outputs/demo_trading/tiny_guarded_stop_attach_dry_run_adapter/latest_tiny_guarded_stop_attach_dry_run_adapter.json
  outputs/demo_trading/tiny_guarded_cleanup_dry_run_adapter/latest_tiny_guarded_cleanup_dry_run_adapter.json
  outputs/demo_trading/tiny_guarded_lifecycle_dry_run_summary/latest_tiny_guarded_lifecycle_dry_run_summary.json
  outputs/demo_trading/tiny_guarded_entry_real_permission_review/latest_tiny_guarded_entry_real_permission_review.json
  outputs/demo_trading/tiny_guarded_entry_manual_authorization_design/latest_tiny_guarded_entry_manual_authorization_design.json
  outputs/demo_trading/tiny_guarded_entry_manual_authorization_dry_run/latest_tiny_guarded_entry_manual_authorization_dry_run.json
  outputs/demo_trading/tiny_guarded_entry_final_pre_execution_review/latest_tiny_guarded_entry_final_pre_execution_review.json
  outputs/demo_trading/tiny_guarded_entry_real_execution_manual_approval_gate/latest_tiny_guarded_entry_real_execution_manual_approval_gate.json

Writes (when --write-report):
  outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_design/
      {ts}_tiny_guarded_entry_real_execution_adapter_design.json
      {ts}_tiny_guarded_entry_real_execution_adapter_design.md
      latest_tiny_guarded_entry_real_execution_adapter_design.json
      latest_tiny_guarded_entry_real_execution_adapter_design.md

IMPORTANT:
  - TASK-014AN produces a STRICT ADAPTER-DESIGN-ONLY artifact.
    No guarded entry sender, no order send, no stop-attach send, no
    cleanup send, no endpoint invoked.  No network, no socket, no
    environment-variable reads, no signing, no order send, NO real
    token validation, NO token-to-authorization mapping, NO real
    phrase validation, NO phrase-to-authorization mapping, NO real
    approval-input validation.  Adapter contract / inputs / outputs /
    boundaries / forbidden surfaces / fail-closed policy / audit
    schema are documented only --- this task does NOT implement the
    adapter and exposes no `send` method.  No automatic git commit,
    no automatic git push.
  - Even with --allow-adapter-design-approval the design review only
    emits a sanitized design artifact.  Readiness conclusion is fixed
    at DESIGN_REVIEW_READY_NOT_EXECUTABLE.
  - Even with --allow-real-entry-execution the design review returns
    REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED (no socket opened, no real
    sender implemented).
  - No --execute-real-* / --send-order / --place-order / --real-run
    flag is exposed by this CLI.  No --confirm-token flag is exposed
    (token is documented only, never validated by this CLI).
  - No --auto-commit / --git-commit / --auto-push / --git-push flag
    is exposed by this CLI (no automatic git operation).
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT
    lifted by this task.
  - The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) are NEVER touched.
  - /v5/order/create is NEVER invoked from this CLI.
  - /v5/position/trading-stop is NEVER invoked from this CLI.
  - No close-only sender / no emergency-close sender / no new-entry
    sender real execution path / no real stop-attach sender real
    execution path / no real cleanup sender real execution path / no
    real lifecycle runner real execution path / no real guarded
    entry sender real execution path / no real guarded entry
    adapter implementation is invoked.

Exit codes:
  0  tiny_guarded_entry_real_execution_adapter_design_ready /
     tiny_guarded_entry_real_execution_adapter_design_ready_but_execution_disabled /
     real_entry_execution_not_implemented
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

from src.demo_tiny_guarded_entry_real_execution_adapter_design import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    DEFAULT_SELECTED_SYMBOL,
    DemoTinyGuardedEntryRealExecutionAdapterDesign,
    TinyGuardedEntryRealExecutionAdapterDesignResult,
    STATUS_DESIGN_READY,
    STATUS_DESIGN_READY_EXEC_DISABLED,
    STATUS_REAL_ENTRY_NOT_IMPL,
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
_DEFAULT_GUARDED_REVIEW_DIR  = (
    ROOT / "outputs" / "demo_trading" / "tiny_lifecycle_guarded_runner_design_review"
)
_DEFAULT_GUARDED_ENTRY_ADAPTER_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_entry_dry_run_adapter"
)
_DEFAULT_GUARDED_STOP_ADAPTER_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_stop_attach_dry_run_adapter"
)
_DEFAULT_GUARDED_CLEANUP_ADAPTER_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_cleanup_dry_run_adapter"
)
_DEFAULT_GUARDED_LIFECYCLE_SUMMARY_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_lifecycle_dry_run_summary"
)
_DEFAULT_ENTRY_REAL_PERMISSION_REVIEW_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_entry_real_permission_review"
)
_DEFAULT_ENTRY_MANUAL_AUTH_DESIGN_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_entry_manual_authorization_design"
)
_DEFAULT_ENTRY_MANUAL_AUTH_DRY_RUN_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_entry_manual_authorization_dry_run"
)
_DEFAULT_ENTRY_FINAL_PRE_EXECUTION_REVIEW_DIR = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_entry_final_pre_execution_review"
)
_DEFAULT_ENTRY_MANUAL_APPROVAL_GATE_DIR = (
    ROOT
    / "outputs"
    / "demo_trading"
    / "tiny_guarded_entry_real_execution_manual_approval_gate"
)
_DEFAULT_OUTPUT_DIR          = (
    ROOT / "outputs" / "demo_trading" / "tiny_guarded_entry_real_execution_adapter_design"
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


def load_latest_tiny_stop_permission(tiny_stop_dir: Path) -> dict | None:
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


def load_latest_guarded_design_review(guarded_review_dir: Path) -> dict | None:
    return _load_json(
        guarded_review_dir / "latest_tiny_lifecycle_guarded_runner_design_review.json"
    )


def load_latest_guarded_entry_adapter(guarded_entry_adapter_dir: Path) -> dict | None:
    return _load_json(
        guarded_entry_adapter_dir / "latest_tiny_guarded_entry_dry_run_adapter.json"
    )


def load_latest_guarded_stop_adapter(guarded_stop_adapter_dir: Path) -> dict | None:
    return _load_json(
        guarded_stop_adapter_dir / "latest_tiny_guarded_stop_attach_dry_run_adapter.json"
    )


def load_latest_guarded_cleanup_adapter(guarded_cleanup_adapter_dir: Path) -> dict | None:
    return _load_json(
        guarded_cleanup_adapter_dir / "latest_tiny_guarded_cleanup_dry_run_adapter.json"
    )


def load_latest_guarded_lifecycle_summary(
    guarded_lifecycle_summary_dir: Path,
) -> dict | None:
    return _load_json(
        guarded_lifecycle_summary_dir
        / "latest_tiny_guarded_lifecycle_dry_run_summary.json"
    )


def load_latest_entry_real_permission_review(
    entry_real_permission_review_dir: Path,
) -> dict | None:
    return _load_json(
        entry_real_permission_review_dir
        / "latest_tiny_guarded_entry_real_permission_review.json"
    )


def load_latest_entry_manual_auth_design(
    entry_manual_auth_design_dir: Path,
) -> dict | None:
    return _load_json(
        entry_manual_auth_design_dir
        / "latest_tiny_guarded_entry_manual_authorization_design.json"
    )


def load_latest_entry_manual_auth_dry_run(
    entry_manual_auth_dry_run_dir: Path,
) -> dict | None:
    return _load_json(
        entry_manual_auth_dry_run_dir
        / "latest_tiny_guarded_entry_manual_authorization_dry_run.json"
    )


def load_latest_entry_final_pre_execution_review(
    entry_final_pre_execution_review_dir: Path,
) -> dict | None:
    return _load_json(
        entry_final_pre_execution_review_dir
        / "latest_tiny_guarded_entry_final_pre_execution_review.json"
    )


def load_latest_entry_manual_approval_gate(
    entry_manual_approval_gate_dir: Path,
) -> dict | None:
    return _load_json(
        entry_manual_approval_gate_dir
        / "latest_tiny_guarded_entry_real_execution_manual_approval_gate.json"
    )


def _print_result(r: TinyGuardedEntryRealExecutionAdapterDesignResult) -> None:
    print(f"  timestamp_utc                              : {r.timestamp_utc}")
    print(f"  mode                                       : {r.mode}")
    print(f"  selected_symbol                            : {r.selected_symbol or '(none)'}")
    print(f"  existing_position_symbols                  : {r.existing_position_symbols}")
    print(f"  adapter_name                               : {r.adapter_name}")
    print(f"  adapter_contract_version                   : {r.adapter_contract_version}")
    print(f"  order_link_id_prefix                       : {r.order_link_id_prefix}")
    print(f"  adapter_design_approval_allowed            : {r.adapter_design_approval_allowed}")
    print(f"  real_entry_execution_requested             : {r.real_entry_execution_requested}")
    print(f"  real_execution_allowed                     : {r.real_execution_allowed}")
    print(f"  real_entry_implemented                     : {r.real_entry_implemented}")
    print(f"  guarded_entry_real_execution_adapter_design: {r.guarded_entry_real_execution_adapter_design}")
    print(f"  adapter_design_only                        : {r.adapter_design_only}")
    print(f"  adapter_implementation_included            : {r.adapter_implementation_included}")
    print(f"  adapter_execution_included                 : {r.adapter_execution_included}")
    print(f"  adapter_grants_execution                   : {r.adapter_grants_execution}")
    print(f"  approval_gate_grants_execution             : {r.approval_gate_grants_execution}")
    print(f"  entry_execution_included                   : {r.entry_execution_included}")
    print(f"  stop_execution_included                    : {r.stop_execution_included}")
    print(f"  cleanup_execution_included                 : {r.cleanup_execution_included}")
    print(f"  full_lifecycle_execution_included          : {r.full_lifecycle_execution_included}")
    print(f"  current_task_real_execution_allowed        : {r.current_task_real_execution_allowed}")
    print(f"  readiness_conclusion                       : {r.readiness_conclusion}")
    print(f"  dry_run_authorization_result               : {r.dry_run_authorization_result}")
    print(f"  expected_commit_hash                       : {r.expected_commit_hash or '(none)'}")
    print(f"  current_commit_hash                        : {r.current_commit_hash or '(none)'}")
    print(f"  order_create_path_ref                      : {r.order_create_path_ref}  (NOT invoked)")
    print(f"  trading_stop_path_ref                      : {r.trading_stop_path_ref}  (NOT invoked)")
    print(f"  base_url_ref                               : {r.base_url_ref}")
    print(f"  send_allowed                               : {r.send_allowed}")
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
    print(f"  upstream_lifecycle_summary_status              : {r.upstream_lifecycle_summary_status}")
    print(f"  upstream_runner_design_status                  : {r.upstream_runner_design_status}")
    print(f"  upstream_runner_dry_run_status                 : {r.upstream_runner_dry_run_status}")
    print(f"  upstream_guarded_design_review_status          : {r.upstream_guarded_design_review_status}")
    print(f"  upstream_guarded_entry_adapter_status          : {r.upstream_guarded_entry_adapter_status}")
    print(f"  upstream_guarded_stop_adapter_status           : {r.upstream_guarded_stop_adapter_status}")
    print(f"  upstream_guarded_cleanup_adapter_status        : {r.upstream_guarded_cleanup_adapter_status}")
    print(f"  upstream_guarded_lifecycle_summary_status      : {r.upstream_guarded_lifecycle_summary_status}")
    print(f"  upstream_entry_real_permission_review_status   : {r.upstream_entry_real_permission_review_status}")
    print(f"  upstream_entry_manual_auth_design_status       : {r.upstream_entry_manual_auth_design_status}")
    print(f"  upstream_entry_manual_auth_dry_run_status      : {r.upstream_entry_manual_auth_dry_run_status}")
    print(f"  upstream_entry_final_pre_execution_review_status   : {r.upstream_entry_final_pre_execution_review_status}")
    print(f"  upstream_entry_manual_approval_gate_status         : {r.upstream_entry_manual_approval_gate_status}")
    print(f"  upstream_entry_manual_approval_gate_readiness      : {r.upstream_entry_manual_approval_gate_readiness_conclusion}")
    print(f"  upstream_entry_manual_approval_gate_grants_exec    : {r.upstream_entry_manual_approval_gate_approval_grants_execution}")
    print(f"  upstream_entry_manual_approval_gate_phrase_valid   : {r.upstream_entry_manual_approval_gate_exact_phrase_validated}")
    print(f"  upstream_entry_manual_approval_gate_inputs_valid   : {r.upstream_entry_manual_approval_gate_approval_inputs_validated}")
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
    r: TinyGuardedEntryRealExecutionAdapterDesignResult,
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
    base = "tiny_guarded_entry_real_execution_adapter_design"
    json_path   = output_dir / f"{ts_safe}_{base}.json"
    json_latest = output_dir / f"latest_{base}.json"
    md_path     = output_dir / f"{ts_safe}_{base}.md"
    md_latest   = output_dir / f"latest_{base}.md"

    data      = r.to_dict()
    json_text = json.dumps(data, indent=2)
    json_path.write_text(json_text, encoding="utf-8")
    json_latest.write_text(json_text, encoding="utf-8")

    md_lines: list[str] = [
        "# Tiny Guarded Entry Real Execution Adapter Design (TASK-014AN)",
        "",
        f"timestamp: `{r.timestamp_utc}`  ",
        f"mode: `{r.mode}`  ",
        f"status: **{r.status}**  ",
        f"failed_stage: `{r.failed_stage or '(none)'}`  ",
        f"readiness_conclusion: `{r.readiness_conclusion}`  ",
        f"dry_run_authorization_result: `{r.dry_run_authorization_result}`  ",
        f"adapter_name: `{ADAPTER_NAME}`  ",
        f"adapter_contract_version: `{ADAPTER_CONTRACT_VERSION}`  ",
        "",
        "## Adapter Design Verdict",
        "",
        "| field | value |",
        "|---|---|",
        f"| selected_symbol | {r.selected_symbol or '(none)'} |",
        f"| existing_position_symbols | {', '.join(r.existing_position_symbols) or '(none)'} |",
        f"| adapter_name | {r.adapter_name} |",
        f"| adapter_contract_version | {r.adapter_contract_version} |",
        f"| order_link_id_prefix | {r.order_link_id_prefix} |",
        f"| adapter_design_approval_allowed | {r.adapter_design_approval_allowed} |",
        f"| real_entry_execution_requested | {r.real_entry_execution_requested} |",
        f"| real_execution_allowed | {r.real_execution_allowed} |",
        f"| real_entry_implemented | {r.real_entry_implemented} |",
        f"| guarded_entry_real_execution_adapter_design | {r.guarded_entry_real_execution_adapter_design} |",
        f"| adapter_design_only | {r.adapter_design_only} |",
        f"| adapter_implementation_included | {r.adapter_implementation_included} |",
        f"| adapter_execution_included | {r.adapter_execution_included} |",
        f"| adapter_grants_execution | {r.adapter_grants_execution} |",
        f"| approval_gate_grants_execution | {r.approval_gate_grants_execution} |",
        f"| entry_execution_included | {r.entry_execution_included} |",
        f"| stop_execution_included | {r.stop_execution_included} |",
        f"| cleanup_execution_included | {r.cleanup_execution_included} |",
        f"| full_lifecycle_execution_included | {r.full_lifecycle_execution_included} |",
        f"| current_task_real_execution_allowed | {r.current_task_real_execution_allowed} |",
        f"| readiness_conclusion | {r.readiness_conclusion} |",
        f"| dry_run_authorization_result | {r.dry_run_authorization_result} |",
        f"| expected_commit_hash | {r.expected_commit_hash or '(none)'} |",
        f"| current_commit_hash | {r.current_commit_hash or '(none)'} |",
        f"| upstream_lifecycle_summary_status | {r.upstream_lifecycle_summary_status} |",
        f"| upstream_runner_design_status | {r.upstream_runner_design_status} |",
        f"| upstream_runner_dry_run_status | {r.upstream_runner_dry_run_status} |",
        f"| upstream_guarded_design_review_status | {r.upstream_guarded_design_review_status} |",
        f"| upstream_guarded_entry_adapter_status | {r.upstream_guarded_entry_adapter_status} |",
        f"| upstream_guarded_stop_adapter_status | {r.upstream_guarded_stop_adapter_status} |",
        f"| upstream_guarded_cleanup_adapter_status | {r.upstream_guarded_cleanup_adapter_status} |",
        f"| upstream_guarded_lifecycle_summary_status | {r.upstream_guarded_lifecycle_summary_status} |",
        f"| upstream_entry_real_permission_review_status | {r.upstream_entry_real_permission_review_status} |",
        f"| upstream_entry_manual_auth_design_status | {r.upstream_entry_manual_auth_design_status} |",
        f"| upstream_entry_manual_auth_dry_run_status | {r.upstream_entry_manual_auth_dry_run_status} |",
        f"| upstream_entry_final_pre_execution_review_status | {r.upstream_entry_final_pre_execution_review_status} |",
        f"| upstream_entry_manual_approval_gate_status | {r.upstream_entry_manual_approval_gate_status} |",
        f"| upstream_entry_manual_approval_gate_readiness_conclusion | {r.upstream_entry_manual_approval_gate_readiness_conclusion} |",
        f"| upstream_entry_manual_approval_gate_approval_grants_execution | {r.upstream_entry_manual_approval_gate_approval_grants_execution} |",
        f"| upstream_entry_manual_approval_gate_exact_phrase_validated | {r.upstream_entry_manual_approval_gate_exact_phrase_validated} |",
        f"| upstream_entry_manual_approval_gate_approval_inputs_validated | {r.upstream_entry_manual_approval_gate_approval_inputs_validated} |",
        f"| next_required_task | {r.next_required_task} |",
        "",
        "## Adapter Design Scope",
        "",
        "```json",
        json.dumps(r.adapter_design_scope, indent=2),
        "```",
        "",
        "## Adapter Contract Design",
        "",
        "```json",
        json.dumps(r.adapter_contract_design, indent=2),
        "```",
        "",
        "## Adapter Input Schema Design",
        "",
        "```json",
        json.dumps(r.adapter_input_schema_design, indent=2),
        "```",
        "",
        "## Adapter Output Schema Design",
        "",
        "```json",
        json.dumps(r.adapter_output_schema_design, indent=2),
        "```",
        "",
        "## Entry Payload Design Preview",
        "",
        "```json",
        json.dumps(r.entry_payload_design_preview, indent=2),
        "```",
        "",
        "## Secret and Signature Boundary Design",
        "",
        "```json",
        json.dumps(r.secret_and_signature_boundary_design, indent=2),
        "```",
        "",
        "## Stop / Cleanup Boundary Design",
        "",
        "```json",
        json.dumps(r.stop_cleanup_boundary_design, indent=2),
        "```",
        "",
        "## Forbidden Execution Surface Design",
        "",
        "```json",
        json.dumps(r.forbidden_execution_surface_design, indent=2),
        "```",
        "",
        "## Failure and Abort Adapter Design",
        "",
        "```json",
        json.dumps(r.failure_and_abort_adapter_design, indent=2),
        "```",
        "",
        "## Documentation Sync Review",
        "",
        "```json",
        json.dumps(r.documentation_sync_review, indent=2),
        "```",
        "",
        "## Audit Artifacts",
        "",
        "```json",
        json.dumps(r.audit_artifacts, indent=2),
        "```",
        "",
        "## Final Adapter Design Verdict",
        "",
        "```json",
        json.dumps(r.final_adapter_design_verdict, indent=2),
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
        f"- send_allowed: `{r.send_allowed}`",
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
        "> TASK-014AN is a STRICT ADAPTER-DESIGN-ONLY module.",
        "> It NEVER opens a socket, NEVER invokes /v5/order/create,",
        "> NEVER invokes /v5/position/trading-stop, NEVER modifies any",
        "> position, NEVER invokes the close-only sender, NEVER invokes",
        "> the emergency-close sender, NEVER invokes the new-entry",
        "> sender's real execution path, NEVER invokes the real stop-",
        "> attach sender's real execution path, NEVER invokes a real",
        "> cleanup sender's real execution path, NEVER invokes a real",
        "> guarded entry sender's real execution path, NEVER implements",
        "> any executable adapter, NEVER exposes any adapter `send`",
        "> method, NEVER reads environment variables / secrets,",
        "> NEVER signs any request, NEVER validates any token / phrase",
        "> / approval input as authorization, NEVER includes entry /",
        "> stop-attach / cleanup execution, NEVER lifts TASK-014L",
        "> sender G20 (protected_entry_policy_missing), NEVER performs",
        "> any automatic git commit, NEVER performs any automatic git",
        "> push.  The 5 existing demo positions are NEVER touched.",
        "> Even with --allow-adapter-design-approval the design review",
        "> only emits a sanitized design artifact",
        "> (readiness_conclusion remains",
        "> DESIGN_REVIEW_READY_NOT_EXECUTABLE).  Even with",
        "> --allow-real-entry-execution this task returns",
        "> REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED (no socket opened).",
        "",
    ]
    md_text = "\n".join(md_lines)
    md_path.write_text(md_text, encoding="utf-8")
    md_latest.write_text(md_text, encoding="utf-8")

    print(f"  report: {json_latest}")
    print(f"  report: {md_latest}")


def run_execute(
    symbol:                            str  = DEFAULT_SELECTED_SYMBOL,
    expected_commit_hash:              str  = "",
    allow_adapter_design_approval:     bool = False,
    allow_real_entry_execution:        bool = False,
    write_report:                      bool = False,
    readonly_dir:                      Path | None = None,
    reconciliation_dir:                Path | None = None,
    protection_dir:                    Path | None = None,
    contract_dir:                      Path | None = None,
    noop_plan_dir:                     Path | None = None,
    lifecycle_dir:                     Path | None = None,
    real_permission_dir:               Path | None = None,
    tiny_entry_dir:                    Path | None = None,
    tiny_stop_dir:                     Path | None = None,
    tiny_cleanup_dir:                  Path | None = None,
    lifecycle_summary_dir:             Path | None = None,
    runner_design_dir:                 Path | None = None,
    runner_dry_run_dir:                Path | None = None,
    guarded_design_review_dir:         Path | None = None,
    guarded_entry_adapter_dir:         Path | None = None,
    guarded_stop_adapter_dir:          Path | None = None,
    guarded_cleanup_adapter_dir:       Path | None = None,
    guarded_lifecycle_summary_dir:     Path | None = None,
    entry_real_permission_review_dir:  Path | None = None,
    entry_manual_auth_design_dir:      Path | None = None,
    entry_manual_auth_dry_run_dir:     Path | None = None,
    entry_final_pre_execution_review_dir: Path | None = None,
    entry_manual_approval_gate_dir:    Path | None = None,
    output_dir:                        Path | None = None,
    _now:                              datetime | None = None,
) -> int:
    _ro_dir               = readonly_dir                or _DEFAULT_READONLY_DIR
    _recon_dir            = reconciliation_dir          or _DEFAULT_RECON_DIR
    _protect_dir          = protection_dir              or _DEFAULT_PROTECTION_DIR
    _contract_dir         = contract_dir                or _DEFAULT_CONTRACT_DIR
    _noop_dir             = noop_plan_dir               or _DEFAULT_NOOP_PLAN_DIR
    _lifecycle_dir        = lifecycle_dir               or _DEFAULT_LIFECYCLE_DIR
    _real_perm_dir        = real_permission_dir         or _DEFAULT_REAL_PERMISSION_DIR
    _entry_perm_dir       = tiny_entry_dir              or _DEFAULT_TINY_ENTRY_DIR
    _stop_perm_dir        = tiny_stop_dir               or _DEFAULT_TINY_STOP_DIR
    _cleanup_perm_dir     = tiny_cleanup_dir            or _DEFAULT_TINY_CLEANUP_DIR
    _summary_dir          = lifecycle_summary_dir       or _DEFAULT_LIFECYCLE_SUMMARY_DIR
    _design_dir           = runner_design_dir           or _DEFAULT_RUNNER_DESIGN_DIR
    _dry_run_dir          = runner_dry_run_dir          or _DEFAULT_RUNNER_DRY_RUN_DIR
    _guarded_dir          = guarded_design_review_dir   or _DEFAULT_GUARDED_REVIEW_DIR
    _entry_adapter_dir    = guarded_entry_adapter_dir   or _DEFAULT_GUARDED_ENTRY_ADAPTER_DIR
    _stop_adapter_dir     = guarded_stop_adapter_dir    or _DEFAULT_GUARDED_STOP_ADAPTER_DIR
    _cleanup_adapter_dir  = guarded_cleanup_adapter_dir or _DEFAULT_GUARDED_CLEANUP_ADAPTER_DIR
    _lifecycle_summary_dir2 = (
        guarded_lifecycle_summary_dir or _DEFAULT_GUARDED_LIFECYCLE_SUMMARY_DIR
    )
    _entry_review_dir     = (
        entry_real_permission_review_dir
        or _DEFAULT_ENTRY_REAL_PERMISSION_REVIEW_DIR
    )
    _entry_design_dir     = (
        entry_manual_auth_design_dir
        or _DEFAULT_ENTRY_MANUAL_AUTH_DESIGN_DIR
    )
    _entry_dry_run_dir    = (
        entry_manual_auth_dry_run_dir
        or _DEFAULT_ENTRY_MANUAL_AUTH_DRY_RUN_DIR
    )
    _entry_final_dir      = (
        entry_final_pre_execution_review_dir
        or _DEFAULT_ENTRY_FINAL_PRE_EXECUTION_REVIEW_DIR
    )
    _entry_approval_gate_dir = (
        entry_manual_approval_gate_dir
        or _DEFAULT_ENTRY_MANUAL_APPROVAL_GATE_DIR
    )
    _out_dir              = output_dir                  or _DEFAULT_OUTPUT_DIR

    print(_SEP)
    if allow_real_entry_execution:
        print("REAL ENTRY EXECUTION GUARD --- NO NETWORK --- REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED")
    elif allow_adapter_design_approval:
        print("ADAPTER DESIGN APPROVAL --- NO NETWORK --- design-only")
    else:
        print("ADAPTER DESIGN CHECKLIST --- NO NETWORK --- design-only")
    print("TASK-014AN: Guarded Tiny Entry Real Execution Adapter Design")
    print(f"  adapter_name             : {ADAPTER_NAME}")
    print(f"  adapter_contract_version : {ADAPTER_CONTRACT_VERSION}")
    print(_SEP)

    readonly                  = load_latest_readonly(_ro_dir)
    reconciliation            = load_latest_reconciliation(_recon_dir)
    protection                = load_latest_protection(_protect_dir)
    contract                  = load_latest_contract(_contract_dir)
    noop_plan                 = load_latest_noop_plan(_noop_dir)
    lifecycle                 = load_latest_lifecycle(_lifecycle_dir)
    real_permission_gate      = load_latest_real_permission(_real_perm_dir)
    tiny_entry_perm_gate      = load_latest_tiny_entry_permission(_entry_perm_dir)
    tiny_stop_perm_gate       = load_latest_tiny_stop_permission(_stop_perm_dir)
    tiny_cleanup_perm_gate    = load_latest_tiny_cleanup_permission(_cleanup_perm_dir)
    lifecycle_summary         = load_latest_lifecycle_summary(_summary_dir)
    runner_design             = load_latest_runner_design(_design_dir)
    runner_dry_run            = load_latest_runner_dry_run(_dry_run_dir)
    guarded_design_review     = load_latest_guarded_design_review(_guarded_dir)
    guarded_entry_adapter     = load_latest_guarded_entry_adapter(_entry_adapter_dir)
    guarded_stop_adapter      = load_latest_guarded_stop_adapter(_stop_adapter_dir)
    guarded_cleanup_adapter   = load_latest_guarded_cleanup_adapter(_cleanup_adapter_dir)
    guarded_lifecycle_summary = load_latest_guarded_lifecycle_summary(_lifecycle_summary_dir2)
    entry_real_perm_review    = load_latest_entry_real_permission_review(_entry_review_dir)
    entry_manual_auth_design  = load_latest_entry_manual_auth_design(_entry_design_dir)
    entry_manual_auth_dry_run = load_latest_entry_manual_auth_dry_run(_entry_dry_run_dir)
    entry_final_review        = load_latest_entry_final_pre_execution_review(_entry_final_dir)
    entry_manual_approval_gate = load_latest_entry_manual_approval_gate(_entry_approval_gate_dir)

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
    if guarded_design_review is None:
        missing.append(
            str(_guarded_dir / "latest_tiny_lifecycle_guarded_runner_design_review.json")
        )
    if guarded_entry_adapter is None:
        missing.append(
            str(_entry_adapter_dir / "latest_tiny_guarded_entry_dry_run_adapter.json")
        )
    if guarded_stop_adapter is None:
        missing.append(
            str(_stop_adapter_dir / "latest_tiny_guarded_stop_attach_dry_run_adapter.json")
        )
    if guarded_cleanup_adapter is None:
        missing.append(
            str(_cleanup_adapter_dir / "latest_tiny_guarded_cleanup_dry_run_adapter.json")
        )
    if guarded_lifecycle_summary is None:
        missing.append(
            str(_lifecycle_summary_dir2 / "latest_tiny_guarded_lifecycle_dry_run_summary.json")
        )
    if entry_real_perm_review is None:
        missing.append(
            str(_entry_review_dir / "latest_tiny_guarded_entry_real_permission_review.json")
        )
    if entry_manual_auth_design is None:
        missing.append(
            str(_entry_design_dir / "latest_tiny_guarded_entry_manual_authorization_design.json")
        )
    if entry_manual_auth_dry_run is None:
        missing.append(
            str(_entry_dry_run_dir / "latest_tiny_guarded_entry_manual_authorization_dry_run.json")
        )
    if entry_final_review is None:
        missing.append(
            str(_entry_final_dir / "latest_tiny_guarded_entry_final_pre_execution_review.json")
        )
    if entry_manual_approval_gate is None:
        missing.append(
            str(
                _entry_approval_gate_dir
                / "latest_tiny_guarded_entry_real_execution_manual_approval_gate.json"
            )
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

    print(f"\n  symbol                            : {symbol}")
    print(f"  expected_commit_hash              : {expected_commit_hash or '(none)'}")
    print(f"  readonly_src                      : {_ro_dir / 'latest_smoke.json'} (primary)")
    print(f"  reconciliation_src                : {_recon_dir / 'latest_reconciliation.json'}")
    print(f"  protection_src                    : {_protect_dir / 'latest_new_entry_protection.json'}")
    print(f"  contract_src                      : {_contract_dir / 'latest_trading_stop_contract.json'}")
    print(f"  noop_plan_src                     : {_noop_dir / 'latest_trading_stop_noop_probe_plan.json'} (primary)")
    print(f"  lifecycle_src                     : {_lifecycle_dir / 'latest_tiny_position_lifecycle_mock.json'}")
    print(f"  real_permission_src               : {_real_perm_dir / 'latest_tiny_position_real_permission_gate.json'}")
    print(f"  tiny_entry_perm_src               : {_entry_perm_dir / 'latest_tiny_entry_permission_gate.json'}")
    print(f"  tiny_stop_perm_src                : {_stop_perm_dir / 'latest_tiny_stop_attach_permission_gate.json'}")
    print(f"  tiny_cleanup_perm_src             : {_cleanup_perm_dir / 'latest_tiny_cleanup_permission_gate.json'}")
    print(f"  lifecycle_summary_src             : {_summary_dir / 'latest_tiny_lifecycle_real_execution_summary.json'}")
    print(f"  runner_design_src                 : {_design_dir / 'latest_tiny_lifecycle_runner_design.json'}")
    print(f"  runner_dry_run_src                : {_dry_run_dir / 'latest_tiny_lifecycle_runner_dry_run.json'}")
    print(f"  guarded_review_src                : {_guarded_dir / 'latest_tiny_lifecycle_guarded_runner_design_review.json'}")
    print(f"  guarded_entry_src                 : {_entry_adapter_dir / 'latest_tiny_guarded_entry_dry_run_adapter.json'}")
    print(f"  guarded_stop_src                  : {_stop_adapter_dir / 'latest_tiny_guarded_stop_attach_dry_run_adapter.json'}")
    print(f"  guarded_cleanup_src               : {_cleanup_adapter_dir / 'latest_tiny_guarded_cleanup_dry_run_adapter.json'}")
    print(f"  guarded_lifecycle_summary_src     : {_lifecycle_summary_dir2 / 'latest_tiny_guarded_lifecycle_dry_run_summary.json'}")
    print(f"  entry_real_perm_review_src        : {_entry_review_dir / 'latest_tiny_guarded_entry_real_permission_review.json'}")
    print(f"  entry_manual_auth_design_src      : {_entry_design_dir / 'latest_tiny_guarded_entry_manual_authorization_design.json'}")
    print(f"  entry_manual_auth_dry_run_src     : {_entry_dry_run_dir / 'latest_tiny_guarded_entry_manual_authorization_dry_run.json'}")
    print(f"  entry_final_pre_execution_review_src: {_entry_final_dir / 'latest_tiny_guarded_entry_final_pre_execution_review.json'}")
    print(f"  entry_manual_approval_gate_src    : {_entry_approval_gate_dir / 'latest_tiny_guarded_entry_real_execution_manual_approval_gate.json'}")

    gate = DemoTinyGuardedEntryRealExecutionAdapterDesign()
    result = gate.run_review(
        readonly_smoke=readonly,
        reconciliation=reconciliation,
        protection=protection,
        contract=contract,
        noop_plan=noop_plan,
        lifecycle_mock=lifecycle,
        real_permission_gate=real_permission_gate,
        tiny_entry_permission_gate=tiny_entry_perm_gate,
        tiny_stop_permission_gate=tiny_stop_perm_gate,
        tiny_cleanup_permission_gate=tiny_cleanup_perm_gate,
        lifecycle_summary=lifecycle_summary,
        runner_design=runner_design,
        runner_dry_run=runner_dry_run,
        guarded_design_review=guarded_design_review,
        guarded_entry_adapter=guarded_entry_adapter,
        guarded_stop_adapter=guarded_stop_adapter,
        guarded_cleanup_adapter=guarded_cleanup_adapter,
        guarded_lifecycle_summary=guarded_lifecycle_summary,
        entry_real_permission_review=entry_real_perm_review,
        entry_manual_authorization_design=entry_manual_auth_design,
        entry_manual_authorization_dry_run=entry_manual_auth_dry_run,
        entry_final_pre_execution_review=entry_final_review,
        entry_manual_approval_gate=entry_manual_approval_gate,
        symbol=symbol,
        expected_commit_hash=expected_commit_hash,
        allow_adapter_design_approval=allow_adapter_design_approval,
        allow_real_entry_execution=allow_real_entry_execution,
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
        STATUS_REAL_ENTRY_NOT_IMPL,
    ):
        return 0
    return 1


def main() -> None:
    parser = argparse.ArgumentParser(
        description=(
            "Tiny guarded entry REAL EXECUTION ADAPTER DESIGN. "
            "No network, no live endpoint, no orders / positions modified, "
            "no guarded entry sender implemented, no executable adapter, "
            "no adapter `send` method, no real entry execution, no "
            "entry / stop-attach / cleanup execution included, no "
            "close-only sender, no emergency-close sender, no new-entry "
            "sender real execution, no real stop-attach sender real "
            "execution, no real cleanup sender real execution, no real "
            "guarded entry sender real execution, no real token "
            "validation, no token-to-authorization mapping, no real "
            "phrase validation, no phrase-to-authorization mapping, no "
            "real approval-input validation, no automatic git commit, "
            "no automatic git push.  Adapter contract / inputs / outputs "
            "/ boundaries / forbidden surfaces / fail-closed policy / "
            "audit schema are documented only.  Even with "
            "--allow-adapter-design-approval this only emits a design "
            "artifact; even with --allow-real-entry-execution it returns "
            "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED."
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
    parser.add_argument("--from-latest-guarded-design-review", action="store_true",
                        help=("Read tiny lifecycle guarded runner design "
                              "review JSON (TASK-014AD artifact) from "
                              "outputs/.../tiny_lifecycle_guarded_runner_design_review/."))
    parser.add_argument("--from-latest-guarded-entry-adapter", action="store_true",
                        help=("Read tiny guarded entry dry-run adapter JSON "
                              "(TASK-014AE artifact) from "
                              "outputs/.../tiny_guarded_entry_dry_run_adapter/."))
    parser.add_argument("--from-latest-guarded-stop-adapter", action="store_true",
                        help=("Read tiny guarded stop-attach dry-run adapter "
                              "JSON (TASK-014AF artifact) from "
                              "outputs/.../tiny_guarded_stop_attach_dry_run_adapter/."))
    parser.add_argument("--from-latest-guarded-cleanup-adapter", action="store_true",
                        help=("Read tiny guarded cleanup dry-run adapter "
                              "JSON (TASK-014AG artifact) from "
                              "outputs/.../tiny_guarded_cleanup_dry_run_adapter/."))
    parser.add_argument("--from-latest-guarded-lifecycle-summary", action="store_true",
                        help=("Read tiny guarded lifecycle dry-run summary "
                              "JSON (TASK-014AH artifact) from "
                              "outputs/.../tiny_guarded_lifecycle_dry_run_summary/."))
    parser.add_argument("--from-latest-entry-real-permission-review", action="store_true",
                        help=("Read tiny guarded entry real permission review "
                              "JSON (TASK-014AI artifact) from "
                              "outputs/.../tiny_guarded_entry_real_permission_review/."))
    parser.add_argument("--from-latest-entry-manual-auth-design", action="store_true",
                        help=("Read tiny guarded entry manual authorization "
                              "design JSON (TASK-014AJ artifact) from "
                              "outputs/.../tiny_guarded_entry_manual_authorization_design/."))
    parser.add_argument("--from-latest-entry-manual-auth-dry-run", action="store_true",
                        help=("Read tiny guarded entry manual authorization "
                              "dry-run JSON (TASK-014AK artifact) from "
                              "outputs/.../tiny_guarded_entry_manual_authorization_dry_run/."))
    parser.add_argument("--from-latest-entry-final-pre-execution-review", action="store_true",
                        help=("Read tiny guarded entry final pre-execution "
                              "review JSON (TASK-014AL artifact) from "
                              "outputs/.../tiny_guarded_entry_final_pre_execution_review/."))
    parser.add_argument("--from-latest-entry-manual-approval-gate", action="store_true",
                        help=("Read tiny guarded entry real execution manual "
                              "approval gate JSON (TASK-014AM artifact) from "
                              "outputs/.../tiny_guarded_entry_real_execution_manual_approval_gate/."))
    parser.add_argument("--symbol", default=DEFAULT_SELECTED_SYMBOL,
                        metavar="SYMBOL",
                        help=("Symbol to adapter-design against.  "
                              "MUST equal SOLUSDT (post-entry symbol).  MUST "
                              "NOT be in the 5 existing demo position symbols "
                              "(ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / "
                              "EDUUSDT)."))
    parser.add_argument("--expected-commit-hash", default="",
                        metavar="HASH",
                        help=("Optional expected commit hash to record in the "
                              "documentation sync review (recorded only; the "
                              "design review NEVER performs an automatic git "
                              "commit or push)."))
    parser.add_argument("--allow-adapter-design-approval", action="store_true",
                        help=("Promote envelope to adapter_design_approval. "
                              "Even with this flag, TASK-014AN only emits an "
                              "adapter-design artifact "
                              "(readiness_conclusion stays "
                              "DESIGN_REVIEW_READY_NOT_EXECUTABLE).  "
                              "No implementation, no execution, no real "
                              "token validation, no token-to-authorization "
                              "mapping, no real phrase validation, no "
                              "phrase-to-authorization mapping, no real "
                              "approval-input validation, no automatic git "
                              "commit, no automatic git push."))
    parser.add_argument("--allow-real-entry-execution", action="store_true",
                        help=("Guarded flag for a hypothetical future real "
                              "tiny entry sender execution.  TASK-014AN "
                              "returns REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED "
                              "even when this flag is set (no socket opened, "
                              "no real sender implemented, no adapter `send` "
                              "method exposed)."))
    parser.add_argument("--write-report", action="store_true",
                        help=("Write JSON + Markdown report to "
                              "outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_design/."))
    args = parser.parse_args()
    sys.exit(run_execute(
        symbol=args.symbol,
        expected_commit_hash=args.expected_commit_hash,
        allow_adapter_design_approval=args.allow_adapter_design_approval,
        allow_real_entry_execution=args.allow_real_entry_execution,
        write_report=args.write_report,
    ))


if __name__ == "__main__":
    main()
