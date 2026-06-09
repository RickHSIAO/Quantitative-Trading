"""
tests/demo_trading/test_demo_new_entry_sender.py
TASK-014L: Tests for src/demo_new_entry_sender.py and
           scripts/execute_demo_new_entry.py

Covers TASK-014L requirements F1-F25:
  F1.  dry-run default does not send
  F2.  missing review file => fail closed
  F3.  missing confirm token => fail closed
  F4.  wrong / yesterday confirm token => fail closed
  F5.  invalid token format => fail closed
  F6.  missing --symbol => fail closed (CLI)
  F7.  symbol not in accepted_candidates => fail closed
  F8.  review.fail_closed=True => fail closed
  F9.  proof_strength != STRONG => fail closed
  F10. endpoint_family != bybit_demo => fail closed
  F11. account_mode != demo => fail closed
  F12. position_details_source != real_readonly => fail closed
  F13. new_entry_allowed_from_reconciliation=False => fail closed
  F14. available_balance_usd <= 0 => fail closed
  F15. open_positions_count >= 10 => fail closed
  F16. short candidate selected => fail closed (short_new_entry_not_permitted)
  F17. payload.reduce_only=True => fail closed (new entry must be False)
  F18. payload.preview_only=False => fail closed
  F19. payload.order_sent=True / order_endpoint_called=True => fail closed
  F20. payload qty <= 0 / invalid order_side => fail closed
  F21. long capacity full (max_long_allowed_remaining=0) => fail closed
  F22. order_side mismatch vs side label => fail closed
  F23. pre-send refresh: target symbol already open / live capacity full
  F24. pre-send refresh: proof not strong / balance non-positive
  F25. successful order submission (mocked) — order_id set, no secrets,
       no_position_modified=False; failed order — no secrets, position unmodified
  + source scan: no live hostname, no leverage, no TP/SL, no transfer,
       no /v5/order/create-batch, no close-only sender imports
  + invariants: no_live_endpoint=True, no_batch_order=True, no_close_only_path=True,
       reduce_only=False, secret_value_observed=False

SAFETY: no real network calls; mocks used for pre-send refresh and order POST.
"""
from __future__ import annotations

