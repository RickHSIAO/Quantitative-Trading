"""
src/demo_runtime_probe.py
TASK-014B: Demo environment runtime probe.

Validates a caller-supplied DemoRuntimeProof that the connected account is in Demo mode.
This module makes NO network calls and loads NO secrets.

FAIL-CLOSED design:
  Any absent, incomplete, or contradictory proof -> demo_runtime_verified=False.

WHY a config flag alone is insufficient:
  demo_config_expected=True is a caller assertion, not evidence. An operator
  error could set it True while the account is live. Runtime proof must come
  from a verified external source (e.g. the account-info API response that
  explicitly carries the demo/account_mode field). Phase 3 callers are
  responsible for fetching that proof; this module only validates it.

PHASE 3 WIRING POINT:
  Callers read the read-only account-info endpoint, extract account_mode and
  demo fields, then construct a DemoRuntimeProof. This module verifies the
  proof without touching the network itself.

SAFETY:
  no_orders_sent = True       (always)
  secrets_loaded = False      (always)
  private_order_endpoint_called = False  (always)
"""
from __future__ import annotations

from dataclasses import dataclass


# ---------------------------------------------------------------------------
# Failure-reason tokens
# ---------------------------------------------------------------------------

FAIL_NO_PROOF              = "no_runtime_proof_supplied"
FAIL_CONFIG_FALSE          = "demo_config_expected_is_false"
FAIL_DEMO_FLAG_FALSE       = "runtime_proof_demo_flag_is_false"
FAIL_ACCOUNT_MODE_INVALID  = "runtime_proof_account_mode_does_not_indicate_demo"
FAIL_ENDPOINT_UNRECOGNISED = "runtime_proof_endpoint_family_not_recognised"
FAIL_PROOF_FIELDS_INVALID  = "runtime_proof_fields_missing_or_invalid"

# Recognised demo-endpoint family identifiers (matched case-insensitively)
DEMO_ENDPOINT_FAMILIES: frozenset[str] = frozenset({
    "bybit_demo",
    "demo",
    "testnet",
    "bybit_testnet",
    "sandbox",
})


# ---------------------------------------------------------------------------
# Input type: DemoRuntimeProof
# ---------------------------------------------------------------------------

@dataclass
class DemoRuntimeProof:
    """
    Evidence that the runtime environment is Demo.

    Must be obtained from a verified external source (e.g. an account-info
    API response) — NOT derived from a config flag alone.

    Fields:
      account_mode    : Account-mode string from the environment.
                        Must contain "demo" (case-insensitive) to be accepted.
      demo_flag       : Whether the environment explicitly signals demo mode.
                        Must be True to be accepted.
      endpoint_family : Endpoint-family identifier; must be in DEMO_ENDPOINT_FAMILIES.
      source          : Human-readable description of where the proof was obtained.
    """
    account_mode:    str
    demo_flag:       bool
    endpoint_family: str
    source:          str


# ---------------------------------------------------------------------------
# Output type: DemoRuntimeProbeResult
# ---------------------------------------------------------------------------

@dataclass
class DemoRuntimeProbeResult:
    """
    Result of a demo-runtime probe.

    demo_runtime_verified=True only when ALL six checks in probe_demo_runtime() pass.
    fail_closed=True means new sizing proposals must not be generated.
    """
    demo_config_expected:          bool
    demo_runtime_verified:         bool
    endpoint_family:               str
    account_mode:                  str
    failure_reason:                str
    fail_closed:                   bool
    no_orders_sent:                bool = True
    secrets_loaded:                bool = False
    private_order_endpoint_called: bool = False


# ---------------------------------------------------------------------------
# Core probe function
# ---------------------------------------------------------------------------

