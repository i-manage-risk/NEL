#!/usr/bin/env python3
"""Build a daily, non-extended momentum-leader focus list from TradingView."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import datetime
from math import ceil
from pathlib import Path
from typing import Iterable

import pandas as pd

from industry_flow_dashboard import write_dashboard


@dataclass(frozen=True)
class Settings:
    min_dollar_volume: float = 30_000_000
    min_adr_pct: float = 4.0
    min_avg_volume_10d: int = 350_000
    top_pct: float = 0.01
    max_atr_extension: float = 4.0


SCAN_COLUMNS = [
    "name",
    "description",
    "exchange",
    "industry",
    "close",
    "SMA30",
    "SMA50",
    "ADRP",
    "ATRP",
    "Perf.1M",
    "Perf.3M",
    "Perf.6M",
    "average_volume_10d_calc",
    "average_volume_30d_calc",
]


def fetch_universe() -> pd.DataFrame:
    """Fetch a broad US stock universe; exact liquidity filtering happens locally.

    Keeping the dollar-volume expression out of the server-side query avoids
    depending on TradingView expression support and makes the output auditable.
    """
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error

    query = (
        Query()
        .set_markets("america")
        .select(*SCAN_COLUMNS)
        .where(
            col("type") == "stock",
            col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
            col("average_volume_10d_calc") > 0,
        )
        .limit(5_000)
    )
    _, frame = query.get_scanner_data()
    return frame


def _require_columns(frame: pd.DataFrame, columns: Iterable[str]) -> None:
    missing = sorted(set(columns).difference(frame.columns))
    if missing:
        raise ValueError(
            "TradingView did not return required column(s): " + ", ".join(missing)
        )


def _assign_exact_top_flags(frame: pd.DataFrame, metric: str, rank_column: str, flag_column: str, cutoff: int) -> None:
    """Assign deterministic ranks and an exact-size top group for one metric."""
    ordered = frame.sort_values([metric, "name"], ascending=[False, True], kind="stable")
    ranks = pd.Series(range(1, len(ordered) + 1), index=ordered.index, dtype="int64")
    frame[rank_column] = ranks
    frame[flag_column] = frame[rank_column] <= cutoff


def calculate_nel(raw: pd.DataFrame, settings: Settings) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return the eligible universe, leaders, and non-extended leaders (NEL)."""
    _require_columns(raw, ["name", "industry", "close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M", "Perf.6M", "average_volume_10d_calc", "average_volume_30d_calc"])
    df = raw.copy()
    numeric = ["close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M", "Perf.6M", "average_volume_10d_calc", "average_volume_30d_calc"]
    for column in numeric:
        df[column] = pd.to_numeric(df[column], errors="coerce")

    # ADRP and ATRP are TradingView's daily 14-period percentage indicators.
    # ADRP is used only for the initial activity filter. ATRP feeds the
    # extension calculation exactly as in your manual spreadsheet.
    df["dollar_volume_30d"] = df["close"] * df["average_volume_30d_calc"]
    df["average_dollar_volume_30d"] = df["SMA30"] * df["average_volume_30d_calc"]
    df["atr_extension_from_50d"] = (df["close"] - df["SMA50"]) / (
        df["SMA50"] * (df["ATRP"] / 100)
    )

    valid_industry = ~df["industry"].fillna("").str.contains("biotech", case=False, regex=False)
    valid_metrics = (df[["close", "SMA30", "SMA50", "ADRP", "ATRP"]] > 0).all(axis=1)
    has_performance = df[["Perf.1M", "Perf.3M", "Perf.6M"]].notna().all(axis=1)
    universe = df.loc[
        valid_industry
        & valid_metrics
        & has_performance
        & (df["average_dollar_volume_30d"] > settings.min_dollar_volume)
        & (df["ADRP"] > settings.min_adr_pct)
        & (df["average_volume_10d_calc"] > settings.min_avg_volume_10d)
    ].copy()

    if universe.empty:
        return universe, universe.copy(), universe.copy()

    cutoff = max(1, ceil(len(universe) * settings.top_pct))
    _assign_exact_top_flags(universe, "Perf.1M", "perf_1m_rank", "is_top_1m", cutoff)
    _assign_exact_top_flags(universe, "Perf.3M", "perf_3m_rank", "is_top_3m", cutoff)
    _assign_exact_top_flags(universe, "Perf.6M", "perf_6m_rank", "is_top_6m", cutoff)
    universe["momentum_score"] = universe[["Perf.1M", "Perf.3M", "Perf.6M"]].mean(axis=1)

    # Combine the three leader groups. A symbol can lead in more than one
    # timeframe but appears only once in the final leader list.
    leaders = pd.concat(
        [
            universe.loc[universe["is_top_1m"]],
            universe.loc[universe["is_top_3m"]],
            universe.loc[universe["is_top_6m"]],
        ],
        ignore_index=True,
    ).drop_duplicates(subset="name", keep="first")
    nel = leaders.loc[
        leaders["atr_extension_from_50d"] <= settings.max_atr_extension
    ].copy()
    sort_order = ["momentum_score", "Perf.1M", "Perf.3M", "Perf.6M"]
    leaders.sort_values(sort_order, ascending=False, inplace=True)
    nel.sort_values(sort_order, ascending=False, inplace=True)
    return universe.sort_values("momentum_score", ascending=False), leaders, nel


