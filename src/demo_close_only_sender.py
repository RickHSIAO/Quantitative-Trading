"""
src/demo_close_only_sender.py
TASK-014G: Demo close-only order gate — single-order, manual-confirmed execution.

Enforces layered safety gates before any order submission:
  1. TASK-014F cleanup plan gates: cleanup_needed, snapshot_fresh, token_valid,
     demo_runtime_verified, proof_strength=STRONG.
  2. Symbol must be in cleanup plan candidates (unique match).
  3. Payload reduce_only must be True; close_order_side must match position direction.
  4. Pre-send read-only refresh: position still exists, qty/side consistent.
  5. Demo endpoint only (api-demo.bybit.com); no fallback.
  6. One order per invocation — no batch submission.
  7. execute_close_only=True required; default is dry-run (no order submitted).

SAFETY INVARIANTS (structural — verified by tests):
  secret_value_observed = False (always)
  no_live_endpoint = True (always)
  no_new_position_intent = True (always; reduce_only=True enforced at gate level)
  order_endpoint_called = False when execute_close_only is False
  private_order_endpoint_called = False when execute_close_only is False

Allowed order endpoint: /v5/order/create (Demo endpoint only, category=linear, Market,
  reduce_only=True, qty>0, symbol in plan candidates).

Forbidden operations (not implemented; verified by source scan):
  Leverage adjustment, stop-level management, balance movement.

This module does not modify main.py, src/risk.py, or exchange executor classes.
"""
from __future__ import annotations

import hashlib
import hmac
import json
import os
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

from src.demo_readonly_client import (
    DEMO_BASE_URL,
    PROOF_MISSING,
    PROOF_STRONG,
    PROOF_WEAK,
    DemoReadOnlyClient,
    PositionSnapshot,
)
from src.demo_close_only_cleanup import _check_snapshot_freshness

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Only this endpoint path is ever used for order operations.
_ORDER_ENDPOINT = "/v5/order/create"
_ALLOWED_ORDER_PATHS: frozenset[str] = frozenset({_ORDER_ENDPOINT})

# Required field values enforced at submission time.
_REQUIRED_CATEGORY    = "linear"
_REQUIRED_ORDER_TYPE  = "Market"
_ALLOWED_CLOSE_SIDES  = frozenset({"Buy", "Sell"})


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class CloseOrderResult:
    """
    Single-order close-only execution result.

    Records gate outcomes, order status, and safety invariants.
    secret_value_observed is always False.
    no_live_endpoint is always True.
    no_new_position_intent is always True (reduce_only enforced).
    """
    timestamp_utc:               str
    mode:                        str    # "dry_run" or "execute_close_only"
    demo_runtime_verified:       bool
    proof_strength:              str
    selected_symbol:             str
    selected_qty:                float
    selected_side:               str    # direction of the existing position
    close_order_side:            str    # "Buy" or "Sell"
    order_type:                  str    # always "Market"
    execute_requested:           bool
    execute_allowed:             bool
    order_sent:                  bool
    order_response_status:       str    # "" / "success" / "error:<detail>"
    order_id:                    str    # from exchange response on success; "" otherwise
    blocked_gates:               list[str]
    reduce_only:                 bool  = True
    no_live_endpoint:            bool  = True
    no_new_position_intent:      bool  = True
    secret_value_observed:       bool  = False
    order_endpoint_called:       bool  = False
    private_order_endpoint_called: bool = False
    no_position_modified:        bool  = True   # False only when order succeeds
    position_details_source:     str   = "fixture"   # TASK-014H
    source_position_details_is_real: bool = False    # TASK-014H

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc":                  self.timestamp_utc,
            "mode":                           self.mode,
            "demo_runtime_verified":          self.demo_runtime_verified,
            "proof_strength":                 self.proof_strength,
            "selected_symbol":                self.selected_symbol,
            "selected_qty":                   self.selected_qty,
            "selected_side":                  self.selected_side,
            "close_order_side":               self.close_order_side,
            "order_type":                     self.order_type,
            "reduce_only":                    self.reduce_only,
            "execute_requested":              self.execute_requested,
            "execute_allowed":                self.execute_allowed,
            "order_sent":                     self.order_sent,
            "order_response_status":          self.order_response_status,
            "order_id":                       self.order_id,
            "blocked_gates":                  self.blocked_gates,
            "no_live_endpoint":               self.no_live_endpoint,
            "no_new_position_intent":         self.no_new_position_intent,
            "secret_value_observed":          self.secret_value_observed,
            "order_endpoint_called":          self.order_endpoint_called,
            "private_order_endpoint_called":  self.private_order_endpoint_called,
            "no_position_modified":           self.no_position_modified,
            "position_details_source":        self.position_details_source,
            "source_position_details_is_real": self.source_position_details_is_real,
        }


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------

