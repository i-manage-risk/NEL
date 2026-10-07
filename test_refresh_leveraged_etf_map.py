import unittest

import pandas as pd

from scripts.refresh_leveraged_etf_map import metrics_from_history, refresh_map


class LeveragedMapRefreshTests(unittest.TestCase):
    def test_uses_last_30_complete_rows(self):
        dates = pd.date_range("2026-01-01", periods=35, freq="B")
        history = pd.DataFrame({"Close": range(1, 36), "Volume": range(100, 135)}, index=dates)
        average_volume, dollar_volume, updated = metrics_from_history(history)
        expected = history.tail(30)
        self.assertAlmostEqual(average_volume, expected.Volume.mean())
        self.assertAlmostEqual(dollar_volume, (expected.Close * expected.Volume).mean())
        self.assertEqual(updated, dates[-1].date().isoformat())

    def test_preserves_old_values_when_download_failed(self):
        mapping = pd.DataFrame({
            "Underlying Ticker": ["ABC"], "Ticker": ["ABCX"],
            "Average Daily Volume": [123], "Dollar Volume": [456],
            "Date Last Updated": ["2026-01-01"],
        })
        refreshed, failures = refresh_map(mapping, {})
        self.assertEqual(failures, ["ABCX"])
        self.assertEqual(refreshed.loc[0, "Average Daily Volume"], 123)


if __name__ == "__main__":
    unittest.main()
