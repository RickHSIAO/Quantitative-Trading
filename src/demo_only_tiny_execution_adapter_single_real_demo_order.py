"""TASK-014BO -- demo-only single real Bybit Demo order execution gate.

This module implements ONE manually-triggered, fail-closed execution path
for the single Bybit Demo order that Rick has explicitly authorized:

    Bybit Demo only / https://api-demo.bybit.com / POST /v5/order/create
    category=linear symbol=SOLUSDT side=Buy orderType=Market qty="0.1"
    timeInForce=IOC reduceOnly=false closeOnTrigger=false
    maximum order-create POST calls = 1, maximum orders submitted = 1,
    automatic retry forbidden.

Exact human authorization (recorded verbatim):
    "I authorize one Bybit Demo SOLUSDT 0.1 Buy Market IOC order test.
     Live endpoints are forbidden. More than one order is forbidden.
     Automatic retries are forbidden."

CRITICAL: importing this module, running its tests, generating reports,
or running CLI ``preflight`` mode NEVER sends an order. The single real
order may only be sent by a deliberate, fully-gated ``execute_once``
invocation run manually on the VPS, after every preflight gate passes.

Hard safety invariants (cross-checked by tests):
    * Only ``https://api-demo.bybit.com`` may ever be contacted. Live
      (``api.bybit.com``) and Testnet (``api-testnet.bybit.com``) hosts
      are rejected. Redirects to another host are rejected, never followed.
    * Only ``BYBIT_DEMO_API_KEY`` / ``BYBIT_DEMO_API_SECRET`` /
      ``BYBIT_DEMO_RECV_WINDOW`` are read. Live / Testnet credential
      aliases are never read. Secrets are never printed, serialized,
      or stored in any report.
    * The order-create sender may be invoked at most once (in-process
      ``OneShotSenderGuard``) and a durable crash-safe one-shot journal
      refuses any resubmission once a POST may have occurred.
    * No retry, no scheduler, no loop, no fallback sender, no batch sender,
      no second client. No automatic close, no TP/SL, no reduce-only.
    * Does not import or use ``BybitExecutor`` / ``main`` / ``src.risk``.
    * Stage 1 fake-only behavior elsewhere is untouched; a real Demo
      transport here is NEVER labelled ``FAKE_SENDER``.
"""

from __future__ import annotations

import hashlib
import hmac
import json
import os
import pathlib
import re
import time
import urllib.error
import urllib.parse
import urllib.request
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BO"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-SINGLE-REAL-DEMO-ORDER"
IMPLEMENTATION_PATH_PHASE = "single_real_demo_order"
IS_REVIEW_CHAIN_SUFFIX = False

# The one exact authorization marker. Possession of the marker alone is NOT
# sufficient: every preflight gate, flag, commit hash, body hash, credential,
# journal, and manual command must also match.
AUTHORIZATION_MARKER = (
    "DEMO_ONLY_SOLUSDT_0_1_BUY_MARKET_IOC_ONE_SHOT_RICK_AUTHORIZED_20260621"
)

AUTHORIZATION_QUOTE = (
    "I authorize one Bybit Demo SOLUSDT 0.1 Buy Market IOC order test. "
    "Live endpoints are forbidden. More than one order is forbidden. "
    "Automatic retries are forbidden."
)

# Immutable description of the authorized order scope. The permanent exchange
# deduplication identity (orderLinkId) is derived ONLY from this plus TASK_ID
# and the marker, so it never changes when new (e.g. documentation/result)
# commits are created. It deliberately contains NO commit SHA, date, time,
# randomness, PID, or hostname.
AUTHORIZATION_SCOPE_IDENTITY = (
    "TASK-014BO|BYBIT_DEMO|linear|SOLUSDT|Buy|Market|0.1|IOC|"
    "reduceOnly=false|closeOnTrigger=false|max_order_create_post=1"
)


# ---------------------------------------------------------------------------
# Endpoint locks
# ---------------------------------------------------------------------------

DEMO_BASE_URL = "https://api-demo.bybit.com"
DEMO_HOST = "api-demo.bybit.com"
ORDER_CREATE_PATH = "/v5/order/create"

# Read-only verification endpoints (Demo host only).
EP_ORDER_REALTIME = "/v5/order/realtime"
EP_ORDER_HISTORY = "/v5/order/history"
EP_EXECUTION_LIST = "/v5/execution/list"
EP_POSITION_LIST = "/v5/position/list"
EP_INSTRUMENTS = "/v5/market/instruments-info"
EP_TICKERS = "/v5/market/tickers"
EP_WALLET = "/v5/account/wallet-balance"
EP_OPEN_ORDERS = "/v5/order/realtime"

# Hosts that must always be rejected. Defined as blocking sentinels only;
# never used as a request target.
FORBIDDEN_HOSTS: frozenset[str] = frozenset(
    {
        "api.bybit.com",
        "api-testnet.bybit.com",
        "api.bytick.com",
        "api-testnet.bytick.com",
        "stream.bybit.com",
    }
)


# ---------------------------------------------------------------------------
# Immutable approved order contract
# ---------------------------------------------------------------------------

REQUIRED_CATEGORY = "linear"
REQUIRED_SYMBOL = "SOLUSDT"
REQUIRED_SIDE = "Buy"
REQUIRED_ORDER_TYPE = "Market"
REQUIRED_QTY = Decimal("0.1")
REQUIRED_QTY_STR = "0.1"
REQUIRED_TIME_IN_FORCE = "IOC"
REQUIRED_REDUCE_ONLY = False
REQUIRED_CLOSE_ON_TRIGGER = False

# The order-create body must contain EXACTLY these nine fields.
APPROVED_BODY_FIELDS: tuple[str, ...] = (
    "category",
    "symbol",
    "side",
    "orderType",
    "qty",
    "timeInForce",
    "reduceOnly",
    "closeOnTrigger",
    "orderLinkId",
)

MAX_ORDER_CREATE_CALLS = 1
MAX_ORDERS_SUBMITTED = 1
RETRY_ENABLED = False
SCHEDULER_ENABLED = False
QTY_ADJUSTMENT_ALLOWED = False

# 0.1 * mark_price must be <= 20 USDT.
MAX_NOTIONAL_USDT = Decimal("20")

ORDER_LINK_ID_PREFIX = "BO1-"
ORDER_LINK_ID_MAX_LEN = 36

# Protected symbols that must never be touched.
PROTECTED_SYMBOLS: frozenset[str] = frozenset(
    {"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"}
)

# Credential env var names. Live / Testnet aliases are intentionally absent.
ENV_DEMO_API_KEY = "BYBIT_DEMO_API_KEY"
ENV_DEMO_API_SECRET = "BYBIT_DEMO_API_SECRET"
ENV_DEMO_RECV_WINDOW = "BYBIT_DEMO_RECV_WINDOW"
DEFAULT_RECV_WINDOW = "5000"

# Required execute_once control flags (canonical set).
REQUIRED_EXECUTE_MODE = "execute_once"
REQUIRED_EXECUTE_FLAG = "execute_one_real_demo_order"


# ---------------------------------------------------------------------------
# Journal states
# ---------------------------------------------------------------------------

JOURNAL_FILENAME = "task_014bo_one_shot_journal.json"

# The journal location is CANONICAL and NOT caller-overridable. It is anchored
# to the repository root (this file lives in <root>/src/), never to the current
# working directory, and never to a CLI argument / env var / config file.
PROJECT_ROOT = pathlib.Path(__file__).resolve().parents[1]
CANONICAL_JOURNAL_DIR = (
    PROJECT_ROOT / "outputs" / "demo_trading" / "task_014bo_single_real_demo_order"
)
# Retained name for reports/back-compat; equals the canonical resolved path.
DEFAULT_JOURNAL_DIR = str(CANONICAL_JOURNAL_DIR)

JOURNAL_STATE_NONE = "NONE"
JOURNAL_STATE_ARMED_BEFORE_POST = "ARMED_BEFORE_POST"
JOURNAL_STATE_POST_RESPONSE_RECEIVED = "POST_RESPONSE_RECEIVED"
JOURNAL_STATE_POST_EXCEPTION_AMBIGUOUS = "POST_EXCEPTION_AMBIGUOUS"
JOURNAL_STATE_POST_TIMEOUT_AMBIGUOUS = "POST_TIMEOUT_AMBIGUOUS"
JOURNAL_STATE_POST_REDIRECT_REJECTED = "POST_REDIRECT_REJECTED"
JOURNAL_STATE_POST_REJECTED_BEFORE_NETWORK = "POST_REJECTED_BEFORE_NETWORK"
JOURNAL_STATE_POST_RESULT_VERIFIED = "POST_RESULT_VERIFIED"
JOURNAL_STATE_POST_RESULT_UNVERIFIED = "POST_RESULT_UNVERIFIED"

