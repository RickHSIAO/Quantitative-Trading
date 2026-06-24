"""TASK-014CH1 (+_FIX1, _FIX2) -- pure, offline consumer contract for the canonical
WebSocket-bound Strategy-native Plan artifact.

This module VALIDATES (and only validates) the canonical bound-plan wrapper produced
by ``src/demo_strategy_native_ws_price_binding.build_ws_bound_plan_artifact`` /
``scripts/bind_plan_prices_to_ws_evidence.py``. It is the read-side contract a LATER
integration task (CH2) would call before trusting a WebSocket-bound Plan.

Hard scope (CH1):

  * It does NOT wire the artifact into the daily runner, readiness, execution gate,
    margin audit, or native execution. It changes no runtime behaviour.
  * Its validation core is PURE and deterministic (no network, no file, no clock,
    no global state). Only :func:`load_ws_bound_plan_artifact` touches the filesystem.
  * It imports neither a sender, an execution module, the live ``BybitExecutor``,
    ``main`` nor ``src.risk``. It cannot place / amend / cancel an order, cannot
    mutate Pilot state, and contains no order-endpoint string.
  * It NEVER falls back to the original REST Plan: execution-grade freshness is
    reported complete ONLY when a fully validated WS-bound Plan passes every check.

FIX1 hardening: total fail-closed behaviour (never raises for a JSON-compatible
Mapping), full per-symbol fingerprint recomputation (source-message + post-binding
action), provenance cross-checks vs caller ground truth.

FIX2 hardening:

  * SIGNED Strategy-native V1 semantics: long => weight +0.02 / notional +200;
    short => weight -0.02 / notional -200; notional == weight * 10,000 (signed);
    side, weight sign and notional sign must all agree. No absolute-value-only
    acceptance. Quantity still derives from |notional| (binder convention).
  * Externally-anchored WS artifact fingerprint: the caller supplies the expected
    WS ``artifact_fingerprint``; it must equal the wrapper copy, the canonical bound
    Plan copy, AND every action's ``price_evidence.source_artifact_fingerprint``
    (the expected value is never derived from the wrapper itself).
  * Required, non-null, correctly-typed, semantically-valid execution-grade
    price-evidence fields per action (a generic ``None``-tolerant type check is no
    longer sufficient for a required field).

FIX3 hardening (temporal / freshness integrity):

  * Caller-anchored temporal expectations ``expected_binding_epoch_ns`` and
    ``expected_freshness_threshold_ms`` (never derived from the wrapper). The
    threshold must be positive and must not exceed the producer's strict maximum
    (``DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS`` = 10_000 ms) and must equal the
    stored threshold fields; the binding epoch must equal the canonical / wrapper
    binding-epoch copies.
  * Binding-time freshness is INDEPENDENTLY recomputed per action from the caller
    binding epoch + the fingerprint-verified exchange ``source_ts``, using the
    producer's threshold + 5_000 ms future tolerance. Stale / future evidence is
    rejected even when every stored FRESH/COMPLETE field is retained; the stored
    age is cross-checked within the producer's bounded clock-offset tolerance.
  * ``local_received_at_utc`` is parsed as a real tz-aware UTC ISO-8601 instant
    (naive / non-UTC / invalid rejected) and must represent the same instant as
    ``local_received_epoch_ns``.
  * ``message_type`` must be one of the producer's real values (snapshot / delta).
  * Caller-supplied fingerprints/sha256 must be canonical ``sha256:<64 hex>``.

  The validator performs NO wall-clock / current-time read; all temporal anchors
  are caller-supplied and all evidence timestamps come from the artifact.

FIX4 hardening (source WS artifact cross-validation):

  * The original source WS evidence artifact is now a REQUIRED parameter. It is
    independently validated with the producer's own ``validate_ws_artifact_compatibility``
    gate (schema, canonical-binding sub-schema, COMPLETE status, 52-symbol coverage,
    public unauthenticated linear endpoint, ACK / control-plane / counter parity,
    authoritative policy/strategy/date/symbol + clock-offset provenance, no
    execution/order activity) and anchored to the caller fingerprint/sha.
  * The producer-authoritative clock offset is extracted from that artifact and the
    EXACT producer freshness formula is applied via ``wb._evaluate_binding_freshness``
    (no offset-free approximation; future tolerance is not used as an offset
    tolerance). Stored ``evidence_age_at_binding_ms`` must equal the recomputation.
  * Every bound action's price evidence is proven to BELONG to the source artifact:
    each field is compared to the unique per-symbol source record and the record's
    own evidence + source-message fingerprints are recomputed with producer helpers.
"""

from __future__ import annotations

import json
import re
from dataclasses import dataclass
from datetime import datetime, timedelta
from decimal import Decimal
from pathlib import Path
from typing import Any, Mapping, Sequence

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb

TASK_ID = "TASK-014CH1_FIX4"

EXPECTED_STRATEGY_SYMBOL_COUNT = wb.EXPECTED_STRATEGY_SYMBOL_COUNT  # 50
EXPECTED_LONG_COUNT = 25
EXPECTED_SHORT_COUNT = 25

# Strategy-native V1 fixed SIGNED semantics (preserved; never inferred).
V1_CAPITAL_BASE_USD = Decimal("10000")
V1_LONG_TARGET_WEIGHT = Decimal("0.02")
V1_SHORT_TARGET_WEIGHT = Decimal("-0.02")
V1_LONG_TARGET_NOTIONAL_USD = Decimal("200")
V1_SHORT_TARGET_NOTIONAL_USD = Decimal("-200")
V1_ABS_TARGET_WEIGHT = Decimal("0.02")
V1_ABS_TARGET_NOTIONAL_USD = Decimal("200")

# Producer temporal contract (reused; never loosened).
STRICT_MAX_FRESHNESS_THRESHOLD_MS = wb.DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS  # 10_000
FUTURE_TOLERANCE_MS = wb.DEFAULT_FUTURE_TOLERANCE_MS  # 5_000
ALLOWED_MESSAGE_TYPES = frozenset({"snapshot", "delta"})
_CANONICAL_SHA_RE = re.compile(r"^sha256:[0-9a-f]{64}$")
# Tolerance (seconds) for the UTC-string vs epoch-ns instant comparison; the
# producer emits microsecond-precision UTC strings, so 1 ms is comfortably exact.
_UTC_EPOCH_TOLERANCE_S = 0.001

# --- Status vocabulary ------------------------------------------------------
WS_BOUND_PLAN_CONSUMER_PASS = "WS_BOUND_PLAN_CONSUMER_PASS"

