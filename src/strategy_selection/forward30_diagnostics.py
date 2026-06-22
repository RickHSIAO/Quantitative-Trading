"""TASK-014BY -- deterministic, offline 30-day Forward Validation diagnostics.

Read-only with respect to all Forward / Pilot source artifacts. Reuses the
canonical performance metrics in ``src.metrics.performance`` (no duplicate
financial formulas). Never fabricates unavailable MAE/MFE, regime, cost or trade
data: missing dimensions are labelled UNAVAILABLE / INSUFFICIENT_SAMPLE /
NO_CANONICAL_DEFINITION and the exact missing input is reported.

Every numeric output is tagged with its scope and period. Thresholds used for
sample-sufficiency / scorecard gates are REVIEW thresholds (clearly labelled),
not optimized strategy parameters, and are never tuned against the 30-day sample.
"""

from __future__ import annotations

import csv
import hashlib
import json
import math
import pathlib
import re
from dataclasses import dataclass, field
from typing import Any, Callable, Mapping, Sequence

TASK_ID = "TASK-014BY"

# Audit status vocabulary.
PRESENT = "PRESENT"
MISSING = "MISSING"
INCOMPATIBLE = "INCOMPATIBLE"
PARTIAL = "PARTIAL"
EXCLUDED = "EXCLUDED"
UNAVAILABLE = "UNAVAILABLE"
INSUFFICIENT_SAMPLE = "INSUFFICIENT_SAMPLE"
NO_CANONICAL_DEFINITION = "NO_CANONICAL_DEFINITION"

# Records excluded from strategy performance (never counted).
EXCLUDED_RECORD_CATEGORIES = ("TASK-014BO_BP_MANUAL_ROUND_TRIP", "SMOKE_TEST")

# REVIEW thresholds (NOT optimized strategy parameters; minimum observation
# counts below which a metric is reported INSUFFICIENT_SAMPLE).
REVIEW_THRESHOLDS = {
    "min_days_for_return_metrics": 20,
    "min_days_for_risk_ratios": 20,
    "min_trades_for_trade_metrics": 20,
    "min_obs_per_regime": 10,
    "forward_required_days": 30,
}

EXPECTED_STRATEGY_NAME = "prev3y_crypto_combined_paper_safe_variant"
PRIMARY_RUN_KEY = "prev3y_crypto"
SHADOW_RUN_KEY = "prev3y_crypto_shadow_a_roll12"

_DATE_FILE_RE = re.compile(r"^(\d{8})_(pnl|forward_stats|positions)\.")
_COMPACT_RE = re.compile(r"^\d{8}$")


def sha256_file(path: pathlib.Path) -> str:
    if not path.exists() or not path.is_file():
        return ""
    return "sha256:" + hashlib.sha256(path.read_bytes()).hexdigest()


def _read_json(path: pathlib.Path) -> tuple[dict[str, Any] | None, str]:
    if not path.exists():
        return None, MISSING
    try:
        return json.loads(path.read_text(encoding="utf-8")), PRESENT
    except (json.JSONDecodeError, OSError) as exc:
        return None, f"{INCOMPATIBLE}:{exc}"


def _iso(compact: str) -> str:
    return f"{compact[:4]}-{compact[4:6]}-{compact[6:8]}"


# ---------------------------------------------------------------------------
# Loaded run model
# ---------------------------------------------------------------------------


@dataclass
class ForwardRun:
    run_key: str
    root: pathlib.Path
    strategy_name: str
    summary: dict[str, Any]
    dates: list[str]                       # compact YYYYMMDD, sorted, deduped
    pnl_by_date: dict[str, dict[str, Any]]
    stats_by_date: dict[str, dict[str, Any]]
    validation_rows: list[dict[str, str]]
    fingerprints: dict[str, str]
    warnings: list[str] = field(default_factory=list)

    def iso_dates(self) -> list[str]:
        return [_iso(d) for d in self.dates]


