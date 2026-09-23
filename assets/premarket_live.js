const scannerBase = 'https://scanner.tradingview.com';
const pmBody = document.querySelector('#pm-body');
const pmStatus = document.querySelector('#pm-status');
const pmCopyButton = document.querySelector('#pm-copy');
const currentBody = document.querySelector('#current-body');
const currentStatus = document.querySelector('#current-status');
const currentCopyButton = document.querySelector('#current-copy');
const openingBody = document.querySelector('#opening-body');
const openingStatus = document.querySelector('#opening-status');
const openingCopyButton = document.querySelector('#opening-copy');
let pmTickers = [];
let currentTickers = [];
let openingTickers = [];

const pmQuery = {
  markets: ['america'], symbols: {}, options: { lang: 'en' },
  columns: ['name', 'exchange', 'industry', 'close', 'SMA30', 'SMA50', 'ATR', 'premarket_close', 'premarket_open', 'premarket_high', 'premarket_low', 'premarket_change', 'premarket_volume', 'average_volume_10d_calc', 'average_volume_30d_calc', 'average_volume_60d_calc'],
  filter: [{ left: 'type', operation: 'equal', right: 'stock' }, { left: 'exchange', operation: 'in_range', right: ['NASDAQ', 'NYSE', 'AMEX'] }, { left: 'premarket_change', operation: 'egreater', right: 3 }],
  sort: { sortBy: 'premarket_volume', sortOrder: 'desc', nullsFirst: false }, range: [0, 5000], ignore_unknown_fields: false,
};

const openingColumns = ['name', 'exchange', 'close', 'open', 'high', 'low', 'volume', 'ATR', 'ADRP', 'average_volume_30d_calc', 'average_volume_60d_calc', 'relative_volume_10d_calc', 'relative_volume_10d_calc|5', 'SMA50', 'change'];
const openingQuery = {
  markets: ['america'], symbols: {}, options: { lang: 'en' }, columns: openingColumns,
  filter: [{ left: 'type', operation: 'equal', right: 'stock' }, { left: 'exchange', operation: 'in_range', right: ['NASDAQ', 'NYSE', 'AMEX'] }],
  sort: { sortBy: 'volume', sortOrder: 'desc', nullsFirst: false }, range: [0, 5000], ignore_unknown_fields: false,
};
function lockedOpeningQuery(tickers) {
  return {
    markets: [], symbols: { tickers }, options: { lang: 'en' }, columns: openingColumns,
    filter: [{ left: 'is_primary', operation: 'equal', right: true }],
    range: [0, 50], ignore_unknown_fields: false,
  };
}

async function scan(query, market = 'america') {
  const response = await fetch(`${scannerBase}/${market}/scan`, { method: 'POST', body: JSON.stringify(query) });
  if (!response.ok) throw new Error(`TradingView returned ${response.status}`);
  return (await response.json()).data || [];
}

function pmExtension(record) { return (Number(record.d[7]) - Number(record.d[5])) / Number(record.d[6]); }
function pmQualifies(record) {
  const [, , industry, close, sma30, sma50, atr, premarketPrice, premarketOpen, premarketHigh, premarketLow, change, premarketVolume, averageVolume10d, averageVolume30d, averageVolume60d] = record.d;
  return !String(industry || '').toLowerCase().includes('biotech') && Number(close) > 0 && Number(sma30) > 0 && Number(sma50) > 0 && Number(atr) > 0 && Number(premarketPrice) > 0 && Number(premarketOpen) > 0 && Number(premarketHigh) > 0 && Number(premarketLow) > 0 && Number(averageVolume10d) > 350000 && Number(averageVolume30d) > 0 && Number(averageVolume60d) > 0 && Number(sma30) * Number(averageVolume30d) > 30000000 && Number(change) >= 3 && Number(premarketVolume) >= 0 && pmExtension(record) <= 4;
}
function rankPm(records) {
  return records.filter(pmQualifies).sort((a, b) => {
    const difference = (Number(b.d[12]) / Number(b.d[15])) - (Number(a.d[12]) / Number(a.d[15]));
    return difference || Number(b.d[12]) - Number(a.d[12]) || String(a.s).localeCompare(String(b.s));
  }).slice(0, 20);
}
function pmRvol(record) { return Number(record.d[12]) / Number(record.d[15]); }
function pmMetrics(record) {
  const [, , , , , , atr, price, pmOpen, pmHigh, pmLow, change] = record.d;
  return [pmRvol(record), Number(change) / 100, (Number(price) - Number(pmOpen)) / Number(pmOpen), (Number(price) - Number(pmLow)) / Number(atr), (Number(pmHigh) - Number(pmLow)) / Number(atr), pmExtension(record)];
}

