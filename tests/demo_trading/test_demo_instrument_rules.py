"""
tests/demo_trading/test_demo_instrument_rules.py
TASK-014B: Tests for src/demo_instrument_rules.py + preview script safety.

Covers all required test cases:
  8.  qty rounds down to qty_step
  9.  price rounds deterministically to tick_size
  10. rounding does not increase quantity
  11. rounding does not increase stop risk
  12. quantity < min_qty after rounding -> reject
  13. notional < min_notional -> reject
  14. invalid qty_step / tick_size -> reject
  15. NaN / infinity / negative -> reject
  16. accepted proposal maintains exposure invariants
  17. symbol missing instrument rule -> reject
  18. preview script runs without secrets
  19. preview script prints DRY RUN / NO ORDERS SENT
  20. preview script does not import forbidden tokens
  21. preview script returns nonzero when demo not verified
  22. fixture verified mode produces rounded dry-run preview

SAFETY: no exchange imports, no order calls, no secrets.
"""
from __future__ import annotations

import io
import math
import sys
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace

import pytest

ROOT = Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

import src.demo_instrument_rules as di
import src.demo_portfolio_risk   as dr


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _rules(
    symbol="SYM",
    qty_step=0.1, min_qty=0.1, max_qty=0.0,
    tick_size=0.01, min_notional=5.0,
    price_precision=2, qty_precision=1,
) -> di.InstrumentRules:
    return di.InstrumentRules(
        symbol=symbol,
        qty_step=qty_step, min_qty=min_qty, max_qty=max_qty,
        tick_size=tick_size, min_notional=min_notional,
        price_precision=price_precision, qty_precision=qty_precision,
    )


def _proposal(
    symbol="SYM", side="long", score=0.9, rank=1,
    quantity=10.0, entry_price=100.0, stop_price=90.0,
    proposed_notional_usd=1000.0, allocated_stop_risk_usd=100.0,
):
    """Build a duck-typed proposal using SimpleNamespace."""
    return SimpleNamespace(
        symbol=symbol, side=side, score=score, rank=rank,
        quantity=quantity, entry_price=entry_price, stop_price=stop_price,
        proposed_notional_usd=proposed_notional_usd,
        allocated_stop_risk_usd=allocated_stop_risk_usd,
    )


# ---------------------------------------------------------------------------
# 8. round_qty_down
# ---------------------------------------------------------------------------

class TestRoundQtyDown:
    def test_basic_rounds_down(self):
        """Test case 8: qty rounds down to qty_step."""
        assert di.round_qty_down(1.239, 0.1) == pytest.approx(1.2)

    def test_exact_multiple_unchanged(self):
        assert di.round_qty_down(1.2, 0.1) == pytest.approx(1.2)

    def test_large_qty(self):
        assert di.round_qty_down(100.999, 1.0) == pytest.approx(100.0)

    def test_tiny_step(self):
        assert di.round_qty_down(12.07347, 0.001) == pytest.approx(12.073)

    def test_does_not_exceed_input(self):
        """Test case 10: rounding does not increase quantity."""
        for qty in [1.0, 1.05, 1.099, 5.555, 100.999]:
            assert di.round_qty_down(qty, 0.1) <= qty + 1e-12

    def test_nan_returns_zero(self):
        """Test case 15: NaN -> 0."""
        assert di.round_qty_down(float("nan"), 0.1) == 0.0

    def test_inf_returns_zero(self):
        assert di.round_qty_down(float("inf"), 0.1) == 0.0

    def test_negative_returns_zero(self):
        assert di.round_qty_down(-1.0, 0.1) == 0.0

    def test_invalid_step_zero_returns_zero(self):
        """Test case 14: invalid qty_step -> 0."""
        assert di.round_qty_down(1.0, 0.0) == 0.0

    def test_invalid_step_negative_returns_zero(self):
        assert di.round_qty_down(1.0, -0.1) == 0.0

    def test_invalid_step_nan_returns_zero(self):
        assert di.round_qty_down(1.0, float("nan")) == 0.0

    def test_zero_qty_returns_zero(self):
        assert di.round_qty_down(0.0, 0.1) == 0.0


# ---------------------------------------------------------------------------
# 9. round_price_to_tick
# ---------------------------------------------------------------------------

