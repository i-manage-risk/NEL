"""RSP-benchmarked market overview; completed daily sessions, no extended-hours bars."""
import json
import csv
from pathlib import Path
from concurrent.futures import ThreadPoolExecutor
from datetime import datetime, date
from zoneinfo import ZoneInfo
import yfinance as yf
from index_history import calculate

GROUPS={
 'market':[('RSP','S&P 500 Equal Weight'),('SPY','S&P 500'),('QQQ','Nasdaq 100'),('QQQE','Nasdaq 100 Equal Weight'),('IWM','Russell 2000'),('DIA','Dow Jones'),('SPMO','S&P 500 Momentum'),('TLT','20+ Year Treasuries')],
 'segments':[('IJS','Small Cap Value'),('IJR','Small Cap'),('IJT','Small Cap Growth'),('IJJ','Mid Cap Value'),('IJH','Mid Cap'),('IJK','Mid Cap Growth'),('IVE','Large Cap Value'),('IVV','Large Cap'),('IVW','Large Cap Growth')],
 'equal_weight':[('RSPC','Communication'),('RSPN','Industrials'),('RSPF','Financials'),('RSPS','Staples'),('RSPH','Health Care'),('RSPD','Discretionary'),('RSPR','Real Estate'),('RSPU','Utilities'),('RSPM','Materials'),('RSPT','Technology'),('RSPG','Energy')],
 'sectors':[('XLC','Communication'),('XLI','Industrials'),('XLF','Financials'),('XLP','Staples'),('XLV','Health Care'),('XLY','Discretionary'),('XLRE','Real Estate'),('XLU','Utilities'),('XLB','Materials'),('XLK','Technology'),('XLE','Energy')]
}
GROUPS['industries']=[(r['Ticker'],r['Group']+' · '+r['Ticker']) for r in csv.DictReader(open('data/theme_etfs.tsv'),delimiter='\t')]
def main():
 path=Path('outputs/flow_market.json');old=json.loads(path.read_text()) if path.exists() else {};series={};errors={}
 market=dict(GROUPS['market']);symbols=dict(sum(GROUPS.values(),[]))
 def fetch(symbol):
  frame=yf.Ticker(symbol).history(period='max',auto_adjust=False,actions=False)
  if frame.empty:raise ValueError('No daily OHLC')
  now=datetime.now(ZoneInfo('America/New_York'))
  frame=frame[[stamp.date()<now.date() or (stamp.date()==now.date() and now.hour>=16) for stamp in frame.index]]
  metrics={r['date']:r for r in calculate(frame)}
  rows=[]
  for stamp,r in frame.tail(520).iterrows():
   day=stamp.date().isoformat();vals={key:float(r[key]) for key in ['Open','High','Low','Close']}
   if not all(__import__('math').isfinite(v) for v in vals.values()):continue
   rows.append(dict(date=day,open=vals['Open'],high=vals['High'],low=vals['Low'],close=vals['Close'],volume=float(r['Volume']),extension=metrics.get(day,{}).get('extension'),oscillator=metrics.get(day,{}).get('oscillator')))
  return symbol,rows,str(frame.index[0].date())
 with ThreadPoolExecutor(max_workers=4) as pool:
  futures={symbol:pool.submit(fetch,symbol) for symbol in symbols}
  for symbol,future in futures.items():
   try:
    key,rows,start=future.result();series[key]=dict(name=symbols[key],history=rows,history_start=start);print(key,len(rows),rows[-1]['date'])
   except Exception as error:
    if symbol in old.get('series',{}):series[symbol]=old['series'][symbol]
    errors[symbol]=str(error);print(symbol,'FAILED',error)
 if 'RSP' not in series:raise RuntimeError('RSP benchmark unavailable')
 # Intraday is stored independently so historical close views keep their own trace.
 from debrief_intraday import fetch_intraday
 intraday_errors={}
 cutoff=series['RSP']['history'][-1]['date']
 with ThreadPoolExecutor(max_workers=4) as pool:
  tasks={symbol:pool.submit(fetch_intraday,symbol,old.get('series',{}).get(symbol,{}).get('intraday'),cutoff) for symbol in market}
  for symbol,task in tasks.items():
   try:series[symbol]['intraday']=task.result()
   except Exception as error:
    intraday_errors[symbol]=str(error)
    prior=old.get('series',{}).get(symbol,{}).get('intraday')
    if prior:series[symbol]['intraday']=prior
 # Existing industry/sector holdings remain in their original payloads. Add
 # holdings for the newly introduced market and segment ETFs here.
 from etf_strength import fetch_fund_holdings, enrich_holdings
 existing_holdings=set()
 for source in ['outputs/etf/themes_snapshots.json','outputs/etf/sectors_snapshots.json']:
  if Path(source).exists():existing_holdings.update(json.loads(Path(source).read_text()).get('holdings',{}))
 target=set(dict(GROUPS['market']+GROUPS['segments'])) | (set(symbols)-existing_holdings)
 with ThreadPoolExecutor(max_workers=4) as pool:
  funds=dict(zip(sorted(target),pool.map(lambda symbol:fetch_fund_holdings(symbol,set(symbols)),sorted(target))))
 holdings=enrich_holdings({'funds':funds},date.fromisoformat(series['RSP']['history'][-1]['date']),target)
 payload=dict(intraday_errors=intraday_errors,holdings=holdings,holdings_checked_at=datetime.now(ZoneInfo('UTC')).date().isoformat(),benchmark='RSP',generated_at=datetime.now(ZoneInfo('UTC')).isoformat(),groups={k:[dict(symbol=s,name=n) for s,n in v] for k,v in GROUPS.items()},series=series,errors=errors)
 path.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False)+'\n')
if __name__=='__main__':main()