import ast
import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_instrument_rules import InstrumentRules
from src.demo_new_entry_review import (
    NewEntryCandidate,
    review_new_entry_candidates,
)
from src.demo_new_entry_sender import (
    CONFIRM_TOKEN_PREFIX,
    DemoNewEntrySender,
    NewEntryOrderResult,
    _expected_token,
    _ORDER_ENDPOINT,
)
from src.demo_portfolio_risk import DemoOpenPosition
from src.demo_position_reconcile import reconcile
from src.demo_readonly_client import (
    DEMO_BASE_URL,
    PROOF_MISSING,
    PROOF_STRONG,
    PROOF_WEAK,
    DemoReadOnlyClient,
    PositionSnapshot,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RULES: dict[str, InstrumentRules] = {
    "BTCUSDT":  InstrumentRules("BTCUSDT",  0.001, 0.001, 0,  0.1,    1.0, 1, 3),
    "ETHUSDT":  InstrumentRules("ETHUSDT",  0.01,  0.01,  0,  0.05,   1.0, 2, 2),
    "BNBUSDT":  InstrumentRules("BNBUSDT",  0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "SOLUSDT":  InstrumentRules("SOLUSDT",  0.1,   0.1,   0,  0.01,   1.0, 2, 1),
    "AAVEUSDT": InstrumentRules("AAVEUSDT", 0.01,  0.01,  0,  0.01,   1.0, 2, 2),
    "AVAXUSDT": InstrumentRules("AVAXUSDT", 0.1,   0.1,   0,  0.01,   1.0, 2, 1),
    "LINKUSDT": InstrumentRules("LINKUSDT", 0.1,   0.1,   0,  0.001,  1.0, 3, 1),
    "XRPUSDT":  InstrumentRules("XRPUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "ADAUSDT":  InstrumentRules("ADAUSDT",  1.0,   1.0,   0,  0.0001, 1.0, 4, 0),
    "DOTUSDT":  InstrumentRules("DOTUSDT",  0.1,   0.1,   0,  0.001,  1.0, 3, 1),
}


def _full_short_positions() -> list[DemoOpenPosition]:
    """5 shorts — production-like state.  short_count=5/5, long_count=0/5."""
    return [
        DemoOpenPosition("ETHUSDT", "short", 0.10, 3_500.0, 3_700.0),
        DemoOpenPosition("BNBUSDT", "short", 0.50,   600.0,   640.0),
        DemoOpenPosition("SOLUSDT", "short", 1.00,   160.0,   175.0),
        DemoOpenPosition("XRPUSDT", "short", 100.0,    0.62,    0.68),
        DemoOpenPosition("ADAUSDT", "short", 200.0,    0.45,    0.49),
    ]


def _good_long(symbol: str = "AAVEUSDT") -> NewEntryCandidate:
    """Long candidate that should be accepted in the production-like state."""
    return NewEntryCandidate(
        symbol=symbol, side="long",
        entry_reference_price=120.0, stop_price=110.0,
        requested_risk_usd=30.0, score=1.0,
    )


def _good_short(symbol: str = "LINKUSDT") -> NewEntryCandidate:
    return NewEntryCandidate(
        symbol=symbol, side="short",
        entry_reference_price=14.5, stop_price=16.0,
        requested_risk_usd=20.0, score=0.8,
    )


def _build_review(
    candidates:               list[NewEntryCandidate] | None = None,
    positions:                list[DemoOpenPosition]  | None = None,
    equity_usd:               float = 11_560.91,
    available_balance_usd:    float = 7_048.86,
    demo_runtime_verified:    bool  = True,
    proof_strength:           str   = PROOF_STRONG,
    position_details_source:  str   = "real_readonly",
    endpoint_family:          str   = "bybit_demo",
    account_mode:             str   = "demo",
    available_balance_source: str   = "account.totalAvailableBalance",
    timestamp_utc:            str   = "2026-06-09T12:00:00Z",
    realtime_price_guard_verified: bool = True,
) -> dict[str, Any]:
    """Build a valid review dict via review_new_entry_candidates(...).to_dict()."""
    rec = reconcile(
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        positions=positions if positions is not None else _full_short_positions(),
        instrument_rules=_RULES,
        full_kelly_fraction=0.60,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        mode="real_readonly_snapshot",
        position_details_source=position_details_source,
    )
    cands = candidates if candidates is not None else [_good_long()]
    review = review_new_entry_candidates(
        reconciliation=rec,
        candidates=cands,
        instrument_rules=_RULES,
        endpoint_family=endpoint_family,
        account_mode=account_mode,
        available_balance_usd_source=available_balance_source,
    )
    d = review.to_dict(timestamp_utc=timestamp_utc)
    # TASK-014M: real-time price guard — explicitly assert that the preview's
    # entry_reference_price was sourced from a live market reading.
    d["realtime_price_guard_verified"] = realtime_price_guard_verified
    return d


def _valid_token(now: datetime | None = None) -> str:
    return _expected_token(now)


def _fixed_now() -> datetime:
    """Stable UTC timestamp for deterministic token equality tests."""
    return datetime(2026, 6, 9, 12, 0, 0, tzinfo=timezone.utc)


def _token_for(now: datetime) -> str:
    return _expected_token(now)


def _mock_ro_client(
    proof_strength:          str  = PROOF_STRONG,
    endpoint_family:         str  = "bybit_demo",
    account_mode:            str  = "demo",
    available_balance_usd:   float = 6_968.07,
    available_balance_source: str = "account.totalAvailableBalance",
    positions:               list[PositionSnapshot] | None = None,
) -> DemoReadOnlyClient:
    """Return a MagicMock DemoReadOnlyClient for pre-send refresh tests."""
    mock_client = MagicMock(spec=DemoReadOnlyClient)

    mock_proof                                = MagicMock()
    mock_proof.proof_strength                 = proof_strength
    mock_proof.endpoint_family                = endpoint_family
    mock_proof.account_mode                   = account_mode
    mock_proof.live_endpoint_fallback_detected = False
    mock_client.build_runtime_proof.return_value = mock_proof

    mock_wallet                                  = MagicMock()
    mock_wallet.available_balance_usd            = available_balance_usd
    mock_wallet.available_balance_usd_source     = available_balance_source
    mock_wallet.equity_usd                       = available_balance_usd + 4_000.0
    mock_client.get_wallet_balance.return_value  = mock_wallet

    if positions is None:
        # Default: production-like 5-short layout (matches review fixture)
        positions = [
            PositionSnapshot("ETHUSDT", "short", 0.10, 3_500.0, 3_700.0, 0.0, 3.0),
            PositionSnapshot("BNBUSDT", "short", 0.50,   600.0,   640.0, 0.0, 3.0),
            PositionSnapshot("SOLUSDT", "short", 1.00,   160.0,   175.0, 0.0, 3.0),
            PositionSnapshot("XRPUSDT", "short", 100.0,    0.62,    0.68, 0.0, 3.0),
            PositionSnapshot("ADAUSDT", "short", 200.0,    0.45,    0.49, 0.0, 3.0),
        ]
    mock_client.get_open_positions.return_value = positions
    return mock_client


def _write_review_to_dir(tmpdir: str, review: dict | None = None) -> Path:
    d = Path(tmpdir)
    content = review if review is not None else _build_review()
    (d / "latest_new_entry_review.json").write_text(
        json.dumps(content), encoding="utf-8"
    )
    return d


def _accepted_symbol(review: dict) -> str:
    """Return the first accepted candidate's symbol, or '' if none."""
    accepted = review.get("accepted_candidates", []) or []
    if not accepted:
        return ""
    return str(accepted[0].get("symbol", ""))


# ---------------------------------------------------------------------------
# Sanity prerequisites
# ---------------------------------------------------------------------------

class TestFixtureSanity:
    """Verify the fixture builder produces a review with at least one accepted long."""

    def test_default_review_has_accepted_long(self):
        review = _build_review()
        assert review["fail_closed"] is False
        assert _accepted_symbol(review), "Fixture must yield at least one accepted long"

    def test_default_review_short_capacity_full(self):
        review = _build_review()
        assert review["short_count"] == 5
        assert review["max_short_allowed_remaining"] == 0


# ---------------------------------------------------------------------------
# F1. Dry-run default does not send
# ---------------------------------------------------------------------------

class TestF1DryRunDefault:
    def _result(self) -> NewEntryOrderResult:
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        sender = DemoNewEntrySender()
        return sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=False, _now=now,
        )

    def test_order_not_sent(self):
        assert self._result().order_sent is False

    def test_order_endpoint_called_false(self):
        assert self._result().order_endpoint_called is False

    def test_no_position_modified(self):
        assert self._result().no_position_modified is True

    def test_execute_allowed_true_when_gates_pass(self):
        assert self._result().execute_allowed is True

    def test_mode_dry_run(self):
        assert self._result().mode == "dry_run"


# ---------------------------------------------------------------------------
# F2. Missing review file => fail closed
# ---------------------------------------------------------------------------

class TestF2MissingReviewFile:
    def test_missing_file_cli_exits_one(self):
        from scripts.execute_demo_new_entry import run_execute
        token = _valid_token()
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = run_execute(
                symbol="SOLUSDT", confirm_token=token,
                review_dir=Path(tmpdir),
            )
        assert rc == 1

    def test_missing_file_prints_fail_message(self, capsys):
        from scripts.execute_demo_new_entry import run_execute
        token = _valid_token()
        with tempfile.TemporaryDirectory() as tmpdir:
            run_execute(
                symbol="SOLUSDT", confirm_token=token,
                review_dir=Path(tmpdir),
            )
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out or "not found" in out

    def test_load_latest_review_returns_none_when_missing(self):
        from scripts.execute_demo_new_entry import load_latest_review
        with tempfile.TemporaryDirectory() as tmpdir:
            assert load_latest_review(Path(tmpdir)) is None


# ---------------------------------------------------------------------------
# F3. Missing confirm token => fail closed
# ---------------------------------------------------------------------------

class TestF3MissingConfirmToken:
    def test_empty_token_sender_blocks(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token="",
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "missing_confirm_token" in r.blocked_gates
        assert r.order_sent is False
        assert r.execute_allowed is False

    def test_empty_token_cli_exits_one(self):
        from scripts.execute_demo_new_entry import run_execute
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_review_to_dir(tmpdir)
            rc = run_execute(
                symbol="AAVEUSDT", confirm_token="",
                review_dir=d,
            )
        assert rc == 1


# ---------------------------------------------------------------------------
# F4. Wrong / yesterday token => fail closed
# ---------------------------------------------------------------------------

class TestF4WrongOrYesterdayToken:
    def test_yesterday_token_blocked(self):
        now       = _fixed_now()
        yesterday = now - timedelta(days=1)
        review    = _build_review()
        symbol    = _accepted_symbol(review)
        sender    = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_token_for(yesterday),
            execute_new_entry=False, _now=now,
        )
        assert "confirm_token_date_mismatch" in r.blocked_gates

    def test_tomorrow_token_blocked(self):
        now      = _fixed_now()
        tomorrow = now + timedelta(days=1)
        review   = _build_review()
        symbol   = _accepted_symbol(review)
        sender   = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_token_for(tomorrow),
            execute_new_entry=False, _now=now,
        )
        assert "confirm_token_date_mismatch" in r.blocked_gates


# ---------------------------------------------------------------------------
# F5. Invalid token format => fail closed
# ---------------------------------------------------------------------------

class TestF5InvalidTokenFormat:
    @pytest.mark.parametrize("bad_token", [
        "WRONG_TOKEN_12345",
        "CONFIRM_DEMO_NEW_ENTRY_",        # missing date
        "CONFIRM_DEMO_NEW_ENTRY_abcd",    # non-numeric
        "CONFIRM_DEMO_NEW_ENTRY_2026060",  # 7 digits
        "CONFIRM_DEMO_NEW_ENTRY_202606099",  # 9 digits
        "CONFIRM_DEMO_CLOSE_ONLY_20260609",  # close-only token
        " CONFIRM_DEMO_NEW_ENTRY_20260609",  # leading space
    ])
    def test_invalid_format_blocked(self, bad_token):
        review = _build_review()
        symbol = _accepted_symbol(review)
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=bad_token,
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "invalid_confirm_token_format" in r.blocked_gates or \
               "confirm_token_date_mismatch" in r.blocked_gates
        assert r.order_sent is False

    def test_token_prefix_constant(self):
        assert CONFIRM_TOKEN_PREFIX == "CONFIRM_DEMO_NEW_ENTRY_"


# ---------------------------------------------------------------------------
# F6. Missing --symbol => fail closed
# ---------------------------------------------------------------------------

class TestF6MissingSymbol:
    def test_cli_missing_symbol_exits_one(self):
        from scripts.execute_demo_new_entry import run_execute
        token = _valid_token()
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_review_to_dir(tmpdir)
            rc = run_execute(symbol="", confirm_token=token, review_dir=d)
        assert rc == 1

    def test_cli_missing_symbol_prints_fail_message(self, capsys):
        from scripts.execute_demo_new_entry import run_execute
        token = _valid_token()
        with tempfile.TemporaryDirectory() as tmpdir:
            d = _write_review_to_dir(tmpdir)
            run_execute(symbol="", confirm_token=token, review_dir=d)
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out
        assert "--symbol" in out or "symbol" in out.lower()

    def test_sender_missing_symbol_blocked(self):
        review = _build_review()
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="", confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "missing_symbol" in r.blocked_gates


# ---------------------------------------------------------------------------
# F7. Symbol not in accepted_candidates => fail closed
# ---------------------------------------------------------------------------

class TestF7SymbolNotInAccepted:
    def test_nonexistent_symbol_blocked(self):
        review = _build_review()
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="NONEXISTENT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "symbol_not_in_accepted_candidates" in r.blocked_gates

    def test_rejected_short_symbol_blocked(self):
        # AVAXUSDT short candidate is rejected (short_capacity_full).
        review = _build_review(candidates=[
            _good_long("AAVEUSDT"),
            _good_short("AVAXUSDT"),
        ])
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AVAXUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "symbol_not_in_accepted_candidates" in r.blocked_gates


# ---------------------------------------------------------------------------
# F8. review.fail_closed=True => fail closed
# ---------------------------------------------------------------------------

class TestF8ReviewFailClosed:
    def test_fail_closed_review_blocked(self):
        review = _build_review()
        review["fail_closed"] = True
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "review_fail_closed" in r.blocked_gates
        assert r.order_sent is False


# ---------------------------------------------------------------------------
# F9. proof_strength != STRONG => fail closed
# ---------------------------------------------------------------------------

class TestF9ProofNotStrong:
    @pytest.mark.parametrize("proof", [PROOF_WEAK, PROOF_MISSING, "", "strong"])
    def test_non_strong_proof_blocked(self, proof):
        review = _build_review()
        review["proof_strength"] = proof
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "proof_not_strong" in r.blocked_gates
        assert r.order_sent is False


# ---------------------------------------------------------------------------
# F10. endpoint_family != bybit_demo => fail closed
# ---------------------------------------------------------------------------

class TestF10EndpointFamily:
    @pytest.mark.parametrize("ep", ["bybit_live", "bybit_testnet", "", "demo"])
    def test_non_demo_endpoint_blocked(self, ep):
        review = _build_review()
        review["endpoint_family"] = ep
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "endpoint_family_not_bybit_demo" in r.blocked_gates


# ---------------------------------------------------------------------------
# F11. account_mode != demo => fail closed
# ---------------------------------------------------------------------------

class TestF11AccountMode:
    @pytest.mark.parametrize("mode", ["live", "testnet", "unknown", ""])
    def test_non_demo_account_mode_blocked(self, mode):
        review = _build_review()
        review["account_mode"] = mode
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "account_mode_not_demo" in r.blocked_gates


# ---------------------------------------------------------------------------
# F12. position_details_source != real_readonly => fail closed
# ---------------------------------------------------------------------------

class TestF12PositionDetailsSource:
    @pytest.mark.parametrize("src", ["fixture", "fixture_from_smoke", "", "unknown"])
    def test_non_real_source_blocked(self, src):
        review = _build_review()
        review["position_details_source"] = src
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "position_details_source_not_real_readonly" in r.blocked_gates


# ---------------------------------------------------------------------------
# F13. new_entry_allowed_from_reconciliation=False => fail closed
# ---------------------------------------------------------------------------

class TestF13NewEntryNotAllowed:
    def test_not_allowed_blocked(self):
        review = _build_review()
        review["new_entry_allowed_from_reconciliation"] = False
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "new_entry_not_allowed_from_reconciliation" in r.blocked_gates


# ---------------------------------------------------------------------------
# F14. available_balance_usd <= 0 => fail closed
# ---------------------------------------------------------------------------

class TestF14AvailableBalance:
    @pytest.mark.parametrize("bal", [0.0, -1.0, -100.0])
    def test_non_positive_balance_blocked(self, bal):
        review = _build_review()
        review["available_balance_usd"] = bal
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "available_balance_zero_or_negative" in r.blocked_gates


# ---------------------------------------------------------------------------
# F15. open_positions_count >= 10 => fail closed
# ---------------------------------------------------------------------------

class TestF15OpenPositionsFull:
    def test_open_positions_at_cap_blocked(self):
        review = _build_review()
        review["open_positions_count"] = 10
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "open_positions_full" in r.blocked_gates

    def test_open_positions_over_cap_blocked(self):
        review = _build_review()
        review["open_positions_count"] = 12
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AAVEUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "open_positions_full" in r.blocked_gates


# ---------------------------------------------------------------------------
# F16. short candidate selected => short_new_entry_not_permitted
# ---------------------------------------------------------------------------

class TestF16ShortNotPermitted:
    def test_short_in_accepted_still_blocked(self):
        """Even if a short shows up in accepted_candidates (e.g., a stale
        review file), the sender blocks short new-entries at the static gate."""
        review = _build_review()
        # Forge a short evaluation as accepted (defensive scenario)
        forged_short = {
            "symbol": "AVAXUSDT", "side": "short", "accepted": True,
            "reject_reason": "",
            "detail": {},
            "payload": {
                "symbol": "AVAXUSDT", "side": "Sell", "order_type": "Market",
                "qty": 1.0, "reduce_only": False, "preview_only": True,
                "entry_reference_price": 30.0, "rounded_entry_price": 30.0,
                "stop_price": 33.0, "rounded_stop_price": 33.0,
                "estimated_notional_usd": 30.0, "estimated_stop_risk_usd": 3.0,
                "portfolio_risk_budget_usd": 100.0,
                "remaining_risk_budget_before": 100.0,
                "remaining_risk_budget_after":  97.0,
                "projected_open_positions_count": 6,
                "projected_long_count": 0, "projected_short_count": 6,
                "projected_gross_exposure_ratio": 0.1,
                "projected_net_exposure_ratio": -0.1,
                "confirmation_required": True,
                "order_sent": False, "order_endpoint_called": False,
            },
        }
        review["accepted_candidates"].append(forged_short)
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol="AVAXUSDT",
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "short_new_entry_not_permitted" in r.blocked_gates
        assert r.order_sent is False


# ---------------------------------------------------------------------------
# F17. payload.reduce_only=True => fail closed
# ---------------------------------------------------------------------------

class TestF17ReduceOnlyMustBeFalse:
    def test_reduce_only_true_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                ev["payload"]["reduce_only"] = True
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "payload_reduce_only_must_be_false" in r.blocked_gates


# ---------------------------------------------------------------------------
# F18. payload.preview_only=False => fail closed
# ---------------------------------------------------------------------------

class TestF18PreviewOnlyMustBeTrue:
    def test_preview_only_false_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                ev["payload"]["preview_only"] = False
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "payload_preview_only_must_be_true" in r.blocked_gates


# ---------------------------------------------------------------------------
# F19. payload.order_sent=True / order_endpoint_called=True => fail closed
# ---------------------------------------------------------------------------

class TestF19PayloadOrderFlagsMustBeFalse:
    def test_order_sent_true_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                ev["payload"]["order_sent"] = True
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "payload_order_sent_must_be_false" in r.blocked_gates

    def test_order_endpoint_called_true_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                ev["payload"]["order_endpoint_called"] = True
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "payload_order_endpoint_called_must_be_false" in r.blocked_gates


# ---------------------------------------------------------------------------
# F20. payload qty <= 0 / invalid order_side / order_type != Market
# ---------------------------------------------------------------------------

class TestF20InvalidPayload:
    def test_zero_qty_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                ev["payload"]["qty"] = 0.0
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "invalid_qty_not_positive" in r.blocked_gates

    def test_invalid_order_side_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                ev["payload"]["side"] = "InvalidSide"
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "invalid_order_side_in_payload" in r.blocked_gates

    def test_non_market_order_type_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                ev["payload"]["order_type"] = "Limit"
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "payload_order_type_not_market" in r.blocked_gates


# ---------------------------------------------------------------------------
# F21. Long capacity full => fail closed
# ---------------------------------------------------------------------------

class TestF21LongCapacityFull:
    def test_max_long_remaining_zero_blocked(self):
        review = _build_review()
        review["max_long_allowed_remaining"] = 0
        symbol = _accepted_symbol(review)
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "long_capacity_full" in r.blocked_gates


# ---------------------------------------------------------------------------
# F22. order_side mismatch vs side label
# ---------------------------------------------------------------------------

class TestF22OrderSideMismatch:
    def test_long_with_sell_side_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        for ev in review["accepted_candidates"]:
            if ev["symbol"] == symbol and ev.get("payload"):
                # evaluation side is "long" but payload side becomes "Sell"
                ev["payload"]["side"] = "Sell"
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert "order_side_mismatch_vs_side_label" in r.blocked_gates


# ---------------------------------------------------------------------------
# F23. Pre-send refresh: target already open / live capacity full
# ---------------------------------------------------------------------------

class TestF23PreSendRefresh:
    def _sender_with_creds(self) -> DemoNewEntrySender:
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "test_key_f23"
        sender._api_secret = "test_secret_f23"
        sender._key_present    = True
        sender._secret_present = True
        return sender

    def test_target_symbol_already_open_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)

        # Live positions include the target symbol — must block
        live_positions = [
            PositionSnapshot(symbol, "long", 1.0, 100.0, 90.0, 0.0, 3.0),
        ]
        ro = _mock_ro_client(positions=live_positions)
        sender = self._sender_with_creds()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert "refresh_target_symbol_already_open" in r.blocked_gates
        assert r.order_sent is False
        assert r.order_endpoint_called is False

    def test_live_long_capacity_full_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)

        # 5 longs in live positions — long capacity full
        live_positions = [
            PositionSnapshot("BTCUSDT", "long", 0.01, 67000.0, 65000.0, 0.0, 3.0),
            PositionSnapshot("ETHUSDT", "long", 0.10,  3500.0,  3400.0, 0.0, 3.0),
            PositionSnapshot("BNBUSDT", "long", 0.50,   600.0,   580.0, 0.0, 3.0),
            PositionSnapshot("LINKUSDT","long", 5.00,    14.5,    13.5, 0.0, 3.0),
            PositionSnapshot("DOTUSDT", "long", 5.00,     7.8,     7.0, 0.0, 3.0),
        ]
        ro = _mock_ro_client(positions=live_positions)
        sender = self._sender_with_creds()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert any("refresh_long_capacity_full" in g for g in r.blocked_gates)
        assert r.order_sent is False

    def test_open_positions_full_in_refresh_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)

        # 10 positions total (mix of long+short, no target symbol overlap)
        live_positions = [
            PositionSnapshot(f"X{i}USDT", "short", 1.0, 10.0, 11.0, 0.0, 3.0)
            for i in range(10)
        ]
        ro = _mock_ro_client(positions=live_positions)
        sender = self._sender_with_creds()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert any("refresh_open_positions_full" in g for g in r.blocked_gates)


