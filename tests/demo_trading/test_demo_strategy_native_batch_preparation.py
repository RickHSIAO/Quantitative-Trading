"""TASK-014 -- terminal DRY-RUN preparation of the Strategy-native 50-order Demo batch.

Narrow offline tests for the dry-run wiring only. The non-sending preparation mode lives on
the canonical runner (``scripts/run_demo_strategy_pilot_native_daily.py
--prepare-from-current-feasibility-artifacts``) and reuses the existing native-execution
builders (``classify_action`` / ``build_order_body`` / ``order_link_id``) to turn the three
CH4A artifacts into the EXACT 50 order payloads WITHOUT sending. Proves: 50 payloads + 25/25;
natural (non-redistributed) gross/net; protected overlap rejects the whole batch; failed
feasibility / missing leverage rejects; and that no transport / ``execute_daily_native`` /
POST is ever reached. (Per-symbol sizing / freshness are already covered by the CH4A and
native-execution suites and are not re-tested here.)
"""
from __future__ import annotations

import importlib.util
import json
import os
from decimal import Decimal

import pytest

from src import demo_strategy_pilot_native_execution as nx

_HERE = os.path.dirname(os.path.abspath(__file__))
_ROOT = os.path.dirname(os.path.dirname(_HERE))
_RUNNER = os.path.join(_ROOT, "scripts", "run_demo_strategy_pilot_native_daily.py")
_spec = importlib.util.spec_from_file_location("crun_batch_prep", _RUNNER)
crun = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(crun)


# ---------------------------------------------------------------------------
# CH4A-shaped artifacts (match demo_strategy_native_current_feasibility output)
# ---------------------------------------------------------------------------

def _artifacts(*, n=50, long_n=25, leverage="10", price="100.0",
               long_notional="200", short_notional="200", qty="2",
               protected=("EDUUSDT",), overlaps=(), symbols=None,
               feas_status="CURRENT_FEASIBILITY_PASS",
               margin_status="MARGIN_FEASIBILITY_PASS",
               leverage_status="TARGET_LEVERAGE_EVIDENCE_OK"):
    syms = symbols or [f"SYM{i:02d}USDT" for i in range(n)]
    actions, leverage_by, im_rows = [], {}, []
    for i, s in enumerate(syms):
        is_long = i < long_n
        notional = long_notional if is_long else short_notional
        im = str(Decimal(notional) / Decimal(leverage))
        actions.append({
            "symbol": s, "side": "long" if is_long else "short", "current_price": price,
            "rounded_quantity": qty, "rounded_notional_usd": notional,
            "quantity_validation_status": "QUANTITY_VALIDATION_OK",
            "tick_size": "0.01", "qty_step": "0.001", "min_order_qty": "0.001",
            "min_notional_value": "5",
        })
        leverage_by[s] = leverage
        im_rows.append({"symbol": s, "configured_leverage": leverage,
                        "projected_initial_margin_usd": im})
    market = {"schema": "demo_strategy_native_current_market_evidence",
              "current_actions": actions}
    account = {"account_evidence_status": "DEMO_ACCOUNT_EVIDENCE_OK",
               "target_leverage_evidence_status": leverage_status,
               "target_configured_leverage_by_symbol": leverage_by,
               "protected_positions": list(protected),
               "strategy_position_overlaps": list(overlaps),
               "position_mode": "one_way"}
    review = {"status": feas_status,
              "account_margin_feasibility_status": margin_status,
              "long_count": long_n, "short_count": n - long_n,
              "per_symbol_initial_margin": im_rows}
    return review, market, account


def _prepare(review, market, account, *, pilot_id="BYBIT_DEMO_PILOT_7D_202606_V1",
             date="2026-06-30"):
    return nx.prepare_strategy_native_batch_dry_run(
        feasibility_review=review, current_actions=market["current_actions"],
        account_evidence=account, pilot_id=pilot_id, date=date)


# ===========================================================================
# Pure function
# ===========================================================================

