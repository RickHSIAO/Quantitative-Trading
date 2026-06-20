"""TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR preview CLI.

Stage 1 demo-only one-shot orchestrator runner. Default mode is
``readiness`` -- no network, no order. The
``execute_with_fake_sender`` mode is intentionally disabled from the
CLI surface in Stage 1 and refuses to run unless the explicit testing
flag ``--stage1-allow-fake-sender-execute-mode`` AND a callable
``--fake-sender-import-path`` are both supplied; even then, no real
order/network is sent because the fake sender is supplied by the
caller.

Instrument-rules discovery mode (``--ir-mode discover``) is disabled
by default. To enable the single bounded public GET to
``https://api-demo.bybit.com/v5/market/instruments-info`` pass:

    --i-understand-this-performs-one-public-read-only-instrument-rules-get

This flag only authorises the read-only instruments-info endpoint.
It never authorises ``/v5/order/create``, ``/v5/order/cancel``,
``/v5/position/set-trading-stop``, any live Bybit host, or any
WebSocket endpoint. No credentials are required or read for this
public GET. The CLI remains ``order_endpoint_called=False`` and
``order_sent=False`` in all cases.

Exit codes:
    0 -- ORCHESTRATION_OK_*
    1 -- any ORCHESTRATION_REJECTED_* (chain failed-closed) or
         --ir-mode discover used without the opt-in flag
    2 -- ORCHESTRATION_REJECTED_MISSING_CREDENTIALS or
         ORCHESTRATION_REJECTED_MISSING_FAKE_SENDER
"""

from __future__ import annotations

import argparse
import importlib
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


def _load_pre_parsed_response(path: str | None) -> dict | None:
    if not path:
        return None
    return json.loads(pathlib.Path(path).read_text(encoding="utf-8"))