WS_BOUND_PLAN_SCHEMA_INVALID = "WS_BOUND_PLAN_SCHEMA_INVALID"
WS_BOUND_PLAN_WRAPPER_FINGERPRINT_MISMATCH = "WS_BOUND_PLAN_WRAPPER_FINGERPRINT_MISMATCH"
WS_BOUND_PLAN_FINGERPRINT_MISMATCH = "WS_BOUND_PLAN_FINGERPRINT_MISMATCH"
WS_BOUND_PLAN_PROVENANCE_MISMATCH = "WS_BOUND_PLAN_PROVENANCE_MISMATCH"
WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH = "WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH"
WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH = "WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH"
WS_BOUND_PLAN_SYMBOL_SET_MISMATCH = "WS_BOUND_PLAN_SYMBOL_SET_MISMATCH"
WS_BOUND_PLAN_DUPLICATE_SYMBOL = "WS_BOUND_PLAN_DUPLICATE_SYMBOL"
WS_BOUND_PLAN_INCOMPLETE = "WS_BOUND_PLAN_INCOMPLETE"
WS_BOUND_PLAN_STALE = "WS_BOUND_PLAN_STALE"
WS_BOUND_PLAN_PARITY_FAIL = "WS_BOUND_PLAN_PARITY_FAIL"
WS_BOUND_PLAN_ACTION_INCONSISTENT = "WS_BOUND_PLAN_ACTION_INCONSISTENT"
WS_BOUND_PLAN_AUTHORIZATION_PRESENT = "WS_BOUND_PLAN_AUTHORIZATION_PRESENT"

# Single-status resolution priority (most fundamental failure wins).
_STATUS_PRIORITY: tuple[str, ...] = (
    WS_BOUND_PLAN_SCHEMA_INVALID,
    WS_BOUND_PLAN_WRAPPER_FINGERPRINT_MISMATCH,
    WS_BOUND_PLAN_FINGERPRINT_MISMATCH,
    WS_BOUND_PLAN_INCOMPLETE,
    WS_BOUND_PLAN_PARITY_FAIL,
    WS_BOUND_PLAN_STALE,
    WS_BOUND_PLAN_PROVENANCE_MISMATCH,
    WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH,
    WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH,
    WS_BOUND_PLAN_SYMBOL_SET_MISMATCH,
    WS_BOUND_PLAN_DUPLICATE_SYMBOL,
    WS_BOUND_PLAN_ACTION_INCONSISTENT,
    WS_BOUND_PLAN_AUTHORIZATION_PRESENT,
)

# Authorization / dispatch fields that MUST remain false / zero in the wrapper.
_FALSE_REQUIRED_FIELDS: tuple[str, ...] = (
    "execution_batch_authorized",
    "execution_ready",
    "sender_reachable",
    "execution_authorization_marker_created",
)
_ZERO_REQUIRED_FIELDS: tuple[str, ...] = (
    "execute_daily_native_call_count",
    "transport_sender_call_count",
    "order_post_count",
    "amend_post_count",
    "cancel_post_count",
    "live_order_post_count",
)
_ZERO_REQUIRED_NETWORK_FIELDS: tuple[str, ...] = (
    "private_http_count",
    "public_http_count",
    "websocket_connection_count",
    "order_endpoint_count",
)

# Required execution-grade price-evidence fields (non-null + typed + semantic).
_REQ_EVIDENCE_STR_FIELDS: tuple[str, ...] = (
    "selected_price", "message_type", "local_received_at_utc",
    "source_message_fingerprint", "source_artifact_fingerprint", "source_artifact_sha256",
)
_REQ_EVIDENCE_INT_POS_FIELDS: tuple[str, ...] = (
    "exchange_data_generated_ts_ms", "local_received_epoch_ns",
)
_REQ_EVIDENCE_INT_NONNEG_FIELDS: tuple[str, ...] = (
    "cross_sequence", "connection_generation", "local_monotonic_received_ns",
)


class WsBoundPlanConsumerError(ValueError):
    """Raised for a structurally unusable input to the consumer (fail closed)."""


@dataclass(frozen=True)
class ValidatedBoundAction:
    """One independently re-verified canonical bound-plan target position."""
    symbol: str
    side: str
    target_weight: str | None
    price: str | None
    qty: str | None
    qty_step: str | None
    target_notional: str | None
    effective_notional: str | None
    source_message_fingerprint: str | None
    action_fingerprint: str | None
    action_price_binding_status: str | None


@dataclass(frozen=True)
class BoundPlanConsumerResult:
    """Immutable verdict of validating a canonical WS-bound Plan wrapper.

    ``validated_actions`` is non-empty ONLY when ``status`` is the single PASS
    status; every other field is informational and never authorizes execution."""
    status: str
    failure_codes: tuple[str, ...]
    provenance_verified: bool
    canonical_plan_available: bool
    canonical_bound_plan_fingerprint: str | None
    source_ws_artifact_sha256: str | None
    original_plan_fingerprint: str | None
    execution_grade_freshness_complete: bool
    validated_actions: tuple[ValidatedBoundAction, ...]
    blockers: tuple[str, ...]

    @property
    def passed(self) -> bool:
        return self.status == WS_BOUND_PLAN_CONSUMER_PASS and not self.failure_codes


# ---------------------------------------------------------------------------
# Small defensive helpers (keep the validator total / non-raising)
# ---------------------------------------------------------------------------

def _as_map(value: Any) -> Mapping[str, Any]:
    return value if isinstance(value, Mapping) else {}


def _as_list(value: Any) -> list[Any]:
    return list(value) if isinstance(value, (list, tuple)) else []


def _is_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool)


def _nonempty_str(value: Any) -> bool:
    return isinstance(value, str) and bool(value.strip())


def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _is_canonical_sha(value: Any) -> bool:
    return isinstance(value, str) and bool(_CANONICAL_SHA_RE.match(value))


def _parse_utc_iso(value: Any) -> tuple[datetime | None, str | None]:
    """Parse a producer UTC ISO-8601 timestamp. Returns ``(datetime, None)`` for a
    valid tz-aware UTC instant, else ``(None, reason)``. Rejects naive and non-UTC
    timestamps and invalid calendar/time values. Reads no current time."""
    if not isinstance(value, str) or not value.strip():
        return None, "missing"
    txt = value.strip()
    iso = (txt[:-1] + "+00:00") if txt.endswith(("Z", "z")) else txt
    try:
        dt = datetime.fromisoformat(iso)
    except ValueError:
        return None, "invalid"
    if dt.tzinfo is None or dt.utcoffset() is None:
        return None, "naive"
    if dt.utcoffset() != timedelta(0):
        return None, "non_utc"
    return dt, None


# ---------------------------------------------------------------------------
# File loading (the ONLY impure surface; kept out of the validation core)
# ---------------------------------------------------------------------------

def load_ws_bound_plan_artifact(path: Path | str) -> Mapping[str, Any]:
    """Read a canonical WS-bound Plan wrapper artifact from a local JSON file.

    Performs no network call and no validation -- pass the result to
    :func:`validate_ws_bound_plan_artifact`. Raises :class:`WsBoundPlanConsumerError`
    when the file is unreadable or is not a JSON object."""
    p = Path(path)
    try:
        raw = p.read_text(encoding="utf-8")
    except OSError as exc:
        raise WsBoundPlanConsumerError(f"artifact unreadable: {exc}") from exc
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise WsBoundPlanConsumerError(f"artifact is not valid JSON: {exc}") from exc
    if not isinstance(data, Mapping):
        raise WsBoundPlanConsumerError("artifact JSON root is not an object")
    return data


