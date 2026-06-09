"""
tests/demo_trading/test_demo_close_only_cleanup.py
TASK-014F: Tests for src/demo_close_only_cleanup.py and
           scripts/preview_demo_close_only_cleanup.py

Covers TASK-014F requirements E1-E19:
  E1.  no violations => cleanup_needed False
  E2.  short_count 7 => proposed_close_count 2
  E3.  close candidates only from short positions (when short violated)
  E4.  deterministic sorting: stop_risk DESC, notional DESC, symbol ASC
  E5.  close side: short => Buy
  E6.  close side: long => Sell
  E7.  reduce_only always True
  E8.  qty <= position qty
  E9.  missing latest_reconciliation => fail closed
  E10. unverified reconciliation => fail closed
  E11. stale snapshot => execute_ready False
  E12. missing confirm token => execute_ready False
  E13. wrong confirm token => execute_ready False
  E14. correct confirm token but no sender => no_orders_sent True
  E15. payload no leverage / transfer / TP/SL fields
  E16. no order endpoint tokens in source
  E17. no secrets in report json/md
  E18. no_position_modified True
  E19. main.py / src/risk.py / exchange executor not modified

SAFETY: no exchange imports, no order calls, no secrets.
"""
from __future__ import annotations

import dataclasses
import json
import sys
import tempfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_close_only_cleanup import (
    MAX_SHORT_POSITIONS,
    CleanupPlan,
    ClosePayloadPreview,
    plan_cleanup,
    _expected_confirm_token,
)
from src.demo_portfolio_risk import DemoOpenPosition


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _pos(symbol="BTCUSDT", side="long", qty=0.05, entry=67_000.0,
         stop=65_000.0) -> DemoOpenPosition:
    return DemoOpenPosition(symbol=symbol, side=side, quantity=qty,
                            entry_price=entry, stop_price=stop)


def _legacy_positions() -> list[DemoOpenPosition]:
    """Legacy fixture: 1 long + 7 short (matches real Demo account state)."""
    return [
        DemoOpenPosition("BTCUSDT",  "long",  0.02,   67_000.0, 65_000.0),
        DemoOpenPosition("ETHUSDT",  "short", 0.50,    3_500.0,  3_700.0),
        DemoOpenPosition("BNBUSDT",  "short", 2.00,      600.0,    640.0),
        DemoOpenPosition("SOLUSDT",  "short", 5.00,      160.0,    175.0),
        DemoOpenPosition("XRPUSDT",  "short", 500.00,      0.62,     0.68),
        DemoOpenPosition("ADAUSDT",  "short", 800.00,      0.45,     0.49),
        DemoOpenPosition("DOTUSDT",  "short",  30.00,      7.80,     8.50),
        DemoOpenPosition("LINKUSDT", "short",  20.00,     14.50,    16.00),
    ]


def _clean_positions() -> list[DemoOpenPosition]:
    return [
        _pos("BTCUSDT", "long",  0.05, 67_000.0, 65_000.0),
        _pos("ETHUSDT", "short", 0.30,  3_500.0,  3_700.0),
    ]


def _valid_token(today: date) -> str:
    return _expected_confirm_token(today)


# ---------------------------------------------------------------------------
# E1. No violations => cleanup_needed False
# ---------------------------------------------------------------------------

class TestNoCleanupNeeded:
    """E1: clean state (counts within limits) → cleanup_needed=False."""

    def test_cleanup_not_needed(self):
        plan = plan_cleanup(10_000.0, 5_000.0, _clean_positions())
        assert plan.cleanup_needed is False

    def test_no_suggested_candidates(self):
        plan = plan_cleanup(10_000.0, 5_000.0, _clean_positions())
        assert plan.suggested_close_candidates == []

    def test_proposed_close_count_zero(self):
        plan = plan_cleanup(10_000.0, 5_000.0, _clean_positions())
        assert plan.proposed_close_count == 0

    def test_no_payloads(self):
        plan = plan_cleanup(10_000.0, 5_000.0, _clean_positions())
        assert plan.close_payload_previews == []

    def test_execute_ready_false_when_no_cleanup(self):
        plan = plan_cleanup(10_000.0, 5_000.0, _clean_positions())
        assert plan.execute_ready is False

    def test_preview_exits_zero_fixture(self):
        from scripts.preview_demo_close_only_cleanup import run_preview
        rc = run_preview(mode="fixture")
        # Fixture uses clean positions → cleanup_needed=False → exit 0
        assert rc == 0


