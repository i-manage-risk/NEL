const fs=require('fs'),vm=require('vm'),assert=require('node:assert/strict');
const ctx={document:{addEventListener(){}}};vm.createContext(ctx);vm.runInContext(fs.readFileSync('assets/debrief.js','utf8'),ctx);
const marketData=JSON.parse(fs.readFileSync('outputs/flow_market.json')),breadthData=JSON.parse(fs.readFileSync('outputs/breadth_market_monitor.json')),cotData=JSON.parse(fs.readFileSync('outputs/positioning.json'));
for(const closeDate of ['2026-11-10','2026-11-05','2026-10-01']){
 const m=ctx.buildDebriefModel({closeDate,planDate:'test',marketData,breadthData,cotData});
 assert(m.breadth.date<=closeDate);assert(m.marketDate<=closeDate);assert(m.positions.every(p=>p.release<=closeDate));assert(Object.values(m.metrics).every(p=>p.date<=closeDate));assert(m.metrics.RSP.relative===0);
 if(closeDate==='2026-11-05')assert.equal(m.publicationDate,'2026-10-30');
 const h=marketData.series.SPY.history.filter(r=>r.date<=m.marketDate),r=marketData.series.RSP.history.filter(r=>r.date<=m.marketDate),expected=100*((h.at(-1).close/h.at(-22).close)/(r.at(-1).close/r.at(-22).close)-1);assert(Math.abs(m.metrics.SPY.relative-expected)<1e-10);
}
const dates=Array.from({length:25},(_,i)=>'2026-01-'+String(i+1).padStart(2,'0'));
const series=(growth)=>({history:dates.map((date,i)=>({date,close:100+i*growth,open:100,high:120,low:99}))});
const synthetic={series:{RSP:series(0),A:series(1),B:series(1),C:series(2)},groups:{industries:[{symbol:'A',name:'Multiple · A'},{symbol:'B',name:'Multiple · B'},{symbol:'C',name:'Single · C'}]}};
const model=ctx.buildDebriefModel({closeDate:'2026-01-25',marketData:synthetic,breadthData:[],cotData:{}});assert.equal(model.industryLeader.symbol,'C');assert.equal(model.industries.length,3);assert.equal(model.industries.filter(m=>m.name==='Multiple').length,2);
console.log('Debrief: point-in-time cutoffs, release timing, RSP returns and individual ETF ranking passed.');
