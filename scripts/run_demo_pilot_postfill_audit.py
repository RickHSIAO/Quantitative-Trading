#!/usr/bin/env python3
"""TASK: READ-ONLY post-fill audit of a dispatched Strategy-native Demo batch, and a SEPARATE
explicit gate to advance the Pilot only after that audit PASSES.

Two mutually-exclusive, explicitly-selected modes (neither runs by default):

  --run-postfill-audit
      Stage 1 (read-only). Loads the durable batch artifacts, fetches COMPLETELY-paginated Demo
      positions via the shared read-only client, evaluates every post-fill condition, and writes a
      machine-readable audit artifact. Never sends/cancels/closes an order, never mutates a
      position, never advances the Pilot. With --allow-real-network it issues Bybit Demo PRIVATE
      read-only GETs only; without it, it stays offline (and cannot produce a real PASS).

  --advance-after-audit
      Stage 2. Reads a COMPLETED audit artifact and, only if it is a genuine POST_FILL_AUDIT_PASS
      bound to this exact pilot/date/fingerprint, advances the successful-day counter through the
      existing idempotent advancement path. Never touches the network, an order sender, or the
      Pilot JSON directly.

This runner deliberately does NOT auto-chain the two stages.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import os
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import demo_strategy_native_current_feasibility as cf  # noqa: E402
from src import demo_strategy_native_postfill_audit as au  # noqa: E402
from src import demo_strategy_pilot_native_execution as nx  # noqa: E402
from src.demo_readonly_client import DemoReadOnlyClient  # noqa: E402

PROTECTED_SYMBOLS_SOURCE = (
    "src.demo_strategy_native_current_feasibility._HISTORICAL_PROTECTED_SYMBOLS")
AUDIT_ARTIFACT_FILENAME = "post_fill_audit.json"

EXIT_PASS = 0
EXIT_FAIL = 1
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _load_runner_module():
    """Import the canonical execution runner (a script) to reuse its EXACT allocation-intent
    fingerprint recompute / artifact verification (no duplicated fingerprint logic)."""
    path = os.path.join(_HERE, "run_demo_strategy_pilot_native_daily.py")
    spec = importlib.util.spec_from_file_location("_crun_postfill", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _read_json(path: str):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _read_jsonl(path: str) -> list[dict]:
    out: list[dict] = []
    if not path or not os.path.isfile(path):
        return out
    with open(path, encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line:
                out.append(json.loads(line))
    return out


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    mode = p.add_mutually_exclusive_group(required=True)
    mode.add_argument("--run-postfill-audit", action="store_true")
    mode.add_argument("--advance-after-audit", action="store_true")

    p.add_argument("--pilot-id", required=True)
    p.add_argument("--date", required=True)
    p.add_argument("--allocation-intent-fingerprint", required=True)
    p.add_argument("--output-root", dest="output_root", default=None)
    p.add_argument("--allow-real-network", action="store_true")

    # Stage 1 inputs (durable artifacts).
    p.add_argument("--allocation-intent-json", default=None)
    p.add_argument("--execution-summary-json", default=None)
    p.add_argument("--execution-state-json", default=None)
    p.add_argument("--execution-journal-jsonl", default=None)
    p.add_argument("--sent-ledger-jsonl", default=None)
    p.add_argument("--batch-attempt-json", default=None)
    p.add_argument("--audit-output-json", default=None)

    # Stage 2 input.
    p.add_argument("--audit-artifact-json", default=None)
    return p


def _emit(obj: dict, code: int) -> int:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return code


def _audit_output_path(args) -> str:
    if args.audit_output_json:
        return args.audit_output_json
    store = nx.NativeExecutionStore(args.pilot_id, args.date, args.output_root)
    return str(store.dir / AUDIT_ARTIFACT_FILENAME)


def run_postfill_audit(args, *, position_provider=None) -> int:
    """Stage 1: produce the read-only post-fill audit artifact. ``position_provider`` is an
    injection seam for tests: a callable returning (positions, provenance, network_counters)."""
    required = {
        "--allocation-intent-json": args.allocation_intent_json,
        "--execution-summary-json": args.execution_summary_json,
        "--execution-state-json": args.execution_state_json,
        "--batch-attempt-json": args.batch_attempt_json,
    }
    missing = [flag for flag, val in required.items() if not val]
    if missing:
        return _emit({"verdict": au.POST_FILL_AUDIT_FAIL, "mode": "RUN_POSTFILL_AUDIT",
                      "blockers": [f"missing_input:{m}" for m in missing]}, EXIT_INVALID)
    try:
        intent = _read_json(args.allocation_intent_json)
        summary = _read_json(args.execution_summary_json)
        state = _read_json(args.execution_state_json)
        battempt = _read_json(args.batch_attempt_json)
        journal = _read_jsonl(args.execution_journal_jsonl)
        ledger = _read_jsonl(args.sent_ledger_jsonl)
    except (OSError, ValueError) as exc:
        return _emit({"verdict": au.POST_FILL_AUDIT_FAIL, "mode": "RUN_POSTFILL_AUDIT",
                      "blockers": [f"input_unreadable:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    # Reuse the runner's EXACT immutable-intent verification (recomputes the price-independent
    # allocation-intent fingerprint from the artifact's own fields -> tamper detection).
    crun = _load_runner_module()
    token = str(intent.get("expected_batch_authorization_token", ""))
    ok, _bl, recomputed_fp, _allocs, _cap = crun.verify_immutable_prepared_artifact(
        intent, pilot_id=args.pilot_id, date=args.date, token=token)

    # Completely-paginated, read-only position evidence (fail-closed on any incomplete page).
    try:
        if position_provider is not None:
            positions, provenance, counters = position_provider()
        else:
            client = DemoReadOnlyClient(allow_real_network=args.allow_real_network)
            positions, provenance = client.get_open_positions_paginated()
            counters = client.network_audit_counters()
    except Exception as exc:  # noqa: BLE001 -- fail closed on any collector/pagination error
        return _emit({"verdict": au.POST_FILL_AUDIT_FAIL, "mode": "RUN_POSTFILL_AUDIT",
                      "blockers": [f"position_collection_failed:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    artifact = au.evaluate_post_fill_audit(
        pilot_id=args.pilot_id, date=args.date,
        expected_fingerprint=args.allocation_intent_fingerprint,
        allocation_intent_artifact=intent, execution_summary=summary, execution_state=state,
        journal=journal, sent_ledger=ledger, batch_attempt=battempt,
        positions=positions, positions_provenance=provenance,
        protected_symbols=sorted(cf._HISTORICAL_PROTECTED_SYMBOLS),
        protected_symbols_source=PROTECTED_SYMBOLS_SOURCE,
        network_counters=counters,
        intent_recomputed_fingerprint=recomputed_fp, intent_structurally_valid=ok,
        source_paths={
            "allocation_intent_json": args.allocation_intent_json,
            "execution_summary_json": args.execution_summary_json,
            "execution_state_json": args.execution_state_json,
            "execution_journal_jsonl": args.execution_journal_jsonl,
            "sent_ledger_jsonl": args.sent_ledger_jsonl,
            "batch_attempt_json": args.batch_attempt_json,
        },
        generated_at=_utc_now_iso())

    out_path = _audit_output_path(args)
    store = nx.NativeExecutionStore(args.pilot_id, args.date, args.output_root)
    import pathlib
    store._atomic_write(pathlib.Path(out_path),
                        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    artifact_out = dict(artifact)
    artifact_out["audit_artifact_path"] = out_path
    artifact_out["mode"] = "RUN_POSTFILL_AUDIT"
    return _emit(artifact_out,
                 EXIT_PASS if artifact["verdict"] == au.POST_FILL_AUDIT_PASS else EXIT_FAIL)


def advance_after_audit(args, *, advance_fn=None) -> int:
    """Stage 2: advance the Pilot ONLY if a completed PASS audit binds this batch identity."""
    audit_path = args.audit_artifact_json or _audit_output_path(args)
    try:
        audit_artifact = _read_json(audit_path)
    except (OSError, ValueError) as exc:
        return _emit({"status": au.ADVANCE_REFUSED, "mode": "ADVANCE_AFTER_AUDIT",
                      "advanced": False,
                      "refusal_reasons": [f"audit_artifact_unreadable:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    result = au.gate_and_advance_pilot(
        audit_artifact=audit_artifact, pilot_id=args.pilot_id, date=args.date,
        expected_fingerprint=args.allocation_intent_fingerprint,
        output_root=args.output_root, advance_fn=advance_fn)
    result["mode"] = "ADVANCE_AFTER_AUDIT"
    # An already-counted date is a successful idempotent no-op (still EXIT_PASS); only a genuine
    # refusal (validation failure / Pilot would not advance) is EXIT_FAIL.
    return _emit(result, EXIT_FAIL if result.get("refused") else EXIT_PASS)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.run_postfill_audit:
        return run_postfill_audit(args)
    if args.advance_after_audit:
        return advance_after_audit(args)
    return _emit({"blockers": ["no_mode_selected"]}, EXIT_INVALID)


if __name__ == "__main__":
    raise SystemExit(main())
