"""TASK-014BX -- strategy-native automatic Bybit Demo execution engine.

Converts the existing strategy's *own* desired actions into Bybit Demo orders.
It does NOT normalize the strategy to one order, one position, or 10 USDT: the
strategy-produced symbol, side, quantity/notional, opening/closing intent, and
position-management behaviour (averaging / pyramiding / adding / partial close /
multi-position) all flow through unchanged. Actions are rejected ONLY when an
existing hard safety rule requires it: a forbidden endpoint, a protected symbol,
stale/invalid input, a duplicate identity, or a Demo endpoint failure.

Hard safety boundaries enforced here (never weakened):
    * Bybit Demo endpoint ONLY; Live host permanently denied (the endpoint guard
      is reused verbatim from the single-real-demo-order adapter).
    * No automatic retry that could create a second order.
    * Ambiguous request/response outcome fails closed and requires reconciliation
      (the per-action identity is recorded so a rerun reconciles, never resends).
    * Protected symbols (ENAUSDT/TIAUSDT/AIXBTUSDT/POLYXUSDT/EDUUSDT) are rejected.
    * Manual BO/BP round-trip and smoke records are excluded from Pilot
      performance.
    * Local JSONL/state are authoritative; Notion/Discord delivery is recorded
      separately and a delivery failure never re-runs strategy execution.

This module imports neither ``main``, ``src.risk`` nor the live ``BybitExecutor``.
It performs network I/O ONLY through an injected transport (a fake transport is
used in every test); importing or unit-testing it sends no real order.
"""

from __future__ import annotations

import hashlib
import json
import os
import pathlib
from dataclasses import dataclass, field
from datetime import datetime, timezone
from decimal import Decimal, InvalidOperation
from typing import Any, Mapping, Sequence

from src import demo_strategy_pilot_lifecycle as lc
from src import demo_strategy_pilot_readiness as rd
from src.demo_strategy_pilot_store import CANONICAL_PILOT_ROOT
# Reuse the proven Demo-only endpoint guard verbatim (never weakened here).
from src.demo_only_tiny_execution_adapter_single_real_demo_order import (
    DEMO_BASE_URL,
    DEMO_HOST,
    ORDER_CREATE_PATH,
    assert_demo_url,
    host_of,
)

TASK_ID = "TASK-014BX"
PROTECTED_SYMBOLS = frozenset(rd.PROTECTED_SYMBOLS)

# Record categories excluded from Pilot performance (never counted, never sent).
EXCLUDED_RECORD_CATEGORIES = frozenset({
    "TASK-014BO_BP_MANUAL_ROUND_TRIP",
    "MANUAL_ROUND_TRIP",
    "SMOKE_TEST",
    "SMOKE",
})

ORDER_LINK_ID_PREFIX = "BX7-"
ORDER_LINK_ID_MAX_LEN = 36

# Action intents (all strategy-native; no Pilot cap is applied to any of them).
INTENT_OPEN = "OPEN"
INTENT_ADD = "ADD"            # averaging / pyramiding (strategy-produced)
INTENT_CLOSE = "CLOSE"
INTENT_REDUCE = "REDUCE"      # partial close (strategy-produced)
CLOSING_INTENTS = frozenset({INTENT_CLOSE, INTENT_REDUCE})

# Eligibility verdicts.
ELIGIBLE = "ELIGIBLE"
REJECT_PROTECTED = "REJECT_PROTECTED_SYMBOL"
REJECT_INVALID = "REJECT_INVALID_ACTION"
REJECT_EXCLUDED = "REJECT_EXCLUDED_RECORD_CATEGORY"
REJECT_ENDPOINT = "REJECT_FORBIDDEN_ENDPOINT"

# Per-action execution outcomes.
OUTCOME_RECONCILED = "RECONCILED"                 # unambiguous terminal/accepted state
OUTCOME_DUPLICATE_RECONCILED = "DUPLICATE_RECONCILED"  # prior send found; not resent
OUTCOME_REJECTED = "REJECTED_PRE_SEND"
OUTCOME_AMBIGUOUS = "AMBIGUOUS_FAIL_CLOSED"

