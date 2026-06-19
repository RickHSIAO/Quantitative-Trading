"""TASK-014BM_MIN_QTY_FIX -- demo-only SOLUSDT instrument rules discovery.

Stage 1, read-only, demo-only instrument rules discovery layer for
SOLUSDT. Adds a narrowly-scoped reader for the **public** Bybit Demo
``/v5/market/instruments-info`` endpoint locked to
``category=linear`` and ``symbol=SOLUSDT`` so that the BM tiny order
preparation / execution path can stop hard-coding ``qty=0.01`` when the
current Bybit instrument rules require a larger minimum (the observed
``retCode=10001 "The number of contracts exceeds minimum limit
allowed"`` failure after TASK-014BM_FIX).

Hard safety invariants (cross-checked by tests):
    * **No order endpoint call.** This module never imports, references,
      or constructs any URL that resembles ``/v5/order/create`` or
      ``/v5/position/*``. It only ever reads from
      ``/v5/market/instruments-info``.
    * **Demo domain only.** The single allowed host is
      ``api-demo.bybit.com``. Any other host (live ``api.bybit.com``,
      live ``api.bytick.com``, websocket streams) is rejected before
      any network code is reached.
    * **No live secrets.** This module never reads ``BYBIT_API_KEY`` /
      ``BYBIT_API_SECRET`` / ``BYBIT_DEMO_API_KEY`` /
      ``BYBIT_DEMO_API_SECRET``. The instruments-info endpoint is
      public; no signing, no API key, no recv-window.
    * **Symbol locked to SOLUSDT.** Any other symbol is rejected.
    * **Category locked to linear.** Any other category is rejected.
    * **Fail closed on tiny cap.** If the exchange minimum implies a
      candidate quantity or notional above the configured tiny safety
      cap (``TINY_QTY_CAP_SOL`` / ``TINY_SIZE_CAP_USDT`` from BH), the
      module returns
      ``STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN`` -- it never silently
      lifts the cap and never sends anything.
    * **No retry, no scheduler.** A single bounded GET via stdlib
      ``urllib.request``.
    * **No protected-position interaction.** SOLUSDT is the only symbol
      this module touches; protected symbols
      (ENA / TIA / AIXBT / POLYX / EDU) are never referenced.
    * **No mutation of main.py / src/risk.py / BybitExecutor.** This
      module does not import any of them.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass
from decimal import ROUND_CEILING, ROUND_HALF_UP, Decimal, InvalidOperation
from typing import Any, Callable, Mapping

from src import demo_only_tiny_execution_adapter as bh

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BM_MIN_QTY_FIX"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-TINY-ORDER-INSTRUMENT-RULES"
IMPLEMENTATION_PATH_PHASE = "tiny_order_instrument_rules"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BM",
    "TASK-014BM_FIX",
)
NEXT_REQUIRED_TASK = "TASK-014BN_demo_only_tiny_execution_postfill_audit"

REPORT_NAME = "demo_only_tiny_execution_adapter_tiny_order_instrument_rules"
DEFAULT_OUTPUT_DIR = pathlib.Path("outputs/demo_trading") / REPORT_NAME

INSTRUMENT_RULES_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_tiny_order_instrument_rules_v1"
)

# Re-assert at import time that this task pointer is not a review-chain
# suffix (defence-in-depth via the BH guard).
bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)


# ---------------------------------------------------------------------------
# Strict immutable read-only constants
# ---------------------------------------------------------------------------

ALLOWED_DEMO_HOST = "api-demo.bybit.com"
ALLOWED_DEMO_BASE = f"https://{ALLOWED_DEMO_HOST}"
ALLOWED_READONLY_PATH = "/v5/market/instruments-info"
ALLOWED_READONLY_URL = f"{ALLOWED_DEMO_BASE}{ALLOWED_READONLY_PATH}"

ALLOWED_CATEGORY = "linear"
ALLOWED_SYMBOL = bh.ALLOWED_SYMBOL  # "SOLUSDT"

# Forbidden tokens cross-checked by tests (no order create, no live host,
# no signing surface).
FORBIDDEN_URL_TOKENS: tuple[str, ...] = (
    "/v5/order/create",
    "/v5/order/cancel",
    "/v5/position/set-trading-stop",
    "https://api.bybit.com",
    "https://api.bytick.com",
    "wss://stream.bybit.com",
    "wss://stream.bytick.com",
)

# Discovery status values.
STATUS_DISCOVERY_OK = "DISCOVERY_OK"
STATUS_DISCOVERY_OFFLINE_NO_NETWORK = "DISCOVERY_OFFLINE_NO_NETWORK"
STATUS_DISCOVERY_NETWORK_ERROR = "DISCOVERY_NETWORK_ERROR"
STATUS_DISCOVERY_BYBIT_NON_ZERO_RETCODE = "DISCOVERY_BYBIT_NON_ZERO_RETCODE"
STATUS_DISCOVERY_MISSING_LOT_SIZE_FILTER = "DISCOVERY_MISSING_LOT_SIZE_FILTER"
STATUS_DISCOVERY_SYMBOL_MISMATCH = "DISCOVERY_SYMBOL_MISMATCH"

# Candidate qty status values.
STATUS_CANDIDATE_OK = "CANDIDATE_OK"
STATUS_CANDIDATE_RULES_NOT_LOADED = "CANDIDATE_RULES_NOT_LOADED"
STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN = "TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN"
STATUS_CANDIDATE_INVALID_RULES = "CANDIDATE_INVALID_RULES"
STATUS_CANDIDATE_INVALID_MARK_PRICE = "CANDIDATE_INVALID_MARK_PRICE"

# Modes.
MODE_OFFLINE = "offline"
MODE_DISCOVER = "discover"
SUPPORTED_MODES: tuple[str, ...] = (MODE_OFFLINE, MODE_DISCOVER)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class InstrumentRulesDiscoveryError(bh.DemoOnlyTinyExecutionAdapterError):
    """Raised when the discovery contract is violated before network."""


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class InstrumentRules:
    """Parsed Bybit V5 SOLUSDT linear instrument rules.

    Decimal-only string representation to avoid floating-point drift in
    qty/step alignment.
    """

    symbol: str
    status: str
    min_order_qty: str
    qty_step: str
    min_notional_value: str
    max_mkt_order_qty: str | None
    tick_size: str | None
    source_endpoint: str
    source_query: Mapping[str, str]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "status": self.status,
            "min_order_qty": self.min_order_qty,
            "qty_step": self.qty_step,
            "min_notional_value": self.min_notional_value,
            "max_mkt_order_qty": self.max_mkt_order_qty,
            "tick_size": self.tick_size,
            "source_endpoint": self.source_endpoint,
            "source_query": dict(self.source_query),
        }


@dataclass(frozen=True)
class CandidateQty:
    """Computed safe minimum demo candidate qty."""

    status: str
    candidate_qty: str
    candidate_notional: str
    mark_price_used: str
    aligns_to_qty_step: bool
    satisfies_min_order_qty: bool
    satisfies_min_notional_value: bool
    within_tiny_qty_cap: bool
    within_tiny_size_cap: bool
    confirms_qty_0_01_invalid: bool
    is_executable_under_tiny_caps: bool
    reason: str
    tiny_qty_cap_sol: str
    tiny_size_cap_usdt: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "status": self.status,
            "candidate_qty": self.candidate_qty,
            "candidate_notional": self.candidate_notional,
            "mark_price_used": self.mark_price_used,
            "aligns_to_qty_step": self.aligns_to_qty_step,
            "satisfies_min_order_qty": self.satisfies_min_order_qty,
            "satisfies_min_notional_value": self.satisfies_min_notional_value,
            "within_tiny_qty_cap": self.within_tiny_qty_cap,
            "within_tiny_size_cap": self.within_tiny_size_cap,
            "confirms_qty_0_01_invalid": self.confirms_qty_0_01_invalid,
            "is_executable_under_tiny_caps": self.is_executable_under_tiny_caps,
            "reason": self.reason,
            "tiny_qty_cap_sol": self.tiny_qty_cap_sol,
            "tiny_size_cap_usdt": self.tiny_size_cap_usdt,
        }


@dataclass(frozen=True)
class InstrumentRulesReport:
    task_id: str
    identity: str
    phase: str
    mode: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    is_review_chain_suffix: bool
    instrument_rules_contract_version: str
    discovery_status: str
    instrument_rules_loaded: bool
    network_attempted: bool
    order_endpoint_called: bool
    order_sent: bool
    allowed_demo_host: str
    allowed_readonly_url: str
    allowed_category: str
    allowed_symbol: str
    http_status: int | None
    bybit_ret_code: int | None
    bybit_ret_msg: str
    raw_response_summary: str
    rules: InstrumentRules | None
    candidate: CandidateQty | None
    generated_at_utc: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "mode": self.mode,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "instrument_rules_contract_version": (
                self.instrument_rules_contract_version
            ),
            "discovery_status": self.discovery_status,
            "instrument_rules_loaded": self.instrument_rules_loaded,
            "network_attempted": self.network_attempted,
            "order_endpoint_called": self.order_endpoint_called,
            "order_sent": self.order_sent,
            "allowed_demo_host": self.allowed_demo_host,
            "allowed_readonly_url": self.allowed_readonly_url,
            "allowed_category": self.allowed_category,
            "allowed_symbol": self.allowed_symbol,
            "http_status": self.http_status,
            "bybit_ret_code": self.bybit_ret_code,
            "bybit_ret_msg": self.bybit_ret_msg,
            "raw_response_summary": self.raw_response_summary,
            "rules": self.rules.to_dict() if self.rules is not None else None,
            "candidate": (
                self.candidate.to_dict() if self.candidate is not None else None
            ),
            "generated_at_utc": self.generated_at_utc,
        }


# ---------------------------------------------------------------------------
# Endpoint / category / symbol assertions
# ---------------------------------------------------------------------------


def _assert_locked_inputs(
    *,
    category: str,
    symbol: str,
    endpoint_url: str,
) -> None:
    if category != ALLOWED_CATEGORY:
        raise InstrumentRulesDiscoveryError(
            f"category {category!r} not allowed; expected {ALLOWED_CATEGORY!r}"
        )
    if symbol != ALLOWED_SYMBOL:
        raise InstrumentRulesDiscoveryError(
            f"symbol {symbol!r} not allowed; expected {ALLOWED_SYMBOL!r}"
        )
    if endpoint_url != ALLOWED_READONLY_URL:
        raise InstrumentRulesDiscoveryError(
            f"endpoint_url {endpoint_url!r} not allowed; expected "
            f"{ALLOWED_READONLY_URL!r}"
        )
    for token in FORBIDDEN_URL_TOKENS:
        if token in endpoint_url:
            raise InstrumentRulesDiscoveryError(
                f"forbidden URL token {token!r} appears in endpoint_url "
                f"{endpoint_url!r}"
            )


def build_readonly_request_url(
    *,
    category: str = ALLOWED_CATEGORY,
    symbol: str = ALLOWED_SYMBOL,
) -> str:
    """Build the single allowed read-only instruments-info URL.

    Locked to ``category=linear`` and ``symbol=SOLUSDT``. Any other
    input raises ``InstrumentRulesDiscoveryError``.
    """

    _assert_locked_inputs(
        category=category,
        symbol=symbol,
        endpoint_url=ALLOWED_READONLY_URL,
    )
    query = urllib.parse.urlencode({"category": category, "symbol": symbol})
    return f"{ALLOWED_READONLY_URL}?{query}"


# ---------------------------------------------------------------------------
# Sender (single bounded HTTPS GET) -- network side
# ---------------------------------------------------------------------------


PublicGetSender = Callable[[str], Mapping[str, Any]]


def _real_public_get_via_urllib(url: str) -> dict[str, Any]:
    """One-shot HTTPS GET via stdlib urllib. No retry.

    Hard-asserts the URL prefix is the single allowed read-only endpoint.
    """

    if not url.startswith(f"{ALLOWED_READONLY_URL}?"):
        raise InstrumentRulesDiscoveryError(
            f"sender refused: url {url!r} does not start with "
            f"{ALLOWED_READONLY_URL!r}"
        )

    req = urllib.request.Request(
        url=url,
        data=None,
        headers={"Accept": "application/json"},
        method="GET",
    )
    try:
        with urllib.request.urlopen(req, timeout=10) as resp:  # nosec: B310
            raw = resp.read()
            status = int(resp.status)
    except urllib.error.HTTPError as exc:
        raw = exc.read() if hasattr(exc, "read") else b""
        status = int(getattr(exc, "code", 0) or 0)
    except Exception as exc:  # pragma: no cover - network failure path
        return {
            "_network_error": True,
            "_error_repr": repr(exc),
            "http_status": None,
            "raw_text": "",
            "json": None,
        }

    text = raw.decode("utf-8", errors="replace")
    parsed: dict[str, Any] | None = None
    try:
        parsed = json.loads(text)
    except Exception:
        parsed = None
    return {
        "_network_error": False,
        "http_status": status,
        "raw_text": text,
        "json": parsed,
    }


# ---------------------------------------------------------------------------
# Response parser
# ---------------------------------------------------------------------------


def _extract_solusdt_entry(parsed: Any) -> Mapping[str, Any] | None:
    if not isinstance(parsed, dict):
        return None
    result = parsed.get("result")
    if not isinstance(result, dict):
        return None
    items = result.get("list")
    if not isinstance(items, list):
        return None
    for entry in items:
        if not isinstance(entry, dict):
            continue
        if str(entry.get("symbol", "")) == ALLOWED_SYMBOL:
            return entry
    return None


def parse_instrument_rules(
    parsed: Any,
    *,
    source_endpoint: str = ALLOWED_READONLY_URL,
    source_query: Mapping[str, str] | None = None,
) -> InstrumentRules:
    """Parse a Bybit V5 ``/v5/market/instruments-info`` response.

    Requires the SOLUSDT linear entry to be present with a populated
    ``lotSizeFilter``. Raises ``InstrumentRulesDiscoveryError`` if the
    response is shaped incorrectly or refers to a different symbol.
    """

    entry = _extract_solusdt_entry(parsed)
    if entry is None:
        raise InstrumentRulesDiscoveryError(
            f"SOLUSDT entry not found in parsed response: {parsed!r}"
        )
    if str(entry.get("symbol", "")) != ALLOWED_SYMBOL:
        raise InstrumentRulesDiscoveryError(
            f"symbol mismatch in entry: {entry.get('symbol')!r} != "
            f"{ALLOWED_SYMBOL!r}"
        )

    lot = entry.get("lotSizeFilter")
    if not isinstance(lot, dict):
        raise InstrumentRulesDiscoveryError(
            "lotSizeFilter missing or not a dict in SOLUSDT entry"
        )

    min_order_qty = lot.get("minOrderQty")
    qty_step = lot.get("qtyStep")
    min_notional_value = lot.get("minNotionalValue")
    if min_order_qty is None or qty_step is None or min_notional_value is None:
        raise InstrumentRulesDiscoveryError(
            "lotSizeFilter missing one of "
            "{minOrderQty, qtyStep, minNotionalValue}"
        )

    max_mkt_order_qty = lot.get("maxMktOrderQty")

    price = entry.get("priceFilter")
    tick_size = price.get("tickSize") if isinstance(price, dict) else None

    return InstrumentRules(
        symbol=ALLOWED_SYMBOL,
        status=str(entry.get("status", "") or ""),
        min_order_qty=str(min_order_qty),
        qty_step=str(qty_step),
        min_notional_value=str(min_notional_value),
        max_mkt_order_qty=(
            str(max_mkt_order_qty) if max_mkt_order_qty is not None else None
        ),
        tick_size=(str(tick_size) if tick_size is not None else None),
        source_endpoint=source_endpoint,
        source_query=dict(
            source_query
            if source_query is not None
            else {"category": ALLOWED_CATEGORY, "symbol": ALLOWED_SYMBOL}
        ),
    )


# ---------------------------------------------------------------------------
# Candidate qty computation
# ---------------------------------------------------------------------------


def _decimal_or_none(value: Any) -> Decimal | None:
    if value is None:
        return None
    try:
        d = Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return None
    return d


def _ceil_to_step(value: Decimal, step: Decimal) -> Decimal:
    if step <= 0:
        return value
    quotient = (value / step).quantize(Decimal("1"), rounding=ROUND_CEILING)
    return (quotient * step).quantize(step, rounding=ROUND_HALF_UP)


def compute_candidate_tiny_qty(
    rules: InstrumentRules | None,
    *,
    mark_price: str | Decimal | None,
    tiny_qty_cap_sol: Decimal = bh.TINY_QTY_CAP_SOL,
    tiny_size_cap_usdt: Decimal = bh.TINY_SIZE_CAP_USDT,
) -> CandidateQty:
    """Compute the smallest tiny-cap-compliant candidate qty.

    Algorithm (in order):
        1. ``candidate = max(minOrderQty, qty_step)`` aligned UP to
           ``qty_step``.
        2. If ``mark_price * candidate < minNotionalValue``, increase
           ``candidate`` to the smallest ``qty_step`` multiple that
           satisfies the notional constraint.
        3. Verify the result still aligns to ``qty_step`` (it does, by
           construction).
        4. Compare against tiny safety caps (``TINY_QTY_CAP_SOL``,
           ``TINY_SIZE_CAP_USDT``). If either cap is exceeded, return
           ``STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN`` -- do **not**
           silently lift the cap.

    ``mark_price`` is mandatory only if ``minNotionalValue > 0`` and the
    caller needs to compute candidate notional; otherwise the candidate
    is qty-only and notional is reported as ``"0"``.
    """

    tiny_qty_cap = tiny_qty_cap_sol
    tiny_size_cap = tiny_size_cap_usdt

    if rules is None:
        return CandidateQty(
            status=STATUS_CANDIDATE_RULES_NOT_LOADED,
            candidate_qty="",
            candidate_notional="",
            mark_price_used="",
            aligns_to_qty_step=False,
            satisfies_min_order_qty=False,
            satisfies_min_notional_value=False,
            within_tiny_qty_cap=False,
            within_tiny_size_cap=False,
            confirms_qty_0_01_invalid=False,
            is_executable_under_tiny_caps=False,
            reason="instrument rules not loaded",
            tiny_qty_cap_sol=format(tiny_qty_cap, "f"),
            tiny_size_cap_usdt=format(tiny_size_cap, "f"),
        )

    min_order_qty = _decimal_or_none(rules.min_order_qty)
    qty_step = _decimal_or_none(rules.qty_step)
    min_notional_value = _decimal_or_none(rules.min_notional_value)
    if (
        min_order_qty is None
        or qty_step is None
        or min_notional_value is None
        or qty_step <= 0
        or min_order_qty < 0
        or min_notional_value < 0
    ):
        return CandidateQty(
            status=STATUS_CANDIDATE_INVALID_RULES,
            candidate_qty="",
            candidate_notional="",
            mark_price_used="",
            aligns_to_qty_step=False,
            satisfies_min_order_qty=False,
            satisfies_min_notional_value=False,
            within_tiny_qty_cap=False,
            within_tiny_size_cap=False,
            confirms_qty_0_01_invalid=False,
            is_executable_under_tiny_caps=False,
            reason=(
                "invalid instrument rules: "
                f"minOrderQty={rules.min_order_qty!r} "
                f"qtyStep={rules.qty_step!r} "
                f"minNotionalValue={rules.min_notional_value!r}"
            ),
            tiny_qty_cap_sol=format(tiny_qty_cap, "f"),
            tiny_size_cap_usdt=format(tiny_size_cap, "f"),
        )

    mark = _decimal_or_none(mark_price)

    candidate = _ceil_to_step(max(min_order_qty, qty_step), qty_step)

    if min_notional_value > 0:
        if mark is None or mark <= 0:
            return CandidateQty(
                status=STATUS_CANDIDATE_INVALID_MARK_PRICE,
                candidate_qty=format(candidate, "f"),
                candidate_notional="",
                mark_price_used="",
                aligns_to_qty_step=True,
                satisfies_min_order_qty=(candidate >= min_order_qty),
                satisfies_min_notional_value=False,
                within_tiny_qty_cap=False,
                within_tiny_size_cap=False,
                confirms_qty_0_01_invalid=(Decimal("0.01") < min_order_qty),
                is_executable_under_tiny_caps=False,
                reason=(
                    f"mark_price {mark_price!r} required to satisfy "
                    f"minNotionalValue={rules.min_notional_value!r}"
                ),
                tiny_qty_cap_sol=format(tiny_qty_cap, "f"),
                tiny_size_cap_usdt=format(tiny_size_cap, "f"),
            )
        required_qty = _ceil_to_step(min_notional_value / mark, qty_step)
        if required_qty > candidate:
            candidate = required_qty
        notional = candidate * mark
    else:
        notional = candidate * mark if mark is not None and mark > 0 else Decimal("0")

    aligns = (candidate % qty_step) == 0
    satisfies_min_qty = candidate >= min_order_qty
    satisfies_min_notional = (
        notional >= min_notional_value if min_notional_value > 0 else True
    )

    within_qty_cap = candidate <= tiny_qty_cap
    within_size_cap = (notional <= tiny_size_cap) if notional > 0 else True
    executable = (
        within_qty_cap
        and within_size_cap
        and aligns
        and satisfies_min_qty
        and satisfies_min_notional
    )

    if not within_qty_cap or not within_size_cap:
        status = STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN
        reason = (
            f"candidate qty={format(candidate, 'f')} notional="
            f"{format(notional, 'f')} exceeds tiny cap "
            f"(qty_cap={format(tiny_qty_cap, 'f')} SOL, size_cap="
            f"{format(tiny_size_cap, 'f')} USDT) -- fail closed, do NOT send"
        )
    else:
        status = STATUS_CANDIDATE_OK
        reason = ""

    return CandidateQty(
        status=status,
        candidate_qty=format(candidate, "f"),
        candidate_notional=format(notional, "f"),
        mark_price_used=(format(mark, "f") if mark is not None else ""),
        aligns_to_qty_step=aligns,
        satisfies_min_order_qty=satisfies_min_qty,
        satisfies_min_notional_value=satisfies_min_notional,
        within_tiny_qty_cap=within_qty_cap,
        within_tiny_size_cap=within_size_cap,
        confirms_qty_0_01_invalid=(Decimal("0.01") < min_order_qty),
        is_executable_under_tiny_caps=executable,
        reason=reason,
        tiny_qty_cap_sol=format(tiny_qty_cap, "f"),
        tiny_size_cap_usdt=format(tiny_size_cap, "f"),
    )


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def run_instrument_rules_discovery(
    *,
    mode: str = MODE_OFFLINE,
    mark_price: str | Decimal | None = None,
    category: str = ALLOWED_CATEGORY,
    symbol: str = ALLOWED_SYMBOL,
    sender: PublicGetSender | None = None,
    pre_parsed_response: Mapping[str, Any] | None = None,
) -> InstrumentRulesReport:
    """Run a single demo-only instrument rules discovery cycle.

    Modes:
        * ``offline`` (default) -- no network. If ``pre_parsed_response``
          is provided (e.g. a previously cached payload), the parser
          runs against it; otherwise the report carries
          ``DISCOVERY_OFFLINE_NO_NETWORK`` and rules=None.
        * ``discover`` -- single GET to the locked read-only endpoint
          via the supplied sender (or stdlib urllib if no sender is
          injected). No retry, no scheduler, no signing.

    The discovery cycle NEVER touches the order endpoint, NEVER reads
    any secret, NEVER references a live URL.
    """

    if mode not in SUPPORTED_MODES:
        raise InstrumentRulesDiscoveryError(
            f"unsupported mode {mode!r}; expected one of {SUPPORTED_MODES!r}"
        )

    bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)
    _assert_locked_inputs(
        category=category,
        symbol=symbol,
        endpoint_url=ALLOWED_READONLY_URL,
    )

    rules: InstrumentRules | None = None
    discovery_status = STATUS_DISCOVERY_OFFLINE_NO_NETWORK
    network_attempted = False
    http_status: int | None = None
    ret_code: int | None = None
    ret_msg = ""
    raw_text = ""

    if pre_parsed_response is not None:
        try:
            rules = parse_instrument_rules(
                pre_parsed_response,
                source_endpoint=ALLOWED_READONLY_URL,
                source_query={"category": category, "symbol": symbol},
            )
            discovery_status = STATUS_DISCOVERY_OK
        except InstrumentRulesDiscoveryError as exc:
            discovery_status = STATUS_DISCOVERY_MISSING_LOT_SIZE_FILTER
            ret_msg = str(exc)

    if mode == MODE_DISCOVER:
        network_attempted = True
        url = build_readonly_request_url(category=category, symbol=symbol)
        use_sender = sender or _real_public_get_via_urllib
        response = use_sender(url)
        network_error = bool(response.get("_network_error"))
        http_status_value = response.get("http_status")
        http_status = (
            int(http_status_value)
            if isinstance(http_status_value, int)
            else None
        )
        raw_text = str(response.get("raw_text", "") or "")
        parsed = response.get("json")
        if network_error:
            discovery_status = STATUS_DISCOVERY_NETWORK_ERROR
            ret_msg = str(response.get("_error_repr", "") or "")
        else:
            if isinstance(parsed, dict):
                try:
                    ret_code = int(parsed.get("retCode", -1))
                except Exception:
                    ret_code = None
                ret_msg = str(parsed.get("retMsg", "") or "")
            if ret_code is not None and ret_code != 0:
                discovery_status = STATUS_DISCOVERY_BYBIT_NON_ZERO_RETCODE
            else:
                try:
                    rules = parse_instrument_rules(
                        parsed,
                        source_endpoint=ALLOWED_READONLY_URL,
                        source_query={
                            "category": category,
                            "symbol": symbol,
                        },
                    )
                    discovery_status = STATUS_DISCOVERY_OK
                except InstrumentRulesDiscoveryError as exc:
                    discovery_status = (
                        STATUS_DISCOVERY_MISSING_LOT_SIZE_FILTER
                    )
                    ret_msg = ret_msg or str(exc)

    candidate = compute_candidate_tiny_qty(rules, mark_price=mark_price)

    return InstrumentRulesReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        mode=mode,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        instrument_rules_contract_version=INSTRUMENT_RULES_CONTRACT_VERSION,
        discovery_status=discovery_status,
        instrument_rules_loaded=(rules is not None),
        network_attempted=network_attempted,
        order_endpoint_called=False,
        order_sent=False,
        allowed_demo_host=ALLOWED_DEMO_HOST,
        allowed_readonly_url=ALLOWED_READONLY_URL,
        allowed_category=ALLOWED_CATEGORY,
        allowed_symbol=ALLOWED_SYMBOL,
        http_status=http_status,
        bybit_ret_code=ret_code,
        bybit_ret_msg=ret_msg,
        raw_response_summary=raw_text[:2048],
        rules=rules,
        candidate=candidate,
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(report: InstrumentRulesReport) -> str:
    lines: list[str] = []
    lines.append(f"# {report.task_id} -- {report.identity}")
    lines.append("")
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(f"- mode: `{report.mode}`")
    lines.append(f"- upstream_tasks: `{', '.join(report.upstream_tasks)}`")
    lines.append(f"- next_required_task: `{report.next_required_task}`")
    lines.append(f"- is_review_chain_suffix: `{report.is_review_chain_suffix}`")
    lines.append(
        f"- instrument_rules_contract_version: "
        f"`{report.instrument_rules_contract_version}`"
    )
    lines.append("")
    lines.append("## Discovery")
    lines.append("")
    lines.append(f"- discovery_status: `{report.discovery_status}`")
    lines.append(f"- instrument_rules_loaded: `{report.instrument_rules_loaded}`")
    lines.append(f"- network_attempted: `{report.network_attempted}`")
    lines.append(f"- order_endpoint_called: `{report.order_endpoint_called}`")
    lines.append(f"- order_sent: `{report.order_sent}`")
    lines.append(f"- allowed_demo_host: `{report.allowed_demo_host}`")
    lines.append(f"- allowed_readonly_url: `{report.allowed_readonly_url}`")
    lines.append(f"- allowed_category: `{report.allowed_category}`")
    lines.append(f"- allowed_symbol: `{report.allowed_symbol}`")
    lines.append(f"- http_status: `{report.http_status}`")
    lines.append(f"- bybit_ret_code: `{report.bybit_ret_code}`")
    ret_msg = report.bybit_ret_msg.replace("|", "\\|") if report.bybit_ret_msg else ""
    lines.append(f"- bybit_ret_msg: `{ret_msg}`")
    lines.append("")
    lines.append("## Instrument rules")
    lines.append("")
    if report.rules is None:
        lines.append("_No rules loaded (offline mode or discovery failure)._")
    else:
        r = report.rules
        lines.append(f"- symbol: `{r.symbol}`")
        lines.append(f"- status: `{r.status}`")
        lines.append(f"- minOrderQty: `{r.min_order_qty}`")
        lines.append(f"- qtyStep: `{r.qty_step}`")
        lines.append(f"- minNotionalValue: `{r.min_notional_value}`")
        lines.append(f"- maxMktOrderQty: `{r.max_mkt_order_qty}`")
        lines.append(f"- tickSize: `{r.tick_size}`")
        lines.append(f"- source_endpoint: `{r.source_endpoint}`")
        lines.append(f"- source_query: `{dict(r.source_query)}`")
    lines.append("")
    lines.append("## Candidate")
    lines.append("")
    if report.candidate is None:
        lines.append("_No candidate computed._")
    else:
        c = report.candidate
        lines.append(f"- status: `{c.status}`")
        lines.append(f"- candidate_qty: `{c.candidate_qty}`")
        lines.append(f"- candidate_notional: `{c.candidate_notional}`")
        lines.append(f"- mark_price_used: `{c.mark_price_used}`")
        lines.append(f"- aligns_to_qty_step: `{c.aligns_to_qty_step}`")
        lines.append(
            f"- satisfies_min_order_qty: `{c.satisfies_min_order_qty}`"
        )
        lines.append(
            f"- satisfies_min_notional_value: "
            f"`{c.satisfies_min_notional_value}`"
        )
        lines.append(f"- within_tiny_qty_cap: `{c.within_tiny_qty_cap}`")
        lines.append(f"- within_tiny_size_cap: `{c.within_tiny_size_cap}`")
        lines.append(
            f"- confirms_qty_0_01_invalid: `{c.confirms_qty_0_01_invalid}`"
        )
        lines.append(
            f"- is_executable_under_tiny_caps: "
            f"`{c.is_executable_under_tiny_caps}`"
        )
        reason = c.reason.replace("|", "\\|") if c.reason else ""
        lines.append(f"- reason: `{reason}`")
        lines.append(f"- tiny_qty_cap_sol: `{c.tiny_qty_cap_sol}`")
        lines.append(f"- tiny_size_cap_usdt: `{c.tiny_size_cap_usdt}`")
    lines.append("")
    lines.append(
        "_demo-only read-only instrument rules discovery -- no live "
        "endpoint, no live credentials, no order create, no signing, no "
        "retry, no scheduler, no main.py / src.risk / BybitExecutor "
        "changes._"
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: InstrumentRulesReport,
    output_dir: pathlib.Path | str | None = None,
) -> dict[str, pathlib.Path]:
    """Write JSON + Markdown report (latest_* + timestamped)."""

    out_dir = pathlib.Path(output_dir) if output_dir else DEFAULT_OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)

    ts = _utc_timestamp()
    json_payload = json.dumps(report.to_dict(), indent=2, sort_keys=True)
    md_payload = _render_markdown(report)

    paths = {
        "latest_json": out_dir / f"latest_{REPORT_NAME}.json",
        "latest_md": out_dir / f"latest_{REPORT_NAME}.md",
        "timestamped_json": out_dir / f"{REPORT_NAME}_{ts}.json",
        "timestamped_md": out_dir / f"{REPORT_NAME}_{ts}.md",
    }
    for key, path in paths.items():
        if key.endswith("_json"):
            path.write_text(json_payload, encoding="utf-8")
        else:
            path.write_text(md_payload, encoding="utf-8")
    return paths


# ---------------------------------------------------------------------------
# Public surface
# ---------------------------------------------------------------------------


__all__ = [
    "ALLOWED_CATEGORY",
    "ALLOWED_DEMO_BASE",
    "ALLOWED_DEMO_HOST",
    "ALLOWED_READONLY_PATH",
    "ALLOWED_READONLY_URL",
    "ALLOWED_SYMBOL",
    "CandidateQty",
    "DEFAULT_OUTPUT_DIR",
    "FORBIDDEN_URL_TOKENS",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "INSTRUMENT_RULES_CONTRACT_VERSION",
    "IS_REVIEW_CHAIN_SUFFIX",
    "InstrumentRules",
    "InstrumentRulesDiscoveryError",
    "InstrumentRulesReport",
    "MODE_DISCOVER",
    "MODE_OFFLINE",
    "NEXT_REQUIRED_TASK",
    "PublicGetSender",
    "REPORT_NAME",
    "STATUS_CANDIDATE_INVALID_MARK_PRICE",
    "STATUS_CANDIDATE_INVALID_RULES",
    "STATUS_CANDIDATE_OK",
    "STATUS_CANDIDATE_RULES_NOT_LOADED",
    "STATUS_DISCOVERY_BYBIT_NON_ZERO_RETCODE",
    "STATUS_DISCOVERY_MISSING_LOT_SIZE_FILTER",
    "STATUS_DISCOVERY_NETWORK_ERROR",
    "STATUS_DISCOVERY_OFFLINE_NO_NETWORK",
    "STATUS_DISCOVERY_OK",
    "STATUS_DISCOVERY_SYMBOL_MISMATCH",
    "STATUS_TINY_CAP_TOO_LOW_FOR_EXCHANGE_MIN",
    "SUPPORTED_MODES",
    "TASK_ID",
    "UPSTREAM_TASKS",
    "build_readonly_request_url",
    "compute_candidate_tiny_qty",
    "parse_instrument_rules",
    "run_instrument_rules_discovery",
    "write_report",
]
