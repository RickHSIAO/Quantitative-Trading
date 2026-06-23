"""TASK-014CC -- ACTIVE Strategy-native V1 Demo portfolio policy tests.

Proves the active V1 policy follows the production-shaped multi-symbol strategy
portfolio: obsolete one-position / tiny one-shot limits are NOT the active policy,
the full 50-target plan is preserved, legacy protected positions are separated
(untouched, non-blocking, but counted toward account risk), reconciliation +
deterministic execution batch + feasibility work, and nothing is dispatched.
Fully offline: zero HTTP, zero Bybit, zero orders.
"""

from __future__ import annotations

import importlib
import json
import pathlib
import re
import sys
from decimal import Decimal

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src import demo_strategy_native_v1_portfolio as v1
from src import demo_strategy_pilot_action_planner as ap
from src import demo_strategy_pilot_lifecycle as lc
from src import demo_strategy_pilot_native_execution as nx
from src import demo_strategy_pilot_readiness as rd
from src import demo_only_tiny_execution_adapter as bh
from src.demo_instrument_rules import InstrumentRules
from src.demo_portfolio_risk import DemoOpenPosition

daily_cli = importlib.import_module("scripts.run_demo_strategy_pilot_native_daily")

PILOT = "BYBIT_DEMO_PILOT_7D_202606_V1"
DATE = "2026-06-22"
PROTECTED = frozenset(rd.PROTECTED_SYMBOLS)
INIT = 10_000.0
FULL_ENV = {"NOTION_TOKEN": "tok", "NOTION_PILOT_DATABASE_ID": "db",
            "MONITOR_DISCORD_WEBHOOK_URL": "http://hook"}
DEMO_ENV = dict(FULL_ENV, BYBIT_DEMO_API_KEY="DEMOKEY", BYBIT_DEMO_API_SECRET="DEMOSECRET")
_ARTIFACT_RE = re.compile(r"\d\.\d*(?:000000000000|999999999999)\d*")


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


class FakeForward:
    def __init__(self, signals):
        self.normalized_signals = tuple(signals)


class FakeProvider:
    def __init__(self, *, positions=None, prices=None, steps=None, symbols=None,
                 rule_status=None, min_qty=None, max_qty=None, min_notional=None,
                 leverage_authoritative=False,
                 initial_margin_authoritative=False, assumed_leverage=None,
                 equity=INIT, available=8_500.0):
        self._positions = positions or []
        self._symbols = symbols or []
        self._prices = prices or {s: 2.0 for s in self._symbols}
        self._steps = steps or {}
        self._rule_status = rule_status or {}
        self._min_qty = min_qty or {}
        self._max_qty = max_qty or {}
        self._min_notional = min_notional or {}
        self._lev_auth = leverage_authoritative
        self._im_auth = initial_margin_authoritative
        self._assumed_leverage = assumed_leverage
        self._equity = equity
        self._available = available

    def equity_usd(self): return self._equity
    def available_balance_usd(self): return self._available
    def open_positions(self): return list(self._positions)
    def market_price(self, symbol): return self._prices.get(symbol)

    def instrument_rule(self, symbol):
        step = self._steps.get(symbol, 0.1)
        return InstrumentRules(symbol=symbol, qty_step=step, min_qty=step, max_qty=0.0,
                               tick_size=0.01, min_notional=1.0,
                               price_precision=2, qty_precision=1)

    def instrument_rule_evidence(self, symbol):
        # Mirrors the REAL provider: numeric rule fields come only from the
        # InstrumentRules snapshot; no fingerprint is synthesised by the provider
        # (the module derives the authoritative fingerprint from these fields).
        status = self._rule_status.get(symbol, "TRADING")
        ev = {"symbol": symbol, "rule_status": status,
              "instrument_rule_source":
                  "DemoReadOnlyClient.get_instruments_info() -> /v5/market/instruments-info",
              "market_price_source": "DemoMarketPriceGuard -> /v5/market/tickers (public GET)",
              "market_price": self._prices.get(symbol)}
        if status == "TRADING":
            step = self._steps.get(symbol, 0.1)
            ev["qty_step"] = step
            ev["min_qty"] = self._min_qty.get(symbol, step)
            ev["max_qty"] = self._max_qty.get(symbol, 0.0)
            ev["min_notional"] = self._min_notional.get(symbol, 1.0)
            ev["tick_size"] = 0.01
        return ev

    def account_risk_snapshot(self):
        return {"wallet_equity_usd": self._equity, "available_balance_usd": self._available,
                "positions": [{"symbol": p.symbol, "side": p.side, "quantity": float(p.quantity),
                               "entry_price": float(p.entry_price), "leverage": 0.0}
                              for p in self._positions],
                "leverage_authoritative": self._lev_auth,
                "initial_margin_authoritative": self._im_auth,
                "assumed_leverage": self._assumed_leverage}


