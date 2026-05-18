from __future__ import annotations

import argparse
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

from apps.paper_trading.config import PaperTradingConfig
from apps.paper_trading.monitor_hook import PaperTradingMonitorHook
from apps.paper_trading.recorder import (
    SIMULATED_FILL_COLUMNS,
    build_intended_fills,
    write_simulated_fills,
    write_target_positions,
)
from apps.paper_trading.risk import evaluate_kill_switches, evaluate_monthly_review_gates
from apps.paper_trading.sizing import SizingResult, build_target_positions
from apps.paper_trading.validator import build_daily_pnl_from_task007, evaluate_forward_validation
from src.attribution.reproducibility import build_input_hashes, canonical_hash, git_commit


FUNDING_FILTER_RULE = "funding_filter_0.03pct_8h"


@dataclass(frozen=True)
class Task006Result:
    sizing: SizingResult
    fills: pd.DataFrame
    daily_pnl: pd.DataFrame
    monthly_review: dict[str, Any]
    risk_events: list[dict[str, Any]]
    forward_validation: dict[str, Any]
    review_numbers: dict[str, Any]
    review_packet: str
    log_text: str


def run_task006(config: PaperTradingConfig) -> Task006Result:
    positions = pd.read_parquet(config.positions_path)
    baseline = pd.read_csv(config.baseline_path)
    funding = pd.read_parquet(config.funding_path)
    prices = pd.read_parquet(config.prices_path)
    task007_daily = pd.read_csv(config.task007_daily_path)
    task007_summary = pd.read_csv(config.task007_summary_path)
    review007_numbers = json.loads(config.review007_numbers_path.read_text(encoding="utf-8"))

    sizing = build_target_positions(positions, funding, config, as_of_date=_latest_rebalance_date(baseline))
    fills = build_intended_fills(sizing.positions, positions, prices, config)
    daily_pnl = build_daily_pnl_from_task007(
        task007_daily,
        config.initial_nav_usd,
        config.primary_variant,
        config.secondary_variant,
    )
    forward_validation = evaluate_forward_validation(
        daily_pnl,
        config.forward_validation_days,
        config.annualization_factor,
    )
    monthly_review = _monthly_review(daily_pnl, sizing, fills, forward_validation, config)
    risk_events = _risk_events(daily_pnl, monthly_review, sizing, config)
    safety_scan = validate_no_external_execution_paths([Path("apps/paper_trading")])
    if safety_scan["violations"]:
        raise RuntimeError(f"NEED_CLARIFICATION: forbidden execution path text found: {safety_scan['violations']}")
    review_numbers = _review_numbers(
        sizing,
        fills,
        daily_pnl,
        monthly_review,
        risk_events,
        forward_validation,
        task007_summary,
        review007_numbers,
        safety_scan,
        config,
    )
    review_packet = _review_packet(review_numbers, config)
    log_text = _log_text(review_numbers, config)
    return Task006Result(
        sizing=sizing,
        fills=fills,
        daily_pnl=daily_pnl,
        monthly_review=monthly_review,
        risk_events=risk_events,
        forward_validation=forward_validation,
        review_numbers=review_numbers,
        review_packet=review_packet,
        log_text=log_text,
    )


