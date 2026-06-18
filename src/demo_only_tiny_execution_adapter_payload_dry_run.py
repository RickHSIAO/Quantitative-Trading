"""TASK-014BI — demo-only tiny execution adapter payload dry-run.

Offline dry-run layer for the TASK-014BH demo-only tiny execution
adapter implementation path. Exercises the BH payload builder with a
table of realistic SOLUSDT tiny payload cases (happy paths + every
guard rejection) and emits a structured JSON + Markdown proof report.

Implementation-path successor — NOT a review-chain suffix:

    BH (scaffold) -> BI (offline payload dry-run) -> next:
    TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration
    (or equivalent final demo-only pre-execution checklist).

Hard safety invariants (cross-checked by tests):
    * No network library import (no ``requests`` / ``urllib`` /
      ``http`` / ``socket`` / ``ssl`` / ``pybit`` / ``websocket`` /
      ``aiohttp`` / ``httpx``).
    * No environment-variable / secret read.
    * No reference to ``BybitExecutor`` / live executor wiring.
    * No call to any exchange endpoint.
    * Does not import ``main`` or ``src.risk``.
    * Re-uses the BH payload builder directly — no parallel
      implementation, no relaxed guard.
"""

from __future__ import annotations

import dataclasses
import datetime as _dt
import json
import pathlib
from dataclasses import asdict, dataclass, field
from decimal import Decimal
from typing import Any, Mapping, Sequence

from src import demo_only_tiny_execution_adapter as bh

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BI"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-PAYLOAD-DRY-RUN"
IMPLEMENTATION_PATH_PHASE = "offline_payload_dry_run"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASK = "TASK-014BH"
NEXT_REQUIRED_TASK = (
    "TASK-014BJ_demo_only_tiny_execution_adapter_endpoint_guard_integration"
)
REPORT_NAME = "demo_only_tiny_execution_adapter_payload_dry_run"
DEFAULT_OUTPUT_DIR = (
    pathlib.Path("outputs/demo_trading")
    / REPORT_NAME
)


# ---------------------------------------------------------------------------
# Case definition
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class DryRunCase:
    """A single offline payload dry-run case."""

    case_id: str
    description: str
    kwargs: Mapping[str, Any]
    expected: str  # "built" or "rejected"
    expected_rejection_substring: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "kwargs": {k: _jsonify(v) for k, v in self.kwargs.items()},
            "expected": self.expected,
            "expected_rejection_substring": self.expected_rejection_substring,
        }


@dataclass(frozen=True)
class DryRunOutcome:
    """Result of executing one DryRunCase."""

    case_id: str
    description: str
    expected: str
    actual: str  # "built" / "rejected" / "unexpected_exception"
    matches_expectation: bool
    rejection_reason: str = ""
    rejection_substring_matched: bool = False
    payload_audit: Mapping[str, Any] | None = None

    def to_dict(self) -> dict[str, Any]:
        return {
            "case_id": self.case_id,
            "description": self.description,
            "expected": self.expected,
            "actual": self.actual,
            "matches_expectation": self.matches_expectation,
            "rejection_reason": self.rejection_reason,
            "rejection_substring_matched": self.rejection_substring_matched,
            "payload_audit": dict(self.payload_audit) if self.payload_audit else None,
        }


@dataclass(frozen=True)
class DryRunReport:
    """Aggregate report across all dry-run cases."""

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
    total_cases: int
    built_cases: int
    rejected_cases: int
    unexpected_outcomes: int
    all_match_expectation: bool
    generated_at_utc: str
    outcomes: tuple[DryRunOutcome, ...] = field(default_factory=tuple)

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
            "total_cases": self.total_cases,
            "built_cases": self.built_cases,
            "rejected_cases": self.rejected_cases,
            "unexpected_outcomes": self.unexpected_outcomes,
            "all_match_expectation": self.all_match_expectation,
            "generated_at_utc": self.generated_at_utc,
            "outcomes": [o.to_dict() for o in self.outcomes],
        }


