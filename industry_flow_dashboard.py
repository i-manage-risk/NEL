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
}

def collect_industry_history(output_dir: Path) -> list[dict]:
    """Summarise every dated momentum-leader snapshot by industry and timeframe."""
    snapshots = []
    for path in sorted(output_dir.glob("momentum_leaders_*.csv")):
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
            "name", "industry", "dollar_volume_30d", "Perf.1M", "Perf.3M", "Perf.6M",
            "atr_extension_from_50d", "is_top_1m", "is_top_3m", "is_top_6m",
        ] if column in frame.columns]
        liquid_records = json.loads(frame.loc[:, leader_columns].to_json(orient="records"))
        nel_path = output_dir / f"non_extended_leaders_{match.group(1)}.csv"
        nel_records = []
        if nel_path.exists():
            nel = pd.read_csv(nel_path)
            columns = [column for column in [
                "name", "industry", "dollar_volume_30d", "Perf.1M", "Perf.3M", "Perf.6M",
                "atr_extension_from_50d", "is_top_1m", "is_top_3m", "is_top_6m",
            ] if column in nel.columns]
            nel_records = json.loads(nel.loc[:, columns].to_json(orient="records"))
        # `groups` comes only from full momentum-leader files. The NEL subset
        # below is a display table and cannot influence theme leadership.
        snapshots.append({"date": match.group(1), "groups": groups, "liquid": liquid_records, "nel": nel_records})
    return snapshots