# ---------------------------------------------------------------------------
# Independent fingerprint recomputation (reuse producer helpers; no new algo)
# ---------------------------------------------------------------------------

def _recompute_wrapper_fingerprint(artifact: Mapping[str, Any]) -> str:
    return wb._fingerprint({k: v for k, v in artifact.items()
                            if k != "wrapper_fingerprint"})


def _recompute_canonical_bound_plan_fingerprint(cbp: Mapping[str, Any]) -> str:
    """Reconstruct the EXACT fingerprint material the binder used (see
    ``demo_strategy_native_ws_price_binding._build_revised_plan``) and recompute it
    with the binder's own fingerprint function -- no second algorithm."""
    review = _as_map(cbp.get("rebuilt_price_dependent_review"))
    targets = _as_list(_as_map(cbp.get("planner")).get("target_positions"))
    fp_material = {
        "active_policy": cbp.get("active_policy"),
        "active_strategy": cbp.get("active_strategy"),
        "requested_strategy_date": cbp.get("requested_strategy_date"),
        "binding_epoch_ns": cbp.get("binding_epoch_ns"),
        "source_ws_artifact_fingerprint": cbp.get("source_ws_artifact_fingerprint"),
        "source_ws_artifact_sha256": cbp.get("source_ws_artifact_sha256"),
        "projected_margin_model_status": review.get("projected_margin_model_status"),
        "strategy_gross_notional": review.get("strategy_gross_notional"),
        "target_positions": [
            {"symbol": t.get("symbol"), "side": t.get("side"),
             "target_weight": t.get("target_weight"),
             "price": t.get("price"), "qty": t.get("qty"),
             "qty_step": t.get("qty_step"),
             "target_notional": t.get("target_notional"),
             "effective_notional": t.get("effective_notional"),
             "source_message_fingerprint": _as_map(t.get("price_evidence")).get(
                 "source_message_fingerprint"),
             "action_price_binding_status": t.get("action_price_binding_status")}
            for t in (dict(_as_map(t)) for t in targets)],
    }
    return wb._fingerprint(fp_material)


def _recompute_source_message_fingerprint(symbol: Any, pe: Mapping[str, Any]) -> str:
    """Independently recompute the source-message fingerprint from the price-evidence
    fields the artifact carries, using the WS module's canonical function."""
    return ws.canonical_source_message_fingerprint(
        symbol=symbol,
        topic=pe.get("topic"),
        selected_price_field=pe.get("selected_price_field"),
        selected_price=pe.get("selected_price"),
        source_message_type=pe.get("message_type"),
        source_ts_ms=pe.get("exchange_data_generated_ts_ms"),
        source_cs=pe.get("cross_sequence"),
        local_received_epoch_ns=pe.get("local_received_epoch_ns"),
        local_received_at_utc=pe.get("local_received_at_utc"),
        local_monotonic_received_ns=pe.get("local_monotonic_received_ns"),
        connection_generation=pe.get("connection_generation"))


def _recompute_action_fingerprint(tp: Mapping[str, Any], pe: Mapping[str, Any]) -> str:
    """Recompute the post-binding action fingerprint exactly as the binder did
    (``_bind_one_action`` ``post_fp`` material), with the binder's fingerprint fn."""
    return wb._fingerprint({
        "symbol": str(tp.get("symbol", "")).strip().upper(),
        "side": tp.get("side"),
        "target_weight": tp.get("target_weight"),
        "price": tp.get("price"),
        "target_notional": wb._canon_dec_str(wb._dec(tp.get("target_notional"))),
        "qty": tp.get("qty"),
        "qty_step": tp.get("qty_step"),
        "price_source": wb.WS_SOURCE_TYPE,
        "source_message_fingerprint": pe.get("source_message_fingerprint")})


# ---------------------------------------------------------------------------
# Per-action validation (fail closed; one bad action == ACTION_INCONSISTENT)
# ---------------------------------------------------------------------------

def _validate_evidence_fields(sym: str, pe: Mapping[str, Any]) -> list[str]:
    """Require non-null, correctly typed and semantically valid execution-grade
    price-evidence. A required field is NEVER accepted merely because ``None`` would
    satisfy a generic type helper."""
    probs: list[str] = []
    topic = pe.get("topic")
    if not isinstance(topic, str) or topic != f"tickers.{sym}":
        probs.append(f"{sym}:evidence_topic_invalid:topic")
    spf = pe.get("selected_price_field")
    if not isinstance(spf, str) or spf != wb.PLANNER_PRICE_FIELD:
        probs.append(f"{sym}:evidence_selected_price_field_invalid:selected_price_field")
    if str(pe.get("source_type", "")) != wb.WS_SOURCE_TYPE:
        probs.append(f"{sym}:evidence_source_type_invalid:source_type")
    for f in _REQ_EVIDENCE_STR_FIELDS:
        if not _nonempty_str(pe.get(f)):
            probs.append(f"{sym}:evidence_field_missing_or_invalid:{f}")
    for f in _REQ_EVIDENCE_INT_POS_FIELDS:
        v = pe.get(f)
        if not _is_int(v) or v <= 0:
            probs.append(f"{sym}:evidence_field_missing_or_invalid:{f}")
    for f in _REQ_EVIDENCE_INT_NONNEG_FIELDS:
        v = pe.get(f)
        if not _is_int(v) or v < 0:
            probs.append(f"{sym}:evidence_field_missing_or_invalid:{f}")
    # Message type must be one of the producer's real values (snapshot / delta).
    mt = pe.get("message_type")
    if not isinstance(mt, str) or mt not in ALLOWED_MESSAGE_TYPES:
        probs.append(f"{sym}:evidence_message_type_unsupported:message_type")
    return probs


def _check_utc(sym: str, pe: Mapping[str, Any]) -> list[str]:
    """UTC timestamp semantics: ``local_received_at_utc`` must be a tz-aware UTC
    ISO-8601 instant equal to ``local_received_epoch_ns`` (only checked when present;
    an absent field is an evidence failure handled elsewhere). No wall-clock read."""
    probs: list[str] = []
    at_utc = pe.get("local_received_at_utc")
    epoch_ns = pe.get("local_received_epoch_ns")
    if isinstance(at_utc, str) and at_utc.strip():
        dt, reason = _parse_utc_iso(at_utc)
        if reason is not None:
            probs.append(f"{sym}:local_received_at_utc_{reason}")
        elif _is_pos_int(epoch_ns):
            if abs(dt.timestamp() - (epoch_ns / 1e9)) > _UTC_EPOCH_TOLERANCE_S:
                probs.append(f"{sym}:utc_epoch_instant_mismatch")
    return probs


