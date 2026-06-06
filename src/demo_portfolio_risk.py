"""
src/demo_portfolio_risk.py
TASK-014 Phase 2 (v2) — Demo Trading: batch portfolio-level 0.4 fractional Kelly sizer.

ALGORITHM (batch, deterministic):
  1. Validate all candidates.
  2. Sort valid candidates: score DESC, then symbol ASC (deterministic tie-break).
  3. Slot-filter: assign each candidate to accepted/rejected based on position caps.
     Existing open positions consume slots first.
  4. Compute slot_risk_budget = remaining_budget / remaining_slots.
  5. Per-candidate preliminary allocation:
       allocated = min(slot_risk_budget, portfolio_budget x MAX_SINGLE_TRADE_RISK_SHARE)
  6. Scale check: if sum(preliminary) > remaining_budget, apply proportional scale-down.
  7. Apply per-candidate exposure caps (gross, net, single, balance) in sorted order.
     Reduce deterministically; reject with 'allocation_scaled_to_zero' if reduced to 0.
  8. Return DemoPortfolioSizingResult — pure computation, no network, no orders.

INVARIANTS (verified in tests):
  existing_stop_risk + proposed_new_stop_risk <= portfolio_risk_budget
  proposed_gross_ratio <= MAX_GROSS_EXPOSURE_RATIO
  |proposed_net_ratio| <= MAX_NET_EXPOSURE_RATIO
  accepted_total <= MAX_OPEN_POSITIONS
  accepted_long  <= MAX_LONG_POSITIONS
  accepted_short <= MAX_SHORT_POSITIONS
  per candidate: allocated_risk <= slot_risk_budget
  per candidate: allocated_risk <= portfolio_budget x MAX_SINGLE_TRADE_RISK_SHARE

ISOLATION:
  No import of exchange executors, order APIs, main, or src.risk.
  Pure computation. Callers control all I/O and order submission.
"""
from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

KELLY_MULTIPLIER: float = 0.40

# Absolute stop-risk hard cap: even with high Kelly, never risk > 25% of equity
# in aggregate stop-losses. Justification: guards against regime where historical
# win-rate was lucky (e.g. full Kelly > 60%) and prevents runaway budget.
MAX_TOTAL_STOP_RISK_PCT_EQUITY: float = 0.25

MAX_OPEN_POSITIONS:  int   = 10
MAX_LONG_POSITIONS:  int   = 5
MAX_SHORT_POSITIONS: int   = 5

MAX_GROSS_EXPOSURE_RATIO:         float = 1.0
MAX_NET_EXPOSURE_RATIO:           float = 0.5
MAX_SINGLE_POSITION_NOTIONAL_PCT: float = 0.15   # 15% of equity per position
MAX_SINGLE_TRADE_RISK_SHARE:      float = 0.10   # 10% of portfolio budget per trade

MIN_STOP_DISTANCE_PCT: float = 0.0005   # 0.05%
MAX_STOP_DISTANCE_PCT: float = 0.50     # 50%
MIN_POSITION_NOTIONAL_USD: float = 5.0
MIN_QUANTITY:              float = 1e-9
MAX_VALID_FULL_KELLY:      float = 1.0

# Rejection reason constants
REJECT_MAX_OPEN_POSITIONS:       str = "max_open_positions"
REJECT_MAX_LONG_POSITIONS:       str = "max_long_positions"
REJECT_MAX_SHORT_POSITIONS:      str = "max_short_positions"
REJECT_INVALID_KELLY:            str = "invalid_kelly"
REJECT_INVALID_ENTRY_PRICE:      str = "invalid_entry_price"
REJECT_INVALID_STOP_DISTANCE:    str = "invalid_stop_distance"
REJECT_MISSING_VALID_STOP:       str = "missing_valid_stop"
REJECT_INSUFFICIENT_RISK_BUDGET: str = "insufficient_risk_budget"
REJECT_MAX_GROSS_EXPOSURE:       str = "max_gross_exposure"
REJECT_MAX_NET_EXPOSURE:         str = "max_net_exposure"
REJECT_MAX_SINGLE_POSITION:      str = "max_single_position"
REJECT_AVAILABLE_BALANCE:        str = "available_balance_exceeded"
REJECT_DEMO_NOT_VERIFIED:        str = "demo_environment_not_verified"
REJECT_SCALED_TO_ZERO:           str = "allocation_scaled_to_zero"


