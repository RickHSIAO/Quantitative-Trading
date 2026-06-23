"""TASK-014CE -- authoritative account-mode / margin-tier / exchange-clock evidence.

Plan-only evidence layer that sits ON TOP of the accepted TASK-014CD chain. It adds
three authoritative read-only evidence sources WITHOUT ever assuming or fabricating a
value:

  * account-mode evidence from ``GET /v5/account/info`` (marginMode,
    unifiedMarginStatus, updatedTime, ...), with an explicit availability status and a
    deterministic fingerprint;
  * public risk-limit (margin-tier) evidence from ``GET /v5/market/risk-limit``, with a
    FAIL-CLOSED applicable-tier selection that proves the combined projected exposure
    fits inside the selected tier's ``riskLimitValue`` before any tier is used (never
    inferring a rate from ``maxLeverage`` alone, never ``1 / maxLeverage`` unless the
    authoritative ``initialMargin`` confirms the same rate, never reusing
    ``accountIMRate``);
  * exchange-clock evidence from ``GET /v5/market/time`` used to BRACKET the price
    collection window. The Bybit server time is explicitly NOT labelled a per-symbol
    quote timestamp, and freshness can never be promoted to PASS from a server-time
    bracket or a REST response-envelope time alone.

It then computes an explicit margin-mode-branched projected-margin model
(REGULAR / ISOLATED / PORTFOLIO) that becomes COMPLETE only when applicability is
proven for every Strategy action, with exact Decimal arithmetic.

Every function here is PURE (no network, no secrets, no global state) so the audit is
deterministic for identical evidence. This module authorises NOTHING and sends
NOTHING. The execution batch remains UNAUTHORISED in this task even if all evidence
passes.
"""

from __future__ import annotations

import hashlib
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from src import demo_strategy_native_margin_freshness_audit as md

TASK_ID = "TASK-014CE"

# Exact Bybit V5 read-only endpoints this evidence layer is built from.
EP_ACCOUNT_INFO = "/v5/account/info"
EP_MARKET_TIME = "/v5/market/time"
EP_RISK_LIMIT = "/v5/market/risk-limit"

# --- Authoritative account margin modes (Bybit V5 marginMode values) --------
MARGIN_MODE_ISOLATED = "ISOLATED_MARGIN"
MARGIN_MODE_REGULAR = "REGULAR_MARGIN"
MARGIN_MODE_PORTFOLIO = "PORTFOLIO_MARGIN"
ALLOWED_MARGIN_MODES = frozenset({MARGIN_MODE_ISOLATED, MARGIN_MODE_REGULAR, MARGIN_MODE_PORTFOLIO})

# --- Account-mode evidence availability -------------------------------------
ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE = "ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE"
ACCOUNT_MODE_EVIDENCE_UNAVAILABLE = "ACCOUNT_MODE_EVIDENCE_UNAVAILABLE"
ACCOUNT_MODE_EVIDENCE_MALFORMED = "ACCOUNT_MODE_EVIDENCE_MALFORMED"

# --- Risk-tier selection statuses -------------------------------------------
RISK_TIER_APPLICABLE = "RISK_TIER_APPLICABLE"
RISK_TIER_EVIDENCE_MISSING = "RISK_TIER_EVIDENCE_MISSING"
RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS = "RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS"
RISK_TIER_SCOPE_NOT_APPLICABLE_TO_MARGIN_MODE = "RISK_TIER_SCOPE_NOT_APPLICABLE_TO_MARGIN_MODE"
RISK_TIER_CONFLICT = "RISK_TIER_CONFLICT"

# --- Per-action projected-margin evidence statuses --------------------------
PROJECTED_MARGIN_EVIDENCE_COMPLETE = "PROJECTED_MARGIN_EVIDENCE_COMPLETE"
PROJECTED_MARGIN_EVIDENCE_PARTIAL = "PROJECTED_MARGIN_EVIDENCE_PARTIAL"
PROJECTED_MARGIN_EVIDENCE_UNAVAILABLE = "PROJECTED_MARGIN_EVIDENCE_UNAVAILABLE"

# --- Margin-model statuses (shared vocabulary with TASK-014CD) --------------
AUTHORITATIVE_MARGIN_MODEL_COMPLETE = md.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
AUTHORITATIVE_MARGIN_MODEL_PARTIAL = md.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
AUTHORITATIVE_MARGIN_MODEL_UNAVAILABLE = "AUTHORITATIVE_MARGIN_MODEL_UNAVAILABLE"
MARGIN_EVIDENCE_CONFLICT = md.MARGIN_EVIDENCE_CONFLICT

# --- Readiness blockers introduced / resolved by this task ------------------
ACCOUNT_MARGIN_MODE_UNAVAILABLE = "ACCOUNT_MARGIN_MODE_UNAVAILABLE"
APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE = "APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE"
PORTFOLIO_MARGIN_STATIC_RATE_NOT_APPLICABLE = "PORTFOLIO_MARGIN_STATIC_RATE_NOT_APPLICABLE"
ISOLATED_MARGIN_PER_SYMBOL_SCOPE_NOT_PROVEN = "ISOLATED_MARGIN_PER_SYMBOL_SCOPE_NOT_PROVEN"
RISK_TIER_EVIDENCE_INCOMPLETE = "RISK_TIER_EVIDENCE_INCOMPLETE"
RISK_TIER_SCOPE_NOT_PROVEN = "RISK_TIER_SCOPE_NOT_PROVEN"
PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE = "PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE"
EXCHANGE_CLOCK_BRACKET_ONLY = "EXCHANGE_CLOCK_BRACKET_ONLY"
EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK = md.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK

# --- Network-audit consistency (extended, complete-account) -----------------
NETWORK_AUDIT_CONSISTENT = md.NETWORK_AUDIT_CONSISTENT
NETWORK_AUDIT_COUNTER_MISMATCH = md.NETWORK_AUDIT_COUNTER_MISMATCH

# --- Observed (non-atomic) snapshot blocker (preserved from TASK-014CD/FIX1) -
NON_ATOMIC_MARGIN_SNAPSHOT = "NON_ATOMIC_MARGIN_SNAPSHOT"

