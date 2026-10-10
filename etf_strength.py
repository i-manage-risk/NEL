#!/usr/bin/env python3
"""Build fixed-universe theme and sector strength dashboards from yfinance."""

from __future__ import annotations

import argparse
import concurrent.futures
import json
import re
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import yfinance as yf

from scripts.run_after_close import NY_TZ, nyse_holidays


PROJECT_DIR = Path(__file__).resolve().parent
DATA_DIR = PROJECT_DIR / "data"
OUTPUT_DIR = PROJECT_DIR / "outputs" / "etf"
HOLDINGS_CACHE = DATA_DIR / "etf_holdings_cache.json"
WINDOWS = {"1w": 0, "1m": 1, "3m": 3, "6m": 6, "1y": 12}
GROUP_ALIASES = {"Oil & Gas": "Oil & gas"}
NON_STOCK_TERMS = {
    "CASH", "CURRENCY", "TREASURY", "BOND", "NOTE", "BILL", "SWAP", "FUTURE",
    "OPTION", "COLLATERAL", "REPO", "RECEIVABLE", "MARGIN", "FORWARD", "ETF", "FUND",
    "BITCOIN", "ETHER", "ETHEREUM", "SOLANA", "XRP", "ZCASH", "GOLD BULLION",
    "SILVER BULLION", "PALLADIUM", "PLATINUM",
}


@dataclass(frozen=True)
class UniverseConfig:
    source: Path
    key: str
    title: str
    top_n: int
    page: Path


UNIVERSES = (
    UniverseConfig(DATA_DIR / "theme_etfs.tsv", "themes", "Theme Leadership", 5, PROJECT_DIR / "themes.html"),
    UniverseConfig(DATA_DIR / "sector_etfs.tsv", "sectors", "Sector Leadership", 3, PROJECT_DIR / "sectors.html"),
)


def load_universe(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path, sep="\t").rename(columns=str.strip)
    required = {"Ticker", "Group", "Description"}
    missing = required.difference(frame.columns)
    if missing:
        raise ValueError(f"{path} is missing: {', '.join(sorted(missing))}")
    frame = frame.loc[:, ["Ticker", "Group", "Description"]].copy()
    frame["Ticker"] = frame["Ticker"].astype(str).str.strip().str.upper()
    frame["Group"] = frame["Group"].astype(str).str.strip().replace(GROUP_ALIASES)
    if frame["Ticker"].duplicated().any():
        duplicates = ", ".join(frame.loc[frame["Ticker"].duplicated(), "Ticker"])
        raise ValueError(f"Duplicate ETF ticker(s) in {path}: {duplicates}")
    return frame


def yahoo_symbol(symbol: str) -> str:
    symbol = str(symbol).strip().upper()
    # Yahoo uses a dash for U.S. class shares (BRK.B -> BRK-B), while dots in
    # international symbols are exchange suffixes and must be preserved.
    return symbol.replace(".", "-") if re.fullmatch(r"[A-Z]{1,5}\.[A-Z]", symbol) else symbol


def _extract_symbol_frame(downloaded: pd.DataFrame, symbol: str) -> pd.DataFrame:
    if isinstance(downloaded.columns, pd.MultiIndex):
        level_zero = set(downloaded.columns.get_level_values(0))
        frame = downloaded[symbol] if symbol in level_zero else downloaded.xs(symbol, axis=1, level=1)
    else:
        frame = downloaded
    renamed = {
        column: str(column).strip().lower().replace(" ", "_")
        for column in frame.columns
    }
    frame = frame.rename(columns=renamed)
    wanted = [column for column in ["open", "high", "low", "close", "adj_close", "volume"] if column in frame]
    result = frame.loc[:, wanted].copy()
    result.index = pd.to_datetime(result.index, utc=True).tz_convert(None).normalize()
    return result.loc[~result.index.duplicated(keep="last")].sort_index()


