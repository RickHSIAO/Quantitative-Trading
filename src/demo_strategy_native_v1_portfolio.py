"""TASK-014CC -- ACTIVE Strategy-native V1 Demo portfolio policy.

User policy decision: the active Demo implementation follows the production-shaped
Strategy-native portfolio logic of the V1 strategy
(``prev3y_crypto_combined_paper_safe_variant``: 50 targets, 25 long / 25 short,
+/-0.02 weights, fixed 10000-USDT strategy capital, +/-200-USDT target notionals,
gross 1.0, net ~ 0). The obsolete readiness/one-shot limits are NOT the active V1
policy:

    * max_simultaneous_open_positions = 1            -> LEGACY_INACTIVE_READINESS_POLICY
    * max_new_opening_orders_per_successful_day = 1   -> LEGACY_INACTIVE_READINESS_POLICY
    * TINY_SIZE_CAP_USDT (5 / 10 USDT)               -> ISOLATED_ONE_SHOT_TEST_POLICY
    * SOLUSDT-only allowlist + one-shot tiny order    -> ISOLATED_ONE_SHOT_TEST_POLICY

Those modules remain as isolated one-shot safety/test utilities and MUST NOT be
treated as the authoritative active V1 policy.

This module is a NON-dispatching, Plan-only review layer. It separates
strategy-managed positions from LEGACY_PROTECTED_EXTERNAL_POSITIONS
(EDUUSDT / POLYXUSDT etc.), builds a deterministic portfolio reconciliation, a
production-shaped (multi-symbol) execution BATCH that is never sent, and an
account-level feasibility assessment. Legacy protected positions are never
touched and never block V1 planning, but they DO count toward account-level
exposure / margin / risk feasibility.

Non-negotiable safety boundaries (enforced elsewhere, asserted here):
Demo-only endpoint, Live permanently denied, deterministic idempotent identities,
no blind retry, instrument-rule + price-freshness validation, complete audit, and
NO real Demo order without a separate explicit user authorization (a future task).
This module sends nothing and authorizes nothing.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation, ROUND_DOWN
from typing import Any, Mapping, Sequence

from src import demo_strategy_pilot_readiness as rd
from src import demo_strategy_native_margin_freshness_audit as md
from src import demo_strategy_native_account_mode_risk_tier_audit as ce

TASK_ID = "TASK-014CC"

PROTECTED_SYMBOLS = frozenset(rd.PROTECTED_SYMBOLS)

ACTIVE_STRATEGY = "prev3y_crypto_combined_paper_safe_variant"

# --- Policy classification --------------------------------------------------
POLICY_ACTIVE_STRATEGY_NATIVE_V1 = "ACTIVE_STRATEGY_NATIVE_V1_POLICY"
POLICY_LEGACY_INACTIVE_READINESS = "LEGACY_INACTIVE_READINESS_POLICY"
POLICY_ISOLATED_ONE_SHOT_TEST = "ISOLATED_ONE_SHOT_TEST_POLICY"

# --- Legacy / external position classification ------------------------------
LEGACY_PROTECTED_EXTERNAL_POSITIONS = "LEGACY_PROTECTED_EXTERNAL_POSITIONS"
RECON_LEGACY_PROTECTED_UNMANAGED = "LEGACY_PROTECTED_UNMANAGED"

# --- Reconciliation classes (strategy-managed symbols) ----------------------
RECON_OPEN = "OPEN"
RECON_HOLD = "HOLD"
RECON_INCREASE = "INCREASE"
RECON_REDUCE = "REDUCE"
RECON_CLOSE = "CLOSE"
RECON_REVERSE = "REVERSE"

# --- Feasibility statuses ---------------------------------------------------
STRATEGY_PORTFOLIO_FEASIBLE = "STRATEGY_PORTFOLIO_FEASIBLE"
STRATEGY_PORTFOLIO_INSUFFICIENT_AVAILABLE_MARGIN = "STRATEGY_PORTFOLIO_INSUFFICIENT_AVAILABLE_MARGIN"
STRATEGY_PORTFOLIO_RULE_REJECTION = "STRATEGY_PORTFOLIO_RULE_REJECTION"
STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED = "STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED"

# --- Batch authorization / execution statuses -------------------------------
BATCH_AUTHORIZATION_UNAUTHORIZED_PLAN_ONLY = "UNAUTHORIZED_PLAN_ONLY"
BATCH_EXECUTION_NOT_STARTED = "NOT_STARTED"

# --- Instrument-rule status (authoritative InstrumentRules snapshot) ---------
INSTRUMENT_RULE_STATUS_TRADING = "TRADING"

# --- Per-action rule-validation statuses ------------------------------------
RULE_VALIDATION_PASS = "RULE_VALIDATION_PASS"
RULE_VALIDATION_MISSING = "RULE_MISSING"
RULE_VALIDATION_NON_TRADING = "RULE_NON_TRADING"
RULE_VALIDATION_MALFORMED = "RULE_MALFORMED"
RULE_VALIDATION_QTY_STEP_VIOLATION = "RULE_QTY_STEP_VIOLATION"
RULE_VALIDATION_MIN_QTY_VIOLATION = "RULE_MIN_QTY_VIOLATION"
RULE_VALIDATION_MAX_QTY_VIOLATION = "RULE_MAX_QTY_VIOLATION"
RULE_VALIDATION_MIN_NOTIONAL_VIOLATION = "RULE_MIN_NOTIONAL_VIOLATION"

# --- Legacy mark-price valuation --------------------------------------------
MARK_PRICE_AVAILABLE = "MARK_PRICE_AVAILABLE"
LEGACY_MARK_PRICE_UNAVAILABLE = "LEGACY_MARK_PRICE_UNAVAILABLE"

# --- Market-price freshness evidence ----------------------------------------
PRICE_FRESHNESS_FRESH = "PRICE_FRESH"
PRICE_FRESHNESS_STALE = "PRICE_STALE"
PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE = "PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE"

_QTY_TOL = Decimal("1e-12")


# ---------------------------------------------------------------------------
# Decimal helpers (canonical strings; no binary-float artifact)
# ---------------------------------------------------------------------------


def _dec(value: Any) -> Decimal:
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _fmt(value: Any) -> str:
    v = _dec(value).normalize()
    if v == v.to_integral_value():
        v = v.quantize(Decimal("1"))
    return format(v, "f")


def has_float_artifact(text: Any) -> bool:
    s = str(text)
    if "." not in s:
        return False
    frac = s.split(".", 1)[1]
    return ("000000000000" in frac) or ("999999999999" in frac)


def _canon_qty_dec(value: Any, qty_step: Any) -> Decimal:
    """Canonical Decimal quantity floored to an exact ``qty_step`` multiple using
    pure Decimal arithmetic. The numeric value is unchanged; only the binary-float
    representation tail (e.g. ``1430.8000000000002``) is removed. When ``qty_step``
    is unknown/non-positive the value is returned verbatim (rule validation then
    fails closed elsewhere)."""
    v = _dec(value)
    step = _dec(qty_step) if qty_step is not None else Decimal("0")
    if step > 0:
        steps = (v / step).to_integral_value(rounding=ROUND_DOWN)
        v = steps * step
    return v


def _rule_fingerprint(symbol: Any, qty_step: Any, min_qty: Any, max_qty: Any,
                      tick_size: Any, min_notional: Any, status: Any) -> str:
    """Deterministic identity of one authoritative InstrumentRules snapshot. Derived
    ONLY from the real rule fields + status (never inferred from any action qty)."""
    payload = "|".join([
        str(symbol), str(qty_step), str(min_qty), str(max_qty),
        str(tick_size), str(min_notional), str(status),
    ])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _price_fingerprint(symbol: Any, price: Any, source: Any) -> str:
    payload = "|".join([str(symbol), str(price), str(source)])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def normalize_rule_evidence(symbol: str, raw_ev: Mapping[str, Any] | None) -> dict[str, Any]:
    """Normalise authoritative instrument-rule evidence into the canonical batch
    form. ``qty_step`` / ``min_qty`` / ``max_qty`` / ``min_notional`` / ``tick_size``
    come ONLY from the real ``InstrumentRules`` snapshot surfaced by the provider
    (``DemoReadOnlyClient.get_instruments_info()``); nothing is inferred from an
    action quantity. A non-null ``instrument_rule_fingerprint`` is emitted only when
    the rule is a valid TRADING rule with a positive ``qty_step``."""
    ev = dict(raw_ev or {})
    status = str(ev.get("rule_status", "MISSING")).upper()
    qty_step = ev.get("qty_step")
    out: dict[str, Any] = {
        "symbol": symbol,
        "rule_status": status,
        "instrument_rule_status": status,
        "instrument_rule_source": ev.get("instrument_rule_source"),
        "market_price_source": ev.get("market_price_source"),
        "qty_step": _fmt(qty_step) if qty_step is not None else None,
        "min_qty": _fmt(ev.get("min_qty")) if ev.get("min_qty") is not None else None,
        "max_qty": _fmt(ev.get("max_qty")) if ev.get("max_qty") is not None else None,
        "min_notional": _fmt(ev.get("min_notional")) if ev.get("min_notional") is not None else None,
        "tick_size": _fmt(ev.get("tick_size")) if ev.get("tick_size") is not None else None,
    }
    if status == INSTRUMENT_RULE_STATUS_TRADING and qty_step is not None and _dec(qty_step) > 0:
        out["instrument_rule_fingerprint"] = _rule_fingerprint(
            symbol, out["qty_step"], out["min_qty"], out["max_qty"],
            out["tick_size"], out["min_notional"], INSTRUMENT_RULE_STATUS_TRADING)
    else:
        out["instrument_rule_fingerprint"] = None
    return out


def validate_action_rule(*, qty: Any, price: Any, rule: Mapping[str, Any]) -> str:
    """Validate a canonical Decimal ``qty`` (and ``qty * price`` notional) against an
    authoritative normalised rule. Fails closed for a missing / malformed /
    non-Trading rule and for qtyStep / minQty / maxQty / minNotional violations.
    Returns ``RULE_VALIDATION_PASS`` only when every check holds."""
    status = str(rule.get("rule_status", "MISSING")).upper()
    if status != INSTRUMENT_RULE_STATUS_TRADING:
        return {
            "MISSING": RULE_VALIDATION_MISSING,
            "NON_TRADING": RULE_VALIDATION_NON_TRADING,
            "MALFORMED": RULE_VALIDATION_MALFORMED,
        }.get(status, RULE_VALIDATION_MISSING)
    if rule.get("instrument_rule_fingerprint") is None:
        return RULE_VALIDATION_MALFORMED
    step = _dec(rule.get("qty_step"))
    if step <= 0:
        return RULE_VALIDATION_MALFORMED
    q = _dec(qty)
    if (q % step) != 0:
        return RULE_VALIDATION_QTY_STEP_VIOLATION
    min_qty = rule.get("min_qty")
    if min_qty is not None and q < _dec(min_qty):
        return RULE_VALIDATION_MIN_QTY_VIOLATION
    max_qty = rule.get("max_qty")
    if max_qty is not None and _dec(max_qty) > 0 and q > _dec(max_qty):
        return RULE_VALIDATION_MAX_QTY_VIOLATION
    min_notional = rule.get("min_notional")
    if min_notional is not None and price is not None:
        notional = (q * _dec(price)).copy_abs()
        if notional < _dec(min_notional):
            return RULE_VALIDATION_MIN_NOTIONAL_VIOLATION
    return RULE_VALIDATION_PASS


# ---------------------------------------------------------------------------
# Active policy classification
# ---------------------------------------------------------------------------


def active_policy_classification() -> dict[str, Any]:
    """The authoritative active V1 policy + the explicit non-active classifications.
    Visible in JSON and documentation."""
    return {
        "active_policy": POLICY_ACTIVE_STRATEGY_NATIVE_V1,
        "active_strategy": ACTIVE_STRATEGY,
        "strategy_native_policy_active": True,
        "policy_catalog": [
            {"policy": POLICY_ACTIVE_STRATEGY_NATIVE_V1, "active": True,
             "source": "V1 prev3y_crypto_combined_paper_safe_variant strategy-native portfolio",
             "description": "production-shaped multi-symbol portfolio (50 targets, +/-0.02, "
                            "fixed 10000-USDT capital, gross 1.0, net ~ 0)"},
            {"policy": POLICY_LEGACY_INACTIVE_READINESS, "active": False,
             "source": "demo_strategy_pilot_readiness.SAFETY_POLICY",
             "inactive_limits": ["max_simultaneous_open_positions=1",
                                 "max_new_opening_orders_per_successful_day=1"],
             "description": "historical readiness limits; NOT applied to active V1"},
            {"policy": POLICY_ISOLATED_ONE_SHOT_TEST, "active": False,
             "source": "demo_only_tiny_execution_adapter* (SOLUSDT one-shot tiny order)",
             "inactive_limits": ["TINY_SIZE_CAP_USDT", "SOLUSDT-only allowlist",
                                 "one-shot single-order restriction"],
             "description": "isolated one-shot safety/test utility; NOT the active V1 policy"},
        ],
        "non_negotiable_boundaries": [
            "BYBIT_DEMO_ENDPOINT_ONLY", "LIVE_ENDPOINT_PERMANENTLY_DENIED",
            "DETERMINISTIC_IDEMPOTENT_IDENTITY", "DUPLICATE_ORDER_PREVENTION",
            "NO_BLIND_RETRY_ON_AMBIGUOUS_OUTCOME", "INSTRUMENT_RULE_VALIDATION",
            "MARKET_PRICE_FRESHNESS_VALIDATION", "AVAILABLE_MARGIN_FEASIBILITY",
            "COMPLETE_PRE_AND_POST_ORDER_AUDIT",
            "NO_REAL_ORDER_WITHOUT_SEPARATE_EXPLICIT_USER_AUTHORIZATION",
        ],
    }


# ---------------------------------------------------------------------------
# Position separation (strategy-managed vs legacy protected external)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SeparatedPositions:
    strategy_managed: list[dict[str, Any]]
    legacy_protected: list[dict[str, Any]]

    def to_dict(self) -> dict[str, Any]:
        return {"strategy_managed": self.strategy_managed,
                "legacy_protected": self.legacy_protected}


def _position_record(p: Any) -> dict[str, Any]:
    symbol = str(getattr(p, "symbol", "")).strip().upper()
    side = str(getattr(p, "side", ""))
    qty = _dec(getattr(p, "quantity", getattr(p, "qty", 0)))
    entry = _dec(getattr(p, "entry_price", 0))
    notional = (qty * entry).copy_abs()
    return {"symbol": symbol, "side": side, "qty": _fmt(qty),
            "entry_price": _fmt(entry), "notional_usdt": _fmt(notional),
            "_notional": notional}


def separate_positions(open_positions: Sequence[Any]) -> SeparatedPositions:
    """Split account positions into strategy-managed and LEGACY protected external.
    Protected symbols are ALWAYS legacy/external and never strategy-managed."""
    managed: list[dict[str, Any]] = []
    legacy: list[dict[str, Any]] = []
    for p in open_positions or []:
        rec = _position_record(p)
        if rec["symbol"] in PROTECTED_SYMBOLS:
            rec = dict(rec, classification=LEGACY_PROTECTED_EXTERNAL_POSITIONS)
            legacy.append(rec)
        else:
            managed.append(rec)
    managed.sort(key=lambda r: r["symbol"])
    legacy.sort(key=lambda r: r["symbol"])
    return SeparatedPositions(strategy_managed=managed, legacy_protected=legacy)


def value_legacy_positions(
    legacy_records: Sequence[Mapping[str, Any]], *,
    mark_price_by_symbol: Mapping[str, Any] | None,
    mark_price_source: str = "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
    mark_price_observed_at_by_symbol: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], Decimal, bool]:
    """Value each LEGACY protected external position at its CURRENT MARK price (never
    its entry price). Positions are NEVER modified. Entry price/notional are retained
    as informational evidence only; account-level current risk uses the mark notional.

    Fails closed when a current mark price is unavailable for any legacy position:
    that position's mark fields are null with status ``LEGACY_MARK_PRICE_UNAVAILABLE``
    and the third return value (``all_marks_available``) is False. There is NO silent
    fallback to entry price for current-risk valuation.

    Returns ``(enriched_legacy_records, legacy_mark_gross_notional, all_marks_available)``."""
    mark_price_by_symbol = dict(mark_price_by_symbol or {})
    observed_at_by = dict(mark_price_observed_at_by_symbol or {})
    out: list[dict[str, Any]] = []
    total_mark = Decimal("0")
    all_available = True

    for rec in legacy_records:
        symbol = rec["symbol"]
        side = rec["side"]
        qty = _dec(rec["qty"])
        entry = _dec(rec["entry_price"])
        entry_notional = (qty * entry).copy_abs()
        item: dict[str, Any] = {
            "symbol": symbol, "side": side, "qty": _fmt(qty),
            "entry_price": _fmt(entry),
            "entry_notional_usdt": _fmt(entry_notional),
            "entry_notional_usdt_informational_only": True,
            "classification": LEGACY_PROTECTED_EXTERNAL_POSITIONS,
            "executable": False,
            "mark_price_source": mark_price_source,
        }
        mark_raw = mark_price_by_symbol.get(symbol)
        mark = _dec(mark_raw) if mark_raw is not None else None
        if mark is None or mark <= 0:
            all_available = False
            item.update({
                "mark_price": None, "mark_price_snapshot": None,
                "mark_price_snapshot_fingerprint": None, "mark_notional_usdt": None,
                "unrealized_pnl_usdt": None,
                "mark_price_status": LEGACY_MARK_PRICE_UNAVAILABLE,
                "mark_price_observed_at": observed_at_by.get(symbol),
            })
        else:
            mark_notional = (qty * mark).copy_abs()
            total_mark += mark_notional
            ns = _norm_side(side)
            if ns == "long":
                upnl: Decimal | None = (mark - entry) * qty
            elif ns == "short":
                upnl = (entry - mark) * qty
            else:
                upnl = None
            item.update({
                "mark_price": _fmt(mark), "mark_price_snapshot": _fmt(mark),
                "mark_price_snapshot_fingerprint": _price_fingerprint(symbol, _fmt(mark), mark_price_source),
                "mark_notional_usdt": _fmt(mark_notional),
                "unrealized_pnl_usdt": (_fmt(upnl) if upnl is not None else None),
                "mark_price_status": MARK_PRICE_AVAILABLE,
                "mark_price_observed_at": observed_at_by.get(symbol),
            })
        out.append(item)

    out.sort(key=lambda r: r["symbol"])
    return out, total_mark, all_available


# ---------------------------------------------------------------------------
# Deterministic reconciliation (target vs strategy-managed vs legacy)
# ---------------------------------------------------------------------------


def _classify(target: Mapping[str, Any] | None, current: Mapping[str, Any] | None) -> str:
    if target is None:
        return RECON_CLOSE if current is not None else RECON_HOLD
    if current is None:
        return RECON_OPEN
    t_side = _norm_side(target.get("side"))
    c_side = _norm_side(current.get("side"))
    t_qty = _dec(target.get("qty"))
    c_qty = _dec(current.get("qty"))
    if t_side != c_side:
        return RECON_REVERSE
    diff = t_qty - c_qty
    if diff > _QTY_TOL:
        return RECON_INCREASE
    if diff < -_QTY_TOL:
        return RECON_REDUCE
    return RECON_HOLD


def _norm_side(side: Any) -> str:
    s = str(side or "").strip().lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return s


def reconcile_portfolio(
    *, targets: Sequence[Mapping[str, Any]], separated: SeparatedPositions,
) -> list[dict[str, Any]]:
    """Deterministic reconciliation. Strategy-managed symbols are classified
    OPEN/HOLD/INCREASE/REDUCE/CLOSE/REVERSE; legacy protected symbols are always
    LEGACY_PROTECTED_UNMANAGED with no executable action. Stable across reruns."""
    targets_by = {str(t.get("symbol", "")).strip().upper(): t for t in targets}
    managed_by = {r["symbol"]: r for r in separated.strategy_managed}

    records: list[dict[str, Any]] = []
    for symbol in sorted(set(targets_by) | set(managed_by)):
        if symbol in PROTECTED_SYMBOLS:
            continue  # protected can never be a strategy target/managed symbol
        cls = _classify(targets_by.get(symbol), managed_by.get(symbol))
        records.append({
            "symbol": symbol, "classification": cls,
            "executable": cls != RECON_HOLD,
            "target_present": symbol in targets_by,
            "current_present": symbol in managed_by,
        })

    for rec in separated.legacy_protected:
        records.append({
            "symbol": rec["symbol"], "classification": RECON_LEGACY_PROTECTED_UNMANAGED,
            "executable": False, "target_present": False, "current_present": True,
            "note": "legacy protected external position; untouched, no executable action",
        })
    records.sort(key=lambda r: (r["classification"] == RECON_LEGACY_PROTECTED_UNMANAGED, r["symbol"]))
    return records


# ---------------------------------------------------------------------------
# Deterministic action / batch identity
# ---------------------------------------------------------------------------


def action_fingerprint(
    *, run_date: str, pilot_id: str, symbol: str, side: str, intent: str,
    reduce_only: bool, qty: str, notional: str, price: str | None = None,
    instrument_rule_fingerprint: str | None,
    artifact_fingerprint: str | None,
) -> str:
    """Stable canonical action identity. Computed from the CANONICAL string
    representation (canonical qty, price snapshot and target notional) plus the
    NON-NULL authoritative instrument-rule fingerprint. A rule change, qty change or
    price-snapshot change therefore changes this fingerprint (and the batch_id)."""
    payload = "|".join([
        TASK_ID, str(run_date), str(pilot_id), str(symbol), str(side), str(intent),
        str(reduce_only), str(qty), str(notional), str(price or ""),
        str(instrument_rule_fingerprint or ""), str(artifact_fingerprint or ""),
    ])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


def canonical_action_payload_fingerprint(payload: Mapping[str, Any]) -> str:
    """Fingerprint over the COMPLETE canonical action payload (every canonical
    string field, in stable key order). Used as explicit evidence that the action
    is built entirely from canonical Decimal strings + authoritative rule fields."""
    keys = (
        "symbol", "side", "intent", "reduce_only", "qty", "qty_step", "price_snapshot",
        "target_notional_usdt", "current_position_qty", "current_position_notional_usdt",
        "delta_notional_usdt", "min_qty", "max_qty", "min_notional", "tick_size",
        "instrument_rule_fingerprint",
    )
    body = "|".join(f"{k}={payload.get(k)!s}" for k in keys)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def idempotency_key(
    *, run_date: str, pilot_id: str, symbol: str, side: str, intent: str, qty: str,
) -> str:
    payload = "|".join(["IDEMPOTENT", str(run_date), str(pilot_id), str(symbol),
                        str(side), str(intent), str(qty)])
    return "idem:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()[:32]


@dataclass
class ExecutionBatch:
    batch_id: str
    strategy_run_date: str
    strategy_artifact_fingerprint: str | None
    pre_execution_account_snapshot_fingerprint: str
    ordered_action_fingerprints: list[str]
    expected_action_count: int
    total_opening_notional_usdt: str
    total_reducing_notional_usdt: str
    total_projected_gross_exposure_usdt: str
    actions: list[dict[str, Any]]
    batch_authorization_status: str
    batch_execution_status: str
    rule_validation_passed: bool = True
    rule_rejection: bool = False
    rule_validation_failures: list[dict[str, Any]] = field(default_factory=list)
    non_null_rule_fingerprint_count: int = 0
    price_freshness_status: str = PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    sender_reachable: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "batch_id": self.batch_id,
            "strategy_run_date": self.strategy_run_date,
            "strategy_artifact_fingerprint": self.strategy_artifact_fingerprint,
            "pre_execution_account_snapshot_fingerprint": self.pre_execution_account_snapshot_fingerprint,
            "ordered_action_fingerprints": list(self.ordered_action_fingerprints),
            "expected_action_count": self.expected_action_count,
            "total_opening_notional_usdt": self.total_opening_notional_usdt,
            "total_reducing_notional_usdt": self.total_reducing_notional_usdt,
            "total_projected_gross_exposure_usdt": self.total_projected_gross_exposure_usdt,
            "actions": self.actions,
            "batch_authorization_status": self.batch_authorization_status,
            "batch_execution_status": self.batch_execution_status,
            "rule_validation_passed": self.rule_validation_passed,
            "rule_rejection": self.rule_rejection,
            "rule_validation_failures": list(self.rule_validation_failures),
            "non_null_rule_fingerprint_count": self.non_null_rule_fingerprint_count,
            "price_freshness_status": self.price_freshness_status,
            "sender_reachable": self.sender_reachable,
        }


def _account_snapshot_fingerprint(separated: SeparatedPositions, wallet_equity: str,
                                  available_balance: str) -> str:
    payload = {
        "wallet_equity_usd": wallet_equity, "available_balance_usd": available_balance,
        "strategy_managed": [(r["symbol"], r["side"], r["qty"]) for r in separated.strategy_managed],
        "legacy_protected": [(r["symbol"], r["side"], r["qty"]) for r in separated.legacy_protected],
    }
    return "sha256:" + hashlib.sha256(repr(payload).encode("utf-8")).hexdigest()


def build_execution_batch(
    *, run_date: str, pilot_id: str, artifact_fingerprint: str | None,
    reconciliation: Sequence[Mapping[str, Any]],
    targets_by_symbol: Mapping[str, Mapping[str, Any]],
    managed_by_symbol: Mapping[str, Mapping[str, Any]],
    rule_evidence_by_symbol: Mapping[str, Mapping[str, Any]],
    price_by_symbol: Mapping[str, Any],
    separated: SeparatedPositions, wallet_equity: str, available_balance: str,
    price_observed_at_by_symbol: Mapping[str, Any] | None = None,
    price_freshness_status: str = PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE,
    freshness_evidence_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
) -> ExecutionBatch:
    """Deterministic production-shaped (multi-symbol) execution batch. NEVER sent;
    sender_reachable is always False. Actions are ordered by symbol so the batch
    identity is stable across reruns.

    Every action is BOUND to the authoritative ``InstrumentRules`` snapshot (non-null
    fingerprint, qty_step / min_qty / max_qty / min_notional / tick_size, rule source,
    rule status) and built from CANONICAL Decimal strings (qty floored to qty_step via
    pure Decimal; no binary-float artifact). Each action is rule-validated; any failure
    sets ``rule_rejection`` while the complete plan is preserved for audit.

    When ``freshness_evidence_by_symbol`` is supplied, each action attaches the matching
    symbol's price-observation / freshness evidence (observed/request/response times,
    elapsed, price age, exchange timestamp, freshness status, evidence fingerprint). This
    OBSERVATION/audit metadata is intentionally NOT part of the action fingerprint or
    batch_id (identity stays bound to price value + market snapshot identity, so request
    timing never creates accidental duplicate order identities)."""
    price_observed_at_by_symbol = dict(price_observed_at_by_symbol or {})
    freshness_evidence_by_symbol = dict(freshness_evidence_by_symbol or {})
    actions: list[dict[str, Any]] = []
    opening = Decimal("0")
    reducing = Decimal("0")
    gross = Decimal("0")
    failures: list[dict[str, Any]] = []
    non_null_rule_fp = 0

    for rec in reconciliation:
        cls = rec["classification"]
        symbol = rec["symbol"]
        if cls in (RECON_HOLD, RECON_LEGACY_PROTECTED_UNMANAGED) or not rec.get("executable"):
            continue
        tgt = targets_by_symbol.get(symbol, {})
        cur = managed_by_symbol.get(symbol, {})
        rule = normalize_rule_evidence(symbol, rule_evidence_by_symbol.get(symbol))

        # Canonical Decimal qty floored to the AUTHORITATIVE qty_step (never a float
        # round-trip of the planner value). Fall back to the target's own step only
        # for display when the rule is absent (validation then fails closed).
        rule_step = rule.get("qty_step")
        step_for_floor = rule_step if rule_step is not None else (
            _fmt(tgt.get("qty_step")) if tgt.get("qty_step") is not None else None)
        qty_dec = _canon_qty_dec(tgt.get("qty", cur.get("qty", 0)), step_for_floor)
        qty = _fmt(qty_dec)
        qty_step = rule_step if rule_step is not None else (
            _fmt(tgt.get("qty_step", 0)) if tgt.get("qty_step") is not None else None)
        price_raw = price_by_symbol.get(symbol, tgt.get("price"))
        price = _fmt(price_raw) if price_raw is not None else None
        target_notional = _fmt(tgt.get("target_notional", 0))
        cur_notional = _dec(cur.get("notional_usdt", 0))
        tgt_notional = _dec(tgt.get("target_notional", 0)).copy_abs()
        delta_notional = (tgt_notional - cur_notional)
        side = _open_side(_norm_side(tgt.get("side", cur.get("side"))))
        intent = cls
        reduce_only = cls in (RECON_REDUCE, RECON_CLOSE)
        if cls in (RECON_OPEN, RECON_INCREASE, RECON_REVERSE):
            opening += tgt_notional
        if cls in (RECON_REDUCE, RECON_CLOSE):
            reducing += cur_notional
        gross += tgt_notional

        rule_fp = rule.get("instrument_rule_fingerprint")
        if rule_fp is not None:
            non_null_rule_fp += 1
        rule_validation_status = validate_action_rule(qty=qty, price=price, rule=rule)
        if rule_validation_status != RULE_VALIDATION_PASS:
            failures.append({"symbol": symbol, "rule_validation_status": rule_validation_status})

        # Attach the matching symbol's authoritative price-observation / freshness
        # evidence record (TASK-014CD_FIX1). The action-level status EQUALS the
        # evidence-record status; absent evidence stays explicitly UNAVAILABLE.
        fe = freshness_evidence_by_symbol.get(symbol) or {}
        action_freshness = fe.get("price_freshness_status",
                                  price_freshness_status if fe else PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE)
        observed_at = fe.get("local_observed_at_utc", price_observed_at_by_symbol.get(symbol))

        afp = action_fingerprint(run_date=run_date, pilot_id=pilot_id, symbol=symbol,
                                 side=side, intent=intent, reduce_only=reduce_only, qty=qty,
                                 notional=target_notional, price=price,
                                 instrument_rule_fingerprint=rule_fp,
                                 artifact_fingerprint=artifact_fingerprint)
        ikey = idempotency_key(run_date=run_date, pilot_id=pilot_id, symbol=symbol,
                               side=side, intent=intent, qty=qty)
        action: dict[str, Any] = {
            "symbol": symbol, "side": side, "intent": intent, "reduce_only": reduce_only,
            "qty": qty, "qty_decimal": qty, "qty_step": qty_step, "price_snapshot": price,
            "target_notional_usdt": target_notional,
            "current_position_qty": _fmt(cur.get("qty", 0)),
            "current_position_notional_usdt": _fmt(cur_notional),
            "delta_notional_usdt": _fmt(delta_notional),
            # --- Authoritative instrument-rule provenance (never inferred) -----
            "instrument_rule_fingerprint": rule_fp,
            "instrument_rule_source": rule.get("instrument_rule_source"),
            "instrument_rule_status": rule.get("instrument_rule_status"),
            "min_qty": rule.get("min_qty"), "max_qty": rule.get("max_qty"),
            "min_notional": rule.get("min_notional"), "tick_size": rule.get("tick_size"),
            "rule_validation_status": rule_validation_status,
            # --- Market-price provenance + freshness (audit metadata) ----------
            # price_snapshot_fingerprint is the identity-bound market fingerprint
            # (symbol|price|source, NO timestamp). price_evidence_fingerprint
            # references the freshness evidence record (includes observation time)
            # and is NOT part of the action identity.
            "price_source": fe.get("price_source", rule.get("market_price_source")),
            "price_snapshot_fingerprint": (_price_fingerprint(symbol, price, rule.get("market_price_source"))
                                           if price is not None else None),
            "price_observed_at": observed_at,
            "request_started_at_utc": fe.get("request_started_at_utc"),
            "response_received_at_utc": fe.get("response_received_at_utc"),
            "request_elapsed_ms": fe.get("request_elapsed_ms"),
            "price_age_seconds": fe.get("price_age_seconds_at_batch_build"),
            "exchange_timestamp": fe.get("exchange_timestamp"),
            "freshness_threshold_seconds": fe.get("freshness_threshold_seconds"),
            "price_freshness_status": action_freshness,
            "price_evidence_fingerprint": fe.get("price_snapshot_fingerprint"),
            "action_fingerprint": afp, "idempotency_key": ikey,
        }
        action["canonical_action_payload_fingerprint"] = canonical_action_payload_fingerprint(action)
        actions.append(action)

    actions.sort(key=lambda a: a["symbol"])
    ordered_fps = [a["action_fingerprint"] for a in actions]
    snap_fp = _account_snapshot_fingerprint(separated, wallet_equity, available_balance)
    batch_payload = "|".join([str(run_date), str(pilot_id), str(artifact_fingerprint or ""),
                              snap_fp, *ordered_fps])
    batch_id = "batch:" + hashlib.sha256(batch_payload.encode("utf-8")).hexdigest()[:32]

    rule_rejection = bool(failures)
    # The batch's aggregate freshness status is DERIVED from the per-action statuses
    # via the canonical fail-closed priority (TASK-014CD_FIX2). When there are no
    # actions, fall back to the supplied batch-level status.
    aggregate_freshness = (md.aggregate_freshness_statuses(
        [a["price_freshness_status"] for a in actions]) if actions else price_freshness_status)
    return ExecutionBatch(
        batch_id=batch_id, strategy_run_date=str(run_date),
        strategy_artifact_fingerprint=artifact_fingerprint,
        pre_execution_account_snapshot_fingerprint=snap_fp,
        ordered_action_fingerprints=ordered_fps, expected_action_count=len(actions),
        total_opening_notional_usdt=_fmt(opening), total_reducing_notional_usdt=_fmt(reducing),
        total_projected_gross_exposure_usdt=_fmt(gross), actions=actions,
        batch_authorization_status=BATCH_AUTHORIZATION_UNAUTHORIZED_PLAN_ONLY,
        batch_execution_status=BATCH_EXECUTION_NOT_STARTED,
        rule_validation_passed=not rule_rejection, rule_rejection=rule_rejection,
        rule_validation_failures=failures, non_null_rule_fingerprint_count=non_null_rule_fp,
        price_freshness_status=aggregate_freshness, sender_reachable=False)


def _open_side(long_short: str) -> str:
    return "Buy" if long_short == "long" else "Sell"


# ---------------------------------------------------------------------------
# Account-level feasibility (legacy exposure included; fail closed on unknowns)
# ---------------------------------------------------------------------------


def assess_feasibility(
    *, wallet_equity: Any, available_balance: Any, strategy_gross_notional: Any,
    legacy_gross_notional: Any, leverage_authoritative: bool,
    initial_margin_authoritative: bool, assumed_leverage: Any = None,
    instrument_rule_rejection: bool = False,
    legacy_mark_price_available: bool = True,
    price_freshness_status: str = md.PRICE_FRESHNESS_PASS,
    exchange_timestamp_available: bool = True,
) -> dict[str, Any]:
    """Account-level feasibility for the FULL strategy portfolio. Legacy protected
    exposure (valued at CURRENT MARK price) is included in total account gross notional
    and risk. Leverage/initial margin are never assumed; if they cannot be read
    authoritatively the result is ACCOUNT_RISK_REVIEW_REQUIRED (fail closed) while the
    full plan stays visible.

    Price-freshness semantics (TASK-014CD_FIX2): local observation-time evidence is
    distinguished from EXECUTION-GRADE freshness (which additionally needs an
    authoritative exchange timestamp). PARTIAL evidence (local-only) is reported as
    PARTIAL + EXCHANGE_TIMESTAMP_UNAVAILABLE, NOT globally UNAVAILABLE.

    Fail-closed precedence: instrument-rule rejection > missing legacy mark price >
    non-execution-grade price freshness > unavailable leverage / initial margin."""
    strat = _dec(strategy_gross_notional)
    legacy = _dec(legacy_gross_notional)
    total = strat + legacy
    equity = _dec(wallet_equity)
    avail = _dec(available_balance)

    # Freshness evidence classification (canonical md vocabulary).
    price_freshness_evidence_available = price_freshness_status in (
        md.PRICE_FRESHNESS_EVIDENCE_PARTIAL, md.PRICE_FRESHNESS_PASS, md.PRICE_FRESHNESS_STALE)
    local_observation_time_available = price_freshness_evidence_available
    execution_grade_freshness_complete = (
        price_freshness_status == md.PRICE_FRESHNESS_PASS and bool(exchange_timestamp_available))

    assumptions: list[str] = [
        "strategy sizing is NEVER reduced by wallet equity (feasibility is a check, not a resize)",
        "legacy protected exposure is valued at CURRENT MARK price and included in total "
        "account gross notional and risk (entry notional is informational only)",
    ]
    account_risk_review_reasons: list[str] = []
    required_im: Decimal | None = None

    if instrument_rule_rejection:
        status = STRATEGY_PORTFOLIO_RULE_REJECTION
        assumptions.append("one or more target symbols failed instrument-rule validation")
    elif not legacy_mark_price_available:
        status = STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
        account_risk_review_reasons.append(LEGACY_MARK_PRICE_UNAVAILABLE)
        assumptions.append("a current MARK price for a legacy protected position is UNAVAILABLE; "
                           "failing closed without any fallback to entry price for current risk")
    elif not execution_grade_freshness_complete:
        status = STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
        if price_freshness_status == md.PRICE_FRESHNESS_STALE:
            account_risk_review_reasons.append(md.PRICE_FRESHNESS_STALE)
            assumptions.append("a price snapshot is STALE versus the review freshness threshold; "
                               "failing closed")
        elif price_freshness_status == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL:
            account_risk_review_reasons.append(md.PRICE_FRESHNESS_EVIDENCE_PARTIAL)
            account_risk_review_reasons.append("EXCHANGE_TIMESTAMP_UNAVAILABLE")
            assumptions.append("local request/response/observed-time evidence is available, but the "
                               "authoritative EXCHANGE timestamp is unavailable, so execution-grade "
                               "freshness is incomplete -> PARTIAL (not globally unavailable)")
        elif not price_freshness_evidence_available:
            account_risk_review_reasons.append(PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE)
            assumptions.append("no price-observation / freshness evidence is available; failing closed")
        else:
            account_risk_review_reasons.append("EXCHANGE_TIMESTAMP_UNAVAILABLE")
            assumptions.append("authoritative exchange timestamp unavailable; execution-grade "
                               "freshness incomplete; failing closed")
    elif not (leverage_authoritative and initial_margin_authoritative):
        status = STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
        account_risk_review_reasons.append("LEVERAGE_OR_INITIAL_MARGIN_EVIDENCE_UNAVAILABLE")
        assumptions.append("authoritative per-symbol leverage / initial-margin requirement is "
                           "UNAVAILABLE from read-only Demo metadata; required initial margin "
                           "cannot be computed; failing closed without assuming leverage")
    else:
        lev = _dec(assumed_leverage)
        if lev <= 0:
            status = STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
            account_risk_review_reasons.append("LEVERAGE_OR_INITIAL_MARGIN_EVIDENCE_UNAVAILABLE")
            assumptions.append("authoritative leverage non-positive; failing closed")
        else:
            required_im = (total / lev)
            assumptions.append(f"required initial margin = total_gross_notional / leverage "
                               f"({_fmt(total)} / {_fmt(lev)})")
            status = (STRATEGY_PORTFOLIO_FEASIBLE if avail >= required_im
                      else STRATEGY_PORTFOLIO_INSUFFICIENT_AVAILABLE_MARGIN)

    return {
        "projected_margin_feasibility_status": status,
        "wallet_equity_usdt": _fmt(equity),
        "available_balance_usdt": _fmt(avail),
        "strategy_target_gross_notional_usdt": _fmt(strat),
        "legacy_mark_gross_notional_usdt": _fmt(legacy),
        # Compatibility alias: legacy_gross_notional_usdt now carries the MARK valuation.
        "legacy_gross_notional_usdt": _fmt(legacy),
        "total_projected_account_gross_notional_usdt": _fmt(total),
        "required_initial_margin_usdt": (_fmt(required_im) if required_im is not None else None),
        "leverage_authoritative": leverage_authoritative,
        "initial_margin_authoritative": initial_margin_authoritative,
        "legacy_mark_price_available": legacy_mark_price_available,
        # Explicit freshness semantics (TASK-014CD_FIX2): evidence availability is
        # distinguished from EXECUTION-GRADE completeness.
        "price_freshness_status": price_freshness_status,
        "price_freshness_evidence_available": price_freshness_evidence_available,
        "local_observation_time_available": local_observation_time_available,
        "exchange_timestamp_available": bool(exchange_timestamp_available),
        "execution_grade_freshness_complete": execution_grade_freshness_complete,
        "account_risk_review_reasons": account_risk_review_reasons,
        "assumptions": assumptions,
    }


# ---------------------------------------------------------------------------
# Top-level Strategy-native V1 review (Plan-only; non-dispatching)
# ---------------------------------------------------------------------------


def build_strategy_native_review(
    *, plan: Any, open_positions: Sequence[Any], pilot_id: str, run_date: str,
    artifact_fingerprint: str | None, wallet_equity: Any, available_balance: Any,
    rule_evidence_by_symbol: Mapping[str, Mapping[str, Any]] | None = None,
    price_by_symbol: Mapping[str, Any] | None = None,
    leverage_authoritative: bool = False, initial_margin_authoritative: bool = False,
    assumed_leverage: Any = None,
    legacy_mark_price_by_symbol: Mapping[str, Any] | None = None,
    legacy_mark_price_source: str = "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
    legacy_mark_price_observed_at_by_symbol: Mapping[str, Any] | None = None,
    price_observed_at_by_symbol: Mapping[str, Any] | None = None,
    price_freshness_status: str = PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE,
    # TASK-014CD authoritative evidence (Plan-only; never authorizes execution).
    margin_evidence: Mapping[str, Any] | None = None,
    applicable_initial_margin_rate: Any = None,
    price_freshness_evidence: Mapping[str, Any] | None = None,
    network_audit: Mapping[str, Any] | None = None,
    # TASK-014CE authoritative account-mode / risk-tier / exchange-clock evidence
    # (Plan-only; never authorizes execution). Each defaults to None so the accepted
    # TASK-014CD behavior is byte-identical when no CE evidence is supplied.
    account_mode_evidence: Mapping[str, Any] | None = None,
    risk_limit_evidence: Mapping[str, Any] | None = None,
    exchange_clock_evidence: Mapping[str, Any] | None = None,
    account_margin_model: Mapping[str, Any] | None = None,
    account_network_audit: Mapping[str, Any] | None = None,
    # TASK-014CE_FIX1: the planner/ticker-only CD network audit, retained under an
    # explicitly scoped name (NOT the canonical network_audit).
    ticker_price_network_audit: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    """Full ACTIVE V1 Strategy-native Plan-only review. Non-dispatching: builds a
    multi-symbol execution batch but authorizes and sends nothing.

    Every batch action is bound to the authoritative ``InstrumentRules`` snapshot
    (non-null fingerprint + canonical rule fields) and built from canonical Decimal
    strings. Legacy protected positions are separated, untouched, never block
    planning, and are valued at CURRENT MARK price (entry notional is informational
    only) for account-level feasibility. Missing rule / mark-price / freshness
    evidence fails closed while the full plan stays visible."""
    rule_evidence_by_symbol = dict(rule_evidence_by_symbol or {})
    price_by_symbol = dict(price_by_symbol or {})
    price_observed_at_by_symbol = dict(price_observed_at_by_symbol or {})

    targets = list(getattr(plan, "target_positions", []) or [])
    targets_by = {str(t.get("symbol", "")).strip().upper(): t for t in targets}
    separated = separate_positions(open_positions)
    managed_by = {r["symbol"]: r for r in separated.strategy_managed}

    recon = reconcile_portfolio(targets=targets, separated=separated)

    strategy_gross = sum((_dec(t.get("target_notional")).copy_abs() for t in targets), Decimal("0"))

    # Legacy protected positions valued at CURRENT MARK price (never entry price).
    # When no explicit legacy mark map is supplied, fall back to the shared price map
    # (which on the VPS includes per-symbol public tickers). Missing marks fail closed.
    legacy_marks = dict(legacy_mark_price_by_symbol) if legacy_mark_price_by_symbol is not None \
        else {r["symbol"]: price_by_symbol.get(r["symbol"]) for r in separated.legacy_protected}
    legacy_valued, legacy_mark_gross, legacy_marks_available = value_legacy_positions(
        separated.legacy_protected, mark_price_by_symbol=legacy_marks,
        mark_price_source=legacy_mark_price_source,
        mark_price_observed_at_by_symbol=legacy_mark_price_observed_at_by_symbol)
    legacy_mark_price_available = legacy_marks_available or not separated.legacy_protected

    # Per-symbol price-freshness evidence (TASK-014CD_FIX1): attach each action's
    # matching observation/freshness record so action-level status equals the
    # canonical evidence-record status (no stale UNAVAILABLE fields).
    freshness_evidence_by_symbol = {
        str(s.get("symbol", "")).strip().upper(): s
        for s in ((price_freshness_evidence or {}).get("snapshots") or [])}

    # TASK-014CD_FIX2 (E): where canonical freshness evidence exists for a legacy
    # protected symbol, reference its mark-price observation/freshness (positions are
    # NEVER modified; this is audit metadata only).
    for rec in legacy_valued:
        fe = freshness_evidence_by_symbol.get(str(rec.get("symbol", "")).strip().upper())
        if fe:
            rec["mark_price_observed_at"] = fe.get("local_observed_at_utc")
            rec["mark_price_age_seconds"] = fe.get("price_age_seconds_at_batch_build")
            rec["mark_price_evidence_fingerprint"] = fe.get("price_snapshot_fingerprint")
            rec["mark_price_freshness_status"] = fe.get("price_freshness_status")

    batch = build_execution_batch(
        run_date=run_date, pilot_id=pilot_id, artifact_fingerprint=artifact_fingerprint,
        reconciliation=recon, targets_by_symbol=targets_by, managed_by_symbol=managed_by,
        rule_evidence_by_symbol=rule_evidence_by_symbol, price_by_symbol=price_by_symbol,
        separated=separated, wallet_equity=_fmt(wallet_equity), available_balance=_fmt(available_balance),
        price_observed_at_by_symbol=price_observed_at_by_symbol,
        price_freshness_status=price_freshness_status,
        freshness_evidence_by_symbol=freshness_evidence_by_symbol)

    # Instrument-rule rejection is driven by AUTHORITATIVE per-action rule validation.
    rule_rejection = batch.rule_rejection

    # --- TASK-014CD authoritative margin / freshness / network evidence -------
    margin_ev = dict(margin_evidence) if margin_evidence is not None \
        else md.unavailable_margin_evidence()
    margin_model = md.build_projected_margin_model(
        margin_evidence=margin_ev, strategy_gross_notional=strategy_gross,
        legacy_gross_notional=legacy_mark_gross, available_balance=available_balance,
        applicable_initial_margin_rate=applicable_initial_margin_rate)

    # CANONICAL aggregate freshness is DERIVED from the per-action statuses (the batch
    # aggregate). The review-level and top-level status equal this aggregate so the
    # whole document is consistent (TASK-014CD_FIX2). When no actions exist, fall back
    # to the evidence-summary status.
    overall_freshness_status = (batch.price_freshness_status if batch.actions
                                else (str(price_freshness_evidence.get("price_freshness_status"))
                                      if price_freshness_evidence is not None else price_freshness_status))
    # Exchange-timestamp availability is read straight from the evidence (never invented).
    exchange_timestamp_available = any(
        s.get("exchange_timestamp") is not None
        for s in ((price_freshness_evidence or {}).get("snapshots") or []))

    network_audit_status = (str(network_audit.get("network_audit_status"))
                            if network_audit is not None else md.NETWORK_AUDIT_CONSISTENT)

    # --- TASK-014CE_FIX1: canonical margin-model status semantics --------------
    # observed_margin_snapshot_model_status: the CD/FIX1 NON-ATOMIC wallet+position
    #   snapshot interpretation (may stay PARTIAL because the two GETs are non-atomic).
    # projected_margin_model_status: the CE per-action risk-tier projection result.
    # margin_model_status (canonical execution-planning meaning): the PROJECTED model
    #   when CE evidence exists, else the observed snapshot model.
    observed_margin_snapshot_model_status = margin_model["margin_model_status"]
    canonical_margin_model_status = (str(account_margin_model.get("margin_model_status"))
                                     if account_margin_model is not None
                                     else observed_margin_snapshot_model_status)

    feasibility = assess_feasibility(
        wallet_equity=wallet_equity, available_balance=available_balance,
        strategy_gross_notional=strategy_gross, legacy_gross_notional=legacy_mark_gross,
        leverage_authoritative=leverage_authoritative,
        initial_margin_authoritative=initial_margin_authoritative,
        assumed_leverage=assumed_leverage, instrument_rule_rejection=rule_rejection,
        legacy_mark_price_available=legacy_mark_price_available,
        price_freshness_status=overall_freshness_status,
        exchange_timestamp_available=exchange_timestamp_available)

    batch_float_artifact_count = _batch_float_artifact_count(batch.actions)
    # The blocker list uses the CANONICAL (projected, when present) margin-model status,
    # so AUTHORITATIVE_MARGIN_MODEL_PARTIAL is NOT emitted once all 50 projected actions
    # are complete. The observed NON-ATOMIC snapshot concern is preserved via the CD
    # margin_model_blockers (NON_ATOMIC_MARGIN_SNAPSHOT), which are passed through.
    execution_readiness_blockers = md.build_execution_readiness_blockers(
        rule_rejection=rule_rejection, batch_float_artifact_count=batch_float_artifact_count,
        legacy_mark_price_available=legacy_mark_price_available,
        price_freshness_status=overall_freshness_status,
        margin_model_status=canonical_margin_model_status,
        margin_model_blockers=margin_model.get("margin_model_blockers"),
        network_audit_status=network_audit_status)

    # --- TASK-014CE: refine blockers with authoritative account-mode / risk-tier /
    # exchange-clock evidence. ACCOUNT_MARGIN_MODE_UNAVAILABLE and
    # APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE are resolved ONLY when the evidence
    # actually permits; precise CE blockers (PORTFOLIO/ISOLATED/tier/quote-timestamp)
    # are merged. The per-task authorization blocker always remains last. When no CE
    # evidence is supplied, the blocker list is unchanged (accepted CD behavior).
    if (account_mode_evidence is not None or account_margin_model is not None
            or exchange_clock_evidence is not None):
        execution_readiness_blockers = ce.reconcile_readiness_blockers(
            base_blockers=execution_readiness_blockers,
            account_mode_evidence=account_mode_evidence,
            account_margin_model=account_margin_model,
            exchange_clock_evidence=exchange_clock_evidence)

    longs = sum(1 for t in targets if _norm_side(t.get("side")) == "long")
    shorts = sum(1 for t in targets if _norm_side(t.get("side")) == "short")

    plan_valid = bool(getattr(plan, "available", False)) and \
        bool((getattr(plan, "sizing_verification", {}) or {}).get("verified", False))

    legacy_entry_gross = sum((r["_notional"] for r in separated.legacy_protected), Decimal("0"))

    return {
        "task_id": TASK_ID,
        **active_policy_classification(),
        # Isolated one-shot review is NEVER authoritative for the active V1 policy.
        "isolated_one_shot_review_is_authoritative": False,
        "plan_valid": plan_valid,
        "target_position_count": len(targets),
        "long_target_count": longs,
        "short_target_count": shorts,
        # Position separation + account-level exposure.
        "strategy_managed_open_position_count": len(separated.strategy_managed),
        "legacy_protected_position_count": len(separated.legacy_protected),
        "total_account_open_position_count": len(separated.strategy_managed) + len(separated.legacy_protected),
        "legacy_protected_positions": legacy_valued,
        "legacy_executable_action_count": 0,
        "legacy_mark_price_available": legacy_mark_price_available,
        "strategy_target_gross_notional_usdt": _fmt(strategy_gross),
        # Account-level CURRENT risk uses the MARK valuation; entry is informational.
        "legacy_mark_gross_notional_usdt": _fmt(legacy_mark_gross),
        "legacy_gross_notional_usdt": _fmt(legacy_mark_gross),
        "legacy_entry_gross_notional_usdt_informational": _fmt(legacy_entry_gross),
        "total_projected_account_gross_notional_usdt": _fmt(strategy_gross + legacy_mark_gross),
        "available_balance_usdt": _fmt(available_balance),
        "wallet_equity_usdt": _fmt(wallet_equity),
        "projected_margin_feasibility_status": feasibility["projected_margin_feasibility_status"],
        "feasibility": feasibility,
        "reconciliation": recon,
        "execution_batch": batch.to_dict(),
        "batch_float_artifact_count": batch_float_artifact_count,
        "non_null_rule_fingerprint_count": batch.non_null_rule_fingerprint_count,
        "price_freshness_status": overall_freshness_status,
        # TASK-014CD authoritative evidence (Plan-only; authorizes nothing).
        "margin_evidence": margin_ev,
        # CD observed (non-atomic wallet+position) snapshot model, kept for audit.
        "margin_model": margin_model,
        "observed_margin_snapshot_model": margin_model,
        "observed_margin_snapshot_model_status": observed_margin_snapshot_model_status,
        # Canonical execution-planning margin status = projected model when CE evidence
        # exists (COMPLETE for the REGULAR_MARGIN VPS case), else the observed snapshot.
        "margin_model_status": canonical_margin_model_status,
        "price_freshness_evidence": (dict(price_freshness_evidence)
                                     if price_freshness_evidence is not None else None),
        # ONE canonical complete-account network audit (TASK-014CE_FIX1). When CE
        # evidence is supplied this carries the full public/private GET counts; the
        # planner/ticker-only CD counts live under the explicitly scoped
        # ticker_price_network_audit (never the canonical network_audit name).
        "network_audit": (dict(network_audit) if network_audit is not None else None),
        "network_audit_status": network_audit_status,
        "ticker_price_network_audit": (dict(ticker_price_network_audit)
                                       if ticker_price_network_audit is not None else None),
        # TASK-014CE authoritative account-mode / risk-tier / exchange-clock evidence
        # (Plan-only; authorizes nothing). Null when not supplied (accepted CD output).
        "account_mode_evidence": (dict(account_mode_evidence)
                                  if account_mode_evidence is not None else None),
        "risk_limit_evidence": (dict(risk_limit_evidence)
                                if risk_limit_evidence is not None else None),
        "exchange_clock_evidence": (dict(exchange_clock_evidence)
                                    if exchange_clock_evidence is not None else None),
        "projected_margin_model": (dict(account_margin_model)
                                   if account_margin_model is not None else None),
        "projected_margin_model_status": ((account_margin_model or {}).get("margin_model_status")
                                          if account_margin_model is not None else None),
        # account_network_audit is retained ONLY as an exact alias of the canonical
        # network_audit (proven value-equal) so no two blocks carry different counts.
        "account_network_audit": (dict(network_audit)
                                  if account_network_audit is not None else None),
        "execution_readiness_blockers": execution_readiness_blockers,
        # Authorization / dispatch invariants (Plan-only).
        "execution_batch_present": True,
        "execution_batch_authorized": False,
        "execution_ready": False,
        "sender_reachable": False,
        "execute_daily_native_called": False,
        "execute_daily_native_call_count": 0,
        "transport_sender_call_count": 0,
        "order_endpoint_called": False,
        "order_post_count": 0,
        "amend_post_count": 0,
        "cancel_post_count": 0,
        "live_endpoint_called": False,
        "live_trading_authorized": False,
        "detail": ("ACTIVE Strategy-native V1 portfolio review (Plan-only). The full multi-symbol V1 "
                   "plan is preserved; every batch action is bound to authoritative instrument rules "
                   "and canonical Decimal payloads. Legacy protected positions are untouched and "
                   "never block planning but count toward account-level feasibility at CURRENT MARK "
                   "price. No order is dispatched and no execution is authorized in this task."),
    }


def _batch_float_artifact_count(actions: Sequence[Mapping[str, Any]]) -> int:
    """Count canonical string fields that still carry a binary-float artifact tail.
    Authoritative evidence that the batch is artifact-free (expected 0)."""
    fields = ("qty", "qty_decimal", "qty_step", "price_snapshot", "target_notional_usdt",
              "current_position_qty", "current_position_notional_usdt", "delta_notional_usdt",
              "min_qty", "max_qty", "min_notional", "tick_size")
    count = 0
    for a in actions:
        for f in fields:
            v = a.get(f)
            if v is not None and has_float_artifact(v):
                count += 1
    return count


__all__ = [
    "TASK_ID", "ACTIVE_STRATEGY", "PROTECTED_SYMBOLS",
    "POLICY_ACTIVE_STRATEGY_NATIVE_V1", "POLICY_LEGACY_INACTIVE_READINESS",
    "POLICY_ISOLATED_ONE_SHOT_TEST", "LEGACY_PROTECTED_EXTERNAL_POSITIONS",
    "RECON_OPEN", "RECON_HOLD", "RECON_INCREASE", "RECON_REDUCE", "RECON_CLOSE",
    "RECON_REVERSE", "RECON_LEGACY_PROTECTED_UNMANAGED",
    "STRATEGY_PORTFOLIO_FEASIBLE", "STRATEGY_PORTFOLIO_INSUFFICIENT_AVAILABLE_MARGIN",
    "STRATEGY_PORTFOLIO_RULE_REJECTION", "STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED",
    "INSTRUMENT_RULE_STATUS_TRADING",
    "RULE_VALIDATION_PASS", "RULE_VALIDATION_MISSING", "RULE_VALIDATION_NON_TRADING",
    "RULE_VALIDATION_MALFORMED", "RULE_VALIDATION_QTY_STEP_VIOLATION",
    "RULE_VALIDATION_MIN_QTY_VIOLATION", "RULE_VALIDATION_MAX_QTY_VIOLATION",
    "RULE_VALIDATION_MIN_NOTIONAL_VIOLATION",
    "MARK_PRICE_AVAILABLE", "LEGACY_MARK_PRICE_UNAVAILABLE",
    "PRICE_FRESHNESS_FRESH", "PRICE_FRESHNESS_STALE", "PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE",
    "active_policy_classification", "separate_positions", "value_legacy_positions",
    "reconcile_portfolio", "normalize_rule_evidence", "validate_action_rule",
    "build_execution_batch", "assess_feasibility", "build_strategy_native_review",
    "action_fingerprint", "canonical_action_payload_fingerprint", "idempotency_key",
    "has_float_artifact", "SeparatedPositions", "ExecutionBatch",
]
