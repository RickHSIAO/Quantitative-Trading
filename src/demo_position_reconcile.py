"""
src/demo_position_reconcile.py
TASK-014E: Demo position reconciliation and legacy position cleanup plan.

Reads DemoOpenPosition list and wallet state; computes portfolio metrics,
detects rule violations, and produces a human-readable cleanup plan.

SAFETY INVARIANTS (all enforced structurally and verified by tests):
  no_orders_sent = True         (always)
  no_position_modified = True   (always)
  order_endpoint_called = False (always)
  secret_value_observed = False (always)
  action_type = "MANUAL_REVIEW_ONLY" (always)

No network calls. No exchange imports. No order endpoints.
Does not modify main.py, src/risk.py, or exchange executor classes.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import (
    KELLY_MULTIPLIER,
    MAX_GROSS_EXPOSURE_RATIO,
    MAX_LONG_POSITIONS,
    MAX_NET_EXPOSURE_RATIO,
    MAX_OPEN_POSITIONS,
    MAX_SHORT_POSITIONS,
    MAX_TOTAL_STOP_RISK_PCT_EQUITY,
    DemoOpenPosition,
)


# Threshold: available_balance_usd must exceed this to allow new entries
_MIN_AVAILABLE_BALANCE_USD: float = 0.0


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class ViolationRecord:
    code:    str
    detail:  str
    is_hard: bool = True   # hard violations block new entries


@dataclass
class PositionDetail:
    symbol:                  str
    side:                    str
    quantity:                float
    entry_price:             float
    stop_price:              float    # 0.0 when stop is missing
    notional_usd:            float    # |qty * entry_price|
    stop_risk_usd:           float    # conservative: full notional when missing stop
    missing_stop:            bool
    missing_instrument_rule: bool


@dataclass
class ReconciliationResult:
    # Context
    equity_usd:              float
    available_balance_usd:   float
    full_kelly_fraction:     float
    demo_runtime_verified:   bool
    proof_strength:          str
    mode:                    str      # "fixture" or "real_readonly_snapshot"

    # Portfolio metrics
    open_positions_count:          int
    long_count:                    int
    short_count:                   int
    gross_notional_usd:            float
    net_notional_usd:              float
    gross_exposure_ratio:          float
    net_exposure_ratio:            float
    existing_stop_risk_usd:        float
    portfolio_risk_budget_usd:     float
    remaining_risk_budget_usd:     float
    current_slot_usage:            int
    available_slots:               int
    max_long_allowed_remaining:    int
    max_short_allowed_remaining:   int

    # Per-position breakdown
    positions:               list[PositionDetail]

    # Violations and cleanup plan
    violations:              list[ViolationRecord]
    new_entry_allowed:       bool
    blocked_reasons:         list[str]
    suggested_actions:       list[str]
    cannot_proceed_to_order_smoke: bool

    # Safety invariants (always these values)
    action_type:             str  = "MANUAL_REVIEW_ONLY"
    no_orders_sent:          bool = True
    no_position_modified:    bool = True
    order_endpoint_called:   bool = False
    secret_value_observed:   bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "mode":                        self.mode,
            "demo_runtime_verified":       self.demo_runtime_verified,
            "proof_strength":              self.proof_strength,
            "equity_usd":                  round(self.equity_usd, 2),
            "available_balance_usd":       round(self.available_balance_usd, 2),
            "full_kelly_fraction":         self.full_kelly_fraction,
            "open_positions_count":        self.open_positions_count,
            "long_count":                  self.long_count,
            "short_count":                 self.short_count,
            "gross_notional_usd":          round(self.gross_notional_usd, 2),
            "net_notional_usd":            round(self.net_notional_usd, 2),
            "gross_exposure_ratio":        round(self.gross_exposure_ratio, 4),
            "net_exposure_ratio":          round(self.net_exposure_ratio, 4),
            "existing_stop_risk_usd":      round(self.existing_stop_risk_usd, 2),
            "portfolio_risk_budget_usd":   round(self.portfolio_risk_budget_usd, 2),
            "remaining_risk_budget_usd":   round(self.remaining_risk_budget_usd, 2),
            "current_slot_usage":          self.current_slot_usage,
            "available_slots":             self.available_slots,
            "max_long_allowed_remaining":  self.max_long_allowed_remaining,
            "max_short_allowed_remaining": self.max_short_allowed_remaining,
            "violations": [
                {"code": v.code, "detail": v.detail, "is_hard": v.is_hard}
                for v in self.violations
            ],
            "new_entry_allowed":           self.new_entry_allowed,
            "blocked_reasons":             self.blocked_reasons,
            "suggested_actions":           self.suggested_actions,
            "cannot_proceed_to_order_smoke": self.cannot_proceed_to_order_smoke,
            "action_type":                 self.action_type,
            "no_orders_sent":              self.no_orders_sent,
            "no_position_modified":        self.no_position_modified,
            "order_endpoint_called":       self.order_endpoint_called,
            "secret_value_observed":       self.secret_value_observed,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _conservative_stop_risk(pos: DemoOpenPosition) -> float:
    """Stop risk in USD.  When stop is missing, count full notional (worst case)."""
    if pos.stop_price <= 0:
        return abs(pos.quantity * pos.entry_price)
    return abs(pos.entry_price - pos.stop_price) * pos.quantity


# ---------------------------------------------------------------------------
# Core reconciliation function
# ---------------------------------------------------------------------------

def reconcile(
    equity_usd:              float,
    available_balance_usd:   float,
    positions:               list[DemoOpenPosition],
    instrument_rules:        dict[str, InstrumentRules],
    full_kelly_fraction:     float = 0.60,
    demo_runtime_verified:   bool  = False,
    proof_strength:          str   = "",
    mode:                    str   = "fixture",
) -> ReconciliationResult:
    """
    Compute portfolio reconciliation metrics, detect rule violations, and
    produce a manual cleanup plan.

    Pure computation — no network calls, no order calls, no secrets,
    no position modifications.  All safety invariants are structural.

    Args:
        equity_usd:            Total account equity in USD.
        available_balance_usd: Free margin / available balance in USD.
        positions:             Current open positions.
        instrument_rules:      Exchange instrument specs keyed by symbol.
        full_kelly_fraction:   Strategy full Kelly fraction (e.g. 0.60).
        demo_runtime_verified: True if TASK-014D proof was STRONG.
        proof_strength:        "STRONG" / "WEAK" / "MISSING" from TASK-014D.
        mode:                  Report mode label ("fixture" or "real_readonly_snapshot").

    Returns:
        ReconciliationResult with all metrics, violations, and cleanup plan.
    """
    # ── Portfolio counts ───────────────────────────────────────────────────
    long_count  = sum(1 for p in positions if p.side.lower() == "long")
    short_count = sum(1 for p in positions if p.side.lower() == "short")
    n_open      = len(positions)

    # ── Notional ───────────────────────────────────────────────────────────
    long_notional  = sum(
        p.quantity * p.entry_price for p in positions if p.side.lower() == "long"
    )
    short_notional = sum(
        p.quantity * p.entry_price for p in positions if p.side.lower() == "short"
    )
    gross_notional = long_notional + short_notional
    net_notional   = long_notional - short_notional  # negative = net short

    safe_equity          = equity_usd if equity_usd > 0 else 1.0
    gross_exposure_ratio = gross_notional / safe_equity
    net_exposure_ratio   = abs(net_notional) / safe_equity

    # ── Risk budget ────────────────────────────────────────────────────────
    existing_stop_risk = sum(_conservative_stop_risk(p) for p in positions)

    raw_budget               = equity_usd * full_kelly_fraction * KELLY_MULTIPLIER
    cap_budget               = equity_usd * MAX_TOTAL_STOP_RISK_PCT_EQUITY
    portfolio_risk_budget    = min(raw_budget, cap_budget)
    remaining_risk_budget    = max(0.0, portfolio_risk_budget - existing_stop_risk)

    # ── Slot counts ────────────────────────────────────────────────────────
    available_slots          = max(0, MAX_OPEN_POSITIONS - n_open)
    max_long_remaining       = max(0, MAX_LONG_POSITIONS  - long_count)
    max_short_remaining      = max(0, MAX_SHORT_POSITIONS - short_count)

    # ── Per-position breakdown ─────────────────────────────────────────────
    pos_details: list[PositionDetail] = []
    for p in positions:
        missing_stop = (p.stop_price <= 0)
        missing_rule = (p.symbol not in instrument_rules)
        pos_details.append(PositionDetail(
            symbol=p.symbol,
            side=p.side,
            quantity=p.quantity,
            entry_price=p.entry_price,
            stop_price=p.stop_price,
            notional_usd=abs(p.quantity * p.entry_price),
            stop_risk_usd=_conservative_stop_risk(p),
            missing_stop=missing_stop,
            missing_instrument_rule=missing_rule,
        ))

    # ── Violation detection ────────────────────────────────────────────────
    violations: list[ViolationRecord] = []

    if n_open > MAX_OPEN_POSITIONS:
        violations.append(ViolationRecord(
            code="too_many_open_positions",
            detail=f"open_positions_count={n_open} > MAX={MAX_OPEN_POSITIONS}",
        ))
    if long_count > MAX_LONG_POSITIONS:
        violations.append(ViolationRecord(
            code="long_count_exceeded",
            detail=f"long_count={long_count} > MAX_LONG={MAX_LONG_POSITIONS}",
        ))
    if short_count > MAX_SHORT_POSITIONS:
        violations.append(ViolationRecord(
            code="short_count_exceeded",
            detail=f"short_count={short_count} > MAX_SHORT={MAX_SHORT_POSITIONS}",
        ))
    if gross_exposure_ratio > MAX_GROSS_EXPOSURE_RATIO:
        violations.append(ViolationRecord(
            code="gross_exposure_exceeded",
            detail=(
                f"gross_exposure_ratio={gross_exposure_ratio:.4f} "
                f"> MAX={MAX_GROSS_EXPOSURE_RATIO}"
            ),
        ))
    if net_exposure_ratio > MAX_NET_EXPOSURE_RATIO:
        violations.append(ViolationRecord(
            code="net_exposure_exceeded",
            detail=(
                f"net_exposure_ratio={net_exposure_ratio:.4f} "
                f"> MAX={MAX_NET_EXPOSURE_RATIO}"
            ),
        ))
    if available_balance_usd <= _MIN_AVAILABLE_BALANCE_USD:
        violations.append(ViolationRecord(
            code="available_balance_zero_or_negative",
            detail=f"available_balance_usd={available_balance_usd:.2f} <= 0",
        ))
    for pd in pos_details:
        if pd.missing_stop:
            violations.append(ViolationRecord(
                code="missing_stop_price",
                detail=f"symbol={pd.symbol} has no valid stop price (stop_price <= 0)",
            ))
        if pd.missing_instrument_rule:
            violations.append(ViolationRecord(
                code="missing_instrument_rule",
                detail=f"symbol={pd.symbol} not found in instrument_rules",
            ))
    if existing_stop_risk > portfolio_risk_budget:
        violations.append(ViolationRecord(
            code="stop_risk_exceeds_budget",
            detail=(
                f"existing_stop_risk_usd={existing_stop_risk:.2f} "
                f"> portfolio_risk_budget_usd={portfolio_risk_budget:.2f}"
            ),
        ))

    # ── Cleanup plan ───────────────────────────────────────────────────────
    hard_violations   = [v for v in violations if v.is_hard]
    new_entry_allowed = len(hard_violations) == 0
    blocked_reasons   = [v.code for v in hard_violations]

    suggested_actions: list[str] = []
    if hard_violations:
        suggested_actions.append("pause_new_entries")
    if short_count > MAX_SHORT_POSITIONS:
        suggested_actions.append("review_legacy_short_positions")
        suggested_actions.append(
            f"reduce_short_count_to_max_{MAX_SHORT_POSITIONS}_manually_"
            "or_via_future_confirmed_close_only_task"
        )
    if long_count > MAX_LONG_POSITIONS:
        suggested_actions.append(
            f"reduce_long_count_to_max_{MAX_LONG_POSITIONS}_manually"
        )
    if available_balance_usd <= 0:
        suggested_actions.append(
            "restore_available_balance_before_enabling_new_entries"
        )
    if any(pd.missing_stop for pd in pos_details):
        suggested_actions.append("add_stop_loss_to_all_open_positions")
    if existing_stop_risk > portfolio_risk_budget:
        suggested_actions.append(
            "reduce_position_sizes_to_bring_stop_risk_within_budget"
        )

    return ReconciliationResult(
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        full_kelly_fraction=full_kelly_fraction,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        mode=mode,
        open_positions_count=n_open,
        long_count=long_count,
        short_count=short_count,
        gross_notional_usd=gross_notional,
        net_notional_usd=net_notional,
        gross_exposure_ratio=gross_exposure_ratio,
        net_exposure_ratio=net_exposure_ratio,
        existing_stop_risk_usd=existing_stop_risk,
        portfolio_risk_budget_usd=portfolio_risk_budget,
        remaining_risk_budget_usd=remaining_risk_budget,
        current_slot_usage=n_open,
        available_slots=available_slots,
        max_long_allowed_remaining=max_long_remaining,
        max_short_allowed_remaining=max_short_remaining,
        positions=pos_details,
        violations=violations,
        new_entry_allowed=new_entry_allowed,
        blocked_reasons=blocked_reasons,
        suggested_actions=suggested_actions,
        cannot_proceed_to_order_smoke=not new_entry_allowed,
    )
