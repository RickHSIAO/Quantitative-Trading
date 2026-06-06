"""
src/demo_instrument_rules.py
TASK-014B: Instrument rules and position rounding for Demo sizing proposals.

Provides pure functions for exchange-compatible quantity/price rounding and
validation. Accepts duck-typed proposal objects from demo_portfolio_risk.py
without importing it (structural compatibility, no circular dependency).

SAFETY INVARIANTS:
  1. rounded_quantity <= original_quantity          (always round DOWN)
  2. stop_risk_after_rounding <= orig_risk + STOP_RISK_TOLERANCE_USD
  3. reject if rounded_quantity < min_qty
  4. reject if notional_after_rounding < min_notional
  5. reject if rules are invalid (NaN, inf, <= 0)
  6. reject if proposal values are NaN / inf / negative
  7. reject if rules is None                        (missing_instrument_rule)

No exchange API calls. No secrets. No order endpoints.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Rejection reason constants
# ---------------------------------------------------------------------------

REJECT_MISSING_RULE     = "missing_instrument_rule"
REJECT_MIN_QTY          = "min_qty_after_rounding"
REJECT_MIN_NOTIONAL     = "min_notional_after_rounding"
REJECT_INVALID_RULES    = "invalid_instrument_rules"
REJECT_INVALID_INPUT    = "invalid_input_values"
REJECT_STOP_RISK_RAISED = "stop_risk_increased_after_rounding"

# Rounded stop-risk may exceed original by at most this many USD (float tolerance).
STOP_RISK_TOLERANCE_USD: float = 0.01


# ---------------------------------------------------------------------------
# Instrument rules
# ---------------------------------------------------------------------------

@dataclass
class InstrumentRules:
    """
    Exchange instrument specification for a symbol.
    qty_step, tick_size, min_notional must be finite and positive.
    min_qty must be finite and >= 0.
    max_qty = 0 means no upper limit.
    """
    symbol:          str
    qty_step:        float   # minimum quantity increment (e.g. 0.001 for BTC)
    min_qty:         float   # minimum allowed order quantity
    max_qty:         float   # maximum allowed order quantity (0 = no limit)
    tick_size:       float   # minimum price increment (e.g. 0.01)
    min_notional:    float   # minimum order value in USD
    price_precision: int     # decimal places for price display
    qty_precision:   int     # decimal places for quantity display

    def is_valid(self) -> tuple[bool, str]:
        if not math.isfinite(self.qty_step) or self.qty_step <= 0:
            return False, f"qty_step={self.qty_step!r} must be finite and > 0"
        if not math.isfinite(self.min_qty) or self.min_qty < 0:
            return False, f"min_qty={self.min_qty!r} must be finite and >= 0"
        if not math.isfinite(self.tick_size) or self.tick_size <= 0:
            return False, f"tick_size={self.tick_size!r} must be finite and > 0"
        if not math.isfinite(self.min_notional) or self.min_notional < 0:
            return False, f"min_notional={self.min_notional!r} must be finite and >= 0"
        return True, ""


# ---------------------------------------------------------------------------
# Rounding functions
# ---------------------------------------------------------------------------

def round_qty_down(quantity: float, qty_step: float) -> float:
    """
    Round quantity DOWN to the nearest qty_step multiple (always floors).
    Never rounds up — prevents risk overshoot.
    Returns 0.0 for any invalid inputs (NaN, inf, negative, bad step).

    A tiny epsilon (1e-9) is added to the ratio before flooring to absorb
    binary floating-point representation errors (e.g. 1.2/0.1 = 11.9999…
    in IEEE 754 instead of the exact 12.0).  The epsilon is far smaller than
    any realistic qty_step difference, so it never causes genuine rounding-up.
    """
    if not math.isfinite(quantity) or quantity < 0:
        return 0.0
    if not math.isfinite(qty_step) or qty_step <= 0:
        return 0.0
    steps = math.floor(quantity / qty_step + 1e-9)
    return steps * qty_step


def round_price_to_tick(price: float, tick_size: float) -> float:
    """
    Round price to nearest tick_size using standard (half-up) rounding.
    Deterministic: same input always gives same output.
    Returns 0.0 for invalid inputs.
    """
    if not math.isfinite(price) or price <= 0:
        return 0.0
    if not math.isfinite(tick_size) or tick_size <= 0:
        return 0.0
    ticks = round(price / tick_size)
    return ticks * tick_size


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_min_qty(quantity: float, min_qty: float) -> tuple[bool, str]:
    """Returns (passes, rejection_reason_or_empty_string)."""
    if not math.isfinite(quantity) or quantity < 0:
        return False, REJECT_INVALID_INPUT
    if quantity < min_qty - 1e-12:
        return False, REJECT_MIN_QTY
    return True, ""


def validate_min_notional(notional: float, min_notional: float) -> tuple[bool, str]:
    """Returns (passes, rejection_reason_or_empty_string)."""
    if not math.isfinite(notional) or notional < 0:
        return False, REJECT_INVALID_INPUT
    if notional < min_notional - 1e-6:
        return False, REJECT_MIN_NOTIONAL
    return True, ""


# ---------------------------------------------------------------------------
# Per-proposal result
# ---------------------------------------------------------------------------

@dataclass
class RoundedProposal:
    symbol:                   str
    side:                     str
    score:                    float
    rank:                     int
    original_quantity:        float
    rounded_quantity:         float
    original_entry_price:     float
    rounded_entry_price:      float
    original_stop_price:      float
    rounded_stop_price:       float
    original_notional_usd:    float
    notional_after_rounding:  float
    original_stop_risk_usd:   float
    stop_risk_after_rounding: float
    accepted:                 bool
    reject_reason:            str
    detail:                   dict[str, Any] = field(default_factory=dict)


# ---------------------------------------------------------------------------
# Core: apply rules to one proposal (duck-typed input)
# ---------------------------------------------------------------------------

def apply_instrument_rules_to_proposal(
    proposal: Any,
    rules: "InstrumentRules | None",
) -> RoundedProposal:
    """
    Apply instrument rounding and validation to a sizing proposal.

    `proposal` must carry attributes:
      symbol, side, score, rank, quantity, entry_price, stop_price,
      proposed_notional_usd, allocated_stop_risk_usd

    Accepts PositionProposal from demo_portfolio_risk without importing it
    (duck typing / structural compatibility).

    INVARIANTS enforced:
      rounded_quantity      <= original_quantity            (floor, never ceil)
      stop_risk_after       <= orig_risk + STOP_RISK_TOLERANCE_USD
      rounded_quantity      >= min_qty                      (or reject)
      notional_after        >= min_notional                 (or reject)
    """
    sym           = getattr(proposal, "symbol",                "")
    side          = getattr(proposal, "side",                  "")
    score         = float(getattr(proposal, "score",           0.0))
    rank          = int(getattr(proposal,   "rank",            0))
    orig_qty      = float(getattr(proposal, "quantity",        float("nan")))
    orig_entry    = float(getattr(proposal, "entry_price",     float("nan")))
    orig_stop     = float(getattr(proposal, "stop_price",      float("nan")))
    orig_notional = float(getattr(proposal, "proposed_notional_usd",    float("nan")))
    orig_risk     = float(getattr(proposal, "allocated_stop_risk_usd",  float("nan")))

    def _rej(reason: str, rq=0.0, re=0.0, rs=0.0, na=0.0, ra=0.0,
             detail: dict | None = None) -> RoundedProposal:
        return RoundedProposal(
            symbol=sym, side=side, score=score, rank=rank,
            original_quantity=orig_qty,      rounded_quantity=rq,
            original_entry_price=orig_entry, rounded_entry_price=re,
            original_stop_price=orig_stop,   rounded_stop_price=rs,
            original_notional_usd=orig_notional, notional_after_rounding=na,
            original_stop_risk_usd=orig_risk,    stop_risk_after_rounding=ra,
            accepted=False, reject_reason=reason,
            detail=detail or {},
        )

    # ── guard: missing rules ──────────────────────────────────────────────
    if rules is None:
        return _rej(REJECT_MISSING_RULE, detail={"symbol": sym})

    # ── guard: invalid proposal inputs ───────────────────────────────────
    if (not math.isfinite(orig_qty)      or orig_qty      <  0
     or not math.isfinite(orig_entry)    or orig_entry    <= 0
     or not math.isfinite(orig_stop)     or orig_stop     <= 0
     or not math.isfinite(orig_notional) or orig_notional <  0
     or not math.isfinite(orig_risk)     or orig_risk     <  0):
        return _rej(REJECT_INVALID_INPUT)

    # ── guard: invalid rules ──────────────────────────────────────────────
    rules_ok, rules_err = rules.is_valid()
    if not rules_ok:
        return _rej(REJECT_INVALID_RULES, detail={"rules_error": rules_err})

    # ── round quantity DOWN to qty_step ───────────────────────────────────
    rounded_qty = round_qty_down(orig_qty, rules.qty_step)

    # ── round prices to tick_size ─────────────────────────────────────────
    rounded_entry = round_price_to_tick(orig_entry, rules.tick_size)
    rounded_stop  = round_price_to_tick(orig_stop,  rules.tick_size)

    # ── recompute notional and stop-risk from rounded values ──────────────
    notional_after = rounded_qty * rounded_entry if rounded_entry > 0 else 0.0
    if rounded_stop > 0 and rounded_entry > 0 and rounded_qty > 0:
        stop_risk_after = abs(rounded_entry - rounded_stop) * rounded_qty
    else:
        stop_risk_after = 0.0

    # ── invariant: rounded_qty must not exceed original ───────────────────
    if rounded_qty > orig_qty + 1e-12:
        return _rej(
            REJECT_INVALID_RULES,
            rq=rounded_qty, re=rounded_entry, rs=rounded_stop,
            na=notional_after, ra=stop_risk_after,
            detail={"violation": "rounded_qty > original_qty",
                    "rounded_qty": rounded_qty, "original_qty": orig_qty},
        )

    # ── invariant: stop risk must not increase beyond tolerance ──────────
    if stop_risk_after > orig_risk + STOP_RISK_TOLERANCE_USD:
        return _rej(
            REJECT_STOP_RISK_RAISED,
            rq=rounded_qty, re=rounded_entry, rs=rounded_stop,
            na=notional_after, ra=stop_risk_after,
            detail={"stop_risk_after": stop_risk_after,
                    "original_risk":   orig_risk,
                    "excess":          stop_risk_after - orig_risk},
        )

    # ── min_qty check ─────────────────────────────────────────────────────
    qty_ok, qty_err = validate_min_qty(rounded_qty, rules.min_qty)
    if not qty_ok:
        return _rej(
            qty_err,
            rq=rounded_qty, re=rounded_entry, rs=rounded_stop,
            na=notional_after, ra=stop_risk_after,
            detail={"rounded_qty": rounded_qty, "min_qty": rules.min_qty},
        )

    # ── min_notional check ────────────────────────────────────────────────
    notional_ok, notional_err = validate_min_notional(notional_after, rules.min_notional)
    if not notional_ok:
        return _rej(
            notional_err,
            rq=rounded_qty, re=rounded_entry, rs=rounded_stop,
            na=notional_after, ra=stop_risk_after,
            detail={"notional_after": notional_after, "min_notional": rules.min_notional},
        )

    # ── all checks passed ─────────────────────────────────────────────────
    return RoundedProposal(
        symbol=sym, side=side, score=score, rank=rank,
        original_quantity=orig_qty,      rounded_quantity=rounded_qty,
        original_entry_price=orig_entry, rounded_entry_price=rounded_entry,
        original_stop_price=orig_stop,   rounded_stop_price=rounded_stop,
        original_notional_usd=orig_notional, notional_after_rounding=notional_after,
        original_stop_risk_usd=orig_risk,    stop_risk_after_rounding=stop_risk_after,
        accepted=True, reject_reason="",
        detail={
            "qty_step":     rules.qty_step,
            "tick_size":    rules.tick_size,
            "min_qty":      rules.min_qty,
            "min_notional": rules.min_notional,
        },
    )
