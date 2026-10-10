(() => {
  const chart = document.querySelector('#chart');
  const spxChart = document.querySelector('#spx-chart');
  const metricControls = document.querySelector('#controls');
  const chartHead = document.querySelector('.chart-head');
  if (!chart || !spxChart || !metricControls || !chartHead || typeof rows === 'undefined' || typeof views === 'undefined') return;

  const chartStyles = document.createElement('link');
  chartStyles.rel = 'stylesheet';
  chartStyles.href = 'assets/breadth-chart.css?v=5';
  document.head.append(chartStyles);

  const breadthCard = chart.closest('.chart');
  const spxCard = spxChart.closest('.chart');
  const spxNote = spxCard.querySelector('.legend');
  breadthCard.classList.add('breadth-chart-card');
  spxCard.classList.add('spx-chart-card');
  const historyIntro = document.createElement('div');
  historyIntro.className = 'history-intro';
  historyIntro.innerHTML = '<div><div class="history-kicker">Historical context</div><h2>Breadth and price through time</h2><p>Compare participation measures with SPX across the same selected window. The values on the right belong to the Time Machine date.</p></div>';
  breadthCard.before(historyIntro);
  const breadthStage = document.createElement('div');
  breadthStage.className = 'chart-stage';
  chart.before(breadthStage);
  breadthStage.append(chart);
  const spxStage = document.createElement('div');
  spxStage.className = 'chart-stage';
  spxChart.before(spxStage);
  spxStage.append(spxChart);
  const spxRangeBadge = document.createElement('span');
  spxRangeBadge.className = 'chart-window-badge';
  spxCard.querySelector('.chart-head').append(spxRangeBadge);

  let selectedMetric = 'daily';
  let selectedRange = '3m';
  const rangeDefinitions = [
    { key: '1w', label: '1W', amount: 7, unit: 'day' },
    { key: '1m', label: '1M', amount: 1, unit: 'month' },
    { key: '3m', label: '3M', amount: 3, unit: 'month' },
    { key: '6m', label: '6M', amount: 6, unit: 'month' },
    { key: 'ytd', label: 'YTD', unit: 'ytd' },
    { key: '1y', label: '1Y', amount: 1, unit: 'year' },
    { key: '3y', label: '3Y', amount: 3, unit: 'year' },
    { key: '5y', label: '5Y', amount: 5, unit: 'year' },
  ];
  const rangeControls = document.createElement('div');
  rangeControls.className = 'controls chart-range-controls';
  rangeControls.setAttribute('aria-label', 'Chart range');
  const toolbar = document.createElement('div');
  toolbar.className = 'chart-toolbar';
  const measureBlock = document.createElement('div');
  measureBlock.className = 'chart-control-block';
  const rangeBlock = document.createElement('div');
  rangeBlock.className = 'chart-control-block';
  const measureLabel = document.createElement('span');
  measureLabel.className = 'chart-control-label';
  measureLabel.textContent = 'Measure';
  const rangeLabel = document.createElement('span');
  rangeLabel.className = 'chart-control-label';
  rangeLabel.textContent = 'Chart range';
  chartHead.after(toolbar);
  measureBlock.append(measureLabel, metricControls);
  rangeBlock.append(rangeLabel, rangeControls);
  toolbar.append(measureBlock, rangeBlock);

  metricControls.innerHTML = '';
  Object.entries(views).forEach(([key, view]) => {
    const button = document.createElement('button');
    button.textContent = view.label;
    button.addEventListener('click', () => { selectedMetric = key; renderAll(); });
    metricControls.append(button);
  });
  const valid = value => value !== null && value !== undefined && Number.isFinite(Number(value));
  const singleLineColor = '#86d65d';
  const svgText = (x, y, value, options = '') => `<text x="${x}" y="${y}" ${options}>${value}</text>`;
  const linePath = (data, key, x, y) => data.map((row, index) => `${index ? 'L' : 'M'}${x(index).toFixed(1)},${y(row[key]).toFixed(1)}`).join(' ');

  function signed(value, digits = 1) {
    return `${value > 0 ? '+' : ''}${Number(value).toFixed(digits)}`;
  }

  function attachHover(target, data, series, x, y, options = {}) {
    const namespace = 'http://www.w3.org/2000/svg';
    const stage = target.closest('.chart-stage');
    let tooltip = stage.querySelector('.chart-hover-tooltip');
    if (!tooltip) {
      tooltip = document.createElement('div');
      tooltip.className = 'chart-hover-tooltip';
      tooltip.hidden = true;
      stage.append(tooltip);
    }
    const layer = document.createElementNS(namespace, 'g');
    layer.classList.add('chart-hover-layer');
    layer.setAttribute('visibility', 'hidden');
    const guide = document.createElementNS(namespace, 'line');
    guide.classList.add('chart-hover-guide');
    guide.setAttribute('y1', '24');
    guide.setAttribute('y2', '294');
    layer.append(guide);
    const dots = series.map(item => {
      const dot = document.createElementNS(namespace, 'circle');
      dot.classList.add('chart-hover-dot');
      dot.setAttribute('r', '5');
      dot.setAttribute('fill', item.color);
      layer.append(dot);
      return dot;
    });
    target.append(layer);
    target.style.cursor = 'crosshair';

    target.onpointermove = event => {
      const matrix = target.getScreenCTM();
      if (!matrix) return;
      const point = target.createSVGPoint();
      point.x = event.clientX;
      point.y = event.clientY;
      const local = point.matrixTransform(matrix.inverse());
      if (local.x < 28 || local.x > 805 || local.y < 18 || local.y > 305) {
        layer.setAttribute('visibility', 'hidden');
        tooltip.hidden = true;
        return;
      }
      const index = Math.max(0, Math.min(data.length - 1, Math.round((local.x - 28) / (805 - 28) * Math.max(data.length - 1, 1))));
      const row = data[index], px = x(index);
      guide.setAttribute('x1', px);
      guide.setAttribute('x2', px);
      series.forEach((item, position) => {
        dots[position].setAttribute('cx', px);
        dots[position].setAttribute('cy', y(row[item.key]));
      });
      layer.setAttribute('visibility', 'visible');

      const latest = data.at(-1);
      const values = series.map(item => {
        const value = Number(row[item.key]), current = Number(latest[item.key]);
        const change = options.percentChange
          ? `${signed((current / value - 1) * 100, 2)}%`
          : options.points
            ? `${signed(current - value, 2)} pts`
            : signed(current - value, options.ratio ? 2 : 0);
        return `<div class="chart-hover-row"><span><i style="background:${item.color}"></i>${item.label}</span><b>${options.format(value)}</b><em>to now ${change}</em></div>`;
      }).join('');
      tooltip.innerHTML = `<div class="chart-hover-date">${row.date}</div>${values}`;
      tooltip.hidden = false;
      const stageBounds = stage.getBoundingClientRect();
      const tooltipWidth = tooltip.offsetWidth;
      const preferredLeft = event.clientX - stageBounds.left + 14;
      tooltip.style.left = `${Math.max(8, Math.min(stageBounds.width - tooltipWidth - 8, preferredLeft))}px`;
      tooltip.style.top = `${Math.max(8, Math.min(stageBounds.height - tooltip.offsetHeight - 8, event.clientY - stageBounds.top - 20))}px`;
    };
    target.onpointerleave = () => {
      layer.setAttribute('visibility', 'hidden');
      tooltip.hidden = true;
    };
  }

  function selectedDate() {
    const index = Number(window.BREADTH_ASOF_INDEX || 0);
    return new Date(`${rows[index].date}T12:00:00`);
  }

  function rangeCutoff(definition, endDate = selectedDate()) {
    const cutoff = new Date(endDate);
    if (definition.unit === 'ytd') return new Date(endDate.getFullYear(), 0, 1, 12);
    if (definition.unit === 'day') cutoff.setDate(cutoff.getDate() - definition.amount);
    if (definition.unit === 'month' || definition.unit === 'year') {
      const originalDay = cutoff.getDate();
      cutoff.setDate(1);
      if (definition.unit === 'month') cutoff.setMonth(cutoff.getMonth() - definition.amount);
      if (definition.unit === 'year') cutoff.setFullYear(cutoff.getFullYear() - definition.amount);
      const lastDay = new Date(cutoff.getFullYear(), cutoff.getMonth() + 1, 0).getDate();
      cutoff.setDate(Math.min(originalDay, lastDay));
    }
    return cutoff;
  }

  function localIsoDate(value) {
    const pad = number => String(number).padStart(2, '0');
    return `${value.getFullYear()}-${pad(value.getMonth() + 1)}-${pad(value.getDate())}`;
  }

  function buildRangeControls() {
    const endDate = selectedDate();
    const ordered = rangeDefinitions.slice().sort((a, b) =>
      (endDate - rangeCutoff(a, endDate)) - (endDate - rangeCutoff(b, endDate))
    );
    rangeControls.innerHTML = '';
    ordered.forEach(definition => {
      const button = document.createElement('button');
      button.textContent = definition.label;
      button.dataset.range = definition.key;
      button.classList.toggle('active', definition.key === selectedRange);
      button.addEventListener('click', () => { selectedRange = definition.key; renderAll(); });
      rangeControls.append(button);
    });
  }

  function sourceRows() {
    const index = Number(window.BREADTH_ASOF_INDEX || 0);
    const historical = rows.slice(index);
    const definition = rangeDefinitions.find(item => item.key === selectedRange);
    const cutoff = localIsoDate(rangeCutoff(definition));
    return historical.filter(row => row.date >= cutoff);
  }

  function noData(target, message) {
    target.innerHTML = svgText(500, 170, message, 'text-anchor="middle" fill="#c8c4b9" font-size="15"');
  }

  function significantT2108Points(data) {
    if (data.length < 2) return [];
    const windowSize = Math.min(4, Math.max(1, Math.floor((data.length - 1) / 2)));
    const candidates = [];
    for (let index = windowSize; index < data.length - windowSize; index += 1) {
      const value = data[index].t2108;
      const neighborhood = data.slice(index - windowSize, index + windowSize + 1).map(row => row.t2108);
      const edgeAverage = (data[index - windowSize].t2108 + data[index + windowSize].t2108) / 2;
      if (value === Math.max(...neighborhood) && value - edgeAverage >= 4) candidates.push({ index, value, kind: 'Swing high', score: value - edgeAverage });
      if (value === Math.min(...neighborhood) && edgeAverage - value >= 4) candidates.push({ index, value, kind: 'Swing low', score: edgeAverage - value });
    }
    const values = data.map(row => row.t2108);
    const highValue = Math.max(...values), lowValue = Math.min(...values);
    const selected = [
      { index: values.indexOf(highValue), value: highValue, kind: 'Range high', score: Infinity },
      { index: values.indexOf(lowValue), value: lowValue, kind: 'Range low', score: Infinity },
      ...candidates.sort((a, b) => b.score - a.score),
    ];
    const result = [];
    for (const point of selected) {
      if (result.some(existing => Math.abs(existing.index - point.index) < 8)) continue;
      result.push(point);
      if (result.length === 8) break;
    }
    return result.sort((a, b) => a.index - b.index);
  }

  function renderBreadthChart() {
    [...metricControls.children].forEach((button, index) => button.classList.toggle('active', Object.keys(views)[index] === selectedMetric));
    [...rangeControls.children].forEach(button => button.classList.toggle('active', button.dataset.range === selectedRange));
    const view = views[selectedMetric];
    const data = sourceRows().filter(row => view.keys.every(key => valid(row[key]))).reverse();
    document.querySelector('#chart-title').textContent = view.label;
    document.querySelector('#chart-note').textContent = selectedMetric === 't2108'
      ? 'Markers identify the visible range high/low and locally significant swings. The 20/80 lines are context zones, not automatic signals.'
      : `${view.note} Lines end at the selected date; labels show that session's values.`;
    if (!data.length) {
      noData(chart, `${view.label} is not available for this historical period.`);
      return;
    }

    const values = data.flatMap(row => view.keys.map(key => Number(row[key])));
    let minimum = Math.min(...values), maximum = Math.max(...values);
    if (selectedMetric !== 'ratios' && selectedMetric !== 't2108') minimum = 0;
    if (selectedMetric === 't2108') { minimum = 0; maximum = 100; }
    const padding = selectedMetric === 'ratios' ? Math.max((maximum - minimum) * 0.12, 0.05) : maximum * 0.07;
    if (selectedMetric !== 't2108') { minimum = Math.max(0, minimum - padding); maximum += padding; }
    const left = 28, right = 805, axisX = 820, latestX = 976, top = 24, bottom = 294;
    const x = index => left + index * ((right - left) / Math.max(data.length - 1, 1));
    const y = value => bottom - (value - minimum) / Math.max(maximum - minimum, 1) * (bottom - top);
    const colors = selectedMetric === 'ratios' ? ['#e9c46a', '#75baff'] : ['#62d6b4', '#ff6b8a'];
    let markup = '';
    for (let step = 0; step <= 4; step += 1) {
      const value = minimum + (maximum - minimum) * (4 - step) / 4;
      const position = top + (bottom - top) * step / 4;
      markup += `<path d="M${left},${position}H${right}" stroke="#414141" stroke-width="1"/>`;
      markup += svgText(axisX, position + 4, selectedMetric === 't2108' ? `${value.toFixed(0)}%` : value.toFixed(maximum < 10 ? 2 : 0), 'fill="#c8c4b9" font-size="12"');
    }
    markup += `<path d="M${right},${top}V${bottom}" stroke="#686868" stroke-width="1"/>`;
    if (selectedMetric === 'ratios') markup += `<path d="M${left},${y(1)}H${right}" stroke="#F5F2E8" stroke-dasharray="5 5" opacity=".8"/>${svgText(left + 5, y(1) - 6, 'Balance = 1.0', 'fill="#F5F2E8" font-size="11"')}`;
    if (selectedMetric === 't2108') {
      [[20, '20 — washed out'], [80, '80 — broad strength']].forEach(([level, label]) => {
        markup += `<path d="M${left},${y(level)}H${right}" stroke="#e9c46a" stroke-dasharray="6 5" opacity=".8"/>${svgText(left + 5, y(level) - 6, label, 'fill="#e9c46a" font-size="11"')}`;
      });
    }
    markup += view.keys.map((key, index) => `<path d="${linePath(data, key, x, y)}" stroke="${view.keys.length === 1 ? singleLineColor : colors[index]}" stroke-width="3" stroke-linejoin="round" fill="none"/>`).join('');
    if (selectedMetric === 't2108') {
      significantT2108Points(data).forEach(point => {
        const px = x(point.index), py = y(point.value), isHigh = point.kind.includes('high');
        const label = selectedRange === 'ytd' && point.kind.startsWith('Range') ? point.kind.replace('Range', 'YTD') : point.kind;
        const anchor = px > right - 120 ? 'end' : px < left + 70 ? 'start' : 'middle';
        const tx = anchor === 'end' ? px - 7 : anchor === 'start' ? px + 7 : px;
        markup += `<circle cx="${px}" cy="${py}" r="5" fill="${isHigh ? '#e9c46a' : '#ff6b8a'}" stroke="#141414" stroke-width="2"><title>${label}: ${point.value.toFixed(2)}% on ${data[point.index].date}</title></circle>`;
        markup += svgText(tx, isHigh ? py + 20 : py - 12, `${label} ${point.value.toFixed(1)}%`, `text-anchor="${anchor}" fill="${isHigh ? '#e9c46a' : '#ff9bb0'}" font-size="11" font-weight="700"`);
      });
      const latest = data.at(-1), latestY = y(latest.t2108);
      markup += `<circle cx="${right}" cy="${latestY}" r="5" fill="${singleLineColor}" stroke="#141414" stroke-width="2"/>${svgText(latestX, Math.max(top + 12, Math.min(bottom - 4, latestY)), `T2108  ${latest.t2108.toFixed(2)}%`, `text-anchor="end" fill="${singleLineColor}" font-size="13" font-weight="750"`)}`;
    } else {
      view.keys.forEach((key, index) => {
        const latest = data.at(-1), py = y(latest[key]), color = colors[index];
        const names = selectedMetric === 'ratios' ? ['5D', '10D'] : ['Up', 'Down'];
        const latestY = Math.max(top + 12, Math.min(bottom - 4, py + (index ? 11 : -8)));
        markup += `<circle cx="${right}" cy="${py}" r="5" fill="${color}" stroke="#141414" stroke-width="2"/>${svgText(latestX, latestY, `${names[index]}  ${latest[key].toFixed(maximum < 10 ? 2 : 0)}`, `text-anchor="end" fill="${color}" font-size="13" font-weight="750"`)}`;
      });
    }
    markup += svgText(left, 327, data[0].date, 'fill="#c8c4b9" font-size="12"');
    markup += svgText(right, 327, data.at(-1).date, 'text-anchor="end" fill="#c8c4b9" font-size="12"');
    chart.innerHTML = markup;
    const names = selectedMetric === 'ratios' ? ['5D', '10D'] : selectedMetric === 't2108' ? ['T2108'] : ['Up', 'Down'];
    const series = view.keys.map((key, index) => ({
      key,
      label: names[index],
      color: view.keys.length === 1 ? singleLineColor : colors[index],
    }));
    attachHover(chart, data, series, x, y, {
      ratio: selectedMetric === 'ratios',
      points: selectedMetric === 't2108',
      format: value => selectedMetric === 't2108'
        ? `${value.toFixed(2)}%`
        : selectedMetric === 'ratios'
          ? value.toFixed(2)
          : value.toLocaleString(undefined, { maximumFractionDigits: 0 }),
    });
  }

  function renderSpxChart() {
    const data = sourceRows().filter(row => valid(row.sp)).reverse();
    spxNote.textContent = selectedMetric === 't2108'
      ? 'T2108 turning points are projected onto SPX. Hover or focus a marker for its breadth reading, SPX close and date.'
      : 'S&P 500 close through the selected date, using the same timeframe.';
    if (!data.length) {
      noData(spxChart, 'SPX close data is not available for this historical period.');
      return;
    }
    const values = data.map(row => Number(row.sp));
    let minimum = Math.min(...values), maximum = Math.max(...values);
    const padding = Math.max((maximum - minimum) * 0.1, maximum * 0.005);
    minimum -= padding; maximum += padding;
    const left = 28, right = 805, axisX = 820, latestX = 976, top = 24, bottom = 294;
    const x = index => left + index * ((right - left) / Math.max(data.length - 1, 1));
    const y = value => bottom - (value - minimum) / Math.max(maximum - minimum, 1) * (bottom - top);
    let markup = '';
    for (let step = 0; step <= 4; step += 1) {
      const value = minimum + (maximum - minimum) * (4 - step) / 4;
      const position = top + (bottom - top) * step / 4;
      markup += `<path d="M${left},${position}H${right}" stroke="#414141" stroke-width="1"/>${svgText(axisX, position + 4, value.toLocaleString(undefined, { maximumFractionDigits: 0 }), 'fill="#c8c4b9" font-size="12"')}`;
    }
    markup += `<path d="M${right},${top}V${bottom}" stroke="#686868" stroke-width="1"/>`;
    markup += `<path d="${linePath(data, 'sp', x, y)}" stroke="${singleLineColor}" stroke-width="3" stroke-linejoin="round" fill="none"/>`;
    if (selectedMetric === 't2108') {
      const t2108Data = sourceRows().filter(row => valid(row.sp) && valid(row.t2108)).reverse();
      const signalPoints = significantT2108Points(t2108Data);
      const spxIndexByDate = new Map(data.map((row, index) => [row.date, index]));
      signalPoints.forEach(point => {
        const signal = t2108Data[point.index], spxIndex = spxIndexByDate.get(signal.date);
        if (spxIndex === undefined) return;
        const px = x(spxIndex), py = y(data[spxIndex].sp), isHigh = point.kind.includes('high');
        const label = selectedRange === 'ytd' && point.kind.startsWith('Range') ? point.kind.replace('Range', 'YTD') : point.kind;
        const color = isHigh ? '#e9c46a' : '#ff6b8a';
        const anchor = px > right - 125 ? 'end' : px < left + 80 ? 'start' : 'middle';
        const tx = anchor === 'end' ? px - 8 : anchor === 'start' ? px + 8 : px;
        markup += `<path d="M${px},${top}V${bottom}" stroke="${color}" stroke-width="1" stroke-dasharray="3 5" opacity=".32"/>`;
        markup += `<circle class="spx-signal-point" cx="${px}" cy="${py}" r="5" fill="${color}" stroke="#141414" stroke-width="2" tabindex="0"><title>${label}: T2108 ${point.value.toFixed(2)}% · SPX ${Number(data[spxIndex].sp).toFixed(2)} · ${signal.date}</title></circle>`;
        markup += svgText(tx, isHigh ? py - 12 : py + 20, `T2108 ${label.toLowerCase()} ${point.value.toFixed(1)}%`, `text-anchor="${anchor}" fill="${color}" font-size="10" font-weight="700"`);
      });
    }
    const latest = data.at(-1), latestY = y(latest.sp);
    markup += `<circle cx="${right}" cy="${latestY}" r="5" fill="${singleLineColor}" stroke="#141414" stroke-width="2"><title>SPX ${latest.sp.toFixed(2)} on ${latest.date}</title></circle>`;
    markup += svgText(latestX, Math.max(top + 12, Math.min(bottom - 4, latestY)), `SPX  ${latest.sp.toLocaleString(undefined, { maximumFractionDigits: 2 })}`, `text-anchor="end" fill="${singleLineColor}" font-size="13" font-weight="750"`);
    markup += svgText(left, 327, data[0].date, 'fill="#c8c4b9" font-size="12"');
    markup += svgText(right, 327, latest.date, 'text-anchor="end" fill="#c8c4b9" font-size="12"');
    spxChart.innerHTML = markup;
    attachHover(spxChart, data, [{ key: 'sp', label: 'SPX', color: singleLineColor }], x, y, {
      percentChange: true,
      format: value => value.toLocaleString(undefined, { minimumFractionDigits: 2, maximumFractionDigits: 2 }),
    });
  }

  function renderAll() {
    const range = rangeDefinitions.find(item => item.key === selectedRange);
    spxRangeBadge.textContent = `${range ? range.label : selectedRange} window`;
    renderBreadthChart();
    renderSpxChart();
  }

  window.addEventListener('breadth-asof-change', () => {
    buildRangeControls();
    renderAll();
  });
  buildRangeControls();
  renderAll();
})();
