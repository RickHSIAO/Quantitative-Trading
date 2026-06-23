"""TASK-014CE -- authoritative account-mode / margin-tier / exchange-clock evidence.

Proves, fully offline:
  * the narrow read-only endpoint guard allows ONLY GET /v5/account/info,
    /v5/market/time, /v5/market/risk-limit and denies set-margin-mode / order /
    position-mutation / Live paths;
  * account marginMode parses + validates (REGULAR / ISOLATED / PORTFOLIO), malformed
    fails closed, fingerprint is deterministic;
  * fail-closed risk-tier selection (sorted, exact boundary, exposure outside limits,
    missing initialMargin, maxLeverage alone, accountIMRate never reused);
  * explicit REGULAR / ISOLATED / PORTFOLIO margin-mode branching, exact Decimal sum of
    50 projected action margins, one-incomplete-keeps-PARTIAL, observed legacy stays
    observed;
  * Bybit server-time second/nano parsing, bracket ordering, deterministic clock offset,
    REST envelope time is not a quote timestamp, freshness can never become PASS from a
    server-time bracket;
  * the extended network counters have one canonical meaning and top-level mirrors
    nested; and the execution batch remains UNAUTHORISED with zero order/Live posts.
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
from src import demo_strategy_native_v1_portfolio as v1
from src import demo_readonly_client as rc
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

# A two-tier authoritative risk-limit ladder (rates are fractions, not leverage).
TIERS = [
    {"id": 1, "symbol": "X", "riskLimitValue": "2000000", "initialMargin": "0.01",
     "maintenanceMargin": "0.005", "maxLeverage": "100.00", "isLowestRisk": 1},
    {"id": 2, "symbol": "X", "riskLimitValue": "4000000", "initialMargin": "0.02",
     "maintenanceMargin": "0.01", "maxLeverage": "50.00", "isLowestRisk": 0},
]


# ===========================================================================
# A. Read-only endpoint guard
# ===========================================================================


def test_new_read_only_paths_allowed():
    for p in ("/v5/account/info", "/v5/market/time", "/v5/market/risk-limit"):
        assert p in rc._ALLOWED_PATHS


def test_write_paths_denied():
    for p in ("/v5/account/set-margin-mode", "/v5/order/create", "/v5/order/create-batch",
              "/v5/order/amend", "/v5/order/cancel", "/v5/position/set-leverage",
              "/v5/position/switch-isolated"):
        assert p not in rc._ALLOWED_PATHS
        assert p in rc._FORBIDDEN_WRITE_PATHS


def test_allowed_and_forbidden_paths_disjoint():
    assert rc._ALLOWED_PATHS.isdisjoint(rc._FORBIDDEN_WRITE_PATHS)


def test_get_raises_on_forbidden_path():
    c = rc.DemoReadOnlyClient(allow_real_network=True)
    with pytest.raises(ValueError):
        c._get("/v5/account/set-margin-mode", {}, signed=True)
    with pytest.raises(ValueError):
        c._get("/v5/order/create", {}, signed=True)


def test_no_generic_account_get_allow_rule():
    # An arbitrary unlisted account endpoint must NOT be allowed.
    assert "/v5/account/transaction-log" not in rc._ALLOWED_PATHS
    c = rc.DemoReadOnlyClient(allow_real_network=True)
    with pytest.raises(ValueError):
        c._get("/v5/account/transaction-log", {}, signed=True)


def test_fixture_mode_account_info_unavailable():
    c = rc.DemoReadOnlyClient(allow_real_network=False)
    ai = c.get_account_info()
    assert ai.response_present is False and ai.margin_mode is None
    st = c.get_server_time()
    assert st.response_present is False
    assert c.get_risk_limit("BTCUSDT") == {}


# ===========================================================================
# B. Account marginMode evidence
# ===========================================================================


@pytest.mark.parametrize("mode", [ce.MARGIN_MODE_REGULAR, ce.MARGIN_MODE_ISOLATED,
                                  ce.MARGIN_MODE_PORTFOLIO])
def test_margin_mode_parses_for_all_supported(mode):
    ev = ce.normalize_account_mode_evidence(margin_mode=mode, unified_margin_status=3,
                                            updated_time="1700000000000")
    assert ev["margin_mode"] == mode
    assert ev["account_mode_evidence_status"] == ce.ACCOUNT_MODE_EVIDENCE_AUTHORITATIVE


def test_unified_margin_status_and_updated_time_retained():
    ev = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN",
                                            unified_margin_status=5, updated_time="1700000000001")
    assert ev["unified_margin_status"] == 5
    assert ev["updated_time"] == "1700000000001"


def test_account_evidence_fingerprint_deterministic():
    a = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN", unified_margin_status=3,
                                           updated_time="1700000000000")
    b = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN", unified_margin_status=3,
                                           updated_time="1700000000000")
    assert a["account_info_evidence_fingerprint"] == b["account_info_evidence_fingerprint"]
    c = ce.normalize_account_mode_evidence(margin_mode="ISOLATED_MARGIN", unified_margin_status=3,
                                           updated_time="1700000000000")
    assert c["account_info_evidence_fingerprint"] != a["account_info_evidence_fingerprint"]


def test_malformed_account_info_fails_closed():
    ev = ce.normalize_account_mode_evidence(margin_mode="WEIRD_MODE")
    assert ev["margin_mode"] is None
    assert ev["margin_mode_raw"] == "WEIRD_MODE"
    assert ev["account_mode_evidence_status"] == ce.ACCOUNT_MODE_EVIDENCE_MALFORMED


def test_absent_account_info_unavailable():
    ev = ce.unavailable_account_mode_evidence()
    assert ev["account_mode_evidence_status"] == ce.ACCOUNT_MODE_EVIDENCE_UNAVAILABLE
    assert ev["margin_mode"] is None


# ===========================================================================
# C. Risk-tier selection (fail closed)
# ===========================================================================


def test_tiers_sorted_ascending_deterministically():
    norm = ce.normalize_risk_tiers("X", list(reversed(TIERS)))
    assert [t["risk_id"] for t in norm] == [1, 2]
    assert [t["risk_limit_value"] for t in norm] == ["2000000", "4000000"]


def test_select_tier_lowest_band_for_small_exposure():
    sel = ce.select_risk_tier(symbol="X", combined_projected_exposure="200", tiers=TIERS)
    assert sel["risk_tier_selection_status"] == ce.RISK_TIER_APPLICABLE
    assert sel["applicable_risk_tier_id"] == 1
    assert sel["applicable_initial_margin_rate"] == "0.01"


def test_select_tier_exact_boundary():
    # Exposure exactly equal to tier-1 riskLimitValue stays in tier 1.
    sel = ce.select_risk_tier(symbol="X", combined_projected_exposure="2000000", tiers=TIERS)
    assert sel["applicable_risk_tier_id"] == 1
    # One unit above tier-1 boundary moves to tier 2.
    sel2 = ce.select_risk_tier(symbol="X", combined_projected_exposure="2000001", tiers=TIERS)
    assert sel2["applicable_risk_tier_id"] == 2
    assert sel2["applicable_initial_margin_rate"] == "0.02"


def test_exposure_above_all_tiers_fails_closed():
    sel = ce.select_risk_tier(symbol="X", combined_projected_exposure="5000000", tiers=TIERS)
    assert sel["risk_tier_selection_status"] == ce.RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS
    assert sel["applicable_initial_margin_rate"] is None


def test_missing_tiers_fails_closed():
    sel = ce.select_risk_tier(symbol="X", combined_projected_exposure="200", tiers=[])
    assert sel["risk_tier_selection_status"] == ce.RISK_TIER_EVIDENCE_MISSING


def test_missing_initial_margin_fails_closed():
    tiers = [{"id": 1, "symbol": "X", "riskLimitValue": "2000000",
              "maintenanceMargin": "0.005", "maxLeverage": "100", "isLowestRisk": 1}]
    sel = ce.select_risk_tier(symbol="X", combined_projected_exposure="200", tiers=tiers)
    assert sel["risk_tier_selection_status"] == ce.RISK_TIER_EVIDENCE_MISSING
    assert sel["applicable_initial_margin_rate"] is None


def test_max_leverage_alone_is_insufficient():
    # A tier carrying ONLY maxLeverage (no authoritative initialMargin) must NOT yield a
    # rate (no 1/maxLeverage inference).
    tiers = [{"id": 1, "symbol": "X", "riskLimitValue": "2000000", "maxLeverage": "100"}]
    sel = ce.select_risk_tier(symbol="X", combined_projected_exposure="200", tiers=tiers)
    assert sel["risk_tier_selection_status"] == ce.RISK_TIER_EVIDENCE_MISSING
    assert sel["applicable_initial_margin_rate"] is None


def test_not_lowest_tier_just_because_is_lowest_risk_flag():
    # Exposure that does not fit tier 1 must select tier 2 even though tier 1 has
    # isLowestRisk=1.
    sel = ce.select_risk_tier(symbol="X", combined_projected_exposure="3000000", tiers=TIERS)
    assert sel["applicable_risk_tier_id"] == 2


def test_risk_tier_evidence_fingerprint_deterministic():
    a = ce.select_risk_tier(symbol="X", combined_projected_exposure="200", tiers=TIERS)
    b = ce.select_risk_tier(symbol="X", combined_projected_exposure="999", tiers=TIERS)
    # Fingerprint is over the tier ladder identity, not the exposure.
    assert a["risk_tier_evidence_fingerprint"] == b["risk_tier_evidence_fingerprint"]


# ===========================================================================
# D. Margin-mode branching + projected Strategy margin
# ===========================================================================


def test_regular_margin_projects_complete():
    p = ce.project_action_margin(symbol="C0USDT", projected_symbol_notional_usdt="200",
                                 tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR)
    assert p["projected_margin_evidence_status"] == ce.PROJECTED_MARGIN_EVIDENCE_COMPLETE
    assert p["projected_action_initial_margin_usdt"] == "2"        # 200 * 0.01
    assert p["projected_action_maintenance_margin_usdt"] == "1"    # 200 * 0.005


def test_isolated_margin_stays_partial():
    p = ce.project_action_margin(symbol="C0USDT", projected_symbol_notional_usdt="200",
                                 tiers=TIERS, margin_mode=ce.MARGIN_MODE_ISOLATED)
    assert p["projected_margin_evidence_status"] == ce.PROJECTED_MARGIN_EVIDENCE_PARTIAL
    assert p["projected_action_initial_margin_usdt"] is None


def test_portfolio_margin_never_complete():
    p = ce.project_action_margin(symbol="C0USDT", projected_symbol_notional_usdt="200",
                                 tiers=TIERS, margin_mode=ce.MARGIN_MODE_PORTFOLIO)
    assert p["projected_margin_evidence_status"] == ce.PROJECTED_MARGIN_EVIDENCE_PARTIAL
    assert p["risk_tier_selection_status"] == ce.RISK_TIER_SCOPE_NOT_APPLICABLE_TO_MARGIN_MODE


def test_combined_exposure_uses_existing_same_symbol():
    p = ce.project_action_margin(symbol="C0USDT", projected_symbol_notional_usdt="200",
                                 existing_same_symbol_notional_usdt="100", tiers=TIERS,
                                 margin_mode=ce.MARGIN_MODE_REGULAR)
    assert p["combined_projected_symbol_exposure_usdt"] == "300"
    assert p["existing_same_symbol_notional_usdt"] == "100"
    # Projected IM uses the NEW strategy notional (200), not the combined value.
    assert p["projected_action_initial_margin_usdt"] == "2"


def test_account_im_rate_never_reused_as_projected():
    # accountIMRate is NOT an input to project_action_margin: only the authoritative
    # tier initialMargin rate is used. A wildly different accountIMRate cannot leak in.
    p = ce.project_action_margin(symbol="C0USDT", projected_symbol_notional_usdt="200",
                                 tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR)
    # 200 * 0.01 == 2 (tier rate), never 200 * accountIMRate.
    assert p["applicable_initial_margin_rate"] == "0.01"
    assert p["projected_action_initial_margin_usdt"] == "2"


def test_decimal_arithmetic_preserved_no_float_artifact():
    p = ce.project_action_margin(symbol="C0USDT", projected_symbol_notional_usdt="0.1",
                                 tiers=[{"id": 1, "riskLimitValue": "100", "initialMargin": "0.1",
                                         "maintenanceMargin": "0.05", "maxLeverage": "10"}],
                                 margin_mode=ce.MARGIN_MODE_REGULAR)
    assert p["projected_action_initial_margin_usdt"] == "0.01"  # 0.1 * 0.1 exact Decimal


def test_50_projected_action_margins_sum_exactly():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN", unified_margin_status=3)
    projs = [ce.project_action_margin(symbol=f"C{i}USDT", projected_symbol_notional_usdt="200",
                                      tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR)
             for i in range(50)]
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs,
                                          observed_legacy_position_initial_margin_sum_usdt="3.5",
                                          available_balance="8500")
    assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    assert model["projected_strategy_initial_margin_usdt"] == "100"      # 50 * 2
    assert model["projected_strategy_maintenance_margin_usdt"] == "50"   # 50 * 1
    assert model["projected_total_initial_margin_usdt"] == "103.5"       # +observed legacy


def test_one_incomplete_action_keeps_model_partial():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    projs = [ce.project_action_margin(symbol=f"C{i}USDT", projected_symbol_notional_usdt="200",
                                      tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR)
             for i in range(49)]
    # One action with exposure outside all tiers -> UNAVAILABLE.
    projs.append(ce.project_action_margin(symbol="C49USDT", projected_symbol_notional_usdt="9999999",
                                          tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR))
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs)
    assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
    assert model["projected_strategy_initial_margin_usdt"] is None
    assert ce.RISK_TIER_EXPOSURE_OUTSIDE_RETRIEVED_LIMITS in model["margin_model_blockers"]


def test_portfolio_model_partial_with_blocker():
    am = ce.normalize_account_mode_evidence(margin_mode="PORTFOLIO_MARGIN")
    projs = [ce.project_action_margin(symbol=f"C{i}USDT", projected_symbol_notional_usdt="200",
                                      tiers=TIERS, margin_mode=ce.MARGIN_MODE_PORTFOLIO)
             for i in range(50)]
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs)
    assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
    assert ce.PORTFOLIO_MARGIN_STATIC_RATE_NOT_APPLICABLE in model["margin_model_blockers"]
    assert model["projected_strategy_initial_margin_usdt"] is None


def test_unavailable_account_mode_keeps_model_blocked():
    am = ce.unavailable_account_mode_evidence()
    projs = [ce.project_action_margin(symbol="C0USDT", projected_symbol_notional_usdt="200",
                                      tiers=TIERS, margin_mode=None)]
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs)
    assert model["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
    assert ce.ACCOUNT_MARGIN_MODE_UNAVAILABLE in model["margin_model_blockers"]


def test_observed_legacy_im_remains_observed():
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    projs = [ce.project_action_margin(symbol=f"C{i}USDT", projected_symbol_notional_usdt="200",
                                      tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR)
             for i in range(50)]
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs,
                                          observed_legacy_position_initial_margin_sum_usdt="7.25")
    # Observed legacy IM is carried as OBSERVED, never relabelled projected.
    assert model["observed_legacy_position_initial_margin_sum_usdt"] == "7.25"


# ===========================================================================
# E. Exchange-clock evidence
# ===========================================================================


def test_server_time_second_nano_parsing():
    ev = ce.build_exchange_clock_evidence(before_time_second="1700000000",
                                          after_time_second="1700000002")
    assert ev["exchange_server_time_before"] == "1700000000"
    assert ev["exchange_server_time_after"] == "1700000002"
    assert ev["server_time_bracket_duration_seconds"] == "2"


def test_server_time_nano_fallback():
    ev = ce.build_exchange_clock_evidence(before_time_nano="1700000000000000000",
                                          after_time_nano="1700000001500000000")
    assert ev["exchange_server_time_before"] == "1700000000"
    assert ev["server_time_bracket_duration_seconds"] == "1.5"


def test_bracket_ordering_valid():
    ok = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="105")
    assert ok["server_time_bracket_ordered"] is True
    bad = ce.build_exchange_clock_evidence(before_time_second="105", after_time_second="100")
    assert bad["server_time_bracket_ordered"] is False


def test_clock_offset_deterministic():
    ev = ce.build_exchange_clock_evidence(before_time_second="1700000005",
                                          after_time_second="1700000007",
                                          local_observation_epoch_for_offset="1700000003")
    assert ev["estimated_local_vs_exchange_clock_offset_seconds"] == "2"


def test_rest_envelope_time_not_quote_timestamp():
    ev = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="101",
                                          before_response_envelope_time="1700000000123")
    assert ev["rest_response_envelope_time_before"] == "1700000000123"
    assert "exchange_quote_timestamp" not in ev
    assert ev["per_symbol_exchange_quote_timestamp_available"] is False


def test_missing_per_symbol_quote_keeps_freshness_partial():
    ev = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="101")
    assert ev["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
    assert ev["execution_grade_freshness_complete"] is False


def test_freshness_never_pass_from_server_bracket():
    ev = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="101")
    assert ev["price_freshness_status"] != md.PRICE_FRESHNESS_PASS
    assert ev["websocket_ticker_ts_required_for_execution_grade"] is True
    assert ev["websocket_belongs_in_this_task"] is False


def test_clock_evidence_fingerprint_deterministic():
    a = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="101")
    b = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="101")
    assert a["server_time_evidence_fingerprint"] == b["server_time_evidence_fingerprint"]


# ===========================================================================
# F. Extended network audit
# ===========================================================================


def _account_network(**over):
    base = dict(instrument_metadata_public_get_count=1, ticker_http_request_count=52,
                ticker_requested_symbol_count=152, ticker_unique_symbol_count=52,
                ticker_cache_hit_count=100, server_time_public_get_count=2,
                risk_limit_public_get_count=52, risk_limit_page_count=52,
                account_info_private_read_only_get_count=1,
                wallet_private_read_only_get_count=1,
                positions_private_read_only_get_count=1)
    base.update(over)
    return ce.build_account_network_audit(**base)


def test_account_network_audit_consistent_and_totals():
    na = _account_network()
    assert na["network_audit_status"] == ce.NETWORK_AUDIT_CONSISTENT
    # total public = instrument(1) + ticker_http(52) + server_time(2) + risk_limit(52)
    assert na["total_public_get_count"] == 1 + 52 + 2 + 52 == 107
    # total private = account_info(1) + wallet(1) + positions(1)
    assert na["total_private_read_only_get_count"] == 3
    assert na["order_post_count"] == 0 and na["live_endpoint_called"] is False


def test_account_network_counters_one_canonical_meaning():
    na = _account_network()
    keys = [k for k in na if k.endswith("_count")]
    assert len(keys) == len(set(keys))
    # request vs cache vs unique are distinct fields.
    assert na["ticker_http_request_count"] != na["ticker_requested_symbol_count"]
    assert na["ticker_cache_hit_count"] == 100


def test_account_network_audit_mismatch_fails_closed():
    na = _account_network(ticker_cache_hit_count=99)  # 52 + 99 != 152
    assert na["network_audit_status"] == ce.NETWORK_AUDIT_COUNTER_MISMATCH


# ===========================================================================
# G. Readiness-blocker reconciliation
# ===========================================================================


def test_blockers_resolve_account_mode_when_authoritative():
    base = [ce.ACCOUNT_MARGIN_MODE_UNAVAILABLE,
            ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE,
            ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK]
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    out = ce.reconcile_readiness_blockers(base_blockers=base, account_mode_evidence=am,
                                          account_margin_model=None, exchange_clock_evidence=None)
    assert ce.ACCOUNT_MARGIN_MODE_UNAVAILABLE not in out
    assert out[-1] == ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK


def test_blockers_resolve_im_rate_when_model_complete():
    base = [ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE,
            ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK]
    am = ce.normalize_account_mode_evidence(margin_mode="REGULAR_MARGIN")
    projs = [ce.project_action_margin(symbol=f"C{i}USDT", projected_symbol_notional_usdt="200",
                                      tiers=TIERS, margin_mode=ce.MARGIN_MODE_REGULAR)
             for i in range(50)]
    model = ce.build_account_margin_model(account_mode_evidence=am, per_action_projections=projs)
    out = ce.reconcile_readiness_blockers(base_blockers=base, account_mode_evidence=am,
                                          account_margin_model=model, exchange_clock_evidence=None)
    assert ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE not in out
    assert out[-1] == ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK


def test_blockers_merge_clock_and_keep_auth_last():
    base = [ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK]
    clk = ce.build_exchange_clock_evidence(before_time_second="100", after_time_second="101")
    out = ce.reconcile_readiness_blockers(base_blockers=base, account_mode_evidence=None,
                                          account_margin_model=None, exchange_clock_evidence=clk)
    assert ce.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE in out
    assert ce.EXCHANGE_CLOCK_BRACKET_ONLY in out
    assert out[-1] == ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK
    assert out.count(ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK) == 1


# ===========================================================================
# H. CLI integration (CE-aware provider, fully offline)
# ===========================================================================


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class CEProvider:
    """CE-aware offline provider: REGULAR margin mode + a tier ladder that covers the
    +/-200-USDT Strategy notionals so the projected margin model reaches COMPLETE."""

    def __init__(self, *, symbols, prices, positions=None, margin_mode="REGULAR_MARGIN"):
        self._symbols = symbols
        self._prices = prices
        self._positions = positions or []
        self._margin_mode = margin_mode
        self._price_cache: dict = {}
        self._http = 0
        self._requested = 0
        self._cache_hits = 0
        self._obs: dict = {}
        self._rl_get = 0
        self._rl_pages = 0
        self._st_get = 1  # before-bracket captured at init
        self._ai_get = 1

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
                "initial_margin": None, "maintenance_margin": None,
                "position_value": None, "mark_price": None, "liq_price": None}
               for p in self._positions]
        return md.normalize_margin_evidence(
            margin_evidence_source="fixture-readonly", account_type="UNIFIED",
            account_margin_mode=self._margin_mode, wallet_equity=INIT,
            available_balance=8_500.0, per_position=per)

    # --- CE methods --------------------------------------------------------
    def account_mode_evidence(self):
        return ce.normalize_account_mode_evidence(
            margin_mode=self._margin_mode, unified_margin_status=3,
            updated_time="1700000000000", request_started_at_utc="s",
            response_received_at_utc="r", request_elapsed_ms=1.0)

    def risk_limit_tiers(self, symbol):
        self._rl_get += 1
        self._rl_pages += 1
        return [dict(t, symbol=symbol) for t in TIERS]

    def exchange_clock_evidence(self, **window):
        self._st_get += 1  # after-bracket
        return ce.build_exchange_clock_evidence(
            before_time_second="1700000000", before_local_response_received_at_utc="b",
            before_local_monotonic_start=100.0, before_local_monotonic_end=100.01,
            after_time_second="1700000002", after_local_response_received_at_utc="a",
            after_local_monotonic_start=101.0, after_local_monotonic_end=101.01,
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


def _plan_and_provider(positions=None, margin_mode="REGULAR_MARGIN"):
    syms = _50_symbols()
    prices = {s: 2.0 for s in syms}
    prices.update({"EDUUSDT": 0.6, "POLYXUSDT": 0.3})
    prov = CEProvider(symbols=syms, prices=prices, positions=positions, margin_mode=margin_mode)
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


def test_cli_review_regular_margin_model_complete(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider(positions=_legacy_positions(), margin_mode="REGULAR_MARGIN")
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    # CE evidence blocks present.
    assert review["account_mode_evidence"]["margin_mode"] == "REGULAR_MARGIN"
    assert review["risk_limit_evidence"]["symbol_count"] == 50
    pm = review["projected_margin_model"]
    assert pm["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_COMPLETE
    assert pm["projected_strategy_initial_margin_usdt"] == "100"  # 50 * 200 * 0.01
    # Strategy core preserved.
    assert review["target_position_count"] == 50
    assert review["non_null_rule_fingerprint_count"] == 50
    assert review["batch_float_artifact_count"] == 0
    # ACCOUNT_MARGIN_MODE_UNAVAILABLE + APPLICABLE rate resolved.
    blk = review["execution_readiness_blockers"]
    assert ce.ACCOUNT_MARGIN_MODE_UNAVAILABLE not in blk
    assert ce.APPLICABLE_INITIAL_MARGIN_RATE_UNAVAILABLE not in blk
    assert blk[-1] == ce.EXECUTION_AUTHORIZATION_NOT_GRANTED_THIS_TASK
    # Still unauthorised regardless.
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False
    assert review["sender_reachable"] is False
    assert review["order_post_count"] == 0
    assert review["live_trading_authorized"] is False


def test_cli_review_portfolio_margin_stays_partial(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider(positions=_legacy_positions(), margin_mode="PORTFOLIO_MARGIN")
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    pm = review["projected_margin_model"]
    assert pm["margin_model_status"] == ce.AUTHORITATIVE_MARGIN_MODEL_PARTIAL
    assert ce.PORTFOLIO_MARGIN_STATIC_RATE_NOT_APPLICABLE in review["execution_readiness_blockers"]
    assert review["execution_batch_authorized"] is False


def test_cli_review_exchange_clock_and_network(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    clk = review["exchange_clock_evidence"]
    assert clk["exchange_clock_bracket_available"] is True
    assert clk["per_symbol_exchange_quote_timestamp_available"] is False
    assert clk["price_freshness_status"] == md.PRICE_FRESHNESS_EVIDENCE_PARTIAL
    na = review["account_network_audit"]
    assert na["network_audit_status"] == ce.NETWORK_AUDIT_CONSISTENT
    assert na["server_time_public_get_count"] == 2          # before + after bracket
    assert na["risk_limit_public_get_count"] == 50          # 50 strategy targets (legacy excluded)
    assert na["risk_limit_page_count"] == 50                # symbol-specific: 1 page per GET
    assert na["account_info_private_read_only_get_count"] == 1
    # Freshness blockers present.
    assert ce.PER_SYMBOL_EXCHANGE_QUOTE_TIMESTAMP_UNAVAILABLE in review["execution_readiness_blockers"]


def test_cli_pilot_state_byte_identical(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    state_path = pathlib.Path(out_root)
    before = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert before
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    after = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert after == before


def test_cli_review_no_dispatch_counters(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _plan_and_provider(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    assert review["execute_daily_native_call_count"] == 0
    assert review["transport_sender_call_count"] == 0
    assert review["order_post_count"] == 0
    assert review["amend_post_count"] == 0
    assert review["cancel_post_count"] == 0
    assert review["live_endpoint_called"] is False
