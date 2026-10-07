#!/usr/bin/env python3
"""Build Super Liquid leaders from $1B stocks and their liquid 2x ETFs."""

from __future__ import annotations

import argparse
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from pathlib import Path

import pandas as pd

from focus_list import SCAN_COLUMNS, Settings, prepare_for_export, rank_and_filter_leaders
from etf_strength import build_metric_history, download_prices
from industry_flow_dashboard import write_dashboard
from tight_nel import CoilSettings, find_tight_nel


@dataclass(frozen=True)
class SuperLiquidSettings(Settings):
    min_dollar_volume: float = 1_000_000_000
    min_adr_pct: float = 4.0
    min_avg_volume_10d: int = 350_000
    top_pct: float = 0.05
    max_atr_extension: float = 4.0
    min_etf_avg_volume_30d: int = 1_000_000
    leaders_per_window: int = 10


NUMERIC = [
    "close", "SMA30", "SMA50", "ADRP", "ATRP", "Perf.1M", "Perf.3M",
    "Perf.6M", "Perf.Y", "average_volume_10d_calc", "average_volume_30d_calc",
]


def fetch_tradingview(instrument_type: str = "stock") -> pd.DataFrame:
    try:
        from tradingview_screener import Query, col
    except ImportError as error:
        raise SystemExit("Missing dependency. Run: pip install -r requirements.txt") from error
    query = (
        Query().set_markets("america").select(*SCAN_COLUMNS).where(
            col("type") == instrument_type,
            col("exchange").isin(["NASDAQ", "NYSE", "AMEX"]),
            col("average_volume_10d_calc") > 0,
        ).limit(8_000)
    )
    _, frame = query.get_scanner_data()
    return frame


def mapped_symbols_for_underlyings(
    raw_stocks: pd.DataFrame, mapping: pd.DataFrame, settings: SuperLiquidSettings
) -> list[str]:
    stocks = add_metrics(raw_stocks)
    performance = ["Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y"]
    eligible = stocks.loc[
        ~stocks["industry"].fillna("").str.contains("biotech", case=False, regex=False)
        & (stocks[["close", "SMA30", "SMA50", "ATRP"]] > 0).all(axis=1)
        & stocks[performance].notna().all(axis=1)
        & (stocks["average_dollar_volume_30d"] > settings.min_dollar_volume)
        & (stocks["average_volume_10d_calc"] > settings.min_avg_volume_10d),
        "name",
    ]
    wanted = set(eligible.astype(str).str.upper())
    return sorted(mapping.loc[mapping["Underlying Ticker"].astype(str).str.upper().isin(wanted), "Ticker"].astype(str).str.upper().unique())


def fetch_mapped_etfs(symbols: list[str]) -> pd.DataFrame:
    """Build TradingView-compatible rows from regular-session Yahoo bars."""
    if not symbols:
        return pd.DataFrame(columns=SCAN_COLUMNS)
    histories, errors = download_prices(symbols, date.today() - timedelta(days=500), date.today(), chunk_size=60)
    rows = []
    for symbol in symbols:
        history = histories.get(symbol)
        if history is None or len(history) < 30:
            continue
        metrics = build_metric_history(history).iloc[-1]
        rows.append({
            "name": symbol, "description": f"2x leveraged ETF for {symbol}", "exchange": "US",
            "industry": "", "close": metrics["close"],
            "SMA30": history["close"].rolling(30).mean().iloc[-1],
            "SMA50": history["close"].rolling(50).mean().iloc[-1],
            "ADRP": metrics["adrp"], "ATRP": metrics["atrp"],
            "Perf.1M": metrics["perf_1m"], "Perf.3M": metrics["perf_3m"],
            "Perf.6M": metrics["perf_6m"], "Perf.Y": metrics["perf_1y"],
            "average_volume_10d_calc": history["volume"].rolling(10).mean().iloc[-1],
            "average_volume_30d_calc": history["volume"].rolling(30).mean().iloc[-1],
        })
    if errors:
        print(f"Warning: Yahoo history unavailable for {len(errors)} mapped ETF(s).")
    return pd.DataFrame(rows, columns=SCAN_COLUMNS)


def add_metrics(raw: pd.DataFrame) -> pd.DataFrame:
    frame = raw.copy()
    for column in NUMERIC:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    frame["dollar_volume_30d"] = frame["close"] * frame["average_volume_30d_calc"]
    frame["average_dollar_volume_30d"] = frame["SMA30"] * frame["average_volume_30d_calc"]
    frame["atr_extension_from_50d"] = (frame["close"] - frame["SMA50"]) / (
        frame["SMA50"] * (frame["ATRP"] / 100)
    )
    return frame


