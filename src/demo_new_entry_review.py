"""
src/demo_new_entry_review.py
TASK-014K: Demo new-entry dry-run proposal review.

Reads a verified reconciliation snapshot (real_readonly) and a list of new-entry
candidates; per candidate it applies a layered fail-closed gate, projects the
resulting portfolio state, and produces a payload preview that is NEVER sent.

This module is PREVIEW ONLY.  It does not import or call any order endpoints.
It does not modify positions, send orders, or touch the close-only sender.
No secrets are loaded, read, or printed.

SAFETY INVARIANTS (structural — verified by tests):
  no_orders_sent          = True   (always)
  order_endpoint_called   = False  (always)
  order_sent              = False  (always, on every payload preview)
  preview_only            = True   (always, on every payload preview)
  confirmation_required   = True   (always, on every payload preview)
  no_position_modified    = True   (always)
  secret_value_observed   = False  (always)
  action_type             = "PREVIEW_REVIEW_ONLY" (always)
  short_capacity_full     → every short candidate REJECTED (no short payloads)

No imports of main, src.risk, BybitExecutor, close-only sender, or any
exchange-execution module.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from src.demo_instrument_rules import (
    InstrumentRules,
    REJECT_MIN_NOTIONAL,
    REJECT_MIN_QTY,
    REJECT_MISSING_RULE,
    round_price_to_tick,
    round_qty_down,
)
from src.demo_portfolio_risk import (
    MAX_GROSS_EXPOSURE_RATIO,
    MAX_LONG_POSITIONS,
    MAX_NET_EXPOSURE_RATIO,
    MAX_OPEN_POSITIONS,
    MAX_SHORT_POSITIONS,
    MAX_SINGLE_POSITION_NOTIONAL_PCT,
    MAX_SINGLE_TRADE_RISK_SHARE,
)
from src.demo_position_reconcile import ReconciliationResult


# ---------------------------------------------------------------------------
# Rejection reason constants
# ---------------------------------------------------------------------------

REJECT_RECONCILIATION_NOT_PASS    = "reconciliation_not_pass"
REJECT_PROOF_NOT_STRONG           = "proof_not_strong"
REJECT_RUNTIME_NOT_VERIFIED       = "runtime_not_verified"
REJECT_SOURCE_NOT_REAL_READONLY   = "position_details_source_not_real_readonly"
REJECT_AVAILABLE_BALANCE          = "available_balance_zero_or_negative"
REJECT_OPEN_POSITIONS_FULL        = "open_positions_full"
REJECT_SHORT_CAPACITY_FULL        = "short_capacity_full"
REJECT_LONG_CAPACITY_FULL         = "long_capacity_full"
REJECT_DUPLICATE_SYMBOL           = "duplicate_symbol_existing_position"
REJECT_MISSING_INSTRUMENT_RULE    = "missing_instrument_rule"
REJECT_INVALID_SIDE               = "invalid_side"
REJECT_INVALID_ENTRY_PRICE        = "invalid_entry_price"
REJECT_INVALID_STOP_PRICE         = "invalid_stop_price"
REJECT_INVALID_STOP_DISTANCE      = "invalid_stop_distance"
REJECT_REQUESTED_RISK_NON_POSITIVE = "requested_risk_non_positive"
REJECT_ROUND_QTY_ZERO             = "rounded_qty_zero"
REJECT_MIN_QTY_AFTER_ROUNDING     = REJECT_MIN_QTY
REJECT_MIN_NOTIONAL_AFTER_ROUNDING = REJECT_MIN_NOTIONAL
REJECT_STOP_RISK_NON_POSITIVE     = "stop_risk_non_positive"
REJECT_REMAINING_BUDGET_INSUFFICIENT = "remaining_risk_budget_insufficient"
REJECT_PER_TRADE_RISK_CAP         = "per_trade_risk_cap_exceeded"
REJECT_MAX_SINGLE_NOTIONAL        = "max_single_position_notional_exceeded"
REJECT_PROJECTED_GROSS_EXPOSURE   = "projected_gross_exposure_exceeded"
REJECT_PROJECTED_NET_EXPOSURE     = "projected_net_exposure_exceeded"


# ---------------------------------------------------------------------------
# Input dataclass
# ---------------------------------------------------------------------------

@dataclass
class NewEntryCandidate:
    """
    A proposed new-entry trade.  Caller-supplied; the review never originates
    candidates itself.

    side:               "long" or "short" (case-insensitive)
    entry_reference_price: indicative entry price (USD)
    stop_price:         hard stop-loss price (USD); must be > 0 and on the
                        protective side of entry
    requested_risk_usd: the USD stop-risk the caller would like to allocate
                        to this trade (capped by per-trade share)
    score:              strategy score (sort key only; not used for risk)
    order_type:         preview order type label (default "Market")
    """
    symbol:                str
    side:                  str
    entry_reference_price: float
    stop_price:            float
    requested_risk_usd:    float
    score:                 float = 0.0
    order_type:            str   = "Market"


# ---------------------------------------------------------------------------
# Output dataclasses
# ---------------------------------------------------------------------------

@dataclass
class NewEntryPayloadPreview:
    """
    Read-only preview of the payload that WOULD be submitted to open a new
    position.  This is a planning artefact only; no sender exists in
    TASK-014K and order_sent is always False.

    Even though `reduce_only=False` (which would be required for new entries
    if a sender existed), this preview must NEVER be passed to any order
    endpoint — `preview_only=True` is the explicit gate.
    """
    symbol:                          str
    side:                            str    # "Buy" for long entry, "Sell" for short entry
    order_type:                      str
    qty:                             float
    reduce_only:                     bool   # always False for new entries
    preview_only:                    bool   # always True — never to be sent
    entry_reference_price:           float
    rounded_entry_price:             float
    stop_price:                      float
    rounded_stop_price:              float
    estimated_notional_usd:          float
    estimated_stop_risk_usd:         float
    portfolio_risk_budget_usd:       float
    remaining_risk_budget_before:    float
    remaining_risk_budget_after:     float
    projected_open_positions_count:  int
    projected_long_count:            int
    projected_short_count:           int
    projected_gross_exposure_ratio:  float
    projected_net_exposure_ratio:    float
    confirmation_required:           bool   # always True
    order_sent:                      bool   # always False
    order_endpoint_called:           bool   # always False

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol":                         self.symbol,
            "side":                           self.side,
            "order_type":                     self.order_type,
            "qty":                            self.qty,
            "reduce_only":                    self.reduce_only,
            "preview_only":                   self.preview_only,
            "entry_reference_price":          self.entry_reference_price,
            "rounded_entry_price":            self.rounded_entry_price,
            "stop_price":                     self.stop_price,
            "rounded_stop_price":             self.rounded_stop_price,
            "estimated_notional_usd":         round(self.estimated_notional_usd, 2),
            "estimated_stop_risk_usd":        round(self.estimated_stop_risk_usd, 2),
            "portfolio_risk_budget_usd":      round(self.portfolio_risk_budget_usd, 2),
            "remaining_risk_budget_before":   round(self.remaining_risk_budget_before, 2),
            "remaining_risk_budget_after":    round(self.remaining_risk_budget_after, 2),
            "projected_open_positions_count": self.projected_open_positions_count,
            "projected_long_count":           self.projected_long_count,
            "projected_short_count":          self.projected_short_count,
            "projected_gross_exposure_ratio": round(self.projected_gross_exposure_ratio, 4),
            "projected_net_exposure_ratio":   round(self.projected_net_exposure_ratio, 4),
            "confirmation_required":          self.confirmation_required,
            "order_sent":                     self.order_sent,
            "order_endpoint_called":          self.order_endpoint_called,
        }


@dataclass
class NewEntryEvaluation:
    """
    One per input candidate: accepted/rejected with diagnostic detail.
    `payload` is non-None iff `accepted=True`.
    """
    symbol:            str
    side:              str
    accepted:          bool
    reject_reason:     str            # "" when accepted
    detail:            dict[str, Any] = field(default_factory=dict)
    payload:           NewEntryPayloadPreview | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol":        self.symbol,
            "side":          self.side,
            "accepted":      self.accepted,
            "reject_reason": self.reject_reason,
            "detail":        self.detail,
            "payload":       self.payload.to_dict() if self.payload else None,
        }


@dataclass
class NewEntryReviewResult:
    """
    Full new-entry review output.  Reports gate state, evaluations,
    payload previews, and safety invariants.
    """
    # Context
    mode:                                str   # "fixture" | "real_readonly_snapshot"
    demo_runtime_verified:               bool
    proof_strength:                      str
    endpoint_family:                     str
    account_mode:                        str
    position_details_source:             str

    # Reconciliation snapshot
    new_entry_allowed_from_reconciliation: bool
    available_balance_usd:               float
    available_balance_usd_source:        str
    equity_usd:                          float
    portfolio_risk_budget_usd:           float
    remaining_risk_budget_usd:           float
    open_positions_count:                int
    long_count:                          int
    short_count:                         int
    max_long_allowed_remaining:          int
    max_short_allowed_remaining:         int
    gross_exposure_ratio:                float
    net_exposure_ratio:                  float

    # Fail-closed gate state (top-level — applies before per-candidate review)
    fail_closed:                         bool
    fail_closed_reasons:                 list[str]

    # Per-candidate results
    evaluations:                         list[NewEntryEvaluation]
    accepted_candidates:                 list[NewEntryEvaluation]
    rejected_candidates:                 list[NewEntryEvaluation]
    payload_previews:                    list[NewEntryPayloadPreview]

    # Existing-position symbols (for duplicate check)
    existing_symbols:                    list[str]

    # Recommended next action
    next_required_task:                  str

    # Safety invariants — always these values
    action_type:                         str  = "PREVIEW_REVIEW_ONLY"
    no_orders_sent:                      bool = True
    no_position_modified:                bool = True
    order_endpoint_called:               bool = False
    secret_value_observed:               bool = False

    def to_dict(self, timestamp_utc: str = "") -> dict[str, Any]:
        return {
            "timestamp":                             timestamp_utc,
            "mode":                                  self.mode,
            "demo_runtime_verified":                 self.demo_runtime_verified,
            "proof_strength":                        self.proof_strength,
            "endpoint_family":                       self.endpoint_family,
            "account_mode":                          self.account_mode,
            "position_details_source":               self.position_details_source,
            "new_entry_allowed_from_reconciliation": self.new_entry_allowed_from_reconciliation,
            "available_balance_usd":                 round(self.available_balance_usd, 2),
            "available_balance_usd_source":          self.available_balance_usd_source,
            "equity_usd":                            round(self.equity_usd, 2),
            "portfolio_risk_budget_usd":             round(self.portfolio_risk_budget_usd, 2),
            "remaining_risk_budget_usd":             round(self.remaining_risk_budget_usd, 2),
            "open_positions_count":                  self.open_positions_count,
            "long_count":                            self.long_count,
            "short_count":                           self.short_count,
            "max_long_allowed_remaining":            self.max_long_allowed_remaining,
            "max_short_allowed_remaining":           self.max_short_allowed_remaining,
            "gross_exposure_ratio":                  round(self.gross_exposure_ratio, 4),
            "net_exposure_ratio":                    round(self.net_exposure_ratio, 4),
            "fail_closed":                           self.fail_closed,
            "fail_closed_reasons":                   list(self.fail_closed_reasons),
            "evaluations":                           [e.to_dict() for e in self.evaluations],
            "accepted_candidates":                   [e.to_dict() for e in self.accepted_candidates],
            "rejected_candidates":                   [e.to_dict() for e in self.rejected_candidates],
            "payload_preview":                       [p.to_dict() for p in self.payload_previews],
            "existing_symbols":                      list(self.existing_symbols),
            "next_required_task":                    self.next_required_task,
            "action_type":                           self.action_type,
            "no_orders_sent":                        self.no_orders_sent,
            "no_position_modified":                  self.no_position_modified,
            "order_endpoint_called":                 self.order_endpoint_called,
            "secret_value_observed":                 self.secret_value_observed,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _norm_side(side: str) -> str:
    s = (side or "").strip().lower()
    if s in ("long", "buy"):
        return "long"
    if s in ("short", "sell"):
        return "short"
    return ""


def _order_side_for_entry(direction: str) -> str:
    """Bybit-style order side string for a new entry in the given direction."""
    return "Buy" if direction == "long" else "Sell"


def _is_pos_float(v: float) -> bool:
    return isinstance(v, (int, float)) and math.isfinite(v) and v > 0


def _stop_distance_valid(side: str, entry: float, stop: float) -> bool:
    """For long: stop < entry; for short: stop > entry; both > 0."""
    if not (_is_pos_float(entry) and _is_pos_float(stop)):
        return False
    if side == "long":
        return stop < entry
    if side == "short":
        return stop > entry
    return False


# ---------------------------------------------------------------------------
# Top-level fail-closed gate
# ---------------------------------------------------------------------------

_REQUIRED_ENDPOINT_FAMILY = "bybit_demo"
_REQUIRED_ACCOUNT_MODE    = "demo"
_REQUIRED_PROOF_STRENGTH  = "STRONG"


def _evaluate_top_level_gates(
    recon:                ReconciliationResult,
    endpoint_family:      str,
    account_mode:         str,
) -> list[str]:
    """Return the list of reasons the top-level gate fails closed (empty = OK)."""
    reasons: list[str] = []

    if not recon.demo_runtime_verified:
        reasons.append(REJECT_RUNTIME_NOT_VERIFIED)
    if recon.proof_strength != _REQUIRED_PROOF_STRENGTH:
        reasons.append(REJECT_PROOF_NOT_STRONG)
    if endpoint_family != _REQUIRED_ENDPOINT_FAMILY:
        reasons.append("endpoint_family_not_bybit_demo")
    if account_mode and account_mode != _REQUIRED_ACCOUNT_MODE:
        reasons.append("account_mode_not_demo")
    if recon.position_details_source != "real_readonly":
        reasons.append(REJECT_SOURCE_NOT_REAL_READONLY)
    if not recon.new_entry_allowed:
        reasons.append(REJECT_RECONCILIATION_NOT_PASS)
    if recon.available_balance_usd <= 0:
        reasons.append(REJECT_AVAILABLE_BALANCE)
    if recon.open_positions_count >= MAX_OPEN_POSITIONS:
        reasons.append(REJECT_OPEN_POSITIONS_FULL)

    return reasons


# ---------------------------------------------------------------------------
# Per-candidate review
# ---------------------------------------------------------------------------

def _reject(
    cand:          NewEntryCandidate,
    reason:        str,
    detail:        dict[str, Any] | None = None,
) -> NewEntryEvaluation:
    return NewEntryEvaluation(
        symbol=cand.symbol,
        side=_norm_side(cand.side) or cand.side,
        accepted=False,
        reject_reason=reason,
        detail=detail or {},
        payload=None,
    )


def _evaluate_candidate(
    cand:                        NewEntryCandidate,
    recon:                       ReconciliationResult,
    instrument_rules:            dict[str, InstrumentRules],
    existing_symbols:            set[str],
    portfolio_risk_budget_usd:   float,
    remaining_risk_budget_usd:   float,
    running_long_count:          int,
    running_short_count:         int,
    running_open_count:          int,
    running_long_notional:       float,
    running_short_notional:      float,
    max_long_allowed_remaining:  int,
    max_short_allowed_remaining: int,
) -> NewEntryEvaluation:
    """Apply per-candidate gates; return evaluation (accepted or rejected)."""
    side = _norm_side(cand.side)
    if side not in ("long", "short"):
        return _reject(cand, REJECT_INVALID_SIDE, {"raw_side": cand.side})

    # --- side capacity ----------------------------------------------------
    if side == "short" and max_short_allowed_remaining <= 0:
        return _reject(
            cand, REJECT_SHORT_CAPACITY_FULL,
            {"max_short_allowed_remaining": max_short_allowed_remaining,
             "current_short_count": recon.short_count,
             "max_short_positions": MAX_SHORT_POSITIONS},
        )
    if side == "long" and max_long_allowed_remaining <= 0:
        return _reject(
            cand, REJECT_LONG_CAPACITY_FULL,
            {"max_long_allowed_remaining": max_long_allowed_remaining,
             "current_long_count": recon.long_count,
             "max_long_positions": MAX_LONG_POSITIONS},
        )

    # --- open-slot capacity ----------------------------------------------
    if running_open_count >= MAX_OPEN_POSITIONS:
        return _reject(cand, REJECT_OPEN_POSITIONS_FULL,
                       {"running_open_count": running_open_count,
                        "max_open_positions": MAX_OPEN_POSITIONS})

    # --- duplicate symbol -------------------------------------------------
    if cand.symbol in existing_symbols:
        return _reject(cand, REJECT_DUPLICATE_SYMBOL,
                       {"existing_symbol": cand.symbol})

    # --- instrument rule --------------------------------------------------
    rules = instrument_rules.get(cand.symbol)
    if rules is None:
        return _reject(cand, REJECT_MISSING_INSTRUMENT_RULE,
                       {"symbol": cand.symbol})
    rules_ok, rules_err = rules.is_valid()
    if not rules_ok:
        return _reject(cand, REJECT_MISSING_RULE,
                       {"rules_error": rules_err})

    # --- prices -----------------------------------------------------------
    if not _is_pos_float(cand.entry_reference_price):
        return _reject(cand, REJECT_INVALID_ENTRY_PRICE,
                       {"entry_reference_price": cand.entry_reference_price})
    if not _is_pos_float(cand.stop_price):
        return _reject(cand, REJECT_INVALID_STOP_PRICE,
                       {"stop_price": cand.stop_price})
    if not _stop_distance_valid(side, cand.entry_reference_price, cand.stop_price):
        return _reject(cand, REJECT_INVALID_STOP_DISTANCE,
                       {"side": side, "entry": cand.entry_reference_price,
                        "stop": cand.stop_price})

    if not (math.isfinite(cand.requested_risk_usd) and cand.requested_risk_usd > 0):
        return _reject(cand, REJECT_REQUESTED_RISK_NON_POSITIVE,
                       {"requested_risk_usd": cand.requested_risk_usd})

    # --- per-trade risk cap ----------------------------------------------
    per_trade_cap = portfolio_risk_budget_usd * MAX_SINGLE_TRADE_RISK_SHARE
    allowed_risk  = min(cand.requested_risk_usd, per_trade_cap, remaining_risk_budget_usd)
    if allowed_risk <= 0:
        return _reject(cand, REJECT_REMAINING_BUDGET_INSUFFICIENT,
                       {"remaining_risk_budget_usd": remaining_risk_budget_usd,
                        "per_trade_cap_usd": per_trade_cap})

    # --- compute quantity from risk --------------------------------------
    rounded_entry = round_price_to_tick(cand.entry_reference_price, rules.tick_size)
    rounded_stop  = round_price_to_tick(cand.stop_price,            rules.tick_size)
    if rounded_entry <= 0 or rounded_stop <= 0:
        return _reject(cand, REJECT_INVALID_STOP_DISTANCE,
                       {"rounded_entry": rounded_entry,
                        "rounded_stop":  rounded_stop})

    stop_distance = abs(rounded_entry - rounded_stop)
    if stop_distance <= 0:
        return _reject(cand, REJECT_INVALID_STOP_DISTANCE,
                       {"stop_distance": stop_distance})

    raw_qty     = allowed_risk / stop_distance
    rounded_qty = round_qty_down(raw_qty, rules.qty_step)
    if rounded_qty <= 0:
        return _reject(cand, REJECT_ROUND_QTY_ZERO,
                       {"raw_qty": raw_qty, "qty_step": rules.qty_step,
                        "allowed_risk_usd": allowed_risk,
                        "stop_distance": stop_distance})

    if rounded_qty < rules.min_qty - 1e-12:
        return _reject(cand, REJECT_MIN_QTY_AFTER_ROUNDING,
                       {"rounded_qty": rounded_qty, "min_qty": rules.min_qty})

    notional_after = rounded_qty * rounded_entry
    if notional_after < rules.min_notional - 1e-6:
        return _reject(cand, REJECT_MIN_NOTIONAL_AFTER_ROUNDING,
                       {"notional_after": notional_after,
                        "min_notional":   rules.min_notional})

    stop_risk_after = stop_distance * rounded_qty
    if stop_risk_after <= 0:
        return _reject(cand, REJECT_STOP_RISK_NON_POSITIVE,
                       {"stop_risk_after": stop_risk_after})

    if stop_risk_after > remaining_risk_budget_usd + 1e-6:
        return _reject(cand, REJECT_REMAINING_BUDGET_INSUFFICIENT,
                       {"stop_risk_after": stop_risk_after,
                        "remaining_risk_budget_usd": remaining_risk_budget_usd})

    if stop_risk_after > per_trade_cap + 1e-6:
        return _reject(cand, REJECT_PER_TRADE_RISK_CAP,
                       {"stop_risk_after": stop_risk_after,
                        "per_trade_cap_usd": per_trade_cap})

    # --- single-position notional cap ------------------------------------
    safe_equity = recon.equity_usd if recon.equity_usd > 0 else 1.0
    max_single_notional = safe_equity * MAX_SINGLE_POSITION_NOTIONAL_PCT
    if notional_after > max_single_notional + 1e-6:
        return _reject(cand, REJECT_MAX_SINGLE_NOTIONAL,
                       {"notional_after": notional_after,
                        "max_single_notional_usd": max_single_notional})

    # --- projected exposure ratios ---------------------------------------
    new_long_notional  = running_long_notional
    new_short_notional = running_short_notional
    if side == "long":
        new_long_notional += notional_after
    else:
        new_short_notional += notional_after

    projected_gross = (new_long_notional + new_short_notional) / safe_equity
    projected_net   = abs(new_long_notional - new_short_notional) / safe_equity

    if projected_gross > MAX_GROSS_EXPOSURE_RATIO + 1e-9:
        return _reject(cand, REJECT_PROJECTED_GROSS_EXPOSURE,
                       {"projected_gross_exposure_ratio": projected_gross,
                        "max_gross_exposure_ratio": MAX_GROSS_EXPOSURE_RATIO})
    if projected_net > MAX_NET_EXPOSURE_RATIO + 1e-9:
        return _reject(cand, REJECT_PROJECTED_NET_EXPOSURE,
                       {"projected_net_exposure_ratio": projected_net,
                        "max_net_exposure_ratio": MAX_NET_EXPOSURE_RATIO})

    # --- accepted --------------------------------------------------------
    projected_open  = running_open_count + 1
    projected_long  = running_long_count  + (1 if side == "long"  else 0)
    projected_short = running_short_count + (1 if side == "short" else 0)
    remaining_after = remaining_risk_budget_usd - stop_risk_after

    payload = NewEntryPayloadPreview(
        symbol=cand.symbol,
        side=_order_side_for_entry(side),
        order_type=cand.order_type or "Market",
        qty=rounded_qty,
        reduce_only=False,
        preview_only=True,
        entry_reference_price=cand.entry_reference_price,
        rounded_entry_price=rounded_entry,
        stop_price=cand.stop_price,
        rounded_stop_price=rounded_stop,
        estimated_notional_usd=notional_after,
        estimated_stop_risk_usd=stop_risk_after,
        portfolio_risk_budget_usd=portfolio_risk_budget_usd,
        remaining_risk_budget_before=remaining_risk_budget_usd,
        remaining_risk_budget_after=remaining_after,
        projected_open_positions_count=projected_open,
        projected_long_count=projected_long,
        projected_short_count=projected_short,
        projected_gross_exposure_ratio=projected_gross,
        projected_net_exposure_ratio=projected_net,
        confirmation_required=True,
        order_sent=False,
        order_endpoint_called=False,
    )
    return NewEntryEvaluation(
        symbol=cand.symbol,
        side=side,
        accepted=True,
        reject_reason="",
        detail={
            "allowed_risk_usd": allowed_risk,
            "per_trade_cap_usd": per_trade_cap,
            "stop_distance": stop_distance,
            "rounded_qty": rounded_qty,
            "notional_after": notional_after,
        },
        payload=payload,
    )


# ---------------------------------------------------------------------------
# Top-level entry point
# ---------------------------------------------------------------------------

def review_new_entry_candidates(
    reconciliation:    ReconciliationResult,
    candidates:        list[NewEntryCandidate],
    instrument_rules:  dict[str, InstrumentRules],
    endpoint_family:   str = _REQUIRED_ENDPOINT_FAMILY,
    account_mode:      str = _REQUIRED_ACCOUNT_MODE,
    available_balance_usd_source: str = "account.totalAvailableBalance",
) -> NewEntryReviewResult:
    """
    Review a list of new-entry candidates against the reconciliation snapshot.

    Pure computation — no network calls, no orders sent, no secrets, no
    positions modified.  All safety invariants are structural.

    Args:
        reconciliation:   PASS-state reconciliation snapshot (required: real_readonly).
        candidates:       List of NewEntryCandidate proposals to review.
        instrument_rules: Exchange instrument specs keyed by symbol.
        endpoint_family:  Endpoint family label (must be "bybit_demo").
        account_mode:     Account mode label (must be "demo").
        available_balance_usd_source: Provenance label for available_balance.

    Returns:
        NewEntryReviewResult with per-candidate evaluations, payload previews,
        projected portfolio state, and safety invariants.
    """
    existing_symbols = {p.symbol for p in reconciliation.positions}

    # ── top-level gate ────────────────────────────────────────────────────
    fail_reasons = _evaluate_top_level_gates(
        reconciliation, endpoint_family, account_mode,
    )
    fail_closed = bool(fail_reasons)

    portfolio_risk_budget_usd = reconciliation.portfolio_risk_budget_usd
    remaining_risk_budget_usd = reconciliation.remaining_risk_budget_usd

    # Running portfolio state for projections (mutated when each candidate accepts)
    running_long_count       = reconciliation.long_count
    running_short_count      = reconciliation.short_count
    running_open_count       = reconciliation.open_positions_count

    # Existing long/short notional (per side) — derive from positions list
    running_long_notional = sum(
        abs(p.quantity * p.entry_price)
        for p in reconciliation.positions
        if p.side.lower() == "long"
    )
    running_short_notional = sum(
        abs(p.quantity * p.entry_price)
        for p in reconciliation.positions
        if p.side.lower() == "short"
    )

    max_long_allowed_remaining  = reconciliation.max_long_allowed_remaining
    max_short_allowed_remaining = reconciliation.max_short_allowed_remaining

    evaluations: list[NewEntryEvaluation] = []

    if fail_closed:
        # Top-level fail — reject everything with the leading reason
        leading_reason = fail_reasons[0]
        for cand in candidates:
            evaluations.append(_reject(
                cand, leading_reason,
                {"fail_closed_reasons": list(fail_reasons)},
            ))
    else:
        for cand in candidates:
            ev = _evaluate_candidate(
                cand=cand,
                recon=reconciliation,
                instrument_rules=instrument_rules,
                existing_symbols=existing_symbols,
                portfolio_risk_budget_usd=portfolio_risk_budget_usd,
                remaining_risk_budget_usd=remaining_risk_budget_usd,
                running_long_count=running_long_count,
                running_short_count=running_short_count,
                running_open_count=running_open_count,
                running_long_notional=running_long_notional,
                running_short_notional=running_short_notional,
                max_long_allowed_remaining=max_long_allowed_remaining,
                max_short_allowed_remaining=max_short_allowed_remaining,
            )
            evaluations.append(ev)

            if ev.accepted and ev.payload is not None:
                # Consume capacity / budget so subsequent candidates see the
                # projected portfolio state.
                running_open_count   += 1
                if ev.side == "long":
                    running_long_count       += 1
                    running_long_notional    += ev.payload.estimated_notional_usd
                    max_long_allowed_remaining = max(0, max_long_allowed_remaining - 1)
                else:
                    running_short_count      += 1
                    running_short_notional   += ev.payload.estimated_notional_usd
                    max_short_allowed_remaining = max(0, max_short_allowed_remaining - 1)
                remaining_risk_budget_usd = max(
                    0.0, remaining_risk_budget_usd - ev.payload.estimated_stop_risk_usd,
                )
                existing_symbols.add(cand.symbol)

    accepted = [e for e in evaluations if e.accepted]
    rejected = [e for e in evaluations if not e.accepted]
    payloads = [e.payload for e in accepted if e.payload is not None]

    next_required_task = (
        "TASK-014L Demo New-entry Sender Gate (manual approval required)"
        if accepted and not fail_closed
        else "no_payload_to_send"
    )

    return NewEntryReviewResult(
        mode=reconciliation.mode,
        demo_runtime_verified=reconciliation.demo_runtime_verified,
        proof_strength=reconciliation.proof_strength,
        endpoint_family=endpoint_family,
        account_mode=account_mode,
        position_details_source=reconciliation.position_details_source,
        new_entry_allowed_from_reconciliation=reconciliation.new_entry_allowed,
        available_balance_usd=reconciliation.available_balance_usd,
        available_balance_usd_source=available_balance_usd_source,
        equity_usd=reconciliation.equity_usd,
        portfolio_risk_budget_usd=reconciliation.portfolio_risk_budget_usd,
        remaining_risk_budget_usd=reconciliation.remaining_risk_budget_usd,
        open_positions_count=reconciliation.open_positions_count,
        long_count=reconciliation.long_count,
        short_count=reconciliation.short_count,
        max_long_allowed_remaining=reconciliation.max_long_allowed_remaining,
        max_short_allowed_remaining=reconciliation.max_short_allowed_remaining,
        gross_exposure_ratio=reconciliation.gross_exposure_ratio,
        net_exposure_ratio=reconciliation.net_exposure_ratio,
        fail_closed=fail_closed,
        fail_closed_reasons=list(fail_reasons),
        evaluations=evaluations,
        accepted_candidates=accepted,
        rejected_candidates=rejected,
        payload_previews=payloads,
        existing_symbols=sorted(reconciliation.positions and
                                [p.symbol for p in reconciliation.positions] or []),
        next_required_task=next_required_task,
    )
