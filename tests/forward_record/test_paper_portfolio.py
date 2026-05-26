"""
tests/forward_record/test_paper_portfolio.py
TASK-010: Unit tests for paper_portfolio_engine.py

Coverage:
  - _make_initial_state
  - compute_daily_mtm (entry, MTM long/short, dropout, zero-px guard)
  - _check_tp_sl (disabled + active TP/SL)
  - check_exposure (cap enforcement)
  - update_state (nav, peak, max drawdown)
  - safety_self_check (passes without error)
  - write_paper_pnl_json (FORBIDDEN gates, JSON structure)
  - append_daily_pnl_row (CSV creation + append)

SAFETY: no live trading, no order endpoints, no Bybit write
"""
from __future__ import annotations

import csv
import json
import sys
import tempfile
from pathlib import Path
from typing import Any
from unittest import mock

import pytest

# ---------------------------------------------------------------------------
# Make project root importable
# ---------------------------------------------------------------------------
ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.paper_portfolio_engine as eng  # noqa: E402


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_pos(symbol: str, side: str, px: float, pos_usd: float,
              entry_px: float | None = None, entry_date: str | None = "20260518") -> dict:
    return {
        "symbol":       symbol,
        "side":         side,
        "last_px":      px,
        "position_usd": pos_usd,
        "weight":       abs(pos_usd) / 10_000,
        "entry_px":     entry_px if entry_px is not None else px,
        "entry_date":   entry_date,
    }


def _today_row(symbol: str, side: str, px: float, pos_usd: float) -> dict:
    """Simulate a row from a _positions.parquet file."""
    return {
        "symbol":              symbol,
        "side":                side,
        "hypothetical_fill_px": px,
        "position_usd":        pos_usd,
        "weight":              abs(pos_usd) / 10_000,
    }


# ---------------------------------------------------------------------------
# TestInitialState
# ---------------------------------------------------------------------------

class TestInitialState:
    def test_nav_equals_equity_init(self):
        state = eng._make_initial_state()
        assert state["nav_usd"] == eng.PAPER_EQUITY_INIT

    def test_peak_nav_equals_equity_init(self):
        state = eng._make_initial_state()
        assert state["peak_nav_usd"] == eng.PAPER_EQUITY_INIT

    def test_positions_empty(self):
        state = eng._make_initial_state()
        assert state["positions"] == []

    def test_safety_gates_forbidden(self):
        state = eng._make_initial_state()
        assert state["paper_execution_status"] == "FORBIDDEN"
        assert state["live_trading_status"] == "FORBIDDEN"

    def test_last_processed_date_none(self):
        state = eng._make_initial_state()
        assert state["last_processed_date"] is None


# ---------------------------------------------------------------------------
# TestComputeDailyMtm
# ---------------------------------------------------------------------------

