from __future__ import annotations

import math
from typing import Any

import numpy as np
import pandas as pd


def build_daily_pnl_from_task007(
    task007_daily: pd.DataFrame,
    initial_nav_usd: float,
    primary_variant: str,
    secondary_variant: str,
) -> pd.DataFrame:
    primary = task007_daily[task007_daily["variant"].astype(str).eq(primary_variant)].copy()
    if primary.empty:
        raise ValueError(f"missing primary variant in TASK-007 daily output: {primary_variant}")
    secondary = task007_daily[task007_daily["variant"].astype(str).eq(secondary_variant)].copy()
    primary["date"] = pd.to_datetime(primary["date"]).dt.strftime("%Y-%m-%d")
    primary["paper_return"] = pd.to_numeric(primary["portfolio_return_net"], errors="coerce").fillna(0.0)
    primary["model_return"] = primary["paper_return"]
    primary["nav_usd"] = float(initial_nav_usd) * (1.0 + primary["paper_return"]).cumprod()
    out = primary.loc[:, [
        "date",
        "variant",
        "paper_return",
        "model_return",
        "nav_usd",
        "gross_exposure",
        "net_exposure",
        "n_longs",
        "n_shorts",
        "fee_cost",
        "slippage_cost",
        "funding_cost",
    ]].copy()
    if not secondary.empty:
        sec = secondary.loc[:, ["date", "portfolio_return_net"]].copy()
        sec["date"] = pd.to_datetime(sec["date"]).dt.strftime("%Y-%m-%d")
        sec = sec.rename(columns={"portfolio_return_net": "secondary_return"})
        out = out.merge(sec, on="date", how="left")
    else:
        out["secondary_return"] = 0.0
    return out.sort_values("date").reset_index(drop=True)


def evaluate_forward_validation(daily_pnl: pd.DataFrame, days: int = 30, annualization: float = 365.25) -> dict[str, Any]:
    full_frame = daily_pnl.copy()
    frame = full_frame.tail(int(days))
    if frame.empty:
        return {
            "forward_validation_status": "NOT_STARTED",
            "validation_basis": "no paper execution data",
            "calendar_days": 0,
            "forward_validation_pass": False,
        }
    paper = pd.to_numeric(frame["paper_return"], errors="coerce").fillna(0.0)
    model = pd.to_numeric(frame["model_return"], errors="coerce").fillna(0.0)
    nav = pd.to_numeric(frame["nav_usd"], errors="coerce")
    paper_sharpe = _annual_ratio(paper, annualization)
    proxy_sharpe = _proxy_sharpe_windows(full_frame, int(days), annualization, paper_sharpe)
    metrics = {
        "forward_validation_status": "NOT_STARTED",
        "validation_basis": "historical_simulation_proxy_not_forward_execution",
        "calendar_days": int(len(frame)),
        "paper_sharpe": paper_sharpe,
        "paper_sharpe_30d_proxy": paper_sharpe,
        "paper_sharpe_30d_window_days": int(len(frame)),
        "paper_sharpe_30d_proxy_note": "Noisy short-window historical proxy; not a forward paper record.",
        "proxy_sharpe_long_window": proxy_sharpe,
        "max_drawdown": _max_drawdown(paper),
        "tracking_error_monthly": float((paper - model).std(ddof=1) * math.sqrt(30.0)) if len(frame) > 1 else 0.0,
        "fatal_errors": 0,
        "min_nav_usd": float(nav.min()) if not nav.empty else 0.0,
        "nav_floor_ratio": float(nav.min() / nav.iloc[0]) if len(nav) else 0.0,
    }
    metrics["forward_validation_pass"] = False
    metrics["pass_blocker"] = "requires real 30-day forward paper record plus Opus REVIEW-006b and Rick approval"
    return metrics


def _proxy_sharpe_windows(
    daily_pnl: pd.DataFrame,
    short_days: int,
    annualization: float,
    short_window_sharpe: float,
) -> dict[str, Any]:
    total_days = int(len(daily_pnl))
    return {
        "basis": "historical_simulation_proxy_not_forward_execution",
        "annualization_factor": float(annualization),
        "short_window": {
            "label": f"{int(short_days)}d_proxy",
            "requested_days": int(short_days),
            "observed_days": min(total_days, int(short_days)),
            "annualized_sharpe": float(short_window_sharpe),
            "note": "Noisy short-window proxy; keep separate from real forward paper results.",
        },
        "window_90d": _proxy_sharpe_window(daily_pnl, 90, annualization),
        "full_active_window": _proxy_sharpe_window(daily_pnl, total_days, annualization),
    }


def _proxy_sharpe_window(daily_pnl: pd.DataFrame, requested_days: int, annualization: float) -> dict[str, Any]:
    requested = int(requested_days)
    observed = min(int(len(daily_pnl)), requested)
    if requested <= 0 or len(daily_pnl) < requested:
        return {
            "requested_days": requested,
            "observed_days": observed,
            "available": False,
            "annualized_sharpe": None,
        }
    frame = daily_pnl.copy().tail(requested)
    paper = pd.to_numeric(frame["paper_return"], errors="coerce").fillna(0.0)
    return {
        "requested_days": requested,
        "observed_days": int(len(frame)),
        "available": True,
        "annualized_sharpe": _annual_ratio(paper, annualization),
    }


def _annual_ratio(series: pd.Series, annualization: float) -> float:
    clean = pd.Series(series, dtype=float).replace([np.inf, -np.inf], np.nan).dropna()
    if clean.empty:
        return 0.0
    std = float(clean.std(ddof=1))
    if std == 0.0 or math.isnan(std):
        return 0.0
    return float(clean.mean() / std * math.sqrt(annualization))


def _max_drawdown(returns: pd.Series) -> float:
    clean = pd.Series(returns, dtype=float).replace([np.inf, -np.inf], np.nan).fillna(0.0)
    if clean.empty:
        return 0.0
    equity = (1.0 + clean).cumprod()
    peak = equity.cummax()
    return float((equity / peak - 1.0).min())
