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
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from src import demo_strategy_pilot_readiness as rd

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
    reduce_only: bool, qty: str, notional: str, instrument_rule_fingerprint: str | None,
    artifact_fingerprint: str | None,
) -> str:
    payload = "|".join([
        TASK_ID, str(run_date), str(pilot_id), str(symbol), str(side), str(intent),
        str(reduce_only), str(qty), str(notional), str(instrument_rule_fingerprint or ""),
        str(artifact_fingerprint or ""),
    ])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


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
) -> ExecutionBatch:
    """Deterministic production-shaped (multi-symbol) execution batch. NEVER sent;
    sender_reachable is always False. Actions are ordered by symbol so the batch
    identity is stable across reruns."""
    actions: list[dict[str, Any]] = []
    opening = Decimal("0")
    reducing = Decimal("0")
    gross = Decimal("0")

    for rec in reconciliation:
        cls = rec["classification"]
        symbol = rec["symbol"]
        if cls in (RECON_HOLD, RECON_LEGACY_PROTECTED_UNMANAGED) or not rec.get("executable"):
            continue
        tgt = targets_by_symbol.get(symbol, {})
        cur = managed_by_symbol.get(symbol, {})
        rule_ev = rule_evidence_by_symbol.get(symbol, {})
        qty = _fmt(tgt.get("qty", cur.get("qty", 0)))
        qty_step = _fmt(rule_ev.get("qty_step")) if rule_ev.get("qty_step") is not None else \
            _fmt(tgt.get("qty_step", 0))
        price = _fmt(price_by_symbol.get(symbol, tgt.get("price", 0)))
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
        rule_fp = rule_ev.get("instrument_rule_fingerprint")
        afp = action_fingerprint(run_date=run_date, pilot_id=pilot_id, symbol=symbol,
                                 side=side, intent=intent, reduce_only=reduce_only, qty=qty,
                                 notional=target_notional, instrument_rule_fingerprint=rule_fp,
                                 artifact_fingerprint=artifact_fingerprint)
        ikey = idempotency_key(run_date=run_date, pilot_id=pilot_id, symbol=symbol,
                               side=side, intent=intent, qty=qty)
        actions.append({
            "symbol": symbol, "side": side, "intent": intent, "reduce_only": reduce_only,
            "qty": qty, "qty_decimal": qty, "qty_step": qty_step, "price_snapshot": price,
            "target_notional_usdt": target_notional,
            "current_position_qty": _fmt(cur.get("qty", 0)),
            "current_position_notional_usdt": _fmt(cur_notional),
            "delta_notional_usdt": _fmt(delta_notional),
            "instrument_rule_fingerprint": rule_fp,
            "action_fingerprint": afp, "idempotency_key": ikey,
        })

    actions.sort(key=lambda a: a["symbol"])
    ordered_fps = [a["action_fingerprint"] for a in actions]
    snap_fp = _account_snapshot_fingerprint(separated, wallet_equity, available_balance)
    batch_payload = "|".join([str(run_date), str(pilot_id), str(artifact_fingerprint or ""),
                              snap_fp, *ordered_fps])
    batch_id = "batch:" + hashlib.sha256(batch_payload.encode("utf-8")).hexdigest()[:32]

    return ExecutionBatch(
        batch_id=batch_id, strategy_run_date=str(run_date),
        strategy_artifact_fingerprint=artifact_fingerprint,
        pre_execution_account_snapshot_fingerprint=snap_fp,
        ordered_action_fingerprints=ordered_fps, expected_action_count=len(actions),
        total_opening_notional_usdt=_fmt(opening), total_reducing_notional_usdt=_fmt(reducing),
        total_projected_gross_exposure_usdt=_fmt(gross), actions=actions,
        batch_authorization_status=BATCH_AUTHORIZATION_UNAUTHORIZED_PLAN_ONLY,
        batch_execution_status=BATCH_EXECUTION_NOT_STARTED, sender_reachable=False)


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
) -> dict[str, Any]:
    """Account-level feasibility for the FULL strategy portfolio. Legacy protected
    exposure is included in total account gross notional and risk. Leverage/initial
    margin are never assumed; if they cannot be read authoritatively the result is
    ACCOUNT_RISK_REVIEW_REQUIRED (fail closed) while the full plan stays visible."""
    strat = _dec(strategy_gross_notional)
    legacy = _dec(legacy_gross_notional)
    total = strat + legacy
    equity = _dec(wallet_equity)
    avail = _dec(available_balance)

    assumptions: list[str] = [
        "strategy sizing is NEVER reduced by wallet equity (feasibility is a check, not a resize)",
        "legacy protected exposure is included in total account gross notional and risk",
    ]

    if instrument_rule_rejection:
        status = STRATEGY_PORTFOLIO_RULE_REJECTION
        assumptions.append("one or more target symbols failed instrument-rule validation")
        required_im: Decimal | None = None
    elif not (leverage_authoritative and initial_margin_authoritative):
        status = STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
        assumptions.append("authoritative per-symbol leverage / initial-margin requirement is "
                           "UNAVAILABLE from read-only Demo metadata; required initial margin "
                           "cannot be computed; failing closed without assuming leverage")
        required_im = None
    else:
        lev = _dec(assumed_leverage)
        if lev <= 0:
            status = STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
            required_im = None
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
        "legacy_gross_notional_usdt": _fmt(legacy),
        "total_projected_account_gross_notional_usdt": _fmt(total),
        "required_initial_margin_usdt": (_fmt(required_im) if required_im is not None else None),
        "leverage_authoritative": leverage_authoritative,
        "initial_margin_authoritative": initial_margin_authoritative,
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
) -> dict[str, Any]:
    """Full ACTIVE V1 Strategy-native Plan-only review. Non-dispatching: builds a
    multi-symbol execution batch but authorizes and sends nothing. Legacy protected
    positions are separated, untouched, never block planning, but count toward
    account-level feasibility."""
    rule_evidence_by_symbol = dict(rule_evidence_by_symbol or {})
    price_by_symbol = dict(price_by_symbol or {})

    targets = list(getattr(plan, "target_positions", []) or [])
    targets_by = {str(t.get("symbol", "")).strip().upper(): t for t in targets}
    separated = separate_positions(open_positions)
    managed_by = {r["symbol"]: r for r in separated.strategy_managed}

    recon = reconcile_portfolio(targets=targets, separated=separated)

    strategy_gross = sum((_dec(t.get("target_notional")).copy_abs() for t in targets), Decimal("0"))
    legacy_gross = sum((r["_notional"] for r in separated.legacy_protected), Decimal("0"))

    # Instrument-rule rejection if any target lacks a valid TRADING rule (when
    # rule evidence is supplied).
    rule_rejection = False
    if rule_evidence_by_symbol:
        for sym in targets_by:
            ev = rule_evidence_by_symbol.get(sym)
            if ev is not None and ev.get("rule_status") not in (None, "TRADING"):
                rule_rejection = True
                break

    feasibility = assess_feasibility(
        wallet_equity=wallet_equity, available_balance=available_balance,
        strategy_gross_notional=strategy_gross, legacy_gross_notional=legacy_gross,
        leverage_authoritative=leverage_authoritative,
        initial_margin_authoritative=initial_margin_authoritative,
        assumed_leverage=assumed_leverage, instrument_rule_rejection=rule_rejection)

    batch = build_execution_batch(
        run_date=run_date, pilot_id=pilot_id, artifact_fingerprint=artifact_fingerprint,
        reconciliation=recon, targets_by_symbol=targets_by, managed_by_symbol=managed_by,
        rule_evidence_by_symbol=rule_evidence_by_symbol, price_by_symbol=price_by_symbol,
        separated=separated, wallet_equity=_fmt(wallet_equity), available_balance=_fmt(available_balance))

    longs = sum(1 for t in targets if _norm_side(t.get("side")) == "long")
    shorts = sum(1 for t in targets if _norm_side(t.get("side")) == "short")

    plan_valid = bool(getattr(plan, "available", False)) and \
        bool((getattr(plan, "sizing_verification", {}) or {}).get("verified", False))

    return {
        "task_id": TASK_ID,
        **active_policy_classification(),
        "plan_valid": plan_valid,
        "target_position_count": len(targets),
        "long_target_count": longs,
        "short_target_count": shorts,
        # Position separation + account-level exposure.
        "strategy_managed_open_position_count": len(separated.strategy_managed),
        "legacy_protected_position_count": len(separated.legacy_protected),
        "total_account_open_position_count": len(separated.strategy_managed) + len(separated.legacy_protected),
        "legacy_protected_positions": [
            {k: v for k, v in r.items() if not k.startswith("_")} for r in separated.legacy_protected],
        "legacy_executable_action_count": 0,
        "strategy_target_gross_notional_usdt": _fmt(strategy_gross),
        "legacy_gross_notional_usdt": _fmt(legacy_gross),
        "total_projected_account_gross_notional_usdt": _fmt(strategy_gross + legacy_gross),
        "available_balance_usdt": _fmt(available_balance),
        "wallet_equity_usdt": _fmt(wallet_equity),
        "projected_margin_feasibility_status": feasibility["projected_margin_feasibility_status"],
        "feasibility": feasibility,
        "reconciliation": recon,
        "execution_batch": batch.to_dict(),
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
                   "plan is preserved; legacy protected positions are untouched and never block "
                   "planning but count toward account-level feasibility. No order is dispatched and "
                   "no execution is authorized in this task."),
    }


__all__ = [
    "TASK_ID", "ACTIVE_STRATEGY", "PROTECTED_SYMBOLS",
    "POLICY_ACTIVE_STRATEGY_NATIVE_V1", "POLICY_LEGACY_INACTIVE_READINESS",
    "POLICY_ISOLATED_ONE_SHOT_TEST", "LEGACY_PROTECTED_EXTERNAL_POSITIONS",
    "RECON_OPEN", "RECON_HOLD", "RECON_INCREASE", "RECON_REDUCE", "RECON_CLOSE",
    "RECON_REVERSE", "RECON_LEGACY_PROTECTED_UNMANAGED",
    "STRATEGY_PORTFOLIO_FEASIBLE", "STRATEGY_PORTFOLIO_INSUFFICIENT_AVAILABLE_MARGIN",
    "STRATEGY_PORTFOLIO_RULE_REJECTION", "STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED",
    "active_policy_classification", "separate_positions", "reconcile_portfolio",
    "build_execution_batch", "assess_feasibility", "build_strategy_native_review",
    "action_fingerprint", "idempotency_key", "has_float_artifact", "SeparatedPositions",
    "ExecutionBatch",
]
