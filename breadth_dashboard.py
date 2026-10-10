#!/usr/bin/env python3
"""Capture Stockbee's published Market Monitor and build the Breadth page."""
from __future__ import annotations

import csv
import io
import json
import re
from concurrent.futures import ThreadPoolExecutor
from datetime import date, datetime, timedelta
from pathlib import Path

import requests
import yfinance as yf

SHEET_ID = "1O6OhS7ciA8zwfycBfGPbP2fWJnR0pn2UUvFZVDP9jpE"
YEAR_GIDS = {2026:1082103394,2025:780188096,2024:1146204629,2023:632667710,2022:1394777987,2021:1981550515,2020:2093835319,2019:1089581064,2018:280217788,2017:1391207759,2016:233732777,2015:0,2014:1622090416,2013:299051502,2012:2142678713,2011:24026662,2010:1622166415,2009:1397702728,2008:1269494253,2007:908739106}
OUT = Path("outputs/breadth_market_monitor.json")
SOURCE_KEYS = {
    "date": "Date",
    "up4": "Number of stocks up 4% plus today",
    "down4": "Number of stocks down 4% plus today",
    "ratio5": "5 day ratio",
    "ratio10": "10 day  ratio",
    "up25q": "Number of stocks up 25% plus in a quarter",
    "down25q": "Number of stocks down 25% + in a quarter",
    "up25m": "Number of stocks up 25% + in a month",
    "down25m": "Number of stocks down 25% + in a month",
    "up50m": "Number of stocks up 50% + in a month",
    "down50m": "Number of stocks down 50% + in a month",
    "up13d34": "Number of stocks up 13% + in 34 days",
    "down13d34": "Number of stocks down 13% + in 34 days",
    "universe": "Worden Common stock universe",
    "t2108": "T2108",
    "sp": "S&P",
}


def numeric(value: str) -> float | None:
    try:
        return float(value.replace(",", "").strip())
    except (AttributeError, ValueError):
        return None


def sheet_url(gid: int) -> str:
    return f"https://docs.google.com/spreadsheets/d/{SHEET_ID}/pub?gid={gid}&single=true&output=csv"


def parse_date(value: str, fallback_year: int) -> date | None:
    value = value.strip().replace(".", "/")
    if not value:
        return None
    parts = value.split("/")
    if len(parts) == 2:
        parts.append(str(fallback_year))
    if len(parts) != 3:
        return None
    try:
        first, second, year = (int(part) for part in parts)
        year = year + 2000 if year < 100 else year
        # A few legacy cells contain malformed years. Keep valid dates as-is
        # because the newest tab includes a short prior-year overlap.
        if not 1900 <= year <= 2100:
            year = fallback_year
        month, day = (second, first) if first > 12 else (first, second)
        return date(year, month, day)
    except ValueError:
        return None


def key_for_header(header: str) -> str | None:
    value = re.sub(r"\s+", " ", header.strip().lower())
    if value == "date": return "date"
    is_daily_4 = "4%" in value and ("today" in value or "daily" in value or "high volume" in value)
    if is_daily_4 and "down" in value: return "down4"
    if is_daily_4 and ("plus" in value or " up" in value or "breakout" in value): return "up4"
    if "5 day" in value and "ratio" in value: return "ratio5"
    if "10 day" in value and "ratio" in value: return "ratio10"
    if "25%" in value and "quarter" in value and "down" in value: return "down25q"
    if "25%" in value and "quarter" in value: return "up25q"
    if "25" in value and "month" in value and "down" in value: return "down25m"
    if "25" in value and "month" in value: return "up25m"
    if "50" in value and "month" in value and "down" in value: return "down50m"
    if "50" in value and "month" in value: return "up50m"
    if "34/13" in value and ("bear" in value or "down" in value): return "down13d34"
    if "34/13" in value and ("bull" in value or "up" in value): return "up13d34"
    if "13%" in value and "34 days" in value and "down" in value: return "down13d34"
    if "13%" in value and "34 days" in value and "up" in value: return "up13d34"
    if "t2108" in value: return "t2108"
    if value in {"s&p", "s&p 500", "spx"}: return "sp"
    if "common stock" in value or "total (no etf)" in value or value == "total": return "universe"
    return None


def empty_row(day: date) -> dict:
    return {"date": day.isoformat(), **{key: None for key in SOURCE_KEYS if key != "date"}}


