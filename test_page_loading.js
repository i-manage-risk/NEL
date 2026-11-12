const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('assets/workspace.js','utf8');
const block=source.slice(source.indexOf('const loadedPageData='),source.indexOf('async function start(){'));
let requests=[];
const ctx={db:{},themes:{},sectors:{},breadth:[],spxHistory:[],cot:{},context:{},indexHistory:{},flowMarket:{},loadJSON:async path=>{requests.push(path);return {source:path}},$(){return {}},titles:{},escapeHTML:s=>s,render(){}};
vm.createContext(ctx);vm.runInContext(block,ctx);
(async()=>{
 await vm.runInContext("Promise.all(pageDataNeeds.leadership.map(loadPageDataset))",ctx);
 assert.deepEqual(requests,['outputs/flow_market.json']);
 await vm.runInContext("Promise.all(pageDataNeeds.leadership.map(loadPageDataset))",ctx);assert.equal(requests.length,1);
 await vm.runInContext("Promise.all(pageDataNeeds.screener.map(loadPageDataset))",ctx);assert.equal(requests.at(-1),'outputs/workspace.json');
 assert(vm.runInContext("routeDataReady('screener')",ctx));assert(!vm.runInContext("routeDataReady('environment')",ctx));
 const calendar=JSON.parse(fs.readFileSync('outputs/workspace_calendar.json'));
 assert(calendar.snapshots.length>40);assert(!('stocks' in calendar.snapshots[0]));
 console.log('Page loading: route-only downloads, reused data, stock archive deferred, preserved calendar passed.');
})().catch(e=>{console.error(e);process.exit(1)});