# ---------------------------------------------------------------------------
# Input types
# ---------------------------------------------------------------------------

@dataclass
class DemoOpenPosition:
    symbol:      str
    side:        str       # "long" | "short"
    quantity:    float
    entry_price: float
    stop_price:  float     # <= 0 → missing stop; triggers fail-closed

    @property
    def is_long(self) -> bool:
        return self.side.lower() == "long"

    @property
    def notional_usd(self) -> float:
        n = self.quantity * self.entry_price
        return n if self.is_long else -n

    @property
    def stop_risk_usd(self) -> float:
        if self.stop_price <= 0:
            return 0.0   # caller warned separately
        return abs(self.entry_price - self.stop_price) * self.quantity


@dataclass
class DemoSignalCandidate:
    symbol:      str
    side:        str       # "long" | "short"
    entry_price: float
    stop_price:  float
    score:       float = 0.0

    @property
    def is_long(self) -> bool:
        return self.side.lower() == "long"

    @property
    def stop_distance_pct(self) -> float:
        if self.entry_price <= 0:
            return 0.0
        return abs(self.entry_price - self.stop_price) / self.entry_price


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class SafetyWarning:
    code:    str
    message: str


@dataclass
class PositionProposal:
    symbol:                      str
    side:                        str
    score:                       float
    rank:                        int      # 1 = highest score
    entry_price:                 float
    stop_price:                  float
    stop_distance_pct:           float
    candidate_desired_risk_usd:  float    # = slot_risk_budget (before per-trade cap)
    slot_risk_budget_usd:        float    # = remaining_budget / remaining_slots
    allocated_stop_risk_usd:     float    # after all caps and scaling
    proposed_notional_usd:       float
    quantity:                    float
    accepted:                    bool
    reject_reason:               str
    detail:                      dict[str, Any] = field(default_factory=dict)


@dataclass
class DemoPortfolioSizingResult:
    # Environment
    demo_environment_expected:    bool

    # Portfolio inputs
    equity_usd:                   float
    available_balance_usd:        float
    full_kelly_fraction:          float
    kelly_multiplier:             float

    # Risk budget
    portfolio_raw_kelly_budget_usd: float
    absolute_hard_cap_usd:        float
    portfolio_risk_budget_usd:    float
    hard_cap_applied:             bool
    existing_stop_risk_usd:       float
    remaining_risk_budget_before: float
    remaining_slots:              int
    slot_risk_budget_usd:         float

    # Proposals
    proposals:                    list[PositionProposal]
    n_accepted:                   int
    n_rejected:                   int
    reject_summary:               dict[str, int]

    # Proposed stop-risk consumed
    proposed_new_stop_risk_usd:   float
    remaining_risk_budget_after:  float

    # Exposure
    current_gross_notional:       float
    current_net_notional:         float
    current_gross_ratio:          float
    current_net_ratio:            float
    proposed_gross_notional:      float
    proposed_net_notional:        float
    proposed_gross_ratio:         float
    proposed_net_ratio:           float

    # Position counts
    n_open:                       int
    n_long_open:                  int
    n_short_open:                 int

    # Scaling info
    scale_factor_applied:         float    # 1.0 = no scaling

    # Warnings
    warnings:                     list[SafetyWarning]

    def to_dict(self) -> dict[str, Any]:
        d = {k: v for k, v in self.__dict__.items() if k != "proposals" and k != "warnings"}
        d["proposals"] = [
            {
                "symbol":                     p.symbol,
                "side":                       p.side,
                "score":                      p.score,
                "rank":                       p.rank,
                "entry_price":                p.entry_price,
                "stop_price":                 p.stop_price,
                "stop_distance_pct":          round(p.stop_distance_pct, 6),
                "candidate_desired_risk_usd": round(p.candidate_desired_risk_usd, 4),
                "slot_risk_budget_usd":       round(p.slot_risk_budget_usd, 4),
                "allocated_stop_risk_usd":    round(p.allocated_stop_risk_usd, 4),
                "proposed_notional_usd":      round(p.proposed_notional_usd, 4),
                "quantity":                   round(p.quantity, 8),
                "accepted":                   p.accepted,
                "reject_reason":              p.reject_reason,
                "detail":                     p.detail,
            }
            for p in self.proposals
        ]
        d["warnings"] = [{"code": w.code, "message": w.message} for w in self.warnings]
        return d


