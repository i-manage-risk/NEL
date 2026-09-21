import unittest

import pandas as pd

from focus_list import Settings, calculate_nel
from premarket_rvol import calculate_premarket_rvol


class FocusListTests(unittest.TestCase):
    def test_excludes_biotech_and_overextended_leaders(self):
        raw = pd.DataFrame([
            {"name": "KEEP", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 100, "ADRP": 5, "ATRP": 6, "Perf.1M": 40, "Perf.3M": 60, "Perf.6M": 80, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "EXTENDED", "industry": "Technology Services", "close": 140, "SMA30": 140, "SMA50": 100, "ADRP": 5, "ATRP": 4.5, "Perf.1M": 30, "Perf.3M": 50, "Perf.6M": 70, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "LOW_ADR", "industry": "Technology Services", "close": 150, "SMA30": 150, "SMA50": 100, "ADRP": 3.9, "ATRP": 6, "Perf.1M": 20, "Perf.3M": 40, "Perf.6M": 60, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "BIOTECH", "industry": "Biotechnology", "close": 150, "SMA30": 150, "SMA50": 100, "ADRP": 6, "ATRP": 6, "Perf.1M": 20, "Perf.3M": 40, "Perf.6M": 60, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
        ])
        universe, leaders, focus = calculate_nel(raw, Settings(top_pct=1, max_atr_extension=4))
        self.assertEqual(set(universe.name), {"KEEP", "EXTENDED"})
        self.assertEqual(set(leaders.name), {"KEEP", "EXTENDED"})
        self.assertEqual(list(focus.name), ["KEEP"])
        self.assertAlmostEqual(focus.iloc[0].atr_extension_from_50d, 20 / 6)
        self.assertEqual(focus.iloc[0].average_dollar_volume_30d, 60_000_000)

    def test_combines_1m_3m_and_6m_leaders_without_duplicates(self):
        raw = pd.DataFrame([
            {"name": "MOM_1M", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 50, "Perf.3M": 10, "Perf.6M": 5, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "MOM_3M", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 10, "Perf.3M": 50, "Perf.6M": 5, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
            {"name": "MOM_6M", "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 10, "Perf.3M": 5, "Perf.6M": 50, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000},
        ])
        _, leaders, _ = calculate_nel(raw, Settings(top_pct=0.33, max_atr_extension=100))
        self.assertEqual(set(leaders.name), {"MOM_1M", "MOM_3M", "MOM_6M"})
        self.assertEqual(len(leaders), 3)

    def test_liquidity_filter_uses_30_day_price_sma(self):
        raw = pd.DataFrame([
            {"name": "PASS", "industry": "Technology Services", "close": 120, "SMA30": 100, "SMA50": 100, "ADRP": 5, "ATRP": 10, "Perf.1M": 50, "Perf.3M": 50, "Perf.6M": 50, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
            {"name": "FAIL", "industry": "Technology Services", "close": 120, "SMA30": 70, "SMA50": 100, "ADRP": 5, "ATRP": 10, "Perf.1M": 40, "Perf.3M": 40, "Perf.6M": 40, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
        ])
        universe, _, _ = calculate_nel(raw, Settings(top_pct=1))
        self.assertEqual(list(universe.name), ["PASS"])

    def test_top_group_has_an_exact_size_when_performance_values_tie(self):
        raw = pd.DataFrame([
            {"name": name, "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 50, "Perf.3M": 50, "Perf.6M": 50, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000}
            for name in ["AAA", "BBB", "CCC", "DDD"]
        ])
        _, leaders, _ = calculate_nel(raw, Settings(top_pct=0.25, max_atr_extension=100))
        self.assertEqual(list(leaders.name), ["AAA"])

    def test_premarket_rvol_uses_nel_liquidity_and_three_percent_gain(self):
        raw = pd.DataFrame([
            {"ticker": "NASDAQ:HIGH", "name": "HIGH", "exchange": "NASDAQ", "industry": "Software", "close": 100, "SMA30": 100, "premarket_change": 4, "premarket_volume": 2_000_000, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
            {"ticker": "NYSE:SECOND", "name": "SECOND", "exchange": "NYSE", "industry": "Software", "close": 100, "SMA30": 100, "premarket_change": 3, "premarket_volume": 1_000_000, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
            {"ticker": "NASDAQ:LOWGAIN", "name": "LOWGAIN", "exchange": "NASDAQ", "industry": "Software", "close": 100, "SMA30": 100, "premarket_change": 2.99, "premarket_volume": 3_000_000, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
            {"ticker": "NYSE:ILLIQUID", "name": "ILLIQUID", "exchange": "NYSE", "industry": "Software", "close": 100, "SMA30": 100, "premarket_change": 8, "premarket_volume": 4_000_000, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 200_000},
            {"ticker": "NASDAQ:BIOTECH", "name": "BIOTECH", "exchange": "NASDAQ", "industry": "Biotechnology", "close": 100, "SMA30": 100, "premarket_change": 9, "premarket_volume": 4_000_000, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
            {"ticker": "NASDAQ:EXTENDED", "name": "EXTENDED", "exchange": "NASDAQ", "industry": "Software", "close": 100, "SMA30": 100, "premarket_change": 6, "premarket_volume": 3_000_000, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 400_000},
        ])
        raw["SMA50"] = 100
        raw["ATRP"] = 5
        raw["premarket_close"] = 105
        raw["average_volume_60d_calc"] = 400_000
        raw.loc[raw["ticker"] == "NYSE:SECOND", "premarket_close"] = 120
        raw.loc[raw["ticker"] == "NASDAQ:EXTENDED", "premarket_close"] = 125
        results = calculate_premarket_rvol(raw, Settings(), limit=20)
        self.assertEqual(list(results.ticker), ["NASDAQ:HIGH", "NYSE:SECOND"])
