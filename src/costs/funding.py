from __future__ import annotations

from dataclasses import dataclass

import pandas as pd


KNOWN_FUNDING_GAP_SYMBOLS = [
    "BYBIT:XTZUSDT.P",
    "BYBIT:FLOWUSDT.P",
    "BYBIT:LPTUSDT.P",
    "BYBIT:AXSUSDT.P",
    "BYBIT:RVNUSDT.P",
    "BYBIT:INJUSDT.P",
    "BYBIT:CTCUSDT.P",
]


@dataclass(frozen=True)
class FundingAttribution:
    symbol_day: pd.DataFrame
    interval_distribution: dict[str, int]
    funding_gap_breakdown: dict[str, object]
    outlier_breakdown_base: dict[str, object]
    audit_samples: list[dict[str, object]]


def validate_funding_rates(funding: pd.DataFrame) -> None:
    expected = ["timestamp", "symbol", "exchange", "funding_rate", "interval_hours", "source", "is_proxy"]
    if list(funding.columns) != expected:
        raise ValueError(f"funding_rates schema mismatch: {list(funding.columns)}")
    if str(funding["timestamp"].dtype) != "datetime64[ns, UTC]":
        raise ValueError(f"funding timestamp must be UTC, got {funding['timestamp'].dtype}")
    if funding["is_proxy"].astype(bool).any():
        raise ValueError("funding_rates contains proxy rows")
    if set(funding["source"].dropna().astype(str).unique()) != {"bybit_api"}:
        raise ValueError("funding source must be bybit_api")
    intervals = set(funding["interval_hours"].dropna().astype(int).unique())
    if not intervals.issubset({1, 4, 8}):
        raise ValueError(f"unsupported funding interval_hours: {sorted(intervals)}")
    if funding.duplicated(["symbol", "timestamp"]).any():
        raise ValueError("funding_rates contains duplicate symbol+timestamp rows")
    if funding["funding_rate"].abs().max() > 0.25:
        raise ValueError("funding_rate values look like percentages rather than decimals")


def build_funding_attribution(funding: pd.DataFrame, positions: pd.DataFrame) -> FundingAttribution:
    validate_funding_rates(funding)
    held = positions.loc[:, ["date", "symbol", "weight"]].copy()
    held["date"] = pd.to_datetime(held["date"]).dt.tz_localize(None)
    held["symbol"] = held["symbol"].astype(str)
    held["weight"] = held["weight"].astype(float)

    rows = funding.copy()
    rows["date"] = rows["timestamp"].dt.tz_convert("UTC").dt.floor("D").dt.tz_localize(None)
    merged = rows.merge(held, on=["date", "symbol"], how="inner")
    merged["funding_cost_base"] = merged["weight"].astype(float) * merged["funding_rate"].astype(float)
    merged["outlier"] = merged["funding_rate"].abs() >= 0.01
    merged["outlier_abs_cost_base"] = merged["funding_cost_base"].abs().where(merged["outlier"], 0.0)

    symbol_day = merged.groupby(["date", "symbol"], as_index=False).agg(
        weight=("weight", "first"),
        funding_cost_base=("funding_cost_base", "sum"),
        funding_abs_cost_base=("funding_cost_base", lambda series: float(series.abs().sum())),
        outlier_count_today=("outlier", "sum"),
        outlier_abs_cost_base=("outlier_abs_cost_base", "sum"),
        funding_settlement_count=("timestamp", "count"),
    )
    symbol_day["funding_gap"] = False

    funded_pairs = symbol_day.loc[:, ["date", "symbol"]].drop_duplicates()
    known_held = held[held["symbol"].isin(KNOWN_FUNDING_GAP_SYMBOLS)].copy()
    known_gap = known_held.merge(funded_pairs, on=["date", "symbol"], how="left", indicator=True)
    known_gap = known_gap[known_gap["_merge"] == "left_only"].drop(columns=["_merge"])
    if not known_gap.empty:
        gap_rows = known_gap.assign(
            funding_cost_base=0.0,
            funding_abs_cost_base=0.0,
            outlier_count_today=0,
            outlier_abs_cost_base=0.0,
            funding_settlement_count=0,
            funding_gap=True,
        )
        symbol_day = pd.concat([symbol_day, gap_rows], ignore_index=True, sort=False)

    symbol_day["outlier_count_today"] = symbol_day["outlier_count_today"].astype(int)
    symbol_day["funding_settlement_count"] = symbol_day["funding_settlement_count"].astype(int)
    symbol_day["funding_gap"] = symbol_day["funding_gap"].astype(bool)

    active_position_days = int(len(held))
    gap_days = int(len(known_gap))
    gap_by_symbol = {
        str(symbol): int(count)
        for symbol, count in known_gap.groupby("symbol").size().sort_index().items()
    }
    funding_gap_breakdown = {
        "known_gap_symbols": KNOWN_FUNDING_GAP_SYMBOLS,
        "active_position_symbol_days_with_gap": gap_days,
        "pct_of_active_position": float(gap_days / active_position_days) if active_position_days else 0.0,
        "per_symbol_breakdown": gap_by_symbol,
    }

    total_abs_cost = float(merged["funding_cost_base"].abs().sum())
    outlier_abs_cost = float(merged.loc[merged["outlier"], "funding_cost_base"].abs().sum())
    outlier_breakdown = {
        "outlier_count": int(rows["funding_rate"].abs().ge(0.01).sum()),
        "held_outlier_rows": int(merged["outlier"].sum()),
        "held_outlier_symbol_days": int(
            merged.loc[merged["outlier"], ["date", "symbol"]].drop_duplicates().shape[0]
        ),
        "max_abs_funding_rate": float(rows["funding_rate"].abs().max()),
        "held_max_abs_funding_rate": float(merged["funding_rate"].abs().max()) if len(merged) else 0.0,
        "outlier_abs_funding_cost_base": outlier_abs_cost,
        "total_abs_funding_cost_base": total_abs_cost,
        "outlier_pct_of_total_abs_funding_cost": float(outlier_abs_cost / total_abs_cost) if total_abs_cost else 0.0,
    }

    interval_distribution = {
        f"{int(interval)}h_rows": int(count)
        for interval, count in merged["interval_hours"].value_counts().sort_index().items()
    }
    for key in ["1h_rows", "4h_rows", "8h_rows"]:
        interval_distribution.setdefault(key, 0)

    audit_samples = _build_audit_samples(merged, rows)

    return FundingAttribution(
        symbol_day=symbol_day.sort_values(["date", "symbol"]).reset_index(drop=True),
        interval_distribution=interval_distribution,
        funding_gap_breakdown=funding_gap_breakdown,
        outlier_breakdown_base=outlier_breakdown,
        audit_samples=audit_samples,
    )