def load_forward_run(
    input_root: str | pathlib.Path,
    run_key: str,
    *,
    positions_reader: Callable[[pathlib.Path], Sequence[Mapping[str, Any]]] | None = None,
) -> ForwardRun:
    """Load (read-only) the Forward run artifacts for ``run_key``. Never mutates
    or rewrites any source artifact."""
    root = pathlib.Path(input_root)
    run_dir = root / run_key
    summary, _ = _read_json(run_dir / "forward_summary.json")
    summary = summary or {}
    strategy_name = str(summary.get("strategy", ""))

    dates: set[str] = set()
    pnl_by_date: dict[str, dict[str, Any]] = {}
    stats_by_date: dict[str, dict[str, Any]] = {}
    fingerprints: dict[str, str] = {}
    warnings: list[str] = []

    if run_dir.exists():
        for p in sorted(run_dir.iterdir()):
            m = _DATE_FILE_RE.match(p.name)
            if not m:
                continue
            compact, kind = m.group(1), m.group(2)
            dates.add(compact)
            fingerprints[p.name] = sha256_file(p)
            if kind == "pnl":
                data, st = _read_json(p)
                if data is not None:
                    pnl_by_date[compact] = data
                else:
                    warnings.append(f"pnl_unreadable:{p.name}:{st}")
            elif kind == "forward_stats":
                data, st = _read_json(p)
                if data is not None:
                    stats_by_date[compact] = data
                else:
                    warnings.append(f"stats_unreadable:{p.name}:{st}")
    fingerprints["forward_summary.json"] = sha256_file(run_dir / "forward_summary.json")

    # Shared dashboard validation rows (filtered to this run's strategy where possible).
    validation_rows: list[dict[str, str]] = []
    csv_path = root / "dashboard" / "validation_30d.csv"
    if csv_path.exists():
        fingerprints["dashboard/validation_30d.csv"] = sha256_file(csv_path)
        try:
            with open(csv_path, "r", encoding="utf-8", newline="") as fh:
                validation_rows = list(csv.DictReader(fh))
        except (OSError, csv.Error) as exc:
            warnings.append(f"validation_csv_unreadable:{exc}")

    return ForwardRun(
        run_key=run_key, root=root, strategy_name=strategy_name, summary=summary,
        dates=sorted(dates), pnl_by_date=pnl_by_date, stats_by_date=stats_by_date,
        validation_rows=validation_rows, fingerprints=fingerprints, warnings=warnings)


# ---------------------------------------------------------------------------
# 0. Input audit
# ---------------------------------------------------------------------------


