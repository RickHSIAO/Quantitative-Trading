"""
scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py
TASK-014BB: Guarded Entry Real Execution Adapter Disabled Implementation
            Scaffold Manual Authorization Gate Final Pre-Execution Review
            Manual Authorization Review CLI.

Usage (DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL
       PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW CHECKLIST -- default,
       no network, no implementation, no execution):
  python scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py \\
    --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review \\
    --symbol SOLUSDT \\
    [--expected-commit-hash <hash>] \\
    [--write-report]

Usage (DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL
       PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW APPROVAL --
       documented-only, no execution):
  ... --allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review

Usage (REAL ENTRY EXECUTION GUARD -- always returns
       REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED, no socket opened,
       no real entry sender implemented, no adapter `send` method):
  ... --allow-real-entry-execution

Reads (1 upstream artifact -- BA only):
  outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review/latest_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review.json

Writes (when --write-report):
  outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review/
      latest_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.json
      latest_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.md
      tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_<UTC_TS>.json
      tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_<UTC_TS>.md

IMPORTANT:
  - TASK-014BB produces a STRICT
    DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-FINAL-PRE-
    EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY artifact.
    No guarded entry sender, no adapter implementation, no order send,
    no stop-attach send, no cleanup send, no endpoint invoked. No
    network, no socket, no environment-variable reads, no signing, no
    order send, NO real token validation, NO token-to-authorization
    mapping, NO real phrase validation, NO phrase-to-authorization
    mapping, NO real approval-input validation. NO adapter
    implementation, NO adapter `send` method. This task is a manual
    authorization review only -- it never authorizes any real
    execution. No automatic git commit, no automatic git push.
  - Even with
    --allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review
    the module only emits a documented-only-never-authorized review
    artifact. conclusion is fixed at
    DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY_NOT_EXECUTABLE.
  - Even with --allow-real-entry-execution the review returns
    REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED (no socket opened, no
    real sender implemented).
  - No --execute-real-* / --send-order / --place-order / --real-run
    flag is exposed by this CLI. No --confirm-token flag is exposed
    (token is documented only, never validated by this CLI).
  - No --auto-commit / --git-commit / --auto-push / --git-push flag
    is exposed by this CLI (no automatic git operation).
  - TASK-014L sender G20 (protected_entry_policy_missing) is NOT
    lifted by this task.
  - The 5 existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT /
    POLYXUSDT / EDUUSDT) are NEVER touched.
  - /v5/order/create is NEVER invoked from this CLI.
  - /v5/position/trading-stop is NEVER invoked from this CLI.
  - main.py / src/risk.py / BybitExecutor are NEVER imported or
    invoked from this CLI.

Exit codes:
  0  STATUS_READY / STATUS_READY_BUT_EXECUTION_DISABLED /
     STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
  1  STATUS_FAIL_CLOSED / missing upstream / any failure
"""
from __future__ import annotations

import argparse
import json
import os
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

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review import (
    ADAPTER_CONTRACT_VERSION,
    ADAPTER_NAME,
    BA_DEFAULT_ARTIFACT_DIR,
    BA_DEFAULT_ARTIFACT_FILE,
    BB_DEFAULT_OUTPUT_DIR,
    IDENTITY_CHECKLIST,
    IDENTITY_STRICT,
    NEXT_REQUIRED_TASK,
    SCOPE_SUMMARY_LITERAL,
    STATUS_FAIL_CLOSED,
    STATUS_READY,
    STATUS_READY_BUT_EXECUTION_DISABLED,
    STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewResult,
    _load_ba_final_pre_execution_review_artifact,
    get_default_ba_artifact_path,
    get_default_bb_output_dir,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review,
    write_report,
)

_SEP = "-" * 72

_DEFAULT_BA_ARTIFACT_DIR = ROOT / BA_DEFAULT_ARTIFACT_DIR
_DEFAULT_BA_ARTIFACT_FILE = _DEFAULT_BA_ARTIFACT_DIR / BA_DEFAULT_ARTIFACT_FILE
_DEFAULT_OUTPUT_DIR = ROOT / BB_DEFAULT_OUTPUT_DIR

DEFAULT_SELECTED_SYMBOL = "SOLUSDT"
_EXISTING_DEMO_SYMBOLS = (
    "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
)


def _print_banner() -> None:
    print(_SEP)
    print(
        "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
        "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW CHECKLIST "
        "--- NO NETWORK --- manual-authorization-review-only"
    )
    print(_SEP)


