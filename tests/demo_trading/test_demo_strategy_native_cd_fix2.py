"""TASK-014CD_FIX2 -- aggregate price freshness + network-audit schema parity.

Proves the schema-parity corrections on top of the VPS-run TASK-014CD_FIX1 review:
the batch / review / top-level freshness statuses are a deterministic fail-closed
aggregate of the 50 action statuses; feasibility distinguishes evidence-available
from execution-grade-complete (PARTIAL, not globally UNAVAILABLE); the top-level
network counters have ONE canonical meaning that mirrors the nested network audit;
non-atomic snapshot timing uses sub-millisecond precision. Fully offline.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
import time

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_strategy_native_margin_freshness_audit as md
from src import demo_strategy_native_v1_portfolio as v1
from src import demo_strategy_pilot_action_planner as ap
from src import demo_strategy_pilot_lifecycle as lc
from src import demo_strategy_pilot_readiness as rd
from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition

daily_cli = importlib.import_module("scripts.run_demo_strategy_pilot_native_daily")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
DATE = "2026-06-22"
INIT = 10_000.0
FULL_ENV = {"NOTION_TOKEN": "tok", "NOTION_PILOT_DATABASE_ID": "db",
            "MONITOR_DISCORD_WEBHOOK_URL": "http://hook"}
DEMO_ENV = dict(FULL_ENV, BYBIT_DEMO_API_KEY="DEMOKEY", BYBIT_DEMO_API_SECRET="DEMOSECRET")


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class CDProvider:
    def __init__(self, *, symbols, prices, positions=None):
        self._symbols = symbols
        self._prices = prices
        self._positions = positions or []
        self._price_cache = {}
        self._http = 0
        self._requested = 0
        self._cache_hits = 0
        self._obs = {}

    def equity_usd(self): return INIT
    def available_balance_usd(self): return 8_500.0
    def open_positions(self): return list(self._positions)

    def account_risk_snapshot(self):
        return {"wallet_equity_usd": INIT, "available_balance_usd": 8_500.0,
                "leverage_authoritative": False, "initial_margin_authoritative": False,
                "assumed_leverage": None}

    def instrument_rule(self, symbol):
        return InstrumentRules(symbol=symbol, qty_step=0.1, min_qty=0.1, max_qty=0.0,
                               tick_size=0.01, min_notional=1.0, price_precision=2, qty_precision=1)

    def instrument_rule_evidence(self, symbol):
        return {"symbol": symbol, "rule_status": "TRADING",
                "instrument_rule_source": "instruments-info", "market_price_source": "tickers",
                "market_price": self._prices.get(symbol),
                "qty_step": 0.1, "min_qty": 0.1, "max_qty": 0.0, "min_notional": 1.0,
                "tick_size": 0.01}

    def market_price(self, symbol):
        self._requested += 1
        if symbol in self._price_cache:
            self._cache_hits += 1
            return self._price_cache[symbol]
        self._http += 1
        now = time.time()
        self._obs[symbol] = {
            "price_source": "tickers", "exchange_timestamp_ms": None,
            "request_started_at_utc": now, "response_received_at_utc": now,
            "response_received_epoch": now, "request_elapsed_ms": 1.0}
        self._price_cache[symbol] = self._prices.get(symbol)
        return self._price_cache[symbol]

    def price_observation(self, symbol): return self._obs.get(symbol)

    def network_audit_counters(self):
        return {"ticker_http_request_count": self._http,
                "ticker_requested_symbol_count": self._requested,
                "ticker_unique_symbol_count": len(self._price_cache),
                "ticker_cache_hit_count": self._cache_hits,
                "priced_symbols": [s for s, v in self._price_cache.items() if v is not None]}

    def margin_evidence(self):
        per = [{"symbol": p.symbol, "leverage": getattr(p, "leverage", None),
                "initial_margin": None, "maintenance_margin": None,
                "position_value": None, "mark_price": None, "liq_price": None}
               for p in self._positions]
        return md.normalize_margin_evidence(
            margin_evidence_source="fixture-readonly", account_type="UNIFIED",
            wallet_equity=INIT, available_balance=8_500.0, per_position=per)


def _50_symbols():
    return [f"C{i}USDT" for i in range(50)]


def _50_signals():
    syms = _50_symbols()
    return [{"symbol": s, "side": "long" if i < 25 else "short", "weight": 0.02, "score": 0.02}
            for i, s in enumerate(syms)]


def _legacy_positions():
    return [DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=1655.0,
                             entry_price=0.5, stop_price=0.6),
            DemoOpenPosition(symbol="POLYXUSDT", side="short", quantity=5615.6,
                             entry_price=0.25, stop_price=0.3)]


def _plan_and_provider(positions=None):
    syms = _50_symbols()
    prices = {s: 2.0 for s in syms}
    prices.update({"EDUUSDT": 0.6, "POLYXUSDT": 0.3})
    prov = CDProvider(symbols=syms, prices=prices, positions=positions)
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(_50_signals()), provider=prov)
    return plan, prov


def _partial_freshness_evidence(symbols, *, observed=1990.0, batch_built=2000.0):
    snaps = [md.build_price_freshness_snapshot(
        symbol=s, price=2.0, price_source="tickers",
        request_started_at_utc=observed, response_received_at_utc=observed,
        request_elapsed_ms=1.0, batch_built_at_utc=batch_built) for s in symbols]
    return md.build_price_freshness_evidence(snaps)


def _freshness_with_override(override):
    syms = _50_symbols() + ["EDUUSDT", "POLYXUSDT"]
    snaps = []
    for s in syms:
        if s in override:
            snaps.append(md.build_price_freshness_snapshot(**override[s]))
        else:
            snaps.append(md.build_price_freshness_snapshot(
                symbol=s, price=2.0, price_source="g",
                request_started_at_utc=1990.0, response_received_at_utc=1990.0,
                request_elapsed_ms=1.0, batch_built_at_utc=2000.0))
    return md.build_price_freshness_evidence(snaps)


def _review_with_evidence(*, positions=None, price_freshness_evidence=None, margin_evidence=None,
                          network_audit=None):
    plan, prov = _plan_and_provider(positions=positions)
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    return v1.build_strategy_native_review(
        plan=plan, open_positions=positions if positions is not None else [], pilot_id=PILOT,
        run_date=DATE, artifact_fingerprint="sha256:fp", wallet_equity=INIT,
        available_balance=8_500.0, rule_evidence_by_symbol=rule_ev,
        price_by_symbol={s: 2.0 for s in _50_symbols()},
        legacy_mark_price_by_symbol={"EDUUSDT": 0.6, "POLYXUSDT": 0.3},
        margin_evidence=margin_evidence, network_audit=network_audit,
        price_freshness_evidence=price_freshness_evidence)


def running_pilot(tmp_path, fwd_root):
    out = str(tmp_path / "out")
    rd.initialize_pilot(pilot_id=PILOT, acknowledged=True, env=FULL_ENV,
                        output_root=out, forward_source_root=fwd_root)
    lc.migrate_to_strategy_native(pilot_id=PILOT, acknowledged=True, output_root=out)
    lc.start_pilot(pilot_id=PILOT, acknowledged=True, env=DEMO_ENV, output_root=out)
    return out


@pytest.fixture
def fwd_root(tmp_path):
    d = tmp_path / "fwd" / "prev3y_crypto"
    d.mkdir(parents=True)
    (d / "forward_summary.json").write_text(
        json.dumps({"strategy": "prev3y_crypto_combined_paper_safe_variant",
                    "latest_date": "20260518"}), encoding="utf-8")
    return str(tmp_path / "fwd")


# --- A. Aggregate price freshness ------------------------------------------


def test_aggregation_priority_fail_closed():
    P = md.PRICE_FRESHNESS_PASS
    S = md.PRICE_FRESHNESS_STALE
    U = md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    F = md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
    assert md.aggregate_freshness_statuses([P, P, P]) == P
    assert md.aggregate_freshness_statuses([P, F, P]) == F      # partial beats pass
    assert md.aggregate_freshness_statuses([F, U, P]) == U      # unavailable beats partial
    assert md.aggregate_freshness_statuses([F, U, S]) == S      # stale beats all
    assert md.aggregate_freshness_statuses([]) == U             # empty fails closed


def test_batch_review_top_aggregate_freshness_partial():
    pfe = _partial_freshness_evidence(_50_symbols())
    review = _review_with_evidence(positions=_legacy_positions(), price_freshness_evidence=pfe)
    actions = review["execution_batch"]["actions"]
    assert all(a["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL for a in actions)
    assert review["execution_batch"]["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
    assert review["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
    assert review["feasibility"]["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL


def test_stale_action_forces_aggregate_stale():
    pfe = _freshness_with_override({"C0USDT": dict(
        symbol="C0USDT", price=2.0, price_source="g", exchange_timestamp_ms=1000_000,
        response_received_at_utc=1000.0, batch_built_at_utc=1100.0)})
    review = _review_with_evidence(positions=_legacy_positions(), price_freshness_evidence=pfe)
    c0 = [a for a in review["execution_batch"]["actions"] if a["symbol"] == "C0USDT"][0]
    assert c0["price_freshness_status"] == md.PRICE_FRESHNESS_STALE
    assert review["execution_batch"]["price_freshness_status"] == md.PRICE_FRESHNESS_STALE
    assert review["price_freshness_status"] == md.PRICE_FRESHNESS_STALE


def test_unavailable_action_forces_aggregate_unavailable():
    pfe = _freshness_with_override({"C1USDT": dict(
        symbol="C1USDT", price=2.0, price_source="g")})
    review = _review_with_evidence(positions=_legacy_positions(), price_freshness_evidence=pfe)
    c1 = [a for a in review["execution_batch"]["actions"] if a["symbol"] == "C1USDT"][0]
    assert c1["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    assert review["execution_batch"]["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    assert review["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE


# --- B. Feasibility freshness semantics ------------------------------------


def test_feasibility_reports_partial_not_unavailable():
    f = v1.assess_feasibility(
        wallet_equity=10000, available_balance=8500, strategy_gross_notional=10000,
        legacy_gross_notional=2677, leverage_authoritative=True,
        initial_margin_authoritative=True, assumed_leverage=10,
        price_freshness_status=md.PRICE_FRESHNESS_EVIDENCE_PARTIAL,
        exchange_timestamp_available=False)
    assert f["projected_margin_feasibility_status"] == \
        v1.STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
    assert md.PRICE_FRESHNESS_EVIDENCE_PARTIAL in f["account_risk_review_reasons"]
    assert "EXCHANGE_TIMESTAMP_UNAVAILABLE" in f["account_risk_review_reasons"]
    assert md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE not in f["account_risk_review_reasons"]


def test_feasibility_distinguishes_evidence_from_execution_grade():
    f = v1.assess_feasibility(
        wallet_equity=10000, available_balance=8500, strategy_gross_notional=10000,
        legacy_gross_notional=2677, leverage_authoritative=True,
        initial_margin_authoritative=True, assumed_leverage=10,
        price_freshness_status=md.PRICE_FRESHNESS_EVIDENCE_PARTIAL,
        exchange_timestamp_available=False)
    assert f["price_freshness_evidence_available"] is True
    assert f["local_observation_time_available"] is True
    assert f["exchange_timestamp_available"] is False
    assert f["execution_grade_freshness_complete"] is False


def test_review_feasibility_partial_for_vps_case():
    pfe = _partial_freshness_evidence(_50_symbols())
    review = _review_with_evidence(positions=_legacy_positions(), price_freshness_evidence=pfe)
    feas = review["feasibility"]
    assert feas["projected_margin_feasibility_status"] == \
        v1.STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
    assert feas["exchange_timestamp_available"] is False
    assert md.PRICE_FRESHNESS_EVIDENCE_PARTIAL in feas["account_risk_review_reasons"]
    assert "EXCHANGE_TIMESTAMP_UNAVAILABLE" in feas["account_risk_review_reasons"]
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False


# --- C. Network schema parity ----------------------------------------------


def _canonical_review_network():
    return {"network_audit": md.build_network_audit(
        ticker_http_request_count=52, ticker_requested_symbol_count=152,
        ticker_unique_symbol_count=52, ticker_cache_hit_count=100,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)}


def test_top_level_canonical_network_mirrors_nested():
    review = _canonical_review_network()
    planner = {"ticker_http_request_count": 50, "ticker_requested_symbol_count": 50,
               "ticker_unique_symbol_count": 50, "ticker_cache_hit_count": 0}
    top = daily_cli._canonical_network_top_level(
        review=review, planner_phase_audit=planner, instrument_metadata_get_count=1)
    na = review["network_audit"]
    assert top["ticker_http_request_count"] == na["ticker_http_request_count"] == 52
    assert top["ticker_requested_symbol_count"] == na["ticker_requested_symbol_count"] == 152
    assert top["ticker_unique_symbol_count"] == na["ticker_unique_symbol_count"] == 52
    assert top["ticker_cache_hit_count"] == na["ticker_cache_hit_count"] == 100
    assert top["total_priced_symbol_count"] == na["total_priced_symbol_count"] == 52
    assert top["network_audit_status"] == md.NETWORK_AUDIT_CONSISTENT


def test_planner_only_counters_renamed():
    review = _canonical_review_network()
    planner = {"ticker_http_request_count": 50, "ticker_requested_symbol_count": 50,
               "ticker_unique_symbol_count": 50, "ticker_cache_hit_count": 0}
    top = daily_cli._canonical_network_top_level(
        review=review, planner_phase_audit=planner, instrument_metadata_get_count=1)
    assert top["planner_ticker_http_request_count"] == 50
    assert top["planner_ticker_requested_symbol_count"] == 50
    assert top["planner_ticker_unique_symbol_count"] == 50
    assert top["planner_ticker_cache_hit_count"] == 0
    assert top["ticker_http_request_count"] != top["planner_ticker_http_request_count"]


def test_total_public_get_count_internally_consistent():
    review = _canonical_review_network()
    top = daily_cli._canonical_network_top_level(
        review=review, planner_phase_audit={}, instrument_metadata_get_count=1)
    assert top["total_public_get_count"] == 1 + top["ticker_http_request_count"] == 53


def test_no_duplicate_ambiguous_counter_names():
    review = _canonical_review_network()
    top = daily_cli._canonical_network_top_level(
        review=review, planner_phase_audit={}, instrument_metadata_get_count=1)
    keys = list(top.keys())
    assert len(keys) == len(set(keys))


def test_cli_top_level_network_equals_nested(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    planner_audit = {"ticker_http_request_count": 50, "ticker_requested_symbol_count": 50,
                     "ticker_unique_symbol_count": 50, "ticker_cache_hit_count": 0}
    top = daily_cli._canonical_network_top_level(
        review=review, planner_phase_audit=planner_audit, instrument_metadata_get_count=1)
    na = review["network_audit"]
    assert top["ticker_http_request_count"] == na["ticker_http_request_count"]
    assert top["ticker_unique_symbol_count"] == na["ticker_unique_symbol_count"] == 52
    assert top["total_priced_symbol_count"] == 52
    assert top["network_audit_status"] == md.NETWORK_AUDIT_CONSISTENT


# --- D. Snapshot time precision --------------------------------------------


def test_snapshot_delta_uses_monotonic_precision():
    ev = md.normalize_margin_evidence(
        margin_evidence_source="fixture", total_initial_margin=200.0,
        per_position=[{"symbol": "EDUUSDT", "leverage": 10.0, "initial_margin": 200.0}],
        wallet_snapshot_response_received_at_utc="2026-06-22T00:00:00Z",
        position_snapshot_response_received_at_utc="2026-06-22T00:00:00Z",
        wallet_snapshot_response_received_monotonic=100.000000,
        position_snapshot_response_received_monotonic=100.000250)
    assert ev["margin_snapshot_atomic"] is False
    assert ev["snapshot_time_delta_ms"] == 0.25


def test_snapshot_atomicity_not_inferred_from_equal_utc_strings():
    ev = md.normalize_margin_evidence(
        margin_evidence_source="fixture",
        wallet_snapshot_response_received_at_utc="2026-06-22T00:00:00Z",
        position_snapshot_response_received_at_utc="2026-06-22T00:00:00Z")
    assert ev["margin_snapshot_atomic"] is False
    assert ev["comparison_scope_status"] == md.COMPARISON_SCOPE_NOT_PROVEN_COMPARABLE


# --- E. Legacy price-evidence parity ---------------------------------------


def test_legacy_mark_freshness_attached():
    pfe = _partial_freshness_evidence(_50_symbols() + ["EDUUSDT", "POLYXUSDT"])
    review = _review_with_evidence(positions=_legacy_positions(), price_freshness_evidence=pfe)
    legacy = {p["symbol"]: p for p in review["legacy_protected_positions"]}
    for sym in ("EDUUSDT", "POLYXUSDT"):
        assert legacy[sym]["mark_price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
        assert legacy[sym]["mark_price_observed_at"] is not None
        assert legacy[sym]["mark_price_age_seconds"] is not None
        assert legacy[sym]["mark_price_evidence_fingerprint"] is not None
        assert legacy[sym]["executable"] is False


# --- F. Preservation under FIX2 --------------------------------------------


def test_fix2_preserves_rules_decimal_and_unauthorized():
    pfe = _partial_freshness_evidence(_50_symbols())
    review = _review_with_evidence(positions=_legacy_positions(), price_freshness_evidence=pfe)
    batch = review["execution_batch"]
    assert review["target_position_count"] == 50
    assert review["long_target_count"] == 25 and review["short_target_count"] == 25
    assert batch["expected_action_count"] == 50
    assert review["non_null_rule_fingerprint_count"] == 50
    assert all(a["rule_validation_status"] == v1.RULE_VALIDATION_PASS for a in batch["actions"])
    assert review["batch_float_artifact_count"] == 0
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False
    assert review["sender_reachable"] is False
    assert review["order_post_count"] == 0


def test_cli_pilot_state_byte_identical(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    state_path = pathlib.Path(out_root)
    before = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert before
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    after = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert after == before