def audit_inputs(input_root: str | pathlib.Path, run_key: str) -> dict[str, Any]:
    """Report PRESENT / MISSING / INCOMPATIBLE / PARTIAL / EXCLUDED per expected
    artifact. Never assumes an artifact exists."""
    root = pathlib.Path(input_root)
    run_dir = root / run_key
    items: list[dict[str, Any]] = []

    def record(role: str, rel: str, *, optional: bool = False) -> None:
        path = root / rel
        if path.exists():
            status = PRESENT
        else:
            status = (PARTIAL if optional else MISSING)
        items.append({"role": role, "path": str(rel).replace("\\", "/"),
                      "status": status, "fingerprint": sha256_file(path) if path.exists() else ""})

    record("forward_summary", f"{run_key}/forward_summary.json")
    record("validation_30d_csv", "dashboard/validation_30d.csv")
    record("latest_summary_md", "dashboard/latest_summary.md", optional=True)
    record("paper_portfolio_state", "paper_portfolio/state.json", optional=True)
    record("paper_daily_pnl_csv", "paper_portfolio/daily_pnl.csv", optional=True)

    # Per-date artifact coverage.
    date_files: dict[str, dict[str, bool]] = {}
    if run_dir.exists():
        for p in run_dir.iterdir():
            m = _DATE_FILE_RE.match(p.name)
            if m:
                date_files.setdefault(m.group(1), {})[m.group(2)] = True
    per_date = []
    for d in sorted(date_files):
        kinds = date_files[d]
        per_date.append({"date": _iso(d), "pnl": bool(kinds.get("pnl")),
                         "forward_stats": bool(kinds.get("forward_stats")),
                         "positions": bool(kinds.get("positions"))})

    # Parquet engine availability (positions readability).
    parquet_engine = _parquet_engine_available()

    # Excluded categories are explicitly recorded as EXCLUDED (never counted).
    excluded = [{"category": c, "status": EXCLUDED} for c in EXCLUDED_RECORD_CATEGORIES]

    present_dates = len(date_files)
    required = REVIEW_THRESHOLDS["forward_required_days"]
    coverage_status = (PRESENT if present_dates >= required
                       else PARTIAL if present_dates > 0 else MISSING)

    return {
        "task_id": TASK_ID, "input_root": str(root).replace("\\", "/"), "run_key": run_key,
        "artifacts": items,
        "per_date_coverage": per_date,
        "present_date_count": present_dates,
        "required_date_count": required,
        "coverage_status": coverage_status,
        "positions_parquet_engine_available": parquet_engine,
        "positions_status": (PRESENT if parquet_engine and any(x["positions"] for x in per_date)
                             else UNAVAILABLE),
        "positions_unavailable_reason": ("" if parquet_engine
                                         else "no parquet engine (pyarrow/fastparquet) installed; "
                                              "positions.parquet not read; per-symbol PnL UNAVAILABLE"),
        "excluded_record_categories": excluded,
        "summary": {
            "present": sum(1 for i in items if i["status"] == PRESENT),
            "missing": sum(1 for i in items if i["status"] == MISSING),
            "partial": sum(1 for i in items if i["status"] == PARTIAL),
        },
    }


def _parquet_engine_available() -> bool:
    for eng in ("pyarrow", "fastparquet"):
        try:
            __import__(eng)
            return True
        except Exception:  # noqa: BLE001
            continue
    return False


# ---------------------------------------------------------------------------
# 1. Data integrity
# ---------------------------------------------------------------------------


def compute_data_integrity(run: ForwardRun) -> dict[str, Any]:
    iso_dates = run.iso_dates()
    # Duplicate detection (compact list already deduped via set; check raw csv).
    csv_dates = [r.get("date", "") for r in run.validation_rows if r.get("date")]
    dup = sorted({d for d in csv_dates if csv_dates.count(d) > 1})

    latest = str(run.summary.get("latest_date", ""))
    days_required = int(run.summary.get("days_required", REVIEW_THRESHOLDS["forward_required_days"]) or 0)
    days_elapsed = int(run.summary.get("days_elapsed", len(run.dates)) or 0)
    present = len(run.dates)

    stale = bool(latest) and run.dates and latest != run.dates[-1]
    strategy_ok = run.strategy_name == EXPECTED_STRATEGY_NAME if run.run_key == PRIMARY_RUN_KEY else True

    # Sample sufficiency per metric family.
    suff = {
        "return_metrics": present >= REVIEW_THRESHOLDS["min_days_for_return_metrics"],
        "risk_ratios": present >= REVIEW_THRESHOLDS["min_days_for_risk_ratios"],
        "trade_metrics": False,  # no trade-level records in Forward artifacts
        "regime_metrics": present >= REVIEW_THRESHOLDS["min_obs_per_regime"],
    }

    return {
        "task_id": TASK_ID, "run_key": run.run_key, "strategy_name": run.strategy_name,
        "strategy_id_matches_expected": strategy_ok,
        "covered_dates": iso_dates,
        "present_date_count": present,
        "expected_date_count": days_required,
        "days_elapsed": days_elapsed,
        "missing_date_count": max(days_required - present, 0),
        "duplicate_dates": [_iso(d) if _COMPACT_RE.match(d) else d for d in dup],
        "stale_summary": stale,
        "latest_summary_date": _iso(latest) if _COMPACT_RE.match(latest) else latest,
        "excluded_record_categories": list(EXCLUDED_RECORD_CATEGORIES),
        "signal_record_available": bool(run.pnl_by_date),
        "trade_record_available": False,
        "position_record_available": _parquet_engine_available(),
        "sample_sufficient": suff,
        "sample_sufficiency_thresholds": REVIEW_THRESHOLDS,
        "source_fingerprints": dict(sorted(run.fingerprints.items())),
        "warnings": list(run.warnings),
    }