def prepare_for_export(frame: pd.DataFrame) -> pd.DataFrame:
    """Order and round the columns so the daily review sheet is scan-friendly."""
    preferred = [
        "name", "description", "exchange", "industry", "close", "SMA30", "SMA50", "ADRP", "ATRP",
        "average_volume_10d_calc", "average_volume_30d_calc", "dollar_volume_30d", "average_dollar_volume_30d",
        "Perf.1M", "perf_1m_rank", "Perf.3M", "perf_3m_rank", "Perf.6M", "perf_6m_rank",
        "momentum_score", "atr_extension_from_50d", "is_top_1m", "is_top_3m", "is_top_6m",
    ]
    columns = [column for column in preferred if column in frame.columns]
    result = frame.loc[:, columns].copy()
    return result.round({
        "close": 2, "SMA30": 2, "SMA50": 2, "ADRP": 2, "ATRP": 2,
        "dollar_volume_30d": 0, "average_dollar_volume_30d": 0, "Perf.1M": 2, "Perf.3M": 2, "Perf.6M": 2,
        "momentum_score": 2, "atr_extension_from_50d": 2,
    })


def write_outputs(universe: pd.DataFrame, leaders: pd.DataFrame, nel: pd.DataFrame, settings: Settings, output_dir: Path) -> list[Path]:
    """Write each review view as a plain CSV file."""
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = datetime.now().strftime("%Y-%m-%d")
    settings_frame = pd.DataFrame(list(asdict(settings).items()), columns=["setting", "value"])
    outputs = {
        "non_extended_leaders": prepare_for_export(nel),
        "nel_symbols": nel.loc[:, ["name"]].rename(columns={"name": "symbol"}),
        "momentum_leaders": prepare_for_export(leaders),
        "filtered_universe": prepare_for_export(universe),
        "settings": settings_frame,
    }
    paths = []
    for name, frame in outputs.items():
        destination = export_dir if name == "nel_symbols" else output_dir
        path = destination / f"{name}_{stamp}.csv"
        frame.to_csv(path, index=False)
        paths.append(path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create a non-extended leader (NEL) list.")
    parser.add_argument("--min-adr-pct", type=float, default=4.0, help="Minimum TradingView ADR%% (default: 4).")
    parser.add_argument("--top-pct", type=float, default=0.05, help="Top share from each 1-, 3-, and 6-month ranking before deduplication (default: 0.05).")
    parser.add_argument("--max-extension", type=float, default=4.0, help="Maximum ATRs extended from SMA50 (default: 4).")
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"), help="CSV output directory.")
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    if not 0 < args.top_pct <= 1:
        raise SystemExit("--top-pct must be greater than 0 and no more than 1.")
    if args.min_adr_pct < 0:
        raise SystemExit("--min-adr-pct cannot be negative.")
    settings = Settings(min_adr_pct=args.min_adr_pct, top_pct=args.top_pct, max_atr_extension=args.max_extension)
    raw = fetch_universe()
    universe, leaders, nel = calculate_nel(raw, settings)
    paths = write_outputs(universe, leaders, nel, settings, args.output_dir)
    paths.append(write_dashboard(args.output_dir))
    print(f"Scanned: {len(raw):,} | eligible: {len(universe):,} | leaders: {len(leaders):,} | NEL: {len(nel):,}")
    print("Saved:\n" + "\n".join(str(path) for path in paths))


if __name__ == "__main__":
    main()
