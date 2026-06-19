"""Preview CLI for TASK-014BM_WIRE_AUTHORIZED_CANDIDATE_QTY.

Readiness / planning preview that evaluates the demo-only SOLUSDT
authorized execution qty wiring. No network, no order, no live endpoint,
no credentials, no order send.

Default mode: ``offline-default-reject``. Without an explicit
authorization flag the upstream cap-escalation gate fails closed, the
wiring rejects, and ``execution_qty`` stays empty.

Exit code:
    * 0 when the wiring produces a coherent decision (any of
      ``WIRING_AUTHORIZED_CANDIDATE_QTY``,
      ``WIRING_NOT_AUTHORIZED_NO_OVERRIDE``,
      ``WIRING_NOT_REQUIRED_ORIGINAL_PASSES``, or any of the documented
      fail-closed rejected statuses).
    * 1 if the wiring raises or produces an unrecognized status.
"""

from __future__ import annotations

import argparse
import json
import sys
from decimal import Decimal
from pathlib import Path

_ROOT = Path(__file__).resolve().parents[1]
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from src import (  # noqa: E402  -- path-injected import.
    demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring as bm_wire,
)
from src import (  # noqa: E402
    demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as bm_ce,
)
from src import (  # noqa: E402
    demo_only_tiny_execution_adapter_tiny_order_instrument_rules as bm_ir,
)


_OK_STATUSES = frozenset(
    {
        bm_wire.STATUS_WIRING_AUTHORIZED_CANDIDATE_QTY,
        bm_wire.STATUS_WIRING_NOT_REQUIRED_ORIGINAL_PASSES,
        bm_wire.STATUS_WIRING_NOT_AUTHORIZED_NO_OVERRIDE,
        bm_wire.STATUS_WIRING_REJECTED_RULES_NOT_LOADED,
        bm_wire.STATUS_WIRING_REJECTED_GATE_MISSING,
        bm_wire.STATUS_WIRING_REJECTED_GATE_OVER_CAP,
        bm_wire.STATUS_WIRING_REJECTED_WRONG_SYMBOL,
        bm_wire.STATUS_WIRING_REJECTED_WRONG_ENVIRONMENT,
        bm_wire.STATUS_WIRING_REJECTED_WRONG_SIDE,
        bm_wire.STATUS_WIRING_REJECTED_QTY_MISMATCH,
        bm_wire.STATUS_WIRING_REJECTED_PROTECTED_SYMBOL,
        bm_wire.STATUS_WIRING_REJECTED_CANDIDATE_INVALID,
    }
)


def _build_argparser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "Demo-only SOLUSDT authorized execution qty wiring preview"
        )
    )
    p.add_argument("--mark-price", type=str, default="100")
    p.add_argument(
        "--ir-mode",
        choices=(bm_ir.MODE_OFFLINE, bm_ir.MODE_DISCOVER),
        default=bm_ir.MODE_OFFLINE,
    )
    p.add_argument("--proposed-qty", type=str, default="0.1")
    p.add_argument(
        "--max-demo-min-qty-notional-cap-usdt",
        type=str,
        default=str(bm_ce.MAX_DEMO_MIN_QTY_NOTIONAL_CAP_USDT),
    )
    p.add_argument(
        bm_ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_FLAG_NAME,
        dest="explicit_auth_flag",
        action="store_true",
    )
    p.add_argument("--authorization-marker", type=str, default="")
    p.add_argument("--write-report", action="store_true")
    p.add_argument("--output-dir", type=str, default="")
    return p


def main(argv: list[str] | None = None) -> int:
    args = _build_argparser().parse_args(argv)

    ir_report = bm_ir.run_instrument_rules_discovery(
        mode=args.ir_mode, mark_price=args.mark_price
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
    gate_report = bm_ce.run_cap_escalation_gate(
        instrument_rules_report=ir_report,
        request=request,
        max_demo_min_qty_notional_cap_usdt=Decimal(
            args.max_demo_min_qty_notional_cap_usdt
        ),
    )

    try:
        report = bm_wire.run_authorized_execution_qty_wiring(
            instrument_rules_report=ir_report,
            cap_escalation_report=gate_report,
        )
    except Exception as exc:  # pragma: no cover - defensive
        print(f"authorized execution qty wiring raised: {exc!r}")
        return 1

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))

    if args.write_report:
        out_dir = Path(args.output_dir) if args.output_dir else None
        paths = bm_wire.write_report(report, output_dir=out_dir)
        for key, path in paths.items():
            print(f"# wrote {key}: {path}")

    if report.resolution.status in _OK_STATUSES:
        return 0
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
