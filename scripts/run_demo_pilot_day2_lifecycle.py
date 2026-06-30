#!/usr/bin/env python3
"""TASK-014BY: READ-ONLY Day-2 strategy-position lifecycle reconciliation + dry-run plan runner.

ONE explicit mode (``--day2-lifecycle-dry-run``; nothing runs by default). It collects the
COMPLETELY-paginated Demo positions via the shared read-only client, re-derives the Day-2 target
from the FORMAL Forward per-date call chain (``load_primary_forward_strategy_result`` ->
``plan_strategy_native_actions``), exact-matches the supplied sealed target artifact against that
production recompute, re-validates the MANDATORY Day-1 evidence, and writes a machine-readable
dry-run plan.

It NEVER sends/closes/cancels/amends an order, never resizes a position, never advances the Pilot,
never writes a batch_attempt, never initializes a sender, and never calls execute_daily_native.
With --allow-real-network it issues Bybit Demo PRIVATE read-only GETs only.

PRODUCTION READY requires genuine provenance: if the Forward per-date source for ``lifecycle_date``
does not exist / is stale / fails validation, the formal chain fails closed and the plan is
DAY2_LIFECYCLE_DRY_RUN_BLOCKED. A hand-built / self-sealed target cannot produce READY because the
authoritative target is the production recompute, not the supplied artifact.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import os
import pathlib
import sys
from datetime import datetime, timezone

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(_HERE)
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import demo_strategy_native_day2_lifecycle as d2  # noqa: E402
from src import demo_strategy_pilot_action_planner as planner  # noqa: E402
from src import demo_strategy_pilot_forward_source as fs  # noqa: E402
from src import demo_strategy_pilot_native_execution as nx  # noqa: E402
from src.demo_readonly_client import DemoReadOnlyClient  # noqa: E402

PROTECTED_SOURCE = "src.demo_strategy_pilot_native_execution.PROTECTED_SYMBOLS"
ARTIFACT_FILENAME = "day2_lifecycle_dry_run.json"

EXIT_READY = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--day2-lifecycle-dry-run", action="store_true", required=True)
    p.add_argument("--pilot-id", required=True)
    p.add_argument("--lifecycle-date", required=True)
    p.add_argument("--day1-date", required=True)
    p.add_argument("--day1-fingerprint", required=True)
    p.add_argument("--lifecycle-policy", required=True)
    p.add_argument("--output-root", dest="output_root", default=None)
    p.add_argument("--forward-source-root", dest="forward_source_root", default=None)
    p.add_argument("--allow-real-network", action="store_true")
    # Mandatory formal evidence (absent / unvalidated => fail closed; never guessed).
    p.add_argument("--day1-post-fill-audit-json", required=True)
    p.add_argument("--day1-allocation-intent-json", required=True)
    p.add_argument("--target-intent-artifact-json", required=True,
                   help="sealed Day-2 target; ACCEPTED only if it exact-matches the production recompute")
    p.add_argument("--artifact-output-json", default=None)
    return p


def _read_json(path):
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _sha256_file(path: pathlib.Path) -> str:
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _load_daily_runner():
    """Lazily import the canonical daily runner to reuse its EXACT production provider builder."""
    spec = importlib.util.spec_from_file_location(
        "_crun_day2_provider", os.path.join(_HERE, "run_demo_strategy_pilot_native_daily.py"))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def _hash_source_artifacts(args) -> dict:
    """Hash EXACTLY the four canonical Forward source-artifact roles for ``lifecycle_date``. Each
    file must still exist and be a regular file at hash time; a missing role fails closed."""
    root = pathlib.Path(args.forward_source_root) if args.forward_source_root \
        else pathlib.Path(_ROOT) / "outputs" / "forward_record"
    primary = root / fs.PRIMARY_RUN_KEY
    compact = str(args.lifecycle_date).replace("-", "")
    role_files = {
        "positions": primary / f"{compact}_positions.parquet",
        "forward_stats": primary / f"{compact}_forward_stats.json",
        "pnl": primary / f"{compact}_pnl.json",
        "forward_summary": primary / "forward_summary.json"}
    source_artifacts = {}
    for role, fp in role_files.items():
        if not fp.is_file():
            raise fs.ForwardSourceError(f"forward_source_artifact_missing:{role}:{fp}")
        source_artifacts[role] = {"path": str(fp), "sha256": _sha256_file(fp)}
    return source_artifacts


def resolve_production_forward_target(args, *, provider=None) -> dict:
    """Re-derive the Day-2 target from the FORMAL Forward per-date call chain. Raises
    fs.ForwardSourceError (fail closed) on missing/stale/invalid source, unverified planner, an
    unauthorized real-network run, or a provider that cannot report complete transport counters.

    Real network is used ONLY under explicit --allow-real-network: when no provider is injected
    and the flag is absent, this returns/raises BEFORE building any real-network client/guard.
    Provenance evidence is the formal loader's own validation (``loader_validation = PASS``) plus
    the four source-artifact SHA-256; there is no resolver-fabricated runner_status/safety_scan."""
    if provider is None and not getattr(args, "allow_real_network", False):
        raise fs.ForwardSourceError("production_recompute_network_not_authorized")
    forward_result = fs.load_primary_forward_strategy_result(
        run_date=args.lifecycle_date, repo_root=_ROOT,
        forward_source_root=args.forward_source_root)
    if provider is None:
        # Build the production provider ONLY now, with real network explicitly authorized.
        provider = _load_daily_runner()._build_production_provider()
    if provider is None:
        raise fs.ForwardSourceError("production_provider_unavailable")
    plan = planner.plan_strategy_native_actions(forward_result=forward_result, provider=provider)
    if not getattr(plan, "available", False) or not plan.sizing_verification.get("verified", False):
        raise fs.ForwardSourceError(f"production planner unavailable/unverified: {plan.status}")
    allocations = []
    for tp in plan.targets:
        allocations.append({
            "symbol": str(tp.get("symbol", "")).strip().upper(),
            "side": tp.get("side"),
            "target_notional_usd": tp.get("target_notional", tp.get("target_notional_usd")),
            "qty": tp.get("qty"), "qty_step": tp.get("qty_step")})
    # Every provider network request (wallet / positions / market / instrument) must be counted.
    counters_fn = getattr(provider, "network_audit_counters", None)
    provider_counters = counters_fn() if callable(counters_fn) else None
    return {
        "strategy": forward_result.strategy_name,
        "requested_run_date": forward_result.requested_run_date,
        "signal_date": forward_result.market_data_date,
        "loader_validation": "PASS",
        "source_artifacts": _hash_source_artifacts(args),
        "network_audit_counters": provider_counters,
        "provider_snapshot_evidence": {
            "read_only_provider": True,
            "target_symbol_count": len(allocations),
            "evidence": ["wallet_balance", "open_positions", "market_price", "instrument_rule"]},
        "allocations": allocations}


def _emit(obj: dict, code: int) -> int:
    print(json.dumps(obj, ensure_ascii=False, sort_keys=True))
    return code


def _artifact_path(args) -> str:
    if args.artifact_output_json:
        return args.artifact_output_json
    store = nx.NativeExecutionStore(args.pilot_id, args.lifecycle_date, args.output_root)
    return str(store.dir / ARTIFACT_FILENAME)


def run_day2_lifecycle_dry_run(args, *, position_provider=None, forward_target_resolver=None) -> int:
    try:
        day1_audit = _read_json(args.day1_post_fill_audit_json)
        day1_alloc = _read_json(args.day1_allocation_intent_json)
        sealed_target = _read_json(args.target_intent_artifact_json)
    except (OSError, ValueError) as exc:
        return _emit({"verdict": d2.DRY_RUN_BLOCKED, "mode": "DAY2_LIFECYCLE_DRY_RUN",
                      "blockers": [f"input_unreadable:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    # Authoritative target = formal production recompute (fail closed if the source is absent).
    resolver = forward_target_resolver or (lambda: resolve_production_forward_target(args))
    try:
        production_recompute = resolver()
    except Exception as exc:  # noqa: BLE001 -- ForwardSourceError / missing per-date source -> BLOCKED
        production_recompute = None
        forward_block = f"production_forward_source_unavailable:{type(exc).__name__}"
    else:
        forward_block = None

    collector_blocked = None
    try:
        if position_provider is not None:
            positions, provenance, collector_counters = position_provider()
        elif not args.allow_real_network:
            # No real-network authorization -> do NOT build any client / touch any endpoint.
            positions, collector_counters = [], None
            provenance = {"termination_reason": "network_not_authorized", "page_count": 0}
            collector_blocked = "current_position_collection_network_not_authorized"
        else:
            client = DemoReadOnlyClient(allow_real_network=True)
            positions, provenance = client.get_open_positions_paginated()
            collector_counters = client.network_audit_counters()
    except Exception as exc:  # noqa: BLE001 -- fail closed on any collector/pagination error
        return _emit({"verdict": d2.DRY_RUN_BLOCKED, "mode": "DAY2_LIFECYCLE_DRY_RUN",
                      "blockers": [f"position_collection_failed:{type(exc).__name__}"],
                      "detail": str(exc)}, EXIT_INPUT_FAILURE)

    # Single, complete transport audit: BOTH the production provider's requests and the
    # current-position collector's requests must be accounted for (a missing component -> BLOCKED).
    network_counter_components = {
        "production_forward_provider": (production_recompute or {}).get("network_audit_counters"),
        "current_position_collector": collector_counters}

    artifact = d2.build_day2_lifecycle_dry_run(
        pilot_id=args.pilot_id, lifecycle_date=args.lifecycle_date, day1_date=args.day1_date,
        day1_fingerprint=args.day1_fingerprint, lifecycle_policy=args.lifecycle_policy,
        day1_post_fill_audit=day1_audit, day1_allocation_intent=day1_alloc,
        sealed_target=sealed_target,
        production_target_recompute=production_recompute, current_positions=positions,
        positions_provenance=provenance, network_counter_components=network_counter_components,
        protected_symbols=sorted(nx.PROTECTED_SYMBOLS), protected_symbols_source=PROTECTED_SOURCE,
        source_paths={"day1_post_fill_audit_json": args.day1_post_fill_audit_json,
                      "day1_allocation_intent_json": args.day1_allocation_intent_json,
                      "target_intent_artifact_json": args.target_intent_artifact_json},
        generated_at=_utc_now_iso())
    for extra_block in (forward_block, collector_blocked):
        if extra_block and extra_block not in artifact["blockers"]:
            artifact["blockers"].append(extra_block)
            artifact["verdict"] = d2.DRY_RUN_BLOCKED

    out_path = _artifact_path(args)
    store = nx.NativeExecutionStore(args.pilot_id, args.lifecycle_date, args.output_root)
    store._atomic_write(pathlib.Path(out_path),
                        json.dumps(artifact, ensure_ascii=False, indent=2, sort_keys=True))
    out = dict(artifact)
    out["artifact_path"] = out_path
    out["mode"] = "DAY2_LIFECYCLE_DRY_RUN"
    return _emit(out, EXIT_READY if artifact["verdict"] == d2.DRY_RUN_READY else EXIT_BLOCKED)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.day2_lifecycle_dry_run:
        return run_day2_lifecycle_dry_run(args)
    return _emit({"blockers": ["no_mode_selected"]}, EXIT_INVALID)


if __name__ == "__main__":
    raise SystemExit(main())
