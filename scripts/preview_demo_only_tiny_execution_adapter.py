"""TASK-014BH preview CLI — demo-only tiny execution adapter
implementation-path scaffold.

Prints the implementation-path identity, builds a sample SOLUSDT tiny
entry payload offline, and reports it as JSON. This script is pure:
no network, no exchange call, no secret read.

Exit codes:
    0 — payload built successfully (still NOT sent)
    1 — any guard rejected the payload
"""

from __future__ import annotations

import argparse
import json
import os
import pathlib
import sys
from decimal import Decimal

os.environ.setdefault("COLUMNS", "400")
try:
    sys.stdout.reconfigure(encoding="utf-8")  # type: ignore[attr-defined]
except Exception:  # pragma: no cover
    pass

ROOT = pathlib.Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_only_tiny_execution_adapter as bh  # noqa: E402


def _build_arg_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        description=(
            "TASK-014BH demo-only tiny execution adapter implementation-path "
            "scaffold preview (offline; does NOT send)."
        ),
    )
    p.add_argument("--symbol", default="SOLUSDT")
    p.add_argument("--side", default="Buy", choices=sorted(bh.ALLOWED_SIDES))
    p.add_argument("--qty", default="0.01")
    p.add_argument("--mark-price", default=None)
    p.add_argument(
        "--existing-positions",
        nargs="*",
        default=(),
        help="Existing-position symbols (offline scope check).",
    )
    p.add_argument(
        "--order-link-id",
        default=None,
        help="Custom order link id (must start with DEMO_ONLY_TINY_BH_).",
    )
    return p


def main(argv: list[str] | None = None) -> int:
    parser = _build_arg_parser()
    args = parser.parse_args(argv)

    print(
        "TASK-014BH demo-only tiny execution adapter implementation-path "
        "scaffold preview"
    )
    print(
        "next_required_task = "
        f"{bh.NEXT_REQUIRED_TASK} (this is the implementation path; NOT a "
        "review-chain suffix)"
    )
    print("identity:")
    print(json.dumps(bh.describe_implementation_path(), indent=2, sort_keys=True))

    try:
        payload = bh.build_demo_only_tiny_solusdt_entry_payload(
            symbol=args.symbol,
            side=args.side,
            qty=args.qty,
            mark_price=args.mark_price if args.mark_price else None,
            existing_positions=tuple(args.existing_positions),
            order_link_id=args.order_link_id,
        )
    except bh.DemoOnlyTinyExecutionAdapterError as exc:
        print(f"REJECTED: {exc}")
        return 1

    print("offline-built payload (NOT sent):")
    print(json.dumps(payload.to_audit_dict(), indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
