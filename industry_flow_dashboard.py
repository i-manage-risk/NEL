"""Generate a self-contained interactive industry-leadership dashboard."""

from __future__ import annotations

import json
import re
from pathlib import Path

import pandas as pd


TIMEFRAMES = {
    "1m": "is_top_1m",
    "3m": "is_top_3m",
    "6m": "is_top_6m",
    "1y": "is_top_1y",
}

def collect_industry_history(output_dir: Path, prefix: str = "") -> list[dict]:
    """Summarise every dated momentum-leader snapshot by industry and timeframe."""
    snapshots = []
    for path in sorted(output_dir.glob(f"{prefix}momentum_leaders_*.csv")):
        match = re.search(r"(\d{4}-\d{2}-\d{2})\.csv$", path.name)
        if not match:
            continue
        frame = pd.read_csv(path)
        if "industry" not in frame.columns:
            continue
        groups = {}
        for label, flag in TIMEFRAMES.items():
            if flag not in frame.columns:
                continue
            counts = (
                frame.loc[frame[flag].fillna(False).astype(bool), "industry"]
                .fillna("Unclassified")
                .value_counts()
                .to_dict()
            )
            groups[label] = {str(industry): int(count) for industry, count in counts.items()}
        leader_columns = [column for column in [
            "name", "paired_etf", "industry", "average_volume_30d_calc", "average_dollar_volume_30d", "dollar_volume_30d", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
            "atr_extension_from_50d", "is_top_1m", "is_top_3m", "is_top_6m", "is_top_1y",
        ] if column in frame.columns]
        liquid_records = json.loads(frame.loc[:, leader_columns].to_json(orient="records"))
        nel_path = output_dir / f"{prefix}non_extended_leaders_{match.group(1)}.csv"
        nel_records = []
        if nel_path.exists():
            nel = pd.read_csv(nel_path)
            columns = [column for column in [
                "name", "paired_etf", "industry", "average_volume_30d_calc", "average_dollar_volume_30d", "dollar_volume_30d", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
                "atr_extension_from_50d", "is_top_1m", "is_top_3m", "is_top_6m", "is_top_1y",
            ] if column in nel.columns]
            nel_records = json.loads(nel.loc[:, columns].to_json(orient="records"))
        tight_path = output_dir / f"{prefix}tight_non_extended_leaders_{match.group(1)}.csv"
        tight_records = []
        if tight_path.exists():
            tight = pd.read_csv(tight_path)
            columns = [column for column in [
                "name", "paired_etf", "industry", "average_volume_30d_calc", "average_dollar_volume_30d", "dollar_volume_30d", "Perf.1M", "Perf.3M", "Perf.6M", "Perf.Y",
                "atr_extension_from_50d", "is_top_1m", "is_top_3m", "is_top_6m", "is_top_1y", "coil_setup", "rmv_15d",
                "rmv_tight_days", "coil_range_5d_atr", "true_range_ratio_3d", "true_range_ratio_5d",
            ] if column in tight.columns]
            tight_records = json.loads(tight.loc[:, columns].to_json(orient="records"))
        # `groups` comes only from full momentum-leader files. The NEL subset
        # below is a display table and cannot influence theme leadership.
        snapshots.append({"date": match.group(1), "groups": groups, "liquid": liquid_records, "nel": nel_records, "tight": tight_records})
    return snapshots


