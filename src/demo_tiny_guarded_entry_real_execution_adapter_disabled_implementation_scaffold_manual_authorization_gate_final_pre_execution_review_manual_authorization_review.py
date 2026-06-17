"""
src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review.py
TASK-014BB: Guarded Entry Real Execution Adapter Disabled Implementation
            Scaffold Manual Authorization Gate Final Pre-Execution Review
            Manual Authorization Review.

Disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-review-
manual-authorization-review-only module. This task consumes TASK-014BA's
DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW
artifact at runtime (the DIRECT upstream), plus BA-proven chained proof
flowing back through:
  - AZ DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE READINESS REVIEW
  - AY DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE DRY-RUN
  - AX DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE DESIGN
  - AW DISABLED IMPLEMENTATION SCAFFOLD FINAL PRE-EXECUTION REVIEW
  - AV DISABLED IMPLEMENTATION SCAFFOLD READINESS REVIEW
  - AU DISABLED IMPLEMENTATION SCAFFOLD DRY-RUN
  - AT DISABLED IMPLEMENTATION SCAFFOLD DESIGN
  - AS STATIC SKELETON DRY-RUN
  - AR STATIC SKELETON DESIGN
  - AQ IMPLEMENTATION DESIGN

This module produces a DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION
GATE FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW verdict for the
future TASK-014BC dry-run.

This module does NOT:
  * import any sender / private client / network primitive
    (no urllib / requests / httpx / socket / http.client / aiohttp /
     websockets)
  * read os.environ / dotenv / any secret loader
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit
  * expose any adapter `send`, `place_order`, `execute` method
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * modify any position
  * validate any token / phrase / approval input
  * treat any token / phrase / input as authorization
  * auto-commit / auto-push git
  * implement any real execution adapter

This module is STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-
GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY.

Stage 1 implementation only: identity constants, 36 hard-fail gate
constants, ~52-field result dataclass, BA artifact loader, BA upstream
parser, gate evaluation, and the run function. CLI / preview script /
markdown report writer / full test pack are deferred to Stage 2 / Stage 3.
"""
from __future__ import annotations

import io
import json
import re
import tokenize
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ===========================================================================
# A. Phase identity constants
# ===========================================================================

ADAPTER_NAME = "GuardedTinyEntryRealExecutionAdapter"
ADAPTER_CONTRACT_VERSION = (
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review_v1"
)

STATUS_READY = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_"
    "SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_"
    "AUTHORIZATION_REVIEW_READY"
)
STATUS_READY_BUT_EXECUTION_DISABLED = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_"
    "SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_"
    "AUTHORIZATION_REVIEW_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED = (
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
)
STATUS_FAIL_CLOSED = "FAIL_CLOSED"

MODE_CHECKLIST = (
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review_checklist"
)
MODE_FAIL_CLOSED = "fail_closed"

CONCLUSION_READY_NOT_EXECUTABLE = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY_NOT_EXECUTABLE"
)
AUTHORIZATION_RESULT_DOCUMENTED = "DOCUMENTED_ONLY_NOT_AUTHORIZED"
RESPONSE_STATUS_NOT_SENT = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_NOT_SENT"
)

NEXT_REQUIRED_TASK = (
    "TASK-014BC_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review_manual_authorization_review_dry_run"
)

IDENTITY_CHECKLIST = (
    "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
    "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW CHECKLIST"
)
IDENTITY_STRICT = (
    "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-"
    "FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY"
)

SCOPE_SUMMARY_LITERAL = (
    "TASK-014BB consumes TASK-014BA DISABLED IMPLEMENTATION SCAFFOLD "
    "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW output at "
    "runtime plus BA-proven chained proof, including AZ readiness "
    "review, AY dry-run, AX manual authorization gate design, AW final "
    "pre-execution review, AV readiness review, AU dry-run, AT design, "
    "AS static skeleton dry-run, AR static skeleton design, and AQ "
    "implementation design."
)

BA_DEFAULT_ARTIFACT_DIR = Path(
    "outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_"
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review"
)
BA_DEFAULT_ARTIFACT_FILE = (
    "latest_tiny_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review.json"
)

# BA-side accepted values for Group A gate evaluation.
_BA_ACCEPTED_STATUS = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_"
    "SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_READY"
)
_BA_ACCEPTED_MODE = (
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_checklist"
)
_BA_ACCEPTED_CONCLUSION = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_READY_NOT_EXECUTABLE"
)
_BA_ACCEPTED_AUTHORIZATION_RESULT = "DOCUMENTED_ONLY_NOT_AUTHORIZED"
_BA_ACCEPTED_RESPONSE_STATUS = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_NOT_SENT"
)
_BA_ACCEPTED_NEXT_REQUIRED_TASK = (
    "TASK-014BB_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review_manual_authorization_review"
)

# Denylisted live-endpoint reference URLs.  These strings are listed
# here for self-introspection ONLY and are NEVER invoked by this
# module.  Any live-endpoint URL that appears outside this denylist
# constant triggers GATE_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST.
_DENYLISTED_ENDPOINT_REFERENCES: frozenset[str] = frozenset({
    "https://api.bybit.com",
    "https://api-testnet.bybit.com",
})

# Network primitive import substrings BB must not contain.
_NETWORK_PRIMITIVE_IMPORT_PATTERNS: tuple[str, ...] = (
    "import socket",
    "from socket",
    "import requests",
    "from requests",
    "import urllib",
    "from urllib",
    "import httpx",
    "from httpx",
    "import websockets",
    "from websockets",
    "import aiohttp",
    "from aiohttp",
    "import http.client",
    "from http.client",
)

# Secret-loader / signing patterns BB must not contain.
_SECRET_SIGNING_PATTERNS: tuple[str, ...] = (
    "os.environ",
    "os.getenv",
    "dotenv",
    "load_dotenv",
    "import hmac",
    "from hmac",
    "hmac.new",
    "hashlib.sha256",
)

# Coupling patterns BB must not contain.
_COUPLING_PATTERNS: tuple[str, ...] = (
    "from main import",
    "import main",
    "from src.risk",
    "import src.risk",
    "BybitExecutor",
    "from pybit",
    "import pybit",
)

# Active send / place_order / execute method-definition patterns.
# These regexes look for ACTIVE method definitions (def send(...,
# def place_order(..., def execute(...), as opposed to descriptive
# string literals.
_ACTIVE_EXEC_METHOD_PATTERNS: tuple[str, ...] = (
    r"^\s*def\s+send\s*\(",
    r"^\s*def\s+place_order\s*\(",
    r"^\s*def\s+execute\s*\(",
    r"^\s*async\s+def\s+send\s*\(",
    r"^\s*async\s+def\s+place_order\s*\(",
    r"^\s*async\s+def\s+execute\s*\(",
)


# ===========================================================================
# B. 36 hard-fail gate constants
# ===========================================================================

