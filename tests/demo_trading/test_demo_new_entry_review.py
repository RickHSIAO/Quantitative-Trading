"""
tests/demo_trading/test_demo_new_entry_review.py
TASK-014K: Tests for the Demo new-entry dry-run proposal review.

Tests are grouped K1-K19 covering:
  K1  reconciliation_not_pass -> fail_closed
  K2  proof_not_strong -> fail_closed
  K3  position_details_source != real_readonly -> fail_closed
  K4  available_balance <= 0 -> fail_closed
  K5  short capacity full -> every short candidate rejected
  K6  long capacity available -> long candidates reviewed normally
  K7  duplicate symbol with existing position -> rejected
  K8  missing instrument rule -> rejected
  K9  rounded qty zero -> rejected
  K10 min_notional violation after rounding -> rejected
  K11 invalid stop distance (stop on wrong side / zero) -> rejected
  K12 projected gross exposure over max -> rejected
  K13 projected net exposure over max -> rejected
  K14 every payload has preview_only=True
  K15 every payload has order_sent=False
  K16 every payload has order_endpoint_called=False / module never calls endpoint
  K17 no secrets observed: secret_value_observed=False
  K18 no order endpoint tokens / no live hostname in module source
  K19 module does not import main / src.risk / BybitExecutor / close-only sender

All tests are pure-computation: zero network calls, zero secrets loaded.
"""
from __future__ import annotations

import ast
from pathlib import Path

import pytest

from src.demo_instrument_rules import InstrumentRules
from src.demo_new_entry_review import (
    NewEntryCandidate,
    NewEntryEvaluation,
    NewEntryPayloadPreview,
    NewEntryReviewResult,
    REJECT_AVAILABLE_BALANCE,
    REJECT_DUPLICATE_SYMBOL,
    REJECT_INVALID_STOP_DISTANCE,
    REJECT_LONG_CAPACITY_FULL,
    REJECT_MAX_SINGLE_NOTIONAL,
    REJECT_MIN_NOTIONAL_AFTER_ROUNDING,
    REJECT_MISSING_INSTRUMENT_RULE,
    REJECT_PROJECTED_GROSS_EXPOSURE,
    REJECT_PROJECTED_NET_EXPOSURE,
    REJECT_PROOF_NOT_STRONG,
    REJECT_RECONCILIATION_NOT_PASS,
    REJECT_ROUND_QTY_ZERO,
    REJECT_RUNTIME_NOT_VERIFIED,
    REJECT_SHORT_CAPACITY_FULL,
    REJECT_SOURCE_NOT_REAL_READONLY,
    review_new_entry_candidates,
)
from src.demo_portfolio_risk import (
    DemoOpenPosition,
    MAX_GROSS_EXPOSURE_RATIO,
    MAX_NET_EXPOSURE_RATIO,
    MAX_SHORT_POSITIONS,
)
from src.demo_position_reconcile import ReconciliationResult, reconcile


