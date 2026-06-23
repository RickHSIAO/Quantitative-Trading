"""TASK-014CE_FIX1 -- canonical margin / network / blocker reconciliation.

Proves, fully offline, the schema reconciliation on top of the VPS-run TASK-014CE review:
  * authoritative REGULAR_MARGIN + available balance are wired into projected_margin_model;
  * the 50 projected IM and MM values sum exactly and the canonical margin_model_status
    becomes AUTHORITATIVE_MARGIN_MODEL_COMPLETE while the observed NON-ATOMIC snapshot
    status stays separately represented;
  * AUTHORITATIVE_MARGIN_MODEL_PARTIAL / ACCOUNT_MARGIN_MODE_UNAVAILABLE /
    APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE are removed from the readiness blockers once
    the projected model is complete, while NON_ATOMIC_MARGIN_SNAPSHOT remains and the
    authorization blocker stays last;
  * there is ONE canonical complete-account network_audit (top-level mirrors it exactly,
    105 public / 3 private), account_network_audit is an exact alias, and the ticker/
    planner-only counts live under an explicitly scoped name;
  * the exchange-clock block has an explicit status, real field names, a deterministic
    high-resolution clock offset, and never promotes freshness to PASS; and
  * the execution batch stays unauthorised with zero order/Live posts.
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

from src import demo_strategy_native_account_mode_risk_tier_audit as ce
from src import demo_strategy_native_margin_freshness_audit as md
from src import demo_strategy_pilot_action_planner as ap
from src import demo_strategy_pilot_lifecycle as lc
from src import demo_strategy_pilot_readiness as rd
from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition

daily_cli = importlib.import_module("scripts.run_demo_strategy_pilot_native_daily")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
DATE = "2026-06-22"
INIT = 10_000.0
AVAIL = 9606.53486705
FULL_ENV = {"NOTION_TOKEN": "tok", "NOTION_PILOT_DATABASE_ID": "db",
            "MONITOR_DISCORD_WEBHOOK_URL": "http://hook"}
DEMO_ENV = dict(FULL_ENV, BYBIT_DEMO_API_KEY="DEMOKEY", BYBIT_DEMO_API_SECRET="DEMOSECRET")

TIERS = [
    {"id": 1, "symbol": "X", "riskLimitValue": "2000000", "initialMargin": "0.01",
     "maintenanceMargin": "0.005", "maxLeverage": "100.00", "isLowestRisk": 1},
    {"id": 2, "symbol": "X", "riskLimitValue": "4000000", "initialMargin": "0.02",
     "maintenanceMargin": "0.01", "maxLeverage": "50.00", "isLowestRisk": 0},
]


# ===========================================================================
# A. Projected-margin field wiring + exact sums
# ===========================================================================


def _regular_projections(n=50):
    return [ce.project_action_margin(symbol=f"C{i}USDT", projected_symbol_notional_usdt="200",
                                     tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR)
            for i in range(n)]


def test_account_margin_mode_and_available_balance_wired():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN", unified_margin_status=3,
                                            spot_hedging_status="OFF")
    model = ce.build_account_margin_model(account_mode_evidence=am,
                                          per_action_projections=_regular_projections(),
                                          observed_legacy_position_initial_margin_sum_usdt="1795.55557102",
                                          available_balance=str(AVAIL))
    assert model["account_margin_mode"] == "REGULAR_MARGIN"
    assert model["available_balance_usdt"] == "9606.53486705"
    assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_COMPLETE


def test_projected_im_and_mm_sum_exactly():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    projs = _regular_projections()
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs,
                                          observed_legacy_position_initial_margin_sum_usdt="1795.55557102",
                                          available_balance=str(AVAIL))
    # 50 * (200 * 0.01) = 100 IM ; 50 * (200 * 0.005) = 50 MM.
    assert model["projected_strategy_initial_margin_usdt"] == "100"
    assert model["projected_strategy_maintenance_margin_usdt"] == "50"
    assert model["projected_strategy_initial_margin_exact_sum_usdt"] == "100"
    assert model["projected_strategy_initial_margin_exact_sum_matches"] is True
    # projected total = strategy 100 + observed legacy 1795.55557102.
    assert model["projected_total_initial_margin_usdt"] == "1895.55557102"
    assert model["observed_legacy_position_initial_margin_sum_usdt"] == "1795.55557102"


def test_account_im_rate_not_used_flag():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    model = ce.build_account_margin_model(account_mode_evidence=am,
                                          per_action_projections=_regular_projections())
    assert model["account_im_rate_used_for_projection"] is False


def test_all_50_actions_have_projected_im_and_mm():
    projs = _regular_projections()
    assert sum(1 for p in projs if p["projected_action_initial_margin_usdt"] is not None) == 50
    assert sum(1 for p in projs if p["projected_action_maintenance_margin_usdt"] is not None) == 50


def test_available_balance_is_evidence_only():
    # Even with a COMPLETE projected model + ample available balance, nothing is authorized.
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    model = ce.build_account_margin_model(account_mode_evidence=am,
                                          per_action_projections=_regular_projections(),
                                          available_balance="9999999")
    assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    # The model carries no authorization flag; it is pure evidence.
    assert "execution_authorized" not in model and "execution_ready" not in model


# ===========================================================================
# B. Canonical margin status + blocker reconciliation
# ===========================================================================


def test_complete_model_removes_partial_keeps_non_atomic():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    model = ce.build_account_margin_model(account_mode_evidence=am,
                                          per_action_projections=_regular_projections())
    base = [md.PRICE_FRESHNESS_EVIDENCE_PARTIAL,
            ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL,
            ce.NON_ATOMIC_MARGIN_SNAPSHOT,
            ce.ACCOUNT_MARGIN_MODE_UNAVAILABLE,
            ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE,
            ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK]
    clk = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="109")
    out = ce.reconcile_readiness_blockers(base_blockers=base, account_mode_evidence=am,
                                          account_margin_model=model, exchange_clock_evidence=clk)
    assert ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL not in out
    assert ce.ACCOUNT_MARGIN_MODE_UNAVAILABLE not in out
    assert ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE not in out
    assert ce.NON_ATOMIC_MARGIN_SNAPSHOT in out
    assert md.PRICE_FRESHNESS_EVIDENCE_PARTIAL in out
    assert ce.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE in out
    assert ce.EXCHANGE_CLOCK_BRACKET_ONLY in out
    assert out[-1] == ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK
    assert out.count(ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK) == 1


def test_incomplete_evidence_still_partial():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    projs = _regular_projections(49)
    projs.append(ce.project_action_margin(symbol="C49USDT", projected_symbol_notional_usdt="9999999",
                                          tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR))
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs)
    assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
    base = [ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE,
            ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK]
    out = ce.reconcile_readiness_blockers(base_blockers=base, account_mode_evidence=am,
                                          account_margin_model=model, exchange_clock_evidence=None)
    # Incomplete -> applicable-rate blocker is NOT resolved.
    assert ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE in out


def test_portfolio_and_isolated_remain_fail_closed():
    for mode, blocker in ((ce.MARGIN_MODE_PORTFOLIO, ce.PORTFOLIO_MARGIN_STATIC_RATE_NOT_APPLICABLE),
                          (ce.MARGIN_MODE_ISOLATED, ce.ISOLATED_MARGIN_PER_SYMBOL_SCOPE_NOT_PROVEN)):
        am = ce.normalize_account_mode_evidence(margin_mode=mode)
        projs = [ce.project_action_margin(symbol=f"C{i}USDT", projected_symbol_notional_usdt="200",
                                          tiers=TIERS, margin_mode=mode) for i in range(50)]
        model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs)
        assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
        assert blocker in model["margin_model_blockers"]
        assert model["projected_strategy_initial_margin_usdt"] is None


# ===========================================================================
# C. Canonical network audit (105 / 3) + alias + scoped CD block
# ===========================================================================


def test_canonical_network_105_public_3_private():
    na = ce.build_account_network_audit(
        instrument_metadata_public_get_count=1, ticker_http_request_count=52,
        ticker_requested_symbol_count=152, ticker_unique_symbol_count=52,
        ticker_cache_hit_count=100, server_time_public_get_count=2,
        risk_limit_public_get_count=50, risk_limit_page_count=50,
        account_info_private_read_only_get_count=1, wallet_private_read_only_get_count=1,
        positions_private_read_only_get_count=1,
        strategy_target_priced_symbol_count=50, legacy_mark_priced_symbol_count=2)
    assert na["total_public_get_count"] == 1 + 2 + 50 + 52 == 105
    assert na["total_private_read_only_get_count"] == 3
    assert na["total_priced_symbol_count"] == 52
    assert na["network_audit_status"] == ce.NETWORK_AUDIT_CONSISTENT


def test_total_get_arithmetic_documented():
    na = ce.build_account_network_audit(
        instrument_metadata_public_get_count=1, ticker_http_request_count=52,
        ticker_requested_symbol_count=152, ticker_unique_symbol_count=52,
        ticker_cache_hit_count=100, server_time_public_get_count=2,
        risk_limit_public_get_count=50, risk_limit_page_count=50,
        account_info_private_read_only_get_count=1, wallet_private_read_only_get_count=1,
        positions_private_read_only_get_count=1)
    # Distinct semantics: requests vs cache vs unique vs pages.
    assert na["ticker_http_request_count"] == na["ticker_unique_symbol_count"] == 52
    assert na["ticker_cache_hit_count"] == 100
    assert na["risk_limit_page_count"] == na["risk_limit_public_get_count"] == 50


# ===========================================================================
# D. Exchange-clock status + high-resolution offset
# ===========================================================================


def test_exchange_clock_status_and_field_names():
    ev = ce.build_exchange_clock_evidence(
        before_time_second="1700000000", after_time_second="1700000009",
        first_ticker_observed_at_utc="2026-06-22T00:00:00Z",
        last_ticker_observed_at_utc="2026-06-22T00:00:09Z",
        before_response_envelope_time="1700000000123",
        after_response_envelope_time="1700000009456")
    assert ev["exchange_clock_evidence_status"] == ce.EXCHANGE_CLOCK_BRACKET_AVAILABLE
    assert ev["server_time_bracket_duration_seconds"] == "9"
    for field in ("exchange_server_time_before", "exchange_server_time_after",
                  "first_ticker_observed_at_utc", "last_ticker_observed_at_utc",
                  "rest_response_envelope_time_before", "rest_response_envelope_time_after"):
        assert field in ev


def test_high_resolution_clock_offset_deterministic():
    # before: server epoch 1700000000.5 (from nano), local midpoint 1700000000.0 -> +0.5
    # after:  server epoch 1700000009.5 (from nano), local midpoint 1700000009.0 -> +0.5
    ev = ce.build_exchange_clock_evidence(
        before_time_nano="1700000000500000000",
        before_local_request_epoch="1699999999.5", before_local_response_epoch="1700000000.5",
        after_time_nano="1700000009500000000",
        after_local_request_epoch="1700000008.5", after_local_response_epoch="1700000009.5")
    assert ev["clock_offset_evidence_status"] == ce.CLOCK_OFFSET_AVAILABLE
    assert ev["clock_offset_before_seconds"] == "0.5"
    assert ev["clock_offset_after_seconds"] == "0.5"
    assert ev["estimated_local_vs_exchange_clock_offset_seconds"] == "0.5"
    assert ev["clock_offset_range_seconds"] == ["0.5", "0.5"]
    # Determinism.
    ev2 = ce.build_exchange_clock_evidence(
        before_time_nano="1700000000500000000",
        before_local_request_epoch="1699999999.5", before_local_response_epoch="1700000000.5",
        after_time_nano="1700000009500000000",
        after_local_request_epoch="1700000008.5", after_local_response_epoch="1700000009.5")
    assert ev2["server_time_evidence_fingerprint"] == ev["server_time_evidence_fingerprint"]


def test_clock_offset_unavailable_has_explicit_status():
    ev = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="109")
    assert ev["estimated_local_vs_exchange_clock_offset_seconds"] is None
    assert ev["clock_offset_evidence_status"] == ce.CLOCK_OFFSET_LOCAL_TIMING_UNAVAILABLE
    assert ev["clock_offset_evidence_reason"]


def test_server_time_not_quote_time_freshness_partial():
    ev = ce.build_exchange_clock_evidence(
        before_time_second="100", after_time_second="109",
        before_response_envelope_time="123")
    assert "exchange_quote_timestamp" not in ev
    assert ev["per_symbol_exchange_quote_timestamp_available"] is False
    assert ev["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
    assert ev["price_freshness_status"] != md.PRICE_FRESHNESS_PASS


# ===========================================================================
# E. CLI integration (VPS-shaped CE provider)
# ===========================================================================


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class FIX1Provider:
    """VPS-shaped provider: REGULAR margin, 2 legacy positions WITH observed IM, server
    time bracketed with high-resolution local epochs."""

    def __init__(self, *, symbols, prices, positions, legacy_im):
        self._symbols = symbols
        self._prices = prices
        self._positions = positions
        self._legacy_im = legacy_im
        self._price_cache: dict = {}
        self._http = 0
        self._requested = 0
        self._cache_hits = 0
        self._obs: dict = {}
        self._rl_get = 0
        self._rl_pages = 0
        self._st_get = 1
        self._ai_get = 1

    def equity_usd(self): return INIT
    def available_balance_usd(self): return AVAIL
    def open_positions(self): return list(self._positions)

    def account_risk_snapshot(self):
        return {"wallet_equity_usd": INIT, "available_balance_usd": AVAIL,
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
        self._obs[symbol] = {"price_source": "tickers", "exchange_timestamp_ms": None,
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
                "initial_margin": self._legacy_im.get(p.symbol), "maintenance_margin": None,
                "position_value": None, "mark_price": None, "liq_price": None}
               for p in self._positions]
        return md.normalize_margin_evidence(
            margin_evidence_source="fixture-readonly", account_type="UNIFIED",
            account_margin_mode="REGULAR_MARGIN", wallet_equity=INIT,
            available_balance=AVAIL, per_position=per,
            total_initial_margin=str(sum(self._legacy_im.values())))

    def account_mode_evidence(self):
        return ce.normalize_account_mode_evidence(
            margin_mode="REGULAR_MARGIN", unified_margin_status=3, spot_hedging_status="OFF",
            updated_time="1700000000000", request_started_at_utc="s",
            response_received_at_utc="r", request_elapsed_ms=1.0)

    def risk_limit_tiers(self, symbol):
        self._rl_get += 1
        self._rl_pages += 1
        return [dict(t, symbol=symbol) for t in TIERS]

    def exchange_clock_evidence(self, **window):
        self._st_get += 1
        return ce.build_exchange_clock_evidence(
            before_time_nano="1700000000000000000",
            before_local_request_epoch="1699999999.5", before_local_response_epoch="1700000000.5",
            after_time_nano="1700000009000000000",
            after_local_request_epoch="1700000008.5", after_local_response_epoch="1700000009.5",
            **window)

    def account_network_counters(self):
        return {"account_info_private_read_only_get_count": self._ai_get,
                "server_time_public_get_count": self._st_get,
                "risk_limit_public_get_count": self._rl_get,
                "risk_limit_page_count": self._rl_pages}

    def audit(self):
        return {"instrument_metadata_public_get_count": 1,
                "wallet_private_read_only_get_count": 1,
                "positions_private_read_only_get_count": 1,
                "total_private_read_only_get_count": 2,
                "market_price_source": "tickers", "instrument_rule_source": "instruments-info",
                "instrument_rule_cache_count": len(self._symbols)}


def _50_symbols():
    return [f"C{i}USDT" for i in range(50)]


def _50_signals():
    return [{"symbol": s, "side": "long" if i < 25 else "short", "weight": 0.02, "score": 0.02}
            for i, s in enumerate(_50_symbols())]


def _legacy_positions():
    return [DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=1655.0,
                             entry_price=0.5, stop_price=0.6),
            DemoOpenPosition(symbol="POLYXUSDT", side="short", quantity=5615.6,
                             entry_price=0.25, stop_price=0.3)]


def _plan_and_provider():
    syms = _50_symbols()
    prices = {s: 2.0 for s in syms}
    prices.update({"EDUUSDT": 0.6, "POLYXUSDT": 0.3})
    legacy_im = {"EDUUSDT": 1000.0, "POLYXUSDT": 795.55557102}
    prov = FIX1Provider(symbols=syms, prices=prices, positions=_legacy_positions(),
                        legacy_im=legacy_im)
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(_50_signals()), provider=prov)
    return plan, prov


@pytest.fixture
def fwd_root(tmp_path):
    d = tmp_path / "fwd" / "prev3y_crypto"
    d.mkdir(parents=True)
    (d / "forward_summary.json").write_text(
        json.dumps({"strategy": "prev3y_crypto_combined_paper_safe_variant",
                    "latest_date": "20260518"}), encoding="utf-8")
    return str(tmp_path / "fwd")


def running_pilot(tmp_path, fwd_root):
    out = str(tmp_path / "out")
    rd.initialize_pilot(pilot_id=PILOT, acknowledged=True, env=FULL_ENV,
                        output_root=out, forward_source_root=fwd_root)
    lc.migrate_to_strategy_native(pilot_id=PILOT, acknowledged=True, output_root=out)
    lc.start_pilot(pilot_id=PILOT, acknowledged=True, env=DEMO_ENV, output_root=out)
    return out


def test_cli_canonical_margin_status_complete(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider()
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    # Canonical margin_model_status = projected (COMPLETE); observed snapshot separate.
    assert review["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    assert review["projected_margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    assert review["observed_margin_snapshot_model_status"] == md.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
    pm = review["projected_margin_model"]
    assert pm["account_margin_mode"] == "REGULAR_MARGIN"
    assert pm["available_balance_usdt"] == "9606.53486705"
    assert pm["projected_strategy_initial_margin_usdt"] == "100"
    assert pm["projected_strategy_maintenance_margin_usdt"] == "50"
    assert pm["observed_legacy_position_initial_margin_sum_usdt"] == "1795.55557102"
    assert pm["projected_total_initial_margin_usdt"] == "1895.55557102"


def test_cli_blockers_reconciled(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider()
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    blk = review["execution_readiness_blockers"]
    assert ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL not in blk
    assert ce.ACCOUNT_MARGIN_MODE_UNAVAILABLE not in blk
    assert ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE not in blk
    assert ce.NON_ATOMIC_MARGIN_SNAPSHOT in blk
    assert md.PRICE_FRESHNESS_EVIDENCE_PARTIAL in blk
    assert ce.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE in blk
    assert blk[-1] == ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK


def test_cli_one_canonical_network_audit(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider()
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    na = review["network_audit"]
    # Complete-account canonical counts.
    assert na["total_public_get_count"] == 105
    assert na["total_private_read_only_get_count"] == 3
    assert na["server_time_public_get_count"] == 2
    assert na["risk_limit_public_get_count"] == 50
    assert na["account_info_private_read_only_get_count"] == 1
    assert na["network_audit_status"] == ce.NETWORK_AUDIT_CONSISTENT
    # account_network_audit is an EXACT alias of network_audit.
    assert review["account_network_audit"] == na
    # The old ticker/planner-only block is scoped, not the canonical name.
    tp = review["ticker_price_network_audit"]
    assert tp is not None and "total_public_get_count" not in tp
    assert tp["ticker_http_request_count"] == 52


def test_cli_top_level_mirrors_nested_network(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider()
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    planner_audit = {"ticker_http_request_count": 50, "ticker_requested_symbol_count": 50,
                     "ticker_unique_symbol_count": 50, "ticker_cache_hit_count": 0}
    top = daily_cli._canonical_network_top_level(
        review=review, planner_phase_audit=planner_audit, instrument_metadata_get_count=1)
    na = review["network_audit"]
    assert top["total_public_get_count"] == na["total_public_get_count"] == 105
    assert top["total_private_read_only_get_count"] == na["total_private_read_only_get_count"] == 3
    assert top["server_time_public_get_count"] == na["server_time_public_get_count"] == 2
    assert top["risk_limit_public_get_count"] == na["risk_limit_public_get_count"] == 50
    assert top["ticker_http_request_count"] == na["ticker_http_request_count"] == 52
    # Planner-only counters remain explicitly scoped and distinct.
    assert top["planner_ticker_http_request_count"] == 50
    assert top["planner_ticker_http_request_count"] != top["ticker_http_request_count"]
    assert len(list(top.keys())) == len(set(top.keys()))


def test_cli_exchange_clock_status_and_offset(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider()
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    clk = review["exchange_clock_evidence"]
    assert clk["exchange_clock_evidence_status"] == ce.EXCHANGE_CLOCK_BRACKET_AVAILABLE
    assert clk["server_time_bracket_duration_seconds"] == "9"
    assert clk["clock_offset_evidence_status"] == ce.CLOCK_OFFSET_AVAILABLE
    assert clk["estimated_local_vs_exchange_clock_offset_seconds"] is not None
    assert clk["per_symbol_exchange_quote_timestamp_available"] is False
    assert clk["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL


def test_cli_v1_preserved_and_unauthorized(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider()
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    assert review["target_position_count"] == 50
    assert review["long_target_count"] == 25 and review["short_target_count"] == 25
    assert review["execution_batch"]["expected_action_count"] == 50
    assert review["non_null_rule_fingerprint_count"] == 50
    assert review["batch_float_artifact_count"] == 0
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False
    assert review["sender_reachable"] is False
    assert review["execute_daily_native_call_count"] == 0
    assert review["transport_sender_call_count"] == 0
    assert review["order_post_count"] == 0
    assert review["amend_post_count"] == 0
    assert review["cancel_post_count"] == 0
    assert review["live_endpoint_called"] is False
    assert review["live_trading_authorized"] is False


def test_cli_pilot_state_byte_identical(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    state_path = pathlib.Path(out_root)
    before = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert before
    plan, prov = _plan_and_provider()
    daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    after = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert after == before
