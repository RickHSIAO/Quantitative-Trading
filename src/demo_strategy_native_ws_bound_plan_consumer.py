"""TASK-014CH1 -- pure, offline consumer contract for the canonical WebSocket-bound
Strategy-native Plan artifact.

This module VALIDATES (and only validates) the canonical bound-plan wrapper produced
by ``src/demo_strategy_native_ws_price_binding.build_ws_bound_plan_artifact`` /
``scripts/bind_plan_prices_to_ws_evidence.py``. It is the read-side contract a LATER
integration task would call before trusting a WebSocket-bound Plan.

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

Reuse, never reinvent: the wrapper fingerprint, the canonical bound-plan fingerprint
and the per-symbol source-message fingerprint are recomputed with the SAME functions
that produced them (``demo_strategy_native_ws_price_binding`` and
``demo_public_ws_ticker_evidence``), so no second incompatible algorithm is created.
Self-reported ``*_matches`` / ``PASS`` / ``COMPLETE`` fields are never trusted on
their own -- each is independently recomputed or verified against caller-supplied
ground truth.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Mapping, Sequence

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_ws_price_binding as wb

TASK_ID = "TASK-014CH1"

EXPECTED_STRATEGY_SYMBOL_COUNT = wb.EXPECTED_STRATEGY_SYMBOL_COUNT  # 50
EXPECTED_LONG_COUNT = 25
EXPECTED_SHORT_COUNT = 25

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
# Pure validation core
# ---------------------------------------------------------------------------

def _recompute_wrapper_fingerprint(artifact: Mapping[str, Any]) -> str:
    return wb._fingerprint({k: v for k, v in artifact.items()
                            if k != "wrapper_fingerprint"})


def _recompute_canonical_bound_plan_fingerprint(cbp: Mapping[str, Any]) -> str:
    """Reconstruct the EXACT fingerprint material the binder used (see
    ``demo_strategy_native_ws_price_binding._build_revised_plan``) and recompute it
    with the binder's own fingerprint function -- no second algorithm."""
    review = cbp.get("rebuilt_price_dependent_review") or {}
    targets = (cbp.get("planner") or {}).get("target_positions") or []
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
             "source_message_fingerprint": (t.get("price_evidence") or {}).get(
                 "source_message_fingerprint"),
             "action_price_binding_status": t.get("action_price_binding_status")}
            for t in targets],
    }
    return wb._fingerprint(fp_material)