def write_dashboard(output_dir: Path) -> Path:
    """Write an offline-friendly interactive dashboard with embedded history."""
    history = collect_industry_history(output_dir)
    dashboard = Path("industry_flow_dashboard.html")
    pages_entrypoint = Path("index.html")
    payload = json.dumps(history, separators=(",", ":"))
    template = r'''<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Industry leadership flow</title>
  <link rel="icon" type="image/png" href="assets/nel-favicon.png">
  <link rel="apple-touch-icon" href="assets/nel-favicon.png">
  <style>
    :root { color-scheme: dark; --bg:#141414; --panel:#2A2A2A; --line:#454545; --text:#F5F2E8; --muted:#F5F2E8; --orange:#ff9900; --cyan:#00ffff; --pink:#ff3366; --previous:#727272; }
    * { box-sizing:border-box; }
    body { margin:0; background:var(--bg); color:var(--text); font:15px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    main { width:100%; max-width:2200px; margin:0 auto; padding:24px 52px 40px; }
    h2 { font-size:17px; margin:0 0 14px; }
    .topbar { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin-bottom:22px; }
    .dashboard-title { margin:0; color:var(--text); font-size:19px; font-weight:650; letter-spacing:-.01em; }
    select { width:128px; height:34px; background:#F5F2E8; color:#141414; border:0; border-radius:7px; padding:7px 8px; font:600 13px/1 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
    .download-btn { width:128px; height:34px; background:#F5F2E8; color:#141414; border:0; border-radius:7px; padding:8px 10px; font:600 13px/1 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; cursor:pointer; }
    .topbar .download-btn { justify-self:end; }
    .download-btn:disabled { cursor:wait; opacity:.7; }
    .panel { background:var(--panel); border:1px solid var(--line); border-radius:10px; }
    .panel { padding:18px; margin:0; }
    .panel[data-frame="1m"] { border-top:3px solid var(--orange); } .panel[data-frame="3m"] { border-top:3px solid var(--cyan); } .panel[data-frame="6m"] { border-top:3px solid var(--pink); }
    .bars { display:grid; gap:11px; }
    .bar-row { display:grid; grid-template-columns:minmax(150px,220px) 1fr 42px; gap:10px; align-items:center; }
    .industry { overflow:visible; text-overflow:clip; white-space:normal; font-size:12px; line-height:1.25; }
    .track { height:22px; position:relative; background:#141414; border-radius:4px; }
    .bar { height:8px; border-radius:3px; position:absolute; left:0; transition:width .2s ease; }
    .bar.current { top:3px; background:var(--blue); } .bar.previous { bottom:3px; background:var(--previous); }
    .value { color:var(--text); text-align:right; font-variant-numeric:tabular-nums; }
    svg { width:100%; height:300px; display:block; overflow:visible; }
    .window-sections { display:grid; grid-template-columns:repeat(3,minmax(0,1fr)); gap:24px; align-items:start; }
    .section-heading { display:grid; grid-template-columns:1fr auto 1fr; align-items:center; margin:28px 0 14px; }
    .section-heading h2 { grid-column:2; margin:0; color:var(--text); font-size:19px; letter-spacing:-.01em; text-align:center; }
    .section-heading .download-btn { grid-column:3; justify-self:end; }
    .theme-card { padding:10px 12px; background:#141414; border-radius:4px; border-left:3px solid var(--orange); margin-bottom:12px; }
    .theme-card.frame-3m { border-color:var(--cyan); } .theme-card.frame-6m { border-color:var(--pink); }
    .theme-line { display:block; color:var(--text); font-size:13px; }
    .theme-line strong { font-size:16px; }
    .nel-window { background:var(--panel); border:1px solid var(--line); border-top:3px solid var(--orange); border-radius:10px; padding:18px; } .nel-window[data-frame="3m"] { border-top-color:var(--cyan); } .nel-window[data-frame="6m"] { border-top-color:var(--pink); }
    .nel-window h3 { margin:8px 0; font-size:14px; color:var(--orange); } .nel-window[data-frame="3m"] h3 { color:var(--cyan); } .nel-window[data-frame="6m"] h3 { color:var(--pink); }
    .table-wrap { overflow-x:auto; } table { width:100%; border-collapse:collapse; font-variant-numeric:tabular-nums; }
    .scrollable-table { max-height:251px; overflow:auto; } .scrollable-table th { position:sticky; top:0; background:var(--panel); z-index:1; }
    th, td { padding:10px 8px; border-bottom:1px solid var(--line); text-align:right; white-space:nowrap; } th:first-child, th:nth-child(2), td:first-child, td:nth-child(2) { text-align:left; } th { color:var(--text); font-size:12px; font-weight:600; } td:first-child { font-weight:650; }
    .high-liquidity { color:#ccff00; }
    .empty { color:var(--text); padding:30px 0; }
    .snapshot-date { color:#F5F2E8; font-size:14px; font-weight:600; }
    @media (max-width:980px) { .window-sections { grid-template-columns:1fr; } .bar-row { grid-template-columns:130px 1fr 34px; font-size:12px; } main { padding:18px 16px; } }
    @media (max-width:640px) { .topbar { grid-template-columns:1fr; justify-items:start; gap:12px; } .dashboard-title { justify-self:center; } .topbar .download-btn { justify-self:start; } .section-heading { grid-template-columns:1fr auto; } .section-heading h2 { grid-column:1; text-align:left; } .section-heading .download-btn { grid-column:2; } }
  </style>
</head>
<body>
<main>
  <div class="topbar"><select id="date" aria-label="Snapshot date"></select><h1 class="dashboard-title">Thematic Leadership</h1><button id="download-image" class="download-btn" type="button">Snapshot</button></div>
  <div id="leadership-sections" class="window-sections"></div>
  <div class="section-heading"><h2>Liquid Leaders (LL)</h2><button id="download-ll" class="download-btn" type="button">Export LL</button></div>
  <div id="liquid-sections" class="window-sections"></div>
  <div class="section-heading"><h2>Non-Extended Leaders (NEL)</h2><button id="download-nel" class="download-btn" type="button">Export NEL</button></div>
  <div id="nel-sections" class="window-sections"></div>
</main>
<script src="https://cdn.jsdelivr.net/npm/html2canvas@1.4.1/dist/html2canvas.min.js"></script>
<script>
const history = __DATA__;
const dateSelect = document.getElementById('date');
const leadershipSections = document.getElementById('leadership-sections');
const liquidSections = document.getElementById('liquid-sections');
const nelSections = document.getElementById('nel-sections');
const downloadButton = document.getElementById('download-image');
const downloadLiquidButton = document.getElementById('download-ll');
const downloadNelButton = document.getElementById('download-nel');
const flowMeta = { '1m': { label:'1 month', color:'#ff9900' }, '3m': { label:'3 months', color:'#00ffff' }, '6m': { label:'6 months', color:'#ff3366' } };
const rankColors = ['#5C7CFA', '#E9C46A', '#E76F51', '#70C1B3', '#C77DFF'];

function counts(snapshot, frame) { return snapshot?.groups?.[frame] || {}; }
function total(map) { return Object.values(map).reduce((a,b) => a + b, 0); }
function escapeHTML(value) { return String(value ?? '—').replace(/[&<>'"]/g, char => ({'&':'&amp;','<':'&lt;','>':'&gt;',"'":'&#39;','"':'&quot;'}[char])); }
function formatPct(value) { return Number.isFinite(Number(value)) ? `${Number(value).toFixed(1)}%` : '—'; }
function formatNumber(value) { return Number.isFinite(Number(value)) ? Number(value).toFixed(2) : '—'; }
function formatDollarVolume(value) { const amount = Number(value); if (!Number.isFinite(amount) || amount <= 0) return '—'; if (amount >= 1_000_000_000) return `$${Math.ceil(amount / 1_000_000_000)}B`; return `$${Math.ceil(amount / 10_000_000) * 10}M`; }
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
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    const table = document.getElementById(`liquid-table-${frame}`);
    const themeCard = document.getElementById(`liquid-theme-${frame}`);
    const top = Object.entries(counts(snapshot, frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0];
    themeCard.innerHTML = `<span class="theme-line"><strong>${top ? escapeHTML(top[0]) : '—'}</strong>${top ? ` (${top[1]} Liquid Leader${top[1] === 1 ? '' : 's'})` : ''}</span>`;
    const rows = records.filter(row => row[flag] === true || String(row[flag]).toLowerCase() === 'true').sort((a, b) => Number(b[performance]) - Number(a[performance]));
    table.innerHTML = rows.length ? rows.map(row => { const highLiquidity = Number(row.dollar_volume_30d) > 450_000_000; const className = highLiquidity ? 'high-liquidity' : ''; const isLeaderTheme = top && row.industry === top[0]; const industryStyle = isLeaderTheme ? ` style="color:${flowMeta[frame].color};font-weight:650"` : ''; return `<tr><td class="${className}">${escapeHTML(row.name)}</td><td${industryStyle}>${escapeHTML(row.industry)}</td><td>${formatPct(row[performance])}</td><td class="${className}">${formatDollarVolume(row.dollar_volume_30d)}</td><td>${formatNumber(row.atr_extension_from_50d)}×</td></tr>`; }).join('') : '<tr><td colspan="5" class="empty">No liquid leaders.</td></tr>';
  });
}
function renderNEL(snapshot) {
  const records = snapshot?.nel || [];
  [['1m', 'Perf.1M', 'is_top_1m'], ['3m', 'Perf.3M', 'is_top_3m'], ['6m', 'Perf.6M', 'is_top_6m']].forEach(([frame, performance, flag]) => {
    const nelTable = document.getElementById(`nel-table-${frame}`);
    const themeCard = document.getElementById(`theme-${frame}`);
    const top = Object.entries(counts(snapshot, frame)).sort((a,b) => b[1]-a[1] || a[0].localeCompare(b[0]))[0];
    themeCard.innerHTML = `<span class="theme-line"><strong>${top ? escapeHTML(top[0]) : '—'}</strong>${top ? ` (${top[1]} Liquid Leader${top[1] === 1 ? '' : 's'})` : ''}</span>`;
    const rows = records.filter(row => row[flag] === true || String(row[flag]).toLowerCase() === 'true').sort((a, b) => Number(b[performance]) - Number(a[performance]));
    nelTable.innerHTML = rows.length ? rows.map(row => { const highLiquidity = Number(row.dollar_volume_30d) > 450_000_000; const className = highLiquidity ? 'high-liquidity' : ''; const isLeaderTheme = top && row.industry === top[0]; const industryStyle = isLeaderTheme ? ` style="color:${flowMeta[frame].color};font-weight:650"` : ''; return `<tr><td class="${className}">${escapeHTML(row.name)}</td><td${industryStyle}>${escapeHTML(row.industry)}</td><td>${formatPct(row[performance])}</td><td class="${className}">${formatDollarVolume(row.dollar_volume_30d)}</td><td>${formatNumber(row.atr_extension_from_50d)}×</td></tr>`; }).join('') : '<tr><td colspan="5" class="empty">No NEL leaders.</td></tr>';
  });
}
function render() {
  const current = currentSnapshot(), index = Number(dateSelect.value), previous = history[index-1];
  leadershipSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="panel" data-frame="${frame}"><h2 style="color:${meta.color}">${meta.label} leadership</h2><div id="bars-${frame}" class="bars"></div><h2 style="margin-top:22px">Leadership over time</h2><svg id="trend-${frame}" role="img" aria-label="${meta.label} industry leader counts across available snapshots"></svg></section>`).join('');
  liquidSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="nel-window" data-frame="${frame}"><h3>${meta.label} LL</h3><div id="liquid-theme-${frame}" class="theme-card frame-${frame}"></div><div class="table-wrap scrollable-table"><table><thead><tr><th>Symbol</th><th>Industry</th><th>Performance</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody id="liquid-table-${frame}"></tbody></table></div></section>`).join('');
  nelSections.innerHTML = Object.entries(flowMeta).map(([frame, meta]) => `<section class="nel-window" data-frame="${frame}"><h3>${meta.label} NEL</h3><div id="theme-${frame}" class="theme-card frame-${frame}"></div><div class="table-wrap"><table><thead><tr><th>Symbol</th><th>Industry</th><th>Performance</th><th>Avg $ Vol</th><th>Extension</th></tr></thead><tbody id="nel-table-${frame}"></tbody></table></div></section>`).join('');
  Object.keys(flowMeta).forEach(frame => { const rankedNames = renderBars(current, previous, frame, document.getElementById(`bars-${frame}`)); renderTrend(frame, document.getElementById(`trend-${frame}`), rankedNames); });
  renderLiquid(current);
  renderNEL(current);
}
function downloadSymbols(key, filePrefix) {
  const snapshot = currentSnapshot();
  const symbols = [...new Set((snapshot?.[key] || []).map(row => String(row.name || '').trim()).filter(Boolean))].sort();
  const csv = ['symbol', ...symbols.map(symbol => `"${symbol.replaceAll('"', '""')}"`)].join('\n') + '\n';
  const blob = new Blob([csv], { type:'text/csv;charset=utf-8' });
  const link = document.createElement('a'); link.download = `${filePrefix}_symbols_${snapshot.date}.csv`; link.href = URL.createObjectURL(blob); link.click(); URL.revokeObjectURL(link.href);
}
async function downloadPageImage() {
  if (typeof html2canvas !== 'function') { window.alert('The image exporter could not load. Check your connection and try again.'); return; }
  downloadButton.disabled = true; downloadButton.textContent = 'Creating image…';
  try {
    const canvas = await html2canvas(document.querySelector('main'), { backgroundColor:'#141414', scale:2, useCORS:true, windowWidth:document.documentElement.scrollWidth, windowHeight:document.documentElement.scrollHeight, onclone: clonedDocument => { const bar = clonedDocument.querySelector('.topbar'); bar.innerHTML = `<span class="snapshot-date">${currentSnapshot().date}</span><h1 class="dashboard-title">Thematic Leadership</h1><span></span>`; } });
    const link = document.createElement('a'); link.download = `industry-leadership-${currentSnapshot().date}.png`; link.href = canvas.toDataURL('image/png'); link.click();
  } finally { downloadButton.disabled = false; downloadButton.textContent = 'Snapshot'; }
}
if (!history.length) { document.querySelector('main').innerHTML = '<p class="empty">Run the scanner once to create a momentum-leader snapshot.</p>'; } else { updateDates(); dateSelect.addEventListener('change', render); downloadButton.addEventListener('click', downloadPageImage); downloadLiquidButton.addEventListener('click', () => downloadSymbols('liquid', 'liquid_leaders')); downloadNelButton.addEventListener('click', () => downloadSymbols('nel', 'nel')); window.addEventListener('resize', render); render(); }
</script>
</body>
</html>'''
    rendered = template.replace("__DATA__", payload)
    dashboard.write_text(rendered, encoding="utf-8")
    pages_entrypoint.write_text(rendered, encoding="utf-8")
    return dashboard