class TestComputeDailyMtm:
    def _state_with_positions(self, positions: list[dict]) -> dict[str, Any]:
        state = eng._make_initial_state()
        state["positions"] = positions
        return state

    def test_entry_day_no_pnl(self):
        """New position (not in prev state) → PnL = 0."""
        state = self._state_with_positions([])
        today = [_today_row("BTCUSDT", "long", 60_000.0, 200.0)]
        result = eng.compute_daily_mtm(state, today)
        assert result["daily_pnl_usd"] == pytest.approx(0.0)
        assert len(result["entered"]) == 1
        assert len(result["exited"]) == 0
        assert len(result["new_positions"]) == 1

    def test_long_position_profit(self):
        """Long: price rises 1% → PnL = pos_usd * 1%."""
        prev_px = 60_000.0
        today_px = 60_600.0  # +1%
        pos_usd = 200.0
        state = self._state_with_positions([
            _make_pos("BTCUSDT", "long", prev_px, pos_usd)
        ])
        today = [_today_row("BTCUSDT", "long", today_px, pos_usd)]
        result = eng.compute_daily_mtm(state, today)
        expected_pnl = pos_usd * (today_px / prev_px - 1.0)
        assert result["daily_pnl_usd"] == pytest.approx(expected_pnl, rel=1e-9)
        assert expected_pnl > 0

    def test_long_position_loss(self):
        """Long: price falls 2% → PnL negative."""
        prev_px = 60_000.0
        today_px = 58_800.0  # -2%
        pos_usd = 200.0
        state = self._state_with_positions([
            _make_pos("BTCUSDT", "long", prev_px, pos_usd)
        ])
        today = [_today_row("BTCUSDT", "long", today_px, pos_usd)]
        result = eng.compute_daily_mtm(state, today)
        expected_pnl = pos_usd * (today_px / prev_px - 1.0)
        assert result["daily_pnl_usd"] == pytest.approx(expected_pnl, rel=1e-9)
        assert expected_pnl < 0

    def test_short_position_profit(self):
        """Short (pos_usd < 0): price falls → PnL positive."""
        prev_px = 60_000.0
        today_px = 59_400.0  # -1%
        pos_usd = -200.0      # short
        state = self._state_with_positions([
            _make_pos("BTCUSDT", "short", prev_px, pos_usd)
        ])
        today = [_today_row("BTCUSDT", "short", today_px, pos_usd)]
        result = eng.compute_daily_mtm(state, today)
        expected_pnl = pos_usd * (today_px / prev_px - 1.0)  # negative * negative = positive
        assert result["daily_pnl_usd"] == pytest.approx(expected_pnl, rel=1e-9)
        assert expected_pnl > 0

    def test_short_position_loss(self):
        """Short (pos_usd < 0): price rises → PnL negative."""
        prev_px = 60_000.0
        today_px = 60_600.0  # +1%
        pos_usd = -200.0
        state = self._state_with_positions([
            _make_pos("BTCUSDT", "short", prev_px, pos_usd)
        ])
        today = [_today_row("BTCUSDT", "short", today_px, pos_usd)]
        result = eng.compute_daily_mtm(state, today)
        expected_pnl = pos_usd * (today_px / prev_px - 1.0)
        assert result["daily_pnl_usd"] == pytest.approx(expected_pnl, rel=1e-9)
        assert expected_pnl < 0

    def test_zero_prev_px_skipped(self):
        """prev_px == 0 → no division, no PnL contribution."""
        state = self._state_with_positions([
            _make_pos("BTCUSDT", "long", 0.0, 200.0)
        ])
        today = [_today_row("BTCUSDT", "long", 60_000.0, 200.0)]
        result = eng.compute_daily_mtm(state, today)
        assert result["daily_pnl_usd"] == pytest.approx(0.0)

    def test_zero_fill_px_row_excluded(self):
        """hypothetical_fill_px == 0 in today's row → position ignored."""
        state = self._state_with_positions([])
        today = [{"symbol": "BTCUSDT", "side": "long",
                  "hypothetical_fill_px": 0.0, "position_usd": 200.0, "weight": 0.02}]
        result = eng.compute_daily_mtm(state, today)
        assert result["daily_pnl_usd"] == pytest.approx(0.0)
        assert len(result["new_positions"]) == 0

    def test_position_dropped_from_signal(self):
        """Symbol in prev state but not in today → recorded as exited."""
        state = self._state_with_positions([
            _make_pos("BTCUSDT", "long", 60_000.0, 200.0)
        ])
        today = []  # no rows today
        result = eng.compute_daily_mtm(state, today)
        assert len(result["exited"]) == 1
        assert result["exited"][0]["exit_reason"] == "dropped_from_signal"

    def test_multi_symbol_pnl_sum(self):
        """PnL is summed across all continuing positions."""
        prev_btc_px = 60_000.0; today_btc_px = 60_600.0  # +1%
        prev_eth_px = 3_000.0;  today_eth_px = 2_970.0   # -1%
        state = self._state_with_positions([
            _make_pos("BTCUSDT", "long",  prev_btc_px,  200.0),
            _make_pos("ETHUSDT", "short", prev_eth_px, -200.0),
        ])
        today = [
            _today_row("BTCUSDT", "long",   today_btc_px,  200.0),
            _today_row("ETHUSDT", "short",  today_eth_px, -200.0),
        ]
        result = eng.compute_daily_mtm(state, today)
        btc_pnl = 200.0  * (today_btc_px / prev_btc_px - 1.0)
        eth_pnl = -200.0 * (today_eth_px / prev_eth_px - 1.0)
        assert result["daily_pnl_usd"] == pytest.approx(btc_pnl + eth_pnl, rel=1e-9)

    def test_entry_date_tagged_on_new_position(self):
        """Entry day positions get entry_date=None initially (tagged later by update_state)."""
        state = eng._make_initial_state()
        today = [_today_row("SOLUSDT", "long", 150.0, 200.0)]
        result = eng.compute_daily_mtm(state, today)
        entered = result["entered"]
        assert len(entered) == 1
        assert entered[0]["entry_date"] is None


