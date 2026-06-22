"""TASK-014BY -- offline tests for the 30-day Forward diagnostics.

Deterministic, temp output roots only. No network, no Bybit, no order, no Pilot
mutation; reuses the canonical metrics module.
"""

from __future__ import annotations

import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.strategy_selection import forward30_diagnostics as diag

EXPECTED = diag.EXPECTED_STRATEGY_NAME


def make_run(tmp, run_key, dates, *, strategy=EXPECTED, returns=None, costs=None,
             cumulative=None, latest=None, summary_over=None, positions=None):
    """Build a temp Forward run directory with structurally valid artifacts."""
    root = tmp
    d = root / run_key
    d.mkdir(parents=True, exist_ok=True)
    (root / "dashboard").mkdir(parents=True, exist_ok=True)
    (root / "paper_portfolio").mkdir(parents=True, exist_ok=True)
    rets = returns or [0.0] * len(dates)
    cum = 0.0
    csv_lines = ["date,n_longs,n_shorts,daily_pnl_pct,cumulative_pnl_pct,safety_scan,dry_run"]
    for i, compact in enumerate(dates):
        cum += rets[i]
        pnl = {
            "date": compact, "daily_pnl_pct": rets[i], "cumulative_pnl_pct": cum,
            "gross_exposure": 1.0, "net_exposure": 0.0, "n_longs": 25, "n_shorts": 25,
            "long_weight_sum": 0.5, "short_weight_sum": -0.5, "variant": "combined_paper_safe_variant",
        }
        if costs:
            pnl.update(costs)
        (d / f"{compact}_pnl.json").write_text(json.dumps(pnl), encoding="utf-8")
        (d / f"{compact}_forward_stats.json").write_text(
            json.dumps({"date": compact, "variant": "combined_paper_safe_variant"}), encoding="utf-8")
        csv_lines.append(f"{compact},25,25,{rets[i]},{cum},PASS,True")
    summary = {"strategy": strategy, "latest_date": latest or dates[-1],
               "days_required": 30, "days_elapsed": len(dates),
               "gate_status": {"overlay_always_pass": True}}
    if summary_over:
        summary.update(summary_over)
    (d / "forward_summary.json").write_text(json.dumps(summary), encoding="utf-8")
    (root / "dashboard" / "validation_30d.csv").write_text("\n".join(csv_lines) + "\n", encoding="utf-8")
    pos = positions or [{"symbol": f"SYM{i}USDT", "side": "long" if i % 2 else "short",
                         "weight": 0.02 if i % 2 else -0.02, "position_usd": 200.0} for i in range(50)]
    (root / "paper_portfolio" / "state.json").write_text(json.dumps({"positions": pos}), encoding="utf-8")
    return root


def days(n, start=1):
    return [f"202606{d:02d}" for d in range(start, start + n)]


# --- Input audit / integrity ----------------------------------------------


def test_input_audit_reports_present_and_partial(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    audit = diag.audit_inputs(tmp_path, "prev3y_crypto")
    assert audit["coverage_status"] == diag.PARTIAL
    assert audit["present_date_count"] == 2 and audit["required_date_count"] == 30
    roles = {a["role"]: a["status"] for a in audit["artifacts"]}
    assert roles["forward_summary"] == diag.PRESENT
    assert any(c["category"] == "SMOKE_TEST" and c["status"] == diag.EXCLUDED
               for c in audit["excluded_record_categories"])


def test_input_audit_missing_summary(tmp_path):
    (tmp_path / "prev3y_crypto").mkdir(parents=True)
    audit = diag.audit_inputs(tmp_path, "prev3y_crypto")
    roles = {a["role"]: a["status"] for a in audit["artifacts"]}
    assert roles["forward_summary"] == diag.MISSING


def test_data_integrity_insufficient_sample(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    integ = diag.compute_data_integrity(run)
    assert integ["present_date_count"] == 2
    assert integ["sample_sufficient"]["return_metrics"] is False
    assert integ["covered_dates"] == ["2026-06-01", "2026-06-02"]


def test_data_integrity_strategy_mismatch(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2), strategy="some_other_strategy")
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    integ = diag.compute_data_integrity(run)
    assert integ["strategy_id_matches_expected"] is False


def test_stale_summary_detected(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2), latest="20991231")
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    integ = diag.compute_data_integrity(run)
    assert integ["stale_summary"] is True


