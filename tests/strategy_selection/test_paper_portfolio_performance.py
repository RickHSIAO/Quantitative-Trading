"""TASK-014BZ -- offline tests for the authoritative Paper Portfolio performance
source, the official 30-day window derivation, and the corrected scorecard /
challenger / lineage logic.

Deterministic, temp roots only. No network, no Bybit, no order, no Pilot mutation.
Reuses the canonical metrics module for risk ratios.
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
from src.strategy_selection import corrected_strategy_analysis as csa

cli = importlib.import_module("scripts.analyze_forward30_authoritative_performance")

INIT = 10_000.0


# --- fixtures ---------------------------------------------------------------


def cal_dates(start: str, n: int) -> list[str]:
    d = datetime.date(int(start[:4]), int(start[4:6]), int(start[6:8]))
    return [(d + datetime.timedelta(days=i)).strftime("%Y%m%d") for i in range(n)]


def _row(date, nav, daily_pct, cum_pct, *, guard="PASS", n_entered=50, n_open=50, n_exited=0):
    daily_usd = nav - INIT  # placeholder; not used by metrics
    return (f"{date},{nav},{daily_usd},{daily_pct},{cum_pct},0.0,{n_open},{n_entered},"
            f"{n_exited},0,1.0,0.0,{guard}")


def write_ledger(paper_dir: pathlib.Path, cumulative_pcts, dates, *,
                 init=INIT, state_extra=None, guard_for=None, n_entered_for=None):
    """Write a headerless daily_pnl.csv + state.json that is internally NAV-consistent.

    nav = init*(1+cum/100); daily = (nav[i]/nav[i-1]-1)*100 -> both continuity
    checks pass exactly."""
    paper_dir.mkdir(parents=True, exist_ok=True)
    lines = []
    prev = None
    last_nav = init
    for i, dt in enumerate(dates):
        cum = cumulative_pcts[i]
        nav = init * (1.0 + cum / 100.0)
        daily = 0.0 if prev is None else (nav / prev - 1.0) * 100.0
        guard = (guard_for(i) if guard_for else "PASS")
        ne = (n_entered_for(i) if n_entered_for else (50 if i == 0 else 0))
        lines.append(_row(dt, nav, daily, cum, guard=guard, n_entered=ne,
                          n_open=50, n_exited=0))
        prev = nav
        last_nav = nav
    (paper_dir / "daily_pnl.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    state = {"paper_equity_init": init, "nav_usd": last_nav,
             "peak_nav_usd": init * (1.0 + max(cumulative_pcts) / 100.0),
             "last_processed_date": dates[-1], "positions": []}
    if state_extra:
        state.update(state_extra)
    (paper_dir / "state.json").write_text(json.dumps(state), encoding="utf-8")
    return paper_dir


def vps_shaped_cumulatives():
    """36 cumulative pcts: official (first 30) ends at +6.077668% on 20260616;
    extension (6) ends at +4.954855% on 20260622; interim peak +6.50566%."""
    cum = [round(6.077668 * (i / 29.0), 6) for i in range(30)]
    cum += [6.15, 6.505660, 6.30, 5.60, 5.20, 4.954855]
    return cum


def write_dry_run_snapshots(snap_dir: pathlib.Path, dates, *, clock_started=False, day_number=0):
    snap_dir.mkdir(parents=True, exist_ok=True)
    for dt in dates:
        (snap_dir / f"{dt}_pnl.json").write_text(json.dumps({
            "date": dt, "clock_started": clock_started, "day_number": day_number,
            "daily_pnl_pct": 0.0, "cumulative_pnl_pct": 0.0, "nav_usd": 10000.0,
            "paper_execution_status": "FORBIDDEN", "dry_run": True}), encoding="utf-8")


# ===========================================================================
# Dry-run snapshots cannot become performance data
# ===========================================================================


def test_dry_run_snapshots_never_become_performance(tmp_path):
    snap = tmp_path / "prev3y_crypto"
    dates = cal_dates("20260518", 37)
    write_dry_run_snapshots(snap, dates)
    scan = pp.scan_dry_run_snapshots(snap)
    assert scan["snapshot_file_count"] == 37
    assert scan["dry_run_placeholder_detected"] is True
    assert scan["snapshot_clock_started_count"] == 0
    assert scan["snapshot_day_number_distribution"] == {"0": 37}


def test_is_dry_run_placeholder_markers():
    assert pp.is_dry_run_placeholder(
        {"clock_started": False, "day_number": 0, "paper_execution_status": "FORBIDDEN"}) is True
    # A real performance day (clock started, day_number>0) is NOT a placeholder.
    assert pp.is_dry_run_placeholder(
        {"clock_started": True, "day_number": 5, "paper_execution_status": "PAPER"}) is False


def test_missing_ledger_with_dry_run_snapshots_fails_closed(tmp_path):
    """37 dry-run snapshots present but no authoritative ledger -> FAIL CLOSED,
    never silently fall back to the zero-valued dry-run JSON."""
    write_dry_run_snapshots(tmp_path / "prev3y_crypto", cal_dates("20260518", 37))
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    assert perf.status == pp.PERFORMANCE_SOURCE_MISSING
    assert perf.valid_row_count == 0


# ===========================================================================
# 36 rows -> exactly the first 30-row official window
# ===========================================================================


def test_36_rows_produce_first_30_official_window(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    assert perf.status == pp.VALID_AUTHORITATIVE_PERFORMANCE
    assert perf.valid_row_count == 36
    w = pp.derive_validation_window(perf)
    assert w.official_day_count == 30
    assert w.official_start == "20260518"
    assert w.official_end == "20260616"
    assert len(w.extension_rows) == 6
    assert w.extension_start == "20260617"
    assert w.extension_end == "20260622"


def test_official_and_extension_cumulative_returns(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    om = pp.compute_window_metrics(w.official_rows, paper_equity_init=INIT)
    em = pp.compute_window_metrics(w.extension_rows, paper_equity_init=INIT)
    assert om["cumulative_return_decimal"] == pytest.approx(0.06077668, abs=1e-8)
    assert em["cumulative_return_decimal"] == pytest.approx(0.04954855, abs=1e-8)
    assert om["end_nav_usd"] == pytest.approx(INIT * 1.06077668, rel=1e-9)


def test_snapshot_count_and_performance_count_are_separate(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    write_dry_run_snapshots(tmp_path / "prev3y_crypto", cal_dates("20260518", 37))
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    scan = pp.scan_dry_run_snapshots(tmp_path / "prev3y_crypto")
    om = pp.compute_window_metrics(w.official_rows, paper_equity_init=INIT)
    em = pp.compute_window_metrics(w.extension_rows, paper_equity_init=INIT)
    lineage = csa.build_source_lineage(perf, w, scan, om, em)
    assert lineage["snapshot_file_count"] == 37
    assert lineage["authoritative_performance_row_count"] == 36
    assert lineage["official_validation_day_count"] == 30
    # Three distinct fields; 37/30 never used as a coverage label.
    assert lineage["snapshot_file_count"] != lineage["official_validation_day_count"]


def test_end_date_not_hardcoded_window_shifts_with_data(tmp_path):
    """A different start date yields a different derived official_end (no hardcode)."""
    dates = cal_dates("20260601", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    assert w.official_start == "20260601"
    assert w.official_end == "20260630"  # 30th calendar day from 0601, derived


# ===========================================================================
# NAV continuity + duplicate + corrupt + zero-valid-vs-placeholder
# ===========================================================================


def test_nav_continuity_validation_flags_break(tmp_path):
    dates = cal_dates("20260518", 30)
    paper = write_ledger(tmp_path / "paper_portfolio",
                         [round(0.2 * i, 4) for i in range(30)], dates)
    # Corrupt one NAV to break continuity (keep guard PASS).
    lines = (paper / "daily_pnl.csv").read_text(encoding="utf-8").splitlines()
    parts = lines[10].split(",")
    parts[1] = str(float(parts[1]) * 1.5)  # nav jump
    lines[10] = ",".join(parts)
    (paper / "daily_pnl.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    perf = pp.load_authoritative_performance(paper)
    assert perf.status == pp.NAV_CONTINUITY_FAILURE
    assert len(perf.nav_continuity_failures) >= 1


def test_duplicate_date_rejected(tmp_path):
    dates = cal_dates("20260518", 30)
    paper = write_ledger(tmp_path / "paper_portfolio",
                         [round(0.2 * i, 4) for i in range(30)], dates)
    lines = (paper / "daily_pnl.csv").read_text(encoding="utf-8").splitlines()
    lines.append(lines[5])  # duplicate an existing date row
    (paper / "daily_pnl.csv").write_text("\n".join(lines) + "\n", encoding="utf-8")
    perf = pp.load_authoritative_performance(paper)
    assert perf.status == pp.DUPLICATE_PERFORMANCE_DATE
    assert perf.duplicate_dates


def test_corrupt_ledger_fails_closed(tmp_path):
    paper = tmp_path / "paper_portfolio"
    paper.mkdir(parents=True)
    # Digit-leading data rows that are structurally broken: too few columns, and a
    # non-finite NAV. These must be REJECTED (not silently treated as returns).
    (paper / "daily_pnl.csv").write_text(
        "20260518,10000.0,bad\n"
        "20260519,not_a_number,0,0,0,0,50,50,0,0,1.0,0.0,PASS\n", encoding="utf-8")
    perf = pp.load_authoritative_performance(paper)
    # No valid rows parsed -> insufficient (fail closed), never returns fabricated returns.
    assert perf.status == pp.INSUFFICIENT_VALID_PERFORMANCE_DAYS
    assert perf.valid_row_count == 0
    assert perf.rejected


def test_missing_ledger_fails_closed(tmp_path):
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    assert perf.status == pp.PERFORMANCE_SOURCE_MISSING


def test_zero_valued_valid_row_distinct_from_dry_run_placeholder(tmp_path):
    """A flat (zero-return) but VALID market day in the ledger is NOT a dry-run
    placeholder; the placeholder lives only in the snapshot JSON."""
    paper = write_ledger(tmp_path / "paper_portfolio", [0.0], ["20260518"])
    perf = pp.load_authoritative_performance(paper)
    # One valid (zero) authoritative row -> insufficient for 30d, but the row IS valid.
    assert perf.valid_row_count == 1
    row = perf.all_rows[0]
    assert row.guard_status == "PASS" and row.daily_pnl_pct == 0.0
    # The same date as a dry-run snapshot is classified as a placeholder.
    assert pp.is_dry_run_placeholder(
        {"clock_started": False, "day_number": 0, "paper_execution_status": "FORBIDDEN"}) is True


def test_state_conflict_detected(tmp_path):
    dates = cal_dates("20260518", 30)
    paper = write_ledger(tmp_path / "paper_portfolio",
                         [round(0.2 * i, 4) for i in range(30)], dates,
                         state_extra={"last_processed_date": "20991231"})
    perf = pp.load_authoritative_performance(paper)
    assert perf.status == pp.PERFORMANCE_SOURCE_CONFLICT
    assert perf.state_conflicts


# ===========================================================================
# Corrected scorecard / challengers / comparability / hold
# ===========================================================================


def test_insufficient_window_is_needs_more_data(tmp_path):
    paper = write_ledger(tmp_path / "paper_portfolio", [0.0], ["20260518"])
    perf = pp.load_authoritative_performance(paper)
    w = pp.derive_validation_window(perf)
    om = pp.compute_window_metrics(w.official_rows, paper_equity_init=INIT)
    sc = csa.score_official_window(perf, w, om)
    assert sc["label"] == csa.NEEDS_MORE_DATA


def test_corrected_positive_return_cannot_be_reject_insufficient_edge(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    om = pp.compute_window_metrics(w.official_rows, paper_equity_init=INIT)
    sc = csa.score_official_window(perf, w, om)
    # Prior invalid label must not survive a corrected positive cumulative return.
    assert sc["label"] != csa.SUPERSEDED_LABEL
    assert sc["label"] == csa.KEEP_BASELINE
    pne = {g["gate"]: g["status"] for g in sc["gates"]}["positive_net_expectancy"]
    assert pne == csa.GATE_PASS
    assert sc["supersedes"]["invalid_label"] == "REJECT_INSUFFICIENT_EDGE"


def test_prior_challengers_not_evidence_backed_from_snapshots(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    om = pp.compute_window_metrics(w.official_rows, paper_equity_init=INIT)
    # contribution unavailable -> no causal claim, no evidence-backed emission.
    ch = csa.correct_challengers(perf, w, om, contribution_available=False,
                                 capabilities={"volatility_adjusted_sizing": True})
    assert ch["emitted_count"] == 0
    assert all(inv["corrected_status"] == "INVALIDATED_FROM_DRY_RUN_ANALYSIS"
               for inv in ch["invalidated_prior_challengers"])
    assert "no causal claim" in ch["contribution_note"].lower()


def test_challengers_emitted_only_with_contribution_evidence(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    om = pp.compute_window_metrics(w.official_rows, paper_equity_init=INIT)
    ch = csa.correct_challengers(perf, w, om, contribution_available=True,
                                 capabilities={"volatility_adjusted_sizing": True})
    assert ch["emitted_count"] <= csa.MAX_CHALLENGERS
    assert ch["emitted_count"] == 1
    assert ch["promotion_status"] == "NONE_PROMOTED"


def test_primary_shadow_not_comparable_without_independent_shadow(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    comp = csa.assess_primary_shadow_comparability(perf, None)
    assert comp["primary_shadow_comparable"] is False
    assert "MISSING_SHADOW" in comp["reason"]


def test_static_hold_not_a_defect(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    hold = csa.classify_hold_behavior(w, rebalancing_documented=False)
    assert hold["behavior"] == csa.STATIC_HOLD
    assert hold["is_defect"] is False
    assert hold["warning"] is None
    assert hold["daily_mark_to_market_observed"] is True


def test_static_hold_warns_when_rebalancing_documented(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    perf = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    w = pp.derive_validation_window(perf)
    hold = csa.classify_hold_behavior(w, rebalancing_documented=True)
    assert hold["is_defect"] is False
    assert hold["warning"] is not None


# ===========================================================================
# Determinism + read-only + CLI end-to-end
# ===========================================================================


def test_deterministic_rerun(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    p1 = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    p2 = pp.load_authoritative_performance(tmp_path / "paper_portfolio")
    assert p1.performance_source_fingerprint == p2.performance_source_fingerprint
    w1 = pp.derive_validation_window(p1)
    w2 = pp.derive_validation_window(p2)
    m1 = pp.compute_window_metrics(w1.official_rows, paper_equity_init=INIT)
    m2 = pp.compute_window_metrics(w2.official_rows, paper_equity_init=INIT)
    assert json.dumps(m1, sort_keys=True) == json.dumps(m2, sort_keys=True)


def test_source_files_read_only(tmp_path):
    dates = cal_dates("20260518", 36)
    paper = write_ledger(tmp_path / "paper_portfolio", vps_shaped_cumulatives(), dates)
    before_csv = (paper / "daily_pnl.csv").read_bytes()
    before_state = (paper / "state.json").read_bytes()
    pp.load_authoritative_performance(paper)
    assert (paper / "daily_pnl.csv").read_bytes() == before_csv
    assert (paper / "state.json").read_bytes() == before_state


def test_cli_end_to_end_writes_corrected_reports(tmp_path):
    pytest.importorskip("openpyxl")
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "fwd" / "paper_portfolio", vps_shaped_cumulatives(), dates)
    write_dry_run_snapshots(tmp_path / "fwd" / "prev3y_crypto", cal_dates("20260518", 37))
    out = tmp_path / "out"
    rc = cli.main(["--input-root", str(tmp_path / "fwd"), "--run-key", "prev3y_crypto",
                   "--output-root", str(out), "--json-only"])
    assert rc == 0
    for f in ("source_lineage.json", "official_30d_metrics.json", "post_validation_extension.json",
              "corrected_strategy_scorecard.json", "corrected_challenger_hypotheses.json",
              "primary_shadow_comparability.json", "static_hold_behavior.json",
              "superseded_notice.json", "corrected_strategy_selection_report.md",
              "corrected_strategy_selection_report.xlsx"):
        assert (out / f).exists(), f
    lineage = json.loads((out / "source_lineage.json").read_text(encoding="utf-8"))
    assert lineage["official_30d_cumulative_return"] == pytest.approx(0.06077668, abs=1e-8)
    assert lineage["extension_latest_cumulative_return"] == pytest.approx(0.04954855, abs=1e-8)
    assert lineage["snapshot_file_count"] == 37
    assert lineage["official_validation_day_count"] == 30
    sc = json.loads((out / "corrected_strategy_scorecard.json").read_text(encoding="utf-8"))
    assert sc["label"] == csa.KEEP_BASELINE


def test_cli_is_read_only_on_sources(tmp_path):
    dates = cal_dates("20260518", 36)
    paper = write_ledger(tmp_path / "fwd" / "paper_portfolio", vps_shaped_cumulatives(), dates)
    before = (paper / "daily_pnl.csv").read_bytes()
    cli.main(["--input-root", str(tmp_path / "fwd"), "--run-key", "prev3y_crypto",
              "--output-root", str(tmp_path / "out"), "--json-only"])
    assert (paper / "daily_pnl.csv").read_bytes() == before


def test_cli_reports_zero_network_and_orders(tmp_path):
    dates = cal_dates("20260518", 36)
    write_ledger(tmp_path / "fwd" / "paper_portfolio", vps_shaped_cumulatives(), dates)
    result = cli.run_analysis(
        input_root=str(tmp_path / "fwd"), run_key="prev3y_crypto",
        shadow_run_key="prev3y_crypto_shadow_a_roll12", output_root=str(tmp_path / "out"),
        pilot_id="TEST_PILOT")
    assert result["network_calls"] == 0
    assert result["bybit_calls"] == 0
    assert result["orders_sent"] == 0
    assert result["challengers_promoted"] == 0
    assert result["data_lineage_status"] == pp.VALID_AUTHORITATIVE_PERFORMANCE
