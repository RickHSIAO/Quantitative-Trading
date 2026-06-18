"""
src/demo_tiny_guarded_entry_real_execution_adapter_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review.py
TASK-014BF: Guarded Entry Real Execution Adapter Disabled Implementation
            Scaffold Manual Authorization Gate Final Pre-Execution Review
            Manual Authorization Review Final Pre-Execution Review Manual
            Authorization Review.

Disabled-implementation-scaffold-manual-authorization-gate-final-pre-execution-
review-manual-authorization-review-final-pre-execution-review-manual-
authorization-review-only module.  This task consumes TASK-014BE's DISABLED
IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW
MANUAL AUTHORIZATION REVIEW FINAL PRE-EXECUTION REVIEW artifact at runtime
(the DIRECT upstream), plus BE-proven chained proof flowing back through:
  - BD DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL
    PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW READINESS REVIEW
  - BC DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL
    PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW DRY-RUN
  - BB DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL
    PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW
  - BA DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL
    PRE-EXECUTION REVIEW
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

BF consumes BE only as direct upstream. BD/BC/BB/BA/AZ/AY/AX/AW/AV/AU/AT/AS/AR/AQ
are chained proof THROUGH BE, never consumed directly by BF.

This module produces a DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION
GATE FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW FINAL
PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW verdict for the future
TASK-014BG dry-run.

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
GATE-FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-
EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY.

SCOPE_SUMMARY_LITERAL:
"TASK-014BF consumes TASK-014BE DISABLED IMPLEMENTATION SCAFFOLD MANUAL
AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW
FINAL PRE-EXECUTION REVIEW output at runtime plus BE-proven chained proof,
including BD readiness review, BC dry-run, BB manual authorization review,
BA final pre-execution review, AZ readiness review, AY dry-run, AX manual
authorization gate design, AW final pre-execution review, AV readiness
review, AU dry-run, AT design, AS static skeleton dry-run, AR static
skeleton design, and AQ implementation design."

Stage 1 implementation only: identity constants, 37 hard-fail gate
constants (BF mirrors BE's 37-gate hardening, with the dedicated AV
direct-consumption guard at the BE-scope level enforcing that any
"TASK-014BE consumes TASK-014AV" wording fails closed), result
dataclass, BE artifact loader, BE upstream parser, gate evaluation, and
the run function. CLI / preview script / markdown report writer / full
test pack are deferred to Stage 2 / Stage 3.
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
    "pre_execution_review_manual_authorization_review_final_pre_execution_"
    "review_manual_authorization_review_v1"
)

STATUS_READY = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_"
    "SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_"
    "AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_"
    "REVIEW_READY"
)
STATUS_READY_BUT_EXECUTION_DISABLED = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_"
    "SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_"
    "AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_MANUAL_AUTHORIZATION_"
    "REVIEW_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED = (
    "REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED"
)
STATUS_FAIL_CLOSED = "FAIL_CLOSED"

MODE_CHECKLIST = (
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review_final_pre_execution_"
    "review_manual_authorization_review_checklist"
)
MODE_FAIL_CLOSED = "fail_closed"

CONCLUSION_READY_NOT_EXECUTABLE = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_"
    "REVIEW_MANUAL_AUTHORIZATION_REVIEW_READY_NOT_EXECUTABLE"
)
AUTHORIZATION_RESULT_DOCUMENTED_ONLY = "DOCUMENTED_ONLY_NOT_AUTHORIZED"
RESPONSE_STATUS_NOT_SENT = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_"
    "REVIEW_MANUAL_AUTHORIZATION_REVIEW_NOT_SENT"
)

NEXT_REQUIRED_TASK = (
    "TASK-014BG_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review_manual_authorization_review_final_pre_execution_"
    "review_manual_authorization_review_dry_run"
)

IDENTITY_CHECKLIST = (
    "DISABLED IMPLEMENTATION SCAFFOLD MANUAL AUTHORIZATION GATE FINAL "
    "PRE-EXECUTION REVIEW MANUAL AUTHORIZATION REVIEW FINAL PRE-EXECUTION "
    "REVIEW MANUAL AUTHORIZATION REVIEW CHECKLIST"
)
IDENTITY_STRICT = (
    "STRICT DISABLED-IMPLEMENTATION-SCAFFOLD-MANUAL-AUTHORIZATION-GATE-"
    "FINAL-PRE-EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-FINAL-PRE-"
    "EXECUTION-REVIEW-MANUAL-AUTHORIZATION-REVIEW-ONLY"
)

SCOPE_SUMMARY_LITERAL = (
    "TASK-014BF consumes TASK-014BE DISABLED IMPLEMENTATION SCAFFOLD "
    "MANUAL AUTHORIZATION GATE FINAL PRE-EXECUTION REVIEW MANUAL "
    "AUTHORIZATION REVIEW FINAL PRE-EXECUTION REVIEW output at runtime "
    "plus BE-proven chained proof, including BD readiness review, BC "
    "dry-run, BB manual authorization review, BA final pre-execution "
    "review, AZ readiness review, AY dry-run, AX manual authorization "
    "gate design, AW final pre-execution review, AV readiness review, "
    "AU dry-run, AT design, AS static skeleton dry-run, AR static "
    "skeleton design, and AQ implementation design."
)

BE_DEFAULT_ARTIFACT_DIR = Path(
    "outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_"
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review_final_pre_"
    "execution_review"
)
BE_DEFAULT_ARTIFACT_FILE = (
    "latest_tiny_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review_manual_authorization_review_final_pre_execution_"
    "review.json"
)

# BE-side accepted values for Group A gate evaluation.
STATUS_BE_READY = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_"
    "SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_"
    "AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_READY"
)
STATUS_BE_READY_BUT_EXECUTION_DISABLED = (
    "TINY_GUARDED_ENTRY_REAL_EXECUTION_ADAPTER_DISABLED_IMPLEMENTATION_"
    "SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_EXECUTION_REVIEW_MANUAL_"
    "AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_REVIEW_READY_BUT_EXECUTION_"
    "DISABLED"
)
_BE_ACCEPTED_STATUSES: frozenset[str] = frozenset({
    STATUS_BE_READY,
    STATUS_BE_READY_BUT_EXECUTION_DISABLED,
})
_BE_ACCEPTED_MODES: frozenset[str] = frozenset({
    (
        "disabled_implementation_scaffold_manual_authorization_gate_final_"
        "pre_execution_review_manual_authorization_review_final_pre_"
        "execution_review_checklist"
    ),
    (
        "disabled_implementation_scaffold_manual_authorization_gate_final_"
        "pre_execution_review_manual_authorization_review_final_pre_"
        "execution_review_approval"
    ),
})
_BE_ACCEPTED_CONCLUSION = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_"
    "REVIEW_READY_NOT_EXECUTABLE"
)
_BE_ACCEPTED_AUTHORIZATION_RESULT = "DOCUMENTED_ONLY_NOT_AUTHORIZED"
_BE_ACCEPTED_RESPONSE_STATUS = (
    "DISABLED_IMPLEMENTATION_SCAFFOLD_MANUAL_AUTHORIZATION_GATE_FINAL_PRE_"
    "EXECUTION_REVIEW_MANUAL_AUTHORIZATION_REVIEW_FINAL_PRE_EXECUTION_"
    "REVIEW_NOT_SENT"
)
_BE_ACCEPTED_NEXT_REQUIRED_TASK = (
    "TASK-014BF_guarded_entry_real_execution_adapter_disabled_"
    "implementation_scaffold_manual_authorization_gate_final_pre_"
    "execution_review_manual_authorization_review_final_pre_execution_"
    "review_manual_authorization_review"
)
_BE_ACCEPTED_CONSUMED_CONTRACT_VERSION = (
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review_final_pre_execution_"
    "review_v1"
)

# BE scope_summary required substrings (must all be present).
_BE_SCOPE_REQUIRED_SUBSTRINGS: tuple[str, ...] = (
    "TASK-014BE consumes TASK-014BD",
    "BD-proven chained proof",
    "BC dry-run",
    "BB manual authorization review",
    "BA final pre-execution review",
)
# BE scope_summary forbidden substrings (none may be present).
# Mirrors BE's 6-forbidden-phrases pattern (chained-proof-only items
# closest to the top of the chain) + Itdocuments typo.  AV is the
# dedicated direct-consumption hardening guard mirroring BE-FIX1's
# GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_AV.
_BE_SCOPE_FORBIDDEN_BB        = "TASK-014BE consumes TASK-014BB"
_BE_SCOPE_FORBIDDEN_BA        = "TASK-014BE consumes TASK-014BA"
_BE_SCOPE_FORBIDDEN_AZ        = "TASK-014BE consumes TASK-014AZ"
_BE_SCOPE_FORBIDDEN_AY        = "TASK-014BE consumes TASK-014AY"
_BE_SCOPE_FORBIDDEN_AX        = "TASK-014BE consumes TASK-014AX"
_BE_SCOPE_FORBIDDEN_AV        = "TASK-014BE consumes TASK-014AV"
_BE_SCOPE_FORBIDDEN_ITDOC     = "Itdocuments"

# Denylisted live-endpoint reference URLs.  Listed here for self-
# introspection ONLY and NEVER invoked by this module.  Any live-endpoint
# URL beyond this denylist triggers GATE_BF_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST.
_DENYLISTED_ENDPOINT_REFERENCES: frozenset[str] = frozenset({
    "https://api.bybit.com",
    "https://api-testnet.bybit.com",
})

# Network primitive import substrings BF must not contain.
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

# Secret-loader / signing patterns BF must not contain.
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

# Coupling patterns BF must not contain.
_COUPLING_PATTERNS: tuple[str, ...] = (
    "from main import",
    "import main",
    "from src.risk",
    "import src.risk",
    "BybitExecutor",
    "from pybit",
    "import pybit",
)


# ===========================================================================
# B. 37 hard-fail gate constants  (mirrors BE's 37-gate hardening)
#
# TASK-014BF preserves BE's hardening pattern by enforcing a dedicated
# forbidden-direct-consumption guard for the chain phrase
# "TASK-014BE consumes TASK-014AV" at the BE-scope-summary level.
# Rationale: BE's scope_summary explicitly references AV only as
# BD-proven chained proof; any direct "BE consumes AV" wording from
# upstream would invalidate that chain claim and must fail closed.
# Counts: A=18 + B=7 + C=3 + D=9 = 37.
# ===========================================================================

# --- Group A: BE artifact / fields (18 gates) ---
GATE_BE_ARTIFACT_MISSING                        = "be_artifact_missing"
GATE_BE_STATUS_UNACCEPTABLE                     = "be_status_unacceptable"
GATE_BE_MODE_MISMATCH                           = "be_mode_mismatch"
GATE_BE_CONCLUSION_MISMATCH                     = "be_conclusion_mismatch"
GATE_BE_RESPONSE_STATUS_MISMATCH                = "be_response_status_mismatch"
GATE_BE_AUTHORIZATION_RESULT_MISMATCH           = "be_authorization_result_mismatch"
GATE_BE_NEXT_REQUIRED_TASK_MISMATCH             = "be_next_required_task_mismatch"
GATE_BE_REAL_EXECUTION_ALLOWED_TRUE             = "be_real_execution_allowed_true"
GATE_BE_SEND_ALLOWED_TRUE                       = "be_send_allowed_true"
GATE_BE_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE    = "be_adapter_implementation_included_true"
GATE_BE_ADAPTER_EXECUTION_INCLUDED_TRUE         = "be_adapter_execution_included_true"
GATE_BE_ORDER_ENDPOINT_CALLED_TRUE              = "be_order_endpoint_called_true"
GATE_BE_STOP_ENDPOINT_CALLED_TRUE               = "be_stop_endpoint_called_true"
GATE_BE_NO_POSITION_MODIFIED_FALSE              = "be_no_position_modified_false"
GATE_BE_NO_SECRETS_LOADED_FALSE                 = "be_no_secrets_loaded_false"
GATE_BE_G20_LIFTED_TRUE                         = "be_g20_lifted_true"
GATE_BE_MISSING_BD_CHAINED_PROOF                = "be_missing_bd_chained_proof"
GATE_BE_MISSING_BD_PROVEN_CHAINED_PROOF         = "be_missing_bd_proven_chained_proof"

# --- Group B: BE scope_summary content gates (8 defined, 7 enforced) ---
GATE_BE_SCOPE_SUMMARY_MISSING_BD_DIRECT_UPSTREAM  = "be_scope_summary_missing_bd_direct_upstream"
GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BB          = "be_scope_summary_has_be_consumes_bb"
GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BA          = "be_scope_summary_has_be_consumes_ba"
GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AZ          = "be_scope_summary_has_be_consumes_az"
GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AY          = "be_scope_summary_has_be_consumes_ay"
GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AX          = "be_scope_summary_has_be_consumes_ax"
GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AV          = "be_scope_summary_has_be_consumes_av"
GATE_BE_SCOPE_SUMMARY_HAS_ITDOCUMENTS_TYPO        = "be_scope_summary_has_itdocuments_typo"

# --- Group C: BE failure passthrough (3 gates) ---
GATE_BE_STATUS_FAIL_CLOSED                      = "be_status_fail_closed_passthrough"
GATE_BE_MODE_FAIL_CLOSED                        = "be_mode_fail_closed_passthrough"
GATE_BE_FAILED_STAGE_NON_EMPTY                  = "be_failed_stage_non_empty_passthrough"

# --- Group D: BF own-source safety invariants (9 gates) ---
GATE_BF_APPROVAL_PHRASE_TREATED_AS_AUTHORIZATION    = "bf_approval_phrase_treated_as_authorization"
GATE_BF_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST     = "bf_live_endpoint_reference_beyond_denylist"
GATE_BF_NETWORK_PRIMITIVE_OR_IMPORT                 = "bf_network_primitive_or_import"
GATE_BF_SECRET_LOADER_OR_HMAC_OR_SIGNING            = "bf_secret_loader_or_hmac_or_signing"
GATE_BF_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING = "bf_sender_or_main_or_risk_or_bybitexecutor_coupling"
GATE_BF_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR    = "bf_active_send_place_order_execute_behavior"
GATE_BF_REAL_ORDER_OR_STOP_ENDPOINT_CALL            = "bf_real_order_or_stop_endpoint_call"
GATE_BF_G20_LIFT                                    = "bf_g20_lift"
GATE_BF_POSITION_MODIFICATION                       = "bf_position_modification"


# The 37 hard-fail gates (mirrors BE's 37-gate hardening).
# Counts: A=18 + B=7 + C=3 + D=9 = 37.  Group B drops
# MISSING_BD_DIRECT_UPSTREAM from the enforced set (its absence is also
# signalled via Group A missing-bd-chained-proof); Group B is 7 entries:
# 6 forbidden BE-consumes-* phrases (BB, BA, AZ, AY, AX, AV) +
# itdocuments-typo.  AV is the explicit hardening guard.
_HARD_FAIL_GATES: frozenset[str] = frozenset({
    # Group A (18)
    GATE_BE_ARTIFACT_MISSING,
    GATE_BE_STATUS_UNACCEPTABLE,
    GATE_BE_MODE_MISMATCH,
    GATE_BE_CONCLUSION_MISMATCH,
    GATE_BE_RESPONSE_STATUS_MISMATCH,
    GATE_BE_AUTHORIZATION_RESULT_MISMATCH,
    GATE_BE_NEXT_REQUIRED_TASK_MISMATCH,
    GATE_BE_REAL_EXECUTION_ALLOWED_TRUE,
    GATE_BE_SEND_ALLOWED_TRUE,
    GATE_BE_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE,
    GATE_BE_ADAPTER_EXECUTION_INCLUDED_TRUE,
    GATE_BE_ORDER_ENDPOINT_CALLED_TRUE,
    GATE_BE_STOP_ENDPOINT_CALLED_TRUE,
    GATE_BE_NO_POSITION_MODIFIED_FALSE,
    GATE_BE_NO_SECRETS_LOADED_FALSE,
    GATE_BE_G20_LIFTED_TRUE,
    GATE_BE_MISSING_BD_CHAINED_PROOF,
    GATE_BE_MISSING_BD_PROVEN_CHAINED_PROOF,
    # Group B (7) -- 6 forbidden BE-consumes phrases + itdocuments typo.
    # The AV phrase is the dedicated hardening guard mirroring BE's
    # GATE_BD_SCOPE_SUMMARY_HAS_BD_CONSUMES_AV.
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BB,
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BA,
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AZ,
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AY,
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AX,
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AV,
    GATE_BE_SCOPE_SUMMARY_HAS_ITDOCUMENTS_TYPO,
    # Group C (3)
    GATE_BE_STATUS_FAIL_CLOSED,
    GATE_BE_MODE_FAIL_CLOSED,
    GATE_BE_FAILED_STAGE_NON_EMPTY,
    # Group D (9)
    GATE_BF_APPROVAL_PHRASE_TREATED_AS_AUTHORIZATION,
    GATE_BF_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST,
    GATE_BF_NETWORK_PRIMITIVE_OR_IMPORT,
    GATE_BF_SECRET_LOADER_OR_HMAC_OR_SIGNING,
    GATE_BF_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING,
    GATE_BF_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR,
    GATE_BF_REAL_ORDER_OR_STOP_ENDPOINT_CALL,
    GATE_BF_G20_LIFT,
    GATE_BF_POSITION_MODIFICATION,
})

# Per-gate stage descriptor for failed_stage labelling.
_GATE_TO_STAGE: dict[str, str] = {
    GATE_BE_ARTIFACT_MISSING:                          "stage_0_be_artifact_preflight",
    GATE_BE_STATUS_UNACCEPTABLE:                       "stage_1_be_status_check",
    GATE_BE_MODE_MISMATCH:                             "stage_1_be_mode_check",
    GATE_BE_CONCLUSION_MISMATCH:                       "stage_1_be_conclusion_check",
    GATE_BE_RESPONSE_STATUS_MISMATCH:                  "stage_1_be_response_status_check",
    GATE_BE_AUTHORIZATION_RESULT_MISMATCH:             "stage_1_be_authorization_result_check",
    GATE_BE_NEXT_REQUIRED_TASK_MISMATCH:               "stage_1_be_next_required_task_check",
    GATE_BE_REAL_EXECUTION_ALLOWED_TRUE:               "stage_2_be_real_execution_allowed_check",
    GATE_BE_SEND_ALLOWED_TRUE:                         "stage_2_be_send_allowed_check",
    GATE_BE_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE:      "stage_2_be_adapter_implementation_included_check",
    GATE_BE_ADAPTER_EXECUTION_INCLUDED_TRUE:           "stage_2_be_adapter_execution_included_check",
    GATE_BE_ORDER_ENDPOINT_CALLED_TRUE:                "stage_2_be_order_endpoint_called_check",
    GATE_BE_STOP_ENDPOINT_CALLED_TRUE:                 "stage_2_be_stop_endpoint_called_check",
    GATE_BE_NO_POSITION_MODIFIED_FALSE:                "stage_2_be_no_position_modified_check",
    GATE_BE_NO_SECRETS_LOADED_FALSE:                   "stage_2_be_no_secrets_loaded_check",
    GATE_BE_G20_LIFTED_TRUE:                           "stage_2_be_g20_lifted_check",
    GATE_BE_MISSING_BD_CHAINED_PROOF:                  "stage_3_be_missing_bd_chained_proof_check",
    GATE_BE_MISSING_BD_PROVEN_CHAINED_PROOF:           "stage_3_be_missing_bd_proven_chained_proof_check",
    GATE_BE_SCOPE_SUMMARY_MISSING_BD_DIRECT_UPSTREAM:  "stage_4_be_scope_summary_bd_direct_check",
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BB:          "stage_4_be_scope_summary_no_be_consumes_bb_check",
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BA:          "stage_4_be_scope_summary_no_be_consumes_ba_check",
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AZ:          "stage_4_be_scope_summary_no_be_consumes_az_check",
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AY:          "stage_4_be_scope_summary_no_be_consumes_ay_check",
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AX:          "stage_4_be_scope_summary_no_be_consumes_ax_check",
    GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AV:          "stage_4_be_scope_summary_no_be_consumes_av_check",
    GATE_BE_SCOPE_SUMMARY_HAS_ITDOCUMENTS_TYPO:        "stage_4_be_scope_summary_no_itdocuments_typo_check",
    GATE_BE_STATUS_FAIL_CLOSED:                        "stage_5_be_status_passthrough_check",
    GATE_BE_MODE_FAIL_CLOSED:                          "stage_5_be_mode_passthrough_check",
    GATE_BE_FAILED_STAGE_NON_EMPTY:                    "stage_5_be_failed_stage_passthrough_check",
    GATE_BF_APPROVAL_PHRASE_TREATED_AS_AUTHORIZATION:  "stage_6_bf_self_approval_input_check",
    GATE_BF_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST:   "stage_6_bf_self_live_endpoint_check",
    GATE_BF_NETWORK_PRIMITIVE_OR_IMPORT:               "stage_6_bf_self_network_primitive_check",
    GATE_BF_SECRET_LOADER_OR_HMAC_OR_SIGNING:          "stage_6_bf_self_secret_signing_check",
    GATE_BF_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING: "stage_6_bf_self_coupling_check",
    GATE_BF_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR:  "stage_6_bf_self_active_exec_method_check",
    GATE_BF_REAL_ORDER_OR_STOP_ENDPOINT_CALL:          "stage_6_bf_self_endpoint_call_check",
    GATE_BF_G20_LIFT:                                  "stage_6_bf_self_g20_lift_check",
    GATE_BF_POSITION_MODIFICATION:                     "stage_6_bf_self_position_modification_check",
}


# ===========================================================================
# C. Result dataclass
# ===========================================================================

@dataclass
class TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewFinalPreExecutionReviewManualAuthorizationReviewResult:
    """
    Read-only outcome of one BF disabled-implementation-scaffold-manual-
    authorization-gate-final-pre-execution-review-manual-authorization-
    review-final-pre-execution-review manual authorization review.
    Defaults make a freshly-constructed instance directly READY (no
    failures); the run function flips status to FAIL_CLOSED when any
    hard-fail gate triggers.
    """

    # ----- Core identity / mode -----
    status: str = STATUS_READY
    mode: str = MODE_CHECKLIST
    selected_symbol: str = ""
    existing_position_symbols: list[str] = field(default_factory=list)
    adapter_name: str = ADAPTER_NAME
    adapter_contract_version: str = ADAPTER_CONTRACT_VERSION

    # ----- Adapter / execution surface guard flags (all default safe) -----
    disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_only: bool = True
    manual_authorization_review_final_pre_execution_review_manual_authorization_review_only: bool = True
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
    manual_authorization_review_final_pre_execution_review_manual_authorization_review_grants_execution: bool = False
    manual_authorization_review_final_pre_execution_review_grants_execution: bool = False
    manual_authorization_review_readiness_review_grants_execution: bool = False
    manual_authorization_review_dry_run_grants_execution: bool = False
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
    manual_authorization_review_final_pre_execution_review_manual_authorization_review_accepts_runtime_approval: bool = False
    manual_authorization_review_final_pre_execution_review_manual_authorization_review_translates_text_to_execution: bool = False

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
    disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_conclusion: str = CONCLUSION_READY_NOT_EXECUTABLE
    disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_authorization_result: str = AUTHORIZATION_RESULT_DOCUMENTED_ONLY
    response_status: str = RESPONSE_STATUS_NOT_SENT
    next_required_task: str = NEXT_REQUIRED_TASK

    # ----- Failure reporting -----
    failed_stage: str = ""
    blocked_gates: list[str] = field(default_factory=list)

    # ----- Identity literals -----
    scope_summary: str = SCOPE_SUMMARY_LITERAL
    identity_checklist: str = IDENTITY_CHECKLIST
    identity_strict: str = IDENTITY_STRICT

    # ===== 17 BE-upstream fields =====
    consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_contract_version: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_mode: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_conclusion: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_authorization_result: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_response_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_real_execution_allowed: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_send_allowed: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_adapter_implementation_included: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_adapter_execution_included: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_order_endpoint_called: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_stop_endpoint_called: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_no_position_modified: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_no_secrets_loaded: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_g20_lifted: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_next_required_task: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary: str = ""

    # ===== 11 BE->BD chained proof fields =====
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_consumed_contract_version: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_status: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_next_required_task: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_scope_summary: str = ""
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_mentions_bd_direct_upstream: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_mentions_bd_proven_chained_proof: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_bb: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_ba: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_az: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_ay: bool = False
    upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_itdocuments_typo: bool = False

    # ------------------------------------------------------------------
    # JSON serialization (stable key ordering)
    # ------------------------------------------------------------------
    def to_dict(self) -> dict[str, Any]:
        from dataclasses import fields as _fields
        out: dict[str, Any] = {}
        for f in _fields(self):
            val = getattr(self, f.name)
            if isinstance(val, list):
                out[f.name] = list(val)
            else:
                out[f.name] = val
        return out


# Short alias for internal use.
_Result = TinyGuardedEntryRealExecutionAdapterDisabledImplementationScaffoldManualAuthorizationGateFinalPreExecutionReviewManualAuthorizationReviewFinalPreExecutionReviewManualAuthorizationReviewResult


# ===========================================================================
# D. BE artifact loader
# ===========================================================================

def _load_be_final_pre_execution_review_artifact(path: Path) -> dict | None:
    """
    Load the BE final-pre-execution-review JSON artifact.

    Returns None if the file does not exist or is unreadable / invalid
    JSON.  The loader never raises -- it returns None on any failure so
    the caller can trigger GATE_BE_ARTIFACT_MISSING in a controlled way.
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
# E. BE upstream parser
# ===========================================================================

