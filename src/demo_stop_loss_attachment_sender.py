"""
src/demo_stop_loss_attachment_sender.py
TASK-014R: Demo Stop-loss Attachment Sender / Trading Stop Dry-run.

Pure-computation / mock-safe sender that prepares a Bybit V5 trading-stop
PAYLOAD PREVIEW from a TASK-014Q ProtectedEntryPlan and either:

  * reports it as DRY-RUN (default) — no network at all; or
  * MOCK-executes (--mock-execute-stop) — still no network at all, but emits
    a synthetic success envelope so the report pipeline / gate machinery /
    downstream tooling can be exercised end-to-end.

This module DOES NOT (enforced by source-scan tests):
  * import urllib / requests / httpx
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor
  * import demo_close_only_sender / demo_new_entry_sender /
    demo_emergency_close_sender / scripts.execute_*
  * invoke the order-create endpoint (/v5/order/create)
  * invoke the trading-stop endpoint (/v5/position/trading-stop) — even in
    --mock-execute-stop mode, the endpoint string is recorded but never
    contacted; mock_stop_attached is purely synthetic
  * touch leverage / transfer / withdraw / deposit / take-profit endpoints
  * batch orders
  * close positions

Background (TASK-014K -> TASK-014Q):
  TASK-014L sender remained blocked at G20 (protected_entry_policy_missing)
  because attaching the stop-loss after fill was never implemented and a
  prior smoke run produced a naked SOLUSDT position requiring TASK-014N
  emergency close.  TASK-014Q produced a preview-only protection plan
  (stop_loss_attach_required=True, stop_loss_endpoint_allowed=False,
  protected_entry_execute_allowed=False reason=stop_loss_attachment_not_implemented).

This module is the first concrete step toward closing that gap, but it is
intentionally restricted to dry-run / mock execution — no real attach.  A
future TASK-014S orchestrator will chain entry-submit + stop-attach.

Confirm-token pattern (only required for --mock-execute-stop):
  CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD  (today UTC)

Inputs:
  protection: dict matching outputs/demo_trading/new_entry_protection/
              latest_new_entry_protection.json (ProtectedEntryPlan.to_dict()).
  symbol:     CLI --symbol (must match protection.selected_symbol).
  confirm_token: only validated when mock_execute_stop=True.
  mock_execute_stop: bool — when True, status becomes MOCK_STOP_ATTACH_SUCCESS
                    AND mock_stop_attached=True, but no network call is made.

Outputs:
  StopAttachmentResult dataclass (.to_dict()).
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Endpoint allowlist (DEMO-ONLY; informational — never invoked here)
# ---------------------------------------------------------------------------

# Trading-stop / stop-loss attachment endpoint.  Recorded for the payload
# preview ONLY; this module never opens a socket to this endpoint, nor any
# other endpoint, even under --mock-execute-stop.
STOP_ATTACH_ENDPOINT      = "/v5/position/trading-stop"

# Order-create endpoint — used by TASK-014L sender (NOT this module).
ORDER_CREATE_ENDPOINT     = "/v5/order/create"

# Demo endpoint family (informational; this module makes no network calls).
DEMO_ENDPOINT_FAMILY      = "bybit_demo"

# Bybit V5 trading-stop body invariants for protected new-entry stops.
TPSL_MODE_FULL            = "Full"
SL_TRIGGER_BY_DEFAULT     = "MarkPrice"   # constant; documented choice
CATEGORY_LINEAR           = "linear"
POSITION_IDX_ONE_WAY      = 0


# ---------------------------------------------------------------------------
# Status / reason codes
# ---------------------------------------------------------------------------

STATUS_DRY_RUN_ALLOWED      = "DRY_RUN_STOP_ATTACH_ALLOWED"
STATUS_DRY_RUN_BLOCKED      = "DRY_RUN_STOP_ATTACH_BLOCKED"
STATUS_MOCK_SUCCESS         = "MOCK_STOP_ATTACH_SUCCESS"
STATUS_MOCK_BLOCKED         = "MOCK_STOP_ATTACH_BLOCKED"
STATUS_FAIL_CLOSED          = "FAIL_CLOSED"

GATE_PROTECTION_REPORT_MISSING                = "protection_report_missing"
GATE_SELECTED_SYMBOL_MISMATCH                 = "selected_symbol_mismatch"
GATE_REVIEW_FAIL_CLOSED                       = "review_fail_closed"
GATE_MISSING_REALTIME_PRICE_GUARD             = "missing_realtime_price_guard"
GATE_STOP_LOSS_ATTACH_NOT_REQUIRED            = "stop_loss_attach_not_required"
GATE_UNEXPECTED_STOP_LOSS_ENDPOINT_ALLOWED    = "unexpected_stop_loss_endpoint_allowed"
GATE_UNEXPECTED_PROTECTED_ENTRY_EXECUTE       = "unexpected_protected_entry_execute_allowed"
GATE_INVALID_SIDE                             = "invalid_side"
GATE_INVALID_QTY                              = "invalid_qty"
GATE_INVALID_ENTRY_REFERENCE_PRICE            = "invalid_entry_reference_price"
GATE_MISSING_STOP_PRICE                       = "missing_stop_price"
GATE_LONG_STOP_NOT_BELOW_ENTRY                = "long_stop_must_be_below_entry"
GATE_SHORT_STOP_NOT_ABOVE_ENTRY               = "short_stop_must_be_above_entry"
GATE_INVALID_STOP_ORDER_SIDE                  = "invalid_stop_order_side"
GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK           = "invalid_confirm_token_for_mock_execute"
GATE_PROTECTION_PREVIEW_ONLY_FALSE            = "protection_preview_only_must_be_true"
GATE_PROTECTION_STATUS_NOT_PREVIEW_ONLY       = "protection_status_not_preview_only"
GATE_ORDER_ENDPOINT_CALLED_TRUE               = "protection_order_endpoint_called_must_be_false"
GATE_STOP_ENDPOINT_CALLED_TRUE                = "protection_stop_endpoint_called_must_be_false"


# Token pattern: CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD  (today UTC)
_TOKEN_PREFIX = "CONFIRM_DEMO_STOP_ATTACH_"

# Side mapping: long position closed via Sell; short position closed via Buy.
_REQUIRED_STOP_SIDE_FOR_LONG  = "Sell"
_REQUIRED_STOP_SIDE_FOR_SHORT = "Buy"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class StopAttachmentResult:
    """
    Read-only result of a Demo stop-loss attachment dry-run / mock execution.

    Safety invariants (always; enforced by tests):
      stop_endpoint_called      = False
      order_endpoint_called     = False
      no_orders_sent            = True
      no_position_modified      = True
      no_live_endpoint          = True
      secret_value_observed     = False
      payload_preview_only      = True (when payload built; False on early abort)
    """
    timestamp_utc:              str
    mode:                       str             # "dry_run" / "mock_execute_stop"
    selected_symbol:            str
    selected_side:              str             # "long" / "short" / ""
    qty:                        float
    entry_reference_price:      float
    stop_price:                 float
    stop_order_side:            str             # "Buy" / "Sell" / ""
    stop_trigger_direction:     str
    confirm_token_prefix:       str             # never the full token
    confirm_token_valid:        bool

    # Endpoint metadata (recorded but not contacted)
    endpoint_family:            str  = DEMO_ENDPOINT_FAMILY
    stop_attach_endpoint:       str  = STOP_ATTACH_ENDPOINT

    # Payload preview (Bybit V5 trading-stop body shape) -- never sent
    payload_preview:            dict = field(default_factory=dict)
    payload_preview_only:       bool = False

    # Execution gates
    execute_requested:          bool = False
    mock_execute_requested:     bool = False
    mock_stop_attached:         bool = False
    mock_response:              dict = field(default_factory=dict)

    # Safety invariants (always True after build)
    stop_endpoint_called:       bool = False
    order_endpoint_called:      bool = False
    no_orders_sent:             bool = True
    no_position_modified:       bool = True
    no_live_endpoint:           bool = True
    no_batch_order:             bool = True
    no_close_only_path:         bool = True
    secret_value_observed:      bool = False

    blocked_gates:              list[str] = field(default_factory=list)
    status:                     str       = STATUS_FAIL_CLOSED
    next_required_task:         str       = "TASK-014S_protected_new_entry_orchestrator"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                  self.timestamp_utc,
            "timestamp_utc":              self.timestamp_utc,
            "mode":                       self.mode,
            "selected_symbol":            self.selected_symbol,
            "selected_side":              self.selected_side,
            "qty":                        self.qty,
            "entry_reference_price":      self.entry_reference_price,
            "stop_price":                 self.stop_price,
            "stop_order_side":            self.stop_order_side,
            "stop_trigger_direction":     self.stop_trigger_direction,
            "confirm_token_prefix":       self.confirm_token_prefix,
            "confirm_token_valid":        self.confirm_token_valid,
            "endpoint_family":            self.endpoint_family,
            "stop_attach_endpoint":       self.stop_attach_endpoint,
            "payload_preview":            dict(self.payload_preview),
            "payload_preview_only":       self.payload_preview_only,
            "execute_requested":          self.execute_requested,
            "mock_execute_requested":     self.mock_execute_requested,
            "mock_stop_attached":         self.mock_stop_attached,
            "mock_response":              dict(self.mock_response),
            "stop_endpoint_called":       self.stop_endpoint_called,
            "order_endpoint_called":      self.order_endpoint_called,
            "no_orders_sent":             self.no_orders_sent,
            "no_position_modified":       self.no_position_modified,
            "no_live_endpoint":           self.no_live_endpoint,
            "no_batch_order":             self.no_batch_order,
            "no_close_only_path":         self.no_close_only_path,
            "secret_value_observed":      self.secret_value_observed,
            "blocked_gates":              list(self.blocked_gates),
            "status":                     self.status,
            "next_required_task":         self.next_required_task,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _validate_confirm_token(token: str, _now: datetime | None = None) -> bool:
    """
    Validate the manual confirmation token shape.

    Expected: CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD where YYYYMMDD is today UTC.
    """
    if not token.startswith(_TOKEN_PREFIX):
        return False
    suffix = token[len(_TOKEN_PREFIX):]
    if len(suffix) != 8 or not suffix.isdigit():
        return False
    today = (_now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return suffix == today


def _build_payload_preview(
    symbol: str,
    stop_price: float,
) -> dict[str, Any]:
    """
    Build a Bybit V5 /v5/position/trading-stop body preview.

    Excludes (intentionally): takeProfit, leverage, transfer/withdraw/deposit,
    order-create fields (side, qty, orderType, etc.).  Only stop-loss is set.
    """
    return {
        "category":     CATEGORY_LINEAR,
        "symbol":       symbol,
        "stopLoss":     str(stop_price),
        "tpslMode":     TPSL_MODE_FULL,
        "slTriggerBy":  SL_TRIGGER_BY_DEFAULT,
        "positionIdx":  POSITION_IDX_ONE_WAY,
    }


def _build_mock_response(symbol: str, stop_price: float) -> dict[str, Any]:
    """Synthetic Bybit-shaped response for --mock-execute-stop (no network)."""
    return {
        "retCode":   0,
        "retMsg":    "OK",
        "result": {
            "stop_attach_id":   f"MOCK-STOP-{symbol}-{int(stop_price * 100):d}",
            "symbol":           symbol,
            "stopLoss":         str(stop_price),
            "tpslMode":         TPSL_MODE_FULL,
            "slTriggerBy":      SL_TRIGGER_BY_DEFAULT,
        },
        "mock":      True,
    }


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------

class DemoStopLossAttachmentSender:
    """
    Demo-only stop-loss attachment sender — dry-run / mock-safe.

    This class deliberately holds no network client and reads no environment
    variables.  Its only job is to validate the TASK-014Q protection plan,
    build a payload preview, and (under --mock-execute-stop) emit a synthetic
    success envelope.  No socket is ever opened.
    """

    def __init__(self) -> None:
        # No credentials, no clients, no env reads.
        self._mode_dry_run = "dry_run"
        self._mode_mock    = "mock_execute_stop"

    # -- public ------------------------------------------------------------

    def submit_stop_attachment(
        self,
        protection:         dict[str, Any] | None,
        symbol:             str,
        confirm_token:      str = "",
        mock_execute_stop:  bool = False,
        _now:               datetime | None = None,
    ) -> StopAttachmentResult:
        """
        Validate the protection plan and produce a stop-attach result.

        Never contacts the network.  Under mock_execute_stop=True a synthetic
        success envelope is added; the trading-stop endpoint is still not
        called.
        """
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mode   = self._mode_mock if mock_execute_stop else self._mode_dry_run
        token_prefix = (confirm_token[:8] + "***") if confirm_token else ""

        blocked: list[str] = []

        # G1: protection report present
        if not isinstance(protection, dict) or not protection:
            blocked.append(GATE_PROTECTION_REPORT_MISSING)
            return self._fail_closed(
                ts_utc=ts_utc, mode=mode, symbol=symbol,
                token_prefix=token_prefix,
                blocked=blocked,
            )

        # G2: symbol must match
        plan_symbol = str(protection.get("selected_symbol", ""))
        if not symbol or symbol != plan_symbol:
            blocked.append(GATE_SELECTED_SYMBOL_MISMATCH)

        # Extract plan fields (defensive defaults)
        side       = str(protection.get("selected_side", "")).strip().lower()
        qty        = _safe_float(protection.get("selected_qty", 0.0))
        entry      = _safe_float(protection.get("entry_reference_price", 0.0))
        stop_px    = _safe_float(protection.get("stop_price", 0.0))
        stop_side  = str(protection.get("stop_order_side", ""))
        stop_dir   = str(protection.get("stop_trigger_direction", ""))

        # G3: review must not be fail-closed
        if bool(protection.get("review_fail_closed", True)):
            blocked.append(GATE_REVIEW_FAIL_CLOSED)

        # G4: realtime price guard must be verified
        if not bool(protection.get("realtime_price_guard_verified", False)):
            blocked.append(GATE_MISSING_REALTIME_PRICE_GUARD)

        # G5: protection must report stop_loss_attach_required=True
        if not bool(protection.get("stop_loss_attach_required", False)):
            blocked.append(GATE_STOP_LOSS_ATTACH_NOT_REQUIRED)

        # G6: protection must keep stop_loss_endpoint_allowed=False (preview-only)
        if bool(protection.get("stop_loss_endpoint_allowed", True)):
            blocked.append(GATE_UNEXPECTED_STOP_LOSS_ENDPOINT_ALLOWED)

        # G7: protection must keep protected_entry_execute_allowed=False
        if bool(protection.get("protected_entry_execute_allowed", True)):
            blocked.append(GATE_UNEXPECTED_PROTECTED_ENTRY_EXECUTE)

        # G7b: preview-only must be True and status preview_only
        if not bool(protection.get("preview_only", False)):
            blocked.append(GATE_PROTECTION_PREVIEW_ONLY_FALSE)
        if str(protection.get("protected_entry_status", "")) != "PREVIEW_ONLY":
            blocked.append(GATE_PROTECTION_STATUS_NOT_PREVIEW_ONLY)

        # G7c: protection must not claim any endpoint was called
        if bool(protection.get("order_endpoint_called", True)):
            blocked.append(GATE_ORDER_ENDPOINT_CALLED_TRUE)
        if bool(protection.get("stop_endpoint_called", True)):
            blocked.append(GATE_STOP_ENDPOINT_CALLED_TRUE)

        # G8: side
        if side not in ("long", "short"):
            blocked.append(GATE_INVALID_SIDE)

        # G9: qty
        if qty <= 0:
            blocked.append(GATE_INVALID_QTY)

        # G10: entry price
        if entry <= 0:
            blocked.append(GATE_INVALID_ENTRY_REFERENCE_PRICE)

        # G11: stop price
        if stop_px <= 0:
            blocked.append(GATE_MISSING_STOP_PRICE)

        # G12 / G13: stop direction
        if side == "long" and entry > 0 and stop_px > 0 and not (stop_px < entry):
            blocked.append(GATE_LONG_STOP_NOT_BELOW_ENTRY)
        if side == "short" and entry > 0 and stop_px > 0 and not (stop_px > entry):
            blocked.append(GATE_SHORT_STOP_NOT_ABOVE_ENTRY)

        # G14: stop_order_side
        if side == "long" and stop_side != _REQUIRED_STOP_SIDE_FOR_LONG:
            blocked.append(GATE_INVALID_STOP_ORDER_SIDE)
        elif side == "short" and stop_side != _REQUIRED_STOP_SIDE_FOR_SHORT:
            blocked.append(GATE_INVALID_STOP_ORDER_SIDE)

        # G15: confirm token (only required when mock execute requested)
        token_valid = False
        if mock_execute_stop:
            token_valid = _validate_confirm_token(confirm_token, _now=_now)
            if not token_valid:
                blocked.append(GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK)

        # Build payload preview (always populated when all of symbol/side/stop
        # are usable -- even if other gates failed; this is preview-only).
        payload: dict[str, Any] = {}
        payload_preview_only = False
        if symbol and stop_px > 0:
            payload = _build_payload_preview(symbol=symbol, stop_price=stop_px)
            payload_preview_only = True

        # Decide final status
        if blocked:
            status = STATUS_MOCK_BLOCKED if mock_execute_stop else STATUS_DRY_RUN_BLOCKED
            mock_stop_attached = False
            mock_response: dict[str, Any] = {}
        elif mock_execute_stop:
            status             = STATUS_MOCK_SUCCESS
            mock_stop_attached = True
            mock_response      = _build_mock_response(symbol=symbol, stop_price=stop_px)
        else:
            status             = STATUS_DRY_RUN_ALLOWED
            mock_stop_attached = False
            mock_response      = {}

        return StopAttachmentResult(
            timestamp_utc=ts_utc,
            mode=mode,
            selected_symbol=plan_symbol or symbol,
            selected_side=side if side in ("long", "short") else "",
            qty=qty,
            entry_reference_price=entry,
            stop_price=stop_px,
            stop_order_side=stop_side if stop_side in ("Buy", "Sell") else "",
            stop_trigger_direction=stop_dir,
            confirm_token_prefix=token_prefix,
            confirm_token_valid=token_valid,
            payload_preview=payload,
            payload_preview_only=payload_preview_only,
            execute_requested=False,                       # never True in TASK-014R
            mock_execute_requested=bool(mock_execute_stop),
            mock_stop_attached=mock_stop_attached,
            mock_response=mock_response,
            blocked_gates=blocked,
            status=status,
        )

    # -- private -----------------------------------------------------------

    def _fail_closed(
        self,
        ts_utc:       str,
        mode:         str,
        symbol:       str,
        token_prefix: str,
        blocked:      list[str],
    ) -> StopAttachmentResult:
        """Return a minimally-populated fail-closed result for early aborts."""
        return StopAttachmentResult(
            timestamp_utc=ts_utc,
            mode=mode,
            selected_symbol=symbol,
            selected_side="",
            qty=0.0,
            entry_reference_price=0.0,
            stop_price=0.0,
            stop_order_side="",
            stop_trigger_direction="",
            confirm_token_prefix=token_prefix,
            confirm_token_valid=False,
            payload_preview={},
            payload_preview_only=False,
            execute_requested=False,
            mock_execute_requested=(mode == "mock_execute_stop"),
            mock_stop_attached=False,
            mock_response={},
            blocked_gates=blocked,
            status=STATUS_FAIL_CLOSED,
        )


__all__ = [
    "STOP_ATTACH_ENDPOINT",
    "ORDER_CREATE_ENDPOINT",
    "DEMO_ENDPOINT_FAMILY",
    "TPSL_MODE_FULL",
    "SL_TRIGGER_BY_DEFAULT",
    "CATEGORY_LINEAR",
    "POSITION_IDX_ONE_WAY",
    "STATUS_DRY_RUN_ALLOWED",
    "STATUS_DRY_RUN_BLOCKED",
    "STATUS_MOCK_SUCCESS",
    "STATUS_MOCK_BLOCKED",
    "STATUS_FAIL_CLOSED",
    "GATE_PROTECTION_REPORT_MISSING",
    "GATE_SELECTED_SYMBOL_MISMATCH",
    "GATE_REVIEW_FAIL_CLOSED",
    "GATE_MISSING_REALTIME_PRICE_GUARD",
    "GATE_STOP_LOSS_ATTACH_NOT_REQUIRED",
    "GATE_UNEXPECTED_STOP_LOSS_ENDPOINT_ALLOWED",
    "GATE_UNEXPECTED_PROTECTED_ENTRY_EXECUTE",
    "GATE_INVALID_SIDE",
    "GATE_INVALID_QTY",
    "GATE_INVALID_ENTRY_REFERENCE_PRICE",
    "GATE_MISSING_STOP_PRICE",
    "GATE_LONG_STOP_NOT_BELOW_ENTRY",
    "GATE_SHORT_STOP_NOT_ABOVE_ENTRY",
    "GATE_INVALID_STOP_ORDER_SIDE",
    "GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK",
    "GATE_PROTECTION_PREVIEW_ONLY_FALSE",
    "GATE_PROTECTION_STATUS_NOT_PREVIEW_ONLY",
    "GATE_ORDER_ENDPOINT_CALLED_TRUE",
    "GATE_STOP_ENDPOINT_CALLED_TRUE",
    "StopAttachmentResult",
    "DemoStopLossAttachmentSender",
]