# Any of these states means a POST may already have occurred (or the run is
# already consumed): a rerun must refuse.
BLOCKING_JOURNAL_STATES: frozenset[str] = frozenset(
    {
        JOURNAL_STATE_ARMED_BEFORE_POST,
        JOURNAL_STATE_POST_RESPONSE_RECEIVED,
        JOURNAL_STATE_POST_EXCEPTION_AMBIGUOUS,
        JOURNAL_STATE_POST_TIMEOUT_AMBIGUOUS,
        JOURNAL_STATE_POST_REDIRECT_REJECTED,
        JOURNAL_STATE_POST_REJECTED_BEFORE_NETWORK,
        JOURNAL_STATE_POST_RESULT_VERIFIED,
        JOURNAL_STATE_POST_RESULT_UNVERIFIED,
    }
)


# ---------------------------------------------------------------------------
# Final outcome conclusions
# ---------------------------------------------------------------------------

OUTCOME_FILLED_VERIFIED = "DEMO_ORDER_FILLED_VERIFIED"
OUTCOME_PARTIALLY_FILLED_VERIFIED = "DEMO_ORDER_PARTIALLY_FILLED_VERIFIED"
OUTCOME_CANCELLED_VERIFIED = "DEMO_ORDER_CANCELLED_VERIFIED"
OUTCOME_REJECTED_VERIFIED = "DEMO_ORDER_REJECTED_VERIFIED"
OUTCOME_ACCEPTED_STATUS_PENDING = "DEMO_ORDER_ACCEPTED_STATUS_PENDING"
OUTCOME_POST_FAILED = "DEMO_ORDER_POST_FAILED"
OUTCOME_AMBIGUOUS = "DEMO_ORDER_OUTCOME_AMBIGUOUS"
OUTCOME_REFUSED_PREFLIGHT = "DEMO_ORDER_REFUSED_PREFLIGHT"


# Read-only verification polling limits.
MAX_REALTIME_READS = 3
MAX_HISTORY_READS = 1
MAX_EXECUTION_READS = 1
MAX_POSITION_READS = 1
VERIFICATION_POLL_DELAY_SECONDS = 0.5


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class SingleRealDemoOrderError(Exception):
    """Base class for all single-real-demo-order rejections."""


class EndpointLockViolation(SingleRealDemoOrderError):
    """A non-demo host / forbidden URL was referenced."""


class RedirectRejected(SingleRealDemoOrderError):
    """A redirect to another host was attempted and refused."""


class CredentialsMissing(SingleRealDemoOrderError):
    """Required Demo credentials are absent."""


class SenderInvokedTwice(SingleRealDemoOrderError):
    """A second order-create send was attempted (hard safety error)."""


class JournalStateConflict(SingleRealDemoOrderError):
    """A journal already exists in a state that forbids submission."""


class TransportTimeout(SingleRealDemoOrderError):
    """The order-create POST timed out (ambiguous; no retry)."""


class TransportConnectionError(SingleRealDemoOrderError):
    """The order-create POST hit a connection error (ambiguous; no retry)."""


# ---------------------------------------------------------------------------
# Time / clock
# ---------------------------------------------------------------------------


class _RealClock:
    def now_utc(self) -> datetime:
        return datetime.now(timezone.utc)

    def sleep(self, seconds: float) -> None:
        time.sleep(seconds)


def _utc_timestamp(clock: Any | None = None) -> str:
    now = (clock or _RealClock()).now_utc()
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def _utc_compact(clock: Any | None = None) -> str:
    now = (clock or _RealClock()).now_utc()
    return now.strftime("%Y%m%dT%H%M%SZ")


def _utc_yyyymmdd(clock: Any | None = None) -> str:
    now = (clock or _RealClock()).now_utc()
    return now.strftime("%Y%m%d")


# ---------------------------------------------------------------------------
# Endpoint helpers
# ---------------------------------------------------------------------------


def host_of(url: str) -> str:
    return urllib.parse.urlsplit(url).hostname or ""


def assert_demo_url(url: str) -> None:
    """Reject any URL whose host is not exactly ``api-demo.bybit.com``."""
    host = host_of(url)
    if host in FORBIDDEN_HOSTS:
        raise EndpointLockViolation(
            f"forbidden host {host!r} (url={url!r}); only {DEMO_HOST!r} allowed"
        )
    if host != DEMO_HOST:
        raise EndpointLockViolation(
            f"host {host!r} not allowed (url={url!r}); only {DEMO_HOST!r} allowed"
        )
    if not url.startswith(DEMO_BASE_URL):
        raise EndpointLockViolation(
            f"url {url!r} must start with {DEMO_BASE_URL!r}"
        )


# ---------------------------------------------------------------------------
# Approved body + hashing
# ---------------------------------------------------------------------------


_FULL_SHA_RE = re.compile(r"^[0-9a-f]{40}$")


def is_full_commit_sha(value: str | None) -> bool:
    """True only for an exact 40-character lowercase hexadecimal SHA.

    Rejects 7-char short hashes, abbreviated/prefix SHAs, uppercase, symbolic
    refs (HEAD/main), and whitespace variants.
    """
    if not isinstance(value, str):
        return False
    return bool(_FULL_SHA_RE.match(value))


def build_order_link_id() -> str:
    """Permanently STABLE exchange-deduplication orderLinkId for THIS
    authorization.

    Derived ONLY from immutable authorization identity:
    ``TASK_ID | AUTHORIZATION_MARKER | AUTHORIZATION_SCOPE_IDENTITY``. It
    contains NO commit SHA, no UTC date, no timestamp, no random/UUID, no
    hostname, and no PID. Consequently it is identical across different valid
    Git commits (including future documentation/result/closeout commits),
    across clock dates, and across process restarts; preflight and execute_once
    derive the same value; and a caller cannot override it. It therefore
    remains a permanent duplicate-detection key even if the local journal is
    lost or a later commit is created.

    Commit identity is enforced SEPARATELY as a runtime code-identity gate and
    deliberately does NOT influence this value.
    """
    digest = hashlib.sha256(
        (TASK_ID + "|" + AUTHORIZATION_MARKER + "|" + AUTHORIZATION_SCOPE_IDENTITY).encode("utf-8")
    ).hexdigest()[:16]
    link = f"{ORDER_LINK_ID_PREFIX}{digest}"
    return link[:ORDER_LINK_ID_MAX_LEN]


def build_approved_body(*, order_link_id: str) -> dict[str, Any]:
    """Return the exact nine-field approved order-create body."""
    return {
        "category": REQUIRED_CATEGORY,
        "symbol": REQUIRED_SYMBOL,
        "side": REQUIRED_SIDE,
        "orderType": REQUIRED_ORDER_TYPE,
        "qty": REQUIRED_QTY_STR,
        "timeInForce": REQUIRED_TIME_IN_FORCE,
        "reduceOnly": REQUIRED_REDUCE_ONLY,
        "closeOnTrigger": REQUIRED_CLOSE_ON_TRIGGER,
        "orderLinkId": order_link_id,
    }


def canonical_body_json(body: Mapping[str, Any]) -> str:
    """Deterministic canonical JSON (sorted keys, compact separators)."""
    return json.dumps(body, sort_keys=True, separators=(",", ":"))


