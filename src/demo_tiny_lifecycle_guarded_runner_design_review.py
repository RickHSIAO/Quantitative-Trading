"""
src/demo_tiny_lifecycle_guarded_runner_design_review.py
TASK-014AD: Tiny Lifecycle Real Execution Guarded Runner Design Review.

Pure-computation / design-review only module.  Consolidates the 13
upstream artifacts (readonly / reconciliation / protection / contract /
noop_plan / lifecycle_mock / tiny_position_real_permission_gate /
tiny_entry_permission_gate / tiny_stop_attach_permission_gate /
tiny_cleanup_permission_gate / tiny_lifecycle_real_execution_summary /
tiny_lifecycle_runner_design / tiny_lifecycle_runner_dry_run) and emits
a *guarded real runner design review*.

This module DOES NOT implement, design, or invoke a real runner.  It
only answers: if some future task ever wants to graduate from the
TASK-014AC dry-run runner to a guarded real runner, what extra
defences, manual authorizations, environment isolation, per-step
human stops, post-readonly verifications, and abort conditions are
required?

This module DOES NOT execute anything against Bybit: no
/v5/order/create, no /v5/position/trading-stop, no order send,
no position modification, no close-only, no emergency close, no
leverage / transfer / withdraw, no token validation, no socket open,
no .env read, no dotenv, no signing.  It does not modify main.py,
src/risk.py, or BybitExecutor.

Stages:

  stage_0_artifact_preflight
      Validate 13 upstream artifacts + runtime proof envelope.

  stage_1_review_scope
      Assert guarded design review only.  No real runner / no guarded
      runner implementation / no endpoint invocation / no position
      modification / no secrets loaded.

  stage_2_readiness_matrix
      Combine W / X / Y / Z / AA / AB / AC readiness signals.  The
      readiness conclusion is DESIGN_REVIEW_READY_NOT_EXECUTABLE.  It
      is NEVER READY_TO_EXECUTE.

  stage_3_guarded_runner_minimum_requirements
      Future guarded runner must be split into three independent
      executable commands (entry-only / stop-only / cleanup-only).
      Single-command full-lifecycle execution is forbidden.  Each
      step requires fresh readonly, fresh artifact timestamps, a
      manual token, a second confirmation flag, explicit date, an
      isolated output directory, post-readonly verification, and
      a human stop afterwards.

  stage_4_manual_authorization_model
      Token-per-step design.  Each token includes UTC date and symbol
      and is paired with --i-understand-this-is-demo-real-execution,
      --max-notional-usdt 10, --expected-existing-position-count 5
      and --expected-existing-symbols.  Token format alone is NEVER
      authorization and this task does not validate any token.

  stage_5_environment_isolation_review
      Future guarded runner must be locked to demo endpoints with
      explicit allowlist / denylist.  No fallback to live endpoints,
      no daemon, no cron, no scheduler, no background worker, no
      Discord trigger, no Notion trigger.  Secrets are only read by
      the future real step and are never written into reports.  This
      task does not read secrets.

  stage_6_pre_post_readonly_contract
      Every future real step must be wrapped in pre/post readonly
      checks (account mode demo, endpoint family bybit_demo, existing
      5 positions unchanged, selected-symbol presence rules, qty/side/
      stopLoss assertions).  readonly unavailable -> FAIL_CLOSED.
      mismatch -> MANUAL_REVIEW_REQUIRED.

  stage_7_failure_and_abort_review
      Future guarded runner failure policy: any rejection, partial
      fill, readonly unavailable, symbol mismatch, live endpoint, or
      secret emission -> FAIL_CLOSED.  Existing position touched ->
      MANUAL_REVIEW_REQUIRED.  No auto retry, cleanup, emergency
      close, or next step.

  stage_8_final_guarded_design_verdict
      Resolve final status:
          TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY (default)
          TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY_BUT_EXECUTION_DISABLED
              (--allow-guarded-design-approval)
          REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED
              (--allow-real-runner-execution)
          FAIL_CLOSED                                       (hard-fail)
      Always emits real_execution_allowed=False,
      real_runner_implemented=False, guarded_runner_implemented=False,
      g20_lifted=False.

Modes:
  design_review_checklist               --- default
  guarded_design_approval_dry_run       --- with --allow-guarded-design-approval
  real_runner_execution_guard           --- with --allow-real-runner-execution
  fail_closed                           --- upstream / consistency validation failed

This module DOES NOT (enforced by source-scan tests):
  * import urllib / requests / httpx / socket / http.client
  * read os.environ / dotenv
  * call HMAC / signing
  * import main / src.risk / BybitExecutor / pybit
  * import src.demo_new_entry_sender
  * import src.demo_close_only_sender
  * import src.demo_emergency_close_sender
  * import src.demo_protected_new_entry_orchestrator
  * import src.demo_trading_stop_contract_probe
  * import src.demo_trading_stop_noop_probe_plan
  * import src.demo_tiny_position_lifecycle_mock
  * import src.demo_tiny_position_real_permission_gate
  * import src.demo_tiny_entry_permission_gate
  * import src.demo_tiny_stop_attach_permission_gate
  * import src.demo_tiny_cleanup_permission_gate
  * import src.demo_tiny_lifecycle_real_execution_summary
  * import src.demo_tiny_lifecycle_runner_design
  * import src.demo_tiny_lifecycle_runner_dry_run
  * invoke /v5/order/create or /v5/position/trading-stop
  * lift TASK-014L sender G20 (protected_entry_policy_missing)
  * touch ENAUSDT / TIAUSDT / AIXBTUSDT / POLYXUSDT / EDUUSDT
  * mutate leverage / transfer / withdraw / deposit
  * expose any real-execute / send-order / place-order / real-run flag
"""
from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime, timezone
from typing import Any


# ---------------------------------------------------------------------------
# Live state references (string-only; never invoked)
# ---------------------------------------------------------------------------

EXISTING_POSITION_SYMBOLS: tuple[str, ...] = (
    "ENAUSDT", "TIAUSDT", "AIXBTUSDT", "POLYXUSDT", "EDUUSDT",
)

DEFAULT_SELECTED_SYMBOL = "SOLUSDT"

ORDER_CREATE_PATH_REF = "/v5/order/create"            # NOT invoked
TRADING_STOP_PATH_REF = "/v5/position/trading-stop"   # NOT invoked
BASE_URL_DEMO_REF     = "https://api-demo.bybit.com"  # informational only
BASE_URL_LIVE_REF     = "https://api.bybit.com"       # denylist reference

DEMO_ENDPOINT_ALLOWLIST: tuple[str, ...] = (BASE_URL_DEMO_REF,)
LIVE_ENDPOINT_DENYLIST:  tuple[str, ...] = (BASE_URL_LIVE_REF,)


# ---------------------------------------------------------------------------
# Stage identifiers
# ---------------------------------------------------------------------------

STAGE_0_ARTIFACT_PREFLIGHT                 = "stage_0_artifact_preflight"
STAGE_1_REVIEW_SCOPE                       = "stage_1_review_scope"
STAGE_2_READINESS_MATRIX                   = "stage_2_readiness_matrix"
STAGE_3_GUARDED_RUNNER_MINIMUM_REQUIREMENTS = "stage_3_guarded_runner_minimum_requirements"
STAGE_4_MANUAL_AUTHORIZATION_MODEL         = "stage_4_manual_authorization_model"
STAGE_5_ENVIRONMENT_ISOLATION_REVIEW       = "stage_5_environment_isolation_review"
STAGE_6_PRE_POST_READONLY_CONTRACT         = "stage_6_pre_post_readonly_contract"
STAGE_7_FAILURE_AND_ABORT_REVIEW           = "stage_7_failure_and_abort_review"
STAGE_8_FINAL_GUARDED_DESIGN_VERDICT       = "stage_8_final_guarded_design_verdict"

ALL_STAGES: tuple[str, ...] = (
    STAGE_0_ARTIFACT_PREFLIGHT,
    STAGE_1_REVIEW_SCOPE,
    STAGE_2_READINESS_MATRIX,
    STAGE_3_GUARDED_RUNNER_MINIMUM_REQUIREMENTS,
    STAGE_4_MANUAL_AUTHORIZATION_MODEL,
    STAGE_5_ENVIRONMENT_ISOLATION_REVIEW,
    STAGE_6_PRE_POST_READONLY_CONTRACT,
    STAGE_7_FAILURE_AND_ABORT_REVIEW,
    STAGE_8_FINAL_GUARDED_DESIGN_VERDICT,
)


# ---------------------------------------------------------------------------
# Status / mode constants
# ---------------------------------------------------------------------------

STATUS_DESIGN_REVIEW_READY               = "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY"
STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED = (
    "TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY_BUT_EXECUTION_DISABLED"
)
STATUS_REAL_RUNNER_NOT_IMPL              = "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED"
STATUS_FAIL_CLOSED                       = "FAIL_CLOSED"

