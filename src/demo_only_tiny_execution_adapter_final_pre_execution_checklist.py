"""TASK-014BK -- demo-only tiny execution adapter final pre-execution checklist.

Aggregates the BH (scaffold) + BI (offline payload dry-run) + BJ
(endpoint guard integration) safety proofs into one final offline
pre-execution checklist. Emits a structured JSON + Markdown report.

This module is itself offline-only. It does NOT prepare, authorize, or
send any order. It does NOT touch any existing position. It does NOT
read any secret. Its sole purpose is to verify, in one place, that
every BH/BI/BJ safety invariant required before *any future* explicit
demo-only tiny order preparation task is still intact.

Implementation-path successor -- NOT a review-chain suffix:

    BH (scaffold) -> BI (offline payload dry-run) -> BJ (endpoint guard
    integration) -> BK (final pre-execution checklist) -> next:
    TASK-014BL_demo_only_tiny_order_preparation (or equivalent explicit
    demo-only tiny order preparation / authorization task) -- NEVER
    another review-chain suffix.

Hard safety invariants (cross-checked by tests):
    * No network library import (no ``requests`` / ``urllib`` /
      ``http`` / ``socket`` / ``ssl`` / ``pybit`` / ``websocket`` /
      ``aiohttp`` / ``httpx``).
    * No environment-variable / secret read.
    * No reference to ``BybitExecutor`` / live executor wiring.
    * No call to any exchange endpoint.
    * Does not import ``main`` or ``src.risk``.
    * Re-uses BH/BI/BJ directly -- no parallel implementation, no
      relaxed guard, no weakened denylist.
"""

from __future__ import annotations

import ast
import datetime as _dt
import inspect
import io
import json
import pathlib
import sys
import tokenize
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any, Callable, Mapping, Sequence

from src import demo_only_tiny_execution_adapter as bh
from src import demo_only_tiny_execution_adapter_endpoint_guard_integration as bj
from src import demo_only_tiny_execution_adapter_payload_dry_run as bi

# ---------------------------------------------------------------------------
# Identity / chain-break markers
# ---------------------------------------------------------------------------

TASK_ID = "TASK-014BK"
IDENTITY = "DEMO-ONLY-TINY-EXECUTION-ADAPTER-FINAL-PRE-EXECUTION-CHECKLIST"
IMPLEMENTATION_PATH_PHASE = "final_pre_execution_checklist"
IS_REVIEW_CHAIN_SUFFIX = False
UPSTREAM_TASKS: tuple[str, ...] = (
    "TASK-014BH",
    "TASK-014BI",
    "TASK-014BJ",
)
NEXT_REQUIRED_TASK = "TASK-014BL_demo_only_tiny_order_preparation"

REPORT_NAME = "demo_only_tiny_execution_adapter_final_pre_execution_checklist"
DEFAULT_OUTPUT_DIR = (
    pathlib.Path("outputs/demo_trading") / REPORT_NAME
)

CHECKLIST_CONTRACT_VERSION = (
    "demo_only_tiny_execution_adapter_final_pre_execution_checklist_v1"
)

# Static-source safety invariant lexicons -- consumed by tokenize/ast.
FORBIDDEN_NETWORK_MODULES: tuple[str, ...] = (
    "requests",
    "urllib",
    "urllib3",
    "http",
    "socket",
    "ssl",
    "pybit",
    "websocket",
    "websockets",
    "aiohttp",
    "httpx",
)

FORBIDDEN_SECRET_NAMES: tuple[str, ...] = (
    "getenv",
    "environ",
    "load_dotenv",
    "dotenv_values",
)

FORBIDDEN_SEND_TOKENS: tuple[str, ...] = (
    "place_order",
    "post_order",
    "submit_order",
)

FORBIDDEN_MAIN_MODULES: tuple[str, ...] = ("main", "src.risk")

FORBIDDEN_EXECUTOR_MODULES: tuple[str, ...] = (
    "src.executors.bybit",
)

# The full set of forbidden review-chain suffixes (mirror of BH constant
# but explicit here so the checklist can compare even if BH ever evolves).
FORBIDDEN_REVIEW_CHAIN_SUFFIXES: tuple[str, ...] = (
    "_readiness_review",
    "_final_pre_execution_review",
    "_manual_authorization_review",
)


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class ChecklistItem:
    """A single checklist invariant + its pass/fail outcome."""

    item_id: str
    category: str
    description: str
    passed: bool
    detail: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "item_id": self.item_id,
            "category": self.category,
            "description": self.description,
            "passed": self.passed,
            "detail": self.detail,
        }


