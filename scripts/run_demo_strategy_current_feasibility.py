#!/usr/bin/env python3
"""TASK-014CH4A -- read-only CURRENT market + Demo-account feasibility CLI.

ONE explicit, terminal, READ-ONLY operational mode:

    --current-market-demo-account-feasibility-read-only

It pins the trusted CH3C2 inputs (Review artifact, Anchor Manifest, canonical wrapper,
strategy-symbol source) by exact bytes + externally supplied canonical SHA256, collects
FRESH public market evidence + authenticated Demo-only read-only account evidence,
recomputes the current executable quantity per target from the CURRENT price, and writes
four immutable, atomic, no-clobber artifacts (market evidence / account evidence /
feasibility review / CLI summary).

HARD SCOPE
----------
  * Terminal: runs BEFORE any Pilot-state loading or mutation and stops.
  * Read-only: only public Bybit linear market reads + authenticated Demo GET reads.
    No POST/PUT/PATCH/DELETE; no order create/amend/cancel; no leverage / margin-mode /
    position-mode mutation; no Live endpoint.
  * It NEVER calls readiness, the execution gate, native execution, a sender, or the
    Pilot store, and never writes an execution-authorization marker.
  * There is NO REST fallback to historical CH3 prices once current-market collection
    begins. PASS means feasible AT THE COLLECTION TIMESTAMP ONLY.

The collection transports are injectable (``market_provider`` / ``account_provider``)
so the entire flow is exercised offline with fake transports; the default providers use
the audited read-only ``DemoMarketPriceGuard`` and ``DemoReadOnlyClient`` (GET only).
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import datetime, timezone
from decimal import Decimal
from pathlib import Path
from typing import Any, Callable, Mapping, Sequence

_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if _ROOT not in sys.path:
    sys.path.insert(0, _ROOT)

from src import demo_strategy_native_current_feasibility as cf  # noqa: E402
from src import demo_strategy_native_ws_bound_plan_only as wsbpo  # noqa: E402

# Exit codes (mirrors the native daily runner conventions).
EXIT_OK = 0
EXIT_BLOCKED = 2
EXIT_INVALID = 3
EXIT_INPUT_FAILURE = 4

# Flags that are fundamentally incompatible with a read-only feasibility run. Presence of
# any rejects the run BEFORE any network or file side effect.
_CONFLICTING_FLAGS = (
    "--send-orders-to-demo", "--advance-on-success", "--ws-bound-plan-only",
    "--ws-bound-plan-review-only", "--reconcile-outputs-only", "--execute",
)

MarketProvider = Callable[[Sequence[str], bool], "tuple[list[dict], dict]"]
AccountProvider = Callable[[Sequence[str], bool], "tuple[dict, dict]"]


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%fZ")


# ---------------------------------------------------------------------------
# Default real read-only collection providers (GET only; injectable for tests)
# ---------------------------------------------------------------------------

def _default_market_provider(symbols: Sequence[str], allow_real_network: bool,
                             ) -> tuple[list[dict], dict]:
    """Collect current public market evidence + instrument rules for ``symbols`` using
    the audited read-only clients. GET only; never references an order endpoint."""
    from src.demo_market_price_guard import (
        DemoMarketPriceGuard, DEMO_BASE_URL)
    from src.demo_readonly_client import DemoReadOnlyClient

    audit = cf.zeroed_network_audit()
    guard = DemoMarketPriceGuard(allow_real_network=allow_real_network)
    client = DemoReadOnlyClient(allow_real_network=allow_real_network)
    endpoint = f"{DEMO_BASE_URL}/v5/market/tickers"

    instruments = client.get_instruments_info(list(symbols))
    audit["public_http_get_count"] += 1
    server = client.get_server_time()
    audit["public_http_get_count"] += 1
    ex_ts_ms = None
    try:
        ex_ts_ms = int(float(getattr(server, "time_second", 0) or 0) * 1000) or None
    except (TypeError, ValueError):
        ex_ts_ms = None

    records: list[dict] = []
    for sym in symbols:
        price = guard.fetch_market_price(sym)
        audit["public_http_get_count"] += 1
        inst = instruments.get(sym)
        now_ns = time.time_ns()
        records.append({
            "symbol": sym,
            "current_price": (str(price.realtime_market_price)
                              if price.is_usable() else None),
            "exchange_ts_ms": ex_ts_ms or int(now_ns / 1_000_000),
            "local_received_epoch_ns": now_ns,
            "endpoint": endpoint,
            "instrument_status": (inst.status if inst else ""),
            "tick_size": (str(inst.tick_size) if inst else None),
            "qty_step": (str(inst.qty_step) if inst else None),
            "min_order_qty": (str(inst.min_qty) if inst else None),
            "min_notional_value": (str(inst.min_notional) if inst else None),
            "max_market_order_qty": (str(inst.max_qty) if inst else "0"),
            "contract_type": "LinearPerpetual",
            "settle_coin": "USDT",
            "trading": bool(inst and inst.status == "Trading"),
        })
    return records, audit


def _default_account_provider(target_symbols: Sequence[str], allow_real_network: bool,
                              ) -> tuple[dict, dict]:
    """Collect authenticated Demo-only read-only account evidence (GET only). Never
    returns any credential value; only derived scalar evidence."""
    from src.demo_readonly_client import DemoReadOnlyClient, DEMO_BASE_URL

    audit = cf.zeroed_network_audit()
    client = DemoReadOnlyClient(allow_real_network=allow_real_network)
    proof = client.build_runtime_proof()
    audit["private_demo_http_get_count"] += 1
    wallet = client.get_wallet_balance()
    audit["private_demo_http_get_count"] += 1
    positions = client.get_open_positions()
    audit["private_demo_http_get_count"] += 1
    info = client.get_account_info()
    audit["private_demo_http_get_count"] += 1

    pos = [{"symbol": p.symbol, "side": p.side, "size": str(p.quantity),
            "leverage": str(p.leverage),
            "initial_margin_usd": (None if p.initial_margin_usd is None
                                   else str(p.initial_margin_usd))}
           for p in positions]
    snapshot = {
        "endpoint_family": proof.endpoint_family,
        "demo_flag": bool(proof.demo_flag),
        "base_url": DEMO_BASE_URL,
        "live_endpoint_fallback_detected": bool(proof.live_endpoint_fallback_detected),
        "account_mode": proof.account_mode,
        "margin_mode": (info.margin_mode if info.response_present else None),
        "position_mode": "one_way",  # Demo strategy account is one-way (validated downstream)
        "wallet_evidence_present": bool(wallet.api_key_present),
        "account_equity_usd": str(wallet.equity_usd),
        "available_balance_usd": str(wallet.available_balance_usd),
        "existing_initial_margin_usd": (None if wallet.total_initial_margin_usd is None
                                        else str(wallet.total_initial_margin_usd)),
        "existing_maintenance_margin_usd": (None if wallet.total_maintenance_margin_usd is None
                                            else str(wallet.total_maintenance_margin_usd)),
        "applicable_initial_margin_rate": (None if wallet.account_im_rate is None
                                           else str(wallet.account_im_rate)),
        "margin_rate_source": ("wallet.accountIMRate" if wallet.account_im_rate is not None
                               else None),
        "positions": pos,
        "snapshot_epoch_ns": time.time_ns(),
    }
    return snapshot, audit


# ---------------------------------------------------------------------------
# Argument parsing
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="run_demo_strategy_current_feasibility",
        description="Read-only CURRENT market + Demo-account feasibility (CH4A).")
    p.add_argument("--current-market-demo-account-feasibility-read-only",
                   dest="feasibility_mode", action="store_true",
                   help="The single explicit terminal read-only feasibility mode.")
    # Trusted inputs.
    p.add_argument("--review-artifact-json", dest="review_json")
    p.add_argument("--review-artifact-sha256", dest="review_sha")
    p.add_argument("--anchor-manifest-json", dest="manifest_json")
    p.add_argument("--anchor-manifest-sha256", dest="manifest_sha")
    p.add_argument("--wrapper-json", dest="wrapper_json")
    p.add_argument("--strategy-symbols-json", dest="symbols_json")
    p.add_argument("--strategy-symbols-sha256", dest="symbols_sha")
    # Outputs (explicit, no-clobber).
    p.add_argument("--market-evidence-output-json", dest="market_out")
    p.add_argument("--account-evidence-output-json", dest="account_out")
    p.add_argument("--feasibility-review-output-json", dest="review_out")
    p.add_argument("--summary-output-json", dest="summary_out")
    # Tunables.
    p.add_argument("--market-freshness-threshold-ms", type=int,
                   default=cf.DEFAULT_MARKET_FRESHNESS_THRESHOLD_MS)
    p.add_argument("--account-freshness-threshold-ms", type=int,
                   default=cf.DEFAULT_ACCOUNT_FRESHNESS_THRESHOLD_MS)
    p.add_argument("--safety-headroom-fraction", default="0.10")
    p.add_argument("--fees-buffer-usd", default="5")
    p.add_argument("--allow-real-network", action="store_true",
                   help="Permit read-only GET/WS network reads (default: offline fixtures).")
    return p


def _emit(summary: Mapping[str, Any]) -> None:
    print(json.dumps(summary, ensure_ascii=False, sort_keys=True))


def _invalid(status: str, *blockers: str) -> dict:
    return {"status": status, "blockers": list(blockers),
            **cf.safe_safety_counters()}


def _read_bytes(path: str) -> bytes:
    return Path(path).read_bytes()


def _norm(path: str | None) -> str | None:
    return None if not path else os.path.normcase(os.path.normpath(os.path.abspath(path)))


# ---------------------------------------------------------------------------
# main
# ---------------------------------------------------------------------------

def main(argv: Sequence[str] | None = None, *,
         market_provider: MarketProvider | None = None,
         account_provider: AccountProvider | None = None) -> int:
    raw_argv = list(sys.argv[1:] if argv is None else argv)

    # --- Pre-parse safety gate (runs BEFORE argparse so incompatible flags are
    # rejected even though they are not defined options, and BEFORE any side effect) ---
    if "--current-market-demo-account-feasibility-read-only" not in raw_argv:
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, "feasibility_mode_flag_absent"))
        return EXIT_INVALID
    for flag in _CONFLICTING_FLAGS:
        if flag in raw_argv:
            _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, f"conflicting_flag:{flag}"))
            return EXIT_INVALID

    args = build_parser().parse_args(raw_argv)

    required = {
        "--review-artifact-json": args.review_json,
        "--review-artifact-sha256": args.review_sha,
        "--anchor-manifest-json": args.manifest_json,
        "--anchor-manifest-sha256": args.manifest_sha,
        "--wrapper-json": args.wrapper_json,
        "--strategy-symbols-json": args.symbols_json,
        "--strategy-symbols-sha256": args.symbols_sha,
        "--market-evidence-output-json": args.market_out,
        "--account-evidence-output-json": args.account_out,
        "--feasibility-review-output-json": args.review_out,
        "--summary-output-json": args.summary_out,
    }
    missing = [k for k, v in required.items() if not v]
    if missing:
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID,
                       *(f"missing_arg:{k}" for k in missing)))
        return EXIT_INVALID

    # --- No input/output alias and no pre-existing output (no-clobber) ---
    in_paths = {_norm(p) for p in (args.review_json, args.manifest_json,
                                   args.wrapper_json, args.symbols_json)}
    out_paths = [args.market_out, args.account_out, args.review_out, args.summary_out]
    norm_out = [_norm(p) for p in out_paths]
    if len(set(norm_out)) != len(norm_out):
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, "duplicate_output_path"))
        return EXIT_INVALID
    if in_paths & set(norm_out):
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, "input_output_alias"))
        return EXIT_INVALID
    for p in out_paths:
        if os.path.lexists(p):
            _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, f"output_exists:{p}"))
            return EXIT_INVALID

    # --- Read exact trusted-input bytes ---
    try:
        review_bytes = _read_bytes(args.review_json)
        manifest_bytes = _read_bytes(args.manifest_json)
        wrapper_bytes = _read_bytes(args.wrapper_json)
        symbols_bytes = _read_bytes(args.symbols_json)
    except OSError as exc:
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, f"input_unreadable:{type(exc).__name__}"))
        return EXIT_INPUT_FAILURE

    trusted = cf.validate_trusted_inputs(
        review_artifact_bytes=review_bytes,
        expected_review_artifact_sha256=args.review_sha,
        anchor_manifest_bytes=manifest_bytes,
        expected_anchor_manifest_sha256=args.manifest_sha,
        wrapper_artifact_bytes=wrapper_bytes,
        strategy_symbols_bytes=symbols_bytes,
        expected_strategy_symbols_sha256=args.symbols_sha)
    if not trusted.ok:
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, *trusted.blockers))
        return EXIT_INVALID

    # --- Validate tunables ---
    try:
        headroom = Decimal(str(args.safety_headroom_fraction))
        fees = Decimal(str(args.fees_buffer_usd))
    except Exception:  # noqa: BLE001
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, "invalid_decimal_tunable"))
        return EXIT_INVALID

    market_provider = market_provider or _default_market_provider
    account_provider = account_provider or _default_account_provider

    # --- Collect current evidence (read-only) ---
    symbols = list(trusted.symbols)
    try:
        market_records, market_audit = market_provider(symbols, args.allow_real_network)
        account_snapshot, account_audit = account_provider(symbols, args.allow_real_network)
    except Exception as exc:  # noqa: BLE001  (collection failure is terminal, fail closed)
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID,
                       f"collection_error:{type(exc).__name__}"))
        return EXIT_INPUT_FAILURE

    # Merge the read-only audits (never any mutating/order counter).
    network_audit = cf.zeroed_network_audit()
    for a in (market_audit, account_audit):
        for k, v in (a or {}).items():
            if k in network_audit and isinstance(v, int) and not isinstance(v, bool):
                network_audit[k] += v
    if not cf.network_audit_is_read_only(network_audit):
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, "network_audit_not_read_only"))
        return EXIT_BLOCKED

    collection_epoch_ns = time.time_ns()
    now_iso = _utc_now_iso()

    market = cf.evaluate_current_market_and_quantities(
        market_records, targets=trusted.targets,
        collection_epoch_ns=collection_epoch_ns,
        market_freshness_threshold_ms=args.market_freshness_threshold_ms)
    account = cf.evaluate_demo_account_evidence(
        account_snapshot, target_symbols=symbols,
        collection_epoch_ns=collection_epoch_ns,
        account_freshness_threshold_ms=args.account_freshness_threshold_ms)
    margin = cf.evaluate_margin_feasibility(
        account_result=account, target_gross_notional_usd=cf.V1_GROSS_USD,
        safety_headroom_fraction=headroom, fees_buffer_usd=fees)

    market_art = cf.build_market_evidence_artifact(
        trusted=trusted, market=market, collection_epoch_ns=collection_epoch_ns,
        collected_at_utc=now_iso, network_audit=network_audit)
    account_art = cf.build_account_evidence_artifact(
        account=account, collection_epoch_ns=collection_epoch_ns,
        collected_at_utc=now_iso, network_audit=network_audit)

    # --- Atomic no-clobber publication. Each artifact's recorded SHA is the SHA of the
    # ACTUAL on-disk bytes (read back after the write), so downstream references and the
    # summary always match the published files exactly (platform-newline independent). ---
    try:
        market_sha = _write_and_sha(args.market_out, market_art)
        account_sha = _write_and_sha(args.account_out, account_art)
        feasibility = cf.build_current_feasibility_review(
            trusted=trusted, market=market, account=account, margin=margin,
            collection_epoch_ns=collection_epoch_ns, reviewed_at_utc=now_iso,
            network_audit=network_audit,
            market_evidence_artifact_sha256=market_sha,
            account_evidence_artifact_sha256=account_sha)
        review_sha = _write_and_sha(args.review_out, feasibility.review_artifact)
        summary = cf.build_cli_summary(
            feasibility=feasibility, trusted=trusted, market=market, account=account,
            network_audit=network_audit, review_artifact_sha256=review_sha,
            market_artifact_sha256=market_sha, account_artifact_sha256=account_sha)
        _write_and_sha(args.summary_out, summary)
    except wsbpo.WsBoundPlanOnlyError as exc:
        _emit(_invalid(cf.CURRENT_FEASIBILITY_INPUT_INVALID, f"output_write_failed:{exc}"))
        return EXIT_INPUT_FAILURE

    _emit(summary)
    if feasibility.status == cf.CURRENT_FEASIBILITY_PASS:
        return EXIT_OK
    if feasibility.status in (cf.CURRENT_FEASIBILITY_BLOCKED,
                              cf.CURRENT_FEASIBILITY_MARKET_EVIDENCE_FAILED,
                              cf.CURRENT_FEASIBILITY_ACCOUNT_EVIDENCE_FAILED,
                              cf.CURRENT_FEASIBILITY_UNAVAILABLE):
        return EXIT_BLOCKED
    return EXIT_INVALID


def _write_and_sha(path: str, artifact: Mapping[str, Any]) -> str:
    """Atomic no-clobber write, then return the canonical SHA256 of the ACTUAL on-disk
    bytes (so the recorded anchor is platform-newline independent and always matches)."""
    from src.demo_strategy_native_ws_price_binding import compute_file_sha256
    wsbpo.atomic_write_wrapper(path, artifact)
    return compute_file_sha256(Path(path).read_bytes())


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