def probe_demo_runtime(
    demo_config_expected: bool,
    runtime_proof: "DemoRuntimeProof | None" = None,
) -> DemoRuntimeProbeResult:
    """
    Validate that the runtime is a verified Demo environment.

    Returns demo_runtime_verified=True ONLY when ALL of the following hold:
      1. demo_config_expected is True
      2. runtime_proof is not None
      3. runtime_proof.account_mode and endpoint_family are non-empty strings
      4. runtime_proof.demo_flag is True
      5. runtime_proof.account_mode contains "demo" (case-insensitive)
      6. runtime_proof.endpoint_family is in DEMO_ENDPOINT_FAMILIES

    Fail-closed in all other cases: demo_runtime_verified=False, fail_closed=True.
    No network calls. No secrets. no_orders_sent=True in every output.
    """
    # ── 1. Config must assert demo ────────────────────────────────────────
    if not demo_config_expected:
        return DemoRuntimeProbeResult(
            demo_config_expected=False,
            demo_runtime_verified=False,
            endpoint_family="", account_mode="",
            failure_reason=FAIL_CONFIG_FALSE,
            fail_closed=True,
        )

    # ── 2. Proof must be supplied ─────────────────────────────────────────
    if runtime_proof is None:
        return DemoRuntimeProbeResult(
            demo_config_expected=True,
            demo_runtime_verified=False,
            endpoint_family="", account_mode="",
            failure_reason=FAIL_NO_PROOF,
            fail_closed=True,
        )

    # ── 3. Proof fields must be valid non-empty strings ───────────────────
    ef  = getattr(runtime_proof, "endpoint_family", None) or ""
    am  = getattr(runtime_proof, "account_mode",    None) or ""
    if not (isinstance(ef, str) and isinstance(am, str)
            and ef.strip() and am.strip()):
        return DemoRuntimeProbeResult(
            demo_config_expected=True,
            demo_runtime_verified=False,
            endpoint_family=ef, account_mode=am,
            failure_reason=FAIL_PROOF_FIELDS_INVALID,
            fail_closed=True,
        )

    # ── 4. demo_flag must be True ─────────────────────────────────────────
    if not runtime_proof.demo_flag:
        return DemoRuntimeProbeResult(
            demo_config_expected=True,
            demo_runtime_verified=False,
            endpoint_family=ef, account_mode=am,
            failure_reason=FAIL_DEMO_FLAG_FALSE,
            fail_closed=True,
        )

    # ── 5. account_mode must contain "demo" ───────────────────────────────
    if "demo" not in am.lower():
        return DemoRuntimeProbeResult(
            demo_config_expected=True,
            demo_runtime_verified=False,
            endpoint_family=ef, account_mode=am,
            failure_reason=FAIL_ACCOUNT_MODE_INVALID,
            fail_closed=True,
        )

    # ── 6. endpoint_family must be recognised ─────────────────────────────
    if ef.lower() not in DEMO_ENDPOINT_FAMILIES:
        return DemoRuntimeProbeResult(
            demo_config_expected=True,
            demo_runtime_verified=False,
            endpoint_family=ef, account_mode=am,
            failure_reason=FAIL_ENDPOINT_UNRECOGNISED,
            fail_closed=True,
        )

    # ── All checks passed ─────────────────────────────────────────────────
    return DemoRuntimeProbeResult(
        demo_config_expected=True,
        demo_runtime_verified=True,
        endpoint_family=ef, account_mode=am,
        failure_reason="",
        fail_closed=False,
    )


# ---------------------------------------------------------------------------
# Fixture factory  (tests and dry-run previews only)
# ---------------------------------------------------------------------------

def make_fixture_proof(
    account_mode:    str  = "demo",
    demo_flag:       bool = True,
    endpoint_family: str  = "bybit_demo",
    source:          str  = "fixture_for_dry_run_preview",
) -> DemoRuntimeProof:
    """
    Build a fixture DemoRuntimeProof for tests and local dry-run previews.
    Must NOT be used to bypass real environment checks in production paths.
    """
    return DemoRuntimeProof(
        account_mode=account_mode,
        demo_flag=demo_flag,
        endpoint_family=endpoint_family,
        source=source,
    )
