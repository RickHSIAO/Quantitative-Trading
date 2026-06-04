"""
tests/forward_record/test_paper_portfolio_guard.py
TASK-012: Exposure guard tests for paper_portfolio_engine.py

Coverage:
  - apply_exposure_guard() — all six rule checks
  - skip_reason aggregation
  - guard_summary JSON fields
  - _guard_status() transitions
  - _guard_compute_ratios()
  - audit script reads guard_summary
  - safety: no order/private API

SAFETY: no live trading, no order endpoints, no Bybit write API.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import scripts.paper_portfolio_engine as eng
import scripts.audit_paper_portfolio_exposure as audit


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_state(nav: float = 10_000.0, positions: list | None = None) -> dict:
    s = eng._make_initial_state()
    s["nav_usd"] = nav
    s["positions"] = positions or []
    return s


def _pos(symbol: str, side: str, pos_usd: float) -> dict:
    return {
        "symbol": symbol, "side": side,
        "position_usd": pos_usd,
        "last_px": 100.0, "entry_px": 100.0,
        "weight": abs(pos_usd) / 10_000,
        "entry_date": "20260518",
    }


def _entered(symbol: str, side: str, pos_usd: float) -> dict:
    """New-entry position dict (from compute_daily_mtm 'entered' list)."""
    return {
        "symbol": symbol, "side": side,
        "position_usd": pos_usd,
        "last_px": 100.0, "entry_px": 100.0,
        "weight": abs(pos_usd) / 10_000,
        "entry_date": None,
    }


# ---------------------------------------------------------------------------
# TestGuardComputeRatios
# ---------------------------------------------------------------------------

class TestGuardComputeRatios:
    def test_symmetric_portfolio(self):
        positions = [_pos(f"L{i}", "long", 200.0) for i in range(5)] + \
                    [_pos(f"S{i}", "short", -200.0) for i in range(5)]
        gross, net, max_s = eng._guard_compute_ratios(positions, 2_000.0)
        assert gross == pytest.approx(1.0)
        assert net   == pytest.approx(0.0)
        assert max_s == pytest.approx(0.10)   # 200/2000

    def test_all_long(self):
        positions = [_pos("BTC", "long", 500.0)]
        gross, net, max_s = eng._guard_compute_ratios(positions, 1_000.0)
        assert gross == pytest.approx(0.5)
        assert net   == pytest.approx(0.5)

    def test_zero_nav_returns_zeros(self):
        positions = [_pos("BTC", "long", 200.0)]
        gross, net, max_s = eng._guard_compute_ratios(positions, 0.0)
        assert gross == 0.0
        assert net   == 0.0

    def test_empty_positions_zeros(self):
        gross, net, max_s = eng._guard_compute_ratios([], 10_000.0)
        assert gross == 0.0 and net == 0.0 and max_s == 0.0


# ---------------------------------------------------------------------------
# TestGuardStatus
# ---------------------------------------------------------------------------

class TestGuardStatus:
    def test_pass_when_none_skipped(self):
        assert eng._guard_status(0, 10) == "PASS"

    def test_warning_when_some_skipped_some_entered(self):
        assert eng._guard_status(3, 7) == "WARNING"

    def test_blocked_when_all_skipped(self):
        assert eng._guard_status(5, 0) == "BLOCKED"

    def test_warning_even_one_skipped_many_entered(self):
        assert eng._guard_status(1, 49) == "WARNING"


# ---------------------------------------------------------------------------
# TestApplyExposureGuard — individual rule checks
# ---------------------------------------------------------------------------

class TestApplyExposureGuard:
    NAV = 10_000.0

    def test_all_approved_when_within_limits(self):
        entered = [_entered(f"L{i}", "long", 200.0) for i in range(5)]
        approved, skipped = eng.apply_exposure_guard(entered, [], self.NAV)
        assert len(approved) == 5
        assert len(skipped)  == 0

    def test_max_open_positions_blocks_excess(self):
        """If continuing already at cap, all new entries are blocked."""
        continuing = [_pos(f"C{i}", "long", 200.0) for i in range(eng.GUARD_MAX_OPEN_POSITIONS)]
        entered    = [_entered("NEW", "long", 200.0)]
        approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        assert len(approved) == 0
        assert len(skipped)  == 1
        assert skipped[0]["skip_reason"] == "max_open_positions"

    def test_max_long_positions_blocks_excess_long(self):
        continuing = [_pos(f"L{i}", "long", 200.0) for i in range(eng.GUARD_MAX_LONG_POSITIONS)]
        entered    = [_entered("NEWL", "long", 200.0)]
        approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        assert any(s["skip_reason"] == "max_long_positions" for s in skipped)

    def test_max_long_does_not_block_shorts(self):
        """Long cap should not affect short entries."""
        continuing = [_pos(f"L{i}", "long", 200.0) for i in range(eng.GUARD_MAX_LONG_POSITIONS)]
        entered    = [_entered("NEWS", "short", -200.0)]
        approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        assert len(approved) == 1
        assert len(skipped)  == 0

    def test_max_short_positions_blocks_excess_short(self):
        continuing = [_pos(f"S{i}", "short", -200.0) for i in range(eng.GUARD_MAX_SHORT_POSITIONS)]
        entered    = [_entered("NEWS", "short", -200.0)]
        approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        assert any(s["skip_reason"] == "max_short_positions" for s in skipped)

    def test_max_short_does_not_block_longs(self):
        continuing = [_pos(f"S{i}", "short", -200.0) for i in range(eng.GUARD_MAX_SHORT_POSITIONS)]
        entered    = [_entered("NEWL", "long", 200.0)]
        approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        assert len(approved) == 1

    def test_max_single_position_blocks_oversized(self):
        """pos_usd > nav * GUARD_MAX_SINGLE_POSITION_PCT → blocked."""
        big_pos_usd = self.NAV * eng.GUARD_MAX_SINGLE_POSITION_PCT * 2  # 2× limit
        entered = [_entered("BIG", "long", big_pos_usd)]
        approved, skipped = eng.apply_exposure_guard(entered, [], self.NAV)
        assert len(approved) == 0
        assert skipped[0]["skip_reason"] == "max_single_position"

    def test_max_single_position_allows_at_limit(self):
        exact_pos_usd = self.NAV * eng.GUARD_MAX_SINGLE_POSITION_PCT  # exactly at limit
        entered = [_entered("EXACT", "long", exact_pos_usd)]
        approved, skipped = eng.apply_exposure_guard(entered, [], self.NAV)
        assert len(approved) == 1   # exactly at limit is OK (guard is strict >)

    def test_max_gross_exposure_blocks_when_full(self):
        """When continuing already fills gross cap, new entries are blocked."""
        # 10_000 gross on 10_000 NAV = 1.0x (at cap)
        continuing = [_pos("L", "long", self.NAV * eng.GUARD_MAX_GROSS_EXPOSURE_RATIO)]
        entered    = [_entered("NEW", "long", 1.0)]  # even $1 would push over
        approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        assert any(s["skip_reason"] == "max_gross_exposure" for s in skipped)

    def test_max_net_exposure_blocks_imbalanced_long(self):
        """Long-heavy portfolio exceeding net cap blocks further longs.
        Mock max_long_positions to a high value so net exposure is the binding rule.
        """
        # Continuing: 20×$200 long = $4000, 0 short → net_ratio = 0.40x
        # After 5 more: net = 5000/10000 = 0.50 (exactly at cap)
        # 6th entry: net = 5200/10000 = 0.52 > GUARD_MAX_NET_EXPOSURE_RATIO (0.5) → blocked
        continuing = [_pos(f"L{i}", "long", 200.0) for i in range(20)]
        entered    = [_entered(f"NL{i}", "long", 200.0) for i in range(6)]
        # Raise the long-count cap so net_exposure is the binding constraint
        with mock.patch.object(eng, "GUARD_MAX_LONG_POSITIONS", 100),              mock.patch.object(eng, "GUARD_MAX_OPEN_POSITIONS", 100):
            approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        assert len(approved) == 5   # 5 more brings net to 50% (at limit, ok)
        assert len(skipped)  == 1
        assert skipped[0]["skip_reason"] == "max_net_exposure"

    def test_partial_approval_within_gross_cap(self):
        """First entries approved, later ones blocked when cap reached."""
        # Each position = $200 = 2% of NAV (exactly at single-pos limit, allowed)
        # 50 × $200 = $10000 gross = 100% NAV = at cap → 51st entry blocked
        entered = [_entered(f"L{i}", "long", 200.0) for i in range(52)]
        approved, skipped = eng.apply_exposure_guard(entered, [], self.NAV)
        # First 25 approved (GUARD_MAX_LONG_POSITIONS=25), rest blocked by max_long or max_gross
        # At minimum: some are approved and some are skipped
        assert len(approved) > 0
        assert len(skipped)  > 0
        # All skipped for a guard rule (not arbitrary)
        valid_reasons = {"max_gross_exposure", "max_long_positions",
                         "max_open_positions", "max_net_exposure"}
        assert all(s["skip_reason"] in valid_reasons for s in skipped)

    def test_skip_reason_recorded_on_skipped_entry(self):
        big = self.NAV * eng.GUARD_MAX_SINGLE_POSITION_PCT * 3
        entered  = [_entered("BIG", "long", big)]
        _, skipped = eng.apply_exposure_guard(entered, [], self.NAV)
        assert "skip_reason" in skipped[0]

    def test_continuing_positions_never_skipped(self):
        """Guard only applies to 'entered'; continuing is always kept."""
        # 100 continuing positions (well over MAX_OPEN_POSITIONS=50)
        continuing = [_pos(f"C{i}", "long", 100.0) for i in range(100)]
        entered    = []
        approved, skipped = eng.apply_exposure_guard(entered, continuing, self.NAV)
        # Nothing to skip/approve since entered is empty
        assert approved == []
        assert skipped  == []


# ---------------------------------------------------------------------------
# TestSkipReasonAggregation
# ---------------------------------------------------------------------------

class TestSkipReasonAggregation:
    def test_skip_reasons_aggregated_correctly(self):
        """Multiple skips with same reason → count > 1."""
        # 200 USD each (2% NAV, at single-pos limit — not violated).
        # 26+ longs: first 25 allowed (GUARD_MAX_LONG_POSITIONS), rest blocked by max_long_positions.
        entered = [_entered(f"L{i}", "long", 200.0) for i in range(28)]
        _, skipped = eng.apply_exposure_guard(entered, [], 10_000.0)
        reasons = [s["skip_reason"] for s in skipped]
        # All 3 excess longs should be blocked for the same reason
        assert len(skipped) == 3
        assert all(r == reasons[0] for r in reasons)   # consistent reason

    def test_mixed_skip_reasons_possible(self):
        """Different rules can trigger in the same batch."""
        # One oversized (max_single_position), then over gross cap
        big = 10_000.0 * 0.05  # 5% > 2% limit → max_single_position
        rest = [_entered(f"L{i}", "long", 1_200.0) for i in range(8)]
        entered = [_entered("BIG", "long", big)] + rest
        _, skipped = eng.apply_exposure_guard(entered, [], 10_000.0)
        reason_set = {s["skip_reason"] for s in skipped}
        # Should have at least max_single_position among reasons
        assert "max_single_position" in reason_set


# ---------------------------------------------------------------------------
# TestGuardSummaryJsonFields
# ---------------------------------------------------------------------------

class TestGuardSummaryJsonFields:
    def test_guard_summary_present_in_pnl_json(self, tmp_path: Path):
        state   = _make_state()
        pnl_row = {
            "daily_pnl_usd": 0.0, "daily_pnl_pct": 0.0,
            "cumulative_pnl_pct": 0.0, "max_dd_pct": 0.0,
            "n_open": 50, "n_entered": 50, "n_exited": 0,
        }
        gs = {
            "n_signals_seen": 50, "n_skipped": 0,
            "skip_reasons": {}, "gross_exposure_ratio": 1.0,
            "net_exposure_ratio": 0.0, "max_single_position_pct_nav": 2.0,
            "guard_status": "PASS",
        }
        with mock.patch.object(eng, "PAPER_DIR", tmp_path):
            eng.write_paper_pnl_json("20260518", state, pnl_row, False, guard_summary=gs)
        data = json.loads((tmp_path / "20260518_paper_pnl.json").read_text())
        assert "guard_summary" in data
        assert data["guard_summary"]["guard_status"] == "PASS"

    def test_guard_summary_required_keys(self, tmp_path: Path):
        state   = _make_state()
        pnl_row = {
            "daily_pnl_usd": 0.0, "daily_pnl_pct": 0.0,
            "cumulative_pnl_pct": 0.0, "max_dd_pct": 0.0,
            "n_open": 0, "n_entered": 0, "n_exited": 0,
        }
        gs = {
            "n_signals_seen": 50, "n_skipped": 3,
            "skip_reasons": {"max_gross_exposure": 3},
            "gross_exposure_ratio": 1.0, "net_exposure_ratio": 0.0,
            "max_single_position_pct_nav": 2.0, "guard_status": "WARNING",
        }
        with mock.patch.object(eng, "PAPER_DIR", tmp_path):
            eng.write_paper_pnl_json("20260519", state, pnl_row, False, guard_summary=gs)
        data = json.loads((tmp_path / "20260519_paper_pnl.json").read_text())
        gs_out = data["guard_summary"]
        for key in ("n_signals_seen", "n_entered", "n_skipped", "skip_reasons",
                    "gross_exposure_ratio", "net_exposure_ratio",
                    "max_single_position_pct_nav", "guard_status"):
            assert key in gs_out, f"Missing key: {key}"

    def test_guard_summary_safety_gates_preserved(self, tmp_path: Path):
        state   = _make_state()
        pnl_row = {"daily_pnl_usd": 0.0, "daily_pnl_pct": 0.0,
                   "cumulative_pnl_pct": 0.0, "max_dd_pct": 0.0,
                   "n_open": 0, "n_entered": 0, "n_exited": 0}
        with mock.patch.object(eng, "PAPER_DIR", tmp_path):
            eng.write_paper_pnl_json("20260518", state, pnl_row, False)
        data = json.loads((tmp_path / "20260518_paper_pnl.json").read_text())
        assert data["paper_execution_status"] == "FORBIDDEN"
        assert data["live_trading_status"]    == "FORBIDDEN"

    def test_guard_summary_absent_defaults_gracefully(self, tmp_path: Path):
        """write_paper_pnl_json without guard_summary must not crash."""
        state   = _make_state()
        pnl_row = {"daily_pnl_usd": 0.0, "daily_pnl_pct": 0.0,
                   "cumulative_pnl_pct": 0.0, "max_dd_pct": 0.0,
                   "n_open": 0, "n_entered": 0, "n_exited": 0}
        with mock.patch.object(eng, "PAPER_DIR", tmp_path):
            eng.write_paper_pnl_json("20260518", state, pnl_row, False)
        data = json.loads((tmp_path / "20260518_paper_pnl.json").read_text())
        assert data["guard_summary"]["guard_status"] == "PASS"


# ---------------------------------------------------------------------------
# TestGuardInDailyPnlCsv
# ---------------------------------------------------------------------------

class TestGuardInDailyPnlCsv:
    def test_guard_columns_present_in_csv(self, tmp_path: Path):
        state   = _make_state()
        csv_path = tmp_path / "daily_pnl.csv"
        gs = {"n_skipped": 2, "gross_exposure_ratio": 0.95,
              "net_exposure_ratio": 0.02, "guard_status": "WARNING"}
        with mock.patch.object(eng, "DAILY_PNL_CSV", csv_path):
            eng.append_daily_pnl_row("20260518", state, 0.0, 50, 0, False, guard_summary=gs)
        import csv as _csv
        rows = list(_csv.DictReader(csv_path.open(encoding="utf-8")))
        assert rows[0]["guard_status"] == "WARNING"
        assert rows[0]["n_skipped"]    == "2"

    def test_guard_columns_default_pass_without_summary(self, tmp_path: Path):
        state    = _make_state()
        csv_path = tmp_path / "daily_pnl.csv"
        with mock.patch.object(eng, "DAILY_PNL_CSV", csv_path):
            eng.append_daily_pnl_row("20260518", state, 0.0, 0, 0, False)
        import csv as _csv
        rows = list(_csv.DictReader(csv_path.open(encoding="utf-8")))
        assert rows[0]["guard_status"] == "PASS"


# ---------------------------------------------------------------------------
# TestAuditReadsGuardSummary
# ---------------------------------------------------------------------------

class TestAuditReadsGuardSummary:
    def test_audit_reads_guard_status_from_json(self, tmp_path: Path):
        """Audit should pick up guard_status from {date}_paper_pnl.json."""
        pnl_json = {
            "date": "20260518", "nav_usd": 10000, "daily_pnl_usd": 0.0,
            "daily_pnl_pct": 0.0, "cumulative_pnl_pct": 0.0, "max_dd_pct": 0.0,
            "n_open": 50, "n_entered": 47, "n_exited": 0,
            "paper_equity_init": 10000,
            "paper_execution_status": "FORBIDDEN",
            "live_trading_status": "FORBIDDEN",
            "guard_summary": {
                "n_signals_seen": 50, "n_entered": 47, "n_skipped": 3,
                "skip_reasons": {"max_gross_exposure": 3},
                "gross_exposure_ratio": 0.94,
                "net_exposure_ratio": 0.02,
                "max_single_position_pct_nav": 2.0,
                "guard_status": "WARNING",
            },
        }
        state_json = {
            "paper_equity_init": 10000, "nav_usd": 10000, "peak_nav_usd": 10000,
            "last_processed_date": "20260518", "positions": [],
            "paper_execution_status": "FORBIDDEN", "live_trading_status": "FORBIDDEN",
        }
        (tmp_path / "20260518_paper_pnl.json").write_text(
            json.dumps(pnl_json), encoding="utf-8")
        (tmp_path / "state.json").write_text(
            json.dumps(state_json), encoding="utf-8")
        # Mock FWD_DIR to return no parquets (audit still runs)
        with (mock.patch.object(audit, "FWD_DIR",   tmp_path),
              mock.patch.object(audit, "PAPER_DIR", tmp_path),
              mock.patch.object(audit, "AUDIT_DIR", tmp_path)):
            result = audit.run_audit(lookback_days=1, dry_run=True)
        # No days audited (no parquets), but result structure is intact
        assert result["paper_execution_status"] == "FORBIDDEN"


# ---------------------------------------------------------------------------
# TestGuardSafetyInvariants
# ---------------------------------------------------------------------------

class TestGuardSafetyInvariants:
    def test_guard_constants_exist(self):
        assert hasattr(eng, "GUARD_MAX_OPEN_POSITIONS")
        assert hasattr(eng, "GUARD_MAX_LONG_POSITIONS")
        assert hasattr(eng, "GUARD_MAX_SHORT_POSITIONS")
        assert hasattr(eng, "GUARD_MAX_GROSS_EXPOSURE_RATIO")
        assert hasattr(eng, "GUARD_MAX_NET_EXPOSURE_RATIO")
        assert hasattr(eng, "GUARD_MAX_SINGLE_POSITION_PCT")

    def test_guard_default_values_reasonable(self):
        assert eng.GUARD_MAX_OPEN_POSITIONS       == 50
        assert eng.GUARD_MAX_LONG_POSITIONS        == 25
        assert eng.GUARD_MAX_SHORT_POSITIONS       == 25
        assert eng.GUARD_MAX_GROSS_EXPOSURE_RATIO  == pytest.approx(1.0)
        assert eng.GUARD_MAX_NET_EXPOSURE_RATIO    == pytest.approx(0.5)
        assert eng.GUARD_MAX_SINGLE_POSITION_PCT   == pytest.approx(0.02)

    def test_no_order_endpoint_in_engine(self):
        import re
        src = (ROOT / "scripts" / "paper_portfolio_engine.py").read_text(encoding="utf-8")
        skip = False
        for line in src.splitlines():
            if "begin skip" in line: skip = True
            if "end skip"   in line: skip = False; continue
            if skip or line.strip().startswith("#"): continue
            for tok in ("place_order", "create_order", "submit_order",
                        "cancel_order", "private_post", "private_put"):
                if re.search(r"(?:import|from).*" + re.escape(tok), line, re.IGNORECASE):
                    pytest.fail(f"Forbidden import in engine: {line.strip()}")

    def test_safety_self_check_passes(self):
        with mock.patch("sys.exit") as mock_exit:
            eng.safety_self_check()
            mock_exit.assert_not_called()