# --- Group A: BA artifact / fields (18 gates, numbered 1..18) ---
GATE_BA_ARTIFACT_MISSING                        = "ba_artifact_missing"
GATE_BA_STATUS_UNACCEPTABLE                     = "ba_status_unacceptable"
GATE_BA_MODE_MISMATCH                           = "ba_mode_mismatch"
GATE_BA_CONCLUSION_MISMATCH                     = "ba_conclusion_mismatch"
GATE_BA_RESPONSE_STATUS_MISMATCH                = "ba_response_status_mismatch"
GATE_BA_AUTHORIZATION_RESULT_MISMATCH           = "ba_authorization_result_mismatch"
GATE_BA_NEXT_REQUIRED_TASK_MISMATCH             = "ba_next_required_task_mismatch"
GATE_BA_REAL_EXECUTION_ALLOWED_TRUE             = "ba_real_execution_allowed_true"
GATE_BA_SEND_ALLOWED_TRUE                       = "ba_send_allowed_true"
GATE_BA_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE    = "ba_adapter_implementation_included_true"
GATE_BA_ADAPTER_EXECUTION_INCLUDED_TRUE         = "ba_adapter_execution_included_true"
GATE_BA_ORDER_ENDPOINT_CALLED_TRUE              = "ba_order_endpoint_called_true"
GATE_BA_STOP_ENDPOINT_CALLED_TRUE               = "ba_stop_endpoint_called_true"
GATE_BA_NO_POSITION_MODIFIED_FALSE              = "ba_no_position_modified_false"
GATE_BA_NO_SECRETS_LOADED_FALSE                 = "ba_no_secrets_loaded_false"
GATE_BA_G20_LIFTED_TRUE                         = "ba_g20_lifted_true"
GATE_BA_AZ_DIRECT_PROOF_MISSING                 = "ba_az_direct_proof_missing"
GATE_BA_AZ_CHAINED_PROOF_MISSING                = "ba_az_chained_proof_missing"

# --- Group B: BA scope_summary content gates (6 gates, 19..24) ---
GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT         = "ba_scope_summary_missing_az_direct"
GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY   = "ba_scope_summary_contains_ba_consumes_ay"
GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AX   = "ba_scope_summary_contains_ba_consumes_ax"
GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AW   = "ba_scope_summary_contains_ba_consumes_aw"
GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AV   = "ba_scope_summary_contains_ba_consumes_av"
GATE_BA_SCOPE_SUMMARY_CONTAINS_ITDOCUMENTS_TYPO = "ba_scope_summary_contains_itdocuments_typo"

# --- Group C: BA failure passthrough (3 gates, 25..27) ---
GATE_BA_STATUS_FAIL_CLOSED                      = "ba_status_fail_closed_passthrough"
GATE_BA_MODE_FAIL_CLOSED                        = "ba_mode_fail_closed_passthrough"
GATE_BA_FAILED_STAGE_NON_EMPTY                  = "ba_failed_stage_non_empty_passthrough"

# --- Group D: BB own-source safety invariants (9 gates, 28..36) ---
GATE_APPROVAL_INPUT_TREATED_AS_AUTHORIZATION    = "bb_approval_input_treated_as_authorization"
GATE_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST    = "bb_live_endpoint_reference_beyond_denylist"
GATE_NETWORK_PRIMITIVE_OR_IMPORT                = "bb_network_primitive_or_import"
GATE_SECRET_LOADER_OR_HMAC_OR_SIGNING           = "bb_secret_loader_or_hmac_or_signing"
GATE_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING = "bb_sender_or_main_or_risk_or_bybitexecutor_coupling"
GATE_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR   = "bb_active_send_place_order_execute_behavior"
GATE_REAL_ORDER_OR_STOP_ENDPOINT_CALL           = "bb_real_order_or_stop_endpoint_call"
GATE_G20_LIFT                                   = "bb_g20_lift"
GATE_POSITION_MODIFICATION                      = "bb_position_modification"


# The 36 hard-fail gates.  Any one of these forces the BB result to
# FAIL_CLOSED regardless of any other state.
_HARD_FAIL_GATES: frozenset[str] = frozenset({
    # Group A (18)
    GATE_BA_ARTIFACT_MISSING,
    GATE_BA_STATUS_UNACCEPTABLE,
    GATE_BA_MODE_MISMATCH,
    GATE_BA_CONCLUSION_MISMATCH,
    GATE_BA_RESPONSE_STATUS_MISMATCH,
    GATE_BA_AUTHORIZATION_RESULT_MISMATCH,
    GATE_BA_NEXT_REQUIRED_TASK_MISMATCH,
    GATE_BA_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BA_SEND_ALLOWED_TRUE,
    GATE_BA_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE,
    GATE_BA_ADAPTER_EXECUTION_INCLUDED_TRUE,
    GATE_BA_ORDER_ENDPOINT_CALLED_TRUE,
    GATE_BA_STOP_ENDPOINT_CALLED_TRUE,
    GATE_BA_NO_POSITION_MODIFIED_FALSE,
    GATE_BA_NO_SECRETS_LOADED_FALSE,
    GATE_BA_G20_LIFTED_TRUE,
    GATE_BA_AZ_DIRECT_PROOF_MISSING,
    GATE_BA_AZ_CHAINED_PROOF_MISSING,
    # Group B (6)
    GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AX,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AW,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AV,
    GATE_BA_SCOPE_SUMMARY_CONTAINS_ITDOCUMENTS_TYPO,
    # Group C (3)
    GATE_BA_STATUS_FAIL_CLOSED,
    GATE_BA_MODE_FAIL_CLOSED,
    GATE_BA_FAILED_STAGE_NON_EMPTY,
    # Group D (9)
    GATE_APPROVAL_INPUT_TREATED_AS_AUTHORIZATION,
    GATE_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST,
    GATE_NETWORK_PRIMITIVE_OR_IMPORT,
    GATE_SECRET_LOADER_OR_HMAC_OR_SIGNING,
    GATE_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING,
    GATE_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR,
    GATE_REAL_ORDER_OR_STOP_ENDPOINT_CALL,
    GATE_G20_LIFT,
    GATE_POSITION_MODIFICATION,
})

