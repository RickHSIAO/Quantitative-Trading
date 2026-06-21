"""TASK-014BP -- demo-only single reduce-only close of the TASK-014BO long.

This module implements ONE manually-triggered, fail-closed reduce-only close
for the single Bybit Demo position that Rick has explicitly authorized closing:

    Bybit Demo only / https://api-demo.bybit.com / POST /v5/order/create
    category=linear symbol=SOLUSDT side=Sell orderType=Market qty="0.1"
    timeInForce=IOC reduceOnly=true closeOnTrigger=false
    maximum order-create POST calls = 1, maximum close orders submitted = 1,
    automatic retry forbidden, no reversal / no short opening.

Exact human authorization (recorded verbatim):
    "我授權關閉目前 TASK-014BO 建立的 Bybit Demo SOLUSDT 0.1 多單，只允許一筆
     reduceOnly Market 平倉單，不得反向開倉、不得超過目前持倉、不得自動重試。"

The position being closed is the verified-filled TASK-014BO opening order:
    source order id      : 77173918-71f6-4829-91c9-025bd8cd76fa
    source orderLinkId   : BO1-4696d511edf11b50
    source result        : DEMO_ORDER_FILLED_VERIFIED
    expected position    : SOLUSDT Buy 0.1

CRITICAL: importing this module, running its tests, running CLI help, the
default/offline preflight, generating reports, or VPS validation NEVER sends
an order. The single reduce-only close may only be sent by a deliberate,
fully-gated ``execute_once`` invocation run manually on the VPS.

This is a SEPARATE narrow module. It reuses (without modifying or weakening)
the proven TASK-014BO opening module for host lock, redirect rejection,
signing/transport, full-SHA gate, duplicate detection, the one-shot sender
guard, and sanitized patterns. It does not import or use BybitExecutor /
main / src.risk and does not change Stage 1 defaults.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from src import demo_only_tiny_execution_adapter_single_real_demo_order as bo

# Re-exported / reused primitives (imported, never modified):
from src.demo_only_tiny_execution_adapter_single_real_demo_order import (  # noqa: F401
    DEMO_BASE_URL,
    DEMO_HOST,
    ORDER_CREATE_PATH,
    EP_ORDER_REALTIME,
    EP_ORDER_HISTORY,
    EP_EXECUTION_LIST,
    EP_POSITION_LIST,
    DemoCredentials,
    DuplicateCheckResult,
    EndpointLockViolation,
    GateResult,
    JournalStateConflict,
    OneShotSenderGuard,
    RealDemoHttpTransport,
    RedirectRejected,
    SenderInvokedTwice,
    SingleRealDemoOrderError,
    TransportConnectionError,
    TransportTimeout,
    assert_demo_url,
    body_hash,
    canonical_body_json,
    host_of,
    is_full_commit_sha,
    load_demo_credentials,
    offline_duplicate_check,
    perform_duplicate_check,
)


# ---------------------------------------------------------------------------
# Identity
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BP"
IDENTITY = "DEMO-ONLY-SINGLE-REDUCE-ONLY-CLOSE"
IS_REVIEW_CHAIN_SUFFIX = False

CLOSE_AUTHORIZATION_MARKER = (
    "DEMO_ONLY_CLOSE_TASK014BO_SOLUSDT_0_1_LONG_REDUCE_ONLY_MARKET_"
    "ONE_SHOT_RICK_AUTHORIZED_20260621"
)

AUTHORIZATION_QUOTE = (
    "我授權關閉目前 TASK-014BO 建立的 Bybit Demo SOLUSDT 0.1 多單，只允許一筆 "
    "reduceOnly Market 平倉單，不得反向開倉、不得超過目前持倉、不得自動重試。"
)


# ---------------------------------------------------------------------------
# Source TASK-014BO opening position that may be closed
# ---------------------------------------------------------------------------

SOURCE_TASK_ID = "TASK-014BO"
SOURCE_ORDER_ID = "77173918-71f6-4829-91c9-025bd8cd76fa"
SOURCE_ORDER_LINK_ID = "BO1-4696d511edf11b50"
SOURCE_RESULT = "DEMO_ORDER_FILLED_VERIFIED"
SOURCE_REQUIRED_JOURNAL_STATE = bo.JOURNAL_STATE_POST_RESULT_VERIFIED  # POST_RESULT_VERIFIED
EXPECTED_POSITION_SIDE = "Buy"
EXPECTED_POSITION_SIZE = Decimal("0.1")


# ---------------------------------------------------------------------------
# Immutable approved close-order contract
# ---------------------------------------------------------------------------

REQUIRED_CATEGORY = "linear"
REQUIRED_SYMBOL = "SOLUSDT"
REQUIRED_SIDE = "Sell"
REQUIRED_ORDER_TYPE = "Market"
REQUIRED_QTY = Decimal("0.1")
REQUIRED_QTY_STR = "0.1"
REQUIRED_TIME_IN_FORCE = "IOC"
REQUIRED_REDUCE_ONLY = True
REQUIRED_CLOSE_ON_TRIGGER = False

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
MAX_CLOSE_ORDERS_SUBMITTED = 1
RETRY_ENABLED = False
SCHEDULER_ENABLED = False
QTY_ADJUSTMENT_ALLOWED = False

PROTECTED_SYMBOLS = bo.PROTECTED_SYMBOLS

# Credential env names (Demo only; live/testnet aliases never read).
ENV_DEMO_API_KEY = bo.ENV_DEMO_API_KEY
ENV_DEMO_API_SECRET = bo.ENV_DEMO_API_SECRET
ENV_DEMO_RECV_WINDOW = bo.ENV_DEMO_RECV_WINDOW

REQUIRED_EXECUTE_MODE = "execute_once"
REQUIRED_EXECUTE_FLAG = "execute_one_reduce_only_close"


# ---------------------------------------------------------------------------
# Permanent close orderLinkId (commit/date/time independent)
# ---------------------------------------------------------------------------

ORDER_LINK_ID_PREFIX = "BC1-"
ORDER_LINK_ID_MAX_LEN = 36

# Immutable description of the authorized CLOSE scope. The permanent close
# orderLinkId is derived ONLY from this plus TASK_ID and the close marker, so
# it never changes across commits, dates, processes, or hosts.
CLOSE_AUTHORIZATION_SCOPE_IDENTITY = (
    "TASK-014BP|BYBIT_DEMO|linear|SOLUSDT|Sell|Market|0.1|IOC|"
    "reduceOnly=true|closeOnTrigger=false|"
    f"source_order_id={SOURCE_ORDER_ID}|"
    f"source_order_link_id={SOURCE_ORDER_LINK_ID}|"
    "max_order_create_post=1"
)


def build_close_order_link_id() -> str:
    """Permanently STABLE close orderLinkId for THIS close authorization.

    Derived ONLY from ``TASK_ID | CLOSE_AUTHORIZATION_MARKER |
    CLOSE_AUTHORIZATION_SCOPE_IDENTITY``. Contains NO commit SHA, date, time,
    UUID, randomness, PID, or hostname; not caller-overridable; <=36 chars.
    Identical across commits, dates, and process restarts.
    """
    digest = hashlib.sha256(
        (TASK_ID + "|" + CLOSE_AUTHORIZATION_MARKER + "|" + CLOSE_AUTHORIZATION_SCOPE_IDENTITY).encode("utf-8")
    ).hexdigest()[:16]
    link = f"{ORDER_LINK_ID_PREFIX}{digest}"
    return link[:ORDER_LINK_ID_MAX_LEN]


def build_close_body(*, order_link_id: str) -> dict[str, Any]:
    """Return the exact nine-field approved reduce-only close body."""
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


# ---------------------------------------------------------------------------
# Canonical close journal
# ---------------------------------------------------------------------------

PROJECT_ROOT = bo.PROJECT_ROOT
CLOSE_JOURNAL_FILENAME = "task_014bp_close_journal.json"
CANONICAL_CLOSE_JOURNAL_DIR = (
    PROJECT_ROOT / "outputs" / "demo_trading" / "task_014bp_single_reduce_only_close"
)
DEFAULT_CLOSE_JOURNAL_DIR = str(CANONICAL_CLOSE_JOURNAL_DIR)

CLOSE_STATE_NONE = "NONE"
CLOSE_STATE_ARMED_BEFORE_CLOSE_POST = "ARMED_BEFORE_CLOSE_POST"
CLOSE_POST_RESPONSE_RECEIVED = "CLOSE_POST_RESPONSE_RECEIVED"
CLOSE_POST_TIMEOUT_AMBIGUOUS = "CLOSE_POST_TIMEOUT_AMBIGUOUS"
CLOSE_POST_EXCEPTION_AMBIGUOUS = "CLOSE_POST_EXCEPTION_AMBIGUOUS"
CLOSE_POST_REJECTED_BEFORE_NETWORK = "CLOSE_POST_REJECTED_BEFORE_NETWORK"
CLOSE_RESULT_VERIFIED = "CLOSE_RESULT_VERIFIED"
CLOSE_RESULT_UNVERIFIED = "CLOSE_RESULT_UNVERIFIED"

BLOCKING_CLOSE_JOURNAL_STATES: frozenset[str] = frozenset(
    {
        CLOSE_STATE_ARMED_BEFORE_CLOSE_POST,
        CLOSE_POST_RESPONSE_RECEIVED,
        CLOSE_POST_TIMEOUT_AMBIGUOUS,
        CLOSE_POST_EXCEPTION_AMBIGUOUS,
        CLOSE_POST_REJECTED_BEFORE_NETWORK,
        CLOSE_RESULT_VERIFIED,
        CLOSE_RESULT_UNVERIFIED,
    }
)


class CloseOneShotJournal:
    """Durable, atomic, single-close journal stored outside source control."""

    def __init__(self, journal_dir: str) -> None:
        self.dir = journal_dir
        self.path = os.path.join(journal_dir, CLOSE_JOURNAL_FILENAME)

    def read(self) -> dict[str, Any] | None:
        try:
            with open(self.path, "r", encoding="utf-8") as fh:
                return json.load(fh)
        except FileNotFoundError:
            return None
        except (json.JSONDecodeError, OSError):
            return {"state": "UNREADABLE"}

    def state(self) -> str:
        data = self.read()
        if data is None:
            return CLOSE_STATE_NONE
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

    def arm_close(
        self,
        *,
        body_hash_value: str,
        order_link_id: str,
        expected_commit: str,
        preflight_summary: Mapping[str, Any],
        clock: Any | None = None,
    ) -> dict[str, Any]:
        if self.exists():
            raise bo.JournalStateConflict(
                f"close journal already exists at {self.path!r} (state={self.state()!r}); "
                f"investigate by orderLinkId before any resubmission"
            )
        ts = bo._utc_timestamp(clock)
        record = {
            "task_id": TASK_ID,
            "state": CLOSE_STATE_ARMED_BEFORE_CLOSE_POST,
            "armed_at_utc": ts,
            "order_link_id": order_link_id,
            "request_body_hash": body_hash_value,
            "expected_commit": expected_commit,
            "source_order_id": SOURCE_ORDER_ID,
            "source_order_link_id": SOURCE_ORDER_LINK_ID,
            "preflight_summary": dict(preflight_summary),
            "history": [{"state": CLOSE_STATE_ARMED_BEFORE_CLOSE_POST, "at_utc": ts}],
        }
        self._atomic_write(record)
        return record

    def transition(self, new_state: str, *, clock: Any | None = None, **extra: Any) -> dict[str, Any]:
        data = self.read() or {"task_id": TASK_ID, "history": []}
        ts = bo._utc_timestamp(clock)
        data["state"] = new_state
        data["updated_at_utc"] = ts
        history = list(data.get("history", []))
        history.append({"state": new_state, "at_utc": ts})
        data["history"] = history
        for k, v in extra.items():
            data[k] = v
        self._atomic_write(data)
        return data


def canonical_close_journal() -> CloseOneShotJournal:
    """Return the close journal anchored to the CANONICAL, non-overridable
    repository-root path. Production code obtains its journal ONLY here."""
    resolved = CANONICAL_CLOSE_JOURNAL_DIR.resolve()
    root = PROJECT_ROOT.resolve()
    try:
        resolved.relative_to(root)
    except ValueError as exc:
        raise SingleRealDemoOrderError(
            f"canonical close journal path {resolved!r} escapes repository root {root!r}"
        ) from exc
    return CloseOneShotJournal(str(CANONICAL_CLOSE_JOURNAL_DIR))


# ---------------------------------------------------------------------------
# Position snapshot (read-only inputs to close preflight gates)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClosePositionSnapshot:
    instrument_fresh: bool
    symbol_tradable: bool
    min_order_qty: Decimal | None
    qty_step: Decimal | None
    long_size: Decimal | None          # size of the SOLUSDT Buy position (None if absent)
    short_size: Decimal | None         # size of any SOLUSDT Sell position (None/0 if absent)
    long_row_count: int                # number of nonzero SOLUSDT long rows
    position_mode_one_way: bool
    ambiguous: bool                    # conflicting/unparseable SOLUSDT rows
    read_source: str


# ---------------------------------------------------------------------------
# Close preflight gates
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ClosePreflightReport:
    task_id: str
    mode: str
    generated_at_utc: str
    expected_commit: str
    actual_commit: str
    authorization_marker_matches: bool
    order_link_id: str
    request_body: Mapping[str, Any]
    request_body_hash: str
    close_journal_state: str
    credentials_source: str
    source_journal_summary: Mapping[str, Any] | None
    position_evidence: Mapping[str, Any] | None
    duplicate_check: Mapping[str, Any] | None
    gates: tuple[GateResult, ...]
    all_passed: bool
    ready: bool

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
            "close_journal_state": self.close_journal_state,
            "credentials_source": self.credentials_source,
            "source_journal_summary": dict(self.source_journal_summary) if self.source_journal_summary else None,
            "position_evidence": dict(self.position_evidence) if self.position_evidence else None,
            "duplicate_check": dict(self.duplicate_check) if self.duplicate_check else None,
            "gates": [
                {"index": g.index, "name": g.name, "passed": g.passed, "detail": g.detail}
                for g in self.gates
            ],
            "all_passed": self.all_passed,
            "ready": self.ready,
            "failed_gate_names": [g.name for g in self.failed_gates()],
        }


def _qty_satisfies_step(qty: Decimal, step: Decimal) -> bool:
    if step <= 0:
        return False
    ratio = qty / step
    return ratio == ratio.to_integral_value()


def _source_journal_ok(source_journal: Mapping[str, Any] | None) -> tuple[bool, bool, bool, bool, bool]:
    """Return (exists, state_ok, conclusion_ok, order_id_ok, link_ok)."""
    if not isinstance(source_journal, Mapping):
        return (False, False, False, False, False)
    exists = True
    state_ok = str(source_journal.get("state", "")) == SOURCE_REQUIRED_JOURNAL_STATE
    conclusion_ok = str(source_journal.get("conclusion", "")) == SOURCE_RESULT
    order_id_ok = str(source_journal.get("order_id", "")) == SOURCE_ORDER_ID
    link_ok = str(source_journal.get("order_link_id", "")) == SOURCE_ORDER_LINK_ID
    return (exists, state_ok, conclusion_ok, order_id_ok, link_ok)


def evaluate_close_preflight_gates(
    *,
    request_body: Mapping[str, Any],
    order_link_id: str,
    authorization_marker: str | None,
    expected_commit: str | None,
    actual_commit: str | None,
    credentials: DemoCredentials,
    snapshot: ClosePositionSnapshot | None,
    source_journal: Mapping[str, Any] | None,
    journal_state: str,
    execution_flags: Mapping[str, Any] | None,
    expected_body_hash: str | None,
    duplicate_check: DuplicateCheckResult | None,
    real_order_count_before: int,
    base_url: str = DEMO_BASE_URL,
) -> list[GateResult]:
    """Evaluate the fail-closed reduce-only close preflight gates. Pure; no I/O."""
    gates: list[GateResult] = []

    def add(index: int, name: str, passed: bool, detail: str = "") -> None:
        gates.append(GateResult(index=index, name=name, passed=bool(passed), detail=detail))

    body = dict(request_body)
    computed_hash = body_hash(body) if set(body) == set(APPROVED_BODY_FIELDS) else ""
    s_exists, s_state, s_concl, s_oid, s_link = _source_journal_ok(source_journal)

    # 1. Git / code identity -- exact 40-char lowercase hex SHA equal to HEAD.
    commit_ok = (
        is_full_commit_sha(expected_commit)
        and is_full_commit_sha(actual_commit)
        and expected_commit == actual_commit
    )
    add(1, "git_identity_matches_approved_full_sha", commit_ok,
        f"expected={expected_commit!r} actual={actual_commit!r}")

    # 2. Endpoint host lock.
    try:
        assert_demo_url(base_url + ORDER_CREATE_PATH)
        host_ok = host_of(base_url) == DEMO_HOST
    except EndpointLockViolation:
        host_ok = False
    add(2, "endpoint_host_is_api_demo_bybit_com", host_ok, f"base_url={base_url!r}")

    # 3. Credentials BYBIT_DEMO only.
    add(3, "credentials_are_bybit_demo_only",
        credentials.usable and credentials.source == "BYBIT_DEMO",
        f"source={credentials.source!r}")

    # 4. Exact close authorization marker.
    add(4, "close_authorization_marker_matches",
        authorization_marker == CLOSE_AUTHORIZATION_MARKER,
        "marker matches" if authorization_marker == CLOSE_AUTHORIZATION_MARKER else "marker mismatch/missing")

    # 5-9. Source TASK-014BO opening position evidence.
    add(5, "source_opening_journal_exists", s_exists)
    add(6, "source_journal_state_is_post_result_verified", s_state,
        f"required={SOURCE_REQUIRED_JOURNAL_STATE}")
    add(7, "source_conclusion_is_demo_order_filled_verified", s_concl,
        f"required={SOURCE_RESULT}")
    add(8, "source_order_id_matches", s_oid, f"required={SOURCE_ORDER_ID}")
    add(9, "source_order_link_id_matches", s_link, f"required={SOURCE_ORDER_LINK_ID}")

    # 10. Exactly one relevant SOLUSDT long position.
    one_long = bool(snapshot) and snapshot.long_size is not None and snapshot.long_row_count == 1
    add(10, "exactly_one_solusdt_long_position", one_long,
        f"long_size={getattr(snapshot, 'long_size', None)} rows={getattr(snapshot, 'long_row_count', None)}")

    # 11. Position side is Buy (a long is present).
    add(11, "position_side_is_buy", bool(snapshot) and snapshot.long_size is not None)

    # 12. Position size is exactly Decimal("0.1").
    size_exact = bool(snapshot) and snapshot.long_size is not None and snapshot.long_size == EXPECTED_POSITION_SIZE
    add(12, "position_size_is_exactly_0_1", size_exact,
        f"long_size={getattr(snapshot, 'long_size', None)}")

    # 13. Size neither zero, below, nor above 0.1.
    size_band = (
        bool(snapshot)
        and snapshot.long_size is not None
        and snapshot.long_size == EXPECTED_POSITION_SIZE
        and snapshot.long_size > 0
    )
    add(13, "position_size_not_zero_below_or_above_0_1", size_band)

    # 14. Position mode one-way compatible (no hedge positionIdx required).
    add(14, "position_mode_one_way_compatible",
        bool(snapshot) and snapshot.position_mode_one_way)

    # 15. No SOLUSDT short / opposite position exists.
    no_short = bool(snapshot) and (snapshot.short_size is None or snapshot.short_size == 0)
    add(15, "no_solusdt_short_position", no_short,
        f"short_size={getattr(snapshot, 'short_size', None)}")

    # 16. No ambiguity in the returned SOLUSDT position records.
    add(16, "no_ambiguous_solusdt_position_rows", bool(snapshot) and not snapshot.ambiguous)

    # 17. Instrument tradable + fresh.
    add(17, "instrument_fresh_and_tradable",
        bool(snapshot) and snapshot.instrument_fresh and snapshot.symbol_tradable)

    # 18. Qty 0.1 satisfies step + min.
    qty_rules_ok = False
    if snapshot and snapshot.min_order_qty is not None and snapshot.qty_step is not None:
        qty_rules_ok = (
            REQUIRED_QTY >= snapshot.min_order_qty
            and _qty_satisfies_step(REQUIRED_QTY, snapshot.qty_step)
        )
    add(18, "qty_satisfies_min_and_step", qty_rules_ok)

    # 19. Body has exactly nine approved fields.
    add(19, "body_has_exactly_nine_approved_fields",
        set(body) == set(APPROVED_BODY_FIELDS), f"fields={sorted(body)!r}")

    # 20. Side is exactly Sell.
    add(20, "side_is_sell", body.get("side") == REQUIRED_SIDE, f"side={body.get('side')!r}")

    # 21. reduceOnly is exactly True.
    add(21, "reduce_only_is_true", body.get("reduceOnly") is True,
        f"reduceOnly={body.get('reduceOnly')!r}")

    # 22. closeOnTrigger is exactly False.
    add(22, "close_on_trigger_is_false", body.get("closeOnTrigger") is False,
        f"closeOnTrigger={body.get('closeOnTrigger')!r}")

    # 23. No active TASK-014BP close order already exists (overall dedup clean).
    add(23, "no_active_task_014bp_close_order",
        duplicate_check is not None and duplicate_check.clean,
        duplicate_check.detail if duplicate_check is not None else "duplicate check not performed")

    # 24. realtime contains no permanent close orderLinkId.
    add(24, "realtime_has_no_close_order_link_id",
        duplicate_check is not None and duplicate_check.realtime_checked and not duplicate_check.realtime_match)

    # 25. history contains no permanent close orderLinkId.
    add(25, "history_has_no_close_order_link_id",
        duplicate_check is not None and duplicate_check.history_checked and not duplicate_check.history_match)

    # 26. Both duplicate sources were actually checked and structurally valid.
    add(26, "both_duplicate_sources_checked_and_valid",
        duplicate_check is not None
        and duplicate_check.realtime_checked
        and duplicate_check.history_checked
        and not duplicate_check.ambiguous)

    # 27. Canonical close journal has no prior blocking state.
    add(27, "no_conflicting_close_journal",
        journal_state not in BLOCKING_CLOSE_JOURNAL_STATES, f"journal_state={journal_state!r}")

    # 28. Sender count before POST is zero.
    add(28, "real_close_order_count_before_is_zero", real_order_count_before == 0,
        f"count={real_order_count_before}")

    # 29. No retry policy active.
    add(29, "no_retry_policy_active", RETRY_ENABLED is False)

    # 30. No scheduler / loop / batch / automatic caller.
    add(30, "no_scheduler_active", SCHEDULER_ENABLED is False)

    # 31. Request-body hash matches the fresh preflight body.
    if expected_body_hash is None:
        hash_ok = computed_hash != ""
    else:
        hash_ok = computed_hash != "" and computed_hash == expected_body_hash
    add(31, "request_body_hash_matches", hash_ok,
        f"computed={computed_hash!r} expected={expected_body_hash!r}")

    # 32. Required final execute flag present.
    flags = dict(execution_flags or {})
    flags_ok = flags.get("mode") == REQUIRED_EXECUTE_MODE and flags.get(REQUIRED_EXECUTE_FLAG) is True
    add(32, "execution_flags_match", flags_ok, f"flags={flags!r}")

    return gates


def _position_evidence(snapshot: ClosePositionSnapshot | None) -> dict[str, Any] | None:
    if snapshot is None:
        return {"authenticated_position_check": "not performed"}
    return {
        "read_source": snapshot.read_source,
        "long_size": str(snapshot.long_size) if snapshot.long_size is not None else None,
        "short_size": str(snapshot.short_size) if snapshot.short_size is not None else None,
        "long_row_count": snapshot.long_row_count,
        "position_mode_one_way": snapshot.position_mode_one_way,
        "ambiguous": snapshot.ambiguous,
        "symbol_tradable": snapshot.symbol_tradable,
    }


def _source_journal_summary(source_journal: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if not isinstance(source_journal, Mapping):
        return None
    return {
        "state": source_journal.get("state"),
        "conclusion": source_journal.get("conclusion"),
        "order_id": source_journal.get("order_id"),
        "order_link_id": source_journal.get("order_link_id"),
    }


def run_close_preflight(
    *,
    probe: Any,
    credentials: DemoCredentials,
    expected_commit: str | None,
    authorization_marker: str | None,
    source_journal: Mapping[str, Any] | None,
    actual_commit: str | None = None,
    journal_state: str = CLOSE_STATE_NONE,
    execution_flags: Mapping[str, Any] | None = None,
    expected_body_hash: str | None = None,
    real_order_count_before: int = 0,
    allow_real_network: bool = False,
    clock: Any | None = None,
    base_url: str = DEMO_BASE_URL,
    mode: str = "preflight",
) -> ClosePreflightReport:
    """Run all read-only close preflight checks. NEVER sends; NEVER arms.

    Authenticated position and exchange duplicate checks are performed ONLY when
    ``allow_real_network`` is True AND Demo credentials are usable; otherwise
    they are reported as not performed and the corresponding gates fail closed.
    The source TASK-014BO opening journal is read locally regardless.
    """
    order_link_id = build_close_order_link_id()
    body = build_close_body(order_link_id=order_link_id)
    computed_hash = body_hash(body)

    if not allow_real_network:
        snapshot = None
        duplicate_check = offline_duplicate_check(
            "authenticated exchange duplicate checks not performed "
            "(--allow-real-network not set)")
    elif not credentials.usable:
        snapshot = None
        duplicate_check = offline_duplicate_check(
            "authenticated exchange duplicate checks not performed (Demo credentials absent)")
    else:
        try:
            snapshot = probe.build_close_snapshot()
        except Exception:
            snapshot = None
        duplicate_check = perform_duplicate_check(probe, order_link_id)

    if execution_flags is None and mode == "preflight":
        execution_flags = {"mode": REQUIRED_EXECUTE_MODE, REQUIRED_EXECUTE_FLAG: True}

    gates = evaluate_close_preflight_gates(
        request_body=body,
        order_link_id=order_link_id,
        authorization_marker=authorization_marker,
        expected_commit=expected_commit,
        actual_commit=actual_commit,
        credentials=credentials,
        snapshot=snapshot,
        source_journal=source_journal,
        journal_state=journal_state,
        execution_flags=execution_flags,
        expected_body_hash=expected_body_hash,
        duplicate_check=duplicate_check,
        real_order_count_before=real_order_count_before,
        base_url=base_url,
    )
    all_passed = all(g.passed for g in gates)
    return ClosePreflightReport(
        task_id=TASK_ID,
        mode=mode,
        generated_at_utc=bo._utc_timestamp(clock),
        expected_commit=expected_commit or "",
        actual_commit=actual_commit or "",
        authorization_marker_matches=authorization_marker == CLOSE_AUTHORIZATION_MARKER,
        order_link_id=order_link_id,
        request_body=body,
        request_body_hash=computed_hash,
        close_journal_state=journal_state,
        credentials_source=credentials.source,
        source_journal_summary=_source_journal_summary(source_journal),
        position_evidence=_position_evidence(snapshot),
        duplicate_check=duplicate_check.to_dict(),
        gates=tuple(gates),
        all_passed=all_passed,
        ready=all_passed,
    )


# ---------------------------------------------------------------------------
# Read-only post-close verification
# ---------------------------------------------------------------------------

MAX_REALTIME_READS = bo.MAX_REALTIME_READS
MAX_HISTORY_READS = bo.MAX_HISTORY_READS
MAX_EXECUTION_READS = bo.MAX_EXECUTION_READS
MAX_POSITION_READS = bo.MAX_POSITION_READS
VERIFICATION_POLL_DELAY_SECONDS = bo.VERIFICATION_POLL_DELAY_SECONDS

_TERMINAL_STATUSES = {"Filled", "PartiallyFilledCanceled", "Cancelled", "Rejected", "Deactivated"}

# Conclusions
OUTCOME_FILLED_ZERO = "DEMO_REDUCE_ONLY_CLOSE_FILLED_POSITION_ZERO_VERIFIED"
OUTCOME_PARTIAL_RESIDUAL = "DEMO_REDUCE_ONLY_CLOSE_PARTIAL_RESIDUAL_LONG_VERIFIED"
OUTCOME_CANCELLED_REMAINS = "DEMO_REDUCE_ONLY_CLOSE_CANCELLED_POSITION_REMAINS"
OUTCOME_REJECTED = "DEMO_REDUCE_ONLY_CLOSE_REJECTED"
OUTCOME_ACCEPTED_PENDING = "DEMO_REDUCE_ONLY_CLOSE_ACCEPTED_STATUS_PENDING"
OUTCOME_POST_FAILED = "DEMO_REDUCE_ONLY_CLOSE_POST_FAILED"
OUTCOME_AMBIGUOUS = "DEMO_REDUCE_ONLY_CLOSE_OUTCOME_AMBIGUOUS"
OUTCOME_REFUSED_PREFLIGHT = "DEMO_REDUCE_ONLY_CLOSE_REFUSED_PREFLIGHT"
OUTCOME_CRITICAL_SHORT = "DEMO_REDUCE_ONLY_CLOSE_CRITICAL_SHORT_POSITION_DETECTED"


@dataclass(frozen=True)
class CloseVerificationResult:
    close_order_id: str
    close_order_link_id: str
    ret_code: int
    ret_msg: str
    final_order_status: str
    cum_exec_qty: str
    avg_price: str
    exec_fee: str
    position_size_before: str
    position_size_after: str
    position_is_zero: bool
    short_position_after: bool
    verification_source: str
    final_state_verified: bool
    outcome_ambiguous: bool
    realtime_reads: int
    history_reads: int
    execution_reads: int
    position_reads: int

    def to_dict(self) -> dict[str, Any]:
        return {
            "close_order_id": self.close_order_id,
            "close_order_link_id": self.close_order_link_id,
            "ret_code": self.ret_code,
            "ret_msg": self.ret_msg,
            "final_order_status": self.final_order_status,
            "cum_exec_qty": self.cum_exec_qty,
            "avg_price": self.avg_price,
            "exec_fee": self.exec_fee,
            "position_size_before": self.position_size_before,
            "position_size_after": self.position_size_after,
            "position_is_zero": self.position_is_zero,
            "short_position_after": self.short_position_after,
            "verification_source": self.verification_source,
            "final_state_verified": self.final_state_verified,
            "outcome_ambiguous": self.outcome_ambiguous,
            "realtime_reads": self.realtime_reads,
            "history_reads": self.history_reads,
            "execution_reads": self.execution_reads,
            "position_reads": self.position_reads,
        }


def _extract_order(resp: Any, *, order_id: str, order_link_id: str) -> dict[str, Any] | None:
    if not isinstance(resp, Mapping):
        return None
    items = (resp.get("result", {}) or {}).get("list", []) or []
    for item in items:
        if not isinstance(item, Mapping):
            continue
        if order_id and str(item.get("orderId", "")) == order_id:
            return item
        if order_link_id and str(item.get("orderLinkId", "")) == order_link_id:
            return item
    return items[0] if items and isinstance(items[0], Mapping) else None


def _parse_solusdt_position(resp: Any) -> tuple[Decimal, Decimal]:
    """Return (long_size, short_size) for SOLUSDT from a /v5/position/list resp."""
    long_size = Decimal("0")
    short_size = Decimal("0")
    if not isinstance(resp, Mapping):
        return long_size, short_size
    for item in (resp.get("result", {}) or {}).get("list", []) or []:
        if not isinstance(item, Mapping) or str(item.get("symbol", "")) != REQUIRED_SYMBOL:
            continue
        try:
            size = Decimal(str(item.get("size", "0") or "0"))
        except (InvalidOperation, TypeError):
            continue
        side = str(item.get("side", ""))
        if side == "Buy":
            long_size += size
        elif side == "Sell":
            short_size += size
        elif size != 0:
            # Unknown side with size -> treat conservatively as long residual.
            long_size += size
    return long_size, short_size


def verify_close_outcome(
    *,
    probe: Any,
    order_id: str,
    order_link_id: str,
    ret_code: int,
    ret_msg: str,
    position_size_before: Decimal,
    clock: Any | None = None,
) -> CloseVerificationResult:
    """Read-only post-close verification. Performs NO order POST."""
    clk = clock or bo._RealClock()
    realtime_reads = history_reads = execution_reads = position_reads = 0
    found: dict[str, Any] | None = None
    source = "none"

    for attempt in range(MAX_REALTIME_READS):
        resp = probe.read_order_realtime(order_id=order_id, order_link_id=order_link_id)
        realtime_reads += 1
        cand = _extract_order(resp, order_id=order_id, order_link_id=order_link_id)
        if cand is not None:
            found = cand
            source = "order_realtime"
            if str(cand.get("orderStatus", "")) in _TERMINAL_STATUSES:
                break
        if attempt < MAX_REALTIME_READS - 1:
            clk.sleep(VERIFICATION_POLL_DELAY_SECONDS)

    if found is None or str(found.get("orderStatus", "")) not in _TERMINAL_STATUSES:
        if history_reads < MAX_HISTORY_READS:
            resp = probe.read_order_history(order_id=order_id, order_link_id=order_link_id)
            history_reads += 1
            cand = _extract_order(resp, order_id=order_id, order_link_id=order_link_id)
            if cand is not None:
                found = cand
                source = "order_history"

    final_status = ""
    cum_exec_qty = "0"
    avg_price = ""
    exec_fee = ""
    if found is not None:
        final_status = str(found.get("orderStatus", ""))
        cum_exec_qty = str(found.get("cumExecQty", "0") or "0")
        avg_price = str(found.get("avgPrice", "") or "")
        exec_fee = str(found.get("cumExecFee", "") or "")

    if execution_reads < MAX_EXECUTION_READS:
        try:
            resp = probe.read_execution_list(order_id=order_id, order_link_id=order_link_id)
            execution_reads += 1
            exec_items = (resp.get("result", {}) or {}).get("list", []) or []
            if exec_items and exec_fee == "":
                fee_total = Decimal("0")
                for it in exec_items:
                    try:
                        fee_total += Decimal(str(it.get("execFee", "0") or "0"))
                    except (InvalidOperation, TypeError):
                        pass
                exec_fee = format(fee_total, "f")
        except Exception:
            pass

    long_after = Decimal("0")
    short_after = Decimal("0")
    if position_reads < MAX_POSITION_READS:
        try:
            resp = probe.read_position_list(symbol=REQUIRED_SYMBOL)
            position_reads += 1
            long_after, short_after = _parse_solusdt_position(resp)
        except Exception:
            pass

    position_is_zero = long_after == 0 and short_after == 0
    short_after_present = short_after > 0
    ambiguous = found is None
    verified = (final_status in _TERMINAL_STATUSES or final_status == "New") and not ambiguous

    return CloseVerificationResult(
        close_order_id=order_id,
        close_order_link_id=order_link_id,
        ret_code=ret_code,
        ret_msg=ret_msg,
        final_order_status=final_status,
        cum_exec_qty=cum_exec_qty,
        avg_price=avg_price,
        exec_fee=exec_fee,
        position_size_before=format(position_size_before, "f"),
        position_size_after=format(long_after, "f"),
        position_is_zero=position_is_zero,
        short_position_after=short_after_present,
        verification_source=source,
        final_state_verified=verified,
        outcome_ambiguous=ambiguous,
        realtime_reads=realtime_reads,
        history_reads=history_reads,
        execution_reads=execution_reads,
        position_reads=position_reads,
    )


def classify_close_outcome(v: CloseVerificationResult) -> str:
    """Map a close verification result to a final conclusion."""
    if v.short_position_after:
        return OUTCOME_CRITICAL_SHORT
    if v.outcome_ambiguous:
        return OUTCOME_AMBIGUOUS
    status = v.final_order_status
    if status == "Filled":
        try:
            filled_full = Decimal(v.cum_exec_qty or "0") == REQUIRED_QTY
        except (InvalidOperation, TypeError):
            filled_full = False
        if filled_full and v.position_is_zero:
            return OUTCOME_FILLED_ZERO
        return OUTCOME_PARTIAL_RESIDUAL
    if status in ("PartiallyFilled", "PartiallyFilledCanceled"):
        return OUTCOME_PARTIAL_RESIDUAL
    if status in ("Cancelled", "Deactivated"):
        return OUTCOME_CANCELLED_REMAINS
    if status == "Rejected":
        return OUTCOME_REJECTED
    if status in ("New", "Untriggered", "Triggered", "Created"):
        return OUTCOME_ACCEPTED_PENDING
    return OUTCOME_AMBIGUOUS


# ---------------------------------------------------------------------------
# Final report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class CloseReport:
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
    close_journal_state: str
    sender_call_count: int
    close_post_attempted: bool
    post_count: int
    post_ret_code: int
    post_ret_msg: str
    close_order_id: str
    final_outcome: str
    verification: Mapping[str, Any] | None
    real_close_sent: bool
    outcome_ambiguous: bool
    no_retry_performed: bool
    new_authorization_required: str

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
            "close_journal_state": self.close_journal_state,
            "sender_call_count": self.sender_call_count,
            "close_post_attempted": self.close_post_attempted,
            "post_count": self.post_count,
            "post_ret_code": self.post_ret_code,
            "post_ret_msg": self.post_ret_msg,
            "close_order_id": self.close_order_id,
            "final_outcome": self.final_outcome,
            "verification": dict(self.verification) if self.verification else None,
            "real_close_sent": self.real_close_sent,
            "outcome_ambiguous": self.outcome_ambiguous,
            "no_retry_performed": self.no_retry_performed,
            "new_authorization_required": self.new_authorization_required,
        }


RESIDUAL_AUTHORIZATION_NOTE = (
    "If any SOLUSDT long remains after this single reduce-only close, a NEW "
    "explicit authorization is required to close the residual. This module "
    "never submits a second close and never opens a short."
)


# ---------------------------------------------------------------------------
# Execute-once orchestration
# ---------------------------------------------------------------------------


def execute_single_reduce_only_close(
    *,
    probe: Any,
    sender: OneShotSenderGuard,
    transport: Any,
    credentials: DemoCredentials,
    journal: CloseOneShotJournal,
    source_journal: Mapping[str, Any] | None,
    expected_commit: str,
    actual_commit: str,
    authorization_marker: str | None,
    execution_flags: Mapping[str, Any],
    expected_body_hash: str,
    real_order_count_before: int = 0,
    clock: Any | None = None,
    base_url: str = DEMO_BASE_URL,
) -> CloseReport:
    """Fully-gated one-shot reduce-only close.

    Independently re-runs source-journal verification, position lookup, and
    realtime/history duplicate detection immediately before arming the canonical
    close journal and the single POST. No retry, no loop, no reversal.
    """
    ts = bo._utc_timestamp(clock)
    order_link_id = build_close_order_link_id()
    body = build_close_body(order_link_id=order_link_id)
    computed_hash = body_hash(body)

    def _report(*, outcome, failed=(), journal_state, post_attempted=False, post_count=0,
                ret_code=0, ret_msg="", order_id="", verification=None, real_sent=False,
                ambiguous=False, preflight_ok=False) -> CloseReport:
        return CloseReport(
            task_id=TASK_ID, generated_at_utc=ts, mode="execute_once",
            expected_commit=expected_commit, actual_commit=actual_commit,
            order_link_id=order_link_id, request_body=body, request_body_hash=computed_hash,
            preflight_all_passed=preflight_ok, preflight_failed_gate_names=tuple(failed),
            close_journal_state=journal_state, sender_call_count=sender.call_count,
            close_post_attempted=post_attempted, post_count=post_count,
            post_ret_code=ret_code, post_ret_msg=ret_msg, close_order_id=order_id,
            final_outcome=outcome, verification=verification, real_close_sent=real_sent,
            outcome_ambiguous=ambiguous, no_retry_performed=True,
            new_authorization_required=RESIDUAL_AUTHORIZATION_NOTE,
        )

    # Fresh read-only evidence (independent of any saved preflight).
    try:
        snapshot = probe.build_close_snapshot()
    except Exception:
        snapshot = None
    journal_state = journal.state()
    duplicate_check = perform_duplicate_check(probe, order_link_id)

    gates = evaluate_close_preflight_gates(
        request_body=body,
        order_link_id=order_link_id,
        authorization_marker=authorization_marker,
        expected_commit=expected_commit,
        actual_commit=actual_commit,
        credentials=credentials,
        snapshot=snapshot,
        source_journal=source_journal,
        journal_state=journal_state,
        execution_flags=execution_flags,
        expected_body_hash=expected_body_hash,
        duplicate_check=duplicate_check,
        real_order_count_before=real_order_count_before,
        base_url=base_url,
    )
    failed = [g.name for g in gates if not g.passed]
    if failed:
        return _report(outcome=OUTCOME_REFUSED_PREFLIGHT, failed=failed, journal_state=journal_state)

    position_before = snapshot.long_size if (snapshot and snapshot.long_size is not None) else Decimal("0")

    # Arm the durable close journal BEFORE any POST. Refuses if one exists.
    try:
        journal.arm_close(
            body_hash_value=computed_hash, order_link_id=order_link_id,
            expected_commit=expected_commit,
            preflight_summary={"all_passed": True, "gate_count": len(gates)}, clock=clock,
        )
    except JournalStateConflict:
        return _report(outcome=OUTCOME_REFUSED_PREFLIGHT,
                       failed=["no_conflicting_close_journal"], journal_state=journal.state())

    body_str = canonical_body_json(body)
    headers = transport.signed_headers_for_post(body_str)
    url = base_url + ORDER_CREATE_PATH

    try:
        response = sender.send_order_create(url=url, headers=headers, body_bytes=body_str.encode("utf-8"))
    except RedirectRejected as exc:
        journal.transition(CLOSE_POST_REJECTED_BEFORE_NETWORK, clock=clock, detail=str(exc))
        return _report(outcome=OUTCOME_POST_FAILED, journal_state=journal.state(),
                       post_attempted=True, post_count=sender.call_count, ret_code=-1, ret_msg=str(exc),
                       preflight_ok=True)
    except TransportTimeout as exc:
        journal.transition(CLOSE_POST_TIMEOUT_AMBIGUOUS, clock=clock, detail=str(exc))
        return _report(outcome=OUTCOME_AMBIGUOUS, journal_state=journal.state(),
                       post_attempted=True, post_count=sender.call_count, ret_code=-1, ret_msg=str(exc),
                       real_sent=True, ambiguous=True, preflight_ok=True)
    except TransportConnectionError as exc:
        journal.transition(CLOSE_POST_EXCEPTION_AMBIGUOUS, clock=clock, detail=str(exc))
        return _report(outcome=OUTCOME_AMBIGUOUS, journal_state=journal.state(),
                       post_attempted=True, post_count=sender.call_count, ret_code=-1, ret_msg=str(exc),
                       real_sent=True, ambiguous=True, preflight_ok=True)
    except SingleRealDemoOrderError as exc:
        journal.transition(CLOSE_RESULT_UNVERIFIED, clock=clock, detail=str(exc))
        return _report(outcome=OUTCOME_AMBIGUOUS, journal_state=journal.state(),
                       post_attempted=True, post_count=sender.call_count, ret_code=-1, ret_msg=str(exc),
                       real_sent=True, ambiguous=True, preflight_ok=True)

    ret_code = int(response.get("retCode", -1))
    ret_msg = str(response.get("retMsg", ""))
    order_id = str((response.get("result", {}) or {}).get("orderId", ""))
    journal.transition(CLOSE_POST_RESPONSE_RECEIVED, clock=clock, ret_code=ret_code, order_id=order_id)

    if ret_code != 0:
        journal.transition(CLOSE_RESULT_VERIFIED, clock=clock, conclusion=OUTCOME_POST_FAILED)
        return _report(outcome=OUTCOME_POST_FAILED, journal_state=journal.state(),
                       post_attempted=True, post_count=sender.call_count, ret_code=ret_code,
                       ret_msg=ret_msg, order_id=order_id, real_sent=False, preflight_ok=True)

    verification = verify_close_outcome(
        probe=probe, order_id=order_id, order_link_id=order_link_id,
        ret_code=ret_code, ret_msg=ret_msg, position_size_before=position_before, clock=clock,
    )
    outcome = classify_close_outcome(verification)
    final_state = CLOSE_RESULT_VERIFIED if verification.final_state_verified else CLOSE_RESULT_UNVERIFIED
    journal.transition(final_state, clock=clock, conclusion=outcome, order_id=order_id)

    real_sent = outcome in (
        OUTCOME_FILLED_ZERO, OUTCOME_PARTIAL_RESIDUAL, OUTCOME_CANCELLED_REMAINS,
        OUTCOME_REJECTED, OUTCOME_ACCEPTED_PENDING, OUTCOME_CRITICAL_SHORT,
    )
    return _report(outcome=outcome, journal_state=journal.state(), post_attempted=True,
                   post_count=sender.call_count, ret_code=ret_code, ret_msg=ret_msg, order_id=order_id,
                   verification=verification.to_dict(), real_sent=real_sent,
                   ambiguous=verification.outcome_ambiguous, preflight_ok=True)


# ---------------------------------------------------------------------------
# Description
# ---------------------------------------------------------------------------


def describe_close_authorization() -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "identity": IDENTITY,
        "close_authorization_marker": CLOSE_AUTHORIZATION_MARKER,
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
        "source_order_id": SOURCE_ORDER_ID,
        "source_order_link_id": SOURCE_ORDER_LINK_ID,
        "source_result": SOURCE_RESULT,
        "expected_position": f"{REQUIRED_SYMBOL} {EXPECTED_POSITION_SIDE} {EXPECTED_POSITION_SIZE}",
        "max_order_create_calls": MAX_ORDER_CREATE_CALLS,
        "permanent_close_order_link_id": build_close_order_link_id(),
        "residual_authorization_note": RESIDUAL_AUTHORIZATION_NOTE,
    }


__all__ = [
    "AUTHORIZATION_QUOTE",
    "APPROVED_BODY_FIELDS",
    "BLOCKING_CLOSE_JOURNAL_STATES",
    "CANONICAL_CLOSE_JOURNAL_DIR",
    "CLOSE_AUTHORIZATION_MARKER",
    "CLOSE_AUTHORIZATION_SCOPE_IDENTITY",
    "CLOSE_JOURNAL_FILENAME",
    "CLOSE_RESULT_UNVERIFIED",
    "CLOSE_RESULT_VERIFIED",
    "CLOSE_STATE_ARMED_BEFORE_CLOSE_POST",
    "CLOSE_STATE_NONE",
    "CloseOneShotJournal",
    "ClosePositionSnapshot",
    "ClosePreflightReport",
    "CloseReport",
    "CloseVerificationResult",
    "DEFAULT_CLOSE_JOURNAL_DIR",
    "EXPECTED_POSITION_SIDE",
    "EXPECTED_POSITION_SIZE",
    "IDENTITY",
    "OUTCOME_ACCEPTED_PENDING",
    "OUTCOME_AMBIGUOUS",
    "OUTCOME_CANCELLED_REMAINS",
    "OUTCOME_CRITICAL_SHORT",
    "OUTCOME_FILLED_ZERO",
    "OUTCOME_PARTIAL_RESIDUAL",
    "OUTCOME_POST_FAILED",
    "OUTCOME_REFUSED_PREFLIGHT",
    "OUTCOME_REJECTED",
    "PROJECT_ROOT",
    "REQUIRED_QTY",
    "REQUIRED_QTY_STR",
    "RESIDUAL_AUTHORIZATION_NOTE",
    "SOURCE_ORDER_ID",
    "SOURCE_ORDER_LINK_ID",
    "SOURCE_RESULT",
    "SOURCE_TASK_ID",
    "TASK_ID",
    "build_close_body",
    "build_close_order_link_id",
    "canonical_close_journal",
    "classify_close_outcome",
    "describe_close_authorization",
    "evaluate_close_preflight_gates",
    "execute_single_reduce_only_close",
    "run_close_preflight",
    "verify_close_outcome",
]