def download_prices(
    symbols: Iterable[str],
    start: date,
    end: date,
    chunk_size: int = 80,
) -> tuple[dict[str, pd.DataFrame], dict[str, str]]:
    """Batch-download raw and adjusted daily bars."""
    originals = sorted({str(symbol).strip().upper() for symbol in symbols if str(symbol).strip()})
    yahoo_to_original = {yahoo_symbol(symbol): symbol for symbol in originals}
    histories: dict[str, pd.DataFrame] = {}
    errors: dict[str, str] = {}

    def fetch_batch(batch: list[str]) -> None:
        if not batch:
            return
        try:
            downloaded = yf.download(
                batch,
                start=start.isoformat(),
                end=(end + timedelta(days=1)).isoformat(),
                auto_adjust=False,
                actions=False,
                group_by="ticker",
                threads=True,
                progress=False,
                timeout=25,
            )
        except Exception as error:
            for item in batch:
                errors[yahoo_to_original[item]] = str(error)
            return
        for item in batch:
            original = yahoo_to_original[item]
            try:
                frame = _extract_symbol_frame(downloaded, item).dropna(subset=["high", "low", "close"])
                if frame.empty:
                    raise ValueError("no daily bars returned")
                histories[original] = frame
                errors.pop(original, None)
            except (KeyError, TypeError, ValueError) as error:
                errors[original] = str(error)

    yahoo_symbols = list(yahoo_to_original)
    for offset in range(0, len(yahoo_symbols), chunk_size):
        fetch_batch(yahoo_symbols[offset:offset + chunk_size])
    return histories, errors


def wilder_average(values: pd.Series, period: int = 14) -> pd.Series:
    numeric = pd.to_numeric(values, errors="coerce").astype(float)
    result = pd.Series(float("nan"), index=numeric.index, dtype=float)
    if len(numeric) < period:
        return result
    result.iloc[period - 1] = numeric.iloc[:period].mean()
    for index in range(period, len(numeric)):
        result.iloc[index] = ((period - 1) * result.iloc[index - 1] + numeric.iloc[index]) / period
    return result


def _calendar_return(adjusted: pd.Series, months: int) -> pd.Series:
    values = []
    dates = adjusted.index
    for current_date, current_value in adjusted.items():
        target = current_date - pd.DateOffset(months=months)
        position = dates.searchsorted(target, side="right") - 1
        if position < 0 or not pd.notna(current_value) or adjusted.iloc[position] <= 0:
            values.append(float("nan"))
        else:
            values.append(100 * (current_value / adjusted.iloc[position] - 1))
    return pd.Series(values, index=dates, dtype=float)


