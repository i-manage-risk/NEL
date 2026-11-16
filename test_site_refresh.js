const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('assets/workspace.js','utf8');
const block=source.slice(source.indexOf('const loadedPageData='),source.indexOf('let pageLoadRequest='));
let downloads=[],headers=[],renders=0,version='v1',latest='2026-11-13';const select={value:latest,innerHTML:''};
const c={db:{snapshots:[{date:latest,closeDate:latest}]},route:'leadership',cot:{},flowMarket:{},themes:{},sectors:{},breadth:[],spxHistory:[],context:{},indexHistory:{},dataETags:new Map([['outputs/flow_market.json','v1']]),setInterval(){},document:{addEventListener(){},visibilityState:'visible'},$(){return select},render(){renders++},fetch:async path=>{headers.push(path);return {ok:true,headers:{get:()=>version}}},loadJSON:async path=>{downloads.push(path);if(path.includes('calendar'))return {snapshots:latest==='2026-11-13'?[{date:latest}]:[{date:'2026-11-13'},{date:latest}]};c.dataETags.set('outputs/flow_market.json',version);return {version}},titles:{},escapeHTML:String,console};
vm.createContext(c);vm.runInContext(block,c);
(async()=>{
 vm.runInContext("loadedPageData.add('flow')",c);
 await c.refreshSiteData();assert.equal(downloads.length,1);assert.equal(headers.length,1);assert.equal(renders,0);
 version='v2';latest='2026-11-16';await c.refreshSiteData();assert.equal(select.value,'2026-11-16');assert.equal(c.flowMarket.version,'v2');assert.equal(renders,1);
 select.value='2026-11-13';version='v3';await c.refreshSiteData();assert.equal(select.value,'2026-11-13');
 const before=downloads.length;await c.refreshSiteData(true);assert.equal(downloads.length,before+2);
 console.log('Site refresh: unchanged payloads skipped, changed data fetched, Latest advances and historical dates preserved.');
})().catch(e=>{console.error(e);process.exit(1)});