MODE_DESIGN_REVIEW_CHECKLIST             = "design_review_checklist"
MODE_GUARDED_DESIGN_APPROVAL_DRY_RUN     = "guarded_design_approval_dry_run"
MODE_REAL_RUNNER_EXECUTION_GUARD         = "real_runner_execution_guard"
MODE_FAIL_CLOSED                         = "fail_closed"

READINESS_CONCLUSION_NOT_EXECUTABLE      = "DESIGN_REVIEW_READY_NOT_EXECUTABLE"


# ---------------------------------------------------------------------------
# Acceptable upstream-status whitelists
# ---------------------------------------------------------------------------

ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY",
    "TINY_LIFECYCLE_PERMISSION_SUMMARY_READY_BUT_EXECUTION_DISABLED",
    "REAL_LIFECYCLE_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_RUNNER_DESIGN_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_RUNNER_DESIGN_READY",
    "TINY_LIFECYCLE_RUNNER_DESIGN_READY_BUT_EXECUTION_DISABLED",
    "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED",
})

ACCEPTABLE_RUNNER_DRY_RUN_STATUSES: frozenset[str] = frozenset({
    "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY",
    "TINY_LIFECYCLE_RUNNER_DRY_RUN_READY_BUT_EXECUTION_DISABLED",
    "REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED",
})


# ---------------------------------------------------------------------------
# Approval token patterns (documentation only --- never validated here)
# ---------------------------------------------------------------------------

ENTRY_TOKEN_PATTERN       = "CONFIRM_DEMO_TINY_ENTRY_YYYYMMDD_SYMBOL"
STOP_ATTACH_TOKEN_PATTERN = "CONFIRM_DEMO_TINY_STOP_ATTACH_YYYYMMDD_SYMBOL"
CLEANUP_TOKEN_PATTERN     = "CONFIRM_DEMO_TINY_CLEANUP_YYYYMMDD_SYMBOL"

REQUIRED_CONFIRMATION_FLAGS: tuple[str, ...] = (
    "--i-understand-this-is-demo-real-execution",
    "--max-notional-usdt 10",
    "--expected-existing-position-count 5",
    "--expected-existing-symbols AIXBTUSDT,ENAUSDT,TIAUSDT,POLYXUSDT,EDUUSDT",
)


# ---------------------------------------------------------------------------
# Expected upstream invariants
# ---------------------------------------------------------------------------

EXPECTED_ENDPOINT_FAMILY         = "bybit_demo"
EXPECTED_ACCOUNT_MODE            = "demo"
EXPECTED_PROOF_STRENGTH          = "STRONG"
EXPECTED_POSITION_DETAILS_SOURCE = "real_readonly"
EXPECTED_LIFECYCLE_STATUS        = "MOCK_TINY_LIFECYCLE_SUCCESS"
EXPECTED_INSTRUMENT_CATEGORY     = "linear"


# ---------------------------------------------------------------------------
# Future guarded runner command catalogue (documentation only)
# ---------------------------------------------------------------------------

FUTURE_GUARDED_COMMANDS: tuple[str, ...] = (
    "guarded_entry_only",
    "guarded_stop_attach_only",
    "guarded_cleanup_only",
)

FORBIDDEN_SINGLE_LIFECYCLE_COMMAND = "guarded_full_lifecycle"

FORBIDDEN_LOG_FIELDS: tuple[str, ...] = (
    "api_key_value", "api_secret_value", "signature_value",
    "auth_header_value", "sign_header_value", "bearer_token_value",
)


# ---------------------------------------------------------------------------
# Gate constants (97 total)
# General (23) + Review scope (8) + Readiness (8) + Guarded requirements (13)
# + Manual auth (11) + Environment isolation (11) + Readonly contract (7)
# + Failure policy (11) + Execution guard (5) = 97
# ---------------------------------------------------------------------------

# General gates (23)
GATE_READONLY_SMOKE_MISSING                     = "readonly_smoke_missing"
GATE_RECONCILIATION_MISSING                     = "reconciliation_missing"
GATE_PROTECTION_MISSING                         = "protection_missing"
GATE_CONTRACT_MISSING                           = "contract_missing"
GATE_NOOP_PLAN_MISSING                          = "noop_plan_missing"
GATE_LIFECYCLE_MOCK_MISSING                     = "lifecycle_mock_missing"
GATE_REAL_PERMISSION_GATE_MISSING               = "real_permission_gate_missing"
GATE_TINY_ENTRY_PERMISSION_GATE_MISSING         = "tiny_entry_permission_gate_missing"
GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING   = "tiny_stop_attach_permission_gate_missing"
GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING       = "tiny_cleanup_permission_gate_missing"
GATE_LIFECYCLE_SUMMARY_MISSING                  = "lifecycle_summary_missing"
GATE_RUNNER_DESIGN_MISSING                      = "runner_design_missing"
GATE_RUNNER_DRY_RUN_MISSING                     = "runner_dry_run_missing"
GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO             = "endpoint_family_not_bybit_demo"
GATE_ACCOUNT_MODE_NOT_DEMO                      = "account_mode_not_demo"
GATE_PROOF_STRENGTH_NOT_STRONG                  = "proof_strength_not_strong"
GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY  = "position_details_source_not_real_readonly"
GATE_SELECTED_SYMBOL_COLLIDES_EXISTING          = "selected_symbol_collides_with_existing_position"
GATE_SELECTED_SYMBOL_MISSING                    = "selected_symbol_missing"
GATE_RUNNER_DRY_RUN_STATUS_UNACCEPTABLE         = "runner_dry_run_status_unacceptable"
GATE_G20_POLICY_STILL_IN_PLACE                  = "g20_sender_policy_still_in_place"
GATE_NO_LIVE_ENDPOINT                           = "no_live_endpoint_in_this_task"
GATE_NO_SECRETS_EMITTED                         = "no_secret_values_emitted_in_this_task"

# Review scope gates (8)
GATE_GUARDED_DESIGN_REVIEW_ONLY                 = "guarded_design_review_only"
GATE_REAL_RUNNER_NOT_IMPLEMENTED                = "real_runner_not_implemented_in_this_task"
GATE_GUARDED_RUNNER_NOT_IMPLEMENTED             = "guarded_runner_not_implemented_in_this_task"
GATE_REAL_EXECUTION_NOT_ALLOWED                 = "real_execution_not_allowed_in_this_task"
GATE_NO_ENDPOINT_INVOKED                        = "no_endpoint_invoked_in_this_task"
GATE_NO_POSITION_MODIFIED_SCOPE                 = "no_position_modified_scope"
GATE_NO_SECRETS_LOADED                          = "no_secrets_loaded_in_this_task"
GATE_NO_G20_LIFT                                = "no_g20_policy_lift_in_this_task"

# Readiness matrix gates (8)
GATE_W_ACCEPTABLE                               = "w_real_permission_gate_acceptable"
GATE_X_ACCEPTABLE                               = "x_tiny_entry_permission_gate_acceptable"
GATE_Y_ACCEPTABLE                               = "y_tiny_stop_attach_permission_gate_acceptable"
GATE_Z_ACCEPTABLE                               = "z_tiny_cleanup_permission_gate_acceptable"
GATE_AA_ACCEPTABLE                              = "aa_tiny_lifecycle_summary_acceptable"
GATE_AB_ACCEPTABLE                              = "ab_runner_design_acceptable"
GATE_AC_ACCEPTABLE                              = "ac_runner_dry_run_acceptable"
GATE_READINESS_NOT_EXECUTABLE                   = "readiness_conclusion_not_executable"

# Guarded runner requirement gates (13)
GATE_ENTRY_ONLY_COMMAND_REQUIRED                = "entry_only_command_required"
GATE_STOP_ONLY_COMMAND_REQUIRED                 = "stop_only_command_required"
GATE_CLEANUP_ONLY_COMMAND_REQUIRED              = "cleanup_only_command_required"
GATE_NO_FULL_LIFECYCLE_SINGLE_COMMAND           = "no_full_lifecycle_single_command"
GATE_FRESH_READONLY_PRE_CHECK_REQUIRED          = "fresh_readonly_pre_check_required"
GATE_POST_READONLY_REQUIRED                     = "post_readonly_required"
GATE_ISOLATED_OUTPUT_DIR_REQUIRED               = "isolated_output_dir_required"
GATE_HUMAN_STOP_BETWEEN_STEPS_REQUIRED          = "human_stop_between_steps_required"
GATE_NO_AUTO_NEXT_STEP                          = "no_auto_next_step"
GATE_NO_AUTO_RETRY                              = "no_auto_retry"
GATE_NO_AUTO_CLEANUP                            = "no_auto_cleanup"
GATE_NO_AUTO_EMERGENCY_CLOSE                    = "no_auto_emergency_close"
GATE_NO_BACKGROUND_LOOP                         = "no_background_loop"