# Day verdicts.
DAY_SUCCESS = "ACCEPTABLE_SUCCESSFUL_DAY"
DAY_AMBIGUOUS = "REJECT_AMBIGUOUS_REQUIRES_RECONCILIATION"
DAY_NOT_RUNNING = "REJECT_PILOT_NOT_RUNNING"
DAY_ENDPOINT = "REJECT_FORBIDDEN_ENDPOINT"

# Bybit-style terminal / accepted order statuses considered unambiguous.
_TERMINAL_STATUSES = frozenset({
    "Filled", "PartiallyFilled", "PartiallyFilledCanceled",
    "Cancelled", "Rejected", "Deactivated",
})
_ACCEPTED_PENDING_STATUSES = frozenset({"New", "Created", "Untriggered", "Triggered"})

NATIVE_EXEC_SUBDIR = "native_execution"
EXECUTION_STATE_FILENAME = "execution_state.json"
EXECUTION_JOURNAL_FILENAME = "execution_journal.jsonl"
SENT_LEDGER_FILENAME = "sent_ledger.jsonl"
DELIVERY_LEDGER_FILENAME = "delivery_ledger.jsonl"


class NativeExecutionError(Exception):
    """Base error for the strategy-native execution engine."""


class PilotNotRunningError(NativeExecutionError):
    """The Pilot state is not RUNNING / not execution-authorized."""


def _utc_now(now: datetime | None = None) -> str:
    n = now or datetime.now(timezone.utc)
    return n.strftime("%Y-%m-%dT%H:%M:%SZ")


def _norm_side(raw: Any) -> str:
    s = str(raw or "").strip().lower()
    if s in ("buy", "long"):
        return "Buy"
    if s in ("sell", "short"):
        return "Sell"
    return ""


# ---------------------------------------------------------------------------
# Strategy-native action model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class StrategyNativeAction:
    """One strategy-produced desired action. NO Pilot cap is applied to qty,
    notional, intent, count, or simultaneous-position behaviour."""

    symbol: str
    side: str                 # "Buy" / "Sell" (normalized)
    qty: str                  # strategy-produced quantity (preserved exactly)
    intent: str = INTENT_OPEN
    reduce_only: bool = False
    notional_usdt: str = ""
    position_idx: int = 0
    record_category: str = "STRATEGY_PILOT"
    action_seq: int = 0       # disambiguates multiple actions on the same symbol/side
    source_reference: str = ""

    def identity(self, pilot_id: str, date: str) -> str:
        """Stable strategy-action identity for idempotency / orderLinkId."""
        return "|".join([
            pilot_id, date, self.symbol, self.side, self.intent,
            str(self.qty), str(self.position_idx), str(self.action_seq),
        ])

    def order_link_id(self, pilot_id: str, date: str) -> str:
        digest = hashlib.sha256(self.identity(pilot_id, date).encode("utf-8")).hexdigest()[:16]
        return (ORDER_LINK_ID_PREFIX + digest)[:ORDER_LINK_ID_MAX_LEN]

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol, "side": self.side, "qty": self.qty,
            "intent": self.intent, "reduce_only": self.reduce_only,
            "notional_usdt": self.notional_usdt, "position_idx": self.position_idx,
            "record_category": self.record_category, "action_seq": self.action_seq,
            "source_reference": self.source_reference,
        }


def build_strategy_native_actions(
    strategy_result: Mapping[str, Any],
    *,
    sizing_resolver,
) -> list[StrategyNativeAction]:
    """Build strategy-native OPEN actions from a normalized strategy result.

    ``sizing_resolver(signal) -> (qty_str, notional_str)`` MUST come from the
    existing strategy's own sizing; this function never invents a quantity and
    never caps it. Protected symbols are kept in the list (and later rejected by
    the safety classifier) so their presence is auditable. Multiple actions and
    multiple symbols are preserved as-is -- there is no one-order normalization.
    """
    signals = strategy_result.get("signals", []) if isinstance(strategy_result, Mapping) else []
    actions: list[StrategyNativeAction] = []
    for seq, sig in enumerate(signals or []):
        if not isinstance(sig, Mapping):
            continue
        symbol = str(sig.get("symbol", "")).strip().upper()
        side = _norm_side(sig.get("side"))
        if not symbol or not side:
            actions.append(StrategyNativeAction(symbol=symbol, side=side, qty="0",
                                                intent=INTENT_OPEN, action_seq=seq,
                                                source_reference=str(sig.get("source_reference", ""))))
            continue
        qty, notional = sizing_resolver(sig)
        actions.append(StrategyNativeAction(
            symbol=symbol, side=side, qty=str(qty), intent=INTENT_OPEN,
            reduce_only=False, notional_usdt=str(notional), action_seq=seq,
            source_reference=str(sig.get("source_reference", symbol))))
    return actions