def test_pass_artifacts_produce_fifty_payloads_25_25_with_required_fields():
    r = _prepare(*_artifacts())
    assert r["verdict"] == nx.BATCH_PREP_PREPARED and r["blockers"] == []
    assert r["order_count"] == 50
    assert r["buy_count"] == 25 and r["sell_count"] == 25
    assert len(r["order_payloads"]) == 50
    p0 = r["order_payloads"][0]
    for field in ("symbol", "side", "qty", "current_reference_price", "rounded_notional_usd",
                  "configured_leverage", "projected_initial_margin_usd",
                  "instrument_rule_validation", "order_link_id", "order_body"):
        assert field in p0, field
    body = p0["order_body"]
    assert body["orderType"] == "Market" and body["reduceOnly"] is False
    assert body["orderLinkId"] == p0["order_link_id"]
    assert body["orderLinkId"].startswith(nx.ORDER_LINK_ID_PREFIX)


def test_natural_gross_net_exposure_preserved_no_redistribution():
    # Longs round to 199, shorts to 200 -> natural short bias; never padded to 10000 / 0.
    r = _prepare(*_artifacts(long_notional="199", short_notional="200"))
    assert r["verdict"] == nx.BATCH_PREP_PREPARED
    assert r["gross_notional_usd"] == "9975"     # 25*199 + 25*200
    assert r["net_notional_usd"] == "-25"        # short bias
    assert r["short_bias_usd"] == "25"
    assert r["total_projected_initial_margin_usd"] == "997.5"


def test_protected_symbol_target_rejects_whole_batch():
    syms = [f"SYM{i:02d}USDT" for i in range(49)] + ["EDUUSDT"]
    r = _prepare(*_artifacts(symbols=syms))
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any("EDUUSDT" in b and "not_eligible" in b for b in r["blockers"])
    assert r["order_payloads"] == [] and r["order_count"] == 0  # never a partial batch


@pytest.mark.parametrize("over,frag", [
    ({"feas_status": "CURRENT_FEASIBILITY_BLOCKED"}, "feasibility_status_not_pass"),
    ({"margin_status": "MARGIN_FEASIBILITY_UNAVAILABLE_NO_INDEPENDENT_RATE"},
     "margin_status_not_pass"),
    ({"leverage_status": "TARGET_LEVERAGE_EVIDENCE_UNAVAILABLE"}, "leverage_status_not_ok"),
    ({"overlaps": ("SYM00USDT",)}, "strategy_position_overlap"),
])
def test_failed_gate_rejects_with_no_payloads(over, frag):
    r = _prepare(*_artifacts(**over))
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(frag in b for b in r["blockers"])
    assert r["order_payloads"] == []


# ===========================================================================
# Canonical runner mode -- nothing is ever sent
# ===========================================================================

def _write(tmp_path, review, market, account):
    (tmp_path / "review.json").write_text(json.dumps(review), encoding="utf-8")
    (tmp_path / "market.json").write_text(json.dumps(market), encoding="utf-8")
    (tmp_path / "account.json").write_text(json.dumps(account), encoding="utf-8")


def _argv(tmp_path, *, out=None):
    argv = ["--prepare-from-current-feasibility-artifacts",
            "--pilot-id", "BYBIT_DEMO_PILOT_7D_202606_V1", "--date", "2026-06-30",
            "--current-feasibility-review-json", str(tmp_path / "review.json"),
            "--current-market-evidence-json", str(tmp_path / "market.json"),
            "--demo-account-evidence-json", str(tmp_path / "account.json")]
    if out:
        argv += ["--prepare-output-json", str(out)]
    return argv


def test_runner_mode_prepares_and_never_touches_transport_or_execution(tmp_path, capsys, monkeypatch):
    _write(tmp_path, *_artifacts())

    def _boom(*a, **k):
        raise AssertionError("send path must never be reached in dry-run preparation")

    # If the prepare mode ever constructed a transport or dispatched, these would fire.
    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom)

    out = tmp_path / "preview.json"
    rc = crun.main(_argv(tmp_path, out=out))
    assert rc == crun.EXIT_OK
    summary = json.loads(capsys.readouterr().out)
    assert summary["verdict"] == nx.BATCH_PREP_PREPARED
    assert summary["order_count"] == 50
    for c in ("order_post_count", "amend_post_count", "cancel_post_count",
              "live_order_post_count", "sender_call_count"):
        assert summary[c] == 0
    assert summary["execution_authorized"] is False
    assert summary["transport_touched"] is False
    written = json.loads(out.read_text(encoding="utf-8"))
    assert len(written["order_payloads"]) == 50