# ---------------------------------------------------------------------------
# F24. Pre-send refresh: proof not strong / balance non-positive
# ---------------------------------------------------------------------------

class TestF24RefreshProofBalance:
    def _sender_with_creds(self) -> DemoNewEntrySender:
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "test_key_f24"
        sender._api_secret = "test_secret_f24"
        return sender

    def test_refresh_proof_weak_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)

        ro = _mock_ro_client(proof_strength=PROOF_WEAK)
        sender = self._sender_with_creds()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert any("refresh_proof_not_strong" in g for g in r.blocked_gates)
        assert r.order_sent is False

    def test_refresh_endpoint_not_demo_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)

        ro = _mock_ro_client(endpoint_family="bybit_live")
        sender = self._sender_with_creds()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert any("refresh_endpoint_not_demo" in g for g in r.blocked_gates)

    def test_refresh_balance_non_positive_blocked(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)

        ro = _mock_ro_client(available_balance_usd=0.0)
        sender = self._sender_with_creds()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert any("refresh_available_balance_non_positive" in g
                   for g in r.blocked_gates)


# ---------------------------------------------------------------------------
# F25. Successful / failed order submission (mocked) — no secrets
# ---------------------------------------------------------------------------

class TestF25MockedOrderExecution:
    def _sender_with_creds(self) -> DemoNewEntrySender:
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "SECRET_KEY_F25_SHOULD_NOT_APPEAR"
        sender._api_secret = "SECRET_F25_SHOULD_NOT_APPEAR"
        sender._key_present    = True
        sender._secret_present = True
        return sender

    def _execute_with_mock_response(
        self, retCode: int, order_id: str,
    ) -> NewEntryOrderResult:
        sender = self._sender_with_creds()
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        ro     = _mock_ro_client()
        mock_resp = {"retCode": retCode, "result": {"orderId": order_id},
                     "retMsg": "OK"}
        with patch.object(sender, "_post_to_demo", return_value=mock_resp):
            return sender.submit_one_new_entry(
                review=review, symbol=symbol, confirm_token=token,
                execute_new_entry=True, _now=now, _ro_client=ro,
            )

    def test_success_sets_order_id(self):
        r = self._execute_with_mock_response(0, "order-new-entry-abc")
        assert r.order_id == "order-new-entry-abc"

    def test_success_order_sent_true(self):
        r = self._execute_with_mock_response(0, "order-new-entry-ok")
        assert r.order_sent is True
        assert r.order_endpoint_called is True
        assert r.no_position_modified is False

    def test_success_no_api_secret_in_result_dict(self):
        r = self._execute_with_mock_response(0, "order-new-entry-x")
        s = json.dumps(r.to_dict())
        assert "SECRET_KEY_F25_SHOULD_NOT_APPEAR" not in s
        assert "SECRET_F25_SHOULD_NOT_APPEAR"     not in s

    def test_success_secret_value_observed_false(self):
        r = self._execute_with_mock_response(0, "order-new-entry-x")
        assert r.secret_value_observed is False

    def test_failure_order_sent_false(self):
        r = self._execute_with_mock_response(10001, "")
        assert r.order_sent is False
        assert r.no_position_modified is True
        assert "error" in r.order_response_status.lower()

    def test_failure_no_secrets_in_result(self):
        r = self._execute_with_mock_response(10001, "")
        s = json.dumps(r.to_dict())
        assert "SECRET_KEY_F25_SHOULD_NOT_APPEAR" not in s
        assert "SECRET_F25_SHOULD_NOT_APPEAR"     not in s