def _legacy_positions():
    return [
        DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=1655.0,
                         entry_price=0.5, stop_price=0.6),
        DemoOpenPosition(symbol="POLYXUSDT", side="short", quantity=5615.6,
                         entry_price=0.25, stop_price=0.3),
    ]


def _50_symbols():
    return [f"C{i}USDT" for i in range(50)]


def _50_signals():
    syms = _50_symbols()
    return [{"symbol": s, "side": "long" if i < 25 else "short", "weight": 0.02, "score": 0.02}
            for i, s in enumerate(syms)]


def _50_plan(positions=None):
    syms = _50_symbols()
    prov = FakeProvider(symbols=syms, prices={s: 2.0 for s in syms}, positions=positions)
    plan = ap.plan_strategy_native_actions(forward_result=FakeForward(_50_signals()), provider=prov)
    return plan, prov


# Current MARK prices for the legacy protected positions (distinct from entry).
_LEGACY_MARKS = {"EDUUSDT": 0.6, "POLYXUSDT": 0.3}


def _review_for_plan(plan, prov, positions=None, *, rule_ev=None, legacy_marks=None,
                     price_freshness_status=None, leverage_authoritative=False,
                     initial_margin_authoritative=False, assumed_leverage=None):
    if rule_ev is None:
        rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    kwargs = {}
    if price_freshness_status is not None:
        kwargs["price_freshness_status"] = price_freshness_status
    return v1.build_strategy_native_review(
        plan=plan, open_positions=positions if positions is not None else [], pilot_id=PILOT,
        run_date=DATE, artifact_fingerprint="sha256:fp", wallet_equity=INIT,
        available_balance=8_500.0, rule_evidence_by_symbol=rule_ev,
        price_by_symbol={s: 2.0 for s in _50_symbols()},
        legacy_mark_price_by_symbol=(legacy_marks if legacy_marks is not None else dict(_LEGACY_MARKS)),
        leverage_authoritative=leverage_authoritative,
        initial_margin_authoritative=initial_margin_authoritative,
        assumed_leverage=assumed_leverage, **kwargs)


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


# ---------------------------------------------------------------------------
# Active policy selection
# ---------------------------------------------------------------------------


def test_active_policy_is_strategy_native_v1():
    pc = v1.active_policy_classification()
    assert pc["active_policy"] == v1.POLICY_ACTIVE_STRATEGY_NATIVE_V1
    assert pc["strategy_native_policy_active"] is True


def test_one_position_policy_not_active():
    pc = v1.active_policy_classification()
    readiness = [p for p in pc["policy_catalog"] if p["policy"] == v1.POLICY_LEGACY_INACTIVE_READINESS][0]
    assert readiness["active"] is False
    assert any("max_simultaneous_open_positions=1" in s for s in readiness["inactive_limits"])


def test_tiny_one_shot_policy_not_active():
    pc = v1.active_policy_classification()
    oneshot = [p for p in pc["policy_catalog"] if p["policy"] == v1.POLICY_ISOLATED_ONE_SHOT_TEST][0]
    assert oneshot["active"] is False
    assert any("SOLUSDT-only allowlist" in s for s in oneshot["inactive_limits"])


def test_inactive_one_position_policy_does_not_block_v1():
    # 50 V1 targets are planned regardless of the readiness max=1 simultaneous limit.
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    assert review["plan_valid"] is True
    assert review["target_position_count"] == 50
    assert review["execution_batch"]["expected_action_count"] == 50


# ---------------------------------------------------------------------------
# Full V1 portfolio preserved
# ---------------------------------------------------------------------------


def test_full_50_target_plan_remains():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov)
    assert review["target_position_count"] == 50
    assert review["long_target_count"] == 25
    assert review["short_target_count"] == 25


def test_strategy_target_weights_remain_pm_002():
    plan, _ = _50_plan()
    for tp in plan.target_positions:
        assert abs(abs(tp["target_weight"]) - 0.02) < 1e-12


def test_50_actions_when_no_managed_positions():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    batch = review["execution_batch"]
    assert batch["expected_action_count"] == 50
    assert all(a["intent"] == v1.RECON_OPEN for a in batch["actions"])


# ---------------------------------------------------------------------------
# Legacy protected position separation
# ---------------------------------------------------------------------------