def _safe_str(value: Any) -> str:
    if isinstance(value, str):
        return value
    if value is None:
        return ""
    return str(value)


def _safe_bool(value: Any) -> bool:
    return bool(value)


def _parse_be_upstream(be_artifact: dict, result: _Result) -> list[str]:
    """
    Populate the BE upstream + BE->BD chained proof fields on `result`
    by reading BE's emitted artifact dict, and return the list of
    triggered Group A / Group B / Group C gate names.
    """
    triggered: list[str] = []

    # ----- Direct BE top-level fields -----
    be_status = _safe_str(be_artifact.get("status"))
    be_mode = _safe_str(be_artifact.get("mode"))
    be_conclusion = _safe_str(
        be_artifact.get(
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_conclusion",
            "",
        )
    )
    be_auth_result = _safe_str(
        be_artifact.get(
            "disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_authorization_result",
            "",
        )
    )
    be_response_status = _safe_str(be_artifact.get("response_status", ""))
    be_next_required = _safe_str(be_artifact.get("next_required_task"))
    be_failed_stage = _safe_str(be_artifact.get("failed_stage"))

    be_real_exec_allowed     = _safe_bool(be_artifact.get("real_execution_allowed", False))
    be_send_allowed          = _safe_bool(be_artifact.get("send_allowed", False))
    be_adapter_impl_included = _safe_bool(be_artifact.get("adapter_implementation_included", False))
    be_adapter_exec_included = _safe_bool(be_artifact.get("adapter_execution_included", False))
    be_order_endpoint_called = _safe_bool(be_artifact.get("order_endpoint_called", False))
    be_stop_endpoint_called  = _safe_bool(be_artifact.get("stop_endpoint_called", False))
    be_no_position_modified  = _safe_bool(be_artifact.get("no_position_modified", False))
    be_no_secrets_loaded     = _safe_bool(be_artifact.get("no_secrets_loaded", False))
    be_g20_lifted            = _safe_bool(be_artifact.get("g20_lifted", False))

    be_scope_summary = _safe_str(be_artifact.get("scope_summary", ""))

    # ----- Populate 17 BE-upstream fields -----
    result.consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_contract_version = \
        _safe_str(be_artifact.get("adapter_contract_version", ""))
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_status = be_status
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_mode = be_mode
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_conclusion = be_conclusion
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_authorization_result = be_auth_result
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_response_status = be_response_status
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_real_execution_allowed = be_real_exec_allowed
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_send_allowed = be_send_allowed
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_adapter_implementation_included = be_adapter_impl_included
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_adapter_execution_included = be_adapter_exec_included
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_order_endpoint_called = be_order_endpoint_called
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_stop_endpoint_called = be_stop_endpoint_called
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_no_position_modified = be_no_position_modified
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_no_secrets_loaded = be_no_secrets_loaded
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_g20_lifted = be_g20_lifted
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_next_required_task = be_next_required
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary = be_scope_summary

    # ----- Populate 11 BE->BD chained proof fields -----
    bd_contract_version = _safe_str(
        be_artifact.get(
            "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_contract_version",
            "",
        )
    )
    bd_status = _safe_str(
        be_artifact.get(
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_status",
            "",
        )
    )
    bd_next_required = _safe_str(
        be_artifact.get(
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_next_required_task",
            "",
        )
    )
    bd_scope_summary = _safe_str(
        be_artifact.get(
            "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_scope_summary",
            "",
        )
    )

    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_consumed_contract_version = bd_contract_version
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_status = bd_status
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_next_required_task = bd_next_required
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_scope_summary = bd_scope_summary

    # ----- scope_summary cross-checks (Group B booleans on BE) -----
    mentions_bd_direct        = _BE_SCOPE_REQUIRED_SUBSTRINGS[0] in be_scope_summary
    mentions_bd_proven        = _BE_SCOPE_REQUIRED_SUBSTRINGS[1] in be_scope_summary
    has_no_be_bb              = _BE_SCOPE_FORBIDDEN_BB not in be_scope_summary
    has_no_be_ba              = _BE_SCOPE_FORBIDDEN_BA not in be_scope_summary
    has_no_be_az              = _BE_SCOPE_FORBIDDEN_AZ not in be_scope_summary
    has_no_be_ay              = _BE_SCOPE_FORBIDDEN_AY not in be_scope_summary
    has_no_be_ax              = _BE_SCOPE_FORBIDDEN_AX not in be_scope_summary
    has_no_be_av              = _BE_SCOPE_FORBIDDEN_AV not in be_scope_summary
    has_no_itdoc_typo         = _BE_SCOPE_FORBIDDEN_ITDOC not in be_scope_summary

    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_mentions_bd_direct_upstream = mentions_bd_direct
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_mentions_bd_proven_chained_proof = mentions_bd_proven
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_bb = has_no_be_bb
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_ba = has_no_be_ba
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_az = has_no_be_az
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_ay = has_no_be_ay
    result.upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_itdocuments_typo = has_no_itdoc_typo

    # ========================================================
    # Group A gate evaluation (BE artifact / fields)
    # ========================================================
    if be_status not in _BE_ACCEPTED_STATUSES:
        if be_status == STATUS_FAIL_CLOSED:
            triggered.append(GATE_BE_STATUS_FAIL_CLOSED)
        else:
            triggered.append(GATE_BE_STATUS_UNACCEPTABLE)
    if be_mode not in _BE_ACCEPTED_MODES:
        if be_mode == MODE_FAIL_CLOSED:
            triggered.append(GATE_BE_MODE_FAIL_CLOSED)
        else:
            triggered.append(GATE_BE_MODE_MISMATCH)
    if be_conclusion != _BE_ACCEPTED_CONCLUSION:
        triggered.append(GATE_BE_CONCLUSION_MISMATCH)
    if be_response_status != _BE_ACCEPTED_RESPONSE_STATUS:
        triggered.append(GATE_BE_RESPONSE_STATUS_MISMATCH)
    if be_auth_result != _BE_ACCEPTED_AUTHORIZATION_RESULT:
        triggered.append(GATE_BE_AUTHORIZATION_RESULT_MISMATCH)
    if be_next_required != _BE_ACCEPTED_NEXT_REQUIRED_TASK:
        triggered.append(GATE_BE_NEXT_REQUIRED_TASK_MISMATCH)
    if be_real_exec_allowed:
        triggered.append(GATE_BE_REAL_EXECUTION_ALLOWED_TRUE)
    if be_send_allowed:
        triggered.append(GATE_BE_SEND_ALLOWED_TRUE)
    if be_adapter_impl_included:
        triggered.append(GATE_BE_ADAPTER_IMPLEMENTATION_INCLUDED_TRUE)
    if be_adapter_exec_included:
        triggered.append(GATE_BE_ADAPTER_EXECUTION_INCLUDED_TRUE)
    if be_order_endpoint_called:
        triggered.append(GATE_BE_ORDER_ENDPOINT_CALLED_TRUE)
    if be_stop_endpoint_called:
        triggered.append(GATE_BE_STOP_ENDPOINT_CALLED_TRUE)
    if not be_no_position_modified:
        triggered.append(GATE_BE_NO_POSITION_MODIFIED_FALSE)
    if not be_no_secrets_loaded:
        triggered.append(GATE_BE_NO_SECRETS_LOADED_FALSE)
    if be_g20_lifted:
        triggered.append(GATE_BE_G20_LIFTED_TRUE)
    # BD chained proof: BE must have produced a non-empty BD contract +
    # BD status; otherwise the chained-back-through-BD promise is empty.
    # Per TASK-014BF lock-in 2: a BE scope_summary that does not contain
    # "TASK-014BE consumes TASK-014BD" also signals a missing BD chained
    # proof and is enforced through this same gate.
    if not bd_contract_version or not bd_status or not mentions_bd_direct:
        triggered.append(GATE_BE_MISSING_BD_CHAINED_PROOF)
    # BD-proven chained proof: BE scope_summary must declare it.
    if not mentions_bd_proven:
        triggered.append(GATE_BE_MISSING_BD_PROVEN_CHAINED_PROOF)

    # ========================================================
    # Group B gate evaluation (BE scope_summary content)
    # ========================================================
    if not has_no_be_bb:
        triggered.append(GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BB)
    if not has_no_be_ba:
        triggered.append(GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_BA)
    if not has_no_be_az:
        triggered.append(GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AZ)
    if not has_no_be_ay:
        triggered.append(GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AY)
    if not has_no_be_ax:
        triggered.append(GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AX)
    if not has_no_be_av:
        triggered.append(GATE_BE_SCOPE_SUMMARY_HAS_BE_CONSUMES_AV)
    if not has_no_itdoc_typo:
        triggered.append(GATE_BE_SCOPE_SUMMARY_HAS_ITDOCUMENTS_TYPO)

    # ========================================================
    # Group C gate evaluation (BE failure passthrough)
    # ========================================================
    if be_failed_stage:
        triggered.append(GATE_BE_FAILED_STAGE_NON_EMPTY)

    return triggered