def parse_vertical(raw: list[list[str]], year: int) -> list[dict]:
    header_index = next((i for i, row in enumerate(raw[:12]) if row and row[0].strip().lower() == "date"), None)
    if header_index is None:
        return []
    keys = [key_for_header(header) for header in raw[header_index]]
    output = []
    for values in raw[header_index + 1:]:
        day = parse_date(values[0], year) if values else None
        if day is None:
            continue
        row = empty_row(day)
        for index, key in enumerate(keys):
            if key and key != "date" and index < len(values):
                row[key] = numeric(values[index])
        output.append(row)
    return output


def parse_transposed(raw: list[list[str]], year: int) -> list[dict]:
    date_index = max(range(min(12, len(raw))), key=lambda i: sum(parse_date(cell, year) is not None for cell in raw[i]))
    dates = raw[date_index]
    metric_rows = {}
    for values in raw[date_index + 1:]:
        label = " ".join(values[:2]) if len(values) > 1 else values[0]
        key = key_for_header(label)
        # Legacy sheets also contain secondary "up 100%/200%" rows whose
        # wording resembles the daily 4% metric. The first mapped row is the
        # canonical Market Monitor series.
        if key and key not in metric_rows:
            metric_rows[key] = values
    output = []
    for index, value in enumerate(dates):
        day = parse_date(value, year)
        if day is None:
            continue
        row = empty_row(day)
        for key, values in metric_rows.items():
            row[key] = numeric(values[index]) if index < len(values) else None
        output.append(row)
    return output


def fetch_year(item: tuple[int, int]) -> list[dict]:
    year, gid = item
    response = requests.get(sheet_url(gid), timeout=45)
    response.raise_for_status()
    raw = list(csv.reader(io.StringIO(response.text)))
    vertical = parse_vertical(raw, year)
    return vertical if vertical else parse_transposed(raw, year)


def spx_closes() -> dict[str, float]:
    history = yf.download("^GSPC", start="2007-01-01", end=(date.today() + timedelta(days=2)).isoformat(), auto_adjust=False, actions=False, progress=False)
    close = history["Close"]
    if hasattr(close, "columns"):
        close = close.iloc[:, 0]
    return {pd_date.date().isoformat(): float(value) for pd_date, value in close.dropna().items()}


def load_rows() -> list[dict]:
    with ThreadPoolExecutor(max_workers=6) as executor:
        year_rows = list(executor.map(fetch_year, YEAR_GIDS.items()))
    by_date = {}
    for rows in year_rows:
        for row in rows:
            by_date[row["date"]] = row
    ordered = sorted(by_date.values(), key=lambda row: row["date"])
    # Older tabs do not always publish rolling ratios. They can be recovered
    # exactly from the daily up/down event counts.
    for index, row in enumerate(ordered):
        for days, key in ((5, "ratio5"), (10, "ratio10")):
            window = ordered[max(0, index - days + 1):index + 1]
            if row[key] is None and len(window) == days and all(item["up4"] is not None and item["down4"] is not None for item in window):
                denominator = sum(item["down4"] for item in window)
                row[key] = sum(item["up4"] for item in window) / denominator if denominator else None
    closes = spx_closes()
    for row in ordered:
        if row["sp"] is None:
            row["sp"] = closes.get(row["date"])
    rows = list(reversed(ordered))
    if not rows:
        raise RuntimeError("The published Market Monitor contained no usable rows.")
    return rows