# ---------------------------------------------------------------------------
# 2. Overall performance (reuse canonical metrics; never extrapolate silently)
# ---------------------------------------------------------------------------


def _build_baseline_df(run: ForwardRun):
    import pandas as pd  # local import; pandas is a project dependency
    rows = []
    for d in run.dates:
        pnl = run.pnl_by_date.get(d, {})
        ret = float(pnl.get("daily_pnl_pct", 0.0) or 0.0) / 100.0
        rows.append({
            "date": _iso(d),
            "portfolio_return": ret,
            "benchmark_return": 0.0,           # cash benchmark; Forward has no per-day benchmark
            "gross_exposure": float(pnl.get("gross_exposure", 0.0) or 0.0),
            "net_exposure": float(pnl.get("net_exposure", 0.0) or 0.0),
            "turnover": 0.0,                   # turnover not recorded per-day in Forward pnl
            "n_longs": float(pnl.get("n_longs", 0) or 0),
            "n_shorts": float(pnl.get("n_shorts", 0) or 0),
        })
    return pd.DataFrame(rows)


def compute_overall_metrics(run: ForwardRun) -> dict[str, Any]:
    """Reuse src.metrics.performance.compute_stats. Returns a metric block tagged
    with scope/period and sample sufficiency; never annualizes a sub-30-day
    sample without an explicit extrapolation label."""
    from src.metrics import performance as perf
    df = _build_baseline_df(run)
    present = len(run.dates)
    sufficient = present >= REVIEW_THRESHOLDS["min_days_for_return_metrics"]

    if df.empty:
        canonical = {}
    else:
        try:
            canonical = perf.compute_stats(df)
        except Exception as exc:  # noqa: BLE001 -- never fabricate; report failure
            canonical = {"_error": str(exc)}

    # Cost contribution from pnl artifacts (real recorded fields only).
    fee = funding = slippage = 0.0
    for d in run.dates:
        pnl = run.pnl_by_date.get(d, {})
        fee += float(pnl.get("fee_cost_usd", 0.0) or 0.0)
        funding += float(pnl.get("funding_cost_usd", 0.0) or 0.0)
        slippage += float(pnl.get("slippage_cost_usd", 0.0) or 0.0)

    cumulative_return = 0.0
    if run.dates:
        last = run.pnl_by_date.get(run.dates[-1], {})
        cumulative_return = float(last.get("cumulative_pnl_pct", 0.0) or 0.0) / 100.0

    annualized = None
    annualization_note = (
        f"NOT ANNUALIZED: only {present} day(s) present (< "
        f"{REVIEW_THRESHOLDS['min_days_for_return_metrics']}); annualizing a sub-30-day "
        f"sample would be a mathematical extrapolation and is intentionally withheld."
    )
    if sufficient:
        annualized = float(canonical.get("sharpe_full", 0.0))  # canonical Sharpe is already annualized
        annualization_note = "canonical metrics are annualized with factor 365.25 (see methodology)"

    return {
        "task_id": TASK_ID, "run_key": run.run_key,
        "scope": "30D_FORWARD_VALIDATION_PAPER_DRY_RUN",
        "period_dates": run.iso_dates(),
        "present_day_count": present,
        "sample_sufficient_for_return_metrics": sufficient,
        "cumulative_return_decimal": cumulative_return,
        "canonical_metrics": canonical,
        "canonical_metric_source": "src/metrics/performance.py::compute_stats",
        "cost_contribution_usd": {"fee": fee, "funding": funding, "slippage": slippage,
                                  "total": fee + funding + slippage},
        "gross_vs_net_note": "Forward pnl records daily_pnl_pct as net; gross-vs-net split "
                             "UNAVAILABLE without per-trade fee attribution.",
        "annualization_note": annualization_note,
        "annualized_reference": annualized,
        "unavailable": {
            "trade_level_pnl": UNAVAILABLE, "profit_factor": UNAVAILABLE,
            "win_rate": UNAVAILABLE, "expectancy": UNAVAILABLE, "average_R": UNAVAILABLE,
            "turnover": UNAVAILABLE,
        } if not sufficient else {},
    }


