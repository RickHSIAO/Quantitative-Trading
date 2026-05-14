from __future__ import annotations

import unittest

import pandas as pd

from src.data_quality.missing import (
    aggregate_data_quality_events,
    apply_data_quality_policy,
    forced_holding_exclusion_events,
)


class MissingDataPolicyTest(unittest.TestCase):
    def test_nonpositive_price_and_missing_volume_are_hard_exclusions(self) -> None:
        prices = _prices()
        prices.loc[
            prices["date"].eq(pd.Timestamp("2024-01-03")) & prices["symbol"].eq("COMP-USD"),
            "close",
        ] = 0.0
        prices.loc[
            prices["date"].eq(pd.Timestamp("2024-01-04")) & prices["symbol"].eq("ICP-USD"),
            ["open", "low"],
        ] = 0.0
        prices.loc[
            prices["date"].eq(pd.Timestamp("2024-01-05")) & prices["symbol"].eq("COMP-USD"),
            "quote_volume",
        ] = pd.NA
        prices.loc[
            prices["date"].eq(pd.Timestamp("2024-01-06")) & prices["symbol"].eq("WARN-USD"),
            "volume",
        ] = 0.0

        result = apply_data_quality_policy(prices, _membership(), _config())
        events = result.events
        tradable_keys = set(zip(result.tradable_membership["date"], result.tradable_membership["symbol"]))

        self.assertIn((pd.Timestamp("2024-01-03"), "COMP-USD"), result.holding_exclusion_reasons)
        self.assertIn((pd.Timestamp("2024-01-04"), "ICP-USD"), result.holding_exclusion_reasons)
        self.assertIn((pd.Timestamp("2024-01-05"), "COMP-USD"), result.holding_exclusion_reasons)
        self.assertNotIn((pd.Timestamp("2024-01-03"), "COMP-USD"), tradable_keys)
        self.assertNotIn((pd.Timestamp("2024-01-04"), "ICP-USD"), tradable_keys)
        self.assertNotIn((pd.Timestamp("2024-01-05"), "COMP-USD"), tradable_keys)
        self.assertIn((pd.Timestamp("2024-01-06"), "WARN-USD"), tradable_keys)

        comp_price = result.prices[
            result.prices["date"].eq(pd.Timestamp("2024-01-03"))
            & result.prices["symbol"].eq("COMP-USD")
        ].iloc[0]
        self.assertTrue(pd.isna(comp_price["close"]))
        self.assertTrue(
            events[
                events["symbol"].eq("WARN-USD")
                & events["action"].eq("warn_only")
                & events["affected_field"].eq("volume")
            ].shape[0]
            >= 1
        )

    def test_forced_holding_exclusion_detects_removed_position(self) -> None:
        positions = pd.DataFrame([
            {
                "date": pd.Timestamp("2024-01-02"),
                "symbol": "COMP-USD",
                "weight": 0.5,
            },
            {
                "date": pd.Timestamp("2024-01-03"),
                "symbol": "ICP-USD",
                "weight": -0.5,
            },
        ])
        events = forced_holding_exclusion_events(
            positions,
            {(pd.Timestamp("2024-01-03"), "COMP-USD"): "close <= 0"},
        )

        self.assertEqual(len(events), 1)
        self.assertEqual(events.iloc[0]["symbol"], "COMP-USD")
        self.assertEqual(events.iloc[0]["action"], "forced_holding_exit")

    def test_exclude_from_ranking_candidate_when_lookback_has_hard_abnormal(self) -> None:
        prices = _prices(end_date="2024-01-08")
        prices.loc[
            prices["date"].eq(pd.Timestamp("2024-01-05")) & prices["symbol"].eq("COMP-USD"),
            "close",
        ] = 0.0

        result = apply_data_quality_policy(
            prices,
            _membership(end_date="2024-01-08"),
            _config(end_date="2024-01-08", lookback_days=2),
        )
        events = result.events
        ranking_events = events[
            events["date"].eq(pd.Timestamp("2024-01-07"))
            & events["symbol"].eq("COMP-USD")
            & events["action"].eq("exclude_from_ranking_candidate")
        ]
        signal_keys = set(zip(result.signal_membership["date"], result.signal_membership["symbol"]))

        self.assertEqual(len(ranking_events), 1)
        self.assertEqual(ranking_events.iloc[0]["issue_type"], "ranking_candidate_abnormal")
        self.assertIn("lookback window", ranking_events.iloc[0]["reason"])
        self.assertNotIn((pd.Timestamp("2024-01-07"), "COMP-USD"), signal_keys)

    def test_missing_price_row_event_for_pit_member_without_price_bar(self) -> None:
        prices = _prices()
        membership = _membership()
        membership = pd.concat(
            [
                membership,
                pd.DataFrame([{
                    "date": pd.Timestamp("2024-01-03"),
                    "symbol": "MISSING-USD",
                    "is_member": True,
                }]),
            ],
            ignore_index=True,
        )

        result = apply_data_quality_policy(prices, membership, _config())
        events = result.events
        missing = events[
            events["date"].eq(pd.Timestamp("2024-01-03"))
            & events["symbol"].eq("MISSING-USD")
            & events["issue_type"].eq("missing_price_row")
        ]

        self.assertEqual(len(missing), 1)
        self.assertEqual(missing.iloc[0]["action"], "exclude_symbol_day")
        self.assertEqual(missing.iloc[0]["source_stage"], "universe_candidate")
        self.assertIn((pd.Timestamp("2024-01-03"), "MISSING-USD"), result.holding_exclusion_reasons)

    def test_aggregate_data_quality_events_boundaries(self) -> None:
        empty = aggregate_data_quality_events(pd.DataFrame(columns=[
            "date",
            "symbol",
            "issue_type",
            "affected_field",
            "action",
            "source_stage",
            "reason",
        ]))
        self.assertEqual(empty["dq_abnormal_symbol_days"], 0)
        self.assertEqual(empty["dq_affected_symbols"], 0)
        self.assertEqual(empty["issue_counts"], {})

        warning_only = aggregate_data_quality_events(_events([
            ("2024-01-01", "WARN-USD", "nonpositive_volume_warning", "volume", "warn_only"),
        ]))
        self.assertEqual(warning_only["dq_abnormal_symbol_days"], 0)
        self.assertEqual(warning_only["dq_affected_symbols"], 0)
        self.assertEqual(warning_only["issue_counts"], {"nonpositive_volume_warning": 1})

        hard_only = aggregate_data_quality_events(_events([
            ("2024-01-01", "HARD-USD", "missing_ohlcv", "close", "exclude_symbol_day"),
            ("2024-01-01", "HARD-USD", "missing_return", "return", "exclude_from_holding_candidate"),
        ]))
        self.assertEqual(hard_only["dq_abnormal_symbol_days"], 1)
        self.assertEqual(hard_only["dq_excluded_from_holding_days"], 1)
        self.assertEqual(hard_only["dq_affected_symbols"], 1)

        mixed = aggregate_data_quality_events(_events([
            ("2024-01-01", "A-USD", "nonpositive_volume_warning", "volume", "warn_only"),
            ("2024-01-02", "B-USD", "ranking_candidate_abnormal", "lookback_close", "exclude_from_ranking_candidate"),
            ("2024-01-03", "C-USD", "missing_return", "return", "exclude_from_holding_candidate"),
            ("2024-01-04", "C-USD", "forced_holding_exit", "position", "forced_holding_exit"),
        ]))
        self.assertEqual(mixed["dq_abnormal_symbol_days"], 1)
        self.assertEqual(mixed["dq_excluded_from_ranking_candidates"], 1)
        self.assertEqual(mixed["dq_excluded_from_holding_days"], 1)
        self.assertEqual(mixed["dq_forced_holding_exits"], 1)
        self.assertEqual(mixed["dq_affected_symbols"], 2)


