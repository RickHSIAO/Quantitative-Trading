"""TASK-014BZ_FIX -- offline tests for additive fixed-capital ledger semantics,
duplicate-date canonicalization, stale/catch-up/fresh price classification, scoped
risk metrics, and the corrected scorecard.

Deterministic, temp roots only. No network, no Bybit, no order, no Pilot mutation.
"""

from __future__ import annotations

import datetime
import importlib
import json
import pathlib
import sys

import pytest

ROOT = pathlib.Path(__file__).resolve().parents[2]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from src.strategy_selection import paper_portfolio_performance as pp
from src.strategy_selection import ledger_fix_semantics as lfs
from src.strategy_selection import price_freshness as pf
from src.strategy_selection import ledger_fix_scorecard as lfsc

cli = importlib.import_module("scripts.analyze_forward30_ledger_fix")

INIT = 10_000.0


def cal_dates(start: str, n: int) -> list[str]:
    d = datetime.date(int(start[:4]), int(start[4:6]), int(start[6:8]))
    return [(d + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def _csv_row(date, nav, daily_usd, *, guard="PASS", n_entered=0):
    daily_pct = round(daily_usd / INIT * 100.0, 6)
    cum = round((nav / INIT - 1.0) * 100.0, 6)
    return (f"{date},{round(nav,4)},{round(daily_usd,4)},{daily_pct},{cum},0.0,"
            f"50,{n_entered},0,0,1.0,0.0,{guard}")


def real_shaped_navs():
    """36-day additive NAV path matching the confirmed VPS structure.

    0518 anchor (10000, flat), 0519-0527 stale (flat), 0528 catch-up jump,
    0529-0604 drift to 10419.2555, 0605 canonical 10445.8930 (+ superseded
    10419.2555), 0606 10597.4148, ... 0616 official end 10607.7668, ... 0622
    extension end 10495.4855.
    """
    dates = cal_dates("20260518", 36)
    nav = {}
    nav[dates[0]] = 10000.0                       # 0518 anchor
    for d in dates[1:10]:                          # 0519-0527 stale flat
        nav[d] = 10000.0
    nav[dates[10]] = 10460.2878                     # 0528 catch-up
    # 0529-0604 linear drift 10460.2878 -> 10419.2555 (idx 11..17)
    start_v, end_v = 10460.2878, 10419.2555
    for k, idx in enumerate(range(11, 18), start=1):
        nav[dates[idx]] = round(start_v + (end_v - start_v) * (k / 7.0), 4)
    nav[dates[17]] = 10419.2555                     # 0604 exact
    nav[dates[18]] = 10445.8930                     # 0605 CANONICAL
    nav[dates[19]] = 10597.4148                     # 0606
    # 0607-0616 linear 10597.4148 -> 10607.7668 (idx 20..29)
    start_v, end_v = 10597.4148, 10607.7668
    for k, idx in enumerate(range(20, 30), start=1):
        nav[dates[idx]] = round(start_v + (end_v - start_v) * (k / 10.0), 4)
    nav[dates[29]] = 10607.7668                     # 0616 official end exact
    # 0617-0622 linear 10607.7668 -> 10495.4855 (idx 30..35)
    start_v, end_v = 10607.7668, 10495.4855
    for k, idx in enumerate(range(30, 36), start=1):
        nav[dates[idx]] = round(start_v + (end_v - start_v) * (k / 6.0), 4)
    nav[dates[35]] = 10495.4855                     # 0622 extension end exact
    return dates, nav


def write_real_shaped_ledger(paper_dir: pathlib.Path, *, include_duplicate=True):
    paper_dir.mkdir(parents=True, exist_ok=True)
    dates, nav = real_shaped_navs()
    lines = []
    prev = INIT
    for i, d in enumerate(dates):
        if d == "20260605" and include_duplicate:
            # Superseded rerun row A FIRST (append order), then canonical B.
            lines.append(_csv_row(d, 10419.2555, -61.0413))          # A (superseded)
            lines.append(_csv_row(d, 10445.8930, 10445.8930 - prev))  # B (canonical)
            prev = 10445.8930
            continue
        daily = nav[d] - prev
        ne = 50 if i == 0 else 0
        lines.append(_csv_row(d, nav[d], daily, n_entered=ne))
        prev = nav[d]
    (paper_dir / "daily_pnl.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (paper_dir / "state.json").write_text(json.dumps({
        "paper_equity_init": INIT, "nav_usd": nav[dates[35]],
        "peak_nav_usd": 10650.566016078088, "last_processed_date": dates[35],
        "positions": []}), encoding="utf-8")
    return dates, nav


