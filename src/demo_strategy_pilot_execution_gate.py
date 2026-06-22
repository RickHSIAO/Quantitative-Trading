"""TASK-014CB -- single-tiny-order execution gate + plan/audit hardening.

The V1 planner (``demo_strategy_pilot_action_planner``) legitimately emits the
FULL 50-target V1 portfolio as research/translation output (50 OPEN actions at
200 USDT each). That raw multi-action plan must NEVER be submitted directly to
Bybit Demo merely because ``--send-orders-to-demo`` is present.

This module is the explicit, fail-closed authorization layer that sits between
the planner and any order send. It separates *planning* (the full V1 portfolio)
from *execution* (at most ONE explicitly authorized tiny probe order):

    * The raw planner action list can never be iterated and submitted.
    * A future executable action requires an explicit, stable action fingerprint
      (run date / pilot id / symbol / side / intent / reduce_only / canonical qty
      / notional / source reference / forward artifact fingerprint) AND the exact
      authorization marker. Selection by list position / action_seq is impossible.
    * The effective safety restriction is the STRICTEST of every approved policy
      source; irreconcilable sources fail closed ``POLICY_CONFLICT_REQUIRES_REVIEW``.
    * Protected symbols (ENA/TIA/AIXBT/POLYX/EDU) never become candidates, and
      existing protected open positions block new-opening eligibility until the
      policy explicitly defines whether they are excluded from the simultaneous
      position count.
    * The full V1 200-USDT target is reported separately from the (lower) tiny
      execution cap; the V1 weight is never renormalized to look compliant.
    * Canonical Decimal quantities (exact qty_step multiples, floored) are used
      for any execution candidate -- no binary-float artifact reaches a payload.

This module performs NO network I/O, sends NO order, reads NO secret, and imports
neither ``main``, ``src.risk`` nor the live ``BybitExecutor``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, ROUND_DOWN, InvalidOperation
from typing import Any, Mapping, Sequence

from src import demo_strategy_pilot_readiness as rd
from src import demo_only_tiny_execution_adapter as bh

TASK_ID = "TASK-014CB"

PROTECTED_SYMBOLS = frozenset(rd.PROTECTED_SYMBOLS)

# The exact, explicit authorization marker a future operator must supply for a
# single tiny Demo execution probe. Anything else fails closed.
REQUIRED_AUTHORIZATION_MARKER = "EXPLICIT_SINGLE_TINY_DEMO_EXECUTION_AUTHORIZED"

# --- Final execution-authorization statuses --------------------------------
AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE = "AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE"
EXECUTION_NOT_AUTHORIZED_PLAN_INVALID = "EXECUTION_NOT_AUTHORIZED_PLAN_INVALID"
EXECUTION_NOT_AUTHORIZED_MULTI_ACTION_PLAN = "EXECUTION_NOT_AUTHORIZED_MULTI_ACTION_PLAN"
NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS = "NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS"
POLICY_CONFLICT_REQUIRES_REVIEW = "POLICY_CONFLICT_REQUIRES_REVIEW"
EXECUTION_NOT_AUTHORIZED_NO_SELECTION = "EXECUTION_NOT_AUTHORIZED_NO_SELECTION"
EXECUTION_NOT_AUTHORIZED_MISSING_MARKER = "EXECUTION_NOT_AUTHORIZED_MISSING_AUTHORIZATION_MARKER"
EXECUTION_NOT_AUTHORIZED_FINGERPRINT_MISMATCH = "EXECUTION_NOT_AUTHORIZED_FINGERPRINT_MISMATCH"
EXECUTION_NOT_AUTHORIZED_MULTIPLE_SELECTED = "EXECUTION_NOT_AUTHORIZED_MULTIPLE_SELECTED"
EXECUTION_NOT_AUTHORIZED_CANDIDATE_INELIGIBLE = "EXECUTION_NOT_AUTHORIZED_CANDIDATE_INELIGIBLE"
EXECUTION_NOT_AUTHORIZED_TINY_CAP_EXCEEDED = "EXECUTION_NOT_AUTHORIZED_TINY_CAP_EXCEEDED"

# Simultaneous-position policy resolution states.
SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED = "AMBIGUOUS_PROTECTED_LEGACY_EXCLUSION_UNDEFINED"
SIM_POLICY_WITHIN_LIMIT = "WITHIN_SIMULTANEOUS_LIMIT"
SIM_POLICY_AT_OR_OVER_LIMIT = "AT_OR_OVER_SIMULTANEOUS_LIMIT"

# Execution candidates may only be derived from genuine NEW-opening intents.
_OPENING_INTENTS = frozenset({"OPEN"})


# ---------------------------------------------------------------------------
# Canonical Decimal quantity
# ---------------------------------------------------------------------------


def canonical_qty(notional: Any, price: Any, qty_step: Any) -> Decimal:
    """Return the largest exact ``qty_step`` multiple whose notional does not
    exceed ``notional`` at ``price``. Pure Decimal: never a binary-float artifact.

    The result is ALWAYS floored (never rounds up) and is an exact integer
    multiple of ``qty_step``.
    """
    try:
        n = Decimal(str(notional))
        p = Decimal(str(price))
        step = Decimal(str(qty_step))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    if n <= 0 or p <= 0 or step <= 0:
        return Decimal("0")
    raw = n / p
    steps = (raw / step).to_integral_value(rounding=ROUND_DOWN)
    return (steps * step).normalize()


def canonical_qty_str(notional: Any, price: Any, qty_step: Any) -> str:
    """Canonical fixed-point string for :func:`canonical_qty` (no exponent, no
    float artifact)."""
    return _format_decimal(canonical_qty(notional, price, qty_step))


def _format_decimal(value: Decimal) -> str:
    """Format a Decimal as a canonical fixed-point string (e.g. ``110.6``)."""
    v = value.normalize()
    # normalize() can yield scientific notation for integers (e.g. 1E+2); expand.
    if v == v.to_integral_value():
        v = v.quantize(Decimal("1"))
    return format(v, "f")


def is_exact_multiple(qty: Any, qty_step: Any) -> bool:
    """True iff ``qty`` is an exact integer multiple of ``qty_step`` (Decimal)."""
    try:
        q = Decimal(str(qty))
        step = Decimal(str(qty_step))
    except (InvalidOperation, ValueError, TypeError):
        return False
    if step <= 0:
        return False
    return (q % step) == 0


def has_float_artifact(text: str) -> bool:
    """Heuristic: a canonical decimal string never carries a long binary-float
    tail such as ``...0000001`` or ``...9999999``."""
    s = str(text)
    if "." not in s:
        return False
    frac = s.split(".", 1)[1]
    return ("000000" in frac) or ("999999" in frac)


# ---------------------------------------------------------------------------
# Effective safety policy (strictest applicable approved source)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class EffectivePolicy:
    max_new_opening_orders_per_successful_day: int
    max_simultaneous_open_positions: int
    per_order_notional_cap_usdt: Decimal
    daily_new_opening_notional_cap_usdt: Decimal
    averaging_pyramiding_forbidden: bool
    protected_legacy_exclusion_defined: bool
    sources: tuple[str, ...]
    conflict: bool
    conflict_detail: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "max_new_opening_orders_per_successful_day": self.max_new_opening_orders_per_successful_day,
            "max_simultaneous_open_positions": self.max_simultaneous_open_positions,
            "per_order_notional_cap_usdt": _format_decimal(self.per_order_notional_cap_usdt),
            "daily_new_opening_notional_cap_usdt": _format_decimal(self.daily_new_opening_notional_cap_usdt),
            "averaging_pyramiding_forbidden": self.averaging_pyramiding_forbidden,
            "protected_legacy_exclusion_defined": self.protected_legacy_exclusion_defined,
            "sources": list(self.sources),
            "conflict": self.conflict,
            "conflict_detail": self.conflict_detail,
        }


def resolve_effective_policy() -> EffectivePolicy:
    """Compute the strictest applicable approved policy across every source.

    Sources inventoried:
      * ``demo_strategy_pilot_readiness.SAFETY_POLICY`` (canonical Pilot policy:
        1 new-opening order/day, 1 simultaneous position, 10 USDT per-order,
        10 USDT daily, averaging forbidden);
      * the canonical tiny-order adapter caps (``TINY_SIZE_CAP_USDT=5``);
    The effective restriction is the most restrictive (smallest) value. A missing
    or structurally contradictory source fails closed (``conflict=True``).
    """
    sources: list[str] = []
    conflict = False
    conflict_detail = ""

    sp = rd.SAFETY_POLICY
    try:
        sp_per_order = Decimal(str(sp["max_per_order_notional_usdt"]))
        sp_daily = Decimal(str(sp["max_daily_new_opening_notional_usdt"]))
        sp_max_sim = int(sp["max_simultaneous_open_positions"])
        sp_max_new = int(sp["max_new_opening_orders_per_successful_day"])
        sp_avg_forbidden = str(sp["averaging_down_pyramiding_adding"]).upper() == "FORBIDDEN"
        sources.append("demo_strategy_pilot_readiness.SAFETY_POLICY")
    except (KeyError, ValueError, InvalidOperation, TypeError) as exc:
        return EffectivePolicy(0, 0, Decimal("0"), Decimal("0"), True, False,
                               tuple(sources), True, f"SAFETY_POLICY unreadable: {exc}")

    try:
        tiny_per_order = Decimal(str(bh.TINY_SIZE_CAP_USDT))
        sources.append("demo_only_tiny_execution_adapter.TINY_SIZE_CAP_USDT")
    except (InvalidOperation, ValueError, TypeError) as exc:
        return EffectivePolicy(0, 0, Decimal("0"), Decimal("0"), True, False,
                               tuple(sources), True, f"tiny cap unreadable: {exc}")

    # Strictest = smallest cap. The tiny adapter (5) is stricter than the Pilot
    # SAFETY_POLICY (10); choosing the smaller is the safe (not weaker) direction.
    per_order = min(sp_per_order, tiny_per_order)
    # Daily new-opening notional is bounded by both the SAFETY_POLICY daily cap
    # and (per-order cap * max new-opening orders/day).
    daily = min(sp_daily, per_order * Decimal(sp_max_new))
    max_sim = max(0, sp_max_sim)
    max_new = max(0, sp_max_new)

    # The SAFETY_POLICY does not state whether protected LEGACY positions are
    # excluded from the simultaneous-position count -> exclusion is UNDEFINED.
    protected_legacy_exclusion_defined = "protected_legacy_excluded_from_simultaneous_count" in sp

    return EffectivePolicy(
        max_new_opening_orders_per_successful_day=max_new,
        max_simultaneous_open_positions=max_sim,
        per_order_notional_cap_usdt=per_order,
        daily_new_opening_notional_cap_usdt=daily,
        averaging_pyramiding_forbidden=sp_avg_forbidden,
        protected_legacy_exclusion_defined=protected_legacy_exclusion_defined,
        sources=tuple(sources),
        conflict=conflict,
        conflict_detail=conflict_detail,
    )


# ---------------------------------------------------------------------------
# Canonical action fingerprint / identity
# ---------------------------------------------------------------------------


def action_fingerprint(
    action: Any, *, pilot_id: str, date: str, forward_fingerprint: str | None,
) -> str:
    """Stable execution-identity fingerprint for one planned action.

    Includes run date, pilot id, symbol, side, intent, reduce_only, canonical
    qty, notional, source reference, and the forward artifact fingerprint. An
    action can therefore only ever be selected by this explicit identity, never
    by list position or ``action_seq``.
    """
    payload = "|".join([
        TASK_ID,
        str(date),
        str(pilot_id),
        str(getattr(action, "symbol", "")),
        str(getattr(action, "side", "")),
        str(getattr(action, "intent", "")),
        str(getattr(action, "reduce_only", "")),
        str(getattr(action, "qty", "")),
        str(getattr(action, "notional_usdt", "")),
        str(getattr(action, "source_reference", "")),
        str(forward_fingerprint or ""),
    ])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Execution candidate (tiny probe; NEVER the full 200-USDT V1 target)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class TinyExecutionCandidate:
    symbol: str
    side: str
    intent: str
    reduce_only: bool
    action_fingerprint: str
    strategy_target_notional_usdt: str
    tiny_execution_cap_usdt: str
    execution_candidate_notional_usdt: str
    canonical_qty: str
    qty_step: str
    price_usdt: str
    candidate_kind: str = "EXECUTION_PROBE_NOT_V1_PORTFOLIO_REPLICATION"

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol, "side": self.side, "intent": self.intent,
            "reduce_only": self.reduce_only, "action_fingerprint": self.action_fingerprint,
            "candidate_kind": self.candidate_kind,
            "strategy_target_notional_usdt": self.strategy_target_notional_usdt,
            "tiny_execution_cap_usdt": self.tiny_execution_cap_usdt,
            "execution_candidate_notional_usdt": self.execution_candidate_notional_usdt,
            "canonical_qty": self.canonical_qty,
            "qty_step": self.qty_step,
            "price_usdt": self.price_usdt,
        }


def build_tiny_execution_candidate(
    *, symbol: str, side: str, intent: str, reduce_only: bool,
    action_fp: str, strategy_target_notional: Any, price: Any, qty_step: Any,
    tiny_cap: Decimal,
) -> TinyExecutionCandidate:
    """Construct a clearly-labelled tiny EXECUTION PROBE candidate.

    The execution notional is capped at ``tiny_cap`` (NOT the 200-USDT V1
    target); the canonical qty is the largest exact ``qty_step`` multiple within
    that capped notional. This is execution probing, never V1 replication.
    """
    cap = min(Decimal(str(strategy_target_notional)), tiny_cap)
    cq = canonical_qty(cap, price, qty_step)
    candidate_notional = (cq * Decimal(str(price))).normalize() if cq > 0 else Decimal("0")
    return TinyExecutionCandidate(
        symbol=symbol, side=side, intent=intent, reduce_only=reduce_only,
        action_fingerprint=action_fp,
        strategy_target_notional_usdt=_format_decimal(Decimal(str(strategy_target_notional))),
        tiny_execution_cap_usdt=_format_decimal(tiny_cap),
        execution_candidate_notional_usdt=_format_decimal(candidate_notional),
        canonical_qty=_format_decimal(cq),
        qty_step=_format_decimal(Decimal(str(qty_step))),
        price_usdt=_format_decimal(Decimal(str(price))),
    )


# ---------------------------------------------------------------------------
# Execution gate result
# ---------------------------------------------------------------------------


@dataclass
class ExecutionGateResult:
    raw_planned_action_count: int
    eligible_execution_candidate_count: int
    selected_execution_candidate_count: int
    selected_action_id: str | None
    authorization_marker_present: bool
    effective_per_order_notional_cap_usdt: str
    effective_daily_new_opening_notional_cap_usdt: str
    existing_open_position_count: int
    existing_protected_position_count: int
    simultaneous_position_policy_status: str
    multi_action_send_refused: bool
    final_execution_authorization_status: str
    refusal_reasons: list[str]
    effective_policy: dict[str, Any]
    strategy_target_notional_usdt: str | None
    execution_authorized_notional_usdt: str | None
    tiny_execution_cap_usdt: str
    cap_compliance_status: str
    selected_candidate: dict[str, Any] | None = None
    eligible_candidate_fingerprints: list[str] = field(default_factory=list)
    detail: str = ""

    @property
    def authorized(self) -> bool:
        return self.final_execution_authorization_status == AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE

    @property
    def plan_valid(self) -> bool:
        return self.final_execution_authorization_status != EXECUTION_NOT_AUTHORIZED_PLAN_INVALID

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": TASK_ID,
            "raw_planned_action_count": self.raw_planned_action_count,
            "eligible_execution_candidate_count": self.eligible_execution_candidate_count,
            "selected_execution_candidate_count": self.selected_execution_candidate_count,
            "selected_action_id": self.selected_action_id,
            "authorization_marker_present": self.authorization_marker_present,
            "effective_per_order_notional_cap_usdt": self.effective_per_order_notional_cap_usdt,
            "effective_daily_new_opening_notional_cap_usdt": self.effective_daily_new_opening_notional_cap_usdt,
            "existing_open_position_count": self.existing_open_position_count,
            "existing_protected_position_count": self.existing_protected_position_count,
            "simultaneous_position_policy_status": self.simultaneous_position_policy_status,
            "multi_action_send_refused": self.multi_action_send_refused,
            "final_execution_authorization_status": self.final_execution_authorization_status,
            "refusal_reasons": list(self.refusal_reasons),
            "effective_policy": self.effective_policy,
            "strategy_target_notional_usdt": self.strategy_target_notional_usdt,
            "execution_authorized_notional_usdt": self.execution_authorized_notional_usdt,
            "tiny_execution_cap_usdt": self.tiny_execution_cap_usdt,
            "cap_compliance_status": self.cap_compliance_status,
            "selected_candidate": self.selected_candidate,
            "eligible_candidate_fingerprints": list(self.eligible_candidate_fingerprints),
            "detail": self.detail,
        }


def _is_opening_eligible(action: Any) -> bool:
    """True iff the action is a genuine NEW-opening of a non-protected symbol."""
    symbol = str(getattr(action, "symbol", "")).strip().upper()
    intent = str(getattr(action, "intent", ""))
    reduce_only = bool(getattr(action, "reduce_only", False))
    if symbol in PROTECTED_SYMBOLS:
        return False
    if intent not in _OPENING_INTENTS:
        return False
    if reduce_only:
        return False
    try:
        if Decimal(str(getattr(action, "qty", "0"))) <= 0:
            return False
    except (InvalidOperation, ValueError, TypeError):
        return False
    return True


def evaluate_execution_gate(
    *,
    plan: Any,
    open_positions: Sequence[Any],
    pilot_id: str,
    date: str,
    forward_fingerprint: str | None = None,
    selected_action_fingerprint: str | None = None,
    authorization_marker: str | None = None,
    effective_policy: EffectivePolicy | None = None,
) -> ExecutionGateResult:
    """Evaluate whether a single tiny Demo execution probe is authorized.

    Fails closed in every ambiguous case. The raw multi-action plan can never be
    authorized as-is; only one explicitly fingerprinted + marker-authorized,
    cap-compliant, non-protected NEW-opening candidate -- with no blocking
    protected legacy positions and a resolvable strictest policy -- yields
    ``AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE``.
    """
    policy = effective_policy or resolve_effective_policy()
    tiny_cap = policy.per_order_notional_cap_usdt

    refusal_reasons: list[str] = []

    plan_available = bool(getattr(plan, "available", False))
    sizing_verified = bool(getattr(plan, "sizing_verification", {}) or {})
    sizing_verified = bool((getattr(plan, "sizing_verification", {}) or {}).get("verified", False))
    actions = list(getattr(plan, "actions", []) or [])
    raw_count = len(actions)

    open_list = list(open_positions or [])
    existing_open_count = len(open_list)
    existing_protected = [p for p in open_list
                          if str(getattr(p, "symbol", "")).strip().upper() in PROTECTED_SYMBOLS]
    existing_protected_count = len(existing_protected)

    # Eligible candidates: non-protected genuine NEW-opening actions only.
    eligible = [a for a in actions if _is_opening_eligible(a)]
    eligible_fps = [action_fingerprint(a, pilot_id=pilot_id, date=date,
                                       forward_fingerprint=forward_fingerprint) for a in eligible]
    eligible_count = len(eligible)

    marker_present = authorization_marker == REQUIRED_AUTHORIZATION_MARKER

    # --- Plan validity gate (fail closed) ---------------------------------
    if not plan_available or not sizing_verified:
        return ExecutionGateResult(
            raw_planned_action_count=raw_count,
            eligible_execution_candidate_count=eligible_count,
            selected_execution_candidate_count=0,
            selected_action_id=None,
            authorization_marker_present=marker_present,
            effective_per_order_notional_cap_usdt=_format_decimal(tiny_cap),
            effective_daily_new_opening_notional_cap_usdt=_format_decimal(
                policy.daily_new_opening_notional_cap_usdt),
            existing_open_position_count=existing_open_count,
            existing_protected_position_count=existing_protected_count,
            simultaneous_position_policy_status=SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED
            if existing_protected_count else SIM_POLICY_WITHIN_LIMIT,
            multi_action_send_refused=raw_count > 1,
            final_execution_authorization_status=EXECUTION_NOT_AUTHORIZED_PLAN_INVALID,
            refusal_reasons=[EXECUTION_NOT_AUTHORIZED_PLAN_INVALID],
            effective_policy=policy.to_dict(),
            strategy_target_notional_usdt=None,
            execution_authorized_notional_usdt=None,
            tiny_execution_cap_usdt=_format_decimal(tiny_cap),
            cap_compliance_status="PLAN_INVALID",
            detail="planner output is not a valid verified V1 plan; execution refused",
        )

    # --- Selection resolution (explicit fingerprint only) ------------------
    selected_indices: list[int] = []
    if selected_action_fingerprint:
        selected_indices = [i for i, fp in enumerate(eligible_fps)
                            if fp == selected_action_fingerprint]
    selected_count = len(selected_indices)
    selected_action_id = selected_action_fingerprint if selected_count == 1 else None

    # --- Policy conflict (fail closed) ------------------------------------
    if policy.conflict:
        refusal_reasons.append(POLICY_CONFLICT_REQUIRES_REVIEW)

    # --- Existing protected positions block (fail closed) ------------------
    sim_status = SIM_POLICY_WITHIN_LIMIT
    if existing_protected_count > 0 and not policy.protected_legacy_exclusion_defined:
        sim_status = SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED
        refusal_reasons.append(NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS)
    elif existing_open_count >= policy.max_simultaneous_open_positions:
        sim_status = SIM_POLICY_AT_OR_OVER_LIMIT
        refusal_reasons.append(NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS
                               if existing_protected_count else POLICY_CONFLICT_REQUIRES_REVIEW)

    # --- Single-candidate authorization checks ----------------------------
    if selected_count == 0:
        if not selected_action_fingerprint:
            refusal_reasons.append(EXECUTION_NOT_AUTHORIZED_NO_SELECTION)
        else:
            refusal_reasons.append(EXECUTION_NOT_AUTHORIZED_FINGERPRINT_MISMATCH)
    elif selected_count > 1:
        refusal_reasons.append(EXECUTION_NOT_AUTHORIZED_MULTIPLE_SELECTED)

    if not marker_present:
        refusal_reasons.append(EXECUTION_NOT_AUTHORIZED_MISSING_MARKER)

    # --- Raw multi-action refusal -----------------------------------------
    # Refuse whenever the plan carries more than one action and we do NOT have
    # exactly one validly selected + marker-authorized candidate.
    single_authorized_selection = (selected_count == 1 and marker_present)
    multi_action_send_refused = (raw_count > 1) and not single_authorized_selection
    if multi_action_send_refused:
        refusal_reasons.append(EXECUTION_NOT_AUTHORIZED_MULTI_ACTION_PLAN)

    # --- Build (or refuse) the tiny execution candidate -------------------
    selected_candidate_dict: dict[str, Any] | None = None
    strategy_target_notional: str | None = None
    execution_authorized_notional: str | None = None
    cap_compliance_status = "NO_CANDIDATE"

    if selected_count == 1:
        action = eligible[selected_indices[0]]
        target_notional = _action_notional(action)
        strategy_target_notional = _format_decimal(target_notional)
        price = _action_price(action, target_notional)
        qty_step = _action_qty_step(action)
        candidate = build_tiny_execution_candidate(
            symbol=str(getattr(action, "symbol", "")), side=str(getattr(action, "side", "")),
            intent=str(getattr(action, "intent", "")), reduce_only=bool(getattr(action, "reduce_only", False)),
            action_fp=eligible_fps[selected_indices[0]],
            strategy_target_notional=target_notional, price=price, qty_step=qty_step,
            tiny_cap=tiny_cap)
        selected_candidate_dict = candidate.to_dict()
        if target_notional > tiny_cap:
            cap_compliance_status = "TARGET_EXCEEDS_TINY_CAP"
        else:
            cap_compliance_status = "TARGET_WITHIN_TINY_CAP"
        if Decimal(candidate.canonical_qty) <= 0:
            refusal_reasons.append(EXECUTION_NOT_AUTHORIZED_TINY_CAP_EXCEEDED)

    # --- Final status resolution (priority order) -------------------------
    # Deduplicate preserving order.
    seen: set[str] = set()
    refusal_reasons = [r for r in refusal_reasons if not (r in seen or seen.add(r))]

    final_status = _resolve_final_status(refusal_reasons)
    authorized = final_status == AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE

    if authorized and selected_candidate_dict is not None:
        execution_authorized_notional = selected_candidate_dict["execution_candidate_notional_usdt"]

    return ExecutionGateResult(
        raw_planned_action_count=raw_count,
        eligible_execution_candidate_count=eligible_count,
        selected_execution_candidate_count=selected_count,
        selected_action_id=selected_action_id,
        authorization_marker_present=marker_present,
        effective_per_order_notional_cap_usdt=_format_decimal(tiny_cap),
        effective_daily_new_opening_notional_cap_usdt=_format_decimal(
            policy.daily_new_opening_notional_cap_usdt),
        existing_open_position_count=existing_open_count,
        existing_protected_position_count=existing_protected_count,
        simultaneous_position_policy_status=sim_status,
        multi_action_send_refused=multi_action_send_refused,
        final_execution_authorization_status=final_status,
        refusal_reasons=refusal_reasons,
        effective_policy=policy.to_dict(),
        strategy_target_notional_usdt=strategy_target_notional,
        execution_authorized_notional_usdt=execution_authorized_notional,
        tiny_execution_cap_usdt=_format_decimal(tiny_cap),
        cap_compliance_status=cap_compliance_status,
        selected_candidate=selected_candidate_dict,
        eligible_candidate_fingerprints=eligible_fps,
        detail=("single tiny execution candidate authorized" if authorized
                else "execution refused; see refusal_reasons"),
    )


def _resolve_final_status(refusal_reasons: list[str]) -> str:
    """Pick the most salient refusal as the final status, else AUTHORIZED."""
    if not refusal_reasons:
        return AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE
    priority = [
        POLICY_CONFLICT_REQUIRES_REVIEW,
        NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS,
        EXECUTION_NOT_AUTHORIZED_MULTIPLE_SELECTED,
        EXECUTION_NOT_AUTHORIZED_MULTI_ACTION_PLAN,
        EXECUTION_NOT_AUTHORIZED_FINGERPRINT_MISMATCH,
        EXECUTION_NOT_AUTHORIZED_TINY_CAP_EXCEEDED,
        EXECUTION_NOT_AUTHORIZED_MISSING_MARKER,
        EXECUTION_NOT_AUTHORIZED_NO_SELECTION,
        EXECUTION_NOT_AUTHORIZED_CANDIDATE_INELIGIBLE,
        EXECUTION_NOT_AUTHORIZED_PLAN_INVALID,
    ]
    for status in priority:
        if status in refusal_reasons:
            return status
    return refusal_reasons[0]


def _action_notional(action: Any) -> Decimal:
    try:
        n = Decimal(str(getattr(action, "notional_usdt", "") or "0"))
        return n if n > 0 else Decimal("0")
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")


def _action_price(action: Any, notional: Decimal) -> Decimal:
    """Derive price from notional / qty (the planner sized qty = |notional|/price)."""
    try:
        qty = Decimal(str(getattr(action, "qty", "0")))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0")
    if qty <= 0 or notional <= 0:
        return Decimal("0")
    return (notional / qty).normalize()


def _action_qty_step(action: Any) -> Decimal:
    """Best-effort qty_step inference from the planned qty's decimal exponent."""
    try:
        q = Decimal(str(getattr(action, "qty", "0")))
    except (InvalidOperation, ValueError, TypeError):
        return Decimal("0.001")
    exp = q.as_tuple().exponent
    if isinstance(exp, int) and exp < 0:
        return Decimal(1).scaleb(exp)
    return Decimal("1")


__all__ = [
    "TASK_ID", "REQUIRED_AUTHORIZATION_MARKER", "PROTECTED_SYMBOLS",
    "AUTHORIZED_SINGLE_TINY_EXECUTION_CANDIDATE",
    "EXECUTION_NOT_AUTHORIZED_PLAN_INVALID",
    "EXECUTION_NOT_AUTHORIZED_MULTI_ACTION_PLAN",
    "NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS",
    "POLICY_CONFLICT_REQUIRES_REVIEW",
    "EXECUTION_NOT_AUTHORIZED_NO_SELECTION",
    "EXECUTION_NOT_AUTHORIZED_MISSING_MARKER",
    "EXECUTION_NOT_AUTHORIZED_FINGERPRINT_MISMATCH",
    "EXECUTION_NOT_AUTHORIZED_MULTIPLE_SELECTED",
    "EXECUTION_NOT_AUTHORIZED_TINY_CAP_EXCEEDED",
    "EffectivePolicy", "resolve_effective_policy", "ExecutionGateResult",
    "evaluate_execution_gate", "action_fingerprint", "canonical_qty",
    "canonical_qty_str", "is_exact_multiple", "has_float_artifact",
    "TinyExecutionCandidate", "build_tiny_execution_candidate",
]