class TestRoundPriceToTick:
    def test_basic_rounding(self):
        """Test case 9: price rounds to tick_size."""
        assert di.round_price_to_tick(14.506, 0.01) == pytest.approx(14.51)

    def test_rounds_down(self):
        assert di.round_price_to_tick(14.504, 0.01) == pytest.approx(14.50)

    def test_exact_tick(self):
        assert di.round_price_to_tick(85.0, 0.01) == pytest.approx(85.0)

    def test_deterministic_same_input_same_output(self):
        """Test case 9: deterministic."""
        for _ in range(5):
            assert di.round_price_to_tick(78.005, 0.01) == di.round_price_to_tick(78.005, 0.01)

    def test_nan_returns_zero(self):
        assert di.round_price_to_tick(float("nan"), 0.01) == 0.0

    def test_negative_price_returns_zero(self):
        assert di.round_price_to_tick(-1.0, 0.01) == 0.0

    def test_zero_price_returns_zero(self):
        assert di.round_price_to_tick(0.0, 0.01) == 0.0

    def test_invalid_tick_zero_returns_zero(self):
        assert di.round_price_to_tick(100.0, 0.0) == 0.0

    def test_invalid_tick_nan_returns_zero(self):
        assert di.round_price_to_tick(100.0, float("nan")) == 0.0


# ---------------------------------------------------------------------------
# validate_min_qty / validate_min_notional
# ---------------------------------------------------------------------------

class TestValidateMinQty:
    def test_sufficient_passes(self):
        ok, reason = di.validate_min_qty(1.0, 0.1)
        assert ok is True
        assert reason == ""

    def test_below_min_fails(self):
        """Test case 12: quantity < min_qty -> reject."""
        ok, reason = di.validate_min_qty(0.05, 0.1)
        assert ok is False
        assert reason == di.REJECT_MIN_QTY

    def test_zero_passes_when_min_zero(self):
        ok, _ = di.validate_min_qty(0.0, 0.0)
        assert ok is True

    def test_nan_fails(self):
        ok, reason = di.validate_min_qty(float("nan"), 0.1)
        assert ok is False
        assert reason == di.REJECT_INVALID_INPUT

    def test_negative_fails(self):
        ok, _ = di.validate_min_qty(-0.1, 0.1)
        assert not ok


class TestValidateMinNotional:
    def test_sufficient_passes(self):
        ok, reason = di.validate_min_notional(100.0, 5.0)
        assert ok is True
        assert reason == ""

    def test_below_min_fails(self):
        """Test case 13: notional < min_notional -> reject."""
        ok, reason = di.validate_min_notional(1.0, 5.0)
        assert ok is False
        assert reason == di.REJECT_MIN_NOTIONAL

    def test_nan_fails(self):
        ok, _ = di.validate_min_notional(float("nan"), 5.0)
        assert not ok


# ---------------------------------------------------------------------------
# InstrumentRules.is_valid
# ---------------------------------------------------------------------------

class TestInstrumentRulesIsValid:
    def test_valid_rules_pass(self):
        ok, _ = _rules().is_valid()
        assert ok is True

    def test_zero_qty_step_fails(self):
        """Test case 14: invalid qty_step -> reject."""
        ok, err = _rules(qty_step=0.0).is_valid()
        assert ok is False
        assert "qty_step" in err

    def test_negative_qty_step_fails(self):
        ok, _ = _rules(qty_step=-0.1).is_valid()
        assert not ok

    def test_nan_qty_step_fails(self):
        ok, _ = _rules(qty_step=float("nan")).is_valid()
        assert not ok

    def test_zero_tick_size_fails(self):
        ok, err = _rules(tick_size=0.0).is_valid()
        assert ok is False
        assert "tick_size" in err

    def test_nan_tick_size_fails(self):
        ok, _ = _rules(tick_size=float("nan")).is_valid()
        assert not ok

    def test_negative_min_qty_fails(self):
        ok, _ = _rules(min_qty=-1.0).is_valid()
        assert not ok


# ---------------------------------------------------------------------------
# apply_instrument_rules_to_proposal
# ---------------------------------------------------------------------------