def test_legacy_positions_separated_from_strategy():
    sep = v1.separate_positions(_legacy_positions())
    assert len(sep.strategy_managed) == 0
    assert len(sep.legacy_protected) == 2
    assert {r["symbol"] for r in sep.legacy_protected} == {"EDUUSDT", "POLYXUSDT"}


def test_legacy_positions_generate_no_actions():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    batch_syms = {a["symbol"] for a in review["execution_batch"]["actions"]}
    assert batch_syms & PROTECTED == set()
    assert review["legacy_executable_action_count"] == 0


def test_legacy_positions_do_not_block_unrelated_targets():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    # 50 unrelated V1 targets still produce 50 OPEN actions despite 2 legacy positions.
    assert review["execution_batch"]["expected_action_count"] == 50
    assert review["plan_valid"] is True


def test_legacy_positions_count_toward_account_risk():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    assert Decimal(review["legacy_gross_notional_usdt"]) > 0
    total = Decimal(review["total_projected_account_gross_notional_usdt"])
    strat = Decimal(review["strategy_target_gross_notional_usdt"])
    legacy = Decimal(review["legacy_gross_notional_usdt"])
    assert total == strat + legacy
    assert review["legacy_protected_position_count"] == 2
    assert review["total_account_open_position_count"] == 2


def test_position_separation_counts_in_review():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    assert review["strategy_managed_open_position_count"] == 0
    assert review["legacy_protected_position_count"] == 2


# ---------------------------------------------------------------------------
# Reconciliation classification
# ---------------------------------------------------------------------------


def test_reconcile_open_hold_increase_reduce_close_reverse():
    targets = [
        {"symbol": "AAAUSDT", "side": "long", "qty": "10", "target_notional": "200", "qty_step": "0.1"},
        {"symbol": "BBBUSDT", "side": "long", "qty": "10", "target_notional": "200", "qty_step": "0.1"},
        {"symbol": "CCCUSDT", "side": "long", "qty": "20", "target_notional": "400", "qty_step": "0.1"},
        {"symbol": "DDDUSDT", "side": "long", "qty": "5", "target_notional": "100", "qty_step": "0.1"},
        {"symbol": "EEEUSDT", "side": "short", "qty": "10", "target_notional": "200", "qty_step": "0.1"},
        # FFFUSDT has a current position but no target -> CLOSE
    ]
    managed = [
        DemoOpenPosition(symbol="BBBUSDT", side="long", quantity=10.0, entry_price=20.0, stop_price=18.0),
        DemoOpenPosition(symbol="CCCUSDT", side="long", quantity=10.0, entry_price=20.0, stop_price=18.0),
        DemoOpenPosition(symbol="DDDUSDT", side="long", quantity=10.0, entry_price=20.0, stop_price=18.0),
        DemoOpenPosition(symbol="EEEUSDT", side="long", quantity=10.0, entry_price=20.0, stop_price=18.0),
        DemoOpenPosition(symbol="FFFUSDT", side="long", quantity=10.0, entry_price=20.0, stop_price=18.0),
    ]
    sep = v1.separate_positions(managed)
    recon = v1.reconcile_portfolio(targets=targets, separated=sep)
    by = {r["symbol"]: r["classification"] for r in recon}
    assert by["AAAUSDT"] == v1.RECON_OPEN
    assert by["BBBUSDT"] == v1.RECON_HOLD
    assert by["CCCUSDT"] == v1.RECON_INCREASE
    assert by["DDDUSDT"] == v1.RECON_REDUCE
    assert by["EEEUSDT"] == v1.RECON_REVERSE
    assert by["FFFUSDT"] == v1.RECON_CLOSE


def test_protected_always_legacy_unmanaged():
    managed = [DemoOpenPosition(symbol="EDUUSDT", side="short", quantity=100.0,
                                entry_price=1.0, stop_price=1.2)]
    sep = v1.separate_positions(managed)
    recon = v1.reconcile_portfolio(targets=[], separated=sep)
    edu = [r for r in recon if r["symbol"] == "EDUUSDT"][0]
    assert edu["classification"] == v1.RECON_LEGACY_PROTECTED_UNMANAGED
    assert edu["executable"] is False


def test_reconciliation_deterministic():
    plan, prov = _50_plan()
    r1 = _review_for_plan(plan, prov, positions=_legacy_positions())["reconciliation"]
    r2 = _review_for_plan(plan, prov, positions=_legacy_positions())["reconciliation"]
    assert r1 == r2