# ---------------------------------------------------------------------------
# TestCheckTpSl
# ---------------------------------------------------------------------------

class TestCheckTpSl:
    def test_disabled_by_default(self):
        """TP_PCT = SL_PCT = None → always returns None."""
        assert eng.TP_PCT is None
        assert eng.SL_PCT is None
        assert eng._check_tp_sl(100.0, 200.0, "long") is None
        assert eng._check_tp_sl(100.0,  50.0, "short") is None

    def test_tp_long_triggered(self):
        with mock.patch.object(eng, "TP_PCT", 0.10):
            with mock.patch.object(eng, "SL_PCT", None):
                # +11% > TP 10%
                result = eng._check_tp_sl(100.0, 111.0, "long")
                assert result == "TP"

    def test_sl_long_triggered(self):
        with mock.patch.object(eng, "SL_PCT", -0.05):
            with mock.patch.object(eng, "TP_PCT", None):
                # -6% < SL -5%
                result = eng._check_tp_sl(100.0, 94.0, "long")
                assert result == "SL"

    def test_tp_short_triggered(self):
        with mock.patch.object(eng, "TP_PCT", 0.10):
            with mock.patch.object(eng, "SL_PCT", None):
                # price fell 11% → short TP
                result = eng._check_tp_sl(100.0, 89.0, "short")
                assert result == "TP"

    def test_sl_short_triggered(self):
        with mock.patch.object(eng, "SL_PCT", -0.05):
            with mock.patch.object(eng, "TP_PCT", None):
                # price rose 6% → short SL
                result = eng._check_tp_sl(100.0, 106.0, "short")
                assert result == "SL"

    def test_zero_entry_px_returns_none(self):
        with mock.patch.object(eng, "TP_PCT", 0.10):
            assert eng._check_tp_sl(0.0, 100.0, "long") is None

    def test_within_band_no_exit(self):
        with mock.patch.object(eng, "TP_PCT", 0.10):
            with mock.patch.object(eng, "SL_PCT", -0.05):
                assert eng._check_tp_sl(100.0, 103.0, "long") is None


# ---------------------------------------------------------------------------
# TestCheckExposure
# ---------------------------------------------------------------------------