# ---------------------------------------------------------------------------
# Canonical case table
# ---------------------------------------------------------------------------


def default_cases() -> tuple[DryRunCase, ...]:
    """Canonical set of offline dry-run cases.

    Covers happy paths (Buy / Sell) and every BH guard rejection path,
    plus the explicit non-SOL symbols required by the BI workorder
    (BTCUSDT, ETHUSDT).
    """

    return (
        DryRunCase(
            case_id="bi_case_01_solusdt_buy_tiny",
            description="valid SOLUSDT Buy 0.01 @ mark 100 (notional 1.0 USDT)",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.01",
                "mark_price": "100",
            },
            expected="built",
        ),
        DryRunCase(
            case_id="bi_case_02_solusdt_sell_tiny",
            description="valid SOLUSDT Sell 0.02 @ mark 200 (notional 4.0 USDT)",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Sell",
                "qty": "0.02",
                "mark_price": "200",
            },
            expected="built",
        ),
        DryRunCase(
            case_id="bi_case_03_solusdt_qty_cap_edge",
            description="SOLUSDT Buy 0.05 @ mark 50 (qty at cap; notional 2.5 USDT)",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.05",
                "mark_price": "50",
            },
            expected="built",
        ),
        DryRunCase(
            case_id="bi_case_04_solusdt_no_mark_price",
            description="SOLUSDT Buy 0.01 with no mark_price (qty-only cap check)",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="built",
        ),
        DryRunCase(
            case_id="bi_case_05_qty_above_cap",
            description="SOLUSDT Buy 0.10 (qty above 0.05 SOL cap) — REJECT",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.10",
            },
            expected="rejected",
            expected_rejection_substring="tiny cap",
        ),
        DryRunCase(
            case_id="bi_case_06_qty_zero",
            description="SOLUSDT Buy 0 (zero qty) — REJECT",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0",
            },
            expected="rejected",
            expected_rejection_substring="must be positive",
        ),
        DryRunCase(
            case_id="bi_case_07_notional_above_cap",
            description="SOLUSDT Buy 0.05 @ mark 150 (notional 7.5 USDT > 5 USDT) — REJECT",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.05",
                "mark_price": "150",
            },
            expected="rejected",
            expected_rejection_substring="exceeds tiny size cap",
        ),
        DryRunCase(
            case_id="bi_case_08_btcusdt_rejected",
            description="BTCUSDT Buy — REJECT (only SOLUSDT allowed)",
            kwargs={
                "symbol": "BTCUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="only 'SOLUSDT'",
        ),
        DryRunCase(
            case_id="bi_case_09_ethusdt_rejected",
            description="ETHUSDT Buy — REJECT (only SOLUSDT allowed)",
            kwargs={
                "symbol": "ETHUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="only 'SOLUSDT'",
        ),
        DryRunCase(
            case_id="bi_case_10_protected_enausdt",
            description="ENAUSDT as entry symbol — REJECT (protected)",
            kwargs={
                "symbol": "ENAUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="protected position",
        ),
        DryRunCase(
            case_id="bi_case_11_protected_tiausdt",
            description="TIAUSDT as entry symbol — REJECT (protected)",
            kwargs={
                "symbol": "TIAUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="protected position",
        ),
        DryRunCase(
            case_id="bi_case_12_protected_aixbtusdt",
            description="AIXBTUSDT as entry symbol — REJECT (protected)",
            kwargs={
                "symbol": "AIXBTUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="protected position",
        ),
        DryRunCase(
            case_id="bi_case_13_protected_polyxusdt",
            description="POLYXUSDT as entry symbol — REJECT (protected)",
            kwargs={
                "symbol": "POLYXUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="protected position",
        ),
        DryRunCase(
            case_id="bi_case_14_protected_eduusdt",
            description="EDUUSDT as entry symbol — REJECT (protected)",
            kwargs={
                "symbol": "EDUUSDT",
                "side": "Buy",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="protected position",
        ),
        DryRunCase(
            case_id="bi_case_15_protected_in_existing",
            description="SOLUSDT Buy with ENAUSDT in existing_positions — REJECT",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.01",
                "existing_positions": ("ENAUSDT", "ADAUSDT"),
            },
            expected="rejected",
            expected_rejection_substring="protected positions present in scope",
        ),
        DryRunCase(
            case_id="bi_case_16_non_demo_environment",
            description="SOLUSDT Buy with environment=bybit_live — REJECT",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.01",
                "environment": "bybit_live",
            },
            expected="rejected",
            expected_rejection_substring="environment 'bybit_live' not allowed",
        ),
        DryRunCase(
            case_id="bi_case_17_unknown_side",
            description="SOLUSDT side=Hold — REJECT",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Hold",
                "qty": "0.01",
            },
            expected="rejected",
            expected_rejection_substring="side 'Hold' not allowed",
        ),
        DryRunCase(
            case_id="bi_case_18_custom_order_link_id_missing_prefix",
            description="SOLUSDT Buy with arbitrary order_link_id — REJECT",
            kwargs={
                "symbol": "SOLUSDT",
                "side": "Buy",
                "qty": "0.01",
                "order_link_id": "ARBITRARY_ID",
            },
            expected="rejected",
            expected_rejection_substring="must start with 'DEMO_ONLY_TINY_BH_'",
        ),
    )


LIVE_ENDPOINT_CASES: tuple[tuple[str, str], ...] = (
    ("https://api.bybit.com", "live root host"),
    ("https://api.bybit.com/v5/order/create", "live order endpoint"),
    ("https://api.bytick.com/v5/order/create", "live mirror order endpoint"),
    ("wss://stream.bybit.com/v5/public/linear", "live websocket stream"),
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _jsonify(value: Any) -> Any:
    if isinstance(value, (str, int, float, bool)) or value is None:
        return value
    if isinstance(value, Decimal):
        return format(value, "f")
    if isinstance(value, (tuple, list)):
        return [_jsonify(v) for v in value]
    if isinstance(value, dict):
        return {k: _jsonify(v) for k, v in value.items()}
    return str(value)


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


# ---------------------------------------------------------------------------
# Core run
# ---------------------------------------------------------------------------


def _execute_case(case: DryRunCase) -> DryRunOutcome:
    try:
        payload = bh.build_demo_only_tiny_solusdt_entry_payload(**case.kwargs)
    except bh.DemoOnlyTinyExecutionAdapterError as exc:
        reason = str(exc)
        matched_substr = (
            case.expected_rejection_substring in reason
            if case.expected_rejection_substring
            else True
        )
        return DryRunOutcome(
            case_id=case.case_id,
            description=case.description,
            expected=case.expected,
            actual="rejected",
            matches_expectation=(case.expected == "rejected" and matched_substr),
            rejection_reason=reason,
            rejection_substring_matched=matched_substr,
        )
    except Exception as exc:  # pragma: no cover — defensive
        return DryRunOutcome(
            case_id=case.case_id,
            description=case.description,
            expected=case.expected,
            actual="unexpected_exception",
            matches_expectation=False,
            rejection_reason=f"{type(exc).__name__}: {exc}",
        )
    return DryRunOutcome(
        case_id=case.case_id,
        description=case.description,
        expected=case.expected,
        actual="built",
        matches_expectation=(case.expected == "built"),
        payload_audit=payload.to_audit_dict(),
    )


def _verify_live_endpoints_denied() -> tuple[DryRunOutcome, ...]:
    outcomes: list[DryRunOutcome] = []
    for idx, (url, label) in enumerate(LIVE_ENDPOINT_CASES, start=1):
        case_id = f"bi_live_endpoint_{idx:02d}"
        description = f"live endpoint denied: {label} ({url})"
        try:
            bh.assert_endpoint_is_demo_only(url)
        except bh.LiveEndpointDenied as exc:
            outcomes.append(
                DryRunOutcome(
                    case_id=case_id,
                    description=description,
                    expected="rejected",
                    actual="rejected",
                    matches_expectation=True,
                    rejection_reason=str(exc),
                    rejection_substring_matched=True,
                )
            )
        else:
            outcomes.append(
                DryRunOutcome(
                    case_id=case_id,
                    description=description,
                    expected="rejected",
                    actual="built",
                    matches_expectation=False,
                    rejection_reason="LIVE ENDPOINT WAS NOT DENIED — SAFETY FAILURE",
                )
            )
    return tuple(outcomes)


def run_dry_run(
    cases: Sequence[DryRunCase] | None = None,
) -> DryRunReport:
    """Execute every dry-run case offline and return a `DryRunReport`."""

    bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

    case_tuple = tuple(cases) if cases is not None else default_cases()
    outcomes = tuple(_execute_case(c) for c in case_tuple)
    outcomes = outcomes + _verify_live_endpoints_denied()

    built = sum(1 for o in outcomes if o.actual == "built")
    rejected = sum(1 for o in outcomes if o.actual == "rejected")
    unexpected = sum(1 for o in outcomes if not o.matches_expectation)

    return DryRunReport(
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
        total_cases=len(outcomes),
        built_cases=built,
        rejected_cases=rejected,
        unexpected_outcomes=unexpected,
        all_match_expectation=(unexpected == 0),
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        outcomes=outcomes,
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _render_markdown(report: DryRunReport) -> str:
    lines: list[str] = []
    lines.append(f"# {report.task_id} — {report.identity}")
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
    lines.append(f"- bh_allowed_environment: `{report.bh_allowed_environment}`")
    lines.append(f"- bh_allowed_symbol: `{report.bh_allowed_symbol}`")
    lines.append(
        f"- bh_protected_symbols: `{', '.join(report.bh_protected_symbols)}`"
    )
    lines.append(f"- bh_tiny_size_cap_usdt: `{report.bh_tiny_size_cap_usdt}`")
    lines.append(f"- bh_tiny_qty_cap_sol: `{report.bh_tiny_qty_cap_sol}`")
    lines.append(
        f"- bh_live_endpoint_denylist: `{', '.join(report.bh_live_endpoint_denylist)}`"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total_cases: `{report.total_cases}`")
    lines.append(f"- built_cases: `{report.built_cases}`")
    lines.append(f"- rejected_cases: `{report.rejected_cases}`")
    lines.append(f"- unexpected_outcomes: `{report.unexpected_outcomes}`")
    lines.append(f"- all_match_expectation: `{report.all_match_expectation}`")
    lines.append("")
    lines.append("## Outcomes")
    lines.append("")
    lines.append(
        "| case_id | expected | actual | matches | description | rejection_reason |"
    )
    lines.append("|---|---|---|---|---|---|")
    for o in report.outcomes:
        rr = o.rejection_reason.replace("|", "\\|") if o.rejection_reason else ""
        desc = o.description.replace("|", "\\|")
        lines.append(
            f"| `{o.case_id}` | `{o.expected}` | `{o.actual}` | "
            f"`{o.matches_expectation}` | {desc} | {rr} |"
        )
    lines.append("")
    lines.append(
        "_offline payload dry-run — no order sent, no endpoint called, "
        "no secret read; BH payload builder consumed directly._"
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: DryRunReport,
    output_dir: pathlib.Path | str | None = None,
) -> dict[str, pathlib.Path]:
    """Write JSON + Markdown report (latest_* + timestamped) and return paths."""

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
    "DEFAULT_OUTPUT_DIR",
    "DryRunCase",
    "DryRunOutcome",
    "DryRunReport",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "LIVE_ENDPOINT_CASES",
    "NEXT_REQUIRED_TASK",
    "REPORT_NAME",
    "TASK_ID",
    "UPSTREAM_TASK",
    "default_cases",
    "run_dry_run",
    "write_report",
]
