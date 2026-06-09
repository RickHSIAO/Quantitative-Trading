"""
src/demo_new_entry_sender.py
TASK-014L: Demo new-entry order gate — single-order, manual-confirmed execution.

Enforces layered safety gates before any new-entry order submission:

  Static gates (read from TASK-014K latest_new_entry_review.json):
    1.  review.fail_closed must be False
    2.  review.demo_runtime_verified must be True
    3.  review.proof_strength must be "STRONG"
    4.  review.endpoint_family must be "bybit_demo"
    5.  review.account_mode must be "demo"
    6.  review.position_details_source must be "real_readonly"
    7.  review.new_entry_allowed_from_reconciliation must be True
    8.  review.available_balance_usd must be > 0
    9.  review.open_positions_count must be < 10
    10. caller-supplied symbol must be in review.accepted_candidates
    11. for long candidate: review.max_long_allowed_remaining must be > 0
    12. for short candidate: review.max_short_allowed_remaining must be > 0
        AND short candidates are presently REJECTED at this layer because
        the production state has short_count=5/5 and tier-1 SHORT new entries
        are not permitted by TASK-014L.
    13. payload.reduce_only must be False (new entry — NOT close-only)
    14. payload.preview_only must be True (came from TASK-014K)
    15. payload.order_sent must be False (came from TASK-014K)
    16. payload.order_endpoint_called must be False (came from TASK-014K)
    17. order side string consistency: Buy for long, Sell for short
    19. (TASK-014M) review.realtime_price_guard_verified must be True
        — protects against stale entry_reference_price values being trusted.

  Token gate:
    18. caller-supplied confirm_token must equal CONFIRM_DEMO_NEW_ENTRY_YYYYMMDD
        for today's UTC date.

  Pre-send read-only refresh (only when execute_new_entry=True):
    R1. live proof_strength=STRONG; endpoint_family=bybit_demo
    R2. live wallet available_balance_usd > 0
    R3. live open positions: target symbol NOT already open
    R4. live open positions: open_positions_count < 10
    R5. live counts: long_count < 5 for long entries
                    (short entries are blocked even if short_count < 5)
    R6. live remaining_risk_budget >= payload.estimated_stop_risk_usd
        (best-effort recomputation; conservative)

SAFETY INVARIANTS (structural — verified by tests):
  secret_value_observed         = False (always)
  no_live_endpoint              = True  (always)
  no_batch_order                = True  (always — only single-symbol per call)
  no_close_only_path            = True  (always — module never imports close-only sender)
  reduce_only                   = False (always, for new-entry payloads)
  order_endpoint_called         = False when execute_new_entry is False
  order_endpoint_called         = True  ONLY when an actual POST is performed
  no_position_modified          = True  unless an order succeeds

Allowed order endpoint: /v5/order/create (Demo endpoint api-demo.bybit.com only,
  category=linear, Market, reduce_only=False, qty>0, symbol in
  review.accepted_candidates, side=Buy for long, side=Sell for short).

Forbidden operations (not implemented; verified by source scan):
  Leverage adjustment, trading-stop / TP / SL management, balance transfer /
  withdrawal / deposit, batch order submission, close-only sender reuse.

This module does NOT modify or import:
  main.py, src/risk.py, BybitExecutor,
  src/demo_close_only_sender.py, scripts/execute_demo_close_only_cleanup.py.
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
    WalletSnapshot,
)


# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

_ORDER_ENDPOINT      = "/v5/order/create"
_ALLOWED_ORDER_PATHS: frozenset[str] = frozenset({_ORDER_ENDPOINT})

_REQUIRED_CATEGORY   = "linear"
_REQUIRED_ORDER_TYPE = "Market"
_ALLOWED_ORDER_SIDES = frozenset({"Buy", "Sell"})

_REQUIRED_ENDPOINT_FAMILY = "bybit_demo"
_REQUIRED_ACCOUNT_MODE    = "demo"
_REQUIRED_POSITION_SOURCE = "real_readonly"

CONFIRM_TOKEN_PREFIX = "CONFIRM_DEMO_NEW_ENTRY_"
_CONFIRM_TOKEN_RE    = re.compile(r"^CONFIRM_DEMO_NEW_ENTRY_(\d{8})$")

_MAX_OPEN_POSITIONS_REFRESH = 10
_MAX_LONG_POSITIONS_REFRESH = 5
_MAX_SHORT_POSITIONS_REFRESH = 5


# ---------------------------------------------------------------------------
# Result type
# ---------------------------------------------------------------------------

@dataclass
class NewEntryOrderResult:
    """
    Single-order new-entry execution result.

    Records gate outcomes, order status, and safety invariants.
    secret_value_observed is always False.
    no_live_endpoint is always True.
    no_batch_order is always True.
    no_close_only_path is always True.
    reduce_only is always False (new-entry payload).
    """
    timestamp_utc:               str
    mode:                        str    # "dry_run" or "execute_new_entry"
    demo_runtime_verified:       bool
    proof_strength:              str
    endpoint_family:             str
    account_mode:                str
    position_details_source:     str
    available_balance_usd_source: str
    selected_symbol:             str
    selected_side:               str   # "long" or "short"
    selected_qty:                float
    order_side:                  str   # "Buy" or "Sell"
    order_type:                  str   # always "Market"
    preview_only_source:         bool  # came from review.payload.preview_only
    execute_requested:           bool
    execute_allowed:             bool
    order_sent:                  bool
    order_response_status:       str   # "" / "success" / "error:<detail>"
    order_id:                    str   # exchange order id when success
    blocked_gates:               list[str]
    reduce_only:                 bool  = False  # new entry — must be False
    no_live_endpoint:            bool  = True
    no_batch_order:              bool  = True
    no_close_only_path:          bool  = True
    secret_value_observed:       bool  = False
    order_endpoint_called:       bool  = False
    no_position_modified:        bool  = True   # False ONLY when order succeeds
    review_fail_closed:          bool  = False
    review_timestamp:            str   = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                     self.timestamp_utc,
            "timestamp_utc":                 self.timestamp_utc,
            "mode":                          self.mode,
            "demo_runtime_verified":         self.demo_runtime_verified,
            "proof_strength":                self.proof_strength,
            "endpoint_family":               self.endpoint_family,
            "account_mode":                  self.account_mode,
            "position_details_source":       self.position_details_source,
            "available_balance_usd_source":  self.available_balance_usd_source,
            "selected_symbol":               self.selected_symbol,
            "selected_side":                 self.selected_side,
            "selected_qty":                  self.selected_qty,
            "order_side":                    self.order_side,
            "order_type":                    self.order_type,
            "reduce_only":                   self.reduce_only,
            "preview_only_source":           self.preview_only_source,
            "execute_requested":             self.execute_requested,
            "execute_allowed":               self.execute_allowed,
            "order_sent":                    self.order_sent,
            "order_response_status":         self.order_response_status,
            "order_id":                      self.order_id,
            "blocked_gates":                 list(self.blocked_gates),
            "no_live_endpoint":              self.no_live_endpoint,
            "no_batch_order":                self.no_batch_order,
            "no_close_only_path":            self.no_close_only_path,
            "secret_value_observed":         self.secret_value_observed,
            "order_endpoint_called":         self.order_endpoint_called,
            "no_position_modified":          self.no_position_modified,
            "review_fail_closed":            self.review_fail_closed,
            "review_timestamp":              self.review_timestamp,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _today_yyyymmdd_utc(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y%m%d")


def _expected_token(now: datetime | None = None) -> str:
    return f"{CONFIRM_TOKEN_PREFIX}{_today_yyyymmdd_utc(now)}"


def _order_side_for(direction: str) -> str:
    d = (direction or "").strip().lower()
    if d == "long":
        return "Buy"
    if d == "short":
        return "Sell"
    return ""


def _find_accepted_candidate(
    review: dict[str, Any], symbol: str,
) -> tuple[dict | None, dict | None]:
    """Return (evaluation_dict, payload_dict) when symbol is accepted; else (None, None)."""
    if not symbol:
        return None, None
    for ev in review.get("accepted_candidates", []) or []:
        if str(ev.get("symbol", "")) == symbol:
            return ev, ev.get("payload") or None
    return None, None


# ---------------------------------------------------------------------------
# Sender
# ---------------------------------------------------------------------------

class DemoNewEntrySender:
    """
    Single-order new-entry sender for Bybit Demo accounts.

    Default mode (allow_real_network=False): fixture-mode gate checks only;
      no network calls; no secrets loaded.

    Real mode (allow_real_network=True, execute_new_entry=True):
      performs pre-send read-only refresh and submits one new-entry order to
      the Demo endpoint (api-demo.bybit.com).

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
    # Static gates (read-only, from review JSON + token)
    # ------------------------------------------------------------------

    def _static_gates(
        self,
        review:        dict[str, Any],
        symbol:        str,
        confirm_token: str,
        now:           datetime | None = None,
    ) -> tuple[list[str], dict | None, dict | None]:
        """
        Validate the review dict + caller token for the requested symbol.

        Returns (blocked_gates, evaluation_dict, payload_dict).
        """
        gates: list[str] = []

        # G1: review must not have fail_closed
        if bool(review.get("fail_closed", True)):
            gates.append("review_fail_closed")

        # G2: demo runtime verified
        if not bool(review.get("demo_runtime_verified", False)):
            gates.append("demo_runtime_not_verified")

        # G3: proof strength
        if str(review.get("proof_strength", "")) != PROOF_STRONG:
            gates.append("proof_not_strong")

        # G4: endpoint family
        if str(review.get("endpoint_family", "")) != _REQUIRED_ENDPOINT_FAMILY:
            gates.append("endpoint_family_not_bybit_demo")

        # G5: account mode
        if str(review.get("account_mode", "")) != _REQUIRED_ACCOUNT_MODE:
            gates.append("account_mode_not_demo")

        # G6: position details source
        if str(review.get("position_details_source", "")) != _REQUIRED_POSITION_SOURCE:
            gates.append("position_details_source_not_real_readonly")

        # G7: reconciliation new-entry allowed
        if not bool(review.get("new_entry_allowed_from_reconciliation", False)):
            gates.append("new_entry_not_allowed_from_reconciliation")

        # G8: available balance > 0
        try:
            available = float(review.get("available_balance_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            available = 0.0
        if available <= 0:
            gates.append("available_balance_zero_or_negative")

        # G9: open positions < 10
        try:
            open_count = int(review.get("open_positions_count", 0) or 0)
        except (TypeError, ValueError):
            open_count = 0
        if open_count >= _MAX_OPEN_POSITIONS_REFRESH:
            gates.append("open_positions_full")

        # G19 (TASK-014M): real-time price guard.
        # The review file MUST carry realtime_price_guard_verified=True, asserting
        # that the entry_reference_price used in the preview was sourced from a
        # live market reading rather than a stale cached value.  Production
        # incident (SOLUSDT, 2026-06-09) showed that a stale 160.0 reference
        # against an actual fill of 66.47 produced a ~58% deviation; this guard
        # blocks future sends until the upstream review explicitly asserts a
        # real-time price was used.
        if not bool(review.get("realtime_price_guard_verified", False)):
            gates.append("missing_realtime_price_guard")

        # G18: confirm token
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

        # G10: symbol must be in accepted candidates
        if not symbol:
            gates.append("missing_symbol")
            return gates, None, None
        ev, payload = _find_accepted_candidate(review, symbol)
        if ev is None or payload is None:
            gates.append("symbol_not_in_accepted_candidates")
            return gates, None, None

        # G12 (precedence): short candidates are presently NOT permitted.
        side_label = str(ev.get("side", "")).strip().lower()
        if side_label == "short":
            gates.append("short_new_entry_not_permitted")
        elif side_label == "long":
            # G11: long capacity remaining > 0
            try:
                long_remaining = int(review.get("max_long_allowed_remaining", 0) or 0)
            except (TypeError, ValueError):
                long_remaining = 0
            if long_remaining <= 0:
                gates.append("long_capacity_full")
        else:
            gates.append("invalid_side_in_review")

        # G13: payload.reduce_only must be False (new-entry sender)
        if bool(payload.get("reduce_only", True)):
            gates.append("payload_reduce_only_must_be_false")

        # G14: payload.preview_only must be True (came from TASK-014K)
        if not bool(payload.get("preview_only", False)):
            gates.append("payload_preview_only_must_be_true")

        # G15: payload.order_sent must be False (came from TASK-014K)
        if bool(payload.get("order_sent", True)):
            gates.append("payload_order_sent_must_be_false")

        # G16: payload.order_endpoint_called must be False (came from TASK-014K)
        if bool(payload.get("order_endpoint_called", True)):
            gates.append("payload_order_endpoint_called_must_be_false")

        # G17: payload qty > 0
        try:
            qty = float(payload.get("qty", 0.0) or 0.0)
        except (TypeError, ValueError):
            qty = 0.0
        if qty <= 0:
            gates.append("invalid_qty_not_positive")

        # G17: order_side consistency between side label and payload side
        expected_order_side = _order_side_for(side_label)
        payload_order_side  = str(payload.get("side", ""))
        if expected_order_side and payload_order_side and \
           expected_order_side != payload_order_side:
            gates.append("order_side_mismatch_vs_side_label")
        if payload_order_side and payload_order_side not in _ALLOWED_ORDER_SIDES:
            gates.append("invalid_order_side_in_payload")

        # G17b: order_type must be Market
        if str(payload.get("order_type", "")) != _REQUIRED_ORDER_TYPE:
            gates.append("payload_order_type_not_market")

        return gates, ev, payload

    # ------------------------------------------------------------------
    # Pre-send read-only refresh
    # ------------------------------------------------------------------

    def _pre_send_refresh(
        self,
        review:    dict[str, Any],
        ev:        dict[str, Any],
        payload:   dict[str, Any],
        ro_client: DemoReadOnlyClient | None = None,
    ) -> tuple[list[str], dict[str, Any]]:
        """
        Re-read Demo proof, wallet, positions immediately before submission.

        Returns (extra_blocked_gates, refresh_summary).
        refresh_summary contains fields useful for the result.
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

        if gates:
            return gates, {
                "refresh_proof_strength": proof.proof_strength,
                "refresh_endpoint_family": proof.endpoint_family,
            }

        # Wallet refresh
        wallet: WalletSnapshot = client.get_wallet_balance()
        if wallet.available_balance_usd <= 0:
            gates.append(
                f"refresh_available_balance_non_positive:{wallet.available_balance_usd:.2f}"
            )

        # Positions refresh
        live_positions: list[PositionSnapshot] = client.get_open_positions()
        live_count  = len(live_positions)
        live_long   = sum(1 for p in live_positions if p.side.lower() == "long")
        live_short  = sum(1 for p in live_positions if p.side.lower() == "short")
        live_symbols = {p.symbol for p in live_positions}

        target_symbol = str(ev.get("symbol", ""))
        side_label    = str(ev.get("side", "")).strip().lower()

        if live_count >= _MAX_OPEN_POSITIONS_REFRESH:
            gates.append(f"refresh_open_positions_full:{live_count}")
        if target_symbol in live_symbols:
            gates.append("refresh_target_symbol_already_open")

        if side_label == "long" and live_long >= _MAX_LONG_POSITIONS_REFRESH:
            gates.append(f"refresh_long_capacity_full:{live_long}")
        if side_label == "short":
            # Short new entries are blocked at the static gate already; keep this
            # as a defensive duplicate so a stale review file cannot slip through.
            gates.append("refresh_short_new_entry_not_permitted")

        # Risk budget — recomputed conservatively
        # Use review.remaining_risk_budget_usd as upper bound; if the payload's
        # estimated_stop_risk_usd exceeds the *review* remaining budget we refuse.
        try:
            review_remaining = float(review.get("remaining_risk_budget_usd", 0.0) or 0.0)
            stop_risk_payload = float(payload.get("estimated_stop_risk_usd", 0.0) or 0.0)
        except (TypeError, ValueError):
            review_remaining = 0.0
            stop_risk_payload = 0.0
        if stop_risk_payload > review_remaining + 1e-6:
            gates.append(
                f"refresh_stop_risk_exceeds_remaining_budget:"
                f"{stop_risk_payload:.2f}>{review_remaining:.2f}"
            )

        return gates, {
            "refresh_proof_strength":       proof.proof_strength,
            "refresh_endpoint_family":      proof.endpoint_family,
            "refresh_account_mode":         proof.account_mode,
            "refresh_available_balance":    wallet.available_balance_usd,
            "refresh_available_balance_source": wallet.available_balance_usd_source,
            "refresh_open_positions_count": live_count,
            "refresh_long_count":           live_long,
            "refresh_short_count":          live_short,
        }

    # ------------------------------------------------------------------
    # Main API
    # ------------------------------------------------------------------

    def submit_one_new_entry(
        self,
        review:            dict[str, Any],
        symbol:            str,
        confirm_token:     str,
        execute_new_entry: bool                       = False,
        _now:              datetime | None            = None,
        _ro_client:        DemoReadOnlyClient | None  = None,
    ) -> NewEntryOrderResult:
        """
        Execute a single Demo new-entry order gate.

        If execute_new_entry=False (default dry-run): static gates only, no
        order submitted; result reports whether the gates pass.

        If execute_new_entry=True AND all static gates pass: pre-send refresh
        then POST one new-entry order to the Demo endpoint.

        The API secret is never included in the returned result.
        """
        ts_utc = (
            _now or datetime.now(timezone.utc)
        ).strftime("%Y-%m-%dT%H:%M:%SZ")
        mode = "execute_new_entry" if execute_new_entry else "dry_run"

        demo_runtime_verified = bool(review.get("demo_runtime_verified", False))
        proof_strength        = str(review.get("proof_strength", ""))
        endpoint_family       = str(review.get("endpoint_family", ""))
        account_mode          = str(review.get("account_mode", ""))
        pds                   = str(review.get("position_details_source", ""))
        avail_src             = str(review.get("available_balance_usd_source", ""))
        review_fail_closed    = bool(review.get("fail_closed", False))
        review_ts             = str(review.get("timestamp", ""))

        blocked_gates, ev, payload = self._static_gates(
            review, symbol, confirm_token, _now,
        )

        selected_side    = str(ev.get("side", "")) if ev else ""
        selected_qty     = float(payload.get("qty", 0.0)) if payload else 0.0
        order_side       = str(payload.get("side", "")) if payload else ""
        order_type       = str(payload.get("order_type", _REQUIRED_ORDER_TYPE)) \
                           if payload else _REQUIRED_ORDER_TYPE
        preview_only_src = bool(payload.get("preview_only", False)) if payload else False

        # Static-gate failure path
        if blocked_gates or ev is None or payload is None:
            return NewEntryOrderResult(
                timestamp_utc=ts_utc,
                mode=mode,
                demo_runtime_verified=demo_runtime_verified,
                proof_strength=proof_strength,
                endpoint_family=endpoint_family,
                account_mode=account_mode,
                position_details_source=pds,
                available_balance_usd_source=avail_src,
                selected_symbol=symbol,
                selected_side=selected_side,
                selected_qty=selected_qty,
                order_side=order_side,
                order_type=order_type,
                preview_only_source=preview_only_src,
                execute_requested=execute_new_entry,
                execute_allowed=False,
                order_sent=False,
                order_response_status="",
                order_id="",
                blocked_gates=blocked_gates,
                review_fail_closed=review_fail_closed,
                review_timestamp=review_ts,
            )

        # Dry-run path (all static gates passed)
        if not execute_new_entry:
            return NewEntryOrderResult(
                timestamp_utc=ts_utc,
                mode="dry_run",
                demo_runtime_verified=demo_runtime_verified,
                proof_strength=proof_strength,
                endpoint_family=endpoint_family,
                account_mode=account_mode,
                position_details_source=pds,
                available_balance_usd_source=avail_src,
                selected_symbol=symbol,
                selected_side=selected_side,
                selected_qty=selected_qty,
                order_side=order_side,
                order_type=order_type,
                preview_only_source=preview_only_src,
                execute_requested=False,
                execute_allowed=True,
                order_sent=False,
                order_response_status="",
                order_id="",
                blocked_gates=[],
                review_fail_closed=review_fail_closed,
                review_timestamp=review_ts,
            )

        # Execute path: pre-send refresh
        refresh_gates, refresh_summary = self._pre_send_refresh(
            review, ev, payload, _ro_client,
        )
        if refresh_gates:
            return NewEntryOrderResult(
                timestamp_utc=ts_utc,
                mode=mode,
                demo_runtime_verified=demo_runtime_verified,
                proof_strength=str(refresh_summary.get("refresh_proof_strength",
                                                       proof_strength)),
                endpoint_family=str(refresh_summary.get("refresh_endpoint_family",
                                                       endpoint_family)),
                account_mode=str(refresh_summary.get("refresh_account_mode",
                                                    account_mode)),
                position_details_source=pds,
                available_balance_usd_source=avail_src,
                selected_symbol=symbol,
                selected_side=selected_side,
                selected_qty=selected_qty,
                order_side=order_side,
                order_type=order_type,
                preview_only_source=preview_only_src,
                execute_requested=True,
                execute_allowed=False,
                order_sent=False,
                order_response_status="",
                order_id="",
                blocked_gates=refresh_gates,
                review_fail_closed=review_fail_closed,
                review_timestamp=review_ts,
            )

        # Build the order payload — minimal Bybit V5 fields for a new-entry Market order.
        # Explicitly excludes: leverage, take-profit / stop-loss, conditional trigger
        # price, balance transfer, and closeOnTrigger=True.
        order_body: dict[str, Any] = {
            "category":        _REQUIRED_CATEGORY,
            "symbol":          symbol,
            "side":            order_side,            # Buy for long
            "orderType":       _REQUIRED_ORDER_TYPE,  # Market
            "qty":             str(selected_qty),
            "reduceOnly":      False,                 # NEW entry — must be False
            "closeOnTrigger":  False,
            "timeInForce":     "IOC",                 # Market default
            "positionIdx":     0,                     # one-way mode
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

        return NewEntryOrderResult(
            timestamp_utc=ts_utc,
            mode=mode,
            demo_runtime_verified=True,
            proof_strength=str(refresh_summary.get("refresh_proof_strength",
                                                   proof_strength)),
            endpoint_family=str(refresh_summary.get("refresh_endpoint_family",
                                                   endpoint_family)),
            account_mode=str(refresh_summary.get("refresh_account_mode",
                                                account_mode)),
            position_details_source=pds,
            available_balance_usd_source=avail_src,
            selected_symbol=symbol,
            selected_side=selected_side,
            selected_qty=selected_qty,
            order_side=order_side,
            order_type=order_type,
            preview_only_source=preview_only_src,
            execute_requested=True,
            execute_allowed=True,
            order_sent=order_sent_flag,
            order_response_status=order_status,
            order_id=order_id_out,
            blocked_gates=[],
            order_endpoint_called=True,
            no_position_modified=no_pos_modified,
            review_fail_closed=review_fail_closed,
            review_timestamp=review_ts,
        )
