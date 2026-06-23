"""src/demo_public_ws_ticker_evidence.py
TASK-014CF: public read-only WebSocket ticker timestamp evidence (pure logic).

This module is the STANDALONE, fully-offline-testable core of the public
WebSocket ticker evidence task. It contains NO network I/O; the thin transport
lives in ``scripts/collect_public_ws_ticker_evidence.py``.

Purpose
-------
The REST planner price path (``src/demo_market_price_guard.py`` ->
``/v5/market/tickers``) surfaces ``lastPrice`` but explicitly does NOT surface an
authoritative exchange message timestamp (``exchange_timestamp_ms = None``). This
module proves whether every required symbol can obtain a same-message price and
an exchange-generated message timestamp from the official public linear
WebSocket ticker stream, and produces a canonical, fingerprinted artifact for a
LATER integration task.

Official WebSocket semantics encoded here
-----------------------------------------
  * Public linear endpoint: wss://stream.bybit.com/v5/public/linear
  * Demo public market data is identical to Mainnet public data; Demo
    (stream-demo) supports PRIVATE streams only, so the Mainnet public stream is
    the correct read-only source for Demo public market data.
  * Public topics require NO authentication. tickers.{symbol} is the topic.
  * Linear ticker messages are ``snapshot`` (full) or ``delta`` (changed fields
    only). A field absent from a delta has NOT changed.
  * Top-level ``ts`` is the millisecond timestamp when Bybit GENERATED the data.
    It is NOT a trade/fill/matching-engine timestamp and is never labelled one.
    Canonical label: ``exchange_data_generated_ts_ms``.
  * Top-level ``cs`` is the cross sequence.

SAFETY INVARIANTS
-----------------
  * Only wss://stream.bybit.com/v5/public/linear is allowed; stream-demo,
    stream-testnet, /v5/private and /v5/trade are denied.
  * No authentication message can be built (no api_key / secret / sign field).
  * No credential value ever appears in a subscription / artifact / fingerprint.
  * This task NEVER promotes execution readiness: it does not replace REST
    planner prices and does not clear the freshness blockers.
"""
from __future__ import annotations

import hashlib
import json
import re
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Identity / schema
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014CF"
SCHEMA_NAME = "public_websocket_ticker_evidence"
SCHEMA_VERSION = 1

# Mainnet public linear stream IS the correct source for Demo public market data.
ENVIRONMENT = "MAINNET_PUBLIC_LINEAR_FOR_DEMO_PUBLIC_MARKET_DATA"
CHANNEL_TYPE = "public/linear"

PUBLIC_LINEAR_WS_ENDPOINT = "wss://stream.bybit.com/v5/public/linear"
_ALLOWED_WS_ENDPOINTS: frozenset[str] = frozenset({PUBLIC_LINEAR_WS_ENDPOINT})

# Explicitly denied hosts / schemes / paths (substring guard, fail-closed).
_DENIED_ENDPOINT_FRAGMENTS: tuple[str, ...] = (
    "stream-demo.bybit.com",      # Demo host: PRIVATE streams only
    "stream-testnet.bybit.com",   # testnet
    "/v5/private",                # private channel
    "/v5/trade",                  # order-entry websocket
)

# Topics that must never be subscribed by this public collector.
_PRIVATE_TOPIC_PREFIXES: tuple[str, ...] = (
    "position", "order", "wallet", "execution", "greek", "dcp",
)

# Forbidden keys anywhere in an outbound payload / artifact (credential guard).
_FORBIDDEN_CREDENTIAL_KEY_FRAGMENTS: tuple[str, ...] = (
    "api_key", "apikey", "api-key", "secret", "sign", "signature",
    "x-bapi-api-key", "x-bapi-sign", "passphrase",
)

# The op that would authenticate a private stream. It must be impossible here.
_FORBIDDEN_OPS: frozenset[str] = frozenset({"auth"})


# ---------------------------------------------------------------------------
# Status vocabulary
# ---------------------------------------------------------------------------

# Overall
WS_TICKER_EVIDENCE_COMPLETE = "WS_TICKER_EVIDENCE_COMPLETE"
WS_TICKER_EVIDENCE_PARTIAL = "WS_TICKER_EVIDENCE_PARTIAL"
WS_TICKER_EVIDENCE_UNAVAILABLE = "WS_TICKER_EVIDENCE_UNAVAILABLE"
WS_TICKER_EVIDENCE_CONFLICT = "WS_TICKER_EVIDENCE_CONFLICT"