# --- Exchange-clock availability statuses -----------------------------------
EXCHANGE_CLOCK_BRACKET_AVAILABLE = "EXCHANGE_CLOCK_BRACKET_AVAILABLE"
EXCHANGE_CLOCK_UNAVAILABLE = "EXCHANGE_CLOCK_UNAVAILABLE"

# --- Clock-offset evidence statuses -----------------------------------------
CLOCK_OFFSET_AVAILABLE = "CLOCK_OFFSET_AVAILABLE"
CLOCK_OFFSET_UNAVAILABLE = "CLOCK_OFFSET_UNAVAILABLE"
CLOCK_OFFSET_LOCAL_TIMING_UNAVAILABLE = "CLOCK_OFFSET_LOCAL_TIMING_UNAVAILABLE"

# Exact Bybit V5 read-only endpoint + field paths for the captured evidence.
ACCOUNT_MODE_FIELD_PATHS: dict[str, str] = {
    "margin_mode": "/v5/account/info -> result.marginMode",
    "unified_margin_status": "/v5/account/info -> result.unifiedMarginStatus",
    "updated_time": "/v5/account/info -> result.updatedTime",
    "is_master_trader": "/v5/account/info -> result.isMasterTrader (when returned)",
    "spot_hedging_status": "/v5/account/info -> result.spotHedgingStatus (when returned)",
    "response_envelope_time": "/v5/account/info -> top-level time (REST envelope, NOT a quote time)",
}
RISK_LIMIT_FIELD_PATHS: dict[str, str] = {
    "risk_id": "/v5/market/risk-limit -> result.list[].id",
    "risk_limit_value": "/v5/market/risk-limit -> result.list[].riskLimitValue",
    "initial_margin": "/v5/market/risk-limit -> result.list[].initialMargin (RATE)",
    "maintenance_margin": "/v5/market/risk-limit -> result.list[].maintenanceMargin (RATE)",
    "max_leverage": "/v5/market/risk-limit -> result.list[].maxLeverage",
    "is_lowest_risk": "/v5/market/risk-limit -> result.list[].isLowestRisk",
    "next_page_cursor": "/v5/market/risk-limit -> result.nextPageCursor (pagination)",
}
EXCHANGE_CLOCK_FIELD_PATHS: dict[str, str] = {
    "time_second": "/v5/market/time -> result.timeSecond (exchange server time, seconds)",
    "time_nano": "/v5/market/time -> result.timeNano (exchange server time, nanoseconds)",
    "response_envelope_time": "/v5/market/time -> top-level time (REST envelope, NOT a quote time)",
}