def extract_authoritative_clock_offset(
    source_ws_artifact: Mapping[str, Any], *, expected_ws_artifact_sha256: str,
) -> tuple[Decimal | None, list[str]]:
    """Extract the producer-authoritative clock offset from the validated source WS
    artifact. Returns ``(Decimal | None, problems)``; the offset is returned only when
    every requirement holds. Reuses producer constants and Decimal parsing."""
    probs: list[str] = []
    src = _as_map(source_ws_artifact)
    if str(src.get("clock_offset_status", "")) != ws.CLOCK_OFFSET_AVAILABLE:
        probs.append("clock_offset_status_not_available")
    if str(src.get("clock_offset_provenance_status", "")) != ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE:
        probs.append("clock_offset_provenance_not_authoritative")
    offset = wb._dec(src.get("clock_offset_seconds"))
    if offset is None:
        probs.append("clock_offset_seconds_not_finite_decimal")
    # Duplicated nested provenance fields, where the producer schema emits them.
    prov = src.get("clock_offset_provenance")
    if isinstance(prov, Mapping) and prov:
        nested = wb._dec(prov.get("estimated_local_vs_exchange_clock_offset_seconds"))
        if offset is None or nested is None or nested != offset:
            probs.append("clock_offset_duplicate_fields_disagree")
        if str(prov.get("clock_offset_provenance_status", "")) != \
                ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE:
            probs.append("clock_offset_provenance_block_not_authoritative")
        nsha = prov.get("clock_offset_source_artifact_sha256")
        if nsha is not None and str(nsha) != str(expected_ws_artifact_sha256):
            probs.append("clock_offset_source_artifact_sha256_mismatch")
    return (offset if not probs else None), probs


def _check_source_record(
    sym: str, tp: Mapping[str, Any], rec: Any, *,
    clock_offset: Decimal | None, caller_epoch_ns: int | None, caller_threshold_ms: int | None,
) -> dict[str, list[str]]:
    """Prove the bound action's price evidence actually belongs to its source WS
    per-symbol record, and recompute freshness with the EXACT producer formula +
    authoritative offset. Returns ``{"ws": [...], "temporal": [...]}``. Never raises."""
    out: dict[str, list[str]] = {"ws": [], "temporal": []}
    if not isinstance(rec, Mapping):
        out["ws"].append(f"{sym}:source_symbol_missing")
        return out
    try:
        pe = _as_map(tp.get("price_evidence"))
        if str(rec.get("symbol", "")).strip().upper() != sym:
            out["ws"].append(f"{sym}:source_record_symbol_mismatch")
        if str(rec.get("evidence_status", "")) != ws.WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE:
            out["ws"].append(f"{sym}:source_record_not_evidence_complete")
        # Field-for-field membership: the bound evidence must equal the source record.
        membership = [
            ("topic", rec.get("topic"), pe.get("topic")),
            ("selected_price_field", rec.get("selected_price_field"), pe.get("selected_price_field")),
            ("selected_price", rec.get("selected_price"), pe.get("selected_price")),
            ("message_type", rec.get("selected_price_source_message_type"), pe.get("message_type")),
            ("exchange_ts_ms", rec.get("selected_price_source_ts_ms"),
             pe.get("exchange_data_generated_ts_ms")),
            ("cross_sequence", rec.get("selected_price_source_cs"), pe.get("cross_sequence")),
            ("local_received_epoch_ns", rec.get("selected_price_source_local_received_epoch_ns"),
             pe.get("local_received_epoch_ns")),
            ("local_received_at_utc", rec.get("selected_price_source_local_received_at_utc"),
             pe.get("local_received_at_utc")),
            ("local_monotonic_received_ns",
             rec.get("selected_price_source_local_monotonic_received_ns"),
             pe.get("local_monotonic_received_ns")),
            ("connection_generation", rec.get("selected_price_source_connection_generation"),
             pe.get("connection_generation")),
            ("source_message_fingerprint", rec.get("selected_price_source_message_fingerprint"),
             pe.get("source_message_fingerprint")),
        ]
        for name, src_v, pe_v in membership:
            if src_v != pe_v:
                out["ws"].append(f"{sym}:source_record_mismatch:{name}")
        # Independently recompute the source record's own fingerprints (producer fns).
        if wb._recompute_evidence_fingerprint(rec) != rec.get("evidence_fingerprint"):
            out["ws"].append(f"{sym}:source_evidence_fingerprint_mismatch")
        recomputed_smf = ws.canonical_source_message_fingerprint(
            symbol=rec.get("symbol"), topic=rec.get("topic"),
            selected_price_field=rec.get("selected_price_field"),
            selected_price=rec.get("selected_price"),
            source_message_type=rec.get("selected_price_source_message_type"),
            source_ts_ms=rec.get("selected_price_source_ts_ms"),
            source_cs=rec.get("selected_price_source_cs"),
            local_received_epoch_ns=rec.get("selected_price_source_local_received_epoch_ns"),
            local_received_at_utc=rec.get("selected_price_source_local_received_at_utc"),
            local_monotonic_received_ns=rec.get(
                "selected_price_source_local_monotonic_received_ns"),
            connection_generation=rec.get("selected_price_source_connection_generation"))
        if recomputed_smf != rec.get("selected_price_source_message_fingerprint"):
            out["ws"].append(f"{sym}:source_record_source_message_fingerprint_mismatch")

        # EXACT authoritative-offset freshness via the producer's own function.
        if (clock_offset is not None and caller_epoch_ns is not None
                and caller_threshold_ms is not None):
            fr = wb._evaluate_binding_freshness(
                rec, binding_epoch_ns=caller_epoch_ns, clock_offset_seconds=clock_offset,
                threshold_ms=caller_threshold_ms, future_tolerance_ms=wb.DEFAULT_FUTURE_TOLERANCE_MS)
            if fr["binding_freshness_status"] != wb.BINDING_FRESHNESS_FRESH:
                out["temporal"].append(
                    f"{sym}:authoritative_freshness_{fr['binding_freshness_status']}:{fr.get('reason')}")
            bf = _as_map(tp.get("binding_freshness"))
            if str(bf.get("binding_freshness_status", "")) != wb.BINDING_FRESHNESS_FRESH:
                out["temporal"].append(f"{sym}:stored_binding_status_not_fresh")
            if bf.get("binding_freshness_threshold_ms") != caller_threshold_ms:
                out["temporal"].append(f"{sym}:stored_threshold_not_expected")
            # Stored age must EQUAL the exact recomputation (producer precision).
            if bf.get("evidence_age_at_binding_ms") != fr.get("evidence_age_at_binding_ms"):
                out["temporal"].append(f"{sym}:stored_age_differs_from_authoritative_recompute")
    except Exception as exc:  # noqa: BLE001  (narrow: per-symbol only, fail closed)
        out["ws"].append(f"{sym}:source_record_validation_error:{type(exc).__name__}")
    return out


