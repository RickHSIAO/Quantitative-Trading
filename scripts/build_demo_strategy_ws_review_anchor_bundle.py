"""scripts/build_demo_strategy_ws_review_anchor_bundle.py
TASK-014CH3C1: offline builder for a trusted CH3 review ANCHOR MANIFEST.

Builds the versioned anchor manifest consumed by `--ws-bound-plan-review-only` from:
  * an externally-pinned CH2 Plan-only PASS summary (exact bytes + caller-owned SHA256);
  * the exact CH2 wrapper bytes;
  * the exact source-WS evidence bytes;
  * an INDEPENDENT canonical 50-symbol source (exact bytes + caller-owned SHA256).

It re-runs the CH1 historical validation, then writes ONE race-safe no-clobber manifest and
prints the manifest's literal-file SHA256 (which the operator must preserve and later pass to
`--ws-bound-plan-anchor-manifest-sha256`).

It does NOT run review-only, query market data, check account margin, or authorize execution.
No network / WebSocket / REST / Pilot / readiness / gate / execution / sender / reporting.

CLI isolation: imports ONLY the pure bundle core + the approved no-clobber writer. It does
NOT import the native-daily runner, Pilot store, readiness, gate, native execution, sender,
or reporting.
"""
from __future__ import annotations

import argparse
import json
import os
import re
import sys

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src import demo_strategy_native_ws_review_anchor_bundle as bundle  # noqa: E402
from src import demo_strategy_native_ws_bound_plan_only as wsbpo  # noqa: E402 (no-clobber writer)
from src import demo_strategy_native_ws_price_binding as wb  # noqa: E402 (pure SHA helper)

EXIT_OK = 0
EXIT_BLOCKED = 1
EXIT_INVALID = 2
EXIT_INPUT_FAILURE = 3

_CANON_SHA = re.compile(r"^sha256:[0-9a-f]{64}$")


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="build_demo_strategy_ws_review_anchor_bundle.py",
        description="TASK-014CH3C1 offline trusted CH3 review anchor-manifest builder "
                    "(no review-only, no market data, no execution).")
    p.add_argument("--ch2-summary-json", required=True,
                   help="path to the trusted CH2 Plan-only PASS summary JSON")
    p.add_argument("--ch2-summary-sha256", required=True,
                   help="REQUIRED caller-owned expected CH2 summary SHA256 (sha256:<64hex>); "
                        "never computed by the builder from the summary")
    p.add_argument("--ws-bound-plan-wrapper-json", required=True,
                   help="path to the exact CH2 wrapper JSON")
    p.add_argument("--ws-ticker-evidence-json", required=True,
                   help="path to the exact source-WS evidence JSON")
    p.add_argument("--expected-strategy-symbols-json", required=True,
                   help="path to the INDEPENDENT canonical 50-symbol source JSON "
                        "(array of 50 normalized symbols, or {strategy_symbols:[...]})")
    p.add_argument("--expected-strategy-symbols-sha256", required=True,
                   help="REQUIRED caller-owned expected symbols-file SHA256 (sha256:<64hex>)")
    p.add_argument("--output-anchor-manifest-json", required=True,
                   help="output path for the anchor manifest (fresh path; no clobber)")
    p.add_argument("--date", required=True, help="expected run date YYYY-MM-DD")
    return p