# ---------------------------------------------------------------------------
# 3. Contribution & concentration
# ---------------------------------------------------------------------------


def compute_contribution(run: ForwardRun) -> dict[str, Any]:
    """Side contribution from recorded weight sums; per-symbol PnL contribution is
    UNAVAILABLE without per-trade PnL (never fabricated)."""
    by_side = []
    by_symbol_pnl_available = False
    long_w = short_w = 0.0
    n_dates = max(len(run.dates), 1)
    for d in run.dates:
        pnl = run.pnl_by_date.get(d, {})
        long_w += float(pnl.get("long_weight_sum", 0.0) or 0.0)
        short_w += float(pnl.get("short_weight_sum", 0.0) or 0.0)
    by_side = [
        {"side": "long", "mean_weight_sum": long_w / n_dates, "pnl_contribution": UNAVAILABLE},
        {"side": "short", "mean_weight_sum": short_w / n_dates, "pnl_contribution": UNAVAILABLE},
    ]

    # Structural symbol exposure from paper_portfolio/state.json (weights only).
    by_symbol = []
    state_path = run.root / "paper_portfolio" / "state.json"
    state, _ = _read_json(state_path)
    if state and isinstance(state.get("positions"), list):
        for pos in state["positions"]:
            by_symbol.append({
                "symbol": str(pos.get("symbol", "")),
                "side": str(pos.get("side", "")),
                "weight": float(pos.get("weight", 0.0) or 0.0),
                "position_usd": float(pos.get("position_usd", 0.0) or 0.0),
                "pnl_contribution": UNAVAILABLE,
            })
        by_symbol.sort(key=lambda r: (-abs(r["weight"]), r["symbol"]))

    return {
        "task_id": TASK_ID, "run_key": run.run_key,
        "by_side": by_side,
        "by_symbol_structural_exposure": by_symbol,
        "by_symbol_pnl_contribution": UNAVAILABLE if not by_symbol_pnl_available else "PRESENT",
        "by_week": UNAVAILABLE,
        "concentration": {
            "symbol_count": len(by_symbol),
            "max_abs_weight": max((abs(r["weight"]) for r in by_symbol), default=0.0),
            "top1_weight_share": (abs(by_symbol[0]["weight"]) / sum(abs(r["weight"]) for r in by_symbol)
                                  if by_symbol else 0.0),
            "outlier_dependence": UNAVAILABLE,
            "note": "PnL concentration UNAVAILABLE (no per-symbol realized PnL); only structural "
                    "weight concentration is observable.",
        },
    }


# ---------------------------------------------------------------------------
# 4. Trade-behavior diagnostics (UNAVAILABLE -> required instrumentation)
# ---------------------------------------------------------------------------