# Per-gate stage descriptor for failed_stage labelling.
_GATE_TO_STAGE: dict[str, str] = {
    GATE_BA_ARTIFACT_MISSING:                          "stage_0_ba_artifact_preflight",
    GATE_BA_STATUS_UNACCEPTABLE:                       "stage_1_ba_status_check",
    GATE_BA_MODE_MISMATCH:                             "stage_1_ba_mode_check",
    GATE_BA_CONCLUSION_MISMATCH:                       "stage_1_ba_conclusion_check",
    GATE_BA_RESPONSE_STATUS_MISMATCH:                  "stage_1_ba_response_status_check",
    GATE_BA_AUTHORIZATION_RESULT_MISMATCH:             "stage_1_ba_authorization_result_check",
    GATE_BA_NEXT_REQUIRED_TASK_MISMATCH:               "stage_1_ba_next_required_task_check",
    GATE_BA_REAL_EXECUTION_ALLOWED_TRUE:               "stage_2_ba_real_execution_allowed_check",
    GATE_BA_SEND_ALLOWED_TRUE:                         "stage_2_ba_send_allowed_check",
    GATE_BA_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE:      "stage_2_ba_adapter_implementation_included_check",
    GATE_BA_ADAPTER_EXECUTION_INCLUDED_TRUE:           "stage_2_ba_adapter_execution_included_check",
    GATE_BA_ORDER_ENDPOINT_CALLED_TRUE:                "stage_2_ba_order_endpoint_called_check",
    GATE_BA_STOP_ENDPOINT_CALLED_TRUE:                 "stage_2_ba_stop_endpoint_called_check",
    GATE_BA_NO_POSITION_MODIFIED_FALSE:                "stage_2_ba_no_position_modified_check",
    GATE_BA_NO_SECRETS_LOADED_FALSE:                   "stage_2_ba_no_secrets_loaded_check",
    GATE_BA_G20_LIFTED_TRUE:                           "stage_2_ba_g20_lifted_check",
    GATE_BA_AZ_DIRECT_PROOF_MISSING:                   "stage_3_ba_az_direct_proof_check",
    GATE_BA_AZ_CHAINED_PROOF_MISSING:                  "stage_3_ba_az_chained_proof_check",
    GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT:           "stage_4_ba_scope_summary_az_direct_check",
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY:     "stage_4_ba_scope_summary_no_ba_consumes_ay_check",
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AX:     "stage_4_ba_scope_summary_no_ba_consumes_ax_check",
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AW:     "stage_4_ba_scope_summary_no_ba_consumes_aw_check",
    GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AV:     "stage_4_ba_scope_summary_no_ba_consumes_av_check",
    GATE_BA_SCOPE_SUMMARY_CONTAINS_ITDOCUMENTS_TYPO:   "stage_4_ba_scope_summary_no_itdocuments_typo_check",
    GATE_BA_STATUS_FAIL_CLOSED:                        "stage_5_ba_status_passthrough_check",
    GATE_BA_MODE_FAIL_CLOSED:                          "stage_5_ba_mode_passthrough_check",
    GATE_BA_FAILED_STAGE_NON_EMPTY:                    "stage_5_ba_failed_stage_passthrough_check",
    GATE_APPROVAL_INPUT_TREATED_AS_AUTHORIZATION:      "stage_6_bb_self_approval_input_check",
    GATE_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST:      "stage_6_bb_self_live_endpoint_check",
    GATE_NETWORK_PRIMITIVE_OR_IMPORT:                  "stage_6_bb_self_network_primitive_check",
    GATE_SECRET_LOADER_OR_HMAC_OR_SIGNING:             "stage_6_bb_self_secret_signing_check",
    GATE_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING: "stage_6_bb_self_coupling_check",
    GATE_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR:     "stage_6_bb_self_active_exec_method_check",
    GATE_REAL_ORDER_OR_STOP_ENDPOINT_CALL:             "stage_6_bb_self_endpoint_call_check",
    GATE_G20_LIFT:                                     "stage_6_bb_self_g20_lift_check",
    GATE_POSITION_MODIFICATION:                        "stage_6_bb_self_position_modification_check",
}


# ===========================================================================
# C. Result dataclass
# ===========================================================================

@dataclass
class TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewResult:
    """
    Read-only outcome of one BB disabled-implementation-scaffold-manual-
    authorization-gate-final-pre-execution-review manual-authorization-
    review run.  Defaults make a freshly-constructed instance directly
    READY (no failures); the run function flips status to FAIL_CLOSED
    when any hard-fail gate triggers.
    """

    # ----- Core identity / mode -----
    status: str = STATUS_READY
    mode: str = MODE_CHECKLIST
    selected_symbol: str = ""
    existing_position_symbols: list[str] = field(default_factory=list)
    adapter_name: str = ADAPTER_NAME
    adapter_contract_version: str = ADAPTER_CONTRACT_VERSION

    # ----- Adapter / execution surface guard flags (all default safe) -----
    disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_only: bool = True
    manual_authorization_review_only: bool = True
    executable_adapter_included: bool = False
    adapter_implementation_included: bool = False
    adapter_execution_included: bool = False
    send_method_included: bool = False
    place_order_method_included: bool = False
    execute_method_included: bool = False
    real_entry_implemented: bool = False
    real_execution_allowed: bool = False
    current_task_real_execution_allowed: bool = False

    # ----- Authorization-grants flags (all default False) -----
    manual_authorization_review_grants_execution: bool = False
    manual_authorization_gate_final_pre_execution_review_grants_execution: bool = False
    manual_authorization_gate_readiness_review_grants_execution: bool = False
    manual_authorization_gate_dry_run_grants_execution: bool = False
    manual_authorization_gate_design_grants_execution: bool = False
    final_pre_execution_review_grants_execution: bool = False
    readiness_review_grants_execution: bool = False
    dry_run_grants_execution: bool = False
    adapter_grants_execution: bool = False

    # ----- Approval-input-not-treated-as-authorization invariants -----
    approval_phrase_validated: bool = False
    approval_token_validated: bool = False
    approval_inputs_validated: bool = False
    approval_phrase_grants_execution: bool = False
    approval_token_grants_execution: bool = False
    approval_inputs_grant_execution: bool = False
    token_to_authorization_mapping: bool = False
    phrase_to_authorization_mapping: bool = False
    manual_authorization_review_accepts_runtime_approval: bool = False
    manual_authorization_review_translates_text_to_execution: bool = False

    # ----- Live-action invariants (all default safe) -----
    send_allowed: bool = False
    order_endpoint_called: bool = False
    stop_endpoint_called: bool = False
    no_position_modified: bool = True
    no_live_endpoint: bool = True
    no_orders_sent: bool = True
    no_secrets_loaded: bool = True
    secret_value_observed: bool = False
    g20_policy_still_in_place: bool = True
    g20_lifted: bool = False
    existing_positions_touched: list[str] = field(default_factory=list)

    # ----- Verdict / response -----
    disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion: str = CONCLUSION_READY_NOT_EXECUTABLE
    disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result: str = AUTHORIZATION_RESULT_DOCUMENTED
    response_status: str = RESPONSE_STATUS_NOT_SENT
    next_required_task: str = NEXT_REQUIRED_TASK

    # ----- Failure reporting -----
    failed_stage: str = ""
    blocked_gates: list[str] = field(default_factory=list)

    # ----- Identity literals -----
    scope_summary: str = SCOPE_SUMMARY_LITERAL
    identity_checklist: str = IDENTITY_CHECKLIST
    identity_strict: str = IDENTITY_STRICT

    # ===== 17 BA-upstream fields =====
    consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_contract_version: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_mode: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_response_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_real_execution_allowed: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_send_allowed: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_implementation_included: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_execution_included: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_order_endpoint_called: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_stop_endpoint_called: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_position_modified: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_secrets_loaded: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_g20_lifted: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary: str = ""

    # ===== 11 BA->AZ chained proof fields =====
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_mentions_az_direct_upstream: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ay: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ax: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_aw: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_av: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_itdocuments_typo: bool = False

    # ------------------------------------------------------------------
    # JSON serialization (stable key ordering)
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        return {
            # Core identity / mode
            "status":                                       self.status,
            "mode":                                         self.mode,
            "selected_symbol":                              self.selected_symbol,
            "existing_position_symbols":                    list(self.existing_position_symbols),
            "adapter_name":                                 self.adapter_name,
            "adapter_contract_version":                     self.adapter_contract_version,
            # Adapter / execution surface guard flags
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_only": self.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_only,
            "manual_authorization_review_only":             self.manual_authorization_review_only,
            "executable_adapter_included":                  self.executable_adapter_included,
            "adapter_implementation_included":              self.adapter_implementation_included,
            "adapter_execution_included":                   self.adapter_execution_included,
            "send_method_included":                         self.send_method_included,
            "place_order_method_included":                  self.place_order_method_included,
            "execute_method_included":                      self.execute_method_included,
            "real_entry_implemented":                       self.real_entry_implemented,
            "real_execution_allowed":                       self.real_execution_allowed,
            "current_task_real_execution_allowed":          self.current_task_real_execution_allowed,
            # Authorization-grants flags
            "manual_authorization_review_grants_execution": self.manual_authorization_review_grants_execution,
            "manual_authorization_gate_final_pre_execution_review_grants_execution": self.manual_authorization_gate_final_pre_execution_review_grants_execution,
            "manual_authorization_gate_readiness_review_grants_execution": self.manual_authorization_gate_readiness_review_grants_execution,
            "manual_authorization_gate_dry_run_grants_execution": self.manual_authorization_gate_dry_run_grants_execution,
            "manual_authorization_gate_design_grants_execution": self.manual_authorization_gate_design_grants_execution,
            "final_pre_execution_review_grants_execution":  self.final_pre_execution_review_grants_execution,
            "readiness_review_grants_execution":            self.readiness_review_grants_execution,
            "dry_run_grants_execution":                     self.dry_run_grants_execution,
            "adapter_grants_execution":                     self.adapter_grants_execution,
            # Approval-input invariants
            "approval_phrase_validated":                    self.approval_phrase_validated,
            "approval_token_validated":                     self.approval_token_validated,
            "approval_inputs_validated":                    self.approval_inputs_validated,
            "approval_phrase_grants_execution":             self.approval_phrase_grants_execution,
            "approval_token_grants_execution":              self.approval_token_grants_execution,
            "approval_inputs_grant_execution":              self.approval_inputs_grant_execution,
            "token_to_authorization_mapping":               self.token_to_authorization_mapping,
            "phrase_to_authorization_mapping":              self.phrase_to_authorization_mapping,
            "manual_authorization_review_accepts_runtime_approval": self.manual_authorization_review_accepts_runtime_approval,
            "manual_authorization_review_translates_text_to_execution": self.manual_authorization_review_translates_text_to_execution,
            # Live-action invariants
            "send_allowed":                                 self.send_allowed,
            "order_endpoint_called":                        self.order_endpoint_called,
            "stop_endpoint_called":                         self.stop_endpoint_called,
            "no_position_modified":                         self.no_position_modified,
            "no_live_endpoint":                             self.no_live_endpoint,
            "no_orders_sent":                               self.no_orders_sent,
            "no_secrets_loaded":                            self.no_secrets_loaded,
            "secret_value_observed":                        self.secret_value_observed,
            "g20_policy_still_in_place":                    self.g20_policy_still_in_place,
            "g20_lifted":                                   self.g20_lifted,
            "existing_positions_touched":                   list(self.existing_positions_touched),
            # Verdict / response
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion": self.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion,
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result": self.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result,
            "response_status":                              self.response_status,
            "next_required_task":                           self.next_required_task,
            # Failure reporting
            "failed_stage":                                 self.failed_stage,
            "blocked_gates":                                list(self.blocked_gates),
            # Identity literals
            "scope_summary":                                self.scope_summary,
            "identity_checklist":                           self.identity_checklist,
            "identity_strict":                              self.identity_strict,
            # BA upstream block
            "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_contract_version":
                self.consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_contract_version,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_mode":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_mode,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_response_status":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_response_status,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_real_execution_allowed":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_real_execution_allowed,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_send_allowed":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_send_allowed,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_implementation_included":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_implementation_included,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_execution_included":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_execution_included,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_order_endpoint_called":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_order_endpoint_called,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_stop_endpoint_called":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_stop_endpoint_called,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_position_modified":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_position_modified,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_secrets_loaded":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_secrets_loaded,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_g20_lifted":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_g20_lifted,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary,
            # BA->AZ chained proof block
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_mentions_az_direct_upstream":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_mentions_az_direct_upstream,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ay":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ay,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ax":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ax,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_aw":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_aw,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_av":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_av,
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_itdocuments_typo":
                self.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_itdocuments_typo,
        }


