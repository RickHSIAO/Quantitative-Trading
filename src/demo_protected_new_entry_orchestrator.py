"""
src/demo_protected_new_entry_orchestrator.py
TASK-014S: Protected New-entry Orchestrator / Entry + Stop Attach Mock Chain.

Pure-computation / mock-safe orchestrator that chains:

  (1) TASK-014P market-backed new-entry review (read from JSON dict)
  (2) TASK-014Q protected-entry policy plan      (read from JSON dict)
  (3) TASK-014R stop-loss attachment payload     (built in-process; mock only)

into a single all-or-fail mock pipeline.  In dry-run mode no mock entry /
no mock attach occur — the chain only validates that every gate from
TASK-014L review + TASK-014Q protection + TASK-014R stop-attach would pass.
In --mock-chain mode synthetic envelopes are produced for entry + stop
attach + post-fill verification, but NO network call is ever made.

This module DOES NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit / src.bybit_executor
  * import src.demo_new_entry_sender         (the live order sender)
  * import src.demo_close_only_sender
  * import src.demo_emergency_close_sender
  * import scripts.execute_*
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing) — TASK-014S
    is deliberately mock-only; lifting G20 is reserved for TASK-014T+
  * trigger emergency close (recommended_action='emergency_close_preview'
    is a recommendation only; no sender is invoked here)

Lifecycle (mock chain):
  Phase A  validate review (12 gates)
  Phase B  validate protection (12 gates)
  Phase C  validate stop direction (defense-in-depth, also covered in B)
  Phase D  validate confirm token (only required for --mock-chain)
  Phase E  build stop payload preview (TASK-014R sender, no network)
  Phase F  (mock-chain only) synthesize mock entry order success
  Phase G  (mock-chain only) synthesize mock post-fill position
  Phase H  (mock-chain only) invoke TASK-014R stop-attach mock_execute_stop
  Phase I  (mock-chain only) build final MOCK_PROTECTED state OR
           MOCK_PROTECTED_ENTRY_FAIL_CLOSED with
           recommended_action='emergency_close_preview' if H fails.

Confirm-token pattern (only required for --mock-chain):
  CONFIRM_DEMO_PROTECTED_ENTRY_YYYYMMDD  (today UTC)

This module ALWAYS keeps these safety invariants True:
  no_orders_sent           = True
  order_endpoint_called    = False
  stop_endpoint_called     = False
  no_position_modified     = True
  no_live_endpoint         = True
  no_batch_order           = True
  no_close_only_path       = True
  emergency_close_invoked  = False
  secret_value_observed    = False
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any

# TASK-014R sender is used to build the stop payload preview and, under
# --mock-chain, to produce the synthetic stop-attach success envelope.  Both
# code paths through TASK-014R are guaranteed network-free by TASK-014R's
# own tests (urlopen sentinel + AST scan).
from src.demo_stop_loss_attachment_sender import (
    STATUS_DRY_RUN_ALLOWED   as _SA_DRY_RUN_ALLOWED,
    STATUS_MOCK_SUCCESS      as _SA_MOCK_SUCCESS,
    STOP_ATTACH_ENDPOINT,
    DemoStopLossAttachmentSender,
    StopAttachmentResult,
)


# ---------------------------------------------------------------------------
# Endpoint allowlist (DEMO-ONLY; informational — never invoked here)
# ---------------------------------------------------------------------------

ORDER_CREATE_ENDPOINT     = "/v5/order/create"
DEMO_ENDPOINT_FAMILY      = "bybit_demo"


# ---------------------------------------------------------------------------
# Status / protected-entry constants
# ---------------------------------------------------------------------------

STATUS_DRY_RUN_ALLOWED        = "DRY_RUN_PROTECTED_ENTRY_CHAIN_ALLOWED"
STATUS_DRY_RUN_BLOCKED        = "DRY_RUN_PROTECTED_ENTRY_CHAIN_BLOCKED"
STATUS_MOCK_SUCCESS           = "MOCK_PROTECTED_ENTRY_SUCCESS"
STATUS_MOCK_FAIL_CLOSED       = "MOCK_PROTECTED_ENTRY_FAIL_CLOSED"
STATUS_FAIL_CLOSED            = "FAIL_CLOSED"

PROTECTED_STATUS_DRY_RUN_PREVIEW = "DRY_RUN_PREVIEW"
PROTECTED_STATUS_MOCK_PROTECTED  = "MOCK_PROTECTED"
PROTECTED_STATUS_MOCK_NAKED      = "MOCK_NAKED"       # forbidden outcome
PROTECTED_STATUS_FAIL_CLOSED     = "FAIL_CLOSED"

RECOMMENDED_ACTION_NONE              = ""
RECOMMENDED_ACTION_EMERGENCY_PREVIEW = "emergency_close_preview"


# ---------------------------------------------------------------------------
# Gate names
# ---------------------------------------------------------------------------

# Review gates (Phase A)
GATE_REVIEW_MISSING                          = "review_report_missing"
GATE_REVIEW_SYMBOL_NOT_IN_PAYLOAD            = "review_symbol_not_in_accepted_candidates"
GATE_REVIEW_FAIL_CLOSED                      = "review_fail_closed"
GATE_REVIEW_DEMO_RUNTIME_NOT_VERIFIED        = "review_demo_runtime_not_verified"
GATE_REVIEW_PROOF_NOT_STRONG                 = "review_proof_not_strong"
GATE_REVIEW_ENDPOINT_NOT_BYBIT_DEMO          = "review_endpoint_not_bybit_demo"
GATE_REVIEW_ACCOUNT_NOT_DEMO                 = "review_account_mode_not_demo"
GATE_REVIEW_POSITION_NOT_REAL_READONLY       = "review_position_details_source_not_real_readonly"
GATE_REVIEW_MISSING_REALTIME_PRICE_GUARD     = "review_missing_realtime_price_guard"
GATE_REVIEW_PAYLOAD_PREVIEW_ONLY_FALSE       = "review_payload_preview_only_must_be_true"
GATE_REVIEW_PAYLOAD_ORDER_SENT_TRUE          = "review_payload_order_sent_must_be_false"
GATE_REVIEW_PAYLOAD_ORDER_ENDPOINT_CALLED    = "review_payload_order_endpoint_called_must_be_false"

# Protection gates (Phase B)
GATE_PROTECTION_MISSING                      = "protection_report_missing"
GATE_PROTECTION_SYMBOL_MISMATCH              = "protection_symbol_mismatch"
GATE_PROTECTION_MISSING_REALTIME_GUARD       = "protection_missing_realtime_price_guard"
GATE_PROTECTION_STOP_NOT_REQUIRED            = "protection_stop_loss_attach_not_required"
GATE_PROTECTION_EXECUTE_ALLOWED_TRUE         = "protection_protected_entry_execute_allowed_must_be_false"
GATE_PROTECTION_UNEXPECTED_EXECUTE_REASON    = "protection_unexpected_protected_entry_execute_reason"
GATE_PROTECTION_STOP_ENDPOINT_CALLED         = "protection_stop_endpoint_called_must_be_false"
GATE_PROTECTION_ORDER_ENDPOINT_CALLED        = "protection_order_endpoint_called_must_be_false"
GATE_PROTECTION_POSITION_MODIFIED            = "protection_no_position_modified_must_be_true"
GATE_PROTECTION_STOP_PRICE_NOT_POSITIVE      = "protection_stop_price_not_positive"
GATE_PROTECTION_LONG_STOP_NOT_BELOW_ENTRY    = "long_stop_must_be_below_entry"
GATE_PROTECTION_SHORT_STOP_NOT_ABOVE_ENTRY   = "short_stop_must_be_above_entry"

# Stop-attach (Phase E/H) — surfaced via TASK-014R sender's own gates
GATE_STOP_ATTACH_BUILD_FAILED                = "stop_attach_payload_build_failed"
GATE_STOP_ATTACH_MOCK_FAILED                 = "stop_attach_mock_failed"

# Token gate (Phase D)
GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK_CHAIN    = "invalid_confirm_token_for_mock_chain"

# Required values
_REQUIRED_PROOF_STRENGTH       = "STRONG"
_REQUIRED_ENDPOINT_FAMILY      = "bybit_demo"
_REQUIRED_ACCOUNT_MODE         = "demo"
_REQUIRED_POSITION_SOURCE      = "real_readonly"
_EXPECTED_EXECUTE_REASON_VALUES = (
    "stop_loss_attachment_not_implemented",
    # accept any value that mentions "stop_loss_attachment" or "not_implemented"
    # via fuzzy fallback below — kept as a constant for readability
)

# Confirm-token
_TOKEN_PREFIX = "CONFIRM_DEMO_PROTECTED_ENTRY_"


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class ProtectedEntryChainResult:
    """
    Read-only result of one protected new-entry mock orchestration.

    Safety invariants (always; enforced by tests):
      no_orders_sent          = True
      order_endpoint_called   = False
      stop_endpoint_called    = False
      no_position_modified    = True
      no_live_endpoint        = True
      no_batch_order          = True
      no_close_only_path      = True
      emergency_close_invoked = False
      secret_value_observed   = False
    """
    timestamp_utc:                      str
    mode:                               str          # "dry_run" / "mock_chain"
    dry_run:                            bool
    mock_chain:                         bool
    selected_symbol:                    str
    selected_side:                      str          # "long" / "short" / ""
    qty:                                float
    entry_reference_price:              float
    stop_price:                         float
    realtime_price_guard_verified:      bool
    protection_status:                  str          # passes through TASK-014Q status
    confirm_token_prefix:               str
    confirm_token_valid:                bool

    # Stop payload preview (TASK-014R shape; built via DemoStopLossAttachmentSender)
    stop_payload_preview:               dict         = field(default_factory=dict)
    stop_payload_preview_only:          bool         = False

    # Mock-chain artifacts (all False/empty unless mock_chain=True and gates pass)
    mock_entry_order_sent:              bool         = False
    mock_order_id:                      str          = ""
    mock_post_fill_position:            dict         = field(default_factory=dict)
    mock_stop_attached:                 bool         = False
    mock_stop_attach_id:                str          = ""
    mock_final_position_stop_price:     float        = 0.0
    missing_stop_price:                 bool         = True
    protected_entry_status:             str          = PROTECTED_STATUS_FAIL_CLOSED

    # Failure-path bookkeeping
    fail_closed:                        bool         = True
    recommended_action:                 str          = RECOMMENDED_ACTION_NONE

    # Endpoint metadata (recorded; not contacted)
    endpoint_family:                    str          = DEMO_ENDPOINT_FAMILY
    order_create_endpoint:              str          = ORDER_CREATE_ENDPOINT
    stop_attach_endpoint:               str          = STOP_ATTACH_ENDPOINT

    # Safety invariants (always True after build)
    no_orders_sent:                     bool         = True
    order_endpoint_called:              bool         = False
    stop_endpoint_called:               bool         = False
    no_position_modified:               bool         = True
    no_live_endpoint:                   bool         = True
    no_batch_order:                     bool         = True
    no_close_only_path:                 bool         = True
    emergency_close_invoked:            bool         = False
    secret_value_observed:              bool         = False

    blocked_gates:                      list[str]    = field(default_factory=list)
    status:                             str          = STATUS_FAIL_CLOSED
    next_required_task:                 str          = (
        "TASK-014T_real_trading_stop_endpoint_probe"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                       self.timestamp_utc,
            "timestamp_utc":                   self.timestamp_utc,
            "mode":                            self.mode,
            "dry_run":                         self.dry_run,
            "mock_chain":                      self.mock_chain,
            "selected_symbol":                 self.selected_symbol,
            "selected_side":                   self.selected_side,
            "qty":                             self.qty,
            "entry_reference_price":           self.entry_reference_price,
            "stop_price":                      self.stop_price,
            "realtime_price_guard_verified":   self.realtime_price_guard_verified,
            "protection_status":               self.protection_status,
            "confirm_token_prefix":            self.confirm_token_prefix,
            "confirm_token_valid":             self.confirm_token_valid,
            "stop_payload_preview":            dict(self.stop_payload_preview),
            "stop_payload_preview_only":       self.stop_payload_preview_only,
            "mock_entry_order_sent":           self.mock_entry_order_sent,
            "mock_order_id":                   self.mock_order_id,
            "mock_post_fill_position":         dict(self.mock_post_fill_position),
            "mock_stop_attached":              self.mock_stop_attached,
            "mock_stop_attach_id":             self.mock_stop_attach_id,
            "mock_final_position_stop_price":  self.mock_final_position_stop_price,
            "missing_stop_price":              self.missing_stop_price,
            "protected_entry_status":          self.protected_entry_status,
            "fail_closed":                     self.fail_closed,
            "recommended_action":              self.recommended_action,
            "endpoint_family":                 self.endpoint_family,
            "order_create_endpoint":           self.order_create_endpoint,
            "stop_attach_endpoint":            self.stop_attach_endpoint,
            "no_orders_sent":                  self.no_orders_sent,
            "order_endpoint_called":           self.order_endpoint_called,
            "stop_endpoint_called":            self.stop_endpoint_called,
            "no_position_modified":            self.no_position_modified,
            "no_live_endpoint":                self.no_live_endpoint,
            "no_batch_order":                  self.no_batch_order,
            "no_close_only_path":              self.no_close_only_path,
            "emergency_close_invoked":         self.emergency_close_invoked,
            "secret_value_observed":           self.secret_value_observed,
            "blocked_gates":                   list(self.blocked_gates),
            "status":                          self.status,
            "next_required_task":              self.next_required_task,
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
    """Validate CONFIRM_DEMO_PROTECTED_ENTRY_YYYYMMDD (today UTC)."""
    if not token.startswith(_TOKEN_PREFIX):
        return False
    suffix = token[len(_TOKEN_PREFIX):]
    if len(suffix) != 8 or not suffix.isdigit():
        return False
    today = (_now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return suffix == today


def _find_accepted_payload(
    review: dict[str, Any], symbol: str,
) -> tuple[dict | None, dict | None]:
    """Return (evaluation_dict, payload_dict) when symbol is accepted in review."""
    if not symbol:
        return None, None
    for ev in (review.get("accepted_candidates") or []):
        if str(ev.get("symbol", "")) == symbol:
            return ev, ev.get("payload") or None
    return None, None


# ---------------------------------------------------------------------------
# Orchestrator
# ---------------------------------------------------------------------------

class DemoProtectedNewEntryOrchestrator:
    """
    Demo-only protected new-entry mock orchestrator.

    Holds no network client; reads no environment variables.  Validates one
    review + one protection report for one symbol and either reports
    DRY-RUN allowed, MOCK-chain success, or fail-closed (with a recommended
    action).  Under no path does this orchestrator open a socket, lift the
    TASK-014L sender G20 gate, or call an emergency-close sender.
    """

    def __init__(self) -> None:
        # No credentials, no clients, no env reads.
        self._stop_attach_sender = DemoStopLossAttachmentSender()

    # -- public ------------------------------------------------------------

    def submit_chain(
        self,
        review:             dict[str, Any] | None,
        protection:         dict[str, Any] | None,
        symbol:             str,
        confirm_token:      str  = "",
        mock_chain:         bool = False,
        _now:               datetime | None = None,
        _simulate_stop_attach_failure: bool = False,
    ) -> ProtectedEntryChainResult:
        """
        Run the protected-new-entry chain end-to-end (mock-only).

        Never contacts the network.  The optional
        ``_simulate_stop_attach_failure`` is a test-only hook that forces
        the Phase H mock-stop-attach to fail, producing
        MOCK_PROTECTED_ENTRY_FAIL_CLOSED with
        recommended_action=emergency_close_preview.
        """
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mode   = "mock_chain" if mock_chain else "dry_run"
        token_prefix = (confirm_token[:8] + "***") if confirm_token else ""

        blocked: list[str] = []

        # -- Phase A: review --------------------------------------------------
        if not isinstance(review, dict) or not review:
            blocked.append(GATE_REVIEW_MISSING)
            return self._fail_closed(
                ts_utc=ts_utc, mode=mode, mock_chain=mock_chain,
                symbol=symbol, token_prefix=token_prefix, blocked=blocked,
            )

        if bool(review.get("fail_closed", True)):
            blocked.append(GATE_REVIEW_FAIL_CLOSED)
        if not bool(review.get("demo_runtime_verified", False)):
            blocked.append(GATE_REVIEW_DEMO_RUNTIME_NOT_VERIFIED)
        if str(review.get("proof_strength", "")) != _REQUIRED_PROOF_STRENGTH:
            blocked.append(GATE_REVIEW_PROOF_NOT_STRONG)
        if str(review.get("endpoint_family", "")) != _REQUIRED_ENDPOINT_FAMILY:
            blocked.append(GATE_REVIEW_ENDPOINT_NOT_BYBIT_DEMO)
        if str(review.get("account_mode", "")) != _REQUIRED_ACCOUNT_MODE:
            blocked.append(GATE_REVIEW_ACCOUNT_NOT_DEMO)
        if str(review.get("position_details_source", "")) != _REQUIRED_POSITION_SOURCE:
            blocked.append(GATE_REVIEW_POSITION_NOT_REAL_READONLY)
        if not bool(review.get("realtime_price_guard_verified", False)):
            blocked.append(GATE_REVIEW_MISSING_REALTIME_PRICE_GUARD)

        ev, payload = _find_accepted_payload(review, symbol)
        if ev is None or payload is None:
            blocked.append(GATE_REVIEW_SYMBOL_NOT_IN_PAYLOAD)
            # Continue to also surface protection issues; payload-level checks
            # below are skipped because payload is None.
        else:
            if not bool(payload.get("preview_only", False)):
                blocked.append(GATE_REVIEW_PAYLOAD_PREVIEW_ONLY_FALSE)
            if bool(payload.get("order_sent", True)):
                blocked.append(GATE_REVIEW_PAYLOAD_ORDER_SENT_TRUE)
            if bool(payload.get("order_endpoint_called", True)):
                blocked.append(GATE_REVIEW_PAYLOAD_ORDER_ENDPOINT_CALLED)

        # -- Phase B: protection ---------------------------------------------
        if not isinstance(protection, dict) or not protection:
            blocked.append(GATE_PROTECTION_MISSING)
            return self._fail_closed(
                ts_utc=ts_utc, mode=mode, mock_chain=mock_chain,
                symbol=symbol, token_prefix=token_prefix, blocked=blocked,
            )

        if str(protection.get("selected_symbol", "")) != symbol or not symbol:
            blocked.append(GATE_PROTECTION_SYMBOL_MISMATCH)

        if not bool(protection.get("realtime_price_guard_verified", False)):
            blocked.append(GATE_PROTECTION_MISSING_REALTIME_GUARD)

        if not bool(protection.get("stop_loss_attach_required", False)):
            blocked.append(GATE_PROTECTION_STOP_NOT_REQUIRED)

        if bool(protection.get("protected_entry_execute_allowed", True)):
            blocked.append(GATE_PROTECTION_EXECUTE_ALLOWED_TRUE)

        # Execute reason should be the policy placeholder, not a misleading
        # value claiming "ok".  Accept anything that contains "not_implemented".
        exec_reason = str(protection.get("protected_entry_execute_reason", ""))
        if "not_implemented" not in exec_reason:
            blocked.append(GATE_PROTECTION_UNEXPECTED_EXECUTE_REASON)

        if bool(protection.get("stop_endpoint_called", True)):
            blocked.append(GATE_PROTECTION_STOP_ENDPOINT_CALLED)
        if bool(protection.get("order_endpoint_called", True)):
            blocked.append(GATE_PROTECTION_ORDER_ENDPOINT_CALLED)
        if not bool(protection.get("no_position_modified", False)):
            blocked.append(GATE_PROTECTION_POSITION_MODIFIED)

        # -- Phase C: stop direction (defense-in-depth) ----------------------
        side    = str(protection.get("selected_side", "")).strip().lower()
        qty     = _safe_float(protection.get("selected_qty", 0.0))
        entry   = _safe_float(protection.get("entry_reference_price", 0.0))
        stop_px = _safe_float(protection.get("stop_price", 0.0))

        if stop_px <= 0:
            blocked.append(GATE_PROTECTION_STOP_PRICE_NOT_POSITIVE)
        if side == "long" and entry > 0 and stop_px > 0 and not (stop_px < entry):
            blocked.append(GATE_PROTECTION_LONG_STOP_NOT_BELOW_ENTRY)
        if side == "short" and entry > 0 and stop_px > 0 and not (stop_px > entry):
            blocked.append(GATE_PROTECTION_SHORT_STOP_NOT_ABOVE_ENTRY)

        # -- Phase D: confirm token (only required for --mock-chain) ---------
        token_valid = False
        if mock_chain:
            token_valid = _validate_confirm_token(confirm_token, _now=_now)
            if not token_valid:
                blocked.append(GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK_CHAIN)

        # -- Phase E: build stop payload preview via TASK-014R sender --------
        # We build the payload preview only — never call mock_execute_stop
        # here; that happens in Phase H below (only when mock_chain=True).
        stop_preview_result: StopAttachmentResult = (
            self._stop_attach_sender.submit_stop_attachment(
                protection=protection, symbol=symbol,
                confirm_token="",                 # not needed in dry-run
                mock_execute_stop=False,
                _now=_now,
            )
        )
        stop_payload = dict(stop_preview_result.payload_preview)
        stop_payload_preview_only = bool(stop_preview_result.payload_preview_only)
        # Promote any new sender-side gate failures (defense-in-depth).
        for g in stop_preview_result.blocked_gates:
            if g not in blocked:
                blocked.append(g)
        # If the sender refused to build a payload for reasons other than
        # gate-state we already accumulated, surface a generic build-fail.
        if not stop_payload and not blocked:
            blocked.append(GATE_STOP_ATTACH_BUILD_FAILED)

        # -- Short-circuit on any failure ------------------------------------
        if blocked:
            return ProtectedEntryChainResult(
                timestamp_utc=ts_utc,
                mode=mode,
                dry_run=not mock_chain,
                mock_chain=mock_chain,
                selected_symbol=symbol,
                selected_side=side if side in ("long", "short") else "",
                qty=qty,
                entry_reference_price=entry,
                stop_price=stop_px,
                realtime_price_guard_verified=bool(
                    protection.get("realtime_price_guard_verified", False)
                ),
                protection_status=str(protection.get("protected_entry_status", "")),
                confirm_token_prefix=token_prefix,
                confirm_token_valid=token_valid,
                stop_payload_preview=stop_payload,
                stop_payload_preview_only=stop_payload_preview_only,
                mock_entry_order_sent=False,
                mock_order_id="",
                mock_post_fill_position={},
                mock_stop_attached=False,
                mock_stop_attach_id="",
                mock_final_position_stop_price=0.0,
                missing_stop_price=True,
                protected_entry_status=PROTECTED_STATUS_FAIL_CLOSED,
                fail_closed=True,
                recommended_action=RECOMMENDED_ACTION_NONE,
                blocked_gates=blocked,
                status=STATUS_FAIL_CLOSED,
            )

        # -- Dry-run success path --------------------------------------------
        if not mock_chain:
            return ProtectedEntryChainResult(
                timestamp_utc=ts_utc,
                mode=mode,
                dry_run=True,
                mock_chain=False,
                selected_symbol=symbol,
                selected_side=side,
                qty=qty,
                entry_reference_price=entry,
                stop_price=stop_px,
                realtime_price_guard_verified=True,
                protection_status=str(protection.get("protected_entry_status", "")),
                confirm_token_prefix=token_prefix,
                confirm_token_valid=token_valid,
                stop_payload_preview=stop_payload,
                stop_payload_preview_only=stop_payload_preview_only,
                mock_entry_order_sent=False,
                mock_order_id="",
                mock_post_fill_position={},
                mock_stop_attached=False,
                mock_stop_attach_id="",
                mock_final_position_stop_price=0.0,
                missing_stop_price=True,
                protected_entry_status=PROTECTED_STATUS_DRY_RUN_PREVIEW,
                fail_closed=False,
                recommended_action=RECOMMENDED_ACTION_NONE,
                blocked_gates=[],
                status=STATUS_DRY_RUN_ALLOWED,
            )

        # -- Phases F-I: mock chain ------------------------------------------
        mock_entry_id  = f"MOCK-ENTRY-{symbol}-{int(entry * 100):d}"

        # Phase G: synthetic post-fill snapshot (stop_price=0 initially —
        # the entire point of TASK-014Q was that this naked state is the
        # vulnerability window; the orchestrator records it explicitly).
        mock_post_fill = {
            "symbol":      symbol,
            "side":        side,
            "qty":         qty,
            "entry_price": entry,
            "stop_price":  0.0,
            "missing_stop_price": True,
            "mock":        True,
        }

        # Phase H: stop-attach via TASK-014R mock execute (still no network)
        if _simulate_stop_attach_failure:
            stop_mock = None
            attach_ok = False
        else:
            stop_mock = self._stop_attach_sender.submit_stop_attachment(
                protection=protection, symbol=symbol,
                confirm_token=_synth_stop_attach_token(_now=_now),
                mock_execute_stop=True, _now=_now,
            )
            attach_ok = (
                stop_mock.status == _SA_MOCK_SUCCESS
                and stop_mock.mock_stop_attached is True
                and not stop_mock.blocked_gates
            )

        if not attach_ok:
            # Mock attach failed.  Per TASK-014S spec, fail closed and
            # recommend emergency_close_preview.  Do NOT mark protected.
            # No emergency close is actually triggered here.
            return ProtectedEntryChainResult(
                timestamp_utc=ts_utc,
                mode=mode,
                dry_run=False,
                mock_chain=True,
                selected_symbol=symbol,
                selected_side=side,
                qty=qty,
                entry_reference_price=entry,
                stop_price=stop_px,
                realtime_price_guard_verified=True,
                protection_status=str(protection.get("protected_entry_status", "")),
                confirm_token_prefix=token_prefix,
                confirm_token_valid=token_valid,
                stop_payload_preview=stop_payload,
                stop_payload_preview_only=stop_payload_preview_only,
                mock_entry_order_sent=True,
                mock_order_id=mock_entry_id,
                mock_post_fill_position=mock_post_fill,
                mock_stop_attached=False,
                mock_stop_attach_id="",
                mock_final_position_stop_price=0.0,
                missing_stop_price=True,
                protected_entry_status=PROTECTED_STATUS_FAIL_CLOSED,
                fail_closed=True,
                recommended_action=RECOMMENDED_ACTION_EMERGENCY_PREVIEW,
                blocked_gates=[GATE_STOP_ATTACH_MOCK_FAILED],
                status=STATUS_MOCK_FAIL_CLOSED,
            )

        # Phase I: final MOCK_PROTECTED state -------------------------------
        mock_attach_id = str(
            stop_mock.mock_response.get("result", {}).get("stop_attach_id", "")
            if stop_mock else ""
        )
        mock_final_position = {
            **mock_post_fill,
            "stop_price":          stop_px,
            "missing_stop_price":  False,
            "mock_stop_attach_id": mock_attach_id,
        }
        return ProtectedEntryChainResult(
            timestamp_utc=ts_utc,
            mode=mode,
            dry_run=False,
            mock_chain=True,
            selected_symbol=symbol,
            selected_side=side,
            qty=qty,
            entry_reference_price=entry,
            stop_price=stop_px,
            realtime_price_guard_verified=True,
            protection_status=str(protection.get("protected_entry_status", "")),
            confirm_token_prefix=token_prefix,
            confirm_token_valid=token_valid,
            stop_payload_preview=stop_payload,
            stop_payload_preview_only=stop_payload_preview_only,
            mock_entry_order_sent=True,
            mock_order_id=mock_entry_id,
            mock_post_fill_position=mock_final_position,
            mock_stop_attached=True,
            mock_stop_attach_id=mock_attach_id,
            mock_final_position_stop_price=stop_px,
            missing_stop_price=False,
            protected_entry_status=PROTECTED_STATUS_MOCK_PROTECTED,
            fail_closed=False,
            recommended_action=RECOMMENDED_ACTION_NONE,
            blocked_gates=[],
            status=STATUS_MOCK_SUCCESS,
        )

    # -- private -----------------------------------------------------------

    def _fail_closed(
        self,
        ts_utc:       str,
        mode:         str,
        mock_chain:   bool,
        symbol:       str,
        token_prefix: str,
        blocked:      list[str],
    ) -> ProtectedEntryChainResult:
        """Minimally-populated fail-closed result for early aborts."""
        return ProtectedEntryChainResult(
            timestamp_utc=ts_utc,
            mode=mode,
            dry_run=not mock_chain,
            mock_chain=mock_chain,
            selected_symbol=symbol,
            selected_side="",
            qty=0.0,
            entry_reference_price=0.0,
            stop_price=0.0,
            realtime_price_guard_verified=False,
            protection_status="",
            confirm_token_prefix=token_prefix,
            confirm_token_valid=False,
            stop_payload_preview={},
            stop_payload_preview_only=False,
            mock_entry_order_sent=False,
            mock_order_id="",
            mock_post_fill_position={},
            mock_stop_attached=False,
            mock_stop_attach_id="",
            mock_final_position_stop_price=0.0,
            missing_stop_price=True,
            protected_entry_status=PROTECTED_STATUS_FAIL_CLOSED,
            fail_closed=True,
            recommended_action=RECOMMENDED_ACTION_NONE,
            blocked_gates=blocked,
            status=STATUS_FAIL_CLOSED,
        )


# ---------------------------------------------------------------------------
# Helper used by Phase H to satisfy TASK-014R's token gate (mock-only)
# ---------------------------------------------------------------------------

def _synth_stop_attach_token(_now: datetime | None = None) -> str:
    """
    The TASK-014R sender requires a CONFIRM_DEMO_STOP_ATTACH_YYYYMMDD token
    under --mock-execute-stop.  When the orchestrator runs a mock chain it
    has ALREADY validated its own CONFIRM_DEMO_PROTECTED_ENTRY token; the
    inner stop-attach mock is purely synthetic and never opens a socket, so
    we synthesize a matching token here.  This is NOT a real credential —
    no API key, no secret, no signing material.
    """
    today = (_now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return f"CONFIRM_DEMO_STOP_ATTACH_{today}"


__all__ = [
    "ORDER_CREATE_ENDPOINT",
    "STOP_ATTACH_ENDPOINT",
    "DEMO_ENDPOINT_FAMILY",
    "STATUS_DRY_RUN_ALLOWED",
    "STATUS_DRY_RUN_BLOCKED",
    "STATUS_MOCK_SUCCESS",
    "STATUS_MOCK_FAIL_CLOSED",
    "STATUS_FAIL_CLOSED",
    "PROTECTED_STATUS_DRY_RUN_PREVIEW",
    "PROTECTED_STATUS_MOCK_PROTECTED",
    "PROTECTED_STATUS_MOCK_NAKED",
    "PROTECTED_STATUS_FAIL_CLOSED",
    "RECOMMENDED_ACTION_NONE",
    "RECOMMENDED_ACTION_EMERGENCY_PREVIEW",
    "GATE_REVIEW_MISSING",
    "GATE_REVIEW_SYMBOL_NOT_IN_PAYLOAD",
    "GATE_REVIEW_FAIL_CLOSED",
    "GATE_REVIEW_DEMO_RUNTIME_NOT_VERIFIED",
    "GATE_REVIEW_PROOF_NOT_STRONG",
    "GATE_REVIEW_ENDPOINT_NOT_BYBIT_DEMO",
    "GATE_REVIEW_ACCOUNT_NOT_DEMO",
    "GATE_REVIEW_POSITION_NOT_REAL_READONLY",
    "GATE_REVIEW_MISSING_REALTIME_PRICE_GUARD",
    "GATE_REVIEW_PAYLOAD_PREVIEW_ONLY_FALSE",
    "GATE_REVIEW_PAYLOAD_ORDER_SENT_TRUE",
    "GATE_REVIEW_PAYLOAD_ORDER_ENDPOINT_CALLED",
    "GATE_PROTECTION_MISSING",
    "GATE_PROTECTION_SYMBOL_MISMATCH",
    "GATE_PROTECTION_MISSING_REALTIME_GUARD",
    "GATE_PROTECTION_STOP_NOT_REQUIRED",
    "GATE_PROTECTION_EXECUTE_ALLOWED_TRUE",
    "GATE_PROTECTION_UNEXPECTED_EXECUTE_REASON",
    "GATE_PROTECTION_STOP_ENDPOINT_CALLED",
    "GATE_PROTECTION_ORDER_ENDPOINT_CALLED",
    "GATE_PROTECTION_POSITION_MODIFIED",
    "GATE_PROTECTION_STOP_PRICE_NOT_POSITIVE",
    "GATE_PROTECTION_LONG_STOP_NOT_BELOW_ENTRY",
    "GATE_PROTECTION_SHORT_STOP_NOT_ABOVE_ENTRY",
    "GATE_STOP_ATTACH_BUILD_FAILED",
    "GATE_STOP_ATTACH_MOCK_FAILED",
    "GATE_INVALID_CONFIRM_TOKEN_FOR_MOCK_CHAIN",
    "ProtectedEntryChainResult",
    "DemoProtectedNewEntryOrchestrator",
]
