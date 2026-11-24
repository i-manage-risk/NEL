"""Local NEL 2.0 TradingView scanner and session scheduler."""
from __future__ import annotations

import json
import math
import sqlite3
import sys
from contextlib import closing
from datetime import datetime, time, timedelta
from pathlib import Path

import pandas as pd
from tradingview_screener import Query, col

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))
from scripts.run_after_close import NY_TZ, nyse_holidays  # noqa: E402

DB = Path(__file__).resolve().parent / ".local" / "custom-scans.sqlite3"
FIELDS = {
    "name": "symbol", "description": "company", "industry": "industry",
    "time": "bar_time", "close": "price", "open": "open", "volume": "volume",
    "market_cap_basic": "market_cap", "average_volume_10d_calc": "avg_volume",
    "change": "change", "Volatility.W": "volatility", "Perf.1M": "month", "ADRP": "adr",
    "EMA21": "ema21", "EMA50": "ema50", "EMA150": "ema150",
    "premarket_change": "gap", "premarket_time": "premarket_time",
}
SCANS = ("potent", "premarket", "leader")
BUCKETS = ("Leading", "Mediocre", "Lagging")
MIN_DOLLARS = 100_000_000
SUPER_DOLLARS = 500_000_000


def trading_day(day):
    # NYSE remains open on December 31 when New Year's Day falls on Saturday.
    return day.weekday() < 5 and (
        (day.month, day.day) == (12, 31) or day not in nyse_holidays(day.year)
    )


def adjacent_session(day, step):
    day += timedelta(days=step)
    while not trading_day(day):
        day += timedelta(days=step)
    return day


def close_time(day):
    early = (day.month, day.day) in {(7, 3), (12, 24)}
    early |= day.month == 11 and day.weekday() == 4 and 23 <= day.day <= 29
    return datetime.combine(day, time(13 if early else 16), NY_TZ)


def due(now):
    now = now.astimezone(NY_TZ)
    day = now.date()
    clock = now.time()
    if trading_day(day) and time(9) <= clock < time(9, 15):
        yield day, adjacent_session(day, -1), ("premarket",)
    if trading_day(day) and now >= close_time(day) + timedelta(minutes=20):
        close = day
    elif not trading_day(day) or clock < time(9, 15):
        close = adjacent_session(day, -1)
    else:
        return
    end_of_week = adjacent_session(close, 1).isocalendar()[:2] != close.isocalendar()[:2]
    yield close, close, ("potent", "leader") if end_of_week else ("potent",)


def connect(path=DB):
    path.parent.mkdir(parents=True, exist_ok=True)
    db = sqlite3.connect(path, timeout=10)
    db.executescript("""
        CREATE TABLE IF NOT EXISTS runs (
            scan TEXT, session TEXT, fetched TEXT, results TEXT,
            PRIMARY KEY (scan, session)
        );
        CREATE TABLE IF NOT EXISTS watch (
            ticker TEXT PRIMARY KEY, payload TEXT
        );
        CREATE TABLE IF NOT EXISTS scan_index_metrics (
            ticker TEXT, close TEXT, adr REAL, oscillator REAL, extension REAL,
            observations INTEGER, attempted REAL, PRIMARY KEY (ticker, close)
        );
        CREATE TABLE IF NOT EXISTS bucket_snapshots (
            session TEXT PRIMARY KEY, captured TEXT NOT NULL, payload TEXT NOT NULL
        );
    """)
    return db


def fetch_universe():
    query = (Query().set_markets("america").select(*FIELDS).where(
        col("type") == "stock",
    ).limit(20_000))
    total, frame = query.get_scanner_data(timeout=25)
    if not total or total != len(frame):
        raise RuntimeError(f"Incomplete TradingView universe ({len(frame)}/{total})")
    return frame.rename(columns=FIELDS)


def quote_window(now):
    return trading_day(now.date()) and time(9, 30) <= now.time() and now < close_time(now.date()) + timedelta(minutes=20)


def intraday_returns(tickers, session):
    """Read current regular-session changes without changing the scan snapshot."""
    fields = ["time", "close", "open", "change", "Perf.1M"]
    results = {}
    for offset in range(0, len(tickers), 200):
        batch = tickers[offset:offset + 200]
        _, frame = (Query().set_markets("america").set_tickers(*batch)
                    .select(*fields).limit(len(batch)).get_scanner_data(timeout=15))
        if frame.empty:
            continue
        frame = frame.rename(columns=FIELDS)
        stamp = pd.to_datetime(frame.bar_time, unit="s", utc=True, errors="coerce")
        frame = frame.loc[stamp.dt.tz_convert(NY_TZ).dt.date.eq(session)].copy()
        frame["from_open"] = (frame.price / frame.open.where(frame.open.gt(0)) - 1) * 100
        values = frame.set_index("ticker")[["change", "from_open", "month"]]
        results.update(json.loads(values.to_json(orient="index")))
    return results