# ---------------------------------------------------------------------------
# Real execute URL goes to Demo endpoint only (no live host)
# ---------------------------------------------------------------------------

class TestExecuteUsesDemoEndpoint:
    def _sender_with_creds(self) -> DemoNewEntrySender:
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "key_demo_only"
        sender._api_secret = "sec_demo_only"
        sender._key_present    = True
        sender._secret_present = True
        return sender

    def test_order_url_is_demo_endpoint(self, monkeypatch):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        ro     = _mock_ro_client()
        sender = self._sender_with_creds()

        captured: list[str] = []

        class _MockResp:
            def read(self):
                return json.dumps(
                    {"retCode": 0, "result": {"orderId": "demo-1"}}
                ).encode()
            def __enter__(self):  return self
            def __exit__(self, *a): return False

        def _capture(req, timeout=None):
            captured.append(req.full_url)
            return _MockResp()

        monkeypatch.setattr("urllib.request.urlopen", _capture)
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert r.order_endpoint_called is True
        assert any("api-demo.bybit.com" in url for url in captured)
        live_only = [
            url for url in captured
            if "bybit.com" in url and "api-demo" not in url
        ]
        assert live_only == [], f"Live endpoint accessed: {live_only}"

    def test_order_url_uses_order_create_path(self, monkeypatch):
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        ro     = _mock_ro_client()
        sender = self._sender_with_creds()

        captured: list[str] = []

        class _MockResp:
            def read(self):
                return json.dumps(
                    {"retCode": 0, "result": {"orderId": "demo-2"}}
                ).encode()
            def __enter__(self):  return self
            def __exit__(self, *a): return False

        monkeypatch.setattr("urllib.request.urlopen",
                            lambda req, timeout=None: (captured.append(req.full_url) or _MockResp()))
        sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=True, _now=now, _ro_client=ro,
        )
        assert all(url.endswith(_ORDER_ENDPOINT) for url in captured)