# Manual authorization model gates (11)
GATE_ENTRY_TOKEN_PATTERN_PRESENT                = "entry_token_pattern_present"
GATE_STOP_TOKEN_PATTERN_PRESENT                 = "stop_token_pattern_present"
GATE_CLEANUP_TOKEN_PATTERN_PRESENT              = "cleanup_token_pattern_present"
GATE_TOKEN_PER_STEP                             = "token_per_step"
GATE_TOKEN_INCLUDES_DATE_POLICY                 = "token_includes_date_policy"
GATE_TOKEN_INCLUDES_SYMBOL                      = "token_includes_symbol"
GATE_SECOND_CONFIRMATION_REQUIRED               = "second_confirmation_required"
GATE_MAX_NOTIONAL_CAP_REQUIRED                  = "max_notional_cap_required"
GATE_EXPECTED_EXISTING_SYMBOLS_REQUIRED         = "expected_existing_symbols_required"
GATE_TOKEN_FORMAT_NOT_AUTHORIZATION             = "token_format_not_authorization"
GATE_TOKENS_NOT_VALIDATED                       = "tokens_not_validated_in_this_task"

# Environment isolation gates (11)
GATE_DEMO_ENDPOINT_ALLOWLIST                    = "demo_endpoint_allowlist"
GATE_LIVE_ENDPOINT_DENYLIST                     = "live_endpoint_denylist"
GATE_NO_FALLBACK_ENDPOINT                       = "no_fallback_endpoint"
GATE_ONE_COMMAND_ONE_STEP                       = "one_command_one_step"
GATE_NO_DAEMON                                  = "no_daemon"
GATE_NO_CRON                                    = "no_cron"
GATE_NO_SCHEDULER                               = "no_scheduler"
GATE_NO_BACKGROUND_WORKER                       = "no_background_worker"
GATE_NO_DISCORD_TRIGGER                         = "no_discord_trigger"
GATE_NO_NOTION_TRIGGER                          = "no_notion_trigger"
GATE_SECRETS_NOT_READ                           = "secrets_not_read_in_this_task"

# Pre/post readonly contract gates (7)
GATE_PRE_CHECK_REQUIRED                         = "pre_check_required"
GATE_POST_ENTRY_REQUIRED                        = "post_entry_required"
GATE_POST_STOP_REQUIRED                         = "post_stop_required"
GATE_POST_CLEANUP_REQUIRED                      = "post_cleanup_required"
GATE_READONLY_UNAVAILABLE_FAIL_CLOSED           = "readonly_unavailable_fail_closed"
GATE_MISMATCH_MANUAL_REVIEW                     = "mismatch_manual_review"
GATE_EXISTING_FIVE_POSITIONS_UNCHANGED          = "existing_five_positions_unchanged_requirement"

# Failure and abort policy gates (11)
GATE_REQUEST_REJECTED_FAIL_CLOSED               = "request_rejected_fail_closed"
GATE_PARTIAL_FILL_FAIL_CLOSED                   = "partial_fill_fail_closed"
GATE_READONLY_UNAVAIL_FAIL_CLOSED_FAILURE       = "failure_readonly_unavailable_fail_closed"
GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED       = "selected_symbol_mismatch_fail_closed"
GATE_EXISTING_POSITION_TOUCHED_MANUAL_REVIEW    = "existing_position_touched_manual_review"
GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED         = "live_endpoint_detected_fail_closed"
GATE_SECRET_EMISSION_FAIL_CLOSED                = "secret_emission_fail_closed"
GATE_NO_AUTOMATIC_RETRY                         = "no_automatic_retry"
GATE_NO_AUTOMATIC_CLEANUP                       = "no_automatic_cleanup"
GATE_NO_AUTOMATIC_EMERGENCY_CLOSE               = "no_automatic_emergency_close"
GATE_NO_AUTOMATIC_NEXT_STEP                     = "no_automatic_next_step"

# Execution guard gates (5)
GATE_REAL_RUNNER_EXECUTION_NOT_IMPL             = "real_runner_execution_not_implemented"
GATE_NO_REAL_ORDER_ENDPOINT                     = "no_real_order_endpoint_in_this_task"
GATE_NO_REAL_STOP_ENDPOINT                      = "no_real_stop_endpoint_in_this_task"
GATE_NO_POSITION_MODIFIED                       = "no_position_modified_in_this_task"
GATE_G20_NOT_LIFTED                             = "g20_policy_not_lifted_by_this_task"


# Hard-fail-closed gates --- if ANY of these surface the result is
# downgraded to FAIL_CLOSED regardless of other state.
_HARD_FAIL_GATES: frozenset[str] = frozenset({
    GATE_READONLY_SMOKE_MISSING,
    GATE_RECONCILIATION_MISSING,
    GATE_PROTECTION_MISSING,
    GATE_CONTRACT_MISSING,
    GATE_NOOP_PLAN_MISSING,
    GATE_LIFECYCLE_MOCK_MISSING,
    GATE_REAL_PERMISSION_GATE_MISSING,
    GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
    GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
    GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
    GATE_LIFECYCLE_SUMMARY_MISSING,
    GATE_RUNNER_DESIGN_MISSING,
    GATE_RUNNER_DRY_RUN_MISSING,
    GATE_SELECTED_SYMBOL_MISSING,
    GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
    GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
    GATE_ACCOUNT_MODE_NOT_DEMO,
    GATE_PROOF_STRENGTH_NOT_STRONG,
    GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
    GATE_RUNNER_DRY_RUN_STATUS_UNACCEPTABLE,
})


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------

@dataclass
class TinyLifecycleGuardedRunnerDesignReviewResult:
    """Read-only outcome of one tiny-lifecycle guarded runner design review."""
    timestamp_utc:                str
    mode:                         str
    selected_symbol:              str
    existing_position_symbols:    list[str] = field(default_factory=list)

    stages:                       dict[str, dict[str, Any]] = field(default_factory=dict)
    stage_order:                  list[str] = field(default_factory=lambda: list(ALL_STAGES))

    review_scope:                 dict[str, Any] = field(default_factory=dict)
    readiness_matrix:             dict[str, Any] = field(default_factory=dict)
    guarded_runner_minimum_requirements: dict[str, Any] = field(default_factory=dict)
    manual_authorization_model:   dict[str, Any] = field(default_factory=dict)
    environment_isolation_review: dict[str, Any] = field(default_factory=dict)
    pre_post_readonly_contract:   dict[str, Any] = field(default_factory=dict)
    failure_and_abort_review:     dict[str, Any] = field(default_factory=dict)
    final_guarded_design_verdict: dict[str, Any] = field(default_factory=dict)

    entry_token_pattern:          str = ENTRY_TOKEN_PATTERN
    stop_attach_token_pattern:    str = STOP_ATTACH_TOKEN_PATTERN
    cleanup_token_pattern:        str = CLEANUP_TOKEN_PATTERN
    required_confirmation_flags:  list[str] = field(
        default_factory=lambda: list(REQUIRED_CONFIRMATION_FLAGS),
    )

    future_guarded_commands:      list[str] = field(
        default_factory=lambda: list(FUTURE_GUARDED_COMMANDS),
    )

    # Design-review gating flags.
    guarded_design_approval_allowed:  bool = False
    real_runner_execution_requested:  bool = False
    real_execution_allowed:           bool = False
    real_runner_implemented:          bool = False
    guarded_runner_implemented:       bool = False
    guarded_runner_design_review:     bool = True
    current_task_real_execution_allowed: bool = False
    readiness_conclusion:             str  = READINESS_CONCLUSION_NOT_EXECUTABLE

    # Safety invariants (string-only references / always documented).
    order_create_path_ref:        str  = ORDER_CREATE_PATH_REF
    trading_stop_path_ref:        str  = TRADING_STOP_PATH_REF
    base_url_ref:                 str  = BASE_URL_DEMO_REF

    order_endpoint_called:        bool = False
    stop_endpoint_called:         bool = False
    no_position_modified:         bool = True
    no_live_endpoint:             bool = True
    no_orders_sent:               bool = True
    no_batch_order:               bool = True
    no_close_only_path:           bool = True
    emergency_close_invoked:      bool = False
    leverage_mutated:             bool = False
    transfer_invoked:             bool = False
    no_secrets_loaded:            bool = True
    secret_value_observed:        bool = False
    g20_policy_still_in_place:    bool = True
    g20_lifted:                   bool = False

    existing_positions_touched:   list[str] = field(default_factory=list)
    upstream_lifecycle_summary_status: str = ""
    upstream_runner_design_status:     str = ""
    upstream_runner_dry_run_status:    str = ""

    blocked_gates:                list[str] = field(default_factory=list)
    failed_stage:                 str  = ""
    status:                       str  = STATUS_FAIL_CLOSED
    next_required_task:           str  = "TASK-014AE_guarded_entry_only_dry_run_adapter"

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp":                       self.timestamp_utc,
            "timestamp_utc":                   self.timestamp_utc,
            "mode":                            self.mode,
            "selected_symbol":                 self.selected_symbol,
            "existing_position_symbols":       list(self.existing_position_symbols),
            "stages":                          {k: dict(v) for k, v in self.stages.items()},
            "stage_order":                     list(self.stage_order),
            "review_scope":                    dict(self.review_scope),
            "readiness_matrix":                dict(self.readiness_matrix),
            "guarded_runner_minimum_requirements": dict(self.guarded_runner_minimum_requirements),
            "manual_authorization_model":      dict(self.manual_authorization_model),
            "environment_isolation_review":    dict(self.environment_isolation_review),
            "pre_post_readonly_contract":      dict(self.pre_post_readonly_contract),
            "failure_and_abort_review":        dict(self.failure_and_abort_review),
            "final_guarded_design_verdict":    dict(self.final_guarded_design_verdict),
            "entry_token_pattern":             self.entry_token_pattern,
            "stop_attach_token_pattern":       self.stop_attach_token_pattern,
            "cleanup_token_pattern":           self.cleanup_token_pattern,
            "required_confirmation_flags":     list(self.required_confirmation_flags),
            "future_guarded_commands":         list(self.future_guarded_commands),
            "guarded_design_approval_allowed": self.guarded_design_approval_allowed,
            "real_runner_execution_requested": self.real_runner_execution_requested,
            "real_execution_allowed":          self.real_execution_allowed,
            "real_runner_implemented":         self.real_runner_implemented,
            "guarded_runner_implemented":      self.guarded_runner_implemented,
            "guarded_runner_design_review":    self.guarded_runner_design_review,
            "current_task_real_execution_allowed": self.current_task_real_execution_allowed,
            "readiness_conclusion":            self.readiness_conclusion,
            "order_create_path_ref":           self.order_create_path_ref,
            "trading_stop_path_ref":           self.trading_stop_path_ref,
            "base_url_ref":                    self.base_url_ref,
            "order_endpoint_called":           self.order_endpoint_called,
            "stop_endpoint_called":            self.stop_endpoint_called,
            "no_position_modified":            self.no_position_modified,
            "no_live_endpoint":                self.no_live_endpoint,
            "no_orders_sent":                  self.no_orders_sent,
            "no_batch_order":                  self.no_batch_order,
            "no_close_only_path":              self.no_close_only_path,
            "emergency_close_invoked":         self.emergency_close_invoked,
            "leverage_mutated":                self.leverage_mutated,
            "transfer_invoked":                self.transfer_invoked,
            "no_secrets_loaded":               self.no_secrets_loaded,
            "secret_value_observed":           self.secret_value_observed,
            "g20_policy_still_in_place":       self.g20_policy_still_in_place,
            "g20_lifted":                      self.g20_lifted,
            "existing_positions_touched":      list(self.existing_positions_touched),
            "upstream_lifecycle_summary_status": self.upstream_lifecycle_summary_status,
            "upstream_runner_design_status":   self.upstream_runner_design_status,
            "upstream_runner_dry_run_status":  self.upstream_runner_dry_run_status,
            "blocked_gates":                   list(self.blocked_gates),
            "failed_stage":                    self.failed_stage,
            "status":                          self.status,
            "next_required_task":              self.next_required_task,
        }


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _safe_float(value: Any, default: float = 0.0) -> float:
    try:
        f = float(value)
    except (TypeError, ValueError):
        return default
    if f != f or f in (float("inf"), float("-inf")):
        return default
    return f