def body_hash(body: Mapping[str, Any]) -> str:
    return hashlib.sha256(canonical_body_json(body).encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Credentials (sanitized view; secrets never stored here)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DemoCredentials:
    api_key_present: bool
    api_secret_present: bool
    recv_window: str
    source: str  # "BYBIT_DEMO" when both present, else "absent"

    @property
    def usable(self) -> bool:
        return self.api_key_present and self.api_secret_present


def load_demo_credentials(env: Mapping[str, str] | None = None) -> DemoCredentials:
    """Read ONLY ``BYBIT_DEMO_*`` credentials. Live/Testnet aliases ignored.

    The returned object carries presence flags only; the secret value is
    never stored in it and never returned.
    """
    src = env if env is not None else os.environ
    key = src.get(ENV_DEMO_API_KEY, "") or ""
    secret = src.get(ENV_DEMO_API_SECRET, "") or ""
    recv = src.get(ENV_DEMO_RECV_WINDOW, "") or DEFAULT_RECV_WINDOW
    key_present = bool(key.strip())
    secret_present = bool(secret.strip())
    source = "BYBIT_DEMO" if (key_present and secret_present) else "absent"
    return DemoCredentials(
        api_key_present=key_present,
        api_secret_present=secret_present,
        recv_window=str(recv).strip() or DEFAULT_RECV_WINDOW,
        source=source,
    )


# ---------------------------------------------------------------------------
# Account snapshot (read-only inputs to preflight gates)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class AccountSnapshot:
    instrument_fresh: bool
    symbol_tradable: bool
    min_order_qty: Decimal | None
    qty_step: Decimal | None
    mark_price: Decimal | None
    mark_price_fresh: bool
    open_order_symbols: tuple[str, ...]
    position_sizes: Mapping[str, Decimal]
    available_balance_usdt: Decimal | None
    position_mode_one_way: bool
    read_source: str  # "fixture" / "bybit_demo_readonly" / "unavailable"

    def has_open_solusdt_order(self) -> bool:
        return REQUIRED_SYMBOL in set(self.open_order_symbols)

    def has_open_solusdt_position(self) -> bool:
        size = self.position_sizes.get(REQUIRED_SYMBOL)
        return size is not None and size != 0


# ---------------------------------------------------------------------------
# Exchange-side duplicate detection (by the fixed orderLinkId)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DuplicateCheckResult:
    realtime_checked: bool
    realtime_match: bool
    history_checked: bool
    history_match: bool
    ambiguous: bool
    detail: str

    @property
    def clean(self) -> bool:
        """True only if BOTH sources were successfully checked and neither
        contains the orderLinkId and nothing was ambiguous."""
        return (
            self.realtime_checked
            and self.history_checked
            and not self.realtime_match
            and not self.history_match
            and not self.ambiguous
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "realtime_checked": self.realtime_checked,
            "realtime_match": self.realtime_match,
            "history_checked": self.history_checked,
            "history_match": self.history_match,
            "ambiguous": self.ambiguous,
            "clean": self.clean,
            "detail": self.detail,
        }


def _scan_for_order_link(resp: Any, order_link_id: str) -> tuple[bool, bool, bool]:
    """Scan one read-only response for the fixed orderLinkId.

    Returns ``(checked, match, ambiguous)``. ``checked`` is True only when the
    response is a well-formed retCode==0 payload whose list could be parsed.
    Any failed / malformed / unexpected response is reported as not-checked and
    ambiguous so the caller fails closed. Any item carrying the orderLinkId is a
    match regardless of order state; any unparseable item is treated as
    potentially matching (ambiguous).
    """
    if not isinstance(resp, Mapping):
        return (False, False, True)
    try:
        ret_code = int(resp.get("retCode", -1))
    except (TypeError, ValueError):
        return (False, False, True)
    if ret_code != 0:
        return (False, False, True)
    result = resp.get("result")
    if not isinstance(result, Mapping) or "list" not in result:
        return (False, False, True)
    items = result.get("list")
    if not isinstance(items, (list, tuple)):
        return (False, False, True)
    match = False
    ambiguous = False
    for item in items:
        if not isinstance(item, Mapping):
            ambiguous = True
            continue
        if "orderLinkId" not in item:
            # An order present without an orderLinkId field is potentially
            # matching evidence for this symbol -> fail closed.
            ambiguous = True
            continue
        if str(item.get("orderLinkId", "")) == order_link_id:
            match = True
    return (True, match, ambiguous)


def perform_duplicate_check(probe: Any, order_link_id: str) -> DuplicateCheckResult:
    """Authenticated read-only duplicate detection by the fixed orderLinkId.

    Queries ``/v5/order/realtime`` and ``/v5/order/history`` for the exact
    orderLinkId. A query failure is NEVER interpreted as "no order exists";
    it fails closed (checked=False -> not clean).
    """
    rt_checked = rt_match = False
    hist_checked = hist_match = False
    ambiguous = False
    details: list[str] = []

    try:
        rt = probe.lookup_order_link_realtime(order_link_id=order_link_id)
        rt_checked, rt_match, amb = _scan_for_order_link(rt, order_link_id)
        ambiguous = ambiguous or amb
    except Exception as exc:  # any read failure fails closed
        ambiguous = True
        details.append(f"realtime_query_error:{exc}")

    try:
        hist = probe.lookup_order_link_history(order_link_id=order_link_id)
        hist_checked, hist_match, amb = _scan_for_order_link(hist, order_link_id)
        ambiguous = ambiguous or amb
    except Exception as exc:
        ambiguous = True
        details.append(f"history_query_error:{exc}")

    if rt_match:
        details.append("realtime_match")
    if hist_match:
        details.append("history_match")
    if not rt_checked:
        details.append("realtime_not_checked")
    if not hist_checked:
        details.append("history_not_checked")

    return DuplicateCheckResult(
        realtime_checked=rt_checked,
        realtime_match=rt_match,
        history_checked=hist_checked,
        history_match=hist_match,
        ambiguous=ambiguous,
        detail="; ".join(details) if details else "clean",
    )


def offline_duplicate_check(
    detail: str = "authenticated exchange duplicate checks not performed",
) -> DuplicateCheckResult:
    """Fail-closed duplicate-check result for any offline / no-network preflight.

    "Network not attempted" is NEVER equated with "no duplicate exists": the
    result reports neither source as checked and marks the outcome ambiguous so
    the duplicate-check gate fails closed.
    """
    return DuplicateCheckResult(
        realtime_checked=False,
        realtime_match=False,
        history_checked=False,
        history_match=False,
        ambiguous=True,
        detail=detail,
    )


# ---------------------------------------------------------------------------
# Preflight gates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class GateResult:
    index: int
    name: str
    passed: bool
    detail: str


@dataclass(frozen=True)
class PreflightReport:
    task_id: str
    mode: str  # "preflight" or "execute_once_precheck"
    generated_at_utc: str
    expected_commit: str
    actual_commit: str
    authorization_marker_matches: bool
    order_link_id: str
    request_body: Mapping[str, Any]
    request_body_hash: str
    journal_state: str
    credentials_source: str
    gates: tuple[GateResult, ...]
    all_passed: bool
    ready: bool
    duplicate_check: Mapping[str, Any] | None = None

    def failed_gates(self) -> tuple[GateResult, ...]:
        return tuple(g for g in self.gates if not g.passed)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "mode": self.mode,
            "generated_at_utc": self.generated_at_utc,
            "expected_commit": self.expected_commit,
            "actual_commit": self.actual_commit,
            "authorization_marker_matches": self.authorization_marker_matches,
            "order_link_id": self.order_link_id,
            "request_body": dict(self.request_body),
            "request_body_hash": self.request_body_hash,
            "journal_state": self.journal_state,
            "credentials_source": self.credentials_source,
            "gates": [
                {
                    "index": g.index,
                    "name": g.name,
                    "passed": g.passed,
                    "detail": g.detail,
                }
                for g in self.gates
            ],
            "all_passed": self.all_passed,
            "ready": self.ready,
            "duplicate_check": dict(self.duplicate_check) if self.duplicate_check else None,
            "failed_gate_names": [g.name for g in self.failed_gates()],
        }


def _qty_satisfies_step(qty: Decimal, step: Decimal) -> bool:
    if step <= 0:
        return False
    ratio = (qty / step)
    return ratio == ratio.to_integral_value()


