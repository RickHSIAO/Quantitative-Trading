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
                 rule_status=None, leverage_authoritative=False,
                 initial_margin_authoritative=False, assumed_leverage=None,
                 equity=INIT, available=8_500.0):
        self._positions = positions or []
        self._symbols = symbols or []
        self._prices = prices or {s: 2.0 for s in self._symbols}
        self._steps = steps or {}
        self._rule_status = rule_status or {}
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
        status = self._rule_status.get(symbol, "TRADING")
        ev = {"symbol": symbol, "rule_status": status,
              "instrument_rule_source": "fixture", "market_price_source": "fixture",
              "market_price": self._prices.get(symbol),
              "instrument_rule_fingerprint": "sha256:rule_" + symbol}
        if status == "TRADING":
            ev["qty_step"] = self._steps.get(symbol, 0.1)
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


def _review_for_plan(plan, prov, positions=None):
    rule_ev = {s: prov.instrument_rule_evidence(s) for s in _50_symbols()}
    return v1.build_strategy_native_review(
        plan=plan, open_positions=positions if positions is not None else [], pilot_id=PILOT,
        run_date=DATE, artifact_fingerprint="sha256:fp", wallet_equity=INIT,
        available_balance=8_500.0, rule_evidence_by_symbol=rule_ev,
        price_by_symbol={s: 2.0 for s in _50_symbols()},
        leverage_authoritative=False, initial_margin_authoritative=False)


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
