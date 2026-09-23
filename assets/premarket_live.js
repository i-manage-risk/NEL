const scannerBase = 'https://scanner.tradingview.com';
const pmOutput = document.querySelector('#pm-tickers');
const pmCopyButton = document.querySelector('#pm-copy');
const openingBody = document.querySelector('#opening-body');
const openingStatus = document.querySelector('#opening-status');
const openingCopyButton = document.querySelector('#opening-copy');
let pmTickers = [];
let openingTickers = [];

const pmQuery = {
  markets: ['america'], symbols: {}, options: { lang: 'en' },
  columns: ['name', 'exchange', 'industry', 'close', 'SMA30', 'SMA50', 'ATRP', 'premarket_close', 'premarket_change', 'premarket_volume', 'average_volume_10d_calc', 'average_volume_30d_calc', 'average_volume_60d_calc'],
  filter: [{ left: 'type', operation: 'equal', right: 'stock' }, { left: 'exchange', operation: 'in_range', right: ['NASDAQ', 'NYSE', 'AMEX'] }, { left: 'premarket_change', operation: 'egreater', right: 3 }],
  sort: { sortBy: 'premarket_volume', sortOrder: 'desc', nullsFirst: false }, range: [0, 5000], ignore_unknown_fields: false,
};

const openingColumns = ['name', 'exchange', 'close', 'low', 'volume', 'ATR', 'ADRP', 'average_volume_30d_calc', 'average_volume_60d_calc', 'relative_volume_10d_calc|5'];
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

function pmExtension(record) { return (Number(record.d[7]) - Number(record.d[5])) / (Number(record.d[5]) * (Number(record.d[6]) / 100)); }
function pmQualifies(record) {
  const [, , industry, close, sma30, sma50, atrp, premarketPrice, change, premarketVolume, averageVolume10d, averageVolume30d, averageVolume60d] = record.d;
  return !String(industry || '').toLowerCase().includes('biotech') && Number(close) > 0 && Number(sma30) > 0 && Number(sma50) > 0 && Number(atrp) > 0 && Number(premarketPrice) > 0 && Number(averageVolume10d) > 350000 && Number(averageVolume30d) > 0 && Number(averageVolume60d) > 0 && Number(sma30) * Number(averageVolume30d) > 30000000 && Number(change) >= 3 && Number(premarketVolume) >= 0 && pmExtension(record) <= 4;
}
function rankPm(records) {
  return records.filter(pmQualifies).sort((a, b) => {
    const difference = (Number(b.d[9]) / Number(b.d[12])) - (Number(a.d[9]) / Number(a.d[12]));
    return difference || Number(b.d[9]) - Number(a.d[9]) || String(a.s).localeCompare(String(b.s));
  }).slice(0, 20);
}
function renderPm(records) {
  const header = `${'Symbol'.padEnd(22)}${'PM RVOL'.padStart(8)}  ${'50d Ext.'.padStart(8)}`;
  return [header, ...records.map(record => {
    const rvol = Number(record.d[9]) / Number(record.d[12]);
    return `${String(record.s).padEnd(22)}${`${rvol.toFixed(2)}×`.padStart(8)}  ${`${pmExtension(record).toFixed(2)}×`.padStart(8)}`;
  })].join('\n');
}

function openingRelativeVolumeAtTime(record) { return Number(record.d[9]); }
function openingQualifies(record) {
  const [, , close, low, , atr, adr, averageVolume30d, averageVolume60d] = record.d;
  return Number(close) > 0 && Number(low) > 0 && Number(atr) > 0 && Number(adr) > 4 && openingRelativeVolumeAtTime(record) > 1 && Number(averageVolume30d) > 350000 && Number(averageVolume60d) > 0 && Number(close) * Number(averageVolume30d) > 50000000;
}
function rankOpening(records) {
  return records.filter(openingQualifies).sort((a, b) => openingRelativeVolumeAtTime(b) - openingRelativeVolumeAtTime(a) || Number(b.d[4]) - Number(a.d[4]) || String(a.s).localeCompare(String(b.s))).slice(0, 20);
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
function renderOpening(records) {
  openingBody.replaceChildren(...records.map(record => {
    const tr = document.createElement('tr');
    const distance = (Number(record.d[2]) - Number(record.d[3])) / Number(record.d[5]);
    const values = [String(record.s), `${openingRelativeVolumeAtTime(record).toFixed(2)}×`, `${(Number(record.d[4]) / Number(record.d[8])).toFixed(2)}×`, `${(distance * 100).toFixed(0)}%`];
    values.forEach((value, index) => {
      const cell = document.createElement('td');
      cell.textContent = value;
      if (index === 3) cell.className = distance > 0.25 && distance < 0.75 ? 'in-range' : 'out-of-range';
      tr.append(cell);
    });
    return tr;
  }));
}
async function refreshPm() {
  pmOutput.textContent = 'Loading…';
  try {
    const records = rankPm(await scan(pmQuery));
    pmTickers = records.map(record => record.s);
    pmOutput.textContent = records.length ? renderPm(records) : 'No matching premarket movers.';
  } catch { pmTickers = []; pmOutput.textContent = 'Live data unavailable. Refresh to try again.'; }
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
    renderOpening(liveLocked);
    openingStatus.textContent = 'Locked tickers · live data';
  } catch {
    openingTickers = [];
    openingBody.replaceChildren();
    openingStatus.textContent = 'Live data unavailable. Refresh to try again.';
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
bindCopy(openingCopyButton, () => openingTickers);
refreshPm(); refreshOpening();
setInterval(() => { refreshPm(); refreshOpening(); }, 60000);
