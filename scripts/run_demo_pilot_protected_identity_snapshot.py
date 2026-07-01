"""TASK-014CA: capture the PRE_DAY1 protected-position identity snapshot for a NEW Demo Pilot.

ONE explicit read-only mode (``--capture-pre-day1-protected-snapshot``); nothing runs by default.
With ``--allow-real-network`` it issues Bybit Demo PRIVATE read-only GETs ONLY (fully paginated
position list + account-mode evidence) and seals the immutable protected-position identity BEFORE
any Day-1 order is authorized. It sends NO orders, cancels/amends/closes nothing, changes no
leverage/position mode, initializes no sender, calls no execution adapter, and advances no Pilot
state. Without ``--allow-real-network`` it touches no endpoint and fails closed. The output file is
written no-clobber (an existing destination is refused, never overwritten).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import demo_pilot_protected_identity_bootstrap as pib  # noqa: E402
from src.demo_readonly_client import DemoReadOnlyClient  # noqa: E402

POSITIONS_ENDPOINT = "/v5/position/list"

EXIT_READY = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-pre-day1-protected-snapshot", action="store_true")
    p.add_argument("--pilot-id")
    p.add_argument("--day1-date")
    p.add_argument("--artifact-output-json")
    p.add_argument("--allow-real-network", action="store_true")
    return p


def _emit(obj: dict, code: int) -> int:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return code


def _no_clobber_write(path: str, text: str) -> None:
    """Create-exclusive write: refuse to overwrite an existing destination."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def _collect_protected_snapshot(*, allow_real_network: bool):
    """Return (positions, provenance, counters, account_evidence). Read-only. Builds a real client
    ONLY under explicit --allow-real-network; otherwise touches no endpoint."""
    client = DemoReadOnlyClient(allow_real_network=True)
    positions, provenance = client.get_open_positions_paginated()
    account = client.build_runtime_proof()
    account_evidence = {
        "account_mode": getattr(account, "account_mode", None),
        "demo_flag": getattr(account, "demo_flag", None),
        "endpoint_family": getattr(account, "endpoint_family", None),
        "base_url_used": getattr(account, "base_url_used", None),
        "live_endpoint_fallback_detected": getattr(account, "live_endpoint_fallback_detected", None),
    }
    return positions, provenance, client.network_audit_counters(), account_evidence


def run_capture(args, *, snapshot_provider=None) -> int:
    missing = [f for f in ("pilot_id", "day1_date", "artifact_output_json")
               if not getattr(args, f, None)]
    if missing:
        return _emit({"verdict": pib.SNAPSHOT_BLOCKED, "mode": "CAPTURE_PRE_DAY1_PROTECTED_SNAPSHOT",
                      "blockers": [f"missing_required_argument:{m}" for m in missing]}, EXIT_INVALID)

    if os.path.exists(args.artifact_output_json):
        return _emit({"verdict": pib.SNAPSHOT_BLOCKED, "mode": "CAPTURE_PRE_DAY1_PROTECTED_SNAPSHOT",
                      "blockers": ["artifact_output_exists_refuse_overwrite"],
                      "artifact_path": args.artifact_output_json}, EXIT_INVALID)

    try:
        if snapshot_provider is not None:
            positions, provenance, counters, account_evidence = snapshot_provider()
        elif not args.allow_real_network:
            # No real-network authorization -> do NOT build any client / touch any endpoint.
            return _emit({"verdict": pib.SNAPSHOT_BLOCKED,
                          "mode": "CAPTURE_PRE_DAY1_PROTECTED_SNAPSHOT",
                          "blockers": ["protected_snapshot_network_not_authorized"]}, EXIT_BLOCKED)
        else:
            positions, provenance, counters, account_evidence = _collect_protected_snapshot(
                allow_real_network=True)
    except Exception as exc:  # noqa: BLE001 -- fail closed on any collector/pagination error
        return _emit({"verdict": pib.SNAPSHOT_BLOCKED, "mode": "CAPTURE_PRE_DAY1_PROTECTED_SNAPSHOT",
                      "blockers": [f"protected_snapshot_collection_failed:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    artifact = pib.build_pre_day1_protected_snapshot(
        pilot_id=args.pilot_id, day1_date=args.day1_date, positions=positions,
        positions_provenance=provenance,
        network_counter_components={"protected_position_collector": counters},
        account_evidence=account_evidence, source_endpoint=POSITIONS_ENDPOINT,
        generated_at=_utc_now_iso())

    try:
        _no_clobber_write(args.artifact_output_json,
                          json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    except FileExistsError:
        return _emit({"verdict": pib.SNAPSHOT_BLOCKED, "mode": "CAPTURE_PRE_DAY1_PROTECTED_SNAPSHOT",
                      "blockers": ["artifact_output_exists_refuse_overwrite"],
                      "artifact_path": args.artifact_output_json}, EXIT_INVALID)

    out = dict(artifact)
    out["artifact_path"] = args.artifact_output_json
    out["mode"] = "CAPTURE_PRE_DAY1_PROTECTED_SNAPSHOT"
    return _emit(out, EXIT_READY if artifact["verdict"] == pib.SNAPSHOT_READY else EXIT_BLOCKED)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.capture_pre_day1_protected_snapshot:
        return run_capture(args)
    return _emit({"blockers": ["no_mode_selected"]}, EXIT_INVALID)


if __name__ == "__main__":
    raise SystemExit(main())
