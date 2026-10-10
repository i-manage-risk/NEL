"""Render interactive Theme and Sector ETF leadership pages."""

from __future__ import annotations

import json
from pathlib import Path

from etf_strength import OUTPUT_DIR, PROJECT_DIR, UNIVERSES

SECTOR_COLORS = {
    "Materials": "#E9C46A",
    "Communication Services": "#5C7CFA",
    "Energy": "#E76F51",
    "Financial Services": "#C77DFF",
    "Industrial": "#70C1B3",
    "Technology": "#4CC9F0",
    "Consumer Staples": "#F4A261",
    "Real Estate": "#D77AAB",
    "Utilities": "#80ED99",
    "Health Care": "#FF6B6B",
    "Consumer Discretionary": "#B8DE6F",
}


def render_dashboard(payload: dict, active_key: str) -> str:
    extended_hours_path = OUTPUT_DIR / "extended_hours.json"
    if extended_hours_path.exists():
        try:
            payload["extended_hours"] = json.loads(extended_hours_path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            payload["extended_hours"] = {}
    completed_after_hours = payload.get("extended_hours", {}).get("values", {})
    if completed_after_hours and payload.get("snapshots"):
        for row in payload["snapshots"][-1].get("daily_changes", []):
            value = completed_after_hours.get(row.get("symbol"))
            if isinstance(value, (int, float)):
                row["postmarket"] = value
    completed_overnight = payload.get("extended_hours", {}).get("overnight", {}).get("values", {})
    if completed_overnight and payload.get("snapshots"):
        for row in payload["snapshots"][-1].get("daily_changes", []):
            value = completed_overnight.get(row.get("symbol"))
            if isinstance(value, (int, float)):
                row["overnight"] = value
    data = json.dumps(payload, separators=(",", ":"))
    title = payload["title"]
    leader_label = "Theme Leaders" if active_key == "themes" else "Sector Leaders"
    filtered_sections = r'''
  <div class="section-heading"><h2 id="nel-title">Non-Extended ETF Leaders (NEL)</h2><button id="export-nel" class="button">Export NEL</button></div>
  <div id="nel-windows" class="windows"></div>''' if active_key == "themes" else ""
    return r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>__TITLE__ | Liquid Leadership</title>
  <meta name="description" content="Track leading market groups, non-extended ETFs, live performance, and underlying stock holdings.">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <style>
    :root { color-scheme:dark; --bg:#141414; --panel:#2A2A2A; --track:#1b1b1b; --line:#454545; --text:#F5F2E8; --purple:#9b7cff; --orange:#ff9900; --cyan:#00ffff; --pink:#ff3366; --green:#86d65d; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:14px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:100%; max-width:2200px; margin:auto; padding:22px 34px 44px; }
    .site-nav { display:flex; justify-content:center; gap:7px; margin:0 0 18px; }
    .site-nav a { min-width:92px; padding:7px 13px; border:1px solid var(--line); border-radius:7px; color:var(--text); text-align:center; text-decoration:none; font-weight:650; }
    .site-nav a:hover,.site-nav a.active { background:var(--text); color:var(--bg); border-color:var(--text); }
    .topbar { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin-bottom:18px; }
    h1 { margin:0; font-size:20px; letter-spacing:-.01em; }
    h2 { margin:0; font-size:19px; }
    select,.button { width:128px; height:34px; border:0; border-radius:7px; padding:7px 9px; background:var(--text); color:var(--bg); font:650 13px/1 system-ui; }
    .button { cursor:pointer; }
    #snapshot { justify-self:end; }
    .section-heading { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin:27px 0 13px; }
    .section-heading h2 { grid-column:2; text-align:center; }
    .section-heading .button { grid-column:3; justify-self:end; }
    .windows { display:grid; grid-template-columns:repeat(5,minmax(0,1fr)); gap:18px; align-items:start; }
    .card { min-width:0; background:var(--panel); border:1px solid var(--line); border-top:3px solid var(--orange); border-radius:10px; padding:16px; }
    .card[data-frame="1w"] { border-top-color:var(--purple); } .card[data-frame="3m"] { border-top-color:var(--cyan); } .card[data-frame="6m"] { border-top-color:var(--pink); } .card[data-frame="1y"] { border-top-color:var(--green); }
    .card h3 { color:var(--orange); margin:0 0 12px; font-size:14px; } .card[data-frame="1w"] h3 { color:var(--purple); } .card[data-frame="3m"] h3 { color:var(--cyan); } .card[data-frame="6m"] h3 { color:var(--pink); } .card[data-frame="1y"] h3 { color:var(--green); }
    .card .trend-title { margin:19px 0 5px; color:var(--text); font-size:14px; }
    .trend-chart { display:block; width:100%; height:260px; overflow:visible; }
    .table-wrap { width:100%; overflow:visible; }
    table { width:100%; table-layout:fixed; border-collapse:collapse; font-variant-numeric:tabular-nums; }
    th,td { padding:8px 5px; border-bottom:1px solid var(--line); text-align:right; vertical-align:middle; white-space:nowrap; }
    th { color:var(--text); font-size:11px; font-weight:650; }
    th:first-child,td:first-child,th:nth-child(2),td:nth-child(2) { text-align:left; }
    td:first-child { font-weight:700; }
    .leaders-table th:nth-child(1) { width:8%; } .leaders-table th:nth-child(2) { width:31%; } .leaders-table th:nth-child(3) { width:15%; } .leaders-table th:nth-child(4) { width:17%; } .leaders-table th:nth-child(5) { width:14%; } .leaders-table th:nth-child(6) { width:15%; }
    .etf-table th:nth-child(1) { width:14%; } .etf-table th:nth-child(2) { width:29%; } .etf-table th:nth-child(3) { width:14%; } .etf-table th:nth-child(4) { width:11%; } .etf-table th:nth-child(5) { width:18%; } .etf-table th:nth-child(6) { width:14%; }
    td:nth-child(2) { white-space:normal; overflow-wrap:anywhere; }
    .clickable { cursor:pointer; } .clickable:hover { background:#343434; }
    .ticker-button,.group-button { all:unset; color:inherit; cursor:pointer; font-weight:700; }
    .ticker-button:hover,.group-button:hover { text-decoration:underline; }
    .muted { opacity:.72; } .empty { padding:28px 6px; text-align:left; }
    .change-toggle { display:flex; justify-content:center; flex-wrap:wrap; gap:6px; margin:-4px 0 13px; }
    .change-scope { margin-bottom:9px; }
    .change-toggle button { min-width:112px; height:34px; padding:0 10px; border:1px solid var(--line); border-radius:7px; background:var(--panel); color:var(--text); cursor:pointer; font:650 12px/1 system-ui; }
    .change-toggle button.active { background:var(--text); color:var(--bg); }
    .change-card { width:min(100%,980px); margin:0 auto; background:var(--panel); border:1px solid var(--line); border-radius:10px; padding:14px 16px 18px; }
    .live-status { min-height:18px; margin:-7px 0 10px; text-align:center; font-size:11px; opacity:.72; }
    .change-axis,.change-row { display:grid; grid-template-columns:minmax(155px,220px) minmax(0,1fr) 68px; align-items:center; column-gap:12px; }
    .change-axis { position:sticky; top:0; z-index:2; padding:0 0 7px; background:var(--panel); color:var(--text); font-size:10px; opacity:.75; }
    .axis-track { display:flex; justify-content:space-between; }
    .change-row { min-height:27px; border-top:1px solid #3b3b3b; }
    .change-label { min-width:0; overflow:hidden; text-overflow:ellipsis; white-space:nowrap; }
    .change-label strong { display:inline-block; min-width:52px; }
    .change-label span { opacity:.7; font-size:11px; }
    .change-track { position:relative; height:14px; border-radius:3px; background:var(--track); overflow:hidden; }
    .change-track::after { content:""; position:absolute; inset:0 auto 0 50%; width:1px; background:#777; }
    .change-bar { position:absolute; top:2px; bottom:2px; min-width:1px; border-radius:2px; }
    .change-bar.positive { left:50%; background:#72B7B2; }
    .change-bar.negative { right:50%; background:#E07A5F; }
    .change-value { text-align:right; font-variant-numeric:tabular-nums; font-weight:650; }
    dialog { width:min(1040px,calc(100vw - 32px)); max-height:88vh; padding:0; border:1px solid var(--line); border-radius:12px; background:var(--panel); color:var(--text); box-shadow:0 24px 80px #000b; }
    dialog::backdrop { background:#000b; }
    .drawer-head { position:sticky; top:0; z-index:4; display:flex; align-items:center; justify-content:space-between; padding:16px 18px; background:var(--panel); border-bottom:1px solid var(--line); }
    .drawer-head h2 { font-size:18px; } .close { width:34px; height:34px; border:0; border-radius:50%; background:var(--text); color:var(--bg); cursor:pointer; font-size:20px; }
    .drawer-body { padding:18px; overflow:auto; }
    .drawer-subtitle { margin:18px 0 8px; font-size:14px; }
    .member-table th:nth-child(1) { width:13%; } .member-table th:nth-child(2) { width:28%; } .member-table th:nth-child(n+3) { width:auto; }
    .tabs { display:flex; flex-wrap:wrap; gap:7px; margin:10px 0 12px; }
    .tab { border:1px solid var(--line); border-radius:999px; background:var(--bg); color:var(--text); padding:7px 12px; cursor:pointer; font-weight:650; }
    .tab.active { color:var(--bg); background:var(--text); border-color:var(--text); }
    .holdings-table th:nth-child(1) { width:16%; } .holdings-table th:nth-child(2) { width:39%; } .holdings-table th:nth-child(3) { width:15%; } .holdings-table th:nth-child(4) { width:17%; } .holdings-table th:nth-child(5) { width:13%; }
    .footnote { margin:14px 0 0; font-size:12px; opacity:.72; }
    @media (max-width:1700px) { .windows { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media (max-width:1120px) { main { padding:18px 14px 36px; } .windows { grid-template-columns:1fr; } }
    @media (max-width:640px) { .topbar { grid-template-columns:1fr; gap:10px; } #snapshot { justify-self:start; } .section-heading { grid-template-columns:1fr auto; } .section-heading h2 { grid-column:1; text-align:left; } .section-heading .button { grid-column:2; } .change-toggle button { min-width:0; width:104px; padding:0 7px; } .change-axis,.change-row { grid-template-columns:96px minmax(0,1fr) 55px; column-gap:7px; } .change-label span { display:none; } .site-nav { justify-content:flex-start; overflow-x:auto; } }
  </style>
  <link rel="stylesheet" href="assets/date-select.css?v=2">
</head>
<body>
<main>
  <nav class="site-nav" aria-label="Dashboard pages"><a href="index.html">Liquid Leaders</a><a href="super-liquid.html">Super Liquid Leaders</a><a href="themes.html" data-page="themes">Themes</a><a href="sectors.html" data-page="sectors">Sectors</a><a href="breadth.html">Breadth</a></nav>
  <div class="topbar"><select id="date" aria-label="Snapshot date"></select><h1>__TITLE__</h1><button id="snapshot" class="button">Snapshot</button></div>
  <div class="section-heading"><h2 id="leaders-title">__LEADER_LABEL__</h2><button id="export-leaders" class="button">Export Leaders</button></div>
  <div id="leader-windows" class="windows"></div>
__FILTERED_SECTIONS__
  <div class="section-heading"><h2>ETF Performance</h2></div>
  <div id="change-scope" class="change-toggle change-scope" role="group" aria-label="Performance chart view"></div>
  <div id="change-modes" class="change-toggle" role="group" aria-label="ETF performance window"><button type="button" data-change-mode="extended">Extended Hours</button><button type="button" data-change-mode="intraday">Intraday</button><button type="button" class="active" data-change-mode="one_day">1 Day</button><button type="button" data-change-mode="one_week">1 Week</button><button type="button" data-change-mode="one_month">1 Month</button><button type="button" data-change-mode="three_months">3 Months</button><button type="button" data-change-mode="six_months">6 Months</button><button type="button" data-change-mode="one_year">1 Year</button></div>
  <div id="live-status" class="live-status">Loading current performance…</div>
  <section class="change-card"><div id="change-chart"></div></section>
</main>
<dialog id="holdings-dialog"><div class="drawer-head"><h2 id="drawer-title">Holdings</h2><button id="drawer-close" class="close" aria-label="Close">×</button></div><div id="drawer-body" class="drawer-body"></div></dialog>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
const data = __DATA__;
const frames = { '1w':'1 week', '1m':'1 month', '3m':'3 months', '6m':'6 months', '1y':'1 year' };
const sectorColors = __SECTOR_COLORS__;
const dateSelect = document.getElementById('date');
const leaderWindows = document.getElementById('leader-windows');
const nelWindows = document.getElementById('nel-windows');
const changeChart = document.getElementById('change-chart');
const changeScope = document.getElementById('change-scope');
const changeModes = document.getElementById('change-modes');
const liveStatus = document.getElementById('live-status');
const dialog = document.getElementById('holdings-dialog');
const drawerTitle = document.getElementById('drawer-title');
const drawerBody = document.getElementById('drawer-body');
document.querySelector(`[data-page="${data.kind}"]`)?.classList.add('active');

function esc(value) { return String(value ?? '—').replace(/[&<>'"]/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[c])); }
function num(value, digits=1) { return Number.isFinite(Number(value)) ? Number(value).toFixed(digits) : '—'; }
function pct(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'; }
function dollars(value) { const n=Number(value); if (!Number.isFinite(n)||n<=0) return '—'; if(n>=1e9) return `$${(n/1e9).toFixed(n>=10e9?0:1)}B`; return `$${Math.ceil(n/1e7)*10}M`; }
function current() { return data.snapshots[Number(dateSelect.value)] || null; }
function windowGroups(frame) { return current()?.windows?.[frame] || []; }
function members(frame) { return windowGroups(frame).flatMap(group => group.members); }
function uniqueMembers(filter) { const map=new Map(); Object.keys(frames).flatMap(frame => members(frame).filter(filter)).forEach(row => map.set(row.symbol,row)); return [...map.values()]; }
function isNEL(row) { return Number.isFinite(Number(row.extension)) && Number(row.extension) <= 4; }
let changeMode = 'one_day';
let changeView = data.kind === 'themes' ? 'groups' : 'etfs';
let liveChanges = null;
let extendedSelected = false;
const completedAfterHours = data.extended_hours || {};

function extendedSession() {
  const parts=Object.fromEntries(new Intl.DateTimeFormat('en-US',{timeZone:'America/New_York',weekday:'short',hour:'2-digit',minute:'2-digit',hourCycle:'h23'}).formatToParts(new Date()).filter(part=>part.type!=='literal').map(part=>[part.type,part.value]));
  const minutes=Number(parts.hour)*60+Number(parts.minute), weekday=parts.weekday;
  if((weekday==='Sun'&&minutes>=1200)||(weekday==='Sat'&&minutes<240)||(weekday!=='Sat'&&weekday!=='Sun'&&(minutes<240||minutes>=1200)))return {key:'overnight',label:'Overnight',active:true};
  if(weekday!=='Sat'&&weekday!=='Sun'&&minutes>=240&&minutes<570)return {key:'premarket',label:'Premarket',active:true};
  if(weekday!=='Sat'&&weekday!=='Sun'&&minutes>=960&&minutes<1200)return {key:'postmarket',label:'After-hours',active:true};
  if(weekday!=='Sat'&&weekday!=='Sun'&&minutes>=570&&minutes<960)return {key:'premarket',label:'Premarket',active:false};
  return {key:'overnight',label:'Overnight',active:false};
}
function performanceStatus(delayed=false) {
  if(Number(dateSelect.value)!==data.snapshots.length-1)return extendedSelected?'Historical snapshots do not retain a complete extended-hours tape.':`Historical close · ${current()?.date||''}`;
  if(extendedSelected){const session=extendedSession(),source=liveChanges||current()?.daily_changes||[],available=source.filter(row=>(!session.active||row[`_live_${session.key}`]===true)&&row[session.key]!==null&&row[session.key]!==''&&Number.isFinite(Number(row[session.key]))).length;return `Extended Hours · ${session.label} · ${session.active?'active session':'latest completed session'} · ${available}/${source.length} ETFs reporting; non-participants omitted${delayed?' · public feed delayed up to 15 min':''} · refreshed ${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}`;}
  const afterHoursNote=completedAfterHours.date?` · completed after-hours: ${completedAfterHours.date}`:'';
  return `TradingView regular-session performance${afterHoursNote}${delayed?' · public feed delayed up to 15 min':''} · refreshed ${new Date().toLocaleTimeString([],{hour:'2-digit',minute:'2-digit'})}`;
}

function renderLeaders(frame) {
  const rows=windowGroups(frame);
  const body=rows.map(group=>{const color=data.kind==='sectors'?sectorColors[group.group]:null;return `<tr class="clickable group-row" data-frame="${frame}" data-group="${esc(group.group)}"><td>${group.rank}</td><td><button class="group-button"${color?` style="color:${color}"`:''}>${esc(group.group)}</button></td><td>${num(group.score)}</td><td>${pct(group.median_performance)}</td><td><button class="ticker-button" data-leader-symbol="${esc(group.leader_etf)}">${esc(group.leader_etf)}</button></td><td>${group.confirmation}/${group.member_count}</td></tr>`;}).join('');
  const trend=data.kind==='sectors'?`<h3 class="trend-title">Leadership over time</h3><svg id="trend-${frame}" class="trend-chart" role="img" aria-label="${frames[frame]} leadership strength over time"></svg>`:'';
  return `<section class="card" data-frame="${frame}"><h3>${frames[frame]} top ${data.top_n}</h3><div class="table-wrap"><table class="leaders-table"><thead><tr><th>#</th><th>Group</th><th>Strength</th><th>Median</th><th>Leader</th><th>Confirmed</th></tr></thead><tbody>${body||'<tr><td colspan="6" class="empty">No ranking data.</td></tr>'}</tbody></table></div>${trend}</section>`;
}
function renderETFTable(frame) {
  const rows=members(frame).filter(isNEL).sort((a,b)=>Number(b.performance)-Number(a.performance));
  const body=rows.map(row=>`<tr class="clickable etf-row" data-frame="${frame}" data-symbol="${esc(row.symbol)}"><td><button class="ticker-button">${esc(row.symbol)}</button></td><td>${esc(row.group)}</td><td>${pct(row.performance)}</td><td>${pct(row.adrp)}</td><td>${dollars(row.average_dollar_volume_30d)}</td><td>${num(row.extension)}×</td></tr>`).join('');
  return `<section class="card" data-frame="${frame}"><h3>${frames[frame]} NEL</h3><div class="table-wrap"><table class="etf-table"><thead><tr><th>ETF</th><th>Group</th><th>Performance</th><th>ADR</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody>${body||'<tr><td colspan="6" class="empty">No qualifying ETFs.</td></tr>'}</tbody></table></div></section>`;
}
function render() {
  leaderWindows.innerHTML=Object.keys(frames).map(renderLeaders).join('');
  if(nelWindows) nelWindows.innerHTML=Object.keys(frames).map(renderETFTable).join('');
  document.getElementById('leaders-title').textContent=`__LEADER_LABEL__ - ${new Set(Object.keys(frames).flatMap(frame=>windowGroups(frame).map(g=>g.group))).size} Groups`;
  if(document.getElementById('nel-title')) document.getElementById('nel-title').textContent=`Non-Extended ETF Leaders (NEL) - ${uniqueMembers(isNEL).length} Tickers`;
  if(data.kind==='sectors') Object.keys(frames).forEach(renderLeadershipTrend);
  renderChangeChart();
}
function renderLeadershipTrend(frame) {
  const svg=document.getElementById(`trend-${frame}`), selectedIndex=Number(dateSelect.value);
  const names=windowGroups(frame).slice(0,5).map(group=>group.group);
  const active=data.snapshots.slice(Math.max(0,selectedIndex-29),selectedIndex+1);
  if(!svg||!names.length||active.length<2){if(svg)svg.innerHTML='<text x="12" y="35" fill="#F5F2E8">More history is needed.</text>';return;}
  const width=Math.max(520,svg.clientWidth||620),height=260,left=35,right=14,top=12,bottom=30;
  const x=index=>left+index*((width-left-right)/Math.max(1,active.length-1));
  const y=value=>top+(100-Number(value||0))*((height-top-bottom)/100);
  const score=(snapshot,name)=>snapshot.leadership?.[frame]?.find(item=>item.group===name)?.score;
  let markup=`<line x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}" stroke="#454545"/><line x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}" stroke="#454545"/>`;
  [0,25,50,75,100].forEach(value=>{markup+=`<line x1="${left}" y1="${y(value)}" x2="${width-right}" y2="${y(value)}" stroke="#3a3a3a"/><text x="${left-6}" y="${y(value)+4}" text-anchor="end" font-size="10" fill="#F5F2E8">${value}</text>`;});
  const tickStep=Math.max(1,Math.ceil((active.length-1)/4)); active.forEach((snapshot,index)=>{if(index%tickStep===0||index===active.length-1)markup+=`<text x="${x(index)}" y="${height-10}" text-anchor="middle" font-size="10" fill="#F5F2E8">${snapshot.date.slice(5)}</text>`;});
  names.forEach(name=>{const color=sectorColors[name]||'#F5F2E8';const points=active.map((snapshot,index)=>{const value=score(snapshot,name);return value==null?null:`${x(index)},${y(value)}`;}).filter(Boolean).join(' ');if(points)markup+=`<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.2"/>`;active.forEach((snapshot,index)=>{const value=score(snapshot,name);if(value!=null)markup+=`<circle cx="${x(index)}" cy="${y(value)}" r="2.2" fill="${color}"><title>${esc(name)}: ${Number(value).toFixed(1)} on ${snapshot.date}</title></circle>`;});});
  svg.setAttribute('viewBox',`0 0 ${width} ${height}`); svg.innerHTML=markup;
}
function renderChangeChart() {
  const activeExtended=extendedSelected?extendedSession():null;
  const hasValue=row=>(!activeExtended?.active||row._aggregate===true||row[`_live_${changeMode}`]===true)&&row[changeMode]!==null&&row[changeMode]!==''&&Number.isFinite(Number(row[changeMode]));
  const isLatest=Number(dateSelect.value)===data.snapshots.length-1;
  const source=[...((isLatest&&liveChanges)||current()?.daily_changes||[])];
  const rows=(changeView==='groups' ? groupPerformanceRows(source,hasValue) : source).filter(row=>!extendedSelected||hasValue(row));
  rows.sort((a,b)=>Number(hasValue(b))-Number(hasValue(a))||(hasValue(a)&&hasValue(b)?Number(b[changeMode])-Number(a[changeMode]):a.symbol.localeCompare(b.symbol)));
  const positiveAxis=Math.max(.1,...rows.filter(row=>hasValue(row)&&Number(row[changeMode])>=0).map(row=>Number(row[changeMode]))), negativeAxis=Math.max(.1,...rows.filter(row=>hasValue(row)&&Number(row[changeMode])<0).map(row=>Math.abs(Number(row[changeMode]))));
  const body=rows.map(row=>{ const available=hasValue(row),value=available?Number(row[changeMode]):0,axis=value>=0?positiveAxis:negativeAxis,width=available?Math.min(50,Math.abs(value)/axis*50):0,isGroup=changeView==='groups',target=isGroup?`data-change-group="${esc(row.symbol)}"`:`data-change-symbol="${esc(row.symbol)}"`; return `<div class="change-row clickable" ${target}><div class="change-label" title="Open ${isGroup?'theme':'ETF'} details: ${esc(row.symbol)}${row.group?` · ${esc(row.group)}`:''}"><strong>${esc(row.symbol)}</strong>${row.group?`<span>${esc(row.group)}</span>`:''}</div><div class="change-track">${available?`<span class="change-bar ${value>=0?'positive':'negative'}" style="width:${width}%"></span>`:''}</div><div class="change-value">${available?`${value>=0?'+':''}${value.toFixed(2)}%`:'—'}</div></div>`; }).join('');
  changeChart.innerHTML=`<div class="change-axis"><span></span><div class="axis-track"><span>−${negativeAxis.toFixed(1)}%</span><span>0%</span><span>+${positiveAxis.toFixed(1)}%</span></div><span></span></div>${body||'<p class="empty">No performance data is available.</p>'}`;
}
function groupPerformanceRows(source,hasValue) {
  const groups=new Map();
  source.forEach(row=>{if(!row.group)return;const item=groups.get(row.group)||{values:[],total:0};item.total+=1;if(hasValue(row))item.values.push(Number(row[changeMode]));groups.set(row.group,item);});
  return [...groups].map(([group,item])=>{const ordered=[...item.values].sort((a,b)=>a-b),middle=Math.floor(ordered.length/2),median=ordered.length?(ordered.length%2?ordered[middle]:(ordered[middle-1]+ordered[middle])/2):null;return {symbol:group,group:extendedSelected?`${ordered.length}/${item.total} ETFs reporting`:'',_aggregate:true,[changeMode]:median};});
}
async function refreshLivePerformance() {
  if(Number(dateSelect.value)!==data.snapshots.length-1){liveStatus.textContent=performanceStatus();return;}
  if(extendedSelected)changeMode=extendedSession().key;
  liveStatus.textContent='Loading current TradingView performance…';
  const fallback=current()?.daily_changes||[], groups=new Map(fallback.map(row=>[row.symbol,row.group])), tickers=fallback.map(row=>row.symbol);
  const query={markets:['america'],symbols:{},options:{lang:'en'},columns:['name','exchange','close','open','change','Perf.W','Perf.1M','Perf.3M','Perf.6M','Perf.Y','premarket_change','postmarket_change','overnight_change','update_mode'],filter:[{left:'name',operation:'in_range',right:tickers}],range:[0,500],ignore_unknown_fields:false};
  try {
    const response=await fetch('https://scanner.tradingview.com/america/scan',{method:'POST',body:JSON.stringify(query)});
    if(!response.ok)throw new Error(`TradingView returned ${response.status}`);
    const records=(await response.json()).data||[], bySymbol=new Map(fallback.map(row=>[row.symbol,{...row,postmarket:Number.isFinite(Number(completedAfterHours.values?.[row.symbol]))?Number(completedAfterHours.values[row.symbol]):null}]));
    records.forEach(record=>{const [symbol,,regularClose,regularOpen,regularChange,oneWeek,oneMonth,threeMonths,sixMonths,oneYear,premarket,postmarket,overnight,updateMode]=record.d;const row=bySymbol.get(symbol)||{symbol,group:groups.get(symbol)||''},savedAfterHours=completedAfterHours.values?.[symbol],savedOvernight=completedAfterHours.overnight?.values?.[symbol],present=value=>value!==null&&value!==''&&value!==undefined&&Number.isFinite(Number(value));
      row._live_premarket=present(premarket);row._live_overnight=present(overnight);row._live_postmarket=present(postmarket);row.premarket=row._live_premarket?Number(premarket):null;row.overnight=row._live_overnight?Number(overnight):(present(savedOvernight)?Number(savedOvernight):null);row.postmarket=row._live_postmarket?Number(postmarket):(present(savedAfterHours)?Number(savedAfterHours):null);row.intraday=Number(regularOpen)>0?100*(Number(regularClose)/Number(regularOpen)-1):null;row.one_day=Number.isFinite(Number(regularChange))?Number(regularChange):null;row.one_week=Number.isFinite(Number(oneWeek))?Number(oneWeek):null;row.one_month=Number.isFinite(Number(oneMonth))?Number(oneMonth):null;row.three_months=Number.isFinite(Number(threeMonths))?Number(threeMonths):null;row.six_months=Number.isFinite(Number(sixMonths))?Number(sixMonths):null;row.one_year=Number.isFinite(Number(oneYear))?Number(oneYear):null;row.update_mode=updateMode;bySymbol.set(symbol,row);});
    liveChanges=[...bySymbol.values()];
    const delayed=records.some(record=>String(record.d[13]||'').includes('900'));
    liveStatus.textContent=performanceStatus(delayed);
    renderChangeChart();
  } catch(error) {
    liveChanges=null; liveStatus.textContent=`Current quote unavailable · showing ${current()?.date||''} close`; renderChangeChart();
  }
}
function combinedHoldings(etfs) {
  const map=new Map(), denominator=Math.max(1,etfs.length);
  etfs.forEach(etf=>(data.holdings[etf]||[]).forEach(item=>{ const old=map.get(item.symbol)||{...item,weight:0,held_by:[]}; old.weight+=Number(item.weight||0)/denominator; old.held_by.push(etf); if(!old.average_dollar_volume_30d&&item.average_dollar_volume_30d) old.average_dollar_volume_30d=item.average_dollar_volume_30d; if(old.extension==null&&item.extension!=null) old.extension=item.extension; map.set(item.symbol,old); }));
  return [...map.values()].sort((a,b)=>b.weight-a.weight).slice(0,10);
}
function holdingRows(items) {
  return items.length?items.map(item=>`<tr><td>${esc(item.symbol)}</td><td>${esc(item.name)}</td><td>${pct(Number(item.weight)*100)}</td><td>${dollars(item.average_dollar_volume_30d)}</td><td>${num(item.extension)}×</td></tr>`).join(''):'<tr><td colspan="5" class="empty">No qualifying stock holdings were reported.</td></tr>';
}
function holdingsTable(items) { return `<table class="holdings-table"><thead><tr><th>Ticker</th><th>Company</th><th>Weight</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody>${holdingRows(items)}</tbody></table>`; }
function openDrawer(groupName, groupMembers, initialSymbol=null) {
  const symbols=groupMembers.map(row=>row.symbol), combined=combinedHoldings(symbols);
  drawerTitle.textContent=initialSymbol?`${initialSymbol} Holdings`:`${groupName} Holdings`;
  const memberRows=groupMembers.map(row=>`<tr><td>${esc(row.symbol)}</td><td>${esc(row.description)}</td><td>${pct(row.performance)}</td><td>${pct(row.adrp)}</td><td>${dollars(row.average_dollar_volume_30d)}</td><td>${num(row.extension)}×</td></tr>`).join('');
  const tabs=initialSymbol?[initialSymbol]:['Combined',...symbols];
  drawerBody.innerHTML=`<h3 class="drawer-subtitle">ETF statistics</h3><table class="member-table"><thead><tr><th>ETF</th><th>Description</th><th>Performance</th><th>ADR</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody>${memberRows}</tbody></table><h3 class="drawer-subtitle">Top stock holdings</h3><div class="tabs">${tabs.map((tab,i)=>`<button class="tab ${i===0?'active':''}" data-tab="${esc(tab)}">${esc(tab)}</button>`).join('')}</div><div id="holding-content">${holdingsTable(initialSymbol?(data.holdings[initialSymbol]||[]):combined)}</div><p class="footnote">Current disclosed holdings retrieved ${esc(data.holdings_as_of)}. Cash, bonds, swaps, futures, options, collateral, commodities, crypto assets, and fund holdings are excluded. Average dollar volume and extension use the latest completed regular-session close.</p>`;
  drawerBody.querySelector('.tabs').addEventListener('click',event=>{ const button=event.target.closest('.tab'); if(!button)return; drawerBody.querySelectorAll('.tab').forEach(tab=>tab.classList.remove('active')); button.classList.add('active'); const key=button.dataset.tab; document.getElementById('holding-content').innerHTML=holdingsTable(key==='Combined'?combined:(data.holdings[key]||[])); });
  dialog.showModal();
}
document.addEventListener('click',event=>{
  const leaderButton=event.target.closest('[data-leader-symbol]'); if(leaderButton){const row=Object.keys(frames).flatMap(frame=>members(frame)).find(item=>item.symbol===leaderButton.dataset.leaderSymbol);if(row)openDrawer(row.group,[row],row.symbol);return;}
  const groupRow=event.target.closest('.group-row'); if(groupRow){ const group=windowGroups(groupRow.dataset.frame).find(item=>item.group===groupRow.dataset.group); if(group)openDrawer(group.group,group.members); return; }
  const etfRow=event.target.closest('.etf-row'); if(etfRow){ const row=members(etfRow.dataset.frame).find(item=>item.symbol===etfRow.dataset.symbol); if(row)openDrawer(row.group,[row],row.symbol); }
  const chartGroup=event.target.closest('[data-change-group]'); if(chartGroup){const group=chartGroup.dataset.changeGroup,rows=(((Number(dateSelect.value)===data.snapshots.length-1&&liveChanges)||current()?.daily_changes||[]).filter(row=>row.group===group)).map(row=>({...row,description:''}));if(rows.length)openDrawer(group,rows);return;}
  const chartSymbol=event.target.closest('[data-change-symbol]'); if(chartSymbol){const row=(((Number(dateSelect.value)===data.snapshots.length-1&&liveChanges)||current()?.daily_changes||[]).find(item=>item.symbol===chartSymbol.dataset.changeSymbol));if(row)openDrawer(row.group,[{...row,description:''}],row.symbol);}
});
function exportSymbols(filter,prefix){ const rows=uniqueMembers(filter),csv=['symbol',...rows.map(row=>`"${row.symbol.replaceAll('"','""')}"`)].join('\n')+'\n'; const blob=new Blob([csv],{type:'text/csv'}),link=document.createElement('a'); link.download=`${prefix}_${current().date}.csv`; link.href=URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href); }
async function snapshot(){ const button=document.getElementById('snapshot'); if(typeof html2canvas!=='function'){alert('Snapshot exporter could not load.');return;} button.disabled=true; try{const canvas=await html2canvas(document.querySelector('main'),{backgroundColor:'#141414',scale:2,useCORS:true});const link=document.createElement('a');link.download=`${data.kind}-leadership-${current().date}.png`;link.href=canvas.toDataURL('image/png');link.click();}finally{button.disabled=false;} }
changeScope.innerHTML=data.kind==='themes'?'<button type="button" class="active" data-change-view="groups">Themes</button><button type="button" data-change-view="etfs">ETFs</button>':'';
dateSelect.innerHTML=data.snapshots.map((snapshot,index)=>`<option value="${index}">${snapshot.date}</option>`).join(''); dateSelect.value=Math.max(0,data.snapshots.length-1); dateSelect.addEventListener('change',()=>{render();refreshLivePerformance();});
changeScope.addEventListener('click',event=>{const button=event.target.closest('[data-change-view]');if(!button)return;changeView=button.dataset.changeView;changeScope.querySelectorAll('[data-change-view]').forEach(item=>item.classList.toggle('active',item===button));renderChangeChart();});
changeModes.addEventListener('click',event=>{ const button=event.target.closest('[data-change-mode]'); if(!button)return; extendedSelected=button.dataset.changeMode==='extended'; changeMode=extendedSelected?extendedSession().key:button.dataset.changeMode; changeModes.querySelectorAll('[data-change-mode]').forEach(item=>item.classList.toggle('active',item===button)); liveStatus.textContent=performanceStatus(); renderChangeChart(); });
document.getElementById('drawer-close').addEventListener('click',()=>dialog.close()); dialog.addEventListener('click',event=>{if(event.target===dialog)dialog.close();});
document.getElementById('export-leaders').addEventListener('click',()=>exportSymbols(()=>true,`${data.kind}_leaders`));
document.getElementById('export-nel')?.addEventListener('click',()=>exportSymbols(isNEL,`${data.kind}_nel`));
document.getElementById('snapshot').addEventListener('click',snapshot); render(); refreshLivePerformance(); setInterval(refreshLivePerformance,60000);
</script>
<script src="assets/date-select.js?v=2"></script>
</body>
</html>'''.replace("__TITLE__", title).replace("__LEADER_LABEL__", leader_label).replace("__FILTERED_SECTIONS__", filtered_sections).replace("__SECTOR_COLORS__", json.dumps(SECTOR_COLORS, separators=(",", ":"))).replace("__DATA__", data)


def write_etf_dashboards() -> list[Path]:
    paths = []
    for config in UNIVERSES:
        payload_path = OUTPUT_DIR / f"{config.key}_snapshots.json"
        if not payload_path.exists():
            continue
        payload = json.loads(payload_path.read_text(encoding="utf-8"))
        from site_chrome import apply_chrome
        config.page.write_text(apply_chrome(render_dashboard(payload, config.key), config.key), encoding="utf-8")
        paths.append(config.page)
    return paths


if __name__ == "__main__":
    for path in write_etf_dashboards():
        print(f"Saved {path}")
