"""Liquidity-first top 2% price leaders; separate from NELL and its filters."""
import argparse,json,math
from datetime import datetime,timedelta
from pathlib import Path
import pandas as pd
ROOT=Path(__file__).resolve().parent
PERIODS={'1d':'change','1w':'Perf.W','1m':'Perf.1M','3m':'Perf.3M','6m':'Perf.6M','ytd':'Perf.YTD','1y':'Perf.Y','3y':'Perf.3Y','5y':'Perf.5Y','10y':'Perf.10Y','all':'Perf.All'}
def select_leaders(raw):
    frame=raw.copy()
    for c in ['SMA30','average_volume_30d_calc','average_volume_10d_calc',*PERIODS.values()]:frame[c]=pd.to_numeric(frame[c],errors='coerce')
    frame['dollarVolume']=frame.SMA30*frame.average_volume_30d_calc
    frame=frame[(frame.dollarVolume>100e6)&(frame.average_volume_10d_calc>1e6)].drop_duplicates('name').copy()
    selected={};counts={}
    for period,column in PERIODS.items():
        valid=frame.dropna(subset=[column]).sort_values([column,'name'],ascending=[False,True])
        n=math.ceil(len(valid)*.02);counts[period]={'eligible':len(valid),'selected':n}
        selected[period]=valid.head(n)['name'].tolist()
    return frame,selected,counts

def build(snapshot_date=None,close_date=None):
    from tradingview_screener import Query,col
    import yfinance as yf
    from scripts.run_after_close import scheduled_close,NY_TZ,nyse_holidays
    close=close_date or scheduled_close(datetime.now(NY_TZ))
    if isinstance(close,str):close=datetime.fromisoformat(close).date()
    if snapshot_date:
        close=datetime.fromisoformat(snapshot_date).date()-timedelta(days=1)
        while close.weekday()>4 or close in nyse_holidays(close.year):close-=timedelta(days=1)
    if close is None:raise RuntimeError('Wait until the completed-close scan window.')
    columns=['name','description','industry','exchange','close','SMA30','SMA50','ADRP','ATRP','average_volume_30d_calc','average_volume_10d_calc','first_bar_time',*PERIODS.values()]
    total,raw=Query().set_markets('america').select(*columns).where(col('type')=='stock',col('exchange').isin(['NASDAQ','NYSE','AMEX']),col('average_volume_10d_calc')>1e6).limit(20000).get_scanner_data()
    if total>len(raw):raise RuntimeError('Incomplete scan: source universe exceeded query limit.')
    universe,leaders,counts=select_leaders(raw)
    if universe.empty:raise RuntimeError('Empty liquid universe; preserving previous data.')
    hist=yf.Ticker('RSP').history(period='max',auto_adjust=False)
    hist.index=hist.index.tz_localize(None).normalize();hist=hist.loc[hist.index<=pd.Timestamp(close)]
    if hist.empty or hist.index[-1].date()!=close:raise RuntimeError('RSP close is stale; preserving previous data.')
    last=float(hist.Close.iloc[-1]);end=hist.index[-1]
    def ret(start):
        eligible=hist.loc[hist.index<=start]
        return (last/float(eligible.Close.iloc[-1])-1)*100 if not eligible.empty else None
    baseline={}
    for k in PERIODS:
        if k=='1d':start=hist.index[-2]
        elif k=='ytd':start=pd.Timestamp(end.year,1,1)-pd.Timedelta(days=1)
        elif k=='all':continue
        else:
            n=int(k[:-1]);unit=k[-1];start=end-(pd.DateOffset(weeks=n) if unit=='w' else pd.DateOffset(months=n) if unit=='m' else pd.DateOffset(years=n))
        baseline[k]=ret(start)
    symbols=set(sum(leaders.values(),[]));rows=[]
    def number(x):return round(float(x),5) if pd.notna(x) and math.isfinite(float(x)) else None
    for _,r in universe[universe.name.isin(symbols)].iterrows():
        performance={k:number(r[c]) for k,c in PERIODS.items()};rs={k:number(performance[k]-baseline[k]) if performance[k] is not None and baseline.get(k) is not None else None for k in PERIODS}
        start=pd.Timestamp(r.first_bar_time,unit='s').normalize() if pd.notna(r.first_bar_time) else None
        if start is not None and start>=hist.index[0]:
            b=ret(start);rs['all']=number(performance['all']-b) if b is not None and performance['all'] is not None else None
        denom=r.SMA50*r.ATRP/100
        rows.append({'symbol':r['name'],'name':r.description,'industry':r.industry,'performance':performance,'rs':rs,'dollarVolume':number(r.dollarVolume),'shareVolume':number(r.average_volume_10d_calc),'adr':number(r.ADRP),'extension':number((r.close-r.SMA50)/denom) if denom>0 else None})
    target=ROOT/'outputs/liquid_leadership.json';payload=json.loads(target.read_text()) if target.exists() else {'snapshots':[]}
    snapshot={'date':str(close),'universe':len(universe),'counts':counts,'leaders':leaders,'rows':rows,'benchmark':baseline}
    payload['snapshots']=[s for s in payload['snapshots'] if s['date']!=str(close)]+[snapshot];payload['snapshots'].sort(key=lambda s:s['date']);payload['generatedAt']=datetime.now().isoformat()
    target.write_text(json.dumps(payload,separators=(',',':'),allow_nan=False));print(f'Liquid Leadership: {len(universe)} liquid stocks, {len(rows)} unique leaders, close {close}')
if __name__=='__main__':
    p=argparse.ArgumentParser();p.add_argument('--snapshot-date');p.add_argument('--close-date');a=p.parse_args();build(a.snapshot_date,a.close_date)
