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
                   legacy_symbols: list[str]) -> dict[str, Any]:
    strategy_symbols, strat_ref = derive_strategy_target_symbols(
        run_date=run_date, repo_root=repo_root, forward_source_root=forward_source_root)
    legacy_ref = ("observed protected legacy positions requiring account-level "
                  "mark-price feasibility evidence (supplied --legacy-symbol; "
                  f"validated against PROTECTED_SYMBOLS={sorted(PROTECTED_SYMBOL_ALLOWLIST)})")
    return ws.derive_required_symbol_universe(
        strategy_target_symbols=strategy_symbols,
        observed_legacy_symbols=legacy_symbols,
        protected_symbol_allowlist=PROTECTED_SYMBOL_ALLOWLIST,
        strategy_source_reference=strat_ref,
        legacy_source_reference=legacy_ref,
    )


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
    sub_msg = ws.build_subscription_message(universe["symbols"], req_id="cf-public-ticker")

    attempts = 0
    reconnects = 0
    acknowledged = False
    generation = -1

    while attempts <= max_reconnect:
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
            builder.record_subscription_request(len(topics))
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
                if op == "pong" or msg.get("ret_msg") == "pong" or (
                        op == "ping"):
                    builder.record_pong()
                    continue
                if op == "subscribe":
                    if bool(msg.get("success", False)):
                        acknowledged = True
                        builder.record_subscription_ack()
                    continue
                if "topic" in msg and "data" in msg:
                    builder.ingest_data_message(
                        msg, local_received_epoch_ns=recv_epoch_ns,
                        local_monotonic_received_ns=recv_mono_ns,
                        connection_generation=generation)
        finally:
            try:
                conn.close()
            except Exception:  # noqa: BLE001
                pass
        # One bounded window per generation; reconnect only if it was not clean.
        if clean:
            break

    # cumulative transport counts already recorded incrementally
    return {
        "subscription_acknowledged": acknowledged,
        "reconnect_generation_ambiguous": reconnects > 0,
    }


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=(
        "Standalone public read-only WebSocket ticker timestamp evidence "
        "collector (TASK-014CF). No credentials, no orders, no Pilot."))
    ap.add_argument("--strategy-date", required=True,
                    help="Primary Forward Record run date (YYYY-MM-DD).")
    ap.add_argument("--legacy-symbol", action="append", default=[],
                    help="Observed protected legacy symbol (repeatable).")
    ap.add_argument("--deadline-seconds", type=float, default=30.0)
    ap.add_argument("--max-reconnect", type=int, default=1)
    ap.add_argument("--heartbeat-seconds", type=float, default=18.0)
    ap.add_argument("--stale-threshold-ms", type=int,
                    default=ws.DEFAULT_STALE_THRESHOLD_MS)
    ap.add_argument("--clock-offset-seconds", default=None,
                    help="Accepted CE clock offset (seconds) for transport delay.")
    ap.add_argument("--clock-offset-status", default=None,
                    help="CE clock_offset_evidence_status (e.g. CLOCK_OFFSET_AVAILABLE).")
    ap.add_argument("--out", default=None, help="Artifact output path (JSON).")
    ap.add_argument("--allow-real-network", action="store_true",
                    help="Open the real public linear WebSocket (default: offline).")
    ap.add_argument("--verify-no-credential-leak", action="store_true",
                    help="Read credential env vars ONLY to prove they never appear "
                         "in the artifact.")
    ap.add_argument("--repo-root", default=ROOT)
    ap.add_argument("--test-forward-source-root", default=None)
    ap.add_argument("--json-only", action="store_true")
    args = ap.parse_args(argv)

    legacy_symbols = [s.strip().upper() for s in args.legacy_symbol if s.strip()]
    universe = build_universe(
        run_date=args.strategy_date, repo_root=args.repo_root,
        forward_source_root=args.test_forward_source_root,
        legacy_symbols=legacy_symbols)

    builder = ws.PublicWsTickerEvidenceBuilder(
        universe=universe,
        clock_offset_seconds=args.clock_offset_seconds,
        clock_offset_status=args.clock_offset_status,
        stale_threshold_ms=args.stale_threshold_ms,
    )

    collect_meta = {"subscription_acknowledged": False,
                    "reconnect_generation_ambiguous": False}
    if args.allow_real_network:
        collect_meta = _collect_real(
            builder, universe=universe, deadline_seconds=args.deadline_seconds,
            max_reconnect=args.max_reconnect, heartbeat_seconds=args.heartbeat_seconds)

    artifact = builder.build_artifact(
        finalize_epoch_ns=time.time_ns(),
        subscription_acknowledged=collect_meta["subscription_acknowledged"],
        reconnect_generation_ambiguous=collect_meta["reconnect_generation_ambiguous"],
        collection_deadline_seconds=args.deadline_seconds,
    )

    if args.verify_no_credential_leak:
        secret_values = [os.environ.get(n, "") for n in _CREDENTIAL_ENV_NAMES]
        ws.assert_no_credentials(artifact, secret_values=secret_values)
        artifact["credential_leak_check"] = "NO_CREDENTIAL_VALUE_OR_KEY_PRESENT"

    if args.out:
        with open(args.out, "w", encoding="utf-8") as fh:
            json.dump(artifact, fh, indent=2, sort_keys=True)

    if args.json_only:
        print(json.dumps(artifact, indent=2, sort_keys=True))
    else:
        cov = artifact["coverage_summary"]
        print(f"overall_status={artifact['overall_status']}")
        print(f"requested={cov['requested_symbol_count']} "
              f"unique={cov['unique_symbol_count']} "
              f"covered={cov['covered_symbol_count']} "
              f"complete={cov['complete_symbol_count']}")
        print(f"symbol_universe_fingerprint={universe['symbol_universe_fingerprint']}")
        print(f"artifact_fingerprint={artifact['artifact_fingerprint']}")

    # Exit 0 only on a clean COMPLETE run; otherwise 0 for offline derivation,
    # non-zero when a real run did not reach COMPLETE.
    if args.allow_real_network and artifact["overall_status"] != ws.WS_TICKER_EVIDENCE_COMPLETE:
        return 2
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