def watch_tickers(path=DB):
    with closing(connect(path)) as db:
        return [ticker for (ticker,) in db.execute("SELECT ticker FROM watch ORDER BY ticker")]


def prepare(raw, close):
    rows = raw.copy().drop_duplicates("ticker")
    numeric = set(FIELDS.values()) - {"symbol", "company", "industry"}
    for field in numeric:
        rows[field] = pd.to_numeric(rows[field], errors="coerce").replace(
            [math.inf, -math.inf], float("nan")
        )
    bar_date = pd.to_datetime(rows.bar_time, unit="s", utc=True, errors="coerce").dt.tz_convert(NY_TZ).dt.date
    valid = rows.loc[bar_date.eq(close)].copy()
    if len(valid) <= len(rows) / 2:
        raise RuntimeError(f"TradingView has not returned a broad snapshot for {close}")
    valid["dollars"] = valid.price * valid.volume
    valid["from_open"] = (valid.price / valid.open.where(valid.open.gt(0)) - 1) * 100
    return valid.set_index("ticker", drop=False).rename_axis(None)


def passes_common_filters(rows):
    biotech = rows.industry.str.contains("biotech", case=False, na=False)
    # Compare prices directly to keep the ±0.5% boundaries exclusive.
    did_move = rows.open.gt(0) & (
        rows.price.gt(rows.open * 1.005 + 1e-9) | rows.price.lt(rows.open * .995 - 1e-9)
    )
    return ~biotech & did_move & rows.volatility.gt(3.5)


def scan(rows, name, session):
    eligible = rows.loc[
        rows.market_cap.gt(MIN_DOLLARS) & rows.dollars.gt(MIN_DOLLARS) & passes_common_filters(rows)
    ]
    if name == "leader":
        ranked = eligible.dropna(subset=["month"]).sort_values(["month", "ticker"], ascending=[False, True])
        return ranked.head(math.ceil(len(ranked) / 10))
    active = eligible.loc[eligible.avg_volume.gt(500_000)]
    if name == "premarket":
        quote_date = pd.to_datetime(active.premarket_time, unit="s", utc=True, errors="coerce").dt.tz_convert(NY_TZ).dt.date
        return active.loc[quote_date.eq(session) & active.gap.gt(4)].sort_values("gap", ascending=False)
    potent = active.price.gt(active.ema50) & active.price.ge(active.ema21)
    return active.loc[potent & active.change.gt(4)].sort_values("change", ascending=False)


def bucket(row):
    if row is None or any(pd.isna(row[field]) or row[field] <= 0 for field in ("price", "ema50", "ema150", "dollars")):
        return None, None
    price, ema50, ema150 = row.price, row.ema50, row.ema150
    direction = "Leading" if price > ema50 > ema150 else "Lagging" if price < ema50 < ema150 else "Mediocre"
    shelf = "Superliquid" if row.dollars >= SUPER_DOLLARS else "Liquid" if row.dollars > MIN_DOLLARS else None
    return direction, shelf


def save_bucket_snapshot(db, close, fetched, watch):
    # Morning additions belong to their own trading session, even when their
    # bucket is calculated from the prior session's completed daily bar.
    members = []
    for record in watch.values():
        sources = {name: session for name, session in record["sources"].items() if session <= close}
        if sources:
            members.append(dict(record, sources=sources))
    db.execute("INSERT OR IGNORE INTO bucket_snapshots VALUES (?, ?, ?)", (
        close, fetched, json.dumps(members),
    ))


def seed_current_snapshot(path=DB):
    # Preserve the first scan already collected before snapshot history was added.
    with closing(connect(path)) as db, db:
        row = db.execute("SELECT session, fetched FROM runs WHERE scan='potent' ORDER BY session DESC LIMIT 1").fetchone()
        if row:
            close, fetched = row
            watch = {ticker: json.loads(payload) for ticker, payload in db.execute("SELECT * FROM watch")}
            if all(record["close"] == close for record in watch.values()):
                save_bucket_snapshot(db, close, fetched, watch)