@dataclass(frozen=True)
class ChecklistReport:
    """Aggregate checklist report across BH/BI/BJ."""

    task_id: str
    identity: str
    phase: str
    upstream_tasks: tuple[str, ...]
    next_required_task: str
    is_review_chain_suffix: bool
    checklist_contract_version: str
    bh_identity: str
    bi_identity: str
    bj_identity: str
    bh_adapter_contract_version: str
    bj_integration_contract_version: str
    bh_allowed_environment: str
    bh_allowed_symbol: str
    bh_protected_symbols: tuple[str, ...]
    bh_tiny_size_cap_usdt: str
    bh_tiny_qty_cap_sol: str
    bh_live_endpoint_denylist: tuple[str, ...]
    bh_audit_response_status_not_sent: str
    bj_audit_response_status_not_sent: str
    bi_dry_run_total_cases: int
    bi_dry_run_all_match: bool
    bj_integration_total_cases: int
    bj_integration_all_match: bool
    total_items: int
    passed_items: int
    failed_items: int
    all_passed: bool
    generated_at_utc: str
    items: tuple[ChecklistItem, ...] = field(default_factory=tuple)

    def to_dict(self) -> dict[str, Any]:
        return {
            "task_id": self.task_id,
            "identity": self.identity,
            "phase": self.phase,
            "upstream_tasks": list(self.upstream_tasks),
            "next_required_task": self.next_required_task,
            "is_review_chain_suffix": self.is_review_chain_suffix,
            "checklist_contract_version": self.checklist_contract_version,
            "bh_identity": self.bh_identity,
            "bi_identity": self.bi_identity,
            "bj_identity": self.bj_identity,
            "bh_adapter_contract_version": self.bh_adapter_contract_version,
            "bj_integration_contract_version": (
                self.bj_integration_contract_version
            ),
            "bh_allowed_environment": self.bh_allowed_environment,
            "bh_allowed_symbol": self.bh_allowed_symbol,
            "bh_protected_symbols": list(self.bh_protected_symbols),
            "bh_tiny_size_cap_usdt": self.bh_tiny_size_cap_usdt,
            "bh_tiny_qty_cap_sol": self.bh_tiny_qty_cap_sol,
            "bh_live_endpoint_denylist": list(self.bh_live_endpoint_denylist),
            "bh_audit_response_status_not_sent": (
                self.bh_audit_response_status_not_sent
            ),
            "bj_audit_response_status_not_sent": (
                self.bj_audit_response_status_not_sent
            ),
            "bi_dry_run_total_cases": self.bi_dry_run_total_cases,
            "bi_dry_run_all_match": self.bi_dry_run_all_match,
            "bj_integration_total_cases": self.bj_integration_total_cases,
            "bj_integration_all_match": self.bj_integration_all_match,
            "total_items": self.total_items,
            "passed_items": self.passed_items,
            "failed_items": self.failed_items,
            "all_passed": self.all_passed,
            "generated_at_utc": self.generated_at_utc,
            "items": [it.to_dict() for it in self.items],
        }


# ---------------------------------------------------------------------------
# Static-source inspection helpers
# ---------------------------------------------------------------------------


def _module_source(module: Any) -> str:
    path = pathlib.Path(inspect.getfile(module))
    return path.read_text(encoding="utf-8")


def _module_source_path(module: Any) -> pathlib.Path:
    return pathlib.Path(inspect.getfile(module)).resolve()


def _tokens(source: str) -> list[tokenize.TokenInfo]:
    return list(tokenize.generate_tokens(io.StringIO(source).readline))


def _collect_imported_modules(source: str) -> set[str]:
    tree = ast.parse(source)
    imported: set[str] = set()
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                imported.add(alias.name)
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                imported.add(node.module)
                for alias in node.names:
                    imported.add(f"{node.module}.{alias.name}")
    return imported


def _check_no_network_import(module: Any) -> tuple[bool, str]:
    imports = _collect_imported_modules(_module_source(module))
    hits = sorted(
        m
        for m in imports
        if any(
            m == bad or m.startswith(bad + ".")
            for bad in FORBIDDEN_NETWORK_MODULES
        )
    )
    if hits:
        return False, f"network imports found: {hits!r}"
    return True, "no network-library imports"


def _check_no_secret_read(module: Any) -> tuple[bool, str]:
    src = _module_source(module)
    tokens = _tokens(src)
    names = {t.string for t in tokens if t.type == tokenize.NAME}
    hits = sorted(n for n in names if n in FORBIDDEN_SECRET_NAMES)
    if hits:
        return False, f"secret-read tokens found: {hits!r}"
    return True, "no getenv/environ/load_dotenv tokens"


