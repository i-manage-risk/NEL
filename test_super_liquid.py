import unittest

import pandas as pd

from super_liquid import SuperLiquidSettings, calculate_super_liquid


def row(name, adr, avg30, industry="Software", perf=20):
    return {
        "name": name, "description": name, "exchange": "NASDAQ", "industry": industry,
        "close": 100, "SMA30": 100, "SMA50": 95, "ADRP": adr, "ATRP": 3,
        "Perf.W": perf, "Perf.1M": perf, "Perf.3M": perf, "Perf.6M": perf, "Perf.Y": perf,
        "average_volume_10d_calc": avg30, "average_volume_30d_calc": avg30,
    }


class SuperLiquidTests(unittest.TestCase):
    def test_uses_most_liquid_etf_only_for_stock_that_fails_adr(self):
        stocks = pd.DataFrame([
            row("LOWADR", 2, 11_000_000, "Semiconductors"),
            row("DIRECT", 5, 11_000_000, "Software"),
            row("SMALL", 2, 5_000_000),
        ])
        etfs = pd.DataFrame([
            row("LOWA", 6, 1_200_000, "Fund"),
            row("LOWB", 6, 2_100_000, "Fund"),
            row("DIRX", 7, 4_000_000, "Fund"),
            row("SMAX", 7, 5_000_000, "Fund"),
        ])
        mapping = pd.DataFrame({
            "Underlying Ticker": ["LOWADR", "LOWADR", "DIRECT", "SMALL"],
            "Ticker": ["LOWA", "LOWB", "DIRX", "SMAX"],
        })
        underlyings, universe, leaders, nel = calculate_super_liquid(
            stocks, etfs, mapping, SuperLiquidSettings(top_pct=1)
        )
        self.assertEqual(set(underlyings.name), {"LOWADR", "DIRECT"})
        self.assertEqual(set(universe.name), {"LOWADR", "DIRECT"})
        selected = universe.set_index("name")
        self.assertEqual(selected.loc["LOWADR", "paired_etf"], "LOWB")
        self.assertEqual(selected.loc["LOWADR", "industry"], "Semiconductors")
        self.assertEqual(selected.loc["LOWADR", "instrument_type"], "Stock")
        self.assertEqual(selected.loc["DIRECT", "paired_etf"], "DIRX")
        self.assertEqual(set(leaders.name), set(universe.name))
        self.assertEqual(set(nel.name), set(universe.name))

    def test_strict_one_million_share_etf_threshold(self):
        stocks = pd.DataFrame([row("LOWADR", 2, 11_000_000)])
        etfs = pd.DataFrame([row("EXACT", 6, 1_000_000)])
        mapping = pd.DataFrame({"Underlying Ticker": ["LOWADR"], "Ticker": ["EXACT"]})
        _, universe, _, _ = calculate_super_liquid(stocks, etfs, mapping, SuperLiquidSettings(top_pct=1))
        self.assertTrue(universe.empty)

    def test_small_universe_keeps_ten_leaders_per_window(self):
        stocks = pd.DataFrame([row(f"S{i:02d}", 5, 11_000_000, perf=i) for i in range(20)])
        _, universe, leaders, _ = calculate_super_liquid(
            stocks, pd.DataFrame(columns=stocks.columns),
            pd.DataFrame(columns=["Underlying Ticker", "Ticker"]),
            SuperLiquidSettings(top_pct=0.05),
        )
        self.assertEqual(len(universe), 20)
        self.assertEqual(len(leaders), 10)


if __name__ == "__main__":
    unittest.main()
