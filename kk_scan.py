#!/usr/bin/env python3
"""Build the KK Liquid Leaders universe without changing the original NEL scan.

KK starts with liquidity only.  Leadership is then the union of the exact top
2% of that universe by 1-, 3-, and 6-month performance.  ADR and extension
are deliberately retained as fields for the dashboard, rather than being
used to decide who is a leader.
"""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime
from math import ceil
from pathlib import Path

import pandas as pd

from focus_list import SCAN_COLUMNS, _assign_exact_top_flags, _require_columns, prepare_for_export


@dataclass(frozen=True)
class KKSettings:
    min_dollar_volume: float = 30_000_000
    min_avg_volume_10d: int = 350_000
    top_pct: float = 0.02


METRICS = ("Perf.1M", "Perf.3M", "Perf.6M")
EMA_COLUMNS = ("EMA9", "EMA9|1W", "EMA9|1M")
KK_SCAN_COLUMNS = [*SCAN_COLUMNS, *EMA_COLUMNS]
NUMERIC = (
    "close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M",
    "Perf.6M", "average_volume_10d_calc", "average_volume_30d_calc",
)


def fetch_kk_universe() -> pd.DataFrame:
    """Fetch the broad stock universe plus the three trend references."""
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error
    query = (
        Query().set_markets("america").select(*KK_SCAN_COLUMNS).where(
            col("type") == "stock",
            col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
            col("average_volume_10d_calc") > 0,
        ).limit(5_000)
    )
    _, frame = query.get_scanner_data()
    return frame


def calculate_kk(raw: pd.DataFrame, settings: KKSettings) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Return liquidity-qualified stocks and the deduplicated KK leader union."""
    _require_columns(raw, ["name", "industry", *NUMERIC])
    frame = raw.copy()
    for column in NUMERIC:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    for column in EMA_COLUMNS:
        if column not in frame:
            frame[column] = pd.NA
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["dollar_volume_30d"] = frame["close"] * frame["average_volume_30d_calc"]
    frame["average_dollar_volume_30d"] = frame["SMA30"] * frame["average_volume_30d_calc"]
    frame["atr_extension_from_50d"] = (frame["close"] - frame["SMA50"]) / (
        frame["SMA50"] * (frame["ATRP"] / 100)
    )
    frame["above_ema9d"] = frame["close"] > frame["EMA9"]
    frame["above_ema9w"] = frame["close"] > frame["EMA9|1W"]
    frame["above_ema9m"] = frame["close"] > frame["EMA9|1M"]

    valid_metrics = (frame[["close", "SMA30", "SMA50", "ATRP"]] > 0).all(axis=1)
    has_performance = frame[list(METRICS)].notna().all(axis=1)
    # This is intentionally the only eligibility filter. ADR and extension are
    # post-selection screener controls, not prerequisites for being a leader.
    universe = frame.loc[
        valid_metrics
        & has_performance
        & (frame["average_dollar_volume_30d"] >= settings.min_dollar_volume)
        & (frame["average_volume_10d_calc"] >= settings.min_avg_volume_10d)
    ].copy()
    if universe.empty:
        return universe, universe.copy()

    cutoff = min(len(universe), max(1, ceil(len(universe) * settings.top_pct)))
    flags = []
    for metric, rank, flag in (
        ("Perf.1M", "perf_1m_rank", "is_top_1m"),
        ("Perf.3M", "perf_3m_rank", "is_top_3m"),
        ("Perf.6M", "perf_6m_rank", "is_top_6m"),
    ):
        _assign_exact_top_flags(universe, metric, rank, flag, cutoff)
        flags.append(flag)
    universe["momentum_score"] = universe[list(METRICS)].mean(axis=1)
    leaders = pd.concat([universe.loc[universe[flag]] for flag in flags], ignore_index=True)
    leaders = leaders.drop_duplicates(subset="name", keep="first")
    leaders.sort_values(["momentum_score", "Perf.1M", "Perf.3M", "Perf.6M", "name"], ascending=[False, False, False, False, True], inplace=True)
    universe.sort_values("momentum_score", ascending=False, inplace=True)
    return universe, leaders


def write_outputs(universe: pd.DataFrame, leaders: pd.DataFrame, settings: KKSettings, output_dir: Path, snapshot_date: date) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = snapshot_date.isoformat()
    outputs = {
        "kk_liquid_universe": prepare_for_export(universe),
        "kk_liquid_leaders": prepare_for_export(leaders),
        "kk_settings": pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"]),
    }
    paths = []
    for name, frame in outputs.items():
        path = output_dir / f"{name}_{stamp}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the KK Liquid Leaders scan.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, default=datetime.now().date())
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--top-pct", type=float, default=0.02)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.top_pct <= 1:
        raise SystemExit("--top-pct must be greater than 0 and no more than 1.")
    settings = KKSettings(top_pct=args.top_pct)
    universe, leaders = calculate_kk(fetch_kk_universe(), settings)
    paths = write_outputs(universe, leaders, settings, args.output_dir, args.snapshot_date)
    print(f"KK liquidity universe: {len(universe):,} | top {settings.top_pct:.0%} union: {len(leaders):,}")
    print("Saved:\n" + "\n".join(map(str, paths)))


if __name__ == "__main__":
    main()