# ---------------------------------------------------------------------------
# Safety classification (strategy-native: rejects ONLY on hard safety rules)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionEligibility:
    action: StrategyNativeAction
    eligibility: str
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {"action": self.action.to_dict(), "eligibility": self.eligibility,
                "reason": self.reason}


def _qty_positive(qty: str) -> bool:
    try:
        return Decimal(str(qty)) > 0
    except (InvalidOperation, TypeError, ValueError):
        return False


def classify_action(action: StrategyNativeAction) -> ActionEligibility:
    """Strategy-native classification. Rejects ONLY for a hard safety rule:
    excluded record category, protected symbol, or structurally invalid action.
    Order count > 1, notional > 10 USDT, and multiple positions are NEVER a
    rejection reason here (those artificial Pilot caps were removed)."""
    if action.record_category in EXCLUDED_RECORD_CATEGORIES:
        return ActionEligibility(action, REJECT_EXCLUDED,
                                 f"record_category {action.record_category!r} excluded from Pilot")
    if action.symbol in PROTECTED_SYMBOLS:
        return ActionEligibility(action, REJECT_PROTECTED,
                                 f"protected symbol {action.symbol!r} permanently excluded")
    if action.side not in ("Buy", "Sell") or not action.symbol:
        return ActionEligibility(action, REJECT_INVALID, "missing/invalid symbol or side")
    if not _qty_positive(action.qty):
        return ActionEligibility(action, REJECT_INVALID, f"non-positive qty {action.qty!r}")
    if action.intent in CLOSING_INTENTS and not action.reduce_only:
        return ActionEligibility(action, REJECT_INVALID,
                                 "closing intent must carry reduce_only=True")
    return ActionEligibility(action, ELIGIBLE, "strategy-native action eligible")


def build_order_body(action: StrategyNativeAction, *, order_link_id: str) -> dict[str, Any]:
    """Bybit v5 order-create body that PRESERVES the strategy's intended qty and,
    for closing intents, reduce-only semantics."""
    body: dict[str, Any] = {
        "category": "linear",
        "symbol": action.symbol,
        "side": action.side,
        "orderType": "Market",
        "qty": str(action.qty),
        "timeInForce": "IOC",
        "reduceOnly": bool(action.reduce_only),
        "closeOnTrigger": False,
        "orderLinkId": order_link_id,
    }
    return body


# ---------------------------------------------------------------------------
# Per-date execution store (append-only journal + ledgers + atomic state)
# ---------------------------------------------------------------------------


