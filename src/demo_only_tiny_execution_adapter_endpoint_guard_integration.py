"""TASK-014BJ -- demo-only tiny execution adapter endpoint guard integration.

Future-safe single integration entry point for the demo-only tiny
execution adapter implementation path. Wraps every TASK-014BH guard
plus the optional endpoint-target live-denylist check into one call
(``integrate_demo_only_tiny_request``) so that future demo-only call
sites cannot bypass any safety guard by reaching for the BH primitives
piecemeal.

Implementation-path successor -- NOT a review-chain suffix:

    BH (scaffold) -> BI (offline payload dry-run) -> BJ (endpoint guard
    integration) -> next: TASK-014BK_demo_only_tiny_execution_adapter
    _final_pre_execution_checklist (or equivalent explicit demo-only
    tiny order preparation task).

Hard safety invariants (cross-checked by tests):
    * No network library import (no ``requests`` / ``urllib`` /
      ``http`` / ``socket`` / ``ssl`` / ``pybit`` / ``websocket`` /
      ``aiohttp`` / ``httpx``).
    * No environment-variable / secret read.
    * No reference to ``BybitExecutor`` / live executor wiring.
    * No call to any exchange endpoint -- the optional
      ``endpoint_target`` is *validated only* against BH's static live
      denylist; this module never opens a connection.
    * Does not import ``main`` or ``src.risk``.
    * Re-uses the BH payload builder and BH guard helpers directly --
      no parallel implementation, no relaxed guard, no weakened
      denylist.
"""

from __future__ import annotations

import datetime as _dt
import json
import pathlib
from dataclasses import dataclass, field
from typing import Any, Mapping, Sequence

from src import demo_only_tiny_execution_adapter as bh

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BJ"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-ENDPOINT-GUARD-INTEGRATION"
IMPLEMENTATION_PATH_PHASE = "endpoint_guard_integration"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASK = "TASK-014BI"
NEXT_REQUIRED_TASK = (
    "TASK-014BK_demo_only_tiny_execution_adapter_final_pre_execution_checklist"
)

REPORT_NAME = "demo_only_tiny_execution_adapter_endpoint_guard_integration"
DEFAULT_OUTPUT_DIR = (
    pathlib.Path("outputs/demo_trading") / REPORT_NAME
)

BJ_AUDIT_RESPONSE_STATUS_NOT_SENT = "DEMO_ONLY_TINY_BJ_NOT_SENT"
INTEGRATION_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_endpoint_guard_integration_v1"
)

GUARD_STEPS: tuple[str, ...] = (
    "environment",
    "symbol",
    "existing_positions",
    "side",
    "qty_cap",
    "notional_cap",
    "order_link_id_prefix",
    "endpoint_target",
)


# ---------------------------------------------------------------------------
# Exceptions
# ---------------------------------------------------------------------------


class GuardIntegrationError(bh.DemoOnlyTinyExecutionAdapterError):
    """Raised when an integration request fails any guard step.

    Inherits from BH's base exception so existing BH-aware callers
    continue to recognise it as a rejection.
    """


# ---------------------------------------------------------------------------
# Request / decision / result dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntegrationRequest:
    """A single offline demo-only tiny request to be guard-integrated."""

    symbol: str
    side: str
    qty: str
    environment: str = bh.ALLOWED_ENVIRONMENT
    mark_price: str | None = None
    existing_positions: tuple[str, ...] = ()
    order_link_id: str | None = None
    endpoint_target: str | None = None
    note: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "symbol": self.symbol,
            "side": self.side,
            "qty": self.qty,
            "environment": self.environment,
            "mark_price": self.mark_price,
            "existing_positions": list(self.existing_positions),
            "order_link_id": self.order_link_id,
            "endpoint_target": self.endpoint_target,
            "note": self.note,
        }


@dataclass(frozen=True)
class GuardDecision:
    """Outcome of a single guard step inside the integration pipeline."""

    step: str
    passed: bool
    reason: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "step": self.step,
            "passed": self.passed,
            "reason": self.reason,
        }


