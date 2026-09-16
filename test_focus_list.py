import unittest

import pandas as pd

from focus_list import Settings, calculate_nel


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

    def test_top_group_has_an_exact_size_when_performance_values_tie(self):
        raw = pd.DataFrame([
            {"name": name, "industry": "Technology Services", "close": 120, "SMA30": 120, "SMA50": 110, "ADRP": 5, "ATRP": 10, "Perf.1M": 50, "Perf.3M": 50, "Perf.6M": 50, "average_volume_10d_calc": 500_000, "average_volume_30d_calc": 500_000}
            for name in ["AAA", "BBB", "CCC", "DDD"]
        ])
        _, leaders, _ = calculate_nel(raw, Settings(top_pct=0.25, max_atr_extension=100))
        self.assertEqual(list(leaders.name), ["AAA"])