def build_metric_history(history: pd.DataFrame) -> pd.DataFrame:
    """Calculate ETF performance, volatility, extension, and coil metrics for every bar."""
    frame = history.copy()
    for column in ["open", "high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame.get(column), errors="coerce")
    adjusted = pd.to_numeric(frame.get("adj_close", frame["close"]), errors="coerce")
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [
            frame["high"] - frame["low"],
            (frame["high"] - previous_close).abs(),
            (frame["low"] - previous_close).abs(),
        ], axis=1,
    ).max(axis=1)
    atr = wilder_average(true_range, 14)
    sma30 = frame["close"].rolling(30).mean()
    sma50 = frame["close"].rolling(50).mean()
    average_volume_10d = frame["volume"].rolling(10).mean()
    average_volume_30d = frame["volume"].rolling(30).mean()
    ema9 = frame["close"].ewm(span=9, adjust=False).mean()
    bar_range = frame["high"] - frame["low"]
    prior_max = bar_range.rolling(15).max().shift(1)
    prior_min = bar_range.rolling(15).min().shift(1)
    rmv_denominator = (prior_max - prior_min).where((prior_max - prior_min) != 0, 0.000001)
    rmv = (100 * (bar_range - prior_min) / rmv_denominator).clip(0, 100)
    close_spread_3 = 100 * (frame["close"].rolling(3).max() - frame["close"].rolling(3).min()) / frame["close"]
    close_spread_5 = 100 * (frame["close"].rolling(5).max() - frame["close"].rolling(5).min()) / frame["close"]
    coil_range_5 = (frame["high"].rolling(5).max() - frame["low"].rolling(5).min()) / atr
    ratio_3 = true_range.rolling(3).mean() / true_range.shift(3).rolling(10).mean()
    ratio_5 = true_range.rolling(5).mean() / true_range.shift(5).rolling(10).mean()
    current_range_pct = 100 * bar_range / atr.shift(1)
    three_day = (close_spread_3 <= 2.5) & (ratio_3 <= 0.85)
    five_day = (close_spread_5 <= 4.0) & (ratio_5 <= 0.85)
    common = (frame["close"] > ema9) & (coil_range_5 <= 2.5) & (current_range_pct < 100)
    is_tight = common & (three_day | five_day)
    coil_setup = pd.Series("", index=frame.index, dtype=object)
    coil_setup.loc[three_day & ~five_day] = "3D"
    coil_setup.loc[five_day & ~three_day] = "5D"
    coil_setup.loc[three_day & five_day] = "3D + 5D"

    metrics = pd.DataFrame(index=frame.index)
    metrics["close"] = frame["close"]
    metrics["adrp"] = 100 * (frame["high"].rolling(14).mean() - frame["low"].rolling(14).mean()) / frame["close"]
    metrics["atrp"] = 100 * atr / frame["close"]
    metrics["average_volume_10d"] = average_volume_10d
    metrics["average_dollar_volume_30d"] = sma30 * average_volume_30d
    metrics["extension"] = (frame["close"] - sma50) / (sma50 * (metrics["atrp"] / 100))
    metrics["perf_1m"] = _calendar_return(adjusted, 1)
    metrics["perf_3m"] = _calendar_return(adjusted, 3)
    metrics["perf_6m"] = _calendar_return(adjusted, 6)
    metrics["perf_1y"] = _calendar_return(adjusted, 12)
    metrics["perf_1w"] = 100 * (adjusted / adjusted.shift(5) - 1)
    metrics["intraday_change"] = 100 * (frame["close"] / frame["open"] - 1)
    metrics["close_to_close_change"] = 100 * (adjusted / adjusted.shift(1) - 1)
    metrics["is_tight"] = is_tight.fillna(False)
    metrics["coil_setup"] = coil_setup
    metrics["rmv_15d"] = rmv
    return metrics


def expected_completed_session(now: datetime | None = None) -> date:
    now = now or datetime.now(NY_TZ)
    candidate = now.date()
    if (now.hour, now.minute) < (16, 25):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in nyse_holidays(candidate.year):
        candidate -= timedelta(days=1)
    return candidate


def validate_completed_session(close_date: date, now: datetime | None = None) -> None:
    latest_completed = expected_completed_session(now)
    if close_date > latest_completed:
        raise RuntimeError(
            f"{close_date} is not a completed regular market session yet. "
            f"The latest completed close is {latest_completed}."
        )


def validate_actual_close(histories: dict[str, pd.DataFrame], close_date: date) -> None:
    spy = histories.get("SPY")
    if spy is None or spy.empty:
        raise RuntimeError("Cannot verify the completed market close because SPY history is unavailable.")
    latest = spy.index.max().date()
    if latest < close_date:
        raise RuntimeError(
            f"Yahoo daily data is stale: expected the {close_date} close, but SPY ends at {latest}. "
            "The next scheduled run will retry."
        )


def validate_universe_coverage(histories: dict[str, pd.DataFrame], symbols: Iterable[str], minimum: float = 0.95) -> None:
    expected = {str(symbol).upper() for symbol in symbols}
    available = expected.intersection(histories)
    coverage = len(available) / max(1, len(expected))
    if coverage < minimum:
        missing = ", ".join(sorted(expected.difference(available)))
        raise RuntimeError(
            f"Yahoo returned only {coverage:.1%} of the fixed ETF universe; refusing to publish an incomplete ranking. "
            f"Missing: {missing}"
        )


def _clean_number(value) -> float | None:
    return round(float(value), 4) if pd.notna(value) else None


def _metric_record(row: pd.Series, metadata: pd.Series, performance_column: str, symbol: str) -> dict:
    return {
        "symbol": symbol,
        "group": metadata["Group"],
        "description": metadata["Description"],
        "performance": _clean_number(row[performance_column]),
        "adrp": _clean_number(row["adrp"]),
        "atrp": _clean_number(row["atrp"]),
        "average_volume_10d": _clean_number(row["average_volume_10d"]),
        "average_dollar_volume_30d": _clean_number(row["average_dollar_volume_30d"]),
        "extension": _clean_number(row["extension"]),
        "is_tight": bool(row["is_tight"]),
        "coil_setup": str(row["coil_setup"] or ""),
        "rmv_15d": _clean_number(row["rmv_15d"]),
    }


