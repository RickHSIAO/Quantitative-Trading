"""TASK-014CH3B1 -- pure, offline WebSocket-bound Plan REVIEW core.

Given a trusted external **anchor manifest** plus the EXACT CH2 wrapper bytes and the
EXACT source-WS evidence bytes, this module:

  1. pins identity to the external manifest (manifest SHA256 + logical fingerprint;
     manifest-supplied source SHA/fingerprint + canonical bound-Plan fingerprint);
  2. re-runs the CH1 consumer historical validation using ONLY manifest anchors;
  3. builds an IMMUTABLE Strategy-native V1 exposure review (frozen scalar rows);
  4. performs an offline MARGIN ARITHMETIC review (absolute gross only);
  5. returns a terminal review-envelope Mapping (references + results, NOT the Plan).

Hard scope (CH3B1): PURE and offline. No CLI/runtime wiring (CH3B2). It performs NO
file I/O, NO network, NO WebSocket collection, NO wall-clock read, and imports neither a
runner, readiness, the execution gate, native execution, a sender/transport, Pilot
lifecycle/store, nor reporting. It cannot place / amend / cancel an order and never
advances Pilot state.

Freshness is HISTORICAL binding-time only: a PASS proves the WS evidence was valid at its
recorded binding epoch -- NOT that the Plan is presently executable. Current-market
freshness is NOT evaluated. No independent offline projected-margin rate exists, so the
projected-margin review is NOT complete and account feasibility is NOT evaluated.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Mapping, Sequence

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_bound_plan_consumer as consumer
from src import demo_strategy_native_ws_price_binding as wb

TASK_ID = "TASK-014CH3B1"

# --- Anchor manifest schema -------------------------------------------------
ANCHOR_MANIFEST_SCHEMA = "demo_strategy_native_ws_bound_plan_anchor_manifest"
ANCHOR_MANIFEST_SCHEMA_VERSION = 1

# --- Fixed Strategy-native V1 identity (repository-pinned; never from artifacts) ---
EXPECTED_POLICY_ID = wb.ACTIVE_STRATEGY_NATIVE_V1_POLICY
EXPECTED_STRATEGY_ID = wb.EXPECTED_STRATEGY_NAME
EXPECTED_STRATEGY_SYMBOL_COUNT = consumer.EXPECTED_STRATEGY_SYMBOL_COUNT  # 50
EXPECTED_LONG_COUNT = consumer.EXPECTED_LONG_COUNT  # 25
EXPECTED_SHORT_COUNT = consumer.EXPECTED_SHORT_COUNT  # 25
STRICT_MAX_FRESHNESS_THRESHOLD_MS = consumer.STRICT_MAX_FRESHNESS_THRESHOLD_MS  # 10_000

V1_CAPITAL_BASE_USD = consumer.V1_CAPITAL_BASE_USD          # Decimal("10000")
V1_LONG_TARGET_WEIGHT = consumer.V1_LONG_TARGET_WEIGHT      # Decimal("0.02")
V1_SHORT_TARGET_WEIGHT = consumer.V1_SHORT_TARGET_WEIGHT    # Decimal("-0.02")
V1_LONG_TARGET_NOTIONAL_USD = consumer.V1_LONG_TARGET_NOTIONAL_USD    # Decimal("200")
V1_SHORT_TARGET_NOTIONAL_USD = consumer.V1_SHORT_TARGET_NOTIONAL_USD  # Decimal("-200")
V1_LONG_GROSS_USD = Decimal("5000")
V1_SHORT_ABS_GROSS_USD = Decimal("5000")
V1_GROSS_USD = Decimal("10000")
V1_NET_USD = Decimal("0")

# --- Status vocabulary ------------------------------------------------------
WS_BOUND_PLAN_REVIEW_PASS = "WS_BOUND_PLAN_REVIEW_PASS"
WS_BOUND_PLAN_REVIEW_INPUT_INVALID = "WS_BOUND_PLAN_REVIEW_INPUT_INVALID"
WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH = "WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH"
WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH = "WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH"
WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED = "WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED"
WS_BOUND_PLAN_REVIEW_CANONICAL_MISMATCH = "WS_BOUND_PLAN_REVIEW_CANONICAL_MISMATCH"
WS_BOUND_PLAN_REVIEW_EXPOSURE_FAILED = "WS_BOUND_PLAN_REVIEW_EXPOSURE_FAILED"
WS_BOUND_PLAN_REVIEW_MARGIN_ARITHMETIC_FAILED = "WS_BOUND_PLAN_REVIEW_MARGIN_ARITHMETIC_FAILED"
WS_BOUND_PLAN_REVIEW_PROVENANCE_FAILED = "WS_BOUND_PLAN_REVIEW_PROVENANCE_FAILED"

# --- Explicit "not evaluated / unavailable" semantics -----------------------
OFFLINE_PROJECTED_MARGIN_RATE_UNAVAILABLE = "UNAVAILABLE_NO_INDEPENDENT_RATE"
ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE = "UNAVAILABLE_NOT_EVALUATED"
CURRENT_MARKET_FRESHNESS_NOT_EVALUATED = "NOT_EVALUATED"

# Required manifest fields (presence + format validated before any review).
_REQUIRED_MANIFEST_FIELDS = (
    "schema", "schema_version", "policy_id", "strategy_id", "run_date",
    "original_plan_fingerprint", "source_ws_artifact_sha256",
    "source_ws_artifact_fingerprint", "canonical_bound_plan_fingerprint",
    "binding_epoch_ns", "freshness_threshold_ms", "strategy_symbols",
    "expected_symbol_set_fingerprint", "manifest_fingerprint",
)


@dataclass(frozen=True)
class WsBoundPlanReviewAction:
    """Immutable, scalar-only review row (no reference to any wrapper Mapping)."""
    symbol: str
    side: str
    target_weight: str
    target_notional: str   # signed: long "+200" / short "-200"
    price: str
    qty: str
    qty_step: str
    effective_notional: str
    source_message_fingerprint: str
    action_fingerprint: str


@dataclass(frozen=True)
class WsBoundPlanReviewResult:
    status: str
    blockers: tuple[str, ...]
    review_artifact: Mapping[str, Any] | None
    review_rows: tuple[WsBoundPlanReviewAction, ...]
    wrapper_file_sha256: str | None
    wrapper_logical_fingerprint: str | None
    canonical_bound_plan_fingerprint: str | None
    source_ws_file_sha256: str | None
    source_ws_logical_fingerprint: str | None
    anchor_manifest_sha256: str | None
    anchor_manifest_fingerprint: str | None
    original_plan_fingerprint: str | None
    expected_symbol_set_fingerprint: str | None
    binding_epoch_ns: int | None
    freshness_threshold_ms: int | None
    offline_exposure_review_complete: bool
    offline_margin_arithmetic_review_complete: bool
    offline_projected_margin_rate_status: str
    offline_projected_margin_review_complete: bool
    account_margin_feasibility_status: str
    binding_time_freshness_verified: bool
    current_market_freshness_status: str
    current_market_freshness_checked: bool
    execution_readiness: bool
    readiness_called: bool
    execution_gate_called: bool
    native_execution_called: bool
    pilot_advanced: bool

    @property
    def passed(self) -> bool:
        return self.status == WS_BOUND_PLAN_REVIEW_PASS


# ---------------------------------------------------------------------------
# Helpers (pure)
# ---------------------------------------------------------------------------

def _is_pos_int(value: Any) -> bool:
    return isinstance(value, int) and not isinstance(value, bool) and value > 0


def _manifest_logical_fingerprint(manifest: Mapping[str, Any]) -> str:
    return ws._fingerprint({k: v for k, v in manifest.items() if k != "manifest_fingerprint"})


def _fail(status: str, *blockers: str) -> WsBoundPlanReviewResult:
    return WsBoundPlanReviewResult(
        status=status, blockers=tuple(blockers), review_artifact=None, review_rows=(),
        wrapper_file_sha256=None, wrapper_logical_fingerprint=None,
        canonical_bound_plan_fingerprint=None, source_ws_file_sha256=None,
        source_ws_logical_fingerprint=None, anchor_manifest_sha256=None,
        anchor_manifest_fingerprint=None, original_plan_fingerprint=None,
        expected_symbol_set_fingerprint=None, binding_epoch_ns=None,
        freshness_threshold_ms=None,
        offline_exposure_review_complete=False,
        offline_margin_arithmetic_review_complete=False,
        offline_projected_margin_rate_status=CURRENT_MARKET_FRESHNESS_NOT_EVALUATED,
        offline_projected_margin_review_complete=False,
        account_margin_feasibility_status=ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE,
        binding_time_freshness_verified=False,
        current_market_freshness_status=CURRENT_MARKET_FRESHNESS_NOT_EVALUATED,
        current_market_freshness_checked=False, execution_readiness=False,
        readiness_called=False, execution_gate_called=False,
        native_execution_called=False, pilot_advanced=False)


def _exposure_check(rows: Sequence[WsBoundPlanReviewAction], wrapper: Mapping[str, Any]) -> list[str]:
    """Independently recompute V1 exposure from frozen rows + read-only wrapper price
    provenance. Returns problems (empty == complete)."""
    probs: list[str] = []
    if len(rows) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        probs.append(f"action_count_not_fifty:{len(rows)}")
    long_n = sum(1 for r in rows if r.side == "long")
    short_n = sum(1 for r in rows if r.side == "short")
    if long_n != EXPECTED_LONG_COUNT or short_n != EXPECTED_SHORT_COUNT:
        probs.append(f"long_short_not_25_25:long={long_n},short={short_n}")

    # Read-only wrapper price-source provenance (rows hold no wrapper ref).
    cbp = wrapper.get("canonical_bound_plan") if isinstance(wrapper, Mapping) else None
    planner = cbp.get("planner") if isinstance(cbp, Mapping) else None
    tps = planner.get("target_positions") if isinstance(planner, Mapping) else []
    pe_by_symbol: dict[str, Mapping[str, Any]] = {}
    for tp in (tps or []):
        if isinstance(tp, Mapping):
            sym = str(tp.get("symbol", "")).strip().upper()
            pe_by_symbol[sym] = tp

    long_exp = Decimal("0")
    short_abs = Decimal("0")
    gross = Decimal("0")
    net = Decimal("0")
    for r in rows:
        sym = str(r.symbol).strip().upper()
        weight = wb._dec(r.target_weight)
        notional = wb._dec(r.target_notional)
        price = wb._dec(r.price)
        qty_step = wb._dec(r.qty_step)
        stored_qty = wb._dec(r.qty)
        if weight is None or notional is None or price is None or qty_step is None or stored_qty is None:
            probs.append(f"{sym}:unparseable_numeric_field")
            continue
        if r.side == "long":
            if weight != V1_LONG_TARGET_WEIGHT:
                probs.append(f"{sym}:long_weight_not_plus_0.02")
            if notional != V1_LONG_TARGET_NOTIONAL_USD:
                probs.append(f"{sym}:long_notional_not_plus_200")
        elif r.side == "short":
            if weight != V1_SHORT_TARGET_WEIGHT:
                probs.append(f"{sym}:short_weight_not_minus_0.02")
            if notional != V1_SHORT_TARGET_NOTIONAL_USD:
                probs.append(f"{sym}:short_notional_not_minus_200")
        else:
            probs.append(f"{sym}:side_not_long_or_short")
        if notional != (weight * V1_CAPITAL_BASE_USD):
            probs.append(f"{sym}:notional_not_weight_times_capital")
        # qty positive, exact qty_step multiple, and qty/effective consistency.
        if price <= 0 or qty_step <= 0:
            probs.append(f"{sym}:price_or_step_not_positive")
            continue
        expected_qty = wb._floor_qty(notional.copy_abs(), price, qty_step)
        if not expected_qty > 0:
            probs.append(f"{sym}:qty_not_positive")
        if (expected_qty % qty_step) != 0:
            probs.append(f"{sym}:qty_not_step_multiple")
        if wb._canon_dec_str(expected_qty) != r.qty:
            probs.append(f"{sym}:qty_inconsistent")
        if wb._canon_dec_str(expected_qty * price) != r.effective_notional:
            probs.append(f"{sym}:effective_notional_inconsistent")
        # Active price provenance: must be the WS-bound price, never the REST seed.
        tp = pe_by_symbol.get(sym)
        if not isinstance(tp, Mapping):
            probs.append(f"{sym}:target_missing_in_wrapper")
        else:
            pe = tp.get("price_evidence") if isinstance(tp.get("price_evidence"), Mapping) else {}
            if str(tp.get("price_source", "")) != wb.WS_SOURCE_TYPE:
                probs.append(f"{sym}:active_price_source_not_websocket")
            if r.price != pe.get("selected_price"):
                probs.append(f"{sym}:active_price_not_ws_selected_price")
            rest_price = tp.get("rest_planning_price")
            if rest_price is not None and r.price == rest_price and rest_price != pe.get("selected_price"):
                probs.append(f"{sym}:active_price_is_rest_seed_price")
        long_exp += notional if r.side == "long" else Decimal("0")
        short_abs += notional.copy_abs() if r.side == "short" else Decimal("0")
        gross += notional.copy_abs()
        net += notional
    if long_exp != V1_LONG_GROSS_USD:
        probs.append(f"long_exposure_not_5000:{long_exp}")
    if short_abs != V1_SHORT_ABS_GROSS_USD:
        probs.append(f"short_absolute_exposure_not_5000:{short_abs}")
    if gross != V1_GROSS_USD:
        probs.append(f"gross_exposure_not_10000:{gross}")
    if net != V1_NET_USD:
        probs.append(f"net_signed_exposure_not_zero:{net}")
    return probs


def _margin_arithmetic_check(rows: Sequence[WsBoundPlanReviewAction],
                             wrapper: Mapping[str, Any]) -> list[str]:
    """Offline margin ARITHMETIC review only: absolute gross (never signed net); the
    wrapper-embedded gross must equal the independently recomputed 10,000; the wrapper
    must NOT claim an independently-verified applicable account rate."""
    probs: list[str] = []
    gross_abs = sum((wb._dec(r.target_notional).copy_abs()
                     for r in rows if wb._dec(r.target_notional) is not None), Decimal("0"))
    if gross_abs != V1_GROSS_USD:
        probs.append(f"absolute_gross_not_10000:{gross_abs}")
    cbp = wrapper.get("canonical_bound_plan") if isinstance(wrapper, Mapping) else None
    review = cbp.get("rebuilt_price_dependent_review") if isinstance(cbp, Mapping) else None
    if isinstance(review, Mapping):
        embedded_gross = review.get("strategy_gross_notional")
        if embedded_gross is not None and wb._dec(embedded_gross) != V1_GROSS_USD:
            probs.append(f"wrapper_gross_not_10000:{embedded_gross}")
        model = review.get("projected_margin_model")
        if isinstance(model, Mapping):
            rate = model.get("applicable_initial_margin_rate")
            if rate is not None:
                probs.append("wrapper_claims_applicable_account_rate")
    return probs


# ---------------------------------------------------------------------------
# Pure review core
# ---------------------------------------------------------------------------

def build_ws_bound_plan_review(
    *,
    anchor_manifest_bytes: bytes,
    expected_anchor_manifest_sha256: str,
    wrapper_artifact_bytes: bytes,
    source_ws_artifact_bytes: bytes,
) -> WsBoundPlanReviewResult:
    """Pure, offline review. Returns a result rather than raising for malformed
    JSON-compatible input. The wrapper is exposed via review references only when every
    anchor matches, CH1 historical validation PASSes, the immutable exposure review
    passes, and the offline margin arithmetic passes."""

    # --- Input shape -----------------------------------------------------------
    for name, b in (("anchor_manifest_bytes", anchor_manifest_bytes),
                    ("wrapper_artifact_bytes", wrapper_artifact_bytes),
                    ("source_ws_artifact_bytes", source_ws_artifact_bytes)):
        if not isinstance(b, (bytes, bytearray)):
            return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, f"{name}_not_bytes")
    if not consumer._is_canonical_sha(expected_anchor_manifest_sha256):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID,
                     "expected_anchor_manifest_sha256_not_canonical")

    # --- Manifest exact-byte trust root ---------------------------------------
    manifest_sha = wb.compute_file_sha256(bytes(anchor_manifest_bytes))
    if manifest_sha != str(expected_anchor_manifest_sha256):
        return _fail(WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH, "manifest_sha256_not_expected")
    try:
        manifest = json.loads(bytes(anchor_manifest_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_bytes_invalid_json")
    if not isinstance(manifest, Mapping):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_bytes_not_object")
    missing = [f for f in _REQUIRED_MANIFEST_FIELDS if f not in manifest]
    if missing:
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, f"manifest_missing_fields:{missing}")
    if (str(manifest.get("schema", "")) != ANCHOR_MANIFEST_SCHEMA
            or manifest.get("schema_version") != ANCHOR_MANIFEST_SCHEMA_VERSION):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_schema_or_version_unsupported")
    stored_manifest_fp = manifest.get("manifest_fingerprint")
    try:
        recomputed_manifest_fp = _manifest_logical_fingerprint(manifest)
    except (TypeError, ValueError):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_unfingerprintable")
    if not stored_manifest_fp or str(stored_manifest_fp) != recomputed_manifest_fp:
        return _fail(WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH, "manifest_fingerprint_does_not_recompute")

    # --- Manifest field validation --------------------------------------------
    if str(manifest.get("policy_id", "")) != EXPECTED_POLICY_ID:
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_policy_not_v1")
    if str(manifest.get("strategy_id", "")) != EXPECTED_STRATEGY_ID:
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_strategy_not_v1")
    run_date = str(manifest.get("run_date", ""))
    if not run_date:
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_run_date_empty")
    for f in ("original_plan_fingerprint", "source_ws_artifact_sha256",
              "source_ws_artifact_fingerprint", "canonical_bound_plan_fingerprint"):
        if not consumer._is_canonical_sha(manifest.get(f)):
            return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, f"manifest_{f}_not_canonical")
    wrapper_fp_anchor = manifest.get("wrapper_fingerprint")
    if wrapper_fp_anchor is not None and not consumer._is_canonical_sha(wrapper_fp_anchor):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_wrapper_fingerprint_not_canonical")
    epoch = manifest.get("binding_epoch_ns")
    if not _is_pos_int(epoch):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_binding_epoch_ns_not_positive_int")
    threshold = manifest.get("freshness_threshold_ms")
    if not (_is_pos_int(threshold) and threshold <= STRICT_MAX_FRESHNESS_THRESHOLD_MS):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_freshness_threshold_invalid")
    raw_syms = manifest.get("strategy_symbols")
    if not isinstance(raw_syms, (list, tuple)):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_symbols_not_list")
    symbols = [str(s).strip().upper() for s in raw_syms]
    if len(set(symbols)) != EXPECTED_STRATEGY_SYMBOL_COUNT or len(symbols) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_symbols_not_fifty_unique")
    expected_symbol_set_fp = str(manifest.get("expected_symbol_set_fingerprint", ""))
    if expected_symbol_set_fp != ws.canonical_strategy_symbol_set_fingerprint(symbols):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "manifest_symbol_set_fingerprint_mismatch")

    # --- Wrapper + source exact bytes -----------------------------------------
    wrapper_sha = wb.compute_file_sha256(bytes(wrapper_artifact_bytes))
    source_sha = wb.compute_file_sha256(bytes(source_ws_artifact_bytes))
    try:
        parsed_wrapper = json.loads(bytes(wrapper_artifact_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "wrapper_bytes_invalid_json")
    if not isinstance(parsed_wrapper, Mapping):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "wrapper_bytes_not_object")
    try:
        parsed_source = json.loads(bytes(source_ws_artifact_bytes))
    except (json.JSONDecodeError, ValueError, TypeError):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "source_bytes_invalid_json")
    if not isinstance(parsed_source, Mapping):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "source_bytes_not_object")

    source_logical_fp = ws._fingerprint(
        {k: v for k, v in parsed_source.items() if k != "artifact_fingerprint"})
    try:
        pre_wrapper_fp = consumer._recompute_wrapper_fingerprint(parsed_wrapper)
    except (TypeError, ValueError, KeyError):
        return _fail(WS_BOUND_PLAN_REVIEW_INPUT_INVALID, "wrapper_unfingerprintable")

    # Source identity must equal the external manifest anchors (not self-derived).
    if source_sha != str(manifest.get("source_ws_artifact_sha256")):
        return _fail(WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH, "source_file_sha256_not_manifest")
    if source_logical_fp != str(manifest.get("source_ws_artifact_fingerprint")):
        return _fail(WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH, "source_logical_fingerprint_not_manifest")
    if wrapper_fp_anchor is not None and pre_wrapper_fp != str(wrapper_fp_anchor):
        return _fail(WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH, "wrapper_fingerprint_not_manifest")

    # --- CH1 historical validation (manifest anchors only) --------------------
    ch1 = consumer.validate_ws_bound_plan_artifact(
        parsed_wrapper,
        source_ws_artifact=parsed_source,
        expected_policy_id=EXPECTED_POLICY_ID,
        expected_strategy_id=EXPECTED_STRATEGY_ID,
        expected_run_date=run_date,
        expected_original_plan_fingerprint=str(manifest.get("original_plan_fingerprint")),
        expected_ws_artifact_sha256=str(manifest.get("source_ws_artifact_sha256")),
        expected_ws_artifact_fingerprint=str(manifest.get("source_ws_artifact_fingerprint")),
        expected_binding_epoch_ns=int(epoch),
        expected_freshness_threshold_ms=int(threshold),
        expected_symbols=symbols)
    if not ch1.passed:
        return _fail(WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED,
                     ch1.status, *ch1.failure_codes[:20])

    # External canonical-Plan pin (manifest, not the wrapper under review).
    if ch1.canonical_bound_plan_fingerprint != str(manifest.get("canonical_bound_plan_fingerprint")):
        return _fail(WS_BOUND_PLAN_REVIEW_CANONICAL_MISMATCH,
                     "canonical_bound_plan_fingerprint_not_manifest")
    if len(ch1.validated_actions) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        return _fail(WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED,
                     f"validated_action_count_not_fifty:{len(ch1.validated_actions)}")

    # --- Immutable review projection (frozen scalar rows; no wrapper ref) -----
    rows: list[WsBoundPlanReviewAction] = []
    for a in ch1.validated_actions:
        rows.append(WsBoundPlanReviewAction(
            symbol=str(a.symbol), side=str(a.side),
            target_weight=str(a.target_weight), target_notional=str(a.target_notional),
            price=str(a.price), qty=str(a.qty), qty_step=str(a.qty_step),
            effective_notional=str(a.effective_notional),
            source_message_fingerprint=str(a.source_message_fingerprint),
            action_fingerprint=str(a.action_fingerprint)))
    review_rows = tuple(rows)

    # --- Offline exposure review (frozen rows + read-only wrapper provenance) -
    exposure_problems = _exposure_check(review_rows, parsed_wrapper)
    if exposure_problems:
        return _fail(WS_BOUND_PLAN_REVIEW_EXPOSURE_FAILED, *exposure_problems[:30])

    # --- Offline margin ARITHMETIC review (absolute gross; rate unavailable) --
    margin_problems = _margin_arithmetic_check(review_rows, parsed_wrapper)
    if margin_problems:
        return _fail(WS_BOUND_PLAN_REVIEW_MARGIN_ARITHMETIC_FAILED, *margin_problems[:30])

    # --- Defensive mutation proof (review never touched the wrapper) ----------
    post_wrapper_fp = consumer._recompute_wrapper_fingerprint(parsed_wrapper)
    post_canonical_fp = consumer._recompute_canonical_bound_plan_fingerprint(
        parsed_wrapper.get("canonical_bound_plan") or {})
    if not (pre_wrapper_fp == post_wrapper_fp
            and post_canonical_fp == ch1.canonical_bound_plan_fingerprint):
        return _fail(WS_BOUND_PLAN_REVIEW_PROVENANCE_FAILED, "wrapper_or_canonical_fingerprint_changed")

    # --- Build the terminal review envelope (references + results; no Plan) ---
    review_rows_fp = ws._fingerprint([
        {"symbol": r.symbol, "side": r.side, "target_weight": r.target_weight,
         "target_notional": r.target_notional, "price": r.price, "qty": r.qty,
         "qty_step": r.qty_step, "effective_notional": r.effective_notional,
         "source_message_fingerprint": r.source_message_fingerprint,
         "action_fingerprint": r.action_fingerprint} for r in review_rows])

    envelope: dict[str, Any] = {
        "schema": "demo_strategy_native_ws_bound_plan_review",
        "schema_version": 1,
        "task_id": TASK_ID,
        "status": WS_BOUND_PLAN_REVIEW_PASS,
        # Identity: external anchors vs current-file computed (never conflated).
        "anchor_manifest_sha256": manifest_sha,
        "anchor_manifest_fingerprint": recomputed_manifest_fp,
        "wrapper_file_sha256": wrapper_sha,
        "wrapper_logical_fingerprint": pre_wrapper_fp,
        "expected_canonical_bound_plan_fingerprint": str(manifest.get("canonical_bound_plan_fingerprint")),
        "recomputed_canonical_bound_plan_fingerprint": ch1.canonical_bound_plan_fingerprint,
        "source_ws_file_sha256": source_sha,
        "source_ws_logical_fingerprint": source_logical_fp,
        "expected_source_ws_artifact_sha256": str(manifest.get("source_ws_artifact_sha256")),
        "expected_source_ws_artifact_fingerprint": str(manifest.get("source_ws_artifact_fingerprint")),
        "original_plan_fingerprint": str(manifest.get("original_plan_fingerprint")),
        "expected_symbol_set_fingerprint": expected_symbol_set_fp,
        "binding_epoch_ns": int(epoch),
        "freshness_threshold_ms": int(threshold),
        # Review results.
        "review_rows": [
            {"symbol": r.symbol, "side": r.side, "target_weight": r.target_weight,
             "target_notional": r.target_notional, "price": r.price, "qty": r.qty,
             "qty_step": r.qty_step, "effective_notional": r.effective_notional}
            for r in review_rows],
        "review_rows_fingerprint": review_rows_fp,
        "offline_exposure_totals": {
            "action_count": len(review_rows),
            "long_count": EXPECTED_LONG_COUNT, "short_count": EXPECTED_SHORT_COUNT,
            "long_exposure_usd": wb._canon_dec_str(V1_LONG_GROSS_USD),
            "short_absolute_exposure_usd": wb._canon_dec_str(V1_SHORT_ABS_GROSS_USD),
            "gross_exposure_usd": wb._canon_dec_str(V1_GROSS_USD),
            "net_signed_exposure_usd": wb._canon_dec_str(V1_NET_USD),
        },
        "offline_exposure_review_complete": True,
        "offline_margin_arithmetic_review_complete": True,
        "offline_projected_margin_rate_status": OFFLINE_PROJECTED_MARGIN_RATE_UNAVAILABLE,
        "offline_projected_margin_review_complete": False,
        "account_margin_feasibility_status": ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE,
        # Freshness: HISTORICAL binding-time only.
        "binding_time_freshness_verified": True,
        "current_market_freshness_status": CURRENT_MARKET_FRESHNESS_NOT_EVALUATED,
        "current_market_freshness_checked": False,
        # Terminal: never execution-ready; no side effects.
        "execution_readiness": False,
        "readiness_called": False, "execution_gate_called": False,
        "native_execution_called": False, "pilot_advanced": False,
        "sender_reachable": False, "order_post_count": 0, "amend_post_count": 0,
        "cancel_post_count": 0, "live_order_post_count": 0,
        "notion_called": False, "discord_called": False, "rest_fallback_used": False,
    }

    return WsBoundPlanReviewResult(
        status=WS_BOUND_PLAN_REVIEW_PASS, blockers=(), review_artifact=envelope,
        review_rows=review_rows,
        wrapper_file_sha256=wrapper_sha, wrapper_logical_fingerprint=pre_wrapper_fp,
        canonical_bound_plan_fingerprint=ch1.canonical_bound_plan_fingerprint,
        source_ws_file_sha256=source_sha, source_ws_logical_fingerprint=source_logical_fp,
        anchor_manifest_sha256=manifest_sha, anchor_manifest_fingerprint=recomputed_manifest_fp,
        original_plan_fingerprint=str(manifest.get("original_plan_fingerprint")),
        expected_symbol_set_fingerprint=expected_symbol_set_fp,
        binding_epoch_ns=int(epoch), freshness_threshold_ms=int(threshold),
        offline_exposure_review_complete=True,
        offline_margin_arithmetic_review_complete=True,
        offline_projected_margin_rate_status=OFFLINE_PROJECTED_MARGIN_RATE_UNAVAILABLE,
        offline_projected_margin_review_complete=False,
        account_margin_feasibility_status=ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE,
        binding_time_freshness_verified=True,
        current_market_freshness_status=CURRENT_MARKET_FRESHNESS_NOT_EVALUATED,
        current_market_freshness_checked=False, execution_readiness=False,
        readiness_called=False, execution_gate_called=False,
        native_execution_called=False, pilot_advanced=False)


__all__ = [
    "TASK_ID", "ANCHOR_MANIFEST_SCHEMA", "ANCHOR_MANIFEST_SCHEMA_VERSION",
    "EXPECTED_POLICY_ID", "EXPECTED_STRATEGY_ID", "EXPECTED_STRATEGY_SYMBOL_COUNT",
    "STRICT_MAX_FRESHNESS_THRESHOLD_MS",
    "WS_BOUND_PLAN_REVIEW_PASS", "WS_BOUND_PLAN_REVIEW_INPUT_INVALID",
    "WS_BOUND_PLAN_REVIEW_MANIFEST_MISMATCH", "WS_BOUND_PLAN_REVIEW_SOURCE_MISMATCH",
    "WS_BOUND_PLAN_REVIEW_CONSUMER_FAILED", "WS_BOUND_PLAN_REVIEW_CANONICAL_MISMATCH",
    "WS_BOUND_PLAN_REVIEW_EXPOSURE_FAILED", "WS_BOUND_PLAN_REVIEW_MARGIN_ARITHMETIC_FAILED",
    "WS_BOUND_PLAN_REVIEW_PROVENANCE_FAILED",
    "OFFLINE_PROJECTED_MARGIN_RATE_UNAVAILABLE", "ACCOUNT_MARGIN_FEASIBILITY_UNAVAILABLE",
    "CURRENT_MARKET_FRESHNESS_NOT_EVALUATED",
    "WsBoundPlanReviewAction", "WsBoundPlanReviewResult",
    "build_ws_bound_plan_review",
]