# ---------------------------------------------------------------------------
# Order body composition tests
# ---------------------------------------------------------------------------

class TestOrderBodyComposition:
    def _sender_with_creds(self) -> DemoNewEntrySender:
        sender = DemoNewEntrySender(allow_real_network=True)
        sender._api_key    = "k_body"
        sender._api_secret = "s_body"
        sender._key_present    = True
        sender._secret_present = True
        return sender

    def _capture_body(self) -> dict:
        captured: dict[str, Any] = {}
        sender = self._sender_with_creds()
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        ro     = _mock_ro_client()

        def _capturing_post(body_dict):
            captured.update(body_dict)
            return {"retCode": 0, "result": {"orderId": "body-1"}, "retMsg": "OK"}

        with patch.object(sender, "_post_to_demo", side_effect=_capturing_post):
            sender.submit_one_new_entry(
                review=review, symbol=symbol, confirm_token=token,
                execute_new_entry=True, _now=now, _ro_client=ro,
            )
        return captured

    def test_body_category_linear(self):
        assert self._capture_body()["category"] == "linear"

    def test_body_order_type_market(self):
        assert self._capture_body()["orderType"] == "Market"

    def test_body_reduce_only_false(self):
        assert self._capture_body()["reduceOnly"] is False

    def test_body_close_on_trigger_false(self):
        assert self._capture_body()["closeOnTrigger"] is False

    def test_body_side_is_buy_for_long(self):
        assert self._capture_body()["side"] == "Buy"

    def test_body_has_no_leverage(self):
        assert "leverage" not in self._capture_body()

    def test_body_has_no_take_profit(self):
        body = self._capture_body()
        assert "takeProfit" not in body
        assert "stopLoss"   not in body
        assert "triggerPrice" not in body
        assert "tpslMode"   not in body