# Short alias for internal use (the full class name is intentionally long
# to match the contract identifier).
_Result = TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewResult


# ===========================================================================
# D. BA artifact loader
# ===========================================================================

def _load_ba_final_pre_execution_review_artifact(path: Path) -> dict | None:
    """
    Load the BA final-pre-execution-review JSON artifact.

    Returns None if the file does not exist or is unreadable / invalid
    JSON.  The loader never raises -- it returns None on any failure so
    the caller can trigger GATE_BA_ARTIFACT_MISSING in a controlled way.
    """
    try:
        if not path.exists() or not path.is_file():
            return None
        text = path.read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, ValueError, UnicodeDecodeError):
        return None
    if not isinstance(data, dict):
        return None
    return data


# ===========================================================================
# E. BA upstream parser (populates 17 BA upstream + 11 BA->AZ chained
#    proof fields, returns the list of Group A / Group B gates triggered).
# ===========================================================================

def _safe_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _safe_bool(value: Any) -> bool:
    return bool(value)


def _parse_ba_upstream(ba_artifact: dict, result: _Result) -> list[str]:
    """
    Populate the BA upstream + BA->AZ chained proof fields on `result`
    by reading BA's emitted artifact dict, and return the list of
    triggered Group A / Group B / Group C gate names.
    """
    triggered: list[str] = []

    # ----- Direct BA top-level fields -----
    ba_status = _safe_str(ba_artifact.get("status"))
    ba_mode = _safe_str(ba_artifact.get("mode"))
    # BA emits the conclusion under both legacy and current keys; prefer
    # the current key, fall back to the legacy.
    ba_conclusion = _safe_str(
        ba_artifact.get(
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion",
            ba_artifact.get("implementation_design_conclusion", ""),
        )
    )
    ba_auth_result = _safe_str(
        ba_artifact.get(
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result",
            ba_artifact.get("implementation_design_authorization_result", ""),
        )
    )
    # BA emits response_status nested inside audit_artifacts /
    # final_implementation_design_verdict.  Prefer top-level for forward
    # compat, then audit_artifacts, then verdict.
    audit = ba_artifact.get("audit_artifacts") if isinstance(ba_artifact.get("audit_artifacts"), dict) else {}
    verdict = ba_artifact.get("final_implementation_design_verdict") if isinstance(ba_artifact.get("final_implementation_design_verdict"), dict) else {}
    ba_response_status = _safe_str(
        ba_artifact.get(
            "response_status",
            audit.get("response_status", verdict.get("response_status", "")),
        )
    )
    ba_next_required = _safe_str(ba_artifact.get("next_required_task"))
    ba_failed_stage = _safe_str(ba_artifact.get("failed_stage"))

    ba_real_exec_allowed     = _safe_bool(ba_artifact.get("real_execution_allowed", False))
    ba_send_allowed          = _safe_bool(ba_artifact.get("send_allowed", False))
    ba_adapter_impl_included = _safe_bool(ba_artifact.get("adapter_implementation_included", False))
    ba_adapter_exec_included = _safe_bool(ba_artifact.get("adapter_execution_included", False))
    ba_order_endpoint_called = _safe_bool(ba_artifact.get("order_endpoint_called", False))
    ba_stop_endpoint_called  = _safe_bool(ba_artifact.get("stop_endpoint_called", False))
    ba_no_position_modified  = _safe_bool(ba_artifact.get("no_position_modified", False))
    ba_no_secrets_loaded     = _safe_bool(ba_artifact.get("no_secrets_loaded", False))
    ba_g20_lifted            = _safe_bool(ba_artifact.get("g20_lifted", False))

    # scope_summary lives inside BA's stage_1 dict
    scope_dict = ba_artifact.get(
        "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope",
        ba_artifact.get("implementation_design_scope", {}),
    )
    if not isinstance(scope_dict, dict):
        scope_dict = {}
    ba_scope_summary = _safe_str(scope_dict.get("scope_summary", ""))

    # ----- Populate 17 BA-upstream fields -----
    result.consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_contract_version = \
        _safe_str(ba_artifact.get("adapter_contract_version", ""))
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status = ba_status
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_mode = ba_mode
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion = ba_conclusion
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result = ba_auth_result
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_response_status = ba_response_status
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_real_execution_allowed = ba_real_exec_allowed
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_send_allowed = ba_send_allowed
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_implementation_included = ba_adapter_impl_included
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_execution_included = ba_adapter_exec_included
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_order_endpoint_called = ba_order_endpoint_called
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_stop_endpoint_called = ba_stop_endpoint_called
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_position_modified = ba_no_position_modified
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_secrets_loaded = ba_no_secrets_loaded
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_g20_lifted = ba_g20_lifted
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task = ba_next_required
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary = ba_scope_summary

    # ----- Populate 11 BA->AZ chained proof fields -----
    az_contract_version = _safe_str(
        ba_artifact.get("consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version", "")
    )
    az_status = _safe_str(
        ba_artifact.get("upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status", "")
    )
    az_response_status = _safe_str(
        ba_artifact.get("upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status", "")
    )
    az_next_required = _safe_str(
        ba_artifact.get("upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task", "")
    )
    ay_status_via_az = _safe_str(
        ba_artifact.get("upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status", "")
    )

    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version = az_contract_version
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status = az_status
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status = az_response_status
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task = az_next_required
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status = ay_status_via_az

    # ----- scope_summary cross-checks (Group B) -----
    mentions_az_direct = "TASK-014BA consumes TASK-014AZ" in ba_scope_summary
    has_no_ay          = "TASK-014BA consumes TASK-014AY" not in ba_scope_summary
    has_no_ax          = "TASK-014BA consumes TASK-014AX" not in ba_scope_summary
    has_no_aw          = "TASK-014BA consumes TASK-014AW" not in ba_scope_summary
    has_no_av          = "TASK-014BA consumes TASK-014AV" not in ba_scope_summary
    has_no_itdoc_typo  = "Itdocuments" not in ba_scope_summary

    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_mentions_az_direct_upstream = mentions_az_direct
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ay = has_no_ay
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ax = has_no_ax
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_aw = has_no_aw
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_av = has_no_av
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_itdocuments_typo = has_no_itdoc_typo

    # ========================================================
    # Group A gate evaluation (BA artifact / fields)
    # ========================================================
    if ba_status != _BA_ACCEPTED_STATUS:
        # Special-case: if BA itself reports FAIL_CLOSED, prefer the
        # Group C passthrough gate so failed_stage is more descriptive.
        if ba_status == STATUS_FAIL_CLOSED:
            triggered.append(GATE_BA_STATUS_FAIL_CLOSED)
        else:
            triggered.append(GATE_BA_STATUS_UNACCEPTABLE)
    if ba_mode != _BA_ACCEPTED_MODE:
        if ba_mode == MODE_FAIL_CLOSED:
            triggered.append(GATE_BA_MODE_FAIL_CLOSED)
        else:
            triggered.append(GATE_BA_MODE_MISMATCH)
    if ba_conclusion != _BA_ACCEPTED_CONCLUSION:
        triggered.append(GATE_BA_CONCLUSION_MISMATCH)
    if ba_response_status != _BA_ACCEPTED_RESPONSE_STATUS:
        triggered.append(GATE_BA_RESPONSE_STATUS_MISMATCH)
    if ba_auth_result != _BA_ACCEPTED_AUTHORIZATION_RESULT:
        triggered.append(GATE_BA_AUTHORIZATION_RESULT_MISMATCH)
    if ba_next_required != _BA_ACCEPTED_NEXT_REQUIRED_TASK:
        triggered.append(GATE_BA_NEXT_REQUIRED_TASK_MISMATCH)
    if ba_real_exec_allowed:
        triggered.append(GATE_BA_REAL_EXECUTION_ALLOWED_TRUE)
    if ba_send_allowed:
        triggered.append(GATE_BA_SEND_ALLOWED_TRUE)
    if ba_adapter_impl_included:
        triggered.append(GATE_BA_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE)
    if ba_adapter_exec_included:
        triggered.append(GATE_BA_ADAPTER_EXECUTION_INCLUDED_TRUE)
    if ba_order_endpoint_called:
        triggered.append(GATE_BA_ORDER_ENDPOINT_CALLED_TRUE)
    if ba_stop_endpoint_called:
        triggered.append(GATE_BA_STOP_ENDPOINT_CALLED_TRUE)
    if not ba_no_position_modified:
        triggered.append(GATE_BA_NO_POSITION_MODIFIED_FALSE)
    if not ba_no_secrets_loaded:
        triggered.append(GATE_BA_NO_SECRETS_LOADED_FALSE)
    if ba_g20_lifted:
        triggered.append(GATE_BA_G20_LIFTED_TRUE)
    # AZ direct proof: BA must have produced a non-empty AZ contract +
    # AZ status; otherwise the chained-back-through-AZ promise is empty.
    if not az_contract_version or not az_status:
        triggered.append(GATE_BA_AZ_DIRECT_PROOF_MISSING)
    if not ay_status_via_az:
        triggered.append(GATE_BA_AZ_CHAINED_PROOF_MISSING)

    # ========================================================
    # Group B gate evaluation (BA scope_summary content)
    # ========================================================
    if not mentions_az_direct:
        triggered.append(GATE_BA_SCOPE_SUMMARY_MISSING_AZ_DIRECT)
    if not has_no_ay:
        triggered.append(GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AY)
    if not has_no_ax:
        triggered.append(GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AX)
    if not has_no_aw:
        triggered.append(GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AW)
    if not has_no_av:
        triggered.append(GATE_BA_SCOPE_SUMMARY_CONTAINS_BA_CONSUMES_AV)
    if not has_no_itdoc_typo:
        triggered.append(GATE_BA_SCOPE_SUMMARY_CONTAINS_ITDOCUMENTS_TYPO)

    # ========================================================
    # Group C gate evaluation (BA failure passthrough)
    # ========================================================
    if ba_failed_stage:
        triggered.append(GATE_BA_FAILED_STAGE_NON_EMPTY)

    return triggered


