#!/usr/bin/env python3
"""Local Webull-backed RVOL/ATR dashboard. No order submission code."""

from __future__ import annotations

import json
import math
import os
import sys
import threading
import time
import webbrowser
from datetime import datetime, timedelta, timezone
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from urllib.parse import urlparse
from zoneinfo import ZoneInfo

from webull.core.client import ApiClient
from webull.data.common.category import Category
from webull.data.common.timespan import Timespan
from webull.data.data_client import DataClient

# A PyInstaller one-file build extracts Python code to a temporary directory.
# Keep user configuration beside the executable instead of in that directory.
ROOT = Path(sys.executable).resolve().parent if getattr(sys, "frozen", False) else Path(__file__).resolve().parent
NY = ZoneInfo("America/New_York")
MAX_SYMBOLS = 20
RVOL_THRESHOLD = 30.0
ATR_THRESHOLD = 68.0
DEFAULT_SYMBOLS = ["MSTR", "BLSH", "NTSK", "ORKA", "PSNL", "APPN", "BAND", "CORT", "GCT", "ETON", "DOCS", "PAY", "APPS", "BB", "WIX", "ZETA", "EOSE", "CRSR"]


def load_env() -> None:
    candidates = []
    custom = os.getenv("WEBULL_CONFIG_FILE")
    if custom:
        candidates.append(Path(custom))
    candidates.extend([ROOT / ".env", Path("/private/tmp/webull-dashboard.env")])
    for path in candidates:
        if not path.exists():
            continue
        for raw in path.read_text().splitlines():
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip().strip('"').strip("'"))
        break