TEMPLATE = r'''<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>Breadth | Liquid Leadership</title><meta name="description" content="A beginner-friendly view of Stockbee's daily Market Monitor breadth data."><link rel="icon" type="image/png" href="assets/nel-favicon.png"><style>
:root{--bg:#141414;--panel:#2A2A2A;--soft:#202020;--line:#454545;--text:#F5F2E8;--muted:#c8c4b9;--up:#62d6b4;--down:#ff6b8a;--gold:#e9c46a;--blue:#75baff}*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--text);font:15px/1.48 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif}main{max-width:1680px;margin:auto;padding:24px 40px 48px}.site-nav{display:flex;justify-content:center;gap:7px;margin:0 0 22px}.site-nav a{min-width:92px;padding:7px 13px;border:1px solid var(--line);border-radius:7px;color:var(--text);text-align:center;text-decoration:none;font-weight:650;font-size:14px}.site-nav a.active,.site-nav a:hover{background:var(--text);color:var(--bg)}.top{display:flex;justify-content:space-between;gap:24px;align-items:flex-end;margin-bottom:20px}h1,h2,h3,p{margin-top:0}h1{font-size:24px;margin-bottom:3px}.sub,.muted{color:var(--muted)}.date-picker{display:grid;position:relative;gap:4px;font-weight:700;white-space:nowrap}.date-picker>span{font-size:11px;color:var(--muted);text-transform:uppercase;letter-spacing:.045em}.date-button{display:flex;align-items:center;justify-content:space-between;gap:16px;min-width:165px;padding:8px 10px;background:var(--text);border-color:var(--text);color:var(--bg);font:inherit;font-weight:750}.date-button:hover,.date-button:focus-visible{background:#fffdf5;outline:2px solid var(--blue);outline-offset:2px}.date-button .date-arrow{font-size:12px;color:var(--bg)}.date-native{position:absolute;width:1px;height:1px;right:0;bottom:22px;opacity:0;pointer-events:none}.date-status{font-size:12px;color:var(--muted);text-align:right}.panel{background:var(--panel);border:1px solid var(--line);border-radius:10px;padding:17px}.overview{display:grid;grid-template-columns:1.15fr repeat(3,1fr);gap:14px}.regime{border-top:3px solid var(--gold)}.eyebrow{font-size:12px;color:var(--muted);font-weight:750;text-transform:uppercase;letter-spacing:.045em}.big{font-size:29px;font-weight:780;margin:4px 0}.up{color:var(--up)}.down{color:var(--down)}.gold{color:var(--gold)}.metric-note{font-size:13px;color:var(--muted)}.balance-grid{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));gap:14px;margin-top:14px}.pair{display:flex;gap:12px;margin-top:10px;font-variant-numeric:tabular-nums}.pair span{flex:1;background:var(--soft);padding:9px;border-radius:6px}.pair b{display:block;font-size:20px}.bar{display:flex;height:7px;border-radius:8px;overflow:hidden;background:#111;margin-top:11px}.bar i:first-child{background:var(--up)}.bar i:last-child{background:var(--down)}.guide{margin-top:14px}.guide-grid{display:grid;grid-template-columns:repeat(3,1fr);gap:14px}.guide h3{font-size:15px;margin-bottom:6px}.guide p{font-size:13px;color:var(--muted);margin-bottom:0}.chart{margin-top:14px}.chart-head{display:flex;justify-content:space-between;gap:14px;align-items:center;flex-wrap:wrap}.controls{display:flex;gap:6px;flex-wrap:wrap}button{background:var(--soft);border:1px solid var(--line);color:var(--text);padding:7px 10px;border-radius:6px;font-weight:650;cursor:pointer}button.active{background:var(--text);color:var(--bg)}svg{width:100%;height:340px;display:block;margin-top:10px}.legend{color:var(--muted);font-size:13px}.table-card{margin-top:14px;overflow:auto;max-height:460px}table{width:100%;border-collapse:collapse;font-variant-numeric:tabular-nums}th,td{padding:9px 10px;border-bottom:1px solid var(--line);text-align:right;white-space:nowrap}th{position:sticky;top:0;background:var(--panel);font-size:12px;color:var(--muted)}th:first-child,td:first-child{text-align:left}.source{font-size:12px;color:var(--muted);margin:13px 2px 0}.source a{color:var(--text)}@media(max-width:1150px){.overview,.balance-grid{grid-template-columns:repeat(2,1fr)}.guide-grid{grid-template-columns:1fr}}@media(max-width:650px){main{padding:18px 14px}.overview,.balance-grid{grid-template-columns:1fr}.top{display:block}.date-picker{margin-top:10px}.date-status{text-align:left}.site-nav{justify-content:flex-start;overflow:auto}}
</style></head><body><main><nav class="site-nav"><a href="index.html">Liquid Leaders</a><a href="super-liquid.html">Super Liquid Leaders</a><a href="themes.html">Themes</a><a href="sectors.html">Sectors</a><a class="active" href="breadth.html">Breadth</a></nav><header class="top"><div><h1>Market Breadth</h1><div class="sub">How much of the market is participating—not just what the index is doing.</div></div><div class="date-picker"><span>Time Machine</span><button class="date-button" id="asof-button" type="button"><span id="asof-label"></span><span class="date-arrow" aria-hidden="true">▼</span></button><input class="date-native" id="asof-date" type="date" aria-label="View market as of date"><small class="date-status" id="date"></small></div></header><section class="overview" id="overview"></section><section class="balance-grid" id="balances"></section><section class="panel guide"><div class="eyebrow">Beginner's guide</div><div class="guide-grid"><div><h3>1. Start with today</h3><p>The ±4% counts show immediate buying and selling pressure. A large gap indicates broad participation; similar counts mean a two-sided, mixed session.</p></div><div><h3>2. Check persistence</h3><p>The 5- and 10-day ratios total up-4% events and divide them by down-4% events. Above 1 favors buying pressure; below 1 favors selling pressure.</p></div><div><h3>3. Confirm the regime</h3><p>Quarter, month and 34-day counts show whether momentum is widespread. T2108 is the percentage of stocks above their 40-day moving average. Read multiple measures together.</p></div></div></section><section class="panel chart"><div class="chart-head"><div><h2 id="chart-title" style="margin-bottom:2px">Daily ±4% movers</h2><div class="legend" id="chart-note"></div></div><div class="controls" id="controls"></div></div><svg id="chart" viewBox="0 0 1000 340" aria-label="Breadth history"></svg></section><section class="panel chart"><div class="chart-head"><div><h2 style="margin-bottom:2px">SPX</h2><div class="legend">S&amp;P 500 close through the selected date, using the same timeframe.</div></div></div><svg id="spx-chart" viewBox="0 0 1000 340" aria-label="S&amp;P 500 history"></svg></section><section class="panel table-card"><h2>Readings through selected date</h2><table><thead><tr><th>Date</th><th>Up 4%</th><th>Down 4%</th><th>Net</th><th>5D</th><th>10D</th><th>Quarter +25%</th><th>Quarter −25%</th><th>T2108</th><th>S&amp;P</th></tr></thead><tbody id="table"></tbody></table></section><p class="source">Data: <a href="https://stockbee.blogspot.com/p/mm.html" target="_blank" rel="noopener">Stockbee Market Monitor</a>. SPX closes: Yahoo Finance. Educational context only; breadth describes participation and is not a standalone trading signal.</p></main><script>
const rows=__DATA__,latest=rows[0],fmt=v=>Number(v).toLocaleString(undefined,{maximumFractionDigits:2}),pct=v=>`${Number(v).toFixed(2)}%`,net=latest.up4-latest.down4;document.querySelector('#date').textContent=`Updated ${latest.date}`;const bothUp=latest.ratio5>1&&latest.ratio10>1,bothDown=latest.ratio5<1&&latest.ratio10<1,regime=bothUp&&net>0?['Buying pressure','up','Up/down pressure is positive today and across both rolling windows.']:bothDown&&net<0?['Selling pressure','down','Downside pressure leads today and across both rolling windows.']:['Mixed / transition','gold','Daily and rolling breadth are not aligned yet.'];document.querySelector('#overview').innerHTML=`<article class="panel regime"><div class="eyebrow">Current read</div><div class="big ${regime[1]}">${regime[0]}</div><div class="metric-note">${regime[2]}</div></article><article class="panel"><div class="eyebrow">Today: up 4% / down 4%</div><div class="big"><span class="up">${fmt(latest.up4)}</span> / <span class="down">${fmt(latest.down4)}</span></div><div class="metric-note">Net breadth: ${net>0?'+':''}${fmt(net)}</div></article><article class="panel"><div class="eyebrow">5-day pressure ratio</div><div class="big ${latest.ratio5>=1?'up':'down'}">${latest.ratio5.toFixed(2)}</div><div class="metric-note">5 sessions of up-4% events ÷ down-4% events</div></article><article class="panel"><div class="eyebrow">10-day pressure ratio</div><div class="big ${latest.ratio10>=1?'up':'down'}">${latest.ratio10.toFixed(2)}</div><div class="metric-note">10 sessions; smoother confirmation of the short-term tape</div></article>`;const pairs=[['Quarter ±25%','up25q','down25q','Stocks ≥25% from a 65-day low vs ≤−25% from a 65-day high.'],['Month ±25%','up25m','down25m','Strong one-month gainers versus strong one-month decliners.'],['Month ±50%','up50m','down50m','Rare, high-velocity one-month moves; useful for spotting extremes.'],['34 days ±13%','up13d34','down13d34','A broader intermediate-momentum participation measure.']];document.querySelector('#balances').innerHTML=pairs.map(([title,u,d,note])=>{const a=latest[u],b=latest[d],total=Math.max(a+b,1);return `<article class="panel"><strong>${title}</strong><div class="metric-note">${note}</div><div class="pair"><span class="up">Up<b>${fmt(a)}</b></span><span class="down">Down<b>${fmt(b)}</b></span></div><div class="bar"><i style="width:${a/total*100}%"></i><i style="width:${b/total*100}%"></i></div></article>`}).join('');const views={daily:{label:'Daily ±4%',keys:['up4','down4'],note:'Immediate buying versus selling pressure.'},ratios:{label:'5D / 10D ratios',keys:['ratio5','ratio10'],note:'Above 1 means more upside than downside 4% events over the window.'},quarter:{label:'Quarter ±25%',keys:['up25q','down25q'],note:'The medium-term momentum regime.'},month:{label:'Month ±25%',keys:['up25m','down25m'],note:'Large one-month moves in both directions.'},month50:{label:'Month ±50%',keys:['up50m','down50m'],note:'Very high-velocity monthly moves.'},fast:{label:'34D ±13%',keys:['up13d34','down13d34'],note:'Intermediate participation across the common-stock universe.'},t2108:{label:'T2108',keys:['t2108'],note:'Percentage of stocks above their 40-day moving average.'}};let active='daily';const controls=document.querySelector('#controls');Object.entries(views).forEach(([key,v])=>{const b=document.createElement('button');b.textContent=v.label;b.onclick=()=>{active=key;renderChart()};controls.append(b)});function renderChart(){[...controls.children].forEach((b,i)=>b.classList.toggle('active',Object.keys(views)[i]===active));const view=views[active],data=rows.slice(0,90).reverse(),values=data.flatMap(r=>view.keys.map(k=>r[k])),max=Math.max(...values,1),min=active==='ratios'?Math.min(...values,0):0,w=930,h=270,x=i=>45+i*(w/Math.max(data.length-1,1)),y=v=>295-(v-min)/(max-min||1)*h,path=k=>data.map((r,i)=>`${i?'L':'M'}${x(i).toFixed(1)},${y(r[k]).toFixed(1)}`).join(' '),colors=['#62d6b4','#ff6b8a'];document.querySelector('#chart').innerHTML=`<path d="M45,295H975 M45,25V295" stroke="#454545" fill="none"/>${active==='ratios'?`<path d="M45,${y(1)}H975" stroke="#e9c46a" stroke-dasharray="5 5"/>`:''}${view.keys.map((k,i)=>`<path d="${path(k)}" stroke="${colors[i]||'#75baff'}" stroke-width="3" fill="none"/>`).join('')}<text x="45" y="325" fill="#c8c4b9" font-size="12">${data[0].date}</text><text x="900" y="325" fill="#c8c4b9" font-size="12">${data.at(-1).date}</text><text x="48" y="39" fill="#c8c4b9" font-size="12">${fmt(max)}</text>`;document.querySelector('#chart-title').textContent=view.label;document.querySelector('#chart-note').textContent=view.note}renderChart();document.querySelector('#table').innerHTML=rows.slice(0,60).map(r=>`<tr><td>${r.date}</td><td class="up">${fmt(r.up4)}</td><td class="down">${fmt(r.down4)}</td><td>${r.up4-r.down4>0?'+':''}${fmt(r.up4-r.down4)}</td><td>${r.ratio5.toFixed(2)}</td><td>${r.ratio10.toFixed(2)}</td><td>${fmt(r.up25q)}</td><td>${fmt(r.down25q)}</td><td>${pct(r.t2108)}</td><td>${fmt(r.sp)}</td></tr>`).join('');
</script><script src="assets/breadth-time-machine.js?v=4"></script><script src="assets/breadth-scenarios.js?v=8"></script><script src="assets/breadth-chart.js?v=9"></script></body></html>'''


def build_page(rows: list[dict]) -> str:
    from site_chrome import apply_chrome
    return apply_chrome(TEMPLATE.replace("__DATA__", json.dumps(rows, separators=(",", ":"))), "breadth")


def main() -> None:
    rows = load_rows()
    OUT.parent.mkdir(exist_ok=True)
    OUT.write_text(json.dumps(rows, separators=(",", ":")))
    Path("breadth.html").write_text(build_page(rows))
    print(f"Captured {len(rows)} breadth rows through {rows[0]['date']}")


if __name__ == "__main__":
    main()