# Per symbol
WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE = "WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE"
WS_SNAPSHOT_MISSING = "WS_SNAPSHOT_MISSING"
WS_SELECTED_PRICE_FIELD_MISSING = "WS_SELECTED_PRICE_FIELD_MISSING"
WS_TIMESTAMP_INVALID = "WS_TIMESTAMP_INVALID"
WS_TIMESTAMP_STALE = "WS_TIMESTAMP_STALE"
WS_SEQUENCE_REGRESSION = "WS_SEQUENCE_REGRESSION"
WS_TIMESTAMP_REGRESSION = "WS_TIMESTAMP_REGRESSION"
WS_SYMBOL_TOPIC_MISMATCH = "WS_SYMBOL_TOPIC_MISMATCH"
WS_CONNECTION_GENERATION_CONFLICT = "WS_CONNECTION_GENERATION_CONFLICT"
WS_PRICE_FIELD_SEMANTICS_MISMATCH = "WS_PRICE_FIELD_SEMANTICS_MISMATCH"

# A per-symbol status is "hard failed" (fail-closed, sticky) when in this set.
_HARD_FAIL_STATUSES: frozenset[str] = frozenset({
    WS_TIMESTAMP_INVALID, WS_SEQUENCE_REGRESSION, WS_TIMESTAMP_REGRESSION,
    WS_SYMBOL_TOPIC_MISMATCH, WS_CONNECTION_GENERATION_CONFLICT,
    WS_PRICE_FIELD_SEMANTICS_MISMATCH,
})

# Blockers this task keeps in place (it does NOT integrate prices).
PRICE_FRESHNESS_EVIDENCE_PARTIAL = "PRICE_FRESHNESS_EVIDENCE_PARTIAL"
PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE = (
    "PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE"
)
WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS = "WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS"
EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK = (
    "EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK"
)

# The planner's price field (authoritative source recorded for provenance).
PLANNER_PRICE_FIELD = "lastPrice"
PLANNER_PRICE_FIELD_SOURCE = (
    "src/demo_market_price_guard.py DemoMarketPriceGuard._fetch_real -> "
    "row['lastPrice'] (public /v5/market/tickers); identical field is selected "
    "from the public linear ticker stream"
)

# Default fail-closed thresholds (milliseconds).
DEFAULT_STALE_THRESHOLD_MS = 10_000
DEFAULT_FUTURE_TOLERANCE_MS = 5_000
DEFAULT_NEGATIVE_DELAY_TOLERANCE_MS = 2_000


class WsEndpointError(ValueError):
    """Raised when an endpoint / topic / payload violates a safety invariant."""


# ---------------------------------------------------------------------------
# Small helpers
# ---------------------------------------------------------------------------

_LINEAR_SYMBOL_RE = re.compile(r"^[A-Z0-9]+USDT$")


def _canonical_symbol(raw: Any) -> str:
    return str(raw or "").strip().upper()


def _fingerprint(payload: Any) -> str:
    body = json.dumps(payload, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True)
    return "sha256:" + hashlib.sha256(body.encode("utf-8")).hexdigest()


