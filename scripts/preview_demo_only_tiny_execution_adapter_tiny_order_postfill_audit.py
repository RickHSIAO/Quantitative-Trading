"""TASK-014BN_demo_only_tiny_execution_postfill_audit preview CLI.

Stage 1, offline / fake-only preview for the postfill audit module.

This CLI never sends any order, never opens any network connection,
never reads credentials, and never authorizes a Stage 2 real Bybit
Demo dispatch. It only constructs an in-memory
``OrchestrationReport`` representing one of four synthetic fixtures
and feeds it through ``run_postfill_audit`` so the audit's behavior
can be inspected without re-running the full one-shot orchestrator.

Exit codes (expressed directly in terms of ``audit_passed``):
    0 -- audit_passed=True
    1 -- audit_passed=False due to NOT_AUDITABLE or a contract / integrity
         mismatch
    2 -- FORBIDDEN_REAL_TRANSPORT, an invalid fixture / configuration, or an
         explicit safety-invariant violation
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys

os.environ.setdefault("COLUMNS", "400")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import (  # noqa: E402
    demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as orch,
)
from src import (  # noqa: E402
    demo_only_tiny_execution_adapter_tiny_order_postfill_audit as pf,
)

FIXTURE_SIMULATED_ACCEPTED = "simulated_accepted"
FIXTURE_SIMULATED_REJECTED = "simulated_rejected"
FIXTURE_SIMULATED_TRANSPORT_ERROR = "simulated_transport_error"
FIXTURE_NOT_AUDITABLE = "not_auditable"
FIXTURES: tuple[str, ...] = (
    FIXTURE_SIMULATED_ACCEPTED,
    FIXTURE_SIMULATED_REJECTED,
    FIXTURE_SIMULATED_TRANSPORT_ERROR,
    FIXTURE_NOT_AUDITABLE,
)

EXIT_OK_AUDITABLE_PASS = 0
EXIT_NOT_AUDITABLE_OR_MISMATCH = 1
EXIT_FORBIDDEN_REAL_TRANSPORT = 2


def _base_body_preview() -> dict:
    return {
        "category": orch.ALLOWED_CATEGORY,
        "symbol": orch.ALLOWED_SYMBOL,
        "side": orch.ALLOWED_SIDE,
        "orderType": orch.ALLOWED_ORDER_TYPE,
        "qty": orch.EXPECTED_CANDIDATE_QTY,
        "timeInForce": orch.ALLOWED_TIME_IN_FORCE,
        "reduceOnly": False,
        "closeOnTrigger": False,
        "orderLinkId": "DEMO_ONLY_PREVIEW_FIXTURE",
    }


def _base_bm_report(
    *,
    body_preview: dict,
    actual_qty: str,
    actual_qty_source: str,
    body_qty_authorized_override: bool,
    final_status: str,
    bybit_ret_code: int | None,
    bybit_order_id: str,
    bybit_ret_msg: str,
    order_sent: bool,
) -> dict:
    return {
        "plan": {
            "body_preview": body_preview,
            "actual_request_body_qty": actual_qty,
            "actual_request_body_qty_source": actual_qty_source,
            "body_qty_authorized_override": body_qty_authorized_override,
        },
        "final_status": final_status,
        "actual_request_body_qty": actual_qty,
        "actual_request_body_qty_source": actual_qty_source,
        "body_qty_authorized_override": body_qty_authorized_override,
        "bybit_ret_code": bybit_ret_code,
        "bybit_ret_msg": bybit_ret_msg,
        "bybit_order_id": bybit_order_id,
        "order_sent": order_sent,
    }


def _base_report_kwargs() -> dict:
    return {
        "task_id": orch.TASK_ID,
        "identity": orch.IDENTITY,
        "phase": orch.IMPLEMENTATION_PATH_PHASE,
        "upstream_tasks": orch.UPSTREAM_TASKS,
        "next_required_task": orch.NEXT_REQUIRED_TASK,
        "is_review_chain_suffix": orch.IS_REVIEW_CHAIN_SUFFIX,
        "orchestration_contract_version": orch.ORCHESTRATION_CONTRACT_VERSION,
        "instrument_rules_loaded": True,
        "instrument_rules_status": "IR_OK",
        "instrument_rules_symbol": orch.ALLOWED_SYMBOL,
        "instrument_rules_trading_status": orch.EXPECTED_INSTRUMENT_STATUS,
        "instrument_rules_min_order_qty": orch.EXPECTED_MIN_ORDER_QTY,
        "instrument_rules_qty_step": orch.EXPECTED_QTY_STEP,
        "candidate_qty": orch.EXPECTED_CANDIDATE_QTY,
        "candidate_notional": "15.0000",
        "qty_0_01_confirmed_invalid": True,
        "cap_gate_status": "ESCALATION_AUTHORIZED",
        "cap_gate_authorized": True,
        "cap_escalated_demo_only": True,
        "explicit_demo_min_qty_cap_authorized": True,
        "wiring_status": "WIRING_AUTHORIZED_CANDIDATE_QTY",
        "wiring_execution_qty_source": (
            "CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY"
        ),
        "wiring_execution_qty": orch.EXPECTED_CANDIDATE_QTY,
        "wiring_execution_notional_estimate": "15.0000",
        "original_packet_qty": orch.ORIGINAL_PACKET_QTY,
        "actual_request_body_qty": orch.EXPECTED_CANDIDATE_QTY,
        "actual_request_body_qty_source": (
            "CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY"
        ),
        "body_qty_authorized_override": True,
        "body_qty_rejection_reason": "",
        "read_only_network_attempted": False,
        "real_execute_disabled_stage1": True,
        "allowed_environment": orch.ALLOWED_ENVIRONMENT,
        "allowed_symbol": orch.ALLOWED_SYMBOL,
        "allowed_side": orch.ALLOWED_SIDE,
        "allowed_order_type": orch.ALLOWED_ORDER_TYPE,
        "allowed_time_in_force": orch.ALLOWED_TIME_IN_FORCE,
        "allowed_max_order_count": orch.ALLOWED_MAX_ORDER_COUNT,
        "tiny_qty_cap_sol": "0.05",
        "tiny_size_cap_usdt": "5",
        "max_demo_min_qty_notional_cap_usdt": "20",
        "protected_symbols_untouched": True,
        "instrument_rules_report": {},
        "cap_escalation_report": {},
        "wiring_report": {},
        "generated_at_utc": "1970-01-01T00:00:00Z",
        "resolved_execution_qty": orch.EXPECTED_CANDIDATE_QTY,
        "resolved_execution_qty_source": (
            "CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY"
        ),
        "resolved_notional": "15.0000",
    }


def _fixture_simulated_accepted() -> orch.OrchestrationReport:
    body = _base_body_preview()
    bm_report = _base_bm_report(
        body_preview=body,
        actual_qty=orch.EXPECTED_CANDIDATE_QTY,
        actual_qty_source="CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY",
        body_qty_authorized_override=True,
        final_status="STATUS_ORDER_SENT_DEMO_ONLY",
        bybit_ret_code=0,
        bybit_order_id="fake-accepted-1",
        bybit_ret_msg="OK",
        order_sent=True,
    )
    base = _base_report_kwargs()
    base.update(
        mode=orch.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        status=orch.STATUS_OK_FAKE_SENDER_EXECUTED,
        reason="fake sender accepted",
        bm_invoked=True,
        bm_mode="execute_demo_order",
        bm_final_status="STATUS_ORDER_SENT_DEMO_ONLY",
        order_network_attempted=True,
        network_attempted=True,
        order_endpoint_called=True,
        order_sent=True,
        bybit_ret_code=0,
        bybit_order_id="fake-accepted-1",
        bybit_ret_msg="OK",
        fake_sender_used=True,
        sender_call_count=1,
        bm_report=bm_report,
        final_status=orch.STATUS_OK_FAKE_SENDER_EXECUTED,
        simulated_order_network_attempted=True,
        simulated_order_endpoint_called=True,
        simulated_order_sent=True,
        order_transport_kind=orch.ORDER_TRANSPORT_KIND_FAKE_SENDER,
    )
    return orch.OrchestrationReport(**base)


def _fixture_simulated_rejected() -> orch.OrchestrationReport:
    body = _base_body_preview()
    bm_report = _base_bm_report(
        body_preview=body,
        actual_qty=orch.EXPECTED_CANDIDATE_QTY,
        actual_qty_source="CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY",
        body_qty_authorized_override=True,
        final_status="STATUS_REJECTED_BY_BYBIT_DEMO",
        bybit_ret_code=10001,
        bybit_order_id="",
        bybit_ret_msg="Insufficient balance",
        order_sent=False,
    )
    base = _base_report_kwargs()
    base.update(
        mode=orch.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        status=orch.STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED,
        reason="bybit returned non-zero retCode",
        bm_invoked=True,
        bm_mode="execute_demo_order",
        bm_final_status="STATUS_REJECTED_BY_BYBIT_DEMO",
        order_network_attempted=True,
        network_attempted=True,
        order_endpoint_called=True,
        order_sent=False,
        bybit_ret_code=10001,
        bybit_order_id="",
        bybit_ret_msg="Insufficient balance",
        fake_sender_used=True,
        sender_call_count=1,
        bm_report=bm_report,
        final_status=orch.STATUS_REJECTED_BM_BYBIT_NOT_EXECUTED,
        simulated_order_network_attempted=True,
        simulated_order_endpoint_called=True,
        simulated_order_sent=True,
        order_transport_kind=orch.ORDER_TRANSPORT_KIND_FAKE_SENDER,
    )
    return orch.OrchestrationReport(**base)


def _fixture_simulated_transport_error() -> orch.OrchestrationReport:
    body = _base_body_preview()
    bm_report = _base_bm_report(
        body_preview=body,
        actual_qty=orch.EXPECTED_CANDIDATE_QTY,
        actual_qty_source="CAP_ESCALATION_AUTHORIZED_CANDIDATE_QTY",
        body_qty_authorized_override=True,
        final_status="STATUS_NETWORK_ERROR_DEMO_ONLY",
        bybit_ret_code=None,
        bybit_order_id="",
        bybit_ret_msg="",
        order_sent=False,
    )
    base = _base_report_kwargs()
    base.update(
        mode=orch.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER,
        status=orch.STATUS_REJECTED_BM_NETWORK_ERROR,
        reason="fake sender raised",
        bm_invoked=True,
        bm_mode="execute_demo_order",
        bm_final_status="STATUS_NETWORK_ERROR_DEMO_ONLY",
        order_network_attempted=True,
        network_attempted=True,
        order_endpoint_called=True,
        order_sent=False,
        bybit_ret_code=None,
        bybit_order_id="",
        bybit_ret_msg="",
        fake_sender_used=True,
        sender_call_count=1,
        bm_report=bm_report,
        final_status=orch.STATUS_REJECTED_BM_NETWORK_ERROR,
        simulated_order_network_attempted=True,
        simulated_order_endpoint_called=True,
        simulated_order_sent=False,
        order_transport_kind=orch.ORDER_TRANSPORT_KIND_FAKE_SENDER,
    )
    return orch.OrchestrationReport(**base)


def _fixture_not_auditable() -> orch.OrchestrationReport:
    base = _base_report_kwargs()
    base.update(
        mode=orch.ORCH_MODE_READINESS,
        status=orch.STATUS_OK_READINESS_NO_NETWORK,
        reason="readiness only -- no BM execute",
        bm_invoked=False,
        bm_mode="readiness",
        bm_final_status="",
        order_network_attempted=False,
        network_attempted=False,
        order_endpoint_called=False,
        order_sent=False,
        bybit_ret_code=None,
        bybit_order_id="",
        bybit_ret_msg="",
        fake_sender_used=False,
        sender_call_count=0,
        bm_report={},
        final_status=orch.STATUS_OK_READINESS_NO_NETWORK,
    )
    return orch.OrchestrationReport(**base)


_FIXTURE_BUILDERS = {
    FIXTURE_SIMULATED_ACCEPTED: _fixture_simulated_accepted,
    FIXTURE_SIMULATED_REJECTED: _fixture_simulated_rejected,
    FIXTURE_SIMULATED_TRANSPORT_ERROR: _fixture_simulated_transport_error,
    FIXTURE_NOT_AUDITABLE: _fixture_not_auditable,
}


def build_fixture(name: str) -> orch.OrchestrationReport:
    builder = _FIXTURE_BUILDERS.get(name)
    if builder is None:
        raise SystemExit(f"unknown --fixture {name!r}; choose from {FIXTURES}")
    return builder()


def _simulated_business_outcome(report: pf.PostfillAuditReport) -> str:
    """Derive a CLI-only simulated business-outcome label from the status.

    This is the simulated (fake-only) outcome, never a real order outcome.
    """

    return {
        pf.AUDIT_STATUS_SIMULATED_ACCEPTED: "ACCEPTED",
        pf.AUDIT_STATUS_SIMULATED_REJECTED: "REJECTED",
        pf.AUDIT_STATUS_SIMULATED_TRANSPORT_ERROR: "TRANSPORT_ERROR",
    }.get(report.audit_status, "NONE")


def _cli_summary_fields(
    report: pf.PostfillAuditReport, *, report_written: bool
) -> dict:
    """Authoritative CLI summary fields (machine + human surfaces)."""

    return {
        "task_id": report.task_id,
        "audit_status": report.audit_status,
        "audit_passed": report.audit_passed,
        "audit_reason": report.audit_reason,
        "simulated_business_outcome": _simulated_business_outcome(report),
        "order_transport_kind": report.order_transport_kind,
        "sender_call_count": report.sender_call_count,
        "simulated_order_sent": report.simulated_order_sent,
        "legacy_order_sent": report.order_sent,
        "real_order_sent": report.real_order_sent,
        "actual_request_body_qty": report.actual_request_body_qty,
        "actual_request_body_qty_source": (
            report.actual_request_body_qty_source
        ),
        "resolved_notional": report.resolved_notional,
        "failed_check_count": len(report.integrity_failed_checks),
        "failed_check_names": list(report.integrity_failed_checks),
        "report_written": report_written,
    }


def _decide_exit_code(report: pf.PostfillAuditReport) -> int:
    # Exit codes are expressed directly in terms of audit_passed.
    if report.audit_status == pf.AUDIT_STATUS_FORBIDDEN_REAL_TRANSPORT:
        return EXIT_FORBIDDEN_REAL_TRANSPORT
    if report.audit_passed:
        return EXIT_OK_AUDITABLE_PASS
    return EXIT_NOT_AUDITABLE_OR_MISMATCH


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "TASK-014BN postfill audit preview -- strictly offline, "
            "no network, no order send."
        )
    )
    parser.add_argument(
        "--fixture",
        choices=FIXTURES,
        default=FIXTURE_SIMULATED_ACCEPTED,
        help="which synthetic orchestration fixture to audit (default: %(default)s)",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help=(
            "also write the audit report to JSON + Markdown "
            "(default: stdout only)"
        ),
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default=None,
        help=(
            "override the default output directory "
            "(only used when --write-report is set)"
        ),
    )
    parser.add_argument(
        "--json-only",
        action="store_true",
        help="emit only the JSON payload on stdout (no Markdown summary)",
    )
    args = parser.parse_args(argv)

    fixture_report = build_fixture(args.fixture)
    audit_report = pf.run_postfill_audit(fixture_report)

    # Write first (if requested) so report_written is accurate in output.
    written_paths: dict = {}
    if args.write_report:
        written_paths = pf.write_report(
            audit_report, output_dir=args.output_dir
        )
    report_written = bool(written_paths)

    cli_summary = _cli_summary_fields(
        audit_report, report_written=report_written
    )

    # The JSON payload carries the full report plus the authoritative CLI
    # summary fields (audit_passed / audit_reason / legacy_order_sent /
    # simulated_business_outcome / failed_check_* / report_written, ...).
    payload_dict = audit_report.to_dict()
    payload_dict.update(cli_summary)
    payload = json.dumps(payload_dict, indent=2, sort_keys=True, default=str)

    if args.json_only:
        print(payload)
    else:
        print(payload)
        print()
        print(f"task_id={audit_report.task_id}")
        print(f"audit_status={audit_report.audit_status}")
        print(f"audit_passed={audit_report.audit_passed}")
        print(f"audit_reason={audit_report.audit_reason}")
        print("-- audit integrity (offline/fake-only evidence consistency) --")
        print(
            f"auditable={audit_report.auditable} "
            f"integrity_all_passed={audit_report.integrity_all_passed} "
            f"failed_check_count={cli_summary['failed_check_count']}"
        )
        print(
            "failed_check_names: "
            + (", ".join(audit_report.integrity_failed_checks) or "(none)")
        )
        print("-- business outcome (simulated, never a real order) --")
        print(
            f"simulated_business_outcome="
            f"{cli_summary['simulated_business_outcome']} "
            f"simulated_order_sent={audit_report.simulated_order_sent} "
            f"legacy_order_sent={audit_report.order_sent}"
        )
        print("-- real order activity (Stage 1 guarantees all False) --")
        print(
            f"real_order_sent={audit_report.real_order_sent} "
            f"order_transport_kind={audit_report.order_transport_kind}"
        )
        print(
            f"actual_request_body_qty={audit_report.actual_request_body_qty} "
            f"actual_request_body_qty_source="
            f"{audit_report.actual_request_body_qty_source} "
            f"resolved_notional={audit_report.resolved_notional} "
            f"sender_call_count={audit_report.sender_call_count}"
        )
        print(f"report_written={report_written}")
        if written_paths:
            for key in sorted(written_paths):
                print(f"wrote {key}: {written_paths[key]}")

    return _decide_exit_code(audit_report)


if __name__ == "__main__":
    raise SystemExit(main())