def injected_signatures(dates):
    """Anchor 0518, stale 0519-0527, catch-up 0528, fresh 0529 onward."""
    sigs = {}
    for i, d in enumerate(dates):
        if i == 0:
            fp = "FP_ANCHOR"
            ds = "cache_fallback"
        elif 1 <= i <= 9:                # 0519-0527 stale (same fp as anchor)
            fp = "FP_ANCHOR"
            ds = "cache_fallback"
        elif i == 10:                    # 0528 catch-up (first change)
            fp = "FP_CATCHUP"
            ds = "bybit_read_only_live"
        else:                            # 0529 onward fresh distinct
            fp = f"FP_{d}"
            ds = "bybit_read_only_live"
        sigs[d] = {"price_vector_fingerprint": fp, "data_source": ds}
    return sigs


def load_canonical(paper_dir):
    raw = pp.load_raw_performance_rows(paper_dir)
    canon = lfs.canonicalize_ledger(raw.rows, raw.paper_equity_init)
    return raw, canon


# ===========================================================================
# BLOCKER 1 -- additive fixed-capital semantics
# ===========================================================================


def test_additive_nav_semantics_pass(tmp_path):
    write_real_shaped_ledger(tmp_path / "pp")
    raw, canon = load_canonical(tmp_path / "pp")
    sem = lfs.validate_ledger_semantics(canon.canonical_rows, INIT)
    assert sem["overall_status"] == lfs.LEDGER_SEMANTICS_VALID
    assert sem["consistency_failure_count"] == 0
    assert sem["additive_nav_status"] == lfs.ADDITIVE_NAV_VALID


def test_prior_nav_compounding_is_rejected(tmp_path):
    write_real_shaped_ledger(tmp_path / "pp")
    raw, canon = load_canonical(tmp_path / "pp")
    # The WRONG compounding relation must NOT hold for this additive ledger.
    assert lfs.compounding_continuity_holds(canon.canonical_rows) is False


def test_fixed_capital_daily_pct_valid(tmp_path):
    write_real_shaped_ledger(tmp_path / "pp")
    raw, canon = load_canonical(tmp_path / "pp")
    sem = lfs.validate_ledger_semantics(canon.canonical_rows, INIT)
    assert sem["daily_pct_status"] == lfs.DAILY_PCT_FIXED_CAPITAL_VALID


def test_cumulative_pct_valid(tmp_path):
    write_real_shaped_ledger(tmp_path / "pp")
    raw, canon = load_canonical(tmp_path / "pp")
    sem = lfs.validate_ledger_semantics(canon.canonical_rows, INIT)
    assert sem["cumulative_pct_status"] == lfs.CUMULATIVE_PCT_VALID