# ---------------------------------------------------------------------------
# Deterministic execution batch identity
# ---------------------------------------------------------------------------


def test_batch_action_ordering_deterministic():
    plan, prov = _50_plan()
    b1 = _review_for_plan(plan, prov)["execution_batch"]
    b2 = _review_for_plan(plan, prov)["execution_batch"]
    assert b1["ordered_action_fingerprints"] == b2["ordered_action_fingerprints"]
    syms = [a["symbol"] for a in b1["actions"]]
    assert syms == sorted(syms)


def test_each_action_has_fingerprint_and_idempotency_key():
    plan, prov = _50_plan()
    batch = _review_for_plan(plan, prov)["execution_batch"]
    for a in batch["actions"]:
        assert a["action_fingerprint"].startswith("sha256:")
        assert a["idempotency_key"].startswith("idem:")
        for field in ("symbol", "side", "intent", "reduce_only", "qty", "qty_step",
                      "price_snapshot", "target_notional_usdt", "current_position_qty",
                      "delta_notional_usdt", "instrument_rule_fingerprint"):
            assert field in a


def test_duplicate_rerun_same_batch_identities():
    plan, prov = _50_plan()
    b1 = _review_for_plan(plan, prov, positions=_legacy_positions())["execution_batch"]
    b2 = _review_for_plan(plan, prov, positions=_legacy_positions())["execution_batch"]
    assert b1["batch_id"] == b2["batch_id"]
    assert [a["idempotency_key"] for a in b1["actions"]] == [a["idempotency_key"] for a in b2["actions"]]


def test_batch_qty_complies_with_instrument_rules():
    plan, prov = _50_plan()
    batch = _review_for_plan(plan, prov)["execution_batch"]
    for a in batch["actions"]:
        step = Decimal(a["qty_step"])
        assert step > 0
        assert (Decimal(a["qty"]) % step) == 0


def test_no_binary_float_artifacts_in_review():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    text = json.dumps(review)
    assert not _ARTIFACT_RE.search(text)


# ---------------------------------------------------------------------------
# Feasibility / account risk
# ---------------------------------------------------------------------------


def test_unavailable_leverage_fails_closed_but_plan_visible():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    assert review["projected_margin_feasibility_status"] == \
        v1.STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
    # Full plan stays visible despite failing closed.
    assert review["target_position_count"] == 50
    assert review["execution_batch"]["expected_action_count"] == 50


