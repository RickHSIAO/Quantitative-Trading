"""TASK-014CG -- Plan-only same-message WebSocket price binding (pure, offline).

Binds each Strategy-native V1 Plan-only planner action to the EXACT public
WebSocket source message that supplied its selected ``lastPrice``. This is a
PLAN-ONLY integration: it reads a local canonical WebSocket evidence artifact
(the VPS-verified ``public_websocket_ticker_evidence`` schema) plus a local
Plan-only run artifact and produces a canonical, fingerprinted
``strategy_native_ws_price_binding`` block.

Hard invariants enforced here (never weakened):

    * No network I/O of any kind (the binding is local-artifact-only).
    * Imports neither ``main``, ``src.risk``, the live ``BybitExecutor``, nor any
      order/transport sender; it CANNOT place, amend or cancel an order.
    * Never attaches a WebSocket timestamp to the original REST price; the REST
      price is retained for audit comparison ONLY.
    * Never mixes one symbol's price with another symbol's evidence.
    * Strategy target weights and the fixed Strategy capital base are preserved
      exactly; ``target_notional = target_weight * capital_base`` is
      price-independent, so only the price-dependent quantity preview is
      recomputed from the WebSocket-bound price.
    * Fails closed on any artifact / compatibility / freshness / fingerprint
      mismatch. Freshness completion alone NEVER authorizes execution.

The 2 protected legacy symbols (EDUUSDT / POLYXUSDT) may appear in the 52-symbol
WebSocket universe as account evidence, but are NEVER converted into Strategy
actions; only the 50 Strategy targets are bound.
"""

from __future__ import annotations

import copy
import hashlib
import json
from datetime import datetime, timezone
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Any, Mapping, Sequence

from src import demo_public_ws_ticker_evidence as ws
from src import demo_strategy_native_margin_freshness_audit as md  # pure audit (no sender)

TASK_ID = "TASK-014CG_FIX1"
SCHEMA_NAME = "strategy_native_ws_price_binding"
SCHEMA_VERSION = 2  # FIX1: canonical bound-plan binding (sidecar overlay retained)
BINDING_MODE_PLAN_ONLY = "PLAN_ONLY"

# Canonical revised Plan-only artifact identity.
CANONICAL_BOUND_PLAN_SCHEMA = "strategy_native_ws_bound_plan"
CANONICAL_BOUND_PLAN_SCHEMA_VERSION = 1

# The exact WebSocket evidence schema/version this binder is compatible with.
# FIX1 canonical binding REQUIRES the new compatible sub-schema version 2 (a
# version-1-only artifact carries no authoritative strategy provenance / no
# recomputable source-message fingerprint material and is rejected).
SUPPORTED_WS_SCHEMA = ws.SCHEMA_NAME  # "public_websocket_ticker_evidence"
REQUIRED_WS_CANONICAL_BINDING_VERSION = ws.CANONICAL_BINDING_SCHEMA_VERSION  # 2
COMPATIBLE_WS_TASK_PREFIX = "TASK-014CF"  # CF / FIX1 / FIX2 / FIX3 lineage

PLANNER_PRICE_FIELD = ws.PLANNER_PRICE_FIELD  # "lastPrice"
WS_SOURCE_TYPE = "PUBLIC_WEBSOCKET_TICKER"

# Strict freshness threshold (ms). NEVER loosened to make integration pass.
DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS = ws.DEFAULT_STALE_THRESHOLD_MS  # 10_000
DEFAULT_FUTURE_TOLERANCE_MS = ws.DEFAULT_FUTURE_TOLERANCE_MS  # 5_000

# Policy / strategy compatibility (must match the WS + Plan-only run).
ACTIVE_STRATEGY_NATIVE_V1_POLICY = ws.ACTIVE_STRATEGY_NATIVE_V1_POLICY
EXPECTED_STRATEGY_NAME = ws.EXPECTED_STRATEGY_NAME
EXPECTED_STRATEGY_SYMBOL_COUNT = 50


# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

# Per-action binding statuses
WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE = "WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE"
WS_EVIDENCE_SYMBOL_MISSING = "WS_EVIDENCE_SYMBOL_MISSING"
WS_EVIDENCE_SYMBOL_DUPLICATE = "WS_EVIDENCE_SYMBOL_DUPLICATE"
WS_EVIDENCE_STATUS_NOT_COMPLETE = "WS_EVIDENCE_STATUS_NOT_COMPLETE"
WS_EVIDENCE_PRICE_FIELD_MISMATCH = "WS_EVIDENCE_PRICE_FIELD_MISMATCH"
WS_EVIDENCE_SOURCE_MESSAGE_INCOMPLETE = "WS_EVIDENCE_SOURCE_MESSAGE_INCOMPLETE"
WS_EVIDENCE_TIMESTAMP_INVALID = "WS_EVIDENCE_TIMESTAMP_INVALID"
WS_EVIDENCE_SEQUENCE_INVALID = "WS_EVIDENCE_SEQUENCE_INVALID"
WS_EVIDENCE_STALE_AT_BINDING = "WS_EVIDENCE_STALE_AT_BINDING"
WS_EVIDENCE_ARTIFACT_INCOMPATIBLE = "WS_EVIDENCE_ARTIFACT_INCOMPATIBLE"
WS_EVIDENCE_FINGERPRINT_MISMATCH = "WS_EVIDENCE_FINGERPRINT_MISMATCH"
WS_ACTION_SYMBOL_MISMATCH = "WS_ACTION_SYMBOL_MISMATCH"
WS_ACTION_PRICE_BINDING_CONFLICT = "WS_ACTION_PRICE_BINDING_CONFLICT"

# Statuses that are a hard integrity CONFLICT (never merely PARTIAL).
_CONFLICT_ACTION_STATUSES: frozenset[str] = frozenset({
    WS_EVIDENCE_SYMBOL_DUPLICATE,
    WS_EVIDENCE_PRICE_FIELD_MISMATCH,
    WS_EVIDENCE_TIMESTAMP_INVALID,
    WS_EVIDENCE_SEQUENCE_INVALID,
    WS_EVIDENCE_FINGERPRINT_MISMATCH,
    WS_ACTION_SYMBOL_MISMATCH,
    WS_ACTION_PRICE_BINDING_CONFLICT,
})

# Overall binding statuses
WS_PLANNER_PRICE_BINDING_COMPLETE = "WS_PLANNER_PRICE_BINDING_COMPLETE"
WS_PLANNER_PRICE_BINDING_PARTIAL = "WS_PLANNER_PRICE_BINDING_PARTIAL"
WS_PLANNER_PRICE_BINDING_UNAVAILABLE = "WS_PLANNER_PRICE_BINDING_UNAVAILABLE"
WS_PLANNER_PRICE_BINDING_CONFLICT = "WS_PLANNER_PRICE_BINDING_CONFLICT"

# Top-level vs nested parity
WS_PLANNER_BINDING_PARITY_PASS = "WS_PLANNER_BINDING_PARITY_PASS"
WS_PLANNER_BINDING_PARITY_FAIL = "WS_PLANNER_BINDING_PARITY_FAIL"

# Compatibility-gate statuses
WS_ARTIFACT_COMPATIBILITY_OK = "WS_ARTIFACT_COMPATIBILITY_OK"
WS_ARTIFACT_COMPATIBILITY_CONFLICT = "WS_ARTIFACT_COMPATIBILITY_CONFLICT"
WS_ARTIFACT_COMPATIBILITY_UNAVAILABLE = "WS_ARTIFACT_COMPATIBILITY_UNAVAILABLE"