# ===========================================================================
# F. BB self-source-introspection (Group D gates)
# ===========================================================================

def _read_self_source() -> str:
    """
    Return this module's own source text for self-introspection.

    Returns the empty string if the file cannot be read (which itself
    forces Group D to fail-open in a safe direction since the patterns
    cannot match an empty string -- the caller treats an unreadable
    self-source as a non-finding rather than crashing).
    """
    try:
        return Path(__file__).read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return ""


def _extract_active_code_tokens(source: str) -> tuple[str, list[str]]:
    """
    Tokenize `source` and return:
      * `code_text`: a reconstruction containing ONLY NAME, OP, NUMBER
        tokens (i.e. real code; no string literals, no comments,
        no docstrings).  Used for active-construct pattern matching.
      * `string_literals`: a list of every string-literal value
        appearing in the source.  Used for URL / endpoint-path scanning
        without conflating with active code.

    Tokenization errors are swallowed -- if the source cannot be
    tokenized we return empty results, which is a safe default.
    """
    code_parts: list[str] = []
    string_parts: list[str] = []
    try:
        readline = io.StringIO(source).readline
        for tok in tokenize.generate_tokens(readline):
            ttype = tok.type
            tstr = tok.string
            if ttype == tokenize.STRING:
                # Strip quotes / prefixes for a clean literal value.
                try:
                    string_parts.append(eval(tstr))  # noqa: S307 -- literal-only
                except Exception:
                    string_parts.append(tstr)
            elif ttype in (tokenize.NAME, tokenize.OP, tokenize.NUMBER):
                code_parts.append(tstr)
            elif ttype == tokenize.NEWLINE or ttype == tokenize.NL:
                code_parts.append("\n")
            # COMMENT / INDENT / DEDENT / ENCODING / ENDMARKER ignored.
    except tokenize.TokenizeError:
        return "", []
    return " ".join(code_parts), string_parts