# ---------------------------------------------------------------------------
# Validation helpers
# ---------------------------------------------------------------------------

def validate_full_kelly(fk: Any) -> tuple[bool, float, str]:
    """Returns (valid, safe_value, error_message)."""
    try:
        fk_f = float(fk)
    except (TypeError, ValueError):
        return False, 0.0, f"full_kelly_fraction cannot be converted to float: {fk!r}"
    if math.isnan(fk_f):
        return False, 0.0, "full_kelly_fraction is NaN"
    if not math.isfinite(fk_f):
        return False, 0.0, f"full_kelly_fraction is not finite: {fk_f}"
    if fk_f <= 0.0:
        return False, 0.0, f"full_kelly_fraction must be > 0, got {fk_f}"
    if fk_f > MAX_VALID_FULL_KELLY:
        return False, 0.0, (
            f"full_kelly_fraction={fk_f:.4f} > {MAX_VALID_FULL_KELLY} "
            "(Kelly > 100% of capital is theoretically invalid)"
        )
    return True, fk_f, ""


def _validate_candidate(c: DemoSignalCandidate) -> tuple[bool, str, str]:
    """Returns (valid, reject_reason, detail)."""
    if not math.isfinite(c.entry_price) or c.entry_price <= 0:
        return False, REJECT_INVALID_ENTRY_PRICE, f"entry_price={c.entry_price!r}"
    if c.stop_price <= 0:
        return False, REJECT_MISSING_VALID_STOP, f"stop_price={c.stop_price!r} must be > 0"
    sd = c.stop_distance_pct
    if not math.isfinite(sd) or sd <= 0:
        return False, REJECT_INVALID_STOP_DISTANCE, f"stop_distance_pct={sd!r}"
    if sd < MIN_STOP_DISTANCE_PCT:
        return False, REJECT_INVALID_STOP_DISTANCE, (
            f"stop_distance_pct={sd:.5%} < min {MIN_STOP_DISTANCE_PCT:.5%}"
        )
    if sd > MAX_STOP_DISTANCE_PCT:
        return False, REJECT_INVALID_STOP_DISTANCE, (
            f"stop_distance_pct={sd:.2%} > max {MAX_STOP_DISTANCE_PCT:.0%}"
        )
    return True, "", ""


# ---------------------------------------------------------------------------
# Risk-budget helpers
# ---------------------------------------------------------------------------

def compute_risk_budget(equity_usd: float, full_kelly_fraction: float) -> dict[str, Any]:
    raw    = equity_usd * full_kelly_fraction * KELLY_MULTIPLIER
    cap    = equity_usd * MAX_TOTAL_STOP_RISK_PCT_EQUITY
    budget = min(raw, cap)
    return {
        "portfolio_raw_kelly_budget_usd": raw,
        "absolute_hard_cap_usd":          cap,
        "portfolio_risk_budget_usd":      budget,
        "hard_cap_applied":               budget < raw,
    }


def compute_existing_stop_risk(
    open_positions: list[DemoOpenPosition],
) -> tuple[float, list[SafetyWarning]]:
    """
    Sum existing stop risks. Positions without valid stop trigger fail-closed warning:
    we do NOT assume zero risk — we flag them and set remaining_budget = 0 for safety.
    Returns (total_risk_usd, warnings).
    """
    total    = 0.0
    warnings: list[SafetyWarning] = []
    for pos in open_positions:
        if pos.stop_price <= 0:
            warnings.append(SafetyWarning(
                code=REJECT_MISSING_VALID_STOP,
                message=(
                    f"Open position {pos.symbol} ({pos.side}) has no valid stop "
                    f"(stop_price={pos.stop_price}). "
                    "Treating full notional as stop risk (fail-closed)."
                ),
            ))
            total += abs(pos.notional_usd)
        else:
            total += pos.stop_risk_usd
    return total, warnings


# ---------------------------------------------------------------------------
# Exposure helper
# ---------------------------------------------------------------------------