def evaluate_preflight_gates(
    *,
    request_body: Mapping[str, Any],
    order_link_id: str,
    authorization_marker: str | None,
    expected_commit: str | None,
    actual_commit: str | None,
    credentials: DemoCredentials,
    snapshot: AccountSnapshot | None,
    journal_state: str,
    execution_flags: Mapping[str, Any] | None,
    expected_body_hash: str | None,
    real_order_count_before: int,
    duplicate_check: DuplicateCheckResult | None = None,
    base_url: str = DEMO_BASE_URL,
) -> list[GateResult]:
    """Evaluate the 31 fail-closed preflight gates. Pure; no I/O."""
    gates: list[GateResult] = []

    def add(index: int, name: str, passed: bool, detail: str = "") -> None:
        gates.append(GateResult(index=index, name=name, passed=bool(passed), detail=detail))

    body = dict(request_body)
    computed_hash = body_hash(body) if set(body) == set(APPROVED_BODY_FIELDS) else ""

    # 1. Git / code identity -- exact 40-char lowercase hex SHA, equal to HEAD.
    commit_ok = (
        is_full_commit_sha(expected_commit)
        and is_full_commit_sha(actual_commit)
        and expected_commit == actual_commit
    )
    add(1, "git_identity_matches_approved_full_sha", commit_ok,
        f"expected={expected_commit!r} actual={actual_commit!r} "
        f"(full 40-char lowercase hex required)")

    # 2. Endpoint host lock
    try:
        assert_demo_url(base_url + ORDER_CREATE_PATH)
        host_ok = host_of(base_url) == DEMO_HOST
    except EndpointLockViolation:
        host_ok = False
    add(2, "endpoint_host_is_api_demo_bybit_com", host_ok, f"base_url={base_url!r}")

    # 3. Credentials from BYBIT_DEMO_* only
    add(3, "credentials_are_bybit_demo_only",
        credentials.usable and credentials.source == "BYBIT_DEMO",
        f"source={credentials.source!r} key={credentials.api_key_present} "
        f"secret={credentials.api_secret_present}")

    # 4-11. Exact body field values
    add(4, "category_is_linear", body.get("category") == REQUIRED_CATEGORY,
        f"category={body.get('category')!r}")
    add(5, "symbol_is_solusdt", body.get("symbol") == REQUIRED_SYMBOL,
        f"symbol={body.get('symbol')!r}")
    add(6, "side_is_buy", body.get("side") == REQUIRED_SIDE,
        f"side={body.get('side')!r}")
    add(7, "order_type_is_market", body.get("orderType") == REQUIRED_ORDER_TYPE,
        f"orderType={body.get('orderType')!r}")
    add(8, "time_in_force_is_ioc", body.get("timeInForce") == REQUIRED_TIME_IN_FORCE,
        f"timeInForce={body.get('timeInForce')!r}")
    qty_exact = False
    try:
        qty_exact = Decimal(str(body.get("qty"))) == REQUIRED_QTY and str(body.get("qty")) == REQUIRED_QTY_STR
    except (InvalidOperation, TypeError, ValueError):
        qty_exact = False
    add(9, "qty_is_exactly_decimal_0_1", qty_exact, f"qty={body.get('qty')!r}")
    add(10, "reduce_only_is_false", body.get("reduceOnly") is False,
        f"reduceOnly={body.get('reduceOnly')!r}")
    add(11, "close_on_trigger_is_false", body.get("closeOnTrigger") is False,
        f"closeOnTrigger={body.get('closeOnTrigger')!r}")

    # 12. Exactly the nine approved fields
    add(12, "body_has_exactly_nine_approved_fields",
        set(body) == set(APPROVED_BODY_FIELDS),
        f"fields={sorted(body)!r}")

    # 13. Max order count is one
    add(13, "max_order_count_is_one",
        MAX_ORDER_CREATE_CALLS == 1 and MAX_ORDERS_SUBMITTED == 1,
        f"create_calls={MAX_ORDER_CREATE_CALLS} submitted={MAX_ORDERS_SUBMITTED}")

    # 14. No retry policy active
    add(14, "no_retry_policy_active", RETRY_ENABLED is False)

    # 15. No scheduler / automatic caller active
    add(15, "no_scheduler_active", SCHEDULER_ENABLED is False)

    # 16. Instrument rules freshly read and SOLUSDT tradable
    instr_ok = bool(snapshot) and snapshot.instrument_fresh and snapshot.symbol_tradable
    add(16, "instrument_rules_fresh_and_tradable", instr_ok,
        f"fresh={getattr(snapshot, 'instrument_fresh', None)} "
        f"tradable={getattr(snapshot, 'symbol_tradable', None)}")

    # 17. qty satisfies min qty and step
    qty_rules_ok = False
    if snapshot and snapshot.min_order_qty is not None and snapshot.qty_step is not None:
        qty_rules_ok = (
            REQUIRED_QTY >= snapshot.min_order_qty
            and _qty_satisfies_step(REQUIRED_QTY, snapshot.qty_step)
        )
    add(17, "qty_satisfies_min_and_step", qty_rules_ok,
        f"min={getattr(snapshot, 'min_order_qty', None)} "
        f"step={getattr(snapshot, 'qty_step', None)}")

    # 18. Fresh mark price available
    mark_ok = bool(snapshot) and snapshot.mark_price is not None and snapshot.mark_price_fresh
    add(18, "fresh_mark_price_available", mark_ok,
        f"mark={getattr(snapshot, 'mark_price', None)} "
        f"fresh={getattr(snapshot, 'mark_price_fresh', None)}")

    # 19. notional <= 20 USDT
    notional_ok = False
    notional_val: Decimal | None = None
    if snapshot and snapshot.mark_price is not None:
        notional_val = (REQUIRED_QTY * snapshot.mark_price)
        notional_ok = notional_val <= MAX_NOTIONAL_USDT
    add(19, "notional_within_20_usdt", notional_ok,
        f"notional={notional_val} cap={MAX_NOTIONAL_USDT}")

    # 20. No fallback or quantity adjustment
    add(20, "no_qty_adjustment_allowed",
        QTY_ADJUSTMENT_ALLOWED is False and str(body.get("qty")) == REQUIRED_QTY_STR)

    # 21. No active SOLUSDT order
    add(21, "no_active_solusdt_order",
        bool(snapshot) and not snapshot.has_open_solusdt_order(),
        f"open_orders={getattr(snapshot, 'open_order_symbols', None)}")

    # 22. No existing SOLUSDT position
    add(22, "no_existing_solusdt_position",
        bool(snapshot) and not snapshot.has_open_solusdt_position(),
        f"positions={dict(snapshot.position_sizes) if snapshot else None}")

    # 23. Position mode compatible with exact body (one-way; no positionIdx)
    add(23, "position_mode_one_way_compatible",
        bool(snapshot) and snapshot.position_mode_one_way,
        f"one_way={getattr(snapshot, 'position_mode_one_way', None)}")

    # 24. Sufficient Demo wallet balance
    bal_ok = False
    if snapshot and snapshot.available_balance_usdt is not None and notional_val is not None:
        bal_ok = snapshot.available_balance_usdt >= notional_val
    add(24, "sufficient_demo_balance", bal_ok,
        f"available={getattr(snapshot, 'available_balance_usdt', None)} "
        f"required={notional_val}")

    # 25. Protected symbols untouched
    protected_ok = (
        REQUIRED_SYMBOL not in PROTECTED_SYMBOLS
        and (not snapshot or not (set(snapshot.open_order_symbols) & PROTECTED_SYMBOLS))
    )
    add(25, "protected_symbols_untouched", protected_ok)

    # 26. No conflicting one-shot journal
    add(26, "no_conflicting_one_shot_journal",
        journal_state not in BLOCKING_JOURNAL_STATES,
        f"journal_state={journal_state!r}")

    # 27. Exact authorization marker
    add(27, "authorization_marker_matches",
        authorization_marker == AUTHORIZATION_MARKER,
        "marker matches" if authorization_marker == AUTHORIZATION_MARKER else "marker mismatch/missing")

    # 28. Exact final execution flags
    flags = dict(execution_flags or {})
    flags_ok = (
        flags.get("mode") == REQUIRED_EXECUTE_MODE
        and flags.get(REQUIRED_EXECUTE_FLAG) is True
    )
    add(28, "execution_flags_match", flags_ok, f"flags={flags!r}")

    # 29. Request-body hash matches preflight-approved body
    if expected_body_hash is None:
        hash_ok = computed_hash != ""
    else:
        hash_ok = computed_hash != "" and computed_hash == expected_body_hash
    add(29, "request_body_hash_matches", hash_ok,
        f"computed={computed_hash!r} expected={expected_body_hash!r}")

    # 30. Real order count before POST is zero
    add(30, "real_order_count_before_is_zero", real_order_count_before == 0,
        f"count={real_order_count_before}")

    # 31. Exchange-side duplicate detection by the fixed orderLinkId.
    # Passes ONLY when both authenticated read-only sources were successfully
    # checked and neither contains the orderLinkId (fail closed otherwise).
    dup_ok = duplicate_check is not None and duplicate_check.clean
    add(31, "no_existing_exchange_order_for_fixed_order_link_id", dup_ok,
        duplicate_check.detail if duplicate_check is not None else "duplicate check not performed")

    return gates