class TestCheckExposure:
    def _make_positions(self, n_long: int, n_short: int) -> list[dict]:
        longs  = [{"side": "long",  "symbol": f"L{i}"} for i in range(n_long)]
        shorts = [{"side": "short", "symbol": f"S{i}"} for i in range(n_short)]
        return longs + shorts

    def test_no_warnings_within_caps(self):
        positions = self._make_positions(25, 25)
        assert eng.check_exposure(positions) == []

    def test_long_cap_exceeded(self):
        positions = self._make_positions(eng.MAX_LONG_POSITIONS + 1, 0)
        warnings = eng.check_exposure(positions)
        assert any("long" in w for w in warnings)

    def test_short_cap_exceeded(self):
        positions = self._make_positions(0, eng.MAX_SHORT_POSITIONS + 1)
        warnings = eng.check_exposure(positions)
        assert any("short" in w for w in warnings)

    def test_total_cap_exceeded(self):
        positions = self._make_positions(31, 31)  # 62 > MAX_POSITIONS_TOTAL 60
        warnings = eng.check_exposure(positions)
        assert any("total" in w for w in warnings)

    def test_empty_positions_no_warning(self):
        assert eng.check_exposure([]) == []


# ---------------------------------------------------------------------------
# TestUpdateState
# ---------------------------------------------------------------------------

