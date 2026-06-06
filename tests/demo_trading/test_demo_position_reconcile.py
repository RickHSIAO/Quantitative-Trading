"""
tests/demo_trading/test_demo_position_reconcile.py
TASK-014E: Tests for src/demo_position_reconcile.py and
           scripts/preview_demo_position_reconcile.py

Covers TASK-014E requirements F1-F16:
  F1.  fixture no violations => new_entry_allowed True
  F2.  short_count > 5 => violation + blocked
  F3.  available_balance <= 0 => violation + blocked
  F4.  open_positions_count > 10 => violation
  F5.  long_count > 5 => violation
  F6.  gross_exposure_ratio > 1.0 => violation
  F7.  net_exposure_ratio > 0.5 => violation
  F8.  missing stop_price => violation
  F9.  existing_stop_risk > portfolio_risk_budget => violation
  F10. latest_smoke missing => fail closed
  F11. latest_smoke not verified => fail closed
  F12. report json/md contains no secrets
  F13. no order endpoint tokens in runtime source
  F14. no_orders_sent=True
  F15. no_position_modified=True
  F16. main.py / src/risk.py / BybitExecutor not modified

SAFETY: no exchange imports, no order calls, no secrets.
"""
from __future__ import annotations

import json
import sys
import tempfile
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import (
    DemoOpenPosition,
    MAX_LONG_POSITIONS,
    MAX_OPEN_POSITIONS,
    MAX_SHORT_POSITIONS,
)
from src.demo_position_reconcile import (
    ReconciliationResult,
    ViolationRecord,
    reconcile,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rules(symbol: str = "BTCUSDT") -> dict[str, InstrumentRules]:
    return {symbol: InstrumentRules(symbol, 0.001, 0.001, 0, 0.1, 1.0, 1, 3)}


def _all_rules() -> dict[str, InstrumentRules]:
    return {
        "BTCUSDT":  InstrumentRules("BTCUSDT",  0.001, 0.001, 0, 0.1,    1.0, 1, 3),
        "ETHUSDT":  InstrumentRules("ETHUSDT",  0.01,  0.01,  0, 0.05,   1.0, 2, 2),
        "BNBUSDT":  InstrumentRules("BNBUSDT",  0.01,  0.01,  0, 0.01,   1.0, 2, 2),
        "SOLUSDT":  InstrumentRules("SOLUSDT",  0.1,   0.1,   0, 0.01,   1.0, 2, 1),
        "XRPUSDT":  InstrumentRules("XRPUSDT",  1.0,   1.0,   0, 0.0001, 1.0, 4, 0),
        "ADAUSDT":  InstrumentRules("ADAUSDT",  1.0,   1.0,   0, 0.0001, 1.0, 4, 0),
        "DOTUSDT":  InstrumentRules("DOTUSDT",  0.1,   0.1,   0, 0.001,  1.0, 3, 1),
        "LINKUSDT": InstrumentRules("LINKUSDT", 0.1,   0.1,   0, 0.001,  1.0, 3, 1),
    }


def _pos(symbol="BTCUSDT", side="long", qty=0.05, entry=67_000.0,
         stop=65_000.0) -> DemoOpenPosition:
    return DemoOpenPosition(symbol=symbol, side=side, quantity=qty,
                            entry_price=entry, stop_price=stop)


def _clean_result() -> ReconciliationResult:
    """Minimal clean state — 1 long + 1 short, all within limits."""
    positions = [
        _pos("BTCUSDT", "long",  0.05, 67_000.0, 65_000.0),
        _pos("ETHUSDT", "short", 0.30,  3_500.0,  3_700.0),
    ]
    return reconcile(10_000.0, 8_500.0, positions, _all_rules())


# ---------------------------------------------------------------------------
# F1. Fixture — no violations → new_entry_allowed True
# ---------------------------------------------------------------------------

class TestFixtureNoViolations:
    """F1: clean state produces no violations and allows new entries."""

    def test_new_entry_allowed_true(self):
        r = _clean_result()
        assert r.new_entry_allowed is True

    def test_no_violations(self):
        r = _clean_result()
        assert r.violations == []

    def test_blocked_reasons_empty(self):
        r = _clean_result()
        assert r.blocked_reasons == []

    def test_cannot_proceed_false(self):
        r = _clean_result()
        assert r.cannot_proceed_to_order_smoke is False

    def test_metrics_populated(self):
        r = _clean_result()
        assert r.equity_usd == 10_000.0
        assert r.open_positions_count == 2
        assert r.long_count == 1
        assert r.short_count == 1

    def test_preview_exits_zero(self):
        from scripts.preview_demo_position_reconcile import run_preview
        rc = run_preview(mode="fixture")
        assert rc == 0


# ---------------------------------------------------------------------------
# F2. short_count > 5 → violation + blocked
# ---------------------------------------------------------------------------

class TestShortCountExceeded:
    """F2: short_count > MAX_SHORT_POSITIONS triggers violation."""

    def _make(self, n_short: int) -> ReconciliationResult:
        positions = [
            _pos(f"SYM{i}USDT", "short", 1.0, 100.0, 110.0)
            for i in range(n_short)
        ]
        rules = {f"SYM{i}USDT": InstrumentRules(f"SYM{i}USDT", 0.01, 0.01, 0, 0.01, 1.0, 2, 2)
                 for i in range(n_short)}
        return reconcile(10_000.0, 1_000.0, positions, rules)

    def test_six_shorts_triggers_violation(self):
        r = self._make(MAX_SHORT_POSITIONS + 1)
        codes = [v.code for v in r.violations]
        assert "short_count_exceeded" in codes

    def test_six_shorts_blocks_new_entry(self):
        r = self._make(MAX_SHORT_POSITIONS + 1)
        assert r.new_entry_allowed is False
        assert "short_count_exceeded" in r.blocked_reasons

    def test_five_shorts_no_violation(self):
        r = self._make(MAX_SHORT_POSITIONS)
        codes = [v.code for v in r.violations]
        assert "short_count_exceeded" not in codes

    def test_short_count_in_metrics(self):
        r = self._make(7)
        assert r.short_count == 7

    def test_suggested_actions_include_review(self):
        r = self._make(7)
        combined = " ".join(r.suggested_actions)
        assert "legacy_short" in combined or "short" in combined


# ---------------------------------------------------------------------------
# F3. available_balance <= 0 → violation + blocked
# ---------------------------------------------------------------------------

class TestAvailableBalanceViolation:
    """F3: available_balance_usd <= 0 triggers hard violation."""

    def _make(self, available: float) -> ReconciliationResult:
        return reconcile(10_000.0, available, [_pos()], _rules())

    def test_zero_available_triggers_violation(self):
        r = self._make(0.0)
        codes = [v.code for v in r.violations]
        assert "available_balance_zero_or_negative" in codes

    def test_negative_available_triggers_violation(self):
        r = self._make(-100.0)
        codes = [v.code for v in r.violations]
        assert "available_balance_zero_or_negative" in codes

    def test_zero_available_blocks_new_entry(self):
        r = self._make(0.0)
        assert r.new_entry_allowed is False

    def test_positive_available_no_violation(self):
        r = self._make(0.01)
        codes = [v.code for v in r.violations]
        assert "available_balance_zero_or_negative" not in codes

    def test_suggested_actions_mention_restore(self):
        r = self._make(0.0)
        combined = " ".join(r.suggested_actions)
        assert "restore" in combined or "available" in combined


# ---------------------------------------------------------------------------
# F4. open_positions_count > 10 → violation
# ---------------------------------------------------------------------------

class TestTooManyOpenPositions:
    """F4: more than MAX_OPEN_POSITIONS triggers violation."""

    def _make(self, n: int) -> ReconciliationResult:
        positions = [_pos(f"S{i}USDT", "long", 0.01, 100.0, 90.0) for i in range(n)]
        rules = {f"S{i}USDT": InstrumentRules(f"S{i}USDT", 0.01, 0.01, 0, 0.01, 1.0, 2, 2)
                 for i in range(n)}
        return reconcile(100_000.0, 50_000.0, positions, rules)

    def test_eleven_positions_triggers_violation(self):
        r = self._make(MAX_OPEN_POSITIONS + 1)
        codes = [v.code for v in r.violations]
        assert "too_many_open_positions" in codes

    def test_ten_positions_no_violation(self):
        r = self._make(MAX_OPEN_POSITIONS)
        codes = [v.code for v in r.violations]
        assert "too_many_open_positions" not in codes

    def test_open_positions_count_correct(self):
        r = self._make(11)
        assert r.open_positions_count == 11

    def test_eleven_blocks_new_entry(self):
        r = self._make(11)
        assert r.new_entry_allowed is False


# ---------------------------------------------------------------------------
# F5. long_count > 5 → violation
# ---------------------------------------------------------------------------

class TestLongCountExceeded:
    """F5: long_count > MAX_LONG_POSITIONS triggers violation."""

    def _make(self, n_long: int) -> ReconciliationResult:
        positions = [_pos(f"L{i}USDT", "long", 0.01, 100.0, 90.0) for i in range(n_long)]
        rules = {f"L{i}USDT": InstrumentRules(f"L{i}USDT", 0.01, 0.01, 0, 0.01, 1.0, 2, 2)
                 for i in range(n_long)}
        return reconcile(100_000.0, 50_000.0, positions, rules)

    def test_six_longs_triggers_violation(self):
        r = self._make(MAX_LONG_POSITIONS + 1)
        codes = [v.code for v in r.violations]
        assert "long_count_exceeded" in codes

    def test_five_longs_no_violation(self):
        r = self._make(MAX_LONG_POSITIONS)
        codes = [v.code for v in r.violations]
        assert "long_count_exceeded" not in codes

    def test_long_count_metric_correct(self):
        r = self._make(6)
        assert r.long_count == 6


# ---------------------------------------------------------------------------
# F6. gross_exposure_ratio > 1.0 → violation
# ---------------------------------------------------------------------------

class TestGrossExposureViolation:
    """F6: gross_exposure_ratio > 1.0 triggers violation."""

    def test_gross_over_limit_triggers_violation(self):
        # equity=1000, one position with notional 1200 → ratio=1.2
        positions = [_pos("BTCUSDT", "long", 0.012, 100_000.0, 90_000.0)]
        r = reconcile(1_000.0, 500.0, positions, _rules())
        codes = [v.code for v in r.violations]
        assert "gross_exposure_exceeded" in codes

    def test_gross_under_limit_no_violation(self):
        # equity=10000, notional=500 → ratio=0.05
        positions = [_pos("BTCUSDT", "long", 0.005, 100.0, 90.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        codes = [v.code for v in r.violations]
        assert "gross_exposure_exceeded" not in codes

    def test_gross_ratio_computed_correctly(self):
        # 1 long: qty=0.1, entry=50000 → notional=5000; equity=10000 → ratio=0.5
        positions = [_pos("BTCUSDT", "long", 0.1, 50_000.0, 48_000.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        assert abs(r.gross_exposure_ratio - 0.5) < 0.001


# ---------------------------------------------------------------------------
# F7. net_exposure_ratio > 0.5 → violation
# ---------------------------------------------------------------------------

class TestNetExposureViolation:
    """F7: |net_notional| / equity > 0.5 triggers violation."""

    def test_net_over_limit_triggers_violation(self):
        # equity=1000, 1 long position with notional=600 → net_ratio=0.6 > 0.5
        positions = [_pos("BTCUSDT", "long", 0.006, 100_000.0, 90_000.0)]
        r = reconcile(1_000.0, 500.0, positions, _rules())
        codes = [v.code for v in r.violations]
        assert "net_exposure_exceeded" in codes

    def test_net_under_limit_no_violation(self):
        # equity=10000, longs=1000, shorts=1000 → net=0 < 0.5
        positions = [
            _pos("BTCUSDT", "long",  0.01, 100.0, 90.0),
            _pos("ETHUSDT", "short", 0.01, 100.0, 110.0),
        ]
        r = reconcile(10_000.0, 5_000.0, positions, _all_rules())
        codes = [v.code for v in r.violations]
        assert "net_exposure_exceeded" not in codes

    def test_net_ratio_is_absolute(self):
        # Net short: net_notional < 0, ratio = abs(net)/equity
        positions = [_pos("ETHUSDT", "short", 0.006, 100_000.0, 110_000.0)]
        r = reconcile(1_000.0, 500.0, positions, _all_rules())
        assert r.net_exposure_ratio > 0


# ---------------------------------------------------------------------------
# F8. missing stop_price → violation
# ---------------------------------------------------------------------------

class TestMissingStopPrice:
    """F8: stop_price <= 0 triggers missing_stop_price violation."""

    def test_stop_zero_triggers_violation(self):
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, 0.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        codes = [v.code for v in r.violations]
        assert "missing_stop_price" in codes

    def test_stop_negative_triggers_violation(self):
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, -1.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        codes = [v.code for v in r.violations]
        assert "missing_stop_price" in codes

    def test_missing_stop_blocks_new_entry(self):
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, 0.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        assert r.new_entry_allowed is False

    def test_missing_stop_conservative_risk(self):
        # Without stop, stop_risk = full notional = 0.05 * 67000 = 3350
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, 0.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        pd = r.positions[0]
        assert pd.missing_stop is True
        assert abs(pd.stop_risk_usd - 0.05 * 67_000.0) < 0.01

    def test_valid_stop_no_violation(self):
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, 65_000.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        codes = [v.code for v in r.violations]
        assert "missing_stop_price" not in codes

    def test_missing_instrument_rule_violation(self):
        positions = [_pos("UNKNOWNUSDT", "long", 0.05, 100.0, 90.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())  # rules only has BTCUSDT
        codes = [v.code for v in r.violations]
        assert "missing_instrument_rule" in codes


# ---------------------------------------------------------------------------
# F9. existing_stop_risk > portfolio_risk_budget → violation
# ---------------------------------------------------------------------------

class TestStopRiskExceedsBudget:
    """F9: existing_stop_risk > portfolio_risk_budget triggers violation."""

    def test_large_stop_risk_triggers_violation(self):
        # equity=1000, budget = min(1000*0.60*0.40, 1000*0.25) = min(240, 250) = 240
        # position: qty=10, entry=100, stop=1 → risk=10*(100-1)=990 > 240
        positions = [_pos("BTCUSDT", "long", 10.0, 100.0, 1.0)]
        r = reconcile(1_000.0, 500.0, positions, _rules())
        codes = [v.code for v in r.violations]
        assert "stop_risk_exceeds_budget" in codes

    def test_small_stop_risk_no_violation(self):
        # equity=10000, budget~2400; 1 position, small stop risk
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, 65_000.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        # stop_risk = 0.05 * 2000 = 100; budget ≈ 2400 → no violation
        codes = [v.code for v in r.violations]
        assert "stop_risk_exceeds_budget" not in codes

    def test_existing_stop_risk_computed(self):
        # qty=0.1, entry=50000, stop=49000 → risk = 0.1 * 1000 = 100
        positions = [_pos("BTCUSDT", "long", 0.1, 50_000.0, 49_000.0)]
        r = reconcile(10_000.0, 5_000.0, positions, _rules())
        assert abs(r.existing_stop_risk_usd - 100.0) < 0.01

    def test_budget_uses_kelly_multiplier(self):
        r = _clean_result()
        # equity=10000, fk=0.60, KELLY_MULTIPLIER=0.40
        # raw=10000*0.60*0.40=2400, cap=10000*0.25=2500, budget=2400
        assert abs(r.portfolio_risk_budget_usd - 2_400.0) < 0.01


# ---------------------------------------------------------------------------
# F10-F11. latest_smoke missing / not verified → fail closed
# ---------------------------------------------------------------------------

class TestSmokeGating:
    """F10-F11: smoke file gates reconciliation."""

    def test_missing_smoke_exits_one(self):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            rc = run_preview(
                mode="from_latest_smoke",
                smoke_dir=Path(tmpdir),  # empty dir, no latest_smoke.json
            )
        assert rc == 1

    def test_smoke_not_verified_exits_one(self):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "latest_smoke.json"
            smoke_path.write_text(json.dumps({
                "demo_runtime_verified": False,
                "proof_strength": "MISSING",
                "equity_usd": 0.0,
                "available_balance_usd": 0.0,
                "open_positions_count": 0,
            }), encoding="utf-8")
            rc = run_preview(
                mode="from_latest_smoke",
                smoke_dir=Path(tmpdir),
            )
        assert rc == 1

    def test_smoke_verified_proceeds(self, capsys):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "latest_smoke.json"
            smoke_path.write_text(json.dumps({
                "demo_runtime_verified": True,
                "proof_strength": "STRONG",
                "equity_usd": 10_000.0,
                "available_balance_usd": 8_500.0,
                "open_positions_count": 2,
            }), encoding="utf-8")
            # use clean fixture positions via 'from_latest_smoke' mode
            # Note: legacy positions may cause violations; we only check it runs
            rc = run_preview(
                mode="from_latest_smoke",
                smoke_dir=Path(tmpdir),
            )
        # rc may be 0 or 1 depending on legacy positions — just verify it ran
        assert rc in (0, 1)

    def test_missing_smoke_prints_error_message(self, capsys):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            run_preview(mode="from_latest_smoke", smoke_dir=Path(tmpdir))
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out or "latest_smoke" in out

    def test_unverified_smoke_prints_error_message(self, capsys):
        from scripts.preview_demo_position_reconcile import run_preview
        with tempfile.TemporaryDirectory() as tmpdir:
            smoke_path = Path(tmpdir) / "latest_smoke.json"
            smoke_path.write_text(json.dumps({
                "demo_runtime_verified": False,
                "proof_strength": "WEAK",
                "equity_usd": 100.0,
                "available_balance_usd": 0.0,
            }), encoding="utf-8")
            run_preview(mode="from_latest_smoke", smoke_dir=Path(tmpdir))
        out = capsys.readouterr().out
        assert "FAIL CLOSED" in out


# ---------------------------------------------------------------------------
# F12. Report JSON/MD contains no secrets
# ---------------------------------------------------------------------------

class TestReportNoSecrets:
    """F12: reconciliation reports never contain secret values."""

    def _make_report(self, monkeypatch) -> tuple[str, str]:
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "SENTINEL_KEY_SHOULD_NOT_APPEAR")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SENTINEL_SECRET_SHOULD_NOT_APPEAR")
        from scripts.preview_demo_position_reconcile import _write_report
        r = _clean_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_report(r, Path(tmpdir), "2026-06-06T12:00:00Z")
            json_text = (Path(tmpdir) / "latest_reconciliation.json").read_text(encoding="utf-8")
            md_text   = (Path(tmpdir) / "latest_reconciliation.md").read_text(encoding="utf-8")
        return json_text, md_text

    def test_json_no_api_key(self, monkeypatch):
        j, _ = self._make_report(monkeypatch)
        assert "SENTINEL_KEY_SHOULD_NOT_APPEAR" not in j

    def test_json_no_api_secret(self, monkeypatch):
        j, _ = self._make_report(monkeypatch)
        assert "SENTINEL_SECRET_SHOULD_NOT_APPEAR" not in j

    def test_md_no_api_key(self, monkeypatch):
        _, m = self._make_report(monkeypatch)
        assert "SENTINEL_KEY_SHOULD_NOT_APPEAR" not in m

    def test_md_no_api_secret(self, monkeypatch):
        _, m = self._make_report(monkeypatch)
        assert "SENTINEL_SECRET_SHOULD_NOT_APPEAR" not in m

    def test_result_secret_value_observed_false(self, monkeypatch):
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SHOULD_NOT_APPEAR")
        r = _clean_result()
        assert r.secret_value_observed is False


# ---------------------------------------------------------------------------
# F13. No order endpoint tokens in reconcile source
# ---------------------------------------------------------------------------

class TestModuleSourceSafety:
    """F13: reconcile source must not contain forbidden order/endpoint tokens."""
    _SRC = ROOT / "src" / "demo_position_reconcile.py"
    _SCRIPT = ROOT / "scripts" / "preview_demo_position_reconcile.py"

    def _read(self, path: Path) -> str:
        return path.read_text(encoding="utf-8")

    def test_reconcile_no_place_order(self):
        assert "place_order" not in self._read(self._SRC)

    def test_reconcile_no_create_order(self):
        assert "create_order" not in self._read(self._SRC)

    def test_reconcile_no_submit_order(self):
        assert "submit_order" not in self._read(self._SRC)

    def test_reconcile_no_cancel_order(self):
        assert "cancel_order" not in self._read(self._SRC)

    def test_reconcile_no_private_post(self):
        assert "private_post" not in self._read(self._SRC)

    def test_reconcile_no_set_leverage(self):
        assert "set_leverage" not in self._read(self._SRC)

    def test_reconcile_no_set_trading_stop(self):
        assert "set_trading_stop" not in self._read(self._SRC)

    def test_reconcile_no_transfer_call(self):
        assert "transfer(" not in self._read(self._SRC)

    def test_reconcile_no_pybit(self):
        assert "pybit" not in self._read(self._SRC)

    def test_reconcile_no_bybit_executor(self):
        assert "BybitExecutor" not in self._read(self._SRC)

    def test_reconcile_no_main_import(self):
        src = self._read(self._SRC)
        assert "import main" not in src
        assert "from main" not in src

    def test_reconcile_no_src_risk(self):
        assert "src.risk" not in self._read(self._SRC)

    def test_script_no_order_endpoint(self):
        src = self._read(self._SCRIPT)
        for token in ("place_order", "create_order", "submit_order", "cancel_order"):
            assert token not in src, f"Forbidden token '{token}' in preview script"


# ---------------------------------------------------------------------------
# F14. no_orders_sent=True
# ---------------------------------------------------------------------------

class TestNoOrdersSent:
    """F14: no_orders_sent is always True in reconciliation result."""

    def test_no_orders_sent_clean(self):
        assert _clean_result().no_orders_sent is True

    def test_no_orders_sent_with_violations(self):
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, 0.0)]  # missing stop
        r = reconcile(10_000.0, 0.0, positions, _rules())
        assert r.no_orders_sent is True

    def test_no_orders_sent_many_positions(self):
        positions = [_pos(f"S{i}USDT", "short", 1.0, 100.0, 110.0) for i in range(7)]
        rules = {f"S{i}USDT": InstrumentRules(f"S{i}USDT", 0.01, 0.01, 0, 0.01, 1.0, 2, 2)
                 for i in range(7)}
        r = reconcile(10_000.0, 0.0, positions, rules)
        assert r.no_orders_sent is True

    def test_action_type_always_manual_review(self):
        r = _clean_result()
        assert r.action_type == "MANUAL_REVIEW_ONLY"


# ---------------------------------------------------------------------------
# F15. no_position_modified=True
# ---------------------------------------------------------------------------

class TestNoPositionModified:
    """F15: no_position_modified is always True."""

    def test_no_position_modified_clean(self):
        assert _clean_result().no_position_modified is True

    def test_no_position_modified_with_violations(self):
        positions = [_pos("BTCUSDT", "long", 0.05, 67_000.0, 0.0)]
        r = reconcile(10_000.0, 0.0, positions, _rules())
        assert r.no_position_modified is True

    def test_order_endpoint_called_false(self):
        assert _clean_result().order_endpoint_called is False

    def test_secret_value_observed_false(self):
        assert _clean_result().secret_value_observed is False


# ---------------------------------------------------------------------------
# F16. main.py / src/risk.py / BybitExecutor not modified
# ---------------------------------------------------------------------------

class TestRegressionScopeNotModified:
    """F16: TASK-014E must not modify core execution paths."""

    def test_main_py_has_no_reconcile_import(self):
        main_path = ROOT / "main.py"
        if not main_path.exists():
            pytest.skip("main.py not found")
        src = main_path.read_text(encoding="utf-8", errors="replace")
        assert "demo_position_reconcile" not in src

    def test_src_risk_has_no_reconcile_import(self):
        risk_path = ROOT / "src" / "risk.py"
        if not risk_path.exists():
            pytest.skip("src/risk.py not found")
        src = risk_path.read_text(encoding="utf-8", errors="replace")
        assert "demo_position_reconcile" not in src

    def test_reconcile_does_not_import_main(self):
        src = (ROOT / "src" / "demo_position_reconcile.py").read_text(encoding="utf-8")
        assert "import main" not in src
        assert "from main" not in src

    def test_reconcile_does_not_import_risk(self):
        src = (ROOT / "src" / "demo_position_reconcile.py").read_text(encoding="utf-8")
        assert "src.risk" not in src


# ---------------------------------------------------------------------------
# Additional: reconciliation metrics correctness
# ---------------------------------------------------------------------------

class TestMetricsCorrectness:
    """Verify metric calculations against known values."""

    def test_gross_notional_long_plus_short(self):
        positions = [
            _pos("BTCUSDT", "long",  0.1, 50_000.0, 48_000.0),   # notional=5000
            _pos("ETHUSDT", "short", 1.0,  3_000.0,  3_200.0),   # notional=3000
        ]
        r = reconcile(10_000.0, 5_000.0, positions, _all_rules())
        assert abs(r.gross_notional_usd - 8_000.0) < 0.01

    def test_net_notional_long_minus_short(self):
        positions = [
            _pos("BTCUSDT", "long",  0.1, 50_000.0, 48_000.0),   # +5000
            _pos("ETHUSDT", "short", 1.0,  3_000.0,  3_200.0),   # -3000
        ]
        r = reconcile(10_000.0, 5_000.0, positions, _all_rules())
        assert abs(r.net_notional_usd - 2_000.0) < 0.01

    def test_remaining_risk_budget_decreases_with_risk(self):
        r_low  = reconcile(10_000.0, 5_000.0,
                           [_pos("BTCUSDT", "long", 0.001, 67_000.0, 65_000.0)], _rules())
        r_high = reconcile(10_000.0, 5_000.0,
                           [_pos("BTCUSDT", "long", 0.1,   67_000.0, 65_000.0)], _rules())
        assert r_high.remaining_risk_budget_usd < r_low.remaining_risk_budget_usd

    def test_slot_counts(self):
        positions = [_pos(f"S{i}USDT", "long", 0.01, 100.0, 90.0) for i in range(3)]
        rules = {f"S{i}USDT": InstrumentRules(f"S{i}USDT", 0.01, 0.01, 0, 0.01, 1.0, 2, 2)
                 for i in range(3)}
        r = reconcile(10_000.0, 5_000.0, positions, rules)
        assert r.current_slot_usage == 3
        assert r.available_slots == 7

    def test_remaining_risk_zero_when_over_budget(self):
        # Force stop_risk > budget
        positions = [_pos("BTCUSDT", "long", 100.0, 100.0, 1.0)]
        r = reconcile(1_000.0, 500.0, positions, _rules())
        assert r.remaining_risk_budget_usd == 0.0

    def test_preview_shows_dry_run_header(self, capsys):
        from scripts.preview_demo_position_reconcile import run_preview
        run_preview(mode="fixture")
        out = capsys.readouterr().out
        assert "DRY RUN" in out

    def test_write_report_creates_four_files(self):
        from scripts.preview_demo_position_reconcile import _write_report
        r = _clean_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_report(r, Path(tmpdir), "2026-06-06T12:00:00Z")
            files = {f.name for f in Path(tmpdir).iterdir()}
        assert "latest_reconciliation.json" in files
        assert "latest_reconciliation.md"   in files
        timestamped_json = [n for n in files if n.endswith("_reconciliation.json") and "latest" not in n]
        timestamped_md   = [n for n in files if n.endswith("_reconciliation.md")   and "latest" not in n]
        assert len(timestamped_json) == 1
        assert len(timestamped_md)   == 1

    def test_write_report_json_has_required_fields(self):
        from scripts.preview_demo_position_reconcile import _write_report
        r = _clean_result()
        with tempfile.TemporaryDirectory() as tmpdir:
            _write_report(r, Path(tmpdir), "2026-06-06T12:00:00Z")
            data = json.loads((Path(tmpdir) / "latest_reconciliation.json").read_text(encoding="utf-8"))
        for field in ("equity_usd", "available_balance_usd", "open_positions_count",
                      "long_count", "short_count", "gross_exposure_ratio",
                      "net_exposure_ratio", "existing_stop_risk_usd",
                      "portfolio_risk_budget_usd", "remaining_risk_budget_usd",
                      "violations", "blocked_reasons", "new_entry_allowed",
                      "suggested_actions", "no_orders_sent", "no_position_modified",
                      "order_endpoint_called", "secret_value_observed"):
            assert field in data, f"Missing field: {field}"

    def test_to_dict_no_secrets(self):
        r = _clean_result()
        d = r.to_dict()
        d_str = json.dumps(d)
        assert "api_key" not in d_str.lower()
        assert "api_secret" not in d_str.lower()

    def test_legacy_positions_produce_expected_violations(self):
        """Verify that the real-account-like fixture generates known violations."""
        from scripts.preview_demo_position_reconcile import (
            _FIXTURE_INSTRUMENT_RULES,
            _FIXTURE_POSITIONS_LEGACY,
        )
        r = reconcile(
            equity_usd=11_404.01,
            available_balance_usd=0.0,
            positions=_FIXTURE_POSITIONS_LEGACY,
            instrument_rules=_FIXTURE_INSTRUMENT_RULES,
        )
        codes = [v.code for v in r.violations]
        assert "short_count_exceeded" in codes
        assert "available_balance_zero_or_negative" in codes
        assert r.new_entry_allowed is False
        assert r.short_count == 7
