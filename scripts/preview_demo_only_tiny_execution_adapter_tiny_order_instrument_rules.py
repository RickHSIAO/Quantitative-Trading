"""TASK-014BM_MIN_QTY_FIX preview CLI -- demo-only SOLUSDT instrument rules.

Default mode is ``offline`` -- no network, no order, no secret read.
Optional ``--mode discover`` performs a single bounded GET to the locked
read-only endpoint
``https://api-demo.bybit.com/v5/market/instruments-info`` with
``category=linear&symbol=SOLUSDT``. No signing, no API key, no
recv-window. The CLI NEVER calls the order create endpoint and NEVER
reads any secret.

Exit codes:
    0 -- discovery_status is DISCOVERY_OK / DISCOVERY_OFFLINE_NO_NETWORK
         AND (candidate is None OR candidate.is_executable_under_tiny_caps
         OR candidate.status is TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN with
         confirms_qty_0_01_invalid=True -- this is the expected
         fail-closed reporting state)
    1 -- any other terminal discovery / candidate status
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
            "TASK-014BM_MIN_QTY_FIX -- demo-only SOLUSDT instrument rules "
            "discovery preview (NEVER calls order create endpoint)"
        )
    )
    parser.add_argument(
        "--mode",
        default="offline",
        choices=["offline", "discover"],
        help=(
            "discovery mode (default: offline, no network). "
            "'discover' performs ONE bounded GET to the locked "
            "read-only instruments-info endpoint."
        ),
    )
    parser.add_argument(
        "--mark-price",
        default=None,
        help=(
            "optional mark price (string Decimal) used to compute "
            "candidate notional against minNotionalValue"
        ),
    )
    parser.add_argument(
        "--write-report",
        action="store_true",
        help="write JSON + Markdown report to the BM_MIN_QTY_FIX output dir",
    )
    parser.add_argument(
        "--output-dir",
        default=None,
        help="override the output directory",
    )
    args = parser.parse_args(argv)

    from src import (
        demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
    )

    report = bm_ir.run_instrument_rules_discovery(
        mode=args.mode,
        mark_price=args.mark_price,
    )

    print(
        f"task_id={report.task_id} identity={report.identity} "
        f"phase={report.phase}"
    )
    print(
        f"mode={report.mode} discovery_status={report.discovery_status} "
        f"is_review_chain_suffix={report.is_review_chain_suffix}"
    )
    print(
        f"upstream_tasks={','.join(report.upstream_tasks)} "
        f"next_required_task={report.next_required_task}"
    )
    print(
        f"network_attempted={report.network_attempted} "
        f"order_endpoint_called={report.order_endpoint_called} "
        f"order_sent={report.order_sent}"
    )
    print(
        f"allowed_readonly_url={report.allowed_readonly_url} "
        f"allowed_category={report.allowed_category} "
        f"allowed_symbol={report.allowed_symbol}"
    )
    print(
        f"http_status={report.http_status} "
        f"bybit_ret_code={report.bybit_ret_code} "
        f"bybit_ret_msg={report.bybit_ret_msg!r}"
    )
    if report.rules is None:
        print("rules: <not loaded>")
    else:
        r = report.rules
        print(
            f"rules: symbol={r.symbol} status={r.status!r} "
            f"minOrderQty={r.min_order_qty} qtyStep={r.qty_step} "
            f"minNotionalValue={r.min_notional_value} "
            f"maxMktOrderQty={r.max_mkt_order_qty} "
            f"tickSize={r.tick_size}"
        )
    if report.candidate is None:
        print("candidate: <none>")
    else:
        c = report.candidate
        print(
            f"candidate: status={c.status} qty={c.candidate_qty} "
            f"notional={c.candidate_notional} "
            f"mark_price_used={c.mark_price_used} "
            f"aligns_to_qty_step={c.aligns_to_qty_step} "
            f"satisfies_min_order_qty={c.satisfies_min_order_qty} "
            f"satisfies_min_notional_value={c.satisfies_min_notional_value} "
            f"within_tiny_qty_cap={c.within_tiny_qty_cap} "
            f"within_tiny_size_cap={c.within_tiny_size_cap} "
            f"confirms_qty_0_01_invalid={c.confirms_qty_0_01_invalid} "
            f"is_executable_under_tiny_caps="
            f"{c.is_executable_under_tiny_caps}"
        )
        if c.reason:
            print(f"candidate_reason: {c.reason}")

    if args.write_report:
        paths = bm_ir.write_report(report, output_dir=args.output_dir)
        print("wrote:")
        for key, path in paths.items():
            print(f"  {key}: {path}")

    discovery_ok = report.discovery_status in (
        bm_ir.STATUS_DISCOVERY_OK,
        bm_ir.STATUS_DISCOVERY_OFFLINE_NO_NETWORK,
    )
    candidate_ok = report.candidate is None or (
        report.candidate.is_executable_under_tiny_caps
        or report.candidate.status
        == bm_ir.STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN
        or report.candidate.status
        == bm_ir.STATUS_CANDIDATE_RULES_NOT_LOADED
    )
    return 0 if (discovery_ok and candidate_ok) else 1


if __name__ == "__main__":
    raise SystemExit(main())