# ---------------------------------------------------------------------------
# Source scan: no live hostname, no forbidden tokens, no close-only imports
# ---------------------------------------------------------------------------

_SRC    = ROOT / "src"     / "demo_new_entry_sender.py"
_SCRIPT = ROOT / "scripts" / "execute_demo_new_entry.py"


def _read_src(path: Path) -> str:
    return path.read_text(encoding="utf-8")


def _imports(path: Path) -> list[str]:
    """Return the list of names imported by this module (AST-based)."""
    tree  = ast.parse(_read_src(path))
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for n in node.names:
                names.append(n.name)
        elif isinstance(node, ast.ImportFrom):
            mod = node.module or ""
            for n in node.names:
                names.append(f"{mod}.{n.name}")
    return names


class TestSourceScanNoLiveEndpoint:
    """No live (non-demo) hostname / no live fallback logic."""

    def test_sender_no_live_hostname(self):
        assert "api.bybit.com" not in _read_src(_SRC)

    def test_script_no_live_hostname(self):
        assert "api.bybit.com" not in _read_src(_SCRIPT)

    def test_sender_uses_demo_base_url(self):
        src = _read_src(_SRC)
        assert "DEMO_BASE_URL" in src or "api-demo.bybit.com" in src


class TestSourceScanForbiddenOps:
    """No leverage / TP/SL / trading-stop / transfer / withdraw / deposit."""

    def test_sender_no_set_leverage(self):
        src = _read_src(_SRC)
        assert "set_leverage" not in src
        assert "setLeverage"  not in src
        assert "/v5/position/set-leverage" not in src

    def test_sender_no_trading_stop(self):
        src = _read_src(_SRC)
        assert "set_trading_stop" not in src
        assert "tradingStop"      not in src
        assert "/v5/position/trading-stop" not in src

    def test_sender_no_tp_sl(self):
        src = _read_src(_SRC)
        assert "takeProfit"   not in src
        assert "stopLoss"     not in src
        assert "triggerPrice" not in src
        assert "tpslMode"     not in src

    def test_sender_no_transfer_or_withdraw(self):
        src = _read_src(_SRC)
        assert "/asset/transfer" not in src
        assert "/withdraw"       not in src
        assert "/deposit"        not in src

    def test_sender_no_batch_order_endpoint(self):
        src = _read_src(_SRC)
        assert "/v5/order/create-batch" not in src
        assert "createBatch"            not in src

    def test_sender_no_pybit(self):
        assert "pybit" not in _read_src(_SRC)

    def test_script_no_forbidden_tokens(self):
        src = _read_src(_SCRIPT)
        assert "set_leverage"  not in src
        assert "setLeverage"   not in src
        assert "takeProfit"    not in src
        assert "stopLoss"      not in src
        assert "/v5/order/create-batch" not in src