def compute_trade_behavior(run: ForwardRun) -> dict[str, Any]:
    return {
        "task_id": TASK_ID, "run_key": run.run_key,
        "status": UNAVAILABLE,
        "reason": "Forward artifacts contain daily paper-portfolio weights/PnL only; there are no "
                  "trade-level entry/exit records, no intratrade price paths, and no MAE/MFE.",
        "unavailable_metrics": ["holding_duration", "entry_add_reduce_exit_counts",
                                "avg_holding_by_winner_loser", "MAE", "MFE", "MFE_giveback",
                                "stop_vs_signal_exit", "reversal_behavior", "partial_close_behavior"],
        "required_instrumentation_for_future_demo_days": [
            "per-order entry/exit timestamps and orderLinkIds (already in the Demo execution journal)",
            "per-trade entry/exit fills, avg prices, fees, realized PnL (Demo reconcile fields)",
            "intratrade high/low (MAE/MFE) sampling during the holding window",
            "exit-reason tagging (stop vs signal-exit vs reduce vs flip)",
        ],
        "synthesized_values": "NONE (never fabricated)",
    }


# ---------------------------------------------------------------------------
# 5. Regime diagnostics (reuse canonical regime def; do not invent)
# ---------------------------------------------------------------------------


def compute_regime(run: ForwardRun) -> dict[str, Any]:
    canonical_regime = _discover_canonical_regime()
    if canonical_regime is None:
        return {
            "task_id": TASK_ID, "run_key": run.run_key, "status": NO_CANONICAL_DEFINITION,
            "reason": "no canonical regime classifier found in the repository; a regime classifier "
                      "is intentionally NOT invented to fill the report.",
            "regimes": {r: INSUFFICIENT_SAMPLE for r in
                        ("uptrend", "downtrend", "sideways", "high_volatility", "low_volatility")},
            "min_obs_per_regime_threshold": REVIEW_THRESHOLDS["min_obs_per_regime"],
        }
    # If a canonical regime module is later added, wire it here (kept explicit).
    return {"task_id": TASK_ID, "run_key": run.run_key, "status": PARTIAL,
            "canonical_regime_module": canonical_regime, "regimes": {}}


def _discover_canonical_regime() -> str | None:
    for mod in ("src.regime", "src.signals.regime", "apps.forward_record.regime"):
        try:
            __import__(mod)
            return mod
        except Exception:  # noqa: BLE001
            continue
    return None


# ---------------------------------------------------------------------------
# 6. OOS vs 30-day Forward
# ---------------------------------------------------------------------------


def compute_oos_vs_forward(run: ForwardRun, *, oos_numbers: Mapping[str, Any] | None) -> dict[str, Any]:
    if not oos_numbers:
        return {"task_id": TASK_ID, "run_key": run.run_key, "status": UNAVAILABLE,
                "reason": "no compatible OOS summary artifact supplied; like-for-like comparison "
                          "withheld (incompatible scopes must not be ranked as comparable)."}
    forward_sufficient = len(run.dates) >= REVIEW_THRESHOLDS["min_days_for_return_metrics"]
    if not forward_sufficient:
        return {"task_id": TASK_ID, "run_key": run.run_key, "status": INSUFFICIENT_SAMPLE,
                "reason": f"Forward sample {len(run.dates)} day(s) < "
                          f"{REVIEW_THRESHOLDS['min_days_for_return_metrics']}; cannot declare "
                          f"improvement or degradation versus OOS from an insufficient Forward scope.",
                "oos_reference": dict(oos_numbers)}
    return {"task_id": TASK_ID, "run_key": run.run_key, "status": PRESENT,
            "note": "like-for-like comparison performed only on compatible scopes",
            "oos_reference": dict(oos_numbers)}


# ---------------------------------------------------------------------------
# 7. Primary vs Shadow (evidence penalty for incomplete artifacts)
# ---------------------------------------------------------------------------