class TestApplyInstrumentRules:

    def test_basic_accepted_with_rounding(self):
        """Basic happy-path: qty rounds down, all checks pass."""
        p = _proposal(quantity=12.073, entry_price=85.0, stop_price=78.0,
                      proposed_notional_usd=1026.2, allocated_stop_risk_usd=84.51)
        r = _rules(qty_step=0.1, min_qty=0.1, tick_size=0.01, min_notional=5.0)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is True
        assert out.rounded_quantity == pytest.approx(12.0)

    def test_rounded_qty_not_greater_than_original(self):
        """Test case 10: rounding does not increase quantity."""
        p = _proposal(quantity=12.073)
        r = _rules(qty_step=0.1)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.rounded_quantity <= out.original_quantity + 1e-12

    def test_stop_risk_not_increased(self):
        """Test case 11: stop risk after rounding <= original."""
        p = _proposal(quantity=10.53, entry_price=100.0, stop_price=90.0,
                      proposed_notional_usd=1053.0, allocated_stop_risk_usd=105.3)
        r = _rules(qty_step=1.0, tick_size=0.01, min_notional=5.0)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is True
        assert out.stop_risk_after_rounding <= p.allocated_stop_risk_usd + di.STOP_RISK_TOLERANCE_USD

    def test_min_qty_rejection_after_rounding(self):
        """Test case 12: quantity rounds to 0 < min_qty -> reject."""
        p = _proposal(quantity=0.05, entry_price=100.0, stop_price=90.0,
                      proposed_notional_usd=5.0, allocated_stop_risk_usd=0.5)
        r = _rules(qty_step=0.1, min_qty=0.1, min_notional=0.0)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False
        assert out.reject_reason == di.REJECT_MIN_QTY

    def test_min_notional_rejection(self):
        """Test case 13: notional after rounding < min_notional -> reject."""
        p = _proposal(quantity=0.1, entry_price=10.0, stop_price=9.0,
                      proposed_notional_usd=1.0, allocated_stop_risk_usd=0.1)
        r = _rules(qty_step=0.1, min_qty=0.0, tick_size=0.01, min_notional=100.0)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False
        assert out.reject_reason == di.REJECT_MIN_NOTIONAL

    def test_invalid_qty_step_rejected(self):
        """Test case 14: invalid qty_step -> invalid_instrument_rules."""
        p = _proposal()
        r = _rules(qty_step=0.0)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False
        assert out.reject_reason == di.REJECT_INVALID_RULES

    def test_invalid_tick_size_rejected(self):
        p = _proposal()
        r = _rules(tick_size=0.0)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False
        assert out.reject_reason == di.REJECT_INVALID_RULES

    def test_nan_quantity_rejected(self):
        """Test case 15: NaN in proposal -> reject."""
        p = _proposal(quantity=float("nan"))
        r = _rules()
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False
        assert out.reject_reason == di.REJECT_INVALID_INPUT

    def test_inf_entry_rejected(self):
        p = _proposal(entry_price=float("inf"))
        r = _rules()
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False

    def test_negative_stop_rejected(self):
        p = _proposal(stop_price=-1.0)
        r = _rules()
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False

    def test_nan_stop_price_rejected(self):
        p = _proposal(stop_price=float("nan"))
        r = _rules()
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False
        assert out.reject_reason == di.REJECT_INVALID_INPUT

    def test_negative_qty_rejected(self):
        p = _proposal(quantity=-1.0)
        r = _rules()
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is False

    def test_missing_rules_rejected(self):
        """Test case 17: rules=None -> missing_instrument_rule."""
        p = _proposal()
        out = di.apply_instrument_rules_to_proposal(p, None)
        assert out.accepted is False
        assert out.reject_reason == di.REJECT_MISSING_RULE

    def test_invariants_maintained_with_real_proposal(self):
        """Test case 16: accepted proposal maintains invariants."""
        # Build a real PositionProposal from Phase 2
        cands = [dr.DemoSignalCandidate("SYM", "long", 100.0, 90.0, 0.9)]
        result = dr.compute_demo_portfolio_sizing(
            equity_usd=10_000.0,
            available_balance_usd=10_000.0,
            full_kelly_fraction=0.2634,
            open_positions=[],
            candidates=cands,
            demo_environment_expected=True,
        )
        accepted = [p for p in result.proposals if p.accepted]
        assert len(accepted) == 1
        prop = accepted[0]
        rules = _rules(
            qty_step=0.1, min_qty=0.1, tick_size=0.01,
            min_notional=5.0, min_qty_kwarg_unused=None
        ) if False else _rules(qty_step=0.1, min_qty=0.1, tick_size=0.01, min_notional=5.0)
        out = di.apply_instrument_rules_to_proposal(prop, rules)
        # Invariants
        assert out.rounded_quantity      <= out.original_quantity + 1e-12
        assert out.stop_risk_after_rounding <= out.original_stop_risk_usd + di.STOP_RISK_TOLERANCE_USD

    def test_multiple_accepted_proposals_all_maintain_invariants(self):
        """Test case 16 extended: all accepted proposals satisfy invariants."""
        cands = [
            dr.DemoSignalCandidate(f"S{i}", "long" if i < 5 else "short",
                                   100.0, 90.0, float(10 - i))
            for i in range(10)
        ]
        result = dr.compute_demo_portfolio_sizing(
            equity_usd=10_000.0,
            available_balance_usd=10_000.0,
            full_kelly_fraction=0.2634,
            open_positions=[],
            candidates=cands,
            demo_environment_expected=True,
        )
        r = _rules(qty_step=0.1, min_qty=0.1, tick_size=0.01, min_notional=5.0)
        for prop in result.proposals:
            if prop.accepted:
                out = di.apply_instrument_rules_to_proposal(prop, r)
                assert out.rounded_quantity <= out.original_quantity + 1e-12
                assert out.stop_risk_after_rounding <= (
                    out.original_stop_risk_usd + di.STOP_RISK_TOLERANCE_USD
                )
                if out.accepted:
                    assert math.isfinite(out.rounded_quantity)
                    assert out.rounded_quantity >= 0.0
                    assert math.isfinite(out.notional_after_rounding)
                    assert out.notional_after_rounding >= 0.0

    def test_output_no_nan_or_inf_on_accepted(self):
        """Test case 15 extended: no NaN/inf in accepted output."""
        p = _proposal(quantity=10.0, entry_price=100.0, stop_price=90.0,
                      proposed_notional_usd=1000.0, allocated_stop_risk_usd=100.0)
        r = _rules()
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.accepted is True
        assert math.isfinite(out.rounded_quantity)
        assert math.isfinite(out.notional_after_rounding)
        assert math.isfinite(out.stop_risk_after_rounding)

    def test_rounded_qty_is_exact_floor_multiple(self):
        """Verify floor semantics: not ceiling, not round-nearest."""
        # 12.099 / 0.1 = 120.99 -> floor = 120 -> 12.0
        p = _proposal(quantity=12.099, entry_price=100.0, stop_price=90.0,
                      proposed_notional_usd=1209.9, allocated_stop_risk_usd=120.99)
        r = _rules(qty_step=0.1, min_qty=0.1, min_notional=5.0)
        out = di.apply_instrument_rules_to_proposal(p, r)
        assert out.rounded_quantity == pytest.approx(12.0)

    def test_symbol_in_missing_rule_dict_entry(self):
        """Test case 17: passing None rules -> REJECT_MISSING_RULE with symbol."""
        p = _proposal(symbol="UNKNOWN:SYM")
        out = di.apply_instrument_rules_to_proposal(p, None)
        assert out.reject_reason == di.REJECT_MISSING_RULE
        assert out.detail.get("symbol") == "UNKNOWN:SYM"


