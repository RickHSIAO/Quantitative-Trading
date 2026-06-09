"""
src/demo_close_only_cleanup.py
TASK-014F: Demo close-only cleanup planner.

Reads current position list and reconciliation state; selects excess positions for
close review deterministically; generates close-only payload previews; enforces a
human confirmation gate.

SAFETY INVARIANTS (structural — verified by tests):
  no_orders_sent = True         (always — no sender is implemented in this module)
  no_position_modified = True   (always)
  order_endpoint_called = False (always)
  secret_value_observed = False (always)
  action_type = "MANUAL_CONFIRMATION_REQUIRED" (always)
  Every payload: reduce_only = True, confirmation_required = True
  execute_ready = True only when ALL hold:
    token_valid AND demo_runtime_verified AND snapshot_fresh
    AND cleanup_needed AND payload_safety_verified

Close-only candidate selection (deterministic):
  1. Only positions in the violating direction are candidates
     (short_count > 5 → only shorts; long_count > 5 → only longs).
  2. close_count = excess count (e.g. short_count − 5).
  3. Sort: stop_risk_usd DESC, notional_usd DESC, symbol ASC.
  4. close_order_side: short position → "Buy"; long position → "Sell".
  5. reduce_only = True always.

This module does NOT modify main.py, src/risk.py, or exchange executor classes.
No network calls. No secrets. No opening of new positions.
"""
from __future__ import annotations

import hashlib
import math
from dataclasses import dataclass, field
from datetime import date, datetime, timezone
from typing import Any

from src.demo_portfolio_risk import DemoOpenPosition

# ---------------------------------------------------------------------------
# Policy constants
# ---------------------------------------------------------------------------

MAX_SNAPSHOT_AGE_HOURS: float = 24.0
MAX_SHORT_POSITIONS:    int   = 5
MAX_LONG_POSITIONS:     int   = 5
MAX_OPEN_POSITIONS:     int   = 10


# ---------------------------------------------------------------------------
# Output types
# ---------------------------------------------------------------------------

@dataclass
class CloseCandidate:
    """A position selected (or considered) for close review."""
    symbol:        str
    side:          str    # "long" or "short" (direction of the existing position)
    quantity:      float
    entry_price:   float
    stop_price:    float  # 0.0 when stop is absent
    notional_usd:  float  # |qty * entry_price|
    stop_risk_usd: float  # conservative: full notional when stop absent
    close_rank:    int    # 1 = first to close; 0 = not selected
    reason:        str    # why this candidate was selected


@dataclass
class ClosePayloadPreview:
    """
    Read-only preview of the payload that WOULD be submitted to close a position.

    This is a planning artefact only.  no_orders_sent is always True.
    reduce_only is always True.  confirmation_required is always True.
    No sender is implemented in TASK-014F.
    """
    symbol:                       str
    side_to_close:                str    # direction of the existing position
    close_order_side:             str    # "Buy" to close short; "Sell" to close long
    qty:                          float
    order_type:                   str    # "Market"
    reduce_only:                  bool   # always True
    close_on_trigger:             bool   # always False
    category:                     str    # "linear"
    position_idx:                 int    # 0 (one-way mode default)
    reason:                       str
    source_position_snapshot_hash: str  # hash of input positions for traceability
    confirmation_required:        bool   # always True
    no_orders_sent:               bool   # always True (preview only)
    order_not_submitted:          bool   # always True


