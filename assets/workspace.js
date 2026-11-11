/* A small, source-driven workspace. Original detailed pages remain accessible. */
const $ = selector => document.querySelector(selector);
const escapeHTML = value => String(value ?? '').replace(/[&<>"']/g, c => ({'&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'}[c]));
const finite = v => v !== null && v !== undefined && v !== '' && Number.isFinite(Number(v));
const numberFormatters=new Map();
const fmt = (v,d=1) => {if(!finite(v))return '—';if(!numberFormatters.has(d))numberFormatters.set(d,new Intl.NumberFormat(undefined,{maximumFractionDigits:d}));return numberFormatters.get(d).format(Number(v));};
const pct = v => finite(v) ? fmt(v,1)+'%' : '—';
const signed = (v,d=1) => finite(v) ? (v>0?'+':'')+fmt(v,d) : '—';
const money = v => finite(v) ? '$'+fmt(v/(v>=1e9?1e9:1e6),1)+(v>=1e9?'B':'M') : '—';
const frames = { '1w':'1W', '1m':'1M', '3m':'3M', '6m':'6M', '1y':'1Y' };
const frameNames = { '1w':'1 Week', '1m':'1 Month', '3m':'3 Months', '6m':'6 Months', '1y':'1 Year' };
const frameRoles = { '1w':'Fast', '1m':'Swing', '3m':'Trend', '6m':'Cycle', '1y':'Long' };
const titles = {briefing:'Now',environment:'Breadth',leadership:'Capital flow',positioning:'Positioning',screener:'Stock radar',review:'Session replay',method:'Sources & definitions'};
const store = {get(key,fallback){try{return JSON.parse(localStorage.getItem('nel-'+key))??fallback;}catch{return fallback;}},set(key,value){try{localStorage.setItem('nel-'+key,JSON.stringify(value));return true;}catch{return false;}}};
let db={}, themes={}, sectors={}, breadth=[], spxHistory=[], indexHistory={}, flowMarket={}, cot={}, context={}, route='briefing', frame='1m', leadershipKind='themes';
let flowFrame='1m', flowMode='strength', flowSort={key:'rank',direction:'asc'}, flowSelection='';
let indexFrame='1y',flowIndexView=null;
let flowETFState=null, flowWidgetSerial=0;
let filters={search:'',group:'',adr:5,extension:4,above9d:false,above9w:false,above9m:false,liquid:false,superLiquid:false,tight:false};
let obcFilters={search:'',group:'',adr:'',extension:'',liquid:false,superLiquid:false};
let overrides=store.get('themes',{}), selected=null, screenerView='kk';
let kkSort={key:'strength',direction:'desc'};
let screenerDisplay='list', tvObserver=null, tvScriptPromise=null;
let breadthMetric='daily', breadthRange='3m';
let cotWindow='5y',cotDate='';
const cotPeriods={'1y':52,'3y':156,'5y':260};
const cotRelease=r=>{if(r.release_date)return r.release_date;const d=new Date(r.date+'T12:00:00Z');d.setUTCDate(d.getUTCDate()+(5-d.getUTCDay()+7)%7);return d.toISOString().slice(0,10);};
const cotDates=()=>[...new Set((cot.markets||[]).flatMap(m=>m.history.map(cotRelease)))].sort();
const cotHistory=m=>m.history.filter(r=>(!cotDate||cotRelease(r)<=cotDate)&&finite(r.participants.large?.net));
const cotParticipant='all';const cotRanges={"5y":true};
const session = () => db.snapshots?.find(s=>s.date===$('#session').value) || db.snapshots?.at(-1);
const asof = () => session()?.closeDate || session()?.date;
const breadthRows = () => breadth.filter(r=>r.date<=asof()).sort((a,b)=>b.date.localeCompare(a.date));
const latestETF = payload => payload.snapshots?.filter(s=>s.date<=asof()).at(-1);
const tag = row => {
  const profile=overrides[row.symbol] || db.profiles?.[row.symbol];
  return profile && (!profile.effective || profile.effective<=session().date) ? profile.theme : row.industry;
};
const isMapped = row => {
  const p=overrides[row.symbol] || db.profiles?.[row.symbol];
  return p && (!p.effective || p.effective<=session().date);
};
const stocks = (kind='liquid') => kind==='kk' ? (session()?.kk||[]) : kind==='obc' ? (session()?.obc||[]) : (session()?.stocks||[]).filter(r=>r.kind===kind);
const leaders = (kind='liquid') => stocks(kind).filter(r=>r.leaders.includes(frame));
const isNEL = r => finite(r.extension) && r.extension<=4;
const button = (label,action,cls='') => '<button class="'+cls+'" data-action="'+action+'">'+label+'</button>';
const detailLink = (href,label) => '<a href="'+href+'">'+label+' ↗</a>';
function frameControls(context='Ranking horizon'){return '<div class="horizon"><span class="horizon-label">'+context+'</span><div class="segments" aria-label="'+context+'">'+Object.entries(frames).map(([f,label])=>'<button title="Rank using trailing '+frameNames[f]+' performance" data-frame="'+f+'" class="'+(f===frame?'active':'')+'"><b>'+label+'</b><small>'+frameRoles[f]+'</small></button>').join('')+'</div></div>';}
function measure(label,value,note=''){return '<div class="measure"><div>'+label+'<small>'+note+'</small></div><strong>'+value+'</strong></div>';}
function metric(label,value){return '<span>'+label+'<b>'+value+'</b></span>';}
function card(title,content,href='',label='Explore'){return '<section class="card"><div class="card-head"><h2>'+title+'</h2>'+(href?detailLink(href,label):'')+'</div>'+content+'</section>';}
function signal(icon,label,value,note,tone='cyan'){return '<div class="signal-tile '+tone+'"><i class="signal-icon">'+icon+'</i><small>'+label+'</small><b>'+value+'</b><em>'+note+'</em></div>';}
function flowBars(rows){const max=Math.max(...rows.map(row=>Math.abs(Number(row.median_performance)||0)),1);return '<div class="flow-list">'+rows.map(row=>'<div class="flow-row"><span>'+escapeHTML(row.group)+'</span><div class="flow-track"><i style="width:'+Math.max(4,Math.abs(Number(row.median_performance)||0)/max*100)+'%"></i></div><b>'+pct(row.median_performance)+'</b></div>').join('')+'</div>';}
function marketRead(row){
  if(!row || !['ratio5','ratio10','up4','down4'].every(k=>finite(row[k]))) return {title:'Waiting for breadth',tone:'gold',reason:'A complete breadth reading is not available for this close.',plan:'Review data freshness before forming a market view.'};
  if(row.down4>=300 || row.ratio10<.85 || (row.ratio5<.70 && row.down4>row.up4*2))
    return {title:'Defensive · prepare selectively',tone:'negative',reason:'Selling pressure remains elevated in the rolling breadth measures.',plan:'Prioritize reviewing existing risk. Keep the strongest tight candidates on watch; require improving participation and a valid chart trigger before adding risk.'};
  if(row.ratio10>=1.25 && row.ratio5>=1.10 && row.up4>=180 && row.down4<150)
    return {title:'Expansion · review breakout setups',tone:'positive',reason:'Daily participation and rolling breadth support each other.',plan:'Focus chart review on tight, non-extended leaders in the strongest groups. Define the trigger and invalidation before taking a position.'};
  return {title:'Mixed · let the setup earn its place',tone:'gold',reason:'Breadth has not aligned into a sustained expansion.',plan:'Favor selectivity. Look for relative strength that survives weak sessions and avoid treating a rank alone as an entry.'};
}
function stockTable(rows,compact=false){
  if(!rows.length)return '<p class="empty">No candidates match this window and filter combination.</p>';
  return '<div class="table-box"><table><thead><tr><th>Stock / theme</th><th class="num">'+frames[frame]+'</th><th class="num">Extension</th>'+(!compact?'<th class="num">ADR</th><th class="num">Avg $ vol</th><th>Structure</th>':'')+'</tr></thead><tbody>'+rows.map(r=>'<tr><td><button data-stock="'+escapeHTML(r.symbol)+'" data-kind="'+r.kind+'">'+escapeHTML(r.symbol)+(r.pair?' / '+escapeHTML(r.pair):'')+'</button><small>'+escapeHTML(tag(r))+(isMapped(r)?' · custom':' · vendor')+'</small></td><td class="num">'+pct(r.performance[frame])+'</td><td class="num">'+fmt(r.extension,2)+'×</td>'+(!compact?'<td class="num">'+pct(r.adr)+'</td><td class="num">'+money(r.dollarVolume)+'</td><td>'+(r.tight?'<span class="positive">Tight</span>':'Review chart')+'</td>':'')+'</tr>').join('')+'</tbody></table></div>';
}
function orderedCandidates(){return leaders().filter(isNEL).sort((a,b)=>Number(b.tight)-Number(a.tight)||(b.performance[frame]??-Infinity)-(a.performance[frame]??-Infinity));}
function changeSummary(){
  const index=db.snapshots.indexOf(session()), previous=db.snapshots[index-1];
  if(!previous)return '<p class="muted">This is the first saved stock snapshot.</p>';
  const now=stocks().filter(r=>r.leaders.includes(frame)&&isNEL(r)), before=previous.stocks.filter(r=>r.kind==='liquid'&&r.leaders.includes(frame)&&isNEL(r));
  const old=new Set(before.map(r=>r.symbol)), current=new Set(now.map(r=>r.symbol));
  const entering=now.filter(r=>!old.has(r.symbol)).map(r=>r.symbol), leaving=before.filter(r=>!current.has(r.symbol)).map(r=>r.symbol);
  return measure('New NEL candidates',escapeHTML(entering.slice(0,8).join(', ')||'None'),entering.length+' entered vs '+previous.date)+measure('Left NEL',escapeHTML(leaving.slice(0,8).join(', ')||'None'),leaving.length+' left; extension and rank may both change')+'<p class="note">Membership changes include ranking changes. A newly introduced window can create a one-time jump.</p>';
}
function miniStat(icon,label,value,note,tone='cyan'){return '<div class="mini-stat '+tone+'"><i>'+icon+'</i><span>'+label+'</span><b>'+value+'</b><small>'+note+'</small></div>';}
function rangeMeter(value,label,tone='cyan'){
  const position=Math.max(1,Math.min(99,Number(value)||0));
  return '<div class="range-meter '+tone+'" aria-label="'+escapeHTML(label)+' '+fmt(value,0)+'"><div class="range-fill" style="width:'+position+'%"></div><i style="left:'+position+'%"></i><span>0</span><span>50</span><span>100</span></div>';
}
const flowKeys={one_day:'one_day',one_week:'one_week',one_month:'one_month',three_months:'three_months',six_months:'six_months',one_year:'one_year'};
const flowLabels={one_day:'1D',one_week:'1W',one_month:'1M',three_months:'3M',six_months:'6M',one_year:'1Y'};
const flowFrameKey={ '1d':'one_day','1w':'one_week','1m':'one_month','3m':'three_months','6m':'six_months','1y':'one_year'};
const flowSessions={one_day:1,one_week:5,one_month:21,three_months:63,six_months:126,one_year:252};
const flowMomentumKey={one_day:'one_week',one_week:'one_day',one_month:'one_week',three_months:'one_week',six_months:'one_week',one_year:'one_week'};
function median(values){const sorted=values.filter(finite).map(Number).sort((a,b)=>a-b);if(!sorted.length)return null;const mid=Math.floor(sorted.length/2);return sorted.length%2?sorted[mid]:(sorted[mid-1]+sorted[mid])/2;}
function percentile(values,p){const sorted=values.filter(finite).map(Number).sort((a,b)=>a-b);if(!sorted.length)return null;const index=(sorted.length-1)*p,low=Math.floor(index),high=Math.ceil(index);return low===high?sorted[low]:sorted[low]+(sorted[high]-sorted[low])*(index-low);}
function etfSnapshot(payload,date=asof()){return payload.snapshots?.filter(s=>s.date<=date).at(-1);}
function flowBenchmark(date,key){
  const rows=spxHistory.filter(r=>r.date<=date&&finite(r.close)).sort((a,b)=>a.date.localeCompare(b.date));
  const now=rows.at(-1), then=rows.at(-(flowSessions[key]+1));
  return now&&then?100*(Number(now.close)/Number(then.close)-1):null;
}
function flowGroupName(payload,row){
  // BWET is tanker-freight futures exposure, not a basket of shipping-company equities.
  // Keeping it separate prevents one niche macro instrument from defining the Shipping theme.
  if(payload?.kind==='themes'&&row.symbol==='BWET')return 'Tanker freight';
  return String(row.group||'Unclassified');
}
function buildFlowGroups(payload,snapshot,key){
  const benchmark=flowBenchmark(snapshot?.date,key), momentumKey=flowMomentumKey[key], momentumBenchmark=flowBenchmark(snapshot?.date,momentumKey), grouped=new Map();
  (snapshot?.daily_changes||[]).filter(row=>row.symbol!=='SVIX').forEach(row=>{
    if(!finite(row[key]))return;
    const group=flowGroupName(payload,row), item=grouped.get(group)||{group,members:[]};
    item.members.push(row);grouped.set(group,item);
  });
  const groups=[...grouped.values()].map(group=>{
    const performance=median(group.members.map(row=>row[key]));
    const returns=Object.fromEntries(Object.keys(flowKeys).map(metric=>[metric,median(group.members.map(row=>row[metric]))]));
    const ordered=[...group.members].sort((a,b)=>Number(b[key])-Number(a[key]));
    const momentum=returns[momentumKey];
    const extension=median(group.members.map(row=>row.extension));
    return {...group,...returns,performance,extension,relative:finite(benchmark)?performance-benchmark:null,momentum,momentum_relative:finite(momentumBenchmark)?momentum-momentumBenchmark:null,momentum_key:momentumKey,leader:ordered[0]?.symbol||'—',member_count:ordered.length,members:ordered};
  }).sort((a,b)=>Number(b.performance)-Number(a.performance)||a.group.localeCompare(b.group));
  return groups.map((group,index)=>({...group,rank:index+1,benchmark}));
}
function flowRanks(payload,snapshot,key){return new Map(buildFlowGroups(payload,snapshot,key).map(group=>[group.group,group.rank]));}
function flowMapMetrics(groups,key){
  const sessionMap=key==='one_day';
  const x=group=>sessionMap?group.performance:(finite(group.relative)?group.relative:group.performance);
  const y=group=>sessionMap?group.one_week:(finite(group.momentum_relative)?group.momentum_relative:group.momentum);
  const maxX=Math.max(3,percentile(groups.map(group=>Math.abs(Number(x(group)))),.95)||0);
  const maxY=Math.max(3,percentile(groups.map(group=>Math.abs(Number(y(group)))),.95)||0);
  const clipped=group=>Math.abs(Number(x(group)))>maxX||Math.abs(Number(y(group)))>maxY;
  return {x,y,maxX,maxY,clipped,outliers:groups.filter(clipped)};
}
function flowGroupPanel(group,groups,key){
  if(!group)return '';
  const rows=group.members.map(row=>'<tr><td><button class="flow-etf-link" data-flow-etf="'+escapeHTML(row.symbol)+'" data-flow-group="'+escapeHTML(group.group)+'">'+escapeHTML(row.symbol)+'</button></td><td class="num '+returnTone(row.one_day)+'">'+pct(row.one_day)+'</td><td class="num '+returnTone(row.one_week)+'">'+pct(row.one_week)+'</td><td class="num '+returnTone(row.one_month)+'">'+pct(row.one_month)+'</td><td class="num '+returnTone(row.three_months)+'">'+pct(row.three_months)+'</td><td class="num '+returnTone(row.six_months)+'">'+pct(row.six_months)+'</td><td class="num '+returnTone(row.one_year)+'">'+pct(row.one_year)+'</td></tr>').join('');
  const metrics=flowMapMetrics(groups,key), selectedLabel=flowLabels[key], momentumLabel=flowLabels[group.momentum_key], sessionMap=key==='one_day', xColumn=sessionMap?'1D raw':selectedLabel+' vs SPX', yColumn=sessionMap?'1W raw':momentumLabel+' vs SPX';
  const outliers=metrics.outliers.map(item=>{const axes=[];if(Math.abs(Number(metrics.x(item)))>metrics.maxX)axes.push(selectedLabel+(sessionMap?' change':' strength'));if(Math.abs(Number(metrics.y(item)))>metrics.maxY)axes.push(momentumLabel+(sessionMap?' trend':' momentum'));return '<tr><td><button data-flow-group="'+escapeHTML(item.group)+'">'+escapeHTML(item.group)+'</button><small>'+escapeHTML(item.leader)+' · '+escapeHTML(axes.join(' + '))+'</small></td><td class="num '+returnTone(metrics.x(item))+'">'+(sessionMap?pct(metrics.x(item)):signed(metrics.x(item))+' pp')+'</td><td class="num '+returnTone(metrics.y(item))+'">'+(sessionMap?pct(metrics.y(item)):signed(metrics.y(item))+' pp')+'</td></tr>';}).join('');
  const outlierPanel=metrics.outliers.length?'<aside class="flow-outliers"><div><span class="eyebrow">MAP OUTLIERS</span><h3>'+metrics.outliers.length+' clipped point'+(metrics.outliers.length===1?'':'s')+'</h3><p>Raw data remains intact; these points stay out of the plot so the rest remains readable.</p></div><div class="flow-outlier-table"><table><thead><tr><th>Theme / sector</th><th class="num">'+xColumn+'</th><th class="num">'+yColumn+'</th></tr></thead><tbody>'+outliers+'</tbody></table></div></aside>':'<aside class="flow-outliers empty"><span class="eyebrow">MAP OUTLIERS</span><h3>No clipped points</h3><p>Every group fits within the current map scale.</p></aside>';
  return '<section class="flow-detail"><div><span class="eyebrow">GROUP BREAKDOWN</span><h3>'+escapeHTML(group.group)+'</h3><p>'+group.member_count+' ETF'+(group.member_count===1?'':'s')+' · equal-weight median '+selectedLabel+' return: <b class="'+returnTone(group.performance)+'">'+pct(group.performance)+'</b></p></div>'+outlierPanel+'<div class="table-box"><table><thead><tr><th>ETF</th><th class="num">1D</th><th class="num">1W</th><th class="num">1M</th><th class="num">3M</th><th class="num">6M</th><th class="num">1Y</th></tr></thead><tbody>'+rows+'</tbody></table></div></section>';
}
function flowPayload(){return leadershipKind==='sectors'?sectors:themes;}
function flowETFDetails(payload,symbol){
  const snapshot=etfSnapshot(payload), daily=(snapshot?.daily_changes||[]).find(row=>row.symbol===symbol)||{};
  const member=Object.values(snapshot?.windows||{}).flatMap(groups=>groups.flatMap(group=>group.members||[])).find(row=>row.symbol===symbol)||{};
  const base={...member,...daily,symbol,description:member.description||daily.description||'',adrp:member.adrp??daily.adrp,average_dollar_volume_30d:member.average_dollar_volume_30d??daily.average_dollar_volume_30d,extension:member.extension??daily.extension};
  if(!flowETFState?.market||!flowOverviewState?.metrics[symbol]?.available)return base;
  const m=flowOverviewState.metrics[symbol],h=m.history,result={...base,description:base.description||m.name,extension:m.extension,oscillator:m.oscillator,relative:m.relative,close:m.close,date:m.date,intraday:m.intraday,offHigh:m.offHigh,...(flowOverviewState.rankings?.[flowETFState.category]?.[symbol]||{})};
  for(const [key,n] of Object.entries({one_day:1,one_week:5,one_month:21,three_months:63,six_months:126,one_year:252})){const back=h.at(-1-n);result[key]=back?100*(m.close/back.close-1):null;}
  result.adrp=h.length>=14?100*h.slice(-14).reduce((sum,r)=>sum+r.high-r.low,0)/14/m.close:null;
  const volumeRows=h.slice(-30);if(volumeRows.length===30&&volumeRows.every(r=>finite(r.volume)))result.average_dollar_volume_30d=(volumeRows.reduce((sum,r)=>sum+r.close,0)/30)*(volumeRows.reduce((sum,r)=>sum+r.volume,0)/30);
  return result;
}
function flowHoldingRows(items){
  if(!items?.length)return '<tr><td colspan="11" class="empty">No qualifying common-stock holdings are available for this ETF.</td></tr>';
  return items.map(item=>'<tr><td><button class="flow-holding-link" data-flow-holding="'+escapeHTML(item.symbol)+'" data-flow-holding-name="'+escapeHTML(item.name)+'">'+escapeHTML(item.symbol)+'</button></td><td>'+escapeHTML(item.name)+'</td><td class="num">'+pct(Number(item.weight)*100)+'</td>'+['one_day','one_week','one_month','three_months','six_months','one_year'].map(key=>'<td class="num '+returnTone(item[key])+'">'+pct(item[key])+'</td>').join('')+'<td class="num">'+money(item.average_dollar_volume_30d)+'</td><td class="num '+extensionTone(item.extension)+'">'+(finite(item.extension)?fmt(item.extension,2)+'×':'—')+'</td></tr>').join('');
}
function flowPerformanceTiles(detail){
  return '<div><span class="eyebrow">PERFORMANCE</span><div class="flow-stat-grid flow-performance-grid">'+Object.entries(flowKeys).map(([key,label])=>'<div><span>'+escapeHTML(flowLabels[key])+'</span><b class="'+returnTone(detail[key])+'">'+pct(detail[key])+'</b></div>').join('')+'</div></div>';
}
function flowEvidenceTiles(detail){
  const extras=flowETFState?.market?'<div><span>1M RS score</span><b>'+pct(detail.rsMonth)+'</b></div><div><span>RS Thrust</span><b>'+pct(detail.thrust)+'</b></div><div><span>Intraday</span><b class="'+returnTone(detail.intraday)+'">'+pct(detail.intraday)+'</b></div><div><span>50D ATR index</span><b class="'+returnTone(detail.oscillator)+'">'+(finite(detail.oscillator)?signed(detail.oscillator,2):'—')+'</b></div><div><span>1M vs RSP</span><b class="'+returnTone(detail.relative)+'">'+pct(detail.relative)+'</b></div><div><span>Off 52W high</span><b class="'+returnTone(detail.offHigh)+'">'+pct(detail.offHigh)+'</b></div>':'';
  return '<div><span class="eyebrow">ETF STATS</span><div class="flow-stat-grid">'+
    '<div><span>ADR</span><b>'+pct(detail.adrp)+'</b></div><div><span>Avg $ vol</span><b>'+money(detail.average_dollar_volume_30d)+'</b></div><div><span>50D ATR ext</span><b class="'+extensionTone(detail.extension)+'">'+(finite(detail.extension)?fmt(detail.extension,2)+'×':'—')+'</b></div>'+
  extras+'</div></div>';
}
function flowETFDialog(){
  const state=flowETFState;if(!state)return;
  const dialog=$('#flow-etf-dialog'), detail=flowETFDetails(state.payload,state.etf), holdings=(state.market&&flowMarket.holdings?.[state.etf])||state.payload.holdings?.[state.etf]||[];
  const selected=state.chartSymbol===state.etf?'ETF chart':'Holding chart · '+state.chartSymbol;
  const chartId='flow-detail-chart-'+(++flowWidgetSerial);
  const members=state.members||[], switcher=members.length>1?'<div class="flow-group-etfs" aria-label="Choose ETF expression">'+members.map(row=>'<button class="'+(row.symbol===state.etf?'active':'')+'" data-flow-etf="'+escapeHTML(row.symbol)+'" data-flow-group="'+escapeHTML(state.group)+'">'+escapeHTML(row.symbol)+'</button>').join('')+'</div>':'';
  $('#flow-etf-content').innerHTML='<div class="flow-dialog-head"><div><span class="eyebrow">'+escapeHTML(state.group)+' · ETF DETAIL</span><h2>'+escapeHTML(state.etf)+' <small>'+escapeHTML(detail.description)+'</small></h2>'+switcher+'</div><button type="button" data-action="flow-dialog-close" class="flow-dialog-close" aria-label="Close ETF details"><svg viewBox="0 0 24 24" width="18" height="18" aria-hidden="true" focusable="false"><path d="M6 6L18 18M18 6L6 18" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round"/></svg></button></div><div class="flow-dialog-grid"><section class="flow-dialog-data">'+(state.market?'<div class="flow-popup-quote"><b>$'+fmt(detail.close,2)+'</b><span class="'+returnTone(detail.one_day)+'">'+signed(detail.one_day,2)+'%</span><small>Close '+detail.date+'</small></div>':'')+flowPerformanceTiles(detail)+flowEvidenceTiles(detail)+'<div class="flow-holdings-head"><div><span class="eyebrow">TOP STOCK HOLDINGS</span><h3>'+holdings.length+' disclosed stocks</h3></div><button class="flow-chart-reset '+(state.chartSymbol===state.etf?'active':'')+'" data-flow-etf="'+escapeHTML(state.etf)+'" data-flow-group="'+escapeHTML(state.group)+'">Show '+escapeHTML(state.etf)+'</button></div><div class="table-box flow-holdings"><table><thead><tr><th>Ticker</th><th>Company</th><th class="num">Weight</th><th class="num">1D</th><th class="num">1W</th><th class="num">1M</th><th class="num">3M</th><th class="num">6M</th><th class="num">1Y</th><th class="num">Avg $ vol</th><th class="num">Extension</th></tr></thead><tbody>'+flowHoldingRows(holdings)+'</tbody></table></div><p class="note">Holdings exclude cash, bonds, swaps, futures, options, collateral, commodities, crypto assets, and fund holdings. Holdings checked: '+escapeHTML(state.market&&flowMarket.holdings?.[state.etf]?flowMarket.holdings_checked_at:state.payload.holdings_as_of||'unavailable')+'.</p></section><section class="flow-dialog-chart"><div><span class="eyebrow">'+escapeHTML(selected)+'</span><h3>'+escapeHTML(state.chartSymbol)+'</h3></div><div id="'+chartId+'" class="flow-tv-chart" data-flow-tv-symbol="'+escapeHTML(state.chartSymbol)+'"><span>Loading chart…</span></div><a class="lead-link" target="_blank" rel="noopener" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(state.chartSymbol)+'">Open in TradingView <b>↗</b></a></section></div>';
  if(!dialog.open)dialog.showModal();
  mountFlowTradingView(chartId,state.chartSymbol);
}
async function mountFlowTradingView(id,symbol,options={}){
  const node=$('#'+id);if(!node)return;
  try{await loadTradingView();if(!node.isConnected)return;node.textContent='';new TradingView.widget({container_id:id,symbol,interval:'D',timeframe:options.range||undefined,extended_hours:false,timezone:'America/New_York',theme:'dark',style:'1',locale:'en',toolbar_bg:'#202020',backgroundColor:'#202020',gridColor:'#343434',hide_top_toolbar:true,hide_side_toolbar:true,hide_legend:true,hide_volume:true,disabled_features:['create_volume_indicator_by_default','create_volume_indicator_by_default_once'],allow_symbol_change:false,enable_publishing:false,save_image:false,withdateranges:!options.range,autosize:true,studies:['STD;EMA'],studies_overrides:{'moving average exponential.ma.color':'#FFFFFF','moving average exponential.ma.linewidth':2,'volume.volume.transparency':100,'volume.volume ma.transparency':100,'moving average exponential.length':9,'moving average exponential.plot.color':'#FFFFFF','moving average exponential.plot.linewidth':2},overrides:{'scalesProperties.showStudyLastValue':false,'paneProperties.backgroundType':'solid','paneProperties.background':'#202020','paneProperties.legendProperties.showLegend':false,'paneProperties.legendProperties.showVolume':false,'paneProperties.legendProperties.showSeriesOHLC':false,'paneProperties.legendProperties.showStudyTitles':false,'paneProperties.legendProperties.showStudyValues':false,'mainSeriesProperties.priceAxisProperties.log':true,'mainSeriesProperties.priceAxisProperties.percentage':false,'mainSeriesProperties.candleStyle.upColor':'#85d65d','mainSeriesProperties.candleStyle.downColor':'#ff3266','mainSeriesProperties.candleStyle.borderUpColor':'#85d65d','mainSeriesProperties.candleStyle.borderDownColor':'#ff3266','mainSeriesProperties.candleStyle.wickUpColor':'#85d65d','mainSeriesProperties.candleStyle.wickDownColor':'#ff3266'}});}catch(error){node.innerHTML='<span class="chart-unavailable">Chart unavailable · <a target="_blank" rel="noopener" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(symbol)+'">open in TradingView ↗</a></span>';}
}
function openFlowETF(symbol,groupName){
  if(flowETFState?.market&&flowOverviewState?.metrics[symbol]?.available){openMarketDetail(symbol);return;}
  const payload=flowPayload(), snapshot=etfSnapshot(payload), group=groupName||flowGroupName(payload,(snapshot?.daily_changes||[]).find(row=>row.symbol===symbol)||{}), key=flowFrameKey[flowFrame], members=buildFlowGroups(payload,snapshot,key).find(item=>item.group===group)?.members||[];
  flowETFState={payload,etf:symbol,group,members,chartSymbol:symbol};flowETFDialog();
}
function flowMap(groups,key){
  if(!groups.length)return '<p class="empty">No group leadership data is available for this close.</p>';
  // A 95th-percentile scale identifies values that would flatten the map.
  // Those values are reported in the outlier panel instead of crowding the scatter field.
  const metrics=flowMapMetrics(groups,key), {x,y,maxX,maxY}=metrics, sessionMap=key==='one_day';
  const scaleX=Math.max(1,median(groups.map(g=>Math.abs(Number(x(g))))))/2,scaleY=Math.max(1,median(groups.map(g=>Math.abs(Number(y(g))))))/2;
  const limitX=Math.max(1,...groups.map(g=>Math.asinh(Math.abs(Number(x(g)))/scaleX))),limitY=Math.max(1,...groups.map(g=>Math.asinh(Math.abs(Number(y(g)))/scaleY)));
  const dots=groups.map(group=>{const xValue=x(group),yValue=y(group),left=50+44*Math.asinh(Number(xValue)/scaleX)/limitX,topPos=50-40*Math.asinh(Number(yValue)/scaleY)/limitY,active=flowSelection===group.group,edge=left>74?' edge-right':'';const tooltip='<span><b>'+escapeHTML(group.group)+'</b></span>';return '<button class="flow-dot '+(active?'active ':'')+(xValue>=0?'positive':'negative')+edge+'" data-flow-group="'+escapeHTML(group.group)+'" style="left:'+Math.max(4,Math.min(96,left))+'%;top:'+Math.max(7,Math.min(93,topPos))+'%" aria-label="'+escapeHTML(group.group)+'">'+tooltip+'</button>';}).join('');
  const xTitle=sessionMap?'1D raw return':finite(groups[0].relative)?flowLabels[key]+' return vs SPX':'Median '+flowLabels[key]+' return';
  const yTitle=sessionMap?'1W raw return':flowLabels[groups[0].momentum_key]+' return vs SPX';
  const outlierNote='<span class="flow-outlier-note">'+groups.length+' groups · compressed axes</span>';
  return '<section class="flow-map"><div class="flow-map-head"><div><span class="eyebrow">STRENGTH MAP</span><h3>Relative strength and near-term momentum</h3><p>Every group is shown. Symmetric compressed axes preserve direction and ordering while fitting extreme readings.</p></div>'+outlierNote+'</div><div class="flow-map-plot"><div class="flow-y-label">Y · '+escapeHTML(yTitle)+' ↑</div><div class="flow-x-axis">X · '+escapeHTML(xTitle)+' →</div><i class="flow-v-axis"></i><i class="flow-h-axis"></i>'+dots+'</div></section>';
}
function flowHash(value){return [...String(value)].reduce((hash,char)=>(hash*31+char.charCodeAt(0))>>>0,7);}
function flowExtensionMap(payload,snapshot){
  const rows=(snapshot?.daily_changes||[]).filter(row=>finite(row.extension)).map(row=>({...row,group:flowGroupName(payload,row)}));
  if(!rows.length)return '<p class="empty">No 50-day ATR extension data is available for this close.</p>';
  const magnitudes=rows.map(row=>Math.abs(Number(row.extension)));
  const scale=Math.max(4,percentile(magnitudes,.95)||0);
  const outliers=rows.filter(row=>Math.abs(Number(row.extension))>scale);
  // Horizontal placement is intentionally non-semantic. A deterministic shuffled lane
  // assignment makes every ETF readable without implying a second metric.
  const lanes=[...rows].sort((a,b)=>flowHash(a.symbol)-flowHash(b.symbol));
  const laneBySymbol=new Map(lanes.map((row,index)=>[row.symbol,lanes.length===1?50:7+86*index/(lanes.length-1)]));
  const dots=rows.map(row=>{
    const extension=Number(row.extension), top=50-44*Math.max(-scale,Math.min(scale,extension))/scale;
    const left=laneBySymbol.get(row.symbol);
    const outlier=Math.abs(extension)>scale;
    const tooltip='<span><b>'+escapeHTML(row.symbol)+' · '+fmt(extension,2)+'×</b><small>'+escapeHTML(row.group)+'</small>'+(outlier?'<em>pinned at map edge</em>':'')+'</span>';
    return '<button class="flow-dot flow-extension-dot '+extensionTone(extension)+(outlier?' outlier':'')+'" data-flow-etf="'+escapeHTML(row.symbol)+'" data-flow-group="'+escapeHTML(row.group)+'" style="left:'+left+'%;top:'+Math.max(6,Math.min(94,top))+'%" aria-label="'+escapeHTML(row.symbol)+' '+fmt(extension,2)+' times ATR extension">'+tooltip+'</button>';
  }).join('');
  const above=rows.filter(row=>Number(row.extension)>=0).length, medianExtension=median(rows.map(row=>row.extension));
  const outlierNote=outliers.length?'<span class="flow-outlier-note">'+outliers.length+' extreme ETF'+(outliers.length===1?'':'s')+' pinned to the edge</span>':'';
  return '<section class="flow-map flow-extension-map"><div class="flow-map-head"><div><span class="eyebrow">50D ATR EXTENSION · ETF DISTRIBUTION</span><h3>Distance from the 50-day moving average</h3><p>One dot is one raw ETF. Its vertical position is its ATR-normalized distance from the 50-day SMA; horizontal position only prevents overlap.</p></div>'+outlierNote+'</div><div class="flow-extension-summary"><span><b>'+above+'</b> above 50D SMA</span><span><b>'+fmt(rows.length-above,0)+'</b> below 50D SMA</span><span><b class="'+extensionTone(medianExtension)+'">'+fmt(medianExtension,2)+'×</b> median extension</span></div><div class="flow-map-plot"><div class="flow-y-label">Y · 50D ATR extension ↑</div><div class="flow-extension-side above">Above 50D SMA · extended</div><div class="flow-extension-side zero">50D SMA · 0×</div><div class="flow-extension-side below">Below 50D SMA · under 50D</div><i class="flow-h-axis"></i>'+dots+'</div></section>';
}
function flowTable(groups,key,previousRanks){
  const columns=['one_day','one_week','one_month','three_months','six_months','one_year'];
  const sorted=[...groups].sort((a,b)=>{const av=flowSort.key==='rank'?a.rank:a[flowSort.key],bv=flowSort.key==='rank'?b.rank:b[flowSort.key];const dir=flowSort.direction==='asc'?1:-1;return (Number(av)-Number(bv))*dir||a.group.localeCompare(b.group);});
  const head=(label,sortKey,align='')=>'<th class="'+align+'"><button data-action="flow-sort" data-sort-key="'+sortKey+'">'+label+(flowSort.key===sortKey?' '+(flowSort.direction==='asc'?'↑':'↓'):'')+'</button></th>';
  const body=sorted.map(group=>{const prior=previousRanks.get(group.group),delta=finite(prior)?Number(prior)-group.rank:null;return '<tr class="'+(flowSelection===group.group?'selected':'')+'" data-flow-group="'+escapeHTML(group.group)+'" data-flow-etf="'+escapeHTML(group.leader)+'"><td class="num">'+group.rank+'</td><td><button data-flow-group="'+escapeHTML(group.group)+'" data-flow-etf="'+escapeHTML(group.leader)+'">'+escapeHTML(group.group)+'</button><small>'+group.member_count+' ETF'+(group.member_count===1?'':'s')+' · '+escapeHTML(group.leader)+'</small></td>'+columns.map(column=>'<td class="num '+returnTone(group[column]??group.performance)+'">'+pct(group[column]??group.performance)+'</td>').join('')+'<td class="num '+extensionTone(group.extension)+'">'+(finite(group.extension)?fmt(group.extension,2)+'×':'—')+'</td><td class="num '+returnTone(group.relative)+'">'+(finite(group.relative)?signed(group.relative)+' pp':'—')+'</td><td class="num '+(delta===null?'':delta>0?'positive':delta<0?'negative':'')+'">'+(delta===null?'—':delta>0?'↑ '+delta:delta<0?'↓ '+Math.abs(delta):'—')+'</td></tr>';}).join('');
  return '<section class="flow-ranking"><div class="flow-ranking-head"><div><span class="eyebrow">COMPLETE RANKING</span><h3>Ranked by median '+flowLabels[key]+' return</h3></div><p>Rank change compares with the saved close five sessions earlier.</p></div><div class="table-box"><table><thead><tr><th class="num">#</th>'+head('Theme / sector','group')+columns.map(column=>head(flowLabels[column],column,'num')).join('')+head('50D ATR ext','extension','num')+head('vs SPX','relative','num')+head('Rank Δ','rank','num')+'</tr></thead><tbody>'+body+'</tbody></table></div></section>';
}
function actionTile(icon,title,copy,href,label,tone='cyan'){return '<a class="action-tile '+tone+'" href="'+href+'"><i>'+icon+'</i><div><b>'+title+'</b><span>'+copy+'</span></div><em>'+label+' →</em></a>';}
const breadthViews={
  daily:{label:'Daily ±4%',keys:['up4','down4'],note:'Stockbee’s primary gauge: stocks moving at least 4% up versus down each session.',colors:['#85d65d','#ff3266'],format:v=>fmt(v,0)},
  ratios:{label:'5D / 10D',keys:['ratio5','ratio10'],note:'Rolling sums of up-4% events divided by down-4% events. Above 1 favors upside pressure.',colors:['#e9c46a','#6aa9ff'],format:v=>fmt(v,2)},
  quarter:{label:'Quarter ±25%',keys:['up25q','down25q'],note:'Counts 25% above the 65-session closing low versus 25% below the closing high; populations can overlap.',colors:['#85d65d','#ff3266'],format:v=>fmt(v,0)},
  month:{label:'Month ±25%',keys:['up25m','down25m'],note:'Counts gaining or losing at least 25% over 20 sessions.',colors:['#85d65d','#ff3266'],format:v=>fmt(v,0)},
  month50:{label:'Month ±50%',keys:['up50m','down50m'],note:'Counts gaining or losing at least 50% over 20 sessions.',colors:['#85d65d','#ff3266'],format:v=>fmt(v,0)},
  fast:{label:'34D ±13%',keys:['up13d34','down13d34'],note:'Counts 13% above the 34-session closing low versus 13% below the closing high; populations can overlap.',colors:['#85d65d','#ff3266'],format:v=>fmt(v,0)},
  t2108:{label:'T2108',keys:['t2108'],note:'Percentage of stocks above their 40-day moving average. 20 and 80 are context zones, not automatic signals.',colors:['#86d65d'],format:v=>pct(v)},
};
function breadthHistoryRows(){
  const end=new Date(`${asof()}T12:00:00`), span={ '1m':31,'3m':92,'6m':184,'ytd':null,'1y':366,'3y':1096,'5y':1827 }[breadthRange];
  const start=breadthRange==='ytd'?new Date(end.getFullYear(),0,1):new Date(end.getTime()-(span||0)*86400000);
  return breadthRows().filter(r=>new Date(`${r.date}T12:00:00`)>=start).reverse();
}
function breadthHistoryChart(){
  const view=breadthViews[breadthMetric], rows=breadthHistoryRows().filter(r=>view.keys.every(k=>finite(r[k])));
  const metricControls='<div class="segments breadth-view-controls">'+Object.entries(breadthViews).map(([key,item])=>'<button data-action="breadth-metric" data-metric="'+key+'" class="'+(breadthMetric===key?'active':'')+'">'+item.label+'</button>').join('')+'</div>';
  const rangeControls='<div class="segments breadth-range-controls">'+[['1m','1M'],['3m','3M'],['6m','6M'],['ytd','YTD'],['1y','1Y'],['3y','3Y'],['5y','5Y']].map(([key,label])=>'<button data-action="breadth-range" data-range="'+key+'" class="'+(breadthRange===key?'active':'')+'">'+label+'</button>').join('')+'</div>';
  if(!rows.length)return '<section class="breadth-workbench"><div class="workbench-head"><div><span class="eyebrow">HISTORICAL BREADTH</span><h2>'+view.label+'</h2></div>'+metricControls+'</div>'+rangeControls+'<p class="empty">No '+view.label+' data is available in this date range.</p></section>';
  const values=rows.flatMap(r=>view.keys.map(k=>Number(r[k]))), floor=breadthMetric==='ratios'?Math.min(0,...values):breadthMetric==='t2108'?0:0, ceiling=breadthMetric==='t2108'?100:Math.max(1,...values)*1.08;
  const width=900,height=250,left=20,right=720,top=18,bottom=215,x=i=>left+i*(right-left)/Math.max(rows.length-1,1),y=v=>bottom-(Number(v)-floor)/Math.max(ceiling-floor,1)*(bottom-top);
  const path=key=>rows.map((r,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(r[key]).toFixed(1)).join(' ');
  const latest=rows.at(-1), axis=Array.from({length:4},(_,i)=>{const value=floor+(ceiling-floor)*i/3;return '<line x1="'+left+'" y1="'+y(value)+'" x2="'+right+'" y2="'+y(value)+'" stroke="#3b3b3b"/><text x="'+(right+12)+'" y="'+(y(value)+4)+'" fill="#aaa89f" font-size="10">'+view.format(value)+'</text>';}).join('');
  const ratioLine=breadthMetric==='ratios'?'<line x1="'+left+'" y1="'+y(1)+'" x2="'+right+'" y2="'+y(1)+'" stroke="#e9c46a" stroke-dasharray="5 5"/>':'';
  const t2108Lines=breadthMetric==='t2108'?'<line x1="'+left+'" y1="'+y(20)+'" x2="'+right+'" y2="'+y(20)+'" stroke="#e9c46a" stroke-dasharray="5 5"/><line x1="'+left+'" y1="'+y(80)+'" x2="'+right+'" y2="'+y(80)+'" stroke="#e9c46a" stroke-dasharray="5 5"/>':'';
  const lines=view.keys.map((key,index)=>'<path d="'+path(key)+'" fill="none" stroke="'+view.colors[index]+'" stroke-width="2.5"/><circle cx="'+x(rows.length-1)+'" cy="'+y(latest[key])+'" r="4" fill="'+view.colors[index]+'"/>').join('');
  const labels=view.keys.map((key,index)=>'<div><i style="background:'+view.colors[index]+'"></i><span>'+(['Up','Down','5D','10D','T2108'][index+(breadthMetric==='ratios'?2:breadthMetric==='t2108'?4:0)]||key)+'</span><b>'+view.format(latest[key])+'</b></div>').join('');
  return '<section class="breadth-workbench"><div class="workbench-head"><div><span class="eyebrow">BREADTH TIME MACHINE</span><h2>'+view.label+'</h2><p>'+view.note+'</p></div>'+metricControls+'</div><div class="workbench-range"><span>Range</span>'+rangeControls+'</div><div class="breadth-plot"><svg viewBox="0 0 900 250" role="img" aria-label="Historical '+escapeHTML(view.label)+' chart">'+axis+ratioLine+t2108Lines+lines+'<text x="'+left+'" y="242" fill="#aaa89f" font-size="10">'+rows[0].date+'</text><text x="'+(right-62)+'" y="242" fill="#aaa89f" font-size="10">'+latest.date+'</text></svg><div class="chart-values">'+labels+'</div></div><div class="workbench-footer"><span>Selected close: <b>'+latest.date+'</b></span><a href="breadth.html">Open full calendar & historical scenarios ↗</a></div></section>';
}
function briefing(){
  const b=breadthRows()[0], old=breadthRows()[1], read=marketRead(b), themesNow=latestETF(themes)?.windows?.[frame]||[];
  const net=(b?.up4||0)-(b?.down4||0), tight=orderedCandidates().filter(r=>r.tight).length, extremes=cot.markets?.filter(m=>{const i=m.history.at(-1).participants.large.index;return i!==null&&(i<=5||i>=95);}).length||0;
  const leader=themesNow[0], breadthShift=old&&finite(b?.t2108)&&finite(old?.t2108)?b.t2108-old.t2108:null;
  return '<section class="command-hero '+read.tone+'"><div><span class="eyebrow">MORNING PLAN · '+escapeHTML(session().date)+'</span><h2>'+read.title+'</h2><p>'+read.plan+'</p><div class="command-tags"><span>Close: '+escapeHTML(asof())+'</span><span>'+frameNames[frame]+' leadership</span><span>Chart review required</span></div></div><aside><span>Risk posture</span><b class="'+read.tone+'">'+(read.tone==='positive'?'Press valid setups':read.tone==='negative'?'Protect capital':'Stay selective')+'</b><small>'+read.reason+'</small></aside></section><div class="toolbar">'+frameControls('Planning horizon')+'</div><section class="decision-strip">'+miniStat('◉','Breadth pressure',fmt(b?.ratio10,2),'10D · above 1 favors upside',b?.ratio10>=1?'positive':'negative')+miniStat('↕','Participation',pct(b?.t2108),'Above 40-day average',b?.t2108>=50?'positive':'gold')+miniStat('◆','Leading theme',escapeHTML(leader?.group||'—'),leader?pct(leader.median_performance)+' median':'No ETF reading','cyan')+miniStat('⚡','Tight candidates',tight,frameNames[frame]+' NEL candidates','orange')+'</section><section class="plan-grid"><div class="plan-main"><div class="section-kicker"><span>WHAT TO DO</span><small>Let the environment dictate how selective you are.</small></div><div class="action-stack">'+actionTile('⌕','Build the chart queue',tight+' tight, non-extended candidates are ready for review.','#screener','Screen','cyan')+actionTile('◆','Trade with leadership',leader?escapeHTML(leader.group)+' is the top '+frameNames[frame].toLowerCase()+' theme.':'Check the current leadership table.','#leadership','Flow','violet')+actionTile('↺','Know what changed',breadthShift===null?'Prior-close comparison is not available.':('T2108 '+signed(breadthShift)+' pp since the prior close.'),'#review','Replay',breadthShift>=0?'positive':'gold')+'</div></div><div class="plan-side"><div class="section-kicker"><span>MARKET CHECK</span><small>Not predictions—just the conditions you are trading in.</small></div><div class="stance-grid"><div><span>Up / down 4%</span><b class="'+(net>=0?'positive':'negative')+'">'+fmt(b?.up4,0)+' / '+fmt(b?.down4,0)+'</b><small>Net '+signed(net)+'</small></div><div><span>COT extremes</span><b>'+extremes+'</b><small>Weekly context only</small></div><div><span>Prior-close breadth</span><b class="'+(breadthShift>=0?'positive':'negative')+'">'+(breadthShift===null?'—':signed(breadthShift)+' pp')+'</b><small>T2108 change</small></div></div></div></section><details class="evidence-drawer"><summary>Why this plan?</summary><p>'+read.reason+' These are decision aids, not calibrated probabilities or trade instructions. Open Pulse for breadth detail, Flow for leadership detail, and Crowding for COT context.</p></details>';
}
let breadthSelected='Daily 4% moves';let breadthPinned=-1;let breadthDate='',breadthWindow=252,breadthHoverRows=[],breadthHoverLatest=null,breadthAth=null;
let breadthSPXChangeSource=null,breadthSPXChanges=new Map();
function breadthSPXChange(date){
 if(breadthSPXChangeSource!==breadth){breadthSPXChangeSource=breadth;breadthSPXChanges=new Map();const ordered=[...breadth].sort((a,b)=>a.date.localeCompare(b.date));let previous=null;ordered.forEach(row=>{if(finite(row.sp)){breadthSPXChanges.set(row.date,previous&&Number(previous.sp)!==0?100*(Number(row.sp)/Number(previous.sp)-1):null);previous=row;}});}
 return breadthSPXChanges.get(date)??null;
}
function breadthSPXChangeLabel(date){const change=breadthSPXChange(date);return change===null?'':(' ('+signed(change,2)+'%)');}
function setBreadthHover(index){
 document.querySelector('.bm-workstation')?._updateBoard?.(index);
  const row=index>=0?breadthHoverRows[index]:breadthHoverLatest,latest=breadthHoverLatest;
  if(!row)return;
  document.querySelectorAll('.bm-explorer-canvas > :not([hidden]) .bm-hit').forEach(node=>node.classList.toggle('bm-linked-active',index>=0&&Number(node.dataset.bmIndex)===index));
  const prior=breadth.filter(r=>r.date<row.date).sort((a,b)=>b.date.localeCompare(a.date))[0];
  const available=breadth.filter(r=>r.date<=row.date);
  document.querySelectorAll('[data-bm-percentile]').forEach(node=>{const k=node.dataset.bmPercentile,rank=breadthPercentile(available,k,row[k]);node.textContent=(k.startsWith('up')?'Upside':'Downside')+' historical rank: '+(rank===null?'—':'percentile '+fmt(rank,0)+'/100');node.style.color=k.startsWith('up')?'#85d65d':'#ff3266';});
  document.querySelectorAll('[data-bm-sp-change]').forEach(node=>{node.textContent=finite(prior?.sp)&&finite(row.sp)?'Session '+signed(row.sp-prior.sp,2)+' ('+signed(100*(row.sp/prior.sp-1),2)+'%)':'Session change unavailable';});
  const date=document.querySelector('[data-bm-date]');
  if(date)date.textContent=(index>=0?(breadthPinned===index?'Pinned ':'Inspecting '):'Close ')+row.date;
 const unpin=document.querySelector('[data-bm-unpin]');if(unpin)unpin.hidden=breadthPinned<0;
  document.querySelectorAll('[data-bm-key]').forEach(el=>{
    const key=el.dataset.bmKey,decimals=Number(el.dataset.bmDecimals||0),suffix=el.dataset.bmSuffix||'';
    const value=finite(row[key])?fmt(row[key],decimals)+suffix+(key==='sp'?breadthSPXChangeLabel(row.date):''):'—';
    const change=index>=0&&finite(row[key])&&finite(latest?.[key])
      ?(key==='sp'
        ?signed(Number(row[key])-Number(latest[key]),2)+' · '+signed(100*(Number(row[key])/Number(latest[key])-1),2)+'% vs latest'
        :signed(Number(row[key])-Number(latest[key]),decimals)+suffix+' vs latest')
      :'Latest close';
    el.innerHTML='<b>'+escapeHTML(el.dataset.bmLabel===undefined?key:el.dataset.bmLabel)+' '+value+'</b><small>'+change+'</small>';
    if(document.body.classList.contains('breadth-page'))el.querySelector('small').textContent=finite(row[key])&&finite(prior?.[key])?signed(Number(row[key])-Number(prior[key]),decimals)+suffix+' vs prior session':'Prior session unavailable';
    if(key==='sp'){const daily=breadthSPXChange(row.date);el.style.color=daily===null||daily===0?'#f5f2e8':daily>0?'#85d65d':'#ff3266';el.style.opacity='1';}else{el.style.color=key.startsWith('up')?'#85d65d':key.startsWith('down')?'#ff3266':breadthInk(row,key);el.style.opacity=key.startsWith('up')||key.startsWith('down')?'1':breadthOpacity(row,key);}
  });
  document.querySelectorAll('[data-spx-performance]').forEach(node=>{
 const first=breadthHoverRows.find(r=>finite(r.sp)),valid=first&&finite(row.sp)&&Number(first.sp)!==0;
 const performance=valid?100*(Number(row.sp)/Number(first.sp)-1):null;
 const period=({5:'1 week',21:'1 month',63:'3 month',126:'6 month',252:'1 year',756:'3 year',1260:'5 year',100000:'All time'})[breadthWindow]||'';
 node.innerHTML='<b>'+period+' Performance: '+(performance===null?'—':signed(performance,2)+'%')+'</b>';
 node.style.color=performance===null||performance===0?'#f5f2e8':performance>0?'#85d65d':'#ff3266';
 });
  document.querySelectorAll('[data-range-key]').forEach(gauge=>{
 const key=gauge.dataset.rangeKey;
 if(key==='sp'){
 const bar=spxHistory.find(bar=>bar.date===row.date),score=bar?.oscillator;
 if(!finite(score)){gauge.hidden=true;return;}gauge.hidden=false;
 const marker=gauge.querySelector('i');marker.style.left=(50+50*Math.max(-1,Math.min(1,Number(score))))+'%';marker.style.background=Number(score)>0?'#85d65d':Number(score)<0?'#ff3266':'#f5f2e8';
 const zero=gauge.querySelector('em');zero.hidden=false;zero.style.left='50%';
 const ends=gauge.querySelector('.bm-range-ends');ends.innerHTML='<small>−1</small><small>'+signed(score,2)+'</small><small>+1</small>';
 gauge.setAttribute('aria-label','50-day ATR extension index '+score+'; zero is the 50-day average; normalized using all available prior SPX history');return;
 }
 const values=breadth.filter(r=>r.date<=row.date&&finite(r[key])).map(r=>Number(r[key]));
 const rail=gauge.querySelector('.bm-range-rail'),ends=gauge.querySelectorAll('.bm-range-ends small');
 if(!values.length||!finite(row[key])){gauge.hidden=true;return;}gauge.hidden=false;
 const low=Math.min(...values),high=Math.max(...values),span=high-low,position=value=>span?Math.max(0,Math.min(100,100*(value-low)/span)):50;
 const marker=rail.querySelector('i');marker.style.left=position(Number(row[key]))+'%';marker.style.background=breadthInk(row,key);
 const balance=rail.querySelector('em');balance.hidden=!key.startsWith('ratio')||low>1||high<1;balance.style.left=position(1)+'%';
 const suffix=key==='t2108'?'%':key==='sp'?'':'×';ends[0].textContent=fmt(low,key==='t2108'?1:2)+suffix;ends[1].textContent=fmt(high,key==='t2108'?1:2)+suffix;
 gauge.setAttribute('aria-label','All-time range through '+row.date+': low '+low+', high '+high+', current '+row[key]);
 });
  if(!document.querySelector('[data-bm-off-ath]'))return;
  const ath=Math.max(...spxHistory.filter(r=>r.date<=row.date&&finite(r.close)).map(r=>Number(r.close)),...available.filter(r=>finite(r.sp)).map(r=>Number(r.sp)));
  const offAth=finite(row.sp)&&finite(ath)?100*(Number(row.sp)/ath-1):null;
  document.querySelectorAll('[data-bm-off-ath]').forEach(el=>el.textContent=offAth===null?'ATH unavailable':Math.abs(offAth)<.005?'At all-time high':fmt(Math.abs(offAth),2)+'% off ATH');
}
function bindBreadthHover(){
  if(document.querySelector('.bm-console'))document.querySelectorAll('.bm-console .bm-tape title').forEach(node=>node.remove());
  document.querySelectorAll('.bm-tape').forEach(tape=>{
    if(tape.dataset.hoverBound)return;tape.dataset.hoverBound='true';
    const setFromPointer=event=>{
      const point=tape.createSVGPoint();
      point.x=event.clientX;point.y=event.clientY;
      const local=point.matrixTransform(tape.getScreenCTM().inverse());
      const index=Math.max(0,Math.min(breadthHoverRows.length-1,Math.floor((local.x-18)/(892/Math.max(breadthHoverRows.length,1)))));
      if(tape.dataset.inspectedIndex!==String(index)){tape.dataset.inspectedIndex=index;setBreadthHover(index);}
      const canvas=tape.closest('.bm-explorer-canvas');if(!canvas)return;
      let overlay=canvas.querySelector('.bm-axis-crosshair');if(!overlay){overlay=document.createElement('div');overlay.className='bm-axis-crosshair';overlay.innerHTML='<i></i><span class="bm-axis-value"></span><span class="bm-axis-date"></span>';canvas.append(overlay);}
      const box=tape.getBoundingClientRect(),parent=canvas.getBoundingClientRect(),cursorY=Math.max(24,Math.min(330,local.y)),low=Number(tape.dataset.low),high=Number(tape.dataset.high),value=high-(cursorY-24)/306*(high-low),spec=JSON.parse(tape.dataset.series);
      overlay.hidden=false;const top=box.top-parent.top+cursorY/380*box.height,left=box.left-parent.left;
      const line=overlay.querySelector('i');line.style.top=top+'px';line.style.left=(left+18/1000*box.width)+'px';line.style.width=(892/1000*box.width)+'px';
      const tag=overlay.querySelector('.bm-axis-value');tag.textContent=fmt(value,spec.keys.some(k=>['sp','ratio5','ratio10'].includes(k))?2:spec.keys.includes('t2108')?1:0)+(spec.keys.includes('t2108')?'%':'');tag.style.top=top+'px';tag.style.left=(left+910/1000*box.width)+'px';
      const dateTag=overlay.querySelector('.bm-axis-date');dateTag.textContent=breadthHoverRows[index]?.date||'';dateTag.style.top=(box.top-parent.top+330/380*box.height+6)+'px';dateTag.style.left=(left+Math.max(55,Math.min(box.width-65,(18+892*(index+.5)/breadthHoverRows.length)/1000*box.width)))+'px';

    };
    let hoverFrame=0,lastPointer=null;tape.addEventListener('pointermove',event=>{lastPointer=event;if(!hoverFrame)hoverFrame=requestAnimationFrame(()=>{hoverFrame=0;setFromPointer(lastPointer);});},{passive:true});
    tape.addEventListener('pointerenter',setFromPointer);
    tape.addEventListener('click',()=>{breadthPinned=Number(tape.dataset.inspectedIndex??-1);setBreadthHover(breadthPinned);});
    tape.addEventListener('pointerleave',()=>{cancelAnimationFrame(hoverFrame);hoverFrame=0;delete tape.dataset.inspectedIndex;setBreadthHover(breadthPinned);const overlay=tape.closest('.bm-explorer-canvas')?.querySelector('.bm-axis-crosshair');if(overlay)overlay.hidden=true;});
  });
}
function breadthPercentile(rows,key,value){
  if(!finite(value))return null;
  const sample=rows.filter(r=>finite(r[key])).map(r=>Number(r[key]));
  return sample.length?100*(sample.filter(v=>v<Number(value)).length+.5*sample.filter(v=>v===Number(value)).length)/sample.length:null;
}
let spxRangeSample=null,spxRangeAverage=null;
function stockbeeColor(r,key){
 if(key==='sp'){if(spxRangeSample!==breadthHoverRows){spxRangeSample=breadthHoverRows;const sample=breadthHoverRows.filter(x=>finite(x.sp));spxRangeAverage=sample.length?sample.reduce((sum,x)=>sum+Number(x.sp),0)/sample.length:null;}if(!finite(r.sp)||spxRangeAverage===null)return '';const average=spxRangeAverage;return Number(r.sp)>average?'sb-green':Number(r.sp)<average?'sb-red':'';}
 const value=Number(r[key]);if(!finite(r[key]))return '';
 if(key==='up4')return !finite(r.down4)?'':value<Number(r.down4)?'sb-soft-red':value>=300?'sb-dark-green':'sb-green';
 if(key==='down4')return value>=300?'sb-red':!finite(r.up4)?'':Number(r.up4)<value?'sb-soft-red':'sb-green';
 if(key==='ratio5'||key==='ratio10')return value>=2?'sb-green':value<.5?'sb-red':'';
 for(const [up,down] of [['up25q','down25q'],['up25m','down25m'],['up13d34','down13d34']])if(key===up||key===down)return finite(r[up])&&finite(r[down])?(Number(r[up])>=Number(r[down])?'sb-green':'sb-red'):'';
 if(key==='up50m')return value>=20?'sb-red':'';
 if(key==='down50m')return value>=20?'sb-green':'';
 if(key==='t2108')return value<20?'sb-green':'';
 return '';
}

function breadthInk(r,key){return {'sb-green':'#85d65d','sb-dark-green':'#85d65d','sb-red':'#ff3266','sb-soft-red':'#ff3266'}[stockbeeColor(r,key)]||'#f5f2e8';}
function breadthOpacity(r,key){return {'sb-green':.65,'sb-dark-green':1,'sb-red':1,'sb-soft-red':.4}[stockbeeColor(r,key)]??1;}
function breadthTape(rows,keys,colors,kind='line',reference=null){
  const W=1000,H=380,L=18,R=910,T=24,B=330;
  const references=reference===null?[]:(Array.isArray(reference)?reference:[{value:reference}]).filter(item=>finite(typeof item==='object'?item.value:item));
  if(keys.length===1&&['sp','indexClose'].includes(keys[0])){const key=keys[0],sample=rows.filter(r=>finite(r[key]));if(sample.length)references.push({value:sample.reduce((sum,r)=>sum+Number(r[key]),0)/sample.length,label:'Range average',color:'#aaa89f'});}
  const referenceValues=references.map(item=>Number(typeof item==='object'?item.value:item));
  const values=rows.flatMap(r=>keys.filter(k=>finite(r[k])).map(k=>Number(r[k])*(kind==='bars'&&k.startsWith('down')?-1:1)));
  if(!values.length)return '<p class="empty">No readings available.</p>';
  let lo=kind==='bars'?Math.min(0,...values):Math.min(...values),hi=Math.max(...values);
  if(referenceValues.length){lo=Math.min(lo,...referenceValues);hi=Math.max(hi,...referenceValues);}
  const pad=Math.max((hi-lo)*.12,kind==='bars'?1:.01);lo-=pad;hi+=pad;
  if(kind==='bars'){hi=Math.ceil(hi/100)*100;lo=Math.floor(lo/100)*100;}
  if(keys.includes('t2108')){lo=0;hi=100;}if(keys[0]?.startsWith('rank_')){lo=0;hi=100;}
  const step=(R-L)/Math.max(rows.length,1),x=i=>L+step*(i+.5),y=v=>B-(v-lo)/(hi-lo)*(B-T);
  let svg=Array.from({length:5},(_,i)=>lo+(hi-lo)*i/4).map(v=>'<line x1="'+L+'" x2="'+R+'" y1="'+y(v)+'" y2="'+y(v)+'" class="bm-grid"/><text x="'+(R+10)+'" y="'+(y(v)+4)+'">'+(kind==='bars'?(v<0?'↓ ':v>0?'↑ ':'')+fmt(Math.abs(v),0):fmt(v,keys.some(k=>k.startsWith('ratio'))?2:0))+'</text>').join('');

  if(kind==='bars')svg+='<line x1="'+L+'" x2="'+R+'" y1="'+y(0)+'" y2="'+y(0)+'" class="bm-reference" style="stroke:#8d8b81"/>';
  svg+=references.map((item,index)=>{const ref=typeof item==='object'?item:{value:item},value=Number(ref.value),label=ref.label||'',color=ref.color||'#8d8b81',offset=(index%2)*11,levelY=y(value),labelY=levelY<T+24?levelY+14+offset:levelY-5-offset;return '<line x1="'+L+'" x2="'+R+'" y1="'+levelY+'" y2="'+levelY+'" class="bm-reference" style="stroke:'+color+'"/>'+(label?'<text x="'+(L+5)+'" y="'+labelY+'" fill="'+color+'" class="bm-level-label">'+escapeHTML(label)+'</text>':'');}).join('');
  keys.forEach((key,j)=>{
    if(kind==='bars'){
      svg+=rows.map((r,i)=>{if(!finite(r[key]))return '';const v=Number(r[key])*(j?-1:1);return '<rect x="'+(x(i)-step*.28)+'" y="'+Math.min(y(v),y(0))+'" width="'+step*.56+'" height="'+Math.max(1,Math.abs(y(v)-y(0)))+'" fill="'+(key.startsWith('down')?'#ff3266':'#85d65d')+'" fill-opacity="1"/>';}).join('');
    }else{
      let pen=false;const d=rows.map((r,i)=>{if(!finite(r[key])){pen=false;return '';}const command=pen?'L':'M';pen=true;return command+x(i)+','+y(Number(r[key]));}).join(' ');
      if(!(keys.length===1&&['ratio5','ratio10','t2108','sp','indexClose'].includes(key)))svg+='<path d="'+d+'" fill="none" stroke="'+(keys.length===1?'#f5f2e8':colors[j])+'" stroke-width="2.3" vector-effect="non-scaling-stroke"/>';
      if(keys.length===1&&['ratio5','ratio10','t2108','sp','indexClose'].includes(key)){
       const average=key==='indexClose'?rows.reduce((sum,r)=>sum+Number(r[key]),0)/rows.length:null;const condition=r=>key==='indexClose'?(Number(r[key])>average?'#85d65d':Number(r[key])<average?'#ff3266':'#f5f2e8'):breadthInk(r,key);
       for(let i=1;i<rows.length;i++){if(!finite(rows[i-1][key])||!finite(rows[i][key]))continue;const color=condition(rows[i]);if(color)svg+='<path d="M'+x(i-1)+','+y(Number(rows[i-1][key]))+' L'+x(i)+','+y(Number(rows[i][key]))+'" fill="none" stroke="'+color+'" stroke-width="2.3" vector-effect="non-scaling-stroke"/>';}
      }
    }
  });
  svg+=rows.map((r,i)=>'<g class="bm-hit" data-bm-index="'+i+'"><rect x="'+(L+step*i)+'" y="0" width="'+step+'" height="'+B+'" fill="rgba(0,0,0,.001)"/><line x1="'+x(i)+'" x2="'+x(i)+'" y1="'+T+'" y2="'+B+'"/>'+keys.filter(k=>finite(r[k])).map((k,j)=>'<circle cx="'+x(i)+'" cy="'+y(Number(r[k])*(kind==='bars'&&k.startsWith('down')?-1:1))+'" r="4" fill="'+(kind==='bars'?(k.startsWith('down')?'#ff3266':'#85d65d'):breadthInk(r,k))+'"/>').join('')+'<title>'+r.date+' · '+keys.map(k=>k+': '+fmt(r[k],kind==='bars'?0:2)).join(' · ')+'</title></g>').join('');
  svg+=rows.filter((r,i)=>i===0||i===rows.length-1||i===Math.floor(rows.length/4)||i===Math.floor(rows.length/2)||i===Math.floor(3*rows.length/4)).map(r=>'<text x="'+x(rows.indexOf(r))+'" y="365" text-anchor="middle">'+r.date.slice(5)+'</text>').join('');
  return '<svg data-low="'+lo+'" data-high="'+hi+'" data-series="'+escapeHTML(JSON.stringify({keys,colors,kind,reference}))+'" class="bm-tape" viewBox="0 0 '+W+' '+H+'" preserveAspectRatio="none" role="img" aria-label="'+escapeHTML(keys.join(', ')+' through '+rows.at(-1).date)+'">'+svg+'</svg>';
}
function legacyEnvironment(){
  const history=breadthRows(),b=history[0],old=history[1];
  if(!b)return '<p class="empty">No breadth data available for this close.</p>';
  const rows=history.slice(0,breadthWindow).reverse();
  breadthHoverRows=rows;breadthHoverLatest=b;
  breadthAth=Math.max(...history.filter(r=>finite(r.sp)).map(r=>Number(r.sp)));
  const net=finite(b.up4)&&finite(b.down4)?b.up4-b.down4:null;
  const delta=(key)=>finite(b[key])&&finite(old?.[key])?signed(b[key]-old[key],0)+' vs prior close':'No prior reading';
  const pair=(key,label,color,decimals=0,suffix='')=>'<span class="bm-hover-key" data-bm-key="'+key+'" data-bm-label="'+label+'" data-bm-decimals="'+decimals+'" data-bm-suffix="'+suffix+'" style="color:'+color+'"><b>'+label+' '+fmt(b[key],decimals)+suffix+'</b><small>Latest close</small></span>';
  const rankTrack=(key,color)=>{
    const rank=breadthPercentile(history,key,b[key]);
    return '<div class="bm-rank"><div><b style="color:'+color+'">'+fmt(b[key],0)+'</b><small>'+delta(key)+'</small><span>'+(rank===null?'Unavailable':Math.round(rank)+'<small> percentile</small>')+'</span></div><div class="bm-track" style="--ink:'+color+'"><i style="width:'+(rank??0)+'%"></i>'+(rank===null?'':'<em style="left:'+Math.max(1,Math.min(99,rank))+'%"></em>')+'</div></div>';
  };
  const measures=[
    ['Quarterly trend','25% from 65-session closing low / high','up25q','down25q'],
    ['Faster trend','13% from 34-session closing low / high','up13d34','down13d34'],
    ['Monthly momentum','25% gain / loss over 20 sessions','up25m','down25m'],
    ['Monthly extremes','50% gain / loss over 20 sessions','up50m','down50m']
  ];
  const upDays=rows.filter(r=>finite(r.up4)&&r.up4>=300).length,downDays=rows.filter(r=>finite(r.down4)&&r.down4>=300).length;
  const t=finite(b.t2108)?Number(b.t2108):null;
  const windowHigh=Math.max(...rows.filter(r=>finite(r.sp)).map(r=>Number(r.sp))),windowLow=Math.min(...rows.filter(r=>finite(r.sp)).map(r=>Number(r.sp)));
  const offAth=finite(b.sp)&&finite(breadthAth)?100*(Number(b.sp)/breadthAth-1):null;
  const priceLevels=[
    {value:breadthAth,label:'ATH '+fmt(breadthAth,0),color:'#e9c46a'},
    ...(Math.abs(windowHigh-breadthAth)>.01?[{value:windowHigh,label:breadthWindow+'D high '+fmt(windowHigh,0),color:'#00bcd4'}]:[]),
    {value:windowLow,label:breadthWindow+'D low '+fmt(windowLow,0),color:'#ff3266'}
  ];
  const spOscillator=finite(b.spOscillator)?Number(b.spOscillator):null;
  const spExtension=finite(b.spExtension)?Number(b.spExtension):null;
  const oscillatorLevels=[
    {value:-1,label:'Deeply oversold',color:'#ff3266'},
    {value:0,label:'At 50D',color:'#8d8b81'},
    {value:1,label:'Deeply overbought',color:'#85d65d'}
  ];
  return '<div class="bm-page"><header class="bm-heading"><div><span class="eyebrow">STOCKBEE MARKET MONITOR</span><h2>The market beneath the index</h2></div><a href="breadth.html">Time Machine ↗</a></header>'+
    '<section class="bm-summary"><div><span>Latest close</span><b>'+b.date+'</b></div><div><span>Net daily 4% moves</span><b class="'+(net>=0?'positive':'negative')+'">'+(net===null?'—':signed(net,0))+'</b><small>'+fmt(b.up4,0)+' up / '+fmt(b.down4,0)+' down</small></div><div><span>10-day pressure</span><b class="'+(b.ratio10>=1?'positive':'negative')+'">'+fmt(b.ratio10,2)+'×</b><small>'+(finite(b.ratio10)?b.ratio10>=1?'More upside events':'More downside events':'Unavailable')+'</small></div><div><span>Above 40-day average</span><b>'+fmt(t,1)+'%</b><small>T2108 · '+(t===null?'Unavailable':t<20?'Below 20%':t>80?'Above 80%':'Between 20–80%')+'</small></div></section>'+
    '<section class="bm-panel"><div class="bm-section-head"><div><h3>Is buying following through?</h3><p data-bm-date>Latest close · hover any chart to inspect a session</p></div><div class="segments">'+[15,30,65].map(n=>'<button data-action="breadth-window" data-window="'+n+'" class="'+(breadthWindow===n?'active':'')+'">'+n+' sessions</button>').join('')+'</div></div>'+
    '<div class="bm-chart-row"><div class="bm-chart-label"><b>S&P 500</b><span class="bm-hover-key bm-price-key" data-bm-key="sp" data-bm-label="SPX" data-bm-decimals="2" data-bm-suffix=""><b>SPX '+fmt(b.sp,2)+'</b><small>Latest close</small></span><span class="bm-sp-context"><b data-bm-off-ath>'+(offAth===null?'ATH unavailable':Math.abs(offAth)<.005?'At all-time high':fmt(Math.abs(offAth),2)+'% off ATH')+'</b><small>'+breadthWindow+'D H '+fmt(windowHigh,2)+' · L '+fmt(windowLow,2)+'</small></span></div>'+breadthTape(rows,['sp'],['#86d65d'],'line',priceLevels)+'</div>'+
    '<div class="bm-chart-row bm-oscillator-row"><div class="bm-chart-label"><b>SPX 50D extension</b><span class="bm-hover-key" data-bm-key="spOscillator" data-bm-label="Score" data-bm-decimals="2" data-bm-suffix=""><b>Score '+signed(spOscillator,2)+'</b><small>0 = 50-day SMA</small></span><span class="bm-hover-key" data-bm-key="spExtension" data-bm-label="Extension" data-bm-decimals="2" data-bm-suffix="× ATR"><b>Extension '+signed(spExtension,2)+'× ATR</b><small>Since-1927 reference</small></span></div>'+breadthTape(rows,['spOscillator'],['#b785ff'],'line',oscillatorLevels)+'</div>'+
    '<div class="bm-chart-row"><div class="bm-chart-label"><b>Daily 4% moves</b>'+pair('up4','↑','#85d65d')+pair('down4','↓','#ff3266')+'<small>Counts, not market share</small></div>'+breadthTape(rows,['up4','down4'],['#85d65d','#ff3266'],'bars')+'</div>'+
    '<div class="bm-chart-row"><div class="bm-chart-label"><b>Rolling pressure</b>'+pair('ratio5','5D','#e9c46a',2,'×')+pair('ratio10','10D','#6aa9ff',2,'×')+'<small>Dashed line = balance (1)</small></div>'+breadthTape(rows,['ratio5','ratio10'],['#e9c46a','#6aa9ff'],'line',1)+'</div>'+
    '<div class="bm-chart-row"><div class="bm-chart-label"><b>T2108</b>'+pair('t2108','Above 40D','#86d65d',1,'%')+'<small>20% / 80% are context zones</small></div>'+breadthTape(rows,['t2108'],['#86d65d'])+'</div>'+
    '<div class="bm-foot"><span>300+ move days in this window: <b class="positive">'+upDays+' upside</b> / <b class="negative">'+downDays+' downside</b></span><span>Clusters matter more than one strong day.</span></div></section>'+
    '<section class="bm-panel"><div class="bm-section-head"><div><h3>How unusual is the participation?</h3><p>Each count compared with its own available history through '+b.date+'.</p></div><span class="bm-chip">Independent percentile scales</span></div><div class="bm-rank-head"><span>Measure</span><span class="positive">↑ Upside count & historical rank</span><span class="negative">↓ Downside count & historical rank</span></div>'+
    measures.map(m=>'<div class="bm-rank-row"><div><b>'+m[0]+'</b><small>'+m[1]+'</small></div>'+rankTrack(m[2],'#85d65d')+rankTrack(m[3],'#ff3266')+'</div>').join('')+
    '<div class="bm-foot">Longer fill = a higher count relative to that series’ history. Upside and downside counts can overlap; these are not shares of the market.</div></section>'+
    '<section class="bm-panel bm-participation"><div><span class="eyebrow">T2108 · TREND PARTICIPATION</span><h3>'+fmt(t,1)+'% above the 40-day average</h3><p>20% and 80% mark extreme participation zones, not automatic trade signals.</p></div><div class="bm-gauge"><div class="bm-gauge-track">'+(t===null?'':'<i style="left:'+Math.max(0,Math.min(100,t))+'%"></i>')+'</div><div><span>0%</span><span>20%</span><span>80%</span><span>100%</span></div></div></section>'+
    '<details class="bm-details"><summary>Explore individual measures & longer history</summary>'+breadthHistoryChart()+'</details>'+
    '<details class="bm-details"><summary>Daily readings · '+rows.length+' sessions</summary><div class="bm-table-wrap"><table><thead><tr><th>Close</th><th>Up 4%</th><th>Down 4%</th><th>5D ratio</th><th>10D ratio</th><th>T2108</th><th>SPX</th></tr></thead><tbody>'+[...rows].reverse().map(r=>'<tr><td>'+r.date+'</td>'+['up4','down4','ratio5','ratio10','t2108','sp'].map(k=>'<td>'+fmt(r[k],k.includes('4')?0:2)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></details>'+
    '<details class="bm-details"><summary>Definitions, sources & calculation notes</summary><div class="bm-method"><p><b>Daily 4% moves:</b> Stockbee’s published scan counts close-to-close moves of at least 4%, with volume of at least 100,000 shares and greater than the previous session. These are breadth events, not individually confirmed chart breakouts.</p><p><b>5D / 10D:</b> Rolling totals of upside events divided by downside events. Above 1 means more upside events. The sequence over roughly 10–15 sessions matters; 300+ days are historical reference levels, not a mechanical bullish signal.</p><p><b>Quarter / 34D:</b> Upside is measured from the lowest closing price over 65 / 34 sessions; downside from the highest closing price. A stock can meet both conditions. Monthly measures use returns over 20 sessions. Stockbee applies additional price/liquidity requirements to these scans.</p><p><b>Percentiles are our context layer, not Stockbee’s official signal.</b> Each series uses all non-missing saved readings through the selected close, with ties assigned their midpoint rank. Missing readings are excluded. Coverage starts as early as '+history.at(-1).date+' but differs by measure. These are raw counts: changes in the stock universe affect comparisons across years.</p><p><a href="https://stockbee.blogspot.com/2014/08/how-i-get-market-monitor-numbers.html?m=0" target="_blank" rel="noopener">Stockbee’s scan definitions ↗</a> · <a href="https://stockbee.blogspot.com/2010/05/if-you-want-to-avoid-market-surprises.html" target="_blank" rel="noopener">Reading the sequence ↗</a></p></div></details></div>';
}

function environment(){
 const history=breadth.filter(r=>!breadthDate||r.date<=breadthDate).sort((a,b)=>b.date.localeCompare(a.date)),b=history[0];
 if(!b)return '<p class="empty">Breadth data unavailable.</p>';
 const rows=history.slice(0,breadthWindow).reverse();
 breadthHoverRows=rows;breadthHoverLatest=b;
 breadthAth=Math.max(...spxHistory.filter(r=>r.date<=b.date&&finite(r.close)).map(r=>Number(r.close)),...history.filter(r=>finite(r.sp)).map(r=>Number(r.sp)));
 const key=(k,label,color,d=0,suffix='')=>'<span class="bm-hover-key" data-bm-key="'+k+'" data-bm-label="'+label+'" data-bm-decimals="'+d+'" data-bm-suffix="'+suffix+'" style="color:'+color+'"><b>'+label+' '+fmt(b[k],d)+suffix+'</b><small>Latest selected close</small></span>';
 const chart=(title,readings,keys,colors,kind='line',levels=null)=>'<div class="bm-chart-row"><div class="bm-chart-label"><b>'+title+'</b>'+readings+'</div>'+breadthTape(rows,keys,colors,kind,levels)+'</div>';
 const spRows=spxHistory.filter(r=>r.date<=b.date&&finite(r.close)),high=Math.max(...rows.filter(r=>finite(r.sp)).map(r=>r.sp)),low=Math.min(...rows.filter(r=>finite(r.sp)).map(r=>r.sp));
 const market=chart('S&P 500',key('sp','Close','#86d65d',2)+'<span data-bm-sp-change></span><span data-bm-off-ath></span>',['sp'],['#86d65d'],'line',[{value:high,label:'Window high',color:'#00bcd4'},{value:low,label:'Window low',color:'#ff3266'}])+
 chart('50D extension',key('spExtension','ATR','#b785ff',2,'×')+key('spOscillator','Score','#b785ff',2),['spOscillator'],['#b785ff'],'line',0)+
 chart('T2108',key('t2108','Above 40D','#86d65d',1,'%')+'<small>Stocks above their 40-day average</small>',['t2108'],['#86d65d'],'line',[{value:20,label:'20%',color:'#aaa89f'},{value:80,label:'80%',color:'#aaa89f'}]);
 const pressure=chart('Daily 4% moves',key('up4','Up','#85d65d')+key('down4','Down','#ff3266'),['up4','down4'],['#85d65d','#ff3266'],'bars')+
 chart('Rolling pressure',key('ratio5','5D','#e9c46a',2,'×')+key('ratio10','10D','#6aa9ff',2,'×')+'<small>Upside events ÷ downside events</small>',['ratio5','ratio10'],['#e9c46a','#6aa9ff'],'line',1);
 const measures=[['Quarterly trend','25% from 65-session closing low / high','up25q','down25q'],['34-session trend','13% from 34-session closing low / high','up13d34','down13d34'],['Monthly momentum','25% gain / loss over 20 sessions','up25m','down25m'],['Monthly extremes','50% gain / loss over 20 sessions','up50m','down50m']];
 const trend=measures.map(([title,definition,up,down])=>'<section class="bm-panel bm-trend-card"><h3>'+title+'</h3><small class="note">'+definition+'</small>'+chart('',key(up,'Up','#85d65d')+key(down,'Down','#ff3266')+'<span data-bm-percentile="'+up+'"></span><span data-bm-percentile="'+down+'"></span>',[up,down],['#85d65d','#ff3266'])+'</section>').join('');
 return '<div class="bm-page bm-redesign"><header class="bm-compact-header"><h2>Breadth</h2><span data-bm-date>Close '+b.date+'</span><label>History <input type="date" data-breadth-date value="'+b.date+'" min="'+breadth.map(r=>r.date).sort()[0]+'" max="'+breadth.map(r=>r.date).sort().at(-1)+'"></label><div class="segments">'+[[5,'1W','Fast'],[21,'1M','Swing'],[63,'3M','Trend'],[126,'6M','Cycle'],[252,'1Y','Long'],[756,'3Y','Regime'],[1260,'5Y','Secular'],[100000,'All time','Full history']].map(([n,label,role])=>'<button data-action="breadth-window" data-window="'+n+'" class="'+(breadthWindow===n?'active':'')+'"><b>'+label+'</b><small>'+role+'</small></button>').join('')+'</div></header><div class="bm-main-grid"><section class="bm-panel"><h3>Market & participation</h3>'+market+'</section><section class="bm-panel"><h3>Buying & selling pressure</h3>'+pressure+'<div class="bm-pressure-note">Daily counts show intensity. The 5D and 10D ratios show whether buying or selling is persisting.</div></section></div><div class="bm-trend-head"><h3>Trend participation</h3><small>Historical ranks use all available readings through the inspected date.</small></div><div class="bm-trend-grid">'+trend+'</div><details class="bm-details"><summary>Daily readings</summary><div class="table-box"><table><thead><tr><th>Date</th><th>SPX</th><th>Up 4%</th><th>Down 4%</th><th>5D</th><th>10D</th><th>T2108</th></tr></thead><tbody>'+[].map(r=>'<tr><td>'+r.date+'</td>'+['sp','up4','down4','ratio5','ratio10','t2108'].map(k=>'<td>'+fmt(r[k],k.includes('4')?0:2)+'</td>').join('')+'</tr>').join('')+'</tbody></table></div></details></div>';
}

function flowIndexPane(){
 const end=asof(),n=({'1w':5,'1m':21,'3m':63,'6m':126,'1y':252,'3y':756,'5y':1260,'all':100000})[indexFrame]||252;
 const markets=Object.entries(indexHistory).map(([id,m])=>({...m,id,history:(m.history||[]).filter(r=>r.date<=end)})).filter(m=>m.history.length);
 const active=markets.find(m=>m.id===flowSelection)||markets[0];
 const tabs='<div class="segments">'+[['themes','Themes'],['sectors','Sectors'],['indexes','Indexes']].map(([id,label])=>'<button data-leadership="'+id+'" class="'+(id===leadershipKind?'active':'')+'">'+label+'</button>').join('')+'</div>';
 if(!active)return '<div class="flow-console-tabs">'+tabs+'</div><p>Index history unavailable.</p>';
 const last=m=>m.history.at(-1),change=(m,count)=>{const h=m.history,prior=h[Math.max(0,h.length-1-count)];return prior?100*(last(m).close/prior.close-1):null;};
 const gauge=m=>{const score=last(m).oscillator;return '<span data-index-gauge="'+m.id+'" class="flow-index-gauge"><i style="left:'+Math.max(0,Math.min(100,50+50*(Number(score)||0)))+'%;background:'+(score<0?'#ff3266':'#85d65d')+'"></i><em></em></span><span class="flow-index-gauge-label"><small>−1</small><b>'+ (finite(score)?signed(score,2):'—')+'</b><small>+1</small></span>';};
 const list=markets.map(m=>'<button data-flow-index="'+m.id+'" class="flow-index-row '+(m.id===active.id?'active':'')+'"><b>'+escapeHTML(m.name)+'</b><strong data-index-quote="'+m.id+'" class="'+returnTone(change(m,1))+'">'+fmt(last(m).close,2)+' ('+signed(change(m,1),2)+'%)</strong>'+gauge(m)+'</button>').join('');
 const rangeOptions=[['1w','1W','Fast'],['1m','1M','Swing'],['3m','3M','Trend'],['6m','6M','Cycle'],['1y','1Y','Long'],['3y','3Y','Regime'],['5y','5Y','Secular'],['all','All time','Full history']];
 const ranges=rangeOptions.map(([id,label,role])=>'<button data-index-range="'+id+'" class="'+(indexFrame===id?'active':'')+'"><b>'+label+'</b><small>'+role+'</small></button>').join('');
 const rows=active.history.slice(-n-1).map(r=>({date:r.date,indexClose:r.close}));
 flowIndexView={markets,active,rows,n};

 const columns=[['1D',1],['1W',5],['1M',21],['3M',63],['6M',126],['1Y',252]];
 return '<div class="flow-console flow-index-console"><div class="flow-console-top"><section class="flow-console-leaders"><div class="flow-console-tabs">'+tabs+'</div><div class="flow-index-list">'+list+'</div><p class="flow-index-note">50D ATR-extension index · −1 / 0 / +1<br>History: '+active.history[0].date+' to '+last(active).date+'</p></section><section class="flow-console-chart"><div class="flow-console-chartbar"><b>'+escapeHTML(active.name)+'</b><div class="segments">'+ranges+'</div></div><div class="flow-index-readout"><strong data-index-current class="'+returnTone(change(active,1))+'">'+fmt(last(active).close,2)+' ('+signed(change(active,1),2)+'%)</strong><span data-index-performance></span><small data-index-inspected></small></div>'+breadthTape(rows,['indexClose'],['#f5f2e8'])+'</section></div><section class="flow-ranking"><div class="table-box"><table><thead><tr><th>Index</th><th>Close</th>'+columns.map(([label])=>'<th>'+label+'</th>').join('')+'<th>50D ATR ext</th><th>Extension index</th></tr></thead><tbody>'+markets.map(m=>'<tr data-flow-index="'+m.id+'"><td>'+escapeHTML(m.name)+'</td><td>'+fmt(last(m).close,2)+'</td>'+columns.map(([,days])=>'<td class="'+returnTone(change(m,days))+'">'+signed(change(m,days),2)+'%</td>').join('')+'<td>'+fmt(last(m).extension,2)+'×</td><td>'+signed(last(m).oscillator,2)+'</td></tr>').join('')+'</tbody></table></div></section></div>';
}
function mountIndexInspection(){
 const state=flowIndexView,root=document.querySelector('.flow-index-console'),svg=root?.querySelector('.bm-tape');if(!state||!svg)return;
 svg.querySelectorAll('title').forEach(node=>node.remove());
 const barAt=(market,date)=>{let low=0,high=market.history.length;while(low<high){const mid=(low+high)>>1;if(market.history[mid].date<=date)low=mid+1;else high=mid;}return low-1;};
 const periods={'1w':'1 week','1m':'1 month','3m':'3 month','6m':'6 month','1y':'1 year','3y':'3 year','5y':'5 year',all:'All time'};
 let previousDate='',pinned=-1,frame=0;
 const update=index=>{
 const date=index<0?state.rows.at(-1).date:state.rows[index].date;if(date===previousDate)return;previousDate=date;
 state.markets.forEach(m=>{const i=barAt(m,date),bar=m.history[i],prior=m.history[i-1];if(!bar)return;
 const daily=prior?100*(bar.close/prior.close-1):null,color=daily===null||daily===0?'#f5f2e8':daily>0?'#85d65d':'#ff3266';
 const quote=root.querySelector('[data-index-quote="'+m.id+'"]');if(quote){quote.textContent=fmt(bar.close,2)+(daily===null?'':' ('+signed(daily,2)+'%)');quote.style.color=color;}
 const gauge=root.querySelector('[data-index-gauge="'+m.id+'"]');if(gauge){const score=bar.oscillator,marker=gauge.querySelector('i');marker.style.left=(50+50*(Number(score)||0))+'%';marker.style.background=score<0?'#ff3266':score>0?'#85d65d':'#f5f2e8';gauge.nextElementSibling.querySelector('b').textContent=finite(score)?signed(score,2):'—';}
 if(m.id===state.active.id){const current=root.querySelector('[data-index-current]');current.textContent=fmt(bar.close,2)+(daily===null?'':' ('+signed(daily,2)+'%)');current.style.color=color;
 const performance=100*(bar.close/state.rows[0].indexClose-1),perf=root.querySelector('[data-index-performance]');perf.textContent=periods[indexFrame]+' Performance: '+signed(performance,2)+'%';perf.style.color=performance>0?'#85d65d':performance<0?'#ff3266':'#f5f2e8';
 root.querySelector('[data-index-inspected]').textContent=(index<0?'Close ':'Inspecting ')+bar.date+' · ATR extension '+fmt(bar.extension,2)+'×';}
 });
 svg.querySelectorAll('.bm-hit.bm-linked-active').forEach(node=>node.classList.remove('bm-linked-active'));if(index>=0)svg.querySelector('[data-bm-index="'+index+'"]')?.classList.add('bm-linked-active');
 };
 document.onkeydown=event=>{if(event.key==='Escape'&&document.querySelector('.flow-index-console')){pinned=-1;update(-1);}};
 const panel=root.querySelector('.flow-console-chart');panel.style.position='relative';const overlay=document.createElement('div');overlay.className='bm-axis-crosshair';overlay.hidden=true;overlay.innerHTML='<i></i><span class="bm-axis-value"></span><span class="bm-axis-date"></span>';panel.append(overlay);
 const inspect=event=>{const point=svg.createSVGPoint();point.x=event.clientX;point.y=event.clientY;const local=point.matrixTransform(svg.getScreenCTM().inverse()),i=Math.max(0,Math.min(state.rows.length-1,Math.floor((local.x-18)/892*state.rows.length)));svg.dataset.index=i;update(i);
 const box=svg.getBoundingClientRect(),parent=panel.getBoundingClientRect(),y=Math.max(24,Math.min(330,local.y)),top=box.top-parent.top+y/380*box.height,left=box.left-parent.left,value=Number(svg.dataset.high)-(y-24)/306*(Number(svg.dataset.high)-Number(svg.dataset.low));overlay.hidden=false;
 const line=overlay.querySelector('i');line.style.cssText='top:'+top+'px;left:'+(left+box.width*.018)+'px;width:'+box.width*.892+'px';const valueLabel=overlay.querySelector('.bm-axis-value');valueLabel.textContent=fmt(value,2);valueLabel.style.cssText='top:'+top+'px;left:'+(left+box.width*.91+5)+'px';const dateLabel=overlay.querySelector('.bm-axis-date');dateLabel.textContent=state.rows[i].date;dateLabel.style.cssText='top:'+(box.top-parent.top+box.height*330/380+6)+'px;left:'+(left+box.width*(18+892*(i+.5)/state.rows.length)/1000)+'px';};
 svg.addEventListener('pointermove',event=>{if(frame)cancelAnimationFrame(frame);frame=requestAnimationFrame(()=>{frame=0;inspect(event);});},{passive:true});svg.addEventListener('click',()=>{pinned=Number(svg.dataset.index??-1);});svg.addEventListener('pointerleave',()=>{cancelAnimationFrame(frame);frame=0;overlay.hidden=true;update(pinned);});
 const size=()=>{const box=svg.getBoundingClientRect();svg.querySelectorAll('text').forEach(text=>{text.style.transformBox='fill-box';text.style.transformOrigin='center';text.style.transform='scale('+1000/box.width+','+380/box.height+')';});};requestAnimationFrame(size);update(-1);
}
let flowOverviewState=null,flowOverviewSort={market:'default',segments:'default',equal_weight:'default',sectors:'default',industries:'default'};
function flowMarketOverview(){
 if(!flowMarket.series?.RSP)return '<p class="empty">Market overview data is not available. Run the daily market-data refresh.</p>';
 const dates=flowMarket.series.RSP.history.filter(r=>r.date<=asof()),date=dates.at(-1)?.date;if(!date)return '<p>No completed session available.</p>';
 const metric=(symbol)=>{const source=flowMarket.series[symbol],history=(source?.history||[]).filter(r=>r.date<=date),last=history.at(-1),prior=history.at(-2);if(!last||last.date!==date)return {symbol,name:source?.name||symbol,available:false};
 const back=history.at(-22),month=back?100*(last.close/back.close-1):null,day=prior?100*(last.close/prior.close-1):null,intraday=100*(last.close/last.open-1),offHigh=100*(last.close/Math.max(...history.slice(-252).map(r=>r.high))-1);
 return {...last,symbol,name:source.name,available:true,history,month,day,intraday,offHigh,historyStart:source.history_start};};
 const benchmark=metric('RSP'),metrics=Object.fromEntries(Object.keys(flowMarket.series).map(symbol=>[symbol,metric(symbol)]));
 Object.values(metrics).forEach(m=>{if(!m.available)return;m.relative=finite(m.month)&&finite(benchmark.month)?100*((1+m.month/100)/(1+benchmark.month/100)-1):null;
 const rspByDate=new Map(benchmark.history.map(r=>[r.date,r.close]));let wins=0,total=0;const h=m.history;for(let i=Math.max(1,h.length-21);i<h.length;i++){const prev=h[i-1],now=h[i],rspPrev=rspByDate.get(prev.date),rspNow=rspByDate.get(now.date);if(rspPrev&&rspNow){total++;if(now.close/prev.close>rspNow/rspPrev)wins++;}}m.rsDays=total?100*wins/total:null;});
 flowOverviewState={date,metrics,benchmark,rankings:{}};
 const value=(v,d=1)=>finite(v)?signed(v,d)+'%':'—';
 const marketChartOrder=['SPY','QQQ','IWM','DIA','RSP','QQQE','SPMO','TLT'];
 const cards=marketChartOrder.map(symbol=>flowMarket.groups.market.find(entry=>entry.symbol===symbol)).filter(Boolean).map(({symbol,name})=>{const m=metrics[symbol],score=m?.oscillator;return '<article class="market-index-card"><header><div><b>'+symbol+'</b><span>'+escapeHTML(name)+'</span></div><strong class="'+returnTone(m?.day)+'">'+(m?.available?fmt(m.close,2)+' <small>('+value(m.day,2)+')</small>':'Unavailable')+'</strong></header><div class="market-tv" id="market-tv-'+symbol+'" data-market-chart="'+symbol+'"><span>Loading daily chart…</span></div><footer><div class="market-gauge-title"><span>50D ATR index</span><b class="'+returnTone(score)+'">'+(finite(score)?signed(score,2):'—')+'</b><small>'+(finite(m?.extension)?fmt(m.extension,2)+'×':'—')+'</small></div><div class="market-extension-gauge"><em></em><i style="left:'+(finite(score)?50+50*score:50)+'%;background:'+(score<0?'#ff3266':'#85d65d')+'"></i></div><div class="market-card-context"><small>−1</small><span>'+(symbol==='RSP'?'RSP · benchmark':'1M vs RSP <b class="'+returnTone(m?.relative)+'">'+value(m?.relative)+'</b>')+'</span><small>+1</small></div></footer></article>';}).join('');
 const spark=(values,relative=false)=>{
 const good=values.filter(finite);if(good.length<2)return '—';
 const high=Math.max(...good),low=Math.min(...good),highIndex=good.indexOf(high),lowIndex=good.indexOf(low),darkGreen='#348747',pink='#ff3266';
 if(relative){
  const returns=good.map(v=>100*(v/good[0]-1)),lo=Math.min(0,...returns),hi=Math.max(0,...returns),span=hi-lo||1,y=v=>30-(v-lo)/span*26,zero=y(0),step=92/good.length;
  const bars=returns.map((v,i)=>{const top=Math.min(zero,y(v)),height=Math.max(.65,Math.abs(y(v)-zero)),color=i===lowIndex&&low!==high?pink:i===highIndex&&low!==high?darkGreen:v<0?pink:'#85d65d';return '<rect x="'+(4+i*step).toFixed(2)+'" y="'+top.toFixed(2)+'" width="'+Math.max(.6,step-.9).toFixed(2)+'" height="'+height.toFixed(2)+'" fill="'+color+'"'+([highIndex,lowIndex].includes(i)&&low!==high?' stroke="#f5f2e8" stroke-width=".65"':'')+'/>';}).join('');
  return '<svg class="market-spark market-rs-columns" viewBox="0 0 100 34" preserveAspectRatio="none" role="img" aria-label="One-month cumulative relative return versus RSP; highest and lowest readings highlighted"><line x1="3" x2="97" y1="'+zero+'" y2="'+zero+'" stroke="#666" stroke-width=".5"/>'+bars+'</svg>';
 }
 const span=high-low||1,x=i=>4+i*92/(good.length-1),y=v=>30-(v-low)/span*26,path=good.map((v,i)=>(i?'L':'M')+x(i).toFixed(1)+','+y(v).toFixed(1)).join(' '),color=good.at(-1)>=good[0]?'#85d65d':pink;
 const dots=high===low?'':[[highIndex,high,darkGreen],[lowIndex,low,pink]].map(([i,v,c])=>'<circle cx="'+x(i).toFixed(1)+'" cy="'+y(v).toFixed(1)+'" r="2.7" fill="'+c+'" stroke="#202020" stroke-width=".8"/>').join('');
 return '<svg class="market-spark market-price-line" viewBox="0 0 100 34" preserveAspectRatio="none" role="img" aria-label="One-month closing prices; highest close dark green, lowest close pink"><path d="'+path+'" fill="none" stroke="'+color+'" stroke-width="1.6"/>'+dots+'</svg>';
 };
 const rspMap=new Map(benchmark.history.map(r=>[r.date,r.close]));
 const rel=(m,n,shift=0)=>{const h=m.history||[],end=h.at(-1-shift),start=h.at(-1-shift-n);return end&&start&&rspMap.get(end.date)&&rspMap.get(start.date)?100*((end.close/start.close)/(rspMap.get(end.date)/rspMap.get(start.date))-1):null;};
 const groupTable=(key,title)=>{let rows=(flowMarket.groups[key]||[]).map(entry=>({...metrics[entry.symbol],symbol:entry.symbol,name:entry.name}));
 const rank=(m,n,shift=0)=>{const v=rel(m,n,shift),pop=rows.filter(r=>r.available&&r.symbol!=='RSP').map(r=>rel(r,n,shift)).filter(finite);if(!finite(v)||!pop.length||m.symbol==='RSP')return null;return 100*(pop.filter(x=>x<v).length+.5*(pop.filter(x=>x===v).length-1))/Math.max(1,pop.length-1);};
 rows.forEach(m=>{m.rsMonth=rank(m,21);m.rsWeek=rank(m,5);const old=rank(m,5,3);m.thrust=finite(m.rsMonth)&&finite(m.rsWeek)&&finite(old)?.6*m.rsWeek+.4*m.rsMonth+.1*(m.rsWeek-old):null;});
 flowOverviewState.rankings[key]=Object.fromEntries(rows.map(m=>[m.symbol,{rsMonth:m.rsMonth,thrust:m.thrust}]));
 const sort=flowOverviewSort[key];if(sort&&sort!=='default')rows.sort((a,b)=>(finite(b[sort])?b[sort]:-Infinity)-(finite(a[sort])?a[sort]:-Infinity));else if(!['market','segments'].includes(key))rows.sort((a,b)=>(b.rsMonth??-Infinity)-(a.rsMonth??-Infinity)||(b.thrust??-Infinity)-(a.thrust??-Infinity));
 const top=rows.filter(m=>m.available&&m.symbol!=='RSP').reduce((a,b)=>!a||b.relative>a.relative?b:a,null);
 const columns=[['RS 1M %','rsMonth'],['RS Thrust %','thrust'],['1M price','priceSpark'],['1M RS','rsSpark'],['50D ATR index','oscillator'],['RS vs RSP','relative'],['Intraday','intraday'],['1D','day'],['1M','month'],['Off 52W H','offHigh']];
 return '<section class="market-comparison market-comparison-'+key+'"><header><h3>'+title+'</h3><small>'+(key==='segments'?'Small → mid → large cap':top?'<b>'+top.symbol+'</b> strongest 1M return vs RSP':'')+'</small></header><div class="market-table-scroll"><table><thead><tr><th>ETF / market</th>'+columns.map(([label,k])=>'<th>'+(['priceSpark','rsSpark'].includes(k)?label:'<button data-market-sort="'+k+'" data-market-category="'+key+'">'+label+(sort===k?' ↓':'')+'</button>')+'</th>').join('')+'</tr></thead><tbody>'+rows.map(m=>'<tr><td><button data-market-detail="'+m.symbol+'" data-market-category="'+key+'"><b>'+m.symbol+'</b><span>'+escapeHTML(m.name)+'</span></button></td>'+columns.map(([,k])=>{if(k==='priceSpark'||k==='rsSpark')return '<td data-sort-value="'+(finite(k==='priceSpark'?m.month:m.relative)?(k==='priceSpark'?m.month:m.relative):'')+'">'+spark((m.history||[]).slice(-22).map(r=>k==='priceSpark'?r.close:rspMap.get(r.date)?r.close/rspMap.get(r.date):null),k==='rsSpark')+'</td>';const v=m[k];if(k==='oscillator')return '<td><div class="market-table-atr"><b class="'+returnTone(v)+'">'+(finite(v)?signed(v,2):'—')+'</b><div><em></em><i style="left:'+(finite(v)?50+50*v:50)+'%;background:'+(v<0?'#ff3266':'#85d65d')+'"></i></div><small>'+(finite(m.extension)?signed(m.extension,2)+'×':'—')+'</small></div></td>';const scoring=['rsMonth','thrust'].includes(k),positive=scoring?v>=50:v>=0,alpha=finite(v)?Math.min(.3,.04+(scoring?Math.abs(v-50)/200:Math.abs(v)/50)):0;return '<td style="color:'+(positive?'#85d65d':'#ff3266')+';background:rgba('+(positive?'133,214,93,':'255,50,102,')+alpha+')">'+(finite(v)?(scoring?fmt(v,0)+'%':value(v)):'—')+'</td>';}).join('')+'</tr>').join('')+'</tbody></table></div></section>';};
 return '<div class="market-flow"><section class="market-chart-grid">'+cards+'</section><div class="market-comparison-grid">'+groupTable('market','Indexes')+groupTable('segments','Market segments')+groupTable('equal_weight','Equal-weight sectors')+groupTable('sectors','SPDR sectors')+groupTable('industries','Industry ETFs')+'</div></div>';
}
let flowDailyCharts=[],flowLightweightPromise;
function loadFlowDailyLibrary(){
 if(window.LightweightCharts)return Promise.resolve();
 return flowLightweightPromise??=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='assets/vendor/lightweight-charts-5.0.9.js';script.onload=resolve;script.onerror=reject;document.head.append(script);});
}
async function mountFlowOverviewCharts(){
 flowDailyCharts.forEach(({chart,observer})=>{observer.disconnect();chart.remove();});flowDailyCharts=[];
 try{await loadFlowDailyLibrary();}catch(error){document.querySelectorAll('[data-market-chart]').forEach(node=>node.textContent='Chart library unavailable');return;}
 const L=window.LightweightCharts;
 document.querySelectorAll('[data-market-chart]').forEach(node=>{
  const m=flowOverviewState?.metrics[node.dataset.marketChart];if(!m?.available){node.textContent='No completed daily bars';return;}
  node.replaceChildren();node.setAttribute('aria-label',node.dataset.marketChart+' daily candles, one month through '+m.date);
  const chart=L.createChart(node,{width:node.clientWidth,height:node.clientHeight,layout:{background:{type:'solid',color:'#202020'},textColor:'#aaa89f',fontSize:10,attributionLogo:true},grid:{vertLines:{color:'#2b2b2b'},horzLines:{color:'#2b2b2b'}},rightPriceScale:{mode:L.PriceScaleMode.Logarithmic,borderVisible:false,scaleMargins:{top:.1,bottom:.08}},timeScale:{borderVisible:false,timeVisible:false,rightOffset:1,fixRightEdge:true},crosshair:{mode:L.CrosshairMode.Normal},handleScroll:{mouseWheel:false,pressedMouseMove:true,horzTouchDrag:true,vertTouchDrag:false},handleScale:{mouseWheel:false,axisPressedMouseMove:true,pinch:true}});
  const candles=chart.addSeries(L.CandlestickSeries,{upColor:'#85d65d',downColor:'#ff3266',borderVisible:false,wickUpColor:'#85d65d',wickDownColor:'#ff3266',priceLineVisible:false});
  candles.setData(m.history.map(r=>({time:r.date,open:r.open,high:r.high,low:r.low,close:r.close})));
  let ema=null;const points=m.history.map(r=>{ema=ema===null?r.close:r.close*.2+ema*.8;return {time:r.date,value:ema};});
  chart.addSeries(L.LineSeries,{color:'#ffffff',lineWidth:1,lastValueVisible:false,priceLineVisible:false,crosshairMarkerVisible:false}).setData(points);
  const end=new Date(m.date+'T12:00:00Z'),start=new Date(end);start.setUTCMonth(start.getUTCMonth()-1);const startDate=start.toISOString().slice(0,10),first=m.history.findIndex(r=>r.date>=startDate);
  const fit=()=>chart.timeScale().setVisibleLogicalRange({from:Math.max(0,first)-.6,to:m.history.length-.2});fit();
  const observer=new ResizeObserver(()=>{if(!node.isConnected){observer.disconnect();return;}chart.resize(node.clientWidth,node.clientHeight);fit();});observer.observe(node);flowDailyCharts.push({chart,observer});
 });
}
function openMarketDetail(symbol,category){
 const m=flowOverviewState?.metrics[symbol];if(!m?.available)return;
 const payload=sectors.holdings?.[symbol]?sectors:themes;
 flowETFState={payload,etf:symbol,group:m.name,members:[],chartSymbol:symbol,market:true,category:category||flowETFState?.category};flowETFDialog();
}
function leadership(){
 return flowMarketOverview();
 if(leadershipKind==='indexes')return flowIndexPane();
  const payload=leadershipKind==='sectors'?sectors:themes;
  const etf=etfSnapshot(payload), key=flowFrameKey[flowFrame], groups=buildFlowGroups(payload,etf,key);
  const snapshots=payload.snapshots?.filter(snapshot=>snapshot.date<=etf?.date)||[];
  const previous=snapshots.at(-6), previousRanks=previous?flowRanks(payload,previous,key):new Map();
  const labels={themes:'Themes',sectors:'Sectors',indexes:'Indexes'};
  const top=groups[0];
  if(!flowSelection||!groups.some(group=>group.group===flowSelection))flowSelection=top?.group||'';
  const selectedGroup=groups.find(group=>group.group===flowSelection);
  const extensionMode=flowMode==='extension';

  const flowHorizons=[['1d','1D','Session'],['1w','1W','Fast'],['1m','1M','Swing'],['3m','3M','Trend'],['6m','6M','Cycle'],['1y','1Y','Long']];
  const flowHorizon='<div class="horizon"><span class="horizon-label">Map view</span><div class="segments" aria-label="Map view">'+flowHorizons.map(([id,label,role])=>'<button data-flow-frame="'+id+'" class="'+(!extensionMode&&flowFrame===id?'active':'')+'"><b>'+label+'</b><small>'+role+'</small></button>').join('')+'<span class="flow-mode-divider" aria-hidden="true"></span><button data-flow-mode="extension" class="flow-extension-button '+(extensionMode?'active':'')+'"><b>Extension</b><small>50D SMA</small></button></div></div>';
  const pageTitle=extensionMode?'50D SMA extension':top?.group||'Leadership map';
  const pageCopy=extensionMode?'Raw ETF extension distribution. This is a separate technical-state view, not a performance timeframe.':'Strongest '+(leadershipKind==='themes'?'theme':'sector')+' in the selected map view.';
  const leaderLimit=leadershipKind==='sectors'?3:5;
  const leaders=groups.slice(0,leaderLimit);
  const ranking=leaders.map(group=>'<button class="flow-rank-item '+(group.group===flowSelection?'active':'')+'" data-flow-group="'+escapeHTML(group.group)+'"><span class="flow-rank-number">'+group.rank+'</span><b>'+escapeHTML(group.group)+'</b><strong class="'+returnTone(group.performance)+'">'+pct(group.performance)+'</strong><span class="flow-rank-bar"><i style="width:'+Math.min(100,Math.abs(group.performance)/Math.max(...groups.map(g=>Math.abs(g.performance)),1)*100)+'%;background:'+(group.performance>=0?'#85d65d':'#ff3266')+'"></i></span></button>').join('');
  const selected=selectedGroup?'<div class="flow-selected-summary"><div><b>'+escapeHTML(selectedGroup.group)+'</b><span class="'+returnTone(selectedGroup.performance)+'">'+pct(selectedGroup.performance)+'</span></div><div class="flow-etf-chips">'+selectedGroup.members.map(row=>'<button data-flow-etf="'+escapeHTML(row.symbol)+'" data-flow-group="'+escapeHTML(selectedGroup.group)+'">'+escapeHTML(row.symbol)+' <span class="'+returnTone(row[key])+'">'+pct(row[key])+'</span></button>').join('')+'</div></div>':'';
  const metrics=flowMapMetrics(groups,key);
  const extremes='';
  return '<div class="flow-console"><div class="flow-console-top"><section class="flow-console-leaders"><div class="flow-console-tabs"><div class="segments">'+['themes','sectors','indexes'].map(k=>'<button data-leadership="'+k+'" class="'+(leadershipKind===k?'active':'')+'">'+labels[k]+'</button>').join('')+'</div><small>Top '+leaderLimit+' · '+flowLabels[key]+'</small></div><div class="flow-leader-list">'+ranking+'</div>'+selected+extremes+'</section><section class="flow-console-chart"><div class="flow-console-chartbar">'+flowHorizon+'</div>'+(extensionMode?flowExtensionMap(payload,etf):flowMap(groups,key))+'</section></div>'+flowTable(groups,key,previousRanks)+'</div>';

}
function arrangeBreadthDashboard(){
 const page=document.querySelector('.bm-redesign');if(!page)return;
 page.classList.add('bm-workstation');
 const original=page.querySelector('.bm-main-grid'),rows=[...original.querySelectorAll('.bm-chart-row')];
 const stack=document.createElement('section');stack.className='bm-history-stack';
 [rows[0],rows[1],rows[3],rows[4],rows[2]].forEach(row=>stack.append(row));
 original.replaceWith(stack);
 const trend=page.querySelector('.bm-trend-grid');trend.querySelectorAll('.bm-trend-card').forEach(card=>stack.append(card));
 trend.remove();page.querySelector('.bm-trend-head').remove();
 const definitions=[['Daily 4% moves','up4','down4'],['Quarterly 25%','up25q','down25q'],['34-session 13%','up13d34','down13d34'],['Monthly 25%','up25m','down25m'],['Monthly 50%','up50m','down50m']];
 const board=document.createElement('section');board.className='bm-comparison';
 board.innerHTML='<div class="bm-board-head"><b>Participation balance</b><small>Counts · historical rank · share of qualifying moves</small></div><div class="bm-board-columns"><span>Measure</span><span>Upside</span><span>Downside</span><span>Balance</span><span>Recent history</span></div>';
 definitions.forEach(([label,up,down],i)=>{
 const row=document.createElement('button');row.className='bm-balance-row';
 row.innerHTML='<b>'+label+'</b><span class="positive" data-board-up="'+up+'"></span><span class="negative" data-board-down="'+down+'"></span><span class="bm-balance-track"><i></i><em></em></span><span>'+breadthTape(breadthHoverRows,[up,down],['#85d65d','#ff3266'])+'</span>';
 row.onclick=()=> (i===0?rows[3]:stack.querySelectorAll('.bm-trend-card')[i-1]).scrollIntoView({behavior:'smooth',block:'center'});
 board.append(row);
 });
 page.querySelector('.bm-compact-header').after(board);
 let boardDate='';
 const updateBoard=index=>{
 const r=index>=0?breadthHoverRows[index]:breadthHoverLatest;if(boardDate===r.date)return;boardDate=r.date;
 const past=breadth.filter(x=>x.date<=r.date);
 definitions.forEach(([,up,down])=>{
 const u=finite(r[up])?Number(r[up]):null,d=finite(r[down])?Number(r[down]):null;
 const rank=k=>breadthPercentile(past,k,r[k]);
 const ordinal=v=>{if(v===null)return 'Unavailable';const n=Math.round(v),suffix=n%100>=11&&n%100<=13?'th':({1:'st',2:'nd',3:'rd'}[n%10]||'th');return n+suffix+' percentile';};
 const el=board.querySelector('[data-board-up="'+up+'"]');
 el.innerHTML=fmt(u,0);
 el.nextElementSibling.innerHTML=fmt(d,0);
 const track=el.parentElement.querySelector('.bm-balance-track');
 track.children[0].style.width=(u!==null&&d!==null&&u+d?100*u/(u+d):50)+'%';track.children[1].style.flex='1';
 [up,down].forEach((k,j)=>{const v=rank(k);track.children[j].style.opacity=v===null?.15:.25+.75*v/100;});
 track.title=u===null||d===null?'Missing reading':Math.round(100*u/(u+d||1))+'% upside share of qualifying moves';
 });
 };
 page._updateBoard=updateBoard;updateBoard(-1);
 const history=breadth.filter(r=>r.date<=breadthHoverLatest.date).sort((a,b)=>a.date.localeCompare(b.date));
 const tips=['S&P 500 daily close; change compares with the previous available session.','ATR distance from the 50-day average. Score is its historical normalized value from −1 to +1.','Stocks rising or falling at least 4% in one session.','Upside events divided by downside events over five and ten sessions. Above 1 means upside events dominate.','T2108: percentage of stocks above their 40-day moving average.'];
 [rows[0],rows[1],rows[3],rows[4],rows[2]].forEach((row,i)=>{const info=document.createElement('button');info.className='bm-info';info.textContent='Definition ⓘ';info.setAttribute('aria-expanded','false');const copy=document.createElement('p');copy.className='bm-definition';copy.hidden=true;copy.textContent=tips[i];info.onclick=()=>{copy.hidden=!copy.hidden;info.setAttribute('aria-expanded',String(!copy.hidden));};row.querySelector('.bm-chart-label').append(info,copy);});
 const details=page.querySelector('.bm-details');
 const tools=document.createElement('div');tools.className='bm-reading-tools';tools.innerHTML='<input type="search" placeholder="Filter readings by date" aria-label="Filter readings by date"><button>Export CSV</button>';
 details.querySelector('.table-box').before(tools);
 tools.querySelector('input').oninput=event=>details.querySelectorAll('tbody tr').forEach(tr=>tr.hidden=!tr.cells[0].textContent.includes(event.target.value));
 tools.querySelector('button').onclick=()=>{const table=details.querySelector('table');const csv=[...table.rows].filter(r=>!r.hidden).map(r=>[...r.cells].map(c=>'"'+c.textContent.replaceAll('"','""')+'"').join(',')).join('\n');const a=document.createElement('a');a.href=URL.createObjectURL(new Blob([csv],{type:'text/csv'}));a.download='breadth-'+breadthHoverLatest.date+'.csv';a.click();URL.revokeObjectURL(a.href);};

 const legend=document.createElement('p');legend.className='bm-board-legend';legend.textContent='Bar length: share of qualifying upside/downside moves. Brightness: historical rarity of each count. These are not percentages of all stocks.';board.append(legend);
 const unpin=document.createElement('button');unpin.dataset.bmUnpin='';unpin.textContent='Unpin';unpin.hidden=true;unpin.onclick=()=>{breadthPinned=-1;setBreadthHover(-1);};page.querySelector('[data-bm-date]').after(unpin);
 const freshness=document.createElement('small');freshness.className='bm-data-dates';freshness.textContent='Latest available · Breadth '+breadth.map(r=>r.date).sort().at(-1);page.querySelector('.bm-compact-header').after(freshness);
 const dates=breadth.map(r=>r.date).sort();
 const controls=document.createElement('span');controls.className='bm-date-controls';
 controls.innerHTML='<button aria-label="Previous session">←</button><button aria-label="Next session">→</button><button>Latest</button>';
 controls.querySelectorAll('button').forEach((button,i)=>button.onclick=()=>{breadthPinned=-1;const at=dates.indexOf(breadthHoverLatest.date);breadthDate=i===2?'':dates[Math.max(0,Math.min(dates.length-1,at+(i===0?-1:1)))];render();});
 page.querySelector('[data-breadth-date]').parentElement.after(controls);
 document.onkeydown=event=>{if(event.key==='Escape'&&document.querySelector('.bm-workstation')){breadthPinned=-1;setBreadthHover(-1);}};
 page.classList.add('bm-console');
 board.querySelector('.bm-board-columns').lastElementChild.remove();
 board.querySelectorAll('.bm-balance-row').forEach(row=>row.lastElementChild.remove());
 board.querySelector('.bm-board-head small').textContent='Counts · historical percentile';
 legend.textContent='Width = upside/downside balance · brightness = historical rarity';
 const layout=document.createElement('div');layout.className='bm-console-layout';board.before(layout);layout.append(board);
 const workspace=document.createElement('section');workspace.className='bm-explorer';layout.append(workspace);
 const nav=document.createElement('div');nav.className='bm-explorer-nav';nav.setAttribute('aria-label','Historical measure');
 const canvas=document.createElement('div');canvas.className='bm-explorer-canvas';workspace.append(canvas);
 const entries=[['Daily 4% moves',rows[3]],...Array.from(stack.querySelectorAll('.bm-trend-card')).map((card,i)=>[definitions[i+1][0],card])];
 const descriptions={'Daily 4% moves':'Stocks rising or falling at least 4% in one session.','Quarterly 25%':'Stocks at least 25% above their lowest close or below their highest close over 65 sessions.','34-session 13%':'Stocks at least 13% above their lowest close or below their highest close over 34 sessions.','Monthly 25%':'Stocks gaining or losing at least 25% over 20 sessions.','Monthly 50%':'Stocks gaining or losing at least 50% over 20 sessions.','5D ratio':'Upside 4% events divided by downside 4% events over five sessions. Above 1 means more upside events.','10D ratio':'Upside 4% events divided by downside 4% events over ten sessions. Above 1 means more upside events.','Above 40D':'Percentage of stocks above their 40-day moving average.','SPX':'S&P 500 daily close. Balance shows its 50-day ATR-extension index using all available prior SPX history: −1 is the deeply negative tail, 0 is the 50-day average, +1 is the strongly positive tail.','Universe':'Number of stocks tracked in the breadth universe for the selected session.'};
 const explanation=document.createElement('p');explanation.className='bm-active-description';board.append(explanation);
 const show=name=>{if(page.dataset.activeMeasure===name)return;page.dataset.activeMeasure=name;breadthSelected=name;explanation.textContent=descriptions[name]||'';entries.forEach(([label,node])=>{node.hidden=label!==name;if(label===name){const controls=workspace.querySelector('.bm-chart-ranges');if(controls)node.querySelector('.bm-chart-label')?.append(controls);}});nav.querySelectorAll('button').forEach(button=>{const active=button.textContent===name;button.classList.toggle('active',active);button.setAttribute('aria-pressed',String(active));});board.querySelectorAll('.bm-balance-row').forEach((row,i)=>{const active=(row.dataset.measure||definitions[i]?.[0])===name;row.classList.toggle('selected',active);if(active)row.after(explanation);});page._refreshActiveChart?.();requestAnimationFrame(()=>resizeCharts());};
 entries.forEach(([name,node])=>{const measure=definitions.find(([label])=>label===name);if(measure&&name!=='Daily 4% moves'){const svg=node.querySelector('.bm-tape');if(svg)svg.outerHTML=breadthTape(breadthHoverRows,measure.slice(1),['#85d65d','#ff3266'],'bars');}node.querySelectorAll('.bm-rank-history').forEach(strip=>strip.remove());canvas.append(node);const button=document.createElement('button');button.textContent=name;button.onclick=()=>show(name);nav.append(button);});
 const singles=[['5D ratio','ratio5',2,'×','#e9c46a'],['10D ratio','ratio10',2,'×','#6aa9ff'],['Above 40D','t2108',1,'%','#86d65d'],['SPX','sp',2,'','#f5f2e8']];
 singles.forEach(([name,key,decimals,suffix,color])=>{
 const row=document.createElement('button');row.className='bm-balance-row bm-single-row';row.dataset.measure=name;row.innerHTML='<b>'+name+'</b><span class="bm-hover-key" data-bm-key="'+key+'" data-bm-label="" data-bm-decimals="'+decimals+'" data-bm-suffix="'+suffix+'" style="color:'+color+'"></span><span class="bm-range-balance" data-range-key="'+key+'"><span class="bm-range-rail"><i></i><em></em></span><span class="bm-range-ends"><small></small><small></small></span></span>';board.insertBefore(row,legend);
 const node=document.createElement('div');node.className='bm-chart-row';node.innerHTML='<div class="bm-chart-label"><b>'+name+'</b><span class="bm-hover-key" data-bm-key="'+key+'" data-bm-label="" data-bm-decimals="'+decimals+'" data-bm-suffix="'+suffix+'" style="color:'+color+'"></span></div>'+breadthTape(breadthHoverRows,[key],['#f5f2e8'],'line',key.startsWith('ratio')?1:key==='t2108'?[{value:20,label:'20%'},{value:80,label:'80%'}]:null);if(key==='sp'){const perf=document.createElement('span');perf.dataset.spxPerformance='';perf.className='bm-spx-performance';node.querySelector('.bm-chart-label').append(perf);}canvas.append(node);entries.push([name,node]);
 });
 entries.forEach(([name,node])=>{node.querySelectorAll(':scope > h3').forEach(heading=>heading.remove());const label=node.querySelector('.bm-chart-label');let heading=label.querySelector(':scope > b');if(!heading){heading=document.createElement('b');label.prepend(heading);}heading.textContent=name;});
 stack.remove();board.querySelectorAll('.bm-balance-row').forEach((row,i)=>row.onclick=()=>show(row.dataset.measure||definitions[i][0]));
 const quick=document.createElement('div');quick.className='bm-quick-readings';
 [['ratio5','5D pressure',2,'×'],['ratio10','10D pressure',2,'×'],['t2108','Above 40D',1,'%']].forEach(([key,label,decimals,suffix])=>{const box=document.createElement('div');box.innerHTML='<span class="bm-hover-key" data-bm-key="'+key+'" data-bm-label="'+label+'" data-bm-decimals="'+decimals+'" data-bm-suffix="'+suffix+'"></span>';box.tabIndex=0;box.setAttribute('role','button');box.setAttribute('aria-label','View '+label+' history');const choose=()=>show(key==='t2108'?'T2108':'Pressure');box.onclick=choose;box.onkeydown=event=>{if(event.key==='Enter'||event.key===' '){event.preventDefault();choose();}};quick.append(box);});
 const columns=[['date','Date'],['up4','Up'],['down4','Down'],['ratio5','5D'],['ratio10','10D'],['up25q','Up'],['down25q','Down'],['up25m','Up'],['down25m','Down'],['up50m','Up'],['down50m','Down'],['up13d34','Up'],['down13d34','Down'],['t2108','T2108'],['sp','SPX']];
 details.open=true;details.classList.add('bm-stockbee-table');details.querySelector('summary').remove();
 const table=details.querySelector('table');
 table.innerHTML='<thead><tr class="bm-table-groups"><th rowspan="2">Date</th><th colspan="2">Daily ±4%</th><th colspan="2">Up / down ratio</th><th colspan="2">Quarter ±25%</th><th colspan="2">Month ±25%</th><th colspan="2">Month ±50%</th><th colspan="2">34D ±13%</th><th rowspan="2">Above 40D</th><th rowspan="2">SPX</th></tr><tr>'+columns.slice(1,13).map(([,label])=>'<th>'+label+'</th>').join('')+'</tr></thead>';
 const body=document.createElement('tbody');table.append(body);
 let tableVisibleCount=120;
 const drawTable=(query,append=false)=>{const all=history.filter(r=>r.date.includes(query)).toReversed(),selected=all.slice(append?tableVisibleCount-120:0,tableVisibleCount);const html=selected.map(r=>'<tr>'+columns.map(([key])=>{if(key==='date')return '<td><button class="bm-table-date" data-table-date="'+r.date+'">'+r.date+'</button></td>';const value=r[key],cls=key==='sp'?'':stockbeeColor(r,key),reason='Stockbee sheet color convention';const daily=key==='sp'?breadthSPXChange(r.date):null;const spStyle=key==='sp'&&daily!==null&&daily!==0?' style="color:'+(daily>0?'#85d65d':'#ff3266')+';background:rgba('+(daily>0?'133,214,93':'255,50,102')+','+(0.06+0.44*Math.min(1,Math.abs(daily)/3)).toFixed(3)+')"':'';return '<td tabindex="0" role="button" data-reading-date="'+r.date+'" data-reading-key="'+key+'" class="'+cls+'"'+spStyle+' aria-label="Select '+r.date+' '+key+'">'+fmt(value,key.startsWith('ratio')?2:key==='t2108'?1:key==='sp'?2:0)+(key==='t2108'&&finite(value)?'%':'')+(key==='sp'&&finite(value)?breadthSPXChangeLabel(r.date):'')+'</td>';}).join('')+'</tr>').join('');if(append)body.insertAdjacentHTML('beforeend',html);else body.innerHTML=html;};
 drawTable('');tools.querySelector('input').oninput=event=>{tableVisibleCount=120;drawTable(event.target.value);};const tableViewport=details.querySelector('.table-box');tableViewport.addEventListener('scroll',()=>{if(tableViewport.scrollTop+tableViewport.clientHeight>=tableViewport.scrollHeight-250&&tableVisibleCount<history.length){tableVisibleCount+=120;drawTable('',true);}},{passive:true});
 const title=document.createElement('div');title.className='bm-table-title';title.innerHTML='<h3>Stockbee Market Monitor</h3><small>Counts: highlight at historical percentile ≥90 · ratios: green above 1, pink below 1 · T2108: 20 / 80 zones. Colors are dashboard rules, not copied sheet formatting.</small>';const permanent=document.createElement('section');permanent.className=details.className;details.querySelectorAll('.bm-table-title,.bm-reading-tools').forEach(node=>node.remove());tools.remove();while(details.firstChild)permanent.append(details.firstChild);details.replaceWith(permanent);page.append(permanent);
 show(entries.some(([name])=>name===breadthSelected)?breadthSelected:'Daily 4% moves');
 const keyMeasures={up4:'Daily 4% moves',down4:'Daily 4% moves',up25q:'Quarterly 25%',down25q:'Quarterly 25%',up13d34:'34-session 13%',down13d34:'34-session 13%',up25m:'Monthly 25%',down25m:'Monthly 25%',up50m:'Monthly 50%',down50m:'Monthly 50%',ratio5:'5D ratio',ratio10:'10D ratio',t2108:'Above 40D',sp:'SPX'};
 page._selectReading=(date,key)=>{
 const reading=history.find(r=>r.date===date);if(!reading)return;
 breadthDate=date;breadthHoverLatest=reading;breadthPinned=-1;
 document.querySelector('[data-breadth-date]').value=date;
 show(keyMeasures[key]||breadthSelected);
 page._setWindow(breadthWindow);
 body.querySelectorAll('.bm-selected-date,.bm-selected-cell').forEach(cell=>cell.classList.remove('bm-selected-date','bm-selected-cell'));
 body.querySelectorAll('[data-reading-date="'+date+'"]').forEach(cell=>{cell.parentElement.classList.add('bm-selected-date');if(cell.dataset.readingKey===key||(keyMeasures[key]&&keyMeasures[cell.dataset.readingKey]===keyMeasures[key]))cell.classList.add('bm-selected-cell');});
 layout.scrollIntoView({behavior:'smooth',block:'start'});
 };
 const previewPair=cell=>{body.querySelectorAll('.bm-pair-hover').forEach(node=>node.classList.remove('bm-pair-hover'));if(!cell)return;const measure=keyMeasures[cell.dataset.readingKey];[...cell.parentElement.querySelectorAll('[data-reading-key]')].filter(node=>keyMeasures[node.dataset.readingKey]===measure).forEach(node=>node.classList.add('bm-pair-hover'));};
 body.addEventListener('pointerover',event=>previewPair(event.target.closest('[data-reading-key]')));
 body.addEventListener('pointerleave',()=>previewPair(null));
 body.addEventListener('focusin',event=>previewPair(event.target.closest('[data-reading-key]')));
 body.addEventListener('click',event=>{const dateButton=event.target.closest('[data-table-date]');if(dateButton){page._selectReading(dateButton.dataset.tableDate);return;}const cell=event.target.closest('[data-reading-key]');if(cell)page._selectReading(cell.dataset.readingDate,cell.dataset.readingKey);});
 body.addEventListener('keydown',event=>{const cell=event.target.closest('[data-reading-key]');if(cell&&(event.key==='Enter'||event.key===' ')){event.preventDefault();page._selectReading(cell.dataset.readingDate,cell.dataset.readingKey);}});
 const resizeCharts=()=>page.querySelectorAll('.bm-tape').forEach(svg=>{const box=svg.getBoundingClientRect();if(!box.width||!box.height)return;svg.querySelectorAll('text').forEach(text=>{text.style.transformBox='fill-box';text.style.transformOrigin='center';const transform='scale('+(1000/box.width)+','+(svg.viewBox.baseVal.height/box.height)+')';if(text.style.transform!==transform)text.style.transform=transform;});});
 entries.forEach(([,node])=>{node.dataset.chartStamp=breadthHoverLatest.date+':'+breadthWindow;node._chartCache=new Map();const svg=node.querySelector('svg.bm-tape');if(svg)node._chartCache.set(node.dataset.chartStamp,svg.outerHTML);});
 page._refreshActiveChart=()=>{
 const active=entries.find(([name])=>name===breadthSelected)?.[1];if(!active)return;
 const stamp=breadthHoverLatest.date+':'+breadthWindow;if(active.dataset.chartStamp===stamp)return;
 const svg=active.querySelector('svg.bm-tape');if(!svg)return;
 const spec=JSON.parse(svg.dataset.series);const cache=active._chartCache||(active._chartCache=new Map());if(!cache.has(stamp)){cache.set(stamp,breadthTape(breadthHoverRows,spec.keys,spec.colors,spec.kind,spec.reference));if(cache.size>12)cache.delete(cache.keys().next().value);}svg.outerHTML=cache.get(stamp).replace(/ data-hover-bound="[^"]*"/g,'');active.dataset.chartStamp=stamp;bindBreadthHover();
 };
 page._setWindow=n=>{
 if(n===breadthWindow&&breadthHoverRows.at(-1)?.date===breadthHoverLatest.date)return;
 breadthPinned=-1;breadthWindow=n;breadthHoverRows=history.filter(r=>r.date<=breadthHoverLatest.date).slice(-n);
 page._refreshActiveChart();
 page.querySelectorAll('[data-action="breadth-window"]').forEach(button=>button.classList.toggle('active',Number(button.dataset.window)===n));

 setBreadthHover(-1);bindBreadthHover();requestAnimationFrame(resizeCharts);
 };
 requestAnimationFrame(resizeCharts);const observer=new ResizeObserver(resizeCharts);observer.observe(page);page._chartObserver=observer;
 page.querySelectorAll('[data-bm-percentile],.bm-info,.bm-definition').forEach(node=>node.remove());
 const range=page.querySelector('.bm-compact-header .segments');range.classList.add('bm-chart-ranges');range.setAttribute('aria-label','Chart range');(entries.find(([name])=>name===breadthSelected)?.[1].querySelector('.bm-chart-label')||workspace).append(range);
}

function cotCrowding(row,window=cotWindow){
 const large=row?.participants?.large?.indices?.[window],commercials=row?.participants?.commercials?.indices?.[window];
 if(!finite(large)||!finite(commercials))return null;
 if(large>90&&commercials<5)return {label:'Crowded Long',tone:'negative'};
 if(large<10&&commercials>95)return {label:'Crowded Short',tone:'positive'};
 return null;
}
function positioning(){
  if(!cot.markets?.length)return '<p class="empty">CFTC positioning is unavailable.</p>';
  const participants=[['large','Large specs','#00bcd4'],['small','Small specs','#ff9800'],['commercials','Commercials','#e040fb']];
  const labels={"1y":"1 year","3y":"3 years","5y":"5 years"};
  const index=(key,row)=>row?.participants?.[key]?.indices?.[cotWindow]??null;
  const extreme=v=>finite(v)&&(Number(v)<=5||Number(v)>=95);
  const markets=cot.markets.map(m=>{const history=cotHistory(m);return {...m,history,last:history.at(-1),prior:history.at(-2)};}).filter(m=>m.last).sort((a,b)=>{
    const score=m=>{const v=index('large',m.last);return finite(v)?Number(v):-1;};
    const groupOrder={'Equity index':0,'Crypto':1,'Metals':2,'Energy':3};
    return (groupOrder[a.group]??3)-(groupOrder[b.group]??3)||score(b)-score(a)||a.name.localeCompare(b.name);
  });
  // The framework is deliberately based on large-spec extremes. Small specs and
  // commercials remain context, rather than independent directional signals.
  const watches=markets.filter(m=>cotCrowding(m.last));
  const latest=markets.map(m=>m.last?.date).filter(Boolean).sort().at(-1);
  const meter=(m,k,label,color)=>{
    const v=index(k,m.last),prev=index(k,m.prior),valid=finite(v),delta=valid&&finite(prev)?Number(v)-Number(prev):null;
    const state=!valid?'Insufficient history':v<=5?'Near range low':v>=95?'Near range high':'Within range';
    return '<div class="cot-participant" style="--party-color:'+color+'"><div><b>'+label+'</b><strong style="color:'+color+'">'+(valid?fmt(v,1):'—')+'</strong></div><div class="cot-track"><i class="cot-zone low"></i><i class="cot-zone high"></i>'+(valid?'<b style="left:'+Math.max(0,Math.min(100,v))+'%;background:'+color+'"></b>':'')+'</div><div><small>'+state+'</small><small>'+(delta===null?'':signed(delta,1)+' pts this week')+'</small></div></div>';
  };
  const card=m=>{
    const p=m.last?.participants||{},crowding=cotCrowding(m.last),label=crowding?m.name+' is '+crowding.label:'',tone=crowding?.tone||'';
    const chartId='cot-tv-'+m.etf.replace(/[^a-z0-9]/gi,'');
    return '<article id="cot-market-'+escapeHTML(m.code)+'" class="cot-row '+tone+'"><section class="cot-position"><header><div><h3>'+escapeHTML(m.name)+'</h3></div></header>'+(label?'<h4 class="'+tone+'">'+label+'</h4>':'')+participants.map(([k,l,c])=>meter(m,k,l,c)).join('')+'<div class="cot-actuals">'+participants.map(([k,l])=>'<span>'+l+' <b>'+signed(p[k]?.net,0)+'</b><small>'+signed(p[k]?.netPctOI)+'% OI</small></span>').join('')+'</div></section><section class="cot-visual"><div id="'+chartId+'" class="tv-chart cot-tv-chart" data-tv-symbol="'+escapeHTML(m.etf)+'" data-tv-interval="W"><span>Loading weekly chart…</span></div>'+cotSpark(m)+'</section></article>';
  };
  const dates=cotDates(),selected=cotDate||dates.at(-1),at=dates.indexOf(selected);
  return '<div class="cot-controls" data-cot-controls><input type="date" aria-label="COT publication week" data-cot-date value="'+selected+'" min="'+dates[0]+'" max="'+dates.at(-1)+'"><button data-action="cot-prev" aria-label="Previous COT report" '+(at<=0?'disabled':'')+'>←</button><button data-action="cot-next" aria-label="Next COT report" '+(at>=dates.length-1?'disabled':'')+'>→</button><button data-action="cot-latest">Latest</button></div><div class="segments cot-lookbacks" data-cot-lookbacks aria-label="Positioning calculation lookback">'+['1y','3y','5y'].map(k=>'<button data-cot-window="'+k+'" aria-pressed="'+(cotWindow===k)+'" class="'+(cotWindow===k?'active':'')+'">'+k.toUpperCase()+'</button>').join('')+'</div><div class="cot-extreme-links cot-header-alerts" data-cot-alerts>'+watches.map(m=>{const c=cotCrowding(m.last);return '<button class="'+c.tone+'" data-cot-jump="'+escapeHTML(m.code)+'">'+escapeHTML(m.name)+' · '+c.label+'</button>';}).join('')+'</div>'+'<section class="cot-rows">'+markets.map(card).join('')+'</section>';

}
function legacyPositioning(){
  if(!cot.markets?.length)return '<p class="empty">The official CFTC dataset is unavailable. No positioning signal has been inferred.</p>';
  const markets=cot.markets.map(m=>({...m,last:m.history.at(-1)}));
  const extremes=markets.filter(m=>{const i=m.last?.participants?.large?.index;return i!==null&&(i<=5||i>=95);});
  return '<section class="page-lead"><div><span class="eyebrow">CROWDED MARKET · OFFICIAL CFTC LEGACY FUTURES</span><h2>'+extremes.length+' crowding watch'+(extremes.length===1?'':'es')+' across '+markets.length+' markets</h2><p>Positioning is a context layer: it can identify one-sided setups worth watching, but price still supplies the trigger.</p></div><div class="source-stamp"><b>Latest report</b><span>'+escapeHTML(cot.fetchedAt?.slice(0,10)||'Unavailable')+'</span><small>Tuesday positions, generally released Friday</small></div></section><section class="crowding-primer"><div><i>①</i><b>Find the extreme</b><span>Near 0 = range low. Near 100 = range high.</span></div><div><i>②</i><b>Read the crowd</b><span>Large specs are the cleanest attention signal here.</span></div><div><i>③</i><b>Wait for price</b><span>Use the matching ETF only after structure confirms.</span></div></section><section class="crowding-grid">'+markets.map(m=>{
    const last=m.last||{}, large=last.participants?.large||{}, commercial=last.participants?.commercials||{}, small=last.participants?.small||{}, i=large.index;
    const extreme=i!==null&&(i<=5||i>=95), state=i===null?'No history':i<=5?'Large specs near range low':i>=95?'Large specs near range high':'Within normal range';
    const tone=i===null?'gold':i<=5?'positive':i>=95?'negative':'cyan';
    const bias=i===null?'Insufficient data':i<=5?'Potentially washed-out speculative positioning':i>=95?'Potentially crowded speculative positioning':'No large-spec extreme';
    return '<article class="crowding-card '+tone+'"><div class="crowding-head"><div><span>'+escapeHTML(m.group)+'</span><h3>'+escapeHTML(m.name)+'</h3></div><b>'+escapeHTML(m.etf)+'</b></div><div class="crowding-score"><strong>'+fmt(i,0)+'</strong><span>large-spec range index</span></div>'+rangeMeter(i,'Large speculator range index',tone)+'<div class="crowding-state '+tone+'">'+state+'</div><div class="position-row"><span>Commercials <b>'+fmt(commercial.index,0)+'</b></span><span>Small specs <b>'+fmt(small.index,0)+'</b></span></div><p>'+bias+'. '+(m.group==='Crypto'?'Crypto futures can contain hedged exposure; no automatic inverse interpretation is applied.':'')+'</p><details><summary>Open positioning evidence</summary><div class="participant-mini"><span>Large specs <b>'+signed(large.net)+' contracts</b><small>'+signed(large.netPctOI)+'% open interest</small></span><span>Commercials <b>'+signed(commercial.net)+' contracts</b><small>'+signed(commercial.netPctOI)+'% open interest</small></span></div>'+cotSpark(m)+'<p>Index = 100 × (current net − five-year minimum net) / (maximum − minimum). It is a range location—not the percentage short, a probability, or an entry signal. Source contract '+escapeHTML(m.code)+': '+escapeHTML(m.contract)+'. ETF expression: '+escapeHTML(m.etf)+'.</p></details></article>';
  }).join('')+'</section><details class="evidence-drawer"><summary>Methodology and timing</summary><p>Positions are official CFTC Legacy Futures-only data. They represent Tuesday positions, usually released Friday; this page is not tied to the daily stock-session selector. Commercials, large specs, and small/nonreportable positions are calculated from net long minus short. The 5 / 95 thresholds are attention flags, not predictions.</p></details>';
}
function cotSpark(m){
  const keys=[['large','Large specs','#00bcd4'],['commercials','Commercials','#e040fb'],['small','Small specs','#ff9800']];
  const fullHistory=cotHistory(m);
  const history=fullHistory.slice(-52);
  const left=32,right=748,top=2,bottom=213,plot=right-left,step=plot/Math.max(1,history.length-1),bar=Math.max(.6,Math.min(3,step*.23));
  const selected=keys.find(([key])=>key===cotParticipant)||keys[0];
  const start=fullHistory.length-history.length;
  const windows=[[cotWindow,cotPeriods[cotWindow]]];
  const rangeAt=(i,key,length)=>{if(i+1<length)return null;const values=fullHistory.slice(i+1-length,i+1).map(r=>r.participants[key]?.net);if(values.some(v=>!finite(v)))return null;return {low:Math.min(...values),high:Math.max(...values)};};
  const displayed=history.flatMap(row=>keys.map(([key])=>Number(row.participants[key]?.net)));
  windows.filter(([name])=>cotRanges[name]).forEach(([,length])=>history.forEach((row,j)=>{const range=rangeAt(start+j,selected[0],length);if(range)displayed.push(range.low,range.high); }));
  const low=Math.min(0,...displayed),high=Math.max(0,...displayed),padding=Math.max(1,(high-low)*.04);
  const minimum=low-padding,maximum=high+padding,scale=(bottom-top)/(maximum-minimum),y=value=>top+(maximum-value)*scale,zero=y(0);
  const path=(length,edge)=>{let d='';history.forEach((row,j)=>{const range=rangeAt(start+j,selected[0],length);if(!range){d='';return;}const point=(left+j*step).toFixed(1)+' '+y(range[edge]).toFixed(1);d+=(d?' L':'M')+point;});return d;};
  const overlays=cotParticipant==='all'?'':windows.filter(([name])=>cotRanges[name]).map(([name,length])=>['high','low'].map(edge=>'<path d="'+path(length,edge)+'" fill="none" stroke="'+selected[2]+'" opacity="'+(name==='3y'?.72:.38)+'" stroke-width="'+(name==='3y'?1.5:1)+'" stroke-dasharray="'+(name==='3y'?'':'4 4')+'"/>').join('')).join('');
  const bars=history.map((row,j)=>keys.map(([key,,color],offset)=>{const net=Number(row.participants[key]?.net)||0,x=left+j*step+(offset-1)*(bar+.25),h=Math.abs(net)*scale;return '<rect x="'+x.toFixed(1)+'" y="'+(net>=0?y(net):zero).toFixed(1)+'" width="'+bar+'" height="'+h.toFixed(1)+'" fill="'+color+'" opacity="'+(cotParticipant==='all'||key===cotParticipant?1:.24)+'"/>';}).join('')).join('');
  const participantButtons='<button type="button" data-cot-participant="all" class="'+(cotParticipant==='all'?'active':'')+'">All</button>'+keys.map(([key,label,color])=>'<button type="button" data-cot-participant="'+key+'" class="'+(key===cotParticipant?'active':'')+'" style="--participant-color:'+color+'">'+label+'</button>').join('');
  const rangeButtons=windows.map(([name])=>'<button type="button" data-cot-range="'+name+'" class="'+(cotRanges[name]?'active':'')+'">'+name.toUpperCase()+' range</button>').join('');
  const latest=history.at(-1),latestNet=latest?.participants[selected[0]]?.net;
  return '<section class="cot-bars"><div class="cot-bars-head"><div><b>Net positioning</b><small>Last year displayed · '+cotWindow.toUpperCase()+' calculation lookback</small></div></div><div class="cot-hover-read" data-cot-read="'+escapeHTML(m.code)+'">'+escapeHTML(latest?.date||'')+' · '+selected[1]+' '+signed(latestNet,0)+' contracts</div><svg viewBox="0 0 780 215" preserveAspectRatio="none" role="img" aria-label="Weekly net positions and rolling five-year boundaries" data-cot-chart="'+escapeHTML(m.code)+'"><path d="M'+left+' '+top+'H'+right+' M'+left+' '+zero+'H'+right+' M'+left+' '+bottom+'H'+right+'" stroke="#383838"/>'+overlays+'<path d="M'+left+' '+zero+'H'+right+'" stroke="#aaa89f"/>'+bars+'<line class="cot-hover-line" x1="0" x2="0" y1="'+top+'" y2="'+bottom+'" stroke="#f5f2e8" opacity="0"/><rect x="'+left+'" y="'+top+'" width="'+plot+'" height="'+(bottom-top)+'" fill="transparent" pointer-events="all"/></svg><div class="cot-chart-dates"><span>'+escapeHTML(history[0]?.date||'')+'</span><span>'+escapeHTML(latest?.date||'')+'</span></div></section>';
}
function filteredKKStocks(){
  const rows=stocks('kk').filter(r=>
    (!filters.search || (r.symbol+' '+r.description+' '+tag(r)).toLowerCase().includes(filters.search.toLowerCase())) &&
    (!filters.group||tag(r)===filters.group) &&
    finite(r.adr) && r.adr>=Number(filters.adr) &&
    (filters.extension==='' || (finite(r.extension)&&r.extension<Number(filters.extension))) &&
    (!filters.above9d || r.above9d) && (!filters.above9w || r.above9w) &&
    (!filters.above9m || r.above9m) &&
    (!filters.liquid || (r.dollarVolume>=100e6 && r.shareVolume>=1e6)) &&
    (!filters.superLiquid || r.dollarVolume>=500e6) &&
    (!filters.tight || r.tight)
  );
  const value=(row,key)=>{
    if(key==='stock') return row.symbol;
    if(key==='theme') return tag(row);
    if(key==='strength') return Math.max(row.performance['1m']??-Infinity,row.performance['3m']??-Infinity,row.performance['6m']??-Infinity);
    if(['1m','3m','6m'].includes(key)) return row.performance[key]??-Infinity;
    if(['above9d','above9w','above9m'].includes(key)) return Number(Boolean(row[key]));
    if(key==='extension') return row.extension??Infinity;
    if(key==='dollarVolume') return row.dollarVolume??-Infinity;
    return row.adr??-Infinity;
  };
  return rows.sort((a,b)=>{
    const left=value(a,kkSort.key), right=value(b,kkSort.key);
    const compared=typeof left==='string' ? left.localeCompare(right) : left-right;
    return (kkSort.direction==='asc'?1:-1)*compared || a.symbol.localeCompare(b.symbol);
  });
}
function selectFilter(key,label,options){return '<label>'+label+'<select data-filter="'+key+'">'+options.map(([v,t])=>'<option value="'+escapeHTML(v)+'" '+(filters[key]===v?'selected':'')+'>'+escapeHTML(t)+'</option>').join('')+'</select></label>';}
function kkToggle(label,key){return '<button data-action="kk-toggle" data-toggle="'+key+'" class="'+(filters[key]?'active':'')+'">'+label+'</button>';}
function screenerDisplayControl(){return '<div class="view-switch"><span class="horizon-label">View</span><div class="segments"><button data-action="screener-view" data-view="list" class="'+(screenerDisplay==='list'?'active':'')+'">List</button><button data-action="screener-view" data-view="charts" class="'+(screenerDisplay==='charts'?'active':'')+'">Charts</button></div></div>';}
function chartStats(row,kind){
  const windows=kind==='obc'?[['1Y',row.performance['1y']],['3M',row.performance['3m']]]:[['1M',row.performance['1m']],['3M',row.performance['3m']],['6M',row.performance['6m']]];
  return windows.map(([label,value])=>'<span>'+label+' <b class="'+returnTone(value)+'">'+pct(value)+'</b></span>').join('')+'<span>EXT <b class="'+extensionTone(row.extension)+'">'+fmt(row.extension,2)+'×</b></span>';
}
function chartGrid(rows,kind){
  if(!rows.length)return '<p class="empty">No candidates match these filters.</p>';
  return '<div class="chart-grid">'+rows.map((row,index)=>{
    const id='tv-'+kind+'-'+row.symbol.replace(/[^a-z0-9]/gi,'')+'-'+index;
    return '<article class="chart-card"><div class="chart-card-head"><div><button data-stock="'+escapeHTML(row.symbol)+'" data-kind="'+kind+'">'+escapeHTML(row.symbol)+'</button><small>'+escapeHTML(tag(row))+'</small></div><div class="chart-stats">'+chartStats(row,kind)+'</div></div><div id="'+id+'" class="tv-chart" data-tv-symbol="'+escapeHTML(row.symbol)+'" aria-label="Daily chart for '+escapeHTML(row.symbol)+'"><span>Loading daily chart…</span></div></article>';
  }).join('')+'</div>';
}
function loadTradingView(){
  if(window.TradingView)return Promise.resolve();
  if(tvScriptPromise)return tvScriptPromise;
  tvScriptPromise=new Promise((resolve,reject)=>{const script=document.createElement('script');script.src='https://s3.tradingview.com/tv.js';script.async=true;script.onload=resolve;script.onerror=reject;document.head.appendChild(script);});
  return tvScriptPromise;
}
function mountTradingViewCharts(){
  if(tvObserver){tvObserver.disconnect();tvObserver=null;}
  const nodes=[...document.querySelectorAll('[data-tv-symbol]')];
  if(!nodes.length)return;
  const mount=async node=>{
    if(node.dataset.tvMounted)return;
    node.dataset.tvMounted='true';
    try{
      await loadTradingView();
      if(!document.body.contains(node))return;
      node.textContent='';
      new TradingView.widget({container_id:node.id,symbol:node.dataset.tvSymbol,interval:node.dataset.tvInterval||'D',timezone:'America/New_York',theme:'dark',style:'1',locale:'en',toolbar_bg:'#202020',backgroundColor:'#202020',gridColor:'#343434',hide_top_toolbar:true,hide_side_toolbar:true,allow_symbol_change:false,enable_publishing:false,save_image:false,withdateranges:false,autosize:true,studies:['STD;EMA'],studies_overrides:{'moving average exponential.ma.color':'#FFFFFF','moving average exponential.ma.linewidth':2,'volume.volume.transparency':100,'volume.volume ma.transparency':100,'moving average exponential.length':9,'moving average exponential.plot.color':'#FFFFFF','moving average exponential.plot.linewidth':2},overrides:{'paneProperties.backgroundType':'solid','paneProperties.background':'#202020','scalesProperties.showStudyLastValue':false,'mainSeriesProperties.priceAxisProperties.log':true,'mainSeriesProperties.priceAxisProperties.percentage':false,'mainSeriesProperties.candleStyle.upColor':'#85d65d','mainSeriesProperties.candleStyle.downColor':'#ff3266','mainSeriesProperties.candleStyle.borderUpColor':'#85d65d','mainSeriesProperties.candleStyle.borderDownColor':'#ff3266','mainSeriesProperties.candleStyle.wickUpColor':'#85d65d','mainSeriesProperties.candleStyle.wickDownColor':'#ff3266'}});
    }catch(error){node.innerHTML='<span class="chart-unavailable">Chart unavailable · <a target="_blank" rel="noopener" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(node.dataset.tvSymbol)+'">open in TradingView ↗</a></span>';}
  };
  if(!('IntersectionObserver' in window)){nodes.forEach(mount);return;}
  tvObserver=new IntersectionObserver(entries=>entries.forEach(entry=>{if(entry.isIntersecting){mount(entry.target);tvObserver.unobserve(entry.target);}}),{rootMargin:'360px 0px'});
  nodes.forEach(node=>tvObserver.observe(node));
}
function sharedScreenFilters(groups){
  return '<div class="filters kk-filters"><label>Search<input data-filter="search" placeholder="Ticker or theme" value="'+escapeHTML(filters.search)+'"></label>'+selectFilter('group','Theme / industry',[['','All themes / industries'],...groups.map(g=>[g,g])])+'<label>Minimum ADR %<input data-filter="adr" type="number" min="0" step=".1" value="'+filters.adr+'"></label><label>Maximum extension ×<input data-filter="extension" type="number" step=".1" value="'+filters.extension+'" placeholder="No limit"></label><div class="filter-toggle-row"><span class="horizon-label">Trend & structure</span><div class="segments">'+kkToggle('> 9D EMA','above9d')+kkToggle('> 9W EMA','above9w')+kkToggle('> 9M EMA','above9m')+kkToggle('Liquid · $100M+ / 1M shares+','liquid')+kkToggle('Superliquid · $500M+','superLiquid')+kkToggle('Tight','tight')+'</div></div></div>';
}
function obcSelectFilter(key,label,options){return '<label>'+label+'<select data-obc-filter="'+key+'">'+options.map(([v,t])=>'<option value="'+escapeHTML(v)+'" '+(obcFilters[key]===v?'selected':'')+'>'+escapeHTML(t)+'</option>').join('')+'</select></label>';}
function obcToggle(label,key){return '<button data-action="obc-toggle" data-toggle="'+key+'" class="'+(obcFilters[key]?'active':'')+'">'+label+'</button>';}
function obcScreenFilters(groups){
  return '<div class="filters kk-filters"><label>Search<input data-obc-filter="search" placeholder="Ticker or theme" value="'+escapeHTML(obcFilters.search)+'"></label>'+obcSelectFilter('group','Theme / industry',[['','All themes / industries'],...groups.map(g=>[g,g])])+'<label>Minimum ADR %<input data-obc-filter="adr" type="number" min="0" step=".1" value="'+obcFilters.adr+'" placeholder="No minimum"></label><label>Maximum extension ×<input data-obc-filter="extension" type="number" step=".1" value="'+obcFilters.extension+'" placeholder="No maximum"></label><div class="filter-toggle-row"><span class="horizon-label">Liquidity</span><div class="segments">'+obcToggle('Liquid · $100M+ / 1M shares+','liquid')+obcToggle('Superliquid · $500M+','superLiquid')+'</div></div></div>';
}
function kkSortHeader(label,key,align=''){
  const active=kkSort.key===key, arrow=active?(kkSort.direction==='asc'?' ↑':' ↓'):'';
  return '<th class="'+align+'"><button type="button" class="sort-header" data-action="kk-sort" data-sort-key="'+key+'" aria-label="Sort by '+label+'">'+label+arrow+'</button></th>';
}
function returnTone(value){return Number(value)>0?'positive':Number(value)<0?'negative':'';}
function extensionTone(value){return value>8?'purple':value>4?'orange':value>0?'positive':value<0?'negative':'';}
function adrTone(value){return value>5?'positive':value<5?'negative':'';}
function volumeTone(value){return value>500e6?'blue':value<500e6?'orange':'';}
function trendLabel(above){return '<span class="'+(above?'positive':'negative')+'">'+(above?'Above':'Below')+'</span>';}
function kkScreener(){
  const rows=filteredKKStocks(), groups=[...new Set(stocks('kk').map(tag))].sort();
  const table=rows.length ? '<div class="table-box kk-table"><table><thead><tr>'+kkSortHeader('Stock','stock')+kkSortHeader('Theme','theme')+kkSortHeader('1M%','1m','num')+kkSortHeader('3M%','3m','num')+kkSortHeader('6M%','6m','num')+kkSortHeader('Extension','extension','num')+kkSortHeader('Avg $ Vol','dollarVolume','num')+kkSortHeader('ADR%','adr','num')+kkSortHeader('9D','above9d','num')+kkSortHeader('9W','above9w','num')+kkSortHeader('9M','above9m','num')+'</tr></thead><tbody>'+rows.map(r=>'<tr><td><button data-stock="'+escapeHTML(r.symbol)+'" data-kind="kk">'+escapeHTML(r.symbol)+'</button></td><td>'+escapeHTML(tag(r))+(isMapped(r)?'<small>Custom</small>':'')+'</td><td class="num '+returnTone(r.performance['1m'])+'">'+pct(r.performance['1m'])+'</td><td class="num '+returnTone(r.performance['3m'])+'">'+pct(r.performance['3m'])+'</td><td class="num '+returnTone(r.performance['6m'])+'">'+pct(r.performance['6m'])+'</td><td class="num '+extensionTone(r.extension)+'">'+fmt(r.extension,2)+'×</td><td class="num '+volumeTone(r.dollarVolume)+'">'+money(r.dollarVolume)+'</td><td class="num '+adrTone(r.adr)+'">'+pct(r.adr)+'</td><td class="num">'+trendLabel(r.above9d)+'</td><td class="num">'+trendLabel(r.above9w)+'</td><td class="num">'+trendLabel(r.above9m)+'</td></tr>').join('')+'</tbody></table></div>' : '<p class="empty">No KK leaders match these speed and extension settings.</p>';
  return '<section class="hero"><span class="eyebrow">KK SCAN · LIQUID LEADERS</span><h2>Strength first. Speed and extension second.</h2><p>The universe is built from stocks with at least $30M average 30-day dollar volume and 350K average 10-day shares. KK then takes the exact top 2% in each of 1M, 3M and 6M performance, combines them, and removes duplicates.</p></section><div class="toolbar"><span class="note"><b>'+rows.length+'</b> of '+stocks('kk').length+' KK Liquid Leaders shown</span><span class="push"></span>'+screenerDisplayControl()+button('Export current symbols','export-kk','primary')+'</div>'+sharedScreenFilters(groups)+(screenerDisplay==='charts'?chartGrid(rows,'kk'):table)+'<p class="note">ADR, extension and trend filters only filter this already-selected leader list. They do not determine who qualifies as a KK Liquid Leader. Click a stock for its evidence and chart.</p>';
}
function screenerTabs(){return '<div class="toolbar screener-tabs"><span class="horizon-label">Screen</span><div class="segments"><button data-action="select-screen" data-screen="kk" class="'+(screenerView==='kk'?'active':'')+'">KK · Liquid Leaders</button><button data-action="select-screen" data-screen="obc" class="'+(screenerView==='obc'?'active':'')+'">OBC · Oversold Bounces</button></div></div>';}
function filteredOBCStocks(){
  return stocks('obc').filter(r=>
    (!obcFilters.search || (r.symbol+' '+r.description+' '+tag(r)).toLowerCase().includes(obcFilters.search.toLowerCase())) &&
    (!obcFilters.group || tag(r)===obcFilters.group) &&
    (obcFilters.adr==='' || (finite(r.adr) && r.adr>=Number(obcFilters.adr))) &&
    (obcFilters.extension==='' || (finite(r.extension)&&r.extension<Number(obcFilters.extension))) &&
    (!obcFilters.liquid || (r.dollarVolume>=100e6 && r.shareVolume>=1e6)) &&
    (!obcFilters.superLiquid || r.dollarVolume>=500e6)
  ).sort((a,b)=>(a.performance['3m']??Infinity)-(b.performance['3m']??Infinity)|| (b.performance['1y']??-Infinity)-(a.performance['1y']??-Infinity));
}
function obcScreener(){
  const all=stocks('obc'), groups=[...new Set(all.map(tag))].sort(), rows=filteredOBCStocks();
  const table=rows.length?'<div class="table-box kk-table"><table><thead><tr><th>Stock</th><th>Theme</th><th class="num">1Y%</th><th class="num">3M%</th><th class="num">Extension</th><th class="num">Avg $ Vol</th><th class="num">ADR%</th></tr></thead><tbody>'+rows.map(r=>'<tr><td><button data-stock="'+escapeHTML(r.symbol)+'" data-kind="obc">'+escapeHTML(r.symbol)+'</button></td><td>'+escapeHTML(tag(r))+(isMapped(r)?'<small>Custom</small>':'')+'</td><td class="num '+returnTone(r.performance['1y'])+'">'+pct(r.performance['1y'])+'</td><td class="num '+returnTone(r.performance['3m'])+'">'+pct(r.performance['3m'])+'</td><td class="num '+extensionTone(r.extension)+'">'+fmt(r.extension,2)+'×</td><td class="num '+volumeTone(r.dollarVolume)+'">'+money(r.dollarVolume)+'</td><td class="num '+adrTone(r.adr)+'">'+pct(r.adr)+'</td></tr>').join('')+'</tbody></table></div>':'<p class="empty">No OBC candidates match these filters.</p>';
  return '<section class="hero"><span class="eyebrow">OBC SCAN · OVERSOLD BOUNCE CANDIDATES</span><h2>Proven leaders on a meaningful pullback.</h2><p>Starts with a separate liquid US-stock universe: average 30-day dollar volume above $30M and average 10-day shares above 350K. From there, it takes the top 10% over the trailing 1 year, then selects the weakest 25% of those leaders over 3 months.</p></section><div class="toolbar"><span class="note"><b>'+rows.length+'</b> of '+all.length+' OBC candidates shown · sorted by weakest 3M performance first</span><span class="push"></span>'+screenerDisplayControl()+button('Export current symbols','export-obc','primary')+'</div>'+obcScreenFilters(groups)+(screenerDisplay==='charts'?chartGrid(rows,'obc'):table)+'<p class="note">These controls filter an already-selected OBC list. OBC identifies a pullback inside established one-year leadership; it is not an entry signal. Review structure, support and catalyst risk on the chart.</p>';
}
function screener(){return screenerTabs()+(screenerView==='kk'?kkScreener():obcScreener());}
function median(values){const clean=values.filter(finite).map(Number).sort((a,b)=>a-b);if(!clean.length)return null;const mid=Math.floor(clean.length/2);return clean.length%2?clean[mid]:(clean[mid-1]+clean[mid])/2;}
function etfPair(payload){const available=(payload.snapshots||[]).filter(s=>s.date<=asof());return {current:available.at(-1),previous:available.at(-2)};}
function groupTape(snapshot){
  const grouped=new Map();
  (snapshot?.daily_changes||[]).forEach(row=>{const item=grouped.get(row.group)||{group:row.group,members:[]};item.members.push(row);grouped.set(row.group,item);});
  return [...grouped.values()].map(item=>{const ordered=[...item.members].filter(r=>finite(r.one_day)).sort((a,b)=>b.one_day-a.one_day);return {...item,move:median(ordered.map(r=>r.one_day)),advancers:ordered.filter(r=>r.one_day>0).length,top:ordered[0],bottom:ordered.at(-1)};}).filter(r=>finite(r.move));
}
function tapeTable(rows,side){
  if(!rows.length)return '<p class="empty">No close-to-close ETF data is available.</p>';
  return '<div class="table-box"><table><thead><tr><th>Theme</th><th class="num">Group median</th><th>Key expression</th><th class="num">Participation</th></tr></thead><tbody>'+rows.map(row=>{const expression=side==='buy'?row.top:row.bottom;return '<tr><td><b>'+escapeHTML(row.group)+'</b></td><td class="num '+(row.move>=0?'positive':'negative')+'">'+signed(row.move)+'%</td><td>'+escapeHTML(expression?.symbol||'—')+' <small>'+signed(expression?.one_day)+'%</small></td><td class="num">'+row.advancers+' / '+row.members.length+' up</td></tr>';}).join('')+'</tbody></table></div>';
}
function sessionVerdict(current,previous){
  if(!current||!previous)return {title:'Waiting for a comparable prior close',tone:'gold',copy:'Two completed breadth readings are needed to describe the session.'};
  const spMove=finite(current.sp)&&finite(previous.sp)?100*(current.sp/previous.sp-1):null, participation=current.t2108-previous.t2108, net=current.up4-current.down4;
  if(spMove>0&&participation>0&&net>0)return {title:'Buying broadened beneath the index',tone:'positive',copy:'SPX rose, T2108 improved and upside 4% events exceeded downside events.'};
  if(spMove>0&&participation<=0)return {title:'The index rose, but participation lagged',tone:'gold',copy:'SPX gained while the share of stocks above their 40-day average failed to improve.'};
  if(spMove<0&&participation<0&&net<0)return {title:'Selling broadened across the tape',tone:'negative',copy:'SPX fell, T2108 weakened and downside 4% events exceeded upside events.'};
  if(spMove<0&&participation>=0)return {title:'The index fell, but internal participation held up',tone:'gold',copy:'SPX declined without a matching deterioration in T2108.'};
  return {title:'A mixed session without clean internal agreement',tone:'gold',copy:'Index direction, breadth and large-move counts did not align into one clear message.'};
}
function review(){
  const rows=breadthRows(), b=rows[0], old=rows[1], priorRead=marketRead(old), verdict=sessionVerdict(b,old), themePair=etfPair(themes), sectorPair=etfPair(sectors);
  const tape=groupTape(themePair.current), bought=tape.filter(r=>r.move>0).sort((a,b)=>b.move-a.move).slice(0,5), sold=tape.filter(r=>r.move<0).sort((a,b)=>a.move-b.move).slice(0,5);
  const sectorMoves=(sectorPair.current?.daily_changes||[]).filter(r=>finite(r.one_day)).sort((a,b)=>b.one_day-a.one_day), spMove=b&&old&&finite(b.sp)&&finite(old.sp)?100*(b.sp/old.sp-1):null;
  const priorThemes=(themePair.previous?.windows?.[frame]||[]).slice(0,3);
  return '<section class="hero"><span class="eyebrow">SESSION DEBRIEF · CLOSE '+escapeHTML(b?.date||asof())+'</span><h2 class="'+verdict.tone+'">'+verdict.title+'</h2><p>'+verdict.copy+'</p><div class="kpis">'+metric('SPX',signed(spMove)+'%')+metric('T2108 change',old?signed(b.t2108-old.t2108)+' pp':'—')+metric('Up / down 4%',fmt(b?.up4,0)+' / '+fmt(b?.down4,0))+metric('5D / 10D',fmt(b?.ratio5,2)+' / '+fmt(b?.ratio10,2))+'</div></section><div class="toolbar">'+frameControls('Leadership comparison')+'<span class="note">Only leadership and NEL comparisons change. Bought/sold always means the latest close-to-close move.</span></div><div class="grid">'+card('How we came in','<h2 class="'+priorRead.tone+'">'+priorRead.title+'</h2><p>'+priorRead.reason+'</p>'+measure('Prior breadth close',escapeHTML(old?.date||'—'),'Information available before this session')+measure('Themes leading into the session',priorThemes.map(g=>escapeHTML(g.group)).join(' · ')||'—',frames[frame]+' ranking at the prior close'))+card('What changed internally',measure('Net large-move breadth',signed((b?.up4||0)-(b?.down4||0)),old?'Prior '+signed((old.up4||0)-(old.down4||0)):'')+measure('T2108',pct(b?.t2108),old?'Change '+signed(b.t2108-old.t2108)+' pp':'')+measure('10D pressure',fmt(b?.ratio10,2),old?'Change '+signed(b.ratio10-old.ratio10,2):'')+measure('Quarter winners / losers',fmt(b?.up25q,0)+' / '+fmt(b?.down25q,0),old?'Previously '+fmt(old.up25q,0)+' / '+fmt(old.down25q,0):''))+'</div><div class="grid">'+card('What got bought',tapeTable(bought,'buy')+'<p class="note">Ranked by median close-to-close return across the ETFs in each theme. “Bought” describes price response, not reported fund flows.</p>')+card('What got sold',tapeTable(sold,'sell')+'<p class="note">Negative group medians show broad selling; a weak ETF inside a positive group can be an isolated laggard.</p>')+'</div>'+card('Sector tape','<div class="sector-strip">'+sectorMoves.map(row=>'<div><span>'+escapeHTML(row.group)+'</span><b class="'+(row.one_day>=0?'positive':'negative')+'">'+signed(row.one_day)+'%</b><small>'+escapeHTML(row.symbol)+'</small></div>').join('')+'</div><p class="note">Close-to-close sector ETF returns for '+escapeHTML(sectorPair.current?.date||'the selected close')+'.</p>')+'<div class="grid" style="margin-top:20px">'+card('Leadership and NEL rotation',changeSummary())+card('What stood out','<p><b>'+escapeHTML(bought[0]?.group||'No theme')+'</b> had the strongest group median at '+signed(bought[0]?.move)+'%, led by '+escapeHTML(bought[0]?.top?.symbol||'—')+'.</p><p><b>'+escapeHTML(sold[0]?.group||'No theme')+'</b> was weakest at '+signed(sold[0]?.move)+'%, with '+escapeHTML(sold[0]?.bottom?.symbol||'—')+' the weakest expression.</p><p>'+escapeHTML(sectorMoves[0]?.group||'No sector')+' led sectors ('+signed(sectorMoves[0]?.one_day)+'%), while '+escapeHTML(sectorMoves.at(-1)?.group||'no sector')+' lagged ('+signed(sectorMoves.at(-1)?.one_day)+'%).</p><p class="note">This is an automatic description of observed returns and breadth—not a causal explanation or trade recommendation.</p>','breadth.html','Open session history')+'</div>';
}
function method(){
 return card('How to use this workspace','<p>Start with Environment, inspect Leadership, then use the Screener to prepare a chart-review list. Positioning is a separate weekly context layer. Debrief automatically compares the completed session with the information available at the prior close.</p><details open><summary>Dates and data freshness</summary><p>Stock lists are named for the next trading session. ETF and breadth readings use the actual close date. The briefing and debrief select only ETF/breadth records at or before the stock snapshot’s close. COT always shows its report date and is not represented as daily or historical point-in-time data.</p></details><details open><summary>Relative strength, themes, and odds</summary><p>Performance versus SPY is a return difference in percentage points. Theme strength scores rank ETF performance. “Bought” and “sold” describe close-to-close price response, not reported fund flows. None of these measures is a probability of a profitable trade. Chart review still determines whether a setup is usable.</p><p>Your uploaded group definitions are available when editing a stock. Three owner-supplied Crypto overrides seed the mapping. Remaining stocks use explicitly labelled vendor groups until reviewed. New mappings apply from their effective snapshot date. Local edits affect this workspace and can be exported; they do not silently rewrite historical CSVs or sync between devices.</p></details><details open><summary>COT methodology</summary><p>CFTC Legacy futures-only reports; commercials, noncommercials, and nonreportables. Five-year min/max normalization of net long minus short. Thresholds 5 and 95 flag range extremes. CMR’s proprietary index is not reproduced, and the uploaded crypto direction reversal is not assumed to be a validated strategy. Commercial net positioning balances speculative net positioning; the three readings are not independent confirmations.</p></details><details><summary>What still requires verification</summary><p>The four INDEX 20-day breadth feeds did not return data through the available scanner endpoint. Their source links and your alert levels are shown rather than substituted values. Jeff’s exact RS Thrust formula was not provided or verified. Current group rankings use the existing documented score.</p></details><p class="source-list"><a href="https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm">CFTC official report definitions</a> · <a href="https://www.crowdedmarketreport.com/wp-content/uploads/2023/04/CMR-New-Member-Guide-2023.pdf">CMR methodology guide</a> · <a href="https://stockbee.blogspot.com/p/mm.html">Stockbee Market Monitor</a></p>');
}
function render(){
 document.querySelector('.bm-workstation')?._chartObserver?.disconnect();
  route=location.hash.slice(1)||'briefing';if(!titles[route])route='briefing';
  $('#page-title').textContent=titles[route];
  const menuButton=document.querySelector('#page-menu-button'),menu=document.querySelector('#page-menu-options');
  menuButton.querySelector('span').textContent=menu.querySelector('[data-page="'+route+'"]')?.textContent||titles[route];
  const closeMenu=()=>{menu.hidden=true;menuButton.setAttribute('aria-expanded','false');};closeMenu();
  const options=[...menu.querySelectorAll('[data-page]')];options.forEach(button=>{button.classList.toggle('active',button.dataset.page===route);button.onclick=()=>{closeMenu();location.hash=button.dataset.page;menuButton.focus();};});
  const openMenu=()=>{menu.hidden=false;menuButton.setAttribute('aria-expanded','true');(options.find(button=>button.dataset.page===route)||options[0]).focus();};
  menuButton.onclick=()=>menu.hidden?openMenu():closeMenu();
  menuButton.onkeydown=event=>{if(event.key==='ArrowDown'||event.key==='ArrowUp'){event.preventDefault();openMenu();}};
  menu.onkeydown=event=>{const index=options.indexOf(document.activeElement);if(event.key==='Escape'){event.stopPropagation();closeMenu();menuButton.focus();}else if(['ArrowDown','ArrowUp','Home','End'].includes(event.key)){event.preventDefault();options[event.key==='Home'?0:event.key==='End'?options.length-1:(index+(event.key==='ArrowDown'?1:-1)+options.length)%options.length].focus();}};
  document.querySelector('.page-menu').onfocusout=event=>{if(!event.currentTarget.contains(event.relatedTarget))closeMenu();};
  if(!window.pageMenuOutsideBound){document.addEventListener('click',event=>{if(!event.target.closest('.page-menu')){document.querySelector('#page-menu-options').hidden=true;document.querySelector('#page-menu-button').setAttribute('aria-expanded','false');}});window.pageMenuOutsideBound=true;}
  const savedSession=document.querySelector('#header-date-controls .session');if(savedSession)document.querySelector('.workspace-top').append(savedSession);document.querySelector('#header-date-controls').replaceChildren();
  document.body.classList.toggle('positioning-page',route==='positioning');
  document.body.classList.toggle('breadth-page',route==='environment');
  document.body.classList.toggle('flow-page',route==='leadership');
  document.querySelectorAll('.session,.research-menu').forEach(node=>{node.style.display=(['positioning','environment'].includes(route)||(route==='leadership'&&node.matches('.research-menu')))?'none':'';});
  $('#session-label').textContent=route==='review'?'Debrief snapshot':'Plan for session';
  document.querySelectorAll('.rail nav a').forEach(a=>a.classList.toggle('active',a.hash==='#'+route));
  const b=breadthRows()[0],e=latestETF(themes);
  $('#freshness').textContent='Stock close '+asof()+' → plan '+session().date+'  ·  Breadth '+(b?.date||'unavailable')+'  ·  ETFs '+(e?.date||'unavailable');
  $('#view').innerHTML=({briefing,environment,leadership,positioning,screener,review,method})[route]();
  if(route==='environment'){arrangeBreadthDashboard();setBreadthHover(-1);bindBreadthHover();const header=document.querySelector('.bm-compact-header'),slot=document.querySelector('#header-date-controls');[...header.children].filter(node=>node.matches('label,.bm-date-controls,[data-bm-unpin]')).forEach(node=>slot.append(node));header.remove();}
  else if(route==='positioning'){const slot=document.querySelector('#header-date-controls');slot.append(document.querySelector('[data-cot-controls]'),document.querySelector('[data-cot-alerts]'),document.querySelector('[data-cot-lookbacks]'));}
  else{document.querySelector('#header-date-controls').append(document.querySelector('.session'));}

  if(route==='leadership')mountFlowOverviewCharts();
  mountTradingViewCharts();
  document.querySelectorAll('.cot-row').forEach(row=>{
    const readings=row.querySelector('.cot-hover-read'),left=row.querySelector('.cot-position');
    if(readings&&left){left.querySelector('.cot-actuals')?.remove();left.appendChild(readings);updateCOTReadings(row.querySelector('[data-cot-chart]'),-1);}
  });
}
function download(name,text,type='text/plain'){
  const url=URL.createObjectURL(new Blob([text],{type})),a=document.createElement('a');a.href=url;a.download=name;a.click();setTimeout(()=>URL.revokeObjectURL(url),500);
}
function showStock(symbol,kind){
  selected=stocks(kind).find(r=>r.symbol===symbol);if(!selected)return;
  const r=selected, known=(db.groups||[]).map(g=>g.name), options=[...new Set([tag(r),...known])];
  $('#stock-content').innerHTML='<span class="eyebrow">CANDIDATE EVIDENCE</span><h1>'+escapeHTML(r.symbol)+'</h1><p>'+escapeHTML(r.description)+'</p><p>'+escapeHTML(tag(r))+' <span class="note">· '+(isMapped(r)?'custom classification':'vendor fallback')+'</span></p><div class="kpis">'+metric(frames[frame]+' return',pct(r.performance[frame]))+metric('Extension',fmt(r.extension,2)+'×')+metric('ADR',pct(r.adr))+metric('Avg $ vol',money(r.dollarVolume))+'</div>'+measure('Leader windows',r.leaders.map(f=>frames[f]).join(' / ')||'None')+measure('Structure',r.tight?'Passes tightness scan':'Manual review required')+'<p class="note">Original industry: '+escapeHTML(r.industry)+'. '+(r.pair?'Paired ETF: '+escapeHTML(r.pair)+'. Displayed metrics are for '+escapeHTML(r.symbol)+'.':'')+'</p><a class="pill" target="_blank" rel="noopener" href="https://www.tradingview.com/chart/?symbol='+encodeURIComponent(r.symbol)+'">Open chart ↗</a><details open><summary>Edit custom theme</summary><div class="inline-form"><select id="theme-edit" aria-label="Custom theme">'+options.map(g=>'<option '+(g===tag(r)?'selected':'')+'>'+escapeHTML(g)+'</option>').join('')+'</select>'+button('Save theme','save-theme')+'</div><p class="note">Effective from this snapshot date. Saved locally in this browser. The original industry is preserved.</p></details>';
  $('#stock-dialog').showModal();
}
document.addEventListener('click',async event=>{
 const node=event.target.closest('button,[data-filter-group],[data-flow-group],[data-flow-index]');if(!node)return;
 if(node.dataset.cotWindow){cotWindow=node.dataset.cotWindow;render();return;}
 const cotAction=node.dataset.action;
 if(cotAction==='cot-prev'||cotAction==='cot-next'||cotAction==='cot-latest'){const dates=cotDates(),current=cotDate||dates.at(-1),at=dates.findLastIndex(d=>d<=current);cotDate=cotAction==='cot-latest'?'':dates[Math.max(0,Math.min(dates.length-1,at+(cotAction==='cot-prev'?-1:1)))];render();return;}
 if(node.dataset.cotJump){document.getElementById('cot-market-'+node.dataset.cotJump)?.scrollIntoView({behavior:'smooth',block:'start'});return;}
 if(node.dataset.flowHolding&&flowETFState){flowETFState.chartSymbol=node.dataset.flowHolding;flowETFDialog();return;}
 if(node.dataset.flowEtf){openFlowETF(node.dataset.flowEtf,node.dataset.flowGroup);return;}
 if(node.dataset.frame){frame=node.dataset.frame;render();}
 if(node.dataset.leadership){leadershipKind=node.dataset.leadership;render();}
 if(node.dataset.indexRange){indexFrame=node.dataset.indexRange;render();return;}
 if(node.dataset.marketDetail){openMarketDetail(node.dataset.marketDetail,node.dataset.marketCategory);return;}
 if(node.dataset.marketSort){flowOverviewSort[node.dataset.marketCategory]=node.dataset.marketSort;const category=node.dataset.marketCategory,old=document.querySelector('.market-comparison-grid'),holder=document.createElement('div');holder.innerHTML=flowMarketOverview();old.replaceWith(holder.querySelector('.market-comparison-grid'));return;}
 if(node.dataset.action==='market-definitions'){const guide=document.querySelector('.market-metric-guide');guide.hidden=!guide.hidden;return;}
 if(node.dataset.flowIndex){flowSelection=node.dataset.flowIndex;render();return;}
 if(node.dataset.flowFrame){flowFrame=node.dataset.flowFrame;flowMode='strength';if(leadershipKind!=='indexes')flowSelection='';render();return;}
 if(node.dataset.flowMode){flowMode=node.dataset.flowMode;flowSelection='';render();return;}
 if(node.dataset.flowGroup){flowSelection=node.dataset.flowGroup;render();return;}
 if(node.dataset.filterGroup){filters.group=node.dataset.filterGroup;location.hash='screener';}
 if(node.dataset.stock)showStock(node.dataset.stock,node.dataset.kind);
 const action=node.dataset.action;
 if(action==='breadth-metric'){breadthMetric=node.dataset.metric;render();document.querySelector('.bm-details').open=true;return;}
 if(action==='breadth-range'){breadthRange=node.dataset.range;render();document.querySelector('.bm-details').open=true;return;}
 if(action==='breadth-window'){const page=document.querySelector('.bm-console');if(page?._setWindow){page._setWindow(Number(node.dataset.window));}else{breadthPinned=-1;breadthWindow=Number(node.dataset.window);render();}return;}
 if(action==='select-screen'){screenerView=node.dataset.screen;render();return;}
 if(action==='screener-view'){screenerDisplay=node.dataset.view;render();return;}
 if(action==='kk-sort'){const key=node.dataset.sortKey;kkSort={key,direction:kkSort.key===key&&kkSort.direction==='desc'?'asc':'desc'};render();return;}
 if(action==='flow-sort'){const key=node.dataset.sortKey;flowSort={key,direction:flowSort.key===key&&flowSort.direction==='asc'?'desc':'asc'};render();return;}
 if(action==='flow-dialog-close'){$('#flow-etf-dialog').close();return;}
 if(action==='kk-toggle'){const key=node.dataset.toggle;filters[key]=!filters[key];render();return;}
 if(action==='obc-toggle'){const key=node.dataset.toggle;obcFilters[key]=!obcFilters[key];render();return;}
 if(action==='export-kk')download('kk-liquid-leaders-'+session().date+'.csv','symbol\n'+[...new Set(filteredKKStocks().map(r=>r.symbol))].join('\n')+'\n','text/csv');
 if(action==='export-obc')download('obc-candidates-'+session().date+'.csv','symbol\n'+[...new Set(filteredOBCStocks().map(r=>r.symbol))].join('\n')+'\n','text/csv');
 if(action==='save-theme'&&selected){overrides[selected.symbol]={theme:$('#theme-edit').value,effective:session().date,source:'Local owner review'};if(store.set('themes',overrides)){$('#stock-dialog').close();render();}}
 if(node.classList.contains('dialog-close'))$('#stock-dialog').close();
});
document.addEventListener('change',event=>{
 if(event.target.matches('[data-cot-date]')){const dates=cotDates();cotDate=dates.filter(d=>d<=event.target.value).at(-1)||dates[0];render();return;}
 if(event.target.matches('[data-breadth-date]')){breadthPinned=-1;breadthDate=event.target.value;render();return;}
 const key=event.target.dataset.filter;if(key){filters[key]=event.target.value;render();}
 const obcKey=event.target.dataset.obcFilter;if(obcKey){obcFilters[obcKey]=event.target.value;render();}
});
window.addEventListener('hashchange',()=>{if(session())render();});
function updateCOTReadings(svg,j){
 const market=cot.markets?.find(m=>m.code===svg.dataset.cotChart);if(!market)return;
 const history=cotHistory(market).slice(-52);
 if(j<0)j=history.length-1;
 const row=history[j],previous=history[j-1],read=svg.closest('.cot-row').querySelector('.cot-hover-read');
 const card=svg.closest('.cot-row'),latestView=j===history.length-1;
 const price=market.prices?.filter(p=>p.date<=cotRelease(row)).at(-1);
 let quote=card.querySelector('.cot-etf-quote');
 if(!quote){quote=document.createElement('div');quote.className='cot-etf-quote';card.querySelector('.cot-position header').appendChild(quote);}
 const previousDate=price?new Date(price.date+'T00:00:00Z'):null;
 if(previousDate)previousDate.setUTCDate(previousDate.getUTCDate()-7);
 const previousPrice=previousDate?market.prices?.filter(p=>p.date<=previousDate.toISOString().slice(0,10)).at(-1):null;
 const change=price&&previousPrice?100*(price.close/previousPrice.close-1):null;
 quote.innerHTML='<div><b>'+escapeHTML(market.etf)+'</b><strong>'+(price?'$'+fmt(price.close,2):'—')+'</strong><span class="'+(change>=0?'positive':'negative')+'" title="Close-to-close return versus '+escapeHTML(previousPrice?.date||'unavailable')+'">'+(finite(change)?'('+signed(change,2)+'%)':'')+'</span></div>';
 card.querySelectorAll('.cot-participant').forEach((node,i)=>{
   const key=['large','small','commercials'][i],value=row.participants[key]?.indices?.[cotWindow],prior=previous?.participants[key]?.indices?.[cotWindow];
   node.querySelector('strong').textContent=fmt(value,1);
   const marker=node.querySelector('.cot-track>b');if(marker){marker.style.left=(finite(value)?value:0)+'%';marker.style.display=finite(value)?'':'none';}
   const notes=node.querySelectorAll('small');notes[0].textContent=!finite(value)?'Insufficient history':value<=5?'Near range low':value>=95?'Near range high':'Within range';
   notes[1].textContent=finite(value)&&finite(prior)?signed(value-prior,1)+' pts this week':'';
 });
 const readKeys=cotParticipant==='all'?['large','commercials','small']:[cotParticipant];
 const names={large:'Large speculators',small:'Small speculators',commercials:'Commercials'};
 const all=cotHistory(market),length=cotPeriods[cotWindow],endIndex=all.findIndex(r=>r.date===row.date);
 read.innerHTML='<span class="cot-read-date">Report · '+escapeHTML(row.date)+'</span><div class="cot-read-grid">'+readKeys.map(key=>{
 const net=row.participants[key]?.net,delta=net-previous?.participants[key]?.net;
 const values=endIndex+1>=length?all.slice(endIndex+1-length,endIndex+1).map(r=>r.participants[key]?.net).filter(finite):[];
 return '<div data-cot-party="'+key+'"><b>'+names[key]+'</b><span>Net '+(net>=0?'long ':'short ')+'<strong>'+fmt(Math.abs(net),0)+'</strong></span><span>Weekly change <strong>'+signed(delta,0)+'</strong></span><small>'+cotWindow.toUpperCase()+' range · '+(values.length===length?signed(Math.min(...values),0)+' to '+signed(Math.max(...values),0):'Insufficient history')+' contracts</small></div>';
 }).join('')+'</div>';

}
document.addEventListener('pointermove',event=>{
 const svg=event.target.closest?.('[data-cot-chart]');if(!svg)return;
 const market=cot.markets?.find(m=>m.code===svg.dataset.cotChart);if(!market)return;
 const history=cotHistory(market).slice(-52);
 const rect=svg.getBoundingClientRect(),x=(event.clientX-rect.left)*780/rect.width;
 const j=Math.max(0,Math.min(history.length-1,Math.round((x-32)/716*(history.length-1))));
 updateCOTReadings(svg,j);
 const guide=svg.querySelector('.cot-hover-line'),gx=32+j*716/Math.max(1,history.length-1);guide.setAttribute('x1',gx);guide.setAttribute('x2',gx);guide.setAttribute('opacity','0.7');
});
document.addEventListener('pointerout',event=>{const svg=event.target.closest?.('[data-cot-chart]');if(svg&&!svg.contains(event.relatedTarget)){svg.querySelector('.cot-hover-line')?.setAttribute('opacity','0');updateCOTReadings(svg,-1);}});
async function loadJSON(path,optional=false){const r=await fetch(path,{cache:'no-cache'});if(!r.ok){if(optional)return {};throw Error('Could not load '+path);}return r.json();}
async function start(){
 try{
 [db,themes,sectors,breadth,spxHistory,cot,context,indexHistory,flowMarket]=await Promise.all([loadJSON('outputs/workspace.json'),loadJSON('outputs/etf/themes_snapshots.json'),loadJSON('outputs/etf/sectors_snapshots.json'),loadJSON('outputs/breadth_market_monitor.json'),loadJSON('outputs/spx_history.json',true),loadJSON('outputs/positioning.json',true),loadJSON('outputs/market_context.json',true),loadJSON('outputs/index_history.json',true),loadJSON('outputs/flow_market.json',true)]);
 if(!db.snapshots?.length)throw Error('No saved stock snapshots available.');
 $('#session').innerHTML=db.snapshots.toReversed().map(s=>'<option value="'+s.date+'">'+s.date+'</option>').join('');
 $('#session').addEventListener('change',render);render();
 }catch(error){$('#view').innerHTML='<p class="alert">'+escapeHTML(error.message)+'</p><a href="industry_flow_dashboard.html">Open saved detailed stock dashboard ↗</a>';}
}
start();
