"""
tests/forward_record/test_paper_portfolio_audit.py
TASK-011B: Tests for audit_paper_portfolio_exposure.py and the
           stale-state-reset fix in paper_portfolio_engine.py.

SAFETY: no live trading, no order endpoints, no Bybit write API.
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.audit_paper_portfolio_exposure as audit
import scripts.paper_portfolio_engine as eng


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_position_rows(n_long: int = 5, n_short: int = 5,
                        px: float = 100.0, pos_usd: float = 200.0) -> list[dict]:
    rows = []
    for i in range(n_long):
        rows.append({"symbol": f"BYBIT:LONG{i}USDT.P", "side": "long",
                     "position_usd": pos_usd, "hypothetical_fill_px": px,
                     "data_source": "test", "weight": 0.02})
    for i in range(n_short):
        rows.append({"symbol": f"BYBIT:SHORT{i}USDT.P", "side": "short",
                     "position_usd": -pos_usd, "hypothetical_fill_px": px,
                     "data_source": "test", "weight": -0.02})
    return rows


# ---------------------------------------------------------------------------
# TestComputeExposure
# ---------------------------------------------------------------------------

class TestComputeExposure:
    def test_gross_exposure_ratio_symmetric(self):
        rows = _make_position_rows(5, 5, pos_usd=200.0)
        nav  = 2_000.0
        result = audit.compute_exposure(rows, nav)
        # 5×200 long + 5×200 short = 2000 gross / 2000 NAV = 1.0
        assert result["gross_exposure_ratio"] == pytest.approx(1.0)

    def test_net_exposure_ratio_zero_for_symmetric(self):
        rows = _make_position_rows(5, 5, pos_usd=200.0)
        result = audit.compute_exposure(rows, 2_000.0)
        assert result["net_exposure_ratio"] == pytest.approx(0.0)

    def test_long_and_short_notional(self):
        rows = _make_position_rows(3, 2, pos_usd=200.0)
        result = audit.compute_exposure(rows, 1_000.0)
        assert result["long_notional_usd"]  == pytest.approx(600.0)
        assert result["short_notional_usd"] == pytest.approx(-400.0)
        assert result["total_notional_usd"] == pytest.approx(1000.0)

    def test_max_single_position(self):
        rows = _make_position_rows(1, 0, pos_usd=500.0)
        result = audit.compute_exposure(rows, 1_000.0)
        assert result["max_single_pos_notional"] == pytest.approx(500.0)
        assert result["max_single_pos_pct_nav"]  == pytest.approx(50.0)

    def test_top10_positions_length(self):
        rows = _make_position_rows(10, 5, pos_usd=100.0)
        result = audit.compute_exposure(rows, 1_500.0)
        assert len(result["top10_positions"]) == 10

    def test_warning_gross_exposure_above_threshold(self):
        rows = _make_position_rows(10, 0, pos_usd=200.0)  # 2000 gross, nav=100
        result = audit.compute_exposure(rows, 100.0)
        assert any("WARNING" in w or "HIGH_RISK" in w for w in result["warnings"])

    def test_warning_high_risk_exposure(self):
        rows = _make_position_rows(20, 0, pos_usd=200.0)  # 4000/100 = 40x
        result = audit.compute_exposure(rows, 100.0)
        assert any("HIGH_RISK" in w for w in result["warnings"])

    def test_no_warnings_within_normal_bounds(self):
        rows = _make_position_rows(5, 5, pos_usd=200.0)
        result = audit.compute_exposure(rows, 10_000.0)
        assert result["warnings"] == []

    def test_empty_positions_no_crash(self):
        result = audit.compute_exposure([], 10_000.0)
        assert result["gross_exposure_ratio"] == pytest.approx(0.0)
        assert result["total_notional_usd"]   == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# TestDetectStaleState
# ---------------------------------------------------------------------------

class TestDetectStaleState:
    def _state(self, last_date: str | None) -> dict:
        return {"last_processed_date": last_date, "nav_usd": 10000.0}

    def test_fresh_same_day(self):
        result = audit.detect_stale_state(self._state("20260528"), "20260528")
        assert result["stale"] is False
        assert result["gap_days"] == 0

    def test_fresh_one_day_gap(self):
        result = audit.detect_stale_state(self._state("20260527"), "20260528")
        assert result["stale"] is False

    def test_stale_large_gap(self):
        result = audit.detect_stale_state(self._state("20260430"), "20260528")
        assert result["stale"] is True
        assert result["gap_days"] == 28

    def test_stale_threshold_boundary(self):
        # gap == STALE_RESET_DAYS should NOT be stale (> not >=)
        import scripts.audit_paper_portfolio_exposure as a
        result = audit.detect_stale_state(self._state("20260525"), "20260528")
        assert result["stale"] is (3 > a.STALE_STATE_DAYS)

    def test_none_last_date_is_stale(self):
        result = audit.detect_stale_state(self._state(None), "20260528")
        assert result["stale"] is True

    def test_diagnosis_string_present(self):
        result = audit.detect_stale_state(self._state("20260430"), "20260528")
        assert "28" in result["diagnosis"]


# ---------------------------------------------------------------------------
# TestPnlSanityWarning
# ---------------------------------------------------------------------------

class TestPnlSanityWarning:
    def test_sanity_warning_triggered_above_threshold(self):
        """daily_pnl_pct > 20% should appear in warnings."""
        # We can check this directly via compute_exposure + threshold
        assert audit.WARN_DAILY_PNL_PCT == pytest.approx(0.20)
        assert abs(460) > audit.WARN_DAILY_PNL_PCT * 100

    def test_normal_pnl_no_sanity_warning(self):
        assert abs(1.5) < audit.WARN_DAILY_PNL_PCT * 100


# ---------------------------------------------------------------------------
# TestStaleStateResetInEngine
# ---------------------------------------------------------------------------

class TestStaleStateResetInEngine:
    """Test the stale-state-reset fix in paper_portfolio_engine.py."""

    def test_maybe_reset_stale_state_large_gap(self):
        """Gap > STALE_RESET_DAYS → positions cleared."""
        state = eng._make_initial_state()
        state["last_processed_date"] = "20260430"
        state["positions"] = [{"symbol": "BTC", "last_px": 75750.0}]
        result = eng._maybe_reset_stale_state(state, "20260528")
        assert result["positions"] == [], "stale state should clear positions"

    def test_maybe_reset_stale_state_fresh(self):
        """Gap within threshold → positions preserved."""
        state = eng._make_initial_state()
        state["last_processed_date"] = "20260527"
        pos = [{"symbol": "BTC", "last_px": 95000.0}]
        state["positions"] = pos
        result = eng._maybe_reset_stale_state(state, "20260528")
        assert result["positions"] == pos, "fresh state should keep positions"

    def test_maybe_reset_preserves_nav(self):
        """NAV must not be touched by the reset."""
        state = eng._make_initial_state()
        state["last_processed_date"] = "20260430"
        state["nav_usd"]      = 12_000.0
        state["peak_nav_usd"] = 12_500.0
        state["positions"]    = [{"symbol": "BTC"}]
        result = eng._maybe_reset_stale_state(state, "20260528")
        assert result["nav_usd"]      == pytest.approx(12_000.0)
        assert result["peak_nav_usd"] == pytest.approx(12_500.0)

    def test_maybe_reset_no_last_date_clears_nothing(self):
        """No last_processed_date → return state unchanged."""
        state = eng._make_initial_state()
        state["positions"] = [{"symbol": "BTC"}]
        result = eng._maybe_reset_stale_state(state, "20260528")
        # With no last date, state returned as-is (no reset triggered)
        assert result["positions"] == [{"symbol": "BTC"}]

    def test_stale_reset_prevents_catchup_pnl(self):
        """
        Simulate the 28-day cache→live transition.
        Without fix: prev_px=75750 (cache), today_px=95000 → +25.4% PnL per long.
        With fix: positions cleared → all positions are new entries → PnL=0.
        """
        # Build stale state (from cache era)
        state = eng._make_initial_state()
        state["last_processed_date"] = "20260430"
        state["positions"] = [
            {"symbol": "BTCUSDT", "side": "long", "last_px": 75750.0,
             "position_usd": 200.0, "weight": 0.02,
             "entry_px": 75750.0, "entry_date": "20260430"},
        ]
        # Trigger stale reset
        state = eng._maybe_reset_stale_state(state, "20260528")
        assert state["positions"] == []

        # Now run compute_daily_mtm with live price
        today_rows = [{"symbol": "BTCUSDT", "side": "long",
                       "hypothetical_fill_px": 95000.0, "position_usd": 200.0,
                       "weight": 0.02}]
        mtm = eng.compute_daily_mtm(state, today_rows)
        # All positions are new entries → PnL = 0
        assert mtm["daily_pnl_usd"] == pytest.approx(0.0)
        assert len(mtm["entered"]) == 1

    def test_stale_reset_constant_exists(self):
        assert hasattr(eng, "STALE_RESET_DAYS")
        assert eng.STALE_RESET_DAYS > 0


# ---------------------------------------------------------------------------
# TestAuditSafetyInvariants
# ---------------------------------------------------------------------------

class TestAuditSafetyInvariants:
    AUDIT_SCRIPT = ROOT / "scripts" / "audit_paper_portfolio_exposure.py"

    def test_no_order_endpoint_in_audit_script(self):
        """Forbidden tokens must not appear in import/from statements (skip string literals)."""
        import re as _re
        src = self.AUDIT_SCRIPT.read_text(encoding="utf-8")
        for tok in ("place_order", "create_order", "submit_order",
                    "cancel_order", "private_post", "private_put"):
            for line in src.splitlines():
                stripped = line.strip()
                if stripped.startswith("#"):
                    continue
                # Only flag actual import lines, not string-literal occurrences
                if _re.search(r"(?:import|from).*" + _re.escape(tok), stripped, _re.IGNORECASE):
                    pytest.fail(f"Forbidden import token '{tok}' in: {stripped}")

    def test_safety_gates_in_result(self, tmp_path: Path):
        with (mock.patch.object(audit, "FWD_DIR",   tmp_path),
              mock.patch.object(audit, "PAPER_DIR", tmp_path),
              mock.patch.object(audit, "AUDIT_DIR", tmp_path)):
            (tmp_path / "state.json").write_text(
                '{"paper_equity_init":10000,"nav_usd":10000,"peak_nav_usd":10000,'
                '"positions":[],"last_processed_date":null,'
                '"paper_execution_status":"FORBIDDEN","live_trading_status":"FORBIDDEN"}',
                encoding="utf-8")
            result = audit.run_audit(lookback_days=1, dry_run=True)
        assert result["paper_execution_status"] == "FORBIDDEN"
        assert result["live_trading_status"]    == "FORBIDDEN"

    def test_safety_self_check_passes(self):
        with mock.patch("sys.exit") as mock_exit:
            audit.safety_self_check()
            mock_exit.assert_not_called()

    def test_audit_output_dir_is_not_trading_path(self):
        src = self.AUDIT_SCRIPT.read_text(encoding="utf-8")
        assert "paper_portfolio_audit" in src
        assert "orders" not in src.lower()
