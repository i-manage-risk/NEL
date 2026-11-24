"""Run the local scanner dashboard and check the schedule once a minute."""
import argparse
import json
import logging
from contextlib import closing
from datetime import date, datetime
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from threading import Event, Thread
from urllib.parse import parse_qs, urlsplit

from scan_metrics import refresh_metrics
from scanner import NY_TZ, archived_watchlist, connect, due, intraday_returns, quote_window, run, seed_current_snapshot, status, watch_tickers

ROOT = Path(__file__).resolve().parents[1]
PAGES = {"/", "/index.html", "/workspace.html", "/breadth.html", "/themes.html",
         "/sectors.html", "/industry_flow_dashboard.html", "/super-liquid.html"}


quote_snapshot = None


def schedule_quotes(stop):
    global quote_snapshot
    while not stop.is_set():
        now = datetime.now(NY_TZ)
        session = now.date()
        if quote_snapshot and quote_snapshot["session"] != session.isoformat():
            quote_snapshot = None
        if quote_window(now):
            try:
                rows = intraday_returns(watch_tickers(), session)
                if rows:
                    quote_snapshot = {"session": session.isoformat(), "rows": rows, "fetched": now.isoformat(timespec="seconds")}
            except Exception:
                logging.exception("Scan quote refresh failed.")
        stop.wait(60)


def tick():
    for session, close, names in due(datetime.now(NY_TZ)):
        try:
            counts = run(session, close, names)
            if counts:
                logging.info("%s | market close %s | %s", session, close, counts)
        except Exception:
            logging.exception("Scan failed for %s (%s). Will retry while the window is open.", session, ", ".join(names))


def schedule(stop):
    while not stop.is_set():
        tick()
        stop.wait(60)


def schedule_metrics(stop):
    while not stop.is_set():
        try:
            refresh_metrics()
        except Exception:
            logging.exception("Scan metric refresh failed.")
        stop.wait(300)


class Handler(SimpleHTTPRequestHandler):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ROOT), **kwargs)

    def public_file(self):
        path = urlsplit(self.path).path
        if path in PAGES:
            return True
        request = Path(self.translate_path(path))
        directory = {"/assets/": "assets", "/outputs/": "outputs"}
        return any(path.startswith(prefix) and request.resolve().is_relative_to(ROOT / name)
                   and request.is_file()
                   and not any(part.startswith(".") for part in request.relative_to(ROOT).parts)
                   and (name != "outputs" or request.suffix in {".json", ".csv", ".txt"})
                   for prefix, name in directory.items())

    def do_GET(self):
        url = urlsplit(self.path)
        if url.path == "/api/scans":
            query = parse_qs(url.query)
            if "close" in query:
                try:
                    close = date.fromisoformat(query["close"][0]).isoformat()
                except ValueError:
                    self.send_error(400)
                    return
                with closing(connect()) as db:
                    snapshot = archived_watchlist(db, close)
                if snapshot is None:
                    self.send_error(404)
                    return
            else:
                snapshot = dict(status(), quotes=quote_snapshot)
            body = json.dumps(snapshot).encode()
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(body)))
            self.send_header("Cache-Control", "no-store")
            self.end_headers()
            self.wfile.write(body)
        elif self.public_file():
            super().do_GET()
        else:
            self.send_error(404)

    def do_HEAD(self):
        if self.public_file():
            super().do_HEAD()
        else:
            self.send_error(404)

    def log_message(self, format, *args):
        if self.path != "/api/scans":
            super().log_message(format, *args)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--port", type=int, default=8765)
    parser.add_argument("--once", action="store_true", help="Run any due scans and exit")
    args = parser.parse_args()
    logging.basicConfig(level=logging.INFO, format="%(asctime)s %(message)s")
    seed_current_snapshot()
    if args.once:
        tick()
        refresh_metrics()
    else:
        stop = Event()
        with ThreadingHTTPServer(("127.0.0.1", args.port), Handler) as server:
            Thread(target=schedule, args=(stop,), daemon=True).start()
            Thread(target=schedule_metrics, args=(stop,), daemon=True).start()
            Thread(target=schedule_quotes, args=(stop,), daemon=True).start()
            print(f"NEL 2.0 · http://127.0.0.1:{server.server_port}", flush=True)
            try:
                server.serve_forever()
            finally:
                stop.set()