@dataclass(frozen=True)
class IntegrationResult:
    """Single integration outcome: built payload + decisions OR rejection."""

    ok: bool
    request: IntegrationRequest
    decisions: tuple[GuardDecision, ...]
    rejection_step: str = ""
    rejection_reason: str = ""
    payload_audit: Mapping[str, Any] | None = None
    endpoint_target_validated: bool = False
    bj_audit_response_status: str = BJ_AUDIT_RESPONSE_STATUS_NOT_SENT
    integration_contract_version: str = INTEGRATION_CONTRACT_VERSION

    def to_dict(self) -> dict[str, Any]:
        return {
            "ok": self.ok,
            "request": self.request.to_dict(),
            "decisions": [d.to_dict() for d in self.decisions],
            "rejection_step": self.rejection_step,
            "rejection_reason": self.rejection_reason,
            "payload_audit": (
                dict(self.payload_audit) if self.payload_audit else None
            ),
            "endpoint_target_validated": self.endpoint_target_validated,
            "bj_audit_response_status": self.bj_audit_response_status,
            "integration_contract_version": self.integration_contract_version,
        }


# ---------------------------------------------------------------------------
# Core integration entry point
# ---------------------------------------------------------------------------


def _check(step: str, fn) -> GuardDecision:
    try:
        fn()
    except bh.DemoOnlyTinyExecutionAdapterError as exc:
        return GuardDecision(step=step, passed=False, reason=str(exc))
    return GuardDecision(step=step, passed=True)


