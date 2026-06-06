"""
tests/demo_trading/test_demo_runtime_adapter.py
TASK-014C: Tests for src/demo_runtime_adapter.py and
           scripts/preview_demo_readonly_runtime.py

Covers TASK-014C requirements 6-23:
  6.  config demo true + runtime proof missing => fail_closed
  7.  config demo false => fail_closed
  8.  demo endpoint proof true => verified
  9.  live endpoint detected => fail_closed
  10. account response ambiguous => fail_closed
  11. wallet balance -> equity / available balance
  12. open positions -> planner positions
  13. missing stop_price => fail closed
  14. instrument info -> InstrumentRules
  15. missing instrument info => rejected by rounding
  16. fixture mode runs and prints DRY RUN / NO ORDERS SENT
  17. unverified mode exits nonzero
  18. verified fixture mode exits zero
  19. no secrets in output
  20. no order endpoint called
  21. proposal passes invariants after rounding
  22. tests/demo_trading all PASS (ensured by running this suite)
  23. main.py / src/risk.py / BybitExecutor not modified

SAFETY: no exchange imports, no order calls, no secrets.
"""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.demo_instrument_rules import InstrumentRules, apply_instrument_rules_to_proposal
from src.demo_portfolio_risk import DemoOpenPosition, DemoSignalCandidate
from src.demo_readonly_client import (
    DEMO_BASE_URL,
    FIXTURE_INSTRUMENTS,
    FIXTURE_POSITIONS,
    FIXTURE_RUNTIME_PROOF,
    FIXTURE_WALLET,
    InstrumentSnapshot,
    PositionSnapshot,
    RuntimeProofSnapshot,
    WalletSnapshot,
)
from src.demo_runtime_adapter import (
    AdaptedPlannerInput,
    adapt_all,
    adapt_instruments,
    adapt_positions,
    adapt_runtime_proof,
    adapt_wallet,
)
from src.demo_runtime_probe import (
    DEMO_ENDPOINT_FAMILIES,
    FAIL_CONFIG_FALSE,
    FAIL_NO_PROOF,
    probe_demo_runtime,
)


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _wallet(equity=10_000.0, available=8_500.0) -> WalletSnapshot:
    return WalletSnapshot(
        equity_usd=equity, available_balance_usd=available,
        wallet_balance_usd=equity, account_type="UNIFIED", api_key_present=False,
    )


def _pos(symbol="BTCUSDT", side="long", qty=0.05, entry=67_000.0,
         stop=65_000.0) -> PositionSnapshot:
    return PositionSnapshot(
        symbol=symbol, side=side, quantity=qty,
        entry_price=entry, stop_price=stop,
        unrealised_pnl=0.0, leverage=2.0,
    )


def _snap(symbol="BTCUSDT") -> InstrumentSnapshot:
    return InstrumentSnapshot(symbol, 0.001, 0.001, 0, 0.1, 1.0, 1, 3)


def _good_proof(**kwargs) -> RuntimeProofSnapshot:
    defaults = dict(
        account_mode="demo", demo_flag=True,
        endpoint_family="bybit_demo", source="fixture",
        base_url_used=DEMO_BASE_URL, live_endpoint_fallback_detected=False,
    )
    defaults.update(kwargs)
    return RuntimeProofSnapshot(**defaults)


# ---------------------------------------------------------------------------
# 11. Wallet -> equity / available balance
# ---------------------------------------------------------------------------

class TestAdaptWallet:
    def test_equity_extracted(self):
        equity, _ = adapt_wallet(_wallet(equity=12_345.0))
        assert equity == 12_345.0

    def test_available_extracted(self):
        _, available = adapt_wallet(_wallet(available=7_000.0))
        assert available == 7_000.0

    def test_zero_wallet(self):
        equity, available = adapt_wallet(_wallet(0, 0))
        assert equity == 0.0
        assert available == 0.0

    def test_wallet_equity_gte_available(self):
        w = _wallet(10_000, 8_000)
        equity, available = adapt_wallet(w)
        assert equity >= available


# ---------------------------------------------------------------------------
# 12. Open positions -> planner positions
# ---------------------------------------------------------------------------

