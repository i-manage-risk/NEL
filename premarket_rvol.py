#!/usr/bin/env python3
"""Create a minimal premarket relative-volume list from TradingView."""

from __future__ import annotations

import argparse
import html
from datetime import date, datetime
from pathlib import Path

import pandas as pd

from focus_list import Settings


PREMARKET_COLUMNS = [
    "name",
    "exchange",
    "industry",
    "close",
    "SMA30",
    "SMA50",
    "ATRP",
    "premarket_close",
    "premarket_change",
    "premarket_volume",
    "average_volume_10d_calc",
    "average_volume_30d_calc",
    "average_volume_60d_calc",
]


def fetch_premarket_universe() -> pd.DataFrame:
    """Fetch US stocks with TradingView's live premarket data."""
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error

    query = (
        Query()
        .set_markets("america")
        .select(*PREMARKET_COLUMNS)
        .where(
            col("type") == "stock",
            col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
            col("premarket_change") >= 3,
        )
        .order_by("premarket_volume", ascending=False)
        .limit(5_000)
    )
    _, frame = query.get_scanner_data()
    return frame


def calculate_premarket_rvol(raw: pd.DataFrame, settings: Settings, limit: int = 20) -> pd.DataFrame:
    """Apply the NEL liquidity filters, then rank eligible gainers by RVOL."""
    required = {
        "ticker", "name", "exchange", "industry", "close", "SMA30", "SMA50", "ATRP", "premarket_close", "premarket_change",
        "premarket_volume", "average_volume_10d_calc",
        "average_volume_30d_calc", "average_volume_60d_calc",
    }
    missing = sorted(required.difference(raw.columns))
    if missing:
        raise ValueError("TradingView did not return required column(s): " + ", ".join(missing))

    df = raw.copy()
    numeric = [
        "close", "SMA30", "SMA50", "ATRP", "premarket_close", "premarket_change", "premarket_volume",
        "average_volume_10d_calc", "average_volume_30d_calc", "average_volume_60d_calc",
    ]
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")
    df["average_dollar_volume_30d"] = df["SMA30"] * df["average_volume_30d_calc"]
    df["premarket_rvol_60d"] = df["premarket_volume"] / df["average_volume_60d_calc"]
    df["premarket_atr_extension_from_50d"] = (df["premarket_close"] - df["SMA50"]) / (
        df["SMA50"] * (df["ATRP"] / 100)
    )

    valid_metrics = (df[["close", "SMA30", "SMA50", "ATRP", "premarket_close", "average_volume_10d_calc", "average_volume_30d_calc", "average_volume_60d_calc"]] > 0).all(axis=1)
    eligible = df.loc[
        valid_metrics
        & ~df["industry"].fillna("").str.contains("biotech", case=False, regex=False)
        & (df["average_dollar_volume_30d"] > settings.min_dollar_volume)
        & (df["average_volume_10d_calc"] > settings.min_avg_volume_10d)
        & (df["premarket_change"] >= 3)
        & df["premarket_rvol_60d"].notna()
        & (df["premarket_atr_extension_from_50d"] <= 4)
    ].copy()

    return eligible.sort_values(
        ["premarket_rvol_60d", "premarket_volume", "ticker"],
        ascending=[False, False, True],
        kind="stable",
    ).head(limit)


def write_premarket_page(frame: pd.DataFrame, destination: Path) -> Path:
    """Write the intentionally minimal list-and-copy GitHub Pages view."""
    lines = "\n".join(frame["ticker"].astype(str))
    display = html.escape(lines or "No matching premarket movers.")
    page = f"""<!doctype html>
<html lang=\"en\">
<head>
  <meta charset=\"utf-8\">
  <meta name=\"viewport\" content=\"width=device-width,initial-scale=1\">
  <meta name=\"robots\" content=\"noindex\">
  <title>Premarket RVOL | NEL</title>
  <style>
    :root {{ color-scheme:dark; }}
    * {{ box-sizing:border-box; }}
    body {{ margin:0; min-height:100vh; display:grid; place-items:center; background:#141414; color:#F5F2E8; font:16px/1.65 Inter,ui-sans-serif,system-ui,sans-serif; }}
    main {{ width:min(100% - 32px,460px); }}
    button {{ width:100%; margin:0 0 12px; padding:10px 14px; border:0; border-radius:7px; background:#F5F2E8; color:#141414; font:inherit; font-weight:700; cursor:pointer; }}
    button:active {{ transform:translateY(1px); }}
    pre {{ margin:0; padding:18px 20px; overflow:auto; border:1px solid #3d3d3d; border-radius:8px; background:#2A2A2A; font:600 16px/1.7 ui-monospace,SFMono-Regular,Menlo,monospace; white-space:pre; }}
  </style>
</head>
<body>
  <main>
    <button id=\"copy\" type=\"button\">Copy</button>
    <pre id=\"tickers\">{display}</pre>
  </main>
  <script src="assets/premarket_live.js?v=pm-rvol-60d-1"></script>
</body>
</html>
"""
    destination.write_text(page, encoding="utf-8")
    return destination


def write_outputs(frame: pd.DataFrame, output_dir: Path, snapshot_date: date | None = None) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = (snapshot_date or datetime.now().date()).isoformat()
    columns = [
        "ticker", "name", "exchange", "premarket_change", "premarket_rvol_60d", "premarket_atr_extension_from_50d",
        "premarket_volume", "average_dollar_volume_30d",
    ]
    output = output_dir / f"premarket_rvol_{stamp}.csv"
    frame.loc[:, columns].round({
        "premarket_change": 2, "premarket_rvol_60d": 2, "premarket_atr_extension_from_50d": 2,
        "average_dollar_volume_30d": 0,
    }).to_csv(output, index=False)
    return [output, write_premarket_page(frame, Path("premarket_rvol.html"))]


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="List the 20 most active liquid premarket gainers by RVOL.")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="CSV output directory.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, help="Date to use in output filenames (YYYY-MM-DD).")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    raw = fetch_premarket_universe()
    results = calculate_premarket_rvol(raw, Settings(), limit=20)
    paths = write_outputs(results, args.output_dir, args.snapshot_date)
    print(f"Scanned: {len(raw):,} | matching premarket RVOL stocks: {len(results):,}")
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
