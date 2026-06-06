"""
apps/demo_trading/kelly_sizer.py
TASK-014: Portfolio-level 0.4 fractional Kelly position sizer for Bybit Demo Trading.

KEY DESIGN PRINCIPLE:
  KELLY_MULTIPLIER applies to the WHOLE portfolio, not per trade.

  total_risk_budget   = equity × 0.40
  existing_stop_risk  = Σ (open_pos_notional × stop_distance_pct)
  remaining_budget    = total_risk_budget − existing_stop_risk
  per_slot_risk       = remaining_budget / available_slots
  position_notional   = per_slot_risk / stop_distance_pct

  Hard caps applied after sizing:
    - Single position ≤ equity × MAX_SINGLE_POSITION_PCT
    - Gross exposure (all notionals) ≤ equity × MAX_GROSS_EXPOSURE_RATIO
    - Net exposure (long − short) ≤ equity × MAX_NET_EXPOSURE_RATIO
    - position_notional ≥ MIN_POSITION_NOTIONAL_USD

SAFETY:
  - This module is pure computation — no network, no order calls.
  - Demo environment guard is checked via DemoGuard.verify().
  - Nothing here imports BybitExecutor or calls any broker API.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

from apps.demo_trading import config as cfg


# ---------------------------------------------------------------------------
# Data structures
# ---------------------------------------------------------------------------

@dataclass
class OpenPosition:
    """Represents a single open position in the demo portfolio."""
    symbol:           str
    side:             str          # "long" or "short"
    notional_usd:     float        # positive for long, negative for short
    entry_price:      float
    stop_loss_price:  float

    @property
    def stop_distance_pct(self) -> float:
        """Fraction of entry price at risk per dollar of notional."""
        if self.entry_price <= 0:
            return 0.0
        return abs(self.entry_price - self.stop_loss_price) / self.entry_price

    @property
    def stop_risk_usd(self) -> float:
        """Dollar amount at risk if stop is hit: abs(notional) × stop_distance_pct."""
        return abs(self.notional_usd) * self.stop_distance_pct


@dataclass
class SignalCandidate:
    """A new signal candidate to be sized."""
    symbol:          str
    side:            str           # "long" or "short"
    entry_price:     float
    stop_loss_price: float
    score:           float = 0.0   # strategy signal score (higher = stronger signal)


@dataclass
class SizingProposal:
    """Result of sizing a single signal candidate."""
    symbol:           str
    side:             str
    entry_price:      float
    stop_loss_price:  float
    stop_distance_pct: float
    proposed_notional_usd: float   # 0 if rejected
    accepted:         bool
    reject_reason:    str          # empty string if accepted
    detail:           dict[str, Any] = field(default_factory=dict)


@dataclass
class PortfolioSizingResult:
    """Full dry-run sizing output for the entire candidate batch."""
    # Portfolio state inputs
    equity_usd:               float
    available_balance_usd:    float
    n_open:                   int
    n_long_open:              int
    n_short_open:             int

    # Risk budget
    total_risk_budget_usd:    float    # equity × KELLY_MULTIPLIER
    existing_stop_risk_usd:   float    # Σ open stop risks
    remaining_risk_budget_usd: float   # total − existing
    available_slots:          int

    # Exposure before new positions
    current_gross_notional:   float
    current_net_notional:     float

    # Per-candidate results
    proposals:                list[SizingProposal]

    # Post-proposal exposure
    proposed_gross_notional:  float
    proposed_net_notional:    float
    proposed_gross_ratio:     float   # proposed_gross / equity
    proposed_net_ratio:       float   # abs(proposed_net) / equity

    # Summary
    n_accepted:               int
    n_rejected:               int
    reject_summary:           dict[str, int]   # reason → count
    demo_guard_ok:            bool
    demo_guard_detail:        str


# ---------------------------------------------------------------------------
# Demo environment guard
# ---------------------------------------------------------------------------

class DemoGuard:
    """
    Verifies that the execution context is definitely a Demo account.
    Fail-closed: if we cannot confirm DEMO, reject all sizing.
    """

    @staticmethod
    def verify(demo_flag: bool, testnet_flag: bool) -> tuple[bool, str]:
        """
        Returns (ok, detail).
        ok=True only when demo_flag is True and testnet_flag is False.
        """
        if not demo_flag:
            return False, (
                "BYBIT_DEMO is not True — refusing to size positions "
                "outside demo environment"
            )
        if testnet_flag:
            return False, (
                "BYBIT_TESTNET is True — testnet and demo are different "
                "environments; this sizer only supports demo=True, testnet=False"
            )
        if demo_flag is not True:
            return False, "demo_flag must be exactly True (bool), not truthy"
        return True, f"demo_flag={demo_flag}, testnet_flag={testnet_flag} → DEMO OK"


# ---------------------------------------------------------------------------
# Risk budget calculator
# ---------------------------------------------------------------------------

def compute_portfolio_risk_budget(
    equity_usd: float,
    open_positions: list[OpenPosition],
) -> dict[str, float]:
    """
    Compute the portfolio-level Kelly risk budget and how much remains.

    Returns dict with:
      total_risk_budget_usd, existing_stop_risk_usd,
      remaining_risk_budget_usd, per_slot_risk_usd (if slots > 0)
    """
    if equity_usd <= 0:
        return {
            "total_risk_budget_usd":     0.0,
            "existing_stop_risk_usd":    0.0,
            "remaining_risk_budget_usd": 0.0,
            "per_slot_risk_usd":         0.0,
        }

    total_budget  = equity_usd * cfg.KELLY_MULTIPLIER
    existing_risk = sum(p.stop_risk_usd for p in open_positions)
    remaining     = max(0.0, total_budget - existing_risk)

    n_open = len(open_positions)
    available_slots = max(0, cfg.MAX_OPEN_POSITIONS - n_open)
    per_slot = (remaining / available_slots) if available_slots > 0 else 0.0

    return {
        "total_risk_budget_usd":     total_budget,
        "existing_stop_risk_usd":    existing_risk,
        "remaining_risk_budget_usd": remaining,
        "per_slot_risk_usd":         per_slot,
    }


# ---------------------------------------------------------------------------
# Exposure calculator
# ---------------------------------------------------------------------------

def compute_exposure(open_positions: list[OpenPosition],
                     proposals: list[SizingProposal] | None = None,
                     equity_usd: float = 1.0) -> dict[str, float]:
    """
    Compute gross/net notional from open positions plus optionally accepted proposals.
    Returns exposure ratios (notional / equity).
    """
    positions = list(open_positions)
    extra: list[tuple[float, str]] = []  # (notional, side)
    if proposals:
        for p in proposals:
            if p.accepted and p.proposed_notional_usd > 0:
                notional = p.proposed_notional_usd * (1 if p.side == "long" else -1)
                extra.append((notional, p.side))

    all_notionals = [pos.notional_usd for pos in positions] + [n for n, _ in extra]
    gross  = sum(abs(n) for n in all_notionals)
    net    = sum(all_notionals)
    n_long  = sum(1 for pos in positions if pos.side == "long") + sum(1 for _, s in extra if s == "long")
    n_short = sum(1 for pos in positions if pos.side == "short") + sum(1 for _, s in extra if s == "short")

    return {
        "gross_notional": gross,
        "net_notional":   net,
        "n_long":         n_long,
        "n_short":        n_short,
        "gross_ratio":    gross / equity_usd if equity_usd > 0 else 0.0,
        "net_ratio":      abs(net) / equity_usd if equity_usd > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Core sizing function
# ---------------------------------------------------------------------------

def size_position(
    candidate:              SignalCandidate,
    equity_usd:             float,
    available_balance_usd:  float,
    per_slot_risk_usd:      float,
    open_positions:         list[OpenPosition],
    accepted_so_far:        list[SizingProposal],
) -> SizingProposal:
    """
    Compute the notional for a single candidate under portfolio-level Kelly constraints.
    Returns a SizingProposal with accepted=True/False and the reason if rejected.
    """
    sym  = candidate.symbol
    side = candidate.side

    # Guard: stop distance validity
    if candidate.entry_price <= 0:
        return _reject(candidate, cfg.REJECT_INVALID_STOP_DISTANCE,
                       "entry_price <= 0")

    raw_stop_dist = abs(candidate.entry_price - candidate.stop_loss_price) / candidate.entry_price
    if raw_stop_dist < cfg.MIN_STOP_DISTANCE_PCT:
        return _reject(candidate, cfg.REJECT_INVALID_STOP_DISTANCE,
                       f"stop_distance_pct={raw_stop_dist:.4%} < min {cfg.MIN_STOP_DISTANCE_PCT:.4%}")
    if raw_stop_dist > cfg.MAX_STOP_DISTANCE_PCT:
        return _reject(candidate, cfg.REJECT_INVALID_STOP_DISTANCE,
                       f"stop_distance_pct={raw_stop_dist:.4%} > max {cfg.MAX_STOP_DISTANCE_PCT:.4%}")

    # Guard: risk budget must be positive
    if per_slot_risk_usd < cfg.MIN_RISK_PER_SLOT_USD:
        return _reject(candidate, cfg.REJECT_INSUFFICIENT_RISK_BUDGET,
                       f"per_slot_risk_usd={per_slot_risk_usd:.2f} < min {cfg.MIN_RISK_PER_SLOT_USD}")

    # Compute raw notional from risk budget
    proposed_notional = per_slot_risk_usd / raw_stop_dist

    # Cap 1: single position maximum
    single_cap = equity_usd * cfg.MAX_SINGLE_POSITION_PCT
    if proposed_notional > single_cap:
        proposed_notional = single_cap

    # Count current sides (open + accepted so far)
    n_long  = sum(1 for p in open_positions if p.side == "long")  + \
              sum(1 for p in accepted_so_far if p.side == "long"  and p.accepted)
    n_short = sum(1 for p in open_positions if p.side == "short") + \
              sum(1 for p in accepted_so_far if p.side == "short" and p.accepted)
    n_open  = len(open_positions) + sum(1 for p in accepted_so_far if p.accepted)

    # Guard: total open positions
    if n_open >= cfg.MAX_OPEN_POSITIONS:
        return _reject(candidate, cfg.REJECT_MAX_OPEN_POSITIONS,
                       f"n_open={n_open} >= {cfg.MAX_OPEN_POSITIONS}")

    # Guard: long/short side caps
    if side == "long" and n_long >= cfg.MAX_LONG_POSITIONS:
        return _reject(candidate, cfg.REJECT_MAX_LONG_POSITIONS,
                       f"n_long={n_long} >= {cfg.MAX_LONG_POSITIONS}")
    if side == "short" and n_short >= cfg.MAX_SHORT_POSITIONS:
        return _reject(candidate, cfg.REJECT_MAX_SHORT_POSITIONS,
                       f"n_short={n_short} >= {cfg.MAX_SHORT_POSITIONS}")

    # Cap 2: gross exposure
    all_pos   = open_positions[:]
    accepted_pos = [
        OpenPosition(p.symbol, p.side,
                     p.proposed_notional_usd * (1 if p.side == "long" else -1),
                     p.entry_price, p.stop_loss_price)
        for p in accepted_so_far if p.accepted
    ]
    current_exp = compute_exposure(all_pos + accepted_pos, equity_usd=equity_usd)
    gross_cap   = equity_usd * cfg.MAX_GROSS_EXPOSURE_RATIO
    gross_headroom = max(0.0, gross_cap - current_exp["gross_notional"])
    if proposed_notional > gross_headroom:
        if gross_headroom < cfg.MIN_POSITION_NOTIONAL_USD:
            return _reject(candidate, cfg.REJECT_MAX_GROSS_EXPOSURE,
                           f"gross_headroom={gross_headroom:.2f} < min {cfg.MIN_POSITION_NOTIONAL_USD}")
        proposed_notional = gross_headroom

    # Cap 3: net exposure
    net_sign      = 1.0 if side == "long" else -1.0
    current_net   = current_exp["net_notional"]
    net_cap_abs   = equity_usd * cfg.MAX_NET_EXPOSURE_RATIO
    new_net       = current_net + net_sign * proposed_notional
    if abs(new_net) > net_cap_abs:
        # Shrink so that abs(new_net) = net_cap_abs
        headroom = net_cap_abs - abs(current_net)
        if net_sign * current_net < 0:
            # Adding this side reduces abs(net)
            headroom = net_cap_abs + abs(current_net)
        clipped = max(0.0, headroom)
        if clipped < cfg.MIN_POSITION_NOTIONAL_USD:
            return _reject(candidate, cfg.REJECT_MAX_NET_EXPOSURE,
                           f"net_headroom={clipped:.2f} < min {cfg.MIN_POSITION_NOTIONAL_USD}")
        proposed_notional = min(proposed_notional, clipped)

    # Cap 4: available balance
    if proposed_notional > available_balance_usd:
        if available_balance_usd < cfg.MIN_POSITION_NOTIONAL_USD:
            return _reject(candidate, cfg.REJECT_INSUFFICIENT_AVAILABLE_BAL,
                           f"available={available_balance_usd:.2f} < min {cfg.MIN_POSITION_NOTIONAL_USD}")
        proposed_notional = available_balance_usd

    # Floor: minimum notional
    if proposed_notional < cfg.MIN_POSITION_NOTIONAL_USD:
        return _reject(candidate, cfg.REJECT_POSITION_TOO_SMALL,
                       f"notional={proposed_notional:.2f} < min {cfg.MIN_POSITION_NOTIONAL_USD}")

    return SizingProposal(
        symbol=sym,
        side=side,
        entry_price=candidate.entry_price,
        stop_loss_price=candidate.stop_loss_price,
        stop_distance_pct=raw_stop_dist,
        proposed_notional_usd=round(proposed_notional, 4),
        accepted=True,
        reject_reason="",
        detail={
            "per_slot_risk_usd":     round(per_slot_risk_usd, 4),
            "risk_used_usd":         round(proposed_notional * raw_stop_dist, 4),
            "single_cap_usd":        round(single_cap, 4),
            "gross_headroom_usd":    round(gross_headroom, 4),
        },
    )


# ---------------------------------------------------------------------------
# Batch sizer (main entry point)
# ---------------------------------------------------------------------------

def compute_portfolio_sizing(
    equity_usd:             float,
    available_balance_usd:  float,
    open_positions:         list[OpenPosition],
    candidates:             list[SignalCandidate],
    demo_flag:              bool = True,
    testnet_flag:           bool = False,
) -> PortfolioSizingResult:
    """
    Compute portfolio-level Kelly sizing for a batch of signal candidates.

    This is the main entry point. It:
      1. Verifies demo environment guard.
      2. Computes remaining risk budget.
      3. Sizes each candidate in score-descending order.
      4. Returns a complete PortfolioSizingResult (dry-run safe).

    IMPORTANT: This function NEVER places orders. It only computes sizing.
    The caller is responsible for order submission after reviewing the result.
    """
    # 1. Demo guard
    guard_ok, guard_detail = DemoGuard.verify(demo_flag, testnet_flag)

    # 2. Risk budget
    budget    = compute_portfolio_risk_budget(equity_usd, open_positions)
    n_open    = len(open_positions)
    n_long    = sum(1 for p in open_positions if p.side == "long")
    n_short   = sum(1 for p in open_positions if p.side == "short")
    avail_slots = max(0, cfg.MAX_OPEN_POSITIONS - n_open)

    per_slot_risk = budget["per_slot_risk_usd"]

    # 3. Current exposure
    cur_exp = compute_exposure(open_positions, equity_usd=equity_usd)

    # 4. Sort candidates by score descending (best signal first)
    sorted_candidates = sorted(candidates, key=lambda c: c.score, reverse=True)

    proposals:   list[SizingProposal] = []
    accepted_so_far: list[SizingProposal] = []

    for candidate in sorted_candidates:
        if not guard_ok:
            proposals.append(_reject(candidate, cfg.REJECT_DEMO_GUARD_FAILED, guard_detail))
            continue

        proposal = size_position(
            candidate=candidate,
            equity_usd=equity_usd,
            available_balance_usd=available_balance_usd,
            per_slot_risk_usd=per_slot_risk,
            open_positions=open_positions,
            accepted_so_far=accepted_so_far,
        )
        proposals.append(proposal)
        if proposal.accepted:
            accepted_so_far.append(proposal)

    # 5. Post-proposal exposure
    accepted_pos = [
        OpenPosition(p.symbol, p.side,
                     p.proposed_notional_usd * (1 if p.side == "long" else -1),
                     p.entry_price, p.stop_loss_price)
        for p in accepted_so_far
    ]
    post_exp = compute_exposure(open_positions + accepted_pos, equity_usd=equity_usd)

    # 6. Reject summary
    n_accepted = sum(1 for p in proposals if p.accepted)
    n_rejected = sum(1 for p in proposals if not p.accepted)
    reject_summary: dict[str, int] = {}
    for p in proposals:
        if not p.accepted:
            reject_summary[p.reject_reason] = reject_summary.get(p.reject_reason, 0) + 1

    return PortfolioSizingResult(
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        n_open=n_open,
        n_long_open=n_long,
        n_short_open=n_short,
        total_risk_budget_usd=budget["total_risk_budget_usd"],
        existing_stop_risk_usd=budget["existing_stop_risk_usd"],
        remaining_risk_budget_usd=budget["remaining_risk_budget_usd"],
        available_slots=avail_slots,
        current_gross_notional=cur_exp["gross_notional"],
        current_net_notional=cur_exp["net_notional"],
        proposals=proposals,
        proposed_gross_notional=post_exp["gross_notional"],
        proposed_net_notional=post_exp["net_notional"],
        proposed_gross_ratio=post_exp["gross_ratio"],
        proposed_net_ratio=post_exp["net_ratio"],
        n_accepted=n_accepted,
        n_rejected=n_rejected,
        reject_summary=reject_summary,
        demo_guard_ok=guard_ok,
        demo_guard_detail=guard_detail,
    )


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _reject(candidate: SignalCandidate, reason: str, detail: str) -> SizingProposal:
    entry = candidate.entry_price
    sl    = candidate.stop_loss_price
    dist  = abs(entry - sl) / entry if entry > 0 else 0.0
    return SizingProposal(
        symbol=candidate.symbol,
        side=candidate.side,
        entry_price=entry,
        stop_loss_price=sl,
        stop_distance_pct=dist,
        proposed_notional_usd=0.0,
        accepted=False,
        reject_reason=reason,
        detail={"detail": detail},
    )