def _print_result(
    r: TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewResult,
) -> None:
    print(f"  status                                     : {r.status}")
    print(f"  mode                                       : {r.mode}")
    print(f"  selected_symbol                            : {r.selected_symbol or '(none)'}")
    print(f"  adapter_name                               : {r.adapter_name}")
    print(f"  adapter_contract_version                   : {r.adapter_contract_version}")
    print(
        "  conclusion                                 : "
        f"{r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion}"
    )
    print(
        "  authorization_result                       : "
        f"{r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result}"
    )
    print(f"  response_status                            : {r.response_status}")
    print(f"  next_required_task                         : {r.next_required_task}")
    print(f"  failed_stage                               : {r.failed_stage or '(none)'}")
    print(f"  identity_checklist                         : {r.identity_checklist}")
    print(f"  identity_strict                            : {r.identity_strict}")
    print()
    print("  ----- Safety invariants -----")
    print(f"  manual_authorization_review_only           : {r.manual_authorization_review_only}")
    print(f"  executable_adapter_included                : {r.executable_adapter_included}")
    print(f"  adapter_implementation_included            : {r.adapter_implementation_included}")
    print(f"  adapter_execution_included                 : {r.adapter_execution_included}")
    print(f"  send_method_included                       : {r.send_method_included}")
    print(f"  place_order_method_included                : {r.place_order_method_included}")
    print(f"  execute_method_included                    : {r.execute_method_included}")
    print(f"  real_entry_implemented                     : {r.real_entry_implemented}")
    print(f"  real_execution_allowed                     : {r.real_execution_allowed}")
    print(f"  current_task_real_execution_allowed        : {r.current_task_real_execution_allowed}")
    print(f"  send_allowed                               : {r.send_allowed}")
    print(f"  order_endpoint_called                      : {r.order_endpoint_called}")
    print(f"  stop_endpoint_called                       : {r.stop_endpoint_called}")
    print(f"  no_position_modified                       : {r.no_position_modified}")
    print(f"  no_live_endpoint                           : {r.no_live_endpoint}")
    print(f"  no_orders_sent                             : {r.no_orders_sent}")
    print(f"  no_secrets_loaded                          : {r.no_secrets_loaded}")
    print(f"  secret_value_observed                      : {r.secret_value_observed}")
    print(f"  g20_policy_still_in_place                  : {r.g20_policy_still_in_place}")
    print(f"  g20_lifted                                 : {r.g20_lifted}")
    print(
        "  existing_positions_touched                 : "
        f"{', '.join(r.existing_positions_touched) or '(none)'}"
    )
    if r.blocked_gates:
        print(f"  blocked_gates ({len(r.blocked_gates)}):")
        for g in r.blocked_gates:
            print(f"    - {g}")
    else:
        print("  blocked_gates                              : (none)")


def run_execute(
    *,
    symbol: str = DEFAULT_SELECTED_SYMBOL,
    expected_commit_hash: str = "",
    allow_manual_authorization_review: bool = False,
    allow_real_entry_execution: bool = False,
    write_report_flag: bool = False,
    ba_artifact_path: Path | None = None,
    output_dir: Path | None = None,
) -> int:
    """Execute one BB review and print a stdout summary.

    Returns an exit code suitable for sys.exit().
    """
    _ba_path = ba_artifact_path or _DEFAULT_BA_ARTIFACT_FILE
    _out_dir = output_dir or _DEFAULT_OUTPUT_DIR

    _print_banner()
    print(f"  ba_artifact_path                           : {_ba_path}")
    print(f"  output_dir                                 : {_out_dir}")
    print(f"  expected_commit_hash                       : {expected_commit_hash or '(none)'}")
    print(
        "  allow_manual_authorization_review          : "
        f"{allow_manual_authorization_review}"
    )
    print(f"  allow_real_entry_execution                 : {allow_real_entry_execution}")
    print(f"  write_report                               : {write_report_flag}")
    print(f"  scope_summary                              : {SCOPE_SUMMARY_LITERAL}")
    print(_SEP)

    # Load BA artifact (may be None -- run() will fail-closed via gate).
    ba_artifact = _load_ba_final_pre_execution_review_artifact(_ba_path)

    result = run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review(
        symbol=symbol,
        ba_artifact_path=_ba_path,
        ba_artifact=ba_artifact,
        allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review=allow_manual_authorization_review,
        allow_real_entry_execution=allow_real_entry_execution,
        expected_commit_hash=expected_commit_hash or None,
    )

    _print_result(result)

    if write_report_flag:
        try:
            paths = write_report(result, _out_dir)
            print(_SEP)
            print(f"  report json    : {paths['json_path']}")
            print(f"  report md      : {paths['md_path']}")
            print(f"  report json_ts : {paths['timestamped_json_path']}")
            print(f"  report md_ts   : {paths['timestamped_md_path']}")
        except OSError as exc:
            print(_SEP)
            print(f"  WARNING: failed to write report: {exc}")

    print(_SEP)

    ok_statuses = (
        STATUS_READY,
        STATUS_READY_BUT_EXECUTION_DISABLED,
        STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    )
    if result.status in ok_statuses:
        return 0
    return 1