class NativeExecutionStore:
    def __init__(self, pilot_id: str, date: str,
                 output_root: str | os.PathLike[str] | None = None) -> None:
        rd.validate_pilot_id(pilot_id)
        from src.demo_strategy_pilot_daily_journal import validate_iso_date
        validate_iso_date(date)
        root = pathlib.Path(output_root) if output_root is not None else CANONICAL_PILOT_ROOT
        self.pilot_id = pilot_id
        self.date = date
        self.dir = (pathlib.Path(root) / pilot_id / NATIVE_EXEC_SUBDIR / date).resolve()
        expected_parent = (pathlib.Path(root) / pilot_id / NATIVE_EXEC_SUBDIR).resolve()
        self.dir.relative_to(expected_parent)  # path-traversal containment
        self.state_path = self.dir / EXECUTION_STATE_FILENAME
        self.journal_path = self.dir / EXECUTION_JOURNAL_FILENAME
        self.sent_ledger_path = self.dir / SENT_LEDGER_FILENAME
        self.delivery_ledger_path = self.dir / DELIVERY_LEDGER_FILENAME

    def _atomic_write(self, path: pathlib.Path, text: str) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        tmp = path.with_name(path.name + ".tmp")
        with open(tmp, "w", encoding="utf-8") as fh:
            fh.write(text)
            fh.flush()
            os.fsync(fh.fileno())
        os.replace(tmp, path)

    def _append(self, path: pathlib.Path, obj: Mapping[str, Any]) -> None:
        self.dir.mkdir(parents=True, exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(dict(obj), ensure_ascii=False, sort_keys=True) + "\n")
            fh.flush()
            os.fsync(fh.fileno())

    def _read_jsonl(self, path: pathlib.Path) -> list[dict[str, Any]]:
        if not path.exists():
            return []
        out: list[dict[str, Any]] = []
        with open(path, "r", encoding="utf-8") as fh:
            for ln in fh:
                ln = ln.strip()
                if ln:
                    out.append(json.loads(ln))
        return out

    def append_journal(self, event: Mapping[str, Any]) -> None:
        self._append(self.journal_path, event)

    def append_sent(self, entry: Mapping[str, Any]) -> None:
        self._append(self.sent_ledger_path, entry)

    def append_delivery(self, entry: Mapping[str, Any]) -> None:
        self._append(self.delivery_ledger_path, entry)

    def sent_ledger(self) -> list[dict[str, Any]]:
        return self._read_jsonl(self.sent_ledger_path)

    def prior_attempt(self, identity: str) -> dict[str, Any] | None:
        match = [e for e in self.sent_ledger() if e.get("identity") == identity]
        return match[-1] if match else None

    def write_state(self, state: Mapping[str, Any]) -> None:
        self._atomic_write(self.state_path,
                           json.dumps(dict(state), ensure_ascii=False, indent=2, sort_keys=True))

    def read_state(self) -> dict[str, Any] | None:
        if not self.state_path.exists():
            return None
        with open(self.state_path, "r", encoding="utf-8") as fh:
            return json.load(fh)


# ---------------------------------------------------------------------------
# Reconciliation of a single submission to an unambiguous exchange state
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ActionExecution:
    identity: str
    order_link_id: str
    eligibility: str
    outcome: str
    order_id: str = ""
    final_status: str = ""
    cum_exec_qty: str = "0"
    avg_price: str = ""
    exec_fee: str = ""
    ret_code: int | None = None
    ret_msg: str = ""
    reason: str = ""
    request_fingerprint: str = ""
    response_fingerprint: str = ""
    sender_calls: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "identity": self.identity, "order_link_id": self.order_link_id,
            "eligibility": self.eligibility, "outcome": self.outcome,
            "order_id": self.order_id, "final_status": self.final_status,
            "cum_exec_qty": self.cum_exec_qty, "avg_price": self.avg_price,
            "exec_fee": self.exec_fee, "ret_code": self.ret_code, "ret_msg": self.ret_msg,
            "reason": self.reason, "request_fingerprint": self.request_fingerprint,
            "response_fingerprint": self.response_fingerprint, "sender_calls": self.sender_calls,
        }


def _fingerprint(obj: Any) -> str:
    return hashlib.sha256(
        json.dumps(obj, sort_keys=True, ensure_ascii=False, default=str).encode("utf-8")
    ).hexdigest()


def _extract_order(resp: Any, order_link_id: str) -> dict[str, Any] | None:
    if not isinstance(resp, Mapping):
        return None
    result = resp.get("result")
    if not isinstance(result, Mapping):
        return None
    items = result.get("list")
    if not isinstance(items, (list, tuple)):
        return None
    for it in items:
        if isinstance(it, Mapping) and str(it.get("orderLinkId", "")) == order_link_id:
            return dict(it)
    return None


