#!/usr/bin/env python3
"""Lock the highest relative-volume tickers from the first five minutes of trading."""

from __future__ import annotations

import argparse
import json
from datetime import date, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd


OPENING_COLUMNS = [
    "name",
    "exchange",
    "close",
    "low",
    "volume",
    "ATR",
    "ADRP",
    "average_volume_30d_calc",
    "average_volume_60d_calc",
]


def fetch_opening_universe() -> pd.DataFrame:
    """Fetch the live US stock universe needed for the opening RVOL snapshot."""
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error

    query = (
        Query()
        .set_markets("america")
        .select(*OPENING_COLUMNS)
        .where(
            col("type") == "stock",
            col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
            col("average_volume_30d_calc") > 350_000,
            col("ADRP") > 4,
        )
        .order_by("volume", ascending=False)
        .limit(5_000)
    )
    _, frame = query.get_scanner_data()
    return frame


def calculate_opening_rvol(raw: pd.DataFrame, minutes_since_open: int, limit: int = 20) -> pd.DataFrame:
    """Apply the opening scanner filters and rank the top names by RVOL at time."""
    required = {
        "ticker", "close", "low", "volume", "ATR", "ADRP",
        "average_volume_30d_calc", "average_volume_60d_calc",
    }
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError("TradingView did not return required column(s): " + ", ".join(missing))
    df = raw.copy()
    numeric = [
        "close", "low", "volume", "ATR", "ADRP",
        "average_volume_30d_calc", "average_volume_60d_calc",
    ]
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["dollar_volume_30d"] = df["close"] * df["average_volume_30d_calc"]
    df["current_volume_vs_60d"] = df["volume"] / df["average_volume_60d_calc"]
    session_fraction = max(1, min(minutes_since_open, 390)) / 390
    df["relative_volume_at_time"] = df["current_volume_vs_60d"] / session_fraction
    df["lod_distance_atr_14"] = (df["close"] - df["low"]) / df["ATR"]

    valid = (df[["close", "low", "ATR", "average_volume_30d_calc", "average_volume_60d_calc"]] > 0).all(axis=1)
    eligible = df.loc[
        valid
        & (df["dollar_volume_30d"] > 50_000_000)
        & (df["average_volume_30d_calc"] > 350_000)
        & (df["ADRP"] > 4)
        & (df["relative_volume_at_time"] > 1)
    ].copy()
    return eligible.sort_values(
        ["relative_volume_at_time", "volume", "ticker"],
        ascending=[False, False, True],
        kind="stable",
    ).head(limit)


def write_lock(frame: pd.DataFrame, output_dir: Path, market_date: date | None = None) -> list[Path]:
    """Write the locked ticker set; the web page keeps its metrics live separately."""
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (market_date or datetime.now().date()).isoformat()
    payload = {"market_date": stamp, "tickers": frame["ticker"].astype(str).tolist()}
    dated = output_dir / f"opening_rvol_lock_{stamp}.json"
    latest = output_dir / "opening_rvol_lock_latest.json"
    encoded = json.dumps(payload, separators=(",", ":")) + "\n"
    dated.write_text(encoded, encoding="utf-8")
    latest.write_text(encoded, encoding="utf-8")
    return [dated, latest]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Lock the opening top-20 RVOL tickers.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--market-date", type=date.fromisoformat, help="Market date for the lock file (YYYY-MM-DD).")
    parser.add_argument("--minutes-since-open", type=int, help="Elapsed regular-session minutes used for time-adjusted RVOL.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    now = datetime.now(ZoneInfo("America/New_York"))
    minutes_since_open = args.minutes_since_open if args.minutes_since_open is not None else max(1, (now.hour * 60 + now.minute) - (9 * 60 + 30))
    results = calculate_opening_rvol(fetch_opening_universe(), minutes_since_open)
    paths = write_lock(results, args.output_dir, args.market_date)
    print(f"Locked {len(results)} opening RVOL tickers.\n" + "\n".join(map(str, paths)))


if __name__ == "__main__":
    main()