def test_runner_mode_rejects_blocked_feasibility(tmp_path, capsys):
    _write(tmp_path, *_artifacts(feas_status="CURRENT_FEASIBILITY_BLOCKED"))
    rc = crun.main(_argv(tmp_path))
    assert rc == crun.EXIT_BLOCKED
    summary = json.loads(capsys.readouterr().out)
    assert summary["verdict"] == nx.BATCH_PREP_REJECTED
    assert summary["order_count"] == 0


# ===========================================================================
# Per-symbol evidence validation (corrections item 1)
# ===========================================================================

def _artifacts_with_row_override(row_index, **overrides):
    """Return artifacts where one row at row_index has fields overridden."""
    review, market, account = _artifacts()
    row = dict(market["current_actions"][row_index])
    row.update(overrides)
    market = dict(market)
    market["current_actions"] = list(market["current_actions"])
    market["current_actions"][row_index] = row
    return review, market, account


def test_missing_configured_leverage_rejects_whole_batch():
    review, market, account = _artifacts()
    # Remove one symbol from the leverage map.
    sym = market["current_actions"][3]["symbol"]
    account = dict(account)
    account["target_configured_leverage_by_symbol"] = {
        k: v for k, v in account["target_configured_leverage_by_symbol"].items() if k != sym}
    r = _prepare(review, market, account)
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"missing_configured_leverage:{sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == [] and r["order_count"] == 0


def test_invalid_projected_initial_margin_rejects_whole_batch():
    review, market, account = _artifacts()
    sym = market["current_actions"][7]["symbol"]
    # Corrupt that symbol's IM row in the review.
    review = dict(review)
    review["per_symbol_initial_margin"] = [
        ({"symbol": r["symbol"], "projected_initial_margin_usd": "-5"}
         if r["symbol"] == sym else r)
        for r in review["per_symbol_initial_margin"]
    ]
    r = _prepare(review, market, account)
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"invalid_projected_initial_margin:{sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == []


def test_invalid_quantity_validation_status_rejects_whole_batch():
    review, market, account = _artifacts_with_row_override(
        5, quantity_validation_status="QUANTITY_VALIDATION_FAILED")
    r = _prepare(review, market, account)
    sym = market["current_actions"][5]["symbol"]
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"quantity_not_valid:{sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == []


def test_duplicate_symbol_rejects_whole_batch():
    review, market, account = _artifacts()
    # Replace last row's symbol with the first row's symbol.
    dup_sym = market["current_actions"][0]["symbol"]
    market = dict(market)
    market["current_actions"] = list(market["current_actions"])
    market["current_actions"][-1] = dict(market["current_actions"][-1], symbol=dup_sym)
    r = _prepare(review, market, account)
    assert r["verdict"] == nx.BATCH_PREP_REJECTED
    assert any(f"duplicate_symbol:{dup_sym}" == b for b in r["blockers"])
    assert r["order_payloads"] == []


# ===========================================================================
# Conflicting-mode rejection (corrections item 2)
# ===========================================================================

def test_prepare_mode_combined_with_send_orders_returns_exit_invalid(tmp_path, capsys, monkeypatch):
    _write(tmp_path, *_artifacts())

    def _boom(*a, **k):
        raise AssertionError("transport / execution must never be reached when flag conflict detected")

    monkeypatch.setattr(crun, "RealDemoOrderTransport", _boom, raising=False)
    monkeypatch.setattr(crun.nx, "execute_daily_native", _boom)

    argv = _argv(tmp_path) + ["--send-orders-to-demo"]
    rc = crun.main(argv)
    assert rc == crun.EXIT_INVALID
    out = json.loads(capsys.readouterr().out)
    assert out["verdict"] == nx.BATCH_PREP_REJECTED
    assert any("incompatible_flag:send_orders_to_demo" == b for b in out["blockers"])