def _safe_str(value: Any) -> str:
    if value is None:
        return ""
    try:
        return str(value).strip()
    except Exception:
        return ""


def _positions_from_reconciliation(
    reconciliation: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    if not isinstance(reconciliation, dict):
        return [
            {"symbol": s, "side": "", "qty": 0.0, "entry": 0.0, "stop": 0.0}
            for s in EXISTING_POSITION_SYMBOLS
        ]
    rows = reconciliation.get("positions", None)
    if not isinstance(rows, list) or not rows:
        return [
            {"symbol": s, "side": "", "qty": 0.0, "entry": 0.0, "stop": 0.0}
            for s in EXISTING_POSITION_SYMBOLS
        ]
    out: list[dict[str, Any]] = []
    for row in rows:
        if isinstance(row, dict):
            sym = _safe_str(row.get("symbol", ""))
            if not sym:
                continue
            out.append({
                "symbol": sym,
                "side":   _safe_str(row.get("side", "")),
                "qty":    _safe_float(row.get("quantity",    row.get("qty",   0.0))),
                "entry":  _safe_float(row.get("entry_price", row.get("entry", 0.0))),
                "stop":   _safe_float(row.get("stop_price",  row.get("stop",  0.0))),
            })
    if not out:
        out = [
            {"symbol": s, "side": "", "qty": 0.0, "entry": 0.0, "stop": 0.0}
            for s in EXISTING_POSITION_SYMBOLS
        ]
    return out


def _symbols_only(snapshot: list[dict[str, Any]]) -> list[str]:
    return [_safe_str(row.get("symbol", "")) for row in snapshot]


# ---------------------------------------------------------------------------
# Guarded runner design review
# ---------------------------------------------------------------------------

class DemoTinyLifecycleGuardedRunnerDesignReview:
    """
    Pure-computation guarded runner design review.  Consolidates the 13
    upstream artifacts (10 baseline + 014AA lifecycle summary + 014AB
    runner design + 014AC runner dry-run) and emits a design review
    artifact answering: what extra defences, manual authorizations,
    environment isolations, per-step human stops, post-readonly
    verifications, and abort conditions are required before any future
    task could implement a guarded real runner.

    Holds no network client, reads no environment variables, opens no
    socket, performs no HMAC signing, and NEVER invokes the
    order-create or trading-stop endpoints.  Does not implement, design,
    or describe a real runner that could be executed.

    --allow-guarded-design-approval --> status promoted to
        TINY_LIFECYCLE_GUARDED_RUNNER_DESIGN_REVIEW_READY_BUT_EXECUTION_DISABLED.

    --allow-real-runner-execution --> status fixed to
        REAL_RUNNER_EXECUTION_NOT_IMPLEMENTED  (no socket opened).
    """

    def __init__(self) -> None:
        pass

    def run_checklist(
        self,
        readonly_smoke:                   dict[str, Any] | None,
        reconciliation:                   dict[str, Any] | None,
        protection:                       dict[str, Any] | None,
        contract:                         dict[str, Any] | None,
        noop_plan:                        dict[str, Any] | None,
        lifecycle_mock:                   dict[str, Any] | None,
        real_permission_gate:             dict[str, Any] | None,
        tiny_entry_permission_gate:       dict[str, Any] | None,
        tiny_stop_attach_permission_gate: dict[str, Any] | None,
        tiny_cleanup_permission_gate:     dict[str, Any] | None,
        lifecycle_summary:                dict[str, Any] | None,
        runner_design:                    dict[str, Any] | None,
        runner_dry_run:                   dict[str, Any] | None,
        symbol:                           str  = DEFAULT_SELECTED_SYMBOL,
        allow_guarded_design_approval:    bool = False,
        allow_real_runner_execution:      bool = False,
        _now:                             datetime | None = None,
    ) -> TinyLifecycleGuardedRunnerDesignReviewResult:
        ts_utc = (_now or datetime.now(timezone.utc)).strftime("%Y-%m-%dT%H:%M:%SZ")

        if allow_real_runner_execution:
            mode = MODE_REAL_RUNNER_EXECUTION_GUARD
        elif allow_guarded_design_approval:
            mode = MODE_GUARDED_DESIGN_APPROVAL_DRY_RUN
        else:
            mode = MODE_DESIGN_REVIEW_CHECKLIST

        blocked: list[str] = []
        stages:  dict[str, dict[str, Any]] = {}

        # ===============================================================
        # stage_0_artifact_preflight
        # ===============================================================
        sym = _safe_str(symbol)
        existing_snapshot = _positions_from_reconciliation(reconciliation)
        existing_symbols  = _symbols_only(existing_snapshot)

        readonly_present     = isinstance(readonly_smoke, dict) and bool(readonly_smoke)
        recon_present        = isinstance(reconciliation, dict) and bool(reconciliation)
        protection_present   = isinstance(protection, dict) and bool(protection)
        contract_present     = isinstance(contract, dict) and bool(contract)
        noop_present         = isinstance(noop_plan, dict) and bool(noop_plan)
        lifecycle_present    = isinstance(lifecycle_mock, dict) and bool(lifecycle_mock)
        real_perm_present    = isinstance(real_permission_gate, dict) and bool(real_permission_gate)
        entry_perm_present   = (
            isinstance(tiny_entry_permission_gate, dict)
            and bool(tiny_entry_permission_gate)
        )
        stop_perm_present    = (
            isinstance(tiny_stop_attach_permission_gate, dict)
            and bool(tiny_stop_attach_permission_gate)
        )
        cleanup_perm_present = (
            isinstance(tiny_cleanup_permission_gate, dict)
            and bool(tiny_cleanup_permission_gate)
        )
        summary_present      = isinstance(lifecycle_summary, dict) and bool(lifecycle_summary)
        runner_design_present = isinstance(runner_design, dict) and bool(runner_design)
        runner_dry_run_present = isinstance(runner_dry_run, dict) and bool(runner_dry_run)

        endpoint_family = _safe_str((readonly_smoke or {}).get("endpoint_family", ""))
        account_mode    = _safe_str((readonly_smoke or {}).get("account_mode", ""))
        proof_strength  = _safe_str((readonly_smoke or {}).get("proof_strength", ""))
        position_details_source = _safe_str(
            (reconciliation or {}).get(
                "position_details_source",
                (reconciliation or {}).get("mode", ""),
            )
        )
        lifecycle_status      = _safe_str((lifecycle_mock or {}).get("status", ""))
        summary_status        = _safe_str((lifecycle_summary or {}).get("status", ""))
        runner_design_status  = _safe_str((runner_design or {}).get("status", ""))
        runner_dry_run_status = _safe_str((runner_dry_run or {}).get("status", ""))

        if not readonly_present:
            blocked.append(GATE_READONLY_SMOKE_MISSING)
        if not recon_present:
            blocked.append(GATE_RECONCILIATION_MISSING)
        if not protection_present:
            blocked.append(GATE_PROTECTION_MISSING)
        if not contract_present:
            blocked.append(GATE_CONTRACT_MISSING)
        if not noop_present:
            blocked.append(GATE_NOOP_PLAN_MISSING)
        if not lifecycle_present:
            blocked.append(GATE_LIFECYCLE_MOCK_MISSING)
        if not real_perm_present:
            blocked.append(GATE_REAL_PERMISSION_GATE_MISSING)
        if not entry_perm_present:
            blocked.append(GATE_TINY_ENTRY_PERMISSION_GATE_MISSING)
        if not stop_perm_present:
            blocked.append(GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING)
        if not cleanup_perm_present:
            blocked.append(GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING)
        if not summary_present:
            blocked.append(GATE_LIFECYCLE_SUMMARY_MISSING)
        if not runner_design_present:
            blocked.append(GATE_RUNNER_DESIGN_MISSING)
        if not runner_dry_run_present:
            blocked.append(GATE_RUNNER_DRY_RUN_MISSING)

        if readonly_present and endpoint_family and endpoint_family != EXPECTED_ENDPOINT_FAMILY:
            blocked.append(GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO)
        if readonly_present and account_mode and account_mode != EXPECTED_ACCOUNT_MODE:
            blocked.append(GATE_ACCOUNT_MODE_NOT_DEMO)
        if readonly_present and proof_strength and proof_strength != EXPECTED_PROOF_STRENGTH:
            blocked.append(GATE_PROOF_STRENGTH_NOT_STRONG)
        if recon_present and position_details_source and position_details_source != EXPECTED_POSITION_DETAILS_SOURCE:
            blocked.append(GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY)

        if runner_dry_run_present and runner_dry_run_status and (
            runner_dry_run_status not in ACCEPTABLE_RUNNER_DRY_RUN_STATUSES
        ):
            blocked.append(GATE_RUNNER_DRY_RUN_STATUS_UNACCEPTABLE)

        if not sym:
            blocked.append(GATE_SELECTED_SYMBOL_MISSING)
        elif sym in existing_symbols:
            blocked.append(GATE_SELECTED_SYMBOL_COLLIDES_EXISTING)

        stages[STAGE_0_ARTIFACT_PREFLIGHT] = {
            "stage":   STAGE_0_ARTIFACT_PREFLIGHT,
            "summary": "Validate 13 upstream artifacts + runtime proof envelope.",
            "readonly_smoke_present":                   readonly_present,
            "reconciliation_present":                   recon_present,
            "protection_present":                       protection_present,
            "contract_present":                         contract_present,
            "noop_plan_present":                        noop_present,
            "lifecycle_mock_present":                   lifecycle_present,
            "real_permission_gate_present":             real_perm_present,
            "tiny_entry_permission_gate_present":       entry_perm_present,
            "tiny_stop_attach_permission_gate_present": stop_perm_present,
            "tiny_cleanup_permission_gate_present":     cleanup_perm_present,
            "lifecycle_summary_present":                summary_present,
            "runner_design_present":                    runner_design_present,
            "runner_dry_run_present":                   runner_dry_run_present,
            "endpoint_family_observed":                 endpoint_family,
            "endpoint_family_expected":                 EXPECTED_ENDPOINT_FAMILY,
            "account_mode_observed":                    account_mode,
            "account_mode_expected":                    EXPECTED_ACCOUNT_MODE,
            "proof_strength_observed":                  proof_strength,
            "proof_strength_expected":                  EXPECTED_PROOF_STRENGTH,
            "position_details_source_observed":         position_details_source,
            "position_details_source_expected":         EXPECTED_POSITION_DETAILS_SOURCE,
            "lifecycle_status_observed":                lifecycle_status,
            "lifecycle_status_expected":                EXPECTED_LIFECYCLE_STATUS,
            "lifecycle_summary_status_observed":        summary_status,
            "runner_design_status_observed":            runner_design_status,
            "runner_dry_run_status_observed":           runner_dry_run_status,
            "runner_dry_run_status_acceptable":         sorted(
                ACCEPTABLE_RUNNER_DRY_RUN_STATUSES
            ),
            "selected_symbol":                          sym,
            "current_task_real_execution_allowed":      False,
        }

        # ===============================================================
        # stage_1_review_scope
        # ===============================================================
        review_scope: dict[str, Any] = {
            "guarded_runner_design_review":         True,
            "real_runner_implemented":              False,
            "guarded_runner_implemented":           False,
            "real_execution_allowed":               False,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "no_endpoint_invoked_in_this_task":     True,
            "no_position_modified":                 True,
            "no_secrets_loaded":                    True,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "next_required_task":                   "TASK-014AE_guarded_entry_only_dry_run_adapter",
            "scope_summary": (
                "TASK-014AD only reviews the design of a future guarded "
                "real runner.  It does not implement a guarded runner, "
                "does not send any order, does not call any endpoint, "
                "does not load any secret, and does not touch any "
                "existing position."
            ),
        }
        stages[STAGE_1_REVIEW_SCOPE] = {
            "stage":   STAGE_1_REVIEW_SCOPE,
            "summary": "Assert guarded design review only scope.",
            "review_scope":                         review_scope,
        }
        blocked.append(GATE_GUARDED_DESIGN_REVIEW_ONLY)
        blocked.append(GATE_REAL_RUNNER_NOT_IMPLEMENTED)
        blocked.append(GATE_GUARDED_RUNNER_NOT_IMPLEMENTED)
        blocked.append(GATE_REAL_EXECUTION_NOT_ALLOWED)
        blocked.append(GATE_NO_ENDPOINT_INVOKED)
        blocked.append(GATE_NO_POSITION_MODIFIED_SCOPE)
        blocked.append(GATE_NO_SECRETS_LOADED)
        blocked.append(GATE_NO_G20_LIFT)

        # ===============================================================
        # stage_2_readiness_matrix
        # ===============================================================
        w_acceptable  = real_perm_present
        x_acceptable  = entry_perm_present
        y_acceptable  = stop_perm_present
        z_acceptable  = cleanup_perm_present
        aa_acceptable = summary_present and (
            (not summary_status)
            or summary_status in ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES
        )
        ab_acceptable = runner_design_present and (
            (not runner_design_status)
            or runner_design_status in ACCEPTABLE_RUNNER_DESIGN_STATUSES
        )
        ac_acceptable = runner_dry_run_present and (
            (not runner_dry_run_status)
            or runner_dry_run_status in ACCEPTABLE_RUNNER_DRY_RUN_STATUSES
        )

        readiness_matrix: dict[str, Any] = {
            "w_real_permission_gate_acceptable":           w_acceptable,
            "x_tiny_entry_permission_gate_acceptable":     x_acceptable,
            "y_tiny_stop_attach_permission_gate_acceptable": y_acceptable,
            "z_tiny_cleanup_permission_gate_acceptable":   z_acceptable,
            "aa_tiny_lifecycle_summary_acceptable":        aa_acceptable,
            "ab_runner_design_acceptable":                 ab_acceptable,
            "ac_runner_dry_run_acceptable":                ac_acceptable,
            "readiness_conclusion":                        READINESS_CONCLUSION_NOT_EXECUTABLE,
            "readiness_conclusion_not_executable":         True,
            "ready_to_execute":                            False,
        }
        stages[STAGE_2_READINESS_MATRIX] = {
            "stage":   STAGE_2_READINESS_MATRIX,
            "summary": "Combine W/X/Y/Z/AA/AB/AC readiness signals.",
            "readiness_matrix":                     readiness_matrix,
        }
        if w_acceptable:
            blocked.append(GATE_W_ACCEPTABLE)
        if x_acceptable:
            blocked.append(GATE_X_ACCEPTABLE)
        if y_acceptable:
            blocked.append(GATE_Y_ACCEPTABLE)
        if z_acceptable:
            blocked.append(GATE_Z_ACCEPTABLE)
        if aa_acceptable:
            blocked.append(GATE_AA_ACCEPTABLE)
        if ab_acceptable:
            blocked.append(GATE_AB_ACCEPTABLE)
        if ac_acceptable:
            blocked.append(GATE_AC_ACCEPTABLE)
        blocked.append(GATE_READINESS_NOT_EXECUTABLE)

        # ===============================================================
        # stage_3_guarded_runner_minimum_requirements
        # ===============================================================
        guarded_runner_minimum_requirements: dict[str, Any] = {
            "future_guarded_commands":              list(FUTURE_GUARDED_COMMANDS),
            "forbidden_single_lifecycle_command":   FORBIDDEN_SINGLE_LIFECYCLE_COMMAND,
            "entry_only_command_required":          True,
            "stop_only_command_required":           True,
            "cleanup_only_command_required":        True,
            "no_full_lifecycle_single_command":     True,
            "per_step_requirements": {
                "matching_symbol":                  True,
                "matching_qty":                     True,
                "matching_side":                    True,
                "fresh_readonly_pre_check":         True,
                "fresh_artifact_timestamp":         True,
                "manual_token":                     True,
                "second_confirmation_flag":         True,
                "explicit_current_date":            True,
                "isolated_output_directory":        True,
                "post_readonly_verification":       True,
                "human_stop_between_steps":         True,
            },
            "no_auto_next_step":                    True,
            "no_auto_retry":                        True,
            "no_auto_cleanup":                      True,
            "no_auto_emergency_close":              True,
            "no_background_loop":                   True,
        }
        stages[STAGE_3_GUARDED_RUNNER_MINIMUM_REQUIREMENTS] = {
            "stage":   STAGE_3_GUARDED_RUNNER_MINIMUM_REQUIREMENTS,
            "summary": "Define minimum requirements for any future guarded real runner.",
            "guarded_runner_minimum_requirements":  guarded_runner_minimum_requirements,
        }
        blocked.append(GATE_ENTRY_ONLY_COMMAND_REQUIRED)
        blocked.append(GATE_STOP_ONLY_COMMAND_REQUIRED)
        blocked.append(GATE_CLEANUP_ONLY_COMMAND_REQUIRED)
        blocked.append(GATE_NO_FULL_LIFECYCLE_SINGLE_COMMAND)
        blocked.append(GATE_FRESH_READONLY_PRE_CHECK_REQUIRED)
        blocked.append(GATE_POST_READONLY_REQUIRED)
        blocked.append(GATE_ISOLATED_OUTPUT_DIR_REQUIRED)
        blocked.append(GATE_HUMAN_STOP_BETWEEN_STEPS_REQUIRED)
        blocked.append(GATE_NO_AUTO_NEXT_STEP)
        blocked.append(GATE_NO_AUTO_RETRY)
        blocked.append(GATE_NO_AUTO_CLEANUP)
        blocked.append(GATE_NO_AUTO_EMERGENCY_CLOSE)
        blocked.append(GATE_NO_BACKGROUND_LOOP)

        # ===============================================================
        # stage_4_manual_authorization_model
        # ===============================================================
        manual_authorization_model: dict[str, Any] = {
            "entry_token_pattern":                  ENTRY_TOKEN_PATTERN,
            "stop_attach_token_pattern":            STOP_ATTACH_TOKEN_PATTERN,
            "cleanup_token_pattern":                CLEANUP_TOKEN_PATTERN,
            "token_per_step":                       True,
            "token_includes_date_policy":           True,
            "token_includes_symbol":                True,
            "token_format_not_authorization":       True,
            "tokens_not_validated_in_this_task":    True,
            "required_confirmation_flags":          list(REQUIRED_CONFIRMATION_FLAGS),
            "second_confirmation_required":         True,
            "max_notional_cap_required":            True,
            "expected_existing_position_count":     5,
            "expected_existing_symbols":            list(EXISTING_POSITION_SYMBOLS),
            "expected_existing_symbols_required":   True,
        }
        stages[STAGE_4_MANUAL_AUTHORIZATION_MODEL] = {
            "stage":   STAGE_4_MANUAL_AUTHORIZATION_MODEL,
            "summary": "Describe the manual token-per-step authorization model (not validated).",
            "manual_authorization_model":           manual_authorization_model,
        }
        blocked.append(GATE_ENTRY_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_STOP_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_CLEANUP_TOKEN_PATTERN_PRESENT)
        blocked.append(GATE_TOKEN_PER_STEP)
        blocked.append(GATE_TOKEN_INCLUDES_DATE_POLICY)
        blocked.append(GATE_TOKEN_INCLUDES_SYMBOL)
        blocked.append(GATE_SECOND_CONFIRMATION_REQUIRED)
        blocked.append(GATE_MAX_NOTIONAL_CAP_REQUIRED)
        blocked.append(GATE_EXPECTED_EXISTING_SYMBOLS_REQUIRED)
        blocked.append(GATE_TOKEN_FORMAT_NOT_AUTHORIZATION)
        blocked.append(GATE_TOKENS_NOT_VALIDATED)

        # ===============================================================
        # stage_5_environment_isolation_review
        # ===============================================================
        environment_isolation_review: dict[str, Any] = {
            "demo_endpoint_allowlist":              list(DEMO_ENDPOINT_ALLOWLIST),
            "live_endpoint_denylist":               list(LIVE_ENDPOINT_DENYLIST),
            "no_fallback_endpoint":                 True,
            "one_command_one_step":                 True,
            "no_daemon":                            True,
            "no_cron":                              True,
            "no_scheduler":                         True,
            "no_background_worker":                 True,
            "no_discord_trigger":                   True,
            "no_notion_trigger":                    True,
            "secrets_only_in_future_real_step":     True,
            "secrets_not_in_report":                True,
            "secrets_not_read_in_this_task":        True,
            "forbidden_log_fields":                 list(FORBIDDEN_LOG_FIELDS),
        }
        stages[STAGE_5_ENVIRONMENT_ISOLATION_REVIEW] = {
            "stage":   STAGE_5_ENVIRONMENT_ISOLATION_REVIEW,
            "summary": "Environment isolation review for any future guarded real runner.",
            "environment_isolation_review":         environment_isolation_review,
        }
        blocked.append(GATE_DEMO_ENDPOINT_ALLOWLIST)
        blocked.append(GATE_LIVE_ENDPOINT_DENYLIST)
        blocked.append(GATE_NO_FALLBACK_ENDPOINT)
        blocked.append(GATE_ONE_COMMAND_ONE_STEP)
        blocked.append(GATE_NO_DAEMON)
        blocked.append(GATE_NO_CRON)
        blocked.append(GATE_NO_SCHEDULER)
        blocked.append(GATE_NO_BACKGROUND_WORKER)
        blocked.append(GATE_NO_DISCORD_TRIGGER)
        blocked.append(GATE_NO_NOTION_TRIGGER)
        blocked.append(GATE_SECRETS_NOT_READ)

        # ===============================================================
        # stage_6_pre_post_readonly_contract
        # ===============================================================
        pre_post_readonly_contract: dict[str, Any] = {
            "pre_check": {
                "account_mode_demo":                True,
                "endpoint_family_bybit_demo":       True,
                "existing_five_positions_unchanged": True,
                "selected_symbol_absent_before_entry":   True,
                "selected_symbol_present_before_stop":   True,
                "selected_symbol_present_before_cleanup": True,
            },
            "post_entry": {
                "selected_symbol_position_appears": True,
                "qty_equals_expected_tiny_qty":     True,
                "side_equals_long":                 True,
            },
            "post_stop": {
                "selected_symbol_stop_loss_equals_expected": True,
            },
            "post_cleanup": {
                "selected_symbol_absent_or_zero":   True,
                "existing_five_positions_unchanged": True,
            },
            "readonly_unavailable_fail_closed":     True,
            "mismatch_manual_review":               True,
            "existing_five_positions_unchanged_requirement": True,
        }
        stages[STAGE_6_PRE_POST_READONLY_CONTRACT] = {
            "stage":   STAGE_6_PRE_POST_READONLY_CONTRACT,
            "summary": "Pre/post readonly contract for any future guarded real runner.",
            "pre_post_readonly_contract":           pre_post_readonly_contract,
        }
        blocked.append(GATE_PRE_CHECK_REQUIRED)
        blocked.append(GATE_POST_ENTRY_REQUIRED)
        blocked.append(GATE_POST_STOP_REQUIRED)
        blocked.append(GATE_POST_CLEANUP_REQUIRED)
        blocked.append(GATE_READONLY_UNAVAILABLE_FAIL_CLOSED)
        blocked.append(GATE_MISMATCH_MANUAL_REVIEW)
        blocked.append(GATE_EXISTING_FIVE_POSITIONS_UNCHANGED)

        # ===============================================================
        # stage_7_failure_and_abort_review
        # ===============================================================
        failure_and_abort_review: dict[str, Any] = {
            "request_rejected":               "FAIL_CLOSED",
            "partial_fill":                   "FAIL_CLOSED",
            "readonly_unavailable":           "FAIL_CLOSED",
            "selected_symbol_mismatch":       "FAIL_CLOSED",
            "existing_position_touched":      "MANUAL_REVIEW_REQUIRED",
            "live_endpoint_detected":         "FAIL_CLOSED",
            "secret_emission_detected":       "FAIL_CLOSED",
            "no_automatic_retry":             True,
            "no_automatic_cleanup":           True,
            "no_automatic_emergency_close":   True,
            "no_automatic_next_step":         True,
            "manual_intervention_only":       True,
        }
        stages[STAGE_7_FAILURE_AND_ABORT_REVIEW] = {
            "stage":   STAGE_7_FAILURE_AND_ABORT_REVIEW,
            "summary": "Failure and abort policy for any future guarded real runner.",
            "failure_and_abort_review":             failure_and_abort_review,
        }
        blocked.append(GATE_REQUEST_REJECTED_FAIL_CLOSED)
        blocked.append(GATE_PARTIAL_FILL_FAIL_CLOSED)
        blocked.append(GATE_READONLY_UNAVAIL_FAIL_CLOSED_FAILURE)
        blocked.append(GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED)
        blocked.append(GATE_EXISTING_POSITION_TOUCHED_MANUAL_REVIEW)
        blocked.append(GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED)
        blocked.append(GATE_SECRET_EMISSION_FAIL_CLOSED)
        blocked.append(GATE_NO_AUTOMATIC_RETRY)
        blocked.append(GATE_NO_AUTOMATIC_CLEANUP)
        blocked.append(GATE_NO_AUTOMATIC_EMERGENCY_CLOSE)
        blocked.append(GATE_NO_AUTOMATIC_NEXT_STEP)

        # ===============================================================
        # stage_8_final_guarded_design_verdict
        # ===============================================================
        blocked.append(GATE_REAL_RUNNER_EXECUTION_NOT_IMPL)
        blocked.append(GATE_NO_REAL_ORDER_ENDPOINT)
        blocked.append(GATE_NO_REAL_STOP_ENDPOINT)
        blocked.append(GATE_NO_POSITION_MODIFIED)
        blocked.append(GATE_G20_NOT_LIFTED)
        blocked.append(GATE_G20_POLICY_STILL_IN_PLACE)
        blocked.append(GATE_NO_LIVE_ENDPOINT)
        blocked.append(GATE_NO_SECRETS_EMITTED)

        unique = self._dedupe(blocked)
        hard_fail = any(g in unique for g in _HARD_FAIL_GATES)

        if hard_fail:
            failed_stage = self._first_failed_stage(unique)
            status_out = STATUS_FAIL_CLOSED
            mode_out   = MODE_FAIL_CLOSED
        elif allow_real_runner_execution:
            failed_stage = ""
            status_out = STATUS_REAL_RUNNER_NOT_IMPL
            mode_out   = MODE_REAL_RUNNER_EXECUTION_GUARD
        elif allow_guarded_design_approval:
            failed_stage = ""
            status_out = STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED
            mode_out   = MODE_GUARDED_DESIGN_APPROVAL_DRY_RUN
        else:
            failed_stage = ""
            status_out = STATUS_DESIGN_REVIEW_READY
            mode_out   = MODE_DESIGN_REVIEW_CHECKLIST

        final_guarded_design_verdict: dict[str, Any] = {
            "guarded_design_approval_allowed":      allow_guarded_design_approval,
            "real_runner_execution_requested":      bool(allow_real_runner_execution),
            "real_execution_allowed":               False,
            "real_runner_implemented":              False,
            "guarded_runner_implemented":           False,
            "guarded_runner_design_review":         True,
            "current_task_real_execution_allowed":  False,
            "readiness_conclusion":                 READINESS_CONCLUSION_NOT_EXECUTABLE,
            "g20_policy_still_in_place":            True,
            "g20_lifted":                           False,
            "no_real_order_endpoint":               True,
            "no_real_stop_endpoint":                True,
            "no_position_modified":                 True,
            "no_live_endpoint":                     True,
            "no_secrets_loaded":                    True,
            "no_secrets_emitted":                   True,
            "order_endpoint_called":                False,
            "stop_endpoint_called":                 False,
            "status":                               status_out,
            "mode":                                 mode_out,
            "next_required_task":                   "TASK-014AE_guarded_entry_only_dry_run_adapter",
        }
        stages[STAGE_8_FINAL_GUARDED_DESIGN_VERDICT] = {
            "stage":   STAGE_8_FINAL_GUARDED_DESIGN_VERDICT,
            "summary": "Final guarded design review verdict + permanent execution guard.",
            "final_guarded_design_verdict":         final_guarded_design_verdict,
        }

        return TinyLifecycleGuardedRunnerDesignReviewResult(
            timestamp_utc=ts_utc,
            mode=mode_out,
            selected_symbol=sym,
            existing_position_symbols=existing_symbols,
            stages=stages,
            review_scope=review_scope,
            readiness_matrix=readiness_matrix,
            guarded_runner_minimum_requirements=guarded_runner_minimum_requirements,
            manual_authorization_model=manual_authorization_model,
            environment_isolation_review=environment_isolation_review,
            pre_post_readonly_contract=pre_post_readonly_contract,
            failure_and_abort_review=failure_and_abort_review,
            final_guarded_design_verdict=final_guarded_design_verdict,
            guarded_design_approval_allowed=allow_guarded_design_approval,
            real_runner_execution_requested=bool(allow_real_runner_execution),
            real_execution_allowed=False,
            real_runner_implemented=False,
            guarded_runner_implemented=False,
            guarded_runner_design_review=True,
            current_task_real_execution_allowed=False,
            readiness_conclusion=READINESS_CONCLUSION_NOT_EXECUTABLE,
            order_endpoint_called=False,
            stop_endpoint_called=False,
            no_position_modified=True,
            no_live_endpoint=True,
            no_orders_sent=True,
            no_batch_order=True,
            no_close_only_path=True,
            emergency_close_invoked=False,
            leverage_mutated=False,
            transfer_invoked=False,
            no_secrets_loaded=True,
            secret_value_observed=False,
            g20_policy_still_in_place=True,
            g20_lifted=False,
            existing_positions_touched=[],
            upstream_lifecycle_summary_status=summary_status,
            upstream_runner_design_status=runner_design_status,
            upstream_runner_dry_run_status=runner_dry_run_status,
            blocked_gates=unique,
            failed_stage=failed_stage,
            status=status_out,
        )

    @staticmethod
    def _dedupe(items: list[str]) -> list[str]:
        seen: set[str] = set()
        out: list[str] = []
        for g in items:
            if g not in seen:
                out.append(g)
                seen.add(g)
        return out

    @staticmethod
    def _first_failed_stage(blocked: list[str]) -> str:
        stage_0_set = {
            GATE_READONLY_SMOKE_MISSING,
            GATE_RECONCILIATION_MISSING,
            GATE_PROTECTION_MISSING,
            GATE_CONTRACT_MISSING,
            GATE_NOOP_PLAN_MISSING,
            GATE_LIFECYCLE_MOCK_MISSING,
            GATE_REAL_PERMISSION_GATE_MISSING,
            GATE_TINY_ENTRY_PERMISSION_GATE_MISSING,
            GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING,
            GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING,
            GATE_LIFECYCLE_SUMMARY_MISSING,
            GATE_RUNNER_DESIGN_MISSING,
            GATE_RUNNER_DRY_RUN_MISSING,
            GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO,
            GATE_ACCOUNT_MODE_NOT_DEMO,
            GATE_PROOF_STRENGTH_NOT_STRONG,
            GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY,
            GATE_RUNNER_DRY_RUN_STATUS_UNACCEPTABLE,
            GATE_SELECTED_SYMBOL_MISSING,
            GATE_SELECTED_SYMBOL_COLLIDES_EXISTING,
        }
        for g in blocked:
            if g in stage_0_set:
                return STAGE_0_ARTIFACT_PREFLIGHT
        return ""


__all__ = [
    "EXISTING_POSITION_SYMBOLS",
    "DEFAULT_SELECTED_SYMBOL",
    "ORDER_CREATE_PATH_REF",
    "TRADING_STOP_PATH_REF",
    "BASE_URL_DEMO_REF",
    "BASE_URL_LIVE_REF",
    "DEMO_ENDPOINT_ALLOWLIST",
    "LIVE_ENDPOINT_DENYLIST",
    "ENTRY_TOKEN_PATTERN",
    "STOP_ATTACH_TOKEN_PATTERN",
    "CLEANUP_TOKEN_PATTERN",
    "REQUIRED_CONFIRMATION_FLAGS",
    "ACCEPTABLE_LIFECYCLE_SUMMARY_STATUSES",
    "ACCEPTABLE_RUNNER_DESIGN_STATUSES",
    "ACCEPTABLE_RUNNER_DRY_RUN_STATUSES",
    "EXPECTED_ENDPOINT_FAMILY",
    "EXPECTED_ACCOUNT_MODE",
    "EXPECTED_PROOF_STRENGTH",
    "EXPECTED_POSITION_DETAILS_SOURCE",
    "EXPECTED_LIFECYCLE_STATUS",
    "EXPECTED_INSTRUMENT_CATEGORY",
    "FUTURE_GUARDED_COMMANDS",
    "FORBIDDEN_SINGLE_LIFECYCLE_COMMAND",
    "FORBIDDEN_LOG_FIELDS",
    "READINESS_CONCLUSION_NOT_EXECUTABLE",
    "STAGE_0_ARTIFACT_PREFLIGHT",
    "STAGE_1_REVIEW_SCOPE",
    "STAGE_2_READINESS_MATRIX",
    "STAGE_3_GUARDED_RUNNER_MINIMUM_REQUIREMENTS",
    "STAGE_4_MANUAL_AUTHORIZATION_MODEL",
    "STAGE_5_ENVIRONMENT_ISOLATION_REVIEW",
    "STAGE_6_PRE_POST_READONLY_CONTRACT",
    "STAGE_7_FAILURE_AND_ABORT_REVIEW",
    "STAGE_8_FINAL_GUARDED_DESIGN_VERDICT",
    "ALL_STAGES",
    "STATUS_DESIGN_REVIEW_READY",
    "STATUS_DESIGN_REVIEW_READY_EXEC_DISABLED",
    "STATUS_REAL_RUNNER_NOT_IMPL",
    "STATUS_FAIL_CLOSED",
    "MODE_DESIGN_REVIEW_CHECKLIST",
    "MODE_GUARDED_DESIGN_APPROVAL_DRY_RUN",
    "MODE_REAL_RUNNER_EXECUTION_GUARD",
    "MODE_FAIL_CLOSED",
    # general (23)
    "GATE_READONLY_SMOKE_MISSING",
    "GATE_RECONCILIATION_MISSING",
    "GATE_PROTECTION_MISSING",
    "GATE_CONTRACT_MISSING",
    "GATE_NOOP_PLAN_MISSING",
    "GATE_LIFECYCLE_MOCK_MISSING",
    "GATE_REAL_PERMISSION_GATE_MISSING",
    "GATE_TINY_ENTRY_PERMISSION_GATE_MISSING",
    "GATE_TINY_STOP_ATTACH_PERMISSION_GATE_MISSING",
    "GATE_TINY_CLEANUP_PERMISSION_GATE_MISSING",
    "GATE_LIFECYCLE_SUMMARY_MISSING",
    "GATE_RUNNER_DESIGN_MISSING",
    "GATE_RUNNER_DRY_RUN_MISSING",
    "GATE_ENDPOINT_FAMILY_NOT_BYBIT_DEMO",
    "GATE_ACCOUNT_MODE_NOT_DEMO",
    "GATE_PROOF_STRENGTH_NOT_STRONG",
    "GATE_POSITION_DETAILS_SOURCE_NOT_REAL_READONLY",
    "GATE_SELECTED_SYMBOL_COLLIDES_EXISTING",
    "GATE_SELECTED_SYMBOL_MISSING",
    "GATE_RUNNER_DRY_RUN_STATUS_UNACCEPTABLE",
    "GATE_G20_POLICY_STILL_IN_PLACE",
    "GATE_NO_LIVE_ENDPOINT",
    "GATE_NO_SECRETS_EMITTED",
    # review scope (8)
    "GATE_GUARDED_DESIGN_REVIEW_ONLY",
    "GATE_REAL_RUNNER_NOT_IMPLEMENTED",
    "GATE_GUARDED_RUNNER_NOT_IMPLEMENTED",
    "GATE_REAL_EXECUTION_NOT_ALLOWED",
    "GATE_NO_ENDPOINT_INVOKED",
    "GATE_NO_POSITION_MODIFIED_SCOPE",
    "GATE_NO_SECRETS_LOADED",
    "GATE_NO_G20_LIFT",
    # readiness (8)
    "GATE_W_ACCEPTABLE",
    "GATE_X_ACCEPTABLE",
    "GATE_Y_ACCEPTABLE",
    "GATE_Z_ACCEPTABLE",
    "GATE_AA_ACCEPTABLE",
    "GATE_AB_ACCEPTABLE",
    "GATE_AC_ACCEPTABLE",
    "GATE_READINESS_NOT_EXECUTABLE",
    # guarded requirements (13)
    "GATE_ENTRY_ONLY_COMMAND_REQUIRED",
    "GATE_STOP_ONLY_COMMAND_REQUIRED",
    "GATE_CLEANUP_ONLY_COMMAND_REQUIRED",
    "GATE_NO_FULL_LIFECYCLE_SINGLE_COMMAND",
    "GATE_FRESH_READONLY_PRE_CHECK_REQUIRED",
    "GATE_POST_READONLY_REQUIRED",
    "GATE_ISOLATED_OUTPUT_DIR_REQUIRED",
    "GATE_HUMAN_STOP_BETWEEN_STEPS_REQUIRED",
    "GATE_NO_AUTO_NEXT_STEP",
    "GATE_NO_AUTO_RETRY",
    "GATE_NO_AUTO_CLEANUP",
    "GATE_NO_AUTO_EMERGENCY_CLOSE",
    "GATE_NO_BACKGROUND_LOOP",
    # manual auth (11)
    "GATE_ENTRY_TOKEN_PATTERN_PRESENT",
    "GATE_STOP_TOKEN_PATTERN_PRESENT",
    "GATE_CLEANUP_TOKEN_PATTERN_PRESENT",
    "GATE_TOKEN_PER_STEP",
    "GATE_TOKEN_INCLUDES_DATE_POLICY",
    "GATE_TOKEN_INCLUDES_SYMBOL",
    "GATE_SECOND_CONFIRMATION_REQUIRED",
    "GATE_MAX_NOTIONAL_CAP_REQUIRED",
    "GATE_EXPECTED_EXISTING_SYMBOLS_REQUIRED",
    "GATE_TOKEN_FORMAT_NOT_AUTHORIZATION",
    "GATE_TOKENS_NOT_VALIDATED",
    # environment isolation (11)
    "GATE_DEMO_ENDPOINT_ALLOWLIST",
    "GATE_LIVE_ENDPOINT_DENYLIST",
    "GATE_NO_FALLBACK_ENDPOINT",
    "GATE_ONE_COMMAND_ONE_STEP",
    "GATE_NO_DAEMON",
    "GATE_NO_CRON",
    "GATE_NO_SCHEDULER",
    "GATE_NO_BACKGROUND_WORKER",
    "GATE_NO_DISCORD_TRIGGER",
    "GATE_NO_NOTION_TRIGGER",
    "GATE_SECRETS_NOT_READ",
    # readonly contract (7)
    "GATE_PRE_CHECK_REQUIRED",
    "GATE_POST_ENTRY_REQUIRED",
    "GATE_POST_STOP_REQUIRED",
    "GATE_POST_CLEANUP_REQUIRED",
    "GATE_READONLY_UNAVAILABLE_FAIL_CLOSED",
    "GATE_MISMATCH_MANUAL_REVIEW",
    "GATE_EXISTING_FIVE_POSITIONS_UNCHANGED",
    # failure policy (11)
    "GATE_REQUEST_REJECTED_FAIL_CLOSED",
    "GATE_PARTIAL_FILL_FAIL_CLOSED",
    "GATE_READONLY_UNAVAIL_FAIL_CLOSED_FAILURE",
    "GATE_SELECTED_SYMBOL_MISMATCH_FAIL_CLOSED",
    "GATE_EXISTING_POSITION_TOUCHED_MANUAL_REVIEW",
    "GATE_LIVE_ENDPOINT_DETECTED_FAIL_CLOSED",
    "GATE_SECRET_EMISSION_FAIL_CLOSED",
    "GATE_NO_AUTOMATIC_RETRY",
    "GATE_NO_AUTOMATIC_CLEANUP",
    "GATE_NO_AUTOMATIC_EMERGENCY_CLOSE",
    "GATE_NO_AUTOMATIC_NEXT_STEP",
    # execution guard (5)
    "GATE_REAL_RUNNER_EXECUTION_NOT_IMPL",
    "GATE_NO_REAL_ORDER_ENDPOINT",
    "GATE_NO_REAL_STOP_ENDPOINT",
    "GATE_NO_POSITION_MODIFIED",
    "GATE_G20_NOT_LIFTED",
    # data
    "DemoTinyLifecycleGuardedRunnerDesignReview",
    "TinyLifecycleGuardedRunnerDesignReviewResult",
]
