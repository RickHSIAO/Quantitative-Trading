"""TASK-014CD -- authoritative read-only margin / price-freshness / network audit.

Plan-only evidence layer that sits ON TOP of the accepted TASK-014CC_FIX1 Strategy-
native V1 review. It captures and normalises (without ever assuming or fabricating):

  * authoritative read-only MARGIN evidence (account + per-position), with exact
    Bybit V5 endpoint + field paths, and an explicit availability status per field;
  * a projected-margin model that is computed ONLY when supported by authoritative
    evidence (never silently selecting a leverage value);
  * price-observation / FRESHNESS evidence that strictly separates a locally
    generated timestamp from an exchange/server timestamp;
  * NETWORK-audit counters that distinguish HTTP request count from requested /
    unique / cached symbol counts and priced-symbol counts, with a consistency
    status that fails closed on any mismatch;
  * a structured execution-readiness blocker list.

Every function here is PURE (no network, no secrets, no global state) so the audit
is deterministic for identical evidence. This module authorises NOTHING and sends
NOTHING. The execution batch remains UNAUTHORISED in this task even if all evidence
passes.
"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

TASK_ID = "TASK-014CD"

# --- Margin-model statuses --------------------------------------------------
AUTHORITATIVE_MARGIN_MODEL_COMPLETE = "AUTHORITATIVE_MARGIN_MODEL_COMPLETE"
AUTHORITATIVE_MARGIN_MODEL_PARTIAL = "AUTHORITATIVE_MARGIN_MODEL_PARTIAL"
MARGIN_EVIDENCE_UNAVAILABLE = "MARGIN_EVIDENCE_UNAVAILABLE"
MARGIN_EVIDENCE_CONFLICT = "MARGIN_EVIDENCE_CONFLICT"
INSUFFICIENT_PROJECTED_MARGIN = "INSUFFICIENT_PROJECTED_MARGIN"

# --- Per-field evidence availability ----------------------------------------
EVIDENCE_AUTHORITATIVE = "AUTHORITATIVE"
EVIDENCE_PARTIAL = "PARTIAL"
EVIDENCE_UNAVAILABLE = "UNAVAILABLE"

# --- Price-freshness statuses ----------------------------------------------
PRICE_FRESHNESS_PASS = "PRICE_FRESHNESS_PASS"
PRICE_FRESHNESS_STALE = "PRICE_FRESHNESS_STALE"
PRICE_FRESHNESS_EVIDENCE_PARTIAL = "PRICE_FRESHNESS_EVIDENCE_PARTIAL"
PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE = "PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE"

# --- Network-audit consistency ----------------------------------------------
NETWORK_AUDIT_CONSISTENT = "NETWORK_AUDIT_CONSISTENT"
NETWORK_AUDIT_COUNTER_MISMATCH = "NETWORK_AUDIT_COUNTER_MISMATCH"

# --- Initial-margin comparison statuses (TASK-014CD_FIX1) -------------------
# Wallet (account-level total IM) and position (per-position IM sum) come from
# SEPARATE non-atomic HTTP responses with no proof of identical calculation scope.
# A small skew is therefore NOT a contradiction; only a proven, comparable, large
# difference is a true conflict.
INITIAL_MARGIN_VALUES_MATCH_WITHIN_TOLERANCE = "INITIAL_MARGIN_VALUES_MATCH_WITHIN_TOLERANCE"
INITIAL_MARGIN_VALUES_DIFFER_WITHIN_NON_ATOMIC_SNAPSHOT_TOLERANCE = \
    "INITIAL_MARGIN_VALUES_DIFFER_WITHIN_NON_ATOMIC_SNAPSHOT_TOLERANCE"
INITIAL_MARGIN_SCOPE_NOT_COMPARABLE = "INITIAL_MARGIN_SCOPE_NOT_COMPARABLE"
INITIAL_MARGIN_TRUE_CONFLICT = "INITIAL_MARGIN_TRUE_CONFLICT"

# --- Margin snapshot comparison scope ---------------------------------------
COMPARISON_SCOPE_PROVEN_COMPARABLE = "COMPARISON_SCOPE_PROVEN_COMPARABLE"
COMPARISON_SCOPE_NOT_PROVEN_COMPARABLE = "COMPARISON_SCOPE_NOT_PROVEN_COMPARABLE"

# Exact-match tolerance (USDT). Within this, the two values are treated as equal.
INITIAL_MARGIN_MATCH_TOLERANCE_USDT = Decimal("0.01")
# Non-atomic snapshot skew tolerance: a difference within EITHER the absolute or
# the relative bound is attributable to ordinary non-atomic snapshot skew (marks /
# reserved margin / account-level adjustments moving between the two GETs), NOT a
# contradiction. The observed VPS skew (~2.22 USDT / ~0.12%) is well inside this.
NON_ATOMIC_SNAPSHOT_ABS_TOLERANCE_USDT = Decimal("25")
NON_ATOMIC_SNAPSHOT_REL_TOLERANCE = Decimal("0.02")  # 2%

# Configurable REVIEW freshness threshold (seconds). This is a review threshold
# ONLY; it never authorises execution. 30s is chosen because the Bybit V5 public
# linear ticker updates well within a second, so a 30s window is generous for a
# read-only Plan-only review while still flagging clearly stale snapshots.
DEFAULT_PRICE_FRESHNESS_THRESHOLD_SECONDS = 30

# This task NEVER authorises the batch, even if every evidence check passes.
EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK = "EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK"

# Exact Bybit V5 read-only endpoint + field paths for the captured margin evidence.
MARGIN_FIELD_PATHS: dict[str, str] = {
    "account_type": "/v5/account/wallet-balance -> result.list[0].accountType",
    "account_margin_mode": "/v5/account/info -> result.marginMode "
                           "(NOT in allowed read-only paths; reported as unavailable)",
    "wallet_equity": "/v5/account/wallet-balance -> result.list[0].coin[USDT].equity",
    "available_balance": "/v5/account/wallet-balance -> result.list[0].totalAvailableBalance",
    "total_initial_margin": "/v5/account/wallet-balance -> result.list[0].totalInitialMargin",
    "total_maintenance_margin": "/v5/account/wallet-balance -> result.list[0].totalMaintenanceMargin",
    "account_initial_margin_rate": "/v5/account/wallet-balance -> result.list[0].accountIMRate",
    "account_maintenance_margin_rate": "/v5/account/wallet-balance -> result.list[0].accountMMRate",
    "per_position_leverage": "/v5/position/list -> result.list[].leverage",
    "per_position_initial_margin": "/v5/position/list -> result.list[].positionIM",
    "per_position_maintenance_margin": "/v5/position/list -> result.list[].positionMM",
    "position_value": "/v5/position/list -> result.list[].positionValue",
    "mark_price": "/v5/position/list -> result.list[].markPrice",
    "liquidation_price": "/v5/position/list -> result.list[].liqPrice",
}

_MARGIN_TOLERANCE = Decimal("0.01")


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
    return _fmt(value)


def _sha(parts: Sequence[Any]) -> str:
    body = "|".join(str(p) for p in parts)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _parse_epoch(value: Any) -> float | None:
    """Parse a timestamp to epoch seconds. Accepts epoch seconds (int/float) or an
    ISO-8601 UTC string ("...Z" or offset). Returns None when unparseable."""
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    s = str(value).strip()
    if not s:
        return None
    try:
        return float(s)
    except (ValueError, TypeError):
        pass
    try:
        iso = s.replace("Z", "+00:00")
        dt = datetime.fromisoformat(iso)
        if dt.tzinfo is None:
            dt = dt.replace(tzinfo=timezone.utc)
        return dt.timestamp()
    except (ValueError, TypeError):
        return None


# ---------------------------------------------------------------------------
# 1. Authoritative read-only margin evidence
# ---------------------------------------------------------------------------


def compare_initial_margin(
    *, reported_total: Decimal | None, observed_sum: Decimal | None,
    snapshot_atomic: bool, scope_proven_comparable: bool,
) -> dict[str, Any]:
    """Compare the account-level reported total initial margin against the observed
    per-position initial-margin sum. A small skew between two SEPARATE non-atomic
    HTTP responses (marks / reserved margin / account-level adjustments moving
    between calls) is NOT a contradiction. A TRUE conflict requires that the
    snapshots are atomic, the calculation scope is proven comparable, AND the
    difference exceeds BOTH an absolute and a relative tolerance."""
    if reported_total is None or observed_sum is None:
        return {
            "reported_total_initial_margin_usdt": _opt_fmt(reported_total),
            "observed_position_initial_margin_sum_usdt": _opt_fmt(observed_sum),
            "initial_margin_difference_usdt": None,
            "initial_margin_difference_ratio": None,
            "initial_margin_comparison_status": None,
        }
    diff = (reported_total - observed_sum).copy_abs()
    base = max(reported_total.copy_abs(), observed_sum.copy_abs(), Decimal("1"))
    ratio = diff / base
    if diff <= INITIAL_MARGIN_MATCH_TOLERANCE_USDT:
        status = INITIAL_MARGIN_VALUES_MATCH_WITHIN_TOLERANCE
    elif snapshot_atomic and scope_proven_comparable:
        if diff > NON_ATOMIC_SNAPSHOT_ABS_TOLERANCE_USDT and ratio > NON_ATOMIC_SNAPSHOT_REL_TOLERANCE:
            status = INITIAL_MARGIN_TRUE_CONFLICT
        else:
            status = INITIAL_MARGIN_VALUES_MATCH_WITHIN_TOLERANCE
    elif diff <= NON_ATOMIC_SNAPSHOT_ABS_TOLERANCE_USDT or ratio <= NON_ATOMIC_SNAPSHOT_REL_TOLERANCE:
        status = INITIAL_MARGIN_VALUES_DIFFER_WITHIN_NON_ATOMIC_SNAPSHOT_TOLERANCE
    else:
        # Large difference but NOT proven comparable (non-atomic / unknown scope):
        # cannot assert a contradiction.
        status = INITIAL_MARGIN_SCOPE_NOT_COMPARABLE
    return {
        "reported_total_initial_margin_usdt": _fmt(reported_total),
        "observed_position_initial_margin_sum_usdt": _fmt(observed_sum),
        "initial_margin_difference_usdt": _fmt(diff),
        "initial_margin_difference_ratio": _fmt(ratio.quantize(Decimal("0.00000001"))),
        "initial_margin_comparison_status": status,
    }


def normalize_margin_evidence(
    *,
    margin_evidence_source: str,
    account_type: Any = None,
    account_margin_mode: Any = None,
    wallet_equity: Any = None,
    available_balance: Any = None,
    total_initial_margin: Any = None,
    total_maintenance_margin: Any = None,
    account_initial_margin_rate: Any = None,
    account_maintenance_margin_rate: Any = None,
    per_position: Sequence[Mapping[str, Any]] | None = None,
    wallet_snapshot_request_started_at_utc: Any = None,
    wallet_snapshot_response_received_at_utc: Any = None,
    position_snapshot_request_started_at_utc: Any = None,
    position_snapshot_response_received_at_utc: Any = None,
    margin_snapshot_atomic: bool = False,
    scope_proven_comparable: bool = False,
) -> dict[str, Any]:
    """Normalise authoritative read-only margin evidence. Absent fields stay None
    (never fabricated). Leverage / initial-margin availability is reported as
    AUTHORITATIVE / PARTIAL / UNAVAILABLE based purely on what the responses carry.

    Wallet and position evidence come from SEPARATE non-atomic HTTP responses, so the
    snapshot provenance (request/response timestamps, delta, atomicity, comparison
    scope) is captured explicitly and the reported-total vs per-position-sum
    comparison is classified WITHOUT calling ordinary snapshot skew a conflict."""
    per_in = list(per_position or [])
    per_out: list[dict[str, Any]] = []
    lev_present = im_present = 0
    observed_im_sum: Decimal | None = Decimal("0")
    for p in per_in:
        lev = _opt_dec(p.get("leverage"))
        im = _opt_dec(p.get("initial_margin"))
        mm = _opt_dec(p.get("maintenance_margin"))
        if lev is not None and lev > 0:
            lev_present += 1
        if im is not None:
            im_present += 1
        per_out.append({
            "symbol": p.get("symbol"),
            "leverage": _opt_fmt(lev),
            "initial_margin_usdt": _opt_fmt(im),
            "maintenance_margin_usdt": _opt_fmt(mm),
            "position_value_usdt": _opt_fmt(p.get("position_value")),
            "mark_price": _opt_fmt(p.get("mark_price")),
            "liquidation_price": _opt_fmt(p.get("liq_price")),
        })
    per_out.sort(key=lambda r: str(r["symbol"]))

    n = len(per_out)
    if n == 0:
        leverage_status = EVIDENCE_UNAVAILABLE
        im_status = (EVIDENCE_AUTHORITATIVE if total_initial_margin is not None
                     else EVIDENCE_UNAVAILABLE)
        observed_im_sum = Decimal("0") if not per_in else None
    else:
        leverage_status = (EVIDENCE_AUTHORITATIVE if lev_present == n
                           else EVIDENCE_PARTIAL if lev_present > 0 else EVIDENCE_UNAVAILABLE)
        if im_present == n:
            im_status = EVIDENCE_AUTHORITATIVE
            observed_im_sum = sum((_dec(r["initial_margin_usdt"]) for r in per_out), Decimal("0"))
        elif im_present > 0 or total_initial_margin is not None:
            im_status = EVIDENCE_PARTIAL
            observed_im_sum = None
        else:
            im_status = EVIDENCE_UNAVAILABLE
            observed_im_sum = None

    # --- Snapshot provenance (wallet + positions are separate, non-atomic GETs).
    w_resp = _parse_epoch(wallet_snapshot_response_received_at_utc)
    p_resp = _parse_epoch(position_snapshot_response_received_at_utc)
    snapshot_delta_ms = (abs(p_resp - w_resp) * 1000.0
                         if (w_resp is not None and p_resp is not None) else None)
    comparison_scope_status = (COMPARISON_SCOPE_PROVEN_COMPARABLE
                               if (margin_snapshot_atomic and scope_proven_comparable)
                               else COMPARISON_SCOPE_NOT_PROVEN_COMPARABLE)

    reported_total_dec = _opt_dec(total_initial_margin)
    comparison = compare_initial_margin(
        reported_total=reported_total_dec, observed_sum=observed_im_sum,
        snapshot_atomic=margin_snapshot_atomic, scope_proven_comparable=scope_proven_comparable)

    evidence = {
        "margin_evidence_source": margin_evidence_source,
        "margin_field_paths": dict(MARGIN_FIELD_PATHS),
        "account_type": account_type,
        "account_margin_mode": account_margin_mode,
        "wallet_equity_usdt": _opt_fmt(wallet_equity),
        "available_balance_usdt": _opt_fmt(available_balance),
        "reported_total_initial_margin_usdt": _opt_fmt(total_initial_margin),
        "reported_account_total_initial_margin_usdt": _opt_fmt(total_initial_margin),
        "observed_legacy_position_initial_margin_sum_usdt": _opt_fmt(observed_im_sum),
        "reported_total_maintenance_margin_usdt": _opt_fmt(total_maintenance_margin),
        "account_initial_margin_rate": _opt_fmt(account_initial_margin_rate),
        "account_maintenance_margin_rate": _opt_fmt(account_maintenance_margin_rate),
        "per_position_margin_evidence": per_out,
        "leverage_evidence_status": leverage_status,
        "initial_margin_evidence_status": im_status,
        # --- Snapshot provenance / comparison (non-atomic, fail-safe) ---------
        "wallet_snapshot_request_started_at_utc": wallet_snapshot_request_started_at_utc,
        "wallet_snapshot_response_received_at_utc": wallet_snapshot_response_received_at_utc,
        "position_snapshot_request_started_at_utc": position_snapshot_request_started_at_utc,
        "position_snapshot_response_received_at_utc": position_snapshot_response_received_at_utc,
        "snapshot_time_delta_ms": (round(snapshot_delta_ms, 3) if snapshot_delta_ms is not None else None),
        "margin_snapshot_atomic": bool(margin_snapshot_atomic),
        "comparison_scope_status": comparison_scope_status,
        "initial_margin_difference_usdt": comparison["initial_margin_difference_usdt"],
        "initial_margin_difference_ratio": comparison["initial_margin_difference_ratio"],
        "initial_margin_comparison_status": comparison["initial_margin_comparison_status"],
    }
    evidence["margin_evidence_snapshot_fingerprint"] = _sha([
        margin_evidence_source, account_type, account_margin_mode,
        evidence["wallet_equity_usdt"], evidence["available_balance_usdt"],
        evidence["reported_total_initial_margin_usdt"],
        evidence["reported_total_maintenance_margin_usdt"],
        evidence["account_initial_margin_rate"], evidence["account_maintenance_margin_rate"],
        leverage_status, im_status, evidence["initial_margin_comparison_status"],
        tuple((r["symbol"], r["leverage"], r["initial_margin_usdt"],
               r["maintenance_margin_usdt"]) for r in per_out),
    ])
    return evidence


def unavailable_margin_evidence(margin_evidence_source: str = "MARGIN_EVIDENCE_UNAVAILABLE") -> dict[str, Any]:
    """Explicit all-unavailable margin evidence (no assumptions)."""
    return normalize_margin_evidence(margin_evidence_source=margin_evidence_source)


# ---------------------------------------------------------------------------
# 2. Strategy portfolio projected-margin model
# ---------------------------------------------------------------------------


def build_projected_margin_model(
    *,
    margin_evidence: Mapping[str, Any],
    strategy_gross_notional: Any,
    legacy_gross_notional: Any,
    available_balance: Any,
    applicable_initial_margin_rate: Any = None,
) -> dict[str, Any]:
    """Projected required-initial-margin model. The projected STRATEGY initial margin
    is computed ONLY when an AUTHORITATIVE applicable initial-margin rate is supplied
    (never silently selected; accountIMRate is NOT applied to the 50-position strategy
    without proven applicability). The legacy contribution is the OBSERVED current
    per-position initial-margin sum (carried forward), never a projected value.

    A non-atomic snapshot skew between the reported account total and the observed
    per-position sum is NOT a conflict: MARGIN_EVIDENCE_CONFLICT is emitted only when
    the comparison proves an INITIAL_MARGIN_TRUE_CONFLICT. Partial / unavailable
    evidence fails closed."""
    strat = _dec(strategy_gross_notional)
    avail = _dec(available_balance)
    blockers: list[str] = []

    per = list(margin_evidence.get("per_position_margin_evidence") or [])
    reported_total_im = _opt_dec(margin_evidence.get("reported_total_initial_margin_usdt"))

    # OBSERVED current per-position IM sum (NOT a projected value).
    if not per:
        observed_legacy_im: Decimal | None = Decimal("0")
    elif all(p.get("initial_margin_usdt") is not None for p in per):
        observed_legacy_im = sum((_dec(p["initial_margin_usdt"]) for p in per), Decimal("0"))
    else:
        observed_legacy_im = None
        blockers.append("PER_POSITION_INITIAL_MARGIN_UNAVAILABLE")

    # Reported-total vs observed-sum comparison status drives conflict (not raw skew).
    comparison_status = margin_evidence.get("initial_margin_comparison_status")
    true_conflict = comparison_status == INITIAL_MARGIN_TRUE_CONFLICT
    if true_conflict:
        blockers.append("REPORTED_TOTAL_IM_CONFLICTS_WITH_PER_POSITION_SUM")

    if not margin_evidence.get("margin_snapshot_atomic", False):
        blockers.append("NON_ATOMIC_MARGIN_SNAPSHOT")
    if margin_evidence.get("account_margin_mode") is None:
        blockers.append("ACCOUNT_MARGIN_MODE_UNAVAILABLE")

    rate = _opt_dec(applicable_initial_margin_rate)
    if rate is None or rate <= 0:
        blockers.append("APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE")
    if margin_evidence.get("initial_margin_evidence_status") == EVIDENCE_UNAVAILABLE:
        blockers.append("INITIAL_MARGIN_EVIDENCE_UNAVAILABLE")
    if margin_evidence.get("leverage_evidence_status") == EVIDENCE_UNAVAILABLE:
        blockers.append("LEVERAGE_EVIDENCE_UNAVAILABLE")

    # Projected STRATEGY IM requires an AUTHORITATIVE applicable rate (never assumed).
    strat_im = (strat * rate) if (rate is not None and rate > 0) else None

    projected_total = projected_avail_after = headroom = None
    projected_legacy_im: Decimal | None = None
    if true_conflict:
        status = MARGIN_EVIDENCE_CONFLICT
    elif strat_im is not None and observed_legacy_im is not None:
        # A genuine projection: carry the observed legacy IM forward + projected strat IM.
        projected_legacy_im = observed_legacy_im
        projected_total = strat_im + observed_legacy_im
        projected_avail_after = avail - projected_total
        if projected_total > 0:
            headroom = avail / projected_total
        if projected_avail_after < 0:
            status = INSUFFICIENT_PROJECTED_MARGIN
        else:
            status = AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    else:
        has_any = (observed_legacy_im is not None and (per or reported_total_im is not None)) \
            or reported_total_im is not None \
            or margin_evidence.get("leverage_evidence_status") != EVIDENCE_UNAVAILABLE
        status = AUTHORITATIVE_MARGIN_MODEL_PARTIAL if has_any else MARGIN_EVIDENCE_UNAVAILABLE

    # De-duplicate while preserving deterministic order.
    seen: set[str] = set()
    blockers = [b for b in blockers if not (b in seen or seen.add(b))]

    return {
        "projected_strategy_initial_margin_usdt": _opt_fmt(strat_im),
        # OBSERVED current per-position IM sum (clearly NOT projected).
        "observed_legacy_position_initial_margin_sum_usdt": _opt_fmt(observed_legacy_im),
        "reported_account_total_initial_margin_usdt": _opt_fmt(reported_total_im),
        # Genuine projected legacy IM only when a projection is actually computed.
        "projected_legacy_initial_margin_usdt": _opt_fmt(projected_legacy_im),
        "projected_total_initial_margin_usdt": _opt_fmt(projected_total),
        "projected_available_margin_after_execution_usdt": _opt_fmt(projected_avail_after),
        "margin_headroom_ratio": _opt_fmt(headroom),
        "applicable_initial_margin_rate": _opt_fmt(rate),
        "initial_margin_comparison_status": comparison_status,
        "margin_model_status": status,
        "margin_model_blockers": blockers,
    }


# ---------------------------------------------------------------------------
# 3. Price observation and freshness evidence
# ---------------------------------------------------------------------------


def build_price_freshness_snapshot(
    *,
    symbol: str,
    price: Any,
    price_source: Any,
    exchange_timestamp_ms: Any = None,
    request_started_at_utc: Any = None,
    response_received_at_utc: Any = None,
    request_elapsed_ms: Any = None,
    batch_built_at_utc: Any = None,
    freshness_threshold_seconds: int = DEFAULT_PRICE_FRESHNESS_THRESHOLD_SECONDS,
) -> dict[str, Any]:
    """One price snapshot's observation + freshness evidence. A locally generated
    timestamp is NEVER described as an exchange timestamp. Price age is deterministic
    from the captured timestamps. Missing timestamps are explicitly partial/unavailable."""
    exch_epoch = None
    if exchange_timestamp_ms is not None:
        try:
            exch_epoch = float(exchange_timestamp_ms) / 1000.0
        except (ValueError, TypeError):
            exch_epoch = None
    local_epoch = _parse_epoch(response_received_at_utc)
    batch_epoch = _parse_epoch(batch_built_at_utc)

    ref_epoch = exch_epoch if exch_epoch is not None else local_epoch
    age_seconds = None
    if ref_epoch is not None and batch_epoch is not None:
        age_seconds = batch_epoch - ref_epoch

    if ref_epoch is None or age_seconds is None:
        status = PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    elif age_seconds > float(freshness_threshold_seconds):
        status = PRICE_FRESHNESS_STALE
    elif exch_epoch is not None:
        status = PRICE_FRESHNESS_PASS
    else:
        # Local observation time only; no authoritative exchange timestamp.
        status = PRICE_FRESHNESS_EVIDENCE_PARTIAL

    age_out = (_fmt(round(age_seconds, 6)) if age_seconds is not None else None)
    return {
        "symbol": symbol,
        "price_snapshot": _opt_fmt(price),
        "price_source": price_source,
        "exchange_timestamp": (str(exchange_timestamp_ms) if exchange_timestamp_ms is not None else None),
        "local_observed_at_utc": response_received_at_utc,
        "request_started_at_utc": request_started_at_utc,
        "response_received_at_utc": response_received_at_utc,
        "request_elapsed_ms": (_fmt(request_elapsed_ms) if request_elapsed_ms is not None else None),
        "price_age_seconds_at_batch_build": age_out,
        "freshness_threshold_seconds": freshness_threshold_seconds,
        "price_freshness_status": status,
        "price_snapshot_fingerprint": _sha([
            symbol, _opt_fmt(price), price_source,
            (str(exchange_timestamp_ms) if exchange_timestamp_ms is not None else ""),
            response_received_at_utc or "",
        ]),
    }


def summarize_price_freshness(snapshots: Sequence[Mapping[str, Any]]) -> str:
    """Aggregate per-snapshot freshness into a single review status (fail-closed
    precedence: STALE > all-UNAVAILABLE > PARTIAL/mixed > PASS)."""
    statuses = [str(s.get("price_freshness_status")) for s in snapshots]
    if not statuses:
        return PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    if any(s == PRICE_FRESHNESS_STALE for s in statuses):
        return PRICE_FRESHNESS_STALE
    if all(s == PRICE_FRESHNESS_PASS for s in statuses):
        return PRICE_FRESHNESS_PASS
    if all(s == PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE for s in statuses):
        return PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    return PRICE_FRESHNESS_EVIDENCE_PARTIAL


def build_price_freshness_evidence(
    snapshots: Sequence[Mapping[str, Any]],
    *, freshness_threshold_seconds: int = DEFAULT_PRICE_FRESHNESS_THRESHOLD_SECONDS,
) -> dict[str, Any]:
    snaps = sorted(snapshots, key=lambda s: str(s.get("symbol")))
    return {
        "freshness_threshold_seconds": freshness_threshold_seconds,
        "freshness_threshold_rationale":
            "review-only window; generous for a sub-second public ticker while still "
            "flagging clearly stale snapshots; does NOT authorise execution",
        "price_freshness_status": summarize_price_freshness(snaps),
        "snapshot_count": len(snaps),
        "snapshots": list(snaps),
    }


# ---------------------------------------------------------------------------
# 4. Network-audit semantics
# ---------------------------------------------------------------------------


def build_network_audit(
    *,
    ticker_http_request_count: int,
    ticker_requested_symbol_count: int,
    ticker_unique_symbol_count: int,
    ticker_cache_hit_count: int,
    strategy_target_priced_symbol_count: int,
    legacy_mark_priced_symbol_count: int,
) -> dict[str, Any]:
    """Distinguish HTTP request count from requested / unique / cached symbol counts
    and priced-symbol counts, and prove their relationship. Any mismatch fails closed
    with NETWORK_AUDIT_COUNTER_MISMATCH and keeps execution unauthorised."""
    total_priced = strategy_target_priced_symbol_count + legacy_mark_priced_symbol_count
    checks = {
        "priced_equals_unique": total_priced == ticker_unique_symbol_count,
        "requests_plus_cache_equals_requested":
            ticker_http_request_count + ticker_cache_hit_count == ticker_requested_symbol_count,
        "one_http_request_per_unique_symbol":
            ticker_http_request_count == ticker_unique_symbol_count,
        "cache_equals_requested_minus_unique":
            ticker_cache_hit_count == ticker_requested_symbol_count - ticker_unique_symbol_count,
    }
    consistent = all(checks.values())
    return {
        "ticker_http_request_count": ticker_http_request_count,
        "ticker_requested_symbol_count": ticker_requested_symbol_count,
        "ticker_unique_symbol_count": ticker_unique_symbol_count,
        "ticker_cache_hit_count": ticker_cache_hit_count,
        "strategy_target_priced_symbol_count": strategy_target_priced_symbol_count,
        "legacy_mark_priced_symbol_count": legacy_mark_priced_symbol_count,
        "total_priced_symbol_count": total_priced,
        "request_per_symbol_proven": checks["one_http_request_per_unique_symbol"],
        "network_audit_checks": checks,
        "network_audit_status":
            NETWORK_AUDIT_CONSISTENT if consistent else NETWORK_AUDIT_COUNTER_MISMATCH,
    }


# ---------------------------------------------------------------------------
# 6. Execution-readiness blocker summary
# ---------------------------------------------------------------------------


def build_execution_readiness_blockers(
    *,
    rule_rejection: bool,
    batch_float_artifact_count: int,
    legacy_mark_price_available: bool,
    price_freshness_status: str,
    margin_model_status: str,
    network_audit_status: str,
    margin_model_blockers: Sequence[str] | None = None,
) -> list[str]:
    """Deterministic, ordered list of the exact remaining blockers. The batch stays
    unauthorised in this task regardless (the task-gate blocker is always present).
    The detailed margin_model_blockers (e.g. NON_ATOMIC_MARGIN_SNAPSHOT,
    APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE, ACCOUNT_MARGIN_MODE_UNAVAILABLE) are
    surfaced alongside the margin_model_status."""
    blockers: list[str] = []
    if rule_rejection:
        blockers.append("INSTRUMENT_RULE_REJECTION")
    if batch_float_artifact_count and batch_float_artifact_count > 0:
        blockers.append("BATCH_FLOAT_ARTIFACT_PRESENT")
    if not legacy_mark_price_available:
        blockers.append("LEGACY_MARK_PRICE_UNAVAILABLE")
    if price_freshness_status != PRICE_FRESHNESS_PASS:
        blockers.append(price_freshness_status)
    if margin_model_status != AUTHORITATIVE_MARGIN_MODEL_COMPLETE:
        blockers.append(margin_model_status)
    for b in (margin_model_blockers or []):
        blockers.append(b)
    if network_audit_status == NETWORK_AUDIT_COUNTER_MISMATCH:
        blockers.append(NETWORK_AUDIT_COUNTER_MISMATCH)
    # The batch is NEVER authorised in this task even if all evidence passes.
    blockers.append(EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK)
    seen: set[str] = set()
    return [b for b in blockers if not (b in seen or seen.add(b))]


__all__ = [
    "TASK_ID",
    "AUTHORITATIVE_MARGIN_MODEL_COMPLETE", "AUTHORITATIVE_MARGIN_MODEL_PARTIAL",
    "MARGIN_EVIDENCE_UNAVAILABLE", "MARGIN_EVIDENCE_CONFLICT", "INSUFFICIENT_PROJECTED_MARGIN",
    "EVIDENCE_AUTHORITATIVE", "EVIDENCE_PARTIAL", "EVIDENCE_UNAVAILABLE",
    "PRICE_FRESHNESS_PASS", "PRICE_FRESHNESS_STALE",
    "PRICE_FRESHNESS_EVIDENCE_PARTIAL", "PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE",
    "NETWORK_AUDIT_CONSISTENT", "NETWORK_AUDIT_COUNTER_MISMATCH",
    "INITIAL_MARGIN_VALUES_MATCH_WITHIN_TOLERANCE",
    "INITIAL_MARGIN_VALUES_DIFFER_WITHIN_NON_ATOMIC_SNAPSHOT_TOLERANCE",
    "INITIAL_MARGIN_SCOPE_NOT_COMPARABLE", "INITIAL_MARGIN_TRUE_CONFLICT",
    "COMPARISON_SCOPE_PROVEN_COMPARABLE", "COMPARISON_SCOPE_NOT_PROVEN_COMPARABLE",
    "INITIAL_MARGIN_MATCH_TOLERANCE_USDT", "NON_ATOMIC_SNAPSHOT_ABS_TOLERANCE_USDT",
    "NON_ATOMIC_SNAPSHOT_REL_TOLERANCE",
    "DEFAULT_PRICE_FRESHNESS_THRESHOLD_SECONDS",
    "EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK", "MARGIN_FIELD_PATHS",
    "compare_initial_margin",
    "normalize_margin_evidence", "unavailable_margin_evidence",
    "build_projected_margin_model", "build_price_freshness_snapshot",
    "summarize_price_freshness", "build_price_freshness_evidence",
    "build_network_audit", "build_execution_readiness_blockers",
]