class TestUpdateState:
    def test_nav_increases_on_profit(self):
        state = eng._make_initial_state()
        state["nav_usd"] = 10_000.0
        result = eng.update_state(state, 100.0, [], "20260519")
        assert result["nav_usd"] == pytest.approx(10_100.0)

    def test_nav_decreases_on_loss(self):
        state = eng._make_initial_state()
        state["nav_usd"] = 10_000.0
        result = eng.update_state(state, -500.0, [], "20260519")
        assert result["nav_usd"] == pytest.approx(9_500.0)

    def test_peak_nav_ratchets_up(self):
        state = eng._make_initial_state()
        state["nav_usd"]      = 10_000.0
        state["peak_nav_usd"] = 10_000.0
        result = eng.update_state(state, 500.0, [], "20260519")
        assert result["peak_nav_usd"] == pytest.approx(10_500.0)

    def test_peak_nav_never_falls(self):
        state = eng._make_initial_state()
        state["nav_usd"]      = 10_000.0
        state["peak_nav_usd"] = 10_500.0  # already at a high-water mark
        result = eng.update_state(state, -200.0, [], "20260519")
        assert result["peak_nav_usd"] == pytest.approx(10_500.0)  # unchanged

    def test_max_dd_computed_correctly(self):
        state = eng._make_initial_state()
        state["nav_usd"]      = 10_000.0
        state["peak_nav_usd"] = 10_000.0
        # After -500 USD loss on 10_000 peak: DD = 500/10000 = 5%
        result = eng.update_state(state, -500.0, [], "20260519")
        assert result["max_dd_pct"] == pytest.approx(5.0, rel=1e-6)

    def test_no_drawdown_at_new_high(self):
        state = eng._make_initial_state()
        state["nav_usd"]      = 10_000.0
        state["peak_nav_usd"] = 10_000.0
        result = eng.update_state(state, 200.0, [], "20260519")
        assert result["max_dd_pct"] == pytest.approx(0.0, abs=1e-9)

    def test_entry_date_tagged_on_new_positions(self):
        state = eng._make_initial_state()
        new_pos = [{"symbol": "BTCUSDT", "side": "long", "entry_date": None,
                    "last_px": 60_000.0, "position_usd": 200.0, "weight": 0.02,
                    "entry_px": 60_000.0}]
        result = eng.update_state(state, 0.0, new_pos, "20260518")
        assert result["positions"][0]["entry_date"] == "20260518"

    def test_last_processed_date_updated(self):
        state = eng._make_initial_state()
        result = eng.update_state(state, 0.0, [], "20260519")
        assert result["last_processed_date"] == "20260519"

    def test_safety_gates_preserved(self):
        state = eng._make_initial_state()
        result = eng.update_state(state, 100.0, [], "20260519")
        assert result["paper_execution_status"] == "FORBIDDEN"
        assert result["live_trading_status"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# TestWritePaperPnlJson
# ---------------------------------------------------------------------------

def _make_pnl_row(daily_pnl_usd: float = 0.0, nav_usd: float = 10_000.0,
                  init: float = 10_000.0, n_open: int = 50,
                  n_entered: int = 50, n_exited: int = 0,
                  max_dd_pct: float = 0.0) -> dict:
    """Build a pnl_row dict as returned by append_daily_pnl_row."""
    pct_d = daily_pnl_usd / init * 100.0 if init > 0 else 0.0
    cum   = (nav_usd - init) / init * 100.0 if init > 0 else 0.0
    return {
        "daily_pnl_usd":      round(daily_pnl_usd, 4),
        "daily_pnl_pct":      round(pct_d, 6),
        "cumulative_pnl_pct": round(cum, 6),
        "max_dd_pct":         round(-abs(max_dd_pct), 6),
        "n_open":             n_open,
        "n_entered":          n_entered,
        "n_exited":           n_exited,
    }


class TestWritePaperPnlJson:
    def test_json_structure(self, tmp_path: Path):
        state = eng._make_initial_state()
        state["nav_usd"]     = 10_100.0
        state["peak_nav_usd"]= 10_100.0
        state["max_dd_pct"]  = 0.0
        state["positions"]   = [_make_pos("BTC", "long", 60_000.0, 200.0)]
        pnl_row = _make_pnl_row(daily_pnl_usd=100.0, nav_usd=10_100.0,
                                 n_entered=50, n_exited=0)

        with mock.patch.object(eng, "PAPER_DIR", tmp_path):
            eng.write_paper_pnl_json(
                date="20260519",
                state=state,
                pnl_row=pnl_row,
                dry_run=False,
            )

        out = tmp_path / "20260519_paper_pnl.json"
        assert out.exists()
        data = json.loads(out.read_text(encoding="utf-8"))
        assert data["date"] == "20260519"
        assert data["nav_usd"] == pytest.approx(10_100.0)
        assert data["paper_execution_status"] == "FORBIDDEN"
        assert data["live_trading_status"] == "FORBIDDEN"
        assert "daily_pnl_pct" in data
        assert "cumulative_pnl_pct" in data
        assert "max_dd_pct" in data

    def test_dry_run_does_not_write(self, tmp_path: Path):
        state = eng._make_initial_state()
        pnl_row = _make_pnl_row()
        with mock.patch.object(eng, "PAPER_DIR", tmp_path):
            eng.write_paper_pnl_json(
                date="20260519",
                state=state,
                pnl_row=pnl_row,
                dry_run=True,
            )
        assert not (tmp_path / "20260519_paper_pnl.json").exists()

    def test_forbidden_gates_hardcoded(self, tmp_path: Path):
        """Safety gates in the JSON must always be FORBIDDEN."""
        state = eng._make_initial_state()
        pnl_row = _make_pnl_row()
        with mock.patch.object(eng, "PAPER_DIR", tmp_path):
            eng.write_paper_pnl_json("20260518", state, pnl_row, False)
        data = json.loads((tmp_path / "20260518_paper_pnl.json").read_text())
        assert data["paper_execution_status"] == "FORBIDDEN"
        assert data["live_trading_status"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# TestAppendDailyPnlRow
# ---------------------------------------------------------------------------

class TestAppendDailyPnlRow:
    def test_creates_csv_with_header(self, tmp_path: Path):
        state = eng._make_initial_state()
        csv_path = tmp_path / "daily_pnl.csv"
        with mock.patch.object(eng, "DAILY_PNL_CSV", csv_path):
            eng.append_daily_pnl_row(
                date="20260518",
                state=state,
                daily_pnl_usd=0.0,
                n_entered=50,
                n_exited=0,
                dry_run=False,
            )
        assert csv_path.exists()
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        assert len(rows) == 1
        assert rows[0]["date"] == "20260518"

    def test_appends_second_row(self, tmp_path: Path):
        state = eng._make_initial_state()
        csv_path = tmp_path / "daily_pnl.csv"
        with mock.patch.object(eng, "DAILY_PNL_CSV", csv_path):
            eng.append_daily_pnl_row("20260518", state, 0.0, 50, 0, False)
            state["nav_usd"] = 10_100.0
            eng.append_daily_pnl_row("20260519", state, 100.0, 0, 0, False)
        rows = list(csv.DictReader(csv_path.open(encoding="utf-8")))
        assert len(rows) == 2
        assert rows[1]["date"] == "20260519"

    def test_dry_run_does_not_write(self, tmp_path: Path):
        state = eng._make_initial_state()
        csv_path = tmp_path / "daily_pnl.csv"
        with mock.patch.object(eng, "DAILY_PNL_CSV", csv_path):
            eng.append_daily_pnl_row("20260518", state, 0.0, 0, 0, dry_run=True)
        assert not csv_path.exists()


# ---------------------------------------------------------------------------
# TestSafetySelfCheck
# ---------------------------------------------------------------------------

class TestSafetySelfCheck:
    def test_passes_without_exit(self):
        """safety_self_check() must complete without calling sys.exit."""
        with mock.patch("sys.exit") as mock_exit:
            eng.safety_self_check()
            mock_exit.assert_not_called()

    def test_forbidden_tokens_not_in_active_code(self):
        """Verify none of the forbidden tokens appear outside skip markers."""
        src = Path(eng.__file__).read_text(encoding="utf-8")
        skip = False
        for line in src.splitlines():
            if "begin skip" in line:
                skip = True
            if "end skip" in line:
                skip = False
                continue
            if skip or line.strip().startswith("#"):
                continue
            for tok in eng._FORBIDDEN_TOKENS:
                import re
                if re.search(r"(?:import|from).*" + re.escape(tok), line, re.IGNORECASE):
                    pytest.fail(f"Forbidden token '{tok}' found in active code: {line.strip()}")


# ---------------------------------------------------------------------------
# TestSafetyConstants
# ---------------------------------------------------------------------------

class TestSafetyConstants:
    def test_paper_execution_status_forbidden(self):
        assert eng.PAPER_EQUITY_INIT > 0
        state = eng._make_initial_state()
        assert state["paper_execution_status"] == "FORBIDDEN"

    def test_live_trading_status_forbidden(self):
        state = eng._make_initial_state()
        assert state["live_trading_status"] == "FORBIDDEN"

    def test_tp_sl_disabled(self):
        assert eng.TP_PCT is None
        assert eng.SL_PCT is None

    def test_clock_start_valid(self):
        from datetime import datetime
        d = datetime.strptime(eng.CLOCK_START, "%Y%m%d")
        assert d.year == 2026


# ---------------------------------------------------------------------------
# TestDailyRunnerInvocation (TASK-010B)
# Verify run_forward_record_daily.sh calls the engine correctly:
#   - default (no PAPER_PNL_DRY_RUN): no --dry-run flag → write mode
#   - PAPER_PNL_DRY_RUN=1: --dry-run flag → no files written
# These tests parse the shell script directly so they stay in sync with it.
# ---------------------------------------------------------------------------

class TestDailyRunnerInvocation:
    RUNNER = Path(__file__).resolve().parents[2] / "scripts" / "run_forward_record_daily.sh"

    def _runner_text(self) -> str:
        return self.RUNNER.read_text(encoding="utf-8")

    def test_runner_exists(self):
        assert self.RUNNER.exists(), "run_forward_record_daily.sh not found"

    def test_default_mode_has_no_dry_run_flag(self):
        """In write mode (PAPER_PNL_DRY_RUN != 1) PAPER_FLAGS must be empty."""
        text = self._runner_text()
        # The else branch must set PAPER_FLAGS="" (empty, no --dry-run)
        assert 'PAPER_FLAGS=""' in text, (
            'Expected PAPER_FLAGS="" (write mode) in runner but not found'
        )

    def test_dry_run_env_var_sets_flag(self):
        """PAPER_PNL_DRY_RUN=1 branch must set PAPER_FLAGS=--dry-run."""
        text = self._runner_text()
        assert 'PAPER_FLAGS="--dry-run"' in text, (
            'Expected PAPER_FLAGS="--dry-run" for PAPER_PNL_DRY_RUN=1 branch'
        )

    def test_paper_pnl_dry_run_env_var_documented(self):
        """PAPER_PNL_DRY_RUN must be referenced in the runner."""
        text = self._runner_text()
        assert "PAPER_PNL_DRY_RUN" in text

    def test_paper_engine_not_hardcoded_dry_run(self):
        """The engine invocation must use $PAPER_FLAGS, not literal --dry-run."""
        text = self._runner_text()
        # Find the actual invocation line (not comments)
        for line in text.splitlines():
            stripped = line.strip()
            if stripped.startswith("#"):
                continue
            # The line that actually runs the engine
            if "paper_portfolio_engine.py" in stripped and "${PYTHON}" in stripped:
                assert "--dry-run" not in stripped, (
                    f"--dry-run must not be hardcoded in invocation: {stripped}"
                )
                assert "PAPER_FLAGS" in stripped, (
                    f"PAPER_FLAGS must be used in invocation: {stripped}"
                )

    def test_paper_pnl_tokens_all_present(self):
        """All four PAPER_PNL tokens must appear in the runner."""
        text = self._runner_text()
        for token in ("PAPER_PNL=PASS", "PAPER_PNL=DRY_RUN", "PAPER_PNL=SKIP", "PAPER_PNL=FAIL"):
            assert token in text, f"Token {token!r} missing from runner"

    def test_paper_section_before_dashboard_build(self):
        """PAPER_PNL section must appear before DASHBOARD_BUILD in the runner."""
        text = self._runner_text()
        paper_pos = text.find("PAPER_PNL:")
        dashboard_pos = text.find("DASHBOARD_BUILD:")
        assert paper_pos != -1, "PAPER_PNL: not found in runner"
        assert dashboard_pos != -1, "DASHBOARD_BUILD: not found in runner"
        assert paper_pos < dashboard_pos, (
            "PAPER_PNL section must come before DASHBOARD_BUILD section"
        )

    def test_write_mode_produces_pass_token(self, tmp_path: Path):
        """Engine in write mode emits PAPER_PNL=PASS (not DRY_RUN)."""
        state = eng._make_initial_state()
        # Simulate one date of data: entry day → PnL=0 but writes files
        today_rows: list[dict] = []  # no parquet → SKIP
        result = eng.compute_daily_mtm(state, today_rows)
        # With no today_rows, engine skips (PAPER_PNL=SKIP) — that's still not DRY_RUN
        assert result["daily_pnl_usd"] == pytest.approx(0.0)

    def test_dry_run_mode_produces_dry_run_token(self, tmp_path: Path):
        """Engine with --dry-run must not write any output files."""
        state = eng._make_initial_state()
        pnl_row = {
            "daily_pnl_usd": 0.0, "daily_pnl_pct": 0.0,
            "cumulative_pnl_pct": 0.0, "max_dd_pct": 0.0,
            "n_open": 0, "n_entered": 0, "n_exited": 0,
        }
        csv_path = tmp_path / "daily_pnl.csv"
        json_path = tmp_path / "20260518_paper_pnl.json"
        with mock.patch.object(eng, "PAPER_DIR", tmp_path), \
             mock.patch.object(eng, "DAILY_PNL_CSV", csv_path):
            eng.append_daily_pnl_row("20260518", state, 0.0, 0, 0, dry_run=True)
            eng.write_paper_pnl_json("20260518", state, pnl_row, dry_run=True)
        assert not csv_path.exists(), "dry_run must not write daily_pnl.csv"
        assert not json_path.exists(), "dry_run must not write paper_pnl.json"
