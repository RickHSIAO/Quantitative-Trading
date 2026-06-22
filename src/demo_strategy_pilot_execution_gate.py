"""TASK-014CB_FIX -- non-dispatching execution-review gate that delegates real
Demo execution to the existing canonical one-shot tiny adapter.

The V1 planner (``demo_strategy_pilot_action_planner``) legitimately emits the
FULL 50-target V1 portfolio (50 OPEN actions at 200 USDT each) as research /
translation output. That raw multi-action plan is PLANNING OUTPUT ONLY and is
never executable as-is.

TASK-014CB introduced a generic execution-authorization stack that converted a
``StrategyNativeAction`` into an order via ``execute_daily_native`` and inferred
the exchange ``qtyStep`` from the serialized planner quantity. Both are corrected
here:

  * The native daily send surface NO LONGER dispatches any order. This gate is a
    READ-ONLY execution REVIEW; it produces no executable packet and never
    reaches a real sender. Real Demo execution is delegated to the existing,
    authoritative canonical one-shot tiny adapter chain (SOLUSDT-locked,
    Market/IOC, single-shot, cap-escalation + explicit Rick authorization marker,
    Demo-only endpoint guard, exact signed payload).
  * Quantity rules come ONLY from the authoritative ``InstrumentRules`` snapshot
    surfaced by the read-only instrument-metadata provider -- never inferred from
    a quantity string, decimal places, or notional/qty.
  * Only symbols inside the canonical one-shot adapter allowlist
    (``demo_only_tiny_execution_adapter.ALLOWED_SYMBOL`` = SOLUSDT) are even
    review-eligible; every other V1 symbol is planning-only and explicitly
    ``SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER``.

No independent real-order authorization marker is defined here. The authoritative
markers live in the canonical chain and are NOT consumed by this module. This
module performs NO network I/O, sends NO order, reads NO secret, and imports
neither ``main``, ``src.risk`` nor the live ``BybitExecutor``.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass, field
from decimal import Decimal, InvalidOperation
from typing import Any, Sequence

from src import demo_strategy_pilot_readiness as rd
from src import demo_only_tiny_execution_adapter as bh
from src import demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate as ce
from src import (
    demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator as osh,
)

TASK_ID = "TASK-014CB_FIX"

PROTECTED_SYMBOLS = frozenset(rd.PROTECTED_SYMBOLS)

# --- Canonical one-shot chain references (REUSED, never replaced) -----------
# The single symbol the existing canonical one-shot tiny Demo adapter supports.
CANONICAL_ONE_SHOT_ALLOWED_SYMBOL = bh.ALLOWED_SYMBOL                 # "SOLUSDT"
CANONICAL_ONE_SHOT_ALLOWED_ENVIRONMENT = bh.ALLOWED_ENVIRONMENT       # "bybit_demo"
CANONICAL_ONE_SHOT_ALLOWED_ORDER_TYPE = bh.ALLOWED_ORDER_TYPE         # "Market"
CANONICAL_ONE_SHOT_ALLOWED_TIME_IN_FORCE = bh.ALLOWED_TIME_IN_FORCE   # "IOC"
# The authoritative real-order authorization marker already exists in the
# canonical one-shot orchestrator. It is referenced for audit ONLY and is NEVER
# consumed by this module (no real order is ever dispatched from here).
CANONICAL_REAL_ORDER_AUTHORIZATION_MARKER = osh.EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER
CANONICAL_CAP_ESCALATION_AUTHORIZATION_MARKER = ce.EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER

# --- Top-level delegation statuses -----------------------------------------
EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER = "EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER"
CANONICAL_ONE_SHOT_EXECUTION_PACKET_REQUIRED = "CANONICAL_ONE_SHOT_EXECUTION_PACKET_REQUIRED"

# --- Review refusal / detail statuses --------------------------------------
EXECUTION_NOT_AUTHORIZED_PLAN_INVALID = "EXECUTION_NOT_AUTHORIZED_PLAN_INVALID"
NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS = "NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS"
POLICY_CONFLICT_REQUIRES_REVIEW = "POLICY_CONFLICT_REQUIRES_REVIEW"
SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER = "SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER"
RULE_MISSING = "INSTRUMENT_RULE_MISSING"
RULE_NON_TRADING = "INSTRUMENT_RULE_NON_TRADING"
RULE_MALFORMED = "INSTRUMENT_RULE_MALFORMED"

# Candidate rule-validation states (display).
RULE_VALID_DELEGATION_REQUIRED = "RULE_VALID_DELEGATION_REQUIRED"

# Simultaneous-position policy resolution states.
SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED = "AMBIGUOUS_PROTECTED_LEGACY_EXCLUSION_UNDEFINED"
SIM_POLICY_WITHIN_LIMIT = "WITHIN_SIMULTANEOUS_LIMIT"
SIM_POLICY_AT_OR_OVER_LIMIT = "AT_OR_OVER_SIMULTANEOUS_LIMIT"

_OPENING_INTENTS = frozenset({"OPEN"})


# ---------------------------------------------------------------------------
# Small display utilities (NOT used to infer any exchange rule)
# ---------------------------------------------------------------------------


def _format_decimal(value: Any) -> str | None:
    if value is None:
        return None
    try:
        v = Decimal(str(value)).normalize()
    except (InvalidOperation, ValueError, TypeError):
        return None
    if v == v.to_integral_value():
        v = v.quantize(Decimal("1"))
    return format(v, "f")


def has_float_artifact(text: Any) -> bool:
    """A canonical decimal string never carries a long binary-float tail."""
    s = str(text)
    if "." not in s:
        return False
    frac = s.split(".", 1)[1]
    return ("000000" in frac) or ("999999" in frac)


def is_exact_multiple(qty: Any, qty_step: Any) -> bool:
    try:
        q = Decimal(str(qty))
        step = Decimal(str(qty_step))
    except (InvalidOperation, ValueError, TypeError):
        return False
    if step <= 0:
        return False
    return (q % step) == 0


# ---------------------------------------------------------------------------
# Effective safety policy + canonical-source inventory
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
    """Strictest applicable approved policy across every source. A missing or
    structurally contradictory source fails closed (``conflict=True``)."""
    sources: list[str] = []
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

    per_order = min(sp_per_order, tiny_per_order)
    daily = min(sp_daily, per_order * Decimal(sp_max_new))
    protected_legacy_exclusion_defined = "protected_legacy_excluded_from_simultaneous_count" in sp

    return EffectivePolicy(
        max_new_opening_orders_per_successful_day=max(0, sp_max_new),
        max_simultaneous_open_positions=max(0, sp_max_sim),
        per_order_notional_cap_usdt=per_order,
        daily_new_opening_notional_cap_usdt=daily,
        averaging_pyramiding_forbidden=sp_avg_forbidden,
        protected_legacy_exclusion_defined=protected_legacy_exclusion_defined,
        sources=tuple(sources),
        conflict=False,
        conflict_detail="",
    )


def policy_source_inventory() -> list[dict[str, Any]]:
    """Full inventory of every relevant policy / authorization source. The
    cap-escalation gate and the one-shot real-order marker are explicitly
    enumerated and reported as NOT authorized by this task."""
    return [
        {"source": "demo_strategy_pilot_readiness.SAFETY_POLICY",
         "role": "canonical Pilot safety policy (caps, simultaneous, averaging)",
         "authorized_here": False},
        {"source": "demo_only_tiny_execution_adapter (TINY_SIZE_CAP_USDT / TINY_QTY_CAP_SOL / TINY_QTY_STEP_SOL)",
         "role": "canonical tiny-order caps + SOLUSDT/Market/IOC locks",
         "tiny_size_cap_usdt": str(bh.TINY_SIZE_CAP_USDT),
         "allowed_symbol": bh.ALLOWED_SYMBOL,
         "authorized_here": False},
        {"source": "demo_only_tiny_execution_adapter_tiny_order_instrument_rules",
         "role": "instrument minimum candidate derivation (authoritative qtyStep)",
         "authorized_here": False},
        {"source": "demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate",
         "role": "cap-escalation authorization gate",
         "cap_escalation_marker": CANONICAL_CAP_ESCALATION_AUTHORIZATION_MARKER,
         "cap_escalation_authorized": False,
         "authorized_here": False},
        {"source": "demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator",
         "role": "one-shot real-demo authorization marker + orchestrator",
         "real_order_marker": CANONICAL_REAL_ORDER_AUTHORIZATION_MARKER,
         "real_order_authorized": False,
         "authorized_here": False},
        {"source": "demo_only_tiny_execution_adapter_single_real_demo_order (endpoint guard)",
         "role": "Demo-only endpoint guard; live host permanently denied",
         "authorized_here": False},
        {"source": "demo_strategy_pilot_readiness.PROTECTED_SYMBOLS",
         "role": "protected-symbol policy",
         "protected_symbols": list(PROTECTED_SYMBOLS),
         "authorized_here": False},
    ]


def canonical_one_shot_references() -> dict[str, Any]:
    """Audit of the exact canonical one-shot modules/constants this review
    delegates to (reused, never replaced)."""
    return {
        "delegated": True,
        "allowed_symbol": CANONICAL_ONE_SHOT_ALLOWED_SYMBOL,
        "allowed_environment": CANONICAL_ONE_SHOT_ALLOWED_ENVIRONMENT,
        "allowed_order_type": CANONICAL_ONE_SHOT_ALLOWED_ORDER_TYPE,
        "allowed_time_in_force": CANONICAL_ONE_SHOT_ALLOWED_TIME_IN_FORCE,
        "tiny_qty_step_sol": str(bh.TINY_QTY_STEP_SOL),
        "tiny_qty_cap_sol": str(bh.TINY_QTY_CAP_SOL),
        "tiny_size_cap_usdt": str(bh.TINY_SIZE_CAP_USDT),
        "real_order_authorization_marker_name": "EXPLICIT_REAL_DEMO_ORDER_AUTHORIZATION_MARKER",
        "cap_escalation_authorization_marker_name": "EXPLICIT_DEMO_MIN_QTY_AUTHORIZATION_MARKER",
        "cap_escalation_authorized": False,
        "real_order_authorized": False,
        "modules": [
            "src.demo_only_tiny_execution_adapter",
            "src.demo_only_tiny_execution_adapter_tiny_order_instrument_rules",
            "src.demo_only_tiny_execution_adapter_tiny_order_cap_escalation_gate",
            "src.demo_only_tiny_execution_adapter_tiny_order_authorized_execution_qty_wiring",
            "src.demo_only_tiny_execution_adapter_tiny_order_one_shot_authorized_execution_orchestrator",
            "src.demo_only_tiny_execution_adapter_single_real_demo_order",
        ],
    }


# ---------------------------------------------------------------------------
# Canonical action fingerprint
# ---------------------------------------------------------------------------


def action_fingerprint(
    action: Any, *, pilot_id: str, date: str, forward_fingerprint: str | None,
) -> str:
    """Stable PLANNING-candidate identity (run date / pilot / symbol / side /
    intent / reduce_only / canonical qty display / notional / source ref /
    forward fingerprint). For human review reference only -- it never authorizes
    or addresses a real order."""
    payload = "|".join([
        TASK_ID, str(date), str(pilot_id),
        str(getattr(action, "symbol", "")), str(getattr(action, "side", "")),
        str(getattr(action, "intent", "")), str(getattr(action, "reduce_only", "")),
        str(getattr(action, "qty", "")), str(getattr(action, "notional_usdt", "")),
        str(getattr(action, "source_reference", "")), str(forward_fingerprint or ""),
    ])
    return "sha256:" + hashlib.sha256(payload.encode("utf-8")).hexdigest()


# ---------------------------------------------------------------------------
# Authoritative instrument-rule evidence (NEVER inferred from action qty)
# ---------------------------------------------------------------------------


def build_rule_evidence(raw_evidence: dict[str, Any] | None) -> dict[str, Any]:
    """Normalise an authoritative instrument-rule evidence dict from the provider
    into the audited review form. ``qty_step`` and all numeric rule fields come
    from the real ``InstrumentRules`` snapshot; nothing is inferred from a
    quantity string."""
    ev = dict(raw_evidence or {})
    status = ev.get("rule_status", RULE_MISSING)
    out: dict[str, Any] = {
        "symbol": ev.get("symbol"),
        "rule_status": status,
        "qty_step_source": "INSTRUMENT_RULE_PROVIDER",
        "qty_step_inferred_from_action": False,
        "instrument_rule_source": ev.get("instrument_rule_source"),
        "market_price_source": ev.get("market_price_source"),
        "market_price_snapshot": _format_decimal(ev.get("market_price")),
        "qty_step": _format_decimal(ev.get("qty_step")),
        "min_qty": _format_decimal(ev.get("min_qty")),
        "max_qty": _format_decimal(ev.get("max_qty")),
        "min_notional": _format_decimal(ev.get("min_notional")),
        "tick_size": _format_decimal(ev.get("tick_size")),
    }
    if status == "TRADING" and out["qty_step"] is not None:
        fp_input = "|".join([
            str(out["symbol"]), str(out["qty_step"]), str(out["min_qty"]),
            str(out["max_qty"]), str(out["tick_size"]), str(out["min_notional"]),
            str(status),
        ])
        out["instrument_rule_fingerprint"] = "sha256:" + hashlib.sha256(
            fp_input.encode("utf-8")).hexdigest()
        out["candidate_rule_validation_status"] = RULE_VALID_DELEGATION_REQUIRED
    else:
        out["instrument_rule_fingerprint"] = None
        out["candidate_rule_validation_status"] = {
            "MISSING": RULE_MISSING, "NON_TRADING": RULE_NON_TRADING,
            "MALFORMED": RULE_MALFORMED,
        }.get(status, RULE_MISSING)
    return out


# ---------------------------------------------------------------------------
# Execution-review gate result (NON-dispatching)
# ---------------------------------------------------------------------------


@dataclass
class ExecutionGateResult:
    raw_planned_action_count: int
    eligible_execution_candidate_count: int
    existing_open_position_count: int
    existing_protected_position_count: int
    simultaneous_position_policy_status: str
    multi_action_send_refused: bool
    # Planning candidate (review only).
    requested_symbol: str | None
    requested_side: str | None
    planning_candidate_fingerprint: str | None
    strategy_target_notional_usdt: str | None
    execution_candidate_eligible: bool
    # Delegation invariants (always non-dispatching here).
    execution_delegation_status: str
    canonical_one_shot_adapter_required: bool
    canonical_execution_packet_present: bool
    execution_authorized: bool
    execution_ready: bool
    sender_reachable: bool
    # Caps / policy / rule evidence.
    effective_per_order_notional_cap_usdt: str
    effective_daily_new_opening_notional_cap_usdt: str
    tiny_execution_cap_usdt: str
    cap_compliance_status: str
    rule_evidence: dict[str, Any] | None
    effective_policy: dict[str, Any]
    policy_sources: list[dict[str, Any]]
    canonical_one_shot_references: dict[str, Any]
    refusal_reasons: list[str]
    final_execution_authorization_status: str
    detail: str = ""

    @property
    def authorized(self) -> bool:
        return False  # this gate NEVER authorizes a dispatch

    @property
    def plan_valid(self) -> bool:
        return self.final_execution_authorization_status != EXECUTION_NOT_AUTHORIZED_PLAN_INVALID

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": TASK_ID,
            "raw_planned_action_count": self.raw_planned_action_count,
            "eligible_execution_candidate_count": self.eligible_execution_candidate_count,
            "existing_open_position_count": self.existing_open_position_count,
            "existing_protected_position_count": self.existing_protected_position_count,
            "simultaneous_position_policy_status": self.simultaneous_position_policy_status,
            "multi_action_send_refused": self.multi_action_send_refused,
            "requested_symbol": self.requested_symbol,
            "requested_side": self.requested_side,
            "planning_candidate_fingerprint": self.planning_candidate_fingerprint,
            "strategy_target_notional_usdt": self.strategy_target_notional_usdt,
            "execution_candidate_eligible": self.execution_candidate_eligible,
            "execution_delegation_status": self.execution_delegation_status,
            "canonical_one_shot_adapter_required": self.canonical_one_shot_adapter_required,
            "canonical_execution_packet_present": self.canonical_execution_packet_present,
            "execution_authorized": self.execution_authorized,
            "execution_ready": self.execution_ready,
            "sender_reachable": self.sender_reachable,
            "effective_per_order_notional_cap_usdt": self.effective_per_order_notional_cap_usdt,
            "effective_daily_new_opening_notional_cap_usdt": self.effective_daily_new_opening_notional_cap_usdt,
            "tiny_execution_cap_usdt": self.tiny_execution_cap_usdt,
            "cap_compliance_status": self.cap_compliance_status,
            "rule_evidence": self.rule_evidence,
            "effective_policy": self.effective_policy,
            "policy_sources": self.policy_sources,
            "canonical_one_shot_references": self.canonical_one_shot_references,
            "refusal_reasons": list(self.refusal_reasons),
            "final_execution_authorization_status": self.final_execution_authorization_status,
            "detail": self.detail,
        }


def _is_opening_eligible(action: Any) -> bool:
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


def _rule_evidence_from_provider(rule_provider: Any, symbol: str) -> dict[str, Any] | None:
    """Pull AUTHORITATIVE instrument-rule evidence for ``symbol`` from the
    provider. The provider owns the real ``InstrumentRules`` snapshot; this gate
    never infers any rule from a quantity string."""
    if rule_provider is None:
        return None
    if hasattr(rule_provider, "instrument_rule_evidence"):
        try:
            return rule_provider.instrument_rule_evidence(symbol)
        except Exception:  # noqa: BLE001
            return None
    return None


def evaluate_execution_gate(
    *,
    plan: Any,
    open_positions: Sequence[Any],
    pilot_id: str,
    date: str,
    forward_fingerprint: str | None = None,
    rule_provider: Any = None,
    effective_policy: EffectivePolicy | None = None,
) -> ExecutionGateResult:
    """Produce a NON-dispatching execution review. The native daily surface uses
    this only to show that the full V1 plan is planning output and that any real
    Demo execution is delegated to the canonical one-shot tiny adapter. It never
    authorizes, builds, or addresses a real order.
    """
    policy = effective_policy or resolve_effective_policy()
    tiny_cap = policy.per_order_notional_cap_usdt
    refusal_reasons: list[str] = []

    plan_available = bool(getattr(plan, "available", False))
    sizing_verified = bool((getattr(plan, "sizing_verification", {}) or {}).get("verified", False))
    actions = list(getattr(plan, "actions", []) or [])
    raw_count = len(actions)

    open_list = list(open_positions or [])
    existing_open_count = len(open_list)
    existing_protected = [p for p in open_list
                          if str(getattr(p, "symbol", "")).strip().upper() in PROTECTED_SYMBOLS]
    existing_protected_count = len(existing_protected)

    eligible = [a for a in actions if _is_opening_eligible(a)]
    eligible_count = len(eligible)
    # Canonical one-shot allowlist: SOLUSDT only.
    allowlisted = [a for a in eligible
                   if str(getattr(a, "symbol", "")).strip().upper() == CANONICAL_ONE_SHOT_ALLOWED_SYMBOL]

    base_kwargs: dict[str, Any] = dict(
        raw_planned_action_count=raw_count,
        eligible_execution_candidate_count=eligible_count,
        existing_open_position_count=existing_open_count,
        existing_protected_position_count=existing_protected_count,
        canonical_one_shot_adapter_required=True,
        canonical_execution_packet_present=False,
        execution_authorized=False,
        execution_ready=False,
        sender_reachable=False,
        effective_per_order_notional_cap_usdt=_format_decimal(tiny_cap),
        effective_daily_new_opening_notional_cap_usdt=_format_decimal(
            policy.daily_new_opening_notional_cap_usdt),
        tiny_execution_cap_usdt=_format_decimal(tiny_cap),
        effective_policy=policy.to_dict(),
        policy_sources=policy_source_inventory(),
        canonical_one_shot_references=canonical_one_shot_references(),
    )

    # --- Plan validity (fail closed) --------------------------------------
    if not plan_available or not sizing_verified:
        return ExecutionGateResult(
            **base_kwargs,
            simultaneous_position_policy_status=SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED
            if existing_protected_count else SIM_POLICY_WITHIN_LIMIT,
            multi_action_send_refused=raw_count > 1,
            requested_symbol=None, requested_side=None, planning_candidate_fingerprint=None,
            strategy_target_notional_usdt=None, execution_candidate_eligible=False,
            execution_delegation_status=EXECUTION_NOT_AUTHORIZED_PLAN_INVALID,
            cap_compliance_status="PLAN_INVALID", rule_evidence=None,
            refusal_reasons=[EXECUTION_NOT_AUTHORIZED_PLAN_INVALID],
            final_execution_authorization_status=EXECUTION_NOT_AUTHORIZED_PLAN_INVALID,
            detail="planner output is not a valid verified V1 plan; execution review refused")

    # --- Simultaneous-position / protected legacy resolution --------------
    sim_status = SIM_POLICY_WITHIN_LIMIT
    if policy.conflict:
        refusal_reasons.append(POLICY_CONFLICT_REQUIRES_REVIEW)
    if existing_protected_count > 0 and not policy.protected_legacy_exclusion_defined:
        sim_status = SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED
        refusal_reasons.append(NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS)
    elif existing_open_count >= policy.max_simultaneous_open_positions and existing_open_count > 0:
        sim_status = SIM_POLICY_AT_OR_OVER_LIMIT
        refusal_reasons.append(NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS
                               if existing_protected_count else POLICY_CONFLICT_REQUIRES_REVIEW)

    multi_action_send_refused = raw_count > 1

    # --- Identify the (review-only) planning candidate --------------------
    requested_symbol: str | None = None
    requested_side: str | None = None
    planning_fp: str | None = None
    target_notional: str | None = None
    rule_valid_candidate = False
    rule_evidence: dict[str, Any] | None = None
    cap_compliance_status = "NO_CANDIDATE"

    if len(allowlisted) == 1:
        cand = allowlisted[0]
        requested_symbol = str(getattr(cand, "symbol", "")).strip().upper()
        requested_side = str(getattr(cand, "side", ""))
        planning_fp = action_fingerprint(cand, pilot_id=pilot_id, date=date,
                                         forward_fingerprint=forward_fingerprint)
        target_notional = _format_decimal(getattr(cand, "notional_usdt", None))
        raw_ev = _rule_evidence_from_provider(rule_provider, requested_symbol)
        rule_evidence = build_rule_evidence(raw_ev) if raw_ev is not None else build_rule_evidence(
            {"symbol": requested_symbol, "rule_status": "MISSING"})
        rstatus = rule_evidence.get("candidate_rule_validation_status")
        if rstatus == RULE_VALID_DELEGATION_REQUIRED:
            rule_valid_candidate = True
            cap_compliance_status = ("TARGET_EXCEEDS_TINY_CAP"
                                     if (target_notional and Decimal(target_notional) > tiny_cap)
                                     else "TARGET_WITHIN_TINY_CAP")
        else:
            refusal_reasons.append(rstatus)
            cap_compliance_status = "RULE_INVALID"
    else:
        # No SOLUSDT candidate. If there ARE eligible non-SOL V1 symbols, they are
        # planning-only and explicitly unsupported by the canonical adapter.
        if eligible:
            first = eligible[0]
            requested_symbol = str(getattr(first, "symbol", "")).strip().upper()
            requested_side = str(getattr(first, "side", ""))
            target_notional = _format_decimal(getattr(first, "notional_usdt", None))
        refusal_reasons.append(SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER)
        cap_compliance_status = "SYMBOL_UNSUPPORTED"

    # --- Final status -----------------------------------------------------
    seen: set[str] = set()
    refusal_reasons = [r for r in refusal_reasons if not (r in seen or seen.add(r))]
    final_status = _resolve_final_status(refusal_reasons, rule_valid_candidate)
    # A candidate is execution-eligible ONLY when the gate resolves to the clean
    # delegation status (rule valid, symbol supported, no protected-position block,
    # no policy conflict). Any blocker fails closed -> not eligible.
    candidate_eligible = final_status == EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER
    # The native surface ALWAYS delegates; the detailed review status is surfaced
    # here. CANONICAL_ONE_SHOT_EXECUTION_PACKET_REQUIRED only when cleanly eligible.
    delegation_status = (CANONICAL_ONE_SHOT_EXECUTION_PACKET_REQUIRED if candidate_eligible
                         else final_status)

    return ExecutionGateResult(
        **base_kwargs,
        simultaneous_position_policy_status=sim_status,
        multi_action_send_refused=multi_action_send_refused,
        requested_symbol=requested_symbol, requested_side=requested_side,
        planning_candidate_fingerprint=planning_fp,
        strategy_target_notional_usdt=target_notional,
        execution_candidate_eligible=candidate_eligible,
        execution_delegation_status=delegation_status,
        cap_compliance_status=cap_compliance_status, rule_evidence=rule_evidence,
        refusal_reasons=refusal_reasons,
        final_execution_authorization_status=final_status,
        detail=("review only: the full V1 plan is planning output; real Demo execution is "
                "delegated to the canonical one-shot tiny adapter. No order is dispatched here."))


def _resolve_final_status(refusal_reasons: list[str], candidate_eligible: bool) -> str:
    if not refusal_reasons:
        # A clean, rule-valid, allowlisted candidate still only DELEGATES.
        return (EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER if candidate_eligible
                else SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER)
    priority = [
        POLICY_CONFLICT_REQUIRES_REVIEW,
        NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS,
        SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER,
        RULE_MISSING, RULE_NON_TRADING, RULE_MALFORMED,
        EXECUTION_NOT_AUTHORIZED_PLAN_INVALID,
    ]
    for status in priority:
        if status in refusal_reasons:
            return status
    return refusal_reasons[0]


__all__ = [
    "TASK_ID", "PROTECTED_SYMBOLS",
    "CANONICAL_ONE_SHOT_ALLOWED_SYMBOL", "CANONICAL_REAL_ORDER_AUTHORIZATION_MARKER",
    "CANONICAL_CAP_ESCALATION_AUTHORIZATION_MARKER",
    "EXECUTION_DELEGATED_TO_CANONICAL_ONE_SHOT_ADAPTER",
    "CANONICAL_ONE_SHOT_EXECUTION_PACKET_REQUIRED",
    "EXECUTION_NOT_AUTHORIZED_PLAN_INVALID",
    "NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS",
    "POLICY_CONFLICT_REQUIRES_REVIEW",
    "SYMBOL_NOT_SUPPORTED_BY_CANONICAL_ONE_SHOT_ADAPTER",
    "RULE_MISSING", "RULE_NON_TRADING", "RULE_MALFORMED",
    "SIM_POLICY_PROTECTED_EXCLUSION_UNDEFINED", "SIM_POLICY_WITHIN_LIMIT",
    "SIM_POLICY_AT_OR_OVER_LIMIT",
    "EffectivePolicy", "resolve_effective_policy", "policy_source_inventory",
    "canonical_one_shot_references", "ExecutionGateResult", "evaluate_execution_gate",
    "action_fingerprint", "build_rule_evidence", "has_float_artifact", "is_exact_multiple",
]