def write_task006_outputs(result: Task006Result, config: PaperTradingConfig) -> tuple[dict[str, Path], list[str]]:
    config.output_dir.mkdir(parents=True, exist_ok=True)
    config.log_dir.mkdir(parents=True, exist_ok=True)
    config.review_packet_path.parent.mkdir(parents=True, exist_ok=True)
    paths = {
        "target_positions": config.output_dir / f"{config.output_date}_target_positions.json",
        "simulated_fills": config.output_dir / f"{config.output_date}_simulated_fills.csv",
        "daily_pnl": config.output_dir / f"{config.output_date}_daily_pnl.csv",
        "monthly_review": config.output_dir / f"{config.output_date}_monthly_review.json",
        "risk_events": config.output_dir / f"{config.output_date}_risk_events.jsonl",
        "forward_validation": config.output_dir / f"{config.output_date}_forward_validation.json",
        "log": config.log_dir / f"{config.output_date}_paper_trading_setup.log",
        "review_packet": config.review_packet_path,
        "review_numbers": config.review_numbers_path,
    }
    write_target_positions(paths["target_positions"], result.sizing.payload)
    write_simulated_fills(paths["simulated_fills"], result.fills)
    result.daily_pnl.to_csv(paths["daily_pnl"], index=False)
    paths["monthly_review"].write_text(
        json.dumps(result.monthly_review, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["risk_events"].write_text(
        "".join(json.dumps(event, sort_keys=True, ensure_ascii=False) + "\n" for event in result.risk_events),
        encoding="utf-8",
    )
    paths["forward_validation"].write_text(
        json.dumps(result.forward_validation, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    paths["log"].write_text(result.log_text, encoding="utf-8")
    paths["review_packet"].write_text(result.review_packet, encoding="utf-8")
    paths["review_numbers"].write_text(
        json.dumps(result.review_numbers, indent=2, sort_keys=True, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )
    return paths, validate_outputs(paths, result, config)


def validate_no_external_execution_paths(roots: list[Path]) -> dict[str, Any]:
    forbidden = [
        "place" + "_order",
        "submit" + "_order",
        "create" + "_order",
        "/v5/" + "order",
        "api" + "_key",
        "api" + "_secret",
        "secret" + "_key",
    ]
    violations = []
    for root in roots:
        if not root.exists():
            continue
        for path in root.rglob("*"):
            if path.suffix not in {".py", ".md"}:
                continue
            text = path.read_text(encoding="utf-8")
            for token in forbidden:
                if token in text:
                    violations.append({"path": str(path), "token": token})
    return {"status": "PASS" if not violations else "FAIL", "violations": violations}


def validate_outputs(paths: dict[str, Path], result: Task006Result, config: PaperTradingConfig) -> list[str]:
    errors = [f"missing output {name}: {path}" for name, path in paths.items() if not path.exists()]
    missing_fill_cols = set(SIMULATED_FILL_COLUMNS) - set(result.fills.columns)
    if missing_fill_cols:
        errors.append(f"simulated_fills missing columns: {sorted(missing_fill_cols)}")
    if result.daily_pnl.empty:
        errors.append("daily_pnl is empty")
    max_weight = result.sizing.positions["weight"].abs().max()
    if float(max_weight) > config.symbol_cap_abs_weight + 1e-12:
        errors.append(f"symbol_cap_5pct violation: {max_weight}")
    if result.review_numbers["safety_scan"]["status"] != "PASS":
        errors.append("safety scan failed")
    return errors


def _monthly_review(
    daily_pnl: pd.DataFrame,
    sizing: SizingResult,
    fills: pd.DataFrame,
    forward_validation: dict[str, Any],
    config: PaperTradingConfig,
) -> dict[str, Any]:
    funding_filter_event_count = sum(
        1 for event in sizing.events if str(event.get("rule", "")) == FUNDING_FILTER_RULE
    )
    funding_filter_active = funding_filter_event_count > 0
    metrics = {
        "paper_sharpe": float(forward_validation.get("paper_sharpe", 0.0)),
        "max_drawdown": float(forward_validation.get("max_drawdown", 0.0)),
        "tracking_error_monthly": float(forward_validation.get("tracking_error_monthly", 0.0)),
    }
    return {
        "date": sizing.payload["date"],
        "variant": config.primary_variant,
        "review_basis": "offline historical simulation proxy; no paper execution started",
        "metrics": metrics,
        "portfolio_summary": sizing.payload["portfolio_summary"],
        "intended_fill_count": int(len(fills)),
        "fill_definition": _fill_definition(int(len(fills))),
        "funding_filter_active_this_month": funding_filter_active,
        "funding_filter_event_count_this_month": int(funding_filter_event_count),
        "funding_filter_activity_note": (
            "Funding filter is regime-dependent; false means no symbol breached "
            "the configured 30-day average funding threshold in this monthly setup."
        ),
        "forward_validation": forward_validation,
        "mandatory_caveats": config.mandatory_caveats,
        "paper_execution_status": "FORBIDDEN_UNTIL_GATES_PASS",
        "live_trading_status": "FORBIDDEN",
    }


def _risk_events(
    daily_pnl: pd.DataFrame,
    monthly_review: dict[str, Any],
    sizing: SizingResult,
    config: PaperTradingConfig,
) -> list[dict[str, Any]]:
    events = []
    events.extend(evaluate_kill_switches(daily_pnl.tail(30)))
    events.extend(evaluate_monthly_review_gates(monthly_review["metrics"]))
    events.extend({
        "event_type": "OVERLAY_RULE_APPLIED",
        "severity": "INFO",
        "action": "local_record_only",
        "details": event,
    } for event in sizing.events)
    hook = PaperTradingMonitorHook()
    events.append(hook.push_rebalance_summary(
        sizing.payload["date"],
        sizing.payload["portfolio_summary"]["n_longs"],
        sizing.payload["portfolio_summary"]["n_shorts"],
        sizing.payload["portfolio_summary"]["gross_exposure_pct"],
        sizing.payload["portfolio_summary"]["net_exposure_pct"],
    ))
    return events


def _review_numbers(
    sizing: SizingResult,
    fills: pd.DataFrame,
    daily_pnl: pd.DataFrame,
    monthly_review: dict[str, Any],
    risk_events: list[dict[str, Any]],
    forward_validation: dict[str, Any],
    task007_summary: pd.DataFrame,
    review007_numbers: dict[str, Any],
    safety_scan: dict[str, Any],
    config: PaperTradingConfig,
) -> dict[str, Any]:
    primary = task007_summary[task007_summary["variant"].astype(str).eq(config.primary_variant)].to_dict(orient="records")
    secondary = task007_summary[task007_summary["variant"].astype(str).eq(config.secondary_variant)].to_dict(orient="records")
    output_basis = {
        "analysis_basis": "TASK-006 offline planning/simulation/logging only",
        "paper_execution_status": "NOT_STARTED",
        "paper_execution_approval": False,
        "live_trading_status": "FORBIDDEN",
        "real_order_submission_possible": False,
    }
    payload = {
        **output_basis,
        "run_date": config.output_date,
        "target_date": sizing.payload["date"],
        "primary_variant": config.primary_variant,
        "secondary_variant": config.secondary_variant,
        "primary_task007_summary": primary[0] if primary else {},
        "secondary_task007_summary": secondary[0] if secondary else {},
        "review007_reproducibility_hash": review007_numbers.get("reproducibility_hash"),
        "portfolio_summary": sizing.payload["portfolio_summary"],
        "overlay_event_count": int(len(sizing.events)),
        "intended_fill_count": int(len(fills)),
        "fill_definition": _fill_definition(int(len(fills))),
        "funding_filter_active_this_month": bool(monthly_review.get("funding_filter_active_this_month", False)),
        "daily_pnl_rows": int(len(daily_pnl)),
        "monthly_review": monthly_review,
        "risk_event_counts": _event_counts(risk_events),
        "forward_validation": forward_validation,
        "safety_scan": safety_scan,
        "input_hashes": build_input_hashes(config.input_paths()),
        "git_commit": git_commit(),
    }
    payload["reproducibility_hash"] = canonical_hash({
        "payload_without_hash": payload,
        "target_positions": sizing.payload,
        "fills": fills.to_dict(orient="records"),
    })
    return payload


def _review_packet(numbers: dict[str, Any], config: PaperTradingConfig) -> str:
    primary = numbers["primary_task007_summary"]
    secondary = numbers["secondary_task007_summary"]
    warnings = numbers["risk_event_counts"].get("WARNING", 0)
    kill_switches = numbers["risk_event_counts"].get("KILL_SWITCH", 0)
    proxy_sharpe = numbers["forward_validation"].get("proxy_sharpe_long_window", {})
    short_window = proxy_sharpe.get("short_window", {})
    window_90d = proxy_sharpe.get("window_90d", {})
    full_window = proxy_sharpe.get("full_active_window", {})
    funding_active = bool(numbers["monthly_review"].get("funding_filter_active_this_month", False))
    return "\n".join([
        "# REVIEW-006 Packet - TASK-006 Paper Trading Planning Modules",
        "",
        "Analysis basis: offline planning, simulation, and logging only.",
        "No paper trading execution or live trading approval is implied.",
        "",
        "## Scope",
        "- Implemented local modules under `apps/paper_trading/`.",
        "- Outputs are local JSON/CSV/JSONL/Markdown/log files only.",
        "- External execution is unsupported by design.",
        "",
        "## Variant Specs",
        f"- Primary: `{config.primary_variant}` Sharpe={float(primary.get('sharpe_active', 0.0)):.4f}, "
        f"Max DD={float(primary.get('max_dd', 0.0)):.2%}, Net Alpha={float(primary.get('net_alpha', 0.0)):.2%}.",
        f"- Secondary tracking: `{config.secondary_variant}` Sharpe={float(secondary.get('sharpe_active', 0.0)):.4f}, "
        f"Max DD={float(secondary.get('max_dd', 0.0)):.2%}, Net Alpha={float(secondary.get('net_alpha', 0.0)):.2%}.",
        "",
        "## Mandatory Overlays",
        "- funding_filter_0.03pct_8h: long weight set to zero when 30-day average funding exceeds 0.03% per 8h.",
        "- long_cap_50pct: long gross capped to 50% of gross exposure.",
        "- symbol_cap_5pct: any symbol absolute weight capped at 5%, no redistribution.",
        "",
        "## Output Summary",
        f"- Target date: {numbers['target_date']}",
        f"- Intended fills: {numbers['intended_fill_count']}",
        f"- Daily PnL rows: {numbers['daily_pnl_rows']}",
        f"- Overlay events: {numbers['overlay_event_count']}",
        f"- Risk warnings: {warnings}; kill switches: {kill_switches}",
        "",
        "## Forward Validation",
        f"- Status: {numbers['forward_validation']['forward_validation_status']}",
        f"- Basis: {numbers['forward_validation']['validation_basis']}",
        f"- Pass: {numbers['forward_validation']['forward_validation_pass']}",
        f"- Blocker: {numbers['forward_validation'].get('pass_blocker', '')}",
        "",
        "## REVIEW-006b Addenda",
        f"- proxy_sharpe_long_window: 30d={_format_metric(short_window.get('annualized_sharpe'))} "
        f"(noisy short-window proxy), 90d={_format_metric(window_90d.get('annualized_sharpe'))}, "
        f"full_active_{int(full_window.get('observed_days', 0))}d={_format_metric(full_window.get('annualized_sharpe'))}.",
        "- Fill definition: `simulated_fills.csv` records nonzero `weight_delta = target_weight - prev_weight` "
        "versus the prior rebalance, not one row per held position.",
        f"- Current intended fills: {numbers['intended_fill_count']}; unchanged positions remain in "
        "`target_positions.json` and do not create fill rows.",
        f"- funding_filter_active_this_month: `{str(funding_active).lower()}`; false means the funding filter "
        "did not trigger in this monthly setup and remains regime-dependent.",
        "",
        "## Safety",
        f"- Safety scan: {numbers['safety_scan']['status']}",
        "- No exchange client, credential intake, or external execution path is implemented.",
        "- Paper execution remains blocked until TASK-007b PASS, TASK-005 online, REVIEW-006b PASS, 30 days forward validation, and Rick approval.",
        "- Live trading remains FORBIDDEN.",
        "",
        "## Reproducibility",
        f"- reproducibility_hash: `{numbers['reproducibility_hash']}`",
        f"- git_commit: `{numbers['git_commit']}`",
        f"- output_date: `{config.output_date}`",
        "",
    ]) + "\n"


def _fill_definition(intended_fill_count: int) -> dict[str, Any]:
    return {
        "basis": "position_delta_vs_prior_period",
        "formula": "weight_delta = target_weight - prev_weight",
        "description": (
            "Each simulated fill row is a nonzero target position delta versus "
            "the prior rebalance position, not one row per held position."
        ),
        "current_intended_fill_count": int(intended_fill_count),
    }


def _format_metric(value: Any) -> str:
    if value is None:
        return "n/a"
    try:
        return f"{float(value):.4f}"
    except (TypeError, ValueError):
        return "n/a"


def _log_text(numbers: dict[str, Any], config: PaperTradingConfig) -> str:
    return "\n".join([
        "TASK-006 Paper Trading Planning Modules",
        f"run_date={config.output_date}",
        "scope=offline planning/simulation/logging only",
        "paper_execution_status=NOT_STARTED",
        "live_trading_status=FORBIDDEN",
        f"primary_variant={config.primary_variant}",
        f"secondary_variant={config.secondary_variant}",
        f"git_commit={numbers['git_commit']}",
        f"reproducibility_hash={numbers['reproducibility_hash']}",
        "",
        "safety_scan:",
        json.dumps(numbers["safety_scan"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "forward_validation:",
        json.dumps(numbers["forward_validation"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
        "input_hashes:",
        json.dumps(numbers["input_hashes"], indent=2, sort_keys=True, ensure_ascii=True),
        "",
    ]) + "\n"


def _event_counts(events: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = {}
    for event in events:
        severity = str(event.get("severity", "INFO"))
        counts[severity] = counts.get(severity, 0) + 1
    return counts


def _latest_rebalance_date(baseline: pd.DataFrame) -> pd.Timestamp:
    frame = baseline.copy()
    frame["date"] = pd.to_datetime(frame["date"]).dt.normalize()
    frame["turnover"] = pd.to_numeric(frame["turnover"], errors="coerce").fillna(0.0)
    frame["gross_exposure"] = pd.to_numeric(frame["gross_exposure"], errors="coerce").fillna(0.0)
    rebalances = frame[frame["turnover"].gt(0) & frame["gross_exposure"].gt(0)]
    if rebalances.empty:
        raise ValueError("baseline has no active rebalance dates")
    return pd.Timestamp(rebalances["date"].max()).normalize()


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate TASK-006 offline paper planning outputs.")
    parser.add_argument("--output-date", default="20260516")
    args = parser.parse_args()
    config = PaperTradingConfig(output_date=args.output_date)
    result = run_task006(config)
    paths, errors = write_task006_outputs(result, config)
    payload = {
        "status": "REVIEW_READY" if not errors else "FAIL",
        "outputs": {key: str(path) for key, path in paths.items()},
        "errors": errors,
        "reproducibility_hash": result.review_numbers["reproducibility_hash"],
        "paper_execution_status": "NOT_STARTED",
        "live_trading_status": "FORBIDDEN",
    }
    print(json.dumps(payload, indent=2, sort_keys=True))
    if errors:
        raise SystemExit(2)


if __name__ == "__main__":
    main()