def test_feasible_when_margin_sufficient():
    f = v1.assess_feasibility(
        wallet_equity=10000, available_balance=8500, strategy_gross_notional=10000,
        legacy_gross_notional=2231, leverage_authoritative=True,
        initial_margin_authoritative=True, assumed_leverage=10)
    # required IM = (10000+2231)/10 = 1223.1 <= 8500 available -> FEASIBLE
    assert f["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_FEASIBLE


def test_insufficient_margin_status():
    f = v1.assess_feasibility(
        wallet_equity=1000, available_balance=100, strategy_gross_notional=10000,
        legacy_gross_notional=2231, leverage_authoritative=True,
        initial_margin_authoritative=True, assumed_leverage=2)
    # required IM = 12231/2 = 6115.5 > 100 -> INSUFFICIENT
    assert f["projected_margin_feasibility_status"] == \
        v1.STRATEGY_PORTFOLIO_INSUFFICIENT_AVAILABLE_MARGIN


def test_rule_rejection_status():
    plan, prov = _50_plan()
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    rule_ev["C0USDT"] = {"symbol": "C0USDT", "rule_status": "NON_TRADING"}
    review = v1.build_strategy_native_review(
        plan=plan, open_positions=[], pilot_id=PILOT, run_date=DATE,
        artifact_fingerprint="fp", wallet_equity=INIT, available_balance=8500.0,
        rule_evidence_by_symbol=rule_ev, price_by_symbol={s: 2.0 for s in _50_symbols()},
        leverage_authoritative=True, initial_margin_authoritative=True, assumed_leverage=10)
    assert review["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_RULE_REJECTION


def test_does_not_assume_leverage():
    f = v1.assess_feasibility(
        wallet_equity=10000, available_balance=8500, strategy_gross_notional=10000,
        legacy_gross_notional=0, leverage_authoritative=False,
        initial_margin_authoritative=False)
    assert f["projected_margin_feasibility_status"] == \
        v1.STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
    assert f["required_initial_margin_usdt"] is None


# ---------------------------------------------------------------------------
# No protected-position BLOCK status; authorization fields
# ---------------------------------------------------------------------------


def test_no_protected_block_status_in_active_review():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    text = json.dumps(review)
    assert "NO_EXECUTION_CANDIDATE_EXISTING_PROTECTED_POSITIONS" not in text


def test_execution_batch_not_authorized():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    assert review["execution_batch_present"] is True
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False
    assert review["sender_reachable"] is False
    assert review["execution_batch"]["batch_authorization_status"] == \
        v1.BATCH_AUTHORIZATION_UNAUTHORIZED_PLAN_ONLY


def test_zero_dispatch_counts():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    assert review["order_post_count"] == 0
    assert review["amend_post_count"] == 0
    assert review["cancel_post_count"] == 0
    assert review["execute_daily_native_call_count"] == 0
    assert review["transport_sender_call_count"] == 0
    assert review["live_endpoint_called"] is False


def test_does_not_reuse_solusdt_one_shot_marker():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov)
    text = json.dumps(review)
    # No SOLUSDT one-shot real-order marker value or name leaks into the active review.
    assert "DEMO_ONLY_SOLUSDT_ONE_SHOT_REAL_ORDER_RICK_AUTHORIZED_v1" not in text


# ---------------------------------------------------------------------------
# CLI integration: active policy visible; legacy does not block; zero dispatch
# ---------------------------------------------------------------------------


def test_cli_review_helper_active_policy(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _50_plan(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    assert review["active_policy"] == v1.POLICY_ACTIVE_STRATEGY_NATIVE_V1
    assert review["target_position_count"] == 50
    assert review["legacy_protected_position_count"] == 2
    assert review["legacy_executable_action_count"] == 0
    assert review["execution_batch_authorized"] is False
    assert review["sender_reachable"] is False
    assert review["order_post_count"] == 0


def test_pilot_state_byte_identical(tmp_path, fwd_root):
    out_root = running_pilot(tmp_path, fwd_root)
    state_path = pathlib.Path(out_root)
    before = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert before
    plan, prov = _50_plan(positions=_legacy_positions())
    daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    after = {p: p.read_bytes() for p in state_path.rglob("pilot_state.json")}
    assert after == before


def test_no_secret_in_review_output(tmp_path, fwd_root):
    plan, prov = _50_plan(positions=_legacy_positions())
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    text = json.dumps(review).lower()
    for sensitive in ("demokey", "demosecret", "bybit_demo_api_key", "bybit_demo_api_secret"):
        assert sensitive not in text


# ===========================================================================
# TASK-014CC_FIX1 -- rule provenance, canonical Decimal, legacy mark risk
# ===========================================================================


def _override_provider(*, steps=None, min_qty=None, max_qty=None, min_notional=None,
                       rule_status=None, prices=None):
    syms = _50_symbols()
    return FakeProvider(symbols=syms, prices=prices or {s: 2.0 for s in syms},
                        steps=steps or {}, min_qty=min_qty or {}, max_qty=max_qty or {},
                        min_notional=min_notional or {}, rule_status=rule_status or {})


def _direct_batch(*, symbol="AAAUSDT", qty=10.0, step=0.1, price=2.0, notional=200.0,
                  side="long", rule_overrides=None):
    targets_by = {symbol: {"symbol": symbol, "side": side, "qty": qty,
                           "target_notional": notional, "qty_step": step, "price": price}}
    recon = [{"symbol": symbol, "classification": v1.RECON_OPEN, "executable": True,
              "target_present": True, "current_present": False}]
    rule = {"symbol": symbol, "rule_status": "TRADING", "qty_step": step,
            "min_qty": step, "max_qty": 0.0, "min_notional": 1.0, "tick_size": 0.01,
            "instrument_rule_source": "fixture-instruments-info",
            "market_price_source": "fixture-tickers"}
    rule.update(rule_overrides or {})
    return v1.build_execution_batch(
        run_date=DATE, pilot_id=PILOT, artifact_fingerprint="sha256:fp", reconciliation=recon,
        targets_by_symbol=targets_by, managed_by_symbol={}, rule_evidence_by_symbol={symbol: rule},
        price_by_symbol={symbol: price}, separated=v1.separate_positions([]),
        wallet_equity="10000", available_balance="8500")


# --- A. Rule provenance bound to every action ------------------------------


def test_all_50_actions_have_non_null_rule_fingerprint():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    batch = review["execution_batch"]
    assert batch["expected_action_count"] == 50
    assert all(a["instrument_rule_fingerprint"] is not None for a in batch["actions"])
    assert batch["non_null_rule_fingerprint_count"] == 50
    assert review["non_null_rule_fingerprint_count"] == 50


def test_every_action_has_authoritative_rule_provenance():
    plan, prov = _50_plan()
    batch = _review_for_plan(plan, prov)["execution_batch"]
    for a in batch["actions"]:
        for field in ("instrument_rule_fingerprint", "instrument_rule_source",
                      "instrument_rule_status", "qty_step", "min_qty", "max_qty",
                      "min_notional", "tick_size", "rule_validation_status"):
            assert field in a
        assert a["instrument_rule_source"] is not None
        assert a["instrument_rule_status"] == "TRADING"
        assert a["rule_validation_status"] == v1.RULE_VALIDATION_PASS


def test_missing_rule_produces_rule_rejection():
    plan, _ = _50_plan()
    prov = _override_provider()
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    rule_ev["C0USDT"] = {"symbol": "C0USDT", "rule_status": "MISSING"}
    review = _review_for_plan(plan, prov, rule_ev=rule_ev)
    assert review["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_RULE_REJECTION
    bad = [a for a in review["execution_batch"]["actions"] if a["symbol"] == "C0USDT"][0]
    assert bad["instrument_rule_fingerprint"] is None
    assert bad["rule_validation_status"] == v1.RULE_VALIDATION_MISSING


def test_non_trading_rule_produces_rule_rejection():
    plan, _ = _50_plan()
    prov = _override_provider(rule_status={"C0USDT": "NON_TRADING"})
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    review = _review_for_plan(plan, prov, rule_ev=rule_ev)
    assert review["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_RULE_REJECTION
    bad = [a for a in review["execution_batch"]["actions"] if a["symbol"] == "C0USDT"][0]
    assert bad["rule_validation_status"] == v1.RULE_VALIDATION_NON_TRADING
    assert bad["instrument_rule_fingerprint"] is None


def test_malformed_rule_produces_rule_rejection():
    plan, _ = _50_plan()
    prov = _override_provider()
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    rule_ev["C0USDT"] = {"symbol": "C0USDT", "rule_status": "MALFORMED"}
    review = _review_for_plan(plan, prov, rule_ev=rule_ev)
    assert review["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_RULE_REJECTION
    bad = [a for a in review["execution_batch"]["actions"] if a["symbol"] == "C0USDT"][0]
    assert bad["rule_validation_status"] == v1.RULE_VALIDATION_MALFORMED


def test_invalid_qty_step_multiple_rejected():
    rule = v1.normalize_rule_evidence("AAAUSDT", {"symbol": "AAAUSDT", "rule_status": "TRADING",
                                                  "qty_step": 0.1, "min_qty": 0.1})
    # 10.05 is not an exact 0.1 multiple.
    assert v1.validate_action_rule(qty="10.05", price="2", rule=rule) == \
        v1.RULE_VALIDATION_QTY_STEP_VIOLATION


def test_min_qty_violation_rejected():
    plan, _ = _50_plan()
    prov = _override_provider(min_qty={"C0USDT": 1_000_000.0})
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    review = _review_for_plan(plan, prov, rule_ev=rule_ev)
    assert review["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_RULE_REJECTION
    bad = [a for a in review["execution_batch"]["actions"] if a["symbol"] == "C0USDT"][0]
    assert bad["rule_validation_status"] == v1.RULE_VALIDATION_MIN_QTY_VIOLATION


def test_min_notional_violation_rejected():
    plan, _ = _50_plan()
    prov = _override_provider(min_notional={"C0USDT": 1_000_000.0})
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    review = _review_for_plan(plan, prov, rule_ev=rule_ev)
    assert review["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_RULE_REJECTION
    bad = [a for a in review["execution_batch"]["actions"] if a["symbol"] == "C0USDT"][0]
    assert bad["rule_validation_status"] == v1.RULE_VALIDATION_MIN_NOTIONAL_VIOLATION


def test_max_qty_violation_rejected():
    rule = v1.normalize_rule_evidence("AAAUSDT", {"symbol": "AAAUSDT", "rule_status": "TRADING",
                                                  "qty_step": 0.1, "min_qty": 0.1, "max_qty": 5.0})
    assert v1.validate_action_rule(qty="10", price="2", rule=rule) == \
        v1.RULE_VALIDATION_MAX_QTY_VIOLATION


# --- B. Canonical Decimal action representation ----------------------------


def test_batch_float_artifact_count_zero():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    assert review["batch_float_artifact_count"] == 0


def test_canonical_qty_has_no_float_artifact_from_planner_float():
    # A planner float qty with a binary tail is canonicalised to an exact step multiple.
    batch = _direct_batch(qty=1430.8000000000002, step=0.1, price=0.13989,
                          notional=200.0).to_dict()
    a = batch["actions"][0]
    assert a["qty"] == "1430.8"
    assert not v1.has_float_artifact(a["qty"])


def test_action_fingerprint_uses_non_null_rule_fingerprint():
    batch = _direct_batch().to_dict()
    a = batch["actions"][0]
    assert a["instrument_rule_fingerprint"] is not None
    assert a["action_fingerprint"].startswith("sha256:")
    assert a["canonical_action_payload_fingerprint"].startswith("sha256:")


def test_canonical_action_fingerprints_stable_across_reruns():
    plan, prov = _50_plan()
    b1 = _review_for_plan(plan, prov, positions=_legacy_positions())["execution_batch"]
    b2 = _review_for_plan(plan, prov, positions=_legacy_positions())["execution_batch"]
    assert b1["batch_id"] == b2["batch_id"]
    assert [a["action_fingerprint"] for a in b1["actions"]] == \
        [a["action_fingerprint"] for a in b2["actions"]]
    assert [a["canonical_action_payload_fingerprint"] for a in b1["actions"]] == \
        [a["canonical_action_payload_fingerprint"] for a in b2["actions"]]


def test_rule_change_changes_fingerprint_and_batch_id():
    base = _direct_batch().to_dict()
    changed = _direct_batch(rule_overrides={"min_notional": 2.0}).to_dict()
    assert base["actions"][0]["instrument_rule_fingerprint"] != \
        changed["actions"][0]["instrument_rule_fingerprint"]
    assert base["actions"][0]["action_fingerprint"] != changed["actions"][0]["action_fingerprint"]
    assert base["batch_id"] != changed["batch_id"]


def test_qty_change_changes_fingerprint_and_batch_id():
    base = _direct_batch(qty=10.0).to_dict()
    changed = _direct_batch(qty=20.0).to_dict()
    assert base["actions"][0]["qty"] != changed["actions"][0]["qty"]
    assert base["actions"][0]["action_fingerprint"] != changed["actions"][0]["action_fingerprint"]
    assert base["batch_id"] != changed["batch_id"]


def test_price_snapshot_change_changes_fingerprint_and_batch_id():
    base = _direct_batch(price=2.0).to_dict()
    changed = _direct_batch(price=2.5).to_dict()
    assert base["actions"][0]["price_snapshot"] != changed["actions"][0]["price_snapshot"]
    assert base["actions"][0]["action_fingerprint"] != changed["actions"][0]["action_fingerprint"]
    assert base["batch_id"] != changed["batch_id"]


# --- C. Legacy exposure uses CURRENT MARK price ----------------------------


def test_legacy_positions_untouched():
    before = _legacy_positions()
    snapshot = [(p.symbol, p.side, p.quantity, p.entry_price) for p in before]
    plan, prov = _50_plan()
    _review_for_plan(plan, prov, positions=before)
    after = [(p.symbol, p.side, p.quantity, p.entry_price) for p in before]
    assert after == snapshot


def test_legacy_current_risk_uses_mark_not_entry():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    # mark: 1655*0.6 + 5615.6*0.3 ; entry: 1655*0.5 + 5615.6*0.25
    mark = Decimal("1655") * Decimal("0.6") + Decimal("5615.6") * Decimal("0.3")
    entry = Decimal("1655") * Decimal("0.5") + Decimal("5615.6") * Decimal("0.25")
    assert Decimal(review["legacy_mark_gross_notional_usdt"]) == mark
    assert Decimal(review["legacy_gross_notional_usdt"]) == mark
    assert mark != entry
    assert Decimal(review["legacy_entry_gross_notional_usdt_informational"]) == entry


def test_legacy_entry_notional_informational_only():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    for pos in review["legacy_protected_positions"]:
        assert pos["entry_notional_usdt_informational_only"] is True
        assert pos["mark_notional_usdt"] is not None
        assert pos["mark_price_status"] == v1.MARK_PRICE_AVAILABLE
        assert pos["executable"] is False


def test_missing_legacy_mark_fails_closed_no_entry_fallback():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions(), legacy_marks={})
    assert review["legacy_mark_price_available"] is False
    assert review["projected_margin_feasibility_status"] == \
        v1.STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
    assert v1.LEGACY_MARK_PRICE_UNAVAILABLE in review["feasibility"]["account_risk_review_reasons"]
    # No fallback: mark notional null and legacy mark gross is zero (NOT entry value).
    assert Decimal(review["legacy_mark_gross_notional_usdt"]) == 0
    for pos in review["legacy_protected_positions"]:
        assert pos["mark_notional_usdt"] is None
        assert pos["mark_price_status"] == v1.LEGACY_MARK_PRICE_UNAVAILABLE
    # Full plan stays visible.
    assert review["target_position_count"] == 50
    assert review["execution_batch"]["expected_action_count"] == 50


def test_legacy_mark_contributes_to_total_account_gross():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov, positions=_legacy_positions())
    total = Decimal(review["total_projected_account_gross_notional_usdt"])
    strat = Decimal(review["strategy_target_gross_notional_usdt"])
    mark = Decimal(review["legacy_mark_gross_notional_usdt"])
    assert total == strat + mark
    assert mark > 0


# --- D. Market-price provenance and freshness ------------------------------


def test_price_provenance_and_freshness_present_or_unavailable():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov)
    assert review["price_freshness_status"] == v1.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
    for a in review["execution_batch"]["actions"]:
        assert a["price_source"] is not None
        assert a["price_snapshot_fingerprint"] is not None
        assert a["price_freshness_status"] == v1.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE
        assert "price_observed_at" in a
        assert "price_age_seconds" in a


def test_freshness_unavailable_fails_closed_with_full_plan():
    plan, prov = _50_plan()
    # Rules valid + legacy marks available + leverage authoritative, but freshness
    # evidence is unavailable -> account-risk review required (full plan visible).
    review = _review_for_plan(plan, prov, positions=_legacy_positions(),
                              leverage_authoritative=True, initial_margin_authoritative=True,
                              assumed_leverage=10)
    assert review["projected_margin_feasibility_status"] == \
        v1.STRATEGY_PORTFOLIO_ACCOUNT_RISK_REVIEW_REQUIRED
    assert v1.PRICE_FRESHNESS_EVIDENCE_UNAVAILABLE in \
        review["feasibility"]["account_risk_review_reasons"]
    assert review["target_position_count"] == 50


# --- E/F. Batch summary schema + isolated one-shot isolation ---------------


def test_batch_summary_schema_field_names():
    plan, prov = _50_plan()
    batch = _review_for_plan(plan, prov)["execution_batch"]
    for field in ("total_opening_notional_usdt", "total_reducing_notional_usdt",
                  "total_projected_gross_exposure_usdt"):
        assert field in batch


def test_isolated_one_shot_review_not_authoritative_flag():
    plan, prov = _50_plan()
    review = _review_for_plan(plan, prov)
    assert review["isolated_one_shot_review_is_authoritative"] is False


def test_full_plan_visible_when_rule_validation_fails():
    plan, _ = _50_plan()
    prov = _override_provider()
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    rule_ev["C0USDT"] = {"symbol": "C0USDT", "rule_status": "MISSING"}
    review = _review_for_plan(plan, prov, rule_ev=rule_ev)
    assert review["projected_margin_feasibility_status"] == v1.STRATEGY_PORTFOLIO_RULE_REJECTION
    assert review["target_position_count"] == 50
    assert review["execution_batch"]["expected_action_count"] == 50
    assert review["execution_batch_authorized"] is False
    assert review["sender_reachable"] is False


# --- H. Real VPS Plan-only expected invariants -----------------------------


def test_cli_review_full_provenance_and_mark_risk(tmp_path, fwd_root):
    running_pilot(tmp_path, fwd_root)
    plan, prov = _50_plan(positions=_legacy_positions())
    # Provide legacy mark prices via the provider's market_price path.
    prov._prices.update({"EDUUSDT": 0.6, "POLYXUSDT": 0.3})
    review = daily_cli.build_active_v1_review(provider=prov, plan=plan, pilot_id=PILOT, date=DATE)
    assert review["active_policy"] == v1.POLICY_ACTIVE_STRATEGY_NATIVE_V1
    assert review["target_position_count"] == 50
    assert review["long_target_count"] == 25
    assert review["short_target_count"] == 25
    assert review["legacy_protected_position_count"] == 2
    assert review["legacy_executable_action_count"] == 0
    assert review["non_null_rule_fingerprint_count"] == 50
    assert review["batch_float_artifact_count"] == 0
    assert Decimal(review["legacy_mark_gross_notional_usdt"]) > 0
    assert review["execution_batch_authorized"] is False
    assert review["execution_ready"] is False
    assert review["sender_reachable"] is False
    assert review["order_post_count"] == 0
    assert review["amend_post_count"] == 0
    assert review["cancel_post_count"] == 0
    assert review["live_endpoint_called"] is False