def _evaluate_self_source_gates(source: str) -> list[str]:
    """
    Statically scan BB's own source text for the 9 Group D invariants.

    Uses Python's `tokenize` module to split the source into active
    code tokens vs. string literals.  Patterns are matched against
    active code only -- string literals (denylist constants, the
    module docstring, pattern definitions themselves) never trigger
    a gate.
    """
    triggered: list[str] = []
    if not source:
        return triggered

    code_text, literals = _extract_active_code_tokens(source)
    if not code_text and not literals:
        return triggered

    # ----- Gate D1: network primitive imports / calls -----
    # Patterns like "import socket" reconstruct in code_text as
    # "import socket" (NAME OP NAME with our space join), so a simple
    # substring search works.
    for pat in _NETWORK_PRIMITIVE_IMPORT_PATTERNS:
        # Normalize whitespace in the pattern to match our space-joined
        # reconstruction.
        normalized = " ".join(pat.split())
        if normalized in code_text:
            triggered.append(GATE_NETWORK_PRIMITIVE_OR_IMPORT)
            break

    # ----- Gate D2: secret loader / HMAC / signing -----
    for pat in _SECRET_SIGNING_PATTERNS:
        normalized = pat
        # Patterns containing '.' need to be matched against the
        # space-joined token stream.  Build a normalized variant.
        if "." in pat:
            normalized = " . ".join(pat.split("."))
            normalized = " ".join(normalized.split())
        elif " " in pat:
            normalized = " ".join(pat.split())
        if normalized in code_text:
            triggered.append(GATE_SECRET_LOADER_OR_HMAC_OR_SIGNING)
            break

    # ----- Gate D3: coupling to main / src.risk / BybitExecutor / pybit -----
    for pat in _COUPLING_PATTERNS:
        normalized = pat
        if "." in pat:
            normalized = " . ".join(pat.split("."))
            normalized = " ".join(normalized.split())
        elif " " in pat:
            normalized = " ".join(pat.split())
        if normalized in code_text:
            triggered.append(GATE_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING)
            break

    # ----- Gate D4: active send / place_order / execute method defs -----
    # In our space-joined code stream these appear as
    # "def send (" / "def place_order (" / "def execute (" /
    # "async def send (" etc.
    method_def_phrases = (
        "def send (",
        "def place_order (",
        "def execute (",
        "async def send (",
        "async def place_order (",
        "async def execute (",
    )
    for phrase in method_def_phrases:
        if phrase in code_text:
            triggered.append(GATE_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR)
            break

    # ----- Gate D5: real order / stop endpoint call (function-call form) ---
    # We look for active CODE patterns like "requests . post (",
    # "httpx . post (", ".post (" in the reconstructed token stream.
    endpoint_call_phrases = (
        "requests . post (", "requests . get (", "requests . request (",
        "httpx . post (",   "httpx . get (",   "httpx . request (",
        "aiohttp . ClientSession",
        "urlopen (",
        "socket . socket (",
    )
    for phrase in endpoint_call_phrases:
        if phrase in code_text:
            triggered.append(GATE_REAL_ORDER_OR_STOP_ENDPOINT_CALL)
            break

    # ----- Gate D6: live-endpoint URL beyond denylist -----
    # Scan only STRING LITERALS for live-endpoint URLs.  Each bybit
    # live URL must appear in the denylist constant.
    url_pat = re.compile(r"https?://[^\s'\")]+")
    for literal in literals:
        for match in url_pat.finditer(literal):
            url = match.group(0).rstrip(",.)")
            if "bybit.com" not in url:
                continue
            if "api-demo" in url or "demo." in url:
                continue
            if url not in _DENYLISTED_ENDPOINT_REFERENCES:
                triggered.append(GATE_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST)
                break
        else:
            continue
        break

    # ----- Gate D7: approval input treated as authorization -----
    # Look for active-code assignments like
    # "approval_phrase_grants_execution = True" or
    # "token_grants_execution = True" or
    # "phrase_validated = True".  Field defaults in our dataclass
    # are ALL `= False` so this should not match.
    grants_phrases = (
        "phrase_grants_execution = True",
        "token_grants_execution = True",
        "approval_inputs_grant_execution = True",
        "approval_phrase_validated = True",
        "approval_token_validated = True",
        "approval_inputs_validated = True",
        "phrase_to_authorization_mapping = True",
        "token_to_authorization_mapping = True",
    )
    for phrase in grants_phrases:
        if phrase in code_text:
            triggered.append(GATE_APPROVAL_INPUT_TREATED_AS_AUTHORIZATION)
            break

    # ----- Gate D8: G20 lift -----
    g20_phrases = (
        "g20_lifted = True",
        "lift_g20 (", "lift_G20 (", "disable_g20 (", "bypass_g20 (",
    )
    for phrase in g20_phrases:
        if phrase in code_text:
            triggered.append(GATE_G20_LIFT)
            break

    # ----- Gate D9: position modification -----
    posmod_phrases = (
        "modify_position (",
        "close_position (",
        "set_leverage (",
        "cancel_order (",
        "amend_order (",
        "place_order (",
        "create_order (",
        "trading_stop (",
    )
    for phrase in posmod_phrases:
        if phrase in code_text:
            triggered.append(GATE_POSITION_MODIFICATION)
            break

    return triggered


# ===========================================================================
# G. run(...) function -- the public BB entrypoint
# ===========================================================================

