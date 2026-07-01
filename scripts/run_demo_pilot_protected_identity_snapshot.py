"""TASK-014CA: read-only operational chain for a NEW Demo Pilot's protected-position identity.

Three mutually-exclusive, explicit modes (nothing runs by default):

  1. --capture-pre-day1-protected-snapshot   (real read needs --allow-real-network)
       seal the PRE_DAY1 protected-position identity from a COMPLETE Demo private read-only
       paginated position read + account/runtime evidence.
  2. --build-day1-protected-binding          (fully offline; no key, no endpoint)
       validate a FORMAL Day-1 allocation artifact and bind it to a sealed snapshot.
  3. --verify-post-fill-protected-continuity  (real read needs --allow-real-network)
       re-read positions and prove EXACT protected identity continuity.

Every mode sends NO orders, cancels/amends/closes nothing, changes no leverage/position mode,
initializes no sender, calls no execution adapter, and advances no Pilot. Output is written
create-exclusive (an existing destination is refused, never overwritten).
"""
from __future__ import annotations

import argparse
import hashlib
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

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3

_MODES = ("capture_pre_day1_protected_snapshot", "build_day1_protected_binding",
          "verify_post_fill_protected_continuity")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--capture-pre-day1-protected-snapshot", action="store_true")
    p.add_argument("--build-day1-protected-binding", action="store_true")
    p.add_argument("--verify-post-fill-protected-continuity", action="store_true")
    p.add_argument("--pilot-id")
    p.add_argument("--day1-date")
    p.add_argument("--protected-snapshot-json")
    p.add_argument("--protected-binding-json")
    p.add_argument("--day1-allocation-intent-json")
    p.add_argument("--artifact-output-json")
    p.add_argument("--allow-real-network", action="store_true")
    return p


def _emit(obj: dict, code: int) -> int:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return code


def _read_json(path: str):
    with open(path, "r", encoding="utf-8") as fh:
        return json.load(fh)


def _sha256_file(path: str) -> str:
    h = hashlib.sha256()
    with open(path, "rb") as fh:
        for chunk in iter(lambda: fh.read(65536), b""):
            h.update(chunk)
    return "sha256:" + h.hexdigest()


def _no_clobber_write(path: str, text: str) -> None:
    """Create-exclusive write: refuse to overwrite an existing destination."""
    parent = os.path.dirname(os.path.abspath(path))
    if parent and not os.path.isdir(parent):
        os.makedirs(parent, exist_ok=True)
    fd = os.open(path, os.O_CREAT | os.O_EXCL | os.O_WRONLY, 0o644)
    with os.fdopen(fd, "w", encoding="utf-8") as fh:
        fh.write(text)


def _require(args, mode, fields):
    missing = [f for f in fields if not getattr(args, f, None)]
    if missing:
        return [f"missing_required_argument:{m}" for m in missing]
    return []