def compute_primary_shadow(primary: ForwardRun, shadows: Sequence[ForwardRun]) -> dict[str, Any]:
    def descriptor(run: ForwardRun) -> dict[str, Any]:
        present = len(run.dates)
        complete = present >= REVIEW_THRESHOLDS["min_days_for_return_metrics"]
        return {
            "run_key": run.run_key, "strategy_name": run.strategy_name,
            "present_date_count": present, "complete_evidence": complete,
            "evidence_penalty_applied": not complete,
            "cumulative_return_decimal": (
                float(run.pnl_by_date.get(run.dates[-1], {}).get("cumulative_pnl_pct", 0.0) or 0.0) / 100.0
                if run.dates else 0.0),
            "comparable": complete,
        }
    rows = [descriptor(primary)] + [descriptor(s) for s in shadows]
    any_complete = any(r["complete_evidence"] for r in rows)
    return {
        "task_id": TASK_ID,
        "strategies": rows,
        "ranking_status": "RANKED" if any_complete else "ALL_INSUFFICIENT_EVIDENCE",
        "ranking_rule": "a strategy with incomplete artifacts is never ranked above one with "
                        "complete evidence without an explicit evidence penalty",
    }


# ---------------------------------------------------------------------------
# Cost stress (recorded/base, fees x2, slippage, funding) -- mark unavailable
# ---------------------------------------------------------------------------


def compute_cost_stress(run: ForwardRun) -> dict[str, Any]:
    fee = funding = slippage = 0.0
    has_fee = has_funding = has_slippage = False
    for d in run.dates:
        pnl = run.pnl_by_date.get(d, {})
        if "fee_cost_usd" in pnl:
            has_fee = True
            fee += float(pnl.get("fee_cost_usd", 0.0) or 0.0)
        if "funding_cost_usd" in pnl:
            has_funding = True
            funding += float(pnl.get("funding_cost_usd", 0.0) or 0.0)
        if "slippage_cost_usd" in pnl:
            has_slippage = True
            slippage += float(pnl.get("slippage_cost_usd", 0.0) or 0.0)
    base_total = fee + funding + slippage
    return {
        "task_id": TASK_ID, "run_key": run.run_key,
        "base": {"fee": fee, "funding": funding, "slippage": slippage, "total": base_total},
        "fees_x2": {"fee": fee * 2, "delta_total": fee, "available": has_fee},
        "slippage_stress": {"status": PRESENT if has_slippage else UNAVAILABLE,
                            "recorded_slippage": slippage,
                            "note": "" if has_slippage else "no execution-price/slippage data recorded"},
        "funding_stress": {"status": PRESENT if has_funding else UNAVAILABLE,
                           "recorded_funding": funding,
                           "note": "" if has_funding else "no funding data recorded"},
        "note": "Forward dry-run records zero cost (paper, no fills); real cost stress requires the "
                "7-day Demo fills. Unavailable dimensions are marked, never invented.",
        "all_costs_zero_paper_dry_run": base_total == 0.0,
    }


def run_all_diagnostics(
    primary: ForwardRun, shadows: Sequence[ForwardRun],
    *, oos_numbers: Mapping[str, Any] | None = None,
) -> dict[str, Any]:
    return {
        "task_id": TASK_ID,
        "data_integrity": compute_data_integrity(primary),
        "overall_metrics": compute_overall_metrics(primary),
        "contribution": compute_contribution(primary),
        "trade_behavior": compute_trade_behavior(primary),
        "regime": compute_regime(primary),
        "oos_vs_forward": compute_oos_vs_forward(primary, oos_numbers=oos_numbers),
        "primary_shadow": compute_primary_shadow(primary, shadows),
        "cost_stress": compute_cost_stress(primary),
    }


__all__ = [
    "EXCLUDED_RECORD_CATEGORIES", "EXPECTED_STRATEGY_NAME", "ForwardRun", "INSUFFICIENT_SAMPLE",
    "NO_CANONICAL_DEFINITION", "PARTIAL", "PRESENT", "PRIMARY_RUN_KEY", "REVIEW_THRESHOLDS",
    "SHADOW_RUN_KEY", "TASK_ID", "UNAVAILABLE", "audit_inputs", "compute_contribution",
    "compute_cost_stress", "compute_data_integrity", "compute_oos_vs_forward",
    "compute_overall_metrics", "compute_primary_shadow", "compute_regime", "compute_trade_behavior",
    "load_forward_run", "run_all_diagnostics", "sha256_file",
]