class TestSourceScanNoCloseOnlyImport:
    """The new-entry sender must NOT import the close-only sender or its CLI."""

    def test_sender_no_demo_close_only_sender_import(self):
        imports = _imports(_SRC)
        assert not any("demo_close_only_sender" in imp for imp in imports)

    def test_sender_no_execute_demo_close_only_cleanup_import(self):
        imports = _imports(_SRC)
        assert not any("execute_demo_close_only_cleanup" in imp for imp in imports)

    def test_script_no_demo_close_only_sender_import(self):
        imports = _imports(_SCRIPT)
        assert not any("demo_close_only_sender" in imp for imp in imports)


class TestNoMainOrRiskOrExecutorImport:
    """The new-entry sender must NOT import main / src.risk / BybitExecutor."""

    def test_sender_no_main_import(self):
        imports = _imports(_SRC)
        assert not any(imp == "main" or imp.startswith("main.") for imp in imports)

    def test_sender_no_src_risk_import(self):
        imports = _imports(_SRC)
        assert not any(imp.startswith("src.risk") for imp in imports)

    def test_sender_no_bybit_executor_import(self):
        imports = _imports(_SRC)
        assert not any(imp.endswith("BybitExecutor") for imp in imports)


# ---------------------------------------------------------------------------
# No secrets in output (sender + report writer)
# ---------------------------------------------------------------------------

class TestNoSecretsInOutput:
    def test_env_secrets_never_in_result(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "ENV_KEY_F25_NEVER_APPEAR")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "ENV_SEC_F25_NEVER_APPEAR")
        sender = DemoNewEntrySender(allow_real_network=True)
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=False, _now=now,
        )
        s = json.dumps(r.to_dict())
        assert "ENV_KEY_F25_NEVER_APPEAR" not in s
        assert "ENV_SEC_F25_NEVER_APPEAR" not in s

    def test_secret_value_observed_always_false(self):
        review = _build_review()
        symbol = _accepted_symbol(review)
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        assert r.secret_value_observed is False

    def test_report_has_no_secrets(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "ENV_KEY_REPORT_NEVER")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "ENV_SEC_REPORT_NEVER")
        from scripts.execute_demo_new_entry import _write_execution_report
        review = _build_review()
        symbol = _accepted_symbol(review)
        sender = DemoNewEntrySender()
        r = sender.submit_one_new_entry(
            review=review, symbol=symbol,
            confirm_token=_valid_token(_fixed_now()),
            execute_new_entry=False, _now=_fixed_now(),
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(r, Path(tmpdir), "2026-06-09T12:00:00Z")
            json_text = (Path(tmpdir) / "latest_new_entry_execution.json").read_text(
                encoding="utf-8"
            )
            md_text = (Path(tmpdir) / "latest_new_entry_execution.md").read_text(
                encoding="utf-8"
            )
        assert "ENV_KEY_REPORT_NEVER" not in json_text
        assert "ENV_SEC_REPORT_NEVER" not in json_text
        assert "ENV_KEY_REPORT_NEVER" not in md_text
        assert "ENV_SEC_REPORT_NEVER" not in md_text


# ---------------------------------------------------------------------------
# Structural invariants on result dataclass
# ---------------------------------------------------------------------------

class TestStructuralInvariants:
    def _dry_run_result(self) -> NewEntryOrderResult:
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        sender = DemoNewEntrySender()
        return sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=False, _now=now,
        )

    def test_no_live_endpoint_always_true(self):
        assert self._dry_run_result().no_live_endpoint is True

    def test_no_batch_order_always_true(self):
        assert self._dry_run_result().no_batch_order is True

    def test_no_close_only_path_always_true(self):
        assert self._dry_run_result().no_close_only_path is True

    def test_reduce_only_always_false(self):
        assert self._dry_run_result().reduce_only is False

    def test_secret_value_observed_always_false(self):
        assert self._dry_run_result().secret_value_observed is False

    def test_to_dict_does_not_emit_secret_fields(self):
        d = self._dry_run_result().to_dict()
        forbidden = ["api_key", "api_secret", "x-bapi-sign", "bapi_sign",
                     "private_key"]
        s = json.dumps(d).lower()
        for tok in forbidden:
            assert tok not in s, f"forbidden token {tok!r} in result dict"
        assert d["secret_value_observed"] is False
        assert d["no_live_endpoint"]      is True
        assert d["no_batch_order"]        is True
        assert d["no_close_only_path"]    is True
        assert d["reduce_only"]           is False