def _config(end_date: str = "2024-01-06", lookback_days: int = 2) -> dict[str, object]:
    return {
        "start_date": "2024-01-01",
        "end_date": end_date,
        "warmup_start_date": "2023-12-29",
        "lookback_days": lookback_days,
        "rebalance_freq": "weekly",
        "top_n": 1,
        "bottom_n": 1,
        "ranking_method": "return",
        "entry_price": "t1_open",
    }


def _prices(end_date: str = "2024-01-06") -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for day, date in enumerate(pd.date_range("2023-12-29", end_date, freq="D"), start=1):
        for idx, symbol in enumerate(["COMP-USD", "ICP-USD", "WARN-USD"], start=1):
            price = 100.0 + day + idx
            rows.append({
                "date": date,
                "symbol": symbol,
                "open": price,
                "high": price + 1.0,
                "low": price - 1.0,
                "close": price + 0.5,
                "volume": 1000.0,
                "quote_volume": price * 1000.0,
            })
    return pd.DataFrame(rows)


def _membership(end_date: str = "2024-01-06") -> pd.DataFrame:
    rows = []
    for date in pd.date_range("2024-01-01", end_date, freq="D"):
        for symbol in ["COMP-USD", "ICP-USD", "WARN-USD"]:
            rows.append({"date": date, "symbol": symbol, "is_member": True})
    return pd.DataFrame(rows)


def _events(rows: list[tuple[str, str, str, str, str]]) -> pd.DataFrame:
    return pd.DataFrame(
        [
            {
                "date": pd.Timestamp(date),
                "symbol": symbol,
                "issue_type": issue_type,
                "affected_field": affected_field,
                "action": action,
                "source_stage": "test",
                "reason": "test event",
            }
            for date, symbol, issue_type, affected_field, action in rows
        ],
        columns=[
            "date",
            "symbol",
            "issue_type",
            "affected_field",
            "action",
            "source_stage",
            "reason",
        ],
    )


if __name__ == "__main__":
    unittest.main()