def run_preflight(
    *,
    probe: Any,
    credentials: DemoCredentials,
    expected_commit: str | None,
    authorization_marker: str | None,
    actual_commit: str | None = None,
    journal_state: str = JOURNAL_STATE_NONE,
    execution_flags: Mapping[str, Any] | None = None,
    expected_body_hash: str | None = None,
    real_order_count_before: int = 0,
    allow_real_network: bool = False,
    clock: Any | None = None,
    base_url: str = DEMO_BASE_URL,
    mode: str = "preflight",
) -> PreflightReport:
    """Run all read-only preflight checks. NEVER sends an order, NEVER arms a
    journal.

    ``probe`` must expose ``build_account_snapshot()``. Authenticated exchange
    duplicate detection is performed ONLY when ``allow_real_network`` is True
    AND Demo credentials are usable; otherwise the duplicate-check result is
    fail-closed ("not performed") so the duplicate gate cannot pass offline.
    """
    order_link_id = build_order_link_id()
    body = build_approved_body(order_link_id=order_link_id)
    computed_hash = body_hash(body)

    try:
        snapshot = probe.build_account_snapshot()
    except Exception:  # fail closed: any read failure -> no snapshot
        snapshot = None

    # Authenticated read-only exchange-side duplicate detection by the fixed
    # orderLinkId is only attempted with real network + usable credentials.
    # Offline / no-network / no-credential preflight fails closed and never
    # claims the authenticated checks completed.
    if not allow_real_network:
        duplicate_check = offline_duplicate_check(
            "authenticated exchange duplicate checks not performed "
            "(--allow-real-network not set)")
    elif not credentials.usable:
        duplicate_check = offline_duplicate_check(
            "authenticated exchange duplicate checks not performed "
            "(Demo credentials absent)")
    else:
        duplicate_check = perform_duplicate_check(probe, order_link_id)

    if execution_flags is None and mode == "preflight":
        execution_flags = {"mode": REQUIRED_EXECUTE_MODE, REQUIRED_EXECUTE_FLAG: True}

    gates = evaluate_preflight_gates(
        request_body=body,
        order_link_id=order_link_id,
        authorization_marker=authorization_marker,
        expected_commit=expected_commit,
        actual_commit=actual_commit,
        credentials=credentials,
        snapshot=snapshot,
        journal_state=journal_state,
        execution_flags=execution_flags,
        expected_body_hash=expected_body_hash,
        real_order_count_before=real_order_count_before,
        duplicate_check=duplicate_check,
        base_url=base_url,
    )
    all_passed = all(g.passed for g in gates)
    return PreflightReport(
        task_id=TASK_ID,
        mode=mode,
        generated_at_utc=_utc_timestamp(clock),
        expected_commit=expected_commit or "",
        actual_commit=actual_commit or "",
        authorization_marker_matches=authorization_marker == AUTHORIZATION_MARKER,
        order_link_id=order_link_id,
        request_body=body,
        request_body_hash=computed_hash,
        journal_state=journal_state,
        credentials_source=credentials.source,
        gates=tuple(gates),
        all_passed=all_passed,
        ready=all_passed,
        duplicate_check=duplicate_check.to_dict(),
    )


# ---------------------------------------------------------------------------
# Crash-safe one-shot journal
# ---------------------------------------------------------------------------


class OneShotJournal:
    """Durable, atomic, single-order journal stored outside source control."""

    def __init__(self, journal_dir: str) -> None:
        self.dir = journal_dir
        self.path = os.path.join(journal_dir, JOURNAL_FILENAME)

    def read(self) -> dict[str, Any] | None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, OSError):
            # A present-but-unreadable journal is treated as a hard conflict.
            return {"state": "UNREADABLE"}

    def state(self) -> str:
        data = self.read()
        if data is None:
            return JOURNAL_STATE_NONE
        return str(data.get("state", "UNREADABLE"))

    def exists(self) -> bool:
        return os.path.exists(self.path)

    def _atomic_write(self, data: Mapping[str, Any]) -> None:
        os.makedirs(self.dir, exist_ok=True)
        tmp = self.path + ".tmp"
        with open(tmp, "w", encoding="utf-8") as fh:
            json.dump(dict(data), fh, indent=2, sort_keys=True)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, self.path)

    def arm(
        self,
        *,
        body_hash_value: str,
        order_link_id: str,
        expected_commit: str,
        preflight_summary: Mapping[str, Any],
        clock: Any | None = None,
    ) -> dict[str, Any]:
        """Transition to ARMED_BEFORE_POST. Refuses if any journal exists."""
        if self.exists():
            raise JournalStateConflict(
                f"journal already exists at {self.path!r} (state={self.state()!r}); "
                f"investigate by orderLinkId before any resubmission"
            )
        record = {
            "task_id": TASK_ID,
            "state": JOURNAL_STATE_ARMED_BEFORE_POST,
            "armed_at_utc": _utc_timestamp(clock),
            "order_link_id": order_link_id,
            "request_body_hash": body_hash_value,
            "expected_commit": expected_commit,
            "preflight_summary": dict(preflight_summary),
            "history": [
                {"state": JOURNAL_STATE_ARMED_BEFORE_POST, "at_utc": _utc_timestamp(clock)}
            ],
        }
        self._atomic_write(record)
        return record

    def transition(self, new_state: str, *, clock: Any | None = None, **extra: Any) -> dict[str, Any]:
        data = self.read() or {"task_id": TASK_ID, "history": []}
        data["state"] = new_state
        data["updated_at_utc"] = _utc_timestamp(clock)
        history = list(data.get("history", []))
        history.append({"state": new_state, "at_utc": _utc_timestamp(clock)})
        data["history"] = history
        for k, v in extra.items():
            data[k] = v
        self._atomic_write(data)
        return data


def canonical_journal() -> "OneShotJournal":
    """Return the one-shot journal anchored to the CANONICAL, non-overridable
    repository-root path. Production code (CLI preflight and execute_once) must
    obtain its journal ONLY through this factory so the location can never be
    redirected by a CLI argument, environment variable, config file, or the
    current working directory.

    The resolved path is verified to live under the repository root; a
    resolved path escaping the root (e.g. via a symlinked outputs/ directory)
    is rejected.
    """
    resolved = CANONICAL_JOURNAL_DIR.resolve()
    root = PROJECT_ROOT.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:  # path traversal / symlink escape
        raise SingleRealDemoOrderError(
            f"canonical journal path {resolved!r} escapes repository root {root!r}"
        ) from exc
    return OneShotJournal(str(CANONICAL_JOURNAL_DIR))


# ---------------------------------------------------------------------------
# One-shot sender guard (in-process call-count enforcement)
# ---------------------------------------------------------------------------


class OneShotSenderGuard:
    """Wraps a transport so order-create may be invoked at most once.

    A second invocation raises ``SenderInvokedTwice`` -- a hard safety error.
    There is intentionally no loop, no retry, no fallback around the POST.
    """

    def __init__(self, transport: Any) -> None:
        self._transport = transport
        self.call_count = 0

    def send_order_create(self, *, url: str, headers: Mapping[str, str], body_bytes: bytes) -> dict[str, Any]:
        if self.call_count >= MAX_ORDER_CREATE_CALLS:
            raise SenderInvokedTwice(
                f"order-create sender already invoked {self.call_count} time(s); "
                f"a second send is forbidden"
            )
        assert_demo_url(url)
        self.call_count += 1
        return self._transport.post_order_create(url=url, headers=dict(headers), body_bytes=body_bytes)


# ---------------------------------------------------------------------------
# Real network transport (only constructed for the manual VPS execute)
# ---------------------------------------------------------------------------


class _NoRedirectHandler(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):  # type: ignore[override]
        raise RedirectRejected(f"redirect to {newurl!r} refused")