# ---------------------------------------------------------------------------
# E2. short_count 7 => proposed_close_count 2
# ---------------------------------------------------------------------------

class TestShortCountViolation:
    """E2: 7 shorts with MAX_SHORT=5 → close 2."""

    def test_proposed_close_count_is_two(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.proposed_close_count == 2

    def test_cleanup_needed_true(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.cleanup_needed is True

    def test_cleanup_reason_mentions_short_count(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        combined = " ".join(plan.cleanup_reasons)
        assert "short_count" in combined

    def test_current_short_count_correct(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.current_short_count == 7

    def test_target_short_count_is_max(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.target_short_count == MAX_SHORT_POSITIONS

    def test_five_shorts_no_cleanup(self):
        positions = [_pos(f"S{i}USDT", "short", 1.0, 100.0, 110.0)
                     for i in range(5)]
        plan = plan_cleanup(10_000.0, 1_000.0, positions)
        assert plan.cleanup_needed is False
        assert plan.proposed_close_count == 0


# ---------------------------------------------------------------------------
# E3. Close candidates only from short positions when short violated
# ---------------------------------------------------------------------------

class TestCandidatesOnlyShort:
    """E3: when only short_count is violated, only shorts are selected."""

    def test_all_candidates_are_short(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        for c in plan.suggested_close_candidates:
            assert c.side.lower() == "short"

    def test_long_not_in_candidates(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        symbols = {c.symbol for c in plan.suggested_close_candidates}
        assert "BTCUSDT" not in symbols   # BTCUSDT is the long position

    def test_candidate_positions_to_review_includes_all(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        # All 8 positions appear in candidate_positions_to_review
        assert len(plan.candidate_positions_to_review) == 8

    def test_long_violation_selects_only_longs(self):
        # 6 longs, 1 short → long_count violated, only longs selected
        positions = [
            _pos(f"L{i}USDT", "long", 0.01, 100.0, 90.0) for i in range(6)
        ] + [_pos("ETHUSDT", "short", 0.5, 100.0, 110.0)]
        plan = plan_cleanup(10_000.0, 5_000.0, positions)
        for c in plan.suggested_close_candidates:
            assert c.side.lower() == "long"
        assert "ETHUSDT" not in {c.symbol for c in plan.suggested_close_candidates}


# ---------------------------------------------------------------------------
# E4. Deterministic sorting: stop_risk DESC, notional DESC, symbol ASC
# ---------------------------------------------------------------------------

class TestDeterministicSorting:
    """E4: candidates sorted by stop_risk DESC, notional DESC, symbol ASC."""

    def test_highest_stop_risk_is_first(self):
        # ETHUSDT: stop_risk = |3500-3700|*0.5 = 100 (highest)
        # BNBUSDT: stop_risk = |600-640|*2     = 80
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.suggested_close_candidates[0].symbol == "ETHUSDT"

    def test_second_highest_stop_risk_is_second(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.suggested_close_candidates[1].symbol == "BNBUSDT"

    def test_symbol_asc_tiebreak(self):
        # 7 shorts all with identical stop_risk and notional → sort by symbol ASC
        positions = [
            DemoOpenPosition(f"{ch}USDT", "short", 1.0, 100.0, 90.0)
            for ch in ["ZZZ", "AAA", "BBB", "CCC", "DDD", "EEE", "FFF"]
        ]
        plan = plan_cleanup(10_000.0, 100.0, positions)
        assert plan.proposed_close_count == 2
        symbols = [c.symbol for c in plan.suggested_close_candidates]
        assert symbols[0] == "AAAUSDT"
        assert symbols[1] == "BBBUSDT"

    def test_notional_desc_tiebreak(self):
        # Two shorts with same stop_risk but different notional
        # Higher notional should come first
        positions = [
            DemoOpenPosition("AXXUSDT", "short", 10.0, 100.0, 90.0),  # notional=1000, risk=100
            DemoOpenPosition("BXXUSDT", "short", 1.0,  500.0, 450.0),  # notional=500, risk=50
            DemoOpenPosition("CXXUSDT", "short", 5.0,  200.0, 180.0),  # notional=1000, risk=100
            DemoOpenPosition("DXXUSDT", "short", 1.0,  100.0, 90.0),   # notional=100, risk=10
            DemoOpenPosition("EXXUSDT", "short", 2.0,  100.0, 90.0),   # notional=200, risk=20
            DemoOpenPosition("FXXUSDT", "short", 0.5,  100.0, 90.0),   # notional=50,  risk=5
            DemoOpenPosition("GXXUSDT", "short", 3.0,  100.0, 90.0),   # notional=300, risk=30
        ]
        plan = plan_cleanup(10_000.0, 1_000.0, positions)
        # AXXUSDT and CXXUSDT both have risk=100, notional=1000
        # tie-break by symbol: AXXUSDT < CXXUSDT → AXXUSDT first
        assert plan.suggested_close_candidates[0].symbol == "AXXUSDT"
        assert plan.suggested_close_candidates[1].symbol == "CXXUSDT"

    def test_close_rank_is_sequential(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        ranks = [c.close_rank for c in plan.suggested_close_candidates]
        assert ranks == list(range(1, plan.proposed_close_count + 1))


# ---------------------------------------------------------------------------
# E5-E6. Close order side direction
# ---------------------------------------------------------------------------

class TestCloseOrderSide:
    """E5: short position → close_order_side="Buy"; E6: long → "Sell"."""

    def test_short_position_close_side_is_buy(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        for p in plan.close_payload_previews:
            assert p.side_to_close == "short"
            assert p.close_order_side == "Buy"

    def test_long_position_close_side_is_sell(self):
        # Force long_count > 5
        positions = [
            _pos(f"L{i}USDT", "long", 0.01, 100.0, 90.0) for i in range(6)
        ]
        plan = plan_cleanup(10_000.0, 5_000.0, positions)
        assert plan.proposed_close_count == 1
        assert plan.close_payload_previews[0].close_order_side == "Sell"
        assert plan.close_payload_previews[0].side_to_close == "long"

    def test_payload_close_side_matches_position_side(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        for payload in plan.close_payload_previews:
            cand_map = {c.symbol: c for c in plan.suggested_close_candidates}
            c = cand_map[payload.symbol]
            expected_side = "Buy" if c.side.lower() == "short" else "Sell"
            assert payload.close_order_side == expected_side


# ---------------------------------------------------------------------------
# E7. reduce_only always True
# ---------------------------------------------------------------------------

class TestReduceOnly:
    """E7: reduce_only must be True in every payload."""

    def test_all_payloads_reduce_only_true(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        for p in plan.close_payload_previews:
            assert p.reduce_only is True

    def test_reduce_only_true_in_dict(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        d = plan.to_dict()
        for p in d["close_payload_preview"]:
            assert p["reduce_only"] is True

    def test_reduce_only_true_when_long_count_violated(self):
        positions = [_pos(f"L{i}USDT", "long", 0.01, 100.0, 90.0) for i in range(6)]
        plan = plan_cleanup(10_000.0, 5_000.0, positions)
        for p in plan.close_payload_previews:
            assert p.reduce_only is True


# ---------------------------------------------------------------------------
# E8. qty <= position qty
# ---------------------------------------------------------------------------

class TestQtyValid:
    """E8: payload qty must be positive and not exceed the position quantity."""

    def test_payload_qty_positive(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        for p in plan.close_payload_previews:
            assert p.qty > 0

    def test_payload_qty_equals_position_qty(self):
        # For a single-position close, qty should match the position
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        candidate_map = {c.symbol: c for c in plan.suggested_close_candidates}
        for p in plan.close_payload_previews:
            c = candidate_map[p.symbol]
            assert p.qty <= c.quantity + 1e-9   # qty must not exceed position qty
            assert p.qty == c.quantity           # for full-position close

    def test_payload_qty_finite(self):
        import math
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        for p in plan.close_payload_previews:
            assert math.isfinite(p.qty)


# ---------------------------------------------------------------------------
# E9. Missing latest_reconciliation => fail closed
# ---------------------------------------------------------------------------

class TestMissingReconciliation:
    """E9: preview exits 1 when latest_reconciliation.json is missing."""

    def test_missing_file_exits_one(self):
        from scripts.preview_demo_close_only_cleanup import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = run_preview(
                mode="from_latest_reconciliation",
                reconcile_dir=Path(tmpdir),
            )
        assert rc == 1

    def test_missing_file_prints_fail_message(self, capsys):
        from scripts.preview_demo_close_only_cleanup import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            run_preview(mode="from_latest_reconciliation", reconcile_dir=Path(tmpdir))
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out or "not found" in out


# ---------------------------------------------------------------------------
# E10. Unverified reconciliation => fail closed
# ---------------------------------------------------------------------------

class TestUnverifiedReconciliation:
    """E10: preview exits 1 when demo_runtime_verified=False in reconciliation."""

    def _write_rec(self, tmpdir: str, verified: bool) -> Path:
        d = Path(tmpdir)
        path = d / "latest_reconciliation.json"
        path.write_text(json.dumps({
            "demo_runtime_verified": verified,
            "proof_strength": "STRONG" if verified else "WEAK",
            "equity_usd": 11_404.01,
            "available_balance_usd": 0.0,
            "timestamp": "2026-06-06T10:00:00Z",
            "position_details_source": "real_readonly",
            "positions": [
                {"symbol": "AIXBTUSDT", "side": "short", "quantity": 100.0,
                 "entry_price": 0.50, "stop_price": 0.55},
                {"symbol": "ENAUSDT", "side": "short", "quantity": 1000.0,
                 "entry_price": 0.80, "stop_price": 0.85},
                {"symbol": "BOMEUSDT", "side": "short", "quantity": 5000.0,
                 "entry_price": 0.01, "stop_price": 0.012},
                {"symbol": "EDUUSDT", "side": "short", "quantity": 800.0,
                 "entry_price": 1.20, "stop_price": 1.30},
                {"symbol": "MERLUSDT", "side": "short", "quantity": 400.0,
                 "entry_price": 2.40, "stop_price": 2.60},
                {"symbol": "XAUTUSDT", "side": "short", "quantity": 0.4,
                 "entry_price": 2400.0, "stop_price": 2500.0},
                {"symbol": "POLYXUSDT", "side": "short", "quantity": 1500.0,
                 "entry_price": 0.30, "stop_price": 0.34},
                {"symbol": "TIAUSDT", "side": "short", "quantity": 50.0,
                 "entry_price": 5.40, "stop_price": 5.80},
            ],
        }), encoding="utf-8")
        return d

    def test_unverified_exits_one(self):
        from scripts.preview_demo_close_only_cleanup import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            d = self._write_rec(tmpdir, verified=False)
            rc = run_preview(mode="from_latest_reconciliation", reconcile_dir=d)
        assert rc == 1

    def test_verified_proceeds(self):
        from scripts.preview_demo_close_only_cleanup import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            d = self._write_rec(tmpdir, verified=True)
            rc = run_preview(
                mode="from_latest_reconciliation",
                reconcile_dir=d,
                max_snapshot_age_hours=1_000_000,  # disable staleness for this test
            )
        assert rc == 0  # proceeds (cleanup plan generated, exit 0 even if cleanup needed)

    def test_unverified_prints_fail_message(self, capsys):
        from scripts.preview_demo_close_only_cleanup import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            d = self._write_rec(tmpdir, verified=False)
            run_preview(mode="from_latest_reconciliation", reconcile_dir=d)
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out


# ---------------------------------------------------------------------------
# E11. Stale snapshot => execute_ready False
# ---------------------------------------------------------------------------

class TestStaleSnapshot:
    """E11: stale snapshot (age > max_age) → execute_ready=False."""

    def test_stale_snapshot_execute_not_ready(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=25)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_legacy_positions(),
            demo_runtime_verified=True,
            proof_strength="STRONG",
            snapshot_timestamp_utc=old_ts,
            max_snapshot_age_hours=24.0,
        )
        assert plan.snapshot_fresh is False
        assert plan.execute_ready is False

    def test_fresh_snapshot_does_not_block(self):
        now = datetime.now(timezone.utc)
        fresh_ts = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        today = now.date()
        token = _valid_token(today)
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_legacy_positions(),
            demo_runtime_verified=True,
            proof_strength="STRONG",
            confirm_token=token,
            today=today,
            snapshot_timestamp_utc=fresh_ts,
            max_snapshot_age_hours=24.0,
            _now=now,
        )
        assert plan.snapshot_fresh is True

    def test_stale_adds_to_cleanup_reasons(self):
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        plan = plan_cleanup(
            equity_usd=10_000.0,
            available_balance_usd=5_000.0,
            positions=_legacy_positions(),
            snapshot_timestamp_utc=old_ts,
        )
        combined = " ".join(plan.cleanup_reasons)
        assert "stale" in combined.lower()

    def test_stale_preview_exits_one(self):
        from scripts.preview_demo_close_only_cleanup import run_preview
        old_ts = (datetime.now(timezone.utc) - timedelta(hours=30)).strftime(
            "%Y-%m-%dT%H:%M:%SZ"
        )
        with tempfile.TemporaryDirectory() as tmpdir:
            d = Path(tmpdir)
            (d / "latest_reconciliation.json").write_text(json.dumps({
                "demo_runtime_verified": True,
                "proof_strength": "STRONG",
                "equity_usd": 11_404.01,
                "available_balance_usd": 0.0,
                "timestamp": old_ts,
            }), encoding="utf-8")
            rc = run_preview(
                mode="from_latest_reconciliation",
                reconcile_dir=d,
                max_snapshot_age_hours=24.0,
            )
        assert rc == 1


# ---------------------------------------------------------------------------
# E12. Missing confirm token => execute_ready False
# ---------------------------------------------------------------------------

class TestConfirmTokenMissing:
    """E12: empty or absent token → execute_ready=False."""

    def test_no_token_execute_not_ready(self):
        plan = plan_cleanup(
            11_404.01, 0.0, _legacy_positions(),
            demo_runtime_verified=True, confirm_token="",
        )
        assert plan.execute_ready is False

    def test_confirm_token_valid_false_when_empty(self):
        plan = plan_cleanup(
            11_404.01, 0.0, _legacy_positions(),
            demo_runtime_verified=True, confirm_token="",
        )
        assert plan.confirm_token_valid is False

    def test_expected_token_pattern_present(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert "CONFIRM_DEMO_CLOSE_ONLY_" in plan.confirm_token_expected_pattern
        assert len(plan.confirm_token_expected_pattern) == len("CONFIRM_DEMO_CLOSE_ONLY_20260606")


# ---------------------------------------------------------------------------
# E13. Wrong confirm token => execute_ready False
# ---------------------------------------------------------------------------

class TestConfirmTokenWrong:
    """E13: wrong token string → execute_ready=False."""

    def test_wrong_token_execute_not_ready(self):
        plan = plan_cleanup(
            11_404.01, 0.0, _legacy_positions(),
            demo_runtime_verified=True,
            confirm_token="WRONG_TOKEN",
        )
        assert plan.execute_ready is False

    def test_wrong_token_valid_false(self):
        plan = plan_cleanup(
            11_404.01, 0.0, _legacy_positions(),
            demo_runtime_verified=True,
            confirm_token="WRONG_TOKEN",
        )
        assert plan.confirm_token_valid is False

    def test_almost_correct_token_still_wrong(self):
        today = date(2026, 6, 6)
        # One char off
        wrong = "CONFIRM_DEMO_CLOSE_ONLY_20260607"
        plan = plan_cleanup(
            11_404.01, 0.0, _legacy_positions(),
            demo_runtime_verified=True,
            confirm_token=wrong,
            today=today,
        )
        assert plan.execute_ready is False
        assert plan.confirm_token_valid is False


# ---------------------------------------------------------------------------
# E14. Correct confirm token but no sender => no_orders_sent True
# ---------------------------------------------------------------------------

class TestCorrectTokenNoSender:
    """E14: valid token + all gates pass → execute_ready=True AND no_orders_sent=True."""

    def _ready_plan(self) -> CleanupPlan:
        now   = datetime.now(timezone.utc)
        today = now.date()
        token = _valid_token(today)
        fresh_ts = (now - timedelta(hours=1)).strftime("%Y-%m-%dT%H:%M:%SZ")
        return plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_legacy_positions(),
            demo_runtime_verified=True,
            proof_strength="STRONG",
            confirm_token=token,
            today=today,
            snapshot_timestamp_utc=fresh_ts,
            max_snapshot_age_hours=24.0,
            _now=now,
            position_details_source="real_readonly",
        )

    def test_no_orders_sent_always_true(self):
        assert self._ready_plan().no_orders_sent is True

    def test_execute_ready_true_with_valid_token(self):
        assert self._ready_plan().execute_ready is True

    def test_no_position_modified_true_even_when_ready(self):
        assert self._ready_plan().no_position_modified is True

    def test_order_endpoint_called_false_when_ready(self):
        assert self._ready_plan().order_endpoint_called is False


# ---------------------------------------------------------------------------
# E15. Payload has no leverage/transfer/TP/SL mutation fields
# ---------------------------------------------------------------------------

class TestPayloadNoLeverageTransfer:
    """E15: close payloads must not include leverage/transfer/TP/SL fields."""

    def _payload_dict(self) -> list[dict]:
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        return plan.to_dict()["close_payload_preview"]

    def test_no_leverage_in_payload(self):
        for p in self._payload_dict():
            assert "leverage" not in p

    def test_no_take_profit_in_payload(self):
        for p in self._payload_dict():
            assert "take_profit" not in str(p)
            assert "takeProfit" not in str(p)

    def test_no_stop_loss_field_in_payload(self):
        for p in self._payload_dict():
            # stop_price from position is not included in the close payload
            assert "stop_loss" not in p
            assert "stopLoss" not in p

    def test_no_transfer_in_payload(self):
        for p in self._payload_dict():
            assert "transfer" not in str(p).lower()

    def test_payload_dataclass_fields_safe(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        for p in plan.close_payload_previews:
            d = dataclasses.asdict(p)
            keys = set(d.keys())
            forbidden = {"leverage", "take_profit", "stop_loss", "transfer",
                         "takeProfit", "stopLoss", "position_mode"}
            assert keys.isdisjoint(forbidden), f"Forbidden keys found: {keys & forbidden}"


# ---------------------------------------------------------------------------
# E16. No order endpoint tokens in source
# ---------------------------------------------------------------------------

class TestModuleSourceSafety:
    """E16: forbidden order/endpoint tokens must not appear in module source."""
    _SRC    = ROOT / "src" / "demo_close_only_cleanup.py"
    _SCRIPT = ROOT / "scripts" / "preview_demo_close_only_cleanup.py"

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_module_no_place_order(self):
        assert "place_order" not in self._read(self._SRC)

    def test_module_no_create_order(self):
        assert "create_order" not in self._read(self._SRC)

    def test_module_no_submit_order(self):
        assert "submit_order" not in self._read(self._SRC)

    def test_module_no_cancel_order(self):
        assert "cancel_order" not in self._read(self._SRC)

    def test_module_no_private_post(self):
        assert "private_post" not in self._read(self._SRC)

    def test_module_no_set_leverage(self):
        assert "set_leverage" not in self._read(self._SRC)

    def test_module_no_set_trading_stop(self):
        assert "set_trading_stop" not in self._read(self._SRC)

    def test_module_no_transfer_call(self):
        assert "transfer(" not in self._read(self._SRC)

    def test_module_no_pybit(self):
        assert "pybit" not in self._read(self._SRC)

    def test_module_no_bybit_executor(self):
        assert "BybitExecutor" not in self._read(self._SRC)

    def test_module_no_main_import(self):
        src = self._read(self._SRC)
        assert "import main" not in src
        assert "from main" not in src

    def test_module_no_src_risk(self):
        assert "src.risk" not in self._read(self._SRC)

    def test_script_no_order_tokens(self):
        src = self._read(self._SCRIPT)
        for token in ("place_order", "create_order", "submit_order", "cancel_order"):
            assert token not in src, f"Forbidden token '{token}' in preview script"

    def test_script_no_bybit_executor(self):
        assert "BybitExecutor" not in self._read(self._SCRIPT)


# ---------------------------------------------------------------------------
# E17. No secrets in report JSON/MD
# ---------------------------------------------------------------------------

class TestReportNoSecrets:
    """E17: report files must not contain any secret values."""

    def _make_report(self, monkeypatch) -> tuple[str, str]:
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "SECRET_KEY_E17_SHOULD_NOT_APPEAR")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SECRET_E17_SHOULD_NOT_APPEAR")
        from scripts.preview_demo_close_only_cleanup import _write_report
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_report(plan, Path(tmpdir), "2026-06-06T12:00:00Z")
            json_text = (Path(tmpdir) / "latest_close_only_cleanup.json").read_text(encoding="utf-8")
            md_text   = (Path(tmpdir) / "latest_close_only_cleanup.md").read_text(encoding="utf-8")
        return json_text, md_text

    def test_json_no_api_key(self, monkeypatch):
        j, _ = self._make_report(monkeypatch)
        assert "SECRET_KEY_E17_SHOULD_NOT_APPEAR" not in j

    def test_json_no_api_secret(self, monkeypatch):
        j, _ = self._make_report(monkeypatch)
        assert "SECRET_E17_SHOULD_NOT_APPEAR" not in j

    def test_md_no_api_key(self, monkeypatch):
        _, m = self._make_report(monkeypatch)
        assert "SECRET_KEY_E17_SHOULD_NOT_APPEAR" not in m

    def test_md_no_api_secret(self, monkeypatch):
        _, m = self._make_report(monkeypatch)
        assert "SECRET_E17_SHOULD_NOT_APPEAR" not in m

    def test_plan_secret_observed_false(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.secret_value_observed is False


# ---------------------------------------------------------------------------
# E18. no_position_modified True
# ---------------------------------------------------------------------------

class TestNoPositionModified:
    """E18: no_position_modified is always True."""

    def test_no_position_modified_no_cleanup(self):
        plan = plan_cleanup(10_000.0, 5_000.0, _clean_positions())
        assert plan.no_position_modified is True

    def test_no_position_modified_with_cleanup(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.no_position_modified is True

    def test_order_endpoint_called_false(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.order_endpoint_called is False

    def test_action_type_always_manual_confirmation(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.action_type == "MANUAL_CONFIRMATION_REQUIRED"

    def test_confirmation_required_always_true(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        assert plan.confirmation_required is True


# ---------------------------------------------------------------------------
# E19. main.py / src/risk.py / exchange executor not modified
# ---------------------------------------------------------------------------

class TestRegressionScopeNotModified:
    """E19: TASK-014F must not modify core execution paths."""

    def test_main_py_no_cleanup_import(self):
        main_path = ROOT / "main.py"
        if not main_path.exists():
            pytest.skip("main.py not found")
        src = main_path.read_text(encoding="utf-8", errors="replace")
        assert "demo_close_only_cleanup" not in src

    def test_src_risk_no_cleanup_import(self):
        risk_path = ROOT / "src" / "risk.py"
        if not risk_path.exists():
            pytest.skip("src/risk.py not found")
        src = risk_path.read_text(encoding="utf-8", errors="replace")
        assert "demo_close_only_cleanup" not in src

    def test_cleanup_module_no_main_import(self):
        src = (ROOT / "src" / "demo_close_only_cleanup.py").read_text(encoding="utf-8")
        assert "import main" not in src
        assert "from main" not in src

    def test_cleanup_module_no_risk_import(self):
        src = (ROOT / "src" / "demo_close_only_cleanup.py").read_text(encoding="utf-8")
        assert "src.risk" not in src


# ---------------------------------------------------------------------------
# Additional: write-report integration and to_dict completeness
# ---------------------------------------------------------------------------

class TestReportArtifacts:
    """Verify report files are created correctly."""

    def test_write_report_creates_four_files(self):
        from scripts.preview_demo_close_only_cleanup import _write_report
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_report(plan, Path(tmpdir), "2026-06-06T12:00:00Z")
            files = {f.name for f in Path(tmpdir).iterdir()}
        assert "latest_close_only_cleanup.json" in files
        assert "latest_close_only_cleanup.md"   in files
        ts_json = [n for n in files if n.endswith("_close_only_cleanup.json") and "latest" not in n]
        ts_md   = [n for n in files if n.endswith("_close_only_cleanup.md")   and "latest" not in n]
        assert len(ts_json) == 1
        assert len(ts_md)   == 1

    def test_to_dict_required_fields(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        d = plan.to_dict()
        for f in ("cleanup_needed", "cleanup_reasons", "current_short_count",
                  "current_long_count", "current_open_count",
                  "target_short_count", "proposed_close_count",
                  "suggested_close_candidates", "close_payload_preview",
                  "confirmation_required", "confirm_token_expected_pattern",
                  "confirm_token_valid", "execute_ready",
                  "no_orders_sent", "no_position_modified",
                  "order_endpoint_called", "secret_value_observed"):
            assert f in d, f"Missing field in to_dict(): {f}"

    def test_to_dict_no_secrets(self):
        plan = plan_cleanup(11_404.01, 0.0, _legacy_positions())
        d_str = json.dumps(plan.to_dict())
        assert "api_key" not in d_str.lower()
        assert "api_secret" not in d_str.lower()

    def test_preview_shows_dry_run_header(self, capsys):
        from scripts.preview_demo_close_only_cleanup import run_preview
        run_preview(mode="fixture")
        out = capsys.readouterr().out
        assert "DRY RUN" in out

    def test_legacy_fixture_produces_expected_plan(self):
        """Verify the legacy fixture (real account approximation) gives expected results."""
        from scripts.preview_demo_close_only_cleanup import _FIXTURE_POSITIONS_LEGACY
        plan = plan_cleanup(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_FIXTURE_POSITIONS_LEGACY,
        )
        assert plan.cleanup_needed is True
        assert plan.proposed_close_count == 2
        assert plan.current_short_count == 7
        # Top 2 by stop_risk: ETHUSDT (100), BNBUSDT (80)
        close_symbols = [c.symbol for c in plan.suggested_close_candidates]
        assert "ETHUSDT" in close_symbols
        assert "BNBUSDT" in close_symbols
        # Both payloads are Buy (closing shorts)
        for p in plan.close_payload_previews:
            assert p.close_order_side == "Buy"
            assert p.reduce_only is True

    def test_token_helper_produces_correct_pattern(self):
        d = date(2026, 6, 6)
        assert _expected_confirm_token(d) == "CONFIRM_DEMO_CLOSE_ONLY_20260606"

    def test_snapshot_hash_deterministic(self):
        from src.demo_close_only_cleanup import _compute_snapshot_hash
        positions = _legacy_positions()
        h1 = _compute_snapshot_hash(positions)
        h2 = _compute_snapshot_hash(positions)
        assert h1 == h2
        assert len(h1) == 12   # 12-char hex
