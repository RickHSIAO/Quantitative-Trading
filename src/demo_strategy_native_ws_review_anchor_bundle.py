"""TASK-014CH3C1 -- pure, offline builder for a trusted CH3 review ANCHOR MANIFEST.

Given an externally-pinned CH2 Plan-only PASS summary (exact bytes + caller-owned SHA256),
exact CH2 wrapper bytes, exact source-WS evidence bytes, and an INDEPENDENT canonical
50-symbol source (exact bytes + caller-owned SHA256), this module:

  1. pins identity to the external CH2 summary (its SHA + the anchors it carries);
  2. pins the 50-symbol set to the external symbols file (no wrapper-derived symbols);
  3. re-runs the CH1 consumer historical validation using ONLY external anchors;
  4. emits the versioned anchor manifest (the schema the CH3B1 review core consumes),
     its deterministic logical fingerprint, and the literal-file SHA256 the operator must
     preserve and later pass to `--ws-bound-plan-anchor-manifest-sha256`.

Hard scope (CH3C1): PURE and offline. It does NOT run review-only, query market data,
check account margin, or authorize execution. It performs NO file I/O, NO network, NO
WebSocket collection, NO wall-clock read, and imports neither the native-daily runner,
Pilot lifecycle/store, readiness, the execution gate, native execution, a sender, nor
reporting. No artifact defines its own expected identity.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import date as _date  # calendar parsing only; never reads the clock
from typing import Any, Mapping, Sequence

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_bound_plan_consumer as consumer
from src import demo_strategy_native_ws_bound_plan_only as wsbpo  # for the CH2 PASS status
from src import demo_strategy_native_ws_bound_plan_review as wsbpr  # manifest schema + constants
from src import demo_strategy_native_ws_price_binding as wb

TASK_ID = "TASK-014CH3C1"

# Fixed Strategy-native V1 identity (repository-pinned; never from artifacts).
EXPECTED_POLICY_ID = wsbpr.EXPECTED_POLICY_ID
EXPECTED_STRATEGY_ID = wsbpr.EXPECTED_STRATEGY_ID
EXPECTED_STRATEGY_SYMBOL_COUNT = wsbpr.EXPECTED_STRATEGY_SYMBOL_COUNT  # 50
EXPECTED_LONG_COUNT = consumer.EXPECTED_LONG_COUNT  # 25
EXPECTED_SHORT_COUNT = consumer.EXPECTED_SHORT_COUNT  # 25
STRICT_MAX_FRESHNESS_THRESHOLD_MS = wsbpr.STRICT_MAX_FRESHNESS_THRESHOLD_MS  # 10_000

# The trusted CH2 Plan-only PASS status (the builder's external trust source).
CH2_PLAN_ONLY_PASS_STATUS = wsbpo.WS_BOUND_PLAN_ONLY_PASS

ANCHOR_MANIFEST_SCHEMA = wsbpr.ANCHOR_MANIFEST_SCHEMA
ANCHOR_MANIFEST_SCHEMA_VERSION = wsbpr.ANCHOR_MANIFEST_SCHEMA_VERSION

# --- Status vocabulary ------------------------------------------------------
WS_REVIEW_ANCHOR_BUNDLE_PASS = "WS_REVIEW_ANCHOR_BUNDLE_PASS"
WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID = "WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID"
WS_REVIEW_ANCHOR_BUNDLE_SUMMARY_MISMATCH = "WS_REVIEW_ANCHOR_BUNDLE_SUMMARY_MISMATCH"
WS_REVIEW_ANCHOR_BUNDLE_SOURCE_MISMATCH = "WS_REVIEW_ANCHOR_BUNDLE_SOURCE_MISMATCH"
WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED = "WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED"
WS_REVIEW_ANCHOR_BUNDLE_CANONICAL_MISMATCH = "WS_REVIEW_ANCHOR_BUNDLE_CANONICAL_MISMATCH"
WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID = "WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID"
WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS = "WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS"
WS_REVIEW_ANCHOR_BUNDLE_INPUT_READ_FAILED = "WS_REVIEW_ANCHOR_BUNDLE_INPUT_READ_FAILED"
WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_FAILED = "WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_FAILED"

# Required anchor fields the trusted CH2 PASS summary must carry.
_REQUIRED_SUMMARY_FIELDS = (
    "status", "canonical_bound_plan_fingerprint", "source_ws_artifact_sha256",
    "source_ws_artifact_fingerprint", "original_plan_fingerprint",
    "binding_epoch_ns", "freshness_threshold_ms",
)

# Deterministic serialization for the manifest FILE (matches the no-clobber writer:
# json.dump(..., ensure_ascii=False, indent=2, sort_keys=True)).
_FILE_INDENT = 2


@dataclass(frozen=True)
class WsReviewAnchorBundleResult:
    status: str
    blockers: tuple[str, ...]
    manifest: Mapping[str, Any] | None
    manifest_bytes: bytes | None
    manifest_sha256: str | None
    manifest_fingerprint: str | None
    ch2_summary_file_sha256: str | None
    wrapper_file_sha256: str | None
    wrapper_logical_fingerprint: str | None
    source_ws_file_sha256: str | None
    source_ws_logical_fingerprint: str | None
    canonical_bound_plan_fingerprint: str | None
    original_plan_fingerprint: str | None
    expected_symbol_set_fingerprint: str | None
    expected_strategy_symbols_file_sha256: str | None
    run_date: str | None
    binding_epoch_ns: int | None
    freshness_threshold_ms: int | None
    action_count: int | None
    long_count: int | None
    short_count: int | None
    execution_readiness: bool
    pilot_advanced: bool

    @property
    def passed(self) -> bool:
        return self.status == WS_REVIEW_ANCHOR_BUNDLE_PASS


def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _valid_iso_date(value: Any) -> bool:
    if not isinstance(value, str) or len(value) != 10 or value[4] != "-" or value[7] != "-":
        return False
    try:
        _date.fromisoformat(value)
        return True
    except ValueError:
        return False


def _fail(status: str, *blockers: str) -> WsReviewAnchorBundleResult:
    return WsReviewAnchorBundleResult(
        status=status, blockers=tuple(blockers), manifest=None, manifest_bytes=None,
        manifest_sha256=None, manifest_fingerprint=None, ch2_summary_file_sha256=None,
        wrapper_file_sha256=None, wrapper_logical_fingerprint=None,
        source_ws_file_sha256=None, source_ws_logical_fingerprint=None,
        canonical_bound_plan_fingerprint=None, original_plan_fingerprint=None,
        expected_symbol_set_fingerprint=None, expected_strategy_symbols_file_sha256=None,
        run_date=None, binding_epoch_ns=None, freshness_threshold_ms=None,
        action_count=None, long_count=None, short_count=None,
        execution_readiness=False, pilot_advanced=False)


def _parse_symbol_list(parsed: Any) -> list[str] | None:
    """Accept either a JSON array of symbols or an object with ``strategy_symbols``."""
    if isinstance(parsed, list):
        raw = parsed
    elif isinstance(parsed, Mapping) and isinstance(parsed.get("strategy_symbols"), list):
        raw = parsed.get("strategy_symbols")
    else:
        return None
    return list(raw)


def build_ws_review_anchor_bundle(
    *,
    ch2_summary_bytes: bytes,
    expected_ch2_summary_sha256: str,
    wrapper_artifact_bytes: bytes,
    source_ws_artifact_bytes: bytes,
    expected_strategy_symbols_bytes: bytes,
    expected_strategy_symbols_sha256: str,
    run_date: str,
) -> WsReviewAnchorBundleResult:
    """Pure, offline anchor-manifest builder. Returns a result rather than raising for
    JSON-compatible input. Emits the manifest only when every external anchor matches and
    the CH1 historical validation PASSes."""

    # --- Input shape -----------------------------------------------------------
    for name, b in (("ch2_summary_bytes", ch2_summary_bytes),
                    ("wrapper_artifact_bytes", wrapper_artifact_bytes),
                    ("source_ws_artifact_bytes", source_ws_artifact_bytes),
                    ("expected_strategy_symbols_bytes", expected_strategy_symbols_bytes)):
        if not isinstance(b, (bytes, bytearray)):
            return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, f"{name}_not_bytes")
    if not consumer._is_canonical_sha(expected_ch2_summary_sha256):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "expected_ch2_summary_sha256_not_canonical")
    if not consumer._is_canonical_sha(expected_strategy_symbols_sha256):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "expected_strategy_symbols_sha256_not_canonical")
    if not _valid_iso_date(run_date):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "run_date_not_yyyy_mm_dd")

    # --- Trusted CH2 summary (external trust source) ---------------------------
    ch2_summary_sha = wb.compute_file_sha256(bytes(ch2_summary_bytes))
    if ch2_summary_sha != str(expected_ch2_summary_sha256):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SUMMARY_MISMATCH, "ch2_summary_sha256_not_expected")
    try:
        summary = json.loads(bytes(ch2_summary_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "ch2_summary_bytes_invalid_json")
    if not isinstance(summary, Mapping):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "ch2_summary_bytes_not_object")
    missing = [f for f in _REQUIRED_SUMMARY_FIELDS if f not in summary]
    if missing:
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, f"ch2_summary_missing_fields:{missing}")
    if str(summary.get("status", "")) != CH2_PLAN_ONLY_PASS_STATUS:
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SUMMARY_MISMATCH,
                     f"ch2_summary_status_not_pass:{summary.get('status')}")
    for f in ("canonical_bound_plan_fingerprint", "source_ws_artifact_sha256",
              "source_ws_artifact_fingerprint", "original_plan_fingerprint"):
        if not consumer._is_canonical_sha(summary.get(f)):
            return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, f"ch2_summary_{f}_not_canonical")
    epoch = summary.get("binding_epoch_ns")
    if not _is_pos_int(epoch):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "ch2_summary_binding_epoch_ns_invalid")
    threshold = summary.get("freshness_threshold_ms")
    if not (_is_pos_int(threshold) and threshold <= STRICT_MAX_FRESHNESS_THRESHOLD_MS):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "ch2_summary_freshness_threshold_invalid")

    # --- Independent 50-symbol source (external; never wrapper-derived) ---------
    symbols_sha = wb.compute_file_sha256(bytes(expected_strategy_symbols_bytes))
    if symbols_sha != str(expected_strategy_symbols_sha256):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID, "symbols_sha256_not_expected")
    try:
        parsed_syms = json.loads(bytes(expected_strategy_symbols_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID, "symbols_bytes_invalid_json")
    symbols = _parse_symbol_list(parsed_syms)
    if symbols is None or len(symbols) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID, "symbols_not_fifty_list")
    for s in symbols:
        if not isinstance(s, str) or not s or s != s.strip().upper():
            return _fail(WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID, "symbol_not_normalized")
    if len(set(symbols)) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID, "symbols_not_fifty_unique")
    symbol_set_fp = ws.canonical_strategy_symbol_set_fingerprint(symbols)

    # --- Wrapper + source exact bytes ------------------------------------------
    wrapper_sha = wb.compute_file_sha256(bytes(wrapper_artifact_bytes))
    source_sha = wb.compute_file_sha256(bytes(source_ws_artifact_bytes))
    try:
        parsed_wrapper = json.loads(bytes(wrapper_artifact_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "wrapper_bytes_invalid_json")
    if not isinstance(parsed_wrapper, Mapping):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "wrapper_bytes_not_object")
    try:
        parsed_source = json.loads(bytes(source_ws_artifact_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "source_bytes_invalid_json")
    if not isinstance(parsed_source, Mapping):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "source_bytes_not_object")

    source_logical_fp = ws._fingerprint(
        {k: v for k, v in parsed_source.items() if k != "artifact_fingerprint"})
    try:
        wrapper_logical_fp = consumer._recompute_wrapper_fingerprint(parsed_wrapper)
    except (TypeError, ValueError, KeyError):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID, "wrapper_unfingerprintable")

    # Current source identity MUST equal the trusted CH2 summary anchors.
    if source_sha != str(summary.get("source_ws_artifact_sha256")):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SOURCE_MISMATCH, "source_file_sha256_not_summary")
    if source_logical_fp != str(summary.get("source_ws_artifact_fingerprint")):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_SOURCE_MISMATCH, "source_logical_fingerprint_not_summary")

    # --- CH1 historical revalidation (external anchors only) -------------------
    ch1 = consumer.validate_ws_bound_plan_artifact(
        parsed_wrapper,
        source_ws_artifact=parsed_source,
        expected_policy_id=EXPECTED_POLICY_ID,
        expected_strategy_id=EXPECTED_STRATEGY_ID,
        expected_run_date=run_date,
        expected_original_plan_fingerprint=str(summary.get("original_plan_fingerprint")),
        expected_ws_artifact_sha256=str(summary.get("source_ws_artifact_sha256")),
        expected_ws_artifact_fingerprint=str(summary.get("source_ws_artifact_fingerprint")),
        expected_binding_epoch_ns=int(epoch),
        expected_freshness_threshold_ms=int(threshold),
        expected_symbols=symbols)
    if not ch1.passed:
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED, ch1.status, *ch1.failure_codes[:20])
    if ch1.canonical_bound_plan_fingerprint != str(summary.get("canonical_bound_plan_fingerprint")):
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_CANONICAL_MISMATCH,
                     "canonical_bound_plan_fingerprint_not_summary")
    actions = ch1.validated_actions
    if len(actions) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED,
                     f"validated_action_count_not_fifty:{len(actions)}")
    long_n = sum(1 for a in actions if str(a.side) == "long")
    short_n = sum(1 for a in actions if str(a.side) == "short")
    if long_n != EXPECTED_LONG_COUNT or short_n != EXPECTED_SHORT_COUNT:
        return _fail(WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED,
                     f"long_short_not_25_25:long={long_n},short={short_n}")

    # --- Build the anchor manifest (references + anchors; no Plan/wrapper) ------
    manifest: dict[str, Any] = {
        "schema": ANCHOR_MANIFEST_SCHEMA,
        "schema_version": ANCHOR_MANIFEST_SCHEMA_VERSION,
        "policy_id": EXPECTED_POLICY_ID,
        "strategy_id": EXPECTED_STRATEGY_ID,
        "run_date": run_date,
        "original_plan_fingerprint": str(summary.get("original_plan_fingerprint")),
        "source_ws_artifact_sha256": str(summary.get("source_ws_artifact_sha256")),
        "source_ws_artifact_fingerprint": str(summary.get("source_ws_artifact_fingerprint")),
        "canonical_bound_plan_fingerprint": ch1.canonical_bound_plan_fingerprint,
        # Available + verified-consistent (CH1 recomputed it); pins the wrapper via the
        # externally-preserved manifest. Optional for the CH3B1 core.
        "wrapper_fingerprint": wrapper_logical_fp,
        "binding_epoch_ns": int(epoch),
        "freshness_threshold_ms": int(threshold),
        "strategy_symbols": list(symbols),
        "expected_symbol_set_fingerprint": symbol_set_fp,
        # Source-summary provenance (file SHAs only; no embedded artifacts).
        "ch2_summary_file_sha256": ch2_summary_sha,
        "wrapper_file_sha256": wrapper_sha,
        "source_file_sha256": source_sha,
        "strategy_symbols_file_sha256": symbols_sha,
        "builder_task_id": TASK_ID,
    }
    manifest["manifest_fingerprint"] = ws._fingerprint(
        {k: v for k, v in manifest.items() if k != "manifest_fingerprint"})

    # Deterministic FILE bytes (identical to the no-clobber writer's serialization).
    manifest_bytes = json.dumps(manifest, ensure_ascii=False, indent=_FILE_INDENT,
                                sort_keys=True).encode("utf-8")
    manifest_sha = wb.compute_file_sha256(manifest_bytes)

    return WsReviewAnchorBundleResult(
        status=WS_REVIEW_ANCHOR_BUNDLE_PASS, blockers=(),
        manifest=manifest, manifest_bytes=manifest_bytes, manifest_sha256=manifest_sha,
        manifest_fingerprint=manifest["manifest_fingerprint"],
        ch2_summary_file_sha256=ch2_summary_sha,
        wrapper_file_sha256=wrapper_sha, wrapper_logical_fingerprint=wrapper_logical_fp,
        source_ws_file_sha256=source_sha, source_ws_logical_fingerprint=source_logical_fp,
        canonical_bound_plan_fingerprint=ch1.canonical_bound_plan_fingerprint,
        original_plan_fingerprint=str(summary.get("original_plan_fingerprint")),
        expected_symbol_set_fingerprint=symbol_set_fp,
        expected_strategy_symbols_file_sha256=symbols_sha,
        run_date=run_date, binding_epoch_ns=int(epoch), freshness_threshold_ms=int(threshold),
        action_count=len(actions), long_count=long_n, short_count=short_n,
        execution_readiness=False, pilot_advanced=False)


__all__ = [
    "TASK_ID", "ANCHOR_MANIFEST_SCHEMA", "ANCHOR_MANIFEST_SCHEMA_VERSION",
    "EXPECTED_POLICY_ID", "EXPECTED_STRATEGY_ID", "EXPECTED_STRATEGY_SYMBOL_COUNT",
    "STRICT_MAX_FRESHNESS_THRESHOLD_MS", "CH2_PLAN_ONLY_PASS_STATUS",
    "WS_REVIEW_ANCHOR_BUNDLE_PASS", "WS_REVIEW_ANCHOR_BUNDLE_INPUT_INVALID",
    "WS_REVIEW_ANCHOR_BUNDLE_SUMMARY_MISMATCH", "WS_REVIEW_ANCHOR_BUNDLE_SOURCE_MISMATCH",
    "WS_REVIEW_ANCHOR_BUNDLE_CONSUMER_FAILED", "WS_REVIEW_ANCHOR_BUNDLE_CANONICAL_MISMATCH",
    "WS_REVIEW_ANCHOR_BUNDLE_SYMBOL_SOURCE_INVALID", "WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_EXISTS",
    "WS_REVIEW_ANCHOR_BUNDLE_INPUT_READ_FAILED", "WS_REVIEW_ANCHOR_BUNDLE_OUTPUT_FAILED",
    "WsReviewAnchorBundleResult", "build_ws_review_anchor_bundle",
]
