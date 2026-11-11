const fs=require('fs'),vm=require('vm'),assert=require('assert');
const source=fs.readFileSync('assets/workspace.js','utf8');
const code=source.slice(source.indexOf('function createTradingView(options){'),source.indexOf('function loadTradingView(){'));
let config;const context={TradingView:{widget:function(options){config=options;}}};
vm.createContext(context);vm.runInContext(code,context);
for(const interval of ['D','W']){
 context.createTradingView({symbol:'QQQ',interval,studies:['STD;EMA'],overrides:{'mainSeriesProperties.priceAxisProperties.log':true}});
 assert.equal(config.studies[0].id,'MAExp@tv-basicstudies');assert.equal(config.studies[0].inputs.length,9);
 assert.equal(config.studies_overrides['EMA.ma.color'],'#FFFFFF');
 assert.equal(config.backgroundColor,'#202020');assert.equal(config.overrides['mainSeriesProperties.priceAxisProperties.log'],true);
 assert.equal(config.interval,interval);
}
console.log('TradingView: native 9 EMA, white MA plot, gray background, daily/weekly intervals preserved.');