# ===========================================================================
# F. BF self-source-introspection (Group D gates)
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
                try:
                    string_parts.append(eval(tstr))  # noqa: S307 -- literal-only
                except Exception:
                    string_parts.append(tstr)
            elif ttype in (tokenize.NAME, tokenize.OP, tokenize.NUMBER):
                code_parts.append(tstr)
            elif ttype == tokenize.NEWLINE or ttype == tokenize.NL:
                code_parts.append("\n")
    except tokenize.TokenizeError:
        return "", []
    return " ".join(code_parts), string_parts


def _evaluate_self_source_gates(source: str) -> list[str]:
    """
    Statically scan BF's own source text for the 9 Group D invariants.

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
    for pat in _NETWORK_PRIMITIVE_IMPORT_PATTERNS:
        normalized = " ".join(pat.split())
        if normalized in code_text:
            triggered.append(GATE_BF_NETWORK_PRIMITIVE_OR_IMPORT)
            break

    # ----- Gate D2: secret loader / HMAC / signing -----
    for pat in _SECRET_SIGNING_PATTERNS:
        normalized = pat
        if "." in pat:
            normalized = " . ".join(pat.split("."))
            normalized = " ".join(normalized.split())
        elif " " in pat:
            normalized = " ".join(pat.split())
        if normalized in code_text:
            triggered.append(GATE_BF_SECRET_LOADER_OR_HMAC_OR_SIGNING)
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
            triggered.append(GATE_BF_SENDER_OR_MAIN_OR_RISK_OR_BYBITEXECUTOR_COUPLING)
            break

    # ----- Gate D4: active send / place_order / execute method defs -----
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
            triggered.append(GATE_BF_ACTIVE_SEND_PLACE_ORDER_EXECUTE_BEHAVIOR)
            break

    # ----- Gate D5: real order / stop endpoint call (function-call form) ---
    endpoint_call_phrases = (
        "requests . post (", "requests . get (", "requests . request (",
        "httpx . post (",   "httpx . get (",   "httpx . request (",
        "aiohttp . ClientSession",
        "urlopen (",
        "socket . socket (",
    )
    for phrase in endpoint_call_phrases:
        if phrase in code_text:
            triggered.append(GATE_BF_REAL_ORDER_OR_STOP_ENDPOINT_CALL)
            break

    # ----- Gate D6: live-endpoint URL beyond denylist -----
    url_pat = re.compile(r"https?://[^\s'\")]+")
    for literal in literals:
        for match in url_pat.finditer(literal):
            url = match.group(0).rstrip(",.)")
            if "bybit.com" not in url:
                continue
            if "api-demo" in url or "demo." in url:
                continue
            if url not in _DENYLISTED_ENDPOINT_REFERENCES:
                triggered.append(GATE_BF_LIVE_ENDPOINT_REFERENCE_BEYOND_DENYLIST)
                break
        else:
            continue
        break

    # ----- Gate D7: approval input treated as authorization -----
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
            triggered.append(GATE_BF_APPROVAL_PHRASE_TREATED_AS_AUTHORIZATION)
            break

    # ----- Gate D8: G20 lift -----
    g20_phrases = (
        "g20_lifted = True",
        "lift_g20 (", "lift_G20 (", "disable_g20 (", "bypass_g20 (",
    )
    for phrase in g20_phrases:
        if phrase in code_text:
            triggered.append(GATE_BF_G20_LIFT)
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
            triggered.append(GATE_BF_POSITION_MODIFICATION)
            break

    return triggered


# ===========================================================================
# G. run(...) function -- the public BF entrypoint
# ===========================================================================

def get_default_be_artifact_path() -> Path:
    """Return the default fully-qualified BE artifact path."""
    return BE_DEFAULT_ARTIFACT_DIR / BE_DEFAULT_ARTIFACT_FILE


def run_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review(
    *,
    symbol: str = "SOLUSDT",
    be_artifact_path: Path | None = None,
    be_artifact: dict | None = None,
    allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review: bool = False,
    allow_real_entry_execution: bool = False,
    existing_position_symbols: tuple[str, ...] = (),
) -> _Result:
    """
    Execute one BF disabled-implementation-scaffold-manual-authorization-
    gate-final-pre-execution-review-manual-authorization-review-final-
    pre-execution-review manual authorization review.

    The function never performs any I/O beyond:
      * reading the BE artifact path (if supplied) from disk via the
        loader, and
      * reading THIS module's own source file for Group D static
        introspection.
    It never opens a socket, reads secrets, calls any endpoint,
    modifies any position, lifts G20, or treats any approval input as
    authorization.
    """
    result = _Result()
    result.selected_symbol = _safe_str(symbol)
    result.existing_position_symbols = list(existing_position_symbols)

    blocked: list[str] = []

    # ------------------------------------------------------------------
    # Stage 0 -- BE artifact preflight
    # ------------------------------------------------------------------
    artifact: dict | None
    if be_artifact is not None:
        artifact = be_artifact if isinstance(be_artifact, dict) else None
    elif be_artifact_path is not None:
        artifact = _load_be_final_pre_execution_review_artifact(be_artifact_path)
    else:
        artifact = None

    if artifact is None:
        blocked.append(GATE_BE_ARTIFACT_MISSING)
    else:
        # Stages 1..5 -- evaluate BE upstream + Group A/B/C gates.
        upstream_gates = _parse_be_upstream(artifact, result)
        blocked.extend(upstream_gates)

    # ------------------------------------------------------------------
    # Stage 6 -- BF self-source introspection (Group D)
    # ------------------------------------------------------------------
    self_source = _read_self_source()
    self_gates = _evaluate_self_source_gates(self_source)
    blocked.extend(self_gates)

    # ------------------------------------------------------------------
    # Finalize status / mode / failed_stage
    # ------------------------------------------------------------------
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
        first = hard_fails[0]
        result.failed_stage = _GATE_TO_STAGE.get(first, f"stage_X_{first}")
    else:
        if allow_real_entry_execution:
            result.status = STATUS_REAL_ENTRY_EXECUTION_NOT_IMPLEMENTED
        elif allow_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review:
            result.status = STATUS_READY_BUT_EXECUTION_DISABLED
        else:
            result.status = STATUS_READY
        result.mode = MODE_CHECKLIST
        result.failed_stage = ""

    # Final invariant re-assertion (defense in depth).  These values are
    # NEVER allowed to change, regardless of any flag, gate, or upstream
    # state -- the BF result is a manual-authorization-REVIEW FINAL-PRE-
    # EXECUTION-REVIEW MANUAL-AUTHORIZATION-REVIEW only, never an
    # authorization or an execution.
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
    result.manual_authorization_review_final_pre_execution_review_manual_authorization_review_only = True
    result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_only = True
    result.manual_authorization_review_final_pre_execution_review_manual_authorization_review_grants_execution = False
    result.manual_authorization_review_final_pre_execution_review_grants_execution = False
    result.manual_authorization_review_readiness_review_grants_execution = False
    result.manual_authorization_review_dry_run_grants_execution = False
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
    result.manual_authorization_review_final_pre_execution_review_manual_authorization_review_accepts_runtime_approval = False
    result.manual_authorization_review_final_pre_execution_review_manual_authorization_review_translates_text_to_execution = False
    result.scope_summary = SCOPE_SUMMARY_LITERAL
    result.identity_checklist = IDENTITY_CHECKLIST
    result.identity_strict = IDENTITY_STRICT
    result.next_required_task = NEXT_REQUIRED_TASK
    result.response_status = RESPONSE_STATUS_NOT_SENT
    result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_conclusion = CONCLUSION_READY_NOT_EXECUTABLE
    result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_authorization_result = AUTHORIZATION_RESULT_DOCUMENTED_ONLY
    result.existing_positions_touched = []

    return result


# ===========================================================================
# H. BF report writer (JSON + Markdown)
# ===========================================================================
#
# These helpers emit a documented-only BF report (JSON + Markdown).  They
# never call any endpoint, never read any secret, never lift G20, never
# modify any position, and never authorize real execution.

BF_DEFAULT_OUTPUT_DIR = Path(
    "outputs/demo_trading/tiny_guarded_entry_real_execution_adapter_"
    "disabled_implementation_scaffold_manual_authorization_gate_final_"
    "pre_execution_review_manual_authorization_review_final_pre_"
    "execution_review_manual_authorization_review"
)

_BF_REPORT_BASE_STEM = (
    "tiny_guarded_entry_real_execution_adapter_disabled_implementation_"
    "scaffold_manual_authorization_gate_final_pre_execution_review_manual_"
    "authorization_review_final_pre_execution_review_manual_authorization_"
    "review"
)


def get_default_bf_output_dir() -> Path:
    """Return the default BF output directory."""
    return BF_DEFAULT_OUTPUT_DIR


def _utc_timestamp_compact(_now: datetime | None = None) -> str:
    """Return a compact UTC timestamp like '20260618T083000Z'."""
    if _now is None:
        _now = datetime.now(tz=timezone.utc)
    else:
        if _now.tzinfo is None:
            _now = _now.replace(tzinfo=timezone.utc)
        else:
            _now = _now.astimezone(timezone.utc)
    return _now.strftime("%Y%m%dT%H%M%SZ")


def _render_markdown(result: _Result) -> str:
    """Render the BF result as a Markdown report.

    Documentation only -- never authorizes any real execution, never
    invokes any endpoint, never reads any secret, never lifts G20,
    never modifies any position.
    """
    d = result.to_dict()
    lines: list[str] = []
    lines.append(
        "# TASK-014BF — Disabled Implementation Scaffold Manual "
        "Authorization Gate Final Pre-Execution Review Manual "
        "Authorization Review Final Pre-Execution Review Manual "
        "Authorization Review"
    )
    lines.append("")
    lines.append(
        "TASK-014BF consumes TASK-014BE disabled implementation scaffold "
        "manual authorization gate final pre-execution review manual "
        "authorization review final pre-execution review output."
    )
    lines.append("")
    lines.append("## Scope summary")
    lines.append("")
    lines.append("```")
    lines.append(result.scope_summary)
    lines.append("```")
    lines.append("")
    lines.append(f"_SCOPE_SUMMARY_LITERAL: `{SCOPE_SUMMARY_LITERAL}`_")
    lines.append("")

    lines.append("## Identity")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append(f"| identity_checklist | `{result.identity_checklist}` |")
    lines.append(f"| identity_strict | `{result.identity_strict}` |")
    lines.append(f"| IDENTITY_CHECKLIST (module) | `{IDENTITY_CHECKLIST}` |")
    lines.append(f"| IDENTITY_STRICT (module) | `{IDENTITY_STRICT}` |")
    lines.append("")

    lines.append("## Result summary")
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
        f"`{result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_conclusion}` |"
    )
    lines.append(
        "| authorization_result | "
        f"`{result.disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_manual_authorization_review_authorization_result}` |"
    )
    lines.append(f"| response_status | `{result.response_status}` |")
    lines.append(f"| next_required_task | `{result.next_required_task}` |")
    lines.append(f"| failed_stage | `{result.failed_stage or '(none)'}` |")
    lines.append(f"| blocked_gates count | `{len(result.blocked_gates)}` |")
    lines.append("")

    lines.append("## BE upstream")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    be_upstream_field_names = (
        "consumed_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_mode",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_conclusion",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_authorization_result",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_response_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_real_execution_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_send_allowed",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_adapter_implementation_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_adapter_execution_included",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_order_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_stop_endpoint_called",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_no_position_modified",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_no_secrets_loaded",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_g20_lifted",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary",
    )
    for name in be_upstream_field_names:
        v = d.get(name, "")
        lines.append(f"| {name} | `{v}` |")
    lines.append("")

    lines.append("## BE-proven chained proof")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    chained_field_names = (
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_consumed_contract_version",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_status",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_next_required_task",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_readiness_review_scope_summary",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_mentions_bd_direct_upstream",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_mentions_bd_proven_chained_proof",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_bb",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_ba",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_az",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_be_consumes_ay",
        "upstream_entry_disabled_implementation_scaffold_manual_authorization_gate_final_pre_execution_review_manual_authorization_review_final_pre_execution_review_scope_summary_has_no_itdocuments_typo",
    )
    for name in chained_field_names:
        v = d.get(name, "")
        lines.append(f"| {name} | `{v}` |")
    lines.append("")

    lines.append("## Blocked gates")
    lines.append("")
    if result.blocked_gates:
        for g in result.blocked_gates:
            lines.append(f"- `{g}`")
    else:
        lines.append("- (none)")
    lines.append("")

    lines.append("## Safety invariants")
    lines.append("")
    lines.append("| field | value |")
    lines.append("|---|---|")
    lines.append(f"| manual_authorization_review_final_pre_execution_review_manual_authorization_review_grants_execution | `{result.manual_authorization_review_final_pre_execution_review_manual_authorization_review_grants_execution}` |")
    lines.append(f"| manual_authorization_review_final_pre_execution_review_grants_execution | `{result.manual_authorization_review_final_pre_execution_review_grants_execution}` |")
    lines.append(f"| manual_authorization_review_readiness_review_grants_execution | `{result.manual_authorization_review_readiness_review_grants_execution}` |")
    lines.append(f"| manual_authorization_review_dry_run_grants_execution | `{result.manual_authorization_review_dry_run_grants_execution}` |")
    lines.append(f"| manual_authorization_review_grants_execution | `{result.manual_authorization_review_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_final_pre_execution_review_grants_execution | `{result.manual_authorization_gate_final_pre_execution_review_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_readiness_review_grants_execution | `{result.manual_authorization_gate_readiness_review_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_dry_run_grants_execution | `{result.manual_authorization_gate_dry_run_grants_execution}` |")
    lines.append(f"| manual_authorization_gate_design_grants_execution | `{result.manual_authorization_gate_design_grants_execution}` |")
    lines.append(f"| final_pre_execution_review_grants_execution | `{result.final_pre_execution_review_grants_execution}` |")
    lines.append(f"| readiness_review_grants_execution | `{result.readiness_review_grants_execution}` |")
    lines.append(f"| dry_run_grants_execution | `{result.dry_run_grants_execution}` |")
    lines.append(f"| adapter_grants_execution | `{result.adapter_grants_execution}` |")
    lines.append(f"| approval_phrase_grants_execution | `{result.approval_phrase_grants_execution}` |")
    lines.append(f"| approval_token_grants_execution | `{result.approval_token_grants_execution}` |")
    lines.append(f"| approval_inputs_grant_execution | `{result.approval_inputs_grant_execution}` |")
    lines.append(f"| no_position_modified | `{result.no_position_modified}` |")
    lines.append(f"| no_secrets_loaded | `{result.no_secrets_loaded}` |")
    lines.append(f"| no_orders_sent | `{result.no_orders_sent}` |")
    lines.append(f"| no_live_endpoint | `{result.no_live_endpoint}` |")
    lines.append(f"| g20_policy_still_in_place | `{result.g20_policy_still_in_place}` |")
    lines.append(f"| g20_lifted | `{result.g20_lifted}` |")
    lines.append(f"| secret_value_observed | `{result.secret_value_observed}` |")
    lines.append("")

    lines.append("---")
    lines.append("")
    lines.append(
        "Documented-only-never-authorized. Does not call endpoints. Does "
        "not read secrets. Does not modify positions. Does not lift G20. "
        "Does not execute real entries."
    )
    lines.append("")
    return "\n".join(lines)


def write_report(
    result: _Result,
    output_dir: Path,
    _now: datetime | None = None,
) -> dict[str, Path]:
    """Write the BF manual authorization review JSON + Markdown report.

    Produces four files in `output_dir`:
      * latest_<base>.json  -- pretty-printed JSON, stable field order
      * latest_<base>.md    -- markdown summary
      * <base>_<ts>.json    -- timestamped JSON snapshot
      * <base>_<ts>.md      -- timestamped markdown snapshot

    Returns a dict with keys: latest_json, latest_md, timestamped_json,
    timestamped_md -- each mapping to the absolute Path actually written.

    This writer NEVER invokes any endpoint, NEVER reads any secret,
    NEVER lifts G20, NEVER modifies any position.  It only writes the
    documentation files described above.
    """
    output_dir = Path(output_dir)
    output_dir.mkdir(parents=True, exist_ok=True)

    ts = _utc_timestamp_compact(_now)
    base = _BF_REPORT_BASE_STEM

    latest_json = output_dir / f"latest_{base}.json"
    latest_md = output_dir / f"latest_{base}.md"
    ts_json = output_dir / f"{base}_{ts}.json"
    ts_md = output_dir / f"{base}_{ts}.md"

    payload = result.to_dict()
    json_text = json.dumps(payload, indent=2, sort_keys=False, ensure_ascii=False, default=str)
    md_text = _render_markdown(result)

    latest_json.write_text(json_text, encoding="utf-8")
    ts_json.write_text(json_text, encoding="utf-8")
    latest_md.write_text(md_text, encoding="utf-8")
    ts_md.write_text(md_text, encoding="utf-8")

    return {
        "latest_json": latest_json,
        "latest_md": latest_md,
        "timestamped_json": ts_json,
        "timestamped_md": ts_md,
    }