def _check_action(tp_raw: Any, *, expected_ws_fp: str, expected_ws_sha: str) -> dict[str, list[str]]:
    """Independently validate one canonical bound action.

    Returns a dict with three problem lists: ``action`` (evidence / price / qty /
    notional / V1-semantics / fingerprint inconsistencies), ``ws`` (per-symbol
    source-WS provenance mismatches against the caller-anchored fingerprint/sha) and
    ``temporal`` (UTC/epoch integrity). Never raises -- a narrow guard converts any
    unexpected error into an action inconsistency for this symbol only."""
    out: dict[str, list[str]] = {"action": [], "ws": [], "temporal": []}
    tp = _as_map(tp_raw)
    sym = str(tp.get("symbol", "")).strip().upper()
    try:
        if not sym:
            out["action"].append("<unknown>:symbol_missing")
        pe_raw = tp.get("price_evidence")
        if not isinstance(pe_raw, Mapping):
            out["action"].append(f"{sym or '<unknown>'}:price_evidence_absent_or_malformed")
            return out
        pe = pe_raw

        # Required execution-grade evidence (non-null, typed, semantic).
        out["action"].extend(_validate_evidence_fields(sym or "<unknown>", pe))

        # Active price provenance.
        if tp.get("price") != pe.get("selected_price"):
            out["action"].append(f"{sym}:active_price_not_selected_price")
        if str(tp.get("price_source", "")) != wb.WS_SOURCE_TYPE:
            out["action"].append(f"{sym}:price_source_not_websocket")
        if str(tp.get("action_price_binding_status", "")) != \
                wb.WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE:
            out["action"].append(f"{sym}:binding_status_not_complete")

        # Numeric parse + bounds (validate BEFORE any qty recomputation).
        price = wb._dec(tp.get("price"))
        notional = wb._dec(tp.get("target_notional"))
        qty_step = wb._dec(tp.get("qty_step"))
        stored_qty = wb._dec(tp.get("qty"))
        eff = wb._dec(tp.get("effective_notional"))
        if price is None or price <= 0:
            out["action"].append(f"{sym}:price_not_positive")
        if notional is None:
            out["action"].append(f"{sym}:target_notional_unparseable")
        if qty_step is None or qty_step <= 0:
            out["action"].append(f"{sym}:qty_step_missing_or_not_positive")
        if stored_qty is None or stored_qty < 0:
            out["action"].append(f"{sym}:qty_unparseable_or_negative")
        if eff is None or eff < 0:
            out["action"].append(f"{sym}:effective_notional_unparseable_or_negative")

        # Recompute qty / effective notional ONLY with a valid price + qty_step;
        # quantity uses ABSOLUTE notional (matches the binder convention).
        if (price is not None and price > 0 and notional is not None
                and qty_step is not None and qty_step > 0):
            expected_qty = wb._floor_qty(notional.copy_abs(), price, qty_step)
            if wb._canon_dec_str(expected_qty) != tp.get("qty"):
                out["action"].append(f"{sym}:rounded_qty_inconsistent")
            if wb._canon_dec_str(expected_qty * price) != tp.get("effective_notional"):
                out["action"].append(f"{sym}:effective_notional_inconsistent")
            if (expected_qty % qty_step) != 0:
                out["action"].append(f"{sym}:qty_not_step_multiple")
            if not expected_qty > 0:
                out["action"].append(f"{sym}:qty_not_positive")

        # Strategy-native V1 SIGNED weight / notional / direction semantics.
        weight = wb._dec(tp.get("target_weight"))
        side = str(tp.get("side", "")).strip().lower()
        if side not in ("long", "short"):
            out["action"].append(f"{sym}:side_not_long_or_short")
        if weight is None or weight == 0:
            out["action"].append(f"{sym}:target_weight_zero_or_unparseable")
        else:
            if weight.copy_abs() != V1_ABS_TARGET_WEIGHT:
                out["action"].append(f"{sym}:target_weight_not_pm_0.02")
            # side <-> weight sign agreement.
            if (side == "long" and weight < 0) or (side == "short" and weight > 0):
                out["action"].append(f"{sym}:side_weight_mismatch")
        if notional is not None:
            if notional.copy_abs() != V1_ABS_TARGET_NOTIONAL_USD:
                out["action"].append(f"{sym}:target_notional_magnitude_not_200")
            # side <-> notional sign agreement.
            if (side == "long" and notional < 0) or (side == "short" and notional > 0):
                out["action"].append(f"{sym}:side_notional_mismatch")
            # weight <-> notional (signed): notional == weight * capital.
            if weight is not None and notional != (weight * V1_CAPITAL_BASE_USD):
                out["action"].append(f"{sym}:weight_notional_mismatch")

        # Per-symbol fingerprints (recomputed; producer helpers reused).
        stored_src_fp = pe.get("source_message_fingerprint")
        if not stored_src_fp or _recompute_source_message_fingerprint(
                tp.get("symbol"), pe) != stored_src_fp:
            out["action"].append(f"{sym}:source_message_fingerprint_mismatch")
        stored_action_fp = tp.get("action_fingerprint")
        if not stored_action_fp or _recompute_action_fingerprint(tp, pe) != stored_action_fp:
            out["action"].append(f"{sym}:action_fingerprint_mismatch")

        # Per-symbol source-WS-artifact provenance, anchored to the CALLER's expected
        # fingerprint / sha256 (never derived from the wrapper).
        if str(pe.get("source_artifact_fingerprint", "")) != str(expected_ws_fp):
            out["ws"].append(f"{sym}:source_artifact_fingerprint_not_expected")
        if str(pe.get("source_artifact_sha256", "")) != str(expected_ws_sha):
            out["ws"].append(f"{sym}:source_artifact_sha256_not_expected")

        # UTC timestamp semantics (exact authoritative freshness lives in the
        # source-record cross-validation, which has the per-symbol source record).
        out["temporal"].extend(_check_utc(sym or "<unknown>", pe))
    except Exception as exc:  # noqa: BLE001  (narrow: per-symbol only, fail closed)
        out["action"].append(f"{sym or '<unknown>'}:action_validation_error:{type(exc).__name__}")
    return out


