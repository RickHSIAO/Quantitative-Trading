#!/usr/bin/env python3
"""
scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py

Preview CLI for TASK-014BF -- Guarded Entry Real Execution Adapter
Disabled Implementation Scaffold Manual Authorization Gate Final
Pre-Execution Review Manual Authorization Review Final Pre-Execution
Review Manual Authorization Review.

Documented-only-never-authorized.  This preview script does NOT call
endpoints, does NOT read secrets, does NOT modify positions, does NOT
lift TASK-014L sender G20, and does NOT execute real entries.  It only
consumes the TASK-014BE manual authorization review FINAL PRE-EXECUTION
REVIEW JSON artifact at runtime, evaluates BF's 37 hard-fail gates, and
emits a manual-authorization-review artifact for the future TASK-014BG
dry-run.

TASK phase mapping:
  * TASK-014BF -- FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW
    (this module).
  * TASK-014BE -- FINAL PRE-EXECUTION REVIEW (direct upstream consumed
    at runtime).
  * TASK-014BD -- READINESS REVIEW (chained proof through BE only).
  * TASK-014BC -- DRY-RUN (chained proof through BE only).
  * TASK-014BB / BA / AZ / AY / AX / AW / AV / AU / AT / AS / AR / AQ --
    chained proof through BE; NOT consumed directly by BF.

Usage (default -- consumes BE latest artifact):
  python scripts/preview_demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py \\
    --from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review \\
    --symbol SOLUSDT \\
    [--expected-commit-hash <hash>] \\
    [--write-report]

IMPORTANT:
  - TASK-014BF is a STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-
    AUTHORIZATION-GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-
    REVIEW-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY
    review.  No guarded entry sender, no adapter implementation, no
    order send, no stop-attach send, no cleanup send, no endpoint
    invoked.  No network, no socket, no environment-variable reads, no
    signing.  NO real token validation, NO token-to-authorization
    mapping, NO real phrase validation, NO phrase-to-authorization
    mapping, NO real approval-input validation.  No automatic git
    commit, no automatic git push.
  - Even with --allow-disabled-..-manual-authorization-review the module
    only emits a documented-only-never-authorized review artifact.
  - Even with --allow-real-entry-execution the review returns
    REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED (no socket opened, no real
    sender implemented, no adapter `send` method exposed).
  - No --execute / --send / --real-run flag is exposed.
  - --expected-commit-hash is recorded ONLY -- this preview does NOT
    validate it as authorization.
  - TASK-014L sender G20 is NOT lifted by this task.
  - The 5 existing demo positions are NEVER touched.

Exit codes:
  0  STATUS_READY / STATUS_READY_BUT_EXECUTION_DISABLED /
     STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
  1  STATUS_FAIL_CLOSED / missing upstream / any failure
"""
from __future__ import annotations

# Prevent argparse help text from wrapping on narrow Windows terminals.
# Must be set BEFORE argparse is imported so HelpFormatter picks it up.
import os
os.environ.setdefault("COLUMNS", "400")

import argparse
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

from src.demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review import (
    BE_DEFAULT_ARTIFACT_DIR,
    BE_DEFAULT_ARTIFACT_FILE,
    BF_DEFAULT_OUTPUT_DIR,
    IDENTITY_CHECKLIST,
    IDENTITY_STRICT,
    NEXT_REQUIRED_TASK,
    SCOPE_SUMMARY_LITERAL,
    STATUS_FAIL_CLOSED,
    STATUS_READY,
    STATUS_READY_BUT_EXECUTION_DISABLED,
    STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED,
    TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewFinalPreExecutionReviewManualAuthorizationReviewResult as BFResult,
    get_default_be_artifact_path,
    get_default_bf_output_dir,
    run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review as run_bf,
    write_report,
)

_SEP = "-" * 72

_DEFAULT_BE_ARTIFACT_DIR = ROOT / BE_DEFAULT_ARTIFACT_DIR
_DEFAULT_BE_ARTIFACT_FILE = _DEFAULT_BE_ARTIFACT_DIR / BE_DEFAULT_ARTIFACT_FILE
_DEFAULT_OUTPUT_DIR = ROOT / BF_DEFAULT_OUTPUT_DIR

DEFAULT_SELECTED_SYMBOL = "SOLUSDT"


def _print_banner() -> None:
    print(_SEP)
    print(
        "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
        "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW FINAL "
        "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW --- NO NETWORK "
        "--- documented-only-never-authorized"
    )
    print(_SEP)
    print(
        "TASK-014BF consumes TASK-014BE disabled implementation scaffold "
        "manual authorization gate final pre-execution review manual "
        "authorization review final pre-execution review output."
    )
    print(_SEP)


