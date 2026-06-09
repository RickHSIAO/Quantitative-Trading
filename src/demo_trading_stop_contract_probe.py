"""
src/demo_trading_stop_contract_probe.py
TASK-014T: Real Demo Trading-stop Endpoint Contract Probe / Permission Gate.

Pure-computation / mock-safe module that describes the Bybit V5
/v5/position/trading-stop endpoint contract (path / method / category /
required body fields / forbidden body fields) and validates a payload
preview against that contract.

Three modes are supported:

  1. preview              -- default.  No network at all.  Output the
                              contract description + payload preview.
  2. mock-permission      -- No network.  Synthetic retCode=0 envelope to
                              exercise the report pipeline / permission
                              gate path.
  3. real-permission-probe -- DISABLED in this task.  Even with
                              --allow-real-stop-probe + a valid
                              CONFIRM_DEMO_TRADING_STOP_PROBE_YYYYMMDD
                              token, the orchestrator returns
                              REAL_PROBE_NOT_IMPLEMENTED because we have
                              NOT yet designed a no-op real probe that
                              provably cannot modify any existing
                              position's stop_price.  Lifting this gate
                              is reserved for TASK-014U+ (Tiny Isolated
                              Position Plan / No-op Probe Design).

This module DOES NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit / src.bybit_executor
  * import src.demo_new_entry_sender
  * import src.demo_close_only_sender
  * import src.demo_emergency_close_sender
  * import src.demo_protected_new_entry_orchestrator
  * import scripts.execute_*
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)

The endpoint constants are stored as strings only and never used as
arguments to a network client.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Endpoint contract constants (string-only; never invoked)
# ---------------------------------------------------------------------------

ENDPOINT_FAMILY      = "bybit_demo"
BASE_URL_DEMO        = "https://api-demo.bybit.com"   # informational only
TRADING_STOP_PATH    = "/v5/position/trading-stop"
TRADING_STOP_METHOD  = "POST"

CATEGORY_LINEAR        = "linear"
TPSL_MODE_FULL         = "Full"
SL_TRIGGER_MARK_PRICE  = "MarkPrice"
SL_TRIGGER_LAST_PRICE  = "LastPrice"
POSITION_IDX_ONE_WAY   = 0

# Order-create endpoint constant kept here ONLY to allow tests to confirm
# it is not present in any payload preview.  Never invoked.
ORDER_CREATE_PATH      = "/v5/order/create"


# ---------------------------------------------------------------------------
# Status / gate constants
# ---------------------------------------------------------------------------

STATUS_PREVIEW_OK              = "TRADING_STOP_CONTRACT_PREVIEW_OK"
STATUS_MOCK_PERMISSION_OK      = "MOCK_TRADING_STOP_PERMISSION_OK"
STATUS_REAL_PROBE_NOT_IMPL     = "REAL_PROBE_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED             = "FAIL_CLOSED"

MODE_PREVIEW                   = "preview"
MODE_MOCK_PERMISSION           = "mock_permission"
MODE_REAL_PERMISSION_PROBE     = "real_permission_probe"

# Gates
GATE_PROTECTION_REPORT_MISSING       = "protection_report_missing"
GATE_SYMBOL_MISMATCH                 = "symbol_mismatch"
GATE_MISSING_STOP_LOSS               = "stop_loss_missing"
GATE_NON_POSITIVE_STOP_LOSS          = "stop_loss_not_positive"
GATE_INVALID_TPSL_MODE               = "invalid_tpsl_mode"
GATE_INVALID_SL_TRIGGER_BY           = "invalid_sl_trigger_by"
GATE_INVALID_POSITION_IDX            = "invalid_position_idx"
GATE_INVALID_CATEGORY                = "invalid_category"
GATE_PAYLOAD_INCLUDES_TAKE_PROFIT    = "payload_includes_take_profit"
GATE_PAYLOAD_INCLUDES_LEVERAGE       = "payload_includes_leverage"
GATE_PAYLOAD_INCLUDES_ORDER_FIELDS   = "payload_includes_order_fields"
GATE_PAYLOAD_INCLUDES_TRANSFER       = "payload_includes_transfer_or_funds"
GATE_PAYLOAD_INCLUDES_LIVE_HOSTNAME  = "payload_includes_live_hostname"
GATE_PAYLOAD_INCLUDES_ORDER_PATH     = "payload_includes_order_create_path"
GATE_INVALID_CONFIRM_TOKEN           = "invalid_confirm_token_for_real_probe"
GATE_REAL_PROBE_NOT_IMPL             = "real_probe_not_implemented"

_TOKEN_PREFIX = "CONFIRM_DEMO_TRADING_STOP_PROBE_"

_VALID_TPSL_MODES        = (TPSL_MODE_FULL,)
_VALID_SL_TRIGGER_VALUES = (SL_TRIGGER_MARK_PRICE, SL_TRIGGER_LAST_PRICE)

_FORBIDDEN_PAYLOAD_KEYS_ORDER = (
    "side", "qty", "orderType", "order_type",
    "price", "timeInForce", "reduceOnly", "reduce_only",
    "closeOnTrigger", "close_on_trigger",
)
_FORBIDDEN_PAYLOAD_KEYS_FUNDS = (
    "transfer", "withdraw", "deposit",
    "transferAmount", "withdrawAmount", "depositAmount",
)
_FORBIDDEN_PAYLOAD_KEYS_LEVERAGE = ("leverage", "buyLeverage", "sellLeverage")
_FORBIDDEN_PAYLOAD_KEYS_TP       = ("takeProfit", "take_profit", "tpTriggerBy")

_LIVE_HOST_PARTS = ("api.bybit.com", "api-testnet.bybit.com")


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TradingStopContractResult:
    """Read-only result of one trading-stop contract probe attempt."""
    timestamp_utc:           str
    mode:                    str
    selected_symbol:         str
    stop_loss:               float
    payload_preview:         dict[str, Any]   = field(default_factory=dict)

    # Contract description (always populated; informational)
    endpoint_family:         str  = ENDPOINT_FAMILY
    base_url:                str  = BASE_URL_DEMO   # informational only
    path:                    str  = TRADING_STOP_PATH
    method:                  str  = TRADING_STOP_METHOD
    category:                str  = CATEGORY_LINEAR
    tpsl_mode:               str  = TPSL_MODE_FULL
    sl_trigger_by:           str  = SL_TRIGGER_MARK_PRICE
    position_idx:            int  = POSITION_IDX_ONE_WAY

    # Confirm-token bookkeeping
    confirm_token_prefix:    str  = ""
    confirm_token_valid:     bool = False

    # Mode flags
    real_probe_allowed:      bool = False
    real_probe_implemented:  bool = False
    mock_permission_status:  bool = False

    # Mock envelope (only populated in mock-permission mode)
    mock_response:           dict[str, Any] = field(default_factory=dict)

    # Safety invariants (always True / False as documented)
    stop_endpoint_called:    bool = False
    order_endpoint_called:   bool = False
    no_position_modified:    bool = True
    no_live_endpoint:        bool = True
    no_orders_sent:          bool = True
    no_batch_order:          bool = True
    no_close_only_path:      bool = True
    emergency_close_invoked: bool = False
    secret_value_observed:   bool = False

    blocked_gates:           list[str] = field(default_factory=list)
    status:                  str = STATUS_FAIL_CLOSED
    next_required_task:      str = (
        "TASK-014U_real_demo_trading_stop_no_op_probe_design"
    )

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":             self.timestamp_utc,
            "timestamp_utc":         self.timestamp_utc,
            "mode":                  self.mode,
            "selected_symbol":       self.selected_symbol,
            "stop_loss":             self.stop_loss,
            "payload_preview":       dict(self.payload_preview),
            "endpoint_family":       self.endpoint_family,
            "base_url":              self.base_url,
            "path":                  self.path,
            "method":                self.method,
            "category":              self.category,
            "tpsl_mode":             self.tpsl_mode,
            "sl_trigger_by":         self.sl_trigger_by,
            "position_idx":          self.position_idx,
            "confirm_token_prefix":  self.confirm_token_prefix,
            "confirm_token_valid":   self.confirm_token_valid,
            "real_probe_allowed":    self.real_probe_allowed,
            "real_probe_implemented": self.real_probe_implemented,
            "mock_permission_status": self.mock_permission_status,
            "mock_response":         dict(self.mock_response),
            "stop_endpoint_called":  self.stop_endpoint_called,
            "order_endpoint_called": self.order_endpoint_called,
            "no_position_modified":  self.no_position_modified,
            "no_live_endpoint":      self.no_live_endpoint,
            "no_orders_sent":        self.no_orders_sent,
            "no_batch_order":        self.no_batch_order,
            "no_close_only_path":    self.no_close_only_path,
            "emergency_close_invoked": self.emergency_close_invoked,
            "secret_value_observed": self.secret_value_observed,
            "blocked_gates":         list(self.blocked_gates),
            "status":                self.status,
            "next_required_task":    self.next_required_task,
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
    """Validate CONFIRM_DEMO_TRADING_STOP_PROBE_YYYYMMDD (today UTC)."""
    if not token.startswith(_TOKEN_PREFIX):
        return False
    suffix = token[len(_TOKEN_PREFIX):]
    if len(suffix) != 8 or not suffix.isdigit():
        return False
    today = (_now or datetime.now(timezone.utc)).strftime("%Y%m%d")
    return suffix == today


def build_payload_preview(
    symbol: str,
    stop_loss: float,
    sl_trigger_by: str = SL_TRIGGER_MARK_PRICE,
) -> dict[str, Any]:
    """
    Build the documented Bybit V5 /v5/position/trading-stop body preview.

    Excludes (intentionally): takeProfit, leverage, transfer/withdraw/deposit,
    order-create fields (side, qty, orderType, price, timeInForce,
    reduceOnly, closeOnTrigger).  Only stop-loss is set.
    """
    return {
        "category":     CATEGORY_LINEAR,
        "symbol":       symbol,
        "stopLoss":     str(stop_loss),
        "tpslMode":     TPSL_MODE_FULL,
        "slTriggerBy":  sl_trigger_by,
        "positionIdx":  POSITION_IDX_ONE_WAY,
    }


def validate_payload(payload: dict[str, Any]) -> list[str]:
    """
    Validate a trading-stop payload preview against the documented contract.

    Returns a list of gate names that were violated; empty list means OK.
    """
    blocked: list[str] = []

    if not isinstance(payload, dict) or not payload:
        return [GATE_MISSING_STOP_LOSS]

    cat = payload.get("category", "")
    if cat != CATEGORY_LINEAR:
        blocked.append(GATE_INVALID_CATEGORY)

    sym = str(payload.get("symbol", "")).strip()
    if not sym:
        blocked.append(GATE_SYMBOL_MISMATCH)

    sl_raw = payload.get("stopLoss", None)
    if sl_raw is None or sl_raw == "":
        blocked.append(GATE_MISSING_STOP_LOSS)
    else:
        sl = _safe_float(sl_raw)
        if sl <= 0:
            blocked.append(GATE_NON_POSITIVE_STOP_LOSS)

    tpsl_mode = payload.get("tpslMode", "")
    if tpsl_mode not in _VALID_TPSL_MODES:
        blocked.append(GATE_INVALID_TPSL_MODE)

    sl_trigger = payload.get("slTriggerBy", "")
    if sl_trigger not in _VALID_SL_TRIGGER_VALUES:
        blocked.append(GATE_INVALID_SL_TRIGGER_BY)

    pos_idx = payload.get("positionIdx", -1)
    if pos_idx != POSITION_IDX_ONE_WAY:
        blocked.append(GATE_INVALID_POSITION_IDX)

    if any(k in payload for k in _FORBIDDEN_PAYLOAD_KEYS_TP):
        blocked.append(GATE_PAYLOAD_INCLUDES_TAKE_PROFIT)
    if any(k in payload for k in _FORBIDDEN_PAYLOAD_KEYS_LEVERAGE):
        blocked.append(GATE_PAYLOAD_INCLUDES_LEVERAGE)
    if any(k in payload for k in _FORBIDDEN_PAYLOAD_KEYS_ORDER):
        blocked.append(GATE_PAYLOAD_INCLUDES_ORDER_FIELDS)
    if any(k in payload for k in _FORBIDDEN_PAYLOAD_KEYS_FUNDS):
        blocked.append(GATE_PAYLOAD_INCLUDES_TRANSFER)

    # Inspect string values for hostname / order-create path leakage.
    for v in payload.values():
        if isinstance(v, str):
            for host in _LIVE_HOST_PARTS:
                if host in v:
                    blocked.append(GATE_PAYLOAD_INCLUDES_LIVE_HOSTNAME)
                    break
            if ORDER_CREATE_PATH in v:
                blocked.append(GATE_PAYLOAD_INCLUDES_ORDER_PATH)
    # Dedupe while preserving order.
    seen: set[str] = set()
    unique: list[str] = []
    for g in blocked:
        if g not in seen:
            unique.append(g)
            seen.add(g)
    return unique


def _build_mock_permission_response(symbol: str, stop_loss: float) -> dict[str, Any]:
    """
    Synthetic envelope used in mock-permission mode.  Never opens a socket.
    Mirrors the shape Bybit returns for a successful trading-stop set, but
    is locally produced and marked mock=True.
    """
    return {
        "retCode":  0,
        "retMsg":   "OK",
        "result":   {
            "symbol":       symbol,
            "stopLoss":     str(stop_loss),
            "tpslMode":     TPSL_MODE_FULL,
            "slTriggerBy":  SL_TRIGGER_MARK_PRICE,
            "positionIdx":  POSITION_IDX_ONE_WAY,
            "mock":         True,
        },
        "mock":     True,
    }


# ---------------------------------------------------------------------------
# Probe
# ---------------------------------------------------------------------------

class DemoTradingStopContractProbe:
    """
    Demo-only trading-stop endpoint contract probe.

    Holds no network client; reads no environment variables.  Outputs the
    documented contract + a payload preview.  Under mock-permission mode
    emits a synthetic envelope (no socket).  Under
    --allow-real-stop-probe (real-permission-probe mode) the probe is
    DELIBERATELY not implemented: TASK-014T returns REAL_PROBE_NOT_IMPL
    because a no-op real probe design is the subject of TASK-014U.
    """

    def __init__(self) -> None:
        # No credentials, no clients, no env reads.
        pass

    def submit_contract_probe(
        self,
        protection:           dict[str, Any] | None,
        symbol:               str,
        confirm_token:        str = "",
        mock_permission:      bool = False,
        allow_real_stop_probe: bool = False,
        sl_trigger_by:        str = SL_TRIGGER_MARK_PRICE,
        _now:                 datetime | None = None,
    ) -> TradingStopContractResult:
        """
        Run one contract probe.

        Never contacts the network.  Real-probe path is intentionally a
        no-op: it returns REAL_PROBE_NOT_IMPLEMENTED to keep TASK-014T
        from modifying any existing position.
        """
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")
        mode   = (
            MODE_REAL_PERMISSION_PROBE if allow_real_stop_probe
            else (MODE_MOCK_PERMISSION if mock_permission else MODE_PREVIEW)
        )
        token_prefix = (confirm_token[:8] + "***") if confirm_token else ""

        blocked: list[str] = []

        # -- Phase 1: protection / symbol -------------------------------------
        if not isinstance(protection, dict) or not protection:
            blocked.append(GATE_PROTECTION_REPORT_MISSING)
            return self._fail_closed(
                ts_utc=ts_utc, mode=mode, symbol=symbol, stop_loss=0.0,
                token_prefix=token_prefix,
                allow_real=allow_real_stop_probe, blocked=blocked,
            )

        sel_symbol = str(protection.get("selected_symbol", ""))
        if not symbol or sel_symbol != symbol:
            blocked.append(GATE_SYMBOL_MISMATCH)

        stop_loss = _safe_float(protection.get("stop_price", 0.0))
        if stop_loss <= 0:
            blocked.append(GATE_NON_POSITIVE_STOP_LOSS)

        # -- Phase 2: payload preview + contract validation -------------------
        payload = build_payload_preview(
            symbol=symbol, stop_loss=stop_loss, sl_trigger_by=sl_trigger_by,
        )
        for g in validate_payload(payload):
            if g not in blocked:
                blocked.append(g)

        # -- Phase 3: confirm-token (required for mock-permission AND real) ---
        token_valid = False
        if mock_permission or allow_real_stop_probe:
            token_valid = _validate_confirm_token(confirm_token, _now=_now)
            if not token_valid:
                blocked.append(GATE_INVALID_CONFIRM_TOKEN)

        # -- Short-circuit on any failure -------------------------------------
        if blocked:
            return self._fail_closed(
                ts_utc=ts_utc, mode=mode, symbol=symbol, stop_loss=stop_loss,
                token_prefix=token_prefix, payload=payload,
                allow_real=allow_real_stop_probe, blocked=blocked,
                token_valid=token_valid,
            )

        # -- Real-permission-probe: deliberately NOT implemented in TASK-014T -
        if allow_real_stop_probe:
            return TradingStopContractResult(
                timestamp_utc=ts_utc,
                mode=MODE_REAL_PERMISSION_PROBE,
                selected_symbol=symbol,
                stop_loss=stop_loss,
                payload_preview=payload,
                category=CATEGORY_LINEAR,
                tpsl_mode=TPSL_MODE_FULL,
                sl_trigger_by=sl_trigger_by,
                position_idx=POSITION_IDX_ONE_WAY,
                confirm_token_prefix=token_prefix,
                confirm_token_valid=token_valid,
                real_probe_allowed=True,
                real_probe_implemented=False,
                mock_permission_status=False,
                mock_response={},
                stop_endpoint_called=False,
                order_endpoint_called=False,
                no_position_modified=True,
                no_live_endpoint=True,
                no_orders_sent=True,
                no_batch_order=True,
                no_close_only_path=True,
                emergency_close_invoked=False,
                secret_value_observed=False,
                blocked_gates=[GATE_REAL_PROBE_NOT_IMPL],
                status=STATUS_REAL_PROBE_NOT_IMPL,
            )

        # -- Mock-permission ---------------------------------------------------
        if mock_permission:
            mock = _build_mock_permission_response(
                symbol=symbol, stop_loss=stop_loss,
            )
            return TradingStopContractResult(
                timestamp_utc=ts_utc,
                mode=MODE_MOCK_PERMISSION,
                selected_symbol=symbol,
                stop_loss=stop_loss,
                payload_preview=payload,
                category=CATEGORY_LINEAR,
                tpsl_mode=TPSL_MODE_FULL,
                sl_trigger_by=sl_trigger_by,
                position_idx=POSITION_IDX_ONE_WAY,
                confirm_token_prefix=token_prefix,
                confirm_token_valid=token_valid,
                real_probe_allowed=False,
                real_probe_implemented=False,
                mock_permission_status=True,
                mock_response=mock,
                stop_endpoint_called=False,
                order_endpoint_called=False,
                no_position_modified=True,
                no_live_endpoint=True,
                no_orders_sent=True,
                blocked_gates=[],
                status=STATUS_MOCK_PERMISSION_OK,
            )

        # -- Preview (default) -------------------------------------------------
        return TradingStopContractResult(
            timestamp_utc=ts_utc,
            mode=MODE_PREVIEW,
            selected_symbol=symbol,
            stop_loss=stop_loss,
            payload_preview=payload,
            category=CATEGORY_LINEAR,
            tpsl_mode=TPSL_MODE_FULL,
            sl_trigger_by=sl_trigger_by,
            position_idx=POSITION_IDX_ONE_WAY,
            confirm_token_prefix=token_prefix,
            confirm_token_valid=token_valid,
            real_probe_allowed=False,
            real_probe_implemented=False,
            mock_permission_status=False,
            mock_response={},
            stop_endpoint_called=False,
            order_endpoint_called=False,
            no_position_modified=True,
            no_live_endpoint=True,
            no_orders_sent=True,
            blocked_gates=[],
            status=STATUS_PREVIEW_OK,
        )

    # -- private -----------------------------------------------------------

    def _fail_closed(
        self,
        ts_utc:       str,
        mode:         str,
        symbol:       str,
        stop_loss:    float,
        token_prefix: str,
        allow_real:   bool,
        blocked:      list[str],
        payload:      dict[str, Any] | None = None,
        token_valid:  bool = False,
    ) -> TradingStopContractResult:
        return TradingStopContractResult(
            timestamp_utc=ts_utc,
            mode=mode,
            selected_symbol=symbol,
            stop_loss=stop_loss,
            payload_preview=dict(payload) if payload else {},
            confirm_token_prefix=token_prefix,
            confirm_token_valid=token_valid,
            real_probe_allowed=allow_real,
            real_probe_implemented=False,
            mock_permission_status=False,
            mock_response={},
            stop_endpoint_called=False,
            order_endpoint_called=False,
            no_position_modified=True,
            no_live_endpoint=True,
            no_orders_sent=True,
            blocked_gates=list(blocked),
            status=STATUS_FAIL_CLOSED,
        )


__all__ = [
    "ENDPOINT_FAMILY",
    "BASE_URL_DEMO",
    "TRADING_STOP_PATH",
    "TRADING_STOP_METHOD",
    "CATEGORY_LINEAR",
    "TPSL_MODE_FULL",
    "SL_TRIGGER_MARK_PRICE",
    "SL_TRIGGER_LAST_PRICE",
    "POSITION_IDX_ONE_WAY",
    "ORDER_CREATE_PATH",
    "STATUS_PREVIEW_OK",
    "STATUS_MOCK_PERMISSION_OK",
    "STATUS_REAL_PROBE_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_PREVIEW",
    "MODE_MOCK_PERMISSION",
    "MODE_REAL_PERMISSION_PROBE",
    "GATE_PROTECTION_REPORT_MISSING",
    "GATE_SYMBOL_MISMATCH",
    "GATE_MISSING_STOP_LOSS",
    "GATE_NON_POSITIVE_STOP_LOSS",
    "GATE_INVALID_TPSL_MODE",
    "GATE_INVALID_SL_TRIGGER_BY",
    "GATE_INVALID_POSITION_IDX",
    "GATE_INVALID_CATEGORY",
    "GATE_PAYLOAD_INCLUDES_TAKE_PROFIT",
    "GATE_PAYLOAD_INCLUDES_LEVERAGE",
    "GATE_PAYLOAD_INCLUDES_ORDER_FIELDS",
    "GATE_PAYLOAD_INCLUDES_TRANSFER",
    "GATE_PAYLOAD_INCLUDES_LIVE_HOSTNAME",
    "GATE_PAYLOAD_INCLUDES_ORDER_PATH",
    "GATE_INVALID_CONFIRM_TOKEN",
    "GATE_REAL_PROBE_NOT_IMPL",
    "TradingStopContractResult",
    "DemoTradingStopContractProbe",
    "build_payload_preview",
    "validate_payload",
]