def integrate_demo_only_tiny_request(
    request: IntegrationRequest,
) -> IntegrationResult:
    """Run every BH guard step plus endpoint-target validation in order.

    This is the single future-safe entry point. Call sites that route
    through this function cannot bypass:
        * bybit_demo-only environment
        * SOLUSDT-only symbol
        * protected-symbols denylist (both for the entry symbol and for
          any symbol present in ``existing_positions``)
        * tiny qty / notional cap
        * order_link_id BH-prefix requirement
        * live endpoint denylist (when ``endpoint_target`` is provided)

    The function never sends, never opens a connection, never reads a
    secret. On success it returns an ``IntegrationResult`` whose
    ``payload_audit`` is the BH adapter audit dict (already marked
    ``DEMO_ONLY_TINY_BH_NOT_SENT``) plus the BJ NOT_SENT marker.
    """

    bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

    decisions: list[GuardDecision] = []

    # 1. environment
    decisions.append(
        _check(
            "environment",
            lambda: bh.assert_environment_is_demo(request.environment),
        )
    )
    if not decisions[-1].passed:
        return _rejection(request, decisions)

    # 2. symbol (protected + SOLUSDT-only)
    decisions.append(
        _check(
            "symbol",
            lambda: bh.assert_symbol_is_allowed(request.symbol),
        )
    )
    if not decisions[-1].passed:
        return _rejection(request, decisions)

    # 3. existing positions
    decisions.append(
        _check(
            "existing_positions",
            lambda: bh.assert_no_protected_position_in_scope(
                request.existing_positions
            ),
        )
    )
    if not decisions[-1].passed:
        return _rejection(request, decisions)

    # 4. side
    decisions.append(
        _check(
            "side",
            lambda: bh.assert_side_is_allowed(request.side),
        )
    )
    if not decisions[-1].passed:
        return _rejection(request, decisions)

    # 5. qty cap (uses Decimal via str -> bh)
    from decimal import Decimal  # local import: stdlib only, no network

    qty_dec = Decimal(str(request.qty))
    decisions.append(
        _check(
            "qty_cap",
            lambda: bh.assert_qty_under_tiny_cap(qty_dec),
        )
    )
    if not decisions[-1].passed:
        return _rejection(request, decisions)

    # 6. notional cap (only when mark_price provided)
    if request.mark_price is not None:
        mark_dec = Decimal(str(request.mark_price))
        decisions.append(
            _check(
                "notional_cap",
                lambda: bh.assert_notional_under_tiny_cap(qty_dec, mark_dec),
            )
        )
        if not decisions[-1].passed:
            return _rejection(request, decisions)
    else:
        decisions.append(
            GuardDecision(
                step="notional_cap",
                passed=True,
                reason="skipped (mark_price not provided)",
            )
        )

    # 7. order_link_id prefix -- BH builder enforces this; pre-check
    #    here so we can surface a clean reason without raising.
    link_id = request.order_link_id or (
        f"{bh.ORDER_LINK_ID_PREFIX}{request.symbol}_OFFLINE_BUILD"
    )
    if not link_id.startswith(bh.ORDER_LINK_ID_PREFIX):
        decisions.append(
            GuardDecision(
                step="order_link_id_prefix",
                passed=False,
                reason=(
                    f"order_link_id {link_id!r} must start with "
                    f"{bh.ORDER_LINK_ID_PREFIX!r}"
                ),
            )
        )
        return _rejection(request, decisions)
    decisions.append(GuardDecision(step="order_link_id_prefix", passed=True))

    # 8. endpoint target (optional) -- live denylist check
    endpoint_validated = False
    if request.endpoint_target is not None:
        decisions.append(
            _check(
                "endpoint_target",
                lambda: bh.assert_endpoint_is_demo_only(request.endpoint_target),
            )
        )
        if not decisions[-1].passed:
            return _rejection(request, decisions)
        endpoint_validated = True
    else:
        decisions.append(
            GuardDecision(
                step="endpoint_target",
                passed=True,
                reason="skipped (endpoint_target not provided)",
            )
        )

    # All guards passed: build the BH payload offline.
    payload = bh.build_demo_only_tiny_solusdt_entry_payload(
        symbol=request.symbol,
        side=request.side,
        qty=request.qty,
        mark_price=request.mark_price,
        environment=request.environment,
        existing_positions=request.existing_positions,
        order_link_id=request.order_link_id,
    )

    audit = dict(payload.to_audit_dict())
    audit["_demo_only_bj_audit_response_status"] = BJ_AUDIT_RESPONSE_STATUS_NOT_SENT
    audit["_demo_only_bj_integration_contract_version"] = (
        INTEGRATION_CONTRACT_VERSION
    )
    audit["_demo_only_bj_endpoint_target_validated"] = endpoint_validated
    audit["_demo_only_bj_endpoint_target"] = request.endpoint_target

    return IntegrationResult(
        ok=True,
        request=request,
        decisions=tuple(decisions),
        payload_audit=audit,
        endpoint_target_validated=endpoint_validated,
    )


def _rejection(
    request: IntegrationRequest,
    decisions: list[GuardDecision],
) -> IntegrationResult:
    failing = decisions[-1]
    return IntegrationResult(
        ok=False,
        request=request,
        decisions=tuple(decisions),
        rejection_step=failing.step,
        rejection_reason=failing.reason,
        payload_audit=None,
        endpoint_target_validated=False,
    )


# ---------------------------------------------------------------------------
# Canonical integration cases (for the dry-run report)
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntegrationCase:
    """One canonical integration request + expected outcome."""

    case_id: str
    description: str
    request: IntegrationRequest
    expected: str  # "ok" / "rejected"
    expected_rejection_step: str = ""
    expected_rejection_substring: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "request": self.request.to_dict(),
            "expected": self.expected,
            "expected_rejection_step": self.expected_rejection_step,
            "expected_rejection_substring": self.expected_rejection_substring,
        }


