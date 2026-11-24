"""Publish the scanner's durable watchlist and display snapshot for GitHub Pages."""
from contextlib import closing
from datetime import datetime
import json
import logging
from pathlib import Path
import tempfile

from scan_metrics import refresh_metrics
from scanner import DB, NY_TZ, ROOT, archived_watchlist, connect, due, intraday_returns, metric_rows, quote_window, run, status

OUTPUT = ROOT / "outputs" / "scan_watchlist.json"
HISTORY = ROOT / "outputs" / "scan_bucket_history"


def restore(payload, path, history=HISTORY):
    """Restore the active watchlist, latest runs and metric cache into a fresh database."""
    scans, watch = payload.get("scans", {}), payload.get("watch", [])
    with closing(connect(path)) as db, db:
        db.executemany(
            "INSERT INTO runs VALUES (?, ?, ?, ?)",
            [(name, item["session"], item["fetched"], json.dumps(item["results"]))
             for name, item in scans.items() if item],
        )
        db.executemany("INSERT INTO watch VALUES (?, ?)", [
            (row["ticker"], json.dumps(row)) for row in watch
        ])
        metrics = {}
        for archive in sorted(history.glob("*.json"))[-3:]:
            snapshot = json.loads(archive.read_text())
            members = snapshot["members"]
            db.execute("INSERT INTO bucket_snapshots VALUES (?, ?, ?)", (
                archive.stem, snapshot["captured"], json.dumps(members),
            ))
            db.executemany("INSERT INTO scan_chart_history VALUES (?,?,?)", [
                (ticker, archive.stem, json.dumps(bars))
                for ticker, bars in snapshot.get("charts", {}).items()
            ])
            store_metrics(metrics, metric_rows({}, members))
        store_metrics(metrics, metric_rows(scans, watch))
        db.executemany("INSERT INTO scan_index_metrics VALUES (?,?,?,?,?,?,0)", [
            (ticker, close, *values) for (ticker, close), values in metrics.items()
        ])


def store_metrics(metrics, rows):
    for ticker, close, row in rows:
        if row.get("atr_observations") is not None:
            metrics[ticker, close] = (
                row.get("adr"), row.get("atr_index"), row.get("atr_extension"), row["atr_observations"],
            )


def save_json(path, data):
    path.parent.mkdir(parents=True, exist_ok=True)
    body = json.dumps(data, separators=(",", ":"), allow_nan=False) + "\n"
    if not path.exists() or path.read_text() != body:
        staged = path.with_suffix(".tmp")
        staged.write_text(body)
        staged.replace(path)


def save_history(path, history=HISTORY):
    """Archive watchlist rows, measures and daily candles as of each close."""
    with closing(connect(path)) as db:
        for (session,) in db.execute("SELECT session FROM bucket_snapshots ORDER BY session"):
            target = history / f"{session}.json"
            snapshot = archived_watchlist(db, session)
            if target.exists():
                previous = json.loads(target.read_text())
                if snapshot["bucket_comparison"] is None:
                    snapshot["bucket_comparison"] = previous.get("bucket_comparison")
            save_json(target, snapshot)


def publish_snapshot(path, quotes=None, output=OUTPUT, history=HISTORY):
    snapshot = status(path)
    if not any(snapshot["scans"].values()):
        raise RuntimeError("No completed scans are available to publish")
    save_history(path, history)
    snapshot["history_dates"] = sorted(archive.stem for archive in history.glob("*.json"))
    save_json(output, dict(snapshot, quotes=quotes))


def refresh():
    now = datetime.now(NY_TZ)
    previous = json.loads(OUTPUT.read_text()) if OUTPUT.exists() else {}
    scheduled = list(due(now))
    update_quotes = quote_window(now)
    if not scheduled and not update_quotes:
        print("Outside the scan and quote collection windows.")
        return 0
    failed = False
    with tempfile.TemporaryDirectory() as scratch:
        path = Path(scratch) / "watchlist.sqlite3"
        restore(previous, path)
        for session, close, names in scheduled:
            try:
                print(f"{session} | close {close} | {run(session, close, names, path)}")
            except Exception:
                failed = True
                logging.exception("Could not capture %s for %s", ", ".join(names), session)
        snapshot = status(path)
        quote = previous.get("quotes")
        latest_close = max((row["close"] for row in snapshot["watch"]), default="")
        if quote and quote["session"] <= latest_close:
            quote = None
        if update_quotes and snapshot["watch"] and now.date().isoformat() > latest_close:
            try:
                rows = intraday_returns([item["ticker"] for item in snapshot["watch"]], now.date())
                if rows and (not quote or quote["session"] != now.date().isoformat() or quote["rows"] != rows or not quote.get("fetched")):
                    quote = {"session": now.date().isoformat(), "rows": rows, "fetched": now.isoformat(timespec="seconds")}
            except Exception:
                failed = True
                logging.exception("Could not refresh watchlist returns")
        if scheduled:
            try:
                refresh_metrics(path)
            except Exception:
                failed = True
                logging.exception("Could not refresh ATR history")
        publish_snapshot(path, quote)
    return int(failed)


if __name__ == "__main__":
    import argparse
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--seed-local", action="store_true", help="Export today's existing local scanner database")
    args = parser.parse_args()
    if args.seed_local:
        publish_snapshot(DB)
    else:
        raise SystemExit(refresh())
