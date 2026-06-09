"""
src/demo_emergency_close_sender.py
TASK-014N: Demo emergency missing-stop close-only sender — single-position gate.

Submits ONE reduce-only close order for the single symbol whose
emergency_close_preview was emitted by the TASK-014M post-fill verifier
(latest_new_entry_postfill.json) with reason="missing_stop_price".

Enforces layered safety gates before any order submission:

  Static gates (read from TASK-014M latest_new_entry_postfill.json):
    1.  postfill.fail_closed must be True
    2.  postfill.recommended_action must be "emergency_close_preview"
    3.  postfill.emergency_close_preview must exist
    4.  preview.reason must be "missing_stop_price"
    5.  preview.preview_only must be True (came from TASK-014M)
    6.  preview.reduce_only must be True
    7.  preview.order_sent must be False (came from TASK-014M)
    8.  preview.symbol must equal caller --symbol
    9.  preview.close_order_side must match preview.position_side:
         long  -> Sell
         short -> Buy
    10. preview.qty must be > 0
    11. preview.order_type must be "Market"

  Token gate:
    12. caller-supplied confirm_token must equal
        CONFIRM_DEMO_EMERGENCY_CLOSE_YYYYMMDD for today's UTC date.

  Pre-send read-only refresh (only when execute_emergency_close=True):
    R1. proof_strength=STRONG; endpoint_family=bybit_demo; account_mode=demo
    R2. target symbol still appears in live positions
    R3. live position side still matches preview position_side
    R4. live position qty >= preview qty  (close qty <= live qty)
    R5. live position stop_price <= 0 (still missing)  --
        if a stop has been restored, refuse to close
    R6. close side computed from CURRENT live side stays consistent
        (long->Sell, short->Buy)

SAFETY INVARIANTS (structural — verified by tests):
  no_live_endpoint                = True  (always — only api-demo.bybit.com)
  no_batch_order                  = True  (always — only single-symbol per call)
  no_new_entry_path               = True  (always — never imports new-entry sender)
  secret_value_observed           = False (always)
  reduce_only                     = True  (always — emergency close)
  order_endpoint_called           = False when execute_emergency_close is False
  order_endpoint_called           = True  ONLY when an actual POST is performed
  no_position_modified            = True  unless an order succeeds

Allowed order endpoint: /v5/order/create (Demo endpoint api-demo.bybit.com only,
  category=linear, Market, reduceOnly=True, closeOnTrigger=False, qty>0,
  side=Sell to close long / Buy to close short).

Forbidden operations (not implemented; verified by source scan):
  Leverage adjustment, trading-stop / TP / SL management, balance transfer /
  withdrawal / deposit, batch order submission, new-entry sender reuse,
  close-only sender reuse, live endpoint fallback.

This module does NOT modify or import:
  main.py, src/risk.py, BybitExecutor,
  src/demo_close_only_sender.py, src/demo_new_entry_sender.py,
  scripts/execute_demo_close_only_cleanup.py, scripts/execute_demo_new_entry.py,
  src/demo_new_entry_postfill_verify.py (read by the CLI, not this module).
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.demo_readonly_client import (
    DEMO_BASE_URL,
    PROOF_STRONG,
    DemoReadOnlyClient,
    PositionSnapshot,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ORDER_ENDPOINT      = "/v5/order/create"
_ALLOWED_ORDER_PATHS: frozenset[str] = frozenset({_ORDER_ENDPOINT})

_REQUIRED_CATEGORY    = "linear"
_REQUIRED_ORDER_TYPE  = "Market"
_ALLOWED_ORDER_SIDES  = frozenset({"Buy", "Sell"})

_REQUIRED_ENDPOINT_FAMILY = "bybit_demo"
_REQUIRED_ACCOUNT_MODE    = "demo"

CONFIRM_TOKEN_PREFIX = "CONFIRM_DEMO_EMERGENCY_CLOSE_"
_CONFIRM_TOKEN_RE    = re.compile(r"^CONFIRM_DEMO_EMERGENCY_CLOSE_(\d{8})$")

EMERGENCY_REASON_MISSING_STOP = "missing_stop_price"

# Acceptable input recommended_action label from TASK-014M
_REQUIRED_RECOMMENDED_ACTION = "emergency_close_preview"


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class EmergencyCloseOrderResult:
    """
    Single-order emergency missing-stop close result.

    Records gate outcomes, order status, and structural safety invariants.
    secret_value_observed is always False.
    no_live_endpoint is always True.
    no_batch_order is always True.
    no_new_entry_path is always True.
    reduce_only is always True (emergency close).
    """
    timestamp_utc:               str
    mode:                        str    # "dry_run" or "execute_emergency_close"
    postfill_loaded:             bool
    postfill_timestamp:          str
    postfill_fail_closed:        bool
    selected_symbol:             str
    position_side:               str    # "long" or "short"
    close_order_side:            str    # "Buy" or "Sell"
    selected_qty:                float
    order_type:                  str
    preview_only_source:         bool
    preview_reason:              str
    execute_requested:           bool
    execute_allowed:             bool
    order_sent:                  bool
    order_response_status:       str    # "" / "success" / "error:..."
    order_id:                    str
    blocked_gates:               list[str]
    reduce_only:                 bool  = True
    no_live_endpoint:            bool  = True
    no_batch_order:              bool  = True
    no_new_entry_path:           bool  = True
    no_close_only_sender_reused: bool  = True
    no_secrets:                  bool  = True
    secret_value_observed:       bool  = False
    order_endpoint_called:       bool  = False
    no_position_modified:        bool  = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                     self.timestamp_utc,
            "timestamp_utc":                 self.timestamp_utc,
            "mode":                          self.mode,
            "postfill_loaded":               self.postfill_loaded,
            "postfill_timestamp":            self.postfill_timestamp,
            "postfill_fail_closed":          self.postfill_fail_closed,
            "selected_symbol":               self.selected_symbol,
            "position_side":                 self.position_side,
            "close_order_side":              self.close_order_side,
            "selected_qty":                  self.selected_qty,
            "order_type":                    self.order_type,
            "reduce_only":                   self.reduce_only,
            "preview_only_source":           self.preview_only_source,
            "preview_reason":                self.preview_reason,
            "execute_requested":             self.execute_requested,
            "execute_allowed":               self.execute_allowed,
            "order_sent":                    self.order_sent,
            "order_response_status":         self.order_response_status,
            "order_id":                      self.order_id,
            "blocked_gates":                 list(self.blocked_gates),
            "no_live_endpoint":              self.no_live_endpoint,
            "no_batch_order":                self.no_batch_order,
            "no_new_entry_path":             self.no_new_entry_path,
            "no_close_only_sender_reused":   self.no_close_only_sender_reused,
            "no_secrets":                    self.no_secrets,
            "secret_value_observed":         self.secret_value_observed,
            "order_endpoint_called":         self.order_endpoint_called,
            "no_position_modified":          self.no_position_modified,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_yyyymmdd_utc(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y%m%d")


def _expected_token(now: datetime | None = None) -> str:
    return f"{CONFIRM_TOKEN_PREFIX}{_today_yyyymmdd_utc(now)}"


def _expected_close_side_for(position_side: str) -> str:
    s = (position_side or "").strip().lower()
    if s == "long":
        return "Sell"
    if s == "short":
        return "Buy"
    return ""


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------

class DemoEmergencyCloseSender:
    """
    Single-order emergency missing-stop close sender for Bybit Demo accounts.

    Default mode (allow_real_network=False): fixture-mode gate checks only;
      no network calls; no secrets loaded.

    Real mode (allow_real_network=True, execute_emergency_close=True):
      performs pre-send read-only refresh and submits one reduce-only close
      order to the Demo endpoint (api-demo.bybit.com).

    The API secret is loaded from env but never printed or included in output.
    """

    def __init__(self, allow_real_network: bool = False) -> None:
        self._allow_real     = allow_real_network
        self._api_key        = ""
        self._api_secret     = ""
        self._key_present    = False
        self._secret_present = False

        if allow_real_network:
            self._api_key        = os.environ.get("BYBIT_DEMO_API_KEY",    "")
            self._api_secret     = os.environ.get("BYBIT_DEMO_API_SECRET", "")
            self._key_present    = bool(self._api_key)
            self._secret_present = bool(self._api_secret)

    # ------------------------------------------------------------------
    # Signing (POST)
    # ------------------------------------------------------------------

    def _make_signed_headers_post(self, body_str: str) -> dict[str, str]:
        """Bybit V5 HMAC-signed headers for POST. Secret is never included in output."""
        timestamp   = str(int(time.time() * 1000))
        recv_window = "5000"
        sign_input  = timestamp + self._api_key + recv_window + body_str
        signature   = hmac.new(
            self._api_secret.encode("utf-8"),
            sign_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-BAPI-API-KEY":     self._api_key,
            "X-BAPI-SIGN":        signature,
            "X-BAPI-TIMESTAMP":   timestamp,
            "X-BAPI-RECV-WINDOW": recv_window,
        }

    # ------------------------------------------------------------------
    # Order submission (Demo endpoint only — no fallback)
    # ------------------------------------------------------------------

    def _post_to_demo(self, body_dict: dict[str, Any]) -> dict[str, Any]:
        if _ORDER_ENDPOINT not in _ALLOWED_ORDER_PATHS:
            raise ValueError(f"Endpoint not in allowed paths: {_ORDER_ENDPOINT!r}")
        body_str = json.dumps(body_dict)
        url      = f"{DEMO_BASE_URL}{_ORDER_ENDPOINT}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if self._api_key:
            headers.update(self._make_signed_headers_post(body_str))
        req = urllib.request.Request(
            url,
            data=body_str.encode("utf-8"),
            headers=headers,
            method="POST",
        )
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"retCode": -1, "retMsg": str(exc), "result": {}}

    # ------------------------------------------------------------------
    # Static gates
    # ------------------------------------------------------------------

    def _static_gates(
        self,
        postfill:       dict[str, Any],
        symbol:         str,
        confirm_token:  str,
        now:            datetime | None = None,
    ) -> tuple[list[str], dict | None]:
        """
        Validate the postfill dict + caller token + caller --symbol.

        Returns (blocked_gates, emergency_close_preview_dict or None).
        """
        gates: list[str] = []

        # G1: postfill.fail_closed must be True (otherwise no emergency needed)
        if not bool(postfill.get("fail_closed", False)):
            gates.append("postfill_not_fail_closed")

        # G2: recommended_action must be emergency_close_preview
        if str(postfill.get("recommended_action", "")) != _REQUIRED_RECOMMENDED_ACTION:
            gates.append("recommended_action_not_emergency_close_preview")

        # G3: emergency_close_preview dict must exist
        preview = postfill.get("emergency_close_preview")
        if not isinstance(preview, dict) or not preview:
            gates.append("emergency_close_preview_missing")
            # Continue with token / symbol checks anyway so we report
            # everything in one pass, but no preview-derived gates below.
            preview = None

        if preview is not None:
            # G4: reason must be missing_stop_price
            if str(preview.get("reason", "")) != EMERGENCY_REASON_MISSING_STOP:
                gates.append("preview_reason_not_missing_stop_price")
            # G5: preview_only must be True
            if not bool(preview.get("preview_only", False)):
                gates.append("preview_only_must_be_true")
            # G6: reduce_only must be True
            if not bool(preview.get("reduce_only", False)):
                gates.append("preview_reduce_only_must_be_true")
            # G7: order_sent must be False
            if bool(preview.get("order_sent", True)):
                gates.append("preview_order_sent_must_be_false")
            # G7b: order_endpoint_called must be False
            if bool(preview.get("order_endpoint_called", True)):
                gates.append("preview_order_endpoint_called_must_be_false")
            # G10: order_type must be Market
            if str(preview.get("order_type", "")) != _REQUIRED_ORDER_TYPE:
                gates.append("preview_order_type_not_market")

        # G12: confirm token
        if not confirm_token:
            gates.append("missing_confirm_token")
        else:
            m = _CONFIRM_TOKEN_RE.match(confirm_token)
            if not m:
                gates.append("invalid_confirm_token_format")
            else:
                expected = _today_yyyymmdd_utc(now)
                if m.group(1) != expected:
                    gates.append("confirm_token_date_mismatch")

        # G8: caller --symbol must be supplied
        if not symbol:
            gates.append("missing_symbol")

        if preview is None:
            return gates, None

        # G8b: caller --symbol must match preview symbol exactly
        preview_symbol = str(preview.get("symbol", ""))
        if symbol and preview_symbol and symbol != preview_symbol:
            gates.append("symbol_mismatch_vs_preview")

        # G9: close_order_side must match position_side (long->Sell, short->Buy)
        position_side    = str(preview.get("position_side", "")).strip().lower()
        close_order_side = str(preview.get("close_order_side", ""))
        expected_close   = _expected_close_side_for(position_side)
        if not expected_close:
            gates.append("invalid_position_side_in_preview")
        elif close_order_side != expected_close:
            gates.append("close_order_side_mismatch_vs_position_side")
        if close_order_side and close_order_side not in _ALLOWED_ORDER_SIDES:
            gates.append("invalid_close_order_side_in_preview")

        # G11: qty must be > 0
        try:
            qty = float(preview.get("qty", 0.0) or 0.0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            gates.append("invalid_qty_not_positive")

        return gates, preview

    # ------------------------------------------------------------------
    # Pre-send read-only refresh
    # ------------------------------------------------------------------

    def _pre_send_refresh(
        self,
        preview:    dict[str, Any],
        ro_client:  DemoReadOnlyClient | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        """
        Re-read Demo proof + positions immediately before submission.

        Returns (extra_blocked_gates, refresh_summary).
        """
        gates: list[str] = []
        client = ro_client or DemoReadOnlyClient(allow_real_network=self._allow_real)

        proof = client.build_runtime_proof()
        if proof.proof_strength != PROOF_STRONG:
            gates.append(f"refresh_proof_not_strong:{proof.proof_strength}")
        if proof.endpoint_family != _REQUIRED_ENDPOINT_FAMILY:
            gates.append(f"refresh_endpoint_not_demo:{proof.endpoint_family}")
        if proof.account_mode != _REQUIRED_ACCOUNT_MODE:
            gates.append(f"refresh_account_mode_not_demo:{proof.account_mode}")

        summary: dict[str, Any] = {
            "refresh_proof_strength":  proof.proof_strength,
            "refresh_endpoint_family": proof.endpoint_family,
            "refresh_account_mode":    proof.account_mode,
        }
        if gates:
            return gates, summary

        target_symbol = str(preview.get("symbol", ""))
        preview_side  = str(preview.get("position_side", "")).strip().lower()
        try:
            preview_qty = float(preview.get("qty", 0.0) or 0.0)
        except (TypeError, ValueError):
            preview_qty = 0.0

        live_positions: list[PositionSnapshot] = client.get_open_positions()
        target_pos: PositionSnapshot | None = None
        for p in live_positions:
            if p.symbol == target_symbol:
                target_pos = p
                break

        if target_pos is None:
            gates.append("target_position_missing")
            summary["refresh_target_position_found"] = False
            return gates, summary

        summary["refresh_target_position_found"] = True
        summary["refresh_live_side"]             = target_pos.side
        summary["refresh_live_qty"]              = target_pos.quantity
        summary["refresh_live_entry_price"]      = target_pos.entry_price
        summary["refresh_live_stop_price"]       = target_pos.stop_price

        live_side = (target_pos.side or "").strip().lower()
        if live_side != preview_side:
            gates.append(
                f"refresh_side_mismatch:preview={preview_side},live={live_side}"
            )

        live_qty = float(target_pos.quantity or 0.0)
        if live_qty <= 0:
            gates.append(f"refresh_live_qty_non_positive:{live_qty}")
        elif preview_qty > live_qty + 1e-9:
            gates.append(
                f"refresh_close_qty_exceeds_live_qty:"
                f"preview={preview_qty},live={live_qty}"
            )

        # stop_price restored => no emergency close needed
        live_stop = target_pos.stop_price
        live_stop_val = 0.0 if live_stop is None else float(live_stop)
        if live_stop_val > 0:
            gates.append("stop_restored_no_emergency_close_needed")

        # Defensive: re-derive expected close side from CURRENT live side
        expected_close_from_live = _expected_close_side_for(live_side)
        preview_close            = str(preview.get("close_order_side", ""))
        if expected_close_from_live and preview_close and \
           preview_close != expected_close_from_live:
            gates.append(
                f"refresh_close_side_inconsistent_with_live:"
                f"live_side={live_side},preview_close={preview_close}"
            )

        return gates, summary

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def submit_one_emergency_close(
        self,
        postfill:                 dict[str, Any],
        symbol:                   str,
        confirm_token:            str,
        execute_emergency_close:  bool                       = False,
        _now:                     datetime | None            = None,
        _ro_client:               DemoReadOnlyClient | None  = None,
    ) -> EmergencyCloseOrderResult:
        """
        Execute a single Demo emergency missing-stop close gate.

        If execute_emergency_close=False (default dry-run): static gates only,
        no order submitted; result reports whether the gates pass.

        If execute_emergency_close=True AND all static gates pass: pre-send
        refresh then POST one reduce-only close order to the Demo endpoint.

        The API secret is never included in the returned result.
        """
        ts_utc = (
            _now or datetime.now(timezone.utc)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mode = "execute_emergency_close" if execute_emergency_close else "dry_run"

        postfill_loaded   = isinstance(postfill, dict) and bool(postfill)
        postfill_ts       = str(postfill.get("timestamp_utc",
                                  postfill.get("timestamp", ""))) if postfill_loaded else ""
        postfill_fc       = bool(postfill.get("fail_closed", False)) if postfill_loaded else False

        if not postfill_loaded:
            return EmergencyCloseOrderResult(
                timestamp_utc=ts_utc, mode=mode,
                postfill_loaded=False, postfill_timestamp="",
                postfill_fail_closed=False,
                selected_symbol=symbol, position_side="", close_order_side="",
                selected_qty=0.0, order_type=_REQUIRED_ORDER_TYPE,
                preview_only_source=False, preview_reason="",
                execute_requested=execute_emergency_close,
                execute_allowed=False, order_sent=False,
                order_response_status="", order_id="",
                blocked_gates=["postfill_report_missing"],
            )

        blocked_gates, preview = self._static_gates(
            postfill, symbol, confirm_token, _now,
        )

        position_side    = str(preview.get("position_side", "")) if preview else ""
        close_order_side = str(preview.get("close_order_side", "")) if preview else ""
        try:
            selected_qty = float(preview.get("qty", 0.0)) if preview else 0.0
        except (TypeError, ValueError):
            selected_qty = 0.0
        order_type       = str(preview.get("order_type", _REQUIRED_ORDER_TYPE)) \
                           if preview else _REQUIRED_ORDER_TYPE
        preview_only_src = bool(preview.get("preview_only", False)) if preview else False
        preview_reason   = str(preview.get("reason", "")) if preview else ""

        # Static-gate failure path
        if blocked_gates or preview is None:
            return EmergencyCloseOrderResult(
                timestamp_utc=ts_utc, mode=mode,
                postfill_loaded=True, postfill_timestamp=postfill_ts,
                postfill_fail_closed=postfill_fc,
                selected_symbol=symbol,
                position_side=position_side,
                close_order_side=close_order_side,
                selected_qty=selected_qty,
                order_type=order_type,
                preview_only_source=preview_only_src,
                preview_reason=preview_reason,
                execute_requested=execute_emergency_close,
                execute_allowed=False, order_sent=False,
                order_response_status="", order_id="",
                blocked_gates=blocked_gates,
            )

        # Dry-run path (all static gates passed)
        if not execute_emergency_close:
            return EmergencyCloseOrderResult(
                timestamp_utc=ts_utc, mode="dry_run",
                postfill_loaded=True, postfill_timestamp=postfill_ts,
                postfill_fail_closed=postfill_fc,
                selected_symbol=symbol,
                position_side=position_side,
                close_order_side=close_order_side,
                selected_qty=selected_qty,
                order_type=order_type,
                preview_only_source=preview_only_src,
                preview_reason=preview_reason,
                execute_requested=False,
                execute_allowed=True, order_sent=False,
                order_response_status="", order_id="",
                blocked_gates=[],
            )

        # Execute path: pre-send refresh
        refresh_gates, _summary = self._pre_send_refresh(preview, _ro_client)
        if refresh_gates:
            return EmergencyCloseOrderResult(
                timestamp_utc=ts_utc, mode=mode,
                postfill_loaded=True, postfill_timestamp=postfill_ts,
                postfill_fail_closed=postfill_fc,
                selected_symbol=symbol,
                position_side=position_side,
                close_order_side=close_order_side,
                selected_qty=selected_qty,
                order_type=order_type,
                preview_only_source=preview_only_src,
                preview_reason=preview_reason,
                execute_requested=True,
                execute_allowed=False, order_sent=False,
                order_response_status="", order_id="",
                blocked_gates=refresh_gates,
            )

        # Build the order payload — minimal Bybit V5 reduce-only Market close.
        # Explicitly excludes: leverage, take-profit / stop-loss, conditional
        # trigger price, balance transfer, closeOnTrigger=True.
        order_body: dict[str, Any] = {
            "category":       _REQUIRED_CATEGORY,
            "symbol":         symbol,
            "side":           close_order_side,        # Sell to close long
            "orderType":      _REQUIRED_ORDER_TYPE,    # Market
            "qty":            str(selected_qty),
            "reduceOnly":     True,                    # emergency CLOSE
            "closeOnTrigger": False,
            "timeInForce":    "IOC",
            "positionIdx":    0,                       # one-way mode
        }

        response     = self._post_to_demo(order_body)
        ret_code     = response.get("retCode", -1)
        ret_msg      = str(response.get("retMsg", ""))
        result_body  = response.get("result", {}) or {}
        order_id_out = str(result_body.get("orderId", ""))

        if ret_code == 0:
            order_status     = "success"
            no_pos_modified  = False
            order_sent_flag  = True
        else:
            order_status     = f"error:retCode={ret_code}:msg={ret_msg}"
            no_pos_modified  = True
            order_sent_flag  = False

        return EmergencyCloseOrderResult(
            timestamp_utc=ts_utc, mode=mode,
            postfill_loaded=True, postfill_timestamp=postfill_ts,
            postfill_fail_closed=postfill_fc,
            selected_symbol=symbol,
            position_side=position_side,
            close_order_side=close_order_side,
            selected_qty=selected_qty,
            order_type=order_type,
            preview_only_source=preview_only_src,
            preview_reason=preview_reason,
            execute_requested=True,
            execute_allowed=True,
            order_sent=order_sent_flag,
            order_response_status=order_status,
            order_id=order_id_out,
            blocked_gates=[],
            order_endpoint_called=True,
            no_position_modified=no_pos_modified,
        )
