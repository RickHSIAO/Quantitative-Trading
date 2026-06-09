"""
tests/demo_trading/test_demo_wallet_audit.py
TASK-014I: Tests for src/demo_wallet_audit.py and
           scripts/preview_demo_wallet_audit.py

Covers TASK-014I requirements I1-I10:
  I1.  wallet audit parses totalAvailableBalance (account level)
  I2.  wallet audit parses coin-level free if present
  I3.  missing all available fields => fail_closed
  I4.  conflicting fields => mapping_suspect True
  I5.  current available=0 but candidate totalAvailableBalance>0 => mapping_suspect True
  I6.  proof not STRONG => fail_closed
  I7.  endpoint not bybit_demo => fail_closed
  I8.  report / dict output contains no secrets
  I9.  no order endpoint tokens in src/demo_wallet_audit.py source
  I10. main.py / src/risk.py / BybitExecutor not modified / not imported

SAFETY: no real network calls; all tests use injected raw response dicts.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path
from typing import Any

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_wallet_audit import (
    CURRENT_MAPPING_FIELD,
    FIXTURE_WALLET_RAW,
    AvailableBalanceCandidate,
    WalletAuditResult,
    WalletFieldSummary,
    audit_wallet,
    extract_wallet_fields,
)
from src.demo_readonly_client import PROOF_STRONG, PROOF_WEAK, PROOF_MISSING


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_TS = "2026-06-09T10:00:00Z"


def _run_audit(
    raw:           dict[str, Any],
    current_avail: float      = 0.0,
    proof:         str        = PROOF_STRONG,
    endpoint:      str        = "bybit_demo",
    account_mode:  str        = "demo",
    verified:      bool       = True,
    equity:        float      = 11_613.47,
) -> WalletAuditResult:
    return audit_wallet(
        raw_response=raw,
        current_available_usd=current_avail,
        proof_strength=proof,
        endpoint_family=endpoint,
        account_mode=account_mode,
        demo_runtime_verified=verified,
        equity_usd=equity,
        timestamp_utc=_TS,
    )


def _raw_with_tab(tab_value: str = "500.00") -> dict[str, Any]:
    """Raw response where totalAvailableBalance is non-zero."""
    return {
        "retCode": 0, "result": {"list": [{
            "accountType": "UNIFIED",
            "totalEquity": "11613.47",
            "totalWalletBalance": "11500.00",
            "totalMarginBalance": "11613.47",
            "totalAvailableBalance": tab_value,
            "accountIMRate": "0.20",
            "accountMMRate": "0.03",
            "availableToWithdraw": "0.00",
            "coin": [{"coin": "USDT", "equity": "11613.47",
                      "walletBalance": "11500.00", "free": "0.00",
                      "locked": "0.00", "availableToWithdraw": "0.00",
                      "usdValue": "11613.47", "borrowAmount": "0.00",
                      "accruedInterest": "0.00"}],
        }]},
    }


def _raw_all_zero() -> dict[str, Any]:
    return FIXTURE_WALLET_RAW


def _raw_missing_all_avail() -> dict[str, Any]:
    """All available-balance candidate keys absent."""
    return {
        "retCode": 0, "result": {"list": [{
            "accountType": "UNIFIED",
            "totalEquity": "11613.47",
            "totalWalletBalance": "11500.00",
            "totalMarginBalance": "11613.47",
            # totalAvailableBalance absent
            # availableToWithdraw absent
            "accountIMRate": "0.20",
            "accountMMRate": "0.03",
            "coin": [{"coin": "USDT", "equity": "11613.47",
                      "walletBalance": "11500.00",
                      # free absent
                      # availableToWithdraw absent
                      "usdValue": "11613.47"}],
        }]},
    }


def _raw_with_coin_free(free_value: str = "250.00") -> dict[str, Any]:
    return {
        "retCode": 0, "result": {"list": [{
            "accountType": "UNIFIED",
            "totalEquity": "11613.47",
            "totalWalletBalance": "11500.00",
            "totalMarginBalance": "11613.47",
            "totalAvailableBalance": "0.00",
            "availableToWithdraw": "0.00",
            "accountIMRate": "0.20",
            "accountMMRate": "0.03",
            "coin": [{"coin": "USDT", "equity": "11613.47",
                      "walletBalance": "11500.00", "free": free_value,
                      "locked": "0.00", "availableToWithdraw": "0.00",
                      "usdValue": "11613.47", "borrowAmount": "0.00",
                      "accruedInterest": "0.00"}],
        }]},
    }


# ---------------------------------------------------------------------------
# I1. Wallet audit parses totalAvailableBalance
# ---------------------------------------------------------------------------

class TestI1ParsesTotalAvailableBalance:
    """I1: extract_wallet_fields captures account.totalAvailableBalance."""

    def test_parses_positive_value(self):
        raw = _raw_with_tab("500.00")
        fs  = extract_wallet_fields(raw)
        assert fs.total_available_balance == pytest.approx(500.0)
        assert fs.field_missing_total_available_balance is False

    def test_parses_zero_value(self):
        fs = extract_wallet_fields(_raw_all_zero())
        assert fs.total_available_balance == pytest.approx(0.0)
        assert fs.field_missing_total_available_balance is False

    def test_missing_flag_set_when_absent(self):
        fs = extract_wallet_fields(_raw_missing_all_avail())
        assert fs.field_missing_total_available_balance is True
        assert fs.total_available_balance is None

    def test_audit_candidate_list_includes_tab(self):
        result = _run_audit(_raw_with_tab("500.00"))
        names  = [c.field_name for c in result.candidate_available_fields]
        assert "account.totalAvailableBalance" in names

    def test_tab_candidate_has_correct_value(self):
        result = _run_audit(_raw_with_tab("500.00"))
        tab    = next(c for c in result.candidate_available_fields
                      if c.field_name == "account.totalAvailableBalance")
        assert tab.value == pytest.approx(500.0)
        assert tab.present is True


# ---------------------------------------------------------------------------
# I2. Wallet audit parses coin-level free if present
# ---------------------------------------------------------------------------

class TestI2ParsesCoinFree:
    """I2: extract_wallet_fields captures coin.USDT.free when present."""

    def test_parses_positive_free(self):
        raw = _raw_with_coin_free("250.00")
        fs  = extract_wallet_fields(raw)
        assert fs.coin_usdt_free == pytest.approx(250.0)
        assert fs.field_missing_coin_usdt_free is False

    def test_parses_zero_free(self):
        fs = extract_wallet_fields(_raw_all_zero())
        assert fs.coin_usdt_free == pytest.approx(0.0)
        assert fs.field_missing_coin_usdt_free is False

    def test_missing_flag_when_free_absent(self):
        fs = extract_wallet_fields(_raw_missing_all_avail())
        assert fs.field_missing_coin_usdt_free is True
        assert fs.coin_usdt_free is None

    def test_candidate_list_includes_coin_free(self):
        result = _run_audit(_raw_with_coin_free("250.00"))
        names  = [c.field_name for c in result.candidate_available_fields]
        assert "coin.USDT.free" in names


# ---------------------------------------------------------------------------
# I3. Missing all available fields => fail_closed
# ---------------------------------------------------------------------------

class TestI3MissingAllFieldsFailClosed:
    """I3: when all 5 candidate available-balance fields are absent, fail_closed=True."""

    def test_all_missing_sets_fail_closed(self):
        result = _run_audit(_raw_missing_all_avail(), current_avail=0.0)
        assert result.fail_closed is True

    def test_all_missing_fail_reason_set(self):
        result = _run_audit(_raw_missing_all_avail(), current_avail=0.0)
        assert result.fail_reason != ""

    def test_all_missing_new_entry_allowed_still_false(self):
        result = _run_audit(_raw_missing_all_avail(), current_avail=0.0)
        assert result.new_entry_allowed is False


# ---------------------------------------------------------------------------
# I4. Conflicting fields => mapping_suspect True
# ---------------------------------------------------------------------------

class TestI4ConflictingFieldsMappingSuspect:
    """I4: when any present candidate differs from current by >threshold, mapping_suspect=True."""

    def test_conflict_sets_suspect(self):
        # totalAvailableBalance = 500, but current is 0 => differ by 500 > 10
        result = _run_audit(_raw_with_tab("500.00"), current_avail=0.0)
        assert result.available_balance_mapping_suspect is True

    def test_no_conflict_when_all_zero(self):
        result = _run_audit(_raw_all_zero(), current_avail=0.0)
        assert result.available_balance_mapping_suspect is False

    def test_mismatch_warning_set_on_conflict(self):
        result = _run_audit(_raw_with_tab("500.00"), current_avail=0.0)
        assert result.mismatch_warning != ""

    def test_no_mismatch_warning_when_agree(self):
        result = _run_audit(_raw_all_zero(), current_avail=0.0)
        assert result.mismatch_warning == ""


# ---------------------------------------------------------------------------
# I5. current=0 but totalAvailableBalance>0 => mapping_suspect True
# ---------------------------------------------------------------------------

class TestI5CurrentZeroButBetterCandidateExists:
    """I5: specifically the bug scenario: current mapping shows 0 but TAB > 0."""

    def test_tab_positive_current_zero_is_suspect(self):
        result = _run_audit(_raw_with_tab("500.00"), current_avail=0.0)
        assert result.available_balance_mapping_suspect is True

    def test_chosen_field_is_tab_when_available(self):
        result = _run_audit(_raw_with_tab("500.00"), current_avail=0.0)
        # account.totalAvailableBalance is first in priority order
        assert result.chosen_available_balance_field == "account.totalAvailableBalance"
        assert result.chosen_available_balance_value == pytest.approx(500.0)

    def test_recommended_action_mentions_chosen_field(self):
        result = _run_audit(_raw_with_tab("500.00"), current_avail=0.0)
        assert "account.totalAvailableBalance" in result.recommended_next_action

    def test_current_zero_all_candidates_zero_not_suspect(self):
        result = _run_audit(_raw_all_zero(), current_avail=0.0)
        assert result.available_balance_mapping_suspect is False
        assert "genuine" in result.recommended_next_action.lower() or \
               "zero" in result.recommended_next_action.lower() or \
               "agree" in result.recommended_next_action.lower()


# ---------------------------------------------------------------------------
# I6. Proof not STRONG => fail_closed
# ---------------------------------------------------------------------------

class TestI6ProofNotStrongFailClosed:
    """I6: non-STRONG proof => fail_closed=True."""

    def test_proof_weak_fails_closed(self):
        result = _run_audit(_raw_all_zero(), proof=PROOF_WEAK)
        assert result.fail_closed is True

    def test_proof_missing_fails_closed(self):
        result = _run_audit(_raw_all_zero(), proof=PROOF_MISSING)
        assert result.fail_closed is True

    def test_proof_strong_does_not_fail_closed_by_proof(self):
        result = _run_audit(_raw_all_zero(), proof=PROOF_STRONG)
        # May still fail for other reasons, but not proof
        if result.fail_closed:
            assert "proof" not in result.fail_reason.lower()

    def test_fail_reason_mentions_proof_when_weak(self):
        result = _run_audit(_raw_all_zero(), proof=PROOF_WEAK)
        assert "proof" in result.fail_reason.lower() or "WEAK" in result.fail_reason


# ---------------------------------------------------------------------------
# I7. Endpoint not bybit_demo => fail_closed
# ---------------------------------------------------------------------------

class TestI7EndpointNotBybytDemoFailClosed:
    """I7: endpoint_family != bybit_demo => fail_closed=True."""

    def test_unknown_endpoint_fails_closed(self):
        result = _run_audit(_raw_all_zero(), endpoint="unknown")
        assert result.fail_closed is True

    def test_live_endpoint_fails_closed(self):
        result = _run_audit(_raw_all_zero(), endpoint="bybit_live")
        assert result.fail_closed is True

    def test_bybit_demo_does_not_fail_from_endpoint(self):
        result = _run_audit(_raw_all_zero(), endpoint="bybit_demo")
        if result.fail_closed:
            assert "endpoint" not in result.fail_reason.lower()

    def test_fail_reason_mentions_endpoint_when_wrong(self):
        result = _run_audit(_raw_all_zero(), endpoint="bybit_live")
        assert "endpoint" in result.fail_reason.lower()


# ---------------------------------------------------------------------------
# I8. Report / dict output contains no secrets
# ---------------------------------------------------------------------------

class TestI8NoSecretsInReport:
    """I8: to_dict() and JSON report never contain secret-shaped strings."""

    _FORBIDDEN = ("X-BAPI-SIGN", "BYBIT_DEMO_API_SECRET")

    def test_audit_dict_no_secrets(self):
        result = _run_audit(_raw_all_zero())
        txt    = json.dumps(result.to_dict())
        for tok in self._FORBIDDEN:
            assert tok not in txt

    def test_field_summary_dict_no_secrets(self):
        raw = _raw_all_zero()
        fs  = extract_wallet_fields(raw)
        txt = json.dumps(fs.to_dict())
        for tok in self._FORBIDDEN:
            assert tok not in txt

    def test_run_preview_report_no_secrets(self, monkeypatch):
        import scripts.preview_demo_wallet_audit as mod
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "wallet_audit"
            monkeypatch.setattr(mod, "_OUTPUT_DIR", out_dir, raising=True)
            mod.run_preview(use_real_network=False, write_report=True,
                            output_dir=out_dir)
            jp = out_dir / "latest_wallet_audit.json"
            mp = out_dir / "latest_wallet_audit.md"
            for path in (jp, mp):
                if path.exists():
                    txt = path.read_text(encoding="utf-8")
                    for tok in self._FORBIDDEN:
                        assert tok not in txt, f"{tok!r} found in {path.name}"

    def test_safety_invariants_always_set(self):
        result = _run_audit(_raw_all_zero())
        assert result.no_orders_sent is True
        assert result.order_endpoint_called is False
        assert result.secret_value_observed is False
        assert result.new_entry_allowed is False


# ---------------------------------------------------------------------------
# I9. No order endpoint tokens in src/demo_wallet_audit.py source
# ---------------------------------------------------------------------------

class TestI9NoOrderEndpointTokensInSource:
    """I9: source file must not contain order submission tokens."""

    _SRC    = ROOT / "src" / "demo_wallet_audit.py"
    _SCRIPT = ROOT / "scripts" / "preview_demo_wallet_audit.py"

    def _read(self, p: Path) -> str:
        return p.read_text(encoding="utf-8")

    def test_no_place_order(self):
        for p in (self._SRC, self._SCRIPT):
            assert "place_order" not in self._read(p), p.name

    def test_no_create_order(self):
        for p in (self._SRC, self._SCRIPT):
            assert "create_order" not in self._read(p), p.name

    def test_no_submit_order(self):
        for p in (self._SRC, self._SCRIPT):
            assert "submit_order" not in self._read(p), p.name

    def test_no_v5_order_create(self):
        for p in (self._SRC, self._SCRIPT):
            assert "/v5/order/create" not in self._read(p), p.name

    def test_no_live_hostname(self):
        # api.bybit.com (live endpoint) must not appear as a request target
        for p in (self._SRC, self._SCRIPT):
            src = self._read(p)
            assert "api.bybit.com" not in src or "_LIVE_HOSTNAME" in src, p.name


# ---------------------------------------------------------------------------
# I10. main.py / src/risk.py / BybitExecutor not modified / not imported
# ---------------------------------------------------------------------------

class TestI10UntouchedFiles:
    """I10: TASK-014I scope must not touch main.py, src/risk.py, or BybitExecutor."""

    _TASK_FILES = [
        "src/demo_wallet_audit.py",
        "scripts/preview_demo_wallet_audit.py",
    ]

    def test_main_not_imported(self):
        for rel in self._TASK_FILES:
            txt = (ROOT / rel).read_text(encoding="utf-8")
            assert "from main" not in txt
            assert "import main" not in txt

    def test_risk_not_imported(self):
        for rel in self._TASK_FILES:
            txt = (ROOT / rel).read_text(encoding="utf-8")
            assert "from src.risk" not in txt
            assert "import src.risk" not in txt

    def test_bybit_executor_not_imported(self):
        for rel in self._TASK_FILES:
            txt = (ROOT / rel).read_text(encoding="utf-8")
            assert "BybitExecutor" not in txt
            assert "from src.exchange" not in txt


# ---------------------------------------------------------------------------
# Integration: run_preview fixture mode returns 0 and writes report
# ---------------------------------------------------------------------------

class TestRunPreviewFixtureMode:
    """Integration: fixture mode produces a valid report without network calls."""

    def test_run_preview_exits_zero(self, monkeypatch):
        import scripts.preview_demo_wallet_audit as mod
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "wallet_audit"
            rc = mod.run_preview(
                use_real_network=False,
                write_report=True,
                output_dir=out_dir,
            )
        assert rc == 0

    def test_run_preview_writes_json(self, monkeypatch):
        import scripts.preview_demo_wallet_audit as mod
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "wallet_audit"
            mod.run_preview(
                use_real_network=False,
                write_report=True,
                output_dir=out_dir,
            )
            jp = out_dir / "latest_wallet_audit.json"
            assert jp.exists()

    def test_run_preview_json_has_required_keys(self, monkeypatch):
        import scripts.preview_demo_wallet_audit as mod
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "wallet_audit"
            mod.run_preview(
                use_real_network=False,
                write_report=True,
                output_dir=out_dir,
            )
            data = json.loads((out_dir / "latest_wallet_audit.json").read_text(encoding="utf-8"))
        for key in (
            "timestamp_utc", "demo_runtime_verified", "proof_strength",
            "endpoint_family", "equity_usd", "current_available_balance_usd",
            "raw_wallet_field_summary", "candidate_available_fields",
            "chosen_available_balance_field", "chosen_available_balance_value",
            "available_balance_mapping_suspect", "recommended_next_action",
            "no_orders_sent", "order_endpoint_called", "secret_value_observed",
            "new_entry_allowed",
        ):
            assert key in data, f"missing key: {key}"

    def test_fixture_no_orders_sent(self, monkeypatch):
        import scripts.preview_demo_wallet_audit as mod
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "wallet_audit"
            mod.run_preview(
                use_real_network=False,
                write_report=True,
                output_dir=out_dir,
            )
            data = json.loads((out_dir / "latest_wallet_audit.json").read_text(encoding="utf-8"))
        assert data["no_orders_sent"] is True
        assert data["order_endpoint_called"] is False
        assert data["new_entry_allowed"] is False

    def test_fixture_has_five_candidates(self, monkeypatch):
        import scripts.preview_demo_wallet_audit as mod
        with tempfile.TemporaryDirectory() as tmp:
            out_dir = Path(tmp) / "wallet_audit"
            mod.run_preview(
                use_real_network=False,
                write_report=True,
                output_dir=out_dir,
            )
            data = json.loads((out_dir / "latest_wallet_audit.json").read_text(encoding="utf-8"))
        assert len(data["candidate_available_fields"]) == 5