class TestAdaptPositions:
    def test_long_position_converted(self):
        positions, missing = adapt_positions([_pos("BTCUSDT", "long")])
        assert len(positions) == 1
        assert positions[0].side == "long"
        assert positions[0].symbol == "BTCUSDT"

    def test_short_position_converted(self):
        positions, _ = adapt_positions([_pos("ETHUSDT", "short")])
        assert positions[0].side == "short"

    def test_stop_price_preserved(self):
        positions, _ = adapt_positions([_pos(stop=65_000.0)])
        assert positions[0].stop_price == 65_000.0

    def test_quantity_preserved(self):
        positions, _ = adapt_positions([_pos(qty=0.123)])
        assert positions[0].quantity == 0.123

    def test_entry_price_preserved(self):
        positions, _ = adapt_positions([_pos(entry=70_000.0)])
        assert positions[0].entry_price == 70_000.0

    def test_empty_input_returns_empty(self):
        positions, missing = adapt_positions([])
        assert positions == []
        assert missing == []

    def test_no_missing_when_all_stops_present(self):
        snaps = [_pos("BTC", stop=60_000.0), _pos("ETH", stop=3_000.0)]
        _, missing = adapt_positions(snaps)
        assert missing == []

    def test_returns_demo_open_position_type(self):
        positions, _ = adapt_positions([_pos()])
        assert isinstance(positions[0], DemoOpenPosition)


# ---------------------------------------------------------------------------
# 13. missing stop_price => fail closed
# ---------------------------------------------------------------------------

class TestMissingStopPrice:
    def test_missing_stop_sets_stop_to_zero(self):
        snap = PositionSnapshot("BTCUSDT", "long", 0.05, 67_000.0, None, 0.0, 2.0)
        positions, _ = adapt_positions([snap])
        assert positions[0].stop_price == 0.0

    def test_missing_stop_in_missing_list(self):
        snap = PositionSnapshot("BTCUSDT", "long", 0.05, 67_000.0, None, 0.0, 2.0)
        _, missing = adapt_positions([snap])
        assert "BTCUSDT" in missing

    def test_adapt_all_missing_stop_fail_closed(self):
        bad_pos = PositionSnapshot("BTCUSDT", "long", 0.05, 67_000.0, None, 0.0, 2.0)
        result = adapt_all(_wallet(), [bad_pos], {}, _good_proof())
        assert result.fail_closed is True

    def test_adapt_all_missing_stop_in_fail_reasons(self):
        bad_pos = PositionSnapshot("BTCUSDT", "long", 0.05, 67_000.0, None, 0.0, 2.0)
        result = adapt_all(_wallet(), [bad_pos], {}, _good_proof())
        assert any("missing_stop_price" in r for r in result.fail_reasons)

    def test_missing_stop_not_treated_as_zero_risk(self):
        snap = PositionSnapshot("BTC", "long", 1.0, 60_000.0, None, 0.0, 1.0)
        positions, missing = adapt_positions([snap])
        assert positions[0].stop_price <= 0
        # Phase 2 will use full notional (not zero) for stop risk
        assert positions[0].quantity > 0

    def test_partial_missing_stop_still_fail_closed(self):
        good = _pos("ETHUSDT", stop=3_000.0)
        bad  = PositionSnapshot("BTCUSDT", "long", 0.05, 67_000.0, None, 0.0, 2.0)
        result = adapt_all(_wallet(), [good, bad], {}, _good_proof())
        assert result.fail_closed is True
        assert "BTCUSDT" in result.positions_with_missing_stop

    def test_no_missing_stops_not_fail_closed_by_positions(self):
        result = adapt_all(_wallet(), [_pos(stop=60_000.0)], {}, _good_proof())
        assert "missing_stop_price: BTCUSDT" not in result.fail_reasons


# ---------------------------------------------------------------------------
# 14. Instrument info -> InstrumentRules
# ---------------------------------------------------------------------------