def calculate_super_liquid(
    raw_stocks: pd.DataFrame,
    raw_etfs: pd.DataFrame,
    mapping: pd.DataFrame,
    settings: SuperLiquidSettings,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Return eligible underlyings, candidate instruments, leaders and S-NEL."""
    stocks = add_metrics(raw_stocks)
    etfs = add_metrics(raw_etfs)
    performance = ["Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y"]
    valid_stock = (
        ~stocks["industry"].fillna("").str.contains("biotech", case=False, regex=False)
        & (stocks[["close", "SMA30", "SMA50", "ATRP"]] > 0).all(axis=1)
        & stocks[performance].notna().all(axis=1)
        & (stocks["average_dollar_volume_30d"] > settings.min_dollar_volume)
        & (stocks["average_volume_10d_calc"] > settings.min_avg_volume_10d)
    )
    underlyings = stocks.loc[valid_stock].copy()
    map_frame = mapping.rename(columns={"Underlying Ticker": "underlying", "Ticker": "name"}).copy()
    map_frame["underlying"] = map_frame["underlying"].astype(str).str.upper().str.strip()
    map_frame["name"] = map_frame["name"].astype(str).str.upper().str.strip()
    mapped = map_frame.loc[map_frame["underlying"].isin(set(underlyings["name"]))]
    eligible_etfs = etfs.loc[etfs["name"].isin(set(mapped["name"]))].merge(
        mapped[["underlying", "name"]], on="name", how="inner"
    )
    valid_etf = (
        (eligible_etfs[["close", "ADRP", "ATRP"]] > 0).all(axis=1)
        & (eligible_etfs["ADRP"] > settings.min_adr_pct)
        & (eligible_etfs["average_volume_30d_calc"] > settings.min_etf_avg_volume_30d)
    )
    eligible_etfs = eligible_etfs.loc[valid_etf].sort_values(
        ["underlying", "average_volume_30d_calc", "name"], ascending=[True, False, True]
    ).drop_duplicates("underlying", keep="first")
    paired = eligible_etfs.set_index("underlying")["name"]
    candidates = underlyings.loc[
        (underlyings["ADRP"] > settings.min_adr_pct)
        | underlyings["name"].isin(set(eligible_etfs["underlying"]))
    ].copy()
    candidates["underlying"] = candidates["name"]
    candidates["paired_etf"] = candidates["name"].map(paired)
    candidates["instrument_type"] = "Stock"
    ranked, leaders, nel = rank_and_filter_leaders(candidates, settings)
    return underlyings, ranked, leaders, nel


def write_outputs(universe, leaders, nel, tight, settings, output_dir: Path, snapshot_date: date) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    export_dir = output_dir / "EXPORT"
    export_dir.mkdir(exist_ok=True)
    stamp = snapshot_date.isoformat()
    frames = {
        "super_liquid_filtered_universe": prepare_for_export(universe),
        "super_liquid_momentum_leaders": prepare_for_export(leaders),
        "super_liquid_non_extended_leaders": prepare_for_export(nel),
        "super_liquid_tight_non_extended_leaders": prepare_for_export(tight),
        "super_liquid_settings": pd.DataFrame(
            list(asdict(settings).items()) + [(f"tight_{k}", v) for k, v in asdict(CoilSettings()).items()],
            columns=["setting", "value"],
        ),
    }
    exports = {
        "super_liquid_nel_symbols": nel[["name"]].rename(columns={"name": "symbol"}),
        "super_liquid_tight_nel_symbols": tight[["name"]].rename(columns={"name": "symbol"}),
    }
    paths: list[Path] = []
    for name, frame in frames.items():
        path = output_dir / f"{name}_{stamp}.csv"
        frame.to_csv(path, index=False); paths.append(path)
    for name, frame in exports.items():
        path = export_dir / f"{name}_{stamp}.csv"
        frame.to_csv(path, index=False); paths.append(path)
    return paths


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Create the Super Liquid leader dashboard.")
    parser.add_argument("--snapshot-date", type=date.fromisoformat, default=datetime.now().date())
    parser.add_argument("--output-dir", type=Path, default=Path("outputs"))
    parser.add_argument("--map", type=Path, default=Path("data/us_leveraged_etf_map.csv"))
    parser.add_argument("--top-pct", type=float, default=0.05)
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = SuperLiquidSettings(top_pct=args.top_pct)
    mapping = pd.read_csv(args.map)
    stocks = fetch_tradingview("stock")
    etf_symbols = mapped_symbols_for_underlyings(stocks, mapping, settings)
    etfs = fetch_mapped_etfs(etf_symbols)
    underlyings, universe, leaders, nel = calculate_super_liquid(stocks, etfs, mapping, settings)
    tight, errors = find_tight_nel(nel)
    paths = write_outputs(universe, leaders, nel, tight, settings, args.output_dir, args.snapshot_date)
    paths.append(write_dashboard(args.output_dir, profile="super"))
    print(
        f"$1B underlyings: {len(underlyings):,} | eligible instruments: {len(universe):,} "
        f"({universe.paired_etf.notna().sum():,} with 2x ETFs) | leaders: {len(leaders):,} "
        f"| S-NEL: {len(nel):,} | Tight: {len(tight):,}"
    )
    if errors:
        print(f"Warning: tightness history unavailable for {len(errors)} symbol(s).")
    print("Saved:\n" + "\n".join(map(str, paths)))


if __name__ == "__main__":
    main()
