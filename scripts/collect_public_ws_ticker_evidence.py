"""scripts/collect_public_ws_ticker_evidence.py
TASK-014CF: standalone public read-only WebSocket ticker evidence collector.

This is the THIN transport + CLI around the pure logic in
``src/demo_public_ws_ticker_evidence.py``. It:

  * derives the required linear-symbol universe from authoritative project
    sources (the Primary Forward Record for the 50 Strategy targets, plus the
    explicitly-supplied observed protected legacy symbols, validated against the
    protected allowlist);
  * opens ONE public linear WebSocket connection to
    wss://stream.bybit.com/v5/public/linear;
  * subscribes ONLY to tickers.{symbol} topics (no auth, no api_key/sign);
  * collects under a bounded deadline with heartbeat pings and at most one
    reconnect (a new connection generation);
  * feeds parsed messages to the pure evidence builder; and
  * writes a canonical, fingerprinted artifact.

It NEVER loads or sends Bybit API credentials, NEVER opens a private/Demo/testnet
or trade endpoint, NEVER replaces the REST planner price source, and NEVER
removes the freshness blockers. No order / execution / Pilot action is possible.

Default (no --allow-real-network): performs ZERO network I/O. It derives and
prints the symbol universe and writes a no-collection artifact.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import tempfile
import time
from typing import Any

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_public_ws_ticker_evidence as ws  # noqa: E402
from src import demo_strategy_pilot_forward_source as fs  # noqa: E402
from src import demo_strategy_pilot_readiness as rd  # noqa: E402


PROTECTED_SYMBOL_ALLOWLIST = tuple(rd.PROTECTED_SYMBOLS)

# Env var names that MIGHT hold credentials. The collector never uses them; the
# optional leak check reads them ONLY to prove they never reach the artifact.
_CREDENTIAL_ENV_NAMES = (
    "BYBIT_API_KEY", "BYBIT_API_SECRET", "BYBIT_DEMO_API_KEY",
    "BYBIT_DEMO_API_SECRET", "API_KEY", "API_SECRET",
)


def derive_strategy_target_symbols(*, run_date: str, repo_root: str,
                                   forward_source_root: str | None) -> tuple[list[str], str]:
    """Return (sorted strategy linear symbols, source reference) from the
    authoritative Primary Forward Record. No credentials, local artifacts only."""
    result = fs.load_primary_forward_strategy_result(
        run_date=run_date, repo_root=repo_root, forward_source_root=forward_source_root)
    symbols = sorted({
        str(sig["symbol"]).strip().upper()
        for sig in result.normalized_signals
        if str(sig.get("symbol", "")).strip()
    })
    ref = (f"Primary Forward Record {result.run_key} "
           f"({result.strategy_name}) fingerprint={result.source_fingerprint}")
    return symbols, ref


def build_universe(*, run_date: str, repo_root: str, forward_source_root: str | None,
                   legacy_symbols: list[str], legacy_source_reference: str
                   ) -> tuple[dict[str, Any], str]:
    strategy_symbols, strat_ref = derive_strategy_target_symbols(
        run_date=run_date, repo_root=repo_root, forward_source_root=forward_source_root)
    universe = ws.derive_required_symbol_universe(
        strategy_target_symbols=strategy_symbols,
        observed_legacy_symbols=legacy_symbols,
        protected_symbol_allowlist=PROTECTED_SYMBOL_ALLOWLIST,
        strategy_source_reference=strat_ref,
        legacy_source_reference=legacy_source_reference,
    )
    return universe, strat_ref


def _in_test_or_temp_context(out_path: str | None) -> bool:
    """True only inside an explicit pytest run or when writing under a temp dir.

    Unsafe test-only overrides (raw clock offset, manual legacy symbols) are
    rejected outside this context.
    """
    if os.environ.get("PYTEST_CURRENT_TEST"):
        return True
    tmp = os.path.realpath(tempfile.gettempdir())
    if out_path:
        try:
            if os.path.realpath(os.path.dirname(out_path) or ".").startswith(tmp):
                return True
        except OSError:
            return False
    return False


def _collect_real(builder: "ws.PublicWsTickerEvidenceBuilder", *, universe: dict[str, Any],
                  deadline_seconds: float, max_reconnect: int,
                  heartbeat_seconds: float) -> dict[str, Any]:
    """Open ONE public linear connection (with <=1 reconnect) and feed messages.

    Lazily imports websocket-client (an accepted transitive dependency via pybit)
    so the default offline path needs no websocket library.
    """
    import websocket  # websocket-client; lazy so offline mode stays I/O-free

    endpoint = ws.assert_public_endpoint_allowed(ws.PUBLIC_LINEAR_WS_ENDPOINT)
    topics = [f"tickers.{s}" for s in universe["symbols"]]
    req_id = "cf-public-ticker"
    sub_msg = ws.build_subscription_message(universe["symbols"], req_id=req_id)

    attempts = 0
    reconnects = 0
    generation = -1
    completion: dict[str, Any] | None = None
    finalize_epoch_ns: int | None = None
    data_completion_at_ns: int | None = None

    while attempts <= max_reconnect and completion is None:
        generation += 1
        attempts += 1
        builder.record_connection_attempt()
        if generation > 0:
            reconnects += 1
            builder.record_reconnect()
        try:
            conn = websocket.create_connection(endpoint, timeout=10)
        except Exception as exc:  # noqa: BLE001
            if attempts > max_reconnect:
                break
            continue
        builder.record_connection_success(generation)
        try:
            conn.send(json.dumps(sub_msg))
            builder.record_subscription_request(len(topics), request_id=req_id,
                                                generation=generation)
            conn.settimeout(1.0)
            deadline = time.monotonic() + deadline_seconds
            last_ping = time.monotonic()
            clean = True
            while time.monotonic() < deadline:
                now = time.monotonic()
                if now - last_ping >= heartbeat_seconds:
                    try:
                        conn.send(json.dumps({"op": "ping"}))
                        builder.record_ping()
                    except Exception:  # noqa: BLE001
                        clean = False
                        break
                    last_ping = now
                try:
                    raw = conn.recv()
                except websocket.WebSocketTimeoutException:
                    continue
                except Exception:  # noqa: BLE001
                    clean = False
                    break
                if not raw:
                    continue
                recv_epoch_ns = time.time_ns()
                recv_mono_ns = time.monotonic_ns()
                try:
                    msg = json.loads(raw)
                except (ValueError, TypeError):
                    builder.ws_malformed_message_count += 1
                    continue
                op = str(msg.get("op", "")).strip().lower()
                if op == "pong" or msg.get("ret_msg") == "pong" or op == "ping":
                    builder.record_pong()
                    continue
                if op == "subscribe":
                    # FIX3: validate + bind the ACK (data messages are NOT an ACK).
                    ack_status = builder.ingest_subscription_ack(
                        msg, connection_generation=generation,
                        received_epoch_ns=recv_epoch_ns)
                    if ack_status == ws.WS_SUBSCRIPTION_ACK_REJECTED:
                        clean = False
                        break
                elif "topic" in msg and "data" in msg:
                    builder.ingest_data_message(
                        msg, local_received_epoch_ns=recv_epoch_ns,
                        local_monotonic_received_ns=recv_mono_ns,
                        connection_generation=generation)

                # FIX3: re-evaluate after EVERY processed message (ack/snapshot/delta).
                # Full completion requires data completion AND a valid ACK; keep reading
                # while either is missing; never loosen the stale threshold.
                check_ns = time.time_ns()
                ev = builder.evaluate_completion(check_epoch_ns=check_ns)
                if ev["data_complete"] and data_completion_at_ns is None:
                    data_completion_at_ns = check_ns
                if ev["full_complete"]:
                    finalize_epoch_ns = check_ns
                    completion = {
                        "early_completion_enabled": True,
                        "completion_achieved": True,
                        "completion_achieved_at_epoch_ns": check_ns,
                        "completion_achieved_at_utc": _utc_from_ns(check_ns),
                        "completion_connection_generation": ev["connection_generation"],
                        "completion_required_symbol_count": ev["required_symbol_count"],
                        "completion_complete_symbol_count": ev["complete_symbol_count"],
                        "completion_trigger_message_count": builder.ws_message_count,
                        "data_completion_achieved_at_epoch_ns": data_completion_at_ns,
                        "data_completion_achieved_at_utc": (
                            _utc_from_ns(data_completion_at_ns)
                            if data_completion_at_ns is not None else None),
                        "collection_terminated_reason":
                            ws.TERMINATED_COMPLETE_AND_ACKED,
                    }
                    break
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        # One bounded window per generation; reconnect only if it was not clean.
        if clean or completion is not None:
            break

    if completion is None:
        # Resolve the intermediate/terminal reason for the unfinished run.
        if builder.subscription_ack_status == ws.WS_SUBSCRIPTION_ACK_REJECTED:
            reason = ws.TERMINATED_SUBSCRIPTION_REJECTED
        elif data_completion_at_ns is not None and not builder.subscription_acknowledged:
            reason = ws.TERMINATED_DATA_WAITING_FOR_ACK
        else:
            reason = ws.TERMINATED_DEADLINE_REACHED
        completion = {
            "early_completion_enabled": True,
            "completion_achieved": False,
            "completion_achieved_at_epoch_ns": None,
            "completion_achieved_at_utc": None,
            "completion_connection_generation": None,
            "completion_required_symbol_count": universe["unique_symbol_count"],
            "completion_complete_symbol_count": None,
            "completion_trigger_message_count": None,
            "data_completion_achieved_at_epoch_ns": data_completion_at_ns,
            "data_completion_achieved_at_utc": (
                _utc_from_ns(data_completion_at_ns)
                if data_completion_at_ns is not None else None),
            "collection_terminated_reason": reason,
        }

    return {
        "reconnect_generation_ambiguous": reconnects > 0,
        "completion_meta": completion,
        "finalize_epoch_ns": finalize_epoch_ns,
    }


def _utc_from_ns(epoch_ns: int) -> str:
    from datetime import datetime, timezone
    return datetime.fromtimestamp(epoch_ns / 1e9, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ")


def _load_ce_evidence(path: str) -> tuple[dict[str, Any], bytes]:
    with open(path, "rb") as fh:
        raw = fh.read()
    return json.loads(raw.decode("utf-8")), raw


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(
        "Standalone public read-only WebSocket ticker timestamp evidence "
        "collector (TASK-014CF/FIX1). No credentials, no orders, no Pilot."))
    ap.add_argument("--strategy-date", required=True,
                    help="Primary Forward Record run date (YYYY-MM-DD).")
    # Authoritative source of BOTH the clock offset and the protected-legacy
    # universe (accepted CE/FIX1 Plan-only artifact). Required for production.
    ap.add_argument("--ce-evidence-json", default=None,
                    help="Path to the accepted TASK-014CE/FIX1 Plan-only JSON artifact.")
    ap.add_argument("--clock-offset-max-age-seconds", type=int,
                    default=ws.DEFAULT_CLOCK_OFFSET_MAX_AGE_SECONDS)
    ap.add_argument("--deadline-seconds", type=float, default=30.0)
    ap.add_argument("--max-reconnect", type=int, default=1)
    ap.add_argument("--heartbeat-seconds", type=float, default=18.0)
    ap.add_argument("--stale-threshold-ms", type=int,
                    default=ws.DEFAULT_STALE_THRESHOLD_MS)
    ap.add_argument("--require-complete", action="store_true",
                    help="Production gate: non-zero exit unless evidence is COMPLETE.")
    ap.add_argument("--out", default=None, help="Artifact output path (JSON).")
    ap.add_argument("--allow-real-network", action="store_true",
                    help="Open the real public linear WebSocket (default: offline).")
    ap.add_argument("--verify-no-credential-leak", action="store_true",
                    help="Read credential env vars ONLY to prove they never appear "
                         "in the artifact.")
    ap.add_argument("--repo-root", default=ROOT)
    ap.add_argument("--test-forward-source-root", default=None)
    ap.add_argument("--json-only", action="store_true")
    # ---- UNSAFE test-only overrides (rejected outside test/temp context) ----
    ap.add_argument("--unsafe-test-legacy-symbol", action="append", default=[],
                    help="TEST-ONLY manual protected-legacy symbol override.")
    ap.add_argument("--unsafe-test-clock-offset-seconds", default=None,
                    help="TEST-ONLY raw clock offset (cannot create authoritative "
                         "provenance).")
    ap.add_argument("--unsafe-test-clock-offset-status", default=None,
                    help="TEST-ONLY raw clock offset status.")
    ap.add_argument("--unsafe-allow-test-overrides", action="store_true",
                    help="Acknowledge unsafe test-only overrides (test/temp only).")
    args = ap.parse_args(argv)

    def _summary_print(artifact: dict[str, Any], universe: dict[str, Any]) -> None:
        cov = artifact["coverage_summary"]
        print(f"overall_status={artifact['overall_status']}")
        print(f"required={cov['unique_symbol_count']} "
              f"covered={cov['covered_symbol_count']} "
              f"complete={cov['complete_symbol_count']}")
        print(f"blockers={artifact['blockers']}")
        print(f"cli_exit_status={artifact['cli_exit_status']} "
              f"cli_exit_reason={artifact['cli_exit_reason']}")
        print(f"symbol_universe_fingerprint={universe['symbol_universe_fingerprint']}")
        print(f"artifact_fingerprint={artifact['artifact_fingerprint']}")

    # ---- resolve unsafe test-only overrides ----
    unsafe_overrides_used = bool(args.unsafe_test_legacy_symbol
                                 or args.unsafe_test_clock_offset_seconds
                                 or args.unsafe_test_clock_offset_status)
    if unsafe_overrides_used:
        if not (args.unsafe_allow_test_overrides and _in_test_or_temp_context(args.out)):
            print("ERROR: unsafe test-only overrides rejected outside a test/temp context",
                  file=sys.stderr)
            return ws.EXIT_INVALID_CONFIG

    # ---- dependency readiness ----
    dependency = ws.check_ws_client_dependency()
    dependency_status = dependency["ws_client_dependency_status"]

    # ---- authoritative clock-offset + legacy provenance from CE evidence ----
    clock_provenance: dict[str, Any] | None = None
    legacy_provenance: dict[str, Any] | None = None
    source_evidence: dict[str, Any] | None = None
    legacy_symbols: list[str] = []
    legacy_source_reference = ""
    clock_offset_seconds = None
    clock_offset_status = None
    clock_provenance_status = None

    if args.ce_evidence_json:
        try:
            ce_artifact, ce_bytes = _load_ce_evidence(args.ce_evidence_json)
        except (OSError, ValueError) as exc:
            print(f"ERROR: cannot read CE evidence artifact: {exc}", file=sys.stderr)
            return ws.EXIT_SOURCE_EVIDENCE_FAILURE
        now_epoch = time.time()
        clock_provenance = ws.extract_clock_offset_provenance(
            ce_artifact, artifact_path=args.ce_evidence_json, artifact_bytes=ce_bytes,
            requested_strategy_date=args.strategy_date,
            max_age_seconds=args.clock_offset_max_age_seconds, now_epoch=now_epoch)
        legacy_provenance = ws.extract_legacy_position_provenance(
            ce_artifact, protected_symbol_allowlist=PROTECTED_SYMBOL_ALLOWLIST,
            requested_strategy_date=args.strategy_date, artifact_bytes=ce_bytes)
        legacy_symbols = list(legacy_provenance["legacy_protected_symbols"])
        legacy_source_reference = (
            f"authoritative CE current-position evidence "
            f"sha256={legacy_provenance['ce_source_artifact_sha256']} "
            f"status={legacy_provenance['symbol_universe_source_status']}")
        clock_provenance_status = clock_provenance["clock_offset_provenance_status"]
        clock_offset_seconds = clock_provenance[
            "estimated_local_vs_exchange_clock_offset_seconds"]
        clock_offset_status = clock_provenance["clock_offset_evidence_status"]
        source_evidence = {
            "ce_evidence_artifact_path": args.ce_evidence_json,
            "ce_source_artifact_sha256": legacy_provenance["ce_source_artifact_sha256"],
            "active_policy": ce_artifact.get("active_policy"),
            "artifact_date": ce_artifact.get("date"),
            "requested_strategy_date": args.strategy_date,
            "account_mode_evidence_status": (
                (ce_artifact.get("strategy_native_review") or {}).get(
                    "account_mode_evidence") or {}).get("account_mode_evidence_status"),
            "strategy_symbol_source_fingerprint": None,  # set after universe build
            "legacy_position_source_fingerprint": (
                legacy_provenance["legacy_position_source_fingerprint"]),
        }
    elif args.unsafe_test_legacy_symbol or args.unsafe_test_clock_offset_seconds:
        # TEST-ONLY path (already gated above): synthesize a non-authoritative
        # provenance so COMPLETE remains impossible from raw inputs.
        legacy_symbols = [s.strip().upper() for s in args.unsafe_test_legacy_symbol
                          if s.strip()]
        legacy_source_reference = "UNSAFE_TEST_ONLY_MANUAL_LEGACY_SYMBOLS"
        clock_offset_seconds = args.unsafe_test_clock_offset_seconds
        clock_offset_status = args.unsafe_test_clock_offset_status
        # Raw numeric offset can NEVER be authoritative provenance.
        clock_provenance_status = ws.CLOCK_OFFSET_PROVENANCE_MISSING
        clock_provenance = {
            "clock_offset_provenance_status": clock_provenance_status,
            "clock_offset_source_artifact_path": None,
            "note": "UNSAFE_TEST_ONLY_RAW_OFFSET_NOT_AUTHORITATIVE",
        }
    else:
        print("ERROR: --ce-evidence-json is required for production collection "
              "(authoritative clock offset + protected-legacy universe)",
              file=sys.stderr)
        return ws.EXIT_INVALID_CONFIG

    # ---- build the authoritative symbol universe ----
    try:
        universe, strat_ref = build_universe(
            run_date=args.strategy_date, repo_root=args.repo_root,
            forward_source_root=args.test_forward_source_root,
            legacy_symbols=legacy_symbols,
            legacy_source_reference=legacy_source_reference)
    except Exception as exc:  # noqa: BLE001 — fail closed on any source error
        print(f"ERROR: symbol-universe derivation failed: {exc}", file=sys.stderr)
        return ws.EXIT_SOURCE_EVIDENCE_FAILURE
    if source_evidence is not None:
        source_evidence["strategy_symbol_source_fingerprint"] = (
            universe["symbol_universe_fingerprint"])

    # ---- CG_FIX1: authoritative WS-side strategy provenance from the CE artifact.
    # Read the active strategy ONLY from the accepted CE artifact (never inferred);
    # bind the canonical Strategy symbol-set fingerprint for mandatory validation.
    strategy_source_provenance: dict[str, Any] | None = None
    if args.ce_evidence_json:
        strategy_source_provenance = ws.extract_strategy_source_provenance(
            ce_artifact, strategy_symbols=universe["strategy_symbols"],
            requested_strategy_date=args.strategy_date, artifact_bytes=ce_bytes)

    builder = ws.PublicWsTickerEvidenceBuilder(
        universe=universe,
        clock_offset_seconds=clock_offset_seconds,
        clock_offset_status=clock_offset_status,
        clock_offset_provenance_status=clock_provenance_status,
        stale_threshold_ms=args.stale_threshold_ms,
    )

    collect_meta: dict[str, Any] = {"reconnect_generation_ambiguous": False,
                                    "completion_meta": None, "finalize_epoch_ns": None}
    if args.allow_real_network:
        if dependency_status != ws.WS_CLIENT_DEPENDENCY_AVAILABLE:
            print(f"ERROR: websocket client dependency not available: {dependency_status}",
                  file=sys.stderr)
        else:
            collect_meta = _collect_real(
                builder, universe=universe, deadline_seconds=args.deadline_seconds,
                max_reconnect=args.max_reconnect, heartbeat_seconds=args.heartbeat_seconds)

    # FIX2: when early completion succeeded, finalize at the ACTUAL early-completion
    # time; otherwise finalize now (deadline reached / offline).
    finalize_ns = collect_meta.get("finalize_epoch_ns") or time.time_ns()
    artifact = builder.build_artifact(
        finalize_epoch_ns=finalize_ns,
        reconnect_generation_ambiguous=collect_meta["reconnect_generation_ambiguous"],
        collection_deadline_seconds=args.deadline_seconds,
        source_evidence=source_evidence,
        clock_offset_provenance=clock_provenance,
        legacy_position_provenance=legacy_provenance,
        strategy_source_provenance=strategy_source_provenance,
        dependency_status=dependency_status,
        require_complete=args.require_complete,
        allow_real_network=args.allow_real_network,
        completion_meta=collect_meta.get("completion_meta"),
    )

    # ---- credential-leak verification (hard abort on failure) ----
    if args.verify_no_credential_leak:
        secret_values = [os.environ.get(n, "") for n in _CREDENTIAL_ENV_NAMES]
        try:
            ws.assert_no_credentials(artifact, secret_values=secret_values)
        except ws.WsEndpointError as exc:
            print(f"ERROR: credential safety failure: {exc}", file=sys.stderr)
            return ws.EXIT_CREDENTIAL_SAFETY
        artifact["credential_leak_check"] = "NO_CREDENTIAL_VALUE_OR_KEY_PRESENT"

    # ---- write artifact (still written on a safe non-zero evidence result) ----
    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(artifact, fh, indent=2, sort_keys=True)

    if args.json_only:
        print(json.dumps(artifact, indent=2, sort_keys=True))
    else:
        _summary_print(artifact, universe)

    return int(artifact["cli_exit_status"])


if __name__ == "__main__":
    raise SystemExit(main())