def _authorization_failures(artifact: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for f in _FALSE_REQUIRED_FIELDS:
        if artifact.get(f) is not False:
            problems.append(f"{f}_not_false")
    for f in _ZERO_REQUIRED_FIELDS:
        if artifact.get(f) != 0:
            problems.append(f"{f}_nonzero")
    na = _as_map(artifact.get("binding_network_audit"))
    for f in _ZERO_REQUIRED_NETWORK_FIELDS:
        if na.get(f) != 0:
            problems.append(f"binding_network_audit.{f}_nonzero")
    return problems


# ---------------------------------------------------------------------------
# Pure validation core
# ---------------------------------------------------------------------------

def validate_ws_bound_plan_artifact(
    artifact: Mapping[str, Any],
    *,
    source_ws_artifact: Mapping[str, Any],
    expected_policy_id: str,
    expected_strategy_id: str,
    expected_run_date: str,
    expected_original_plan_fingerprint: str,
    expected_ws_artifact_sha256: str,
    expected_ws_artifact_fingerprint: str,
    expected_binding_epoch_ns: int,
    expected_freshness_threshold_ms: int,
    expected_symbols: Sequence[str],
) -> BoundPlanConsumerResult:
    """Fail-closed validation of a canonical WS-bound Plan wrapper.

    Never raises for a JSON-compatible Mapping input. Returns a
    :class:`BoundPlanConsumerResult`; the validated canonical Plan
    (``validated_actions``) is exposed ONLY when every required check passes; on any
    failure it is empty and ``execution_grade_freshness_complete`` is False.

    ``expected_ws_artifact_fingerprint`` and ``expected_ws_artifact_sha256`` are the
    EXTERNAL ground truth for WS provenance; they are never derived from the wrapper."""
    failures: list[str] = []
    blockers: list[str] = []

    def _fail(code: str, blocker: str) -> None:
        if code not in failures:
            failures.append(code)
        blockers.append(blocker)

    cbp_map = _as_map(_as_map(artifact).get("canonical_bound_plan"))
    cbp_fp = cbp_map.get("canonical_bound_plan_fingerprint")
    ws_sha = _as_map(artifact).get("source_ws_artifact_sha256")
    original_fp = cbp_map.get("original_plan_fingerprint")

    # --- Stage 0: structural / schema / version --------------------------------
    if not isinstance(artifact, Mapping) or not artifact:
        return _result(WS_BOUND_PLAN_SCHEMA_INVALID, [WS_BOUND_PLAN_SCHEMA_INVALID],
                       ["artifact_absent_or_empty"], cbp_fp, ws_sha, original_fp, ())
    if (str(artifact.get("schema", "")) != wb.SCHEMA_NAME
            or artifact.get("schema_version") != wb.SCHEMA_VERSION
            or str(artifact.get("task_id", "")) != wb.TASK_ID
            or str(artifact.get("binding_mode", "")) != wb.BINDING_MODE_PLAN_ONLY):
        _fail(WS_BOUND_PLAN_SCHEMA_INVALID, "wrapper_schema_or_version_unsupported")
        return _finalize(failures, blockers, False, False, cbp_fp, ws_sha, original_fp, ())

    # --- Stage 0b: caller-supplied expected-value FORMAT validation -------------
    # Canonical fingerprint / sha256 format (never derived from the wrapper).
    if not _is_canonical_sha(expected_ws_artifact_fingerprint):
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "expected_ws_artifact_fingerprint_not_canonical")
    if not _is_canonical_sha(expected_ws_artifact_sha256):
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "expected_ws_artifact_sha256_not_canonical")
    if not _is_canonical_sha(expected_original_plan_fingerprint):
        _fail(WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH, "expected_original_plan_fingerprint_not_canonical")
    # Temporal anchors must be positive non-boolean ints; threshold within strict max.
    epoch_ok = _is_pos_int(expected_binding_epoch_ns)
    if not epoch_ok:
        _fail(WS_BOUND_PLAN_STALE, "expected_binding_epoch_ns_not_positive_int")
    threshold_ok = _is_pos_int(expected_freshness_threshold_ms)
    if not threshold_ok:
        _fail(WS_BOUND_PLAN_STALE, "expected_freshness_threshold_ms_not_positive_int")
    elif expected_freshness_threshold_ms > STRICT_MAX_FRESHNESS_THRESHOLD_MS:
        _fail(WS_BOUND_PLAN_STALE, "expected_freshness_threshold_exceeds_strict_max")
        threshold_ok = False

    # --- Stage 1: wrapper fingerprint recomputes -------------------------------
    stored_wrapper_fp = artifact.get("wrapper_fingerprint")
    try:
        recomputed_wrapper_fp = _recompute_wrapper_fingerprint(artifact)
    except Exception:  # noqa: BLE001
        recomputed_wrapper_fp = None
    if not stored_wrapper_fp or recomputed_wrapper_fp != stored_wrapper_fp:
        _fail(WS_BOUND_PLAN_WRAPPER_FINGERPRINT_MISMATCH, "wrapper_fingerprint_does_not_recompute")

    # --- Stage 2: completeness / parity / freshness ----------------------------
    overall = str(artifact.get("overall_binding_status", ""))
    wrapper_parity = str(artifact.get("wrapper_parity_status", ""))
    binding_parity = str(artifact.get("binding_parity_status", ""))
    egfc = artifact.get("execution_grade_freshness_complete")
    canonical_present = bool(cbp_map)

    binding_audit = _as_map(artifact.get("binding_audit"))
    status_counts = _as_map(binding_audit.get("binding_status_counts"))
    stale_present = (wb.WS_EVIDENCE_STALE_AT_BINDING in status_counts
                     or str(cbp_map.get("price_binding_freshness_status",
                                        wb.BINDING_FRESHNESS_FRESH)) == wb.BINDING_FRESHNESS_STALE)

    if not canonical_present or overall != wb.WS_PLANNER_PRICE_BINDING_COMPLETE:
        if stale_present:
            _fail(WS_BOUND_PLAN_STALE, "binding_freshness_stale")
        elif (binding_parity == wb.WS_PLANNER_BINDING_PARITY_FAIL
              or wrapper_parity == wb.WS_PLANNER_BINDING_PARITY_FAIL):
            _fail(WS_BOUND_PLAN_PARITY_FAIL, "binding_parity_failed")
        else:
            _fail(WS_BOUND_PLAN_INCOMPLETE,
                  "canonical_bound_plan_absent_or_binding_not_complete")
    else:
        if (wrapper_parity != wb.WS_PLANNER_BINDING_PARITY_PASS
                or binding_parity != wb.WS_PLANNER_BINDING_PARITY_PASS):
            _fail(WS_BOUND_PLAN_PARITY_FAIL, "parity_status_not_pass")
        if egfc is not True or str(
                cbp_map.get("price_binding_freshness_status", "")) != wb.BINDING_FRESHNESS_FRESH:
            _fail(WS_BOUND_PLAN_STALE, "execution_grade_freshness_not_complete")

    # Without a canonical plan we cannot verify its fingerprint / actions.
    if not canonical_present:
        return _finalize(failures, blockers, False, False, cbp_fp, ws_sha, original_fp, ())

    # Canonical sub-schema + lineage must be the supported bound-plan schema.
    if (str(cbp_map.get("schema", "")) != wb.CANONICAL_BOUND_PLAN_SCHEMA
            or cbp_map.get("schema_version") != wb.CANONICAL_BOUND_PLAN_SCHEMA_VERSION
            or str(cbp_map.get("binding_mode", "")) != wb.BINDING_MODE_PLAN_ONLY
            or str(cbp_map.get("active_price_source", "")) != wb.WS_SOURCE_TYPE
            or str(cbp_map.get("active_price_field", "")) != wb.PLANNER_PRICE_FIELD):
        _fail(WS_BOUND_PLAN_SCHEMA_INVALID, "canonical_bound_plan_schema_or_lineage_unsupported")

    # --- Stage 3: canonical bound-plan fingerprint recomputes ------------------
    try:
        recomputed_cbp_fp = _recompute_canonical_bound_plan_fingerprint(cbp_map)
    except Exception:  # noqa: BLE001
        recomputed_cbp_fp = None
    if not cbp_fp or recomputed_cbp_fp != cbp_fp:
        _fail(WS_BOUND_PLAN_FINGERPRINT_MISMATCH, "canonical_bound_plan_fingerprint_does_not_recompute")

    # --- Stage 4: provenance / original plan / WS artifact (vs caller truth) ---
    identity = _as_map(artifact.get("strategy_identity"))
    provenance_ok = (
        str(identity.get("active_policy", "")) == expected_policy_id
        and str(identity.get("active_strategy", "")) == expected_strategy_id
        and str(identity.get("requested_strategy_date", "")) == expected_run_date
        and str(cbp_map.get("active_policy", "")) == expected_policy_id
        and str(cbp_map.get("active_strategy", "")) == expected_strategy_id
        and str(cbp_map.get("requested_strategy_date", "")) == expected_run_date)
    if not provenance_ok:
        _fail(WS_BOUND_PLAN_PROVENANCE_MISMATCH, "strategy_identity_mismatch")

    if str(original_fp or "") != str(expected_original_plan_fingerprint):
        _fail(WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH, "original_plan_fingerprint_mismatch")

    # WS artifact provenance externally anchored: caller fingerprint + sha256 are the
    # ground truth; wrapper, canonical Plan AND every action evidence must equal them.
    exp_ws_fp = str(expected_ws_artifact_fingerprint)
    exp_ws_sha = str(expected_ws_artifact_sha256)
    wrapper_ws_fp = artifact.get("source_ws_artifact_fingerprint")
    cbp_ws_fp = cbp_map.get("source_ws_artifact_fingerprint")
    if str(ws_sha or "") != exp_ws_sha:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "wrapper_ws_sha256_not_expected")
    if str(cbp_map.get("source_ws_artifact_sha256", "")) != exp_ws_sha:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "canonical_ws_sha256_not_expected")
    if str(wrapper_ws_fp or "") != exp_ws_fp:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "wrapper_ws_fingerprint_not_expected")
    if str(cbp_ws_fp or "") != exp_ws_fp:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "canonical_ws_fingerprint_not_expected")

    # --- Stage 4b: temporal anchoring (caller epoch / threshold vs artifact) ---
    # The caller's binding epoch must equal the canonical Plan epoch and any wrapper
    # copy; the caller threshold must equal the stored threshold fields. Anchors are
    # external and are never derived from the wrapper.
    if epoch_ok:
        if cbp_map.get("binding_epoch_ns") != expected_binding_epoch_ns:
            _fail(WS_BOUND_PLAN_STALE, "canonical_binding_epoch_not_expected")
        for f in ("binding_started_at_epoch_ns", "binding_completed_at_epoch_ns"):
            if f in binding_audit and binding_audit.get(f) != expected_binding_epoch_ns:
                _fail(WS_BOUND_PLAN_STALE, f"binding_audit_{f}_not_expected")
    if threshold_ok:
        if (f := binding_audit.get("binding_freshness_threshold_ms")) is not None \
                and f != expected_freshness_threshold_ms:
            _fail(WS_BOUND_PLAN_STALE, "binding_audit_threshold_not_expected")

    # --- Stage 4c: source WS artifact self-validation + authoritative offset ---
    # The original source WS evidence artifact is independently validated with the
    # producer's own compatibility gate, anchored to the caller fingerprint/sha, and
    # the authoritative clock offset is extracted from it (never approximated).
    src = _as_map(source_ws_artifact)
    try:
        gate = wb.validate_ws_artifact_compatibility(
            src, requested_strategy_date=expected_run_date,
            active_policy=expected_policy_id, active_strategy=expected_strategy_id,
            strategy_symbols=list(expected_symbols),
            strategy_symbol_source_fingerprint=None)
    except Exception:  # noqa: BLE001
        gate = {"status": "ERROR", "failures": ["source_ws_artifact_gate_error"],
                "ws_artifact_fingerprint_recomputes": False}
    if gate.get("status") != wb.WS_ARTIFACT_COMPATIBILITY_OK:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH,
              "source_ws_artifact_incompatible:" + ";".join(gate.get("failures", [])[:12]))
    if not gate.get("ws_artifact_fingerprint_recomputes"):
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "source_ws_artifact_fingerprint_does_not_recompute")
    if str(src.get("artifact_fingerprint", "")) != exp_ws_fp:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "source_ws_artifact_fingerprint_not_expected")
    # The source artifact itself must carry no execution authorization / order activity.
    for f in ("execution_batch_authorized", "execution_ready", "sender_reachable"):
        if src.get(f) is not False:
            _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, f"source_ws_artifact_{f}_not_false")
    for f in ("order_post_count", "amend_post_count", "cancel_post_count", "live_order_post_count"):
        if src.get(f) not in (0, None) and src.get(f) != 0:
            _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, f"source_ws_artifact_{f}_nonzero")
    offset, offset_problems = extract_authoritative_clock_offset(
        src, expected_ws_artifact_sha256=exp_ws_sha)
    for p in offset_problems:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, f"source_ws_artifact_{p}")

    # --- Stage 5: symbol set + 25/25 structure + symbol-set fingerprint --------
    planner = _as_map(cbp_map.get("planner"))
    targets = _as_list(planner.get("target_positions"))
    symbols = [str(_as_map(t).get("symbol", "")).strip().upper() for t in targets]
    expected_set = {str(s).strip().upper() for s in expected_symbols}
    seen: set[str] = set()
    dups = {s for s in symbols if s in seen or seen.add(s)}
    if dups:
        _fail(WS_BOUND_PLAN_DUPLICATE_SYMBOL, f"duplicate_symbols:{sorted(dups)}")
    if (set(symbols) != expected_set
            or len(expected_set) != EXPECTED_STRATEGY_SYMBOL_COUNT
            or len(symbols) != EXPECTED_STRATEGY_SYMBOL_COUNT):
        _fail(WS_BOUND_PLAN_SYMBOL_SET_MISMATCH, "symbol_set_not_exactly_expected_fifty")
    long_n = sum(1 for t in targets if str(_as_map(t).get("side", "")).strip().lower() == "long")
    short_n = sum(1 for t in targets if str(_as_map(t).get("side", "")).strip().lower() == "short")
    if long_n != EXPECTED_LONG_COUNT or short_n != EXPECTED_SHORT_COUNT:
        _fail(WS_BOUND_PLAN_SYMBOL_SET_MISMATCH,
              f"long_short_structure_not_25_25:long={long_n},short={short_n}")
    # Independently recompute the symbol-set fingerprint from the expected symbols.
    try:
        expected_symbol_fp = ws.canonical_strategy_symbol_set_fingerprint(list(expected_symbols))
    except Exception:  # noqa: BLE001
        expected_symbol_fp = None
    stored_symbol_fp = identity.get("strategy_symbol_source_fingerprint")
    if not stored_symbol_fp or str(stored_symbol_fp) != str(expected_symbol_fp):
        _fail(WS_BOUND_PLAN_SYMBOL_SET_MISMATCH, "symbol_source_fingerprint_mismatch")

    # --- Stage 6: V1 capital base + per-action consistency / fingerprints ------
    sizing = _as_map(planner.get("sizing_verification"))
    capital_base = wb._dec(sizing.get("capital_base_usd"))
    if capital_base is None or capital_base != V1_CAPITAL_BASE_USD:
        _fail(WS_BOUND_PLAN_ACTION_INCONSISTENT,
              f"v1_capital_base_not_10000:{sizing.get('capital_base_usd')}")

    # Index the validated source artifact's per-symbol evidence (producer helper).
    src_by_symbol, src_dups = wb._index_ws_evidence(src)
    if src_dups:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, f"duplicate_source_symbols:{sorted(src_dups)}")

    action_problems: list[str] = []
    ws_prov_problems: list[str] = []
    temporal_problems: list[str] = []
    caller_epoch = expected_binding_epoch_ns if epoch_ok else None
    caller_threshold = expected_freshness_threshold_ms if threshold_ok else None
    for t in targets:
        res = _check_action(t, expected_ws_fp=exp_ws_fp, expected_ws_sha=exp_ws_sha)
        action_problems.extend(res["action"])
        temporal_problems.extend(res["temporal"])
        ws_prov_problems.extend(res["ws"])
        sym = str(_as_map(t).get("symbol", "")).strip().upper()
        src_rec = src_by_symbol.get(sym)
        res2 = _check_source_record(
            sym or "<unknown>", _as_map(t), src_rec,
            clock_offset=offset, caller_epoch_ns=caller_epoch, caller_threshold_ms=caller_threshold)
        ws_prov_problems.extend(res2["ws"])
        temporal_problems.extend(res2["temporal"])
    if temporal_problems:
        _fail(WS_BOUND_PLAN_STALE, "; ".join(temporal_problems[:40]))
    if action_problems:
        _fail(WS_BOUND_PLAN_ACTION_INCONSISTENT, "; ".join(action_problems[:40]))
    if ws_prov_problems:
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "; ".join(ws_prov_problems[:40]))

    # --- Stage 7: authorization / dispatch counters all false / zero -----------
    auth_problems = _authorization_failures(artifact)
    if auth_problems:
        _fail(WS_BOUND_PLAN_AUTHORIZATION_PRESENT, "; ".join(auth_problems))

    if failures:
        return _finalize(failures, blockers, provenance_ok, True, cbp_fp, ws_sha, original_fp, ())

    validated = tuple(
        ValidatedBoundAction(
            symbol=str(_as_map(t).get("symbol", "")).strip().upper(),
            side=str(_as_map(t).get("side", "")),
            target_weight=_as_map(t).get("target_weight"),
            price=_as_map(t).get("price"),
            qty=_as_map(t).get("qty"),
            qty_step=_as_map(t).get("qty_step"),
            target_notional=_as_map(t).get("target_notional"),
            effective_notional=_as_map(t).get("effective_notional"),
            source_message_fingerprint=_as_map(_as_map(t).get("price_evidence")).get(
                "source_message_fingerprint"),
            action_fingerprint=_as_map(t).get("action_fingerprint"),
            action_price_binding_status=_as_map(t).get("action_price_binding_status"))
        for t in targets)
    return BoundPlanConsumerResult(
        status=WS_BOUND_PLAN_CONSUMER_PASS,
        failure_codes=(),
        provenance_verified=True,
        canonical_plan_available=True,
        canonical_bound_plan_fingerprint=cbp_fp,
        source_ws_artifact_sha256=ws_sha,
        original_plan_fingerprint=original_fp,
        execution_grade_freshness_complete=True,
        validated_actions=validated,
        blockers=())