def rank_groups_for_session(
    metric_histories: dict[str, pd.DataFrame],
    universe: pd.DataFrame,
    session: date,
    performance_column: str,
    top_n: int,
) -> list[dict]:
    date_key = pd.Timestamp(session)
    rows = []
    metadata_by_ticker = universe.set_index("Ticker")
    for ticker, metadata in metadata_by_ticker.iterrows():
        history = metric_histories.get(ticker)
        if history is None or date_key not in history.index:
            continue
        row = history.loc[date_key]
        if pd.isna(row[performance_column]) or pd.isna(row["extension"]):
            continue
        rows.append({"ticker": ticker, "group": metadata["Group"], "row": row, "metadata": metadata})
    if not rows:
        return []

    performance = pd.Series({item["ticker"]: item["row"][performance_column] for item in rows})
    percentiles = performance.rank(method="average", pct=True) * 100
    grouped: dict[str, list[dict]] = {}
    for item in rows:
        item["percentile"] = float(percentiles[item["ticker"]])
        grouped.setdefault(item["group"], []).append(item)

    ranked = []
    for group, members in grouped.items():
        scores = pd.Series([member["percentile"] for member in members])
        performances = pd.Series([member["row"][performance_column] for member in members])
        group_score = 0.7 * scores.median() + 0.3 * scores.max()
        ordered = sorted(members, key=lambda item: item["row"][performance_column], reverse=True)
        ranked.append(
            {
                "group": group,
                "score": round(float(group_score), 2),
                "median_performance": round(float(performances.median()), 2),
                "best_performance": round(float(performances.max()), 2),
                "confirmation": int((scores >= 80).sum()),
                "member_count": len(members),
                "leader_etf": ordered[0]["ticker"],
                "members": [
                    _metric_record(member["row"], member["metadata"], performance_column, member["ticker"])
                    for member in ordered
                ],
            }
        )
    ranked.sort(key=lambda group: (group["score"], group["median_performance"], group["best_performance"]), reverse=True)
    for rank, group in enumerate(ranked, start=1):
        group["rank"] = rank
    return ranked[:top_n]


def build_snapshots(
    metric_histories: dict[str, pd.DataFrame],
    universe: pd.DataFrame,
    session_dates: Iterable[date],
    top_n: int,
    include_leadership: bool = True,
) -> list[dict]:
    snapshots = []
    metadata_by_ticker = universe.set_index("Ticker")
    for session in session_dates:
        windows = {}
        leadership = {}
        for label in WINDOWS:
            all_groups = rank_groups_for_session(
                metric_histories,
                universe,
                session,
                f"perf_{label}",
                len(universe) if include_leadership else top_n,
            )
            windows[label] = all_groups[:top_n]
            if include_leadership:
                leadership[label] = [
                    {"group": group["group"], "score": group["score"]}
                    for group in all_groups
                ]
        date_key = pd.Timestamp(session)
        daily_changes = []
        for ticker, metadata in metadata_by_ticker.iterrows():
            history = metric_histories.get(ticker)
            if history is None or date_key not in history.index:
                daily_changes.append(
                    {
                        "symbol": ticker,
                        "group": metadata["Group"],
                        "intraday": None,
                        "one_day": None,
                        "one_week": None,
                        "one_month": None,
                        "three_months": None,
                        "six_months": None,
                        "one_year": None,
                    }
                )
                continue
            row = history.loc[date_key]
            daily_changes.append(
                {
                    "symbol": ticker,
                    "group": metadata["Group"],
                    "intraday": _clean_number(row.get("intraday_change")),
                    "one_day": _clean_number(row.get("close_to_close_change")),
                    "one_week": _clean_number(row.get("perf_1w")),
                    "one_month": _clean_number(row.get("perf_1m")),
                    "three_months": _clean_number(row.get("perf_3m")),
                    "six_months": _clean_number(row.get("perf_6m")),
                    "one_year": _clean_number(row.get("perf_1y")),
                }
            )
        snapshot = {"date": session.isoformat(), "windows": windows, "daily_changes": daily_changes}
        if include_leadership:
            snapshot["leadership"] = leadership
        snapshots.append(snapshot)
    return snapshots


