"""
src/demo_wallet_audit.py
TASK-014I: Bybit Demo wallet / margin availability field audit.

Pure computation — no network calls, no order calls, no secrets in output.

Purpose:
  Investigate whether available_balance_usd = 0.00 is a genuine account state
  or a mapping error.  Captures every relevant wallet field from the raw
  API response, evaluates all candidate available-balance fields, and emits
  a structured audit result with a mapping-suspect flag.

Candidate available-balance fields evaluated (in priority order):
  1. account.totalAvailableBalance
  2. account.availableToWithdraw
  3. coin.USDT.availableToWithdraw
  4. coin.USDT.free
  5. coin.USDT.walletBalance

Current system mapping (from _wallet_real in demo_readonly_client.py):
  coin.USDT.availableToWithdraw  (with fallback to availableToBorrow)

Safety invariants (structural):
  no_orders_sent = True (always)
  order_endpoint_called = False (always)
  secret_value_observed = False (always)
  new_entry_allowed = False (always — this module never enables new entries)
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

from src.demo_readonly_client import PROOF_STRONG


# ---------------------------------------------------------------------------
# Current mapping label (what demo_readonly_client._wallet_real uses)
# ---------------------------------------------------------------------------

CURRENT_MAPPING_FIELD = "coin.USDT.availableToWithdraw"

# Tolerance for "significant conflict" between candidates (absolute USD).
_CONFLICT_THRESHOLD_USD = 10.0

# Only these candidates are used for conflict/suspect detection.
# coin.USDT.walletBalance is intentionally excluded — it includes locked margin
# and will differ from available_balance whenever positions are open.
_CONFLICT_CANDIDATE_FIELDS = frozenset({
    "account.totalAvailableBalance",
    "account.availableToWithdraw",
    "coin.USDT.availableToWithdraw",
    "coin.USDT.free",
})


# ---------------------------------------------------------------------------
# Data types
# ---------------------------------------------------------------------------

@dataclass
class WalletFieldSummary:
    """
    Raw wallet field values extracted from the Bybit wallet-balance response.
    None means the field was absent in the API response.
    """
    # Account-level
    account_type:                   str          = ""
    total_equity:                   float | None = None
    total_wallet_balance:           float | None = None
    total_margin_balance:           float | None = None
    total_available_balance:        float | None = None
    account_im_rate:                float | None = None
    account_mm_rate:                float | None = None
    account_available_to_withdraw:  float | None = None

    # USDT coin-level
    coin_usdt_equity:               float | None = None
    coin_usdt_wallet_balance:       float | None = None
    coin_usdt_free:                 float | None = None
    coin_usdt_locked:               float | None = None
    coin_usdt_available_to_withdraw: float | None = None
    coin_usdt_usd_value:            float | None = None
    coin_usdt_borrow_amount:        float | None = None
    coin_usdt_accrued_interest:     float | None = None

    # Missing-field flags
    field_missing_total_available_balance:       bool = False
    field_missing_account_available_to_withdraw: bool = False
    field_missing_coin_usdt_free:                bool = False
    field_missing_coin_usdt_available_to_withdraw: bool = False
    field_missing_coin_usdt_wallet_balance:      bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "account_type":                   self.account_type,
            "total_equity":                   self.total_equity,
            "total_wallet_balance":           self.total_wallet_balance,
            "total_margin_balance":           self.total_margin_balance,
            "total_available_balance":        self.total_available_balance,
            "account_im_rate":                self.account_im_rate,
            "account_mm_rate":                self.account_mm_rate,
            "account_available_to_withdraw":  self.account_available_to_withdraw,
            "coin_usdt_equity":               self.coin_usdt_equity,
            "coin_usdt_wallet_balance":       self.coin_usdt_wallet_balance,
            "coin_usdt_free":                 self.coin_usdt_free,
            "coin_usdt_locked":               self.coin_usdt_locked,
            "coin_usdt_available_to_withdraw": self.coin_usdt_available_to_withdraw,
            "coin_usdt_usd_value":            self.coin_usdt_usd_value,
            "coin_usdt_borrow_amount":        self.coin_usdt_borrow_amount,
            "coin_usdt_accrued_interest":     self.coin_usdt_accrued_interest,
            "field_missing_total_available_balance":       self.field_missing_total_available_balance,
            "field_missing_account_available_to_withdraw": self.field_missing_account_available_to_withdraw,
            "field_missing_coin_usdt_free":                self.field_missing_coin_usdt_free,
            "field_missing_coin_usdt_available_to_withdraw": self.field_missing_coin_usdt_available_to_withdraw,
            "field_missing_coin_usdt_wallet_balance":      self.field_missing_coin_usdt_wallet_balance,
        }


@dataclass
class AvailableBalanceCandidate:
    """One candidate field for available_balance_usd."""
    field_name: str
    value:      float | None
    present:    bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "field_name": self.field_name,
            "value":      self.value,
            "present":    self.present,
        }


@dataclass
class WalletAuditResult:
    """
    Full wallet availability audit result.

    Safety invariants:
      no_orders_sent = True always
      order_endpoint_called = False always
      secret_value_observed = False always
      new_entry_allowed = False always
    """
    timestamp_utc:                    str
    demo_runtime_verified:            bool
    proof_strength:                   str
    endpoint_family:                  str
    account_mode:                     str
    equity_usd:                       float
    current_available_balance_usd:    float
    current_available_balance_usd_source: str
    raw_wallet_field_summary:         WalletFieldSummary
    candidate_available_fields:       list[AvailableBalanceCandidate]
    chosen_available_balance_field:   str
    chosen_available_balance_value:   float
    chosen_reason:                    str
    available_balance_mapping_suspect: bool
    mismatch_warning:                 str
    fail_closed:                      bool
    fail_reason:                      str
    recommended_next_action:          str
    no_orders_sent:                   bool = True
    order_endpoint_called:            bool = False
    secret_value_observed:            bool = False
    new_entry_allowed:                bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "timestamp_utc":                      self.timestamp_utc,
            "demo_runtime_verified":              self.demo_runtime_verified,
            "proof_strength":                     self.proof_strength,
            "endpoint_family":                    self.endpoint_family,
            "account_mode":                       self.account_mode,
            "equity_usd":                         self.equity_usd,
            "current_available_balance_usd":      self.current_available_balance_usd,
            "current_available_balance_usd_source": self.current_available_balance_usd_source,
            "raw_wallet_field_summary":           self.raw_wallet_field_summary.to_dict(),
            "candidate_available_fields":         [c.to_dict() for c in self.candidate_available_fields],
            "chosen_available_balance_field":     self.chosen_available_balance_field,
            "chosen_available_balance_value":     self.chosen_available_balance_value,
            "chosen_reason":                      self.chosen_reason,
            "available_balance_mapping_suspect":  self.available_balance_mapping_suspect,
            "mismatch_warning":                   self.mismatch_warning,
            "fail_closed":                        self.fail_closed,
            "fail_reason":                        self.fail_reason,
            "recommended_next_action":            self.recommended_next_action,
            "no_orders_sent":                     self.no_orders_sent,
            "order_endpoint_called":              self.order_endpoint_called,
            "secret_value_observed":              self.secret_value_observed,
            "new_entry_allowed":                  self.new_entry_allowed,
        }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

FIXTURE_WALLET_RAW: dict[str, Any] = {
    "retCode": 0,
    "retMsg": "OK",
    "result": {
        "list": [
            {
                "accountType": "UNIFIED",
                "totalEquity": "11613.47",
                "totalWalletBalance": "11500.00",
                "totalMarginBalance": "11613.47",
                "totalAvailableBalance": "0.00",
                "accountIMRate": "0.4447",
                "accountMMRate": "0.0300",
                "availableToWithdraw": "0.00",
                "coin": [
                    {
                        "coin": "USDT",
                        "equity": "11613.47",
                        "walletBalance": "11500.00",
                        "free": "0.00",
                        "locked": "0.00",
                        "availableToWithdraw": "0.00",
                        "usdValue": "11613.47",
                        "borrowAmount": "0.00",
                        "accruedInterest": "0.00",
                    }
                ],
            }
        ]
    },
}


# ---------------------------------------------------------------------------
# Field extractor
# ---------------------------------------------------------------------------

def _opt_float(value: Any) -> float | None:
    """Parse a value to float, returning None if absent/empty/invalid."""
    if value is None:
        return None
    try:
        s = str(value).strip()
        if not s:
            return None
        return float(s)
    except (TypeError, ValueError):
        return None


def extract_wallet_fields(raw_response: dict[str, Any]) -> WalletFieldSummary:
    """
    Extract all relevant wallet fields from a Bybit wallet-balance API response.

    Handles missing keys gracefully — absent fields produce None values with
    corresponding field_missing=True flags.

    Does not include any secret values in output.
    """
    summary = WalletFieldSummary()
    try:
        acc_list = raw_response.get("result", {}).get("list", [])
        if not acc_list:
            return summary
        acc = acc_list[0]

        summary.account_type = str(acc.get("accountType", "") or "")

        # Account-level float fields
        raw_tab  = acc.get("totalAvailableBalance")
        raw_wab  = acc.get("availableToWithdraw")

        summary.total_equity             = _opt_float(acc.get("totalEquity"))
        summary.total_wallet_balance     = _opt_float(acc.get("totalWalletBalance"))
        summary.total_margin_balance     = _opt_float(acc.get("totalMarginBalance"))
        summary.account_im_rate          = _opt_float(acc.get("accountIMRate"))
        summary.account_mm_rate          = _opt_float(acc.get("accountMMRate"))

        if raw_tab is None:
            summary.field_missing_total_available_balance = True
        else:
            summary.total_available_balance = _opt_float(raw_tab)

        if raw_wab is None:
            summary.field_missing_account_available_to_withdraw = True
        else:
            summary.account_available_to_withdraw = _opt_float(raw_wab)

        # USDT coin-level fields
        coins = acc.get("coin", []) or []
        usdt  = next((c for c in coins if c.get("coin") == "USDT"), None)
        if usdt is not None:
            summary.coin_usdt_equity          = _opt_float(usdt.get("equity"))
            summary.coin_usdt_usd_value       = _opt_float(usdt.get("usdValue"))
            summary.coin_usdt_borrow_amount   = _opt_float(usdt.get("borrowAmount"))
            summary.coin_usdt_accrued_interest = _opt_float(usdt.get("accruedInterest"))
            summary.coin_usdt_locked          = _opt_float(usdt.get("locked"))

            raw_wb  = usdt.get("walletBalance")
            raw_free = usdt.get("free")
            raw_atw  = usdt.get("availableToWithdraw")

            if raw_wb is None:
                summary.field_missing_coin_usdt_wallet_balance = True
            else:
                summary.coin_usdt_wallet_balance = _opt_float(raw_wb)

            if raw_free is None:
                summary.field_missing_coin_usdt_free = True
            else:
                summary.coin_usdt_free = _opt_float(raw_free)

            if raw_atw is None:
                summary.field_missing_coin_usdt_available_to_withdraw = True
            else:
                summary.coin_usdt_available_to_withdraw = _opt_float(raw_atw)

    except (KeyError, IndexError, TypeError):
        pass

    return summary


# ---------------------------------------------------------------------------
# Candidate evaluator
# ---------------------------------------------------------------------------

def _build_candidates(summary: WalletFieldSummary) -> list[AvailableBalanceCandidate]:
    """Return all 5 candidate fields in priority order."""
    return [
        AvailableBalanceCandidate(
            field_name="account.totalAvailableBalance",
            value=summary.total_available_balance,
            present=not summary.field_missing_total_available_balance,
        ),
        AvailableBalanceCandidate(
            field_name="account.availableToWithdraw",
            value=summary.account_available_to_withdraw,
            present=not summary.field_missing_account_available_to_withdraw,
        ),
        AvailableBalanceCandidate(
            field_name="coin.USDT.availableToWithdraw",
            value=summary.coin_usdt_available_to_withdraw,
            present=not summary.field_missing_coin_usdt_available_to_withdraw,
        ),
        AvailableBalanceCandidate(
            field_name="coin.USDT.free",
            value=summary.coin_usdt_free,
            present=not summary.field_missing_coin_usdt_free,
        ),
        AvailableBalanceCandidate(
            field_name="coin.USDT.walletBalance",
            value=summary.coin_usdt_wallet_balance,
            present=not summary.field_missing_coin_usdt_wallet_balance,
        ),
    ]


def _choose_candidate(
    candidates: list[AvailableBalanceCandidate],
) -> tuple[AvailableBalanceCandidate | None, str]:
    """
    Select the best available-balance candidate in priority order.

    Priority: account.totalAvailableBalance → account.availableToWithdraw
              → coin.USDT.availableToWithdraw → coin.USDT.free
              → coin.USDT.walletBalance

    Returns (chosen_candidate, reason_string).
    """
    for c in candidates:
        if c.present and c.value is not None:
            return c, f"first present candidate in priority order"
    return None, "all candidates missing"


# ---------------------------------------------------------------------------
# Main audit function
# ---------------------------------------------------------------------------

def audit_wallet(
    raw_response:          dict[str, Any],
    current_available_usd: float,
    proof_strength:        str,
    endpoint_family:       str,
    account_mode:          str,
    demo_runtime_verified: bool,
    equity_usd:            float,
    timestamp_utc:         str,
) -> WalletAuditResult:
    """
    Audit the wallet balance response and evaluate available-balance mapping.

    Pure computation — no network calls, no order calls, no secrets in output.

    Args:
        raw_response:          Full Bybit wallet-balance API response dict.
        current_available_usd: The value currently used as available_balance_usd
                               (from demo_readonly_client._wallet_real).
        proof_strength:        STRONG / WEAK / MISSING from runtime proof.
        endpoint_family:       "bybit_demo" or other.
        account_mode:          "demo" or other.
        demo_runtime_verified: True if TASK-014D proof was STRONG.
        equity_usd:            Current equity in USD.
        timestamp_utc:         ISO timestamp for the report.

    Returns:
        WalletAuditResult with full field summary, candidates, and suspect flag.
    """
    # Fail-closed conditions
    fail_closed = False
    fail_reason = ""

    if proof_strength != PROOF_STRONG:
        fail_closed = True
        fail_reason = f"proof_strength={proof_strength!r} is not STRONG"
    elif endpoint_family != "bybit_demo":
        fail_closed = True
        fail_reason = f"endpoint_family={endpoint_family!r} is not bybit_demo"

    # Extract fields
    summary    = extract_wallet_fields(raw_response)
    candidates = _build_candidates(summary)

    # All liquidity-oriented candidate fields missing (excludes walletBalance)
    all_missing = all(
        not c.present
        for c in candidates
        if c.field_name in _CONFLICT_CANDIDATE_FIELDS
    )
    if all_missing and not fail_closed:
        fail_closed = True
        fail_reason = "all_candidate_available_balance_fields_missing"

    # Choose best candidate
    chosen, chosen_reason = _choose_candidate(candidates)
    if chosen is None:
        chosen_field = ""
        chosen_value = 0.0
        if not fail_closed:
            fail_closed = True
            fail_reason = "no_valid_candidate_available_balance_field"
    else:
        chosen_field = chosen.field_name
        chosen_value = chosen.value if chosen.value is not None else 0.0

    # Significant conflict: any liquidity-oriented candidate differs from current.
    # coin.USDT.walletBalance is excluded — it includes locked margin and will
    # always differ from available_balance when positions are open.
    suspect = False
    mismatch_warning = ""
    if not fail_closed:
        for c in candidates:
            if c.field_name not in _CONFLICT_CANDIDATE_FIELDS:
                continue
            if c.present and c.value is not None:
                diff = abs(c.value - current_available_usd)
                if diff > _CONFLICT_THRESHOLD_USD:
                    suspect = True
                    mismatch_warning = (
                        f"{c.field_name}={c.value:.2f} differs from "
                        f"current ({CURRENT_MAPPING_FIELD}={current_available_usd:.2f}) "
                        f"by {diff:.2f} USD (>{_CONFLICT_THRESHOLD_USD} threshold)"
                    )
                    break

        # Also suspect if chosen field is a liquidity candidate, its value > current
        if not suspect and chosen_field in _CONFLICT_CANDIDATE_FIELDS:
            if current_available_usd <= 0.0 and chosen_value > _CONFLICT_THRESHOLD_USD:
                suspect = True
                mismatch_warning = (
                    f"chosen_candidate {chosen_field}={chosen_value:.2f} "
                    f"while current mapping {CURRENT_MAPPING_FIELD}={current_available_usd:.2f} — "
                    f"possible mapping mismatch"
                )

    # Recommend next action
    if fail_closed:
        recommended = "fail_closed — manual wallet review required before enabling new entries"
    elif suspect:
        recommended = (
            f"available_balance_mapping_suspect=True — "
            f"consider switching to {chosen_field}={chosen_value:.2f} for available_balance_usd; "
            f"verify on VPS with real --real-readonly mode"
        )
    elif current_available_usd <= 0.0:
        recommended = (
            "all candidates agree: available_balance_usd=0.00 — "
            "genuine zero-margin state; close positions to release margin before new entries"
        )
    else:
        recommended = (
            f"current mapping {CURRENT_MAPPING_FIELD}={current_available_usd:.2f} "
            f"matches best candidate — no action needed"
        )

    return WalletAuditResult(
        timestamp_utc=timestamp_utc,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        endpoint_family=endpoint_family,
        account_mode=account_mode,
        equity_usd=equity_usd,
        current_available_balance_usd=current_available_usd,
        current_available_balance_usd_source=CURRENT_MAPPING_FIELD,
        raw_wallet_field_summary=summary,
        candidate_available_fields=candidates,
        chosen_available_balance_field=chosen_field,
        chosen_available_balance_value=chosen_value,
        chosen_reason=chosen_reason,
        available_balance_mapping_suspect=suspect,
        mismatch_warning=mismatch_warning,
        fail_closed=fail_closed,
        fail_reason=fail_reason,
        recommended_next_action=recommended,
        no_orders_sent=True,
        order_endpoint_called=False,
        secret_value_observed=False,
        new_entry_allowed=False,
    )