@dataclass
class CleanupPlan:
    """
    Full close-only cleanup plan: candidates, payloads, confirmation state,
    and safety invariants.
    """
    mode:                    str
    demo_runtime_verified:   bool
    proof_strength:          str

    equity_usd:              float
    available_balance_usd:   float

    current_short_count:     int
    current_long_count:      int
    current_open_count:      int
    target_short_count:      int   # MAX_SHORT_POSITIONS
    target_long_count:       int   # MAX_LONG_POSITIONS
    target_open_count:       int   # MAX_OPEN_POSITIONS

    cleanup_needed:          bool
    cleanup_reasons:         list[str]

    candidate_positions_to_review: list[CloseCandidate]   # all positions (reference)
    suggested_close_candidates:    list[CloseCandidate]   # positions recommended for close
    proposed_close_count:          int

    close_payload_previews:  list[ClosePayloadPreview]

    snapshot_timestamp_utc:  str
    snapshot_fresh:          bool
    snapshot_age_hours:      float | None

    confirmation_required:            bool   # always True
    confirm_token_expected_pattern:   str
    confirm_token_provided:           str    # "" if not supplied
    confirm_token_valid:              bool
    execute_ready:                    bool   # True only when all gates pass

    # Safety invariants — always these values
    action_type:             str  = "MANUAL_CONFIRMATION_REQUIRED"
    no_orders_sent:          bool = True
    no_position_modified:    bool = True
    order_endpoint_called:   bool = False
    secret_value_observed:   bool = False

    # TASK-014H: position-source provenance ("real_readonly" | "fixture")
    position_details_source: str  = "fixture"
    # When True the source matches real_readonly (gates execute_ready)
    source_position_details_is_real: bool = False

    def to_dict(self, timestamp_utc: str = "") -> dict[str, Any]:
        return {
            "timestamp":                    timestamp_utc,
            "mode":                         self.mode,
            "demo_runtime_verified":        self.demo_runtime_verified,
            "proof_strength":               self.proof_strength,
            "equity_usd":                   round(self.equity_usd, 2),
            "available_balance_usd":        round(self.available_balance_usd, 2),
            "current_short_count":          self.current_short_count,
            "current_long_count":           self.current_long_count,
            "current_open_count":           self.current_open_count,
            "target_short_count":           self.target_short_count,
            "target_long_count":            self.target_long_count,
            "target_open_count":            self.target_open_count,
            "cleanup_needed":               self.cleanup_needed,
            "cleanup_reasons":              self.cleanup_reasons,
            "proposed_close_count":         self.proposed_close_count,
            "suggested_close_candidates": [
                {
                    "symbol":        c.symbol,
                    "side":          c.side,
                    "quantity":      c.quantity,
                    "entry_price":   c.entry_price,
                    "stop_price":    c.stop_price,
                    "notional_usd":  round(c.notional_usd, 2),
                    "stop_risk_usd": round(c.stop_risk_usd, 2),
                    "close_rank":    c.close_rank,
                    "reason":        c.reason,
                }
                for c in self.suggested_close_candidates
            ],
            "close_payload_preview": [
                {
                    "symbol":                       p.symbol,
                    "side_to_close":                p.side_to_close,
                    "close_order_side":             p.close_order_side,
                    "qty":                          p.qty,
                    "order_type":                   p.order_type,
                    "reduce_only":                  p.reduce_only,
                    "close_on_trigger":             p.close_on_trigger,
                    "category":                     p.category,
                    "position_idx":                 p.position_idx,
                    "reason":                       p.reason,
                    "source_position_snapshot_hash": p.source_position_snapshot_hash,
                    "confirmation_required":        p.confirmation_required,
                    "no_orders_sent":               p.no_orders_sent,
                    "order_not_submitted":          p.order_not_submitted,
                }
                for p in self.close_payload_previews
            ],
            "snapshot_fresh":                   self.snapshot_fresh,
            "snapshot_age_hours":               self.snapshot_age_hours,
            "snapshot_timestamp_utc":           self.snapshot_timestamp_utc,
            "position_details_source":         self.position_details_source,
            "source_position_details_is_real": self.source_position_details_is_real,
            "confirmation_required":            self.confirmation_required,
            "confirm_token_expected_pattern":   self.confirm_token_expected_pattern,
            "confirm_token_valid":              self.confirm_token_valid,
            "execute_ready":                    self.execute_ready,
            "action_type":                      self.action_type,
            "no_orders_sent":                   self.no_orders_sent,
            "no_position_modified":             self.no_position_modified,
            "order_endpoint_called":            self.order_endpoint_called,
            "secret_value_observed":            self.secret_value_observed,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _conservative_stop_risk(pos: DemoOpenPosition) -> float:
    """Stop risk in USD.  When stop absent, use full notional (worst case)."""
    if pos.stop_price <= 0:
        return abs(pos.quantity * pos.entry_price)
    return abs(pos.entry_price - pos.stop_price) * pos.quantity


def _position_notional(pos: DemoOpenPosition) -> float:
    return abs(pos.quantity * pos.entry_price)


def _compute_snapshot_hash(positions: list[DemoOpenPosition]) -> str:
    """Short deterministic hash of the position list for traceability."""
    data = "|".join(
        f"{p.symbol}:{p.side}:{p.quantity:.8f}:{p.entry_price:.6f}:{p.stop_price:.6f}"
        for p in sorted(positions, key=lambda x: (x.symbol, x.side))
    )
    return hashlib.sha256(data.encode("utf-8")).hexdigest()[:12]


def _expected_confirm_token(today: date) -> str:
    return f"CONFIRM_DEMO_CLOSE_ONLY_{today.strftime('%Y%m%d')}"


def _check_snapshot_freshness(
    timestamp_utc: str,
    max_age_hours: float = MAX_SNAPSHOT_AGE_HOURS,
    now: datetime | None = None,
) -> tuple[bool, float | None]:
    """
    Returns (is_fresh, age_hours_or_None).
    Empty timestamp → assumed fresh (fixture mode with no external snapshot).
    """
    if not timestamp_utc:
        return True, None
    try:
        ts   = datetime.fromisoformat(timestamp_utc.replace("Z", "+00:00"))
        _now = now or datetime.now(timezone.utc)
        age  = (_now - ts).total_seconds() / 3600.0
        return age <= max_age_hours, age
    except (ValueError, TypeError):
        return False, None   # unparseable → treat as stale


def _build_candidates(
    positions: list[DemoOpenPosition],
    n_close_short: int,
    n_close_long:  int,
) -> tuple[list[CloseCandidate], list[CloseCandidate]]:
    """
    Build (all_candidates, selected_candidates).

    all_candidates: every position as a CloseCandidate (for the reviewer).
    selected_candidates: the subset recommended for closing, sorted
        deterministically: stop_risk_usd DESC, notional_usd DESC, symbol ASC.
    """
    # Build candidate objects for all positions
    all_cands: list[CloseCandidate] = []
    for pos in positions:
        sr  = _conservative_stop_risk(pos)
        not_usd = _position_notional(pos)
        all_cands.append(CloseCandidate(
            symbol=pos.symbol,
            side=pos.side,
            quantity=pos.quantity,
            entry_price=pos.entry_price,
            stop_price=pos.stop_price,
            notional_usd=not_usd,
            stop_risk_usd=sr,
            close_rank=0,
            reason="",
        ))

    selected: list[CloseCandidate] = []
    rank_offset = 0

    # Select shorts to close (deterministic sort)
    if n_close_short > 0:
        shorts = sorted(
            [c for c in all_cands if c.side.lower() == "short"],
            key=lambda c: (-c.stop_risk_usd, -c.notional_usd, c.symbol),
        )
        for i, c in enumerate(shorts[:n_close_short]):
            c.close_rank = rank_offset + i + 1
            c.reason = (
                f"short_count_exceeded: rank={c.close_rank}, "
                f"stop_risk_usd={c.stop_risk_usd:.2f}, "
                f"notional_usd={c.notional_usd:.2f}"
            )
            selected.append(c)
        rank_offset += n_close_short

    # Select longs to close (deterministic sort)
    if n_close_long > 0:
        longs = sorted(
            [c for c in all_cands if c.side.lower() == "long"],
            key=lambda c: (-c.stop_risk_usd, -c.notional_usd, c.symbol),
        )
        for i, c in enumerate(longs[:n_close_long]):
            c.close_rank = rank_offset + i + 1
            c.reason = (
                f"long_count_exceeded: rank={c.close_rank}, "
                f"stop_risk_usd={c.stop_risk_usd:.2f}, "
                f"notional_usd={c.notional_usd:.2f}"
            )
            selected.append(c)

    return all_cands, selected


def _build_payload(
    candidate: CloseCandidate,
    snapshot_hash: str,
) -> ClosePayloadPreview:
    """
    Build a close-only payload preview for one candidate.
    reduce_only=True always.  No order is submitted; this is a planning preview.
    """
    # To close a short position → send a Buy order.
    # To close a long  position → send a Sell order.
    close_side = "Buy" if candidate.side.lower() == "short" else "Sell"
    return ClosePayloadPreview(
        symbol=candidate.symbol,
        side_to_close=candidate.side,
        close_order_side=close_side,
        qty=candidate.quantity,
        order_type="Market",
        reduce_only=True,
        close_on_trigger=False,
        category="linear",
        position_idx=0,
        reason=candidate.reason,
        source_position_snapshot_hash=snapshot_hash,
        confirmation_required=True,
        no_orders_sent=True,
        order_not_submitted=True,
    )


# ---------------------------------------------------------------------------
# Core planner
# ---------------------------------------------------------------------------

def plan_cleanup(
    equity_usd:              float,
    available_balance_usd:   float,
    positions:               list[DemoOpenPosition],
    demo_runtime_verified:   bool  = False,
    proof_strength:          str   = "",
    mode:                    str   = "fixture",
    confirm_token:           str   = "",
    today:                   date | None = None,
    snapshot_timestamp_utc:  str   = "",
    max_snapshot_age_hours:  float = MAX_SNAPSHOT_AGE_HOURS,
    position_details_source: str   = "fixture",
    _now:                    datetime | None = None,
) -> CleanupPlan:
    """
    Determine which positions need to be closed, rank candidates, build
    payload previews, and evaluate the human confirmation gate.

    Pure computation — no network calls, no order submissions, no secrets,
    no position modifications.  All safety invariants are structural.

    Args:
        equity_usd:             Total account equity in USD.
        available_balance_usd:  Free margin in USD (context only, does not block cleanup).
        positions:              Current open positions.
        demo_runtime_verified:  True if TASK-014D proof was STRONG.
        proof_strength:         "STRONG" / "WEAK" / "MISSING".
        mode:                   Report mode label.
        confirm_token:          Human-supplied token (must match expected pattern).
        today:                  Override today's date (for testing).
        snapshot_timestamp_utc: ISO-8601 UTC timestamp of the position snapshot.
        max_snapshot_age_hours: Max acceptable snapshot age (default 24 h).
        _now:                   Override current time (for testing staleness checks).

    Returns:
        CleanupPlan with candidates, payloads, confirmation state, and invariants.
    """
    _today = today or date.today()

    # ── Confirmation token ────────────────────────────────────────────────
    expected_token = _expected_confirm_token(_today)
    token_valid    = bool(confirm_token) and (confirm_token == expected_token)

    # ── Snapshot freshness ────────────────────────────────────────────────
    snapshot_fresh, snapshot_age = _check_snapshot_freshness(
        snapshot_timestamp_utc, max_snapshot_age_hours, _now
    )

    # ── Position counts ───────────────────────────────────────────────────
    short_count = sum(1 for p in positions if p.side.lower() == "short")
    long_count  = sum(1 for p in positions if p.side.lower() == "long")
    open_count  = len(positions)

    # ── Cleanup determination ─────────────────────────────────────────────
    n_close_short = max(0, short_count - MAX_SHORT_POSITIONS)
    n_close_long  = max(0, long_count  - MAX_LONG_POSITIONS)
    cleanup_needed = (n_close_short > 0 or n_close_long > 0)

    cleanup_reasons: list[str] = []
    if n_close_short > 0:
        cleanup_reasons.append(
            f"short_count={short_count} > MAX_SHORT={MAX_SHORT_POSITIONS}: "
            f"close {n_close_short} short(s)"
        )
    if n_close_long > 0:
        cleanup_reasons.append(
            f"long_count={long_count} > MAX_LONG={MAX_LONG_POSITIONS}: "
            f"close {n_close_long} long(s)"
        )
    if not snapshot_fresh:
        age_str = f"{snapshot_age:.1f}h" if snapshot_age is not None else "unknown"
        cleanup_reasons.append(
            f"snapshot_stale: age={age_str} > max={max_snapshot_age_hours:.1f}h"
        )

    # ── Candidate selection ───────────────────────────────────────────────
    snapshot_hash         = _compute_snapshot_hash(positions)
    all_cands, selected   = _build_candidates(positions, n_close_short, n_close_long)

    # ── Close-only payloads ───────────────────────────────────────────────
    payloads = [_build_payload(c, snapshot_hash) for c in selected]

    # ── Payload safety verification ───────────────────────────────────────
    payload_safe = all(
        p.reduce_only is True
        and p.confirmation_required is True
        and p.qty > 0
        and math.isfinite(p.qty)
        and p.no_orders_sent is True
        for p in payloads
    ) if payloads else (not cleanup_needed)

    # TASK-014H: source-of-truth gate — close candidates may only come from
    # real_readonly position details.  Fixture/legacy sources never satisfy
    # this gate, blocking execute_ready even if every other gate passes.
    source_is_real = (position_details_source == "real_readonly")

    # ── Execute-ready gate ────────────────────────────────────────────────
    # execute_ready=True only when ALL conditions are satisfied.
    # Even then, no sender is implemented — no_orders_sent remains True.
    execute_ready = bool(
        cleanup_needed
        and snapshot_fresh
        and token_valid
        and payload_safe
        and demo_runtime_verified
        and selected
        and source_is_real
    )

    return CleanupPlan(
        mode=mode,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        current_short_count=short_count,
        current_long_count=long_count,
        current_open_count=open_count,
        target_short_count=MAX_SHORT_POSITIONS,
        target_long_count=MAX_LONG_POSITIONS,
        target_open_count=MAX_OPEN_POSITIONS,
        cleanup_needed=cleanup_needed,
        cleanup_reasons=cleanup_reasons,
        candidate_positions_to_review=all_cands,
        suggested_close_candidates=selected,
        proposed_close_count=len(selected),
        close_payload_previews=payloads,
        snapshot_timestamp_utc=snapshot_timestamp_utc,
        snapshot_fresh=snapshot_fresh,
        snapshot_age_hours=snapshot_age,
        confirmation_required=True,
        confirm_token_expected_pattern=expected_token,
        confirm_token_provided=confirm_token,
        confirm_token_valid=token_valid,
        execute_ready=execute_ready,
        position_details_source=position_details_source,
        source_position_details_is_real=source_is_real,
    )