class TestAdaptInstruments:
    def test_single_snapshot_converted(self):
        rules = adapt_instruments({"BTCUSDT": _snap("BTCUSDT")})
        assert "BTCUSDT" in rules
        assert isinstance(rules["BTCUSDT"], InstrumentRules)

    def test_qty_step_preserved(self):
        snap = InstrumentSnapshot("X", 0.01, 0.01, 0, 0.001, 1.0, 3, 2)
        rules = adapt_instruments({"X": snap})
        assert rules["X"].qty_step == 0.01

    def test_tick_size_preserved(self):
        snap = InstrumentSnapshot("X", 0.01, 0.01, 0, 0.005, 1.0, 3, 2)
        rules = adapt_instruments({"X": snap})
        assert rules["X"].tick_size == 0.005

    def test_is_valid_after_adaptation(self):
        snap = InstrumentSnapshot("ETHUSDT", 0.01, 0.01, 0, 0.05, 1.0, 2, 2)
        rules = adapt_instruments({"ETHUSDT": snap})
        ok, msg = rules["ETHUSDT"].is_valid()
        assert ok, msg

    def test_empty_input_returns_empty(self):
        assert adapt_instruments({}) == {}

    def test_all_fixture_instruments_converted_and_valid(self):
        rules = adapt_instruments(FIXTURE_INSTRUMENTS)
        assert len(rules) == len(FIXTURE_INSTRUMENTS)
        for sym, r in rules.items():
            ok, msg = r.is_valid()
            assert ok, f"{sym}: {msg}"

    def test_all_fields_preserved(self):
        snap = InstrumentSnapshot("SOL", 0.1, 0.1, 0, 0.01, 1.0, 2, 1)
        r = adapt_instruments({"SOL": snap})["SOL"]
        assert r.min_qty == snap.min_qty
        assert r.max_qty == snap.max_qty
        assert r.min_notional == snap.min_notional
        assert r.price_precision == snap.price_precision
        assert r.qty_precision == snap.qty_precision


# ---------------------------------------------------------------------------
# 15. Missing instrument => rejected by rounding
# ---------------------------------------------------------------------------

class TestMissingInstrumentRejected:
    def test_unknown_symbol_not_in_rules(self):
        rules = adapt_instruments({"BTCUSDT": _snap("BTCUSDT")})
        assert "UNKNOWN123" not in rules

    def test_apply_rules_none_gives_rejection(self):
        class _P:
            symbol = "UNKNOWN"; side = "long"; score = 0.5; rank = 1
            quantity = 1.0; entry_price = 100.0; stop_price = 90.0
            proposed_notional_usd = 100.0; allocated_stop_risk_usd = 10.0

        from src.demo_instrument_rules import REJECT_MISSING_RULE
        rp = apply_instrument_rules_to_proposal(_P(), None)
        assert rp.accepted is False
        assert rp.reject_reason == REJECT_MISSING_RULE

    def test_adapt_all_missing_instrument_in_list(self):
        result = adapt_all(
            _wallet(), [], {"ETHUSDT": _snap("ETHUSDT")}, _good_proof(),
            symbols=["ETHUSDT", "MISSING_SYM"],
        )
        assert "MISSING_SYM" in result.missing_instrument_symbols


# ---------------------------------------------------------------------------
# Runtime proof adaptation
# ---------------------------------------------------------------------------

class TestAdaptRuntimeProof:
    def test_valid_fixture_proof_converted(self):
        proof = adapt_runtime_proof(_good_proof())
        assert proof is not None
        assert proof.account_mode == "demo"
        assert proof.demo_flag is True
        assert proof.endpoint_family == "bybit_demo"

    def test_live_endpoint_detected_returns_none(self):
        snap = _good_proof(live_endpoint_fallback_detected=True)
        assert adapt_runtime_proof(snap) is None

    def test_empty_account_mode_returns_none(self):
        snap = _good_proof(account_mode="")
        assert adapt_runtime_proof(snap) is None

    def test_empty_endpoint_family_returns_none(self):
        snap = _good_proof(endpoint_family="")
        assert adapt_runtime_proof(snap) is None

    def test_unknown_endpoint_family_returns_none(self):
        snap = _good_proof(endpoint_family="unknown")
        assert adapt_runtime_proof(snap) is None

    def test_all_recognised_families_convert(self):
        for ef in DEMO_ENDPOINT_FAMILIES:
            snap = _good_proof(endpoint_family=ef)
            proof = adapt_runtime_proof(snap)
            assert proof is not None, f"Expected proof for endpoint_family={ef!r}"


# ---------------------------------------------------------------------------
# 6-10. Demo verification via probe_demo_runtime (through adapter)
# ---------------------------------------------------------------------------