def reconcile_submission(transport: Any, order_link_id: str) -> tuple[dict[str, Any] | None, bool]:
    """Read-only reconcile of one orderLinkId to a terminal/accepted state.

    Returns ``(order_item, ambiguous)``. Any read failure / missing item / unknown
    status is ambiguous (fail closed); a retry of the POST is NEVER performed."""
    try:
        resp = transport.reconcile(order_link_id=order_link_id)
    except Exception:  # noqa: BLE001 -- any read failure fails closed
        return None, True
    item = _extract_order(resp, order_link_id)
    if item is None:
        return None, True
    status = str(item.get("orderStatus", ""))
    if status in _TERMINAL_STATUSES or status in _ACCEPTED_PENDING_STATUSES:
        return item, False
    return item, True


# ---------------------------------------------------------------------------
# Daily strategy-native execution
# ---------------------------------------------------------------------------


@dataclass
class DailyExecutionResult:
    task_id: str
    pilot_id: str
    date: str
    day_verdict: str
    proposed: list[dict[str, Any]]
    accepted: list[dict[str, Any]]
    rejected: list[dict[str, Any]]
    ambiguous: list[dict[str, Any]]
    sender_call_count: int
    order_post_count: int
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id, "pilot_id": self.pilot_id, "date": self.date,
            "day_verdict": self.day_verdict,
            "proposed_count": len(self.proposed), "accepted_count": len(self.accepted),
            "rejected_count": len(self.rejected), "ambiguous_count": len(self.ambiguous),
            "proposed": self.proposed, "accepted": self.accepted,
            "rejected": self.rejected, "ambiguous": self.ambiguous,
            "sender_call_count": self.sender_call_count,
            "order_post_count": self.order_post_count, "detail": self.detail,
        }