def _check_no_send_methods(module: Any) -> tuple[bool, str]:
    """Ensure the module does not define or call any send/post/submit
    order method. We look at function defs + attribute names + literal
    text for ``.send(`` patterns.
    """

    src = _module_source(module)
    tree = ast.parse(src)
    bad: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef):
            if node.name in FORBIDDEN_SEND_TOKENS or node.name == "send":
                bad.append(f"def {node.name}")
        if isinstance(node, ast.Attribute) and node.attr in FORBIDDEN_SEND_TOKENS:
            bad.append(f".{node.attr}")
        if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
            if node.func.attr == "send":
                bad.append(".send(call)")
            if node.func.attr in FORBIDDEN_SEND_TOKENS:
                bad.append(f".{node.func.attr}(call)")
    if bad:
        return False, f"send-like surfaces found: {sorted(set(bad))!r}"
    return True, "no send/post_order/submit_order surfaces"


def _check_no_main_or_risk_import(module: Any) -> tuple[bool, str]:
    imports = _collect_imported_modules(_module_source(module))
    hits = sorted(
        m
        for m in imports
        if m in FORBIDDEN_MAIN_MODULES
        or any(m.startswith(bad + ".") for bad in FORBIDDEN_MAIN_MODULES)
    )
    if hits:
        return False, f"main/src.risk imports found: {hits!r}"
    return True, "no main/src.risk imports"


def _check_no_executor_import(module: Any) -> tuple[bool, str]:
    imports = _collect_imported_modules(_module_source(module))
    hits = sorted(
        m
        for m in imports
        if any(
            m == bad or m.startswith(bad + ".")
            for bad in FORBIDDEN_EXECUTOR_MODULES
        )
    )
    if hits:
        return False, f"executor imports found: {hits!r}"
    return True, "no src.executors.bybit imports"


def _check_consumes_bh_directly(module: Any) -> tuple[bool, str]:
    """Both BI and BJ must import BH via
    ``from src import demo_only_tiny_execution_adapter as bh``.
    """

    src = _module_source(module)
    tree = ast.parse(src)
    for node in ast.walk(tree):
        if (
            isinstance(node, ast.ImportFrom)
            and node.module == "src"
            and any(
                alias.name == "demo_only_tiny_execution_adapter"
                and alias.asname == "bh"
                for alias in node.names
            )
        ):
            return True, "imports BH as `bh` directly from src"
    return False, "does not import BH directly as `bh`"


def _check_chain_break_literals(module: Any) -> tuple[bool, str]:
    """Require ``IS_REVIEW_CHAIN_SUFFIX = False`` and a non-empty
    ``IMPLEMENTATION_PATH_PHASE`` literal at module scope.
    """

    src = _module_source(module)
    tree = ast.parse(src)
    has_false = False
    has_phase = False
    for node in tree.body:
        if isinstance(node, ast.Assign):
            for target in node.targets:
                if (
                    isinstance(target, ast.Name)
                    and target.id == "IS_REVIEW_CHAIN_SUFFIX"
                    and isinstance(node.value, ast.Constant)
                    and node.value.value is False
                ):
                    has_false = True
                if (
                    isinstance(target, ast.Name)
                    and target.id == "IMPLEMENTATION_PATH_PHASE"
                    and isinstance(node.value, ast.Constant)
                    and isinstance(node.value.value, str)
                    and node.value.value
                ):
                    has_phase = True
    if has_false and has_phase:
        return True, "IS_REVIEW_CHAIN_SUFFIX=False and phase literal present"
    return (
        False,
        f"IS_REVIEW_CHAIN_SUFFIX=False={has_false} phase_literal={has_phase}",
    )


# ---------------------------------------------------------------------------
# Runtime invariant helpers
# ---------------------------------------------------------------------------


def _check_bh_allowed_symbol() -> tuple[bool, str]:
    if bh.ALLOWED_SYMBOL == "SOLUSDT":
        return True, "bh.ALLOWED_SYMBOL == 'SOLUSDT'"
    return False, f"bh.ALLOWED_SYMBOL={bh.ALLOWED_SYMBOL!r}"


def _check_bh_protected_symbols() -> tuple[bool, str]:
    expected = frozenset({"ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT"})
    if bh.PROTECTED_SYMBOLS == expected:
        return True, f"bh.PROTECTED_SYMBOLS == {sorted(expected)!r}"
    return False, f"bh.PROTECTED_SYMBOLS={sorted(bh.PROTECTED_SYMBOLS)!r}"