def _exit_code_for(status: str) -> int:
    if status == bundle.WS_REVIEW_ANCHOR_BUNDLE_PASS:
        return EXIT_OK
    if status in (bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID,
                  bundle.WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID,
                  bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS):
        return EXIT_INVALID
    if status in (bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_READ_FAILED,
                  bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_FAILED):
        return EXIT_INPUT_FAILURE
    return EXIT_BLOCKED  # SUMMARY/SOURCE/CONSUMER/CANONICAL validation blocked


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)

    def _summary(status: str, *, detail: str, result=None, written: bool = False,
                 output_sha256: str | None = None) -> int:
        out = {
            "status": status, "mode": "WS_REVIEW_ANCHOR_BUNDLE_BUILDER", "detail": detail,
            "date": args.date,
            "ch2_summary_json": args.ch2_summary_json,
            "wrapper_json": args.ws_bound_plan_wrapper_json,
            "ws_ticker_evidence_json": args.ws_ticker_evidence_json,
            "expected_strategy_symbols_json": args.expected_strategy_symbols_json,
            "output_anchor_manifest_json": args.output_anchor_manifest_json,
            "manifest_written": written,
            # Terminal, never executable; no side effects.
            "execution_readiness": False, "readiness_called": False,
            "execution_gate_called": False, "native_execution_called": False,
            "pilot_advanced": False, "sender_reachable": False,
            "order_post_count": 0, "amend_post_count": 0, "cancel_post_count": 0,
            "live_order_post_count": 0, "notion_called": False, "discord_called": False,
            "live_trading_authorized": False, "rest_fallback_used": False,
        }
        if result is not None:
            out.update({
                "blockers": list(result.blockers),
                # Authoritative on-disk SHA of the written manifest file (the operator
                # preserves THIS and passes it to --ws-bound-plan-anchor-manifest-sha256).
                "output_anchor_manifest_sha256": output_sha256,
                "manifest_fingerprint": result.manifest_fingerprint,
                "ch2_summary_file_sha256": result.ch2_summary_file_sha256,
                "wrapper_file_sha256": result.wrapper_file_sha256,
                "wrapper_logical_fingerprint": result.wrapper_logical_fingerprint,
                "source_ws_file_sha256": result.source_ws_file_sha256,
                "source_ws_logical_fingerprint": result.source_ws_logical_fingerprint,
                "canonical_bound_plan_fingerprint": result.canonical_bound_plan_fingerprint,
                "original_plan_fingerprint": result.original_plan_fingerprint,
                "expected_symbol_set_fingerprint": result.expected_symbol_set_fingerprint,
                "strategy_symbols_file_sha256": result.expected_strategy_symbols_file_sha256,
                "run_date": result.run_date,
                "binding_epoch_ns": result.binding_epoch_ns,
                "freshness_threshold_ms": result.freshness_threshold_ms,
                "action_count": result.action_count,
                "long_count": result.long_count, "short_count": result.short_count,
            })
        print(json.dumps(out, ensure_ascii=False, indent=2, sort_keys=True))
        return _exit_code_for(status)

    # --- Canonical caller-owned SHA formats (never derived from the files) ------
    if not _CANON_SHA.match(str(args.ch2_summary_sha256)):
        return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID,
                        detail="--ch2-summary-sha256 must be sha256:<64 lowercase hex>")
    if not _CANON_SHA.match(str(args.expected_strategy_symbols_sha256)):
        return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID,
                        detail="--expected-strategy-symbols-sha256 must be sha256:<64 lowercase hex>")

    # --- Path identity + occupied-output preflight (BEFORE any read) -----------
    paths = {
        "ch2_summary": args.ch2_summary_json,
        "wrapper": args.ws_bound_plan_wrapper_json,
        "source": args.ws_ticker_evidence_json,
        "symbols": args.expected_strategy_symbols_json,
        "output": args.output_anchor_manifest_json,
    }
    norms = {k: os.path.normcase(os.path.realpath(v)) for k, v in paths.items()}
    if len(set(norms.values())) != len(paths):
        return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID,
                        detail=f"all input/output paths must be pairwise distinct: {norms}")
    if os.path.lexists(args.output_anchor_manifest_json):
        return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS,
                        detail="--output-anchor-manifest-json already exists; refusing to clobber")

    # --- Exact-byte reads (binary, once each) ----------------------------------
    try:
        ch2_summary_bytes = wsbpo.read_source_ws_bytes(args.ch2_summary_json)
        wrapper_bytes = wsbpo.read_source_ws_bytes(args.ws_bound_plan_wrapper_json)
        source_bytes = wsbpo.read_source_ws_bytes(args.ws_ticker_evidence_json)
        symbols_bytes = wsbpo.read_source_ws_bytes(args.expected_strategy_symbols_json)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_INPUT_READ_FAILED, detail=str(exc))

    # --- Pure build + CH1 revalidation -----------------------------------------
    result = bundle.build_ws_review_anchor_bundle(
        ch2_summary_bytes=ch2_summary_bytes,
        expected_ch2_summary_sha256=str(args.ch2_summary_sha256),
        wrapper_artifact_bytes=wrapper_bytes,
        source_ws_artifact_bytes=source_bytes,
        expected_strategy_symbols_bytes=symbols_bytes,
        expected_strategy_symbols_sha256=str(args.expected_strategy_symbols_sha256),
        run_date=str(args.date))
    if not result.passed:
        return _summary(result.status, detail="anchor-bundle build failed; terminal",
                        result=result)

    # --- Publish one race-safe no-clobber manifest (reuse CH2 writer) ----------
    try:
        wsbpo.atomic_write_wrapper(args.output_anchor_manifest_json, result.manifest)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_FAILED, detail=str(exc),
                        result=result)

    # The authoritative SHA is the SHA of the EXACT on-disk bytes (platform newline
    # translation in the text-mode writer means this may differ from the logical bytes).
    try:
        written_bytes = wsbpo.read_source_ws_bytes(args.output_anchor_manifest_json)
    except wsbpo.WsBoundPlanOnlyError as exc:
        return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_FAILED, detail=str(exc),
                        result=result)
    output_sha256 = wb.compute_file_sha256(written_bytes)

    return _summary(bundle.WS_REVIEW_ANCHOR_BUNDLE_PASS,
                    detail="anchor manifest written; preserve output_anchor_manifest_sha256 "
                           "for --ws-bound-plan-anchor-manifest-sha256",
                    result=result, written=True, output_sha256=output_sha256)


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
