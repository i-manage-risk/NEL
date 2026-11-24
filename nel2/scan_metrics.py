"""Completed-session range and signed historical ATR index for scan tickers."""
from collections import defaultdict
from contextlib import closing
from datetime import date, timedelta
import json
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


def chart_bars(frame, close):
    if frame.empty:
        return []
    bars = frame.loc[:, ["Open", "High", "Low", "Close"]].dropna().sort_index()
    bars = bars.loc[bars.index.date <= close].tail(90)
    if bars.empty or bars.index[-1].date() != close:
        return []
    return [[stamp.date().isoformat(), *(round(value, 4) for value in row)]
            for stamp, row in zip(bars.index, bars.to_numpy())]


def refresh_metrics(path=DB):
    with closing(connect(path)) as db:
        scans, watch = scan_snapshot(db)
        targets = metric_targets(scans, watch)
        cutoff = time.time() - 30 * 60
        ready = {(ticker, close) for ticker, close in db.execute(
            """SELECT m.ticker, m.close FROM scan_index_metrics AS m
               LEFT JOIN scan_chart_history AS h USING (ticker, close)
               WHERE (m.observations IS NOT NULL AND h.ticker IS NOT NULL) OR m.attempted >= ?""", (cutoff,)
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
                records, charts = [], []
                for ticker, symbol in symbols.items():
                    history = histories[symbol] if symbol in histories.columns.get_level_values(0) else pd.DataFrame()
                    values = range_metrics(history, close)
                    if values is None:
                        history = yf.Ticker(symbol).history(period="max", end=end, auto_adjust=False, actions=False, timeout=20)
                        values = range_metrics(history, close)
                    records.append((ticker, stamp, *(values or (None, None, None, None)), time.time()))
                    bars = chart_bars(history, close)
                    if bars:
                        charts.append((ticker, stamp, json.dumps(bars, separators=(",", ":"))))
                with db:
                    db.executemany("""INSERT INTO scan_index_metrics VALUES (?,?,?,?,?,?,?)
                        ON CONFLICT(ticker,close) DO UPDATE SET adr=coalesce(excluded.adr,scan_index_metrics.adr),
                        oscillator=coalesce(excluded.oscillator,scan_index_metrics.oscillator),
                        extension=coalesce(excluded.extension,scan_index_metrics.extension),
                        observations=coalesce(excluded.observations,scan_index_metrics.observations),
                        attempted=excluded.attempted""", records)
                    db.executemany("INSERT OR IGNORE INTO scan_chart_history VALUES (?,?,?)", charts)
                logging.info("Range and ATR history %s: %s/%s available", stamp, sum(row[5] is not None for row in records), len(batch))