class RealDemoHttpTransport:
    """Real HTTP transport to api-demo.bybit.com ONLY. Rejects redirects.

    Holds the Demo secret privately for signing; the secret is never returned,
    printed, or serialized. Constructed only by the manual execute path.
    """

    def __init__(self, *, api_key: str, api_secret: str, recv_window: str) -> None:
        self._api_key = api_key
        self._api_secret = api_secret
        self._recv_window = recv_window or DEFAULT_RECV_WINDOW
        self._opener = urllib.request.build_opener(_NoRedirectHandler())

    def _sign(self, payload: str) -> dict[str, str]:
        timestamp = str(int(time.time() * 1000))
        sign_input = timestamp + self._api_key + self._recv_window + payload
        signature = hmac.new(
            self._api_secret.encode("utf-8"),
            sign_input.encode("utf-8"),
            hashlib.sha256,
        ).hexdigest()
        return {
            "X-BAPI-API-KEY": self._api_key,
            "X-BAPI-SIGN": signature,
            "X-BAPI-TIMESTAMP": timestamp,
            "X-BAPI-RECV-WINDOW": self._recv_window,
        }

    def signed_headers_for_post(self, body_str: str) -> dict[str, str]:
        headers = {"Content-Type": "application/json"}
        headers.update(self._sign(body_str))
        return headers

    def post_order_create(self, *, url: str, headers: Mapping[str, str], body_bytes: bytes) -> dict[str, Any]:
        assert_demo_url(url)
        req = urllib.request.Request(url, data=body_bytes, headers=dict(headers), method="POST")
        try:
            with self._opener.open(req, timeout=10) as resp:
                final_host = host_of(resp.geturl())
                if final_host != DEMO_HOST:
                    raise RedirectRejected(f"response host {final_host!r} != {DEMO_HOST!r}")
                raw = resp.read().decode("utf-8")
        except RedirectRejected:
            raise
        except urllib.error.URLError as exc:
            reason = getattr(exc, "reason", exc)
            if isinstance(reason, TimeoutError) or "timed out" in str(reason).lower():
                raise TransportTimeout(str(reason)) from exc
            raise TransportConnectionError(str(reason)) from exc
        except TimeoutError as exc:
            raise TransportTimeout(str(exc)) from exc
        try:
            return json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SingleRealDemoOrderError(f"malformed response: {exc}") from exc


# ---------------------------------------------------------------------------
# Read-only verification
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class VerificationResult:
    order_id: str
    order_link_id: str
    ret_code: int
    ret_msg: str
    final_order_status: str
    cum_exec_qty: str
    avg_price: str
    exec_fee: str
    position_size_after: str
    verification_source: str
    final_state_verified: bool
    outcome_ambiguous: bool
    realtime_reads: int
    history_reads: int
    execution_reads: int
    position_reads: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "order_id": self.order_id,
            "order_link_id": self.order_link_id,
            "ret_code": self.ret_code,
            "ret_msg": self.ret_msg,
            "final_order_status": self.final_order_status,
            "cum_exec_qty": self.cum_exec_qty,
            "avg_price": self.avg_price,
            "exec_fee": self.exec_fee,
            "position_size_after": self.position_size_after,
            "verification_source": self.verification_source,
            "final_state_verified": self.final_state_verified,
            "outcome_ambiguous": self.outcome_ambiguous,
            "realtime_reads": self.realtime_reads,
            "history_reads": self.history_reads,
            "execution_reads": self.execution_reads,
            "position_reads": self.position_reads,
        }


_TERMINAL_STATUSES = {"Filled", "PartiallyFilledCanceled", "Cancelled", "Rejected", "Deactivated"}


def _extract_first_order(resp: Mapping[str, Any], *, order_id: str, order_link_id: str) -> dict[str, Any] | None:
    try:
        items = (resp.get("result", {}) or {}).get("list", []) or []
    except AttributeError:
        return None
    for item in items:
        if order_id and str(item.get("orderId", "")) == order_id:
            return item
        if order_link_id and str(item.get("orderLinkId", "")) == order_link_id:
            return item
    if items:
        return items[0]
    return None


def verify_order_outcome(
    *,
    probe: Any,
    order_id: str,
    order_link_id: str,
    ret_code: int,
    ret_msg: str,
    clock: Any | None = None,
) -> VerificationResult:
    """Read-only verification. Performs NO order POST. Bounded polling only."""
    clk = clock or _RealClock()
    realtime_reads = 0
    history_reads = 0
    execution_reads = 0
    position_reads = 0

    found: dict[str, Any] | None = None
    source = "none"

    # Bounded /v5/order/realtime polling (no retry of the POST).
    for attempt in range(MAX_REALTIME_READS):
        if realtime_reads >= MAX_REALTIME_READS:
            break
        resp = probe.read_order_realtime(order_id=order_id, order_link_id=order_link_id)
        realtime_reads += 1
        candidate = _extract_first_order(resp, order_id=order_id, order_link_id=order_link_id)
        if candidate is not None:
            found = candidate
            source = "order_realtime"
            status = str(candidate.get("orderStatus", ""))
            if status in _TERMINAL_STATUSES:
                break
        if attempt < MAX_REALTIME_READS - 1:
            clk.sleep(VERIFICATION_POLL_DELAY_SECONDS)

    # One /v5/order/history fallback if realtime did not resolve.
    if found is None or str(found.get("orderStatus", "")) not in _TERMINAL_STATUSES:
        if history_reads < MAX_HISTORY_READS:
            resp = probe.read_order_history(order_id=order_id, order_link_id=order_link_id)
            history_reads += 1
            candidate = _extract_first_order(resp, order_id=order_id, order_link_id=order_link_id)
            if candidate is not None:
                found = candidate
                source = "order_history"

    cum_exec_qty = "0"
    avg_price = ""
    exec_fee = ""
    final_status = ""
    if found is not None:
        final_status = str(found.get("orderStatus", ""))
        cum_exec_qty = str(found.get("cumExecQty", found.get("cumExecValue", "0")) or "0")
        avg_price = str(found.get("avgPrice", "") or "")
        exec_fee = str(found.get("cumExecFee", "") or "")

    # One /v5/execution/list query for fee / fill detail.
    if execution_reads < MAX_EXECUTION_READS:
        try:
            resp = probe.read_execution_list(order_id=order_id, order_link_id=order_link_id)
            execution_reads += 1
            exec_items = (resp.get("result", {}) or {}).get("list", []) or []
            if exec_items:
                fee_total = Decimal("0")
                for it in exec_items:
                    try:
                        fee_total += Decimal(str(it.get("execFee", "0") or "0"))
                    except (InvalidOperation, TypeError):
                        pass
                if exec_fee == "":
                    exec_fee = format(fee_total, "f")
        except Exception:
            pass

    # One /v5/position/list query for resulting position size.
    position_size_after = ""
    if position_reads < MAX_POSITION_READS:
        try:
            resp = probe.read_position_list(symbol=REQUIRED_SYMBOL)
            position_reads += 1
            pos_items = (resp.get("result", {}) or {}).get("list", []) or []
            for it in pos_items:
                if str(it.get("symbol", "")) == REQUIRED_SYMBOL:
                    position_size_after = str(it.get("size", "") or "")
                    break
        except Exception:
            pass

    verified = final_status in _TERMINAL_STATUSES or final_status == "New"
    ambiguous = found is None

    return VerificationResult(
        order_id=order_id,
        order_link_id=order_link_id,
        ret_code=ret_code,
        ret_msg=ret_msg,
        final_order_status=final_status,
        cum_exec_qty=cum_exec_qty,
        avg_price=avg_price,
        exec_fee=exec_fee,
        position_size_after=position_size_after,
        verification_source=source,
        final_state_verified=verified and not ambiguous,
        outcome_ambiguous=ambiguous,
        realtime_reads=realtime_reads,
        history_reads=history_reads,
        execution_reads=execution_reads,
        position_reads=position_reads,
    )