# ---------------------------------------------------------------------------
# 18-22. Preview script safety and behaviour
# ---------------------------------------------------------------------------

class TestPreviewScriptSafety:
    PREVIEW  = ROOT / "scripts" / "preview_demo_runtime_and_rounding.py"
    PROBE_M  = ROOT / "src" / "demo_runtime_probe.py"
    INSTR_M  = ROOT / "src" / "demo_instrument_rules.py"
    FORBIDDEN = ("place_order", "create_order", "submit_order",
                 "cancel_order", "private_post", "BybitExecutor",
                 "BYBIT_API_KEY", "BYBIT_API_SECRET", "session.")

    def _load_preview_module(self):
        import importlib.util
        spec = importlib.util.spec_from_file_location("preview_rr", self.PREVIEW)
        mod  = importlib.util.module_from_spec(spec)
        sys.modules["preview_rr"] = mod
        spec.loader.exec_module(mod)
        return mod

    def test_preview_script_exists(self):
        assert self.PREVIEW.exists()

    def test_no_forbidden_tokens_in_probe_module(self):
        """Test case 20: no forbidden order tokens in probe source."""
        src = self.PROBE_M.read_text(encoding="utf-8")
        for token in self.FORBIDDEN:
            assert token not in src, f"'{token}' found in demo_runtime_probe.py"

    def test_no_forbidden_tokens_in_instrument_module(self):
        """Test case 20: no forbidden order tokens in instrument rules source."""
        src = self.INSTR_M.read_text(encoding="utf-8")
        for token in self.FORBIDDEN:
            assert token not in src, f"'{token}' found in demo_instrument_rules.py"

    def test_no_forbidden_tokens_in_preview_script(self):
        """Test case 20: no forbidden order tokens in preview script."""
        src = self.PREVIEW.read_text(encoding="utf-8")
        for token in self.FORBIDDEN:
            assert token not in src, f"'{token}' found in preview script"

    def test_no_secret_loading_in_preview_script(self):
        src = self.PREVIEW.read_text(encoding="utf-8")
        assert "dotenv" not in src
        assert "os.environ" not in src
        assert "getenv" not in src

    def test_no_pybit_in_probe(self):
        src = self.PROBE_M.read_text(encoding="utf-8")
        assert "pybit" not in src

    def test_no_pybit_in_instrument_module(self):
        src = self.INSTR_M.read_text(encoding="utf-8")
        assert "pybit" not in src

    def test_no_pybit_in_preview(self):
        src = self.PREVIEW.read_text(encoding="utf-8")
        assert "pybit" not in src

    def test_preview_script_runs_without_secrets(self):
        """Test case 18: script runs without loading secrets."""
        mod = self._load_preview_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.run_preview()
        assert rc == 0

    def test_preview_script_prints_dry_run_text(self):
        """Test case 19: output contains DRY RUN and NO ORDERS SENT."""
        mod = self._load_preview_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.run_preview()
        output = buf.getvalue()
        assert "DRY RUN" in output.upper() or "DRY RUN" in output
        assert "NO ORDERS SENT" in output.upper() or "NO ORDERS SENT" in output

    def test_preview_unverified_returns_nonzero(self):
        """Test case 21: fail-closed when demo runtime not verified."""
        mod = self._load_preview_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.run_preview(use_fixture_proof=False)
        assert rc != 0

    def test_preview_unverified_prints_fail_closed(self):
        mod = self._load_preview_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.run_preview(use_fixture_proof=False)
        output = buf.getvalue()
        assert "FAIL CLOSED" in output.upper() or "FAIL CLOSED" in output

    def test_preview_verified_mode_returns_zero(self):
        """Test case 22: fixture verified mode succeeds."""
        mod = self._load_preview_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            rc = mod.run_preview(use_fixture_proof=True)
        assert rc == 0

    def test_preview_verified_mode_has_rounded_output(self):
        """Test case 22: rounded proposals appear in output."""
        mod = self._load_preview_module()
        buf = io.StringIO()
        with redirect_stdout(buf):
            mod.run_preview(use_fixture_proof=True)
        output = buf.getvalue()
        # The rounding section header must appear
        assert "Instrument Rounding" in output or "rounding" in output.lower()

    def test_preview_no_main_import(self):
        src = self.PREVIEW.read_text(encoding="utf-8")
        assert "import main" not in src
        assert "from main" not in src

    def test_preview_no_risk_import(self):
        src = self.PREVIEW.read_text(encoding="utf-8")
        assert "src.risk" not in src


# ---------------------------------------------------------------------------
# Safety scan: new modules do not contain forbidden runtime calls
# ---------------------------------------------------------------------------

class TestNewModulesSecurityScan:
    MODULES = [
        ROOT / "src" / "demo_runtime_probe.py",
        ROOT / "src" / "demo_instrument_rules.py",
        ROOT / "scripts" / "preview_demo_runtime_and_rounding.py",
    ]

    @pytest.mark.parametrize("module_path", MODULES)
    def test_no_order_submission_in_module(self, module_path):
        src = module_path.read_text(encoding="utf-8")
        for dangerous in ("place_order", "create_order", "submit_order",
                          "cancel_order", "private_post"):
            assert dangerous not in src, (
                f"Dangerous token '{dangerous}' found in {module_path.name}"
            )

    @pytest.mark.parametrize("module_path", MODULES)
    def test_no_api_key_handling(self, module_path):
        src = module_path.read_text(encoding="utf-8")
        for secret in ("API_KEY", "API_SECRET", "dotenv"):
            assert secret not in src, (
                f"Secret-related token '{secret}' found in {module_path.name}"
            )