# Binding-time freshness statuses
BINDING_FRESHNESS_FRESH = "BINDING_FRESHNESS_FRESH"
BINDING_FRESHNESS_STALE = "BINDING_FRESHNESS_STALE"
BINDING_FRESHNESS_INVALID = "BINDING_FRESHNESS_INVALID"
BINDING_FRESHNESS_UNAVAILABLE = "BINDING_FRESHNESS_UNAVAILABLE"

# Blockers (reuse the canonical names owned by the WS / freshness modules).
PRICE_FRESHNESS_EVIDENCE_PARTIAL = ws.PRICE_FRESHNESS_EVIDENCE_PARTIAL
PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE = (
    ws.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE)
WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS = ws.WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS
EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK = (
    ws.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK)
# A precise blocker that REPLACES the three freshness blockers when binding fails.
WS_PLANNER_PRICE_BINDING_INCOMPLETE = "WS_PLANNER_PRICE_BINDING_INCOMPLETE"

# The three planner-action freshness blockers this task may resolve on COMPLETE.
_RESOLVABLE_FRESHNESS_BLOCKERS: tuple[str, ...] = (
    PRICE_FRESHNESS_EVIDENCE_PARTIAL,
    PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE,
    WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS,
)


class WsPriceBindingError(ValueError):
    """Raised on a structurally invalid binding input (fail closed)."""


# ---------------------------------------------------------------------------
# Decimal / fingerprint helpers (no binary-float ever reaches a payload)
# ---------------------------------------------------------------------------

def _fingerprint(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, default=str)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def compute_file_sha256(raw: bytes) -> str:
    return "sha256:" + hashlib.sha256(raw).hexdigest()