def main() -> None:
    # Prevent argparse help text from wrapping on narrow Windows terminals.
    os.environ.setdefault("COLUMNS", "400")

    parser = argparse.ArgumentParser(
        description=(
            "Tiny guarded entry REAL EXECUTION ADAPTER DISABLED "
            "IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
            "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW "
            "(TASK-014BB).  Consumes TASK-014BA disabled implementation "
            "scaffold manual authorization gate final pre-execution "
            "review output at runtime and produces a disabled "
            "implementation scaffold manual authorization gate final "
            "pre-execution review manual authorization review for the "
            "future TASK-014BC dry-run.  Documented-only-never-authorized: "
            "manual authorization review only -- no real execution, no "
            "sender, no endpoint call, no secret read, no G20 lift, no "
            "position modification, main.py / src/risk.py / BybitExecutor "
            "untouched.  No network, no live endpoint, no orders / "
            "positions modified, no guarded entry sender implemented, no "
            "executable adapter, no adapter `send` method, no real entry "
            "execution, no real token validation, no token-to-"
            "authorization mapping, no real phrase validation, no "
            "phrase-to-authorization mapping, no real approval-input "
            "validation, no automatic git commit, no automatic git push.  "
            "Even with "
            "--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review "
            "this only emits a documented-only-never-authorized review "
            "artifact whose conclusion remains "
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY_NOT_EXECUTABLE; "
            "even with --allow-real-entry-execution it returns "
            "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED."
        ),
        epilog=(
            "TASK-014BB is a manual-authorization-review-only module.  "
            "It never authorizes real execution, never opens a socket, "
            "never invokes /v5/order/create, never invokes "
            "/v5/position/trading-stop, never modifies any of the 5 "
            "existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT / "
            "POLYXUSDT / EDUUSDT), never lifts TASK-014L sender G20."
        ),
    )

    parser.add_argument(
        "--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review",
        action="store_true",
        dest="from_latest_ba",
        help=(
            "Read the TASK-014BA disabled implementation scaffold "
            "manual authorization gate final pre-execution review JSON "
            "from outputs/demo_trading/tiny_guarded_entry_real_execution"
            "_adapter_disabled_implementation_scaffold_manual_"
            "authorization_gate_final_pre_execution_review/"
            "latest_tiny_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_"
            "pre_execution_review.json."
        ),
    )
    parser.add_argument(
        "--ba-artifact-path",
        default="",
        metavar="PATH",
        help=(
            "Explicit BA artifact path override.  When set, this path "
            "is read instead of the default --from-latest-* location.  "
            "The file must be a valid TASK-014BA final pre-execution "
            "review JSON artifact."
        ),
    )
    parser.add_argument(
        "--symbol",
        default=DEFAULT_SELECTED_SYMBOL,
        metavar="SYMBOL",
        help=(
            "Symbol to review against.  MUST equal SOLUSDT (post-entry "
            "symbol).  MUST NOT be in the 5 existing demo position "
            "symbols (ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / "
            "EDUUSDT)."
        ),
    )
    parser.add_argument(
        "--expected-commit-hash",
        default="",
        metavar="HASH",
        help=(
            "Optional expected commit hash to record in the review "
            "(recorded only; the manual authorization review NEVER "
            "performs an automatic git commit or push)."
        ),
    )
    parser.add_argument(
        "--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review",
        dest="allow_manual_authorization_review",
        action="store_true",
        help=(
            "Promote envelope to manual_authorization_review_approval.  "
            "Even with this flag, TASK-014BB only emits a documented-"
            "only-never-authorized review artifact (conclusion stays "
            "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY_NOT_EXECUTABLE).  "
            "No implementation, no execution, no real token validation, "
            "no token-to-authorization mapping, no real phrase "
            "validation, no phrase-to-authorization mapping, no real "
            "approval-input validation, no automatic git commit, no "
            "automatic git push."
        ),
    )
    parser.add_argument(
        "--allow-real-entry-execution",
        action="store_true",
        help=(
            "Guarded flag for a hypothetical future real tiny entry "
            "sender execution.  TASK-014BB returns "
            "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED even when this flag "
            "is set (no socket opened, no real sender implemented, no "
            "adapter `send` method exposed)."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=(
            "Write JSON + Markdown report to outputs/demo_trading/"
            "tiny_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_"
            "pre_execution_review_manual_authorization_review/."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="",
        metavar="PATH",
        help=(
            "Override the default BB output directory.  Only meaningful "
            "when --write-report is also set."
        ),
    )

    args = parser.parse_args()

    # Resolve BA artifact path: explicit override > --from-latest > default.
    if args.ba_artifact_path:
        ba_path: Path | None = Path(args.ba_artifact_path).resolve()
    elif args.from_latest_ba:
        ba_path = _DEFAULT_BA_ARTIFACT_FILE
    else:
        ba_path = _DEFAULT_BA_ARTIFACT_FILE

    out_dir = Path(args.output_dir).resolve() if args.output_dir else _DEFAULT_OUTPUT_DIR

    sys.exit(
        run_execute(
            symbol=args.symbol,
            expected_commit_hash=args.expected_commit_hash,
            allow_manual_authorization_review=args.allow_manual_authorization_review,
            allow_real_entry_execution=args.allow_real_entry_execution,
            write_report_flag=args.write_report,
            ba_artifact_path=ba_path,
            output_dir=out_dir,
        )
    )


if __name__ == "__main__":
    main()
