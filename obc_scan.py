#!/usr/bin/env python3
"""Build Oversold Bounce Candidates from a separate, broad US stock universe."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime
from math import ceil
from pathlib import Path

import pandas as pd

from focus_list import _assign_exact_top_flags, _require_columns, fetch_universe, prepare_for_export


@dataclass(frozen=True)
class OBCSettings:
    min_dollar_volume: float = 30_000_000
    min_avg_volume_10d: int = 350_000
    one_year_top_pct: float = 0.10
    three_month_pullback_pct: float = 0.25


REQUIRED = (
    "name", "industry", "close", "SMA30", "SMA50", "ADRP", "ATRP",
    "Perf.3M", "Perf.Y", "average_volume_10d_calc", "average_volume_30d_calc",
)


def calculate_obc(raw: pd.DataFrame, settings: OBCSettings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return broad universe, one-year leaders, and their deepest 3M pullbacks."""
    _require_columns(raw, REQUIRED)
    frame = raw.copy()
    numeric = [column for column in REQUIRED if column not in {"name", "industry"}]
    for column in numeric:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    frame["average_dollar_volume_30d"] = frame["SMA30"] * frame["average_volume_30d_calc"]
    frame["atr_extension_from_50d"] = (frame["close"] - frame["SMA50"]) / (frame["SMA50"] * (frame["ATRP"] / 100))
    valid = (
        (frame[["close", "SMA30", "SMA50", "ATRP"]] > 0).all(axis=1)
        & frame[["Perf.3M", "Perf.Y"]].notna().all(axis=1)
        & (frame["average_dollar_volume_30d"] > settings.min_dollar_volume)
        & (frame["average_volume_10d_calc"] > settings.min_avg_volume_10d)
    )
    universe = frame.loc[valid].copy()
    if universe.empty:
        return universe, universe.copy(), universe.copy()

    leader_cutoff = min(len(universe), max(1, ceil(len(universe) * settings.one_year_top_pct)))
    _assign_exact_top_flags(universe, "Perf.Y", "perf_1y_rank", "is_top_1y", leader_cutoff)
    leaders = universe.loc[universe["is_top_1y"]].copy()
    pullback_cutoff = min(len(leaders), max(1, ceil(len(leaders) * settings.three_month_pullback_pct)))
    ordered = leaders.sort_values(["Perf.3M", "name"], ascending=[True, True], kind="stable")
    ranks = pd.Series(range(1, len(ordered) + 1), index=ordered.index, dtype="int64")
    leaders["perf_3m_pullback_rank"] = ranks
    leaders["is_obc"] = leaders["perf_3m_pullback_rank"] <= pullback_cutoff
    candidates = leaders.loc[leaders["is_obc"]].sort_values(["Perf.3M", "Perf.Y", "name"], ascending=[True, False, True])
    return universe.sort_values("Perf.Y", ascending=False), leaders.sort_values("Perf.Y", ascending=False), candidates


def write_outputs(universe: pd.DataFrame, leaders: pd.DataFrame, candidates: pd.DataFrame, settings: OBCSettings, output_dir: Path, snapshot_date: date) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = snapshot_date.isoformat()
    outputs = {
        "obc_universe": prepare_for_export(universe),
        "obc_one_year_leaders": prepare_for_export(leaders),
        "obc_candidates": prepare_for_export(candidates),
        "obc_settings": pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"]),
    }
    paths = []
    for name, frame in outputs.items():
        path = output_dir / f"{name}_{stamp}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Create Oversold Bounce Candidates.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, default=datetime.now().date())
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    args = parser.parse_args()
    settings = OBCSettings()
    universe, leaders, candidates = calculate_obc(fetch_universe(), settings)
    paths = write_outputs(universe, leaders, candidates, settings, args.output_dir, args.snapshot_date)
    print(f"OBC broad universe: {len(universe):,} | 1Y leaders: {len(leaders):,} | candidates: {len(candidates):,}")
    print("Saved:\n" + "\n".join(map(str, paths)))


if __name__ == "__main__":
    main()