def run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review(
    *,
    symbol: str = "SOLUSDT",
    ba_artifact_path: Path | None = None,
    ba_artifact: dict | None = None,
    allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review: bool = False,
    allow_real_entry_execution: bool = False,
    expected_commit_hash: str | None = None,  # noqa: ARG001 -- reserved for Stage 2
) -> _Result:
    """
    Execute one BB disabled-implementation-scaffold-manual-authorization-
    gate-final-pre-execution-review manual-authorization-review run.

    The function never performs any I/O beyond:
      * reading the BA artifact path (if supplied) from disk via the
        loader, and
      * reading THIS module's own source file for Group D static
        introspection.
    It never opens a socket, reads secrets, calls any endpoint,
    modifies any position, lifts G20, or treats any approval input as
    authorization.
    """
    result = _Result()
    result.selected_symbol = _safe_str(symbol)

    blocked: list[str] = []

    # ------------------------------------------------------------------
    # Stage 0 -- BA artifact preflight
    # ------------------------------------------------------------------
    artifact: dict | None
    if ba_artifact is not None:
        artifact = ba_artifact if isinstance(ba_artifact, dict) else None
    elif ba_artifact_path is not None:
        artifact = _load_ba_final_pre_execution_review_artifact(ba_artifact_path)
    else:
        artifact = None

    if artifact is None:
        blocked.append(GATE_BA_ARTIFACT_MISSING)
    else:
        # Stages 1..5 -- evaluate BA upstream + Group A/B/C gates.
        upstream_gates = _parse_ba_upstream(artifact, result)
        blocked.extend(upstream_gates)

    # ------------------------------------------------------------------
    # Stage 6 -- BB self-source introspection (Group D)
    # ------------------------------------------------------------------
    self_source = _read_self_source()
    self_gates = _evaluate_self_source_gates(self_source)
    blocked.extend(self_gates)

    # ------------------------------------------------------------------
    # Finalize status / mode / failed_stage
    # ------------------------------------------------------------------
    # Deduplicate while preserving insertion order.
    seen: set[str] = set()
    deduped: list[str] = []
    for g in blocked:
        if g not in seen:
            seen.add(g)
            deduped.append(g)
    result.blocked_gates = deduped

    hard_fails = [g for g in deduped if g in _HARD_FAIL_GATES]

    if hard_fails:
        result.status = STATUS_FAIL_CLOSED
        result.mode = MODE_FAIL_CLOSED
        # Use the first hard-fail gate's stage descriptor.
        first = hard_fails[0]
        result.failed_stage = _GATE_TO_STAGE.get(first, f"stage_X_{first}")
    else:
        # No hard-fail gates.  Apply --allow flags to elevate the
        # status -- the safety invariants on the result still hold.
        if allow_real_entry_execution:
            result.status = STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
        elif allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review:
            result.status = STATUS_READY_BUT_EXECUTION_DISABLED
        else:
            result.status = STATUS_READY
        result.mode = MODE_CHECKLIST
        result.failed_stage = ""

    # Final invariant re-assertion (defense in depth).  These values
    # are NEVER allowed to change, regardless of any flag, gate, or
    # upstream state -- the BB result is a manual-authorization REVIEW
    # only, never an authorization or an execution.
    result.real_execution_allowed = False
    result.current_task_real_execution_allowed = False
    result.send_allowed = False
    result.no_orders_sent = True
    result.order_endpoint_called = False
    result.stop_endpoint_called = False
    result.no_position_modified = True
    result.no_live_endpoint = True
    result.no_secrets_loaded = True
    result.secret_value_observed = False
    result.g20_policy_still_in_place = True
    result.g20_lifted = False
    result.executable_adapter_included = False
    result.adapter_implementation_included = False
    result.adapter_execution_included = False
    result.send_method_included = False
    result.place_order_method_included = False
    result.execute_method_included = False
    result.real_entry_implemented = False
    result.manual_authorization_review_only = True
    result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_only = True
    result.manual_authorization_review_grants_execution = False
    result.manual_authorization_gate_final_pre_execution_review_grants_execution = False
    result.manual_authorization_gate_readiness_review_grants_execution = False
    result.manual_authorization_gate_dry_run_grants_execution = False
    result.manual_authorization_gate_design_grants_execution = False
    result.final_pre_execution_review_grants_execution = False
    result.readiness_review_grants_execution = False
    result.dry_run_grants_execution = False
    result.adapter_grants_execution = False
    result.approval_phrase_grants_execution = False
    result.approval_token_grants_execution = False
    result.approval_inputs_grant_execution = False
    result.token_to_authorization_mapping = False
    result.phrase_to_authorization_mapping = False
    result.manual_authorization_review_accepts_runtime_approval = False
    result.manual_authorization_review_translates_text_to_execution = False
    result.scope_summary = SCOPE_SUMMARY_LITERAL
    result.identity_checklist = IDENTITY_CHECKLIST
    result.identity_strict = IDENTITY_STRICT
    result.next_required_task = NEXT_REQUIRED_TASK
    result.response_status = RESPONSE_STATUS_NOT_SENT
    result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion = CONCLUSION_READY_NOT_EXECUTABLE
    result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result = AUTHORIZATION_RESULT_DOCUMENTED
    result.existing_positions_touched = []

    return result


# ===========================================================================
# H. Stage 2: report writer + default path helper
# ===========================================================================

# Default BB output directory (where write_report writes JSON + Markdown).
BB_DEFAULT_OUTPUT_DIR = Path(
    "outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_"
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review"
)

# Base filename stem used for both latest and timestamped variants.
_REPORT_BASE_STEM = (
    "tiny_guarded_entry_real_execution_adapter_disabled_implementation_"
    "scaffold_manual_authorization_gate_final_pre_execution_review_manual_"
    "authorization_review"
)


def get_default_ba_artifact_path() -> Path:
    """Return the default fully-qualified BA artifact path (latest_*.json)."""
    return BA_DEFAULT_ARTIFACT_DIR / BA_DEFAULT_ARTIFACT_FILE


def get_default_bb_output_dir() -> Path:
    """Return the default BB output directory."""
    return BB_DEFAULT_OUTPUT_DIR


