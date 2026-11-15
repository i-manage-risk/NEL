const fs=require('fs'),vm=require('vm'),assert=require('assert');
const payload=JSON.parse(fs.readFileSync('outputs/liquid_leadership.json'));const snapshot=payload.snapshots.at(-1);
const finite=v=>v!==null&&v!==undefined&&Number.isFinite(Number(v));
const ctx={document:{addEventListener(){}},asof:()=>snapshot.date,finite,escapeHTML:String,fmt:(v)=>finite(v)?Number(v).toFixed(2):'—',pct:v=>finite(v)?v+'%':'—',signed:v=>finite(v)?String(v):'—',returnTone:()=>'',extensionTone:()=>'',money:String};vm.createContext(ctx);vm.runInContext(fs.readFileSync('assets/liquid-leadership.js','utf8'),ctx);ctx.payload=payload;vm.runInContext('liquidLeadership=payload',ctx);
let html=ctx.liquid();assert(html.includes('Group leadership'));assert(html.includes('Group RS'));assert(html.includes('median extension'));
assert.equal(ctx.llMedian([null,0,2,4]),2);
for(const period of Object.keys(snapshot.leaders)){
 ctx.key=period;vm.runInContext('llPeriod=key',ctx);
 const groups=snapshot.groups[period];assert.equal(groups.reduce((n,g)=>n+g.stocks,0),snapshot.universe);assert.equal(groups.reduce((n,g)=>n+g.leaders,0),snapshot.leaders[period].length);
 const rows=ctx.llAllRows();const bands=vm.runInContext('llBands',ctx);assert.equal(bands.reduce((n,b)=>n+rows.filter(r=>finite(r.extension)&&b[2](r.extension)).length,0),rows.filter(r=>finite(r.extension)).length);
}
vm.runInContext("llPeriod='all';llRelative=true",ctx);html=ctx.liquid();assert(html.includes('vs SPX'));assert(snapshot.rows.some(r=>r.rsBenchmark.all==='SPX'&&finite(r.rs.all)));
console.log('Groups: full-universe coverage, leader counts, medians, exhaustive extension bands and SPX fallback passed.');
