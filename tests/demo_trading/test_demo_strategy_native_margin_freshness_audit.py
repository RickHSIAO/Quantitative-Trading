"""TASK-014CD -- authoritative margin / price-freshness / network-audit evidence.

Proves the Plan-only evidence layer on top of the accepted TASK-014CC_FIX1 review:
authoritative read-only margin evidence is captured WITHOUT assumptions, the
projected-margin model is computed ONLY with authoritative inputs, local and
exchange timestamps are never conflated, network request/symbol/cache counts are
distinct and consistent for all 52 priced symbols, and the execution batch remains
UNAUTHORISED. Fully offline: zero HTTP, zero Bybit, zero orders.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import sys
import time
from decimal import Decimal

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


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class CDProvider:
    """Planner + review provider with TASK-014CD margin / observation / network
    evidence. Caches market_price per distinct symbol exactly like production."""

    def __init__(self, *, symbols, prices, positions=None, margin=None,
                 equity=INIT, available=8_500.0):
        self._symbols = symbols
        self._prices = prices
        self._positions = positions or []
        self._margin = margin
        self._equity = equity
        self._available = available
        self._price_cache: dict[str, float | None] = {}
        self._http = 0
        self._requested = 0
        self._cache_hits = 0
        self._obs: dict[str, dict] = {}

    def equity_usd(self): return self._equity
    def available_balance_usd(self): return self._available
    def open_positions(self): return list(self._positions)

    def account_risk_snapshot(self):
        return {"wallet_equity_usd": self._equity, "available_balance_usd": self._available,
                "leverage_authoritative": False, "initial_margin_authoritative": False,
                "assumed_leverage": None}

    def instrument_rule(self, symbol):
        return InstrumentRules(symbol=symbol, qty_step=0.1, min_qty=0.1, max_qty=0.0,
                               tick_size=0.01, min_notional=1.0, price_precision=2, qty_precision=1)

    def instrument_rule_evidence(self, symbol):
        return {"symbol": symbol, "rule_status": "TRADING",
                "instrument_rule_source": "DemoReadOnlyClient.get_instruments_info() -> /v5/market/instruments-info",
                "market_price_source": "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
                "market_price": self._prices.get(symbol),
                "qty_step": 0.1, "min_qty": 0.1, "max_qty": 0.0,
                "min_notional": 1.0, "tick_size": 0.01}

    def market_price(self, symbol):
        self._requested += 1
        if symbol in self._price_cache:
            self._cache_hits += 1
            return self._price_cache[symbol]
        self._http += 1
        now = time.time()
        self._obs[symbol] = {
            "price_source": "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
            "exchange_timestamp_ms": None,
            "request_started_at_utc": now,
            "response_received_at_utc": now,
            "response_received_epoch": now,
            "request_elapsed_ms": 1.0,
        }
        value = self._prices.get(symbol)
        self._price_cache[symbol] = value
        return value

    def price_observation(self, symbol):
        return self._obs.get(symbol)

    def network_audit_counters(self):
        return {"ticker_http_request_count": self._http,
                "ticker_requested_symbol_count": self._requested,
                "ticker_unique_symbol_count": len(self._price_cache),
                "ticker_cache_hit_count": self._cache_hits,
                "priced_symbols": [s for s, v in self._price_cache.items() if v is not None]}

    def margin_evidence(self):
        if self._margin is not None:
            return self._margin
        per = [{"symbol": p.symbol, "leverage": getattr(p, "leverage", None),
                "initial_margin": None, "maintenance_margin": None,
                "position_value": None, "mark_price": None, "liq_price": None}
               for p in self._positions]
        return md.normalize_margin_evidence(
            margin_evidence_source="fixture-readonly", wallet_equity=self._equity,
            available_balance=self._available, per_position=per)


def _50_symbols():
    return [f"C{i}USDT" for i in range(50)]


def _50_signals():
    syms = _50_symbols()
    return [{"symbol": s, "side": "long" if i < 25 else "short", "weight": 0.02, "score": 0.02}
            for i, s in enumerate(syms)]


def _legacy_positions():
    return [
        DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=1655.0,
                         entry_price=0.5, stop_price=0.6),
        DemoOpenPosition(symbol="POLYXUSDT", side="short", quantity=5615.6,
                         entry_price=0.25, stop_price=0.3),
    ]


def _plan_and_provider(positions=None):
    syms = _50_symbols()
    prices = {s: 2.0 for s in syms}
    prices.update({"EDUUSDT": 0.6, "POLYXUSDT": 0.3})  # legacy mark prices
    prov = CDProvider(symbols=syms, prices=prices, positions=positions)
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(_50_signals()), provider=prov)
    return plan, prov


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


# Authoritative margin evidence with full per-position fields + account totals.
def _authoritative_margin(*, im_per_pos=100.0, total_im=200.0):
    return md.normalize_margin_evidence(
        margin_evidence_source="DemoReadOnlyClient wallet+positions (private read-only GET)",
        account_margin_mode=None, wallet_equity=10000.0, available_balance=8500.0,
        total_initial_margin=total_im, total_maintenance_margin=120.0,
        account_initial_margin_rate=0.05, account_maintenance_margin_rate=0.03,
        per_position=[
            {"symbol": "EDUUSDT", "leverage": 10.0, "initial_margin": im_per_pos,
             "maintenance_margin": 60.0, "position_value": 1000.0, "mark_price": 0.6,
             "liq_price": 0.9},
            {"symbol": "POLYXUSDT", "leverage": 10.0, "initial_margin": im_per_pos,
             "maintenance_margin": 60.0, "position_value": 1684.0, "mark_price": 0.3,
             "liq_price": 0.45},
        ])


# ===========================================================================
# 1. Authoritative margin evidence
# ===========================================================================


def test_margin_fields_captured_without_assumption():
    ev = _authoritative_margin()
    assert ev["leverage_evidence_status"] == md.EVIDENCE_AUTHORITATIVE
    assert ev["initial_margin_evidence_status"] == md.EVIDENCE_AUTHORITATIVE
    assert ev["reported_total_initial_margin_usdt"] == "200"
    assert ev["account_initial_margin_rate"] == "0.05"
    assert ev["margin_evidence_snapshot_fingerprint"].startswith("sha256:")
    assert len(ev["per_position_margin_evidence"]) == 2
    assert ev["per_position_margin_evidence"][0]["leverage"] == "10"
    # account margin mode is NOT in an allowed read-only path -> not fabricated.
    assert ev["account_margin_mode"] is None
    assert "/v5/account/wallet-balance" in ev["margin_field_paths"]["total_initial_margin"]


def test_absent_margin_fields_remain_null_and_create_blockers():
    ev = md.unavailable_margin_evidence()
    assert ev["wallet_equity_usdt"] is None
    assert ev["reported_total_initial_margin_usdt"] is None
    assert ev["leverage_evidence_status"] == md.EVIDENCE_UNAVAILABLE
    assert ev["initial_margin_evidence_status"] == md.EVIDENCE_UNAVAILABLE
    model = md.build_projected_margin_model(
        margin_evidence=ev, strategy_gross_notional=10000, legacy_gross_notional=2677.68,
        available_balance=8500)
    assert model["margin_model_status"] == md.MARGIN_EVIDENCE_UNAVAILABLE
    assert model["projected_strategy_initial_margin_usdt"] is None
    assert "APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE" in model["margin_model_blockers"]


def test_conflicting_margin_evidence_fails_closed():
    # reported total IM (200) disagrees with per-position sum (100+100=200 -> set 999 to conflict)
    ev = md.normalize_margin_evidence(
        margin_evidence_source="fixture", total_initial_margin=999.0,
        per_position=[{"symbol": "EDUUSDT", "leverage": 10.0, "initial_margin": 100.0},
                      {"symbol": "POLYXUSDT", "leverage": 10.0, "initial_margin": 100.0}])
    model = md.build_projected_margin_model(
        margin_evidence=ev, strategy_gross_notional=10000, legacy_gross_notional=2677.68,
        available_balance=8500, applicable_initial_margin_rate=0.05)
    assert model["margin_model_status"] == md.MARGIN_EVIDENCE_CONFLICT
    assert "REPORTED_TOTAL_IM_CONFLICTS_WITH_PER_POSITION_SUM" in model["margin_model_blockers"]


def test_no_hardcoded_leverage_used():
    ev = _authoritative_margin()
    # No applicable IM rate supplied -> projected strategy IM is NOT computed.
    model = md.build_projected_margin_model(
        margin_evidence=ev, strategy_gross_notional=10000, legacy_gross_notional=2677.68,
        available_balance=8500)
    assert model["projected_strategy_initial_margin_usdt"] is None
    assert model["margin_model_status"] != md.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    assert "APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE" in model["margin_model_blockers"]


def test_projected_margin_only_with_authoritative_inputs():
    ev = _authoritative_margin()
    model = md.build_projected_margin_model(
        margin_evidence=ev, strategy_gross_notional=10000, legacy_gross_notional=2677.68,
        available_balance=8500, applicable_initial_margin_rate=0.05)
    # strategy IM = 10000 * 0.05 = 500 ; legacy IM = 100 + 100 = 200 ; total = 700
    assert model["margin_model_status"] == md.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    assert model["projected_strategy_initial_margin_usdt"] == "500"
    assert model["projected_legacy_initial_margin_usdt"] == "200"
    assert model["projected_total_initial_margin_usdt"] == "700"
    assert model["projected_available_margin_after_execution_usdt"] == "7800"


def test_insufficient_projected_margin():
    ev = _authoritative_margin()
    # rate 1.0 -> strategy IM = 10000 ; total = 10200 > available 8500 -> INSUFFICIENT
    model = md.build_projected_margin_model(
        margin_evidence=ev, strategy_gross_notional=10000, legacy_gross_notional=2677.68,
        available_balance=8500, applicable_initial_margin_rate=1.0)
    assert model["margin_model_status"] == md.INSUFFICIENT_PROJECTED_MARGIN
    assert Decimal(model["projected_available_margin_after_execution_usdt"]) < 0


# ===========================================================================
# 3. Price observation and freshness evidence
# ===========================================================================


def test_local_and_exchange_timestamps_not_conflated():
    snap = md.build_price_freshness_snapshot(
        symbol="C0USDT", price=2.0, price_source="guard",
        response_received_at_utc=1000.0, batch_built_at_utc=1005.0)
    assert snap["exchange_timestamp"] is None
    assert snap["local_observed_at_utc"] == 1000.0
    assert snap["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL


def test_price_age_deterministic_from_evidence():
    s1 = md.build_price_freshness_snapshot(symbol="C0USDT", price=2.0, price_source="g",
                                           response_received_at_utc=1000.0, batch_built_at_utc=1007.5)
    s2 = md.build_price_freshness_snapshot(symbol="C0USDT", price=2.0, price_source="g",
                                           response_received_at_utc=1000.0, batch_built_at_utc=1007.5)
    assert s1["price_age_seconds_at_batch_build"] == s2["price_age_seconds_at_batch_build"] == "7.5"


def test_stale_price_detected():
    snap = md.build_price_freshness_snapshot(
        symbol="C0USDT", price=2.0, price_source="g", exchange_timestamp_ms=1000_000,
        response_received_at_utc=1000.0, batch_built_at_utc=1100.0,
        freshness_threshold_seconds=30)
    assert snap["price_freshness_status"] == md.PRICE_FRESHNESS_STALE


def test_exchange_timestamp_passes_when_fresh():
    snap = md.build_price_freshness_snapshot(
        symbol="C0USDT", price=2.0, price_source="g", exchange_timestamp_ms=1000_000,
        response_received_at_utc=1000.0, batch_built_at_utc=1005.0)
    assert snap["price_freshness_status"] == md.PRICE_FRESHNESS_PASS
    assert snap["exchange_timestamp"] == "1000000"


def test_missing_timestamp_is_partial_or_unavailable():
    snap = md.build_price_freshness_snapshot(symbol="C0USDT", price=2.0, price_source="g")
    assert snap["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    assert snap["price_age_seconds_at_batch_build"] is None


def test_freshness_summary_precedence():
    pass_snap = {"price_freshness_status": md.PRICE_FRESHNESS_PASS}
    stale_snap = {"price_freshness_status": md.PRICE_FRESHNESS_STALE}
    partial_snap = {"price_freshness_status": md.PRICE_FRESHNESS_EVIDENCE_PARTIAL}
    assert md.summarize_price_freshness([pass_snap, pass_snap]) == md.PRICE_FRESHNESS_PASS
    assert md.summarize_price_freshness([pass_snap, stale_snap]) == md.PRICE_FRESHNESS_STALE
    assert md.summarize_price_freshness([pass_snap, partial_snap]) == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
    assert md.summarize_price_freshness([]) == md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE


# ===========================================================================
# 4. Network-audit semantics
# ===========================================================================


def test_all_52_priced_symbols_represented():
    na = md.build_network_audit(
        ticker_http_request_count=52, ticker_requested_symbol_count=52,
        ticker_unique_symbol_count=52, ticker_cache_hit_count=0,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)
    assert na["total_priced_symbol_count"] == 52
    assert na["network_audit_status"] == md.NETWORK_AUDIT_CONSISTENT


def test_request_and_symbol_counts_distinct_with_cache():
    # 102 lookups, 52 distinct -> 52 HTTP requests + 50 cache hits.
    na = md.build_network_audit(
        ticker_http_request_count=52, ticker_requested_symbol_count=102,
        ticker_unique_symbol_count=52, ticker_cache_hit_count=50,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)
    assert na["ticker_http_request_count"] != na["ticker_requested_symbol_count"]
    assert na["ticker_cache_hit_count"] == 50
    assert na["request_per_symbol_proven"] is True
    assert na["network_audit_status"] == md.NETWORK_AUDIT_CONSISTENT


def test_network_audit_counter_mismatch_fails_closed():
    # Claims 50 HTTP requests but 52 unique symbols -> mismatch.
    na = md.build_network_audit(
        ticker_http_request_count=50, ticker_requested_symbol_count=50,
        ticker_unique_symbol_count=52, ticker_cache_hit_count=0,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)
    assert na["network_audit_status"] == md.NETWORK_AUDIT_COUNTER_MISMATCH
    blockers = md.build_execution_readiness_blockers(
        rule_rejection=False, batch_float_artifact_count=0, legacy_mark_price_available=True,
        price_freshness_status=md.PRICE_FRESHNESS_PASS,
        margin_model_status=md.AUTHORITATIVE_MARGIN_MODEL_COMPLETE,
        network_audit_status=na["network_audit_status"])
    assert md.NETWORK_AUDIT_COUNTER_MISMATCH in blockers


# ===========================================================================
# 5/6. Review integration: rule/Decimal preserved, blockers, unauthorised
# ===========================================================================


def _review_with_evidence(*, margin_evidence=None, network_audit=None,
                          price_freshness_evidence=None, positions=None,
                          applicable_initial_margin_rate=None):
    plan, prov = _plan_and_provider(positions=positions)
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    return v1.build_strategy_native_review(
        plan=plan, open_positions=positions if positions is not None else [], pilot_id=PILOT,
        run_date=DATE, artifact_fingerprint="sha256:fp", wallet_equity=INIT,
        available_balance=8_500.0, rule_evidence_by_symbol=rule_ev,
        price_by_symbol={s: 2.0 for s in _50_symbols()},
        legacy_mark_price_by_symbol={"EDUUSDT": 0.6, "POLYXUSDT": 0.3},
        margin_evidence=margin_evidence, network_audit=network_audit,
        price_freshness_evidence=price_freshness_evidence,
        applicable_initial_margin_rate=applicable_initial_margin_rate)


def test_full_50_plan_preserved_with_evidence():
    review = _review_with_evidence(positions=_legacy_positions())
    assert review["target_position_count"] == 50
    assert review["long_target_count"] == 25
    assert review["short_target_count"] == 25
    assert review["execution_batch"]["expected_action_count"] == 50


def test_rule_and_decimal_integrity_preserved():
    review = _review_with_evidence(positions=_legacy_positions())
    batch = review["execution_batch"]
    assert review["non_null_rule_fingerprint_count"] == 50
    assert all(a["instrument_rule_fingerprint"] is not None for a in batch["actions"])
    assert all(a["rule_validation_status"] == v1.RULE_VALIDATION_PASS for a in batch["actions"])
    assert review["batch_float_artifact_count"] == 0


def test_legacy_mark_risk_remains_current_market():
    review = _review_with_evidence(positions=_legacy_positions())
    mark = Decimal("1655") * Decimal("0.6") + Decimal("5615.6") * Decimal("0.3")
    assert Decimal(review["legacy_mark_gross_notional_usdt"]) == mark
    assert review["legacy_executable_action_count"] == 0


def test_execution_readiness_blockers_complete_and_deterministic():
    na = md.build_network_audit(
        ticker_http_request_count=52, ticker_requested_symbol_count=52,
        ticker_unique_symbol_count=52, ticker_cache_hit_count=0,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)
    r1 = _review_with_evidence(positions=_legacy_positions(), network_audit=na)
    r2 = _review_with_evidence(positions=_legacy_positions(), network_audit=na)
    assert r1["execution_readiness_blockers"] == r2["execution_readiness_blockers"]
    blockers = r1["execution_readiness_blockers"]
    # Margin + freshness unavailable -> both blockers present.
    assert md.MARGIN_EVIDENCE_UNAVAILABLE in blockers
    assert md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE in blockers
    # The batch is never authorised in this task even if all evidence passed.
    assert md.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK in blockers


def test_network_mismatch_blocker_in_review():
    na = md.build_network_audit(
        ticker_http_request_count=50, ticker_requested_symbol_count=50,
        ticker_unique_symbol_count=52, ticker_cache_hit_count=0,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)
    review = _review_with_evidence(positions=_legacy_positions(), network_audit=na)
    assert review["network_audit_status"] == md.NETWORK_AUDIT_COUNTER_MISMATCH
    assert md.NETWORK_AUDIT_COUNTER_MISMATCH in review["execution_readiness_blockers"]


def test_review_execution_unauthorized_and_zero_counts():
    review = _review_with_evidence(positions=_legacy_positions())
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False
    assert review["sender_reachable"] is False
    assert review["order_post_count"] == 0
    assert review["amend_post_count"] == 0
    assert review["cancel_post_count"] == 0
    assert review["execute_daily_native_call_count"] == 0
    assert review["transport_sender_call_count"] == 0
    assert review["live_endpoint_called"] is False


def test_margin_model_complete_still_unauthorized():
    # Even with COMPLETE margin evidence + consistent network + fresh price, the
    # batch stays unauthorised in this task.
    pass_evidence = md.build_price_freshness_evidence([
        {"symbol": s, "price_freshness_status": md.PRICE_FRESHNESS_PASS} for s in _50_symbols()])
    na = md.build_network_audit(
        ticker_http_request_count=52, ticker_requested_symbol_count=52,
        ticker_unique_symbol_count=52, ticker_cache_hit_count=0,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)
    review = _review_with_evidence(
        positions=_legacy_positions(), margin_evidence=_authoritative_margin(),
        applicable_initial_margin_rate=0.05, network_audit=na,
        price_freshness_evidence=pass_evidence)
    assert review["margin_model_status"] == md.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    assert review["network_audit_status"] == md.NETWORK_AUDIT_CONSISTENT
    assert review["price_freshness_status"] == md.PRICE_FRESHNESS_PASS
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False
    assert md.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK in review["execution_readiness_blockers"]


# ===========================================================================
# 8. CLI integration: priced-symbol counts, margin evidence, byte identity
# ===========================================================================


def test_cli_priced_symbol_counts_and_consistency():
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    na = review["network_audit"]
    assert na is not None
    assert na["total_priced_symbol_count"] == 52
    assert na["strategy_target_priced_symbol_count"] == 50
    assert na["legacy_mark_priced_symbol_count"] == 2
    assert na["ticker_unique_symbol_count"] == 52
    assert na["ticker_http_request_count"] == 52
    # Repeated per-symbol lookups (planner + review) are served from cache.
    assert na["ticker_cache_hit_count"] > 0
    assert na["ticker_http_request_count"] != na["ticker_requested_symbol_count"]
    assert na["network_audit_status"] == md.NETWORK_AUDIT_CONSISTENT


def test_cli_margin_evidence_captured_no_assumption():
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    ev = review["margin_evidence"]
    assert ev is not None
    assert ev["margin_evidence_snapshot_fingerprint"].startswith("sha256:")
    # The fixture readonly path does not surface per-position IM -> stays unavailable.
    assert review["margin_model_status"] in (
        md.MARGIN_EVIDENCE_UNAVAILABLE, md.AUTHORITATIVE_MARGIN_MODEL_PARTIAL)
    assert review["execution_batch_authorized"] is False
    assert review["order_post_count"] == 0


def test_cli_freshness_evidence_present_not_conflated():
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    pf = review["price_freshness_evidence"]
    assert pf is not None
    assert pf["snapshot_count"] == 52
    for snap in pf["snapshots"]:
        # local-only observation -> never claims an exchange timestamp.
        assert snap["exchange_timestamp"] is None
        assert snap["price_freshness_status"] in (
            md.PRICE_FRESHNESS_EVIDENCE_PARTIAL, md.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE,
            md.PRICE_FRESHNESS_STALE)


def test_cli_pilot_state_byte_identical(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    state_path = pathlib.Path(out_root)
    before = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert before
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    after = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert after == before


def test_existing_fix1_tests_module_still_imports():
    # Sanity: the FIX1 review module and its constants remain intact.
    assert v1.RULE_VALIDATION_PASS == "RULE_VALIDATION_PASS"
    assert hasattr(v1, "build_strategy_native_review")