def _iso_from_epoch_ns(epoch_ns: int | None) -> str | None:
    if epoch_ns is None:
        return None
    return datetime.fromtimestamp(epoch_ns / 1e9, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ")


def _iso_from_ms(ts_ms: int | None) -> str | None:
    if ts_ms is None:
        return None
    return datetime.fromtimestamp(ts_ms / 1000.0, tz=timezone.utc).strftime(
        "%Y-%m-%dT%H:%M:%S.%fZ")


def _parse_int(value: Any) -> int | None:
    if isinstance(value, bool):
        return None
    if isinstance(value, int):
        return value
    if isinstance(value, str) and value.strip().isdigit():
        return int(value.strip())
    return None


def _is_decimal_string(value: Any) -> bool:
    if not isinstance(value, str):
        return False
    s = value.strip()
    if not s:
        return False
    try:
        Decimal(s)
        return True
    except (InvalidOperation, ValueError):
        return False


# ---------------------------------------------------------------------------
# Endpoint / topic / credential guards
# ---------------------------------------------------------------------------

def assert_public_endpoint_allowed(url: str) -> str:
    """Return ``url`` iff it is EXACTLY the allowed public linear endpoint.

    Fails closed on Demo/testnet hosts, private/trade paths, and any non-wss
    scheme or unapproved host/path.
    """
    u = (url or "").strip()
    low = u.lower()
    for frag in _DENIED_ENDPOINT_FRAGMENTS:
        if frag in low:
            raise WsEndpointError(f"denied websocket endpoint fragment: {frag!r}")
    if not low.startswith("wss://"):
        raise WsEndpointError("only the wss:// scheme is permitted")
    if u not in _ALLOWED_WS_ENDPOINTS:
        raise WsEndpointError(f"websocket endpoint not in allowlist: {u!r}")
    return u


def assert_public_topic(topic: str) -> str:
    """Return ``topic`` iff it is a public tickers.{symbol} topic."""
    t = (topic or "").strip()
    low = t.lower()
    for pref in _PRIVATE_TOPIC_PREFIXES:
        if low.startswith(pref):
            raise WsEndpointError(f"private topic refused: {t!r}")
    if not t.startswith("tickers."):
        raise WsEndpointError(f"only tickers.* public topics permitted: {t!r}")
    sym = t.split(".", 1)[1]
    if not sym or not _LINEAR_SYMBOL_RE.match(sym):
        raise WsEndpointError(f"unsupported ticker topic symbol: {t!r}")
    return t


def assert_no_credentials(payload: Any, *, secret_values: Sequence[str] = ()) -> None:
    """Recursively assert no credential KEY or known secret VALUE is present.

    Used for every outbound payload AND the final artifact / fingerprint input.
    """
    redact = {str(v).strip() for v in secret_values if str(v).strip()}

    def _walk(obj: Any) -> None:
        if isinstance(obj, Mapping):
            for k, v in obj.items():
                kl = str(k).strip().lower()
                for frag in _FORBIDDEN_CREDENTIAL_KEY_FRAGMENTS:
                    if frag in kl:
                        raise WsEndpointError(
                            f"forbidden credential key in payload: {k!r}")
                if kl == "op" and str(v).strip().lower() in _FORBIDDEN_OPS:
                    raise WsEndpointError("forbidden auth op in payload")
                _walk(v)
        elif isinstance(obj, (list, tuple)):
            for item in obj:
                _walk(item)
        elif isinstance(obj, str):
            if obj.strip() and obj.strip() in redact:
                raise WsEndpointError("credential value leaked into payload")

    _walk(payload)


def build_subscription_message(symbols: Sequence[str], *, req_id: str | None = None,
                               ) -> dict[str, Any]:
    """Build a deterministic public subscription message.

    args are sorted ``tickers.{symbol}`` topics; the message carries NO auth /
    api_key / sign field of any kind.
    """
    topics = sorted({f"tickers.{_canonical_symbol(s)}" for s in symbols})
    for t in topics:
        assert_public_topic(t)
    msg: dict[str, Any] = {"op": "subscribe", "args": topics}
    if req_id:
        msg["req_id"] = str(req_id)
    assert_no_credentials(msg)
    return msg


# ---------------------------------------------------------------------------
# Symbol-universe derivation
# ---------------------------------------------------------------------------

def validate_linear_symbol(sym: str) -> str:
    s = _canonical_symbol(sym)
    if not s:
        raise WsEndpointError("empty symbol")
    if not _LINEAR_SYMBOL_RE.match(s):
        raise WsEndpointError(f"non-linear / unsupported symbol: {sym!r}")
    return s


def derive_required_symbol_universe(
    *,
    strategy_target_symbols: Sequence[str],
    observed_legacy_symbols: Sequence[str],
    protected_symbol_allowlist: Sequence[str],
    strategy_source_reference: str,
    legacy_source_reference: str,
) -> dict[str, Any]:
    """Derive and validate the required linear-symbol universe.

    Fails closed on empty / non-linear symbols, duplicates after canonicalization,
    a legacy symbol outside the protected allowlist, a strategy symbol that IS a
    protected symbol, or strategy/legacy overlap.
    """
    allow = {_canonical_symbol(s) for s in protected_symbol_allowlist}

    strat_raw = [_canonical_symbol(s) for s in strategy_target_symbols]
    legacy_raw = [_canonical_symbol(s) for s in observed_legacy_symbols]

    if any(not s for s in strat_raw):
        raise WsEndpointError("empty strategy target symbol")
    if any(not s for s in legacy_raw):
        raise WsEndpointError("empty observed legacy symbol")

    for s in strat_raw:
        validate_linear_symbol(s)
        if s in allow:
            raise WsEndpointError(
                f"strategy target {s!r} is a protected symbol (V1-target mismatch)")
    for s in legacy_raw:
        validate_linear_symbol(s)
        if s not in allow:
            raise WsEndpointError(
                f"observed legacy {s!r} not in protected allowlist "
                f"(protected-legacy mismatch)")

    if len(set(strat_raw)) != len(strat_raw):
        raise WsEndpointError("duplicate strategy target symbol after canonicalization")
    if len(set(legacy_raw)) != len(legacy_raw):
        raise WsEndpointError("duplicate observed legacy symbol after canonicalization")

    overlap = set(strat_raw) & set(legacy_raw)
    if overlap:
        raise WsEndpointError(f"strategy/legacy symbol overlap: {sorted(overlap)!r}")

    strategy_symbols = sorted(strat_raw)
    legacy_symbols = sorted(legacy_raw)
    unique_symbols = sorted(set(strat_raw) | set(legacy_raw))
    requested_count = len(strat_raw) + len(legacy_raw)

    fp_payload = {
        "schema": SCHEMA_NAME,
        "task_id": TASK_ID,
        "strategy_symbols": strategy_symbols,
        "legacy_symbols": legacy_symbols,
        "unique_symbols": unique_symbols,
    }
    universe = {
        "strategy_symbol_count": len(strategy_symbols),
        "legacy_symbol_count": len(legacy_symbols),
        "requested_symbol_count": requested_count,
        "unique_symbol_count": len(unique_symbols),
        "strategy_symbols": strategy_symbols,
        "legacy_symbols": legacy_symbols,
        "symbols": unique_symbols,
        "strategy_source_reference": strategy_source_reference,
        "legacy_source_reference": legacy_source_reference,
        "protected_symbol_allowlist": sorted(allow),
        "symbol_universe_fingerprint": _fingerprint(fp_payload),
    }
    return universe


# ---------------------------------------------------------------------------
# Per-symbol evidence state
# ---------------------------------------------------------------------------

@dataclass
class SymbolEvidence:
    symbol: str
    topic: str
    selected_price_field: str = PLANNER_PRICE_FIELD
    connection_generation: int | None = None
    snapshot_received: bool = False
    covered: bool = False
    selected_price: str | None = None
    selected_price_decimal_ok: bool = False
    selected_price_ts_ms: int | None = None
    selected_price_cs: int | None = None
    selected_price_message_type: str | None = None
    selected_price_updated_in_last_message: bool = False
    selected_price_local_received_epoch_ns: int | None = None
    selected_price_local_received_at_utc: str | None = None
    selected_price_local_monotonic_received_ns: int | None = None
    exchange_data_generated_ts_ms: int | None = None
    last_accepted_cs: int | None = None
    last_accepted_ts: int | None = None
    duplicate_message_count: int = 0
    out_of_order_cs_count: int = 0
    timestamp_regression_count: int = 0
    hard_fail_status: str | None = None
    hard_fail_reason: str | None = None

    def fail(self, status: str, reason: str) -> None:
        # Fail-closed: the first hard failure sticks.
        if self.hard_fail_status is None:
            self.hard_fail_status = status
            self.hard_fail_reason = reason


# ---------------------------------------------------------------------------
# Evidence builder (pure; fed already-parsed messages + local timing)
# ---------------------------------------------------------------------------

class PublicWsTickerEvidenceBuilder:
    """Accumulate per-symbol ticker evidence from parsed public messages.

    All network I/O happens in the caller; this class is pure and deterministic.
    """

    def __init__(
        self,
        *,
        universe: Mapping[str, Any],
        price_field: str = PLANNER_PRICE_FIELD,
        clock_offset_seconds: float | str | None = None,
        clock_offset_status: str | None = None,
        stale_threshold_ms: int = DEFAULT_STALE_THRESHOLD_MS,
        future_tolerance_ms: int = DEFAULT_FUTURE_TOLERANCE_MS,
        negative_delay_tolerance_ms: int = DEFAULT_NEGATIVE_DELAY_TOLERANCE_MS,
    ) -> None:
        self.universe = dict(universe)
        self.price_field = str(price_field)
        self.clock_offset_seconds = (
            None if clock_offset_seconds is None else Decimal(str(clock_offset_seconds))
        )
        self.clock_offset_status = clock_offset_status
        self.stale_threshold_ms = int(stale_threshold_ms)
        self.future_tolerance_ms = int(future_tolerance_ms)
        self.negative_delay_tolerance_ms = int(negative_delay_tolerance_ms)

        self._symbols: dict[str, SymbolEvidence] = {
            s: SymbolEvidence(symbol=s, topic=f"tickers.{s}",
                              selected_price_field=self.price_field)
            for s in self.universe["symbols"]
        }

        # network / message counters
        self.ws_connection_attempt_count = 0
        self.ws_connection_success_count = 0
        self.ws_reconnect_count = 0
        self.ws_subscription_request_count = 0
        self.ws_subscription_topic_count = 0
        self.ws_subscription_ack_count = 0
        self.ws_message_count = 0
        self.ws_snapshot_message_count = 0
        self.ws_delta_message_count = 0
        self.ws_ping_count = 0
        self.ws_pong_count = 0
        self.ws_malformed_message_count = 0
        self.ws_duplicate_message_count = 0
        self.ws_out_of_order_message_count = 0
        self._generations: set[int] = set()

    # -- transport / lifecycle bookkeeping ---------------------------------

    def record_connection_attempt(self) -> None:
        self.ws_connection_attempt_count += 1

    def record_connection_success(self, generation: int) -> None:
        self.ws_connection_success_count += 1
        self._generations.add(int(generation))

    def record_reconnect(self) -> None:
        self.ws_reconnect_count += 1

    def record_subscription_request(self, topic_count: int) -> None:
        self.ws_subscription_request_count += 1
        self.ws_subscription_topic_count = int(topic_count)

    def record_subscription_ack(self) -> None:
        self.ws_subscription_ack_count += 1

    def record_ping(self) -> None:
        self.ws_ping_count += 1

    def record_pong(self) -> None:
        self.ws_pong_count += 1

    # -- message ingestion --------------------------------------------------

    def ingest_data_message(
        self,
        message: Mapping[str, Any],
        *,
        local_received_epoch_ns: int,
        local_monotonic_received_ns: int,
        connection_generation: int,
    ) -> str:
        """Ingest one parsed public ticker data message; return an outcome tag.

        Fail-closed: malformed structure, topic/symbol mismatch, sequence or
        timestamp regression, generation conflict, or delta-before-snapshot all
        mark the affected symbol with a sticky hard-fail status.
        """
        self.ws_message_count += 1

        topic = str(message.get("topic", "")).strip()
        msg_type = str(message.get("type", "")).strip().lower()
        data = message.get("data")
        if not topic.startswith("tickers.") or not isinstance(data, Mapping):
            self.ws_malformed_message_count += 1
            return "malformed"

        sym = topic.split(".", 1)[1]
        ev = self._symbols.get(sym)
        if ev is None:
            # A topic outside our universe must never be silently accepted.
            self.ws_malformed_message_count += 1
            return "out_of_universe"

        ev.covered = True

        # topic vs data.symbol
        data_symbol = _canonical_symbol(data.get("symbol"))
        if data_symbol and data_symbol != sym:
            ev.fail(WS_SYMBOL_TOPIC_MISMATCH,
                    f"topic {sym} != data.symbol {data_symbol}")
            return "symbol_topic_mismatch"

        # connection-generation provenance
        gen = int(connection_generation)
        if ev.connection_generation is None:
            ev.connection_generation = gen
        elif ev.connection_generation != gen:
            ev.fail(WS_CONNECTION_GENERATION_CONFLICT,
                    f"evidence spans generations {ev.connection_generation} and {gen}")
            return "generation_conflict"

        # type accounting + snapshot-before-delta rule
        if msg_type == "snapshot":
            self.ws_snapshot_message_count += 1
            ev.snapshot_received = True
        elif msg_type == "delta":
            self.ws_delta_message_count += 1
            if not ev.snapshot_received:
                ev.fail(WS_SNAPSHOT_MISSING, "delta received before snapshot")
                return "delta_before_snapshot"
        else:
            self.ws_malformed_message_count += 1
            return "unknown_type"

        # ts / cs parsing
        ts_ms = _parse_int(message.get("ts"))
        cs = _parse_int(message.get("cs"))
        if ts_ms is None:
            ev.fail(WS_TIMESTAMP_INVALID, "top-level ts missing/malformed")
            return "ts_invalid"
        if cs is None:
            ev.fail(WS_TIMESTAMP_INVALID, "top-level cs missing/malformed")
            return "cs_invalid"

        # ordering / replay protection
        if ev.last_accepted_cs is not None:
            if cs < ev.last_accepted_cs:
                ev.out_of_order_cs_count += 1
                self.ws_out_of_order_message_count += 1
                ev.fail(WS_SEQUENCE_REGRESSION,
                        f"cs regressed {cs} < {ev.last_accepted_cs}")
                return "cs_regression"
            if cs == ev.last_accepted_cs:
                ev.duplicate_message_count += 1
                self.ws_duplicate_message_count += 1
                return "duplicate"
        if ev.last_accepted_ts is not None and ts_ms < ev.last_accepted_ts:
            ev.timestamp_regression_count += 1
            ev.fail(WS_TIMESTAMP_REGRESSION,
                    f"ts regressed {ts_ms} < {ev.last_accepted_ts}")
            return "ts_regression"

        ev.last_accepted_cs = cs
        ev.last_accepted_ts = ts_ms

        # selected price field handling: refresh price timestamp ONLY when the
        # exact selected field is present in THIS message's data.
        price_present = self.price_field in data
        if price_present:
            raw_price = data.get(self.price_field)
            if not _is_decimal_string(raw_price):
                ev.fail(WS_SELECTED_PRICE_FIELD_MISSING,
                        f"{self.price_field} present but not a Decimal string")
                ev.selected_price_updated_in_last_message = False
                return "price_field_malformed"
            ev.selected_price = str(raw_price)
            ev.selected_price_decimal_ok = True
            ev.selected_price_ts_ms = ts_ms
            ev.selected_price_cs = cs
            ev.selected_price_message_type = msg_type
            ev.selected_price_updated_in_last_message = True
            ev.selected_price_local_received_epoch_ns = int(local_received_epoch_ns)
            ev.selected_price_local_received_at_utc = _iso_from_epoch_ns(
                int(local_received_epoch_ns))
            ev.selected_price_local_monotonic_received_ns = int(
                local_monotonic_received_ns)
            ev.exchange_data_generated_ts_ms = ts_ms
            return "price_updated"

        ev.selected_price_updated_in_last_message = False
        return "no_price_change"

    # -- transport-delay / age estimates -----------------------------------

    def _transport_delay_ms(self, ev: SymbolEvidence) -> float | None:
        if (self.clock_offset_seconds is None
                or self.clock_offset_status != "CLOCK_OFFSET_AVAILABLE"
                or ev.selected_price_local_received_epoch_ns is None
                or ev.selected_price_ts_ms is None):
            return None
        local_s = Decimal(ev.selected_price_local_received_epoch_ns) / Decimal("1e9")
        est_exchange_s = local_s + self.clock_offset_seconds
        delay_s = est_exchange_s - (Decimal(ev.selected_price_ts_ms) / Decimal("1000"))
        return float(delay_s * Decimal("1000"))

    def _evidence_age_ms(self, ev: SymbolEvidence, finalize_epoch_ns: int) -> float | None:
        if ev.selected_price_local_received_epoch_ns is None:
            return None
        return (finalize_epoch_ns - ev.selected_price_local_received_epoch_ns) / 1e6

    # -- finalize -----------------------------------------------------------

    def _finalize_symbol_status(self, ev: SymbolEvidence, *,
                                finalize_epoch_ns: int) -> tuple[str, float | None,
                                                                 float | None]:
        delay_ms = self._transport_delay_ms(ev)
        age_ms = self._evidence_age_ms(ev, finalize_epoch_ns)

        if ev.hard_fail_status is not None:
            return ev.hard_fail_status, delay_ms, age_ms
        if not ev.covered or not ev.snapshot_received:
            return WS_SNAPSHOT_MISSING, delay_ms, age_ms
        if ev.selected_price is None or not ev.selected_price_decimal_ok:
            return WS_SELECTED_PRICE_FIELD_MISSING, delay_ms, age_ms
        if ev.selected_price_ts_ms is None or ev.selected_price_cs is None:
            return WS_TIMESTAMP_INVALID, delay_ms, age_ms

        # implausible-future ts
        finalize_ms = finalize_epoch_ns / 1e6
        if ev.selected_price_ts_ms > finalize_ms + self.future_tolerance_ms:
            return WS_TIMESTAMP_INVALID, delay_ms, age_ms

        # local timing / clock provenance required for a COMPLETE freshness claim
        if delay_ms is None:
            return WS_TIMESTAMP_STALE, delay_ms, age_ms
        if delay_ms < -self.negative_delay_tolerance_ms:
            return WS_TIMESTAMP_INVALID, delay_ms, age_ms
        if age_ms is None or age_ms > self.stale_threshold_ms:
            return WS_TIMESTAMP_STALE, delay_ms, age_ms

        return WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE, delay_ms, age_ms

    def build_per_symbol_evidence(self, *, finalize_epoch_ns: int) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        for sym in self.universe["symbols"]:
            ev = self._symbols[sym]
            status, delay_ms, age_ms = self._finalize_symbol_status(
                ev, finalize_epoch_ns=finalize_epoch_ns)
            fp_payload = {
                "symbol": ev.symbol,
                "topic": ev.topic,
                "selected_price_field": ev.selected_price_field,
                "selected_price": ev.selected_price,
                "selected_price_ts_ms": ev.selected_price_ts_ms,
                "selected_price_cs": ev.selected_price_cs,
                "connection_generation": ev.connection_generation,
                "status": status,
            }
            out.append({
                "symbol": ev.symbol,
                "topic": ev.topic,
                "connection_generation": ev.connection_generation,
                "snapshot_received": ev.snapshot_received,
                "selected_price_field": ev.selected_price_field,
                "selected_price": ev.selected_price,
                "selected_price_decimal": ev.selected_price,
                "selected_price_updated_in_message": (
                    ev.selected_price_updated_in_last_message),
                "selected_price_message_type": ev.selected_price_message_type,
                "selected_price_ts_ms": ev.selected_price_ts_ms,
                "selected_price_cs": ev.selected_price_cs,
                "selected_price_local_received_epoch_ns": (
                    ev.selected_price_local_received_epoch_ns),
                "selected_price_local_received_at_utc": (
                    ev.selected_price_local_received_at_utc),
                "selected_price_local_monotonic_received_ns": (
                    ev.selected_price_local_monotonic_received_ns),
                "exchange_data_generated_ts_ms": ev.exchange_data_generated_ts_ms,
                "exchange_data_generated_at_utc": _iso_from_ms(
                    ev.exchange_data_generated_ts_ms),
                "estimated_transport_delay_ms": (
                    None if delay_ms is None else round(delay_ms, 3)),
                "evidence_age_at_finalize_ms": (
                    None if age_ms is None else round(age_ms, 3)),
                "last_accepted_cs": ev.last_accepted_cs,
                "last_accepted_ts": ev.last_accepted_ts,
                "duplicate_message_count": ev.duplicate_message_count,
                "out_of_order_cs_count": ev.out_of_order_cs_count,
                "timestamp_regression_count": ev.timestamp_regression_count,
                "hard_fail_reason": ev.hard_fail_reason,
                "evidence_status": status,
                "evidence_fingerprint": _fingerprint(fp_payload),
            })
        return out

    def network_audit(self) -> dict[str, Any]:
        required = self.universe["unique_symbol_count"]
        covered = sum(1 for s in self.universe["symbols"] if self._symbols[s].covered)
        complete = sum(
            1 for s in self.universe["symbols"]
            if self._finalize_symbol_status(
                self._symbols[s], finalize_epoch_ns=0)[0]
            == WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE)
        return {
            "ws_connection_attempt_count": self.ws_connection_attempt_count,
            "ws_connection_success_count": self.ws_connection_success_count,
            "ws_reconnect_count": self.ws_reconnect_count,
            "ws_subscription_request_count": self.ws_subscription_request_count,
            "ws_subscription_topic_count": self.ws_subscription_topic_count,
            "ws_subscription_ack_count": self.ws_subscription_ack_count,
            "ws_message_count": self.ws_message_count,
            "ws_snapshot_message_count": self.ws_snapshot_message_count,
            "ws_delta_message_count": self.ws_delta_message_count,
            "ws_ping_count": self.ws_ping_count,
            "ws_pong_count": self.ws_pong_count,
            "ws_malformed_message_count": self.ws_malformed_message_count,
            "ws_duplicate_message_count": self.ws_duplicate_message_count,
            "ws_out_of_order_message_count": self.ws_out_of_order_message_count,
            "ws_required_symbol_count": required,
            "ws_covered_symbol_count": covered,
            "ws_complete_symbol_count": complete,
        }

    def build_artifact(
        self,
        *,
        finalize_epoch_ns: int,
        endpoint: str = PUBLIC_LINEAR_WS_ENDPOINT,
        subscription_acknowledged: bool = False,
        reconnect_generation_ambiguous: bool = False,
        collection_deadline_seconds: float | None = None,
    ) -> dict[str, Any]:
        per_symbol = self.build_per_symbol_evidence(finalize_epoch_ns=finalize_epoch_ns)
        audit = self.network_audit()

        statuses = [row["evidence_status"] for row in per_symbol]
        required = self.universe["unique_symbol_count"]
        complete_n = sum(1 for s in statuses if s == WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE)
        conflict = any(
            s in (WS_SYMBOL_TOPIC_MISMATCH, WS_CONNECTION_GENERATION_CONFLICT,
                  WS_PRICE_FIELD_SEMANTICS_MISMATCH)
            for s in statuses) or reconnect_generation_ambiguous

        if conflict:
            overall = WS_TICKER_EVIDENCE_CONFLICT
        elif complete_n == required and required > 0 and len(self._generations) <= 1:
            overall = WS_TICKER_EVIDENCE_COMPLETE
        elif audit["ws_covered_symbol_count"] == 0:
            overall = WS_TICKER_EVIDENCE_UNAVAILABLE
        else:
            overall = WS_TICKER_EVIDENCE_PARTIAL

        status_counts: dict[str, int] = {}
        for s in statuses:
            status_counts[s] = status_counts.get(s, 0) + 1

        coverage_summary = {
            "requested_symbol_count": self.universe["requested_symbol_count"],
            "unique_symbol_count": required,
            "covered_symbol_count": audit["ws_covered_symbol_count"],
            "complete_symbol_count": complete_n,
            "per_symbol_status_counts": status_counts,
            "all_required_complete": complete_n == required and required > 0,
        }

        # This task NEVER promotes execution readiness.
        freshness_summary = {
            "price_freshness_status": PRICE_FRESHNESS_EVIDENCE_PARTIAL,
            "execution_grade_freshness_complete": False,
            "rest_planner_prices_replaced": False,
            "per_symbol_exchange_quote_timestamp_available": (
                complete_n == required and required > 0),
            "integration_requirement": (
                "A later task MUST bind each planner action price to the exact "
                "same WebSocket message carrying the selected price field, symbol, "
                "ts, cs and local receive timing before freshness can become PASS."),
        }

        blockers = [
            PRICE_FRESHNESS_EVIDENCE_PARTIAL,
            PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE,
            WS_PRICE_NOT_BOUND_TO_PLANNER_ACTIONS,
            EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK,
        ]

        connection_summary = {
            "endpoint": assert_public_endpoint_allowed(endpoint),
            "channel_type": CHANNEL_TYPE,
            "environment": ENVIRONMENT,
            "authenticated": False,
            "connection_attempt_count": audit["ws_connection_attempt_count"],
            "connection_success_count": audit["ws_connection_success_count"],
            "reconnect_count": audit["ws_reconnect_count"],
            "connection_generation_count": len(self._generations),
            "connection_generations": sorted(self._generations),
            "reconnect_generation_ambiguous": reconnect_generation_ambiguous,
            "collection_deadline_seconds": collection_deadline_seconds,
        }
        subscription_summary = {
            "subscription_request_count": audit["ws_subscription_request_count"],
            "subscription_topic_count": audit["ws_subscription_topic_count"],
            "subscription_ack_count": audit["ws_subscription_ack_count"],
            "subscription_acknowledged": bool(subscription_acknowledged),
        }

        artifact: dict[str, Any] = {
            "schema_version": SCHEMA_VERSION,
            "schema": SCHEMA_NAME,
            "task_id": TASK_ID,
            "environment": ENVIRONMENT,
            "endpoint": connection_summary["endpoint"],
            "channel_type": CHANNEL_TYPE,
            "authenticated": False,
            "planner_price_field": self.price_field,
            "planner_price_field_source": PLANNER_PRICE_FIELD_SOURCE,
            "exchange_timestamp_label": "exchange_data_generated_ts_ms",
            "clock_offset_seconds": (
                None if self.clock_offset_seconds is None
                else str(self.clock_offset_seconds)),
            "clock_offset_status": self.clock_offset_status,
            "symbol_universe": self.universe,
            "connection_summary": connection_summary,
            "subscription_summary": subscription_summary,
            "message_audit": audit,
            "per_symbol_evidence": per_symbol,
            "coverage_summary": coverage_summary,
            "freshness_summary": freshness_summary,
            "overall_status": overall,
            "blockers": blockers,
            "execution_batch_authorized": False,
            "execution_ready": False,
            "sender_reachable": False,
            "order_post_count": 0,
            "amend_post_count": 0,
            "cancel_post_count": 0,
            "live_order_post_count": 0,
        }
        # The artifact must never carry a credential key/value.
        assert_no_credentials(artifact)
        artifact["artifact_fingerprint"] = _fingerprint(
            {k: v for k, v in artifact.items() if k != "artifact_fingerprint"})
        return artifact


__all__ = [
    "TASK_ID", "SCHEMA_NAME", "SCHEMA_VERSION", "ENVIRONMENT", "CHANNEL_TYPE",
    "PUBLIC_LINEAR_WS_ENDPOINT", "PLANNER_PRICE_FIELD", "PLANNER_PRICE_FIELD_SOURCE",
    "WS_TICKER_EVIDENCE_COMPLETE", "WS_TICKER_EVIDENCE_PARTIAL",
    "WS_TICKER_EVIDENCE_UNAVAILABLE", "WS_TICKER_EVIDENCE_CONFLICT",
    "WS_PRICE_TIMESTAMP_EVIDENCE_COMPLETE", "WS_SNAPSHOT_MISSING",
    "WS_SELECTED_PRICE_FIELD_MISSING", "WS_TIMESTAMP_INVALID", "WS_TIMESTAMP_STALE",
    "WS_SEQUENCE_REGRESSION", "WS_TIMESTAMP_REGRESSION", "WS_SYMBOL_TOPIC_MISMATCH",
    "WS_CONNECTION_GENERATION_CONFLICT", "WS_PRICE_FIELD_SEMANTICS_MISMATCH",
    "WsEndpointError", "assert_public_endpoint_allowed", "assert_public_topic",
    "assert_no_credentials", "build_subscription_message", "validate_linear_symbol",
    "derive_required_symbol_universe", "SymbolEvidence",
    "PublicWsTickerEvidenceBuilder",
]