def execute_daily_native(
    *,
    pilot_id: str,
    date: str,
    actions: Sequence[StrategyNativeAction],
    transport: Any,
    output_root: str | os.PathLike[str] | None = None,
    base_url: str = DEMO_BASE_URL,
    now: datetime | None = None,
) -> DailyExecutionResult:
    """Execute the strategy's own desired actions against Bybit Demo for one date.

    The Pilot state must be RUNNING and execution-authorized. Every action is
    classified by the hard-safety rules only; eligible actions are sent once to
    the Demo endpoint and reconciled to an unambiguous state. A prior attempt for
    the same identity is reconciled, never resent. An ambiguous outcome fails the
    day closed for reconciliation; the successful-day counter is advanced AT MOST
    once, only on a clean day.
    """
    ts = _utc_now(now)

    # 1. Pilot must be RUNNING + execution authorized + Live never authorized.
    state_store = rd.PilotStateStore(pilot_id, output_root)
    pstate = state_store.read_state()
    running = (pstate is not None and pstate.get("lifecycle_state") == rd.RUNNING
               and pstate.get("order_execution_authorized") is True
               and pstate.get("live_trading_authorized") is False)
    store = NativeExecutionStore(pilot_id, date, output_root)
    if not running:
        store.append_journal({"event": "REFUSED_NOT_RUNNING", "at_utc": ts,
                              "lifecycle_state": (pstate or {}).get("lifecycle_state")})
        return DailyExecutionResult(TASK_ID, pilot_id, date, DAY_NOT_RUNNING, [], [], [], [],
                                    0, 0, "Pilot not RUNNING / execution not authorized")

    # 2. Endpoint guard: Demo host only. A forbidden endpoint sends nothing.
    # The strict guard is invoked AND an explicit host-equality check is made so
    # the decision never depends on a single exception-class identity.
    endpoint_detail = ""
    try:
        assert_demo_url(base_url + ORDER_CREATE_PATH)
        endpoint_ok = host_of(base_url) == DEMO_HOST and base_url.startswith(DEMO_BASE_URL)
    except Exception as exc:  # noqa: BLE001 -- any guard rejection denies the endpoint
        endpoint_ok = False
        endpoint_detail = str(exc)
    if not endpoint_ok:
        store.append_journal({"event": "REFUSED_FORBIDDEN_ENDPOINT", "at_utc": ts,
                              "detail": endpoint_detail or f"host {host_of(base_url)!r} not Demo"})
        return DailyExecutionResult(TASK_ID, pilot_id, date, DAY_ENDPOINT, [], [], [], [],
                                    0, 0, f"forbidden endpoint: {endpoint_detail or base_url}")

    proposed: list[dict[str, Any]] = []
    accepted: list[ActionExecution] = []
    rejected: list[ActionExecution] = []
    ambiguous: list[ActionExecution] = []
    sender_calls = 0
    order_posts = 0

    store.append_journal({"event": "DAILY_EXECUTION_START", "at_utc": ts,
                          "action_count": len(actions), "base_url": base_url})

    for action in actions:
        elig = classify_action(action)
        identity = action.identity(pilot_id, date)
        link_id = action.order_link_id(pilot_id, date)
        proposed.append({**elig.to_dict(), "identity": identity, "order_link_id": link_id})

        if elig.eligibility != ELIGIBLE:
            ex = ActionExecution(identity=identity, order_link_id=link_id,
                                 eligibility=elig.eligibility, outcome=OUTCOME_REJECTED,
                                 reason=elig.reason)
            rejected.append(ex)
            store.append_journal({"event": "ACTION_REJECTED", "at_utc": ts, **ex.to_dict()})
            continue

        body = build_order_body(action, order_link_id=link_id)
        req_fp = _fingerprint(body)

        # Idempotency: a prior attempt for this identity is reconciled, not resent.
        prior = store.prior_attempt(identity)
        if prior is not None:
            item, amb = reconcile_submission(transport, link_id)
            ex = _build_execution(identity, link_id, item, amb, sender_calls=0,
                                  outcome_if_ok=OUTCOME_DUPLICATE_RECONCILED,
                                  req_fp=req_fp, prior_order_id=str(prior.get("order_id", "")))
            (ambiguous if amb else accepted).append(ex)
            store.append_journal({"event": "DUPLICATE_RECONCILE", "at_utc": ts, **ex.to_dict()})
            continue

        # First (and only) send for this identity.
        url = base_url + ORDER_CREATE_PATH
        store.append_sent({"identity": identity, "order_link_id": link_id, "at_utc": ts,
                           "state": "ATTEMPTED", "request_fingerprint": req_fp})
        try:
            resp = transport.post_order_create(url=url, body=body)
            sender_calls += 1
            order_posts += 1
        except Exception as exc:  # noqa: BLE001 -- ambiguous; NO retry, fail closed
            sender_calls += 1
            ex = ActionExecution(identity=identity, order_link_id=link_id, eligibility=ELIGIBLE,
                                 outcome=OUTCOME_AMBIGUOUS, reason=f"send raised: {exc}",
                                 request_fingerprint=req_fp, sender_calls=1)
            ambiguous.append(ex)
            store.append_sent({"identity": identity, "order_link_id": link_id, "at_utc": ts,
                               "state": "AMBIGUOUS", "request_fingerprint": req_fp,
                               "detail": str(exc)})
            store.append_journal({"event": "ACTION_AMBIGUOUS_SEND", "at_utc": ts, **ex.to_dict()})
            continue

        resp_fp = _fingerprint(resp if isinstance(resp, Mapping) else {"raw": str(resp)})
        ret_code = None
        order_id = ""
        if isinstance(resp, Mapping):
            try:
                ret_code = int(resp.get("retCode", -1))
            except (TypeError, ValueError):
                ret_code = None
            order_id = str((resp.get("result") or {}).get("orderId", "")) \
                if isinstance(resp.get("result"), Mapping) else ""

        store.append_sent({"identity": identity, "order_link_id": link_id, "at_utc": ts,
                           "state": "POST_RESPONSE_RECEIVED", "ret_code": ret_code,
                           "order_id": order_id, "request_fingerprint": req_fp,
                           "response_fingerprint": resp_fp})

        if ret_code != 0:
            ex = ActionExecution(identity=identity, order_link_id=link_id, eligibility=ELIGIBLE,
                                 outcome=OUTCOME_AMBIGUOUS, order_id=order_id, ret_code=ret_code,
                                 ret_msg=str((resp or {}).get("retMsg", "")) if isinstance(resp, Mapping) else "",
                                 reason="non-zero retCode", request_fingerprint=req_fp,
                                 response_fingerprint=resp_fp, sender_calls=1)
            ambiguous.append(ex)
            store.append_journal({"event": "ACTION_NONZERO_RETCODE", "at_utc": ts, **ex.to_dict()})
            continue

        item, amb = reconcile_submission(transport, link_id)
        ex = _build_execution(identity, link_id, item, amb, sender_calls=1,
                              outcome_if_ok=OUTCOME_RECONCILED, req_fp=req_fp, resp_fp=resp_fp,
                              ret_code=ret_code, prior_order_id=order_id)
        (ambiguous if amb else accepted).append(ex)
        store.append_sent({"identity": identity, "order_link_id": link_id, "at_utc": ts,
                           "state": "AMBIGUOUS" if amb else "RECONCILED",
                           "order_id": ex.order_id, "final_status": ex.final_status})
        store.append_journal({"event": "ACTION_RECONCILED" if not amb else "ACTION_AMBIGUOUS_RECONCILE",
                              "at_utc": ts, **ex.to_dict()})

    # Day verdict: ambiguous anywhere -> fail closed for reconciliation.
    day_verdict = DAY_AMBIGUOUS if ambiguous else DAY_SUCCESS
    result = DailyExecutionResult(
        TASK_ID, pilot_id, date, day_verdict,
        proposed=proposed,
        accepted=[e.to_dict() for e in accepted],
        rejected=[e.to_dict() for e in rejected],
        ambiguous=[e.to_dict() for e in ambiguous],
        sender_call_count=sender_calls, order_post_count=order_posts,
        detail="strategy-native daily execution complete" if not ambiguous
               else "ambiguous outcome; reconcile before counting this date")
    state_record = {**result.to_dict(), "generated_at_utc": ts,
                    "live_trading_authorized": False, "environment": rd.ENVIRONMENT}
    store.write_state(state_record)
    store.append_journal({"event": "DAILY_EXECUTION_FINISHED", "at_utc": ts,
                          "day_verdict": day_verdict, "accepted": len(accepted),
                          "rejected": len(rejected), "ambiguous": len(ambiguous),
                          "sender_call_count": sender_calls, "order_post_count": order_posts})
    return result