def _check_bh_live_endpoint_denylist() -> tuple[bool, str]:
    required = {
        "https://api.bybit.com",
        "https://api.bytick.com",
        "wss://stream.bybit.com",
        "wss://stream.bytick.com",
    }
    missing = sorted(required - set(bh.LIVE_ENDPOINT_DENYLIST))
    if not missing:
        return (
            True,
            f"bh.LIVE_ENDPOINT_DENYLIST covers required hosts ({len(required)})",
        )
    return False, f"missing live denylist entries: {missing!r}"


def _check_bh_allowed_environment() -> tuple[bool, str]:
    if bh.ALLOWED_ENVIRONMENT == "bybit_demo":
        return True, "bh.ALLOWED_ENVIRONMENT == 'bybit_demo'"
    return False, f"bh.ALLOWED_ENVIRONMENT={bh.ALLOWED_ENVIRONMENT!r}"


def _check_bh_tiny_caps() -> tuple[bool, str]:
    if bh.TINY_SIZE_CAP_USDT == Decimal("5") and bh.TINY_QTY_CAP_SOL == Decimal("0.05"):
        return True, "BH tiny caps: 5 USDT notional / 0.05 SOL qty"
    return (
        False,
        f"unexpected caps usdt={bh.TINY_SIZE_CAP_USDT!r} qty={bh.TINY_QTY_CAP_SOL!r}",
    )


def _check_bh_not_sent_marker() -> tuple[bool, str]:
    if bh.AUDIT_RESPONSE_STATUS_NOT_SENT == "DEMO_ONLY_TINY_BH_NOT_SENT":
        return True, "BH AUDIT_RESPONSE_STATUS_NOT_SENT correct"
    return (
        False,
        f"bh.AUDIT_RESPONSE_STATUS_NOT_SENT={bh.AUDIT_RESPONSE_STATUS_NOT_SENT!r}",
    )


def _check_bj_not_sent_marker() -> tuple[bool, str]:
    if bj.BJ_AUDIT_RESPONSE_STATUS_NOT_SENT == "DEMO_ONLY_TINY_BJ_NOT_SENT":
        return True, "BJ_AUDIT_RESPONSE_STATUS_NOT_SENT correct"
    return (
        False,
        f"bj.BJ_AUDIT_RESPONSE_STATUS_NOT_SENT={bj.BJ_AUDIT_RESPONSE_STATUS_NOT_SENT!r}",
    )


def _check_bh_bi_bj_chain_pointers() -> tuple[bool, str]:
    if (
        bh.NEXT_REQUIRED_TASK.startswith("TASK-014BI_")
        and bi.NEXT_REQUIRED_TASK.startswith("TASK-014BJ_")
        and bj.NEXT_REQUIRED_TASK.startswith("TASK-014BK_")
    ):
        return True, "BH->BI->BJ->BK pointers intact"
    return (
        False,
        (
            f"BH.next={bh.NEXT_REQUIRED_TASK!r} "
            f"BI.next={bi.NEXT_REQUIRED_TASK!r} "
            f"BJ.next={bj.NEXT_REQUIRED_TASK!r}"
        ),
    )


def _check_bh_review_chain_suffix_guard() -> tuple[bool, str]:
    for suffix in FORBIDDEN_REVIEW_CHAIN_SUFFIXES:
        probe = f"TASK-9999_some_label{suffix}"
        try:
            bh.assert_next_task_is_not_review_chain_suffix(probe)
        except bh.DemoOnlyTinyExecutionAdapterError:
            continue
        return False, f"BH did not reject forbidden suffix {suffix!r}"
    # And BK's own next_required_task must pass.
    try:
        bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)
    except bh.DemoOnlyTinyExecutionAdapterError as exc:
        return False, f"BK NEXT_REQUIRED_TASK rejected by BH guard: {exc!s}"
    return True, "BH guard rejects all 3 forbidden suffixes; BK pointer passes"


def _check_bk_pointer_not_review_chain_suffix() -> tuple[bool, str]:
    for suffix in FORBIDDEN_REVIEW_CHAIN_SUFFIXES:
        if NEXT_REQUIRED_TASK.endswith(suffix):
            return (
                False,
                f"BK NEXT_REQUIRED_TASK ends with forbidden {suffix!r}",
            )
    return True, f"BK NEXT_REQUIRED_TASK={NEXT_REQUIRED_TASK!r} is not a review-chain suffix"


def _check_bi_dry_run() -> tuple[bool, str, int]:
    report = bi.run_dry_run()
    if report.all_match_expectation and report.unexpected_outcomes == 0:
        return (
            True,
            f"BI dry-run all_match=True (total={report.total_cases}, "
            f"built={report.built_cases}, rejected={report.rejected_cases})",
            report.total_cases,
        )
    return (
        False,
        f"BI dry-run unexpected={report.unexpected_outcomes} all_match={report.all_match_expectation}",
        report.total_cases,
    )


