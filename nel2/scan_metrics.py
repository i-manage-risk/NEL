"""Completed-session range and signed historical ATR index for scan tickers."""
from collections import defaultdict
from contextlib import closing
from datetime import date, timedelta
import logging
import time

import pandas as pd
import yfinance as yf

from scanner import DB, connect, metric_targets, scan_snapshot
from index_history import calculate


def range_metrics(frame, close):
    """Use the same 50-day ATR Extension Index as the market dashboards."""
    if frame.empty:
        return None
    bars = frame.loc[:, ["High", "Low", "Close"]].dropna().sort_index()
    bars = bars.loc[bars.index.date <= close]
    if bars.empty or bars.index[-1].date() != close:
        return None
    high, low, prices = bars.High, bars.Low, bars.Close
    if prices.iloc[-1] <= 0:
        return None
    adr = (high - low).tail(14).mean() / prices.iloc[-1] * 100 if len(bars) >= 14 else None
    history = calculate(bars, through=close)
    if not history or history[-1]["date"] != close.isoformat():
        return None
    latest = history[-1]
    observations = sum(bar["extension"] is not None for bar in history)
    return adr, latest["oscillator"], latest["extension"], observations


def refresh_metrics(path=DB):
    with closing(connect(path)) as db:
        scans, watch = scan_snapshot(db)
        targets = metric_targets(scans, watch)
        cutoff = time.time() - 30 * 60
        ready = {(ticker, close) for ticker, close in db.execute(
            """SELECT ticker, close FROM scan_index_metrics
               WHERE observations IS NOT NULL OR attempted >= ?""", (cutoff,)
        )}
        pending = defaultdict(list)
        for ticker, close in sorted(targets - ready):
            pending[close].append(ticker)
        for stamp, tickers in pending.items():
            close = date.fromisoformat(stamp)
            for offset in range(0, len(tickers), 30):
                batch = tickers[offset:offset + 30]
                symbols = {ticker: ticker.split(":")[-1].replace(".", "-") for ticker in batch}
                end = close + timedelta(days=1)
                histories = yf.download(
                    sorted(set(symbols.values())), period="max", end=end,
                    auto_adjust=False, actions=False, group_by="ticker", threads=8,
                    progress=False, timeout=15,
                )
                records = []
                for ticker, symbol in symbols.items():
                    history = histories[symbol] if symbol in histories.columns.get_level_values(0) else pd.DataFrame()
                    values = range_metrics(history, close)
                    if values is None:
                        history = yf.Ticker(symbol).history(period="max", end=end, auto_adjust=False, actions=False, timeout=20)
                        values = range_metrics(history, close)
                    records.append((ticker, stamp, *(values or (None, None, None, None)), time.time()))
                with db:
                    db.executemany("""INSERT INTO scan_index_metrics VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(ticker,close) DO UPDATE SET adr=excluded.adr, oscillator=excluded.oscillator,
                        extension=excluded.extension, observations=excluded.observations, attempted=excluded.attempted
                        WHERE scan_index_metrics.observations IS NULL""", records)
                logging.info("Range and ATR history %s: %s/%s available", stamp, sum(row[5] is not None for row in records), len(batch))
