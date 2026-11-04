import unittest

import pandas as pd

from obc_scan import OBCSettings, calculate_obc


def row(symbol, one_year, three_month, price=100, volume=500_000):
    return {
        'name': symbol, 'industry': 'Test', 'close': price, 'SMA30': price,
        'SMA50': price, 'ADRP': 3, 'ATRP': 4, 'Perf.3M': three_month,
        'Perf.Y': one_year, 'average_volume_10d_calc': volume,
        'average_volume_30d_calc': volume,
    }


class OBCScanTests(unittest.TestCase):
    def test_liquidity_precedes_year_leader_and_pullback_ranking(self):
        raw = pd.DataFrame([
            row('YEAR_LEADER_PULLBACK', 100, -30),
            row('YEAR_LEADER_OTHER', 90, -10),
            row('THIN', 200, -50, price=20, volume=100),
            row('OTHER', 10, -40),
        ])
        universe, leaders, candidates = calculate_obc(raw, OBCSettings(one_year_top_pct=.5, three_month_pullback_pct=.5))
        self.assertNotIn('THIN', set(universe.name))
        self.assertEqual(set(leaders.name), {'YEAR_LEADER_PULLBACK', 'YEAR_LEADER_OTHER'})
        self.assertEqual(list(candidates.name), ['YEAR_LEADER_PULLBACK'])