def _build_execution(identity: str, link_id: str, item: Mapping[str, Any] | None, amb: bool,
                     *, sender_calls: int, outcome_if_ok: str, req_fp: str = "", resp_fp: str = "",
                     ret_code: int | None = None, prior_order_id: str = "") -> ActionExecution:
    if amb or item is None:
        return ActionExecution(identity=identity, order_link_id=link_id, eligibility=ELIGIBLE,
                               outcome=OUTCOME_AMBIGUOUS, order_id=prior_order_id, ret_code=ret_code,
                               reason="reconcile ambiguous", request_fingerprint=req_fp,
                               response_fingerprint=resp_fp, sender_calls=sender_calls)
    return ActionExecution(
        identity=identity, order_link_id=link_id, eligibility=ELIGIBLE, outcome=outcome_if_ok,
        order_id=str(item.get("orderId", prior_order_id)), final_status=str(item.get("orderStatus", "")),
        cum_exec_qty=str(item.get("cumExecQty", "0") or "0"),
        avg_price=str(item.get("avgPrice", "") or ""),
        exec_fee=str(item.get("cumExecFee", "") or ""), ret_code=ret_code,
        request_fingerprint=req_fp, response_fingerprint=resp_fp, sender_calls=sender_calls)


# ---------------------------------------------------------------------------
# Successful-day advancement (advances AT MOST once per date)
# ---------------------------------------------------------------------------


STATUS_DAY_ADVANCED = "SUCCESSFUL_DAY_ADVANCED"
STATUS_DAY_ALREADY_COUNTED = "DATE_ALREADY_COUNTED_NO_ADVANCE"
STATUS_DAY_NOT_SUCCESSFUL = "DATE_NOT_SUCCESSFUL_NO_ADVANCE"
STATUS_PILOT_COMPLETED = "PILOT_COMPLETED"