def _result(status: str, failures: list[str], blockers: list[str],
            cbp_fp: str | None, ws_sha: str | None, original_fp: str | None,
            validated: tuple) -> BoundPlanConsumerResult:
    return BoundPlanConsumerResult(
        status=status,
        failure_codes=tuple(dict.fromkeys(failures)),
        provenance_verified=False,
        canonical_plan_available=False,
        canonical_bound_plan_fingerprint=cbp_fp,
        source_ws_artifact_sha256=ws_sha,
        original_plan_fingerprint=original_fp,
        execution_grade_freshness_complete=False,
        validated_actions=validated,
        blockers=tuple(blockers))


def _finalize(failures: list[str], blockers: list[str], provenance_ok: bool,
              canonical_available: bool, cbp_fp: str | None, ws_sha: str | None,
              original_fp: str | None, validated: tuple) -> BoundPlanConsumerResult:
    """Resolve the single status from collected failures (fail closed)."""
    ordered = tuple(dict.fromkeys(failures))
    status = next((c for c in _STATUS_PRIORITY if c in ordered), None)
    if status is None:
        # Defensive: never report PASS from this path (PASS is built explicitly).
        status = ordered[0] if ordered else WS_BOUND_PLAN_SCHEMA_INVALID
    return BoundPlanConsumerResult(
        status=status,
        failure_codes=ordered,
        provenance_verified=bool(provenance_ok) and not ordered,
        canonical_plan_available=bool(canonical_available) and not ordered,
        canonical_bound_plan_fingerprint=cbp_fp,
        source_ws_artifact_sha256=ws_sha,
        original_plan_fingerprint=original_fp,
        execution_grade_freshness_complete=False,
        validated_actions=validated,
        blockers=tuple(blockers))