class TestDemoVerificationViaAdapter:
    """Req 6-10: tests using probe_demo_runtime with adapted proofs."""

    def test_req6_config_true_no_proof_fail_closed(self):
        """Req 6: config demo=True + runtime proof missing => fail_closed."""
        result = probe_demo_runtime(demo_config_expected=True, runtime_proof=None)
        assert result.fail_closed is True
        assert result.demo_runtime_verified is False
        assert result.failure_reason == FAIL_NO_PROOF

    def test_req7_config_false_fail_closed(self):
        """Req 7: config demo=False => fail_closed regardless of proof."""
        result = probe_demo_runtime(demo_config_expected=False, runtime_proof=None)
        assert result.fail_closed is True
        assert result.failure_reason == FAIL_CONFIG_FALSE

    def test_req8_demo_endpoint_proof_verified(self):
        """Req 8: valid demo endpoint proof => verified."""
        snap  = _good_proof()
        proof = adapt_runtime_proof(snap)
        assert proof is not None
        result = probe_demo_runtime(demo_config_expected=True, runtime_proof=proof)
        assert result.demo_runtime_verified is True
        assert result.fail_closed is False

    def test_req9_live_endpoint_detected_fail_closed(self):
        """Req 9: live endpoint detected in snapshot => adapt returns None => fail_closed."""
        snap  = _good_proof(live_endpoint_fallback_detected=True)
        proof = adapt_runtime_proof(snap)
        assert proof is None
        result = probe_demo_runtime(demo_config_expected=True, runtime_proof=proof)
        assert result.fail_closed is True

    def test_req10_ambiguous_proof_fail_closed(self):
        """Req 10: ambiguous account response => unknown endpoint => proof=None => fail_closed."""
        snap  = _good_proof(endpoint_family="unknown", account_mode="unknown", demo_flag=False)
        proof = adapt_runtime_proof(snap)
        assert proof is None
        result = probe_demo_runtime(demo_config_expected=True, runtime_proof=proof)
        assert result.fail_closed is True


# ---------------------------------------------------------------------------
# adapt_all integration
# ---------------------------------------------------------------------------

class TestAdaptAll:
    def test_happy_path_not_fail_closed(self):
        result = adapt_all(_wallet(), [_pos(stop=60_000.0)],
                           {"BTCUSDT": _snap("BTCUSDT")}, _good_proof())
        assert result.fail_closed is False
        assert result.fail_reasons == []

    def test_missing_stop_sets_fail_closed(self):
        bad_pos = PositionSnapshot("BTC", "long", 0.05, 67_000.0, None, 0.0, 2.0)
        result = adapt_all(_wallet(), [bad_pos], {}, _good_proof())
        assert result.fail_closed is True

    def test_live_endpoint_sets_fail_closed(self):
        snap = _good_proof(live_endpoint_fallback_detected=True)
        result = adapt_all(_wallet(), [], {}, snap)
        assert result.fail_closed is True
        assert "live_endpoint_fallback_detected" in result.fail_reasons

    def test_unknown_endpoint_family_sets_fail_closed(self):
        snap = _good_proof(endpoint_family="production_live")
        result = adapt_all(_wallet(), [], {}, snap)
        assert result.fail_closed is True
        assert "cannot_construct_runtime_proof" in result.fail_reasons

    def test_equity_propagated(self):
        result = adapt_all(_wallet(equity=9_999.0), [], {}, _good_proof())
        assert result.equity_usd == 9_999.0

    def test_available_propagated(self):
        result = adapt_all(_wallet(available=7_777.0), [], {}, _good_proof())
        assert result.available_balance_usd == 7_777.0

    def test_instrument_rules_populated(self):
        result = adapt_all(_wallet(), [], {"BTCUSDT": _snap("BTCUSDT")}, _good_proof())
        assert "BTCUSDT" in result.instrument_rules

    def test_runtime_proof_populated(self):
        result = adapt_all(_wallet(), [], {}, _good_proof())
        assert result.runtime_proof is not None


# ---------------------------------------------------------------------------
# 16-21. Preview script tests
# ---------------------------------------------------------------------------