def test_duplicate_dates_detected(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    # Append a duplicate row to the validation CSV.
    csvp = tmp_path / "dashboard" / "validation_30d.csv"
    csvp.write_text(csvp.read_text(encoding="utf-8") + "20260602,25,25,0.0,0.0,PASS,True\n", encoding="utf-8")
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    integ = diag.compute_data_integrity(run)
    assert "2026-06-02" in integ["duplicate_dates"]


# --- Determinism / fingerprints -------------------------------------------


def test_replay_determinism_identical(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(3), returns=[0.1, -0.05, 0.2])
    run1 = diag.load_forward_run(tmp_path, "prev3y_crypto")
    run2 = diag.load_forward_run(tmp_path, "prev3y_crypto")
    d1 = diag.run_all_diagnostics(run1, [])
    d2 = diag.run_all_diagnostics(run2, [])
    assert json.dumps(d1, sort_keys=True) == json.dumps(d2, sort_keys=True)


def test_source_fingerprint_change_detected(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    run_a = diag.load_forward_run(tmp_path, "prev3y_crypto")
    fp_a = diag.compute_data_integrity(run_a)["source_fingerprints"]["forward_summary.json"]
    # Mutate the summary bytes.
    sp = tmp_path / "prev3y_crypto" / "forward_summary.json"
    sp.write_text(sp.read_text(encoding="utf-8") + "  ", encoding="utf-8")
    run_b = diag.load_forward_run(tmp_path, "prev3y_crypto")
    fp_b = diag.compute_data_integrity(run_b)["source_fingerprints"]["forward_summary.json"]
    assert fp_a != fp_b


# --- Overall metrics / cost stress ----------------------------------------


def test_overall_metrics_marks_insufficient_and_uses_canonical(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2), returns=[0.0, 0.0])
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    overall = diag.compute_overall_metrics(run)
    assert overall["sample_sufficient_for_return_metrics"] is False
    assert "NOT ANNUALIZED" in overall["annualization_note"]
    assert overall["canonical_metric_source"] == "src/metrics/performance.py::compute_stats"
    assert overall["unavailable"]["profit_factor"] == diag.UNAVAILABLE


def test_overall_metrics_sufficient_sample(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(25), returns=[0.1] * 25)
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    overall = diag.compute_overall_metrics(run)
    assert overall["sample_sufficient_for_return_metrics"] is True
    assert "sharpe_full" in overall["canonical_metrics"]


def test_cost_stress_unavailable_when_no_cost_fields(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))  # no cost fields
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    cs = diag.compute_cost_stress(run)
    assert cs["slippage_stress"]["status"] == diag.UNAVAILABLE
    assert cs["funding_stress"]["status"] == diag.UNAVAILABLE
    assert cs["all_costs_zero_paper_dry_run"] is True


def test_cost_stress_with_recorded_costs(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2),
             costs={"fee_cost_usd": 1.0, "funding_cost_usd": 0.5, "slippage_cost_usd": 0.25})
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    cs = diag.compute_cost_stress(run)
    assert cs["base"]["fee"] == 2.0 and cs["fees_x2"]["fee"] == 4.0
    assert cs["slippage_stress"]["status"] == diag.PRESENT
    assert cs["funding_stress"]["status"] == diag.PRESENT


# --- Trade behavior / regime never fabricated -----------------------------


def test_trade_behavior_unavailable_no_synthesis(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    tb = diag.compute_trade_behavior(run)
    assert tb["status"] == diag.UNAVAILABLE
    assert tb["synthesized_values"] == "NONE (never fabricated)"
    assert "MAE" in tb["unavailable_metrics"]


def test_regime_not_invented(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    reg = diag.compute_regime(run)
    assert reg["status"] == diag.NO_CANONICAL_DEFINITION


# --- Primary vs shadow / OOS ----------------------------------------------


def test_primary_shadow_all_insufficient(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    make_run(tmp_path, "prev3y_crypto_shadow_a_roll12", days(1), strategy="shadow_x")
    primary = diag.load_forward_run(tmp_path, "prev3y_crypto")
    shadow = diag.load_forward_run(tmp_path, "prev3y_crypto_shadow_a_roll12")
    ps = diag.compute_primary_shadow(primary, [shadow])
    assert ps["ranking_status"] == "ALL_INSUFFICIENT_EVIDENCE"
    assert all(s["evidence_penalty_applied"] for s in ps["strategies"])


def test_oos_vs_forward_insufficient_forward(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    oos = diag.compute_oos_vs_forward(run, oos_numbers={"sharpe": 0.9, "pf": 1.35})
    assert oos["status"] == diag.INSUFFICIENT_SAMPLE


# --- Failure injection -----------------------------------------------------


def test_truncated_json_does_not_crash(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    (tmp_path / "prev3y_crypto" / "20260601_pnl.json").write_text('{"date": "2026', encoding="utf-8")
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")  # must not raise
    assert any("pnl_unreadable" in w for w in run.warnings)
    integ = diag.compute_data_integrity(run)  # still produces a report
    assert integ["present_date_count"] == 2


def test_corrupt_csv_does_not_crash(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))
    # Binary noise CSV: still must not raise (csv reader is tolerant; loader guards).
    (tmp_path / "dashboard" / "validation_30d.csv").write_bytes(b"\x00\x01\x02 not, a, csv\n")
    run = diag.load_forward_run(tmp_path, "prev3y_crypto")
    diag.compute_data_integrity(run)  # no exception


def test_missing_parquet_marks_positions_unavailable(tmp_path):
    make_run(tmp_path, "prev3y_crypto", days(2))  # no parquet engine in env anyway
    audit = diag.audit_inputs(tmp_path, "prev3y_crypto")
    # No positions parquet present and/or no engine -> UNAVAILABLE.
    assert audit["positions_status"] == diag.UNAVAILABLE
