"""
src/demo_new_entry_candidate_builder.py
TASK-014P — Demo new-entry market-backed candidate builder.

Produces NewEntryCandidate objects whose entry_reference_price equals
the realtime market price (not a stale fixture price), with stop_price
derived from a static stop_pct model and rounded to the instrument's
tick_size.

Pure computation:
  - no network calls (the caller supplies RealtimeMarketPrice via the
    TASK-014O DemoMarketPriceGuard.fetch_market_prices() pipeline);
  - no order endpoints;
  - no secrets, no env reads;
  - no fallback to stale fixture prices.

Used by scripts/preview_demo_new_entry_review.py to ensure candidate
entry_reference_price is anchored to the realtime market price BEFORE
the TASK-014O realtime price guard runs — so when the live market is
available the resulting payloads can carry
realtime_price_guard_verified=True and pass TASK-014L sender G19.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from src.demo_instrument_rules import InstrumentRules, round_price_to_tick
from src.demo_market_price_guard import RealtimeMarketPrice
from src.demo_new_entry_review import NewEntryCandidate


# ---------------------------------------------------------------------------
# Stop model constants (TASK-014P)
# ---------------------------------------------------------------------------
# Stop-loss percentage applied to the realtime market price.  The same
# constant is used for both long and short by default, but the two are
# kept as separate symbols so they can diverge in a later workorder
# without breaking the public surface.
DEFAULT_LONG_STOP_PCT:  float = 0.05  # 5% below realtime price for long
DEFAULT_SHORT_STOP_PCT: float = 0.05  # 5% above realtime price for short

# Skip reasons (TASK-014P) — never leak fixture prices upstream.
SKIP_NO_REALTIME_PRICE       = "no_realtime_price"
SKIP_INVALID_REALTIME_PRICE  = "invalid_realtime_price"
SKIP_INVALID_SIDE            = "invalid_side"
SKIP_MISSING_INSTRUMENT_RULE = "missing_instrument_rule"
SKIP_INVALID_STOP_PRICE      = "invalid_stop_price"
SKIP_INVALID_STOP_DISTANCE   = "invalid_stop_distance"
SKIP_INVALID_RISK_USD        = "invalid_requested_risk_usd"
SKIP_INVALID_STOP_PCT        = "invalid_stop_pct"


# ---------------------------------------------------------------------------
# Input intent
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class NewEntryIntent:
    """
    A pre-pricing trade intent.  The builder pairs an intent with a realtime
    market price to produce a NewEntryCandidate; the intent itself carries
    no entry or stop price (those are derived).
    """
    symbol:             str
    side:               str    # "long" or "short" (case-insensitive)
    requested_risk_usd: float
    score:              float = 0.0
    order_type:         str   = "Market"


# ---------------------------------------------------------------------------
# Build result
# ---------------------------------------------------------------------------

@dataclass(frozen=True)
class CandidateBuildResult:
    """
    One result per input intent.  When skipped, `candidate` is None and
    `skip_reason` carries the failure mode; when built, `candidate` carries
    a NewEntryCandidate whose entry_reference_price == realtime_market_price.
    """
    intent:                NewEntryIntent
    candidate:             NewEntryCandidate | None
    skipped:               bool
    skip_reason:           str
    realtime_market_price: float    # 0.0 when skipped due to missing/invalid price
    price_source:          str      # "" when skipped pre-price
    price_timestamp_utc:   str
    long_stop_pct:         float
    short_stop_pct:        float
    rounded_stop_price:    float    # 0.0 when skipped

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol":                self.intent.symbol,
            "side":                  self.intent.side,
            "requested_risk_usd":    self.intent.requested_risk_usd,
            "score":                 self.intent.score,
            "skipped":               self.skipped,
            "skip_reason":           self.skip_reason,
            "realtime_market_price": self.realtime_market_price,
            "price_source":          self.price_source,
            "price_timestamp_utc":   self.price_timestamp_utc,
            "long_stop_pct":         self.long_stop_pct,
            "short_stop_pct":        self.short_stop_pct,
            "candidate_entry_reference_price": (
                self.candidate.entry_reference_price if self.candidate else 0.0
            ),
            "candidate_stop_price": (
                self.candidate.stop_price if self.candidate else 0.0
            ),
            "rounded_stop_price":    self.rounded_stop_price,
        }


# ---------------------------------------------------------------------------
# Internal helpers
# ---------------------------------------------------------------------------

def _norm_side(side: str) -> str:
    s = (side or "").strip().lower()
    return s if s in ("long", "short") else ""


def _is_finite_positive(x: float) -> bool:
    import math
    return isinstance(x, (int, float)) and math.isfinite(x) and x > 0


# ---------------------------------------------------------------------------
# Public API — single intent
# ---------------------------------------------------------------------------

def build_market_backed_candidate(
    intent:           NewEntryIntent,
    market_price:     RealtimeMarketPrice | None,
    instrument_rule:  InstrumentRules | None,
    long_stop_pct:    float = DEFAULT_LONG_STOP_PCT,
    short_stop_pct:   float = DEFAULT_SHORT_STOP_PCT,
) -> CandidateBuildResult:
    """
    Build a NewEntryCandidate anchored to the realtime market price.

    Fail-closed semantics:
      - market_price is None  → SKIP_NO_REALTIME_PRICE
      - market_price unusable → SKIP_INVALID_REALTIME_PRICE
      - intent.side invalid   → SKIP_INVALID_SIDE
      - rule missing          → SKIP_MISSING_INSTRUMENT_RULE
      - stop_pct invalid (<=0 or >=1) → SKIP_INVALID_STOP_PCT
      - requested_risk_usd <=0 / NaN → SKIP_INVALID_RISK_USD
      - rounded stop <=0 or non-finite → SKIP_INVALID_STOP_PRICE
      - rounded |entry-stop|<=0       → SKIP_INVALID_STOP_DISTANCE

    NEVER falls back to a fixture price.
    """
    side = _norm_side(intent.side)

    if not _is_finite_positive(intent.requested_risk_usd):
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_INVALID_RISK_USD,
            realtime_market_price=0.0,
            price_source="", price_timestamp_utc="",
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=0.0,
        )

    if market_price is None:
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_NO_REALTIME_PRICE,
            realtime_market_price=0.0,
            price_source="", price_timestamp_utc="",
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=0.0,
        )

    if not market_price.is_usable():
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_INVALID_REALTIME_PRICE,
            realtime_market_price=float(market_price.realtime_market_price),
            price_source=market_price.price_source,
            price_timestamp_utc=market_price.price_timestamp_utc,
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=0.0,
        )

    if not side:
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_INVALID_SIDE,
            realtime_market_price=market_price.realtime_market_price,
            price_source=market_price.price_source,
            price_timestamp_utc=market_price.price_timestamp_utc,
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=0.0,
        )

    if instrument_rule is None:
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_MISSING_INSTRUMENT_RULE,
            realtime_market_price=market_price.realtime_market_price,
            price_source=market_price.price_source,
            price_timestamp_utc=market_price.price_timestamp_utc,
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=0.0,
        )

    stop_pct = long_stop_pct if side == "long" else short_stop_pct
    if not (_is_finite_positive(stop_pct) and stop_pct < 1.0):
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_INVALID_STOP_PCT,
            realtime_market_price=market_price.realtime_market_price,
            price_source=market_price.price_source,
            price_timestamp_utc=market_price.price_timestamp_utc,
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=0.0,
        )

    rt = float(market_price.realtime_market_price)
    raw_stop = (
        rt * (1.0 - stop_pct) if side == "long"
        else rt * (1.0 + stop_pct)
    )
    rounded_stop = round_price_to_tick(raw_stop, instrument_rule.tick_size)
    rounded_entry = round_price_to_tick(rt, instrument_rule.tick_size)

    if rounded_stop <= 0.0 or rounded_entry <= 0.0:
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_INVALID_STOP_PRICE,
            realtime_market_price=rt,
            price_source=market_price.price_source,
            price_timestamp_utc=market_price.price_timestamp_utc,
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=rounded_stop,
        )

    # Verify stop is on the protective side of entry AND has non-zero distance
    # after tick rounding.  For very low-priced symbols a 5% move can collapse
    # into the same tick — guard catches that.
    if side == "long" and not (rounded_stop < rounded_entry):
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_INVALID_STOP_DISTANCE,
            realtime_market_price=rt,
            price_source=market_price.price_source,
            price_timestamp_utc=market_price.price_timestamp_utc,
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=rounded_stop,
        )
    if side == "short" and not (rounded_stop > rounded_entry):
        return CandidateBuildResult(
            intent=intent, candidate=None, skipped=True,
            skip_reason=SKIP_INVALID_STOP_DISTANCE,
            realtime_market_price=rt,
            price_source=market_price.price_source,
            price_timestamp_utc=market_price.price_timestamp_utc,
            long_stop_pct=long_stop_pct, short_stop_pct=short_stop_pct,
            rounded_stop_price=rounded_stop,
        )

    # entry_reference_price uses the raw realtime price (review module also
    # rounds it internally to tick — keeping the unrounded value here lets
    # the downstream price guard see the exact realtime reading).
    candidate = NewEntryCandidate(
        symbol=intent.symbol,
        side=side,
        entry_reference_price=rt,
        stop_price=rounded_stop,
        requested_risk_usd=float(intent.requested_risk_usd),
        score=float(intent.score),
        order_type=intent.order_type or "Market",
    )
    return CandidateBuildResult(
        intent=intent,
        candidate=candidate,
        skipped=False,
        skip_reason="",
        realtime_market_price=rt,
        price_source=market_price.price_source,
        price_timestamp_utc=market_price.price_timestamp_utc,
        long_stop_pct=long_stop_pct,
        short_stop_pct=short_stop_pct,
        rounded_stop_price=rounded_stop,
    )


# ---------------------------------------------------------------------------
# Public API — batch
# ---------------------------------------------------------------------------

def build_market_backed_candidates(
    intents:          list[NewEntryIntent],
    market_prices:    dict[str, RealtimeMarketPrice],
    instrument_rules: dict[str, InstrumentRules],
    long_stop_pct:    float = DEFAULT_LONG_STOP_PCT,
    short_stop_pct:   float = DEFAULT_SHORT_STOP_PCT,
) -> list[CandidateBuildResult]:
    """Batch helper.  Pure function — no I/O.  Order preserves input order."""
    results: list[CandidateBuildResult] = []
    for intent in intents:
        results.append(build_market_backed_candidate(
            intent=intent,
            market_price=market_prices.get(intent.symbol),
            instrument_rule=instrument_rules.get(intent.symbol),
            long_stop_pct=long_stop_pct,
            short_stop_pct=short_stop_pct,
        ))
    return results
