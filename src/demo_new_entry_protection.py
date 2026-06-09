"""
src/demo_new_entry_protection.py
TASK-014Q: Demo New-entry Protected Entry / Stop-loss Attachment Policy.

Pure-computation policy module that defines and validates the *protected entry*
lifecycle for Demo new-entry orders.  Until a future TASK-014R adds a real
stop-loss attachment sender, this module ONLY produces PREVIEW plans and
explicitly refuses to allow actual execution of any new entry.

Background (incident chain TASK-014K / L / M / N / O / P):
  * TASK-014L sent a SOLUSDT new-entry order successfully but the position
    came up with stop_price=0 (no stop attached); TASK-014M flagged the
    naked position; TASK-014N's emergency close was required to recover.
  * TASK-014O / TASK-014P closed the stale-price root cause (realtime
    market-price guard + market-backed candidate builder).
  * The remaining gap: the new-entry sender will happily submit an entry
    order WITHOUT attaching a stop-loss.  Until a TASK-014R sender exists
    that attaches the stop after fill (Bybit V5 /v5/position/trading-stop
    or equivalent), no actual --execute-new-entry must be permitted.

Protected entry lifecycle (this module enforces phase 1 + computes the
phase plan; phases 2-6 are reserved for TASK-014R):

  Phase 1 — Pre-entry review (THIS MODULE):
      * review.fail_closed == False
      * review.demo_runtime_verified == True
      * review.proof_strength == STRONG
      * review.endpoint_family == bybit_demo
      * review.account_mode == demo
      * review.position_details_source == real_readonly
      * review.realtime_price_guard_verified == True  (TASK-014O guard)
      * payload.stop_price > 0
      * payload.qty > 0
      * payload.preview_only == True
      * payload.order_sent == False
      * payload.order_endpoint_called == False
      * payload side/qty/entry/stop coherent:
          long  => stop < entry, order_side=Buy
          short => stop > entry, order_side=Sell

  Phase 2 — Entry order (TASK-014L / TASK-014R; NOT this module):
      * Demo endpoint only (/v5/order/create on api-demo.bybit.com)
      * single order, reduceOnly=False, no TP, no leverage change

  Phase 3 — Post-fill verification (TASK-014M):
      * refresh read-only positions; target symbol exists; side/qty match;
        entry_price > 0.

  Phase 4 — Stop attachment (TASK-014R, NOT YET IMPLEMENTED):
      * attach stop-loss via Demo-only /v5/position/trading-stop (allowlist
        defined here as STOP_ATTACH_ENDPOINT but NEVER invoked from this
        module).  long stop below entry; short stop above entry.

  Phase 5 — Final verification (TASK-014R):
      * refresh again; stop_price > 0; missing_stop_price=False;
        reconciliation passes; protected_entry_status=PROTECTED.

  Phase 6 — Failure recovery:
      * entry filled but stop attach fails =>
            fail_closed=True
            new_entry_allowed=False
            recommended_action=emergency_close_preview (TASK-014M / N)

Safety invariants enforced by this module (always):
  * preview_only                  = True
  * stop_loss_endpoint_allowed    = False     (preview phase only)
  * stop_endpoint_called          = False
  * order_endpoint_called         = False
  * no_orders_sent                = True
  * no_position_modified          = True
  * protected_entry_execute_allowed = False
  * no_live_endpoint              = True

This module does NOT:
  * import urllib / requests / httpx
  * read os.environ
  * call HMAC / signing
  * import main / src.risk / BybitExecutor
  * import demo_close_only_sender / demo_new_entry_sender /
    demo_emergency_close_sender / scripts.execute_*
  * touch leverage / transfer / withdraw / deposit / take-profit endpoints
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


# ---------------------------------------------------------------------------
# Endpoint allowlist (DEMO-ONLY; informational — never invoked here)
# ---------------------------------------------------------------------------

# Order-create endpoint — used by TASK-014L sender (NOT this module).
ORDER_CREATE_ENDPOINT       = "/v5/order/create"

# Trading-stop / stop-loss attachment endpoint — RESERVED for TASK-014R.
# Listed here for clarity, but this module MUST NOT invoke it.
STOP_ATTACH_ENDPOINT        = "/v5/position/trading-stop"

# Read-only endpoints used by reconcile / wallet audit / runtime probe
# (TASK-014C / D / E / O).  Listed for documentation.
READ_ONLY_ENDPOINTS: tuple[str, ...] = (
    "/v5/account/wallet-balance",
    "/v5/position/list",
    "/v5/market/tickers",
    "/v5/account/info",
)

# Explicit separation: order-create vs stop attach vs read-only.
ENDPOINT_GROUPS: dict[str, tuple[str, ...]] = {
    "order_create":   (ORDER_CREATE_ENDPOINT,),
    "trading_stop":   (STOP_ATTACH_ENDPOINT,),
    "read_only":      READ_ONLY_ENDPOINTS,
}

DEMO_ENDPOINT_FAMILY        = "bybit_demo"


# ---------------------------------------------------------------------------
# Lifecycle phase + status constants
# ---------------------------------------------------------------------------

PHASE_PRE_ENTRY_REVIEW      = "phase_1_pre_entry_review"
PHASE_ENTRY_ORDER           = "phase_2_entry_order"
PHASE_POST_FILL_VERIFY      = "phase_3_post_fill_verify"
PHASE_STOP_ATTACHMENT       = "phase_4_stop_attachment"
PHASE_FINAL_VERIFY          = "phase_5_final_verify"
PHASE_FAILURE_RECOVERY      = "phase_6_failure_recovery"

PROTECTED_ENTRY_STATUS_PREVIEW_ONLY = "PREVIEW_ONLY"
PROTECTED_ENTRY_STATUS_PROTECTED    = "PROTECTED"
PROTECTED_ENTRY_STATUS_NAKED        = "NAKED"          # forbidden outcome
PROTECTED_ENTRY_STATUS_FAIL_CLOSED  = "FAIL_CLOSED"


# Blocked-reason codes
REASON_REVIEW_FAIL_CLOSED                = "review_fail_closed"
REASON_REVIEW_MISSING_REALTIME_GUARD     = "review_missing_realtime_price_guard"
REASON_REVIEW_PROOF_NOT_STRONG           = "review_proof_not_strong"
REASON_REVIEW_ENDPOINT_NOT_DEMO          = "review_endpoint_not_bybit_demo"
REASON_REVIEW_ACCOUNT_NOT_DEMO           = "review_account_mode_not_demo"
REASON_REVIEW_POSITION_NOT_REAL_READONLY = "review_position_details_source_not_real_readonly"
REASON_REVIEW_DEMO_RUNTIME_NOT_VERIFIED  = "review_demo_runtime_not_verified"
REASON_SYMBOL_MISSING                    = "selected_symbol_missing"
REASON_SYMBOL_NOT_IN_PAYLOAD             = "selected_symbol_not_in_accepted_candidates"
REASON_PAYLOAD_MISSING                   = "selected_symbol_payload_missing"
REASON_PAYLOAD_PREVIEW_ONLY_FALSE        = "payload_preview_only_must_be_true"
REASON_PAYLOAD_ORDER_SENT_TRUE           = "payload_order_sent_must_be_false"
REASON_PAYLOAD_ORDER_ENDPOINT_CALLED     = "payload_order_endpoint_called_must_be_false"
REASON_PAYLOAD_REDUCE_ONLY_TRUE          = "payload_reduce_only_must_be_false"
REASON_PAYLOAD_QTY_NOT_POSITIVE          = "payload_qty_not_positive"
REASON_PAYLOAD_INVALID_SIDE              = "payload_invalid_side"
REASON_PAYLOAD_INVALID_ORDER_SIDE        = "payload_invalid_order_side"
REASON_PAYLOAD_INVALID_ENTRY_PRICE       = "payload_invalid_entry_reference_price"
REASON_MISSING_STOP_PRICE                = "payload_missing_stop_price"
REASON_LONG_STOP_NOT_BELOW_ENTRY         = "long_stop_must_be_below_entry"
REASON_SHORT_STOP_NOT_ABOVE_ENTRY        = "short_stop_must_be_above_entry"

# Always-on policy reason (this task: preview-only; TASK-014R will lift it).
REASON_STOP_ATTACH_NOT_IMPLEMENTED       = "stop_loss_attachment_not_implemented"


# ---------------------------------------------------------------------------
# Required review fields
# ---------------------------------------------------------------------------

_REQUIRED_PROOF_STRENGTH       = "STRONG"
_REQUIRED_ENDPOINT_FAMILY      = "bybit_demo"
_REQUIRED_ACCOUNT_MODE         = "demo"
_REQUIRED_POSITION_SOURCE      = "real_readonly"
_REQUIRED_ORDER_SIDE_FOR_LONG  = "Buy"
_REQUIRED_ORDER_SIDE_FOR_SHORT = "Sell"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProtectedEntryPlan:
    """
    Read-only plan describing the protected-entry lifecycle for one symbol.

    Always preview-only in this task (TASK-014Q).  protected_entry_execute_allowed
    is False unless a future task implements the stop-loss attachment sender.

    Safety invariants (always):
      no_orders_sent           = True
      order_endpoint_called    = False
      stop_endpoint_called     = False
      no_position_modified     = True
      stop_loss_endpoint_allowed = False  (preview phase only)
      preview_only             = True
      no_live_endpoint         = True
      secret_value_observed    = False
    """
    timestamp_utc:                  str
    selected_symbol:                str
    selected_side:                  str       # "long" / "short" / ""
    order_side:                     str       # "Buy" / "Sell" / ""
    selected_qty:                   float
    entry_reference_price:          float
    stop_price:                     float
    stop_order_side:                str       # opposite of order_side
    stop_trigger_direction:         str       # "fall_below_entry" / "rise_above_entry" / ""
    realtime_price_guard_verified:  bool
    review_fail_closed:             bool
    review_timestamp:               str
    blocked_reasons:                list[str]
    lifecycle_phase:                str  = PHASE_PRE_ENTRY_REVIEW
    protected_entry_status:         str  = PROTECTED_ENTRY_STATUS_PREVIEW_ONLY
    stop_loss_attach_required:      bool = True
    stop_loss_endpoint_allowed:     bool = False
    preview_only:                   bool = True
    protected_entry_execute_allowed: bool = False
    protected_entry_execute_reason:  str = REASON_STOP_ATTACH_NOT_IMPLEMENTED
    no_orders_sent:                 bool = True
    order_endpoint_called:          bool = False
    stop_endpoint_called:           bool = False
    no_position_modified:           bool = True
    no_live_endpoint:               bool = True
    secret_value_observed:          bool = False
    order_create_endpoint:          str  = ORDER_CREATE_ENDPOINT
    stop_attach_endpoint:           str  = STOP_ATTACH_ENDPOINT
    endpoint_family:                str  = DEMO_ENDPOINT_FAMILY
    next_required_task:             str  = "TASK-014R_stop_loss_attachment_sender"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                       self.timestamp_utc,
            "timestamp_utc":                   self.timestamp_utc,
            "selected_symbol":                 self.selected_symbol,
            "selected_side":                   self.selected_side,
            "order_side":                      self.order_side,
            "selected_qty":                    self.selected_qty,
            "entry_reference_price":           self.entry_reference_price,
            "stop_price":                      self.stop_price,
            "stop_order_side":                 self.stop_order_side,
            "stop_trigger_direction":          self.stop_trigger_direction,
            "realtime_price_guard_verified":   self.realtime_price_guard_verified,
            "review_fail_closed":              self.review_fail_closed,
            "review_timestamp":                self.review_timestamp,
            "blocked_reasons":                 list(self.blocked_reasons),
            "lifecycle_phase":                 self.lifecycle_phase,
            "protected_entry_status":          self.protected_entry_status,
            "stop_loss_attach_required":       self.stop_loss_attach_required,
            "stop_loss_endpoint_allowed":      self.stop_loss_endpoint_allowed,
            "preview_only":                    self.preview_only,
            "protected_entry_execute_allowed": self.protected_entry_execute_allowed,
            "protected_entry_execute_reason":  self.protected_entry_execute_reason,
            "no_orders_sent":                  self.no_orders_sent,
            "order_endpoint_called":           self.order_endpoint_called,
            "stop_endpoint_called":            self.stop_endpoint_called,
            "no_position_modified":            self.no_position_modified,
            "no_live_endpoint":                self.no_live_endpoint,
            "secret_value_observed":           self.secret_value_observed,
            "order_create_endpoint":           self.order_create_endpoint,
            "stop_attach_endpoint":            self.stop_attach_endpoint,
            "endpoint_family":                 self.endpoint_family,
            "next_required_task":              self.next_required_task,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _find_accepted_payload(
    review: dict[str, Any], symbol: str,
) -> tuple[dict | None, dict | None]:
    """Return (evaluation_dict, payload_dict) when symbol is accepted."""
    if not symbol:
        return None, None
    for ev in review.get("accepted_candidates", []) or []:
        if str(ev.get("symbol", "")) == symbol:
            return ev, ev.get("payload") or None
    return None, None


def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _stop_trigger_direction(side: str) -> str:
    s = (side or "").strip().lower()
    if s == "long":
        return "fall_below_entry"
    if s == "short":
        return "rise_above_entry"
    return ""


def _opposite_order_side(order_side: str) -> str:
    if order_side == "Buy":
        return "Sell"
    if order_side == "Sell":
        return "Buy"
    return ""


# ---------------------------------------------------------------------------
# Plan builder
# ---------------------------------------------------------------------------

def build_protected_entry_plan(
    review:         dict[str, Any],
    symbol:         str,
    timestamp_utc:  str,
) -> ProtectedEntryPlan:
    """
    Build a ProtectedEntryPlan for ``symbol`` from a TASK-014K/O review dict.

    The plan is ALWAYS preview-only: ``protected_entry_execute_allowed`` is
    False unless a future task implements a Demo-only stop-loss attachment
    sender.  The plan records every reason the pre-entry phase fails — the
    caller (CLI or sender G20 gate) inspects ``blocked_reasons`` and
    ``protected_entry_execute_allowed``.
    """
    blocked: list[str] = []

    # Review-level checks ----------------------------------------------------
    review_fail_closed = bool(review.get("fail_closed", True))
    if review_fail_closed:
        blocked.append(REASON_REVIEW_FAIL_CLOSED)

    if not bool(review.get("realtime_price_guard_verified", False)):
        blocked.append(REASON_REVIEW_MISSING_REALTIME_GUARD)

    if not bool(review.get("demo_runtime_verified", False)):
        blocked.append(REASON_REVIEW_DEMO_RUNTIME_NOT_VERIFIED)

    if str(review.get("proof_strength", "")) != _REQUIRED_PROOF_STRENGTH:
        blocked.append(REASON_REVIEW_PROOF_NOT_STRONG)

    if str(review.get("endpoint_family", "")) != _REQUIRED_ENDPOINT_FAMILY:
        blocked.append(REASON_REVIEW_ENDPOINT_NOT_DEMO)

    if str(review.get("account_mode", "")) != _REQUIRED_ACCOUNT_MODE:
        blocked.append(REASON_REVIEW_ACCOUNT_NOT_DEMO)

    if str(review.get("position_details_source", "")) != _REQUIRED_POSITION_SOURCE:
        blocked.append(REASON_REVIEW_POSITION_NOT_REAL_READONLY)

    # Symbol / payload lookup ------------------------------------------------
    if not symbol:
        blocked.append(REASON_SYMBOL_MISSING)
        return _fail_plan(
            review, symbol="", timestamp_utc=timestamp_utc,
            blocked=blocked, review_fail_closed=review_fail_closed,
        )

    ev, payload = _find_accepted_payload(review, symbol)
    if ev is None:
        blocked.append(REASON_SYMBOL_NOT_IN_PAYLOAD)
        return _fail_plan(
            review, symbol=symbol, timestamp_utc=timestamp_utc,
            blocked=blocked, review_fail_closed=review_fail_closed,
        )
    if payload is None:
        blocked.append(REASON_PAYLOAD_MISSING)
        return _fail_plan(
            review, symbol=symbol, timestamp_utc=timestamp_utc,
            blocked=blocked, review_fail_closed=review_fail_closed,
        )

    selected_side = str(ev.get("side", "")).strip().lower()
    if selected_side not in ("long", "short"):
        blocked.append(REASON_PAYLOAD_INVALID_SIDE)

    qty = _safe_float(payload.get("qty", 0.0))
    if qty <= 0:
        blocked.append(REASON_PAYLOAD_QTY_NOT_POSITIVE)

    entry_price = _safe_float(payload.get("entry_reference_price", 0.0))
    if entry_price <= 0:
        blocked.append(REASON_PAYLOAD_INVALID_ENTRY_PRICE)

    stop_price = _safe_float(payload.get("stop_price", 0.0))
    if stop_price <= 0:
        blocked.append(REASON_MISSING_STOP_PRICE)

    order_side = str(payload.get("side", ""))
    if selected_side == "long" and order_side != _REQUIRED_ORDER_SIDE_FOR_LONG:
        blocked.append(REASON_PAYLOAD_INVALID_ORDER_SIDE)
    elif selected_side == "short" and order_side != _REQUIRED_ORDER_SIDE_FOR_SHORT:
        blocked.append(REASON_PAYLOAD_INVALID_ORDER_SIDE)

    if bool(payload.get("reduce_only", True)):
        blocked.append(REASON_PAYLOAD_REDUCE_ONLY_TRUE)
    if not bool(payload.get("preview_only", False)):
        blocked.append(REASON_PAYLOAD_PREVIEW_ONLY_FALSE)
    if bool(payload.get("order_sent", True)):
        blocked.append(REASON_PAYLOAD_ORDER_SENT_TRUE)
    if bool(payload.get("order_endpoint_called", True)):
        blocked.append(REASON_PAYLOAD_ORDER_ENDPOINT_CALLED)

    # Stop direction sanity --------------------------------------------------
    if entry_price > 0 and stop_price > 0:
        if selected_side == "long" and not (stop_price < entry_price):
            blocked.append(REASON_LONG_STOP_NOT_BELOW_ENTRY)
        if selected_side == "short" and not (stop_price > entry_price):
            blocked.append(REASON_SHORT_STOP_NOT_ABOVE_ENTRY)

    # Build plan -------------------------------------------------------------
    status = (PROTECTED_ENTRY_STATUS_FAIL_CLOSED if blocked
              else PROTECTED_ENTRY_STATUS_PREVIEW_ONLY)
    return ProtectedEntryPlan(
        timestamp_utc=timestamp_utc,
        selected_symbol=symbol,
        selected_side=selected_side if selected_side in ("long", "short") else "",
        order_side=order_side if order_side in ("Buy", "Sell") else "",
        selected_qty=qty,
        entry_reference_price=entry_price,
        stop_price=stop_price,
        stop_order_side=_opposite_order_side(order_side),
        stop_trigger_direction=_stop_trigger_direction(selected_side),
        realtime_price_guard_verified=bool(
            review.get("realtime_price_guard_verified", False)
        ),
        review_fail_closed=review_fail_closed,
        review_timestamp=str(review.get("timestamp", "")),
        blocked_reasons=blocked,
        lifecycle_phase=PHASE_PRE_ENTRY_REVIEW,
        protected_entry_status=status,
    )


def _fail_plan(
    review:             dict[str, Any],
    symbol:             str,
    timestamp_utc:      str,
    blocked:            list[str],
    review_fail_closed: bool,
) -> ProtectedEntryPlan:
    """Return a minimally-populated fail-closed plan for early aborts."""
    return ProtectedEntryPlan(
        timestamp_utc=timestamp_utc,
        selected_symbol=symbol,
        selected_side="",
        order_side="",
        selected_qty=0.0,
        entry_reference_price=0.0,
        stop_price=0.0,
        stop_order_side="",
        stop_trigger_direction="",
        realtime_price_guard_verified=bool(
            review.get("realtime_price_guard_verified", False)
        ),
        review_fail_closed=review_fail_closed,
        review_timestamp=str(review.get("timestamp", "")),
        blocked_reasons=blocked,
        lifecycle_phase=PHASE_PRE_ENTRY_REVIEW,
        protected_entry_status=PROTECTED_ENTRY_STATUS_FAIL_CLOSED,
    )


# ---------------------------------------------------------------------------
# Sender-side helper: G20 reason name
# ---------------------------------------------------------------------------

# The TASK-014L sender's actual --execute-new-entry path appends this gate to
# blocked_gates as long as protected entry is not yet implemented.  Naming the
# constant here ensures the sender and the policy module agree.
G20_BLOCKED_GATE_NAME = "protected_entry_policy_missing"


__all__ = [
    "ORDER_CREATE_ENDPOINT",
    "STOP_ATTACH_ENDPOINT",
    "READ_ONLY_ENDPOINTS",
    "ENDPOINT_GROUPS",
    "DEMO_ENDPOINT_FAMILY",
    "PHASE_PRE_ENTRY_REVIEW",
    "PHASE_ENTRY_ORDER",
    "PHASE_POST_FILL_VERIFY",
    "PHASE_STOP_ATTACHMENT",
    "PHASE_FINAL_VERIFY",
    "PHASE_FAILURE_RECOVERY",
    "PROTECTED_ENTRY_STATUS_PREVIEW_ONLY",
    "PROTECTED_ENTRY_STATUS_PROTECTED",
    "PROTECTED_ENTRY_STATUS_NAKED",
    "PROTECTED_ENTRY_STATUS_FAIL_CLOSED",
    "REASON_REVIEW_FAIL_CLOSED",
    "REASON_REVIEW_MISSING_REALTIME_GUARD",
    "REASON_REVIEW_PROOF_NOT_STRONG",
    "REASON_REVIEW_ENDPOINT_NOT_DEMO",
    "REASON_REVIEW_ACCOUNT_NOT_DEMO",
    "REASON_REVIEW_POSITION_NOT_REAL_READONLY",
    "REASON_REVIEW_DEMO_RUNTIME_NOT_VERIFIED",
    "REASON_SYMBOL_MISSING",
    "REASON_SYMBOL_NOT_IN_PAYLOAD",
    "REASON_PAYLOAD_MISSING",
    "REASON_PAYLOAD_PREVIEW_ONLY_FALSE",
    "REASON_PAYLOAD_ORDER_SENT_TRUE",
    "REASON_PAYLOAD_ORDER_ENDPOINT_CALLED",
    "REASON_PAYLOAD_REDUCE_ONLY_TRUE",
    "REASON_PAYLOAD_QTY_NOT_POSITIVE",
    "REASON_PAYLOAD_INVALID_SIDE",
    "REASON_PAYLOAD_INVALID_ORDER_SIDE",
    "REASON_PAYLOAD_INVALID_ENTRY_PRICE",
    "REASON_MISSING_STOP_PRICE",
    "REASON_LONG_STOP_NOT_BELOW_ENTRY",
    "REASON_SHORT_STOP_NOT_ABOVE_ENTRY",
    "REASON_STOP_ATTACH_NOT_IMPLEMENTED",
    "G20_BLOCKED_GATE_NAME",
    "ProtectedEntryPlan",
    "build_protected_entry_plan",
]