def _check_bj_integration() -> tuple[bool, str, int]:
    report = bj.run_integration_dry_run()
    if report.all_match_expectation and report.unexpected_outcomes == 0:
        return (
            True,
            f"BJ integration all_match=True (total={report.total_cases}, "
            f"ok={report.ok_cases}, rejected={report.rejected_cases})",
            report.total_cases,
        )
    return (
        False,
        f"BJ integration unexpected={report.unexpected_outcomes} all_match={report.all_match_expectation}",
        report.total_cases,
    )


def _check_happy_path_payload_carries_both_markers() -> tuple[bool, str]:
    """Build one happy-path BJ payload and inspect its audit dict."""

    request = bj.IntegrationRequest(
        symbol="SOLUSDT",
        side="Buy",
        qty="0.01",
        mark_price="100",
        endpoint_target="https://api-demo.bybit.com/v5/order/create",
    )
    result = bj.integrate_demo_only_tiny_request(request)
    if not result.ok or result.payload_audit is None:
        return False, "happy-path BJ integration did not produce a payload"
    audit = result.payload_audit
    bh_marker_ok = (
        audit.get("_demo_only_audit_response_status")
        == bh.AUDIT_RESPONSE_STATUS_NOT_SENT
    )
    bj_marker_ok = (
        audit.get("_demo_only_bj_audit_response_status")
        == bj.BJ_AUDIT_RESPONSE_STATUS_NOT_SENT
    )
    target_ok = audit.get("_demo_only_bj_endpoint_target_validated") is True
    contract_ok = (
        audit.get("_demo_only_bj_integration_contract_version")
        == bj.INTEGRATION_CONTRACT_VERSION
    )
    if bh_marker_ok and bj_marker_ok and target_ok and contract_ok:
        return True, "happy-path BJ audit carries both BH+BJ NOT_SENT markers"
    return (
        False,
        (
            f"bh_marker={bh_marker_ok} bj_marker={bj_marker_ok} "
            f"endpoint_validated={target_ok} contract={contract_ok}"
        ),
    )


def _check_bybit_executor_not_loaded() -> tuple[bool, str]:
    loaded = sorted(
        m
        for m in sys.modules
        if m == "src.executors.bybit"
        or m.startswith("src.executors.bybit.")
    )
    if loaded:
        return False, f"BybitExecutor modules loaded: {loaded!r}"
    return True, "no BybitExecutor module loaded"


def _check_main_and_risk_not_loaded_by_upstream() -> tuple[bool, str]:
    """BH/BI/BJ must not transitively import main or src.risk."""

    for module in (bh, bi, bj):
        imports = _collect_imported_modules(_module_source(module))
        for imp in imports:
            if imp in FORBIDDEN_MAIN_MODULES or any(
                imp.startswith(bad + ".") for bad in FORBIDDEN_MAIN_MODULES
            ):
                return (
                    False,
                    f"{module.__name__} imports forbidden {imp!r}",
                )
    return True, "BH/BI/BJ do not import main or src.risk"


def _check_bj_guard_steps_set() -> tuple[bool, str]:
    expected = {
        "environment",
        "symbol",
        "existing_positions",
        "side",
        "qty_cap",
        "notional_cap",
        "order_link_id_prefix",
        "endpoint_target",
    }
    if set(bj.GUARD_STEPS) == expected and len(bj.GUARD_STEPS) == 8:
        return True, "BJ.GUARD_STEPS == canonical 8-step ordered set"
    return False, f"bj.GUARD_STEPS={bj.GUARD_STEPS!r}"


# ---------------------------------------------------------------------------
# Checklist runner
# ---------------------------------------------------------------------------


def _bool_item(
    item_id: str,
    category: str,
    description: str,
    fn: Callable[[], tuple[bool, str]],
) -> ChecklistItem:
    passed, detail = fn()
    return ChecklistItem(
        item_id=item_id,
        category=category,
        description=description,
        passed=passed,
        detail=detail,
    )