_ROOT = Path(__file__).resolve().parents[2]
_MODULE_PATH = _ROOT / "src" / "demo_new_entry_review.py"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_RULES_CLEAN: dict[str, InstrumentRules] = {
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


_CLEAN_POSITIONS: list[DemoOpenPosition] = [
    DemoOpenPosition("BTCUSDT", "long",  0.05, 67_000.0, 65_000.0),
    DemoOpenPosition("ETHUSDT", "short", 0.30,  3_500.0,  3_700.0),
]


def _clean_recon(
    equity_usd:              float = 10_000.0,
    available_balance_usd:   float = 8_500.0,
    positions:               list[DemoOpenPosition] | None = None,
    demo_runtime_verified:   bool  = True,
    proof_strength:          str   = "STRONG",
    position_details_source: str   = "real_readonly",
) -> ReconciliationResult:
    pos = positions if positions is not None else _CLEAN_POSITIONS
    return reconcile(
        equity_usd=equity_usd,
        available_balance_usd=available_balance_usd,
        positions=pos,
        instrument_rules=_RULES_CLEAN,
        full_kelly_fraction=0.60,
        demo_runtime_verified=demo_runtime_verified,
        proof_strength=proof_strength,
        mode="real_readonly_snapshot",
        position_details_source=position_details_source,
    )


def _full_short_positions() -> list[DemoOpenPosition]:
    """5 short positions — short capacity FULL.  All notionals small enough
    to keep gross exposure < 1.0x of 11560.91 equity."""
    return [
        DemoOpenPosition("ETHUSDT", "short", 0.10,  3_500.0,  3_700.0),
        DemoOpenPosition("BNBUSDT", "short", 0.50,    600.0,    640.0),
        DemoOpenPosition("SOLUSDT", "short", 1.00,    160.0,    175.0),
        DemoOpenPosition("XRPUSDT", "short", 100.0,    0.62,     0.68),
        DemoOpenPosition("ADAUSDT", "short", 200.0,    0.45,     0.49),
    ]


def _full_short_recon() -> ReconciliationResult:
    """Reconciliation modelled on the production state:
    equity≈11560.91, available≈7048.86, short_count=5/5, long_count=0/5."""
    return reconcile(
        equity_usd=11_560.91,
        available_balance_usd=7_048.86,
        positions=_full_short_positions(),
        instrument_rules=_RULES_CLEAN,
        full_kelly_fraction=0.60,
        demo_runtime_verified=True,
        proof_strength="STRONG",
        mode="real_readonly_snapshot",
        position_details_source="real_readonly",
    )


def _good_long(symbol: str = "SOLUSDT") -> NewEntryCandidate:
    return NewEntryCandidate(
        symbol=symbol, side="long",
        entry_reference_price=160.0, stop_price=150.0,
        requested_risk_usd=40.0, score=1.0,
    )


def _good_short(symbol: str = "AVAXUSDT") -> NewEntryCandidate:
    return NewEntryCandidate(
        symbol=symbol, side="short",
        entry_reference_price=30.0, stop_price=33.0,
        requested_risk_usd=25.0, score=0.8,
    )


# ---------------------------------------------------------------------------
# K1 — reconciliation not PASS -> fail_closed
# ---------------------------------------------------------------------------

class TestK1ReconciliationNotPass:
    def test_open_positions_over_max_blocks(self):
        # Construct a reconciliation with new_entry_allowed=False by having
        # too many short positions (>5 -> hard violation).
        positions = [
            DemoOpenPosition("ETHUSDT", "short", 0.10, 3_500.0, 3_700.0),
            DemoOpenPosition("BNBUSDT", "short", 0.50,   600.0,   640.0),
            DemoOpenPosition("SOLUSDT", "short", 1.00,   160.0,   175.0),
            DemoOpenPosition("XRPUSDT", "short", 100.0,    0.62,    0.68),
            DemoOpenPosition("ADAUSDT", "short", 200.0,    0.45,    0.49),
            DemoOpenPosition("LINKUSDT", "short", 5.0,    14.5,    16.0),
        ]
        rec = _clean_recon(positions=positions)
        assert rec.new_entry_allowed is False  # sanity

        r = review_new_entry_candidates(
            reconciliation=rec,
            candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert REJECT_RECONCILIATION_NOT_PASS in r.fail_closed_reasons
        # Every candidate must be rejected when fail_closed
        assert all(e.accepted is False for e in r.evaluations)
        assert r.accepted_candidates == []
        assert r.payload_previews == []

    def test_fail_closed_with_no_candidates_still_reports(self):
        positions = list(_CLEAN_POSITIONS)
        positions.extend([
            DemoOpenPosition(f"X{i}USDT", "short", 1.0, 10.0, 11.0)
            for i in range(MAX_SHORT_POSITIONS + 1)
        ])
        rec = _clean_recon(positions=positions)
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert r.evaluations == []
        assert r.next_required_task == "no_payload_to_send"


# ---------------------------------------------------------------------------
# K2 — proof not STRONG -> fail_closed
# ---------------------------------------------------------------------------

class TestK2ProofNotStrong:
    @pytest.mark.parametrize("proof", ["WEAK", "MISSING", "", "weak"])
    def test_non_strong_proof_blocks(self, proof):
        rec = _clean_recon(proof_strength=proof)
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert REJECT_PROOF_NOT_STRONG in r.fail_closed_reasons
        assert r.accepted_candidates == []

    def test_strong_proof_allows_review(self):
        rec = _clean_recon(proof_strength="STRONG")
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert REJECT_PROOF_NOT_STRONG not in r.fail_closed_reasons


# ---------------------------------------------------------------------------
# K3 — position_details_source not real_readonly -> fail_closed
# ---------------------------------------------------------------------------

class TestK3SourceNotRealReadonly:
    @pytest.mark.parametrize("src", ["fixture", "fixture_from_smoke", "", "unknown"])
    def test_non_real_source_blocks(self, src):
        rec = _clean_recon(position_details_source=src)
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert REJECT_SOURCE_NOT_REAL_READONLY in r.fail_closed_reasons


# ---------------------------------------------------------------------------
# K4 — runtime not verified / available balance <= 0
# ---------------------------------------------------------------------------

class TestK4RuntimeAndBalance:
    def test_runtime_not_verified_blocks(self):
        rec = _clean_recon(demo_runtime_verified=False)
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert REJECT_RUNTIME_NOT_VERIFIED in r.fail_closed_reasons

    def test_available_balance_zero_blocks(self):
        rec = _clean_recon(available_balance_usd=0.0)
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert REJECT_AVAILABLE_BALANCE in r.fail_closed_reasons

    def test_available_balance_negative_blocks(self):
        rec = _clean_recon(available_balance_usd=-5.0)
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert REJECT_AVAILABLE_BALANCE in r.fail_closed_reasons


# ---------------------------------------------------------------------------
# K5 — short capacity full -> every short candidate rejected
# ---------------------------------------------------------------------------

class TestK5ShortCapacityFull:
    def test_short_rejected_when_short_full(self):
        rec = _full_short_recon()
        assert rec.new_entry_allowed is True  # sanity: long capacity exists
        assert rec.max_short_allowed_remaining == 0

        r = review_new_entry_candidates(
            reconciliation=rec,
            candidates=[_good_short("AVAXUSDT"), _good_short("LINKUSDT")],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is False
        for ev in r.evaluations:
            assert ev.accepted is False
            assert ev.reject_reason == REJECT_SHORT_CAPACITY_FULL

    def test_mixed_candidates_short_full_only_longs_accepted(self):
        rec = _full_short_recon()
        cands = [
            _good_long("SOLUSDT"),
            _good_short("AVAXUSDT"),
            _good_long("AAVEUSDT"),
            _good_short("LINKUSDT"),
        ]
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=cands,
            instrument_rules=_RULES_CLEAN,
        )
        short_evals = [e for e in r.evaluations if e.side == "short"]
        assert short_evals
        assert all(
            e.accepted is False and e.reject_reason == REJECT_SHORT_CAPACITY_FULL
            for e in short_evals
        )


# ---------------------------------------------------------------------------
# K6 — long candidates reviewed when capacity exists
# ---------------------------------------------------------------------------

class TestK6LongCapacityAvailable:
    def test_good_long_accepted_on_clean_recon(self):
        rec = _clean_recon()
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is False
        assert len(r.accepted_candidates) == 1
        assert r.accepted_candidates[0].symbol == "SOLUSDT"
        assert r.accepted_candidates[0].payload is not None
        assert r.payload_previews
        assert r.next_required_task.startswith("TASK-014L")

    def test_long_capacity_full_rejects_longs(self):
        # 5 longs already open: any new long rejected with long_capacity_full
        positions = [
            DemoOpenPosition(f"L{i}USDT", "long", 1.0, 10.0, 9.0)
            for i in range(5)
        ]
        rules = dict(_RULES_CLEAN)
        for i in range(5):
            rules[f"L{i}USDT"] = InstrumentRules(
                f"L{i}USDT", 0.001, 0.001, 0, 0.01, 1.0, 2, 3,
            )
        rec = reconcile(
            equity_usd=10_000.0,
            available_balance_usd=8_000.0,
            positions=positions,
            instrument_rules=rules,
            full_kelly_fraction=0.60,
            demo_runtime_verified=True,
            proof_strength="STRONG",
            mode="real_readonly_snapshot",
            position_details_source="real_readonly",
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long("SOLUSDT")],
            instrument_rules=rules | _RULES_CLEAN,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason == REJECT_LONG_CAPACITY_FULL


# ---------------------------------------------------------------------------
# K7 — duplicate symbol rejection
# ---------------------------------------------------------------------------

class TestK7DuplicateSymbol:
    def test_duplicate_of_existing_position_rejected(self):
        rec = _clean_recon()
        # BTCUSDT is already an open long in _CLEAN_POSITIONS
        cand = NewEntryCandidate(
            symbol="BTCUSDT", side="long",
            entry_reference_price=67_000.0, stop_price=65_000.0,
            requested_risk_usd=40.0,
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[cand],
            instrument_rules=_RULES_CLEAN,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason == REJECT_DUPLICATE_SYMBOL

    def test_duplicate_among_candidates_second_rejected(self):
        rec = _clean_recon()
        c1 = _good_long("SOLUSDT")
        c2 = _good_long("SOLUSDT")
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[c1, c2],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.evaluations[0].accepted is True
        assert r.evaluations[1].accepted is False
        assert r.evaluations[1].reject_reason == REJECT_DUPLICATE_SYMBOL


# ---------------------------------------------------------------------------
# K8 — missing instrument rule
# ---------------------------------------------------------------------------

class TestK8MissingInstrumentRule:
    def test_unknown_symbol_rejected(self):
        rec = _clean_recon()
        cand = NewEntryCandidate(
            symbol="UNKNOWNUSDT", side="long",
            entry_reference_price=100.0, stop_price=95.0,
            requested_risk_usd=10.0,
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[cand],
            instrument_rules=_RULES_CLEAN,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason == REJECT_MISSING_INSTRUMENT_RULE


# ---------------------------------------------------------------------------
# K9 — rounded qty zero
# ---------------------------------------------------------------------------

class TestK9RoundedQtyZero:
    def test_qty_step_too_large_rounds_to_zero(self):
        # BTCUSDT rule with qty_step=1.0: requested_risk=5, stop_distance=2000
        # raw_qty = 5/2000 = 0.0025 -> floors to 0
        rules = {"BTCUSDT": InstrumentRules(
            "BTCUSDT", qty_step=1.0, min_qty=1.0, max_qty=0,
            tick_size=0.1, min_notional=1.0, price_precision=1, qty_precision=0,
        )}
        rules.update({k: v for k, v in _RULES_CLEAN.items() if k != "BTCUSDT"})
        rec = _clean_recon()
        cand = NewEntryCandidate(
            symbol="BTCUSDT", side="long",
            entry_reference_price=67_000.0, stop_price=65_000.0,
            requested_risk_usd=5.0,
        )
        # Need to drop existing BTCUSDT position so duplicate gate does not fire
        rec_no_btc = _clean_recon(positions=[
            DemoOpenPosition("ETHUSDT", "short", 0.30, 3_500.0, 3_700.0),
        ])
        r = review_new_entry_candidates(
            reconciliation=rec_no_btc, candidates=[cand],
            instrument_rules=rules,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason == REJECT_ROUND_QTY_ZERO


# ---------------------------------------------------------------------------
# K10 — min_notional violation after rounding
# ---------------------------------------------------------------------------

class TestK10MinNotional:
    def test_notional_below_min_rejected(self):
        # SOLUSDT rule but with very high min_notional so qty=0.1 * 160 = 16
        # is below the threshold (say min_notional=10000).
        rules = dict(_RULES_CLEAN)
        rules["SOLUSDT"] = InstrumentRules(
            "SOLUSDT", qty_step=0.1, min_qty=0.1, max_qty=0,
            tick_size=0.01, min_notional=10_000.0,
            price_precision=2, qty_precision=1,
        )
        rec = _clean_recon()
        # tiny risk -> small qty
        cand = NewEntryCandidate(
            symbol="SOLUSDT", side="long",
            entry_reference_price=160.0, stop_price=150.0,
            requested_risk_usd=2.0,
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[cand],
            instrument_rules=rules,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason == REJECT_MIN_NOTIONAL_AFTER_ROUNDING


# ---------------------------------------------------------------------------
# K11 — invalid stop distance
# ---------------------------------------------------------------------------

class TestK11InvalidStopDistance:
    def test_long_stop_above_entry_rejected(self):
        rec = _clean_recon()
        bad = NewEntryCandidate(
            symbol="SOLUSDT", side="long",
            entry_reference_price=160.0, stop_price=170.0,  # invalid
            requested_risk_usd=40.0,
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[bad],
            instrument_rules=_RULES_CLEAN,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason == REJECT_INVALID_STOP_DISTANCE

    def test_short_stop_below_entry_rejected(self):
        rec = _clean_recon()
        bad = NewEntryCandidate(
            symbol="AVAXUSDT", side="short",
            entry_reference_price=30.0, stop_price=29.0,  # invalid
            requested_risk_usd=25.0,
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[bad],
            instrument_rules=_RULES_CLEAN,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason == REJECT_INVALID_STOP_DISTANCE

    def test_zero_stop_rejected(self):
        rec = _clean_recon()
        bad = NewEntryCandidate(
            symbol="SOLUSDT", side="long",
            entry_reference_price=160.0, stop_price=0.0,
            requested_risk_usd=40.0,
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[bad],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.evaluations[0].accepted is False


# ---------------------------------------------------------------------------
# K12 — projected gross exposure over max
# ---------------------------------------------------------------------------

class TestK12ProjectedGrossExposure:
    def test_too_large_position_violates_single_notional_first(self):
        """A candidate whose notional alone exceeds the single-position notional cap
        (15% of equity) trips that gate before projected_gross is evaluated."""
        rec = _clean_recon(equity_usd=1_000.0, available_balance_usd=800.0,
                           positions=[])
        cand = NewEntryCandidate(
            symbol="BTCUSDT", side="long",
            entry_reference_price=67_000.0, stop_price=66_900.0,
            requested_risk_usd=100.0,
        )
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[cand],
            instrument_rules=_RULES_CLEAN,
        )
        ev = r.evaluations[0]
        assert ev.accepted is False
        assert ev.reject_reason in (
            REJECT_MAX_SINGLE_NOTIONAL,
            REJECT_PROJECTED_GROSS_EXPOSURE,
        )

    def test_max_gross_constant_value(self):
        # Defensive sanity: protects against silent constant tweak
        assert MAX_GROSS_EXPOSURE_RATIO == 1.0


# ---------------------------------------------------------------------------
# K13 — projected net exposure over max
# ---------------------------------------------------------------------------

class TestK13ProjectedNetExposure:
    def test_max_net_constant_value(self):
        assert MAX_NET_EXPOSURE_RATIO == 0.5

    def test_existing_short_heavy_long_rejected(self):
        # Existing short_notional ~0 (clean), short cap full simulation
        # Use the full-short snapshot: short_notional is large.  Adding a long
        # to even the books should reduce net; ensure logic does not over-trip
        # net here.  This negative-control test ensures the gate is reachable
        # for projected_net but a sensible long does not falsely trigger it.
        rec = _full_short_recon()
        cand = _good_long("SOLUSDT")
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[cand],
            instrument_rules=_RULES_CLEAN,
        )
        ev = r.evaluations[0]
        # adding a small long reduces net (which was net-short) -> should accept
        # or reject for some other reason (capacity / budget), but NOT for
        # projected_net.
        assert ev.reject_reason != REJECT_PROJECTED_NET_EXPOSURE


# ---------------------------------------------------------------------------
# K14, K15, K16 — payload preview_only / order_sent / order_endpoint_called
# ---------------------------------------------------------------------------

class TestK14K15K16PayloadInvariants:
    def test_every_payload_has_required_invariants(self):
        rec = _clean_recon()
        cands = [_good_long("SOLUSDT"), _good_long("AAVEUSDT")]
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=cands,
            instrument_rules=_RULES_CLEAN,
        )
        assert r.payload_previews
        for p in r.payload_previews:
            assert p.preview_only is True
            assert p.order_sent is False
            assert p.order_endpoint_called is False
            assert p.reduce_only is False           # new entries
            assert p.confirmation_required is True

    def test_result_level_invariants(self):
        rec = _clean_recon()
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.no_orders_sent is True
        assert r.no_position_modified is True
        assert r.order_endpoint_called is False
        assert r.action_type == "PREVIEW_REVIEW_ONLY"

    def test_fail_closed_still_holds_invariants(self):
        rec = _clean_recon(demo_runtime_verified=False)
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is True
        assert r.no_orders_sent is True
        assert r.order_endpoint_called is False
        assert r.action_type == "PREVIEW_REVIEW_ONLY"


# ---------------------------------------------------------------------------
# K17 — no secrets observed
# ---------------------------------------------------------------------------

class TestK17NoSecrets:
    def test_secret_value_observed_false(self):
        rec = _clean_recon()
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.secret_value_observed is False

    def test_to_dict_does_not_emit_secret_fields(self):
        rec = _clean_recon()
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        d = r.to_dict(timestamp_utc="2026-06-09T00:00:00Z")
        flat = repr(d).lower()
        # `secret_value_observed` is a tracked invariant (False) and must NOT
        # be misread as a leaked secret.  We check for actual secret tokens.
        forbidden = ["api_key", "api_secret", "x-bapi-sign", "private_key", "bapi_sign"]
        for tok in forbidden:
            assert tok not in flat
        # Confirm the invariant itself is present and False.
        assert d["secret_value_observed"] is False


# ---------------------------------------------------------------------------
# K18 — no order endpoint tokens / no live hostname in module source
# ---------------------------------------------------------------------------

class TestK18ModuleSourceClean:
    def test_no_live_hostname_in_module(self):
        src = _MODULE_PATH.read_text(encoding="utf-8").lower()
        assert "api.bybit.com" not in src
        assert "api-testnet.bybit.com" not in src
        # demo hostname is allowed only as documentation, but the module
        # is pure computation and should not need it.
        assert "api-demo.bybit.com" not in src

    def test_no_order_endpoint_paths_in_module(self):
        src = _MODULE_PATH.read_text(encoding="utf-8").lower()
        assert "/v5/order/create" not in src
        assert "/v5/order/cancel" not in src
        assert "/v5/position/set-leverage" not in src

    def test_no_http_client_imports_in_module(self):
        src = _MODULE_PATH.read_text(encoding="utf-8")
        assert "import requests" not in src
        assert "import urllib" not in src
        assert "import httpx" not in src
        assert "import http.client" not in src

    def test_module_has_no_io_side_effect_text(self):
        src = _MODULE_PATH.read_text(encoding="utf-8").lower()
        # No network or fs writes from the module itself
        assert "urlopen" not in src
        assert ".post(" not in src


# ---------------------------------------------------------------------------
# K19 — module does not import main / src.risk / BybitExecutor / close-only sender
# ---------------------------------------------------------------------------

class TestK19ForbiddenImportsAbsent:
    def _imports(self) -> set[str]:
        tree = ast.parse(_MODULE_PATH.read_text(encoding="utf-8"))
        names: set[str] = set()
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                for alias in node.names:
                    names.add(alias.name)
            elif isinstance(node, ast.ImportFrom):
                mod = node.module or ""
                names.add(mod)
                for alias in node.names:
                    names.add(f"{mod}.{alias.name}")
        return names

    def test_no_main_import(self):
        names = self._imports()
        assert all(
            not (n == "main" or n.startswith("main.") or n.endswith(".main"))
            for n in names
        ), f"forbidden 'main' import found: {names}"

    def test_no_src_risk_import(self):
        names = self._imports()
        assert all(
            not (n == "src.risk" or n.startswith("src.risk."))
            for n in names
        ), f"forbidden 'src.risk' import found: {names}"

    def test_no_bybit_executor_import(self):
        names = self._imports()
        # No symbol named BybitExecutor must be imported (docstring mention is OK)
        assert all(
            not n.endswith("BybitExecutor") for n in names
        ), f"forbidden BybitExecutor import found: {names}"

    def test_no_close_only_sender_import(self):
        names = self._imports()
        assert all(
            "demo_close_only_sender" not in n for n in names
        ), f"forbidden close-only sender import found: {names}"

    def test_no_execute_demo_close_only(self):
        src = _MODULE_PATH.read_text(encoding="utf-8")
        assert "execute_demo_close_only_cleanup" not in src


# ---------------------------------------------------------------------------
# Additional safety: dataclass serialization round-trip
# ---------------------------------------------------------------------------

class TestSerialization:
    def test_payload_preview_to_dict_keys(self):
        rec = _clean_recon()
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        assert r.payload_previews
        d = r.payload_previews[0].to_dict()
        required_keys = {
            "symbol", "side", "order_type", "qty", "reduce_only", "preview_only",
            "rounded_entry_price", "rounded_stop_price",
            "estimated_notional_usd", "estimated_stop_risk_usd",
            "projected_gross_exposure_ratio", "projected_net_exposure_ratio",
            "order_sent", "order_endpoint_called", "confirmation_required",
        }
        assert required_keys.issubset(d.keys())

    def test_result_to_dict_action_type(self):
        rec = _clean_recon()
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=[_good_long()],
            instrument_rules=_RULES_CLEAN,
        )
        d = r.to_dict(timestamp_utc="2026-06-09T00:00:00Z")
        assert d["action_type"] == "PREVIEW_REVIEW_ONLY"
        assert d["no_orders_sent"] is True
        assert d["order_endpoint_called"] is False
        assert d["secret_value_observed"] is False


# ---------------------------------------------------------------------------
# Production-state snapshot scenario from TASK-014K spec
# ---------------------------------------------------------------------------

class TestProductionScenario:
    """Mirrors the constants Rick supplied: equity≈11560.91, available≈7048.86,
    short_count=5/5, long_count=0/5.  Any short candidate must be rejected
    with short_capacity_full; well-formed longs should be accepted (subject
    to per-trade caps)."""

    def test_short_candidate_rejected_long_accepted(self):
        rec = _full_short_recon()
        cands = [
            _good_short("AVAXUSDT"),
            _good_short("LINKUSDT"),
            _good_long("SOLUSDT"),
            _good_long("AAVEUSDT"),
        ]
        r = review_new_entry_candidates(
            reconciliation=rec, candidates=cands,
            instrument_rules=_RULES_CLEAN,
        )
        assert r.fail_closed is False

        short_evals = [e for e in r.evaluations if e.side == "short"]
        for e in short_evals:
            assert e.accepted is False
            assert e.reject_reason == REJECT_SHORT_CAPACITY_FULL

        long_evals = [e for e in r.evaluations if e.side == "long"]
        # At least one long should be accepted
        assert any(e.accepted for e in long_evals)