def _build_audit_samples(merged: pd.DataFrame, all_rows: pd.DataFrame) -> list[dict[str, object]]:
    samples: list[dict[str, object]] = []
    for interval in [1, 4, 8]:
        subset = merged[merged["interval_hours"].astype(int) == interval]
        if subset.empty:
            raw_subset = all_rows[all_rows["interval_hours"].astype(int) == interval]
            if raw_subset.empty:
                samples.append({"interval_hours": interval, "available": False})
                continue
            first_key = raw_subset.groupby(["date", "symbol"], sort=True).size().index[0]
            day_rows = raw_subset[
                (raw_subset["date"] == first_key[0]) & (raw_subset["symbol"] == first_key[1])
            ].sort_values("timestamp")
            samples.append(
                {
                    "interval_hours": interval,
                    "available": True,
                    "used_in_stress": False,
                    "not_used_reason": "run008 has no held symbol-day for this funding interval",
                    "date": pd.Timestamp(first_key[0]).strftime("%Y-%m-%d"),
                    "symbol": str(first_key[1]),
                    "settlement_count": int(len(day_rows)),
                    "settlements": [
                        {
                            "timestamp": row.timestamp.isoformat(),
                            "funding_rate": float(row.funding_rate),
                            "position_weight": 0.0,
                            "single_settlement_cost": 0.0,
                        }
                        for row in day_rows.itertuples(index=False)
                    ],
                    "daily_funding_cost_base": 0.0,
                }
            )
            continue
        first_key = subset.groupby(["date", "symbol"], sort=True).size().index[0]
        day_rows = subset[(subset["date"] == first_key[0]) & (subset["symbol"] == first_key[1])].sort_values("timestamp")
        settlements = [
            {
                "timestamp": row.timestamp.isoformat(),
                "funding_rate": float(row.funding_rate),
                "position_weight": float(row.weight),
                "single_settlement_cost": float(row.funding_cost_base),
            }
            for row in day_rows.itertuples(index=False)
        ]
        samples.append(
            {
                "interval_hours": interval,
                "available": True,
                "used_in_stress": True,
                "date": pd.Timestamp(first_key[0]).strftime("%Y-%m-%d"),
                "symbol": str(first_key[1]),
                "settlement_count": int(len(day_rows)),
                "settlements": settlements,
                "daily_funding_cost_base": float(day_rows["funding_cost_base"].sum()),
            }
        )
    return samples
