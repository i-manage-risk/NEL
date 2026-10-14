import unittest

import pandas as pd

from kk_scan import KKSettings, calculate_kk


def row(symbol, one, three, six, adr=1, extension_close=100, volume=500_000):
    return {
        'name': symbol, 'industry': 'Anything', 'close': extension_close, 'SMA30': 100,
        'SMA50': 100, 'ADRP': adr, 'ATRP': 5, 'Perf.1M': one, 'Perf.3M': three,
        'Perf.6M': six, 'average_volume_10d_calc': volume,
        'average_volume_30d_calc': volume,
    }


class KKScanTests(unittest.TestCase):
    def test_liquidity_then_union_of_each_three_window_top_group(self):
        raw = pd.DataFrame([
            row('ONE', 99, 1, 1, adr=1),
            row('THREE', 1, 99, 1, adr=1),
            row('SIX', 1, 1, 99, adr=1),
            row('ILLQUID', 200, 200, 200, volume=100),
        ])
        universe, leaders = calculate_kk(raw, KKSettings(top_pct=.34))
        self.assertEqual(set(universe.name), {'ONE', 'THREE', 'SIX'})
        self.assertEqual(set(leaders.name), {'ONE', 'THREE', 'SIX'})
        self.assertTrue((leaders['ADRP'] == 1).all(), 'ADR must not gate KK leadership')

    def test_extension_is_retained_not_used_to_exclude_a_leader(self):
        raw = pd.DataFrame([row('EXTENDED', 99, 99, 99, extension_close=140)])
        _, leaders = calculate_kk(raw, KKSettings(top_pct=1))
        self.assertEqual(list(leaders.name), ['EXTENDED'])
        self.assertGreater(leaders.iloc[0].atr_extension_from_50d, 4)

