from __future__ import annotations

import unittest

from src.costs.symbol_mapping import to_funding_symbol, to_perp_symbol


class SymbolMappingTest(unittest.TestCase):
    def test_btcusdt_round_trip(self) -> None:
        self.assertEqual(to_funding_symbol("BYBIT:BTCUSDT.P"), "BTCUSDT")
        self.assertEqual(to_perp_symbol("BTCUSDT"), "BYBIT:BTCUSDT.P")

    def test_ethusdt_round_trip(self) -> None:
        self.assertEqual(to_funding_symbol("BYBIT:ETHUSDT.P"), "ETHUSDT")
        self.assertEqual(to_perp_symbol("ETHUSDT"), "BYBIT:ETHUSDT.P")

    def test_prefixed_symbol_is_preserved(self) -> None:
        self.assertEqual(to_funding_symbol("BYBIT:1000PEPEUSDT.P"), "1000PEPEUSDT")
        self.assertEqual(to_perp_symbol("1000PEPEUSDT"), "BYBIT:1000PEPEUSDT.P")

    def test_rlusd_symbol_is_not_split_on_usdt(self) -> None:
        self.assertEqual(to_funding_symbol("BYBIT:RLUSDUSDT.P"), "RLUSDUSDT")
        self.assertEqual(to_perp_symbol("RLUSDUSDT"), "BYBIT:RLUSDUSDT.P")

    def test_raw_symbol_is_not_supported_as_perp_input(self) -> None:
        with self.assertRaises(ValueError):
            to_funding_symbol("BTCUSDT")

    def test_non_usdt_perp_is_not_supported(self) -> None:
        with self.assertRaises(ValueError):
            to_funding_symbol("BYBIT:BTCUSD.P")

    def test_lowercase_symbol_is_not_supported(self) -> None:
        with self.assertRaises(ValueError):
            to_funding_symbol("bybit:btcusdt.p")


if __name__ == "__main__":
    unittest.main()

