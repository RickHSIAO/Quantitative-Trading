"""
src/demo_readonly_client.py
TASK-014C: Bybit Demo read-only runtime probe client.

Default mode (allow_real_network=False): returns fixture data, zero network calls,
zero secrets loaded.
Real mode (allow_real_network=True): calls https://api-demo.bybit.com read-only
endpoints; requires BYBIT_DEMO_API_KEY / BYBIT_DEMO_API_SECRET env vars for
private endpoints.

SAFETY INVARIANTS (enforced structurally and verified by tests):
  1. Fixture mode: zero network calls, zero secrets loaded.
  2. order_endpoint_called is always False in every returned snapshot.
  3. secret_value_observed is always False in every returned snapshot.
  4. secret_leak_violations is always [] in every returned snapshot.
  5. Only DEMO_BASE_URL (https://api-demo.bybit.com) is ever contacted in real mode.
  6. _LIVE_HOSTNAME (api.bybit.com) is defined only as a blocking sentinel, never used
     as a request target.
  7. live_endpoint_fallback_detected is always False.
  8. API secret loaded from env var, never printed, never included in output.

Allowed read-only endpoint paths (_ALLOWED_PATHS):
  /v5/account/wallet-balance
  /v5/position/list
  /v5/market/instruments-info
  /v5/user/query-api
  /v5/account/info        (TASK-014CE: read-only account marginMode evidence)
  /v5/market/time         (TASK-014CE: public exchange server-clock evidence)
  /v5/market/risk-limit   (TASK-014CE: public margin-tier evidence)

Forbidden operations (never called; verified by source scan in tests):
  Order placement / creation / submission / cancellation, private order posting,
  leverage changes, trading-stop changes, balance transfers, withdrawals, deposits.
  In particular POST /v5/account/set-margin-mode is NEVER referenced: this client
  only ever issues GET requests, and set-margin-mode is not in _ALLOWED_PATHS.
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
from typing import Any


# ---------------------------------------------------------------------------
# URL constants
# ---------------------------------------------------------------------------

DEMO_BASE_URL  = "https://api-demo.bybit.com"
_LIVE_HOSTNAME = "api.bybit.com"    # sentinel only — never used as a request target

# Allowed read-only endpoint paths
_EP_WALLET       = "/v5/account/wallet-balance"
_EP_POSITIONS    = "/v5/position/list"
_EP_INSTRUMENTS  = "/v5/market/instruments-info"
_EP_QUERY_API    = "/v5/user/query-api"
_EP_ACCOUNT_INFO = "/v5/account/info"        # TASK-014CE: read-only account marginMode
_EP_MARKET_TIME  = "/v5/market/time"         # TASK-014CE: public exchange server time
_EP_RISK_LIMIT   = "/v5/market/risk-limit"   # TASK-014CE: public margin-tier evidence

_ALLOWED_PATHS: frozenset[str] = frozenset({
    _EP_WALLET, _EP_POSITIONS, _EP_INSTRUMENTS, _EP_QUERY_API,
    _EP_ACCOUNT_INFO, _EP_MARKET_TIME, _EP_RISK_LIMIT,
})

# Explicitly forbidden write/mutation paths. These are NEVER added to _ALLOWED_PATHS
# and this client only ever issues GET. Declared as named sentinels so tests can prove
# they are denied (no generic "allow all account endpoints" rule exists).
_FORBIDDEN_WRITE_PATHS: frozenset[str] = frozenset({
    "/v5/account/set-margin-mode",
    "/v5/order/create",
    "/v5/order/create-batch",
    "/v5/order/amend",
    "/v5/order/cancel",
    "/v5/order/cancel-all",
    "/v5/position/set-leverage",
    "/v5/position/switch-isolated",
    "/v5/position/set-risk-limit",
})


# ---------------------------------------------------------------------------
# Proof strength constants
# ---------------------------------------------------------------------------

PROOF_STRONG  = "STRONG"    # demo URL confirmed + retCode==0 + valid response structure
PROOF_WEAK    = "WEAK"      # retCode==0 but response lacks expected identity fields
PROOF_MISSING = "MISSING"   # no API key, connection error, or retCode != 0


# ---------------------------------------------------------------------------
# Data classes
# ---------------------------------------------------------------------------

@dataclass
class WalletSnapshot:
    equity_usd:                  float
    available_balance_usd:       float
    wallet_balance_usd:          float
    account_type:                str
    api_key_present:             bool
    secret_value_observed:       bool       = False
    secret_leak_violations:      list[str]  = field(default_factory=list)
    order_endpoint_called:       bool       = False
    available_balance_usd_source: str       = "unknown"  # TASK-014J: mapping provenance
    # TASK-014CD: authoritative read-only margin evidence captured WHERE PRESENT.
    # None means the field was absent in the response (never assumed/fabricated).
    total_initial_margin_usd:     float | None = None
    total_maintenance_margin_usd: float | None = None
    account_im_rate:              float | None = None
    account_mm_rate:              float | None = None


@dataclass
class PositionSnapshot:
    symbol:         str
    side:           str          # "long" or "short" (normalised from Bybit "Buy"/"Sell")
    quantity:       float
    entry_price:    float
    stop_price:     float | None  # None when not set on the exchange
    unrealised_pnl: float
    leverage:       float
    # TASK-014CD: per-position read-only margin evidence captured WHERE PRESENT.
    # None means the field was absent in the response (never assumed/fabricated).
    initial_margin_usd:     float | None = None
    maintenance_margin_usd: float | None = None
    position_value_usd:     float | None = None
    mark_price:             float | None = None
    liq_price:              float | None = None
    # TASK-014CH4A_FIX1: Bybit positionIdx (0 = one-way, 1/2 = hedge Buy/Sell), captured
    # as read-only position-mode EVIDENCE. None when absent; never switches mode.
    position_idx:           int | None = None


@dataclass
class InstrumentSnapshot:
    symbol:          str
    qty_step:        float
    min_qty:         float
    max_qty:         float        # 0 = no upper limit
    tick_size:       float
    min_notional:    float
    price_precision: int
    qty_precision:   int
    status:          str = "Trading"  # Bybit instrument status


@dataclass
class AccountInfoSnapshot:
    """TASK-014CE: read-only account-mode evidence from /v5/account/info.
    Absent fields stay None (never assumed). ``response_present`` is False when no
    usable response was returned (retCode != 0 / network error)."""
    margin_mode:           str | None = None
    unified_margin_status: Any        = None
    updated_time:          str | None = None
    is_master_trader:      Any        = None
    spot_hedging_status:   str | None = None
    response_envelope_time: str | None = None
    request_started_at_utc:  str | None = None
    response_received_at_utc: str | None = None
    request_elapsed_ms:     float | None = None
    response_present:       bool        = False


@dataclass
class ServerTimeSnapshot:
    """TASK-014CE: public exchange server-clock evidence from /v5/market/time.
    timeSecond / timeNano are the EXCHANGE server time (not a per-symbol quote time)."""
    time_second:            str | None = None
    time_nano:              str | None = None
    response_envelope_time: str | None = None
    request_started_at_utc:  str | None = None
    response_received_at_utc: str | None = None
    request_started_monotonic: float | None = None
    response_received_monotonic: float | None = None
    # High-resolution local EPOCH seconds (time.time()) for clock-offset estimation.
    request_started_epoch:   float | None = None
    response_received_epoch: float | None = None
    response_present:        bool       = False


@dataclass
class RuntimeProofSnapshot:
    account_mode:                    str   # "demo" if verified, "unknown" otherwise
    demo_flag:                       bool
    endpoint_family:                 str   # "bybit_demo" if Demo API confirmed
    source:                          str   # "fixture" or "bybit_readonly_api"
    base_url_used:                   str
    live_endpoint_fallback_detected: bool  # always False; True would mean a safety breach
    order_endpoint_called:           bool  = False
    api_key_present:                 bool  = False
    secret_value_observed:           bool  = False
    secret_leak_violations:          list[str] = field(default_factory=list)
    proof_strength:                  str   = ""     # PROOF_STRONG / PROOF_WEAK / PROOF_MISSING
    api_secret_present:              bool  = False


# ---------------------------------------------------------------------------
# Fixture data (used when allow_real_network=False)
# ---------------------------------------------------------------------------

FIXTURE_WALLET = WalletSnapshot(
    equity_usd=10_000.0,
    available_balance_usd=8_500.0,
    wallet_balance_usd=10_000.0,
    account_type="UNIFIED",
    api_key_present=False,
    secret_value_observed=False,
    secret_leak_violations=[],
    order_endpoint_called=False,
    available_balance_usd_source="account.totalAvailableBalance",
)

FIXTURE_POSITIONS: list[PositionSnapshot] = [
    PositionSnapshot(
        symbol="BTCUSDT", side="long", quantity=0.05,
        entry_price=67_000.0, stop_price=65_000.0,
        unrealised_pnl=80.0, leverage=2.0,
    ),
    PositionSnapshot(
        symbol="ETHUSDT", side="short", quantity=0.5,
        entry_price=3_200.0, stop_price=3_400.0,
        unrealised_pnl=-25.0, leverage=3.0,
    ),
]

FIXTURE_INSTRUMENTS: dict[str, InstrumentSnapshot] = {
    "BTCUSDT":  InstrumentSnapshot("BTCUSDT",  0.001, 0.001, 0,  0.1,    1.0, 1, 3),
    "ETHUSDT":  InstrumentSnapshot("ETHUSDT",  0.01,  0.01,  0,  0.05,   1.0, 2, 2),
    "BNBUSDT":  InstrumentSnapshot("BNBUSDT",  0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "SOLUSDT":  InstrumentSnapshot("SOLUSDT",  0.1,   0.1,   0,  0.01,   1.0, 2, 1),
    "XRPUSDT":  InstrumentSnapshot("XRPUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "ADAUSDT":  InstrumentSnapshot("ADAUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "DOTUSDT":  InstrumentSnapshot("DOTUSDT",  0.1,   0.1,   0,  0.001,  1.0, 3, 1),
    "LINKUSDT": InstrumentSnapshot("LINKUSDT", 0.1,   0.1,   0,  0.001,  1.0, 3, 1),
    "AAVEUSDT": InstrumentSnapshot("AAVEUSDT", 0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "AVAXUSDT": InstrumentSnapshot("AVAXUSDT", 0.1,   0.1,   0,  0.01,   1.0, 2, 1),
}

FIXTURE_RUNTIME_PROOF = RuntimeProofSnapshot(
    account_mode="demo",
    demo_flag=True,
    endpoint_family="bybit_demo",
    source="fixture",
    base_url_used=DEMO_BASE_URL,
    live_endpoint_fallback_detected=False,
    order_endpoint_called=False,
    api_key_present=False,
    secret_value_observed=False,
    secret_leak_violations=[],
    proof_strength=PROOF_STRONG,
    api_secret_present=False,
)


# ---------------------------------------------------------------------------
# Client
# ---------------------------------------------------------------------------

class DemoReadOnlyClient:
    """
    Read-only Bybit Demo account probe client.

    Default (allow_real_network=False): returns fixture snapshots; no I/O, no secrets.
    Real mode (allow_real_network=True): calls api-demo.bybit.com via HMAC-signed GET
      requests.  Requires BYBIT_DEMO_API_KEY env var for private endpoints.

    Invariants upheld in every mode:
      secret_value_observed is always False in every returned snapshot.
      order_endpoint_called is always False.
      DEMO_BASE_URL is the only URL ever contacted; _LIVE_HOSTNAME is never used.
    """

    def __init__(self, allow_real_network: bool = False) -> None:
        self._allow_real  = allow_real_network
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
    # Public API
    # ------------------------------------------------------------------

    def get_wallet_balance(self) -> WalletSnapshot:
        if not self._allow_real:
            return WalletSnapshot(
                equity_usd=FIXTURE_WALLET.equity_usd,
                available_balance_usd=FIXTURE_WALLET.available_balance_usd,
                wallet_balance_usd=FIXTURE_WALLET.wallet_balance_usd,
                account_type=FIXTURE_WALLET.account_type,
                api_key_present=self._key_present,
                secret_value_observed=False,
                secret_leak_violations=[],
                order_endpoint_called=False,
                available_balance_usd_source=FIXTURE_WALLET.available_balance_usd_source,
            )
        return self._wallet_real()

    def get_open_positions(self) -> list[PositionSnapshot]:
        if not self._allow_real:
            return list(FIXTURE_POSITIONS)
        return self._positions_real()

    def get_instruments_info(
        self, symbols: list[str] | None = None,
    ) -> dict[str, InstrumentSnapshot]:
        if not self._allow_real:
            if symbols:
                return {s: FIXTURE_INSTRUMENTS[s]
                        for s in symbols if s in FIXTURE_INSTRUMENTS}
            return dict(FIXTURE_INSTRUMENTS)
        return self._instruments_real(symbols or [])

    def build_runtime_proof(self) -> RuntimeProofSnapshot:
        if not self._allow_real:
            return RuntimeProofSnapshot(
                account_mode=FIXTURE_RUNTIME_PROOF.account_mode,
                demo_flag=FIXTURE_RUNTIME_PROOF.demo_flag,
                endpoint_family=FIXTURE_RUNTIME_PROOF.endpoint_family,
                source=FIXTURE_RUNTIME_PROOF.source,
                base_url_used=FIXTURE_RUNTIME_PROOF.base_url_used,
                live_endpoint_fallback_detected=False,
                order_endpoint_called=False,
                api_key_present=self._key_present,
                secret_value_observed=False,
                secret_leak_violations=[],
                proof_strength=PROOF_STRONG,
                api_secret_present=self._secret_present,
            )
        return self._proof_real()

    def get_account_info(self) -> AccountInfoSnapshot:
        """TASK-014CE: read-only account-mode evidence (signed GET /v5/account/info).
        Fixture mode returns an explicit all-None UNAVAILABLE snapshot (no I/O)."""
        if not self._allow_real:
            return AccountInfoSnapshot(response_present=False)
        return self._account_info_real()

    def get_server_time(self) -> ServerTimeSnapshot:
        """TASK-014CE: public exchange server-clock evidence (unsigned GET
        /v5/market/time). Fixture mode returns an explicit empty snapshot (no I/O)."""
        if not self._allow_real:
            return ServerTimeSnapshot(response_present=False)
        return self._server_time_real()

    def get_risk_limit(
        self, symbol: str | None = None, category: str = "linear",
    ) -> dict[str, list[dict[str, Any]]]:
        """TASK-014CE: public margin-tier evidence (unsigned GET /v5/market/risk-limit).
        Returns ``{symbol: [raw tier dicts]}`` exactly as returned by Bybit (paginated).
        Fixture mode returns an empty map (no I/O)."""
        if not self._allow_real:
            return {}
        return self._risk_limit_real(symbol=symbol, category=category)

    # ------------------------------------------------------------------
    # Real-mode internals (only reached when allow_real_network=True)
    # ------------------------------------------------------------------

    def _make_signed_headers(self, query_str: str) -> dict[str, str]:
        """Return Bybit V5 HMAC-signed request headers.  Secret is never printed."""
        timestamp   = str(int(time.time() * 1000))
        recv_window = "5000"
        sign_input  = timestamp + self._api_key + recv_window + query_str
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

    def _get(
        self,
        path:   str,
        params: dict[str, str],
        signed: bool = True,
    ) -> dict[str, Any]:
        """Signed GET to DEMO_BASE_URL only.  Raises if path is not in _ALLOWED_PATHS."""
        if path not in _ALLOWED_PATHS:
            raise ValueError(f"Path not in allowed list: {path!r}")
        query_str = urllib.parse.urlencode(sorted(params.items()))
        url = f"{DEMO_BASE_URL}{path}?{query_str}" if query_str else f"{DEMO_BASE_URL}{path}"
        headers: dict[str, str] = {"Content-Type": "application/json"}
        if signed and self._api_key:
            headers.update(self._make_signed_headers(query_str))
        req = urllib.request.Request(url, headers=headers, method="GET")
        try:
            with urllib.request.urlopen(req, timeout=10) as resp:
                return json.loads(resp.read().decode("utf-8"))
        except Exception as exc:
            return {"retCode": -1, "retMsg": str(exc), "result": {}}

    def _wallet_real(self) -> WalletSnapshot:
        data = self._get(_EP_WALLET, {"accountType": "UNIFIED"}, signed=True)
        equity = available = wallet_bal = 0.0
        account_type        = "UNKNOWN"
        available_source    = "missing"
        total_im = total_mm = acc_im_rate = acc_mm_rate = None
        try:
            acc_list = data["result"]["list"]
            if acc_list:
                acc          = acc_list[0]
                account_type = acc.get("accountType", "UNIFIED")
                coins        = acc.get("coin", [])
                usdt = next((c for c in coins if c.get("coin") == "USDT"), {})
                equity     = float(usdt.get("equity", 0) or 0)
                wallet_bal = float(usdt.get("walletBalance", 0) or 0)

                # TASK-014CD: capture account-level margin evidence WHERE PRESENT.
                total_im = _opt_float(acc.get("totalInitialMargin"))
                total_mm = _opt_float(acc.get("totalMaintenanceMargin"))
                acc_im_rate = _opt_float(acc.get("accountIMRate"))
                acc_mm_rate = _opt_float(acc.get("accountMMRate"))

                # Available-balance mapping priority (TASK-014J):
                #   1. account.totalAvailableBalance  — most authoritative for UNIFIED
                #   2. account.availableToWithdraw
                #   3. coin.USDT.availableToWithdraw
                #   4. coin.USDT.free
                # Explicitly excluded: walletBalance, totalWalletBalance, totalEquity
                # (those include locked margin and are not free-margin indicators)
                tab = acc.get("totalAvailableBalance")
                if tab is not None and str(tab).strip():
                    available        = float(tab or 0)
                    available_source = "account.totalAvailableBalance"
                else:
                    wab = acc.get("availableToWithdraw")
                    if wab is not None and str(wab).strip():
                        available        = float(wab or 0)
                        available_source = "account.availableToWithdraw"
                    else:
                        catw = usdt.get("availableToWithdraw")
                        if catw is not None and str(catw).strip():
                            available        = float(catw or 0)
                            available_source = "coin.USDT.availableToWithdraw"
                        else:
                            cfree = usdt.get("free")
                            if cfree is not None and str(cfree).strip():
                                available        = float(cfree or 0)
                                available_source = "coin.USDT.free"
        except (KeyError, IndexError, TypeError, ValueError):
            pass
        return WalletSnapshot(
            equity_usd=equity,
            available_balance_usd=available,
            wallet_balance_usd=wallet_bal,
            account_type=account_type,
            api_key_present=self._key_present,
            secret_value_observed=False,
            secret_leak_violations=[],
            order_endpoint_called=False,
            available_balance_usd_source=available_source,
            total_initial_margin_usd=total_im,
            total_maintenance_margin_usd=total_mm,
            account_im_rate=acc_im_rate,
            account_mm_rate=acc_mm_rate,
        )

    def _positions_real(self) -> list[PositionSnapshot]:
        data = self._get(
            _EP_POSITIONS,
            {"category": "linear", "settleCoin": "USDT"},
            signed=True,
        )
        out: list[PositionSnapshot] = []
        try:
            for item in data["result"]["list"]:
                size = float(item.get("size", 0) or 0)
                if size == 0:
                    continue
                raw_side = str(item.get("side", "")).lower()
                side     = "long" if raw_side == "buy" else "short"
                entry    = float(item.get("avgPrice", 0) or 0)
                try:
                    sl_raw = float(item.get("stopLoss", 0) or 0)
                    stop: float | None = sl_raw if sl_raw > 0 else None
                except (TypeError, ValueError):
                    stop = None
                out.append(PositionSnapshot(
                    symbol=item.get("symbol", ""),
                    side=side,
                    quantity=size,
                    entry_price=entry,
                    stop_price=stop,
                    unrealised_pnl=float(item.get("unrealisedPnl", 0) or 0),
                    leverage=float(item.get("leverage", 1) or 1),
                    # TASK-014CD: per-position margin evidence captured WHERE PRESENT.
                    initial_margin_usd=_opt_float(item.get("positionIM")),
                    maintenance_margin_usd=_opt_float(item.get("positionMM")),
                    position_value_usd=_opt_float(item.get("positionValue")),
                    mark_price=_opt_float(item.get("markPrice")),
                    liq_price=_opt_float(item.get("liqPrice")),
                    position_idx=(int(item["positionIdx"])
                                  if str(item.get("positionIdx", "")).strip().lstrip("-").isdigit()
                                  else None),
                ))
        except (KeyError, TypeError, ValueError):
            pass
        return out

    def _instruments_real(self, symbols: list[str]) -> dict[str, InstrumentSnapshot]:
        """Fetch linear instruments with pagination + targeted candidate symbol lookup.

        Fetches paginated instruments-info, collecting all pages via nextPageCursor.
        Candidate entry symbols (e.g., SOLUSDT) are fetched via targeted lookup if
        missing from paginated results.  Returns dict keyed by symbol.
        """
        out: dict[str, InstrumentSnapshot] = {}
        pages_fetched = 0
        next_cursor = ""
        max_pages = 20  # safety limit to prevent infinite loops
        seen_cursors: set[str] = set()

        # Paginated fetch
        while pages_fetched < max_pages:
            params: dict[str, str] = {"category": "linear"}
            if next_cursor:
                params["cursor"] = next_cursor
            data = self._get(_EP_INSTRUMENTS, params, signed=False)

            pages_fetched += 1
            try:
                for item in data["result"]["list"]:
                    sym = item.get("symbol", "")
                    if symbols and sym not in symbols:
                        continue
                    if sym:
                        out[sym] = self._parse_instrument_snapshot(item)

                next_cursor = data.get("result", {}).get("nextPageCursor", "")
                if not next_cursor or next_cursor in seen_cursors:
                    break
                seen_cursors.add(next_cursor)
            except (KeyError, TypeError, ValueError):
                break

        # Targeted fetch for candidate entry symbols (e.g., SOLUSDT)
        _CANDIDATE_ENTRY_SYMBOLS = ("SOLUSDT",)
        for sym in _CANDIDATE_ENTRY_SYMBOLS:
            if sym not in out:
                data = self._get(
                    _EP_INSTRUMENTS,
                    {"category": "linear", "symbol": sym},
                    signed=False
                )
                try:
                    items = data.get("result", {}).get("list", [])
                    if items:
                        out[sym] = self._parse_instrument_snapshot(items[0])
                except (KeyError, TypeError, ValueError):
                    pass

        return out

    def _parse_instrument_snapshot(self, item: dict[str, Any]) -> InstrumentSnapshot:
        """Parse one instrument item from Bybit API response."""
        sym = item.get("symbol", "")
        lot = item.get("lotSizeFilter", {}) or {}
        pf = item.get("priceFilter", {}) or {}
        qty_step = float(lot.get("qtyStep", lot.get("basePrecision", 0.001)) or 0.001)
        min_qty = float(lot.get("minOrderQty", 0.001) or 0.001)
        max_mkt = lot.get("maxMktOrderQty")
        max_ord = lot.get("maxOrderQty")
        max_qty = float(max_mkt or max_ord or 0)
        min_notional = float(lot.get("minNotionalValue", lot.get("minOrderAmt", 1.0)) or 1.0)
        tick_size = float(pf.get("tickSize", 0.01) or 0.01)
        status = str(item.get("status", "Trading"))
        return InstrumentSnapshot(
            symbol=sym,
            qty_step=qty_step,
            min_qty=min_qty,
            max_qty=max_qty,
            tick_size=tick_size,
            min_notional=min_notional,
            price_precision=_decimal_places(tick_size),
            qty_precision=_decimal_places(qty_step),
            status=status,
        )

    def _proof_real(self) -> RuntimeProofSnapshot:
        if not self._api_key:
            return RuntimeProofSnapshot(
                account_mode="unknown", demo_flag=False,
                endpoint_family="unknown", source="bybit_readonly_api",
                base_url_used=DEMO_BASE_URL, live_endpoint_fallback_detected=False,
                order_endpoint_called=False,
                api_key_present=False, api_secret_present=self._secret_present,
                proof_strength=PROOF_MISSING,
            )
        data     = self._get(_EP_QUERY_API, {}, signed=True)
        ret_code = data.get("retCode", -1)
        result   = data.get("result", {}) or {}
        if ret_code != 0:
            return RuntimeProofSnapshot(
                account_mode="unknown", demo_flag=False,
                endpoint_family="unknown", source="bybit_readonly_api",
                base_url_used=DEMO_BASE_URL, live_endpoint_fallback_detected=False,
                order_endpoint_called=False,
                api_key_present=self._key_present, api_secret_present=self._secret_present,
                proof_strength=PROOF_MISSING,
            )
        has_uid     = bool(result.get("userID") or result.get("uid") or result.get("id"))
        has_api_key = bool(result.get("apiKey") or result.get("note"))
        if has_uid and has_api_key:
            proof_strength  = PROOF_STRONG
            account_mode    = "demo"
            demo_flag       = True
            endpoint_family = "bybit_demo"
        else:
            proof_strength  = PROOF_WEAK
            account_mode    = "unknown"
            demo_flag       = False
            endpoint_family = "unknown"
        return RuntimeProofSnapshot(
            account_mode=account_mode, demo_flag=demo_flag,
            endpoint_family=endpoint_family, source="bybit_readonly_api",
            base_url_used=DEMO_BASE_URL, live_endpoint_fallback_detected=False,
            order_endpoint_called=False,
            api_key_present=self._key_present, api_secret_present=self._secret_present,
            proof_strength=proof_strength,
        )

    def _account_info_real(self) -> AccountInfoSnapshot:
        """Signed GET /v5/account/info. Parses marginMode / unifiedMarginStatus /
        updatedTime (+ optional isMasterTrader / spotHedgingStatus). Captures local
        request/response timing. Never writes; secret never returned/printed."""
        started = _utc_now_iso()
        t0 = time.perf_counter()
        data = self._get(_EP_ACCOUNT_INFO, {}, signed=True)
        elapsed_ms = (time.perf_counter() - t0) * 1000.0
        received = _utc_now_iso()
        ret_code = data.get("retCode", -1)
        result = data.get("result", {}) or {}
        if ret_code != 0 or not result:
            return AccountInfoSnapshot(
                request_started_at_utc=started, response_received_at_utc=received,
                request_elapsed_ms=round(elapsed_ms, 3), response_present=False)
        return AccountInfoSnapshot(
            margin_mode=(str(result.get("marginMode")) if result.get("marginMode") is not None else None),
            unified_margin_status=result.get("unifiedMarginStatus"),
            updated_time=(str(result.get("updatedTime")) if result.get("updatedTime") is not None else None),
            is_master_trader=result.get("isMasterTrader"),
            spot_hedging_status=(str(result.get("spotHedgingStatus"))
                                 if result.get("spotHedgingStatus") is not None else None),
            response_envelope_time=(str(data.get("time")) if data.get("time") is not None else None),
            request_started_at_utc=started, response_received_at_utc=received,
            request_elapsed_ms=round(elapsed_ms, 3), response_present=True)

    def _server_time_real(self) -> ServerTimeSnapshot:
        """Unsigned GET /v5/market/time. Parses timeSecond / timeNano (exchange server
        time). Captures local UTC + monotonic request/response timing for bracketing."""
        started = _utc_now_iso()
        epoch_start = time.time()
        mono_start = time.perf_counter()
        data = self._get(_EP_MARKET_TIME, {}, signed=False)
        mono_end = time.perf_counter()
        epoch_end = time.time()
        received = _utc_now_iso()
        ret_code = data.get("retCode", -1)
        result = data.get("result", {}) or {}
        if ret_code != 0 or not result:
            return ServerTimeSnapshot(
                request_started_at_utc=started, response_received_at_utc=received,
                request_started_monotonic=mono_start, response_received_monotonic=mono_end,
                request_started_epoch=epoch_start, response_received_epoch=epoch_end,
                response_present=False)
        return ServerTimeSnapshot(
            time_second=(str(result.get("timeSecond")) if result.get("timeSecond") is not None else None),
            time_nano=(str(result.get("timeNano")) if result.get("timeNano") is not None else None),
            response_envelope_time=(str(data.get("time")) if data.get("time") is not None else None),
            request_started_at_utc=started, response_received_at_utc=received,
            request_started_monotonic=mono_start, response_received_monotonic=mono_end,
            request_started_epoch=epoch_start, response_received_epoch=epoch_end,
            response_present=True)

    def _risk_limit_real(
        self, *, symbol: str | None, category: str,
    ) -> dict[str, list[dict[str, Any]]]:
        """Unsigned GET /v5/market/risk-limit (paginated). Collects every tier row for
        each symbol verbatim (Bybit returns ascending tiers). Symbol-specific lookup is
        used when ``symbol`` is given; otherwise the full linear catalog is paginated."""
        out: dict[str, list[dict[str, Any]]] = {}
        page_count = 0
        get_count = 0
        next_cursor = ""
        seen_cursors: set[str] = set()
        max_pages = 50
        while page_count < max_pages:
            params: dict[str, str] = {"category": category}
            if symbol:
                params["symbol"] = symbol
            if next_cursor:
                params["cursor"] = next_cursor
            data = self._get(_EP_RISK_LIMIT, params, signed=False)
            page_count += 1
            get_count += 1
            try:
                rows = (data.get("result", {}) or {}).get("list", []) or []
                for row in rows:
                    sym = str(row.get("symbol", "") or "")
                    if not sym:
                        continue
                    out.setdefault(sym, []).append(dict(row))
                next_cursor = (data.get("result", {}) or {}).get("nextPageCursor", "") or ""
                if not next_cursor or next_cursor in seen_cursors:
                    break
                seen_cursors.add(next_cursor)
            except (KeyError, TypeError, ValueError):
                break
            # Symbol-specific lookups return all tiers on one page.
            if symbol:
                break
        out["__page_count__"] = page_count  # provenance; popped by callers
        out["__get_count__"] = get_count
        return out


# ---------------------------------------------------------------------------
# Helper
# ---------------------------------------------------------------------------

def _utc_now_iso() -> str:
    """LOCAL UTC ISO-8601 request/response time (never an exchange/server timestamp)."""
    return time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime(time.time()))


def _decimal_places(v: float) -> int:
    """Infer decimal precision from a step/tick size value."""
    if v >= 1.0:
        return 0
    s = f"{v:.10f}".rstrip("0")
    return len(s.split(".")[-1]) if "." in s else 0


def _opt_float(raw: Any) -> float | None:
    """Parse an optional numeric response field. Returns None when the field is
    absent or blank (never assumed) and never raises."""
    if raw is None:
        return None
    s = str(raw).strip()
    if not s:
        return None
    try:
        return float(s)
    except (TypeError, ValueError):
        return None