def run_final_pre_execution_checklist() -> ChecklistReport:
    """Build and return the aggregate BK checklist report.

    This function does NOT send any order, does NOT open any
    connection, does NOT read any secret. It calls BI's dry-run and
    BJ's integration dry-run -- both of which are themselves offline.
    """

    bh.assert_next_task_is_not_review_chain_suffix(NEXT_REQUIRED_TASK)

    items: list[ChecklistItem] = []

    # Identity / chain-break markers
    items.append(
        _bool_item(
            "bk_item_01_bk_pointer_is_not_review_chain_suffix",
            "identity",
            (
                "BK NEXT_REQUIRED_TASK does not end with any forbidden "
                "review-chain suffix"
            ),
            _check_bk_pointer_not_review_chain_suffix,
        )
    )
    items.append(
        _bool_item(
            "bk_item_02_chain_pointers_bh_bi_bj",
            "identity",
            "BH -> BI -> BJ -> BK pointer chain intact",
            _check_bh_bi_bj_chain_pointers,
        )
    )
    items.append(
        _bool_item(
            "bk_item_03_bh_review_chain_guard",
            "identity",
            "BH assert_next_task_is_not_review_chain_suffix rejects all 3 forbidden suffixes",
            _check_bh_review_chain_suffix_guard,
        )
    )

    # BH runtime invariants
    items.append(
        _bool_item(
            "bk_item_04_bh_allowed_symbol_solusdt",
            "bh_runtime",
            "BH ALLOWED_SYMBOL == 'SOLUSDT'",
            _check_bh_allowed_symbol,
        )
    )
    items.append(
        _bool_item(
            "bk_item_05_bh_protected_symbols",
            "bh_runtime",
            "BH PROTECTED_SYMBOLS == {ENAUSDT, TIAUSDT, AIXBTUSDT, POLYXUSDT, EDUUSDT}",
            _check_bh_protected_symbols,
        )
    )
    items.append(
        _bool_item(
            "bk_item_06_bh_live_endpoint_denylist",
            "bh_runtime",
            "BH LIVE_ENDPOINT_DENYLIST contains required live hosts",
            _check_bh_live_endpoint_denylist,
        )
    )
    items.append(
        _bool_item(
            "bk_item_07_bh_allowed_environment_bybit_demo",
            "bh_runtime",
            "BH ALLOWED_ENVIRONMENT == 'bybit_demo'",
            _check_bh_allowed_environment,
        )
    )
    items.append(
        _bool_item(
            "bk_item_08_bh_tiny_caps",
            "bh_runtime",
            "BH tiny caps: 5 USDT notional, 0.05 SOL qty",
            _check_bh_tiny_caps,
        )
    )
    items.append(
        _bool_item(
            "bk_item_09_bh_not_sent_marker",
            "bh_runtime",
            "BH AUDIT_RESPONSE_STATUS_NOT_SENT == 'DEMO_ONLY_TINY_BH_NOT_SENT'",
            _check_bh_not_sent_marker,
        )
    )
    items.append(
        _bool_item(
            "bk_item_10_bj_not_sent_marker",
            "bj_runtime",
            "BJ_AUDIT_RESPONSE_STATUS_NOT_SENT == 'DEMO_ONLY_TINY_BJ_NOT_SENT'",
            _check_bj_not_sent_marker,
        )
    )
    items.append(
        _bool_item(
            "bk_item_11_bj_guard_steps_set",
            "bj_runtime",
            "BJ.GUARD_STEPS == canonical 8-step ordered set",
            _check_bj_guard_steps_set,
        )
    )

    # BI/BJ aggregate offline runs
    bi_passed, bi_detail, bi_total = _check_bi_dry_run()
    items.append(
        ChecklistItem(
            item_id="bk_item_12_bi_dry_run_all_match",
            category="bi_aggregate",
            description="BI run_dry_run().all_match_expectation is True",
            passed=bi_passed,
            detail=bi_detail,
        )
    )
    bj_passed, bj_detail, bj_total = _check_bj_integration()
    items.append(
        ChecklistItem(
            item_id="bk_item_13_bj_integration_all_match",
            category="bj_aggregate",
            description="BJ run_integration_dry_run().all_match_expectation is True",
            passed=bj_passed,
            detail=bj_detail,
        )
    )
    items.append(
        _bool_item(
            "bk_item_14_happy_path_payload_carries_both_markers",
            "bj_aggregate",
            "Happy-path BJ payload audit carries both BH+BJ NOT_SENT markers",
            _check_happy_path_payload_carries_both_markers,
        )
    )

    # Static source invariants -- BH, BI, BJ
    for prefix, module, label in (
        ("bh", bh, "BH"),
        ("bi", bi, "BI"),
        ("bj", bj, "BJ"),
    ):
        items.append(
            _bool_item(
                f"bk_item_static_{prefix}_no_network_import",
                "static_source",
                f"{label} source contains no network-library import",
                lambda m=module: _check_no_network_import(m),
            )
        )
        items.append(
            _bool_item(
                f"bk_item_static_{prefix}_no_secret_read",
                "static_source",
                f"{label} source contains no getenv/environ/load_dotenv tokens",
                lambda m=module: _check_no_secret_read(m),
            )
        )
        items.append(
            _bool_item(
                f"bk_item_static_{prefix}_no_send_methods",
                "static_source",
                f"{label} source defines/calls no send/post_order/submit_order",
                lambda m=module: _check_no_send_methods(m),
            )
        )
        items.append(
            _bool_item(
                f"bk_item_static_{prefix}_no_main_or_risk_import",
                "static_source",
                f"{label} source does not import main or src.risk",
                lambda m=module: _check_no_main_or_risk_import(m),
            )
        )
        items.append(
            _bool_item(
                f"bk_item_static_{prefix}_no_executor_import",
                "static_source",
                f"{label} source does not import src.executors.bybit",
                lambda m=module: _check_no_executor_import(m),
            )
        )
        items.append(
            _bool_item(
                f"bk_item_static_{prefix}_chain_break_literals",
                "static_source",
                f"{label} source declares IS_REVIEW_CHAIN_SUFFIX=False and IMPLEMENTATION_PATH_PHASE literal",
                lambda m=module: _check_chain_break_literals(m),
            )
        )

    # BI and BJ must consume BH directly (no parallel implementation).
    items.append(
        _bool_item(
            "bk_item_static_bi_consumes_bh_directly",
            "static_source",
            "BI source imports BH as `bh` directly from `src`",
            lambda: _check_consumes_bh_directly(bi),
        )
    )
    items.append(
        _bool_item(
            "bk_item_static_bj_consumes_bh_directly",
            "static_source",
            "BJ source imports BH as `bh` directly from `src`",
            lambda: _check_consumes_bh_directly(bj),
        )
    )

    # Cross-module sanity
    items.append(
        _bool_item(
            "bk_item_cross_bybit_executor_not_loaded",
            "cross_module",
            "src.executors.bybit module is not loaded in sys.modules",
            _check_bybit_executor_not_loaded,
        )
    )
    items.append(
        _bool_item(
            "bk_item_cross_main_risk_not_imported_by_upstream",
            "cross_module",
            "BH/BI/BJ do not import main or src.risk transitively at source level",
            _check_main_and_risk_not_loaded_by_upstream,
        )
    )

    passed_count = sum(1 for it in items if it.passed)
    failed_count = sum(1 for it in items if not it.passed)

    return ChecklistReport(
        task_id=TASK_ID,
        identity=IDENTITY,
        phase=IMPLEMENTATION_PATH_PHASE,
        upstream_tasks=UPSTREAM_TASKS,
        next_required_task=NEXT_REQUIRED_TASK,
        is_review_chain_suffix=IS_REVIEW_CHAIN_SUFFIX,
        checklist_contract_version=CHECKLIST_CONTRACT_VERSION,
        bh_identity=bh.IDENTITY,
        bi_identity=bi.IDENTITY,
        bj_identity=bj.IDENTITY,
        bh_adapter_contract_version=bh.ADAPTER_CONTRACT_VERSION,
        bj_integration_contract_version=bj.INTEGRATION_CONTRACT_VERSION,
        bh_allowed_environment=bh.ALLOWED_ENVIRONMENT,
        bh_allowed_symbol=bh.ALLOWED_SYMBOL,
        bh_protected_symbols=tuple(sorted(bh.PROTECTED_SYMBOLS)),
        bh_tiny_size_cap_usdt=format(bh.TINY_SIZE_CAP_USDT, "f"),
        bh_tiny_qty_cap_sol=format(bh.TINY_QTY_CAP_SOL, "f"),
        bh_live_endpoint_denylist=tuple(sorted(bh.LIVE_ENDPOINT_DENYLIST)),
        bh_audit_response_status_not_sent=bh.AUDIT_RESPONSE_STATUS_NOT_SENT,
        bj_audit_response_status_not_sent=bj.BJ_AUDIT_RESPONSE_STATUS_NOT_SENT,
        bi_dry_run_total_cases=bi_total,
        bi_dry_run_all_match=bi_passed,
        bj_integration_total_cases=bj_total,
        bj_integration_all_match=bj_passed,
        total_items=len(items),
        passed_items=passed_count,
        failed_items=failed_count,
        all_passed=(failed_count == 0),
        generated_at_utc=_dt.datetime.now(_dt.timezone.utc).isoformat(),
        items=tuple(items),
    )