function currentRelativeVolume(record) { return Number(record.d[11]); }
function openingRelativeVolumeAtTime(record) { return Number(record.d[12]); }
function baseOpeningQualifies(record) {
  const [, , close, open, high, low, , atr, adr, averageVolume30d, averageVolume60d, , , sma50] = record.d;
  return Number(close) > 0 && Number(open) > 0 && Number(high) > 0 && Number(low) > 0 && Number(atr) > 0 && Number(sma50) > 0 && Number(adr) > 4 && Number(averageVolume30d) > 350000 && Number(averageVolume60d) > 0 && Number(close) * Number(averageVolume30d) > 50000000;
}
function openingQualifies(record) {
  return baseOpeningQualifies(record) && openingRelativeVolumeAtTime(record) > 1;
}
function currentQualifies(record) {
  return baseOpeningQualifies(record) && currentRelativeVolume(record) > 1;
}
function rankOpening(records) {
  return records.filter(openingQualifies).sort((a, b) => openingRelativeVolumeAtTime(b) - openingRelativeVolumeAtTime(a) || Number(b.d[4]) - Number(a.d[4]) || String(a.s).localeCompare(String(b.s))).slice(0, 20);
}
function rankCurrent(records) {
  return records.filter(currentQualifies).sort((a, b) => currentRelativeVolume(b) - currentRelativeVolume(a) || Number(b.d[4]) - Number(a.d[4]) || String(a.s).localeCompare(String(b.s))).slice(0, 20);
}
function newYorkClock() {
  const parts = new Intl.DateTimeFormat('en-CA', { timeZone: 'America/New_York', year: 'numeric', month: '2-digit', day: '2-digit', hour: '2-digit', minute: '2-digit', hourCycle: 'h23' }).formatToParts(new Date()).reduce((values, part) => ({ ...values, [part.type]: part.value }), {});
  return { date: `${parts.year}-${parts.month}-${parts.day}`, minutes: Number(parts.hour) * 60 + Number(parts.minute) };
}
function localLock(date) { try { return JSON.parse(localStorage.getItem(`opening-rvol-lock-${date}`) || 'null'); } catch { return null; } }
async function remoteLock(date) {
  try {
    const response = await fetch(`outputs/opening_rvol_lock_${date}.json`, { cache: 'no-store' });
    const payload = await response.json();
    return payload.market_date === date && Array.isArray(payload.tickers) ? payload.tickers : null;
  } catch { return null; }
}
function formatPercent(value) { return `${(Number(value) * 100).toFixed(0)}%`; }
function regularMetrics(record, relativeVolume) {
  const [, , close, open, high, low, , atr, , , , , , sma50, change] = record.d;
  return [relativeVolume(record), Number(change) / 100, (Number(close) - Number(open)) / Number(open), (Number(close) - Number(low)) / Number(atr), (Number(high) - Number(low)) / Number(atr), (Number(close) - Number(sma50)) / Number(atr)];
}
function renderRvolTable(body, records, metricValues) {
  body.replaceChildren(...records.map(record => {
    const tr = document.createElement('tr');
    const metrics = metricValues(record);
    const values = [String(record.s), ...metrics.map(formatPercent)];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      if (index === 4) cell.className = metrics[3] > 0.25 && metrics[3] < 0.75 ? 'in-range' : 'out-of-range';
      tr.append(cell);
    });
    return tr;
  }));
}
async function refreshPm() {
  pmStatus.textContent = 'Loading…';
  try {
    const records = rankPm(await scan(pmQuery));
    pmTickers = records.map(record => record.s);
    renderRvolTable(pmBody, records, pmMetrics);
    pmStatus.textContent = records.length ? 'Live data' : 'No matching premarket movers.';
  } catch { pmTickers = []; pmBody.replaceChildren(); pmStatus.textContent = 'Live data unavailable. Refresh to try again.'; }
}
async function refreshOpening() {
  openingStatus.textContent = 'Loading…';
  try {
    const clock = newYorkClock();
    const records = await scan(openingQuery);
    let locked = await remoteLock(clock.date);
    const inLockWindow = clock.minutes >= 570 && clock.minutes < 575;
    if (!locked && inLockWindow) {
      locked = rankOpening(records).map(record => record.s);
      localStorage.setItem(`opening-rvol-lock-${clock.date}`, JSON.stringify(locked));
    }
    if (!locked) locked = localLock(clock.date);
    if (!locked) {
      openingTickers = [];
      openingBody.replaceChildren();
      openingStatus.textContent = 'Waiting for the 9:35 AM ET lock.';
      return;
    }
    const order = new Map(locked.map((ticker, index) => [ticker, index]));
    const liveLocked = (await scan(lockedOpeningQuery(locked), 'global')).filter(record => order.has(record.s)).sort((a, b) => order.get(a.s) - order.get(b.s));
    openingTickers = locked;
    renderRvolTable(openingBody, liveLocked, record => regularMetrics(record, openingRelativeVolumeAtTime));
    openingStatus.textContent = 'Locked tickers · live data';
  } catch {
    openingTickers = [];
    openingBody.replaceChildren();
    openingStatus.textContent = 'Live data unavailable. Refresh to try again.';
  }
}
async function refreshCurrent() {
  currentStatus.textContent = 'Loading…';
  try {
    const records = rankCurrent(await scan(openingQuery));
    currentTickers = records.map(record => record.s);
    renderRvolTable(currentBody, records, record => regularMetrics(record, currentRelativeVolume));
    currentStatus.textContent = 'Live data';
  } catch {
    currentTickers = [];
    currentBody.replaceChildren();
    currentStatus.textContent = 'Live data unavailable. Refresh to try again.';
  }
}
function bindCopy(button, tickers) {
  button.addEventListener('click', async () => {
    await navigator.clipboard.writeText(tickers().join('\n'));
    button.textContent = 'Copied';
    setTimeout(() => { button.textContent = 'Copy'; }, 1200);
  });
}
bindCopy(pmCopyButton, () => pmTickers);
bindCopy(currentCopyButton, () => currentTickers);
bindCopy(openingCopyButton, () => openingTickers);
refreshPm(); refreshCurrent(); refreshOpening();
setInterval(() => { refreshPm(); refreshCurrent(); refreshOpening(); }, 60000);
