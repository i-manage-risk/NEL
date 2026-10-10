import unittest
from datetime import date, datetime
from zoneinfo import ZoneInfo

import pandas as pd

from etf_strength import (
    _is_stock_holding,
    DATA_DIR,
    UNIVERSES,
    build_metric_history,
    build_snapshots,
    load_universe,
    rank_groups_for_session,
    validate_actual_close,
    validate_completed_session,
)


def metric_frame(session: date, performance: float, extension: float = 2.0) -> pd.DataFrame:
    return pd.DataFrame(
        [{
            "perf_1m": performance,
            "perf_3m": performance,
            "perf_6m": performance,
            "perf_1y": performance,
            "adrp": 5.0,
            "atrp": 4.0,
            "average_volume_10d": 1_000_000,
            "average_dollar_volume_30d": 100_000_000,
            "extension": extension,
            "is_tight": True,
            "coil_setup": "3D",
            "rmv_15d": 10.0,
            "intraday_change": 1.25,
            "close_to_close_change": -0.75,
            "perf_1w": 2.5,
        }],
        index=[pd.Timestamp(session)],
    )


class EtfStrengthTests(unittest.TestCase):
    def test_multiple_etfs_confirm_one_group_instead_of_using_multiple_slots(self):
        session = date(2026, 9, 28)
        universe = pd.DataFrame([
            {"Ticker": "HACK", "Group": "Cybersecurity", "Description": "Broad"},
            {"Ticker": "BUG", "Group": "Cybersecurity", "Description": "Pure play"},
            {"Ticker": "CIBR", "Group": "Cybersecurity", "Description": "Security"},
            {"Ticker": "AIQ", "Group": "AI", "Description": "AI"},
        ])
        histories = {
            "HACK": metric_frame(session, 30),
            "BUG": metric_frame(session, 28),
            "CIBR": metric_frame(session, 27),
            "AIQ": metric_frame(session, 20),
        }
        groups = rank_groups_for_session(histories, universe, session, "perf_1m", 2)
        self.assertEqual([group["group"] for group in groups], ["Cybersecurity", "AI"])
        self.assertEqual(groups[0]["member_count"], 3)
        self.assertEqual({row["symbol"] for row in groups[0]["members"]}, {"HACK", "BUG", "CIBR"})

    def test_metric_history_uses_adjusted_close_for_performance(self):
        index = pd.bdate_range("2025-12-01", periods=180)
        raw_close = pd.Series(range(100, 280), index=index, dtype=float)
        history = pd.DataFrame({
            "open": raw_close - 1,
            "high": raw_close + 2,
            "low": raw_close - 2,
            "close": raw_close,
            "adj_close": raw_close * 2,
            "volume": 1_000_000,
        })
        metrics = build_metric_history(history)
        target = index[-1] - pd.DateOffset(months=1)
        prior = history.loc[history.index <= target, "adj_close"].iloc[-1]
        expected = 100 * (history["adj_close"].iloc[-1] / prior - 1)
        self.assertAlmostEqual(metrics["perf_1m"].iloc[-1], expected)
        self.assertAlmostEqual(metrics["intraday_change"].iloc[-1], 100 * (279 / 278 - 1))

    def test_stale_market_close_is_rejected(self):
        histories = {"SPY": pd.DataFrame({"close": [100]}, index=[pd.Timestamp("2026-09-25")])}
        with self.assertRaises(RuntimeError):
            validate_actual_close(histories, date(2026, 9, 28))

    def test_incomplete_current_session_is_rejected(self):
        morning_in_new_york = datetime(2026, 9, 29, 10, 0, tzinfo=ZoneInfo("America/New_York"))
        with self.assertRaises(RuntimeError):
            validate_completed_session(date(2026, 9, 29), morning_in_new_york)
        validate_completed_session(date(2026, 9, 28), morning_in_new_york)

    def test_historical_snapshot_uses_actual_close_date(self):
        session = date(2026, 9, 25)
        universe = pd.DataFrame([
            {"Ticker": "AIQ", "Group": "AI", "Description": "AI"},
            {"Ticker": "MISS", "Group": "Unavailable", "Description": "No bars"},
        ])
        snapshots = build_snapshots({"AIQ": metric_frame(session, 20)}, universe, [session], 10)
        self.assertEqual(snapshots[0]["date"], "2026-09-25")
        self.assertEqual(snapshots[0]["windows"]["1w"][0]["group"], "AI")
        self.assertEqual(snapshots[0]["daily_changes"][0]["intraday"], 1.25)
        self.assertEqual(snapshots[0]["daily_changes"][0]["one_day"], -0.75)
        self.assertEqual(snapshots[0]["daily_changes"][0]["one_week"], 2.5)
        self.assertEqual(snapshots[0]["daily_changes"][1]["symbol"], "MISS")
        self.assertIsNone(snapshots[0]["daily_changes"][1]["one_day"])

    def test_overlapping_theme_etfs_share_one_group(self):
        universe = load_universe(DATA_DIR / "theme_etfs.tsv").set_index("Ticker")
        expected = {
            "ETHA": "Cryptocurrency", "GBTC": "Cryptocurrency", "IBIT": "Cryptocurrency",
            "ESPO": "Video games", "NERD": "Video games",
            "IHF": "Healthcare services", "XHS": "Healthcare services",
            "IHI": "Medical equipment", "XHE": "Medical equipment",
            "HOMZ": "Housing", "ITB": "Housing", "XHB": "Housing",
        }
        self.assertEqual({ticker: universe.loc[ticker, "Group"] for ticker in expected}, expected)
        sectors = load_universe(DATA_DIR / "sector_etfs.tsv").set_index("Ticker")
        self.assertEqual(sectors.loc["XLF", "Group"], "Financial Services")

    def test_sector_dashboard_omits_nel_sections_and_has_all_performance_modes(self):
        from etf_dashboard import SECTOR_COLORS, render_dashboard

        payload = {
            "kind": "sectors",
            "title": "Sector Leadership",
            "top_n": 3,
            "holdings_as_of": "2026-09-28",
            "snapshots": [],
            "holdings": {},
        }
        html = render_dashboard(payload, "sectors")
        self.assertNotIn('id="nel-title"', html)
        self.assertNotIn('id="tight-title"', html)
        self.assertEqual(html.count("data-change-mode="), 8)
        self.assertIn('data-change-mode="extended"', html)
        self.assertNotIn('data-change-mode="premarket"', html)
        self.assertNotIn('data-change-mode="overnight"', html)
        self.assertNotIn('data-change-mode="postmarket"', html)
        self.assertIn("Extended Hours · ${session.label}", html)
        self.assertNotIn("Live TradingView data", html)
        self.assertIn("public feed delayed up to 15 min", html)
        sectors = load_universe(DATA_DIR / "sector_etfs.tsv")
        self.assertEqual(set(SECTOR_COLORS), set(sectors["Group"]))
        self.assertEqual(len(set(SECTOR_COLORS.values())), 11)

        theme_payload = {**payload, "kind": "themes", "title": "Theme Leadership"}
        theme_html = render_dashboard(theme_payload, "themes")
        self.assertIn('id="nel-title"', theme_html)
        self.assertNotIn('id="tight-title"', theme_html)

    def test_dead_vice_ticker_is_not_in_theme_universe(self):
        universe = load_universe(DATA_DIR / "theme_etfs.tsv")
        self.assertNotIn("VICE", set(universe["Ticker"]))

    def test_theme_and_sector_leader_counts(self):
        counts = {config.key: config.top_n for config in UNIVERSES}
        self.assertEqual(counts, {"themes": 5, "sectors": 3})

    def test_non_stock_holdings_are_removed(self):
        funds = {"HACK", "BUG"}
        self.assertTrue(_is_stock_holding("CRWD", "CrowdStrike Holdings", funds))
        self.assertFalse(_is_stock_holding("USD", "U.S. Dollar Cash", funds))
        self.assertFalse(_is_stock_holding("HACK", "ETFMG Prime Cyber Security ETF", funds))
        self.assertFalse(_is_stock_holding("SWP1", "Index Swap", funds))


if __name__ == "__main__":
    unittest.main()
