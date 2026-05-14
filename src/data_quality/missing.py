"""Data-quality exclusions for the Prev3Y crypto baseline.

This module produces filtered data views for research code. It does not score
signals or choose portfolios.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import numpy as np
import pandas as pd

from src.signals.prev3y_momentum import rebalance_dates


DATA_QUALITY_SUMMARY_SCHEMA = [
    {"name": "date", "type": "datetime64[ns]", "unit": "UTC calendar date"},
    {"name": "symbol", "type": "string", "unit": "Bybit perpetual symbol"},
    {"name": "issue_type", "type": "string", "unit": "data-quality issue category"},
    {"name": "affected_field", "type": "string", "unit": "field or derived value affected"},
    {"name": "action", "type": "string", "unit": "policy action taken"},
    {"name": "source_stage", "type": "string", "unit": "price_bar/ranking/holding"},
    {"name": "reason", "type": "string", "unit": "human-readable exclusion reason"},
]

PRICE_FIELDS = ["open", "high", "low", "close"]
REQUIRED_FIELDS = ["open", "high", "low", "close", "volume", "quote_volume"]
SUMMARY_COLUMNS = [col["name"] for col in DATA_QUALITY_SUMMARY_SCHEMA]


@dataclass(frozen=True)
class DataQualityResult:
    prices: pd.DataFrame
    signal_membership: pd.DataFrame
    tradable_membership: pd.DataFrame
    events: pd.DataFrame
    holding_exclusion_reasons: dict[tuple[pd.Timestamp, str], str]


def apply_data_quality_policy(
    prices: pd.DataFrame,
    membership: pd.DataFrame,
    config: dict[str, Any],
) -> DataQualityResult:
    """Return filtered views that exclude abnormal symbol-days.

    Hard abnormal days are removed from ranking candidates, holding candidates,
    and realized return calculation. Volume equal to zero is a warning only.
    """
    clean_prices = _normalize_prices(prices)
    clean_membership = _normalize_membership(membership)
    start = pd.Timestamp(str(config["start_date"])).normalize()
    end = pd.Timestamp(str(config["end_date"])).normalize()
    entry_price = str(config["entry_price"])
    price_col = _price_column(entry_price)

    price_events, abnormal_reasons = _price_bar_events(clean_prices)
    price_view = _filtered_price_view(clean_prices, abnormal_reasons)

    true_membership = clean_membership[clean_membership["is_member"]].copy()
    in_sample_membership = true_membership[
        true_membership["date"].between(start, end)
    ].copy()
    missing_price_events = _missing_price_row_events(in_sample_membership, price_view)
    for key, reason in _event_reasons(missing_price_events).items():
        abnormal_reasons.setdefault(key, reason)

    tradable_membership, holding_events, holding_reasons = _filter_holding_candidates(
        clean_membership,
        price_view,
        abnormal_reasons,
        start,
        end,
        price_col,
    )
    signal_membership, ranking_events = _filter_ranking_candidates(
        clean_membership,
        price_view,
        abnormal_reasons,
        config,
    )

    events = combine_data_quality_events(
        [price_events, missing_price_events, holding_events, ranking_events]
    )
    return DataQualityResult(
        prices=price_view,
        signal_membership=signal_membership,
        tradable_membership=tradable_membership,
        events=events,
        holding_exclusion_reasons=holding_reasons,
    )


def forced_holding_exclusion_events(
    positions: pd.DataFrame,
    holding_exclusion_reasons: dict[tuple[pd.Timestamp, str], str],
) -> pd.DataFrame:
    """Record actual position removals caused by data-quality exclusions."""
    if positions.empty or not holding_exclusion_reasons:
        return _empty_events()

    held_by_date = _position_symbols_by_date(positions)
    rows: list[dict[str, object]] = []
    dates = pd.date_range(positions["date"].min(), positions["date"].max(), freq="D")
    previous_symbols: set[str] = set()
    for date in dates:
        current_symbols = held_by_date.get(pd.Timestamp(date).normalize(), set())
        removed = previous_symbols - current_symbols
        for symbol in sorted(removed):
            key = (pd.Timestamp(date).normalize(), symbol)
            reason = holding_exclusion_reasons.get(key)
            if reason is None:
                continue
            rows.append(_event(
                date=date,
                symbol=symbol,
                issue_type="forced_holding_exit",
                affected_field="position",
                action="forced_holding_exit",
                source_stage="holding",
                reason=f"held symbol removed before return calculation: {reason}",
            ))
        previous_symbols = current_symbols
    return _events_from_rows(rows)


def combine_data_quality_events(events: list[pd.DataFrame]) -> pd.DataFrame:
    frames = [event for event in events if event is not None and not event.empty]
    if not frames:
        return _empty_events()
    combined = pd.concat(frames, ignore_index=True)
    combined["date"] = pd.to_datetime(combined["date"]).dt.normalize()
    combined["symbol"] = combined["symbol"].astype(str)
    combined = combined.drop_duplicates(SUMMARY_COLUMNS)
    return combined.sort_values(["date", "symbol", "source_stage", "action", "issue_type"]).reset_index(drop=True)


def aggregate_data_quality_events(events: pd.DataFrame) -> dict[str, object]:
    if events.empty:
        return {
            "dq_abnormal_symbol_days": 0,
            "dq_excluded_from_ranking_candidates": 0,
            "dq_excluded_from_holding_days": 0,
            "dq_forced_holding_exits": 0,
            "dq_affected_symbols": 0,
            "issue_counts": {},
            "top_affected_symbols": [],
            "affected_date_ranges": {},
        }

    hard_actions = {"exclude_symbol_day", "exclude_from_holding_candidate"}
    abnormal = events[events["action"].isin(hard_actions)]
    non_warning = events[events["action"].ne("warn_only")]
    counts = events["issue_type"].value_counts().sort_index()
    symbol_counts = non_warning["symbol"].value_counts().head(20)
    affected_ranges: dict[str, dict[str, object]] = {}
    for symbol, group in non_warning.groupby("symbol"):
        affected_ranges[str(symbol)] = {
            "start_date": _date_str(group["date"].min()),
            "end_date": _date_str(group["date"].max()),
            "count": int(len(group)),
        }

    return {
        "dq_abnormal_symbol_days": int(abnormal[["date", "symbol"]].drop_duplicates().shape[0]),
        "dq_excluded_from_ranking_candidates": int(events["action"].eq("exclude_from_ranking_candidate").sum()),
        "dq_excluded_from_holding_days": int(events["action"].eq("exclude_from_holding_candidate").sum()),
        "dq_forced_holding_exits": int(events["action"].eq("forced_holding_exit").sum()),
        "dq_affected_symbols": int(non_warning["symbol"].nunique()),
        "issue_counts": {str(key): int(value) for key, value in counts.items()},
        "top_affected_symbols": [
            {"symbol": str(symbol), "count": int(count)}
            for symbol, count in symbol_counts.items()
        ],
        "affected_date_ranges": affected_ranges,
    }


def data_quality_policy() -> dict[str, object]:
    return {
        "abnormal_symbol_day_definition": (
            "missing open/high/low/close/volume/quote_volume, nonpositive open/high/low/close, "
            "missing universe price row, or missing entry-price return for a PIT member"
        ),
        "missing_return_policy": "missing returns are never filled with zero; affected symbol-days are excluded",
        "nonpositive_price_policy": "nonpositive open/high/low/close are hard exclusions and are never filled",
        "price_forward_fill_policy": "prices are not forward-filled to create returns",
        "holding_abnormal_day_policy": (
            "if a held symbol is abnormal on a date, it is removed before return calculation, "
            "no position row is emitted for that symbol-date, and re-entry requires a future rebalance"
        ),
        "volume_zero_policy": "volume <= 0 or quote_volume <= 0 is warning-only; missing volume fields are hard exclusions",
        "forced_exclusion_policy": "forced data-quality removals count through normal membership turnover on the removal date",
        "ranking_window_policy": (
            "a symbol is removed from a decision-date ranking candidate set if that decision-date symbol-day "
            "is hard abnormal or if a hard abnormal price day appears inside its lookback window"
        ),
    }


def events_to_output(events: pd.DataFrame) -> pd.DataFrame:
    output = events.copy()
    if output.empty:
        return pd.DataFrame(columns=SUMMARY_COLUMNS)
    output["date"] = pd.to_datetime(output["date"]).dt.strftime("%Y-%m-%d")
    return output[SUMMARY_COLUMNS]


def _normalize_prices(prices: pd.DataFrame) -> pd.DataFrame:
    df = prices.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["symbol"] = df["symbol"].astype(str)
    for col in REQUIRED_FIELDS:
        df[col] = pd.to_numeric(df[col], errors="coerce")
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def _normalize_membership(membership: pd.DataFrame) -> pd.DataFrame:
    df = membership.copy()
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    df["symbol"] = df["symbol"].astype(str)
    df["is_member"] = df["is_member"].astype(bool)
    return df.sort_values(["date", "symbol"]).reset_index(drop=True)


def _price_bar_events(prices: pd.DataFrame) -> tuple[pd.DataFrame, dict[tuple[pd.Timestamp, str], str]]:
    rows: list[dict[str, object]] = []
    hard_reasons: dict[tuple[pd.Timestamp, str], str] = {}
    for field in REQUIRED_FIELDS:
        missing = prices[prices[field].isna()]
        for rec in missing[["date", "symbol"]].itertuples(index=False):
            rows.append(_event(
                date=rec.date,
                symbol=rec.symbol,
                issue_type="missing_ohlcv",
                affected_field=field,
                action="exclude_symbol_day",
                source_stage="price_bar",
                reason=f"{field} is missing",
            ))
            hard_reasons[(pd.Timestamp(rec.date).normalize(), str(rec.symbol))] = f"{field} is missing"

    for field in PRICE_FIELDS:
        bad = prices[prices[field].notna() & ~prices[field].gt(0)]
        for rec in bad[["date", "symbol"]].itertuples(index=False):
            rows.append(_event(
                date=rec.date,
                symbol=rec.symbol,
                issue_type="nonpositive_price",
                affected_field=field,
                action="exclude_symbol_day",
                source_stage="price_bar",
                reason=f"{field} <= 0",
            ))
            hard_reasons[(pd.Timestamp(rec.date).normalize(), str(rec.symbol))] = f"{field} <= 0"

    for field in ["volume", "quote_volume"]:
        bad = prices[prices[field].notna() & ~prices[field].gt(0)]
        for rec in bad[["date", "symbol"]].itertuples(index=False):
            rows.append(_event(
                date=rec.date,
                symbol=rec.symbol,
                issue_type="nonpositive_volume_warning",
                affected_field=field,
                action="warn_only",
                source_stage="price_bar",
                reason=f"{field} <= 0; warning only",
            ))
    return _events_from_rows(rows), hard_reasons


def _filtered_price_view(
    prices: pd.DataFrame,
    abnormal_reasons: dict[tuple[pd.Timestamp, str], str],
) -> pd.DataFrame:
    if not abnormal_reasons:
        return prices.copy()
    filtered = prices.copy()
    key_index = pd.MultiIndex.from_frame(filtered[["date", "symbol"]])
    abnormal_index = pd.MultiIndex.from_tuples(list(abnormal_reasons.keys()), names=["date", "symbol"])
    mask = key_index.isin(abnormal_index)
    filtered.loc[mask, REQUIRED_FIELDS] = np.nan
    return filtered


def _missing_price_row_events(
    membership: pd.DataFrame,
    prices: pd.DataFrame,
) -> pd.DataFrame:
    if membership.empty:
        return _empty_events()
    available = prices[["date", "symbol"]].drop_duplicates()
    merged = membership[["date", "symbol"]].drop_duplicates().merge(
        available,
        on=["date", "symbol"],
        how="left",
        indicator=True,
    )
    missing = merged[merged["_merge"].eq("left_only")]
    rows = [
        _event(
            date=rec.date,
            symbol=rec.symbol,
            issue_type="missing_price_row",
            affected_field="ohlcv",
            action="exclude_symbol_day",
            source_stage="universe_candidate",
            reason="PIT member has no price row on this date",
        )
        for rec in missing[["date", "symbol"]].itertuples(index=False)
    ]
    return _events_from_rows(rows)


def _filter_holding_candidates(
    membership: pd.DataFrame,
    prices: pd.DataFrame,
    abnormal_reasons: dict[tuple[pd.Timestamp, str], str],
    start: pd.Timestamp,
    end: pd.Timestamp,
    price_col: str,
) -> tuple[pd.DataFrame, pd.DataFrame, dict[tuple[pd.Timestamp, str], str]]:
    output = membership.copy()
    active = output["is_member"] & output["date"].between(start, end)
    returns = prices.pivot(index="date", columns="symbol", values=price_col).sort_index()
    returns = returns.pct_change(fill_method=None).replace([np.inf, -np.inf], np.nan)
    stacked = returns.reset_index().melt(
        id_vars="date",
        var_name="symbol",
        value_name="entry_return",
    )
    candidates = output.loc[active, ["date", "symbol"]].merge(
        stacked,
        on=["date", "symbol"],
        how="left",
    )
    bad = candidates[
        candidates["entry_return"].isna()
        | ~np.isfinite(candidates["entry_return"].astype(float))
    ].copy()
    holding_reasons: dict[tuple[pd.Timestamp, str], str] = {}
    rows: list[dict[str, object]] = []
    for rec in bad[["date", "symbol"]].itertuples(index=False):
        key = (pd.Timestamp(rec.date).normalize(), str(rec.symbol))
        reason = abnormal_reasons.get(key, "entry-price return is missing")
        holding_reasons[key] = reason
        rows.append(_event(
            date=rec.date,
            symbol=rec.symbol,
            issue_type="missing_return",
            affected_field="return",
            action="exclude_from_holding_candidate",
            source_stage="holding",
            reason=reason,
        ))

    if holding_reasons:
        remove_index = pd.MultiIndex.from_tuples(list(holding_reasons.keys()), names=["date", "symbol"])
        candidate_index = pd.MultiIndex.from_frame(output[["date", "symbol"]])
        output.loc[candidate_index.isin(remove_index), "is_member"] = False
    output = output[output["is_member"]].sort_values(["date", "symbol"]).reset_index(drop=True)
    return output, _events_from_rows(rows), holding_reasons


def _filter_ranking_candidates(
    membership: pd.DataFrame,
    prices: pd.DataFrame,
    abnormal_reasons: dict[tuple[pd.Timestamp, str], str],
    config: dict[str, Any],
) -> tuple[pd.DataFrame, pd.DataFrame]:
    output = membership.copy()
    members_by_date = {
        pd.Timestamp(date).normalize(): set(group["symbol"])
        for date, group in output[output["is_member"]].groupby("date")
    }
    close = prices.pivot(index="date", columns="symbol", values="close").sort_index()
    abnormal_by_symbol: dict[str, set[pd.Timestamp]] = {}
    for date, symbol in abnormal_reasons:
        abnormal_by_symbol.setdefault(symbol, set()).add(pd.Timestamp(date).normalize())

    rows: list[dict[str, object]] = []
    exclusions: set[tuple[pd.Timestamp, str]] = set()
    end_ts = pd.Timestamp(str(config["end_date"])).normalize()
    for decision_date in rebalance_dates(
        str(config["start_date"]),
        str(config["end_date"]),
        str(config["rebalance_freq"]),
    ):
        effective_date = decision_date + pd.Timedelta(days=1)
        if effective_date > end_ts:
            continue
        signal_cutoff = decision_date - pd.Timedelta(days=1)
        lookback_start = signal_cutoff - pd.Timedelta(days=int(config["lookback_days"]))
        for symbol in sorted(members_by_date.get(decision_date, set())):
            reason = abnormal_reasons.get((decision_date, symbol))
            if reason is None:
                reason = _ranking_exclusion_reason(
                    close,
                    abnormal_by_symbol,
                    symbol,
                    lookback_start,
                    signal_cutoff,
                )
            if reason is None:
                continue
            exclusions.add((decision_date, symbol))
            rows.append(_event(
                date=decision_date,
                symbol=symbol,
                issue_type="ranking_candidate_abnormal",
                affected_field="lookback_close",
                action="exclude_from_ranking_candidate",
                source_stage="ranking",
                reason=reason,
            ))

    if exclusions:
        exclude_index = pd.MultiIndex.from_tuples(list(exclusions), names=["date", "symbol"])
        row_index = pd.MultiIndex.from_frame(output[["date", "symbol"]])
        output.loc[row_index.isin(exclude_index), "is_member"] = False
    output = output[output["is_member"]].sort_values(["date", "symbol"]).reset_index(drop=True)
    return output, _events_from_rows(rows)


def _ranking_exclusion_reason(
    close: pd.DataFrame,
    abnormal_by_symbol: dict[str, set[pd.Timestamp]],
    symbol: str,
    lookback_start: pd.Timestamp,
    signal_cutoff: pd.Timestamp,
) -> str | None:
    bad_dates = abnormal_by_symbol.get(symbol, set())
    if bad_dates and any(lookback_start <= date <= signal_cutoff for date in bad_dates):
        return "hard abnormal price day appears inside lookback window"
    return None


def _event_reasons(events: pd.DataFrame) -> dict[tuple[pd.Timestamp, str], str]:
    reasons: dict[tuple[pd.Timestamp, str], str] = {}
    if events.empty:
        return reasons
    for rec in events[["date", "symbol", "reason"]].itertuples(index=False):
        reasons[(pd.Timestamp(rec.date).normalize(), str(rec.symbol))] = str(rec.reason)
    return reasons


def _position_symbols_by_date(positions: pd.DataFrame) -> dict[pd.Timestamp, set[str]]:
    if positions.empty:
        return {}
    normalized = positions.copy()
    normalized["date"] = pd.to_datetime(normalized["date"]).dt.normalize()
    return {
        pd.Timestamp(date).normalize(): set(group["symbol"].astype(str))
        for date, group in normalized.groupby("date")
    }


def _event(
    date: Any,
    symbol: str,
    issue_type: str,
    affected_field: str,
    action: str,
    source_stage: str,
    reason: str,
) -> dict[str, object]:
    return {
        "date": pd.Timestamp(date).normalize(),
        "symbol": str(symbol),
        "issue_type": issue_type,
        "affected_field": affected_field,
        "action": action,
        "source_stage": source_stage,
        "reason": reason,
    }


def _events_from_rows(rows: list[dict[str, object]]) -> pd.DataFrame:
    if not rows:
        return _empty_events()
    df = pd.DataFrame(rows, columns=SUMMARY_COLUMNS)
    df["date"] = pd.to_datetime(df["date"]).dt.normalize()
    return df


def _empty_events() -> pd.DataFrame:
    return pd.DataFrame(columns=SUMMARY_COLUMNS)


def _price_column(entry_price: str) -> str:
    if entry_price == "t1_open":
        return "open"
    if entry_price == "t1_close":
        return "close"
    raise ValueError("entry_price must be t1_open or t1_close")


def _date_str(value: Any) -> str:
    if pd.isna(value):
        return ""
    return pd.Timestamp(value).strftime("%Y-%m-%d")