def classify_outcome(verification: VerificationResult) -> str:
    """Map a verification result to a final conclusion."""
    status = verification.final_order_status
    if verification.outcome_ambiguous:
        return OUTCOME_AMBIGUOUS
    if status == "Filled":
        return OUTCOME_FILLED_VERIFIED
    if status in ("PartiallyFilledCanceled",):
        return OUTCOME_PARTIALLY_FILLED_VERIFIED
    if status in ("PartiallyFilled",):
        # An IOC partially filled then resting is unusual; treat as partial.
        return OUTCOME_PARTIALLY_FILLED_VERIFIED
    if status in ("Cancelled", "Deactivated"):
        return OUTCOME_CANCELLED_VERIFIED
    if status == "Rejected":
        return OUTCOME_REJECTED_VERIFIED
    if status in ("New", "Untriggered", "Triggered", "Created"):
        return OUTCOME_ACCEPTED_STATUS_PENDING
    return OUTCOME_AMBIGUOUS


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class SingleRealDemoOrderReport:
    task_id: str
    generated_at_utc: str
    mode: str
    expected_commit: str
    actual_commit: str
    order_link_id: str
    request_body: Mapping[str, Any]
    request_body_hash: str
    preflight_all_passed: bool
    preflight_failed_gate_names: tuple[str, ...]
    journal_state: str
    sender_call_count: int
    order_post_attempted: bool
    post_ret_code: int
    post_ret_msg: str
    order_id: str
    final_outcome: str
    verification: Mapping[str, Any] | None
    position_left_open_warning: str
    real_order_sent: bool
    outcome_ambiguous: bool
    no_retry_performed: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "generated_at_utc": self.generated_at_utc,
            "mode": self.mode,
            "expected_commit": self.expected_commit,
            "actual_commit": self.actual_commit,
            "order_link_id": self.order_link_id,
            "request_body": dict(self.request_body),
            "request_body_hash": self.request_body_hash,
            "preflight_all_passed": self.preflight_all_passed,
            "preflight_failed_gate_names": list(self.preflight_failed_gate_names),
            "journal_state": self.journal_state,
            "sender_call_count": self.sender_call_count,
            "order_post_attempted": self.order_post_attempted,
            "post_ret_code": self.post_ret_code,
            "post_ret_msg": self.post_ret_msg,
            "order_id": self.order_id,
            "final_outcome": self.final_outcome,
            "verification": dict(self.verification) if self.verification else None,
            "position_left_open_warning": self.position_left_open_warning,
            "real_order_sent": self.real_order_sent,
            "outcome_ambiguous": self.outcome_ambiguous,
            "no_retry_performed": self.no_retry_performed,
        }


POSITION_OPEN_WARNING = (
    "WARNING: this authorized order is an OPENING Buy (reduceOnly=false). If "
    "filled it leaves a SOLUSDT Demo LONG position open. This module never "
    "submits a close, never sets TP/SL, and never reduces. Closing the "
    "position requires a SEPARATE explicit authorization."
)


# ---------------------------------------------------------------------------
# Execute-once orchestration
# ---------------------------------------------------------------------------


def execute_single_real_demo_order(
    *,
    probe: Any,
    sender: OneShotSenderGuard,
    transport: Any,
    credentials: DemoCredentials,
    journal: OneShotJournal,
    expected_commit: str,
    actual_commit: str,
    authorization_marker: str | None,
    execution_flags: Mapping[str, Any],
    expected_body_hash: str,
    real_order_count_before: int = 0,
    clock: Any | None = None,
    base_url: str = DEMO_BASE_URL,
) -> SingleRealDemoOrderReport:
    """Fully-gated one-shot real Demo order execution.

    Re-runs every preflight gate, arms the durable journal, then invokes the
    one-shot sender EXACTLY once, then performs read-only verification. There
    is no retry, no loop, and no fallback around the single POST.
    """
    ts = _utc_timestamp(clock)
    order_link_id = build_order_link_id()
    body = build_approved_body(order_link_id=order_link_id)
    computed_hash = body_hash(body)

    def _refused(failed_names: Sequence[str], journal_state: str) -> SingleRealDemoOrderReport:
        return SingleRealDemoOrderReport(
            task_id=TASK_ID,
            generated_at_utc=ts,
            mode="execute_once",
            expected_commit=expected_commit,
            actual_commit=actual_commit,
            order_link_id=order_link_id,
            request_body=body,
            request_body_hash=computed_hash,
            preflight_all_passed=False,
            preflight_failed_gate_names=tuple(failed_names),
            journal_state=journal_state,
            sender_call_count=sender.call_count,
            order_post_attempted=False,
            post_ret_code=0,
            post_ret_msg="",
            order_id="",
            final_outcome=OUTCOME_REFUSED_PREFLIGHT,
            verification=None,
            position_left_open_warning=POSITION_OPEN_WARNING,
            real_order_sent=False,
            outcome_ambiguous=False,
            no_retry_performed=True,
        )

    # Read snapshot (read-only).
    try:
        snapshot = probe.build_account_snapshot()
    except Exception:
        snapshot = None

    journal_state = journal.state()

    # Authenticated read-only exchange-side duplicate detection by the fixed
    # orderLinkId, BEFORE any POST. Any query failure fails closed.
    duplicate_check = perform_duplicate_check(probe, order_link_id)

    gates = evaluate_preflight_gates(
        request_body=body,
        order_link_id=order_link_id,
        authorization_marker=authorization_marker,
        expected_commit=expected_commit,
        actual_commit=actual_commit,
        credentials=credentials,
        snapshot=snapshot,
        journal_state=journal_state,
        execution_flags=execution_flags,
        expected_body_hash=expected_body_hash,
        real_order_count_before=real_order_count_before,
        duplicate_check=duplicate_check,
        base_url=base_url,
    )
    failed = [g.name for g in gates if not g.passed]
    if failed:
        return _refused(failed, journal_state)

    # Arm the durable journal BEFORE any POST. Refuses if a journal exists.
    try:
        journal.arm(
            body_hash_value=computed_hash,
            order_link_id=order_link_id,
            expected_commit=expected_commit,
            preflight_summary={"all_passed": True, "gate_count": len(gates)},
            clock=clock,
        )
    except JournalStateConflict:
        return _refused(["no_conflicting_one_shot_journal"], journal.state())

    # Build signed headers + body bytes. The signature is computed inside the
    # transport and is never returned or stored.
    body_str = canonical_body_json(body)
    body_bytes = body_str.encode("utf-8")
    headers = transport.signed_headers_for_post(body_str)
    url = base_url + ORDER_CREATE_PATH

    post_attempted = True
    ret_code = -1
    ret_msg = ""
    order_id = ""
    response: dict[str, Any] | None = None

    try:
        response = sender.send_order_create(url=url, headers=headers, body_bytes=body_bytes)
    except RedirectRejected as exc:
        journal.transition(JOURNAL_STATE_POST_REDIRECT_REJECTED, clock=clock, detail=str(exc))
        return _ambiguous_or_failed(
            ts, expected_commit, actual_commit, order_link_id, body, computed_hash,
            journal.state(), sender.call_count, OUTCOME_POST_FAILED, str(exc),
            real_order_sent=False,
        )
    except TransportTimeout as exc:
        journal.transition(JOURNAL_STATE_POST_TIMEOUT_AMBIGUOUS, clock=clock, detail=str(exc))
        return _ambiguous_or_failed(
            ts, expected_commit, actual_commit, order_link_id, body, computed_hash,
            journal.state(), sender.call_count, OUTCOME_AMBIGUOUS, str(exc),
            real_order_sent=True, ambiguous=True,
        )
    except TransportConnectionError as exc:
        journal.transition(JOURNAL_STATE_POST_EXCEPTION_AMBIGUOUS, clock=clock, detail=str(exc))
        return _ambiguous_or_failed(
            ts, expected_commit, actual_commit, order_link_id, body, computed_hash,
            journal.state(), sender.call_count, OUTCOME_AMBIGUOUS, str(exc),
            real_order_sent=True, ambiguous=True,
        )
    except SingleRealDemoOrderError as exc:
        # Malformed response or other ambiguous transport-level failure.
        journal.transition(JOURNAL_STATE_POST_RESULT_UNVERIFIED, clock=clock, detail=str(exc))
        return _ambiguous_or_failed(
            ts, expected_commit, actual_commit, order_link_id, body, computed_hash,
            journal.state(), sender.call_count, OUTCOME_AMBIGUOUS, str(exc),
            real_order_sent=True, ambiguous=True,
        )

    # Response received.
    ret_code = int(response.get("retCode", -1))
    ret_msg = str(response.get("retMsg", ""))
    order_id = str((response.get("result", {}) or {}).get("orderId", ""))
    journal.transition(
        JOURNAL_STATE_POST_RESPONSE_RECEIVED,
        clock=clock,
        ret_code=ret_code,
        order_id=order_id,
    )

    if ret_code != 0:
        # The create call itself failed; no retry.
        journal.transition(JOURNAL_STATE_POST_RESULT_VERIFIED, clock=clock, conclusion=OUTCOME_POST_FAILED)
        return SingleRealDemoOrderReport(
            task_id=TASK_ID,
            generated_at_utc=ts,
            mode="execute_once",
            expected_commit=expected_commit,
            actual_commit=actual_commit,
            order_link_id=order_link_id,
            request_body=body,
            request_body_hash=computed_hash,
            preflight_all_passed=True,
            preflight_failed_gate_names=(),
            journal_state=journal.state(),
            sender_call_count=sender.call_count,
            order_post_attempted=True,
            post_ret_code=ret_code,
            post_ret_msg=ret_msg,
            order_id=order_id,
            final_outcome=OUTCOME_POST_FAILED,
            verification=None,
            position_left_open_warning=POSITION_OPEN_WARNING,
            real_order_sent=False,
            outcome_ambiguous=False,
            no_retry_performed=True,
        )

    # retCode==0: read-only verification only (never another POST).
    verification = verify_order_outcome(
        probe=probe,
        order_id=order_id,
        order_link_id=order_link_id,
        ret_code=ret_code,
        ret_msg=ret_msg,
        clock=clock,
    )
    outcome = classify_outcome(verification)
    final_state = (
        JOURNAL_STATE_POST_RESULT_VERIFIED
        if verification.final_state_verified
        else JOURNAL_STATE_POST_RESULT_UNVERIFIED
    )
    journal.transition(final_state, clock=clock, conclusion=outcome, order_id=order_id)

    real_sent = outcome in (
        OUTCOME_FILLED_VERIFIED,
        OUTCOME_PARTIALLY_FILLED_VERIFIED,
        OUTCOME_CANCELLED_VERIFIED,
        OUTCOME_REJECTED_VERIFIED,
        OUTCOME_ACCEPTED_STATUS_PENDING,
    )

    return SingleRealDemoOrderReport(
        task_id=TASK_ID,
        generated_at_utc=ts,
        mode="execute_once",
        expected_commit=expected_commit,
        actual_commit=actual_commit,
        order_link_id=order_link_id,
        request_body=body,
        request_body_hash=computed_hash,
        preflight_all_passed=True,
        preflight_failed_gate_names=(),
        journal_state=journal.state(),
        sender_call_count=sender.call_count,
        order_post_attempted=True,
        post_ret_code=ret_code,
        post_ret_msg=ret_msg,
        order_id=order_id,
        final_outcome=outcome,
        verification=verification.to_dict(),
        position_left_open_warning=POSITION_OPEN_WARNING,
        real_order_sent=real_sent,
        outcome_ambiguous=verification.outcome_ambiguous,
        no_retry_performed=True,
    )