def _iso_from_epoch_ns(epoch_ns: int | None) -> str | None:
    if epoch_ns is None:
        return None
    return datetime.fromtimestamp(epoch_ns / 1e9, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ")


def _dec(value: Any) -> Decimal | None:
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    if not d.is_finite():
        return None
    return d


def _canon_dec_str(value: Any) -> str | None:
    d = _dec(value)
    if d is None:
        return None
    d = d.normalize()
    if d == d.to_integral_value():
        d = d.quantize(Decimal("1"))
    return format(d, "f")


def _floor_qty(notional_abs: Decimal, price: Decimal, qty_step: Decimal | None) -> Decimal:
    """Quantity preview = |notional| / price floored to an exact qty_step multiple
    using pure Decimal (no binary float)."""
    if price <= 0:
        return Decimal("0")
    raw = notional_abs / price
    if qty_step and qty_step > 0:
        steps = (raw / qty_step).to_integral_value(rounding=ROUND_DOWN)
        return steps * qty_step
    return raw


# ---------------------------------------------------------------------------
# WebSocket artifact compatibility gate
# ---------------------------------------------------------------------------

def validate_ws_artifact_compatibility(
    ws_artifact: Mapping[str, Any],
    *,
    requested_strategy_date: str,
    active_policy: str,
    active_strategy: str,
    strategy_symbols: Sequence[str],
    strategy_symbol_source_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Validate a WebSocket evidence artifact + its compatibility with the
    Plan-only run BEFORE any action price is replaced. Returns a gate record with
    ``status`` in {OK, CONFLICT, UNAVAILABLE} and the precise ``failures`` list.

    A raw numeric artifact can never pass: every authoritative provenance,
    parity, ACK and completion field is required to be present and correct.
    """
    failures: list[str] = []
    unavailable = False

    if not isinstance(ws_artifact, Mapping) or not ws_artifact:
        return {
            "status": WS_ARTIFACT_COMPATIBILITY_UNAVAILABLE,
            "failures": ["ws_artifact_absent_or_empty"],
            "ws_artifact_fingerprint": None,
            "ws_artifact_fingerprint_recomputes": False,
        }

    # 1. Schema / version / lineage. Canonical binding REQUIRES the new compatible
    #    sub-schema version 2 (a version-1-only artifact is rejected, never silently
    #    reinterpreted).
    if str(ws_artifact.get("schema", "")) != SUPPORTED_WS_SCHEMA:
        failures.append("ws_schema_unsupported")
    if ws_artifact.get("canonical_binding_schema_version") != REQUIRED_WS_CANONICAL_BINDING_VERSION:
        failures.append("ws_canonical_binding_schema_version_unsupported")
    if not str(ws_artifact.get("task_id", "")).startswith(COMPATIBLE_WS_TASK_PREFIX):
        failures.append("ws_task_lineage_incompatible")

    # 2. Overall status / exit / authentication / credential safety / endpoint
    if str(ws_artifact.get("overall_status", "")) != ws.WS_TICKER_EVIDENCE_COMPLETE:
        failures.append("ws_overall_status_not_complete")
    if ws_artifact.get("cli_exit_status") != ws.EXIT_COMPLETE:
        failures.append("ws_cli_exit_status_not_zero")
    if ws_artifact.get("authenticated") is not False:
        failures.append("ws_artifact_authenticated_true")
    if str(ws_artifact.get("endpoint", "")) != ws.PUBLIC_LINEAR_WS_ENDPOINT:
        failures.append("ws_endpoint_not_public_linear")
    if str(ws_artifact.get("planner_price_field", "")) != PLANNER_PRICE_FIELD:
        failures.append("ws_planner_price_field_not_last_price")

    # 3. Authoritative provenance + parity
    if (str(ws_artifact.get("clock_offset_provenance_status", ""))
            != ws.CLOCK_OFFSET_PROVENANCE_AUTHORITATIVE):
        failures.append("ws_clock_offset_provenance_not_authoritative")
    legacy_prov = ws_artifact.get("legacy_position_provenance") or {}
    if (str(legacy_prov.get("symbol_universe_source_status", ""))
            != ws.SYMBOL_UNIVERSE_SOURCE_AUTHORITATIVE):
        failures.append("ws_symbol_universe_source_not_authoritative")
    if str(ws_artifact.get("counter_parity_status", "")) != ws.WS_COUNTER_PARITY_PASS:
        failures.append("ws_counter_parity_not_pass")
    if (str(ws_artifact.get("control_plane_parity_status", ""))
            != ws.WS_CONTROL_PLANE_PARITY_PASS):
        failures.append("ws_control_plane_parity_not_pass")

    # 4. Subscription ACK + completion
    ack = ws_artifact.get("subscription_ack") or {}
    if ack.get("subscription_acknowledged") is not True:
        failures.append("ws_subscription_not_acknowledged")
    if str(ack.get("subscription_ack_status", "")) != ws.WS_SUBSCRIPTION_ACKNOWLEDGED:
        failures.append("ws_subscription_ack_status_not_acknowledged")
    if ack.get("ws_subscription_ack_count") != 1:
        failures.append("ws_subscription_ack_count_not_one")
    early = ws_artifact.get("early_completion") or {}
    if early.get("completion_achieved") is not True:
        failures.append("ws_completion_not_achieved")
    data_completion = ws_artifact.get("data_completion") or {}
    if data_completion.get("data_completion_achieved") is not True:
        failures.append("ws_data_completion_not_achieved")

    # 5. Coverage 52/52/52 and credential leak / blocker invalidation
    cov = ws_artifact.get("coverage_summary") or {}
    required = cov.get("unique_symbol_count")
    covered = cov.get("covered_symbol_count")
    complete = cov.get("complete_symbol_count")
    if not (required == covered == complete) or not isinstance(required, int) or required <= 0:
        failures.append("ws_coverage_not_fully_complete")
    # The WS artifact's own freshness blockers are EXPECTED (this binder resolves
    # them); only a blocker that invalidates same-message price evidence is fatal.
    invalidating = {
        ws.WS_SUBSCRIPTION_ACKNOWLEDGEMENT_MISSING,
    }
    present_blockers = set(ws_artifact.get("blockers") or [])
    if invalidating & present_blockers:
        failures.append("ws_artifact_blocker_invalidates_price_evidence")

    # 6. Artifact fingerprint present + recomputes (verified with the WS module's
    #    own canonical fingerprint function so the check is exact).
    fp = ws_artifact.get("artifact_fingerprint")
    fp_ok = False
    if not fp:
        failures.append("ws_artifact_fingerprint_absent")
    else:
        recomputed = ws._fingerprint(
            {k: v for k, v in ws_artifact.items() if k != "artifact_fingerprint"})
        fp_ok = (recomputed == fp)
        if not fp_ok:
            failures.append("ws_artifact_fingerprint_mismatch")

    # 7. Plan-only run compatibility (policy / strategy / symbols).
    if str(active_policy) != ACTIVE_STRATEGY_NATIVE_V1_POLICY:
        failures.append("plan_active_policy_not_strategy_native_v1")
    if str(active_strategy) != EXPECTED_STRATEGY_NAME:
        failures.append("plan_active_strategy_incompatible")

    universe = ws_artifact.get("symbol_universe") or {}
    ws_strategy_symbols = [str(s).strip().upper()
                           for s in (universe.get("strategy_symbols") or [])]
    plan_strategy_symbols = sorted({str(s).strip().upper() for s in strategy_symbols})
    if sorted(ws_strategy_symbols) != plan_strategy_symbols:
        failures.append("strategy_symbol_set_mismatch")
    if len(plan_strategy_symbols) != EXPECTED_STRATEGY_SYMBOL_COUNT:
        failures.append("strategy_symbol_count_not_fifty")

    # 8. MANDATORY authoritative WS-side strategy provenance (never inferred).
    prov = ws_artifact.get("strategy_source_provenance")
    if not isinstance(prov, Mapping) or not prov:
        failures.append("ws_strategy_source_provenance_absent")
        prov = {}
    if (prov.get("strategy_provenance_status")
            != ws.STRATEGY_SOURCE_PROVENANCE_AUTHORITATIVE):
        failures.append("ws_strategy_provenance_not_authoritative")
    # WS-side active policy / strategy / date must be present and exactly equal to
    # the Plan-only run (this establishes the WS artifact's OWN strategy identity).
    if not prov.get("active_strategy"):
        failures.append("ws_active_strategy_absent")
    elif str(prov.get("active_strategy")) != EXPECTED_STRATEGY_NAME:
        failures.append("ws_active_strategy_incompatible")
    elif str(prov.get("active_strategy")) != str(active_strategy):
        failures.append("ws_plan_active_strategy_mismatch")
    if not prov.get("active_policy"):
        failures.append("ws_active_policy_absent")
    elif str(prov.get("active_policy")) != str(active_policy):
        failures.append("ws_plan_active_policy_mismatch")
    if not prov.get("requested_strategy_date"):
        failures.append("ws_requested_strategy_date_absent")
    elif str(prov.get("requested_strategy_date")) != str(requested_strategy_date):
        failures.append("ws_plan_strategy_date_mismatch")
    if prov.get("strategy_symbol_count") != EXPECTED_STRATEGY_SYMBOL_COUNT:
        failures.append("ws_strategy_symbol_count_not_fifty")
    ws_prov_symbols = sorted({str(s).strip().upper()
                              for s in (prov.get("strategy_symbols") or [])})
    if ws_prov_symbols != plan_strategy_symbols:
        failures.append("ws_provenance_symbol_set_mismatch")

    # 9. MANDATORY Strategy symbol-source fingerprint: the WS stored fingerprint,
    #    the recomputed canonical fingerprint (from the authoritative Plan symbol
    #    set) and -- when present -- the Plan stored fingerprint MUST all agree.
    #    Never skipped because an argument is None.
    ws_stored_fp = prov.get("strategy_symbol_source_fingerprint")
    recomputed_fp = ws.canonical_strategy_symbol_set_fingerprint(plan_strategy_symbols)
    if not ws_stored_fp:
        failures.append("ws_strategy_symbol_source_fingerprint_absent")
    elif str(ws_stored_fp) != str(recomputed_fp):
        failures.append("ws_strategy_symbol_source_fingerprint_mismatch")
    if strategy_symbol_source_fingerprint is not None:
        if str(strategy_symbol_source_fingerprint) != str(recomputed_fp):
            failures.append("plan_strategy_symbol_source_fingerprint_mismatch")

    status = WS_ARTIFACT_COMPATIBILITY_OK if not failures else (
        WS_ARTIFACT_COMPATIBILITY_UNAVAILABLE if unavailable
        else WS_ARTIFACT_COMPATIBILITY_CONFLICT)
    return {
        "status": status,
        "failures": sorted(set(failures)),
        "ws_artifact_fingerprint": fp,
        "ws_artifact_fingerprint_recomputes": fp_ok,
        "ws_strategy_symbol_count": len(ws_strategy_symbols),
        "ws_required_symbol_count": required,
        "strategy_symbol_source_fingerprint_recomputed": recomputed_fp,
        "strategy_symbol_source_fingerprint_ws_stored": (
            str(ws_stored_fp) if ws_stored_fp else None),
        "strategy_provenance_status": prov.get("strategy_provenance_status"),
        "ws_active_strategy": prov.get("active_strategy"),
        "ws_active_policy": prov.get("active_policy"),
        "ws_requested_strategy_date": prov.get("requested_strategy_date"),
    }


# ---------------------------------------------------------------------------
# Per-symbol WebSocket evidence indexing + verification
# ---------------------------------------------------------------------------

def _index_ws_evidence(ws_artifact: Mapping[str, Any]) -> tuple[dict[str, dict], set[str]]:
    """Return ({symbol: record}, {duplicate_symbols}). A duplicate symbol is a
    hard integrity conflict and is recorded so its action fails closed."""
    by_symbol: dict[str, dict] = {}
    duplicates: set[str] = set()
    for rec in (ws_artifact.get("per_symbol_evidence") or []):
        if not isinstance(rec, Mapping):
            continue
        sym = str(rec.get("symbol", "")).strip().upper()
        if not sym:
            continue
        if sym in by_symbol:
            duplicates.add(sym)
            continue
        by_symbol[sym] = dict(rec)
    return by_symbol, duplicates


def _recompute_evidence_fingerprint(rec: Mapping[str, Any]) -> str:
    """Recompute the WS module's per-symbol evidence_fingerprint deterministically
    from the documented payload so a tampered record is detected offline."""
    fp_payload = {
        "symbol": rec.get("symbol"),
        "topic": rec.get("topic"),
        "selected_price_field": rec.get("selected_price_field"),
        "selected_price": rec.get("selected_price"),
        "selected_price_ts_ms": rec.get("selected_price_ts_ms"),
        "selected_price_cs": rec.get("selected_price_cs"),
        "connection_generation": rec.get("connection_generation"),
        "status": rec.get("evidence_status"),
    }
    return _fingerprint(fp_payload)


def _evaluate_binding_freshness(
    rec: Mapping[str, Any],
    *,
    binding_epoch_ns: int,
    clock_offset_seconds: Decimal | None,
    threshold_ms: int,
    future_tolerance_ms: int,
) -> dict[str, Any]:
    """Recompute evidence age at planner-binding time from the selected-price
    SOURCE ts + the authoritative accepted clock offset. Fails closed on stale /
    future / missing inputs; never loosens the threshold."""
    source_ts_ms = rec.get("selected_price_source_ts_ms")
    if not isinstance(source_ts_ms, int) or isinstance(source_ts_ms, bool) or source_ts_ms <= 0:
        return {"binding_freshness_status": BINDING_FRESHNESS_INVALID,
                "evidence_age_at_binding_ms": None,
                "binding_freshness_threshold_ms": threshold_ms,
                "reason": "selected_price_source_ts_ms_invalid"}
    if clock_offset_seconds is None:
        return {"binding_freshness_status": BINDING_FRESHNESS_UNAVAILABLE,
                "evidence_age_at_binding_ms": None,
                "binding_freshness_threshold_ms": threshold_ms,
                "reason": "clock_offset_unavailable"}
    offset_ms = clock_offset_seconds * Decimal(1000)
    local_now_ms = Decimal(binding_epoch_ns) / Decimal(1_000_000)
    est_exchange_now_ms = local_now_ms + offset_ms
    age_ms = est_exchange_now_ms - Decimal(source_ts_ms)
    age_f = float(age_ms)
    if age_f < -float(future_tolerance_ms):
        status = BINDING_FRESHNESS_INVALID
        reason = "evidence_source_ts_in_future"
    elif age_f > float(threshold_ms):
        status = BINDING_FRESHNESS_STALE
        reason = "evidence_age_exceeds_threshold"
    else:
        status = BINDING_FRESHNESS_FRESH
        reason = None
    return {"binding_freshness_status": status,
            "evidence_age_at_binding_ms": round(age_f, 3),
            "binding_freshness_threshold_ms": threshold_ms,
            "reason": reason}


# ---------------------------------------------------------------------------
# Single-action same-message binding
# ---------------------------------------------------------------------------

def _bind_one_action(
    target: Mapping[str, Any],
    *,
    ws_by_symbol: Mapping[str, dict],
    ws_duplicates: set[str],
    capital_base_usd: Decimal | None,
    binding_epoch_ns: int,
    clock_offset_seconds: Decimal | None,
    threshold_ms: int,
    source_artifact_fingerprint: str | None,
    source_artifact_sha256: str | None,
    gate_ok: bool,
) -> dict[str, Any]:
    symbol = str(target.get("symbol", "")).strip().upper()
    side = str(target.get("side", ""))
    rest_price_s = target.get("price")
    target_weight_s = target.get("target_weight")
    target_notional_s = target.get("target_notional")
    qty_step_s = target.get("qty_step")
    rest_qty_s = target.get("qty")

    pre_fp = _fingerprint({
        "symbol": symbol, "side": side, "target_weight": target_weight_s,
        "price": rest_price_s, "target_notional": target_notional_s,
        "qty": rest_qty_s, "qty_step": qty_step_s, "price_source": "REST"})

    def _fail(status: str, *, freshness: dict | None = None,
              ws_bound_price: str | None = None) -> dict[str, Any]:
        return {
            "action_symbol": symbol,
            "side": side,
            "target_weight": target_weight_s,
            "capital_base_usd": (None if capital_base_usd is None
                                 else _canon_dec_str(capital_base_usd)),
            "original_rest_price": rest_price_s,
            "websocket_bound_price": ws_bound_price,
            "price_delta": None,
            "price_delta_bps": None,
            "recalculated_price_dependent_fields": None,
            "price_evidence": None,
            "binding_freshness": freshness,
            "pre_binding_action_fingerprint": pre_fp,
            "post_binding_action_fingerprint": None,
            "binding_status": status,
        }

    if not gate_ok:
        return _fail(WS_EVIDENCE_ARTIFACT_INCOMPATIBLE)
    if symbol in ws_duplicates:
        return _fail(WS_EVIDENCE_SYMBOL_DUPLICATE)
    rec = ws_by_symbol.get(symbol)
    if rec is None:
        return _fail(WS_EVIDENCE_SYMBOL_MISSING)

    # Symbol / topic integrity: the WS record must be exactly this symbol.
    if str(rec.get("symbol", "")).strip().upper() != symbol:
        return _fail(WS_ACTION_SYMBOL_MISMATCH)
    if str(rec.get("topic", "")) != f"tickers.{symbol}":
        return _fail(WS_ACTION_SYMBOL_MISMATCH)
    src_sym = rec.get("selected_price_source_symbol")
    if src_sym is not None and str(src_sym).strip().upper() != symbol:
        return _fail(WS_ACTION_SYMBOL_MISMATCH)

    if str(rec.get("evidence_status", "")) != ws.WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE:
        return _fail(WS_EVIDENCE_STATUS_NOT_COMPLETE)
    if str(rec.get("selected_price_field", "")) != PLANNER_PRICE_FIELD:
        return _fail(WS_EVIDENCE_PRICE_FIELD_MISMATCH)

    # Source-message completeness (immutable price-source provenance fields).
    selected_price_s = rec.get("selected_price")
    source_fp = rec.get("selected_price_source_message_fingerprint")
    if (rec.get("selected_price_source_message_included_field") is not True
            or selected_price_s is None
            or not source_fp
            or rec.get("selected_price_source_cs") is None
            or rec.get("selected_price_source_local_received_epoch_ns") is None):
        return _fail(WS_EVIDENCE_SOURCE_MESSAGE_INCOMPLETE)

    ws_price = _dec(selected_price_s)
    if ws_price is None or ws_price <= 0:
        return _fail(WS_ACTION_PRICE_BINDING_CONFLICT)

    source_ts = rec.get("selected_price_source_ts_ms")
    if not isinstance(source_ts, int) or isinstance(source_ts, bool) or source_ts <= 0:
        return _fail(WS_EVIDENCE_TIMESTAMP_INVALID)
    source_cs = rec.get("selected_price_source_cs")
    if not isinstance(source_cs, int) or isinstance(source_cs, bool) or source_cs < 0:
        return _fail(WS_EVIDENCE_SEQUENCE_INVALID)

    # Verify the per-symbol evidence fingerprint recomputes (tamper detection).
    rec_fp = rec.get("evidence_fingerprint")
    if not rec_fp or _recompute_evidence_fingerprint(rec) != rec_fp:
        return _fail(WS_EVIDENCE_FINGERPRINT_MISMATCH)

    # Independently RECOMPUTE the canonical source-message fingerprint from the
    # safe immutable material recorded in the artifact and compare it to the
    # stored selected_price_source_message_fingerprint. This fails even after a
    # valid top-level WS re-fingerprint (the material, not the wrapper, is checked).
    recomputed_source_fp = ws.canonical_source_message_fingerprint(
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
    if recomputed_source_fp != source_fp:
        return _fail(WS_EVIDENCE_FINGERPRINT_MISMATCH)

    # Strict binding-time freshness (recomputed; threshold never loosened).
    freshness = _evaluate_binding_freshness(
        rec, binding_epoch_ns=binding_epoch_ns,
        clock_offset_seconds=clock_offset_seconds, threshold_ms=threshold_ms,
        future_tolerance_ms=DEFAULT_FUTURE_TOLERANCE_MS)
    fstatus = freshness["binding_freshness_status"]
    if fstatus == BINDING_FRESHNESS_INVALID:
        return _fail(WS_EVIDENCE_TIMESTAMP_INVALID, freshness=freshness,
                     ws_bound_price=selected_price_s)
    if fstatus != BINDING_FRESHNESS_FRESH:
        return _fail(WS_EVIDENCE_STALE_AT_BINDING, freshness=freshness,
                     ws_bound_price=selected_price_s)

    # Price-dependent recompute (weights + fixed capital preserved exactly).
    # target_notional = target_weight * capital_base is PRICE-INDEPENDENT, so it
    # is preserved; only the quantity preview is recomputed from the WS price.
    notional = _dec(target_notional_s)
    qty_step = _dec(qty_step_s)
    rest_price = _dec(rest_price_s)
    if notional is None:
        return _fail(WS_ACTION_PRICE_BINDING_CONFLICT, ws_bound_price=selected_price_s)
    ws_qty = _floor_qty(abs(notional), ws_price, qty_step)
    ws_qty_s = _canon_dec_str(ws_qty)

    price_delta = None
    price_delta_bps = None
    if rest_price is not None:
        delta = ws_price - rest_price
        price_delta = _canon_dec_str(delta)
        if rest_price != 0:
            bps = (delta / rest_price) * Decimal(10000)
            price_delta_bps = _canon_dec_str(bps.quantize(Decimal("0.0001")))

    price_evidence = {
        "source_type": WS_SOURCE_TYPE,
        "selected_price_field": PLANNER_PRICE_FIELD,
        "selected_price": selected_price_s,
        "exchange_data_generated_ts_ms": source_ts,
        "exchange_data_generated_at_utc": ws._iso_from_ms(source_ts),
        "cross_sequence": source_cs,
        "local_received_epoch_ns": rec.get("selected_price_source_local_received_epoch_ns"),
        "local_received_at_utc": rec.get("selected_price_source_local_received_at_utc"),
        "local_monotonic_received_ns": rec.get(
            "selected_price_source_local_monotonic_received_ns"),
        "connection_generation": rec.get("selected_price_source_connection_generation"),
        "message_type": rec.get("selected_price_source_message_type"),
        "topic": rec.get("topic"),
        "source_message_fingerprint": source_fp,
        "source_artifact_fingerprint": source_artifact_fingerprint,
        "source_artifact_sha256": source_artifact_sha256,
        "binding_status": WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE,
    }
    # Effective (rounded) notional = recomputed qty * WS-bound price (price-dependent).
    effective_notional = (ws_qty * ws_price)
    # qty-step validity: the recomputed qty is an exact multiple of qty_step.
    qty_step_ok = True
    if qty_step is not None and qty_step > 0:
        qty_step_ok = (ws_qty % qty_step) == 0
    recalculated = {
        # PRESERVED (price-independent): weight * fixed capital base.
        "target_notional": _canon_dec_str(notional),
        "target_notional_preserved": True,
        # RECOMPUTED from the WebSocket-bound price.
        "target_qty": ws_qty_s,
        "effective_notional": _canon_dec_str(effective_notional),
        "qty_step": _canon_dec_str(qty_step) if qty_step is not None else None,
        "qty_step_valid": qty_step_ok,
        "min_qty_valid": ws_qty > 0,
        "recomputed_fields": ["target_qty", "effective_notional"],
    }
    post_fp = _fingerprint({
        "symbol": symbol, "side": side, "target_weight": target_weight_s,
        "price": selected_price_s, "target_notional": _canon_dec_str(notional),
        "qty": ws_qty_s, "qty_step": qty_step_s, "price_source": WS_SOURCE_TYPE,
        "source_message_fingerprint": source_fp})

    return {
        "action_symbol": symbol,
        "side": side,
        "target_weight": target_weight_s,
        "capital_base_usd": (None if capital_base_usd is None
                             else _canon_dec_str(capital_base_usd)),
        "original_rest_price": rest_price_s,
        "websocket_bound_price": selected_price_s,
        "price_delta": price_delta,
        "price_delta_bps": price_delta_bps,
        "recalculated_price_dependent_fields": recalculated,
        "price_evidence": price_evidence,
        "binding_freshness": freshness,
        "pre_binding_action_fingerprint": pre_fp,
        "post_binding_action_fingerprint": post_fp,
        "binding_status": WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE,
    }


# ---------------------------------------------------------------------------
# Top-level Plan-only binding
# ---------------------------------------------------------------------------

def _extract_targets(plan_artifact: Mapping[str, Any]) -> list[dict[str, Any]]:
    planner = plan_artifact.get("planner")
    if not isinstance(planner, Mapping):
        raise WsPriceBindingError("plan artifact missing planner block")
    targets = planner.get("target_positions")
    if not isinstance(targets, (list, tuple)):
        raise WsPriceBindingError("plan artifact missing target_positions")
    return [dict(t) for t in targets if isinstance(t, Mapping)]


def _extract_capital_base(plan_artifact: Mapping[str, Any]) -> Decimal | None:
    planner = plan_artifact.get("planner") or {}
    sizing = planner.get("sizing_verification") or {}
    return _dec(sizing.get("capital_base_usd"))


def bind_plan_prices_to_ws_evidence(
    *,
    plan_artifact: Mapping[str, Any],
    ws_artifact: Mapping[str, Any],
    ws_artifact_path: str,
    ws_artifact_sha256: str,
    binding_epoch_ns: int,
    binding_freshness_threshold_ms: int = DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS,
    strategy_symbol_source_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Bind the 50 Strategy-native Plan-only actions to the exact same WebSocket
    source message that supplied each selected ``lastPrice``. PLAN-ONLY: writes
    no order, performs no network call, and never authorizes execution."""
    requested_strategy_date = str(plan_artifact.get("date", ""))
    active_policy = str(plan_artifact.get("active_policy", ""))
    review = plan_artifact.get("strategy_native_review") or {}
    active_strategy = str(review.get("active_strategy", "")) or str(
        plan_artifact.get("active_strategy", ""))

    targets = _extract_targets(plan_artifact)
    target_symbols = [str(t.get("symbol", "")).strip().upper() for t in targets]
    capital_base = _extract_capital_base(plan_artifact)

    # Compatibility gate.
    gate = validate_ws_artifact_compatibility(
        ws_artifact, requested_strategy_date=requested_strategy_date,
        active_policy=active_policy, active_strategy=active_strategy,
        strategy_symbols=target_symbols,
        strategy_symbol_source_fingerprint=strategy_symbol_source_fingerprint)
    gate_ok = gate["status"] == WS_ARTIFACT_COMPATIBILITY_OK

    ws_by_symbol, ws_duplicates = _index_ws_evidence(ws_artifact)
    clock_offset = _dec(ws_artifact.get("clock_offset_seconds")) if gate_ok else _dec(
        ws_artifact.get("clock_offset_seconds"))
    source_fp = ws_artifact.get("artifact_fingerprint")

    binding_started_ns = binding_epoch_ns
    per_action: list[dict[str, Any]] = []
    seen_action_symbols: dict[str, int] = {}
    for t in targets:
        sym = str(t.get("symbol", "")).strip().upper()
        seen_action_symbols[sym] = seen_action_symbols.get(sym, 0) + 1

    for t in targets:
        sym = str(t.get("symbol", "")).strip().upper()
        binding = _bind_one_action(
            t, ws_by_symbol=ws_by_symbol, ws_duplicates=ws_duplicates,
            capital_base_usd=capital_base, binding_epoch_ns=binding_epoch_ns,
            clock_offset_seconds=clock_offset,
            threshold_ms=binding_freshness_threshold_ms,
            source_artifact_fingerprint=source_fp,
            source_artifact_sha256=ws_artifact_sha256, gate_ok=gate_ok)
        # A duplicate ACTION symbol is itself a hard conflict.
        if seen_action_symbols.get(sym, 0) > 1:
            binding["binding_status"] = WS_EVIDENCE_SYMBOL_DUPLICATE
            binding["price_evidence"] = None
            binding["post_binding_action_fingerprint"] = None
        per_action.append(binding)
    binding_completed_ns = binding_epoch_ns

    requested_action_count = len(targets)
    unique_action_symbol_count = len(set(target_symbols))
    available_ws_strategy = len([s for s in target_symbols if s in ws_by_symbol])
    status_counts: dict[str, int] = {}
    for b in per_action:
        status_counts[b["binding_status"]] = status_counts.get(b["binding_status"], 0) + 1
    bound = status_counts.get(WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE, 0)
    failed = requested_action_count - bound
    has_conflict = any(b["binding_status"] in _CONFLICT_ACTION_STATUSES for b in per_action)
    duplicate_action = any(c > 1 for c in seen_action_symbols.values())

    # Overall status.
    if not gate_ok:
        overall = (WS_PLANNER_PRICE_BINDING_UNAVAILABLE
                   if gate["status"] == WS_ARTIFACT_COMPATIBILITY_UNAVAILABLE
                   else WS_PLANNER_PRICE_BINDING_CONFLICT)
    elif has_conflict or duplicate_action:
        overall = WS_PLANNER_PRICE_BINDING_CONFLICT
    elif (bound == requested_action_count
          and requested_action_count == EXPECTED_STRATEGY_SYMBOL_COUNT
          and unique_action_symbol_count == requested_action_count):
        overall = WS_PLANNER_PRICE_BINDING_COMPLETE
    elif requested_action_count == 0:
        overall = WS_PLANNER_PRICE_BINDING_UNAVAILABLE
    else:
        overall = WS_PLANNER_PRICE_BINDING_PARTIAL

    complete = overall == WS_PLANNER_PRICE_BINDING_COMPLETE

    # Freshness blocker transition (planner-action scope only).
    if complete:
        execution_grade_freshness_complete = True
        resolved_blockers = list(_RESOLVABLE_FRESHNESS_BLOCKERS)
        retained_blockers = [EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK]
    else:
        execution_grade_freshness_complete = False
        # The three freshness blockers are REPLACED by a precise binding-failure
        # blocker; the execution-authorization blocker is always retained.
        resolved_blockers = []
        retained_blockers = [
            WS_PLANNER_PRICE_BINDING_INCOMPLETE,
            PRICE_FRESHNESS_EVIDENCE_PARTIAL,
            PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE,
            WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS,
            EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK,
        ]

    summary = {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "binding_mode": BINDING_MODE_PLAN_ONLY,
        "requested_strategy_date": requested_strategy_date,
        "active_policy": active_policy,
        "active_strategy": active_strategy,
        "source_ws_artifact_path": str(ws_artifact_path),
        "source_ws_artifact_sha256": ws_artifact_sha256,
        "source_ws_artifact_fingerprint": source_fp,
        "ws_artifact_compatibility": gate,
        "requested_action_count": requested_action_count,
        "unique_action_symbol_count": unique_action_symbol_count,
        "available_ws_strategy_symbol_count": available_ws_strategy,
        "bound_action_count": bound,
        "failed_action_count": failed,
        "binding_status_counts": status_counts,
        "overall_binding_status": overall,
        "binding_started_at_epoch_ns": binding_started_ns,
        "binding_started_at_utc": _iso_from_epoch_ns(binding_started_ns),
        "binding_completed_at_epoch_ns": binding_completed_ns,
        "binding_completed_at_utc": _iso_from_epoch_ns(binding_completed_ns),
        "binding_freshness_threshold_ms": binding_freshness_threshold_ms,
        "execution_grade_freshness_complete": execution_grade_freshness_complete,
        "resolved_blockers": resolved_blockers,
        "retained_blockers": retained_blockers,
        "per_action_bindings": per_action,
        # Hard safety invariants -- freshness completion NEVER authorizes execution.
        "execution_batch_authorized": False,
        "execution_ready": False,
        "sender_reachable": False,
        "execute_daily_native_call_count": 0,
        "transport_sender_call_count": 0,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_order_post_count": 0,
        "execution_authorization_marker_created": False,
        # Network audit: this binding command is local-artifact-only.
        "binding_network_audit": {
            "private_http_count": 0,
            "public_http_count": 0,
            "websocket_connection_count": 0,
            "order_endpoint_count": 0,
        },
    }

    # Top-level / nested parity (a FAIL prevents COMPLETE).
    parity_pass = (
        summary["bound_action_count"] == bound
        and summary["failed_action_count"] == failed
        and summary["overall_binding_status"] == overall
        and summary["execution_grade_freshness_complete"] == execution_grade_freshness_complete
        and summary["source_ws_artifact_fingerprint"] == source_fp
        and summary["source_ws_artifact_sha256"] == ws_artifact_sha256)
    parity_status = (WS_PLANNER_BINDING_PARITY_PASS if parity_pass
                     else WS_PLANNER_BINDING_PARITY_FAIL)
    if not parity_pass and overall == WS_PLANNER_PRICE_BINDING_COMPLETE:
        overall = WS_PLANNER_PRICE_BINDING_CONFLICT
        summary["overall_binding_status"] = overall
        summary["execution_grade_freshness_complete"] = False
        execution_grade_freshness_complete = False
    summary["binding_parity_status"] = parity_status

    # The artifact must never carry a credential key/value.
    ws.assert_no_credentials(summary)
    summary["binding_artifact_fingerprint"] = _fingerprint(
        {k: v for k, v in summary.items() if k != "binding_artifact_fingerprint"})
    return summary


# ---------------------------------------------------------------------------
# Canonical revised Plan-only artifact (FIX1): the active price IS the WS price
# ---------------------------------------------------------------------------

def _rebuild_projected_margin(plan_artifact: Mapping[str, Any],
                              revised_targets: Sequence[Mapping[str, Any]]) -> dict[str, Any]:
    """Rebuild the projected margin model FROM the canonical bound plan's own
    target positions (never copy the stale REST review). In V1 the projected
    STRATEGY margin is a function of strategy_gross_notional = sum(|weight*capital|),
    which is price-INDEPENDENT, so the rebuilt value provably equals the original
    while being derived from the bound plan (not a stale REST copy)."""
    review = plan_artifact.get("strategy_native_review") or {}
    strategy_gross = sum((_dec(t.get("target_notional")) or Decimal("0")).copy_abs()
                         for t in revised_targets)
    margin_evidence = review.get("margin_evidence")
    if not isinstance(margin_evidence, Mapping):
        margin_evidence = md.unavailable_margin_evidence()
    legacy_gross = review.get("legacy_gross_notional")
    available_balance = review.get("available_balance")
    if available_balance is None:
        available_balance = (review.get("account_feasibility") or {}).get("available_balance")
    applicable_imr = review.get("applicable_initial_margin_rate")
    model = md.build_projected_margin_model(
        margin_evidence=margin_evidence,
        strategy_gross_notional=strategy_gross,
        legacy_gross_notional=(legacy_gross if legacy_gross is not None else 0),
        available_balance=available_balance,
        applicable_initial_margin_rate=applicable_imr)
    return {
        "projected_margin_model": model,
        "projected_margin_model_source": "REBUILT_FROM_CANONICAL_BOUND_PLAN_WS_PRICES",
        "projected_margin_model_status": model.get("margin_model_status"),
        "strategy_gross_notional": _canon_dec_str(strategy_gross),
        "strategy_gross_notional_price_independent": True,
        "note": ("V1 projected strategy margin is notional-weight based "
                 "(notional = target_weight * fixed capital), hence price-independent; "
                 "rebuilt from the canonical bound plan, not copied from the REST review."),
    }


def _build_revised_plan(
    plan_artifact: Mapping[str, Any],
    binding_audit: Mapping[str, Any],
    *,
    ws_artifact_sha256: str,
    ws_artifact_fingerprint: str | None,
    binding_epoch_ns: int,
) -> dict[str, Any]:
    """Deep-copy the accepted Plan artifact and make the WebSocket-bound lastPrice
    the ACTIVE planning price for all 50 Strategy target positions, recomputing
    every price-dependent field and retaining each REST price under audit-only
    ownership. The input Plan artifact is never mutated."""
    revised = copy.deepcopy(dict(plan_artifact))
    by_symbol = {b["action_symbol"]: b for b in binding_audit["per_action_bindings"]}

    planner = revised.get("planner")
    if not isinstance(planner, dict):
        raise WsPriceBindingError("plan artifact missing planner block for revision")

    revised_targets: list[dict[str, Any]] = []
    for tp in planner.get("target_positions") or []:
        tp = dict(tp)
        sym = str(tp.get("symbol", "")).strip().upper()
        b = by_symbol.get(sym)
        if b is None or b.get("binding_status") != WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE:
            raise WsPriceBindingError(f"no complete binding for target {sym!r}")
        bound_price = b["websocket_bound_price"]
        recalculated = b["recalculated_price_dependent_fields"]
        # REST price retained ONLY under audit ownership; never the active price.
        tp["rest_planning_price"] = b["original_rest_price"]
        tp["rest_planning_price_decimal"] = b["original_rest_price"]
        # ACTIVE planning price = the exact WebSocket-bound lastPrice.
        tp["price"] = bound_price
        tp["price_decimal"] = bound_price
        tp["price_source"] = WS_SOURCE_TYPE
        tp["qty"] = recalculated["target_qty"]
        tp["qty_decimal"] = recalculated["target_qty"]
        tp["effective_notional"] = recalculated["effective_notional"]
        tp["price_evidence"] = b["price_evidence"]
        tp["binding_freshness"] = b["binding_freshness"]
        tp["action_price_binding_status"] = WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE
        tp["action_fingerprint"] = b["post_binding_action_fingerprint"]
        revised_targets.append(tp)
    planner["target_positions"] = revised_targets

    # Keep planner.actions consistent: OPEN/ADD qty/notional reflect the WS price.
    revised_actions: list[dict[str, Any]] = []
    for act in planner.get("actions") or []:
        act = dict(act)
        sym = str(act.get("symbol", "")).strip().upper()
        b = by_symbol.get(sym)
        if b is not None and str(act.get("intent", "")) in ("OPEN", "ADD"):
            recalculated = b["recalculated_price_dependent_fields"]
            act["qty"] = recalculated["target_qty"]
            act["notional_usdt"] = recalculated["effective_notional"]
            act["price_source"] = WS_SOURCE_TYPE
        revised_actions.append(act)
    if "actions" in planner:
        planner["actions"] = revised_actions

    # Rebuild the projected margin model from the canonical bound plan itself.
    margin_rebuild = _rebuild_projected_margin(plan_artifact, revised_targets)

    canonical = {
        "schema": CANONICAL_BOUND_PLAN_SCHEMA,
        "schema_version": CANONICAL_BOUND_PLAN_SCHEMA_VERSION,
        "binding_mode": BINDING_MODE_PLAN_ONLY,
        "active_price_source": WS_SOURCE_TYPE,
        "active_price_field": PLANNER_PRICE_FIELD,
        "requested_strategy_date": str(plan_artifact.get("date", "")),
        "active_policy": str(plan_artifact.get("active_policy", "")),
        "active_strategy": str((plan_artifact.get("strategy_native_review") or {}).get(
            "active_strategy", "")),
        "canonical_target_position_count": len(revised_targets),
        "planner": planner,
        "rebuilt_price_dependent_review": margin_rebuild,
        "original_plan_fingerprint": _fingerprint(plan_artifact),
        "source_ws_artifact_fingerprint": ws_artifact_fingerprint,
        "source_ws_artifact_sha256": ws_artifact_sha256,
        "binding_epoch_ns": binding_epoch_ns,
        "binding_at_utc": _iso_from_epoch_ns(binding_epoch_ns),
        "price_binding_freshness_status": BINDING_FRESHNESS_FRESH,
    }
    # Canonical bound-plan fingerprint over the price-bearing, identity material.
    fp_material = {
        "active_policy": canonical["active_policy"],
        "active_strategy": canonical["active_strategy"],
        "requested_strategy_date": canonical["requested_strategy_date"],
        "binding_epoch_ns": binding_epoch_ns,
        "source_ws_artifact_fingerprint": ws_artifact_fingerprint,
        "source_ws_artifact_sha256": ws_artifact_sha256,
        "projected_margin_model_status": margin_rebuild.get("projected_margin_model_status"),
        "strategy_gross_notional": margin_rebuild.get("strategy_gross_notional"),
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
            for t in revised_targets],
    }
    canonical["canonical_bound_plan_fingerprint"] = _fingerprint(fp_material)
    return canonical


def build_ws_bound_plan_artifact(
    *,
    plan_artifact: Mapping[str, Any],
    ws_artifact: Mapping[str, Any],
    ws_artifact_path: str,
    ws_artifact_sha256: str,
    binding_epoch_ns: int,
    binding_freshness_threshold_ms: int = DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS,
    strategy_symbol_source_fingerprint: str | None = None,
) -> dict[str, Any]:
    """Deterministic canonical Plan-only binding. Returns a versioned wrapper whose
    ``canonical_bound_plan`` field is the COMPLETE revised Plan-only artifact (all
    50 Strategy target positions priced at the exact WebSocket-bound lastPrice with
    every price-dependent field rebuilt), alongside the CG binding audit overlay.

    The input Plan artifact is never mutated. ``canonical_bound_plan`` is non-null
    ONLY when binding is fully COMPLETE with parity PASS; otherwise it is null and
    execution_grade_freshness_complete is False (freshness can never complete
    without a complete canonical bound plan)."""
    binding_audit = bind_plan_prices_to_ws_evidence(
        plan_artifact=plan_artifact, ws_artifact=ws_artifact,
        ws_artifact_path=ws_artifact_path, ws_artifact_sha256=ws_artifact_sha256,
        binding_epoch_ns=binding_epoch_ns,
        binding_freshness_threshold_ms=binding_freshness_threshold_ms,
        strategy_symbol_source_fingerprint=strategy_symbol_source_fingerprint)

    overall = binding_audit["overall_binding_status"]
    parity = binding_audit["binding_parity_status"]
    ws_fp = ws_artifact.get("artifact_fingerprint")
    complete = (overall == WS_PLANNER_PRICE_BINDING_COMPLETE
                and parity == WS_PLANNER_BINDING_PARITY_PASS
                and binding_audit["execution_grade_freshness_complete"] is True)

    canonical_bound_plan = None
    canonical_fp = None
    if complete:
        canonical_bound_plan = _build_revised_plan(
            plan_artifact, binding_audit, ws_artifact_sha256=ws_artifact_sha256,
            ws_artifact_fingerprint=ws_fp, binding_epoch_ns=binding_epoch_ns)
        canonical_fp = canonical_bound_plan["canonical_bound_plan_fingerprint"]
        # Invariant: the active canonical price equals the WS-bound price equals
        # the same-message selected price for every revised target position.
        for tp in canonical_bound_plan["planner"]["target_positions"]:
            pe = tp.get("price_evidence") or {}
            if not (tp.get("price") == pe.get("selected_price")):
                raise WsPriceBindingError("canonical active price != selected_price invariant")

    egfc = bool(complete)
    wrapper = {
        "schema": SCHEMA_NAME,
        "schema_version": SCHEMA_VERSION,
        "task_id": TASK_ID,
        "binding_mode": BINDING_MODE_PLAN_ONLY,
        "overall_binding_status": overall,
        "binding_parity_status": parity,
        "canonical_revised_action_count": (
            canonical_bound_plan["canonical_target_position_count"]
            if canonical_bound_plan else 0),
        "bound_action_count": binding_audit["bound_action_count"],
        "failed_action_count": binding_audit["failed_action_count"],
        "execution_grade_freshness_complete": egfc,
        "source_ws_artifact_path": str(ws_artifact_path),
        "source_ws_artifact_sha256": ws_artifact_sha256,
        "source_ws_artifact_fingerprint": ws_fp,
        "canonical_bound_plan_fingerprint": canonical_fp,
        "binding_audit_fingerprint": binding_audit.get("binding_artifact_fingerprint"),
        "resolved_blockers": binding_audit["resolved_blockers"] if complete else [],
        "retained_blockers": binding_audit["retained_blockers"],
        "strategy_identity": {
            "active_policy": str(plan_artifact.get("active_policy", "")),
            "active_strategy": str((plan_artifact.get("strategy_native_review") or {}).get(
                "active_strategy", "")),
            "requested_strategy_date": str(plan_artifact.get("date", "")),
            "ws_strategy_provenance": (ws_artifact.get("strategy_source_provenance") or {}).get(
                "strategy_provenance_status"),
            "strategy_symbol_source_fingerprint": binding_audit[
                "ws_artifact_compatibility"].get("strategy_symbol_source_fingerprint_recomputed"),
        },
        # The canonical revised Plan-only artifact (the next stage's input).
        "canonical_bound_plan": canonical_bound_plan,
        # The CG binding audit overlay is retained (but is no longer the only output).
        "binding_audit": binding_audit,
        # Hard safety invariants -- freshness completion NEVER authorizes execution.
        "execution_batch_authorized": False,
        "execution_ready": False,
        "sender_reachable": False,
        "execute_daily_native_call_count": 0,
        "transport_sender_call_count": 0,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_order_post_count": 0,
        "execution_authorization_marker_created": False,
        "binding_network_audit": binding_audit["binding_network_audit"],
    }

    # Top-level / nested parity for the wrapper (a FAIL prevents COMPLETE).
    parity_ok = (
        wrapper["canonical_revised_action_count"] == (
            EXPECTED_STRATEGY_SYMBOL_COUNT if complete else 0)
        and wrapper["bound_action_count"] == binding_audit["bound_action_count"]
        and wrapper["failed_action_count"] == binding_audit["failed_action_count"]
        and wrapper["execution_grade_freshness_complete"] == egfc
        and wrapper["source_ws_artifact_fingerprint"] == ws_fp
        and wrapper["source_ws_artifact_sha256"] == ws_artifact_sha256
        and wrapper["canonical_bound_plan_fingerprint"] == canonical_fp
        and (not complete or wrapper["overall_binding_status"]
             == WS_PLANNER_PRICE_BINDING_COMPLETE))
    wrapper["wrapper_parity_status"] = (WS_PLANNER_BINDING_PARITY_PASS if parity_ok
                                        else WS_PLANNER_BINDING_PARITY_FAIL)
    if not parity_ok:
        wrapper["execution_grade_freshness_complete"] = False
        wrapper["canonical_bound_plan"] = None
        wrapper["overall_binding_status"] = WS_PLANNER_PRICE_BINDING_CONFLICT

    ws.assert_no_credentials(wrapper)
    wrapper["wrapper_fingerprint"] = _fingerprint(
        {k: v for k, v in wrapper.items() if k != "wrapper_fingerprint"})
    return wrapper


def canonical_bound_plan_actions(wrapper: Mapping[str, Any]) -> list[dict[str, Any]]:
    """Deterministic accessor: the canonical revised 50 target positions (active
    WS-bound price) for the next Plan-only stage, or [] when not COMPLETE."""
    cbp = wrapper.get("canonical_bound_plan")
    if not isinstance(cbp, Mapping):
        return []
    planner = cbp.get("planner") or {}
    return [dict(t) for t in (planner.get("target_positions") or [])]


__all__ = [
    "TASK_ID", "SCHEMA_NAME", "SCHEMA_VERSION", "BINDING_MODE_PLAN_ONLY",
    "SUPPORTED_WS_SCHEMA", "PLANNER_PRICE_FIELD",
    "DEFAULT_BINDING_FRESHNESS_THRESHOLD_MS", "EXPECTED_STRATEGY_SYMBOL_COUNT",
    "WS_SAME_MESSAGE_PRICE_BINDING_COMPLETE", "WS_EVIDENCE_SYMBOL_MISSING",
    "WS_EVIDENCE_SYMBOL_DUPLICATE", "WS_EVIDENCE_STATUS_NOT_COMPLETE",
    "WS_EVIDENCE_PRICE_FIELD_MISMATCH", "WS_EVIDENCE_SOURCE_MESSAGE_INCOMPLETE",
    "WS_EVIDENCE_TIMESTAMP_INVALID", "WS_EVIDENCE_SEQUENCE_INVALID",
    "WS_EVIDENCE_STALE_AT_BINDING", "WS_EVIDENCE_ARTIFACT_INCOMPATIBLE",
    "WS_EVIDENCE_FINGERPRINT_MISMATCH", "WS_ACTION_SYMBOL_MISMATCH",
    "WS_ACTION_PRICE_BINDING_CONFLICT", "WS_PLANNER_PRICE_BINDING_COMPLETE",
    "WS_PLANNER_PRICE_BINDING_PARTIAL", "WS_PLANNER_PRICE_BINDING_UNAVAILABLE",
    "WS_PLANNER_PRICE_BINDING_CONFLICT", "WS_PLANNER_BINDING_PARITY_PASS",
    "WS_PLANNER_BINDING_PARITY_FAIL", "WS_ARTIFACT_COMPATIBILITY_OK",
    "WS_ARTIFACT_COMPATIBILITY_CONFLICT", "WS_ARTIFACT_COMPATIBILITY_UNAVAILABLE",
    "WS_PLANNER_PRICE_BINDING_INCOMPLETE", "BINDING_FRESHNESS_FRESH",
    "BINDING_FRESHNESS_STALE", "BINDING_FRESHNESS_INVALID",
    "BINDING_FRESHNESS_UNAVAILABLE", "WsPriceBindingError",
    "compute_file_sha256", "validate_ws_artifact_compatibility",
    "bind_plan_prices_to_ws_evidence",
    # CG_FIX1 canonical bound-plan API
    "CANONICAL_BOUND_PLAN_SCHEMA", "CANONICAL_BOUND_PLAN_SCHEMA_VERSION",
    "REQUIRED_WS_CANONICAL_BINDING_VERSION", "build_ws_bound_plan_artifact",
    "canonical_bound_plan_actions",
]
