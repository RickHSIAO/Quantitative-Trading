"""Preview CLI for TASK-014BM_CAP_ESCALATION_GATE.

Decision-only preview that evaluates the demo-only SOLUSDT cap-escalation
authorization gate. No network, no order, no live endpoint, no
credentials.

Default mode: ``offline-default-reject``. Without any explicit
authorization flag the gate fails closed.

Exit code:
    * 0 when the gate produces a coherent decision (any of
      ``ESCALATION_NOT_REQUIRED``, ``ESCALATION_NOT_AUTHORIZED``,
      ``ESCALATION_AUTHORIZED``, or the documented fail-closed
      rejections that the authorized opt-in is supposed to trip).
    * 1 if the gate raises or produces an unrecognized status.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

# Make the project's ``src/`` importable when invoked as a script.
_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import (  # noqa: E402  -- path-injected import.
    demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as bm_ce,
)
from src import (  # noqa: E402
    demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
)


_OK_STATUSES = frozenset(
    {
        bm_ce.STATUS_ESCALATION_NOT_REQUIRED,
        bm_ce.STATUS_ESCALATION_NOT_AUTHORIZED,
        bm_ce.STATUS_ESCALATION_AUTHORIZED,
        bm_ce.STATUS_ESCALATION_REJECTED_NOTIONAL_OVER_CAP,
        bm_ce.STATUS_ESCALATION_REJECTED_RULES_NOT_LOADED,
    }
)


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Demo-only SOLUSDT cap-escalation authorization gate preview"
        )
    )
    p.add_argument(
        "--mark-price",
        type=str,
        default="100",
        help="Mark price used to compute candidate_notional (string).",
    )
    p.add_argument(
        "--ir-mode",
        choices=(bm_ir.MODE_OFFLINE, bm_ir.MODE_DISCOVER),
        default=bm_ir.MODE_OFFLINE,
        help="Instrument-rules discovery mode (default offline).",
    )
    p.add_argument(
        "--proposed-qty",
        type=str,
        default="",
        help=(
            "Proposed qty. Must exactly equal candidate_qty for "
            "authorization."
        ),
    )
    p.add_argument(
        "--max-demo-min-qty-notional-cap-usdt",
        type=str,
        default=str(bm_ce.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT),
        help="Notional ceiling for this escalation path (default 20 USDT).",
    )
    p.add_argument(
        bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME,
        dest="explicit_auth_flag",
        action="store_true",
        help=(
            "Rick's explicit authorization flag for the demo-only SOLUSDT "
            "exchange-minimum cap escalation."
        ),
    )
    p.add_argument(
        "--authorization-marker",
        type=str,
        default="",
        help=(
            "Required authorization marker string. Must equal "
            f"{bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER!r} to "
            "authorize."
        ),
    )
    p.add_argument(
        "--write-report",
        action="store_true",
        help="Write JSON+MD report to the default output directory.",
    )
    p.add_argument(
        "--output-dir",
        type=str,
        default="",
        help="Override output directory for --write-report.",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    ir_report = bm_ir.run_instrument_rules_discovery(
        mode=args.ir_mode,
        mark_price=args.mark_price,
    )

    request = bm_ce.EscalationAuthorizationRequest(
        proposed_qty=args.proposed_qty,
        explicit_demo_min_qty_cap_authorization_flag=bool(
            args.explicit_auth_flag
        ),
        explicit_demo_min_qty_cap_authorization_marker=(
            args.authorization_marker
        ),
    )

    try:
        report = bm_ce.run_cap_escalation_gate(
            instrument_rules_report=ir_report,
            request=request,
            max_demo_min_qty_notional_cap_usdt=Decimal(
                args.max_demo_min_qty_notional_cap_usdt
            ),
        )
    except Exception as exc:  # pragma: no cover - defensive
        print(f"cap escalation gate raised: {exc!r}")
        return 1

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))

    if args.write_report:
        out_dir = Path(args.output_dir) if args.output_dir else None
        paths = bm_ce.write_report(report, output_dir=out_dir)
        for key, path in paths.items():
            print(f"# wrote {key}: {path}")

    if report.decision.status in _OK_STATUSES:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
