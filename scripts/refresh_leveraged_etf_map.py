#!/usr/bin/env python3
"""Refresh 30-session liquidity fields in the supplied 2x ETF mapping."""

from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd


def metrics_from_history(history: pd.DataFrame) -> tuple[float, float, str] | None:
    sample = history.loc[:, ["Close", "Volume"]].dropna().tail(30)
    if sample.empty:
        return None
    return (
        float(sample["Volume"].mean()),
        float((sample["Close"] * sample["Volume"]).mean()),
        pd.Timestamp(sample.index[-1]).date().isoformat(),
    )


def download_histories(symbols: list[str]) -> dict[str, pd.DataFrame]:
    import yfinance as yf

    results: dict[str, pd.DataFrame] = {}
    for start in range(0, len(symbols), 80):
        batch = symbols[start:start + 80]
        data = yf.download(
            batch, period="3mo", interval="1d", auto_adjust=False,
            actions=False, group_by="ticker", threads=True, progress=False,
        )
        for symbol in batch:
            try:
                results[symbol] = data[symbol] if len(batch) > 1 else data
            except (KeyError, TypeError):
                continue
    return results


def refresh_map(mapping: pd.DataFrame, histories: dict[str, pd.DataFrame]) -> tuple[pd.DataFrame, list[str]]:
    refreshed = mapping.copy()
    failures: list[str] = []
    for index, row in refreshed.iterrows():
        symbol = str(row["Ticker"]).strip().upper()
        metrics = metrics_from_history(histories[symbol]) if symbol in histories else None
        if metrics is None:
            failures.append(symbol)
            continue
        average_volume, dollar_volume, updated = metrics
        refreshed.at[index, "Average Daily Volume"] = round(average_volume)
        refreshed.at[index, "Dollar Volume"] = round(dollar_volume)
        refreshed.at[index, "Date Last Updated"] = updated
    return refreshed, failures


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--map", type=Path, default=Path("data/us_leveraged_etf_map.csv"))
    args = parser.parse_args()
    mapping = pd.read_csv(args.map)
    symbols = sorted(mapping["Ticker"].dropna().astype(str).str.upper().str.strip().unique())
    refreshed, failures = refresh_map(mapping, download_histories(symbols))
    refreshed.to_csv(args.map, index=False)
    print(f"Refreshed {len(symbols) - len(set(failures)):,}/{len(symbols):,} ETF liquidity records.")
    if failures:
        print("Kept prior values for: " + ", ".join(sorted(set(failures))))


if __name__ == "__main__":
    main()