def _is_stock_holding(symbol: str, name: str, known_funds: set[str]) -> bool:
    symbol = str(symbol).strip().upper()
    name_upper = str(name).upper()
    if not symbol or symbol in known_funds or not re.fullmatch(r"[A-Z0-9][A-Z0-9.\-]{0,14}", symbol):
        return False
    return not any(term in name_upper or term == symbol for term in NON_STOCK_TERMS)


def fetch_fund_holdings(symbol: str, known_funds: set[str]) -> list[dict]:
    try:
        holdings = yf.Ticker(yahoo_symbol(symbol)).funds_data.top_holdings
        if holdings is None or holdings.empty:
            return []
        records = []
        for holding_symbol, row in holdings.reset_index().set_index("Symbol").iterrows():
            name = str(row.get("Name", ""))
            if not _is_stock_holding(holding_symbol, name, known_funds):
                continue
            weight = pd.to_numeric(row.get("Holding Percent"), errors="coerce")
            if pd.isna(weight):
                continue
            records.append({"symbol": str(holding_symbol).upper(), "name": name, "weight": float(weight)})
        return records[:10]
    except Exception:
        return []


def load_or_refresh_holdings(universe_symbols: Iterable[str], as_of: date, refresh_days: int = 7) -> dict:
    known_funds = {str(symbol).upper() for symbol in universe_symbols}
    cached = {"as_of": None, "funds": {}}
    if HOLDINGS_CACHE.exists():
        try:
            cached = json.loads(HOLDINGS_CACHE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    cache_date = date.fromisoformat(cached["as_of"]) if cached.get("as_of") else None
    if cache_date and (as_of - cache_date).days < refresh_days and cached.get("funds"):
        return cached

    old_funds = cached.get("funds", {})
    refreshed: dict[str, list[dict]] = {}
    symbols = sorted(known_funds)
    with concurrent.futures.ThreadPoolExecutor(max_workers=6) as pool:
        futures = {pool.submit(fetch_fund_holdings, symbol, known_funds): symbol for symbol in symbols}
        for future in concurrent.futures.as_completed(futures):
            symbol = futures[future]
            holdings = future.result()
            refreshed[symbol] = holdings if holdings else old_funds.get(symbol, [])
    result = {"as_of": as_of.isoformat(), "funds": refreshed}
    HOLDINGS_CACHE.write_text(json.dumps(result, indent=2, sort_keys=True), encoding="utf-8")
    return result


def latest_holding_stats(history: pd.DataFrame, as_of: date) -> dict | None:
    frame = history.loc[history.index <= pd.Timestamp(as_of)].copy()
    if len(frame) < 50:
        return None
    for column in ["high", "low", "close", "volume"]:
        frame[column] = pd.to_numeric(frame[column], errors="coerce")
    previous_close = frame["close"].shift(1)
    true_range = pd.concat(
        [frame["high"] - frame["low"], (frame["high"] - previous_close).abs(), (frame["low"] - previous_close).abs()],
        axis=1,
    ).max(axis=1)
    atr = wilder_average(true_range, 14).iloc[-1]
    close = frame["close"].iloc[-1]
    sma30 = frame["close"].rolling(30).mean().iloc[-1]
    sma50 = frame["close"].rolling(50).mean().iloc[-1]
    average_volume_30d = frame["volume"].rolling(30).mean().iloc[-1]
    if not all(pd.notna(value) and value > 0 for value in [atr, close, sma30, sma50, average_volume_30d]):
        return None
    atrp = 100 * atr / close
    extension = (close - sma50) / (sma50 * (atrp / 100))
    return {
        "average_dollar_volume_30d": round(float(sma30 * average_volume_30d), 2),
        "extension": round(float(extension), 3),
    }


def enrich_holdings(
    holdings_cache: dict,
    close_date: date,
    active_funds: set[str],
) -> dict[str, list[dict]]:
    funds = holdings_cache.get("funds", {})
    # A dollar-volume label is only truthful for U.S.-listed holdings. Keep
    # international stocks visible but leave their USD statistic blank.
    symbols = sorted({
        item["symbol"]
        for fund, items in funds.items() if fund in active_funds
        for item in items
        if "." not in item["symbol"] and ":" not in item["symbol"]
    })
    start = close_date - timedelta(days=150)
    histories, _ = download_prices(symbols, start, close_date, chunk_size=40)
    stats = {symbol: latest_holding_stats(history, close_date) for symbol, history in histories.items()}
    enriched = {}
    for fund, items in funds.items():
        enriched[fund] = [{**item, **(stats.get(item["symbol"]) or {})} for item in items]
    return enriched


def build_universe_payload(
    config: UniverseConfig,
    universe: pd.DataFrame,
    histories: dict[str, pd.DataFrame],
    close_date: date,
    holdings: dict[str, list[dict]],
    holdings_as_of: str,
) -> dict:
    metric_histories = {
        ticker: build_metric_history(history)
        for ticker, history in histories.items()
        if ticker in set(universe["Ticker"])
    }
    spy = histories["SPY"]
    session_dates = [
        timestamp.date() for timestamp in spy.index
        if date(close_date.year, 1, 1) <= timestamp.date() <= close_date
    ]
    return {
        "kind": config.key,
        "title": config.title,
        "top_n": config.top_n,
        "generated_for": close_date.isoformat(),
        "holdings_as_of": holdings_as_of,
        "snapshots": build_snapshots(
            metric_histories,
            universe,
            session_dates,
            config.top_n,
            include_leadership=config.key == "sectors",
        ),
        "holdings": {ticker: holdings.get(ticker, []) for ticker in universe["Ticker"]},
    }


def write_payload(config: UniverseConfig, payload: dict) -> Path:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    destination = OUTPUT_DIR / f"{config.key}_snapshots.json"
    destination.write_text(json.dumps(payload, separators=(",", ":")), encoding="utf-8")
    return destination


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Build theme and sector ETF strength datasets.")
    parser.add_argument("--close-date", type=date.fromisoformat, help="Completed market session date (YYYY-MM-DD).")
    parser.add_argument("--skip-holdings-refresh", action="store_true", help="Reuse the existing holdings cache even if old.")
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    close_date = args.close_date or expected_completed_session()
    validate_completed_session(close_date)
    universes = {config.key: load_universe(config.source) for config in UNIVERSES}
    all_etfs = sorted({ticker for universe in universes.values() for ticker in universe["Ticker"]})
    # A 12-month return for the first January session needs the corresponding
    # January session from the prior year. Keep all of the prior calendar year
    # so every YTD snapshot can populate the 1-year window.
    history_start = date(close_date.year - 1, 1, 1)
    histories, errors = download_prices([*all_etfs, "SPY"], history_start, close_date)
    validate_actual_close(histories, close_date)
    validate_universe_coverage(histories, all_etfs)

    refresh_days = 100_000 if args.skip_holdings_refresh else 7
    holdings_cache = load_or_refresh_holdings(all_etfs, close_date, refresh_days=refresh_days)
    plain_holdings = holdings_cache.get("funds", {})
    payloads = {}
    for config in UNIVERSES:
        payload = build_universe_payload(
            config,
            universes[config.key],
            histories,
            close_date,
            plain_holdings,
            holdings_cache["as_of"],
        )
        payloads[config.key] = payload

    active_funds = {
        member["symbol"]
        for payload in payloads.values()
        for groups in payload["snapshots"][-1]["windows"].values()
        for group in groups
        for member in group["members"]
    }
    enriched_holdings = enrich_holdings(holdings_cache, close_date, active_funds)
    for config in UNIVERSES:
        payload = payloads[config.key]
        for ticker in active_funds:
            if ticker in payload["holdings"]:
                payload["holdings"][ticker] = enriched_holdings.get(ticker, payload["holdings"][ticker])
        path = write_payload(config, payload)
        print(f"Saved {path} with {len(payload['snapshots'])} daily snapshots")
    from etf_dashboard import write_etf_dashboards
    for path in write_etf_dashboards():
        print(f"Saved {path}")
    if errors:
        print(f"Warning: price history unavailable for {len(errors)} ETF(s): {', '.join(sorted(errors))}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
