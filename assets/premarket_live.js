const output = document.querySelector('#tickers');
const copyButton = document.querySelector('#copy');
let currentTickers = [];

const query = {
  markets: ['america'],
  symbols: {},
  options: { lang: 'en' },
  columns: [
    'name', 'exchange', 'industry', 'close', 'SMA30', 'SMA50', 'ATRP',
    'premarket_close', 'premarket_change', 'premarket_volume',
    'average_volume_10d_calc', 'average_volume_30d_calc', 'average_volume_60d_calc',
  ],
  filter: [
    { left: 'type', operation: 'equal', right: 'stock' },
    { left: 'exchange', operation: 'in_range', right: ['NASDAQ', 'NYSE', 'AMEX'] },
    { left: 'premarket_change', operation: 'egreater', right: 3 },
  ],
  sort: { sortBy: 'premarket_volume', sortOrder: 'desc', nullsFirst: false },
  range: [0, 5000],
  ignore_unknown_fields: false,
};

function qualifies(record) {
  const [, , industry, close, sma30, sma50, atrp, premarketPrice, change, premarketVolume, averageVolume10d, averageVolume30d] = record.d;
  const atrExtension = (Number(premarketPrice) - Number(sma50)) / (Number(sma50) * (Number(atrp) / 100));
  return !String(industry || '').toLowerCase().includes('biotech')
    && Number(close) > 0
    && Number(sma30) > 0
    && Number(sma50) > 0
    && Number(atrp) > 0
    && Number(premarketPrice) > 0
    && Number(averageVolume10d) > 350000
    && Number(averageVolume30d) > 0
    && Number(sma30) * Number(averageVolume30d) > 30000000
    && Number(change) >= 3
    && Number(premarketVolume) >= 0
    && atrExtension <= 4;
}

function ranked(records) {
  return records
    .filter(qualifies)
    .sort((a, b) => {
      const rvolDifference = (Number(b.d[9]) / Number(b.d[12])) - (Number(a.d[9]) / Number(a.d[12]));
      if (rvolDifference) return rvolDifference;
      const volumeDifference = Number(b.d[9]) - Number(a.d[9]);
      return volumeDifference || String(a.s).localeCompare(String(b.s));
    })
    .slice(0, 20)
}

function premarketRvol(record) {
  return Number(record.d[9]) / Number(record.d[12]);
}

function atrExtension(record) {
  return (Number(record.d[7]) - Number(record.d[5])) / (Number(record.d[5]) * (Number(record.d[6]) / 100));
}

function render(records) {
  const header = `${'Symbol'.padEnd(22)}${'PM RVOL'.padStart(8)}  ${'50d Ext.'.padStart(8)}`;
  const rows = records.map(record => (
    `${String(record.s).padEnd(22)}${`${premarketRvol(record).toFixed(2)}×`.padStart(8)}  ${`${atrExtension(record).toFixed(2)}×`.padStart(8)}`
  ));
  return [header, ...rows].join('\n');
}

async function refresh() {
  output.textContent = 'Loading…';
  try {
    // A text body keeps this a browser-safe CORS request to TradingView.
    const response = await fetch('https://scanner.tradingview.com/america/scan', {
      method: 'POST',
      body: JSON.stringify(query),
    });
    if (!response.ok) throw new Error(`TradingView returned ${response.status}`);
    const payload = await response.json();
    const records = ranked(payload.data || []);
    currentTickers = records.map(record => record.s);
    output.textContent = records.length ? render(records) : 'No matching premarket movers.';
  } catch {
    currentTickers = [];
    output.textContent = 'Live data unavailable. Refresh to try again.';
  }
}

copyButton.addEventListener('click', async () => {
  await navigator.clipboard.writeText(currentTickers.join('\n'));
  copyButton.textContent = 'Copied';
  setTimeout(() => { copyButton.textContent = 'Copy'; }, 1200);
});

refresh();
setInterval(refresh, 60000);