class DemoCloseOnlySender:
    """
    Single-order close-only sender for Bybit Demo accounts.

    Default mode (allow_real_network=False): fixture-mode gate checks only;
      no network calls; no secrets loaded.
    Real mode (allow_real_network=True, execute_close_only=True):
      performs pre-send read-only refresh and submits one close-only order
      to the Demo endpoint (api-demo.bybit.com).

    The API secret is loaded from env but never printed or included in output.
    """

    def __init__(self, allow_real_network: bool = False) -> None:
        self._allow_real  = allow_real_network
        self._api_key     = ""
        self._api_secret  = ""
        self._key_present = False

        if allow_real_network:
            self._api_key    = os.environ.get("BYBIT_DEMO_API_KEY",    "")
            self._api_secret = os.environ.get("BYBIT_DEMO_API_SECRET", "")
            self._key_present = bool(self._api_key)

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
    # Order submission (Demo endpoint only)
    # ------------------------------------------------------------------

    def _post_to_demo(self, body_dict: dict[str, Any]) -> dict[str, Any]:
        """
        POST JSON body to the Demo order endpoint.
        Only DEMO_BASE_URL (api-demo.bybit.com) is ever used as target.
        Raises ValueError if the endpoint is not in the allowed list.
        """
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
    # Gate checks (static — from plan dict)
    # ------------------------------------------------------------------

    def _gate_checks(
        self,
        cleanup_plan:  dict[str, Any],
        symbol:        str,
        confirm_token: str,
        _now:          datetime | None = None,
    ) -> tuple[list[str], dict | None, dict | None]:
        """
        Validate the cleanup plan dict for the requested symbol.

        Returns (blocked_gates, candidate_dict, payload_dict).
        Empty blocked_gates means all static gates passed.
        candidate_dict / payload_dict are None if not found.
        """
        gates: list[str] = []

        # Gate 1: cleanup must be needed
        if not cleanup_plan.get("cleanup_needed", False):
            gates.append("cleanup_not_needed")

        # Gate 2: snapshot freshness (re-evaluated from stored timestamp)
        ts = cleanup_plan.get("snapshot_timestamp_utc", "")
        if ts:
            fresh, _ = _check_snapshot_freshness(ts, now=_now)
            if not fresh:
                gates.append("snapshot_stale")

        # Gate 3: human confirmation token
        expected_pattern = cleanup_plan.get("confirm_token_expected_pattern", "")
        if not confirm_token or confirm_token != expected_pattern:
            gates.append("invalid_confirm_token")

        # Gate 4: demo runtime verified in plan
        if not cleanup_plan.get("demo_runtime_verified", False):
            gates.append("demo_not_verified")

        # Gate 5: proof strength must be STRONG
        if cleanup_plan.get("proof_strength", "") != PROOF_STRONG:
            gates.append("proof_not_strong")

        # Gate 5b (TASK-014H): position_details_source must be "real_readonly".
        # Without this gate, a fixture-only cleanup plan could feed candidates
        # like ETHUSDT / BNBUSDT that do not exist on the real Demo account.
        pds = cleanup_plan.get("position_details_source", "")
        if pds != "real_readonly":
            gates.append("position_details_source_not_real_readonly")

        # Gate 6 + 7: symbol must be in candidates (exactly one match)
        candidates = cleanup_plan.get("suggested_close_candidates", [])
        sym_cands = [c for c in candidates if c.get("symbol") == symbol]
        if not sym_cands:
            gates.append("symbol_not_in_candidates")
            return gates, None, None
        if len(sym_cands) > 1:
            gates.append("candidate_not_unique")
            return gates, None, None
        candidate = sym_cands[0]

        # Find matching payload preview
        payloads = cleanup_plan.get("close_payload_preview", [])
        sym_payloads = [p for p in payloads if p.get("symbol") == symbol]
        if not sym_payloads:
            gates.append("payload_not_found_for_symbol")
            return gates, candidate, None
        payload = sym_payloads[0]

        # Gate 8: reduce_only must be True
        if not payload.get("reduce_only", False):
            gates.append("reduce_only_not_true")

        # Gate 9: close_order_side must match position direction
        pos_side         = candidate.get("side", "").lower()
        close_side       = payload.get("close_order_side", "")
        expected_cs      = "Buy" if pos_side == "short" else "Sell"
        if close_side != expected_cs:
            gates.append("close_side_mismatch")

        # Gate 10: qty must be positive
        qty = float(payload.get("qty", 0.0))
        if qty <= 0:
            gates.append("invalid_qty_not_positive")

        return gates, candidate, payload

    # ------------------------------------------------------------------
    # Pre-send read-only refresh
    # ------------------------------------------------------------------

    def _pre_send_refresh(
        self,
        symbol:    str,
        candidate: dict,
        payload:   dict,
        ro_client: DemoReadOnlyClient | None = None,
    ) -> tuple[list[str], PositionSnapshot | None, str, str]:
        """
        Re-reads Demo proof and positions immediately before order submission.

        Returns (extra_blocked_gates, live_position, live_proof_strength,
                 live_endpoint_family).
        """
        gates: list[str] = []

        client = ro_client or DemoReadOnlyClient(allow_real_network=self._allow_real)

        # Verify Demo identity from fresh read
        proof = client.build_runtime_proof()
        live_proof_str    = proof.proof_strength
        live_ep_family    = proof.endpoint_family

        if proof.proof_strength != PROOF_STRONG:
            gates.append(f"refresh_proof_not_strong:{proof.proof_strength}")
        if proof.endpoint_family != "bybit_demo":
            gates.append(f"refresh_endpoint_not_demo:{proof.endpoint_family}")

        if gates:
            return gates, None, live_proof_str, live_ep_family

        # Verify the target position still exists
        live_positions = client.get_open_positions()
        live_pos: PositionSnapshot | None = None
        for p in live_positions:
            if p.symbol == symbol:
                live_pos = p
                break

        if live_pos is None:
            gates.append("position_not_found_after_refresh")
            return gates, None, live_proof_str, live_ep_family

        # Gate: side must still match
        expected_pos_side = candidate.get("side", "").lower()
        if live_pos.side.lower() != expected_pos_side:
            gates.append("position_side_mismatch_after_refresh")

        # Gate: close qty must not exceed current position qty
        close_qty = float(payload.get("qty", 0.0))
        if close_qty > live_pos.quantity + 1e-9:
            gates.append(
                f"close_qty_exceeds_position:"
                f"{close_qty:.6f}>{live_pos.quantity:.6f}"
            )

        return gates, live_pos, live_proof_str, live_ep_family

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def submit_one_close_order(
        self,
        cleanup_plan:       dict[str, Any],
        symbol:             str,
        confirm_token:      str,
        execute_close_only: bool                      = False,
        _now:               datetime | None           = None,
        _ro_client:         DemoReadOnlyClient | None = None,
    ) -> CloseOrderResult:
        """
        Execute a single close-only order gate.

        If execute_close_only=False (default dry-run): runs all static gate
        checks and returns a preview. No order is submitted.

        If execute_close_only=True AND all gates pass: performs a pre-send
        read-only refresh, then submits one close-only order to the Demo
        endpoint. Returns the execution result.

        The API secret is never included in the returned result.

        Args:
            cleanup_plan:       dict from latest_close_only_cleanup.json.
            symbol:             Symbol to close (e.g. "ETHUSDT").
            confirm_token:      Human confirmation token (must match plan pattern).
            execute_close_only: True to permit real order submission.
            _now:               Override current time (for deterministic tests).
            _ro_client:         Override read-only client (for unit tests).

        Returns:
            CloseOrderResult with gate outcomes and invariant flags.
        """
        ts_utc = (
            _now or datetime.now(timezone.utc)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mode   = "execute_close_only" if execute_close_only else "dry_run"

        demo_runtime_verified = bool(cleanup_plan.get("demo_runtime_verified", False))
        proof_strength        = str(cleanup_plan.get("proof_strength", ""))
        pds                   = str(cleanup_plan.get("position_details_source", "fixture"))
        pds_is_real           = (pds == "real_readonly")

        # ── Static gate checks ────────────────────────────────────────────
        blocked_gates, candidate, payload = self._gate_checks(
            cleanup_plan, symbol, confirm_token, _now
        )

        # Extract values for result (may be default if not found)
        selected_qty     = float(payload["qty"]) if payload else 0.0
        selected_side    = str(candidate["side"]) if candidate else ""
        close_order_side = str(payload["close_order_side"]) if payload else ""

        # Return early if any static gate failed
        if blocked_gates or candidate is None or payload is None:
            return CloseOrderResult(
                timestamp_utc=ts_utc,
                mode=mode,
                demo_runtime_verified=demo_runtime_verified,
                proof_strength=proof_strength,
                selected_symbol=symbol,
                selected_qty=selected_qty,
                selected_side=selected_side,
                close_order_side=close_order_side,
                order_type=_REQUIRED_ORDER_TYPE,
                execute_requested=execute_close_only,
                execute_allowed=False,
                order_sent=False,
                order_response_status="",
                order_id="",
                blocked_gates=blocked_gates,
                position_details_source=pds,
                source_position_details_is_real=pds_is_real,
            )

        # ── Dry-run path (all static gates passed, no execution) ──────────
        if not execute_close_only:
            return CloseOrderResult(
                timestamp_utc=ts_utc,
                mode="dry_run",
                demo_runtime_verified=demo_runtime_verified,
                proof_strength=proof_strength,
                selected_symbol=symbol,
                selected_qty=selected_qty,
                selected_side=selected_side,
                close_order_side=close_order_side,
                order_type=_REQUIRED_ORDER_TYPE,
                execute_requested=False,
                execute_allowed=True,
                order_sent=False,
                order_response_status="",
                order_id="",
                blocked_gates=[],
                position_details_source=pds,
                source_position_details_is_real=pds_is_real,
            )

        # ── Execute path: pre-send read-only refresh ──────────────────────
        refresh_gates, live_pos, live_proof_str, live_ep_family = (
            self._pre_send_refresh(symbol, candidate, payload, _ro_client)
        )
        if refresh_gates:
            return CloseOrderResult(
                timestamp_utc=ts_utc,
                mode=mode,
                demo_runtime_verified=demo_runtime_verified,
                proof_strength=live_proof_str or proof_strength,
                selected_symbol=symbol,
                selected_qty=selected_qty,
                selected_side=selected_side,
                close_order_side=close_order_side,
                order_type=_REQUIRED_ORDER_TYPE,
                execute_requested=True,
                execute_allowed=False,
                order_sent=False,
                order_response_status="",
                order_id="",
                blocked_gates=refresh_gates,
                position_details_source=pds,
                source_position_details_is_real=pds_is_real,
            )

        # ── Build and submit the close-only order ─────────────────────────
        order_body: dict[str, Any] = {
            "category":    _REQUIRED_CATEGORY,
            "symbol":      symbol,
            "side":        close_order_side,
            "orderType":   _REQUIRED_ORDER_TYPE,
            "qty":         str(selected_qty),
            "reduceOnly":  True,
            "positionIdx": 0,
        }

        response    = self._post_to_demo(order_body)
        ret_code    = response.get("retCode", -1)
        ret_msg     = str(response.get("retMsg", ""))
        result_body = response.get("result", {}) or {}
        order_id_out = str(result_body.get("orderId", ""))

        if ret_code == 0:
            order_status    = "success"
            no_pos_modified = False  # position was modified by the order
        else:
            order_status    = f"error:retCode={ret_code}:msg={ret_msg}"
            no_pos_modified = True   # order failed; position unchanged

        return CloseOrderResult(
            timestamp_utc=ts_utc,
            mode=mode,
            demo_runtime_verified=True,
            proof_strength=live_proof_str,
            selected_symbol=symbol,
            selected_qty=selected_qty,
            selected_side=selected_side,
            close_order_side=close_order_side,
            order_type=_REQUIRED_ORDER_TYPE,
            execute_requested=True,
            execute_allowed=True,
            order_sent=(ret_code == 0),
            order_response_status=order_status,
            order_id=order_id_out,
            blocked_gates=[],
            order_endpoint_called=True,
            private_order_endpoint_called=True,
            no_position_modified=no_pos_modified,
            position_details_source=pds,
            source_position_details_is_real=pds_is_real,
        )