def run(session, close, names, path=DB):
    with closing(connect(path)) as db:
        pending = [name for name in names if not db.execute(
            "SELECT 1 FROM runs WHERE scan=? AND session=?", (name, session.isoformat())
        ).fetchone()]
        if not pending:
            return {}
        rows = prepare(fetch_universe(), close)
        fetched = datetime.now(NY_TZ).isoformat(timespec="seconds")
        matches = {name: scan(rows, name, session) for name in pending}
        db.execute("BEGIN IMMEDIATE")
        counts = {}
        watch = {ticker: json.loads(payload) for ticker, payload in db.execute("SELECT * FROM watch")}
        for name, result in matches.items():
            cursor = db.execute("INSERT OR IGNORE INTO runs VALUES (?, ?, ?, ?)", (
                name, session.isoformat(), fetched, result.to_json(orient="records"),
            ))
            if cursor.rowcount == 0:
                continue
            counts[name] = len(result)
            for ticker in result.index:
                record = watch.setdefault(ticker, {"ticker": ticker, "sources": {}})
                record["sources"][name] = max(record["sources"].get(name, ""), session.isoformat())
        if counts:
            for ticker, record in watch.items():
                if record.get("close", "") > close.isoformat():
                    continue
                row = rows.loc[ticker] if ticker in rows.index else None
                direction, shelf = bucket(row)
                record.update(bucket=direction, shelf=shelf, close=close.isoformat())
                record["values"] = json.loads(row.to_json()) if row is not None else None
                db.execute("INSERT OR REPLACE INTO watch VALUES (?, ?)", (ticker, json.dumps(record)))
        if "potent" in counts:
            save_bucket_snapshot(db, close.isoformat(), fetched, {
                ticker: record for ticker, record in watch.items() if record.get("close") == close.isoformat()
            })
        db.commit()
        return counts


def scan_snapshot(db):
    latest = {}
    for name in SCANS:
        row = db.execute(
            "SELECT session, fetched, results FROM runs WHERE scan=? ORDER BY session DESC LIMIT 1", (name,)
        ).fetchone()
        latest[name] = {"session": row[0], "fetched": row[1], "results": json.loads(row[2])} if row else None
    watch = [json.loads(payload) for (payload,) in db.execute("SELECT payload FROM watch ORDER BY ticker")]
    return latest, watch


def metric_rows(scans, watch):
    for row in watch:
        if row.get("values"):
            yield row["ticker"], row["close"], row["values"]
    for run in scans.values():
        for row in run["results"] if run else ():
            if row.get("bar_time"):
                close = datetime.fromtimestamp(row["bar_time"], NY_TZ).date().isoformat()
                yield row["ticker"], close, row


def metric_targets(scans, watch):
    return {(ticker, close) for ticker, close, _ in metric_rows(scans, watch)}


def bucket_comparison(db, watch, session):
    row = db.execute(
        "SELECT session, payload FROM bucket_snapshots WHERE session < ? ORDER BY session DESC LIMIT 1",
        (session.isoformat(),),
    ).fetchone()
    if row is None:
        return None
    baseline, payload = row
    previous = json.loads(payload)
    changes = {}
    for direction in (*BUCKETS, "Unclassified"):
        before = {item["ticker"] for item in previous if (item["bucket"] or "Unclassified") == direction}
        after = {item["ticker"] for item in watch if (item["bucket"] or "Unclassified") == direction}
        changes[direction] = {"entered": len(after - before), "left": len(before - after)}
    return {"baseline": baseline, "changes": changes}


def status(path=DB):
    with closing(connect(path)) as db:
        scans, watch = scan_snapshot(db)
        dates = sorted({close for _, close in metric_targets(scans, watch)})
        placeholders = ",".join("?" for _ in dates)
        metrics = {(ticker, close): values for ticker, close, *values in db.execute(
            f"SELECT ticker, close, adr, oscillator, extension, observations FROM scan_index_metrics WHERE close IN ({placeholders})",
            dates,
        )} if dates else {}
        for ticker, close, row in metric_rows(scans, watch):
            adr, oscillator, extension, observations = metrics.get((ticker, close), (None, None, None, None))
            if row.get("adr") is None:
                row["adr"] = adr
            row.update(atr_index=oscillator, atr_extension=extension, atr_observations=observations)
        session = datetime.now(NY_TZ).date()
        if not trading_day(session):
            session = adjacent_session(session, -1)
        return {"scans": scans, "watch": watch, "bucket_comparison": bucket_comparison(db, watch, session)}