def test_additive_failure_detected(tmp_path):
    paper = tmp_path / "pp"
    paper.mkdir(parents=True)
    # nav jumps but daily_pnl_usd does not justify it -> additive failure.
    rows = [_csv_row("20260518", 10000.0, 0.0, n_entered=50),
            _csv_row("20260519", 10500.0, 10.0)]  # 10000+10 != 10500
    (paper / "daily_pnl.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    raw, canon = load_canonical(paper)
    sem = lfs.validate_ledger_semantics(canon.canonical_rows, INIT)
    assert sem["additive_nav_status"] == lfs.ADDITIVE_NAV_FAILURE
    assert sem["consistency_failure_count"] >= 1


# ===========================================================================
# BLOCKER 2 -- duplicate canonicalization
# ===========================================================================


def test_20260605_conflicting_duplicate_selects_second_row(tmp_path):
    write_real_shaped_ledger(tmp_path / "pp", include_duplicate=True)
    raw, canon = load_canonical(tmp_path / "pp")
    assert canon.status == lfs.CANONICALIZATION_VALID
    assert canon.duplicate_date_count == 1
    assert canon.superseded_rerun_count == 1
    assert canon.ambiguous_duplicate_conflict_count == 0
    chosen = {r.date: r for r in canon.canonical_rows}["20260605"]
    assert chosen.nav_usd == pytest.approx(10445.8930, abs=1e-4)
    assert chosen.daily_pnl_usd == pytest.approx(26.6375, abs=1e-3)
    rec = [r for r in canon.resolution_records if r["date"] == "2026-06-05"][0]
    assert rec["classification"] == lfs.SUPERSEDED_RERUN
    assert rec["resolution_method"] == "next_date_additive_continuity"
    assert rec["superseded_rows"][0]["nav_usd"] == pytest.approx(10419.2555, abs=1e-4)


def test_identical_duplicate_safe_dedupe(tmp_path):
    paper = tmp_path / "pp"
    paper.mkdir(parents=True)
    rows = [_csv_row("20260518", 10000.0, 0.0, n_entered=50),
            _csv_row("20260519", 10050.0, 50.0),
            _csv_row("20260519", 10050.0, 50.0)]  # identical duplicate
    (paper / "daily_pnl.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    raw, canon = load_canonical(paper)
    assert canon.identical_duplicate_count == 1
    assert canon.superseded_rerun_count == 0
    assert canon.canonical_row_count == 2
    rec = [r for r in canon.resolution_records if r["classification"] == lfs.IDENTICAL_DUPLICATE][0]
    assert rec["raw_row_count"] == 2


def test_ambiguous_duplicate_fails_closed(tmp_path):
    paper = tmp_path / "pp"
    paper.mkdir(parents=True)
    # Two differing 0519 rows; neither continues additively into 0520.
    rows = [_csv_row("20260518", 10000.0, 0.0, n_entered=50),
            _csv_row("20260519", 10050.0, 50.0),
            _csv_row("20260519", 10070.0, 70.0),
            _csv_row("20260520", 10999.0, 100.0)]  # 10050+100 and 10070+100 both != 10999
    (paper / "daily_pnl.csv").write_text("\n".join(rows) + "\n", encoding="utf-8")
    raw, canon = load_canonical(paper)
    assert canon.ambiguous_duplicate_conflict_count == 1
    assert canon.status == lfs.CANONICALIZATION_AMBIGUOUS
    rec = [r for r in canon.resolution_records
           if r["classification"] == lfs.AMBIGUOUS_DUPLICATE_CONFLICT][0]
    assert "FAIL CLOSED" in rec["reason"]


def test_duplicate_resolution_report_fields(tmp_path):
    write_real_shaped_ledger(tmp_path / "pp")
    raw, canon = load_canonical(tmp_path / "pp")
    rep = lfs.build_duplicate_resolution_report(canon)
    for k in ("raw_performance_row_count", "canonical_performance_row_count", "duplicate_date_count",
              "identical_duplicate_count", "superseded_rerun_count", "ambiguous_duplicate_conflict_count",
              "duplicate_resolution_records", "canonical_row_fingerprints", "superseded_row_fingerprints"):
        assert k in rep
    assert rep["raw_performance_row_count"] == 37   # 36 dates + 1 duplicate row
    assert rep["canonical_performance_row_count"] == 36
    assert len(rep["superseded_row_fingerprints"]) == 1


def test_raw_ledger_byte_identical_after_analysis(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    before = (paper / "daily_pnl.csv").read_bytes()
    raw, canon = load_canonical(paper)
    lfs.validate_ledger_semantics(canon.canonical_rows, INIT)
    assert (paper / "daily_pnl.csv").read_bytes() == before


# ===========================================================================
# BLOCKER 3 -- stale / catch-up / fresh classification + scoped risk
# ===========================================================================


def test_exact_stale_classification_0518_to_0528(tmp_path):
    dates, _ = real_shaped_navs()
    official = dates[:30]
    fr = pf.classify_freshness(official, injected_signatures(dates))
    cls = fr["classifications"]
    assert cls["20260518"] == pf.ENTRY_PRICE_ANCHOR
    for d in cal_dates("20260519", 9):       # 0519-0527
        assert cls[d] == pf.STALE_CACHE_NO_PRICE_CHANGE, d
    assert cls["20260528"] == pf.FRESH_MULTI_DAY_CATCHUP_MARK
    assert cls["20260529"] == pf.FRESH_DAILY_MARK
    assert fr["flat_ledger_date_count"] == 10   # 1 anchor + 9 stale
    assert len(fr["catchup_dates"]) == 1


def test_fresh_one_day_observation_count_is_19(tmp_path):
    dates, _ = real_shaped_navs()
    official = dates[:30]
    fr = pf.classify_freshness(official, injected_signatures(dates))
    assert fr["fresh_daily_observation_count"] == 19   # 0529-0616


def test_official_daily_risk_is_insufficient_fresh_observations(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    raw, canon = load_canonical(paper)
    official = canon.canonical_rows[:30]
    dates, _ = real_shaped_navs()
    fr = pf.classify_freshness([r.date for r in official], injected_signatures(dates))
    risk = lfsc.compute_fresh_daily_risk(official, fr, paper_equity_init=INIT)
    # 19 fresh < min 20 -> insufficient; Sharpe/Sortino NOT published.
    assert risk["fresh_daily_observation_count"] == 19
    assert risk["status"] == pf.INSUFFICIENT_FRESH_DAILY_OBSERVATIONS
    assert risk["sharpe"] is None and risk["sortino"] is None


def test_stale_zeros_and_catchup_excluded_from_risk(tmp_path):
    """With a high min, fresh metrics use only FRESH_DAILY_MARK days (exclude
    anchor/stale/catch-up). Lower the min to compute and verify exclusion."""
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    raw, canon = load_canonical(paper)
    official = canon.canonical_rows[:30]
    dates, _ = real_shaped_navs()
    fr = pf.classify_freshness([r.date for r in official], injected_signatures(dates))
    risk = lfsc.compute_fresh_daily_risk(official, fr, paper_equity_init=INIT, min_fresh=5)
    assert risk["fresh_daily_observation_count"] == 19
    assert risk["status"] == "FRESH_DAILY_METRICS_AVAILABLE"
    # The catch-up day 20260528 (+4.6% mark) is excluded -> best fresh day is far smaller.
    assert risk["best_day"]["return_decimal"] < 0.046
    assert pf.FRESH_MULTI_DAY_CATCHUP_MARK in risk["excluded_scopes"]
    assert pf.STALE_CACHE_NO_PRICE_CHANGE in risk["excluded_scopes"]


def test_price_freshness_unavailable_without_engine(tmp_path):
    """No parquet -> all dates PRICE_FRESHNESS_UNAVAILABLE; risk fails closed."""
    dates, _ = real_shaped_navs()
    official = dates[:30]
    sigs = {d: {"price_vector_fingerprint": None, "data_source": None} for d in dates}
    fr = pf.classify_freshness(official, sigs)
    assert all(c == pf.PRICE_FRESHNESS_UNAVAILABLE for c in fr["classifications"].values())
    assert fr["fresh_daily_observation_count"] == 0


# ===========================================================================
# Holding-period / extension scopes
# ===========================================================================


def test_official_holding_period_return_and_nav(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    raw, canon = load_canonical(paper)
    official = canon.canonical_rows[:30]
    holding = lfsc.compute_holding_period_metrics(official, paper_equity_init=INIT)
    assert holding["calendar_days"] == 30
    assert holding["cumulative_return_decimal"] == pytest.approx(0.06077668, abs=1e-8)
    assert holding["end_nav_usd"] == pytest.approx(10607.7668, abs=1e-4)
    assert holding["drawdown_status"] == lfsc.OBSERVED_MARK_DRAWDOWN
    assert holding["observed_mark_drawdown_decimal"] <= 0.0
    assert "unknown" in holding["drawdown_warning"].lower()


def test_observed_mark_drawdown_scoped_and_warned(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    raw, canon = load_canonical(paper)
    holding = lfsc.compute_holding_period_metrics(canon.canonical_rows[:30], paper_equity_init=INIT)
    # Drawdown from the 10607.7668 region is reported as observed-mark, not verified.
    assert holding["drawdown_status"] == lfsc.OBSERVED_MARK_DRAWDOWN


def test_extension_period_return_relative_to_official_end_nav(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    raw, canon = load_canonical(paper)
    official = canon.canonical_rows[:30]
    extension = canon.canonical_rows[30:]
    holding = lfsc.compute_holding_period_metrics(official, paper_equity_init=INIT)
    dates, _ = real_shaped_navs()
    extfr = pf.classify_freshness([r.date for r in canon.canonical_rows], injected_signatures(dates))
    ext = lfsc.compute_extension_metrics(extension, official_end_nav=holding["end_nav_usd"],
                                         freshness=extfr)
    assert ext["extension_count"] == 6
    assert ext["extension_latest_cumulative_return_from_initial"] == pytest.approx(0.04954855, abs=1e-8)
    # period return = 10495.4855 / 10607.7668 - 1
    expected_period = 10495.4855 / 10607.7668 - 1.0
    assert ext["extension_period_return"] == pytest.approx(expected_period, abs=1e-9)
    assert ext["fresh_daily_observation_count"] == 6
    assert ext["robust"] is False


# ===========================================================================
# BLOCKER 4 -- corrected scorecard / challengers
# ===========================================================================


def test_scorecard_not_reject_data_incomplete(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    raw, canon = load_canonical(paper)
    official = canon.canonical_rows[:30]
    sem = lfs.validate_ledger_semantics(canon.canonical_rows, INIT)
    holding = lfsc.compute_holding_period_metrics(official, paper_equity_init=INIT)
    dates, _ = real_shaped_navs()
    fr = pf.classify_freshness([r.date for r in official], injected_signatures(dates))
    risk = lfsc.compute_fresh_daily_risk(official, fr, paper_equity_init=INIT)
    sc = lfsc.score_corrected(semantics=sem, canonicalization_status=canon.status,
                              holding=holding, fresh_risk=risk, official_sufficient=True)
    assert sc["label"] != "REJECT_DATA_INCOMPLETE"
    assert sc["label"] == lfsc.KEEP_BASELINE_PROVISIONAL
    by = {g["gate"]: g["status"] for g in sc["gates"]}
    assert by["positive_holding_period_return"] == lfsc.GATE_PASS
    assert by["daily_risk_metrics"] == pf.INSUFFICIENT_FRESH_DAILY_OBSERVATIONS
    assert by["observed_drawdown"] in (lfsc.GATE_PASS_WITH_WARNING, lfsc.GATE_PASS)
    assert sc["never_reject_data_incomplete_after_additive_valid"] is True


def test_scorecard_supersedes_prior_labels(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    raw, canon = load_canonical(paper)
    sem = lfs.validate_ledger_semantics(canon.canonical_rows, INIT)
    holding = lfsc.compute_holding_period_metrics(canon.canonical_rows[:30], paper_equity_init=INIT)
    risk = {"status": pf.INSUFFICIENT_FRESH_DAILY_OBSERVATIONS, "fresh_daily_observation_count": 19}
    sc = lfsc.score_corrected(semantics=sem, canonicalization_status=canon.status, holding=holding,
                              fresh_risk=risk, official_sufficient=True)
    tasks = {s["task"] for s in sc["supersedes"]}
    assert tasks == {"TASK-014BY", "TASK-014BZ"}


def test_zero_challengers_promoted():
    ch = cli._challengers()
    assert ch["emitted_count"] == 0
    assert ch["challengers_promoted"] == 0
    assert all(f["status"] == "FUTURE_RESEARCH_CANDIDATE" for f in ch["future_research_candidates"])


# ===========================================================================
# Determinism + CLI end-to-end + safety
# ===========================================================================


def test_deterministic_rerun(tmp_path):
    paper = tmp_path / "pp"
    write_real_shaped_ledger(paper)
    r1, c1 = load_canonical(paper)
    r2, c2 = load_canonical(paper)
    s1 = lfs.validate_ledger_semantics(c1.canonical_rows, INIT)
    s2 = lfs.validate_ledger_semantics(c2.canonical_rows, INIT)
    assert json.dumps(s1, sort_keys=True, default=str) == json.dumps(s2, sort_keys=True, default=str)
    assert (lfs.build_duplicate_resolution_report(c1)["canonical_row_fingerprints"]
            == lfs.build_duplicate_resolution_report(c2)["canonical_row_fingerprints"])


def test_cli_end_to_end(tmp_path):
    pytest.importorskip("openpyxl")
    write_real_shaped_ledger(tmp_path / "fwd" / "paper_portfolio")
    out = tmp_path / "out"
    rc = cli.main(["--input-root", str(tmp_path / "fwd"), "--run-key", "prev3y_crypto",
                   "--output-root", str(out), "--json-only"])
    assert rc == 0
    for f in ("ledger_semantics.json", "duplicate_resolution.json", "price_freshness.json",
              "official_holding_period_metrics.json", "fresh_daily_risk_observations.json",
              "post_validation_extension.json", "corrected_strategy_scorecard.json",
              "corrected_challenger_hypotheses.json", "superseded_notice.json",
              "corrected_strategy_selection_report.md", "corrected_strategy_selection_report.xlsx"):
        assert (out / f).exists(), f
    sem = json.loads((out / "ledger_semantics.json").read_text(encoding="utf-8"))
    assert sem["overall_status"] == lfs.LEDGER_SEMANTICS_VALID
    assert sem["consistency_failure_count"] == 0
    dup = json.loads((out / "duplicate_resolution.json").read_text(encoding="utf-8"))
    assert dup["superseded_rerun_count"] == 1
    holding = json.loads((out / "official_holding_period_metrics.json").read_text(encoding="utf-8"))
    assert holding["cumulative_return_decimal"] == pytest.approx(0.06077668, abs=1e-8)
    assert holding["end_nav_usd"] == pytest.approx(10607.7668, abs=1e-4)
    sc = json.loads((out / "corrected_strategy_scorecard.json").read_text(encoding="utf-8"))
    assert sc["label"] != "REJECT_DATA_INCOMPLETE"
    assert sc["label"] == lfsc.KEEP_BASELINE_PROVISIONAL


def test_cli_source_read_only(tmp_path):
    paper = tmp_path / "fwd" / "paper_portfolio"
    write_real_shaped_ledger(paper)
    before = (paper / "daily_pnl.csv").read_bytes()
    cli.main(["--input-root", str(tmp_path / "fwd"), "--run-key", "prev3y_crypto",
              "--output-root", str(tmp_path / "out"), "--json-only"])
    assert (paper / "daily_pnl.csv").read_bytes() == before


def test_cli_zero_network_and_orders(tmp_path):
    write_real_shaped_ledger(tmp_path / "fwd" / "paper_portfolio")
    result = cli.run_analysis(input_root=str(tmp_path / "fwd"), run_key="prev3y_crypto",
                              output_root=str(tmp_path / "out"), pilot_id="TEST_PILOT")
    assert result["network_calls"] == 0
    assert result["bybit_calls"] == 0
    assert result["orders_sent"] == 0
    assert result["challengers_promoted"] == 0
    assert result["consistency_failure_count"] == 0
    assert result["superseded_rerun_count"] == 1