def parse_time(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%dT%H:%M:%S.%f%z")


def number(value, default=math.nan):
    try:
        return float(value)
    except (TypeError, ValueError):
        return default


def json_safe(value):
    """Replace non-finite floats so one incomplete symbol cannot break the API."""
    if isinstance(value, float) and not math.isfinite(value):
        return None
    if isinstance(value, dict):
        return {key: json_safe(item) for key, item in value.items()}
    if isinstance(value, list):
        return [json_safe(item) for item in value]
    return value


def wilder_atr(bars: list[dict], length: int = 14) -> float:
    bars = sorted(bars, key=lambda b: b["dt"])
    trs = []
    previous_close = None
    for bar in bars:
        high, low, close = bar["high"], bar["low"], bar["close"]
        tr = high - low if previous_close is None else max(high - low, abs(high - previous_close), abs(low - previous_close))
        trs.append(tr)
        previous_close = close
    if len(trs) < length:
        return math.nan
    atr = sum(trs[:length]) / length
    for tr in trs[length:]:
        atr = ((atr * (length - 1)) + tr) / length
    return atr


class DashboardEngine:
    def __init__(self):
        load_env()
        key = os.getenv("WEBULL_APP_KEY")
        secret = os.getenv("WEBULL_APP_SECRET")
        if not key or not secret:
            raise RuntimeError("Missing WEBULL_APP_KEY or WEBULL_APP_SECRET. Copy .env.example to .env and fill it locally.")
        self.region = os.getenv("WEBULL_REGION", "us")
        self.environment = os.getenv("WEBULL_ENV", "paper").lower()
        host = "api.sandbox.webull.com" if self.environment == "paper" else "api.webull.com"
        host = os.getenv("WEBULL_API_HOST", host)
        api = ApiClient(key, secret, self.region)
        api.add_endpoint(self.region, host)
        self.market = DataClient(api).market_data
        self.symbols = DEFAULT_SYMBOLS.copy()
        self.lock = threading.Lock()
        self.daily_cache: dict[str, list[dict]] = {}
        self.daily_cache_time = 0.0
        self.snapshot: dict = {"rows": [], "updatedAt": None, "error": None}
        self.last_refresh = 0.0

    def set_symbols(self, symbols: list[str]) -> None:
        cleaned = []
        for symbol in symbols:
            value = symbol.strip().upper().split(":")[-1]
            if value and value not in cleaned:
                cleaned.append(value)
        with self.lock:
            self.symbols = cleaned[:MAX_SYMBOLS]
            self.daily_cache = {}
            self.last_refresh = 0

    @staticmethod
    def unpack_batch(body: dict) -> dict[str, list[dict]]:
        result = {}
        for group in body.get("result", []):
            symbol = group.get("symbol")
            bars = []
            for raw in group.get("result", []):
                try:
                    bars.append({
                        "dt": parse_time(raw["time"]),
                        "open": number(raw["open"]),
                        "high": number(raw["high"]),
                        "low": number(raw["low"]),
                        "close": number(raw["close"]),
                        "volume": number(raw["volume"], 0),
                    })
                except (KeyError, ValueError):
                    continue
            if symbol:
                result[symbol] = bars
        return result

    def request_batch(self, symbols: list[str], span: str, count: str, sessions=None) -> dict[str, list[dict]]:
        response = self.market.get_batch_history_bar(symbols, Category.US_STOCK.name, span, count=count, trading_sessions=sessions)
        if response.status_code != 200:
            raise RuntimeError(f"Webull returned HTTP {response.status_code}: {response.text[:240]}")
        return self.unpack_batch(response.json())

    def refresh(self, force=False) -> dict:
        now_monotonic = time.monotonic()
        with self.lock:
            if not force and now_monotonic - self.last_refresh < 8 and self.snapshot["rows"]:
                return self.snapshot
            symbols = self.symbols.copy()
        if not symbols:
            return {"rows": [], "updatedAt": datetime.now(timezone.utc).isoformat(), "error": None, "environment": self.environment}
        try:
            if not self.daily_cache or now_monotonic - self.daily_cache_time > 300:
                # Use a long warm-up so Wilder's recursive ATR converges to the
                # value produced by Webull's continuously running ind.atr(14).
                self.daily_cache = self.request_batch(symbols, Timespan.D.name, "500")
                self.daily_cache_time = now_monotonic
            minutes = self.request_batch(symbols, Timespan.M1.name, "1200", ["RTH"])
            rows = [self.calculate(symbol, self.daily_cache.get(symbol, []), minutes.get(symbol, [])) for symbol in symbols]
            rows = [row for row in rows if row is not None]
            rows.sort(key=lambda r: (-r["rvol"], r["range"]))
            result = {
                "rows": rows,
                "updatedAt": datetime.now(timezone.utc).isoformat(),
                "environment": self.environment,
                "error": None,
            }
        except Exception as exc:
            result = {**self.snapshot, "error": str(exc), "environment": self.environment}
        with self.lock:
            self.snapshot = result
            self.last_refresh = now_monotonic
        return result

    def calculate(self, symbol: str, daily: list[dict], minute: list[dict]):
        if len(daily) < 50 or not minute:
            return None
        minute = sorted(minute, key=lambda b: b["dt"])
        latest_session_date = minute[-1]["dt"].astimezone(NY).date()
        session = [b for b in minute if b["dt"].astimezone(NY).date() == latest_session_date]
        if not session:
            return None
        current = {
            "dt": session[-1]["dt"],
            "open": session[0]["open"],
            "high": max(b["high"] for b in session),
            "low": min(b["low"] for b in session),
            "close": session[-1]["close"],
            "volume": sum(b["volume"] for b in session),
        }
        prior = sorted([b for b in daily if b["dt"].astimezone(NY).date() < latest_session_date], key=lambda b: b["dt"])
        if len(prior) < 49:
            return None
        combined = prior + [current]
        atr = wilder_atr(combined[-80:], 14)
        average_volume = sum([b["volume"] for b in prior[-49:]] + [current["volume"]]) / 50
        rvol = round(current["volume"] / average_volume * 100) if average_volume > 0 else math.nan
        lod = round(100 * (current["close"] - current["low"]) / atr) if atr > 0 else math.nan
        range_pct = round(100 * (current["high"] - current["low"]) / atr) if atr > 0 else math.nan
        pdh = current["close"] > prior[-1]["high"]

        first = session[0]
        opening5 = session[:5]
        opening15 = session[:15]
        opening30 = session[:30]
        first_low_broke = current["low"] < first["low"]
        five_low = min(b["low"] for b in opening5)
        five_low_broke = len(session) >= 6 and current["low"] < five_low
        valid_or = 30 if five_low_broke else 15 if first_low_broke else 5
        source = opening5 if valid_or == 5 else opening15 if valid_or == 15 else opening30
        ready = len(session) >= valid_or
        valid_orh = max(b["high"] for b in source) if ready and len(source) == valid_or else math.nan
        above_orh = None if math.isnan(valid_orh) else current["close"] > valid_orh

        latest_close = session[-1]["dt"] + timedelta(minutes=1)
        delay = max(0, int((datetime.now(timezone.utc) - latest_close.astimezone(timezone.utc)).total_seconds() // 60))
        qualifies = rvol > RVOL_THRESHOLD and lod < ATR_THRESHOLD and range_pct < ATR_THRESHOLD and pdh
        return {
            "symbol": symbol, "rvol": rvol, "lod": lod, "range": range_pct,
            "pdh": pdh, "or": valid_or, "aboveOrh": above_orh, "delay": delay,
            "price": current["close"], "sessionDate": str(latest_session_date), "qualifies": qualifies,
        }


HTML = r'''<!doctype html><html><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1">
<title>Focus List Dashboard</title><style>
:root{color-scheme:dark;--cream:#F4F2E8;--dark:#141414;--light:#2A2A2A;--green:#00C853;--red:#FF3B30;--muted:#9b9b95}
*{box-sizing:border-box}body{margin:0;background:#080808;color:var(--cream);font:14px -apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}.shell{max-width:1120px;margin:48px auto;padding:0 20px}.top{display:flex;justify-content:space-between;align-items:end;gap:20px;margin-bottom:14px}.eyebrow{color:var(--muted);font-size:12px;letter-spacing:.1em;text-transform:uppercase}.title{font-size:25px;font-weight:750;margin-top:3px}.status{text-align:right;color:var(--muted);font-variant-numeric:tabular-nums}.controls{display:flex;gap:8px;margin:12px 0}.controls input{flex:1;background:#171717;border:1px solid #333;color:var(--cream);padding:10px 12px;border-radius:7px}.controls button{border:0;border-radius:7px;padding:10px 15px;background:var(--cream);color:#000;font-weight:700;cursor:pointer}.error{display:none;background:#471816;color:#ffaaa4;padding:10px 12px;margin-bottom:10px;border-radius:6px}.table-wrap{overflow:auto;border-radius:8px}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th{background:var(--cream);color:#000;text-align:center;padding:10px 13px;font-weight:800;white-space:nowrap}th:first-child,td:first-child{text-align:left}td{text-align:center;padding:9px 13px;white-space:nowrap}tbody tr:nth-child(odd){background:var(--dark)}tbody tr:nth-child(even){background:var(--light)}.green{color:var(--green)}.red{color:var(--red)}.cream{color:var(--cream)}.qualified{background:var(--green)!important;color:#000!important;font-weight:800}.symbol{font-weight:750}.foot{margin-top:10px;color:var(--muted);font-size:12px}.empty{text-align:center!important;padding:30px}</style></head>
<body><main class="shell"><div class="top"><div><div class="eyebrow">Webull OpenAPI</div><div class="title">Focus List</div></div><div class="status"><div id="env">—</div><div id="updated">Loading…</div></div></div>
<div class="controls"><input id="symbols" spellcheck="false" placeholder="AAPL, MSFT, NVDA"><button onclick="saveWatchlist()">Update</button></div><div id="error" class="error"></div>
<div class="table-wrap"><table><thead><tr><th>Symbol</th><th>RVOL</th><th>LoD</th><th>Range</th><th>PDH</th><th>OR</th><th>P &gt; ORH</th><th>Delay</th></tr></thead><tbody id="body"><tr><td colspan="8" class="empty">Loading Webull data…</td></tr></tbody></table></div>
<div class="foot">RTH only · RVOL 50D · ATR 14 · auto-refresh every 10 seconds</div></main><script>
const cls=(ok)=>ok?'green':'red'; const pct=(v)=>Number.isFinite(v)?`${v}%`:'—';
async function load(){try{const r=await fetch('/api/data');const d=await r.json();document.getElementById('env').textContent=(d.environment||'').toUpperCase();document.getElementById('updated').textContent=d.updatedAt?`Updated ${new Date(d.updatedAt).toLocaleTimeString()}`:'—';const e=document.getElementById('error');e.style.display=d.error?'block':'none';e.textContent=d.error||'';const b=document.getElementById('body');if(!d.rows?.length){b.innerHTML='<tr><td colspan="8" class="empty">No valid rows yet</td></tr>';return}b.innerHTML=d.rows.map(x=>`<tr><td class="symbol ${x.qualifies?'qualified':''}">${x.symbol}</td><td class="${cls(x.rvol>30)}">${pct(x.rvol)}</td><td class="${cls(x.lod<68)}">${pct(x.lod)}</td><td class="${cls(x.range<68)}">${pct(x.range)}</td><td class="${cls(x.pdh)}">${x.pdh?'YES':'NO'}</td><td>${String(x.or).padStart(2,'0')}</td><td class="${x.aboveOrh===null?'cream':cls(x.aboveOrh)}">${x.aboveOrh===null?'—':x.aboveOrh?'YES':'NO'}</td><td class="${x.delay<3?'green':'cream'}">${x.delay}m</td></tr>`).join('');document.getElementById('symbols').value=d.rows.map(x=>x.symbol).join(', ')}catch(err){const e=document.getElementById('error');e.style.display='block';e.textContent=err.message}}
async function saveWatchlist(){const symbols=document.getElementById('symbols').value.split(/[\s,]+/).filter(Boolean);await fetch('/api/watchlist',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({symbols})});load()}load();setInterval(load,10000);
</script></body></html>'''


class Handler(BaseHTTPRequestHandler):
    engine: DashboardEngine = None

    def end_headers(self):
        # The public GitHub Pages file is only a UI. It may access this local,
        # read-only service without exposing the Webull credentials.
        origin = self.headers.get("Origin")
        if origin == "https://i-manage-risk.github.io":
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")
            self.send_header("Access-Control-Allow-Methods", "GET, POST, OPTIONS")
            self.send_header("Access-Control-Allow-Headers", "Content-Type")
            self.send_header("Access-Control-Allow-Private-Network", "true")
        super().end_headers()

    def do_OPTIONS(self):
        self.send_response(204)
        self.end_headers()

    def send_json(self, payload, status=200):
        body = json.dumps(json_safe(payload), allow_nan=False).encode()
        self.send_response(status); self.send_header("Content-Type", "application/json"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body)

    def do_GET(self):
        path = urlparse(self.path).path
        if path == "/api/data": self.send_json(self.engine.refresh()); return
        if path == "/":
            body = HTML.encode(); self.send_response(200); self.send_header("Content-Type", "text/html; charset=utf-8"); self.send_header("Content-Length", str(len(body))); self.end_headers(); self.wfile.write(body); return
        self.send_error(404)

    def do_POST(self):
        if urlparse(self.path).path != "/api/watchlist": self.send_error(404); return
        try:
            size = int(self.headers.get("Content-Length", 0)); payload = json.loads(self.rfile.read(size)); self.engine.set_symbols(payload.get("symbols", [])); self.send_json({"ok": True})
        except Exception as exc: self.send_json({"error": str(exc)}, 400)

    def log_message(self, *_): pass


if __name__ == "__main__":
    engine = DashboardEngine(); Handler.engine = engine
    server = ThreadingHTTPServer(("127.0.0.1", 8765), Handler)
    print("Webull dashboard: http://127.0.0.1:8765")
    if os.getenv("NO_BROWSER") != "1":
        threading.Timer(1, lambda: webbrowser.open("http://127.0.0.1:8765")).start()
    try: server.serve_forever()
    except KeyboardInterrupt: pass
    finally: server.server_close()