def default_integration_cases() -> tuple[IntegrationCase, ...]:
    """Canonical set covering every required BJ workorder scenario."""

    demo_endpoint = "https://api-demo.bybit.com/v5/order/create"

    return (
        IntegrationCase(
            case_id="bj_case_01_solusdt_buy_with_demo_endpoint",
            description=(
                "valid SOLUSDT Buy 0.01 @ mark 100 with demo endpoint target"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
                mark_price="100",
                endpoint_target=demo_endpoint,
                note="happy path with explicit demo endpoint",
            ),
            expected="ok",
        ),
        IntegrationCase(
            case_id="bj_case_02_solusdt_sell_no_endpoint",
            description="valid SOLUSDT Sell 0.02 @ mark 200, no endpoint",
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Sell",
                qty="0.02",
                mark_price="200",
            ),
            expected="ok",
        ),
        IntegrationCase(
            case_id="bj_case_03_btcusdt_rejected",
            description="BTCUSDT entry -- REJECT (only SOLUSDT allowed)",
            request=IntegrationRequest(
                symbol="BTCUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="symbol",
            expected_rejection_substring="only 'SOLUSDT'",
        ),
        IntegrationCase(
            case_id="bj_case_04_ethusdt_rejected",
            description="ETHUSDT entry -- REJECT (only SOLUSDT allowed)",
            request=IntegrationRequest(
                symbol="ETHUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="symbol",
            expected_rejection_substring="only 'SOLUSDT'",
        ),
        IntegrationCase(
            case_id="bj_case_05_protected_enausdt",
            description="ENAUSDT entry -- REJECT (protected)",
            request=IntegrationRequest(
                symbol="ENAUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="symbol",
            expected_rejection_substring="protected position",
        ),
        IntegrationCase(
            case_id="bj_case_06_protected_tiausdt",
            description="TIAUSDT entry -- REJECT (protected)",
            request=IntegrationRequest(
                symbol="TIAUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="symbol",
            expected_rejection_substring="protected position",
        ),
        IntegrationCase(
            case_id="bj_case_07_protected_aixbtusdt",
            description="AIXBTUSDT entry -- REJECT (protected)",
            request=IntegrationRequest(
                symbol="AIXBTUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="symbol",
            expected_rejection_substring="protected position",
        ),
        IntegrationCase(
            case_id="bj_case_08_protected_polyxusdt",
            description="POLYXUSDT entry -- REJECT (protected)",
            request=IntegrationRequest(
                symbol="POLYXUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="symbol",
            expected_rejection_substring="protected position",
        ),
        IntegrationCase(
            case_id="bj_case_09_protected_eduusdt",
            description="EDUUSDT entry -- REJECT (protected)",
            request=IntegrationRequest(
                symbol="EDUUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="symbol",
            expected_rejection_substring="protected position",
        ),
        IntegrationCase(
            case_id="bj_case_10_protected_in_existing_positions",
            description=(
                "SOLUSDT Buy with TIAUSDT in existing_positions -- REJECT"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
                existing_positions=("TIAUSDT", "ADAUSDT"),
            ),
            expected="rejected",
            expected_rejection_step="existing_positions",
            expected_rejection_substring="protected positions present in scope",
        ),
        IntegrationCase(
            case_id="bj_case_11_bybit_live_environment_rejected",
            description="environment=bybit_live -- REJECT",
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
                environment="bybit_live",
            ),
            expected="rejected",
            expected_rejection_step="environment",
            expected_rejection_substring="environment 'bybit_live' not allowed",
        ),
        IntegrationCase(
            case_id="bj_case_12_live_endpoint_root_rejected",
            description="endpoint_target=api.bybit.com root -- REJECT",
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
                endpoint_target="https://api.bybit.com",
            ),
            expected="rejected",
            expected_rejection_step="endpoint_target",
            expected_rejection_substring="live denylist",
        ),
        IntegrationCase(
            case_id="bj_case_13_live_order_endpoint_rejected",
            description=(
                "endpoint_target=api.bybit.com/v5/order/create -- REJECT"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
                endpoint_target="https://api.bybit.com/v5/order/create",
            ),
            expected="rejected",
            expected_rejection_step="endpoint_target",
            expected_rejection_substring="live denylist",
        ),
        IntegrationCase(
            case_id="bj_case_14_live_websocket_endpoint_rejected",
            description=(
                "endpoint_target=wss://stream.bybit.com/v5/public/linear -- REJECT"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
                endpoint_target="wss://stream.bybit.com/v5/public/linear",
            ),
            expected="rejected",
            expected_rejection_step="endpoint_target",
            expected_rejection_substring="live denylist",
        ),
        IntegrationCase(
            case_id="bj_case_15_qty_cap_fail",
            description="SOLUSDT Buy 0.10 (qty above 0.05 SOL cap) -- REJECT",
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.10",
            ),
            expected="rejected",
            expected_rejection_step="qty_cap",
            expected_rejection_substring="tiny cap",
        ),
        IntegrationCase(
            case_id="bj_case_16_notional_cap_fail",
            description=(
                "SOLUSDT Buy 0.05 @ mark 150 (notional 7.5 USDT > 5 USDT) -- REJECT"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.05",
                mark_price="150",
            ),
            expected="rejected",
            expected_rejection_step="notional_cap",
            expected_rejection_substring="exceeds tiny size cap",
        ),
        IntegrationCase(
            case_id="bj_case_17_unknown_side_rejected",
            description="SOLUSDT side=Hold -- REJECT",
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Hold",
                qty="0.01",
            ),
            expected="rejected",
            expected_rejection_step="side",
            expected_rejection_substring="side 'Hold' not allowed",
        ),
        IntegrationCase(
            case_id="bj_case_18_custom_order_link_id_missing_prefix",
            description=(
                "SOLUSDT Buy with arbitrary order_link_id -- REJECT"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
                order_link_id="ARBITRARY_ID_NO_PREFIX",
            ),
            expected="rejected",
            expected_rejection_step="order_link_id_prefix",
            expected_rejection_substring="must start with",
        ),
        IntegrationCase(
            case_id="bj_case_19_solusdt_qty_cap_edge_with_demo_endpoint",
            description=(
                "SOLUSDT Buy 0.05 @ mark 50 (qty at cap; notional 2.5 USDT)"
                " with demo endpoint target"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.05",
                mark_price="50",
                endpoint_target=demo_endpoint,
            ),
            expected="ok",
        ),
        IntegrationCase(
            case_id="bj_case_20_solusdt_buy_no_mark_price",
            description=(
                "SOLUSDT Buy 0.01 with no mark_price"
                " (notional check skipped)"
            ),
            request=IntegrationRequest(
                symbol="SOLUSDT",
                side="Buy",
                qty="0.01",
            ),
            expected="ok",
        ),
    )


# ---------------------------------------------------------------------------
# Aggregate report
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class IntegrationOutcome:
    """Per-case outcome inside the aggregate report."""

    case_id: str
    description: str
    expected: str
    actual: str
    matches_expectation: bool
    rejection_step: str = ""
    rejection_reason: str = ""
    rejection_substring_matched: bool = False
    payload_audit: Mapping[str, Any] | None = None
    decisions: tuple[GuardDecision, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "expected": self.expected,
            "actual": self.actual,
            "matches_expectation": self.matches_expectation,
            "rejection_step": self.rejection_step,
            "rejection_reason": self.rejection_reason,
            "rejection_substring_matched": self.rejection_substring_matched,
            "payload_audit": (
                dict(self.payload_audit) if self.payload_audit else None
            ),
            "decisions": [d.to_dict() for d in self.decisions],
        }


@dataclass(frozen=True)
class IntegrationReport:
    task_id: str
    identity: str
    phase: str
    upstream_task: str
    next_required_task: str
    is_review_chain_suffix: bool
    bh_identity: str
    bh_adapter_contract_version: str
    bh_allowed_environment: str
    bh_allowed_symbol: str
    bh_protected_symbols: tuple[str, ...]
    bh_tiny_size_cap_usdt: str
    bh_tiny_qty_cap_sol: str
    bh_live_endpoint_denylist: tuple[str, ...]
    bj_integration_contract_version: str
    bj_audit_response_status_not_sent: str
    total_cases: int
    ok_cases: int
    rejected_cases: int
    unexpected_outcomes: int
    all_match_expectation: bool
    generated_at_utc: str
    outcomes: tuple[IntegrationOutcome, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "upstream_task": self.upstream_task,
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "bh_identity": self.bh_identity,
            "bh_adapter_contract_version": self.bh_adapter_contract_version,
            "bh_allowed_environment": self.bh_allowed_environment,
            "bh_allowed_symbol": self.bh_allowed_symbol,
            "bh_protected_symbols": list(self.bh_protected_symbols),
            "bh_tiny_size_cap_usdt": self.bh_tiny_size_cap_usdt,
            "bh_tiny_qty_cap_sol": self.bh_tiny_qty_cap_sol,
            "bh_live_endpoint_denylist": list(self.bh_live_endpoint_denylist),
            "bj_integration_contract_version": (
                self.bj_integration_contract_version
            ),
            "bj_audit_response_status_not_sent": (
                self.bj_audit_response_status_not_sent
            ),
            "total_cases": self.total_cases,
            "ok_cases": self.ok_cases,
            "rejected_cases": self.rejected_cases,
            "unexpected_outcomes": self.unexpected_outcomes,
            "all_match_expectation": self.all_match_expectation,
            "generated_at_utc": self.generated_at_utc,
            "outcomes": [o.to_dict() for o in self.outcomes],
        }


def _execute_case(case: IntegrationCase) -> IntegrationOutcome:
    result = integrate_demo_only_tiny_request(case.request)
    if result.ok:
        actual = "ok"
        matches = case.expected == "ok"
        return IntegrationOutcome(
            case_id=case.case_id,
            description=case.description,
            expected=case.expected,
            actual=actual,
            matches_expectation=matches,
            payload_audit=result.payload_audit,
            decisions=result.decisions,
        )
    matched_substr = (
        case.expected_rejection_substring in result.rejection_reason
        if case.expected_rejection_substring
        else True
    )
    matched_step = (
        result.rejection_step == case.expected_rejection_step
        if case.expected_rejection_step
        else True
    )
    matches = (
        case.expected == "rejected"
        and matched_substr
        and matched_step
    )
    return IntegrationOutcome(
        case_id=case.case_id,
        description=case.description,
        expected=case.expected,
        actual="rejected",
        matches_expectation=matches,
        rejection_step=result.rejection_step,
        rejection_reason=result.rejection_reason,
        rejection_substring_matched=matched_substr,
        decisions=result.decisions,
    )


def run_integration_dry_run(
    cases: Sequence[IntegrationCase] | None = None,
) -> IntegrationReport:
    """Run every canonical case offline and return an ``IntegrationReport``."""

    bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

    case_tuple = (
        tuple(cases) if cases is not None else default_integration_cases()
    )
    outcomes = tuple(_execute_case(c) for c in case_tuple)

    ok_count = sum(1 for o in outcomes if o.actual == "ok")
    rejected_count = sum(1 for o in outcomes if o.actual == "rejected")
    unexpected = sum(1 for o in outcomes if not o.matches_expectation)

    return IntegrationReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_task=UPSTREAM_TASK,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        bh_identity=bh.IDENTITY,
        bh_adapter_contract_version=bh.ADAPTER_CONTRACT_VERSION,
        bh_allowed_environment=bh.ALLOWED_ENVIRONMENT,
        bh_allowed_symbol=bh.ALLOWED_SYMBOL,
        bh_protected_symbols=tuple(sorted(bh.PROTECTED_SYMBOLS)),
        bh_tiny_size_cap_usdt=format(bh.TINY_SIZE_CAP_USDT, "f"),
        bh_tiny_qty_cap_sol=format(bh.TINY_QTY_CAP_SOL, "f"),
        bh_live_endpoint_denylist=tuple(sorted(bh.LIVE_ENDPOINT_DENYLIST)),
        bj_integration_contract_version=INTEGRATION_CONTRACT_VERSION,
        bj_audit_response_status_not_sent=BJ_AUDIT_RESPONSE_STATUS_NOT_SENT,
        total_cases=len(outcomes),
        ok_cases=ok_count,
        rejected_cases=rejected_count,
        unexpected_outcomes=unexpected,
        all_match_expectation=(unexpected == 0),
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        outcomes=outcomes,
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(report: IntegrationReport) -> str:
    lines: list[str] = []
    lines.append(f"# {report.task_id} -- {report.identity}")
    lines.append("")
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(f"- upstream_task: `{report.upstream_task}`")
    lines.append(f"- next_required_task: `{report.next_required_task}`")
    lines.append(f"- is_review_chain_suffix: `{report.is_review_chain_suffix}`")
    lines.append("")
    lines.append("## BH upstream identity")
    lines.append("")
    lines.append(f"- bh_identity: `{report.bh_identity}`")
    lines.append(
        f"- bh_adapter_contract_version: `{report.bh_adapter_contract_version}`"
    )
    lines.append(
        f"- bh_allowed_environment: `{report.bh_allowed_environment}`"
    )
    lines.append(f"- bh_allowed_symbol: `{report.bh_allowed_symbol}`")
    lines.append(
        f"- bh_protected_symbols: `{', '.join(report.bh_protected_symbols)}`"
    )
    lines.append(
        f"- bh_tiny_size_cap_usdt: `{report.bh_tiny_size_cap_usdt}`"
    )
    lines.append(f"- bh_tiny_qty_cap_sol: `{report.bh_tiny_qty_cap_sol}`")
    lines.append(
        f"- bh_live_endpoint_denylist: "
        f"`{', '.join(report.bh_live_endpoint_denylist)}`"
    )
    lines.append("")
    lines.append("## BJ integration identity")
    lines.append("")
    lines.append(
        f"- bj_integration_contract_version: "
        f"`{report.bj_integration_contract_version}`"
    )
    lines.append(
        f"- bj_audit_response_status_not_sent: "
        f"`{report.bj_audit_response_status_not_sent}`"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total_cases: `{report.total_cases}`")
    lines.append(f"- ok_cases: `{report.ok_cases}`")
    lines.append(f"- rejected_cases: `{report.rejected_cases}`")
    lines.append(
        f"- unexpected_outcomes: `{report.unexpected_outcomes}`"
    )
    lines.append(
        f"- all_match_expectation: `{report.all_match_expectation}`"
    )
    lines.append("")
    lines.append("## Outcomes")
    lines.append("")
    lines.append(
        "| case_id | expected | actual | matches | rejection_step "
        "| description | rejection_reason |"
    )
    lines.append("|---|---|---|---|---|---|---|")
    for o in report.outcomes:
        rr = o.rejection_reason.replace("|", "\\|") if o.rejection_reason else ""
        desc = o.description.replace("|", "\\|")
        lines.append(
            f"| `{o.case_id}` | `{o.expected}` | `{o.actual}` | "
            f"`{o.matches_expectation}` | `{o.rejection_step}` | "
            f"{desc} | {rr} |"
        )
    lines.append("")
    lines.append(
        "_offline endpoint guard integration -- no order sent, no endpoint "
        "called, no secret read; BH adapter consumed directly._"
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: IntegrationReport,
    output_dir: pathlib.Path | str | None = None,
) -> dict[str, pathlib.Path]:
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
    "BJ_AUDIT_RESPONSE_STATUS_NOT_SENT",
    "DEFAULT_OUTPUT_DIR",
    "GUARD_STEPS",
    "GuardDecision",
    "GuardIntegrationError",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "INTEGRATION_CONTRACT_VERSION",
    "IS_REVIEW_CHAIN_SUFFIX",
    "IntegrationCase",
    "IntegrationOutcome",
    "IntegrationReport",
    "IntegrationRequest",
    "IntegrationResult",
    "NEXT_REQUIRED_TASK",
    "REPORT_NAME",
    "TASK_ID",
    "UPSTREAM_TASK",
    "default_integration_cases",
    "integrate_demo_only_tiny_request",
    "run_integration_dry_run",
    "write_report",
]