def _ambiguous_or_failed(
    ts: str,
    expected_commit: str,
    actual_commit: str,
    order_link_id: str,
    body: Mapping[str, Any],
    computed_hash: str,
    journal_state: str,
    sender_call_count: int,
    outcome: str,
    detail: str,
    *,
    real_order_sent: bool,
    ambiguous: bool = False,
) -> SingleRealDemoOrderReport:
    return SingleRealDemoOrderReport(
        task_id=TASK_ID,
        generated_at_utc=ts,
        mode="execute_once",
        expected_commit=expected_commit,
        actual_commit=actual_commit,
        order_link_id=order_link_id,
        request_body=body,
        request_body_hash=computed_hash,
        preflight_all_passed=True,
        preflight_failed_gate_names=(),
        journal_state=journal_state,
        sender_call_count=sender_call_count,
        order_post_attempted=True,
        post_ret_code=-1,
        post_ret_msg=detail,
        order_id="",
        final_outcome=outcome,
        verification=None,
        position_left_open_warning=POSITION_OPEN_WARNING,
        real_order_sent=real_order_sent,
        outcome_ambiguous=ambiguous,
        no_retry_performed=True,
    )


# ---------------------------------------------------------------------------
# Identity / description
# ---------------------------------------------------------------------------


def describe_authorization() -> dict[str, Any]:
    """Return a sanitized description of the immutable authorized scope."""
    return {
        "task_id": TASK_ID,
        "identity": IDENTITY,
        "authorization_marker": AUTHORIZATION_MARKER,
        "authorization_quote": AUTHORIZATION_QUOTE,
        "environment": "bybit_demo",
        "base_url": DEMO_BASE_URL,
        "order_create_path": ORDER_CREATE_PATH,
        "category": REQUIRED_CATEGORY,
        "symbol": REQUIRED_SYMBOL,
        "side": REQUIRED_SIDE,
        "order_type": REQUIRED_ORDER_TYPE,
        "qty": REQUIRED_QTY_STR,
        "time_in_force": REQUIRED_TIME_IN_FORCE,
        "reduce_only": REQUIRED_REDUCE_ONLY,
        "close_on_trigger": REQUIRED_CLOSE_ON_TRIGGER,
        "approved_body_fields": list(APPROVED_BODY_FIELDS),
        "max_order_create_calls": MAX_ORDER_CREATE_CALLS,
        "max_orders_submitted": MAX_ORDERS_SUBMITTED,
        "retry_enabled": RETRY_ENABLED,
        "scheduler_enabled": SCHEDULER_ENABLED,
        "max_notional_usdt": format(MAX_NOTIONAL_USDT, "f"),
        "forbidden_hosts": sorted(FORBIDDEN_HOSTS),
        "position_open_warning": POSITION_OPEN_WARNING,
    }


__all__ = [
    "AUTHORIZATION_MARKER",
    "AUTHORIZATION_QUOTE",
    "AUTHORIZATION_SCOPE_IDENTITY",
    "APPROVED_BODY_FIELDS",
    "AccountSnapshot",
    "BLOCKING_JOURNAL_STATES",
    "CANONICAL_JOURNAL_DIR",
    "CredentialsMissing",
    "DEMO_BASE_URL",
    "DEMO_HOST",
    "DemoCredentials",
    "DuplicateCheckResult",
    "EndpointLockViolation",
    "FORBIDDEN_HOSTS",
    "GateResult",
    "IDENTITY",
    "JOURNAL_STATE_ARMED_BEFORE_POST",
    "JOURNAL_STATE_NONE",
    "JOURNAL_STATE_POST_EXCEPTION_AMBIGUOUS",
    "JOURNAL_STATE_POST_REDIRECT_REJECTED",
    "JOURNAL_STATE_POST_REJECTED_BEFORE_NETWORK",
    "JOURNAL_STATE_POST_RESPONSE_RECEIVED",
    "JOURNAL_STATE_POST_RESULT_UNVERIFIED",
    "JOURNAL_STATE_POST_RESULT_VERIFIED",
    "JOURNAL_STATE_POST_TIMEOUT_AMBIGUOUS",
    "JournalStateConflict",
    "MAX_NOTIONAL_USDT",
    "MAX_ORDER_CREATE_CALLS",
    "ORDER_CREATE_PATH",
    "ORDER_LINK_ID_PREFIX",
    "OUTCOME_ACCEPTED_STATUS_PENDING",
    "OUTCOME_AMBIGUOUS",
    "OUTCOME_CANCELLED_VERIFIED",
    "OUTCOME_FILLED_VERIFIED",
    "OUTCOME_PARTIALLY_FILLED_VERIFIED",
    "OUTCOME_POST_FAILED",
    "OUTCOME_REFUSED_PREFLIGHT",
    "OUTCOME_REJECTED_VERIFIED",
    "OneShotJournal",
    "OneShotSenderGuard",
    "PROJECT_ROOT",
    "POSITION_OPEN_WARNING",
    "PROTECTED_SYMBOLS",
    "PreflightReport",
    "REQUIRED_QTY",
    "REQUIRED_QTY_STR",
    "RealDemoHttpTransport",
    "RedirectRejected",
    "SenderInvokedTwice",
    "SingleRealDemoOrderError",
    "SingleRealDemoOrderReport",
    "TASK_ID",
    "TransportConnectionError",
    "TransportTimeout",
    "VerificationResult",
    "assert_demo_url",
    "body_hash",
    "build_approved_body",
    "build_order_link_id",
    "canonical_body_json",
    "canonical_journal",
    "classify_outcome",
    "describe_authorization",
    "evaluate_preflight_gates",
    "execute_single_real_demo_order",
    "host_of",
    "is_full_commit_sha",
    "load_demo_credentials",
    "offline_duplicate_check",
    "perform_duplicate_check",
    "run_preflight",
    "verify_order_outcome",
]