# ---------------------------------------------------------------------------
# Report artifact tests
# ---------------------------------------------------------------------------

class TestReportArtifacts:
    def _result(self) -> NewEntryOrderResult:
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        sender = DemoNewEntrySender()
        return sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=False, _now=now,
        )

    def test_write_report_creates_json(self):
        from scripts.execute_demo_new_entry import _write_execution_report
        r = self._result()
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(r, Path(tmpdir), "2026-06-09T12:00:00Z")
            latest = Path(tmpdir) / "latest_new_entry_execution.json"
            ts     = Path(tmpdir) / "20260609_120000_new_entry_execution.json"
            assert latest.exists()
            assert ts.exists()

    def test_write_report_creates_markdown(self):
        from scripts.execute_demo_new_entry import _write_execution_report
        r = self._result()
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(r, Path(tmpdir), "2026-06-09T12:00:00Z")
            assert (Path(tmpdir) / "latest_new_entry_execution.md").exists()

    def test_json_contains_safety_invariant_fields(self):
        from scripts.execute_demo_new_entry import _write_execution_report
        r = self._result()
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_execution_report(r, Path(tmpdir), "2026-06-09T12:00:00Z")
            data = json.loads(
                (Path(tmpdir) / "latest_new_entry_execution.json").read_text(
                    encoding="utf-8"
                )
            )
        for field in ("no_live_endpoint", "no_batch_order", "no_close_only_path",
                      "secret_value_observed", "reduce_only", "no_position_modified",
                      "order_endpoint_called", "order_sent", "blocked_gates"):
            assert field in data, f"missing field {field} in report JSON"
        assert data["no_live_endpoint"]   is True
        assert data["no_batch_order"]     is True
        assert data["no_close_only_path"] is True
        assert data["reduce_only"]        is False
        assert data["order_sent"]         is False

    def test_run_execute_writes_report_when_flag_set(self):
        from scripts.execute_demo_new_entry import run_execute
        review = _build_review()
        symbol = _accepted_symbol(review)
        token  = _valid_token()
        with tempfile.TemporaryDirectory() as review_tmp:
            with tempfile.TemporaryDirectory() as exec_tmp:
                _write_review_to_dir(review_tmp, review)
                run_execute(
                    symbol=symbol, confirm_token=token,
                    write_report=True,
                    review_dir=Path(review_tmp),
                    execution_dir=Path(exec_tmp),
                )
                assert (Path(exec_tmp) / "latest_new_entry_execution.json").exists()


# ---------------------------------------------------------------------------
# Valid dry-run produces executable preview (full success path)
# ---------------------------------------------------------------------------

class TestValidDryRunPreview:
    def _result(self) -> NewEntryOrderResult:
        review = _build_review()
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        sender = DemoNewEntrySender()
        return sender.submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=False, _now=now,
        )

    def test_blocked_gates_empty(self):
        assert self._result().blocked_gates == []

    def test_execute_allowed_true(self):
        assert self._result().execute_allowed is True

    def test_order_sent_false(self):
        assert self._result().order_sent is False

    def test_order_endpoint_called_false(self):
        assert self._result().order_endpoint_called is False

    def test_order_side_is_buy_for_long(self):
        r = self._result()
        assert r.selected_side == "long"
        assert r.order_side    == "Buy"

    def test_order_type_market(self):
        assert self._result().order_type == "Market"

    def test_reduce_only_false(self):
        assert self._result().reduce_only is False

    def test_preview_only_source_true(self):
        assert self._result().preview_only_source is True


# ---------------------------------------------------------------------------
# TASK-014M: realtime_price_guard_verified gate
# ---------------------------------------------------------------------------

class TestRealtimePriceGuard:
    """
    TASK-014M production incident (SOLUSDT, 2026-06-09): a stale preview
    entry_reference_price (160) produced a ~58% deviation against the actual
    fill (66.47).  The sender must now hard-fail when the review file does
    NOT explicitly assert `realtime_price_guard_verified=True`.
    """

    def _send(
        self,
        guard_verified: bool,
        *,
        explicit_field: bool = True,
    ) -> NewEntryOrderResult:
        if explicit_field:
            review = _build_review(realtime_price_guard_verified=guard_verified)
        else:
            review = _build_review()
            review.pop("realtime_price_guard_verified", None)
        symbol = _accepted_symbol(review)
        now    = _fixed_now()
        token  = _token_for(now)
        return DemoNewEntrySender().submit_one_new_entry(
            review=review, symbol=symbol, confirm_token=token,
            execute_new_entry=False, _now=now,
        )

    def test_passes_when_verified_true(self):
        r = self._send(guard_verified=True)
        assert "missing_realtime_price_guard" not in r.blocked_gates

    def test_fails_when_verified_false(self):
        r = self._send(guard_verified=False)
        assert "missing_realtime_price_guard" in r.blocked_gates
        assert r.execute_allowed is False
        assert r.order_sent is False
        assert r.order_endpoint_called is False

    def test_fails_when_field_missing(self):
        r = self._send(guard_verified=False, explicit_field=False)
        assert "missing_realtime_price_guard" in r.blocked_gates
        assert r.execute_allowed is False
