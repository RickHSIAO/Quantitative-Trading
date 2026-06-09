"""
tests/demo_trading/test_demo_task_014j.py
TASK-014J: Fix Demo Available Balance Mapping to account.totalAvailableBalance

The bug TASK-014J fixes:
  VPS real read-only audit showed account.totalAvailableBalance=7169.40 while
  the prior mapping coin.USDT.availableToWithdraw=0.00 caused a false
  available_balance_zero_or_negative violation, blocking new entries.

Requirements verified (J1-J12):
  J1.  _wallet_real uses account.totalAvailableBalance as available_balance_usd
       when the field is present in the API response
  J2.  available_balance_usd_source = "account.totalAvailableBalance" when TAB present
  J3.  coin.USDT.availableToWithdraw absent/None/zero does NOT override TAB with 0
  J4.  coin.USDT.walletBalance is never selected as available_balance_usd
  J5.  account.totalWalletBalance is never selected as available_balance_usd
  J6.  fallback to account.availableToWithdraw when TAB absent
  J7.  fallback to coin.USDT.availableToWithdraw when acc.availableToWithdraw absent
  J8.  fail-closed: all candidate fields absent → available_balance_usd=0, source="missing"
  J9.  wallet audit available_balance_mapping_suspect=False when runtime correctly
       maps to account.totalAvailableBalance and value matches chosen candidate
  J10. new/modified source files contain no embedded API secrets
  J11. no order-endpoint tokens in new/modified source files
  J12. main.py, src/risk.py, BybitExecutor are NOT modified by TASK-014J
"""
from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_readonly_client import PROOF_STRONG, DemoReadOnlyClient
from src.demo_wallet_audit import (
    CURRENT_MAPPING_FIELD,
    _CONFLICT_CANDIDATE_FIELDS,
    audit_wallet,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _bybit_wallet_resp(
    *,
    total_available_balance: float | str | None = "7169.40",
    account_available_to_withdraw: float | str | None = None,
    coin_available_to_withdraw: float | str | None = None,
    coin_free: float | str | None = None,
    wallet_balance: float = 12000.0,
    equity: float = 11500.0,
    total_wallet_balance: float = 12000.0,
    account_type: str = "UNIFIED",
) -> dict:
    """Build a minimal Bybit V5 wallet-balance API response dict."""
    acc: dict = {
        "accountType": account_type,
        "totalWalletBalance": str(total_wallet_balance),
        "coin": [{
            "coin": "USDT",
            "equity": str(equity),
            "walletBalance": str(wallet_balance),
        }],
    }
    if total_available_balance is not None:
        acc["totalAvailableBalance"] = (
            str(total_available_balance)
            if not isinstance(total_available_balance, str)
            else total_available_balance
        )
    if account_available_to_withdraw is not None:
        acc["availableToWithdraw"] = str(account_available_to_withdraw)
    if coin_available_to_withdraw is not None:
        acc["coin"][0]["availableToWithdraw"] = str(coin_available_to_withdraw)
    if coin_free is not None:
        acc["coin"][0]["free"] = str(coin_free)
    return {"retCode": 0, "result": {"list": [acc]}}


def _real_client() -> DemoReadOnlyClient:
    return DemoReadOnlyClient(allow_real_network=True)


# ---------------------------------------------------------------------------
# J1: account.totalAvailableBalance used as available_balance_usd
# ---------------------------------------------------------------------------

class TestJ1TotalAvailableBalanceUsed:
    """J1: _wallet_real maps account.totalAvailableBalance to available_balance_usd."""

    def test_tab_7169_produces_correct_available(self):
        client = _real_client()
        with patch.object(client, "_get", return_value=_bybit_wallet_resp(total_available_balance="7169.40")):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(7169.40, abs=0.01)

    def test_tab_zero_produces_zero_available(self):
        client = _real_client()
        with patch.object(client, "_get", return_value=_bybit_wallet_resp(total_available_balance="0.00")):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(0.0, abs=0.01)

    def test_tab_present_coin_atw_absent_still_uses_tab(self):
        """TAB present; coin.USDT.availableToWithdraw absent → uses TAB, not 0."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance="5000.00",
            coin_available_to_withdraw=None,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(5000.0, abs=0.01)

    def test_order_endpoint_not_called(self):
        client = _real_client()
        with patch.object(client, "_get", return_value=_bybit_wallet_resp()):
            w = client.get_wallet_balance()
        assert w.order_endpoint_called is False


# ---------------------------------------------------------------------------
# J2: available_balance_usd_source = "account.totalAvailableBalance"
# ---------------------------------------------------------------------------

class TestJ2SourceLabel:
    """J2: source label is correct when TAB is used."""

    def test_source_is_account_total_available_balance_real_mode(self):
        client = _real_client()
        with patch.object(client, "_get", return_value=_bybit_wallet_resp(total_available_balance="7169.40")):
            w = client.get_wallet_balance()
        assert w.available_balance_usd_source == "account.totalAvailableBalance"

    def test_fixture_wallet_source_is_tab(self):
        from src.demo_readonly_client import FIXTURE_WALLET
        assert FIXTURE_WALLET.available_balance_usd_source == "account.totalAvailableBalance"

    def test_fixture_mode_returns_tab_source(self):
        client = DemoReadOnlyClient(allow_real_network=False)
        w = client.get_wallet_balance()
        assert w.available_balance_usd_source == "account.totalAvailableBalance"

    def test_snapshot_has_available_balance_usd_source_field(self):
        client = DemoReadOnlyClient(allow_real_network=False)
        w = client.get_wallet_balance()
        assert hasattr(w, "available_balance_usd_source")


# ---------------------------------------------------------------------------
# J3: coin.USDT.availableToWithdraw absent/zero does NOT override TAB
# ---------------------------------------------------------------------------

class TestJ3CoinATWDoesNotOverrideTAB:
    """J3: coin.USDT.availableToWithdraw=0 or absent does not replace TAB value."""

    def test_coin_atw_absent_does_not_zero_out_tab(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance="7169.40",
            coin_available_to_withdraw=None,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(7169.40, abs=0.01)

    def test_coin_atw_zero_does_not_override_tab(self):
        """coin.USDT.availableToWithdraw=0.00 while TAB=7169.40 → TAB wins."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance="7169.40",
            coin_available_to_withdraw="0.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(7169.40, abs=0.01)
        assert w.available_balance_usd_source == "account.totalAvailableBalance"

    def test_coin_atw_nonzero_does_not_override_tab(self):
        """coin.USDT.availableToWithdraw=999 while TAB=7169.40 → TAB wins."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance="7169.40",
            coin_available_to_withdraw="999.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(7169.40, abs=0.01)
        assert w.available_balance_usd_source == "account.totalAvailableBalance"


# ---------------------------------------------------------------------------
# J4: coin.USDT.walletBalance must NOT be used as available_balance_usd
# ---------------------------------------------------------------------------

class TestJ4WalletBalanceExcluded:
    """J4: coin.USDT.walletBalance is never selected as available_balance_usd."""

    def test_only_wallet_balance_present_gives_zero(self):
        """All candidate fields absent; walletBalance=12000 → available_balance_usd=0."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free=None,
            wallet_balance=12000.0,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(0.0, abs=0.01)

    def test_wallet_balance_source_never_returned(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free=None,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd_source != "coin.USDT.walletBalance"

    def test_wallet_balance_stored_separately_not_as_available(self):
        """walletBalance is preserved in wallet_balance_usd, not available_balance_usd."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance="5000.00",
            wallet_balance=12000.0,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.wallet_balance_usd == pytest.approx(12000.0, abs=0.01)
        assert w.available_balance_usd == pytest.approx(5000.0, abs=0.01)

    def test_wallet_balance_excluded_from_conflict_candidates(self):
        assert "coin.USDT.walletBalance" not in _CONFLICT_CANDIDATE_FIELDS


# ---------------------------------------------------------------------------
# J5: account.totalWalletBalance must NOT be used as available_balance_usd
# ---------------------------------------------------------------------------

class TestJ5TotalWalletBalanceExcluded:
    """J5: account.totalWalletBalance is never selected as available_balance_usd."""

    def test_total_wallet_balance_only_gives_zero_available(self):
        """totalWalletBalance=12000; all candidate fields absent → available=0."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free=None,
            total_wallet_balance=12000.0,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(0.0, abs=0.01)

    def test_total_wallet_balance_source_never_in_label(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free=None,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert "totalWalletBalance" not in w.available_balance_usd_source
        assert "walletBalance" not in w.available_balance_usd_source


# ---------------------------------------------------------------------------
# J6: fallback to account.availableToWithdraw when TAB absent
# ---------------------------------------------------------------------------

class TestJ6FallbackToAccountAvailableToWithdraw:
    """J6: TAB absent → use account.availableToWithdraw."""

    def test_tab_absent_uses_account_atw_value(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw="5000.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(5000.0, abs=0.01)

    def test_tab_absent_source_is_account_atw(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw="3000.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd_source == "account.availableToWithdraw"

    def test_tab_empty_string_falls_through_to_acc_atw(self):
        """TAB present but empty string → treated as absent → fallback."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance="",
            account_available_to_withdraw="4000.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(4000.0, abs=0.01)
        assert w.available_balance_usd_source == "account.availableToWithdraw"


# ---------------------------------------------------------------------------
# J7: fallback to coin.USDT.availableToWithdraw when account.availableToWithdraw absent
# ---------------------------------------------------------------------------

class TestJ7FallbackToCoinAvailableToWithdraw:
    """J7: TAB and acc.ATW absent → use coin.USDT.availableToWithdraw."""

    def test_tab_and_acc_atw_absent_uses_coin_atw(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw="3000.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(3000.0, abs=0.01)

    def test_tab_and_acc_atw_absent_source_is_coin_atw(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw="1500.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd_source == "coin.USDT.availableToWithdraw"

    def test_coin_free_fallback_when_coin_atw_also_absent(self):
        """All account fields absent, coin.ATW absent, coin.free present → uses free."""
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free="800.00",
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(800.0, abs=0.01)
        assert w.available_balance_usd_source == "coin.USDT.free"


# ---------------------------------------------------------------------------
# J8: all candidate fields absent → available_balance_usd=0, source="missing"
# ---------------------------------------------------------------------------

class TestJ8AllCandidatesMissingFailClosed:
    """J8: TAB, acc.ATW, coin.ATW, coin.free all absent → available=0, source=missing."""

    def test_all_absent_available_is_zero(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free=None,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd == pytest.approx(0.0, abs=0.01)

    def test_all_absent_source_is_missing(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free=None,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.available_balance_usd_source == "missing"

    def test_order_endpoint_not_called_when_fields_missing(self):
        client = _real_client()
        resp = _bybit_wallet_resp(
            total_available_balance=None,
            account_available_to_withdraw=None,
            coin_available_to_withdraw=None,
            coin_free=None,
        )
        with patch.object(client, "_get", return_value=resp):
            w = client.get_wallet_balance()
        assert w.order_endpoint_called is False
        assert w.secret_value_observed is False


# ---------------------------------------------------------------------------
# J9: audit mapping_suspect=False when runtime correctly maps to TAB
# ---------------------------------------------------------------------------

class TestJ9AuditMappingSuspectFalse:
    """J9: available_balance_mapping_suspect=False when TAB is used and matches."""

    def test_current_mapping_field_constant_is_tab(self):
        assert CURRENT_MAPPING_FIELD == "account.totalAvailableBalance"

    def test_tab_in_conflict_candidate_fields(self):
        assert "account.totalAvailableBalance" in _CONFLICT_CANDIDATE_FIELDS

    def test_wallet_balance_not_in_conflict_candidate_fields(self):
        assert "coin.USDT.walletBalance" not in _CONFLICT_CANDIDATE_FIELDS

    def test_audit_not_suspect_when_current_matches_tab(self):
        # Only TAB present; coin.USDT.availableToWithdraw and free absent.
        # The audit checks each present candidate against current — with only
        # TAB present and current == TAB, diff=0 → no conflict → not suspect.
        raw = {
            "retCode": 0,
            "result": {"list": [{
                "accountType": "UNIFIED",
                "totalAvailableBalance": "7169.40",
                "coin": [{
                    "coin": "USDT",
                    "equity": "11500.00",
                    "walletBalance": "12000.00",
                }],
            }]},
        }
        result = audit_wallet(
            raw_response=raw,
            current_available_usd=7169.40,
            proof_strength=PROOF_STRONG,
            endpoint_family="bybit_demo",
            account_mode="demo",
            demo_runtime_verified=True,
            equity_usd=11500.0,
            timestamp_utc="2026-06-09T00:00:00Z",
        )
        assert result.available_balance_mapping_suspect is False

    def test_audit_chosen_field_is_tab(self):
        raw = {
            "retCode": 0,
            "result": {"list": [{
                "accountType": "UNIFIED",
                "totalAvailableBalance": "7169.40",
                "coin": [{"coin": "USDT", "equity": "11500.00", "walletBalance": "12000.00"}],
            }]},
        }
        result = audit_wallet(
            raw_response=raw,
            current_available_usd=7169.40,
            proof_strength=PROOF_STRONG,
            endpoint_family="bybit_demo",
            account_mode="demo",
            demo_runtime_verified=True,
            equity_usd=11500.0,
            timestamp_utc="2026-06-09T00:00:00Z",
        )
        assert result.chosen_available_balance_field == "account.totalAvailableBalance"
        assert result.chosen_available_balance_value == pytest.approx(7169.40, abs=0.01)

    def test_audit_still_suspect_when_tab_high_but_current_zero(self):
        """Regression guard: TAB=7169 but current_available=0 → suspect=True (stale mapping)."""
        raw = {
            "retCode": 0,
            "result": {"list": [{
                "accountType": "UNIFIED",
                "totalAvailableBalance": "7169.40",
                "coin": [{"coin": "USDT", "equity": "11500.00", "walletBalance": "12000.00"}],
            }]},
        }
        result = audit_wallet(
            raw_response=raw,
            current_available_usd=0.0,
            proof_strength=PROOF_STRONG,
            endpoint_family="bybit_demo",
            account_mode="demo",
            demo_runtime_verified=True,
            equity_usd=11500.0,
            timestamp_utc="2026-06-09T00:00:00Z",
        )
        assert result.available_balance_mapping_suspect is True

    def test_audit_not_suspect_when_tab_and_current_both_zero(self):
        """Both TAB=0 and current=0 → no conflict, not suspect."""
        raw = {
            "retCode": 0,
            "result": {"list": [{
                "accountType": "UNIFIED",
                "totalAvailableBalance": "0.00",
                "coin": [{"coin": "USDT", "equity": "11500.00", "walletBalance": "12000.00"}],
            }]},
        }
        result = audit_wallet(
            raw_response=raw,
            current_available_usd=0.0,
            proof_strength=PROOF_STRONG,
            endpoint_family="bybit_demo",
            account_mode="demo",
            demo_runtime_verified=True,
            equity_usd=11500.0,
            timestamp_utc="2026-06-09T00:00:00Z",
        )
        assert result.available_balance_mapping_suspect is False


# ---------------------------------------------------------------------------
# J10: new/modified source files contain no embedded API secrets
# ---------------------------------------------------------------------------

class TestJ10NoSecretsInSource:
    """J10: new/modified source files contain no hardcoded secrets."""

    _MODIFIED_FILES = [
        ROOT / "src" / "demo_readonly_client.py",
        ROOT / "src" / "demo_wallet_audit.py",
        ROOT / "scripts" / "preview_demo_readonly_runtime.py",
        ROOT / "scripts" / "preview_demo_wallet_audit.py",
    ]

    _SECRET_TOKENS = [
        "BYBIT_DEMO_API_SECRET=",
        "api_secret=",
        "secret_key=",
    ]

    def test_no_hardcoded_secret_in_modified_files(self):
        for fpath in self._MODIFIED_FILES:
            src = fpath.read_text(encoding="utf-8")
            for token in self._SECRET_TOKENS:
                assert token not in src, (
                    f"Secret token {token!r} found in {fpath.name}"
                )

    def test_secret_value_observed_false_in_fixture_mode(self):
        client = DemoReadOnlyClient(allow_real_network=False)
        w = client.get_wallet_balance()
        assert w.secret_value_observed is False
        assert w.secret_leak_violations == []

    def test_available_balance_source_field_is_not_a_secret_value(self):
        from src.demo_readonly_client import FIXTURE_WALLET
        source = FIXTURE_WALLET.available_balance_usd_source
        assert "secret" not in source.lower()
        assert "key" not in source.lower()
        assert len(source) < 100


# ---------------------------------------------------------------------------
# J11: no order-endpoint tokens in new/modified source files
# ---------------------------------------------------------------------------

class TestJ11NoOrderEndpointTokens:
    """J11: new/modified source files contain no order-placement endpoint tokens."""

    _MODIFIED_FILES = [
        ROOT / "src" / "demo_readonly_client.py",
        ROOT / "src" / "demo_wallet_audit.py",
        ROOT / "scripts" / "preview_demo_readonly_runtime.py",
        ROOT / "scripts" / "preview_demo_wallet_audit.py",
    ]

    _FORBIDDEN = [
        "place_order",
        "create_order",
        "submit_order",
        "cancel_order",
        "private_post",
        "set_leverage",
        "set_trading_stop",
        "transfer(",
    ]

    def test_no_forbidden_order_tokens_in_modified_files(self):
        for fpath in self._MODIFIED_FILES:
            src = fpath.read_text(encoding="utf-8")
            for token in self._FORBIDDEN:
                assert token not in src, (
                    f"Forbidden order token {token!r} found in {fpath.name}"
                )


# ---------------------------------------------------------------------------
# J12: main.py, src/risk.py, BybitExecutor NOT modified by TASK-014J
# ---------------------------------------------------------------------------

class TestJ12ForbiddenFilesUnmodified:
    """J12: main.py, src/risk.py, BybitExecutor do not reference TASK-014J symbols."""

    _TASK_014J_SYMBOLS = [
        "available_balance_usd_source",
        "CURRENT_MAPPING_FIELD",
        "demo_readonly_client",
        "demo_wallet_audit",
    ]

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8") if path.exists() else ""

    def test_main_py_not_modified(self):
        src = self._read(ROOT / "main.py")
        for token in self._TASK_014J_SYMBOLS:
            assert token not in src, f"Token {token!r} found in main.py"

    def test_src_risk_not_modified(self):
        src = self._read(ROOT / "src" / "risk.py")
        for token in self._TASK_014J_SYMBOLS:
            assert token not in src, f"Token {token!r} found in src/risk.py"

    def test_bybit_executor_files_not_modified(self):
        executor_files = (
            list((ROOT / "src").glob("*bybit_executor*"))
            + list((ROOT / "src").glob("*BybitExecutor*"))
        )
        for fpath in executor_files:
            src = fpath.read_text(encoding="utf-8")
            for token in self._TASK_014J_SYMBOLS:
                assert token not in src, (
                    f"Token {token!r} found in {fpath.name}"
                )