class TestPreviewScript:
    """Req 16-21."""

    def _run(self, **kwargs):
        from scripts.preview_demo_readonly_runtime import run_preview
        return run_preview(**kwargs)

    def test_req16_fixture_mode_prints_dry_run(self, capsys):
        """Req 16: fixture mode prints DRY RUN / NO ORDERS SENT."""
        self._run(use_real_network=False)
        out = capsys.readouterr().out
        assert "DRY RUN / NO ORDERS SENT" in out

    def test_req18_verified_fixture_exits_zero(self):
        """Req 18: verified fixture mode exits zero."""
        rc = self._run(use_real_network=False)
        assert rc == 0

    def test_req17_unverified_exits_nonzero(self, monkeypatch):
        """Req 17: unverified mode exits nonzero."""
        import src.demo_readonly_client as drc
        # Return a proof that will fail runtime verification
        bad_snap = RuntimeProofSnapshot(
            account_mode="",
            demo_flag=False,
            endpoint_family="",
            source="test",
            base_url_used="",
            live_endpoint_fallback_detected=False,
        )
        monkeypatch.setattr(
            drc.DemoReadOnlyClient, "build_runtime_proof", lambda self: bad_snap
        )
        rc = self._run(use_real_network=False)
        assert rc == 1

    def test_req19_no_secrets_in_output(self, capsys, monkeypatch):
        """Req 19: no secrets in output."""
        monkeypatch.setenv("BYBIT_DEMO_API_KEY",    "SENTINEL_KEY_VALUE_999")
        monkeypatch.setenv("BYBIT_DEMO_API_SECRET", "SENTINEL_SECRET_VALUE_999")
        self._run(use_real_network=False)
        out = capsys.readouterr().out
        assert "SENTINEL_KEY_VALUE_999"    not in out
        assert "SENTINEL_SECRET_VALUE_999" not in out
        assert "secret_value_observed   : False" in out

    def test_req20_no_order_endpoint_in_output(self, capsys):
        """Req 20: no order endpoint called."""
        self._run(use_real_network=False)
        out = capsys.readouterr().out
        assert "order_endpoint_called" in out
        # The value shown must be False
        assert "order_endpoint_called   : False" in out

    def test_req21_proposals_pass_invariants(self, capsys):
        """Req 21: proposal passes invariants after rounding."""
        self._run(use_real_network=False)
        out = capsys.readouterr().out
        assert "All invariants: PASS" in out

    def test_fixture_mode_shows_equity(self, capsys):
        self._run(use_real_network=False)
        out = capsys.readouterr().out
        assert "equity_usd" in out

    def test_fixture_mode_shows_account_snapshot(self, capsys):
        self._run(use_real_network=False)
        out = capsys.readouterr().out
        assert "Account Snapshot" in out


# ---------------------------------------------------------------------------
# 22-23. Regression: main.py / src/risk.py / BybitExecutor not modified
# ---------------------------------------------------------------------------

class TestRegressionScopeNotModified:
    """Req 22-23: ensures TASK-014C did not touch production execution paths."""

    def test_req23_main_py_does_not_import_demo_readonly_client(self):
        """Req 23: main.py not modified to include TASK-014C imports."""
        main_path = ROOT / "main.py"
        if not main_path.exists():
            pytest.skip("main.py not found in project root")
        src = main_path.read_text(encoding="utf-8", errors="replace")
        assert "demo_readonly_client"  not in src
        assert "demo_runtime_adapter"  not in src
        assert "preview_demo_readonly" not in src

    def test_req23_src_risk_not_modified(self):
        """Req 23: src/risk.py not modified to include TASK-014C imports."""
        risk_path = ROOT / "src" / "risk.py"
        if not risk_path.exists():
            pytest.skip("src/risk.py not found")
        src = risk_path.read_text(encoding="utf-8", errors="replace")
        assert "demo_readonly_client" not in src
        assert "demo_runtime_adapter" not in src

    def test_req23_demo_readonly_client_does_not_import_risk(self):
        """TASK-014C client must not import src.risk."""
        src = (ROOT / "src" / "demo_readonly_client.py").read_text(encoding="utf-8")
        assert "src.risk" not in src
        assert "from src import risk" not in src

    def test_req23_demo_runtime_adapter_does_not_import_risk(self):
        src = (ROOT / "src" / "demo_runtime_adapter.py").read_text(encoding="utf-8")
        assert "src.risk" not in src