def _resolve_callable(import_path: str | None):
    if not import_path:
        return None
    module_name, _, attr = import_path.partition(":")
    if not module_name or not attr:
        raise SystemExit(
            f"invalid --fake-sender-import-path {import_path!r}; "
            "expected 'module.path:callable_attr'"
        )
    module = importlib.import_module(module_name)
    fn = getattr(module, attr, None)
    if not callable(fn):
        raise SystemExit(
            f"resolved attribute {import_path!r} is not callable"
        )
    return fn


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description=(
            "TASK-014BM_ONE_SHOT_AUTHORIZED_EXECUTION_ORCHESTRATOR -- "
            "Stage 1 demo-only one-shot orchestration preview"
        )
    )
    parser.add_argument(
        "--mark-price",
        default="100",
        help="mark price used for candidate notional check (default: 100)",
    )
    parser.add_argument(
        "--mode",
        default="readiness",
        choices=["readiness", "execute_with_fake_sender"],
        help=(
            "orchestration mode (default: readiness, no network, no order). "
            "execute_with_fake_sender requires "
            "--stage1-allow-fake-sender-execute-mode AND a "
            "--fake-sender-import-path, AND a fake credential triple."
        ),
    )
    parser.add_argument(
        "--explicit-demo-min-qty-cap-authorization-flag",
        action="store_true",
        help="set the explicit cap-escalation authorization flag",
    )
    parser.add_argument(
        "--authorization-marker",
        default="",
        help=(
            "exact authorization marker string; pass "
            "DEMO_ONLY_SOLUSDT_EXCHANGE_MIN_QTY_CAP_ESCALATION_RICK_AUTHORIZED_v1 "
            "to authorize"
        ),
    )
    parser.add_argument(
        "--ir-mode",
        default="offline",
        choices=["offline", "discover"],
        help="instrument rules discovery mode (default: offline)",
    )
    parser.add_argument(
        "--ir-pre-parsed-response-json",
        default=None,
        help=(
            "path to a JSON file containing a cached "
            "/v5/market/instruments-info response (offline only)"
        ),
    )
    parser.add_argument(
        "--i-understand-this-performs-one-public-read-only-instrument-rules-get",
        dest="allow_real_ir_get",
        action="store_true",
        help=(
            "explicit opt-in for --ir-mode discover. Authorises one bounded "
            "public GET to "
            "https://api-demo.bybit.com/v5/market/instruments-info"
            "?category=linear&symbol=SOLUSDT. "
            "Never authorises /v5/order/create or any live host. "
            "No credentials required. order_endpoint_called and order_sent "
            "remain False in all cases."
        ),
    )
    parser.add_argument(
        "--stage1-allow-fake-sender-execute-mode",
        action="store_true",
        help=(
            "explicit testing-only opt-in to enable the "
            "execute_with_fake_sender mode in the CLI"
        ),
    )
    parser.add_argument(
        "--fake-sender-import-path",
        default=None,
        help=(
            "module:attr import path for a fake BM sender callable "
            "(only used by execute_with_fake_sender mode)"
        ),
    )
    parser.add_argument(
        "--fake-api-key",
        default="",
        help="fake demo api key (testing only; never used against live)",
    )
    parser.add_argument(
        "--fake-api-secret",
        default="",
        help="fake demo api secret (testing only; never used against live)",
    )
    parser.add_argument(
        "--fake-recv-window",
        default="5000",
        help="fake recv_window (testing only)",
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="write JSON + Markdown report to the orchestrator output dir",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="override the orchestrator output directory",
    )
    args = parser.parse_args(argv)

    from src import (
        demo_only_tiny_execution_adapter_tiny_order_execution as bm,
    )
    from src import (
        demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
    )
    from src import (
        demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as orc,
    )

    # CLI-level guard: --ir-mode discover is fail-closed by default.
    # Require the explicit opt-in flag or reject before any network call.
    if args.ir_mode == "discover" and not args.allow_real_ir_get:
        print(
            "REJECTED: --ir-mode discover requires the explicit opt-in flag\n"
            "  --i-understand-this-performs-one-public-read-only-instrument-rules-get\n"
            "Without it the CLI refuses to perform any public GET. "
            "Pass the flag to authorise one bounded GET to\n"
            "  https://api-demo.bybit.com/v5/market/instruments-info"
            "?category=linear&symbol=SOLUSDT\n"
            "No credentials are required. order_endpoint_called and "
            "order_sent remain False."
        )
        return 1

    # CLI-level Stage 1 safety: execute_with_fake_sender requires the
    # explicit testing flag AND a fake sender import path AND a fake
    # credential triple. Without all three the CLI refuses to run that
    # mode and prints a rejection report.
    if args.mode == "execute_with_fake_sender":
        if not args.stage1_allow_fake_sender_execute_mode:
            print(
                "REJECTED: execute_with_fake_sender mode is disabled by "
                "default in Stage 1. Pass "
                "--stage1-allow-fake-sender-execute-mode to opt in "
                "(testing only; never sends a real network call)."
            )
            return 2
        if not args.fake_sender_import_path:
            print(
                "REJECTED: --fake-sender-import-path is required for "
                "execute_with_fake_sender mode"
            )
            return 2
        if not args.fake_api_key or not args.fake_api_secret:
            print(
                "REJECTED: --fake-api-key and --fake-api-secret are "
                "required for execute_with_fake_sender mode"
            )
            return 2

    ir_pre_parsed = _load_pre_parsed_response(args.ir_pre_parsed_response_json)
    ir_mode = bm_ir.MODE_OFFLINE if args.ir_mode == "offline" else bm_ir.MODE_DISCOVER

    bm_fake_sender = _resolve_callable(args.fake_sender_import_path)
    bm_credentials = None
    if args.mode == "execute_with_fake_sender":
        bm_credentials = bm.DemoCredentials(
            api_key=args.fake_api_key,
            api_secret=args.fake_api_secret,
            recv_window=args.fake_recv_window,
        )

    orch_mode = (
        orc.ORCH_MODE_READINESS
        if args.mode == "readiness"
        else orc.ORCH_MODE_EXECUTE_WITH_FAKE_SENDER
    )

    report = orc.run_one_shot_authorized_execution_orchestration(
        mark_price=args.mark_price,
        mode=orch_mode,
        explicit_demo_min_qty_cap_authorization_flag=(
            args.explicit_demo_min_qty_cap_authorization_flag
        ),
        explicit_demo_min_qty_cap_authorization_marker=(
            args.authorization_marker
        ),
        ir_mode=ir_mode,
        ir_pre_parsed_response=ir_pre_parsed,
        bm_credentials=bm_credentials,
        bm_fake_sender=bm_fake_sender,
        allow_real_ir_get=bool(args.allow_real_ir_get),
    )

    # ------------- 12 required surfaces -----------------------------------
    print(
        f"task_id={report.task_id} identity={report.identity} "
        f"phase={report.phase}"
    )
    print(
        f"mode={report.mode} status={report.status} reason={report.reason!r}"
    )
    print(
        f"upstream_tasks={','.join(report.upstream_tasks)} "
        f"next_required_task={report.next_required_task} "
        f"is_review_chain_suffix={report.is_review_chain_suffix}"
    )
    # 1
    print(f"instrument_rules_loaded={report.instrument_rules_loaded}")
    # 2, 3
    print(
        f"candidate_qty={report.candidate_qty!r} "
        f"candidate_notional={report.candidate_notional!r}"
    )
    # 4
    print(f"cap_gate_status={report.cap_gate_status!r}")
    # 5
    print(f"wiring_status={report.wiring_status!r}")
    # 6
    print(f"original_packet_qty={report.original_packet_qty!r}")
    # 7
    print(f"actual_request_body_qty={report.actual_request_body_qty!r}")
    # 8
    print(
        f"actual_request_body_qty_source={report.actual_request_body_qty_source!r}"
    )
    # 9
    print(f"body_qty_authorized_override={report.body_qty_authorized_override}")
    # 10
    print(
        f"read_only_network_attempted={report.read_only_network_attempted}"
    )
    print(f"order_network_attempted={report.order_network_attempted}")
    print(f"network_attempted={report.network_attempted}")
    # 11
    print(f"order_endpoint_called={report.order_endpoint_called}")
    # 12
    print(f"order_sent={report.order_sent}")
    print(
        f"fake_sender_used={report.fake_sender_used} "
        f"sender_call_count={report.sender_call_count} "
        f"real_execute_disabled_stage1={report.real_execute_disabled_stage1}"
    )
    print(
        f"bm_invoked={report.bm_invoked} bm_mode={report.bm_mode!r} "
        f"bm_final_status={report.bm_final_status!r} "
        f"bybit_ret_code={report.bybit_ret_code} "
        f"bybit_order_id={report.bybit_order_id!r}"
    )
    if report.body_qty_rejection_reason:
        print(
            f"body_qty_rejection_reason={report.body_qty_rejection_reason!r}"
        )

    if args.write_report:
        paths = orc.write_report(report, output_dir=args.output_dir)
        print("wrote:")
        for key, path in paths.items():
            print(f"  {key}: {path}")

    status = report.status
    if status in (
        orc.STATUS_OK_READINESS_NO_NETWORK,
        orc.STATUS_OK_FAKE_SENDER_EXECUTED,
    ):
        return 0
    if status in (
        orc.STATUS_REJECTED_MISSING_CREDENTIALS,
        orc.STATUS_REJECTED_MISSING_FAKE_SENDER,
    ):
        return 2
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