def _compute_exposure(
    open_positions: list[DemoOpenPosition],
    accepted: list[PositionProposal] | None = None,
    equity_usd: float = 1.0,
) -> dict[str, float]:
    notionals = [p.notional_usd for p in open_positions]
    if accepted:
        for prop in accepted:
            s = 1.0 if prop.side == "long" else -1.0
            notionals.append(s * prop.proposed_notional_usd)
    gross = sum(abs(n) for n in notionals)
    net   = sum(notionals)
    return {
        "gross_notional": gross,
        "net_notional":   net,
        "gross_ratio":    gross / equity_usd if equity_usd > 0 else 0.0,
        "net_ratio":      abs(net) / equity_usd if equity_usd > 0 else 0.0,
    }


# ---------------------------------------------------------------------------
# Batch allocation core
# ---------------------------------------------------------------------------

def compute_demo_portfolio_sizing(
    equity_usd:                float,
    available_balance_usd:     float,
    full_kelly_fraction:       float,
    open_positions:            list[DemoOpenPosition],
    candidates:                list[DemoSignalCandidate],
    demo_environment_expected: bool = True,
) -> DemoPortfolioSizingResult:
    """
    Portfolio-level 0.4 fractional Kelly batch sizer.
    Pure computation — no network, no orders, no secrets.
    """
    warnings: list[SafetyWarning] = []

    # ── 1. Validate Kelly ────────────────────────────────────────────────
    kelly_ok, fk_safe, kelly_err = validate_full_kelly(full_kelly_fraction)
    if not kelly_ok:
        warnings.append(SafetyWarning(code=REJECT_INVALID_KELLY, message=kelly_err))

    # ── 2. Risk budget ───────────────────────────────────────────────────
    binfo = compute_risk_budget(equity_usd, fk_safe if kelly_ok else 0.0)
    port_budget   = binfo["portfolio_risk_budget_usd"]
    raw_budget    = binfo["portfolio_raw_kelly_budget_usd"]
    hard_cap_usd  = binfo["absolute_hard_cap_usd"]
    hard_cap_appl = binfo["hard_cap_applied"]
    if hard_cap_appl:
        warnings.append(SafetyWarning(
            code="hard_cap_applied",
            message=(
                f"Portfolio risk budget capped at {MAX_TOTAL_STOP_RISK_PCT_EQUITY:.0%} "
                f"of equity (raw={raw_budget:.2f}, capped={port_budget:.2f})"
            ),
        ))

    # ── 3. Existing stop risk ────────────────────────────────────────────
    existing_risk, stop_warns = compute_existing_stop_risk(open_positions)
    warnings.extend(stop_warns)
    has_missing_stop = any(w.code == REJECT_MISSING_VALID_STOP for w in stop_warns)

    remaining_budget = max(0.0, port_budget - existing_risk)

    # ── 4. Current exposure ──────────────────────────────────────────────
    cur_exp = _compute_exposure(open_positions, equity_usd=equity_usd)
    n_open   = len(open_positions)
    n_long   = sum(1 for p in open_positions if p.is_long)
    n_short  = n_open - n_long
    avail_slots = max(0, MAX_OPEN_POSITIONS - n_open)

    slot_risk_budget = (remaining_budget / avail_slots) if avail_slots > 0 else 0.0

    # ── 5. Validate + sort candidates (score DESC, symbol ASC) ───────────
    raw_proposals: list[dict] = []   # working dicts during batch assembly

    if not kelly_ok or not demo_environment_expected or has_missing_stop:
        # Fail-closed: reject everything
        reason = (REJECT_INVALID_KELLY if not kelly_ok
                  else REJECT_DEMO_NOT_VERIFIED if not demo_environment_expected
                  else REJECT_MISSING_VALID_STOP)
        detail = (kelly_err if not kelly_ok
                  else "demo_environment_expected=False"
                  if not demo_environment_expected
                  else "open position missing stop; cannot safely allocate new positions")
        for i, c in enumerate(
            sorted(candidates, key=lambda x: (-x.score, x.symbol)), start=1
        ):
            raw_proposals.append(_make_rejected(c, i, 0.0, slot_risk_budget, reason, detail))
        return _build_result(
            demo_environment_expected=demo_environment_expected,
            equity_usd=equity_usd, available_balance_usd=available_balance_usd,
            full_kelly_fraction=full_kelly_fraction,
            raw_budget=raw_budget, hard_cap_usd=hard_cap_usd,
            port_budget=port_budget, hard_cap_appl=hard_cap_appl,
            existing_risk=existing_risk, remaining_budget=remaining_budget,
            avail_slots=avail_slots, slot_risk_budget=slot_risk_budget,
            n_open=n_open, n_long=n_long, n_short=n_short,
            cur_exp=cur_exp, open_positions=open_positions,
            raw_proposals=raw_proposals, scale_factor=1.0,
            warnings=warnings, equity=equity_usd,
        )

    # ── 6. Sort: score DESC, symbol ASC (deterministic tie-break) ────────
    sorted_candidates = sorted(candidates, key=lambda c: (-c.score, c.symbol))

    # ── 7. Slot-filter: determine eligible set ───────────────────────────
    # Count how many longs/shorts we can still accept
    long_slots  = MAX_LONG_POSITIONS  - n_long
    short_slots = MAX_SHORT_POSITIONS - n_short
    open_slots  = avail_slots

    eligible:   list[tuple[int, DemoSignalCandidate]] = []   # (rank, candidate)
    ineligible: list[tuple[int, DemoSignalCandidate, str, str]] = []

    rank = 0
    for c in sorted_candidates:
        rank += 1
        valid, rej_reason, rej_detail = _validate_candidate(c)
        if not valid:
            ineligible.append((rank, c, rej_reason, rej_detail))
            continue
        # Slot checks
        if open_slots <= 0:
            ineligible.append((rank, c, REJECT_MAX_OPEN_POSITIONS,
                                f"open_slots={open_slots}"))
            continue
        if c.is_long and long_slots <= 0:
            ineligible.append((rank, c, REJECT_MAX_LONG_POSITIONS,
                                f"long_slots={long_slots}"))
            continue
        if not c.is_long and short_slots <= 0:
            ineligible.append((rank, c, REJECT_MAX_SHORT_POSITIONS,
                                f"short_slots={short_slots}"))
            continue
        # Reserve the slot
        eligible.append((rank, c))
        open_slots  -= 1
        if c.is_long:
            long_slots  -= 1
        else:
            short_slots -= 1

    n_eligible = len(eligible)

    # ── 8. Preliminary allocation (per-candidate) ────────────────────────
    # slot_risk_budget and 10%-of-total cap, whichever is smaller
    single_trade_cap = port_budget * MAX_SINGLE_TRADE_RISK_SHARE
    if n_eligible > 0:
        per_candidate_preliminary = min(slot_risk_budget, single_trade_cap)
    else:
        per_candidate_preliminary = 0.0

    # ── 9. Proportional scale-down if sum(preliminary) > remaining ───────
    total_preliminary = per_candidate_preliminary * n_eligible
    if total_preliminary > remaining_budget and total_preliminary > 0:
        scale_factor = remaining_budget / total_preliminary
    else:
        scale_factor = 1.0

    scaled_per_candidate = per_candidate_preliminary * scale_factor

    # ── 10. Apply per-candidate exposure caps in sorted order ─────────────
    accepted_so_far: list[PositionProposal] = []
    allocated_balance_so_far = 0.0

    # Build proposals for eligible candidates
    eligible_proposals: list[PositionProposal] = []
    for (rank_i, c) in eligible:
        sd = c.stop_distance_pct
        allocated_risk = scaled_per_candidate

        # — compute raw notional —
        raw_notional = allocated_risk / sd if sd > 0 else 0.0

        # — single-position notional cap —
        single_notional_cap = equity_usd * MAX_SINGLE_POSITION_NOTIONAL_PCT
        notional = min(raw_notional, single_notional_cap)

        # — gross exposure cap —
        cur_acc_exp = _compute_exposure(
            open_positions, accepted=accepted_so_far, equity_usd=equity_usd
        )
        gross_cap = equity_usd * MAX_GROSS_EXPOSURE_RATIO
        gross_rem = max(0.0, gross_cap - cur_acc_exp["gross_notional"])
        if notional > gross_rem:
            notional = gross_rem

        # — net exposure cap —
        net_sign = 1.0 if c.is_long else -1.0
        cur_net  = cur_acc_exp["net_notional"]
        net_cap  = equity_usd * MAX_NET_EXPOSURE_RATIO
        projected_net = cur_net + net_sign * notional
        if abs(projected_net) > net_cap:
            if net_sign > 0:
                headroom = net_cap - cur_net
            else:
                headroom = net_cap + cur_net
            headroom = max(0.0, headroom)
            notional = min(notional, headroom)

        # — available balance cap —
        bal_rem = max(0.0, available_balance_usd - allocated_balance_so_far)
        if notional > bal_rem:
            notional = bal_rem

        # — minimum notional / reject if scaled to zero —
        rej_reason = ""
        if notional < MIN_POSITION_NOTIONAL_USD:
            if raw_notional < MIN_POSITION_NOTIONAL_USD:
                rej_reason = REJECT_INSUFFICIENT_RISK_BUDGET
            elif gross_rem < MIN_POSITION_NOTIONAL_USD:
                rej_reason = REJECT_MAX_GROSS_EXPOSURE
            elif bal_rem < MIN_POSITION_NOTIONAL_USD:
                rej_reason = REJECT_AVAILABLE_BALANCE
            else:
                rej_reason = REJECT_SCALED_TO_ZERO

        if rej_reason:
            eligible_proposals.append(PositionProposal(
                symbol=c.symbol, side=c.side, score=c.score, rank=rank_i,
                entry_price=c.entry_price, stop_price=c.stop_price,
                stop_distance_pct=sd,
                candidate_desired_risk_usd=per_candidate_preliminary,
                slot_risk_budget_usd=slot_risk_budget,
                allocated_stop_risk_usd=0.0,
                proposed_notional_usd=0.0,
                quantity=0.0,
                accepted=False,
                reject_reason=rej_reason,
                detail={"notional_before_rejection": round(raw_notional, 4)},
            ))
            continue

        # — quantity —
        qty = notional / c.entry_price
        if not math.isfinite(qty) or qty < MIN_QUANTITY:
            eligible_proposals.append(PositionProposal(
                symbol=c.symbol, side=c.side, score=c.score, rank=rank_i,
                entry_price=c.entry_price, stop_price=c.stop_price,
                stop_distance_pct=sd,
                candidate_desired_risk_usd=per_candidate_preliminary,
                slot_risk_budget_usd=slot_risk_budget,
                allocated_stop_risk_usd=0.0,
                proposed_notional_usd=0.0,
                quantity=0.0,
                accepted=False,
                reject_reason=REJECT_INVALID_ENTRY_PRICE,
                detail={"qty_computed": qty},
            ))
            continue

        actual_risk = notional * sd
        prop = PositionProposal(
            symbol=c.symbol, side=c.side, score=c.score, rank=rank_i,
            entry_price=c.entry_price, stop_price=c.stop_price,
            stop_distance_pct=round(sd, 6),
            candidate_desired_risk_usd=round(per_candidate_preliminary, 4),
            slot_risk_budget_usd=round(slot_risk_budget, 4),
            allocated_stop_risk_usd=round(actual_risk, 4),
            proposed_notional_usd=round(notional, 4),
            quantity=round(qty, 8),
            accepted=True,
            reject_reason="",
            detail={
                "raw_notional_usd":       round(raw_notional, 4),
                "single_notional_cap":    round(single_notional_cap, 4),
                "gross_headroom_usd":     round(gross_rem, 4),
                "scale_factor":           round(scale_factor, 6),
            },
        )
        eligible_proposals.append(prop)
        accepted_so_far.append(prop)
        allocated_balance_so_far += notional

    # ── 11. Assemble all proposals in original sorted order ───────────────
    # (eligible in order, ineligible interspersed by rank)
    all_proposals_by_rank: dict[int, PositionProposal] = {}
    for prop in eligible_proposals:
        all_proposals_by_rank[prop.rank] = prop
    for (rank_i, c, rej_r, rej_d) in ineligible:
        all_proposals_by_rank[rank_i] = PositionProposal(
            symbol=c.symbol, side=c.side, score=c.score, rank=rank_i,
            entry_price=c.entry_price, stop_price=c.stop_price,
            stop_distance_pct=c.stop_distance_pct,
            candidate_desired_risk_usd=per_candidate_preliminary,
            slot_risk_budget_usd=slot_risk_budget,
            allocated_stop_risk_usd=0.0,
            proposed_notional_usd=0.0,
            quantity=0.0,
            accepted=False,
            reject_reason=rej_r,
            detail={"detail": rej_d},
        )
    proposals = [all_proposals_by_rank[r] for r in sorted(all_proposals_by_rank)]

    return _build_result(
        demo_environment_expected=demo_environment_expected,
        equity_usd=equity_usd, available_balance_usd=available_balance_usd,
        full_kelly_fraction=full_kelly_fraction,
        raw_budget=raw_budget, hard_cap_usd=hard_cap_usd,
        port_budget=port_budget, hard_cap_appl=hard_cap_appl,
        existing_risk=existing_risk, remaining_budget=remaining_budget,
        avail_slots=avail_slots, slot_risk_budget=slot_risk_budget,
        n_open=n_open, n_long=n_long, n_short=n_short,
        cur_exp=cur_exp, open_positions=open_positions,
        raw_proposals=proposals, scale_factor=scale_factor,
        warnings=warnings, equity=equity_usd,
    )