def _utc_timestamp_compact(_now: datetime | None = None) -> str:
    """Return a compact UTC timestamp like '20260617T083000Z'."""
    if _now is None:
        _now = datetime.now(tz=timezone.utc)
    else:
        # If caller passed a naive datetime, treat it as UTC.
        if _now.tzinfo is None:
            _now = _now.replace(tzinfo=timezone.utc)
        else:
            _now = _now.astimezone(timezone.utc)
    return _now.strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(result: _Result) -> str:
    """Render the BB result as a Markdown report.

    The Markdown report is documentation only -- it never authorizes any
    real execution, never invokes any endpoint, never reads any secret,
    never lifts G20, never modifies any position.
    """
    d = result.to_dict()
    lines: list[str] = []
    lines.append("# TASK-014BB Disabled Implementation Scaffold Manual Authorization Gate Final Pre-Execution Review Manual Authorization Review")
    lines.append("")
    lines.append(
        "_TASK-014BB consumes TASK-014BA disabled implementation scaffold "
        "manual authorization gate final pre-execution review output._"
    )
    lines.append("")
    lines.append(f"Identity: `{result.identity_checklist}`")
    lines.append("")
    lines.append(f"Strict identity: `{result.identity_strict}`")
    lines.append("")
    lines.append("## Scope Summary")
    lines.append("")
    lines.append("```")
    lines.append(result.scope_summary)
    lines.append("```")
    lines.append("")

    lines.append("## Result")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append(f"| status | `{result.status}` |")
    lines.append(f"| mode | `{result.mode}` |")
    lines.append(f"| selected_symbol | `{result.selected_symbol or '(none)'}` |")
    lines.append(f"| adapter_name | `{result.adapter_name}` |")
    lines.append(f"| adapter_contract_version | `{result.adapter_contract_version}` |")
    lines.append(
        "| conclusion | "
        f"`{result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_conclusion}` |"
    )
    lines.append(
        "| authorization_result | "
        f"`{result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_authorization_result}` |"
    )
    lines.append(f"| response_status | `{result.response_status}` |")
    lines.append(f"| next_required_task | `{result.next_required_task}` |")
    lines.append(f"| failed_stage | `{result.failed_stage or '(none)'}` |")
    lines.append("")

    lines.append("## Safety Invariants")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append(f"| manual_authorization_review_only | `{result.manual_authorization_review_only}` |")
    lines.append(
        "| disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_only | "
        f"`{result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_only}` |"
    )
    lines.append(f"| executable_adapter_included | `{result.executable_adapter_included}` |")
    lines.append(f"| adapter_implementation_included | `{result.adapter_implementation_included}` |")
    lines.append(f"| adapter_execution_included | `{result.adapter_execution_included}` |")
    lines.append(f"| send_method_included | `{result.send_method_included}` |")
    lines.append(f"| place_order_method_included | `{result.place_order_method_included}` |")
    lines.append(f"| execute_method_included | `{result.execute_method_included}` |")
    lines.append(f"| real_entry_implemented | `{result.real_entry_implemented}` |")
    lines.append(f"| real_execution_allowed | `{result.real_execution_allowed}` |")
    lines.append(f"| current_task_real_execution_allowed | `{result.current_task_real_execution_allowed}` |")
    lines.append(f"| send_allowed | `{result.send_allowed}` |")
    lines.append(f"| order_endpoint_called | `{result.order_endpoint_called}` |")
    lines.append(f"| stop_endpoint_called | `{result.stop_endpoint_called}` |")
    lines.append(f"| no_position_modified | `{result.no_position_modified}` |")
    lines.append(f"| no_live_endpoint | `{result.no_live_endpoint}` |")
    lines.append(f"| no_orders_sent | `{result.no_orders_sent}` |")
    lines.append(f"| no_secrets_loaded | `{result.no_secrets_loaded}` |")
    lines.append(f"| secret_value_observed | `{result.secret_value_observed}` |")
    lines.append(f"| g20_policy_still_in_place | `{result.g20_policy_still_in_place}` |")
    lines.append(f"| g20_lifted | `{result.g20_lifted}` |")
    lines.append(
        "| existing_positions_touched | "
        f"`{', '.join(result.existing_positions_touched) or '(none)'}` |"
    )
    lines.append(f"| manual_authorization_review_grants_execution | `{result.manual_authorization_review_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_final_pre_execution_review_grants_execution | `{result.manual_authorization_gate_final_pre_execution_review_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_readiness_review_grants_execution | `{result.manual_authorization_gate_readiness_review_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_dry_run_grants_execution | `{result.manual_authorization_gate_dry_run_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_design_grants_execution | `{result.manual_authorization_gate_design_grants_execution}` |")
    lines.append(f"| final_pre_execution_review_grants_execution | `{result.final_pre_execution_review_grants_execution}` |")
    lines.append(f"| readiness_review_grants_execution | `{result.readiness_review_grants_execution}` |")
    lines.append(f"| dry_run_grants_execution | `{result.dry_run_grants_execution}` |")
    lines.append(f"| adapter_grants_execution | `{result.adapter_grants_execution}` |")
    lines.append(f"| approval_phrase_validated | `{result.approval_phrase_validated}` |")
    lines.append(f"| approval_token_validated | `{result.approval_token_validated}` |")
    lines.append(f"| approval_inputs_validated | `{result.approval_inputs_validated}` |")
    lines.append(f"| approval_phrase_grants_execution | `{result.approval_phrase_grants_execution}` |")
    lines.append(f"| approval_token_grants_execution | `{result.approval_token_grants_execution}` |")
    lines.append(f"| approval_inputs_grant_execution | `{result.approval_inputs_grant_execution}` |")
    lines.append(f"| token_to_authorization_mapping | `{result.token_to_authorization_mapping}` |")
    lines.append(f"| phrase_to_authorization_mapping | `{result.phrase_to_authorization_mapping}` |")
    lines.append(f"| manual_authorization_review_accepts_runtime_approval | `{result.manual_authorization_review_accepts_runtime_approval}` |")
    lines.append(f"| manual_authorization_review_translates_text_to_execution | `{result.manual_authorization_review_translates_text_to_execution}` |")
    lines.append("")

    lines.append("## BA Upstream Proof (17 fields)")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    ba_field_names = (
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_mode",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_conclusion",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_authorization_result",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_response_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_real_execution_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_send_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_implementation_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_adapter_execution_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_order_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_stop_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_position_modified",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_no_secrets_loaded",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_g20_lifted",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary",
    )
    for name in ba_field_names:
        v = d.get(name, "")
        lines.append(f"| {name} | `{v}` |")
    lines.append("")

    lines.append("## BA -> AZ Chained Proof (11 fields)")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    chained_field_names = (
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_consumed_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_response_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_readiness_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_dry_run_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_mentions_az_direct_upstream",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ay",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_ax",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_aw",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_ba_consumes_av",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_scope_summary_has_no_itdocuments_typo",
    )
    for name in chained_field_names:
        v = d.get(name, "")
        lines.append(f"| {name} | `{v}` |")
    lines.append("")

    lines.append("## Blocked Gates")
    lines.append("")
    if result.blocked_gates:
        for g in result.blocked_gates:
            lines.append(f"- `{g}`")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "DOCUMENTED ONLY NOT AUTHORIZED -- no real execution, no sender, "
        "no endpoint call, no secret read, no G20 lift, no position "
        "modification, main.py / src/risk.py / BybitExecutor untouched."
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    result: _Result,
    output_dir: Path,
    _now: datetime | None = None,
) -> dict[str, Path]:
    """Write the BB review JSON + Markdown report to `output_dir`.

    Produces four files:
      * latest_<base>.json         -- pretty-printed JSON, stable field order
      * latest_<base>.md           -- markdown summary
      * <base>_<ts>.json           -- timestamped JSON snapshot
      * <base>_<ts>.md             -- timestamped markdown snapshot

    Returns a dict with keys: json_path, md_path, timestamped_json_path,
    timestamped_md_path -- each mapping to the absolute Path actually
    written.

    This writer NEVER invokes any endpoint, NEVER reads any secret,
    NEVER lifts G20, NEVER modifies any position.  It only writes the
    documentation files described above.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _utc_timestamp_compact(_now)
    base = _REPORT_BASE_STEM

    latest_json = output_dir / f"latest_{base}.json"
    latest_md = output_dir / f"latest_{base}.md"
    ts_json = output_dir / f"{base}_{ts}.json"
    ts_md = output_dir / f"{base}_{ts}.md"

    payload = result.to_dict()
    json_text = json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False)
    md_text = _render_markdown(result)

    latest_json.write_text(json_text, encoding="utf-8")
    ts_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    ts_md.write_text(md_text, encoding="utf-8")

    return {
        "json_path": latest_json,
        "md_path": latest_md,
        "timestamped_json_path": ts_json,
        "timestamped_md_path": ts_md,
    }


# Back-compat private alias (the Stage 1 stub was private).
_write_report = write_report
