"""TASK-014BM preview CLI -- demo-only tiny order execution smoke runner.

Default mode is ``readiness`` -- no network, no order, no secret read.
Optional ``--mode execute_demo_order`` *requires* both
``--execute-demo-order`` and ``--i-understand-this-sends-one-bybit-demo-order``
to be present. Without both flags, the CLI refuses to call the network
even if the mode argument is set.

If ``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET`` are not set in the
environment, the CLI produces a MISSING_DEMO_CREDENTIALS report and
exits with code 2 -- it never falls back to live credentials.

Exit codes:
    0 -- final_status is DRY_RUN_OK_NO_NETWORK / READINESS_OK_NO_NETWORK
         / EXECUTED_DEMO_ONLY
    1 -- final_status is GATE_REJECTED_NO_NETWORK / NETWORK_ERROR_DEMO_ONLY
         / BYBIT_REJECTED_NO_ORDER_SENT
    2 -- final_status is MISSING_DEMO_CREDENTIALS
"""

from __future__ import annotations

import argparse
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


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "TASK-014BM -- demo-only tiny execution adapter explicit tiny "
            "order execution preview"
        )
    )
    parser.add_argument(
        "--mode",
        default="readiness",
        choices=["dry_run", "readiness", "execute_demo_order"],
        help="execution mode (default: readiness, no network)",
    )
    parser.add_argument(
        "--execute-demo-order",
        action="store_true",
        help=(
            "first of two required confirmation flags for actually sending "
            "one Bybit Demo tiny order"
        ),
    )
    parser.add_argument(
        "--i-understand-this-sends-one-bybit-demo-order",
        dest="i_understand_this_sends_one_bybit_demo_order",
        action="store_true",
        help=(
            "second of two required confirmation flags; without this AND "
            "--execute-demo-order, no network call is made"
        ),
    )
    parser.add_argument(
        "--endpoint-target",
        default=None,
        help=(
            "override demo endpoint target (default: the single allowed "
            "https://api-demo.bybit.com/v5/order/create)"
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="write JSON + Markdown report to the BM output directory",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="override the BM output directory (default: outputs/demo_trading/...)",
    )
    args = parser.parse_args(argv)

    from src import (
        demo_only_tiny_execution_adapter_tiny_order_execution as bm,
    )

    kwargs: dict[str, object] = {
        "mode": args.mode,
        "execute_flag": bool(args.execute_demo_order),
        "confirm_flag": bool(args.i_understand_this_sends_one_bybit_demo_order),
    }
    if args.endpoint_target is not None:
        kwargs["endpoint_target"] = args.endpoint_target

    report = bm.run_explicit_tiny_order_execution(**kwargs)

    print(
        f"task_id={report.task_id} identity={report.identity} "
        f"phase={report.phase}"
    )
    print(
        f"mode={report.mode} final_status={report.final_status} "
        f"is_review_chain_suffix={report.is_review_chain_suffix}"
    )
    print(
        f"upstream_tasks={','.join(report.upstream_tasks)} "
        f"next_required_task={report.next_required_task}"
    )
    print(
        f"bl_packet_loaded={report.bl_packet_loaded} "
        f"bl_packet_all_passed={report.bl_packet_all_passed} "
        f"packet_symbol={report.packet_symbol!r}"
    )
    print(
        f"packet_audit_response_status={report.packet_audit_response_status!r} "
        f"packet_is_not_execution_authorization="
        f"{report.packet_is_not_execution_authorization}"
    )
    print(
        f"explicit_execute_flag_present={report.explicit_execute_flag_present} "
        f"explicit_confirm_flag_present={report.explicit_confirm_flag_present} "
        f"demo_credentials_present={report.demo_credentials_present}"
    )
    print(
        f"live_endpoint_denied={report.live_endpoint_denied} "
        f"protected_symbols_untouched={report.protected_symbols_untouched} "
        f"max_order_count={report.max_order_count}"
    )
    print(
        f"all_pre_network_gates_passed={report.all_pre_network_gates_passed} "
        f"all_execute_gates_passed={report.all_execute_gates_passed}"
    )
    for gate in report.gates:
        flag = "PASS" if gate.passed else "FAIL"
        reason = f" -- {gate.reason}" if gate.reason else ""
        print(f"  gate[{flag}] {gate.name}{reason}")
    print(
        f"network_attempted={report.network_attempted} "
        f"order_endpoint_called={report.order_endpoint_called} "
        f"order_sent={report.order_sent} "
        f"bybit_order_id={report.bybit_order_id!r}"
    )
    print(
        f"bybit_ret_code={report.bybit_ret_code} "
        f"bybit_ret_msg={report.bybit_ret_msg!r}"
    )
    # TASK-014BM_EXECUTION_BODY_AUTHORIZED_QTY_SOURCE_SWITCH surfaces:
    print(
        f"actual_request_body_qty={report.actual_request_body_qty!r} "
        f"actual_request_body_qty_source={report.actual_request_body_qty_source!r} "
        f"body_qty_authorized_override={report.body_qty_authorized_override}"
    )
    if report.body_qty_rejection_reason:
        print(
            f"body_qty_rejection_reason={report.body_qty_rejection_reason!r}"
        )

    if args.write_report:
        paths = bm.write_report(report, output_dir=args.output_dir)
        print("wrote:")
        for key, path in paths.items():
            print(f"  {key}: {path}")

    status = report.final_status
    if status in (
        bm.STATUS_DRY_RUN_OK_NO_NETWORK,
        bm.STATUS_READINESS_OK_NO_NETWORK,
        bm.STATUS_EXECUTED_DEMO_ONLY,
    ):
        return 0
    if status == bm.STATUS_MISSING_DEMO_CREDENTIALS:
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