__all__ = [
    "TASK_ID",
    "EXPECTED_STRATEGY_SYMBOL_COUNT", "EXPECTED_LONG_COUNT", "EXPECTED_SHORT_COUNT",
    "V1_CAPITAL_BASE_USD", "V1_LONG_TARGET_WEIGHT", "V1_SHORT_TARGET_WEIGHT",
    "V1_LONG_TARGET_NOTIONAL_USD", "V1_SHORT_TARGET_NOTIONAL_USD",
    "V1_ABS_TARGET_WEIGHT", "V1_ABS_TARGET_NOTIONAL_USD",
    "STRICT_MAX_FRESHNESS_THRESHOLD_MS", "FUTURE_TOLERANCE_MS", "ALLOWED_MESSAGE_TYPES",
    "WS_BOUND_PLAN_CONSUMER_PASS",
    "WS_BOUND_PLAN_SCHEMA_INVALID", "WS_BOUND_PLAN_WRAPPER_FINGERPRINT_MISMATCH",
    "WS_BOUND_PLAN_FINGERPRINT_MISMATCH", "WS_BOUND_PLAN_PROVENANCE_MISMATCH",
    "WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH", "WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH",
    "WS_BOUND_PLAN_SYMBOL_SET_MISMATCH", "WS_BOUND_PLAN_DUPLICATE_SYMBOL",
    "WS_BOUND_PLAN_INCOMPLETE", "WS_BOUND_PLAN_STALE", "WS_BOUND_PLAN_PARITY_FAIL",
    "WS_BOUND_PLAN_ACTION_INCONSISTENT", "WS_BOUND_PLAN_AUTHORIZATION_PRESENT",
    "WsBoundPlanConsumerError", "ValidatedBoundAction", "BoundPlanConsumerResult",
    "load_ws_bound_plan_artifact", "validate_ws_bound_plan_artifact",
    "extract_authoritative_clock_offset",
]