# ---------------------------------------------------------------------------
# Decimal / fingerprint helpers (canonical strings; no binary-float artifact)
# ---------------------------------------------------------------------------


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _opt_dec(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None


def _fmt(value: Any) -> str:
    v = _dec(value).normalize()
    if v == v.to_integral_value():
        v = v.quantize(Decimal("1"))
    return format(v, "f")


def _opt_fmt(value: Any) -> str | None:
    if value is None:
        return None
    d = _opt_dec(value)
    return _fmt(d) if d is not None else None


def _sha(parts: Sequence[Any]) -> str:
    body = "|".join(str(p) for p in parts)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# 1. Account-mode evidence (GET /v5/account/info)
# ---------------------------------------------------------------------------


def normalize_account_mode_evidence(
    *,
    source_endpoint: str = EP_ACCOUNT_INFO,
    environment: str = "bybit_demo",
    margin_mode: Any = None,
    unified_margin_status: Any = None,
    updated_time: Any = None,
    is_master_trader: Any = None,
    spot_hedging_status: Any = None,
    request_started_at_utc: Any = None,
    response_received_at_utc: Any = None,
    request_elapsed_ms: Any = None,
    response_envelope_time: Any = None,
    response_present: bool = True,
) -> dict[str, Any]:
    """Normalise authoritative read-only account-mode evidence. The marginMode is
    validated against the allowed Bybit V5 set; an unrecognised non-empty value fails
    closed as MALFORMED (never coerced). An absent response is UNAVAILABLE. Nothing is
    fabricated; absent optional fields stay None."""
    mode_raw = None if margin_mode is None else str(margin_mode).strip()
    if not response_present:
        availability = ACCOUNT_MODE_EVIDENCE_UNAVAILABLE
        parsed_mode: str | None = None
    elif mode_raw is None or mode_raw == "":
        availability = ACCOUNT_MODE_EVIDENCE_UNAVAILABLE
        parsed_mode = None
    elif mode_raw in ALLOWED_MARGIN_MODES:
        availability = ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE
        parsed_mode = mode_raw
    else:
        availability = ACCOUNT_MODE_EVIDENCE_MALFORMED
        parsed_mode = None

    evidence: dict[str, Any] = {
        "source_endpoint": source_endpoint,
        "environment": environment,
        "account_info_field_paths": dict(ACCOUNT_MODE_FIELD_PATHS),
        "margin_mode": parsed_mode,
        "margin_mode_raw": mode_raw,
        # Retained with its native type (Bybit unifiedMarginStatus is an integer enum).
        "unified_margin_status": unified_margin_status,
        "updated_time": (None if updated_time is None else str(updated_time)),
        "is_master_trader": is_master_trader,
        "spot_hedging_status": (None if spot_hedging_status is None
                                else str(spot_hedging_status)),
        # REST envelope time is explicitly NOT a per-symbol quote timestamp.
        "response_envelope_exchange_time": (None if response_envelope_time is None
                                            else str(response_envelope_time)),
        "request_started_at_utc": request_started_at_utc,
        "response_received_at_utc": response_received_at_utc,
        "request_elapsed_ms": (_fmt(request_elapsed_ms) if request_elapsed_ms is not None else None),
        "account_mode_evidence_status": availability,
    }
    evidence["account_info_evidence_fingerprint"] = _sha([
        source_endpoint, environment, parsed_mode, mode_raw,
        evidence["unified_margin_status"], evidence["updated_time"],
        evidence["is_master_trader"], evidence["spot_hedging_status"],
        availability,
    ])
    return evidence


def unavailable_account_mode_evidence() -> dict[str, Any]:
    return normalize_account_mode_evidence(response_present=False)


# ---------------------------------------------------------------------------
# 2. Risk-limit (margin-tier) evidence + fail-closed tier selection
# ---------------------------------------------------------------------------


def normalize_risk_tiers(symbol: str, raw_tiers: Sequence[Mapping[str, Any]] | None) -> list[dict[str, Any]]:
    """Normalise authoritative risk-limit tiers for one symbol into canonical Decimal
    strings, sorted DETERMINISTICALLY by ascending ``riskLimitValue`` (then id). The
    ``initialMargin`` / ``maintenanceMargin`` fields are RATES (fractions) and are kept
    verbatim from the authoritative response; nothing is inferred from ``maxLeverage``."""
    out: list[dict[str, Any]] = []
    for t in (raw_tiers or []):
        rl = _opt_dec(t.get("riskLimitValue", t.get("risk_limit_value")))
        im = _opt_dec(t.get("initialMargin", t.get("initial_margin")))
        mm = _opt_dec(t.get("maintenanceMargin", t.get("maintenance_margin")))
        lev = _opt_dec(t.get("maxLeverage", t.get("max_leverage")))
        rid = t.get("id", t.get("riskId", t.get("risk_id")))
        is_lowest = t.get("isLowestRisk", t.get("is_lowest_risk"))
        out.append({
            "symbol": symbol,
            "risk_id": rid,
            "risk_limit_value": _opt_fmt(rl),
            "initial_margin_rate": _opt_fmt(im),
            "maintenance_margin_rate": _opt_fmt(mm),
            "max_leverage": _opt_fmt(lev),
            "is_lowest_risk": is_lowest,
            "_rl": rl,
        })
    # Deterministic order: ascending riskLimitValue, then id (as string).
    out.sort(key=lambda r: (r["_rl"] if r["_rl"] is not None else Decimal("0"),
                            str(r["risk_id"])))
    for r in out:
        r.pop("_rl", None)
    return out


def _risk_tier_fingerprint(symbol: str, tiers: Sequence[Mapping[str, Any]]) -> str:
    return _sha([symbol, *(f"{t['risk_id']}:{t['risk_limit_value']}:{t['initial_margin_rate']}:"
                           f"{t['maintenance_margin_rate']}:{t['max_leverage']}" for t in tiers)])


def select_risk_tier(
    *,
    symbol: str,
    combined_projected_exposure: Any,
    tiers: Sequence[Mapping[str, Any]] | None,
) -> dict[str, Any]:
    """Fail-closed applicable-tier selection. A tier is selected ONLY when the combined
    projected exposure is PROVEN to fit within the tier's ``riskLimitValue`` and that
    tier carries a valid authoritative ``initialMargin`` rate.

    Selection rule (cumulative bands, sorted ascending): pick the SMALLEST tier whose
    ``riskLimitValue >= combined_projected_exposure``. Exposure beyond the largest
    retrieved tier fails closed (never silently clamped to the top tier, never the
    lowest tier merely because ``isLowestRisk=1``). The applicable rate is read ONLY
    from the authoritative ``initialMargin`` field; it is NEVER derived from
    ``maxLeverage`` (no ``1 / maxLeverage``)."""
    norm = normalize_risk_tiers(symbol, tiers)
    fp = _risk_tier_fingerprint(symbol, norm)
    exposure = _dec(combined_projected_exposure).copy_abs()
    base = {
        "symbol": symbol,
        "combined_projected_symbol_exposure_usdt": _fmt(exposure),
        "retrieved_tier_count": len(norm),
        "tiers": norm,
        "applicable_risk_tier_id": None,
        "applicable_risk_limit_value": None,
        "applicable_initial_margin_rate": None,
        "applicable_maintenance_margin_rate": None,
        "applicable_max_leverage": None,
        "risk_tier_evidence_fingerprint": fp,
    }
    if not norm:
        return {**base, "risk_tier_selection_status": RISK_TIER_EVIDENCE_MISSING}

    # The retrieved set must include at least one tier with a usable riskLimitValue.
    with_rl = [t for t in norm if t["risk_limit_value"] is not None]
    if not with_rl:
        return {**base, "risk_tier_selection_status": RISK_TIER_EVIDENCE_MISSING}

    max_rl = max(_dec(t["risk_limit_value"]) for t in with_rl)
    if exposure > max_rl:
        return {**base, "risk_tier_selection_status": RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS}

    selected = None
    for t in with_rl:  # already ascending
        if _dec(t["risk_limit_value"]) >= exposure:
            selected = t
            break
    if selected is None:
        return {**base, "risk_tier_selection_status": RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS}

    rate = _opt_dec(selected["initial_margin_rate"])
    if rate is None or rate <= 0:
        # The applicable tier exists by exposure but lacks an authoritative IM rate.
        return {**base, "risk_tier_selection_status": RISK_TIER_EVIDENCE_MISSING}

    return {
        **base,
        "applicable_risk_tier_id": selected["risk_id"],
        "applicable_risk_limit_value": selected["risk_limit_value"],
        "applicable_initial_margin_rate": selected["initial_margin_rate"],
        "applicable_maintenance_margin_rate": selected["maintenance_margin_rate"],
        "applicable_max_leverage": selected["max_leverage"],
        "risk_tier_selection_status": RISK_TIER_APPLICABLE,
    }


# ---------------------------------------------------------------------------
# 3. Per-action projected margin with explicit margin-mode branching
# ---------------------------------------------------------------------------


def project_action_margin(
    *,
    symbol: str,
    projected_symbol_notional_usdt: Any,
    existing_same_symbol_notional_usdt: Any = 0,
    tiers: Sequence[Mapping[str, Any]] | None,
    margin_mode: str | None,
) -> dict[str, Any]:
    """Per-action projected margin. The applicable risk tier is selected from the
    COMBINED projected + existing same-symbol exposure (never target notional alone when
    a current same-symbol position exists). The projected action initial/maintenance
    margin become authoritative ONLY under REGULAR_MARGIN with a proven applicable tier:

      * REGULAR_MARGIN  -> projected IM = projected_symbol_notional * initialMargin_rate
                           projected MM = projected_symbol_notional * maintenanceMargin_rate
                           status = PROJECTED_MARGIN_EVIDENCE_COMPLETE
      * ISOLATED_MARGIN -> static tier data is informational; per-symbol isolated
                           applicability is NOT proven from read-only data -> PARTIAL
      * PORTFOLIO_MARGIN-> static per-symbol rate is NOT a complete portfolio model ->
                           PARTIAL (RISK_TIER_SCOPE_NOT_APPLICABLE_TO_MARGIN_MODE)
      * unknown / tier not applicable -> PARTIAL / UNAVAILABLE (fail closed).
    """
    proj_notional = _dec(projected_symbol_notional_usdt).copy_abs()
    existing = _dec(existing_same_symbol_notional_usdt).copy_abs()
    combined = proj_notional + existing
    sel = select_risk_tier(symbol=symbol, combined_projected_exposure=combined, tiers=tiers)
    tier_status = sel["risk_tier_selection_status"]
    rate = _opt_dec(sel.get("applicable_initial_margin_rate"))
    mm_rate = _opt_dec(sel.get("applicable_maintenance_margin_rate"))

    projected_im: Decimal | None = None
    projected_mm: Decimal | None = None
    mode = (margin_mode or "").strip() or None

    if tier_status != RISK_TIER_APPLICABLE or rate is None:
        status = (PROJECTED_MARGIN_EVIDENCE_UNAVAILABLE
                  if tier_status in (RISK_TIER_EVIDENCE_MISSING,
                                     RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS)
                  else PROJECTED_MARGIN_EVIDENCE_PARTIAL)
    elif mode == MARGIN_MODE_REGULAR:
        projected_im = proj_notional * rate
        projected_mm = (proj_notional * mm_rate) if mm_rate is not None else None
        status = PROJECTED_MARGIN_EVIDENCE_COMPLETE
    elif mode == MARGIN_MODE_ISOLATED:
        # Static per-symbol tier is informational; isolated-position applicability is
        # not proven from read-only data.
        status = PROJECTED_MARGIN_EVIDENCE_PARTIAL
        tier_status = RISK_TIER_SCOPE_NOT_APPLICABLE_TO_MARGIN_MODE \
            if tier_status == RISK_TIER_APPLICABLE else tier_status
    elif mode == MARGIN_MODE_PORTFOLIO:
        # Static per-symbol initialMargin is NOT a complete portfolio-margin model.
        status = PROJECTED_MARGIN_EVIDENCE_PARTIAL
        tier_status = RISK_TIER_SCOPE_NOT_APPLICABLE_TO_MARGIN_MODE
    else:
        status = PROJECTED_MARGIN_EVIDENCE_PARTIAL

    return {
        "symbol": symbol,
        "margin_mode": mode,
        "projected_symbol_notional_usdt": _fmt(proj_notional),
        "existing_same_symbol_notional_usdt": _fmt(existing),
        "combined_projected_symbol_exposure_usdt": _fmt(combined),
        "applicable_risk_tier_id": sel.get("applicable_risk_tier_id"),
        "applicable_risk_limit_value": sel.get("applicable_risk_limit_value"),
        "applicable_initial_margin_rate": sel.get("applicable_initial_margin_rate"),
        "applicable_maintenance_margin_rate": sel.get("applicable_maintenance_margin_rate"),
        "applicable_max_leverage": sel.get("applicable_max_leverage"),
        "risk_tier_selection_status": tier_status,
        "risk_tier_evidence_fingerprint": sel.get("risk_tier_evidence_fingerprint"),
        "projected_action_initial_margin_usdt": _opt_fmt(projected_im),
        "projected_action_maintenance_margin_usdt": _opt_fmt(projected_mm),
        "projected_margin_evidence_status": status,
    }


# ---------------------------------------------------------------------------
# 4. Projected Strategy margin model (margin-mode branched, exact Decimal sum)
# ---------------------------------------------------------------------------


def build_account_margin_model(
    *,
    account_mode_evidence: Mapping[str, Any],
    per_action_projections: Sequence[Mapping[str, Any]],
    observed_legacy_position_initial_margin_sum_usdt: Any = None,
    available_balance: Any = None,
) -> dict[str, Any]:
    """Margin-mode-branched projected Strategy margin model. The projected Strategy
    initial margin is the EXACT Decimal sum of the per-action projected values and is
    emitted ONLY when EVERY action is PROJECTED_MARGIN_EVIDENCE_COMPLETE (which only
    happens under REGULAR_MARGIN with a proven applicable tier for all actions).

    Observed legacy IM is carried forward as OBSERVED evidence (never reclassified as
    projected). PORTFOLIO_MARGIN never reaches COMPLETE from static per-symbol rates.
    COMPLETE is never forced merely because /v5/account/info returned a margin mode."""
    mode_status = account_mode_evidence.get("account_mode_evidence_status")
    margin_mode = account_mode_evidence.get("margin_mode")
    projections = list(per_action_projections or [])
    blockers: list[str] = []

    observed_legacy = _opt_dec(observed_legacy_position_initial_margin_sum_usdt)
    avail = _opt_dec(available_balance)

    n = len(projections)
    complete = sum(1 for p in projections
                   if p.get("projected_margin_evidence_status") == PROJECTED_MARGIN_EVIDENCE_COMPLETE)
    unavailable = sum(1 for p in projections
                      if p.get("projected_margin_evidence_status") == PROJECTED_MARGIN_EVIDENCE_UNAVAILABLE)
    exposure_outside = any(p.get("risk_tier_selection_status")
                           == RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS for p in projections)
    conflict = any(p.get("risk_tier_selection_status") == RISK_TIER_CONFLICT for p in projections)

    projected_strategy_im: Decimal | None = None
    projected_strategy_mm: Decimal | None = None
    projected_total_im: Decimal | None = None

    if mode_status != ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE or margin_mode is None:
        blockers.append(ACCOUNT_MARGIN_MODE_UNAVAILABLE)
        status = (AUTHORITATIVE_MARGIN_MODEL_UNAVAILABLE if n == 0
                  else AUTHORITATIVE_MARGIN_MODEL_PARTIAL)
    elif conflict:
        status = MARGIN_EVIDENCE_CONFLICT
        blockers.append(RISK_TIER_CONFLICT)
    elif margin_mode == MARGIN_MODE_PORTFOLIO:
        # Static per-symbol risk-limit rates cannot model portfolio margin.
        status = AUTHORITATIVE_MARGIN_MODEL_PARTIAL
        blockers.append(PORTFOLIO_MARGIN_STATIC_RATE_NOT_APPLICABLE)
    elif margin_mode == MARGIN_MODE_ISOLATED:
        status = AUTHORITATIVE_MARGIN_MODEL_PARTIAL
        blockers.append(ISOLATED_MARGIN_PER_SYMBOL_SCOPE_NOT_PROVEN)
        if exposure_outside:
            blockers.append(RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS)
    elif margin_mode == MARGIN_MODE_REGULAR:
        if n > 0 and complete == n:
            # Exact Decimal sum of the canonical per-action projected IM values.
            projected_strategy_im = sum(
                (_dec(p["projected_action_initial_margin_usdt"]) for p in projections), Decimal("0"))
            mm_vals = [p.get("projected_action_maintenance_margin_usdt") for p in projections]
            if all(v is not None for v in mm_vals):
                projected_strategy_mm = sum((_dec(v) for v in mm_vals), Decimal("0"))
            projected_total_im = projected_strategy_im + (observed_legacy or Decimal("0"))
            status = AUTHORITATIVE_MARGIN_MODEL_COMPLETE
        else:
            status = AUTHORITATIVE_MARGIN_MODEL_PARTIAL
            if exposure_outside:
                blockers.append(RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS)
            if unavailable > 0 or complete < n:
                blockers.append(RISK_TIER_EVIDENCE_INCOMPLETE)
            blockers.append(APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE)
    else:
        status = AUTHORITATIVE_MARGIN_MODEL_PARTIAL
        blockers.append(RISK_TIER_SCOPE_NOT_PROVEN)

    projected_avail_after = headroom = None
    if projected_total_im is not None and avail is not None:
        projected_avail_after = avail - projected_total_im
        if projected_total_im > 0:
            headroom = avail / projected_total_im

    # Deterministic exact-sum verification: the reported projected Strategy IM must equal
    # the exact Decimal sum of the per-action projected IM values (always true here since
    # it IS that sum, but emitted as explicit audit evidence). accountIMRate is NEVER an
    # input to this model -> it cannot leak into the projection.
    exact_im_sum: Decimal | None = None
    exact_sum_matches = None
    if projected_strategy_im is not None:
        exact_im_sum = sum(
            (_dec(p["projected_action_initial_margin_usdt"]) for p in projections), Decimal("0"))
        exact_sum_matches = (exact_im_sum == projected_strategy_im)

    # De-duplicate while preserving deterministic order.
    seen: set[str] = set()
    blockers = [b for b in blockers if not (b in seen or seen.add(b))]

    return {
        # Account margin mode is surfaced explicitly (never null when authoritative).
        "margin_mode": margin_mode,
        "account_margin_mode": margin_mode,
        "account_mode_evidence_status": mode_status,
        # Available balance is wired in as EVIDENCE ONLY; it authorizes nothing.
        "available_balance_usdt": _opt_fmt(avail),
        "strategy_action_count": n,
        "projected_margin_complete_action_count": complete,
        "projected_margin_unavailable_action_count": unavailable,
        "projected_strategy_initial_margin_usdt": _opt_fmt(projected_strategy_im),
        "projected_strategy_initial_margin_exact_sum_usdt": _opt_fmt(exact_im_sum),
        "projected_strategy_initial_margin_exact_sum_matches": exact_sum_matches,
        "projected_strategy_maintenance_margin_usdt": _opt_fmt(projected_strategy_mm),
        "observed_legacy_position_initial_margin_sum_usdt": _opt_fmt(observed_legacy),
        "projected_total_initial_margin_usdt": _opt_fmt(projected_total_im),
        "projected_available_margin_after_execution_usdt": _opt_fmt(projected_avail_after),
        "margin_headroom_ratio": _opt_fmt(headroom),
        # accountIMRate is structurally not an input to this model.
        "account_im_rate_used_for_projection": False,
        "margin_model_status": status,
        "margin_model_blockers": blockers,
    }


# ---------------------------------------------------------------------------
# 5. Exchange-clock evidence (GET /v5/market/time) bracketing the price window
# ---------------------------------------------------------------------------


def _server_epoch(time_second: Any, time_nano: Any) -> Decimal | None:
    """Bybit server epoch (seconds). timeNano (nanoseconds) is PREFERRED when present
    because it carries sub-second precision; timeSecond is the integer-second fallback.
    Sub-second precision is never derived from second-resolution ISO strings."""
    nano = _opt_dec(time_nano)
    if nano is not None and nano > 0:
        return nano / Decimal("1000000000")
    sec = _opt_dec(time_second)
    if sec is not None and sec > 0:
        return sec
    return None


def build_exchange_clock_evidence(
    *,
    before_time_second: Any = None,
    before_time_nano: Any = None,
    before_local_request_started_at_utc: Any = None,
    before_local_response_received_at_utc: Any = None,
    before_local_monotonic_start: float | None = None,
    before_local_monotonic_end: float | None = None,
    before_response_envelope_time: Any = None,
    after_time_second: Any = None,
    after_time_nano: Any = None,
    after_local_request_started_at_utc: Any = None,
    after_local_response_received_at_utc: Any = None,
    after_local_monotonic_start: float | None = None,
    after_local_monotonic_end: float | None = None,
    after_response_envelope_time: Any = None,
    collection_window_started_at_utc: Any = None,
    collection_window_ended_at_utc: Any = None,
    first_ticker_symbol: Any = None,
    first_ticker_observed_at_utc: Any = None,
    last_ticker_symbol: Any = None,
    last_ticker_observed_at_utc: Any = None,
    local_observation_epoch_for_offset: Any = None,
    # High-resolution local EPOCH timing (seconds, sub-second float) captured around
    # each /v5/market/time call so an auditable clock offset can be computed.
    before_local_request_epoch: Any = None,
    before_local_response_epoch: Any = None,
    after_local_request_epoch: Any = None,
    after_local_response_epoch: Any = None,
) -> dict[str, Any]:
    """Build exchange-clock evidence by BRACKETING the price-collection window with two
    Bybit server-time observations (one immediately before, one immediately after).

    The Bybit server time is the EXCHANGE_SERVER_TIME; it is explicitly distinguished
    from the REST response-envelope time, the LOCAL observation time, and a per-symbol
    EXCHANGE QUOTE timestamp (which this REST path does NOT provide). The bracket proves
    the collection happened between two known server instants but does NOT assign a
    per-symbol quote timestamp, so freshness can only be PARTIAL here -- never PASS."""
    before_epoch = _server_epoch(before_time_second, before_time_nano)
    after_epoch = _server_epoch(after_time_second, after_time_nano)

    bracket_ok = before_epoch is not None and after_epoch is not None
    bracket_ordered = bool(bracket_ok and after_epoch >= before_epoch)
    bracket_duration_s = None
    if bracket_ok:
        bracket_duration_s = _fmt((after_epoch - before_epoch).copy_abs())

    # Local elapsed bracket (monotonic) for round-trip context, when present.
    local_bracket_ms = None
    if (before_local_monotonic_start is not None and after_local_monotonic_end is not None):
        local_bracket_ms = round(
            abs(after_local_monotonic_end - before_local_monotonic_start) * 1000.0, 6)

    # --- Auditable local-vs-exchange clock offset (high resolution) -----------
    # For each /v5/market/time call: offset = Bybit server epoch - local midpoint epoch,
    # where the local midpoint is the average of the local request-start and
    # response-received EPOCH seconds (sub-second float, NOT a second-resolution ISO
    # string). A conservative estimate (mean of the available per-call offsets) and the
    # offset range are emitted. When local timing is missing, an explicit status/reason
    # is emitted instead of a silent null.
    def _midpoint(req: Any, resp: Any) -> Decimal | None:
        rq = _opt_dec(req)
        rs = _opt_dec(resp)
        if rq is not None and rs is not None:
            return (rq + rs) / Decimal("2")
        return rq if rq is not None else rs

    before_mid = _midpoint(before_local_request_epoch, before_local_response_epoch)
    if before_mid is None:
        before_mid = _opt_dec(local_observation_epoch_for_offset)
    after_mid = _midpoint(after_local_request_epoch, after_local_response_epoch)

    before_offset = ((before_epoch - before_mid)
                     if (before_epoch is not None and before_mid is not None) else None)
    after_offset = ((after_epoch - after_mid)
                    if (after_epoch is not None and after_mid is not None) else None)
    per_call_offsets = [o for o in (before_offset, after_offset) if o is not None]

    if per_call_offsets:
        conservative = sum(per_call_offsets, Decimal("0")) / Decimal(len(per_call_offsets))
        clock_offset_seconds = _fmt(conservative)
        clock_offset_range = [_fmt(min(per_call_offsets)), _fmt(max(per_call_offsets))]
        clock_offset_status = CLOCK_OFFSET_AVAILABLE
        clock_offset_reason = None
    else:
        clock_offset_seconds = None
        clock_offset_range = None
        if before_epoch is not None or after_epoch is not None:
            clock_offset_status = CLOCK_OFFSET_LOCAL_TIMING_UNAVAILABLE
            clock_offset_reason = ("local high-resolution request/response epoch timing was "
                                   "not captured for any server-time call")
        else:
            clock_offset_status = CLOCK_OFFSET_UNAVAILABLE
            clock_offset_reason = "no Bybit server-time observation available"

    def _elapsed_ms(req: Any, resp: Any) -> str | None:
        rq = _opt_dec(req)
        rs = _opt_dec(resp)
        if rq is None or rs is None:
            return None
        return _fmt((rs - rq) * Decimal("1000"))

    before_elapsed_ms = _elapsed_ms(before_local_request_epoch, before_local_response_epoch)
    after_elapsed_ms = _elapsed_ms(after_local_request_epoch, after_local_response_epoch)

    evidence: dict[str, Any] = {
        "source_endpoint": EP_MARKET_TIME,
        "exchange_clock_field_paths": dict(EXCHANGE_CLOCK_FIELD_PATHS),
        # Explicit time-source taxonomy (never conflated).
        "exchange_server_time_before": (_fmt(before_epoch) if before_epoch is not None else None),
        "exchange_server_time_after": (_fmt(after_epoch) if after_epoch is not None else None),
        "before_time_second": (None if before_time_second is None else str(before_time_second)),
        "before_time_nano": (None if before_time_nano is None else str(before_time_nano)),
        "after_time_second": (None if after_time_second is None else str(after_time_second)),
        "after_time_nano": (None if after_time_nano is None else str(after_time_nano)),
        "rest_response_envelope_time_before": (None if before_response_envelope_time is None
                                               else str(before_response_envelope_time)),
        "rest_response_envelope_time_after": (None if after_response_envelope_time is None
                                              else str(after_response_envelope_time)),
        "before_local_request_started_at_utc": before_local_request_started_at_utc,
        "before_local_response_received_at_utc": before_local_response_received_at_utc,
        "after_local_request_started_at_utc": after_local_request_started_at_utc,
        "after_local_response_received_at_utc": after_local_response_received_at_utc,
        "collection_window_started_at_utc": collection_window_started_at_utc,
        "collection_window_ended_at_utc": collection_window_ended_at_utc,
        "first_ticker_symbol": first_ticker_symbol,
        "first_ticker_observed_at_utc": first_ticker_observed_at_utc,
        "last_ticker_symbol": last_ticker_symbol,
        "last_ticker_observed_at_utc": last_ticker_observed_at_utc,
        "server_time_bracket_duration_seconds": bracket_duration_s,
        "local_round_trip_bracket_ms": local_bracket_ms,
        # Clock-offset evidence (explicit status; never a silent null).
        "estimated_local_vs_exchange_clock_offset_seconds": clock_offset_seconds,
        "clock_offset_before_seconds": (_fmt(before_offset) if before_offset is not None else None),
        "clock_offset_after_seconds": (_fmt(after_offset) if after_offset is not None else None),
        "clock_offset_range_seconds": clock_offset_range,
        "clock_offset_evidence_status": clock_offset_status,
        "clock_offset_evidence_reason": clock_offset_reason,
        "before_request_elapsed_ms": before_elapsed_ms,
        "after_request_elapsed_ms": after_elapsed_ms,
        # Explicit availability status for the whole clock-evidence block.
        "exchange_clock_evidence_status": (EXCHANGE_CLOCK_BRACKET_AVAILABLE if bracket_ok
                                           else EXCHANGE_CLOCK_UNAVAILABLE),
        # Capability conclusions (fail closed; never promote freshness to PASS here).
        "exchange_clock_bracket_available": bracket_ok,
        "server_time_bracket_ordered": bracket_ordered,
        "local_observation_time_available": (
            before_local_response_received_at_utc is not None
            or after_local_response_received_at_utc is not None),
        "per_symbol_exchange_quote_timestamp_available": False,
        "execution_grade_freshness_complete": False,
        "price_freshness_status": md.PRICE_FRESHNESS_EVIDENCE_PARTIAL,
        # Explicit design verdict (section 6).
        "rest_ticker_provides_per_symbol_quote_timestamp": False,
        "websocket_ticker_ts_required_for_execution_grade": True,
        "websocket_belongs_in_this_task": False,
        "exchange_timestamp_source_conclusion": (
            "The read-only REST /v5/market/tickers path does NOT return a per-symbol "
            "exchange quote timestamp. /v5/market/time and any REST response-envelope "
            "time are account/server-wide instants, not per-quote times. Execution-grade "
            "per-symbol freshness requires a public/authenticated WebSocket ticker `ts`. "
            "Adding a WebSocket execution dependency is deferred to a separate follow-up; "
            "it is NOT introduced in this task."),
    }
    evidence["server_time_evidence_fingerprint"] = _sha([
        EP_MARKET_TIME,
        evidence["before_time_second"], evidence["before_time_nano"],
        evidence["after_time_second"], evidence["after_time_nano"],
        bracket_duration_s, clock_offset_seconds, clock_offset_status, bracket_ordered,
    ])
    return evidence


# ---------------------------------------------------------------------------
# 6. Extended complete-account network audit (distinct counter semantics)
# ---------------------------------------------------------------------------


def build_account_network_audit(
    *,
    instrument_metadata_public_get_count: int,
    ticker_http_request_count: int,
    ticker_requested_symbol_count: int,
    ticker_unique_symbol_count: int,
    ticker_cache_hit_count: int,
    server_time_public_get_count: int,
    risk_limit_public_get_count: int,
    risk_limit_page_count: int,
    account_info_private_read_only_get_count: int,
    wallet_private_read_only_get_count: int,
    positions_private_read_only_get_count: int,
    strategy_target_priced_symbol_count: int | None = None,
    legacy_mark_priced_symbol_count: int | None = None,
) -> dict[str, Any]:
    """ONE canonical complete-account network audit with DISTINCT counter semantics.
    Logical symbol requests, HTTP requests, pagination and cache hits are never mixed.
    Totals are recomputed (never hard-coded):

      total_public_get_count  = instrument_metadata + ticker_http + server_time + risk_limit
      total_private_read_only_get_count = account_info + wallet + positions

    Any internal inconsistency fails closed with NETWORK_AUDIT_COUNTER_MISMATCH (execution
    stays unauthorised). When the strategy/legacy priced-symbol counts are supplied, a
    priced==unique check is added; otherwise priced fields are null and that check is
    omitted (the ticker-only CD audit carries the priced proof separately)."""
    total_public = (int(instrument_metadata_public_get_count)
                    + int(ticker_http_request_count)
                    + int(server_time_public_get_count)
                    + int(risk_limit_public_get_count))
    total_private = (int(account_info_private_read_only_get_count)
                     + int(wallet_private_read_only_get_count)
                     + int(positions_private_read_only_get_count))
    checks = {
        "ticker_requests_plus_cache_equals_requested":
            int(ticker_http_request_count) + int(ticker_cache_hit_count)
            == int(ticker_requested_symbol_count),
        "one_ticker_http_request_per_unique_symbol":
            int(ticker_http_request_count) == int(ticker_unique_symbol_count),
        "risk_limit_pages_cover_http":
            int(risk_limit_page_count) >= int(risk_limit_public_get_count),
        "non_negative":
            min(instrument_metadata_public_get_count, ticker_http_request_count,
                ticker_requested_symbol_count, ticker_unique_symbol_count,
                ticker_cache_hit_count, server_time_public_get_count,
                risk_limit_public_get_count, risk_limit_page_count,
                account_info_private_read_only_get_count,
                wallet_private_read_only_get_count,
                positions_private_read_only_get_count) >= 0,
    }
    total_priced = None
    if strategy_target_priced_symbol_count is not None and legacy_mark_priced_symbol_count is not None:
        total_priced = int(strategy_target_priced_symbol_count) + int(legacy_mark_priced_symbol_count)
        checks["total_priced_equals_unique"] = total_priced == int(ticker_unique_symbol_count)
    consistent = all(checks.values())
    return {
        "instrument_metadata_public_get_count": int(instrument_metadata_public_get_count),
        "ticker_http_request_count": int(ticker_http_request_count),
        "ticker_requested_symbol_count": int(ticker_requested_symbol_count),
        "ticker_unique_symbol_count": int(ticker_unique_symbol_count),
        "ticker_cache_hit_count": int(ticker_cache_hit_count),
        "server_time_public_get_count": int(server_time_public_get_count),
        "risk_limit_public_get_count": int(risk_limit_public_get_count),
        "risk_limit_page_count": int(risk_limit_page_count),
        "account_info_private_read_only_get_count": int(account_info_private_read_only_get_count),
        "wallet_private_read_only_get_count": int(wallet_private_read_only_get_count),
        "positions_private_read_only_get_count": int(positions_private_read_only_get_count),
        "strategy_target_priced_symbol_count": (None if strategy_target_priced_symbol_count is None
                                                else int(strategy_target_priced_symbol_count)),
        "legacy_mark_priced_symbol_count": (None if legacy_mark_priced_symbol_count is None
                                            else int(legacy_mark_priced_symbol_count)),
        "total_priced_symbol_count": total_priced,
        "total_public_get_count": total_public,
        "total_private_read_only_get_count": total_private,
        "network_audit_checks": checks,
        "network_audit_status":
            NETWORK_AUDIT_CONSISTENT if consistent else NETWORK_AUDIT_COUNTER_MISMATCH,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_endpoint_called": False,
    }


# ---------------------------------------------------------------------------
# 7. Readiness-blocker reconciliation (resolve CD blockers when evidence permits)
# ---------------------------------------------------------------------------


def reconcile_readiness_blockers(
    *,
    base_blockers: Sequence[str],
    account_mode_evidence: Mapping[str, Any] | None,
    account_margin_model: Mapping[str, Any] | None,
    exchange_clock_evidence: Mapping[str, Any] | None,
) -> list[str]:
    """Resolve the TASK-014CD generic blockers (ACCOUNT_MARGIN_MODE_UNAVAILABLE,
    APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE) ONLY when real authoritative evidence
    permits, replacing them with the precise CE blockers. The per-task authorization
    blocker is ALWAYS present and ALWAYS last."""
    out: list[str] = [b for b in base_blockers
                      if b != EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK]

    mode_authoritative = bool(account_mode_evidence) and (
        account_mode_evidence.get("account_mode_evidence_status")
        == ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE)
    if mode_authoritative and ACCOUNT_MARGIN_MODE_UNAVAILABLE in out:
        out = [b for b in out if b != ACCOUNT_MARGIN_MODE_UNAVAILABLE]

    model_complete = bool(account_margin_model) and (
        account_margin_model.get("margin_model_status") == AUTHORITATIVE_MARGIN_MODEL_COMPLETE)
    if model_complete:
        # The projected Strategy margin model is COMPLETE: the generic CD PARTIAL status
        # and the applicable-rate blocker are no longer true. The NON-ATOMIC observed
        # snapshot concern is preserved separately (it is NOT removed here).
        out = [b for b in out if b not in (APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE,
                                           AUTHORITATIVE_MARGIN_MODEL_PARTIAL)]

    # Merge the precise margin-model blockers (PORTFOLIO/ISOLATED/tier scope).
    for b in (account_margin_model or {}).get("margin_model_blockers", []) or []:
        if b not in out:
            out.append(b)

    # Exchange-clock evidence keeps freshness PARTIAL: surface the precise reason.
    if exchange_clock_evidence is not None:
        if not exchange_clock_evidence.get("per_symbol_exchange_quote_timestamp_available", False):
            if PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE not in out:
                out.append(PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE)
        if exchange_clock_evidence.get("exchange_clock_bracket_available", False):
            if EXCHANGE_CLOCK_BRACKET_ONLY not in out:
                out.append(EXCHANGE_CLOCK_BRACKET_ONLY)

    # De-duplicate, then always append the per-task authorization blocker last.
    seen: set[str] = set()
    out = [b for b in out if not (b in seen or seen.add(b))]
    out.append(EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK)
    return out


__all__ = [
    "TASK_ID",
    "EP_ACCOUNT_INFO", "EP_MARKET_TIME", "EP_RISK_LIMIT",
    "MARGIN_MODE_ISOLATED", "MARGIN_MODE_REGULAR", "MARGIN_MODE_PORTFOLIO",
    "ALLOWED_MARGIN_MODES",
    "ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE", "ACCOUNT_MODE_EVIDENCE_UNAVAILABLE",
    "ACCOUNT_MODE_EVIDENCE_MALFORMED",
    "RISK_TIER_APPLICABLE", "RISK_TIER_EVIDENCE_MISSING",
    "RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS",
    "RISK_TIER_SCOPE_NOT_APPLICABLE_TO_MARGIN_MODE", "RISK_TIER_CONFLICT",
    "PROJECTED_MARGIN_EVIDENCE_COMPLETE", "PROJECTED_MARGIN_EVIDENCE_PARTIAL",
    "PROJECTED_MARGIN_EVIDENCE_UNAVAILABLE",
    "AUTHORITATIVE_MARGIN_MODEL_COMPLETE", "AUTHORITATIVE_MARGIN_MODEL_PARTIAL",
    "AUTHORITATIVE_MARGIN_MODEL_UNAVAILABLE", "MARGIN_EVIDENCE_CONFLICT",
    "ACCOUNT_MARGIN_MODE_UNAVAILABLE", "APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE",
    "PORTFOLIO_MARGIN_STATIC_RATE_NOT_APPLICABLE",
    "ISOLATED_MARGIN_PER_SYMBOL_SCOPE_NOT_PROVEN",
    "RISK_TIER_EVIDENCE_INCOMPLETE", "RISK_TIER_SCOPE_NOT_PROVEN",
    "PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE", "EXCHANGE_CLOCK_BRACKET_ONLY",
    "EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK",
    "NON_ATOMIC_MARGIN_SNAPSHOT",
    "EXCHANGE_CLOCK_BRACKET_AVAILABLE", "EXCHANGE_CLOCK_UNAVAILABLE",
    "CLOCK_OFFSET_AVAILABLE", "CLOCK_OFFSET_UNAVAILABLE",
    "CLOCK_OFFSET_LOCAL_TIMING_UNAVAILABLE",
    "NETWORK_AUDIT_CONSISTENT", "NETWORK_AUDIT_COUNTER_MISMATCH",
    "normalize_account_mode_evidence", "unavailable_account_mode_evidence",
    "normalize_risk_tiers", "select_risk_tier", "project_action_margin",
    "build_account_margin_model", "build_exchange_clock_evidence",
    "build_account_network_audit", "reconcile_readiness_blockers",
]