def write_dashboard(output_dir: Path, profile: str = "liquid") -> Path:
    """Write an offline-friendly interactive dashboard with embedded history."""
    is_super = profile == "super"
    prefix = "super_liquid_" if is_super else ""
    history = collect_industry_history(output_dir, prefix)
    dashboard = Path("super-liquid.html") if is_super else Path("industry_flow_dashboard.html")
    pages_entrypoint = None if is_super else Path("index.html")
    payload = json.dumps(history, separators=(",", ":"))
    template = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Liquid Leadership | NEL</title>
  <meta name="description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta name="robots" content="index, follow">
  <link rel="canonical" href="https://i-manage-risk.github.io/NEL/">
  <meta property="og:type" content="website">
  <meta property="og:site_name" content="Liquid Leadership">
  <meta property="og:title" content="Liquid Leadership | NEL">
  <meta property="og:description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta property="og:url" content="https://i-manage-risk.github.io/NEL/">
  <meta property="og:image" content="https://i-manage-risk.github.io/NEL/assets/nel-social-preview.png">
  <meta property="og:image:width" content="1731">
  <meta property="og:image:height" content="909">
  <meta name="twitter:card" content="summary_large_image">
  <meta name="twitter:title" content="Liquid Leadership | NEL">
  <meta name="twitter:description" content="Find non-extended leaders from the market’s most liquid momentum stocks.">
  <meta name="twitter:image" content="https://i-manage-risk.github.io/NEL/assets/nel-social-preview.png">
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="apple-touch-icon" href="assets/nel-favicon.png">
  <style>
    :root { color-scheme: dark; --bg:#141414; --panel:#2A2A2A; --line:#454545; --text:#F5F2E8; --muted:#F5F2E8; --orange:#ff9900; --cyan:#00ffff; --pink:#ff3366; --green:#86d65d; --previous:#727272; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:15px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:100%; max-width:2200px; margin:0 auto; padding:24px 40px 40px; }
    .site-nav { display:flex; justify-content:center; gap:7px; margin:0 0 18px; }
    .site-nav a { min-width:92px; padding:7px 13px; border:1px solid var(--line); border-radius:7px; color:var(--text); text-align:center; text-decoration:none; font-size:14px; font-weight:650; }
    .site-nav a:hover,.site-nav a.active { background:var(--text); color:var(--bg); border-color:var(--text); }
    h2 { font-size:17px; margin:0 0 14px; }
    .topbar { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin-bottom:22px; }
    .dashboard-title { margin:0; color:var(--text); font-size:19px; font-weight:650; letter-spacing:-.01em; }
    select { width:128px; height:34px; background:#F5F2E8; color:#141414; border:0; border-radius:7px; padding:7px 8px; font:600 13px/1 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    .download-btn { width:128px; height:34px; background:#F5F2E8; color:#141414; border:0; border-radius:7px; padding:8px 10px; font:600 13px/1 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; cursor:pointer; }
    .topbar .download-btn { justify-self:end; }
    .download-btn:disabled { cursor:wait; opacity:.7; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; }
    .panel { padding:18px; margin:0; }
    .panel[data-frame="1m"] { border-top:3px solid var(--orange); } .panel[data-frame="3m"] { border-top:3px solid var(--cyan); } .panel[data-frame="6m"] { border-top:3px solid var(--pink); } .panel[data-frame="1y"] { border-top:3px solid var(--green); }
    .bars { display:grid; gap:11px; }
    .bar-row { display:grid; grid-template-columns:minmax(150px,220px) 1fr 42px; gap:10px; align-items:center; }
    .industry { overflow:visible; text-overflow:clip; white-space:normal; font-size:12px; line-height:1.25; }
    .track { height:22px; position:relative; background:#141414; border-radius:4px; }
    .bar { height:8px; border-radius:3px; position:absolute; left:0; transition:width .2s ease; }
    .bar.current { top:3px; background:var(--blue); } .bar.previous { bottom:3px; background:var(--previous); }
    .value { color:var(--text); text-align:right; font-variant-numeric:tabular-nums; }
    svg { width:100%; height:300px; display:block; overflow:visible; }
    .window-sections { display:grid; grid-template-columns:repeat(4,minmax(0,1fr)); gap:20px; align-items:start; }
    .section-heading { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin:28px 0 14px; }
    .section-heading h2 { grid-column:2; margin:0; color:var(--text); font-size:19px; letter-spacing:-.01em; text-align:center; }
    .section-actions { grid-column:3; justify-self:end; display:flex; gap:8px; }
    .theme-card { padding:10px 12px; background:#141414; border-radius:4px; border-left:3px solid var(--orange); margin-bottom:12px; }
    .theme-card.frame-3m { border-color:var(--cyan); } .theme-card.frame-6m { border-color:var(--pink); } .theme-card.frame-1y { border-color:var(--green); }
    .theme-line { display:block; color:var(--text); font-size:13px; }
    .theme-line strong { font-size:16px; }
    .nel-window { background:var(--panel); border:1px solid var(--line); border-top:3px solid var(--orange); border-radius:10px; padding:18px; } .nel-window[data-frame="3m"] { border-top-color:var(--cyan); } .nel-window[data-frame="6m"] { border-top-color:var(--pink); } .nel-window[data-frame="1y"] { border-top-color:var(--green); }
    .nel-window h3 { margin:8px 0; font-size:14px; color:var(--orange); } .nel-window[data-frame="3m"] h3 { color:var(--cyan); } .nel-window[data-frame="6m"] h3 { color:var(--pink); } .nel-window[data-frame="1y"] h3 { color:var(--green); }
    .table-wrap { overflow:visible; } table { width:100%; border-collapse:collapse; table-layout:fixed; font-variant-numeric:tabular-nums; }
    .scrollable-table { max-height:251px; overflow-y:auto; } .scrollable-table th { position:sticky; top:0; background:var(--panel); z-index:1; }
    th, td { padding:8px 5px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; } th:first-child, th:nth-child(2), td:first-child, td:nth-child(2) { text-align:left; } th:nth-child(1) { width:13%; } th:nth-child(2) { width:39%; } th:nth-child(3) { width:17%; } th:nth-child(4) { width:17%; } th:nth-child(5) { width:14%; } td:nth-child(2) { white-space:normal; overflow-wrap:anywhere; } th { color:var(--text); font-size:12px; font-weight:600; } td:first-child { font-weight:650; }
    .tight-table th:nth-child(1) { width:14%; } .tight-table th:nth-child(2) { width:35%; } .tight-table th:nth-child(3) { width:15%; } .tight-table th:nth-child(4) { width:14%; } .tight-table th:nth-child(5) { width:11%; } .tight-table th:nth-child(6) { width:11%; }
    .super-page table:not(.tight-table) th:nth-child(1) { width:29%; } .super-page table:not(.tight-table) th:nth-child(2) { width:38%; } .super-page table:not(.tight-table) th:nth-child(3) { width:18%; } .super-page table:not(.tight-table) th:nth-child(4) { width:15%; }
    .super-page .tight-table th:nth-child(1) { width:23%; } .super-page .tight-table th:nth-child(2) { width:30%; } .super-page .tight-table th:nth-child(3) { width:14%; } .super-page .tight-table th:nth-child(4) { width:12%; } .super-page .tight-table th:nth-child(5) { width:9%; } .super-page .tight-table th:nth-child(6) { width:12%; }
    .super-page th,.super-page td { padding-left:3px; padding-right:3px; } .super-page td:first-child { font-size:13px; letter-spacing:-.01em; }
    .high-liquidity { color:#ccff00; }
    .empty { color:var(--text); padding:30px 0; }
    .snapshot-date { color:#F5F2E8; font-size:14px; font-weight:600; }
    @media (max-width:1750px) { .window-sections { grid-template-columns:repeat(2,minmax(0,1fr)); } }
    @media (max-width:1180px) { .window-sections { grid-template-columns:1fr; } .bar-row { grid-template-columns:130px 1fr 34px; font-size:12px; } main { padding:18px 16px; } }
    @media (max-width:640px) { .site-nav { justify-content:flex-start; overflow-x:auto; } .topbar { grid-template-columns:1fr; justify-items:start; gap:12px; } .dashboard-title { justify-self:center; } .topbar .download-btn { justify-self:start; } .section-heading { grid-template-columns:1fr auto; } .section-heading h2 { grid-column:1; text-align:left; } .section-actions { grid-column:2; } }
  </style>
  <link rel="stylesheet" href="assets/date-select.css?v=2">
</head>
<body>
<main>
  <nav class="site-nav" aria-label="Dashboard pages"><a class="active" href="index.html">Stocks</a><a href="themes.html">Themes</a><a href="sectors.html">Sectors</a><a href="breadth.html">Breadth</a></nav>
  <div class="topbar"><select id="date" aria-label="Snapshot date"></select><h1 id="thematic-title" class="dashboard-title">Thematic Leadership</h1><button id="download-image" class="download-btn" type="button">Snapshot</button></div>
  <div id="leadership-sections" class="window-sections"></div>
  <div class="section-heading"><h2 id="liquid-title">Liquid Leaders (LL)</h2><div class="section-actions"><button id="copy-ll" class="download-btn" type="button">Copy</button><button id="download-ll" class="download-btn" type="button">Export LL</button></div></div>
  <div id="liquid-sections" class="window-sections"></div>
  <div class="section-heading"><h2 id="nel-title">Non-Extended Leaders (NEL)</h2><div class="section-actions"><button id="copy-nel" class="download-btn" type="button">Copy</button><button id="download-nel" class="download-btn" type="button">Export NEL</button></div></div>
  <div id="nel-sections" class="window-sections"></div>
  <div class="section-heading"><h2 id="tight-title">Tight Non-Extended Leaders (T-NEL)</h2><div class="section-actions"><button id="copy-tight" class="download-btn" type="button">Copy</button><button id="download-tight" class="download-btn" type="button">Export T-NEL</button></div></div>
  <div id="tight-sections" class="window-sections"></div>
</main>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
const history = __DATA__;
const useShareVolume = __USE_SHARE_VOLUME__;
const dateSelect = document.getElementById('date');
const thematicTitle = document.getElementById('thematic-title');
const liquidTitle = document.getElementById('liquid-title');
const nelTitle = document.getElementById('nel-title');
const tightTitle = document.getElementById('tight-title');
const leadershipSections = document.getElementById('leadership-sections');
const liquidSections = document.getElementById('liquid-sections');
const nelSections = document.getElementById('nel-sections');
const tightSections = document.getElementById('tight-sections');
const downloadButton = document.getElementById('download-image');
const downloadLiquidButton = document.getElementById('download-ll');
const downloadNelButton = document.getElementById('download-nel');
const downloadTightButton = document.getElementById('download-tight');
const copyLiquidButton = document.getElementById('copy-ll');
const copyNelButton = document.getElementById('copy-nel');
const copyTightButton = document.getElementById('copy-tight');
const flowMeta = { '1m': { label:'1 month', color:'#ff9900' }, '3m': { label:'3 months', color:'#00ffff' }, '6m': { label:'6 months', color:'#ff3366' }, '1y': { label:'1 year', color:'#86d65d' } };
const rankColors = ['#5C7CFA', '#E9C46A', '#E76F51', '#70C1B3', '#C77DFF'];

function counts(snapshot, frame) { return snapshot?.groups?.[frame] || {}; }
function total(map) { return Object.values(map).reduce((a,b) => a + b, 0); }
function escapeHTML(value) { return String(value ?? '—').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char])); }
function formatPct(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'; }
function formatNumber(value) { return Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—'; }
function formatDollarVolume(value) { const amount = Number(value); if (!Number.isFinite(amount) || amount <= 0) return '—'; if (amount >= 1_000_000_000) return `$${Math.ceil(amount / 1_000_000_000)}B`; return `$${Math.ceil(amount / 10_000_000) * 10}M`; }
function formatShareVolume(value) { const amount = Number(value); if (!Number.isFinite(amount) || amount <= 0) return '—'; if (amount >= 1_000_000) return `${(amount / 1_000_000).toFixed(amount >= 10_000_000 ? 0 : 1)}M`; if (amount >= 1_000) return `${Math.round(amount / 1_000)}K`; return Math.round(amount).toLocaleString(); }
function averageDollarVolume(row) { return row.average_dollar_volume_30d ?? row.dollar_volume_30d; }
function liquidityValue(row) { return useShareVolume ? row.average_volume_30d_calc : averageDollarVolume(row); }
function formatLiquidity(value) { return useShareVolume ? formatShareVolume(value) : formatDollarVolume(value); }
function displaySymbol(row) { return useShareVolume && row.paired_etf ? `${row.name} / ${row.paired_etf}` : row.name; }
function updateDates() {
  dateSelect.innerHTML = history.map((d,i) => `<option value="${i}">${d.date}</option>`).join('');
  dateSelect.value = Math.max(0, history.length - 1);
}
function currentSnapshot() { return history[Number(dateSelect.value)] || null; }
function renderBars(current, previous, frame, container) {
  const now = counts(current, frame), then = counts(previous, frame);
  const names = [...new Set([...Object.keys(now), ...Object.keys(then)])].sort((a,b) => (now[b]||0) - (now[a]||0) || (then[b]||0) - (then[a]||0)).slice(0, 5);
  if (!names.length) { container.innerHTML = '<p class="empty">No leader data is available for this snapshot.</p>'; return []; }
  const max = Math.max(1, ...names.flatMap(n => [now[n]||0, then[n]||0]));
  container.innerHTML = names.map((name, index) => { const color = rankColors[index]; return `<div class="bar-row"><div class="industry" style="color:${color}" title="${name}">${name}</div><div class="track"><div class="bar current" style="width:${(now[name]||0)/max*100}%;background:${color}" title="Selected: ${now[name]||0}"></div><div class="bar previous" style="width:${(then[name]||0)/max*100}%" title="Prior: ${then[name]||0}"></div></div><div class="value">${now[name]||0}</div></div>`; }).join('');
  return names;
}
function renderTrend(frame, svg, names) {
  const active = history.filter(d => d.groups?.[frame]);
  if (active.length < 2) { svg.innerHTML = '<text x="20" y="45" fill="#c0bdb4">Add future daily snapshots to see industry leadership trends.</text>'; return; }
  const width = Math.max(620, svg.clientWidth || 900), height = 300, left = 42, right = 28, top = 18, bottom = 34;
  const max = Math.max(1, ...active.flatMap(d => Object.values(counts(d, frame))));
  const x = i => left + i * ((width-left-right) / Math.max(1, active.length-1));
  const y = value => top + (max-value) * ((height-top-bottom)/max);
  let markup = `<line x1="${left}" y1="${height-bottom}" x2="${width-right}" y2="${height-bottom}" stroke="#454545"/><line x1="${left}" y1="${top}" x2="${left}" y2="${height-bottom}" stroke="#454545"/>`;
  for (let i=0;i<=max;i++) markup += `<text x="${left-8}" y="${y(i)+4}" text-anchor="end" font-size="11" fill="#F5F2E8">${i}</text>`;
  active.forEach((d,i) => markup += `<text x="${x(i)}" y="${height-12}" text-anchor="middle" font-size="11" fill="#F5F2E8">${d.date.slice(5)}</text>`);
  names.forEach((name, index) => { const color = rankColors[index]; const points = active.map((d,i) => `${x(i)},${y(counts(d,frame)[name]||0)}`).join(' '); markup += `<polyline points="${points}" fill="none" stroke="${color}" stroke-width="2.5"/>`; active.forEach((d,i) => markup += `<circle cx="${x(i)}" cy="${y(counts(d,frame)[name]||0)}" r="3" fill="${color}"><title>${escapeHTML(name)}: ${counts(d,frame)[name]||0} on ${d.date}</title></circle>`); });
  svg.setAttribute('viewBox', `0 0 ${width} ${height}`); svg.innerHTML = markup;
}
function renderLiquid(snapshot) {
  const records = snapshot?.liquid || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m'], ['1y', 'Perf.Y', 'is_top_1y']].forEach(([frame, performance, flag]) => {
    const table = document.getElementById(`liquid-table-${frame}`);
    const themeCard = document.getElementById(`liquid-theme-${frame}`);
    const top = Object.entries(counts(snapshot, frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0];
    themeCard.innerHTML = `<span class="theme-line"><strong>${top ? escapeHTML(top[0]) : '—'}</strong>${top ? ` (${top[1]} Liquid Leader${top[1] === 1 ? '' : 's'})` : ''}</span>`;
    const rows = records.filter(row => row[flag] === true || String(row[flag]).toLowerCase() === 'true').sort((a, b) => Number(b[performance]) - Number(a[performance]));
    table.innerHTML = rows.length ? rows.map(row => { const dollarVolume = liquidityValue(row); const highLiquidity = !useShareVolume && Number(dollarVolume) > 450_000_000; const className = highLiquidity ? 'high-liquidity' : ''; const isLeaderTheme = top && row.industry === top[0]; const industryStyle = isLeaderTheme ? ` style="color:${flowMeta[frame].color};font-weight:650"` : ''; return `<tr><td class="${className}">${escapeHTML(displaySymbol(row))}</td><td${industryStyle}>${escapeHTML(row.industry)}</td><td>${formatPct(row[performance])}</td><td class="liquidity-column ${className}">${formatLiquidity(dollarVolume)}</td><td>${formatNumber(row.atr_extension_from_50d)}×</td></tr>`; }).join('') : '<tr><td colspan="5" class="empty">No liquid leaders.</td></tr>';
  });
}
function renderNEL(snapshot) {
  const records = snapshot?.nel || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m'], ['1y', 'Perf.Y', 'is_top_1y']].forEach(([frame, performance, flag]) => {
    const nelTable = document.getElementById(`nel-table-${frame}`);
    const themeCard = document.getElementById(`theme-${frame}`);
    const top = Object.entries(counts(snapshot, frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0];
    themeCard.innerHTML = `<span class="theme-line"><strong>${top ? escapeHTML(top[0]) : '—'}</strong>${top ? ` (${top[1]} Liquid Leader${top[1] === 1 ? '' : 's'})` : ''}</span>`;
    const rows = records.filter(row => row[flag] === true || String(row[flag]).toLowerCase() === 'true').sort((a, b) => Number(b[performance]) - Number(a[performance]));
    nelTable.innerHTML = rows.length ? rows.map(row => { const dollarVolume = liquidityValue(row); const highLiquidity = !useShareVolume && Number(dollarVolume) > 450_000_000; const className = highLiquidity ? 'high-liquidity' : ''; const isLeaderTheme = top && row.industry === top[0]; const industryStyle = isLeaderTheme ? ` style="color:${flowMeta[frame].color};font-weight:650"` : ''; return `<tr><td class="${className}">${escapeHTML(displaySymbol(row))}</td><td${industryStyle}>${escapeHTML(row.industry)}</td><td>${formatPct(row[performance])}</td><td class="liquidity-column ${className}">${formatLiquidity(dollarVolume)}</td><td>${formatNumber(row.atr_extension_from_50d)}×</td></tr>`; }).join('') : '<tr><td colspan="5" class="empty">No NEL leaders.</td></tr>';
  });
}
function renderTight(snapshot) {
  const records = snapshot?.tight || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m'], ['1y', 'Perf.Y', 'is_top_1y']].forEach(([frame, performance, flag]) => {
    const table = document.getElementById(`tight-table-${frame}`);
    const top = Object.entries(counts(snapshot, frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0];
    const rows = records.filter(row => row[flag] === true || String(row[flag]).toLowerCase() === 'true').sort((a, b) => Number(a.rmv_15d) - Number(b.rmv_15d) || Number(b[performance]) - Number(a[performance]));
    table.innerHTML = rows.length ? rows.map(row => { const dollarVolume = averageDollarVolume(row); const highLiquidity = Number(dollarVolume) > 450_000_000; const className = highLiquidity ? 'high-liquidity' : ''; const isLeaderTheme = top && row.industry === top[0]; const industryStyle = isLeaderTheme ? ` style="color:${flowMeta[frame].color};font-weight:650"` : ''; const rmvTitle = `${row.rmv_tight_days || 0} consecutive RMV-tight day${Number(row.rmv_tight_days) === 1 ? '' : 's'}`; return `<tr><td class="${className}">${escapeHTML(displaySymbol(row))}</td><td${industryStyle}>${escapeHTML(row.industry)}</td><td>${formatPct(row[performance])}</td><td>${escapeHTML(row.coil_setup)}</td><td title="${rmvTitle}">${formatNumber(row.rmv_15d)}</td><td>${formatNumber(row.atr_extension_from_50d)}×</td></tr>`; }).join('') : '<tr><td colspan="6" class="empty">No tight NEL setups.</td></tr>';
  });
}
function render() {
  const current = currentSnapshot(), index = Number(dateSelect.value), previous = history[index-1];
  liquidTitle.textContent = `Liquid Leaders (LL) - ${(current.liquid || []).length} Tickers`;
  nelTitle.textContent = `Non-Extended Leaders (NEL) - ${(current.nel || []).length} Tickers`;
  tightTitle.textContent = `Tight Non-Extended Leaders (T-NEL) - ${(current.tight || []).length} Tickers`;
  leadershipSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="panel" data-frame="${frame}"><h2 style="color:${meta.color}">${meta.label} leadership</h2><div id="bars-${frame}" class="bars"></div><h2 style="margin-top:22px">Leadership over time</h2><svg id="trend-${frame}" role="img" aria-label="${meta.label} industry leader counts across available snapshots"></svg></section>`).join('');
  liquidSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="nel-window" data-frame="${frame}"><h3>${meta.label} LL</h3><div id="liquid-theme-${frame}" class="theme-card frame-${frame}"></div><div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th>Industry</th><th>Performance</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody id="liquid-table-${frame}"></tbody></table></div></section>`).join('');
  nelSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="nel-window" data-frame="${frame}"><h3>${meta.label} NEL</h3><div id="theme-${frame}" class="theme-card frame-${frame}"></div><div class="table-wrap"><table><thead><tr><th>Symbol</th><th>Industry</th><th>Performance</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody id="nel-table-${frame}"></tbody></table></div></section>`).join('');
  tightSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="nel-window" data-frame="${frame}"><h3>${meta.label} T-NEL</h3><div class="table-wrap"><table class="tight-table"><thead><tr><th>Symbol</th><th>Industry</th><th>Performance</th><th>Coil</th><th>RMV</th><th>Extension</th></tr></thead><tbody id="tight-table-${frame}"></tbody></table></div></section>`).join('');
  Object.keys(flowMeta).forEach(frame => { const rankedNames = renderBars(current, previous, frame, document.getElementById(`bars-${frame}`)); renderTrend(frame, document.getElementById(`trend-${frame}`), rankedNames); });
  renderLiquid(current);
  renderNEL(current);
  renderTight(current);
}
function downloadSymbols(key, filePrefix) {
  const snapshot = currentSnapshot();
  const symbols = [...new Set((snapshot?.[key] || []).map(row => String(row.name || '').trim()).filter(Boolean))].sort();
  const csv = ['symbol', ...symbols.map(symbol => `"${symbol.replaceAll('"', '""')}"`)].join('\n') + '\n';
  const blob = new Blob([csv], { type:'text/csv;charset=utf-8' });
  const link = document.createElement('a'); link.download = `${filePrefix}_symbols_${snapshot.date}.csv`; link.href = URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href);
}
async function copySymbols(key, button) {
  const symbols = [...new Set((currentSnapshot()?.[key] || []).map(row => String(row.name || '').trim()).filter(Boolean))].sort();
  const text = symbols.join(', ');
  if (!text) return;
  try {
    if (navigator.clipboard?.writeText) await navigator.clipboard.writeText(text);
    else { const area = document.createElement('textarea'); area.value = text; document.body.append(area); area.select(); document.execCommand('copy'); area.remove(); }
    const original = button.textContent; button.textContent = 'Copied'; setTimeout(() => { button.textContent = original; }, 1300);
  } catch { window.alert('Could not copy symbols.'); }
}
async function downloadPageImage() {
  if (typeof html2canvas !== 'function') { window.alert('The image exporter could not load. Check your connection and try again.'); return; }
  downloadButton.disabled = true; downloadButton.textContent = 'Creating image…';
  try {
    const canvas = await html2canvas(document.querySelector('main'), { backgroundColor:'#141414', scale:2, useCORS:true, windowWidth:document.documentElement.scrollWidth, windowHeight:document.documentElement.scrollHeight, onclone: clonedDocument => { const bar = clonedDocument.querySelector('.topbar'); bar.innerHTML = `<span class="snapshot-date">${currentSnapshot().date}</span><h1 class="dashboard-title">${thematicTitle.textContent}</h1><span></span>`; } });
    const link = document.createElement('a'); link.download = `industry-leadership-${currentSnapshot().date}.png`; link.href = canvas.toDataURL('image/png'); link.click();
  } finally { downloadButton.disabled = false; downloadButton.textContent = 'Snapshot'; }
}
if (!history.length) { document.querySelector('main').innerHTML = '<p class="empty">Run the scanner once to create a momentum-leader snapshot.</p>'; } else { updateDates(); dateSelect.addEventListener('change', render); downloadButton.addEventListener('click', downloadPageImage); downloadLiquidButton.addEventListener('click', () => downloadSymbols('liquid', 'liquid_leaders')); downloadNelButton.addEventListener('click', () => downloadSymbols('nel', 'nel')); downloadTightButton.addEventListener('click', () => downloadSymbols('tight', 'tight_nel')); copyLiquidButton.addEventListener('click', () => copySymbols('liquid', copyLiquidButton)); copyNelButton.addEventListener('click', () => copySymbols('nel', copyNelButton)); copyTightButton.addEventListener('click', () => copySymbols('tight', copyTightButton)); window.addEventListener('resize', render); render(); }
</script>
<script src="assets/date-select.js?v=2"></script>
</body>
</html>'''
    rendered = template.replace("__DATA__", payload).replace(
        "__USE_SHARE_VOLUME__", "true" if is_super else "false"
    )
    nav = '<nav class="site-nav" aria-label="Dashboard pages"><a href="index.html">Liquid Leaders</a><a href="super-liquid.html">Super Liquid Leaders</a><a href="themes.html">Themes</a><a href="sectors.html">Sectors</a><a href="breadth.html">Breadth</a></nav>'
    active_label = "Super Liquid Leaders" if is_super else "Liquid Leaders"
    nav = nav.replace(f'>{active_label}</a>', f' class="active">{active_label}</a>')
    rendered = re.sub(r'<nav class="site-nav".*?</nav>', nav, rendered, count=1)
    if is_super:
        replacements = {
            "Liquid Leadership | NEL": "Super Liquid Leadership | NEL",
            "Thematic Leadership": "Super Liquid Thematic Leadership",
            "Liquid Leaders (LL)": "Super Liquid Leaders (SLL)",
            "Non-Extended Leaders (NEL)": "Super Liquid Non-Extended Leaders (S-NEL)",
            "Tight Non-Extended Leaders (T-NEL)": "Tight Super Liquid Leaders (T-SNEL)",
            "Export LL": "Export SLL", "Export NEL": "Export S-NEL", "Export T-NEL": "Export T-SNEL",
            "industry-leadership-": "super-liquid-leadership-",
            "'liquid_leaders'": "'super_liquid_leaders'",
            "downloadSymbols('nel', 'nel')": "downloadSymbols('nel', 'super_liquid_nel')",
            "'tight_nel'": "'super_liquid_tight_nel'",
            "${meta.label} LL": "${meta.label} SLL",
            "${meta.label} NEL": "${meta.label} S-NEL",
            "${meta.label} T-NEL": "${meta.label} T-SNEL",
        }
        for old, new in replacements.items():
            rendered = rendered.replace(old, new)
        rendered = rendered.replace("<th>Avg $ Vol</th>", "")
        rendered = rendered.replace("<td class=\"liquidity-column ${className}\">${formatLiquidity(dollarVolume)}</td>", "")
        rendered = rendered.replace("<body>", '<body class="super-page">', 1)
    dashboard.write_text(rendered, encoding="utf-8")
    if pages_entrypoint is not None:
        pages_entrypoint.write_text(rendered, encoding="utf-8")
    return dashboard