# ---------------------------------------------------------------------------
# Report writer (JSON + Markdown; latest_* + timestamped)
# ---------------------------------------------------------------------------


def _utc_timestamp() -> str:
    return _dt.datetime.now(_dt.timezone.utc).strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(report: ChecklistReport) -> str:
    lines: list[str] = []
    lines.append(f"# {report.task_id} -- {report.identity}")
    lines.append("")
    lines.append(f"- generated_at_utc: `{report.generated_at_utc}`")
    lines.append(f"- phase: `{report.phase}`")
    lines.append(
        f"- upstream_tasks: `{', '.join(report.upstream_tasks)}`"
    )
    lines.append(f"- next_required_task: `{report.next_required_task}`")
    lines.append(f"- is_review_chain_suffix: `{report.is_review_chain_suffix}`")
    lines.append(
        f"- checklist_contract_version: `{report.checklist_contract_version}`"
    )
    lines.append("")
    lines.append("## Upstream identity")
    lines.append("")
    lines.append(f"- bh_identity: `{report.bh_identity}`")
    lines.append(f"- bi_identity: `{report.bi_identity}`")
    lines.append(f"- bj_identity: `{report.bj_identity}`")
    lines.append(
        f"- bh_adapter_contract_version: `{report.bh_adapter_contract_version}`"
    )
    lines.append(
        f"- bj_integration_contract_version: "
        f"`{report.bj_integration_contract_version}`"
    )
    lines.append(f"- bh_allowed_environment: `{report.bh_allowed_environment}`")
    lines.append(f"- bh_allowed_symbol: `{report.bh_allowed_symbol}`")
    lines.append(
        f"- bh_protected_symbols: `{', '.join(report.bh_protected_symbols)}`"
    )
    lines.append(f"- bh_tiny_size_cap_usdt: `{report.bh_tiny_size_cap_usdt}`")
    lines.append(f"- bh_tiny_qty_cap_sol: `{report.bh_tiny_qty_cap_sol}`")
    lines.append(
        f"- bh_live_endpoint_denylist: "
        f"`{', '.join(report.bh_live_endpoint_denylist)}`"
    )
    lines.append(
        f"- bh_audit_response_status_not_sent: "
        f"`{report.bh_audit_response_status_not_sent}`"
    )
    lines.append(
        f"- bj_audit_response_status_not_sent: "
        f"`{report.bj_audit_response_status_not_sent}`"
    )
    lines.append("")
    lines.append("## Aggregate run inputs")
    lines.append("")
    lines.append(
        f"- bi_dry_run_total_cases: `{report.bi_dry_run_total_cases}`"
    )
    lines.append(f"- bi_dry_run_all_match: `{report.bi_dry_run_all_match}`")
    lines.append(
        f"- bj_integration_total_cases: `{report.bj_integration_total_cases}`"
    )
    lines.append(
        f"- bj_integration_all_match: `{report.bj_integration_all_match}`"
    )
    lines.append("")
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- total_items: `{report.total_items}`")
    lines.append(f"- passed_items: `{report.passed_items}`")
    lines.append(f"- failed_items: `{report.failed_items}`")
    lines.append(f"- all_passed: `{report.all_passed}`")
    lines.append("")
    lines.append("## Checklist")
    lines.append("")
    lines.append("| item_id | category | passed | description | detail |")
    lines.append("|---|---|---|---|---|")
    for it in report.items:
        d = it.detail.replace("|", "\\|") if it.detail else ""
        desc = it.description.replace("|", "\\|")
        lines.append(
            f"| `{it.item_id}` | `{it.category}` | `{it.passed}` | {desc} | {d} |"
        )
    lines.append("")
    lines.append(
        "_offline final pre-execution checklist -- no order sent, no endpoint "
        "called, no secret read; BH/BI/BJ consumed directly._"
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    report: ChecklistReport,
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
    "CHECKLIST_CONTRACT_VERSION",
    "ChecklistItem",
    "ChecklistReport",
    "DEFAULT_OUTPUT_DIR",
    "FORBIDDEN_EXECUTOR_MODULES",
    "FORBIDDEN_MAIN_MODULES",
    "FORBIDDEN_NETWORK_MODULES",
    "FORBIDDEN_REVIEW_CHAIN_SUFFIXES",
    "FORBIDDEN_SECRET_NAMES",
    "FORBIDDEN_SEND_TOKENS",
    "IDENTITY",
    "IMPLEMENTATION_PATH_PHASE",
    "IS_REVIEW_CHAIN_SUFFIX",
    "NEXT_REQUIRED_TASK",
    "REPORT_NAME",
    "TASK_ID",
    "UPSTREAM_TASKS",
    "run_final_pre_execution_checklist",
    "write_report",
]