def _print_result(r: BFResult) -> None:
    print(f"  status                                     : {r.status}")
    print(f"  mode                                       : {r.mode}")
    print(f"  selected_symbol                            : {r.selected_symbol or '(none)'}")
    print(f"  adapter_name                               : {r.adapter_name}")
    print(f"  adapter_contract_version                   : {r.adapter_contract_version}")
    print(
        "  conclusion                                 : "
        f"{r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_conclusion}"
    )
    print(
        "  authorization_result                       : "
        f"{r.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_authorization_result}"
    )
    print(f"  response_status                            : {r.response_status}")
    print(f"  next_required_task                         : {r.next_required_task}")
    print(f"  failed_stage                               : {r.failed_stage or '(none)'}")
    print(f"  identity_checklist                         : {r.identity_checklist}")
    print(f"  identity_strict                            : {r.identity_strict}")
    print()
    print("  ----- Safety invariants -----")
    print(f"  manual_authorization_review_final_pre_execution_review_manual_authorization_review_only : {r.manual_authorization_review_final_pre_execution_review_manual_authorization_review_only}")
    print(f"  executable_adapter_included                : {r.executable_adapter_included}")
    print(f"  adapter_implementation_included            : {r.adapter_implementation_included}")
    print(f"  adapter_execution_included                 : {r.adapter_execution_included}")
    print(f"  send_method_included                       : {r.send_method_included}")
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
    be_artifact_path: Path | None = None,
    output_dir: Path | None = None,
) -> int:
    """Execute one BF manual authorization review and print a stdout summary.

    Returns an exit code suitable for sys.exit().
    """
    _be_path = be_artifact_path or _DEFAULT_BE_ARTIFACT_FILE
    _out_dir = output_dir or _DEFAULT_OUTPUT_DIR

    _print_banner()
    print(f"  be_artifact_path                           : {_be_path}")
    print(f"  output_dir                                 : {_out_dir}")
    print(f"  expected_commit_hash                       : {expected_commit_hash or '(none)'}  (recorded only, NOT validated as authorization)")
    print(
        "  allow_disabled_..._manual_authorization_review : "
        f"{allow_manual_authorization_review}"
    )
    print(f"  allow_real_entry_execution                 : {allow_real_entry_execution}")
    print(f"  write_report                               : {write_report_flag}")
    print(f"  scope_summary                              : {SCOPE_SUMMARY_LITERAL}")
    print(_SEP)

    result = run_bf(
        symbol=symbol,
        be_artifact_path=_be_path,
        allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review=allow_manual_authorization_review,
        allow_real_entry_execution=allow_real_entry_execution,
    )

    _print_result(result)

    if write_report_flag:
        try:
            paths = write_report(result, _out_dir)
            print(_SEP)
            print(f"  report json    : {paths['latest_json'].resolve()}")
            print(f"  report md      : {paths['latest_md'].resolve()}")
            print(f"  report json_ts : {paths['timestamped_json'].resolve()}")
            print(f"  report md_ts   : {paths['timestamped_md'].resolve()}")
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
    # COLUMNS already set at module top before argparse import.
    parser = argparse.ArgumentParser(
        description=(
            "Tiny guarded entry REAL EXECUTION ADAPTER DISABLED "
            "IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
            "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW FINAL "
            "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW "
            "(TASK-014BF).  Consumes TASK-014BE Disabled Implementation "
            "Scaffold Manual Authorization Gate Final Pre-Execution "
            "Review Manual Authorization Review Final Pre-Execution "
            "Review output at runtime (BF is the final pre-execution "
            "review manual authorization review; BE is the final "
            "pre-execution review; BD is the readiness review; BC is "
            "the dry-run) and produces a manual-authorization-review "
            "artifact for the future TASK-014BG dry-run.  BF directly "
            "consumes BE only -- BD, BC, BB, BA, AZ, AY, AX, AW, AV, AU, "
            "AT, AS, AR, AQ are chained proof through BE, not consumed "
            "directly by BF.  Documented-only-never-authorized: final "
            "pre-execution review manual authorization review only -- "
            "no real execution, no sender, no endpoint call, no secret "
            "read, no G20 lift, no position modification, main.py / "
            "src/risk.py / BybitExecutor untouched.  No network, no live "
            "endpoint, no orders / positions modified, no guarded entry "
            "sender implemented, no executable adapter, no adapter "
            "`send` method, no real entry execution, no real token "
            "validation, no token-to-authorization mapping, no real "
            "phrase validation, no phrase-to-authorization mapping, no "
            "real approval-input validation, no automatic git commit, "
            "no automatic git push.  Even with "
            "--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review-manual-authorization-review "
            "this only emits a documented-only-never-authorized review "
            "artifact whose conclusion remains DISABLED IMPLEMENTATION "
            "SCAFFOLD MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION "
            "REVIEW MANUAL AUTHORIZATION REVIEW FINAL PRE-EXECUTION "
            "REVIEW MANUAL AUTHORIZATION REVIEW READY NOT EXECUTABLE; "
            "even with --allow-real-entry-execution it returns "
            "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED."
        ),
        epilog=(
            "TASK-014BF is a documented-only-never-authorized final "
            "pre-execution review manual authorization review module.  "
            "It never authorizes real execution, never opens a socket, "
            "never invokes /v5/order/create, never invokes "
            "/v5/position/trading-stop, never modifies any of the 5 "
            "existing demo positions (ENAUSDT / TIAUSDT / AIXBTUSDT / "
            "POLYXUSDT / EDUUSDT), never lifts TASK-014L sender G20."
        ),
    )

    parser.add_argument(
        "--from-latest-entry-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review",
        action="store_true",
        dest="from_latest_be",
        help=(
            "Read the TASK-014BE disabled implementation scaffold "
            "manual authorization gate final pre-execution review "
            "manual authorization review FINAL PRE-EXECUTION REVIEW "
            "JSON from the default outputs/demo_trading/.../manual_"
            "authorization_review_final_pre_execution_review/latest_*."
            "json location.  BE is the final pre-execution review "
            "consumed by BF; BF itself is the final pre-execution "
            "review manual authorization review."
        ),
    )
    parser.add_argument(
        "--be-artifact-path",
        default="",
        metavar="PATH",
        help=(
            "Explicit BE artifact path override.  When set, this path "
            "is read instead of the default --from-latest-* location.  "
            "The file must be a valid TASK-014BE manual authorization "
            "review final pre-execution review JSON artifact."
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
            "BF commit hash for the report (recorded only; this "
            "preview does not validate it as authorization)."
        ),
    )
    parser.add_argument(
        "--allow-disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-manual-authorization-review-final-pre-execution-review-manual-authorization-review",
        dest="allow_manual_authorization_review",
        action="store_true",
        help=(
            "Promote envelope to manual_authorization_review checklist "
            "confirmation.  Even with this flag, TASK-014BF only emits "
            "a documented-only-never-authorized final-pre-execution-"
            "review manual-authorization-review artifact (conclusion "
            "remains MANUAL_AUTHORIZATION_REVIEW_READY_NOT_EXECUTABLE).  "
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
            "Documented opt-in only; real entry execution is NOT "
            "implemented and this flag will not cause any send / "
            "place_order / execute.  TASK-014BF returns "
            "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED (no socket opened, "
            "no real sender implemented, no adapter `send` method "
            "exposed)."
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=(
            "Write JSON + Markdown report to outputs/demo_trading/"
            "tiny_guarded_entry_real_execution_adapter_disabled_"
            "implementation_scaffold_manual_authorization_gate_final_"
            "pre_execution_review_manual_authorization_review_final_"
            "pre_execution_review_manual_authorization_review/."
        ),
    )
    parser.add_argument(
        "--output-dir",
        default="",
        metavar="PATH",
        help=(
            "Override the default BF output directory.  Only "
            "meaningful when --write-report is also set."
        ),
    )

    args = parser.parse_args()

    # Resolve BE artifact path: explicit override > --from-latest > default.
    if args.be_artifact_path:
        be_path: Path | None = Path(args.be_artifact_path).resolve()
    elif args.from_latest_be:
        be_path = _DEFAULT_BE_ARTIFACT_FILE
    else:
        be_path = _DEFAULT_BE_ARTIFACT_FILE

    out_dir = Path(args.output_dir).resolve() if args.output_dir else _DEFAULT_OUTPUT_DIR

    sys.exit(
        run_execute(
            symbol=args.symbol,
            expected_commit_hash=args.expected_commit_hash,
            allow_manual_authorization_review=args.allow_manual_authorization_review,
            allow_real_entry_execution=args.allow_real_entry_execution,
            write_report_flag=args.write_report,
            be_artifact_path=be_path,
            output_dir=out_dir,
        )
    )


if __name__ == "__main__":
    main()
