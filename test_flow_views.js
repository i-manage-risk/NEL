const fs=require('fs'),vm=require('vm'),assert=require('assert');
const s=fs.readFileSync('assets/workspace.js','utf8');
const code=s.slice(s.indexOf('let flowOverviewViews='),s.indexOf('let flowDailyCharts='));
const flowMarket=JSON.parse(fs.readFileSync('outputs/flow_market.json','utf8'));
const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
const ctx={flowMarket,asof:()=> '2026-11-11',finite,escapeHTML:v=>String(v).replace(/&/g,'&amp;').replace(/"/g,'&quot;'),returnTone:v=>v>0?'positive':v<0?'negative':'',fmt:(v,d=1)=>finite(v)?Number(v).toFixed(d):'—',signed:(v,d=1)=>finite(v)?(v>0?'+':'')+Number(v).toFixed(d):'—'};
vm.createContext(ctx);vm.runInContext(code,ctx);
let html=ctx.flowMarketOverview();assert.equal((html.match(/data-flow-category-section=/g)||[]).length,5);assert.equal((html.match(/data-flow-view=/g)||[]).length,10);
assert.equal((html.match(/data-market-chart=/g)||[]).length,8);assert.equal((html.match(/<table>/g)||[]).length,4);
assert(html.indexOf('data-market-chart="SPY"')<html.indexOf('data-market-chart="QQQ"'));
for(const key of ['market','segments','equal_weight','sectors','industries']){
 vm.runInContext(`flowOverviewViews={market:'table',segments:'table',equal_weight:'table',sectors:'table',industries:'table'};flowOverviewViews['${key}']='charts';`,ctx);
 html=ctx.flowMarketOverview();assert.equal((html.match(/data-market-chart=/g)||[]).length,flowMarket.groups[key].length);assert.equal((html.match(/<table>/g)||[]).length,4);
 const ids=[...html.matchAll(/id="(market-tv-[^"]+)"/g)].map(m=>m[1]);assert.equal(new Set(ids).size,ids.length);
}
vm.runInContext("flowOverviewViews={market:'table',segments:'table',equal_weight:'table',sectors:'table',industries:'table'}",ctx);
html=ctx.flowMarketOverview();assert.equal((html.match(/<table>/g)||[]).length,5);assert.equal((html.match(/data-market-chart=/g)||[]).length,0);
console.log('Flow: five independent view toggles, every ETF retained, unique chart IDs and index order passed.');