def advance_successful_day(
    *,
    pilot_id: str,
    date: str,
    day_verdict: str,
    output_root: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Advance the completed-successful-day counter by AT MOST one for ``date``.

    A non-successful verdict never advances. A date already present in
    ``successful_dates`` never advances again. After exactly
    ``TARGET_SUCCESSFUL_DAYS`` accepted dates the Pilot transitions to COMPLETED.
    Never deletes or rewrites prior records."""
    ts = _utc_now(now)
    store = rd.PilotStateStore(pilot_id, output_root)
    state = store.read_state()
    if state is None or state.get("lifecycle_state") not in (rd.RUNNING,):
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date,
                "status": DAY_NOT_RUNNING, "detail": "Pilot not RUNNING"}

    if day_verdict != DAY_SUCCESS:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date,
                "status": STATUS_DAY_NOT_SUCCESSFUL, "day_verdict": day_verdict,
                "completed_successful_days": state.get("completed_successful_days", 0)}

    successful = list(state.get("successful_dates", []) or [])
    if date in successful:
        return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date,
                "status": STATUS_DAY_ALREADY_COUNTED,
                "completed_successful_days": state.get("completed_successful_days", 0)}

    successful.append(date)
    completed = len(successful)
    remaining = max(rd.TARGET_SUCCESSFUL_DAYS - completed, 0)
    new_state = dict(state)
    new_state.update({
        "successful_dates": successful,
        "completed_successful_days": completed,
        "remaining_successful_days": remaining,
        "last_accepted_date": date,
        "event_count": int(state.get("event_count", 0)) + 1,
    })
    event_name = "SUCCESSFUL_DAY"
    pilot_completed = completed >= rd.TARGET_SUCCESSFUL_DAYS
    if pilot_completed:
        new_state["lifecycle_state"] = rd.COMPLETED
        new_state["completed_at_utc"] = ts
        event_name = "SUCCESSFUL_DAY_AND_COMPLETION"
    store.write_state(new_state)
    store.append_event({"event": event_name, "at_utc": ts, "task_id": TASK_ID, "date": date,
                        "completed_successful_days": completed,
                        "remaining_successful_days": remaining,
                        "pilot_completed": pilot_completed})
    return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date,
            "status": STATUS_PILOT_COMPLETED if pilot_completed else STATUS_DAY_ADVANCED,
            "completed_successful_days": completed, "remaining_successful_days": remaining,
            "lifecycle_state": new_state["lifecycle_state"], "pilot_completed": pilot_completed}


def record_delivery_status(
    *,
    pilot_id: str,
    date: str,
    channel: str,
    status: str,
    output_root: str | os.PathLike[str] | None = None,
    now: datetime | None = None,
) -> dict[str, Any]:
    """Record Notion/Discord delivery status in a SEPARATE ledger. A delivery
    retry NEVER re-runs strategy execution (this only touches the delivery
    ledger, never the sent ledger or any order)."""
    ts = _utc_now(now)
    store = NativeExecutionStore(pilot_id, date, output_root)
    entry = {"at_utc": ts, "channel": channel, "status": status}
    store.append_delivery(entry)
    return {"task_id": TASK_ID, "pilot_id": pilot_id, "date": date, **entry}


__all__ = [
    "ActionEligibility",
    "ActionExecution",
    "CLOSING_INTENTS",
    "DAY_AMBIGUOUS",
    "DAY_ENDPOINT",
    "DAY_NOT_RUNNING",
    "DAY_SUCCESS",
    "DailyExecutionResult",
    "ELIGIBLE",
    "EXCLUDED_RECORD_CATEGORIES",
    "INTENT_ADD",
    "INTENT_CLOSE",
    "INTENT_OPEN",
    "INTENT_REDUCE",
    "NativeExecutionError",
    "NativeExecutionStore",
    "PROTECTED_SYMBOLS",
    "REJECT_ENDPOINT",
    "REJECT_EXCLUDED",
    "REJECT_INVALID",
    "REJECT_PROTECTED",
    "STATUS_DAY_ADVANCED",
    "STATUS_DAY_ALREADY_COUNTED",
    "STATUS_DAY_NOT_SUCCESSFUL",
    "STATUS_PILOT_COMPLETED",
    "StrategyNativeAction",
    "TASK_ID",
    "advance_successful_day",
    "build_order_body",
    "build_strategy_native_actions",
    "classify_action",
    "execute_daily_native",
    "record_delivery_status",
    "reconcile_submission",
]