def _publish(mode, artifact, args, *, ok):
    try:
        _no_clobber_write(args.artifact_output_json,
                          json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    except FileExistsError:
        return _emit({"mode": mode, "blockers": ["artifact_output_exists_refuse_overwrite"],
                      "artifact_path": args.artifact_output_json}, EXIT_INVALID)
    out = dict(artifact)
    out["artifact_path"] = args.artifact_output_json
    out["mode"] = mode
    return _emit(out, EXIT_OK if ok else EXIT_BLOCKED)


def _collect_positions_read():
    """Real Demo private read-only paginated positions + account/runtime evidence. Builds a real
    client ONLY under an already-checked --allow-real-network authorization."""
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


# ------------------------------------------------------------------ mode 1: snapshot
def run_capture(args, *, snapshot_provider=None) -> int:
    mode = "CAPTURE_PRE_DAY1_PROTECTED_SNAPSHOT"
    miss = _require(args, mode, ("pilot_id", "day1_date", "artifact_output_json"))
    if miss:
        return _emit({"mode": mode, "blockers": miss}, EXIT_INVALID)
    if os.path.exists(args.artifact_output_json):
        return _emit({"mode": mode, "blockers": ["artifact_output_exists_refuse_overwrite"],
                      "artifact_path": args.artifact_output_json}, EXIT_INVALID)
    try:
        if snapshot_provider is not None:
            positions, provenance, counters, account_evidence = snapshot_provider()
        elif not args.allow_real_network:
            return _emit({"mode": mode, "blockers": ["protected_snapshot_network_not_authorized"]},
                         EXIT_BLOCKED)
        else:
            positions, provenance, counters, account_evidence = _collect_positions_read()
    except Exception as exc:  # noqa: BLE001 -- fail closed on any collector/pagination error
        return _emit({"mode": mode, "blockers": [f"protected_snapshot_collection_failed:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    artifact = pib.build_pre_day1_protected_snapshot(
        pilot_id=args.pilot_id, day1_date=args.day1_date, positions=positions,
        positions_provenance=provenance,
        network_counter_components={"protected_position_collector": counters},
        account_evidence=account_evidence, source_endpoint=POSITIONS_ENDPOINT,
        generated_at=_utc_now_iso())
    return _publish(mode, artifact, args, ok=artifact["bootstrap_ready"])


# ------------------------------------------------------------------ mode 2: binding (offline)
def run_build_binding(args) -> int:
    mode = "BUILD_DAY1_PROTECTED_BINDING"
    miss = _require(args, mode, ("pilot_id", "day1_date", "protected_snapshot_json",
                                 "day1_allocation_intent_json", "artifact_output_json"))
    if miss:
        return _emit({"mode": mode, "blockers": miss}, EXIT_INVALID)
    if os.path.exists(args.artifact_output_json):
        return _emit({"mode": mode, "blockers": ["artifact_output_exists_refuse_overwrite"],
                      "artifact_path": args.artifact_output_json}, EXIT_INVALID)
    try:
        snapshot = _read_json(args.protected_snapshot_json)
        allocation = _read_json(args.day1_allocation_intent_json)
        alloc_sha = _sha256_file(args.day1_allocation_intent_json)
    except (OSError, ValueError) as exc:
        return _emit({"mode": mode, "blockers": [f"input_unreadable:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    artifact = pib.build_day1_protected_binding(
        pilot_id=args.pilot_id, day1_date=args.day1_date, day1_allocation_artifact=allocation,
        snapshot_artifact=snapshot, allocation_source_path=args.day1_allocation_intent_json,
        allocation_source_sha256=alloc_sha)
    return _publish(mode, artifact, args, ok=artifact["execution_ready"])


# ------------------------------------------------------------------ mode 3: continuity
def run_verify_continuity(args, *, positions_provider=None) -> int:
    mode = "VERIFY_POST_FILL_PROTECTED_CONTINUITY"
    miss = _require(args, mode, ("pilot_id", "day1_date", "protected_snapshot_json",
                                 "protected_binding_json", "day1_allocation_intent_json",
                                 "artifact_output_json"))
    if miss:
        return _emit({"mode": mode, "blockers": miss}, EXIT_INVALID)
    if os.path.exists(args.artifact_output_json):
        return _emit({"mode": mode, "blockers": ["artifact_output_exists_refuse_overwrite"],
                      "artifact_path": args.artifact_output_json}, EXIT_INVALID)
    try:
        snapshot = _read_json(args.protected_snapshot_json)
        binding = _read_json(args.protected_binding_json)
        allocation = _read_json(args.day1_allocation_intent_json)
        alloc_sha = _sha256_file(args.day1_allocation_intent_json)
    except (OSError, ValueError) as exc:
        return _emit({"mode": mode, "blockers": [f"input_unreadable:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    # Validate the FORMAL allocation artifact BEFORE any network read: recompute its fingerprint,
    # exact-match the binding's bound allocation fingerprint + file SHA256, and only then take the
    # strategy allowlist from the VALIDATED payloads. On failure NO client is built / no read occurs.
    alloc_ok, alloc_reasons, alloc_fp = pib.validate_day1_allocation_artifact(
        allocation, pilot_id=args.pilot_id, day1_date=args.day1_date)
    pre: list[str] = list(alloc_reasons)
    if alloc_ok and alloc_fp != str((binding or {}).get("allocation_intent_fingerprint", "")):
        pre.append("continuity_binding_allocation_fingerprint_mismatch")
    if alloc_sha != str((binding or {}).get("allocation_artifact_source_sha256", "")):
        pre.append("continuity_allocation_source_sha256_mismatch")
    if pre:
        return _emit({"mode": mode, "blockers": sorted(set(pre)),
                      "allocation_intent_fingerprint": alloc_fp}, EXIT_BLOCKED)

    strategy_symbols = [str(p.get("symbol", "")) for p in (allocation.get("order_payloads") or [])
                        if isinstance(p, dict)]
    try:
        if positions_provider is not None:
            positions, provenance, counters = positions_provider()
        elif not args.allow_real_network:
            return _emit({"mode": mode, "blockers": ["post_fill_positions_network_not_authorized"]},
                         EXIT_BLOCKED)
        else:
            positions, provenance, counters, _acct = _collect_positions_read()
    except Exception as exc:  # noqa: BLE001
        return _emit({"mode": mode, "blockers": [f"post_fill_collection_failed:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    artifact = pib.verify_post_fill_protected_continuity(
        pilot_id=args.pilot_id, day1_date=args.day1_date, snapshot_artifact=snapshot,
        binding_artifact=binding, post_fill_positions=positions, post_fill_provenance=provenance,
        network_counter_components={"post_fill_position_collector": counters},
        strategy_symbols=strategy_symbols, allocation_intent_fingerprint=alloc_fp,
        allocation_artifact_source_sha256=alloc_sha, generated_at=_utc_now_iso())
    return _publish(mode, artifact, args, ok=artifact["continuity_pass"])


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    selected = [m for m in _MODES if getattr(args, m)]
    if len(selected) > 1:
        return _emit({"blockers": [f"mutually_exclusive_modes:{selected}"]}, EXIT_INVALID)
    if not selected:
        return _emit({"blockers": ["no_mode_selected"]}, EXIT_INVALID)
    if selected[0] == "capture_pre_day1_protected_snapshot":
        return run_capture(args)
    if selected[0] == "build_day1_protected_binding":
        return run_build_binding(args)
    return run_verify_continuity(args)


if __name__ == "__main__":
    raise SystemExit(main())
