"""
src/demo_new_entry_postfill_verify.py
TASK-014M: Post-fill verification for Demo new-entry orders.

Reads the most recent new-entry execution report and the most recent Demo
read-only smoke snapshot (optionally also the most recent new-entry review)
and re-confirms:

  - the previous execution actually claimed ORDER_SENT
  - the selected symbol now appears in open positions
  - side / qty match the order that was sent
  - entry_price is present and > 0
  - stop_price is present and > 0  (missing_stop_price gate)
  - preview entry_reference_price vs actual entry_price deviation is within
    the configured threshold (stale_price_mismatch gate)

This module is PREVIEW + DIAGNOSTIC ONLY.  It never sends an order, never
posts to any endpoint, never modifies a position, never loads or prints
credentials.  It can OPTIONALLY emit an emergency close-only PREVIEW dict
(reduce_only=True, preview_only=True, order_sent=False) for symbols with
missing_stop_price — actual execution of such a close is intentionally
out of scope.

SAFETY INVARIANTS (structural — verified by tests):
  no_orders_sent          = True   (always)
  order_endpoint_called   = False  (always)
  no_position_modified    = True   (always)
  secret_value_observed   = False  (always)
  no_live_endpoint        = True   (always — module never makes HTTP calls)
  no_close_only_path      = True   (always — never imports close-only sender)
  no_batch_order          = True   (always)

This module does NOT import or modify:
  main.py, src/risk.py, BybitExecutor,
  src/demo_close_only_sender.py, src/demo_new_entry_sender.py,
  scripts/execute_demo_close_only_cleanup.py, scripts/execute_demo_new_entry.py.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Stale price guard: maximum allowed deviation between the preview's
# entry_reference_price and the actual exchange entry_price, expressed
# as |actual - expected| / expected * 100.  Anything strictly greater
# than this raises stale_price_mismatch.
STALE_PRICE_DEVIATION_THRESHOLD_PCT = 5.0

# Quantity tolerance: |actual - expected| / expected.  Anything strictly
# greater than this raises qty_mismatch.  Set tight; Bybit Market fills
# are usually exact for the IOC qty we send.
QTY_MISMATCH_TOLERANCE_PCT = 1.0

# Recommended action labels
ACTION_MANUAL_UI       = "manual_close_or_add_stop_in_bybit_demo_ui"
ACTION_EMERGENCY_PREV  = "emergency_close_preview"
ACTION_NONE_REQUIRED   = "none_required"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class PostFillVerificationResult:
    """
    Post-fill verification outcome.

    fail_closed = True when ANY of the following is true:
        - execution file missing / not ORDER_SENT
        - read-only smoke missing / fail_closed
        - position not found in live snapshot
        - actual qty / side mismatch
        - missing_stop_price
        - stale_price_mismatch

    new_entry_allowed = False whenever fail_closed = True (and remains False
    even on PASS until the next reconciliation explicitly re-allows it; this
    module never sets it to True).
    """
    timestamp_utc: str

    # Input provenance
    execution_loaded:    bool = False
    readonly_loaded:     bool = False
    review_loaded:       bool = False
    execution_timestamp: str  = ""
    readonly_timestamp:  str  = ""
    review_timestamp:    str  = ""

    # Selected execution context
    last_execution_status:  str   = ""
    selected_symbol:        str   = ""
    expected_side:          str   = ""    # "long" / "short"
    expected_order_side:    str   = ""    # "Buy" / "Sell"
    expected_qty:           float = 0.0
    expected_entry_reference_price: float = 0.0

    # Live observation (from latest_smoke.json positions[])
    position_found:    bool  = False
    actual_side:       str   = ""
    actual_qty:        float = 0.0
    actual_entry_price: float = 0.0
    actual_stop_price:  float = 0.0

    # Deviation analysis
    qty_mismatch:              bool  = False
    side_mismatch:             bool  = False
    entry_price_deviation_pct: float = 0.0
    stale_price_mismatch:      bool  = False
    missing_stop_price:        bool  = False
    stale_price_threshold_pct: float = STALE_PRICE_DEVIATION_THRESHOLD_PCT

    # Gate outcomes
    new_entry_allowed:  bool      = False
    fail_closed:        bool      = True
    fail_closed_reasons: list[str] = field(default_factory=list)
    recommended_action: str       = ACTION_MANUAL_UI

    # Optional emergency close-only preview (preview only, not executed)
    emergency_close_preview: dict[str, Any] | None = None

    # Structural safety invariants — always these values
    no_orders_sent:         bool = True
    order_endpoint_called:  bool = False
    no_position_modified:   bool = True
    secret_value_observed:  bool = False
    no_live_endpoint:       bool = True
    no_close_only_path:     bool = True
    no_batch_order:         bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                        self.timestamp_utc,
            "timestamp_utc":                    self.timestamp_utc,
            "mode":                             "postfill_verify",
            "execution_loaded":                 self.execution_loaded,
            "readonly_loaded":                  self.readonly_loaded,
            "review_loaded":                    self.review_loaded,
            "execution_timestamp":              self.execution_timestamp,
            "readonly_timestamp":               self.readonly_timestamp,
            "review_timestamp":                 self.review_timestamp,
            "last_execution_status":            self.last_execution_status,
            "selected_symbol":                  self.selected_symbol,
            "expected_side":                    self.expected_side,
            "expected_order_side":              self.expected_order_side,
            "expected_qty":                     self.expected_qty,
            "expected_entry_reference_price":   self.expected_entry_reference_price,
            "position_found":                   self.position_found,
            "actual_side":                      self.actual_side,
            "actual_qty":                       self.actual_qty,
            "actual_entry_price":               self.actual_entry_price,
            "actual_stop_price":                self.actual_stop_price,
            "qty_mismatch":                     self.qty_mismatch,
            "side_mismatch":                    self.side_mismatch,
            "entry_price_deviation_pct":        round(self.entry_price_deviation_pct, 4),
            "stale_price_mismatch":             self.stale_price_mismatch,
            "missing_stop_price":               self.missing_stop_price,
            "stale_price_threshold_pct":        self.stale_price_threshold_pct,
            "new_entry_allowed":                self.new_entry_allowed,
            "fail_closed":                      self.fail_closed,
            "fail_closed_reasons":              list(self.fail_closed_reasons),
            "recommended_action":               self.recommended_action,
            "emergency_close_preview":          self.emergency_close_preview,
            "no_orders_sent":                   self.no_orders_sent,
            "order_endpoint_called":            self.order_endpoint_called,
            "no_position_modified":             self.no_position_modified,
            "secret_value_observed":            self.secret_value_observed,
            "no_live_endpoint":                 self.no_live_endpoint,
            "no_close_only_path":               self.no_close_only_path,
            "no_batch_order":                   self.no_batch_order,
        }


# ---------------------------------------------------------------------------
# Status normalisation
# ---------------------------------------------------------------------------

def _derive_execution_status(execution: dict[str, Any]) -> str:
    """Compute the human-readable status of an execution result dict."""
    if not isinstance(execution, dict):
        return ""
    if bool(execution.get("order_sent", False)):
        return "ORDER_SENT"
    if bool(execution.get("execute_allowed", False)) and \
       not bool(execution.get("execute_requested", False)):
        return "DRY_RUN_EXECUTE_ALLOWED"
    if bool(execution.get("execute_allowed", False)) and \
       bool(execution.get("execute_requested", False)) and \
       not bool(execution.get("order_sent", False)):
        return "EXECUTE_FAILED_AT_EXCHANGE"
    return "BLOCKED"


# ---------------------------------------------------------------------------
# Position lookup
# ---------------------------------------------------------------------------

def _find_position(
    readonly_snapshot: dict[str, Any],
    symbol:            str,
) -> dict[str, Any] | None:
    """Return the first matching position dict, or None."""
    if not symbol:
        return None
    positions = readonly_snapshot.get("positions", []) or []
    for pos in positions:
        if str(pos.get("symbol", "")) == symbol:
            return pos
    return None


# ---------------------------------------------------------------------------
# Review lookup
# ---------------------------------------------------------------------------

def _find_review_entry_price(
    review: dict[str, Any] | None,
    symbol: str,
) -> float:
    """Return the preview entry_reference_price for `symbol`, or 0.0."""
    if review is None or not symbol:
        return 0.0
    for ev in review.get("accepted_candidates", []) or []:
        if str(ev.get("symbol", "")) == symbol:
            payload = ev.get("payload") or {}
            try:
                return float(payload.get("entry_reference_price", 0.0) or 0.0)
            except (TypeError, ValueError):
                return 0.0
    # Also try raw payload_preview list (alternate name in some reports)
    for payload in review.get("payload_preview", []) or []:
        if str(payload.get("symbol", "")) == symbol:
            try:
                return float(payload.get("entry_reference_price", 0.0) or 0.0)
            except (TypeError, ValueError):
                return 0.0
    return 0.0


# ---------------------------------------------------------------------------
# Emergency close-only preview
# ---------------------------------------------------------------------------

def make_emergency_close_preview(
    symbol:     str,
    side:       str,    # actual position side: "long" or "short"
    qty:        float,
    entry_price: float = 0.0,
    reason:     str   = "missing_stop_price",
) -> dict[str, Any]:
    """
    Build a preview dict describing an emergency close-only order.

    This function NEVER submits the order; the caller is responsible for any
    follow-up.  The returned dict carries reduce_only=True, preview_only=True,
    order_sent=False, order_endpoint_called=False, confirmation_required=True,
    no_orders_sent=True so the structure is self-documenting.

    The order side is the *opposite* of the position side:
        long  -> Sell
        short -> Buy
    """
    s = (side or "").strip().lower()
    if s == "long":
        close_order_side = "Sell"
    elif s == "short":
        close_order_side = "Buy"
    else:
        close_order_side = ""
    try:
        q = float(qty)
    except (TypeError, ValueError):
        q = 0.0
    try:
        ep = float(entry_price)
    except (TypeError, ValueError):
        ep = 0.0
    return {
        "symbol":                  symbol,
        "position_side":           s,
        "close_order_side":        close_order_side,
        "order_type":              "Market",
        "qty":                     q,
        "reference_entry_price":   ep,
        "reduce_only":             True,
        "preview_only":            True,
        "confirmation_required":   True,
        "order_sent":              False,
        "order_endpoint_called":   False,
        "no_orders_sent":          True,
        "no_position_modified":    True,
        "reason":                  reason,
        "next_required_task":      "TASK-014N_emergency_missing_stop_close_only_sender",
    }


# ---------------------------------------------------------------------------
# Public API
# ---------------------------------------------------------------------------

def verify_postfill(
    execution:          dict[str, Any] | None,
    readonly_snapshot:  dict[str, Any] | None,
    review:             dict[str, Any] | None = None,
    *,
    stale_price_threshold_pct: float = STALE_PRICE_DEVIATION_THRESHOLD_PCT,
    qty_tolerance_pct:         float = QTY_MISMATCH_TOLERANCE_PCT,
    emit_emergency_close_preview: bool = False,
    now: datetime | None = None,
) -> PostFillVerificationResult:
    """
    Verify the most-recent Demo new-entry order against the most-recent
    Demo read-only snapshot.

    `execution`         : parsed latest_new_entry_execution.json (or None).
    `readonly_snapshot` : parsed latest_smoke.json               (or None).
    `review`            : parsed latest_new_entry_review.json    (or None — when
                          absent the stale-price check falls back to
                          stale_price_mismatch=False with an explanatory
                          fail-reason that the review file is missing).
    """
    ts_utc = (now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
    result = PostFillVerificationResult(
        timestamp_utc=ts_utc,
        stale_price_threshold_pct=stale_price_threshold_pct,
    )
    reasons: list[str] = []

    # ------------------------------------------------------------------
    # Input loading
    # ------------------------------------------------------------------
    if not isinstance(execution, dict) or not execution:
        reasons.append("execution_report_missing")
        result.fail_closed         = True
        result.fail_closed_reasons = reasons
        result.recommended_action  = ACTION_MANUAL_UI
        return result
    result.execution_loaded    = True
    result.execution_timestamp = str(execution.get("timestamp_utc",
                                          execution.get("timestamp", "")))

    if not isinstance(readonly_snapshot, dict) or not readonly_snapshot:
        reasons.append("readonly_snapshot_missing")
        result.fail_closed         = True
        result.fail_closed_reasons = reasons
        result.recommended_action  = ACTION_MANUAL_UI
        return result
    result.readonly_loaded    = True
    result.readonly_timestamp = str(readonly_snapshot.get("run_timestamp_utc",
                                          readonly_snapshot.get("timestamp", "")))

    if isinstance(review, dict) and review:
        result.review_loaded    = True
        result.review_timestamp = str(review.get("timestamp", ""))

    # ------------------------------------------------------------------
    # Last execution status
    # ------------------------------------------------------------------
    status = _derive_execution_status(execution)
    result.last_execution_status = status

    selected_symbol = str(execution.get("selected_symbol", ""))
    result.selected_symbol      = selected_symbol
    result.expected_side        = str(execution.get("selected_side", ""))
    result.expected_order_side  = str(execution.get("order_side", ""))
    try:
        result.expected_qty = float(execution.get("selected_qty", 0.0) or 0.0)
    except (TypeError, ValueError):
        result.expected_qty = 0.0

    result.expected_entry_reference_price = _find_review_entry_price(
        review, selected_symbol,
    )

    if status != "ORDER_SENT":
        reasons.append(f"last_execution_status_not_order_sent:{status}")
        result.fail_closed         = True
        result.fail_closed_reasons = reasons
        result.recommended_action  = ACTION_NONE_REQUIRED if status == "BLOCKED" \
                                     else ACTION_MANUAL_UI
        return result

    if not selected_symbol:
        reasons.append("execution_missing_selected_symbol")
        result.fail_closed         = True
        result.fail_closed_reasons = reasons
        result.recommended_action  = ACTION_MANUAL_UI
        return result

    # ------------------------------------------------------------------
    # Readonly snapshot health
    # ------------------------------------------------------------------
    if bool(readonly_snapshot.get("fail_closed", False)):
        reasons.append("readonly_snapshot_fail_closed")
    if not bool(readonly_snapshot.get("demo_runtime_verified", False)):
        reasons.append("readonly_demo_runtime_not_verified")

    # ------------------------------------------------------------------
    # Position lookup + side / qty / price / stop validation
    # ------------------------------------------------------------------
    position = _find_position(readonly_snapshot, selected_symbol)
    if position is None:
        reasons.append(f"position_not_found_after_fill:{selected_symbol}")
        result.fail_closed         = True
        result.fail_closed_reasons = reasons
        result.recommended_action  = ACTION_MANUAL_UI
        return result

    result.position_found = True
    actual_side  = str(position.get("side", "")).strip().lower()
    try:
        actual_qty   = float(position.get("quantity", 0.0) or 0.0)
    except (TypeError, ValueError):
        actual_qty = 0.0
    try:
        entry_price  = float(position.get("entry_price", 0.0) or 0.0)
    except (TypeError, ValueError):
        entry_price = 0.0
    try:
        stop_price   = float(position.get("stop_price", 0.0) or 0.0)
    except (TypeError, ValueError):
        stop_price = 0.0
    result.actual_side       = actual_side
    result.actual_qty        = actual_qty
    result.actual_entry_price = entry_price
    result.actual_stop_price  = stop_price

    # Side mismatch
    expected_side = result.expected_side.strip().lower()
    if expected_side and actual_side and actual_side != expected_side:
        result.side_mismatch = True
        reasons.append(
            f"side_mismatch:expected={expected_side},actual={actual_side}"
        )

    # Qty mismatch (relative tolerance against expected)
    if result.expected_qty > 0:
        rel = abs(actual_qty - result.expected_qty) / result.expected_qty * 100.0
        if rel > qty_tolerance_pct:
            result.qty_mismatch = True
            reasons.append(
                f"qty_mismatch:expected={result.expected_qty},"
                f"actual={actual_qty},rel_pct={rel:.2f}"
            )
    elif actual_qty > 0:
        # We sent something but execution report didn't carry qty — log it.
        reasons.append("execution_missing_expected_qty")

    # Entry price present
    if entry_price <= 0:
        reasons.append("actual_entry_price_non_positive")

    # Stop price present (the headline TASK-014M gate)
    if stop_price <= 0:
        result.missing_stop_price = True
        reasons.append("missing_stop_price")

    # Stale-price mismatch (preview vs actual)
    expected_entry = result.expected_entry_reference_price
    if expected_entry > 0 and entry_price > 0:
        dev_pct = abs(entry_price - expected_entry) / expected_entry * 100.0
        result.entry_price_deviation_pct = dev_pct
        if dev_pct > stale_price_threshold_pct:
            result.stale_price_mismatch = True
            reasons.append(
                f"stale_price_mismatch:"
                f"expected={expected_entry:.4f},actual={entry_price:.4f},"
                f"dev_pct={dev_pct:.2f}>{stale_price_threshold_pct:.2f}"
            )
    elif expected_entry <= 0:
        # Cannot compute deviation without a preview anchor price.
        reasons.append("review_entry_reference_price_unavailable")

    # ------------------------------------------------------------------
    # Resolve fail_closed + recommended_action
    # ------------------------------------------------------------------
    result.fail_closed         = bool(reasons)
    result.fail_closed_reasons = reasons
    result.new_entry_allowed   = False  # Never True from this module.

    if emit_emergency_close_preview and result.missing_stop_price and \
       result.position_found:
        result.emergency_close_preview = make_emergency_close_preview(
            symbol=selected_symbol,
            side=actual_side,
            qty=actual_qty,
            entry_price=entry_price,
            reason="missing_stop_price",
        )
        result.recommended_action = ACTION_EMERGENCY_PREV
    elif result.missing_stop_price or result.stale_price_mismatch:
        result.recommended_action = ACTION_MANUAL_UI
    elif result.fail_closed:
        result.recommended_action = ACTION_MANUAL_UI
    else:
        result.recommended_action = ACTION_NONE_REQUIRED

    return result