# ---------------------------------------------------------------------------
# Result builder
# ---------------------------------------------------------------------------

def _build_result(
    *,
    demo_environment_expected, equity_usd, available_balance_usd,
    full_kelly_fraction, raw_budget, hard_cap_usd, port_budget, hard_cap_appl,
    existing_risk, remaining_budget, avail_slots, slot_risk_budget,
    n_open, n_long, n_short, cur_exp, open_positions,
    raw_proposals, scale_factor, warnings, equity,
) -> DemoPortfolioSizingResult:
    proposals = (
        raw_proposals
        if (not raw_proposals or isinstance(raw_proposals[0], PositionProposal))
        else [PositionProposal(**p) for p in raw_proposals]
    )

    accepted  = [p for p in proposals if p.accepted]
    n_accepted = len(accepted)
    n_rejected = len(proposals) - n_accepted

    rej_summary: dict[str, int] = {}
    for p in proposals:
        if not p.accepted:
            rej_summary[p.reject_reason] = rej_summary.get(p.reject_reason, 0) + 1

    new_stop_risk = sum(p.allocated_stop_risk_usd for p in accepted)
    remaining_after = max(0.0, remaining_budget - new_stop_risk)

    post_exp = _compute_exposure(open_positions, accepted=accepted, equity_usd=equity)

    return DemoPortfolioSizingResult(
        demo_environment_expected=demo_environment_expected,
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        full_kelly_fraction=full_kelly_fraction,
        kelly_multiplier=KELLY_MULTIPLIER,
        portfolio_raw_kelly_budget_usd=raw_budget,
        absolute_hard_cap_usd=hard_cap_usd,
        portfolio_risk_budget_usd=port_budget,
        hard_cap_applied=hard_cap_appl,
        existing_stop_risk_usd=existing_risk,
        remaining_risk_budget_before=remaining_budget,
        remaining_slots=avail_slots,
        slot_risk_budget_usd=slot_risk_budget,
        proposals=proposals,
        n_accepted=n_accepted,
        n_rejected=n_rejected,
        reject_summary=rej_summary,
        proposed_new_stop_risk_usd=new_stop_risk,
        remaining_risk_budget_after=remaining_after,
        current_gross_notional=cur_exp["gross_notional"],
        current_net_notional=cur_exp["net_notional"],
        current_gross_ratio=cur_exp["gross_ratio"],
        current_net_ratio=cur_exp["net_ratio"],
        proposed_gross_notional=post_exp["gross_notional"],
        proposed_net_notional=post_exp["net_notional"],
        proposed_gross_ratio=post_exp["gross_ratio"],
        proposed_net_ratio=post_exp["net_ratio"],
        n_open=n_open,
        n_long_open=n_long,
        n_short_open=n_short,
        scale_factor_applied=scale_factor,
        warnings=warnings,
    )


def _make_rejected(c, rank, desired_risk, slot_risk, reason, detail) -> PositionProposal:
    return PositionProposal(
        symbol=c.symbol, side=c.side, score=c.score, rank=rank,
        entry_price=c.entry_price, stop_price=c.stop_price,
        stop_distance_pct=c.stop_distance_pct,
        candidate_desired_risk_usd=desired_risk,
        slot_risk_budget_usd=slot_risk,
        allocated_stop_risk_usd=0.0,
        proposed_notional_usd=0.0,
        quantity=0.0,
        accepted=False,
        reject_reason=reason,
        detail={"detail": detail},
    )