def _recompute_source_message_fingerprint(tp: Mapping[str, Any]) -> str | None:
    """Independently recompute the source-message fingerprint from the price-evidence
    fields the artifact carries, using the WS module's canonical function."""
    pe = tp.get("price_evidence")
    if not isinstance(pe, Mapping):
        return None
    return ws.canonical_source_message_fingerprint(
        symbol=tp.get("symbol"),
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


def _check_action_consistency(tp: Mapping[str, Any]) -> list[str]:
    """Independently re-derive price / rounded qty / effective notional / price
    evidence consistency for one target, mirroring the binder's own rules."""
    problems: list[str] = []
    sym = str(tp.get("symbol", "")).strip().upper()
    pe = tp.get("price_evidence")
    if not isinstance(pe, Mapping):
        return [f"{sym}:price_evidence_absent"]

    price_s = tp.get("price")
    if price_s != pe.get("selected_price"):
        problems.append(f"{sym}:active_price_not_selected_price")
    if str(tp.get("price_source", "")) != wb.WS_SOURCE_TYPE:
        problems.append(f"{sym}:price_source_not_websocket")
    if str(tp.get("action_price_binding_status", "")) != wb.WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE:
        problems.append(f"{sym}:binding_status_not_complete")

    price = wb._dec(price_s)
    notional = wb._dec(tp.get("target_notional"))
    qty_step = wb._dec(tp.get("qty_step"))
    if price is None or price <= 0:
        problems.append(f"{sym}:bound_price_invalid")
    if notional is None:
        problems.append(f"{sym}:target_notional_invalid")
    if price is not None and price > 0 and notional is not None:
        expected_qty = wb._floor_qty(notional.copy_abs(), price, qty_step)
        expected_qty_s = wb._canon_dec_str(expected_qty)
        if expected_qty_s != tp.get("qty"):
            problems.append(f"{sym}:rounded_qty_inconsistent")
        expected_eff_s = wb._canon_dec_str(expected_qty * price)
        if expected_eff_s != tp.get("effective_notional"):
            problems.append(f"{sym}:effective_notional_inconsistent")
        if qty_step is not None and qty_step > 0 and (expected_qty % qty_step) != 0:
            problems.append(f"{sym}:qty_not_step_multiple")
        if not expected_qty > 0:
            problems.append(f"{sym}:qty_not_positive")

    stored_fp = pe.get("source_message_fingerprint")
    recomputed_fp = _recompute_source_message_fingerprint(tp)
    if not stored_fp or recomputed_fp != stored_fp:
        problems.append(f"{sym}:source_message_fingerprint_mismatch")
    return problems


def _authorization_failures(artifact: Mapping[str, Any]) -> list[str]:
    problems: list[str] = []
    for f in _FALSE_REQUIRED_FIELDS:
        if artifact.get(f) is not False:
            problems.append(f"{f}_not_false")
    for f in _ZERO_REQUIRED_FIELDS:
        if artifact.get(f) != 0:
            problems.append(f"{f}_nonzero")
    na = artifact.get("binding_network_audit") or {}
    for f in _ZERO_REQUIRED_NETWORK_FIELDS:
        if na.get(f) != 0:
            problems.append(f"binding_network_audit.{f}_nonzero")
    return problems


def validate_ws_bound_plan_artifact(
    artifact: Mapping[str, Any],
    *,
    expected_policy_id: str,
    expected_strategy_id: str,
    expected_run_date: str,
    expected_original_plan_fingerprint: str,
    expected_ws_artifact_sha256: str,
    expected_symbols: Sequence[str],
) -> BoundPlanConsumerResult:
    """Fail-closed validation of a canonical WS-bound Plan wrapper.

    Returns a :class:`BoundPlanConsumerResult`. The validated canonical Plan
    (``validated_actions``) is exposed ONLY when every required check passes; on any
    failure it is empty and ``execution_grade_freshness_complete`` is False."""
    failures: list[str] = []
    blockers: list[str] = []

    def _fail(code: str, blocker: str) -> None:
        if code not in failures:
            failures.append(code)
        blockers.append(blocker)

    cbp = artifact.get("canonical_bound_plan") if isinstance(artifact, Mapping) else None
    cbp_map = cbp if isinstance(cbp, Mapping) else {}

    # Informational echoes (never trusted as proof on their own).
    cbp_fp = cbp_map.get("canonical_bound_plan_fingerprint")
    ws_sha = artifact.get("source_ws_artifact_sha256") if isinstance(artifact, Mapping) else None
    original_fp = cbp_map.get("original_plan_fingerprint")

    # --- Stage 0: structural / schema / version --------------------------------
    if not isinstance(artifact, Mapping) or not artifact:
        return _result(WS_BOUND_PLAN_SCHEMA_INVALID, [WS_BOUND_PLAN_SCHEMA_INVALID],
                       ["artifact_absent_or_empty"], cbp_fp, ws_sha, original_fp)
    if (str(artifact.get("schema", "")) != wb.SCHEMA_NAME
            or artifact.get("schema_version") != wb.SCHEMA_VERSION
            or str(artifact.get("task_id", "")) != wb.TASK_ID
            or str(artifact.get("binding_mode", "")) != wb.BINDING_MODE_PLAN_ONLY):
        _fail(WS_BOUND_PLAN_SCHEMA_INVALID, "wrapper_schema_or_version_unsupported")
        return _finalize(failures, blockers, False, False, cbp_fp, ws_sha, original_fp, ())

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
    canonical_present = isinstance(cbp, Mapping) and bool(cbp)

    binding_audit = artifact.get("binding_audit") or {}
    status_counts = binding_audit.get("binding_status_counts") or {}
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

    # Canonical sub-schema must also be the supported bound-plan schema.
    if (str(cbp_map.get("schema", "")) != wb.CANONICAL_BOUND_PLAN_SCHEMA
            or cbp_map.get("schema_version") != wb.CANONICAL_BOUND_PLAN_SCHEMA_VERSION):
        _fail(WS_BOUND_PLAN_SCHEMA_INVALID, "canonical_bound_plan_schema_unsupported")

    # --- Stage 3: canonical bound-plan fingerprint recomputes ------------------
    try:
        recomputed_cbp_fp = _recompute_canonical_bound_plan_fingerprint(cbp_map)
    except Exception:  # noqa: BLE001
        recomputed_cbp_fp = None
    if not cbp_fp or recomputed_cbp_fp != cbp_fp:
        _fail(WS_BOUND_PLAN_FINGERPRINT_MISMATCH, "canonical_bound_plan_fingerprint_does_not_recompute")

    # --- Stage 4: provenance / original plan / WS artifact ---------------------
    identity = artifact.get("strategy_identity") or {}
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

    if (str(ws_sha or "") != str(expected_ws_artifact_sha256)
            or str(cbp_map.get("source_ws_artifact_sha256", "")) != str(expected_ws_artifact_sha256)):
        _fail(WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH, "ws_artifact_sha256_mismatch")

    # --- Stage 5: symbol set + 25/25 structure ---------------------------------
    targets = (cbp_map.get("planner") or {}).get("target_positions") or []
    symbols = [str(t.get("symbol", "")).strip().upper() for t in targets]
    expected_set = {str(s).strip().upper() for s in expected_symbols}
    seen: set[str] = set()
    dups = {s for s in symbols if s in seen or seen.add(s)}
    if dups:
        _fail(WS_BOUND_PLAN_DUPLICATE_SYMBOL, f"duplicate_symbols:{sorted(dups)}")
    if (set(symbols) != expected_set
            or len(expected_set) != EXPECTED_STRATEGY_SYMBOL_COUNT
            or len(symbols) != EXPECTED_STRATEGY_SYMBOL_COUNT):
        _fail(WS_BOUND_PLAN_SYMBOL_SET_MISMATCH, "symbol_set_not_exactly_expected_fifty")
    long_n = sum(1 for t in targets if str(t.get("side", "")).strip().lower() == "long")
    short_n = sum(1 for t in targets if str(t.get("side", "")).strip().lower() == "short")
    if long_n != EXPECTED_LONG_COUNT or short_n != EXPECTED_SHORT_COUNT:
        _fail(WS_BOUND_PLAN_SYMBOL_SET_MISMATCH,
              f"long_short_structure_not_25_25:long={long_n},short={short_n}")

    # --- Stage 6: per-action price / qty / notional / fingerprint consistency --
    action_problems: list[str] = []
    for t in targets:
        action_problems.extend(_check_action_consistency(t))
    if action_problems:
        _fail(WS_BOUND_PLAN_ACTION_INCONSISTENT, "; ".join(action_problems[:20]))

    # --- Stage 7: authorization / dispatch counters all false / zero -----------
    auth_problems = _authorization_failures(artifact)
    if auth_problems:
        _fail(WS_BOUND_PLAN_AUTHORIZATION_PRESENT, "; ".join(auth_problems))

    if failures:
        return _finalize(failures, blockers, provenance_ok, True, cbp_fp, ws_sha, original_fp, ())

    validated = tuple(
        ValidatedBoundAction(
            symbol=str(t.get("symbol", "")).strip().upper(),
            side=str(t.get("side", "")),
            target_weight=t.get("target_weight"),
            price=t.get("price"),
            qty=t.get("qty"),
            qty_step=t.get("qty_step"),
            target_notional=t.get("target_notional"),
            effective_notional=t.get("effective_notional"),
            source_message_fingerprint=(t.get("price_evidence") or {}).get(
                "source_message_fingerprint"),
            action_price_binding_status=t.get("action_price_binding_status"))
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
        status = WS_BOUND_PLAN_SCHEMA_INVALID if not ordered else ordered[0]
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
    "WS_BOUND_PLAN_CONSUMER_PASS",
    "WS_BOUND_PLAN_SCHEMA_INVALID", "WS_BOUND_PLAN_WRAPPER_FINGERPRINT_MISMATCH",
    "WS_BOUND_PLAN_FINGERPRINT_MISMATCH", "WS_BOUND_PLAN_PROVENANCE_MISMATCH",
    "WS_BOUND_PLAN_ORIGINAL_PLAN_MISMATCH", "WS_BOUND_PLAN_WS_ARTIFACT_MISMATCH",
    "WS_BOUND_PLAN_SYMBOL_SET_MISMATCH", "WS_BOUND_PLAN_DUPLICATE_SYMBOL",
    "WS_BOUND_PLAN_INCOMPLETE", "WS_BOUND_PLAN_STALE", "WS_BOUND_PLAN_PARITY_FAIL",
    "WS_BOUND_PLAN_ACTION_INCONSISTENT", "WS_BOUND_PLAN_AUTHORIZATION_PRESENT",
    "WsBoundPlanConsumerError", "ValidatedBoundAction", "BoundPlanConsumerResult",
    "load_ws_bound_plan_artifact", "validate_ws_bound_plan_artifact",
]
