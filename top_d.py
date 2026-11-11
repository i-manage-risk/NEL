"""Top D: independently scan liquid stocks for demonstrated power and trend character."""
from __future__ import annotations
import argparse
import json
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
import numpy as np
import pandas as pd
import yfinance as yf
from tight_nel import calculate_coil_metrics


def character_metrics(history: pd.DataFrame, benchmark: pd.DataFrame, cutoff: str) -> dict:
    """Split-adjusted OHLC, only completed sessions through cutoff; no forward outcomes."""
    h=history.copy().sort_index();h=h.loc[h.index.strftime('%Y-%m-%d')<=cutoff]
    b=benchmark.copy().sort_index();b=b.loc[b.index.strftime('%Y-%m-%d')<=cutoff]
    h=h.dropna(subset=['Close','High','Low']); c=h.Close
    if len(c)<61: raise ValueError('Fewer than 61 daily sessions')
    if c.index[-1].strftime('%Y-%m-%d')!=cutoff: raise ValueError('Latest stock close is stale')
    if b.empty or b.index[-1].strftime('%Y-%m-%d')!=cutoff: raise ValueError('Latest RSP close is stale')
    recent=c.iloc[-253:]
    runs=c.pct_change(20).reindex(recent.index).dropna()
    best=float(runs.max()*100)
    efficiencies=[];coverage=np.zeros(len(c)+1,dtype=int)
    for n,threshold in [(20,.10),(60,.20)]:
        gains=c-c.shift(n);travel=c.diff().abs().rolling(n).sum()
        advancing=(c/c.shift(n)-1)>=threshold
        efficiency=(gains/travel.replace(0,np.nan)).where(advancing).reindex(recent.index).dropna()
        if not efficiency.empty: efficiencies.append(float(efficiency.median()))
        # Assess MA behavior on actual advancing windows, rather than quiet flat periods.
        ends=np.flatnonzero(advancing.to_numpy())
        ends=ends[ends>=max(0,len(c)-253)]
        np.add.at(coverage,np.maximum(0,ends-n),1)
        np.add.at(coverage,ends+1,-1)
    mask=pd.Series(np.cumsum(coverage[:-1])>0,index=c.index) & (c.index>=recent.index[0])
    respects=[];crosses=[];break_depth=[]
    tr=pd.concat([h.High-h.Low,(h.High-c.shift()).abs(),(h.Low-c.shift()).abs()],axis=1).max(axis=1)
    atr=tr.ewm(alpha=1/14,adjust=False,min_periods=14).mean()
    for n in (10,20):
        ma=c.rolling(n).mean();eligible=mask & ma.notna() & (ma>ma.shift(5))
        respects.append(float((c[eligible]>=ma[eligible]).mean()*100) if eligible.any() else None)
        crosses.append(int(((c<ma)&(c.shift()>=ma.shift())&eligible).sum()))
        depth=((ma-c).clip(lower=0)/atr).where(eligible).dropna()
        break_depth.append(float(depth.mean()) if len(depth) else None)
    # Friday-to-Friday returns, excluding an unfinished current week; common endpoints only.
    aligned=pd.concat([c.rename('stock'),b.Close.rename('rsp')],axis=1).dropna()
    weekly=aligned.resample('W-FRI').last()
    weekly=weekly.loc[weekly.index.strftime('%Y-%m-%d')<=cutoff].pct_change(fill_method=None).tail(52).dropna()
    up=weekly.loc[weekly.rsp>0];down=weekly.loc[weekly.rsp<0]
    coil=calculate_coil_metrics(h.rename(columns=str.lower))
    smooth=float(np.mean(efficiencies)*100) if efficiencies else None
    respect=float(np.mean([v for v in respects if v is not None])) if any(v is not None for v in respects) else None
    result={'historySessions':len(recent),'best20d':best,'smoothness':smooth,'respect':respect,
        'respect10':respects[0],'respect20':respects[1],'breaks10':crosses[0],'breaks20':crosses[1],
        'breakDepth10':break_depth[0],'breakDepth20':break_depth[1],
        'upWeeks':len(up),'upReturn':float(up.stock.mean()*100) if len(up)>=6 else None,
        'upBeatRate':float((up.stock>up.rsp).mean()*100) if len(up)>=6 else None,
        'downReturn':float(down.stock.mean()*100) if len(down)>=6 else None,
        'character':'Smooth trender' if smooth is not None and respect is not None and smooth>=35 and respect>=75 else 'Explosive / choppy',
        'tight':bool(coil and coil.get('is_tight_nel'))}
    return result


def rank_records(rows: list[dict]) -> list[dict]:
    if not rows:return []
    f=pd.DataFrame(rows)
    # Explicit cross-sectional ranking, not a forecast or probability of success.
    score=pd.Series(0.,index=f.index)
    for key,weight in [('best20d',.30),('smoothness',.30),('upReturn',.125),('upBeatRate',.125),('respect',.15)]:
        score+=f[key].rank(pct=True)*100*weight
    f['score']=score
    return f.sort_values(['score','symbol'],ascending=[False,True],na_position='last').replace({np.nan:None}).to_dict('records')


def main():
    p=argparse.ArgumentParser();p.add_argument('--snapshot-date',required=True);p.add_argument('--close-date');p.add_argument('--output-dir',type=Path,default=Path('outputs'));args=p.parse_args()
    from scripts.run_after_close import nyse_holidays
    close=date.fromisoformat(args.close_date) if args.close_date else date.fromisoformat(args.snapshot_date)-timedelta(days=1)
    while close.weekday()>4 or close in nyse_holidays(close.year):close-=timedelta(days=1)
    cutoff=close.isoformat()
    # Use the independent broad liquidity universe, never the KK or OSB leader subset.
    source=args.output_dir/f'stock_universe_{args.snapshot_date}.csv'
    archived_fallback=not source.exists()
    if archived_fallback:source=args.output_dir/f'obc_universe_{args.snapshot_date}.csv'
    raw=pd.read_csv(source)
    raw['average_dollar_volume_30d']=pd.to_numeric(raw.SMA30,errors='coerce')*pd.to_numeric(raw.average_volume_30d_calc,errors='coerce')
    raw['average_volume_10d_calc']=pd.to_numeric(raw.average_volume_10d_calc,errors='coerce')
    raw['atr_extension_from_50d']=(pd.to_numeric(raw['close'],errors='coerce')-pd.to_numeric(raw.SMA50,errors='coerce'))/(pd.to_numeric(raw.SMA50,errors='coerce')*pd.to_numeric(raw.ATRP,errors='coerce')/100)
    raw=raw.drop_duplicates('name')
    raw=raw.loc[(raw.average_dollar_volume_30d>=30e6)&(raw.average_volume_10d_calc>=350000)].copy()
    symbols=raw.name.drop_duplicates().tolist(); histories={};errors={}
    start=(close-timedelta(days=760)).isoformat();end=(close+timedelta(days=1)).isoformat()
    cache=Path('/tmp/nel-top-d-history')/cutoff;cache.mkdir(parents=True,exist_ok=True)
    for symbol in ['RSP']+symbols:
        cached=cache/(symbol.replace('/','_')+'.csv')
        if cached.exists():histories[symbol]=pd.read_csv(cached,index_col=0,parse_dates=True)
    pending=[symbol for symbol in ['RSP']+symbols if symbol not in histories]
    for i in range(0,len(pending),60):
        batch=pending[i:i+60]
        if not batch:continue
        mapping={s.replace('.','-'):s for s in batch}
        data=yf.download(list(mapping),start=start,end=end,auto_adjust=True,actions=False,group_by='ticker',threads=8,progress=False,timeout=25)
        for yahoo,symbol in mapping.items():
            try:
                frame=data[yahoo] if isinstance(data.columns,pd.MultiIndex) else data
                frame.index=pd.to_datetime(frame.index).tz_localize(None)
                histories[symbol]=frame
                frame.to_csv(cache/(symbol.replace('/','_')+'.csv'))
            except Exception as exc:errors[symbol]=str(exc)
        print(f'Top D history {min(i+60,len(pending))}/{len(pending)}',flush=True)
    if 'RSP' not in histories:raise RuntimeError('RSP history unavailable')
    rows=[]
    for _,r in raw.iterrows():
        symbol=r['name']
        try:
            m=character_metrics(histories[symbol],histories['RSP'],cutoff)
            if m['best20d']<30:continue
            rows.append({'symbol':symbol,'industry':r.get('industry','Unclassified'),'description':r.get('description',''),
                'kind':'topd','price':float(r['close']),'adr':float(r.ADRP),'extension':float(r.atr_extension_from_50d),
                'dollarVolume':float(r.average_dollar_volume_30d),'shareVolume':float(r.average_volume_10d_calc),
                'performance':dict(zip(['1w','1m','3m','6m','1y'],[float(r.get(k,np.nan)) for k in ['Perf.W','Perf.1M','Perf.3M','Perf.6M','Perf.Y']])),
                'leaders':[],**m})
        except Exception as exc:errors[symbol]=str(exc)
    if len(errors)>max(20,len(raw)*.25):raise RuntimeError(f'History coverage too low: {len(errors)}/{len(raw)} unavailable; prior outputs preserved')
    def clean(obj):
        if isinstance(obj,dict):return {k:clean(v) for k,v in obj.items()}
        if isinstance(obj,list):return [clean(v) for v in obj]
        if isinstance(obj,float) and not np.isfinite(obj):return None
        return obj
    payload={'closeDate':cutoff,'snapshotDate':args.snapshot_date,'generatedAt':datetime.now(timezone.utc).isoformat(),
        'source':'Saved broad TradingView universe; Yahoo split-adjusted daily history; RSP benchmark',
        'archivedUniverseFallback':archived_fallback,'universeCount':len(raw),'errors':errors,'rows':rank_records(rows)}
    path=args.output_dir/f'top_d_{args.snapshot_date}.json';path.write_text(json.dumps(clean(payload),allow_nan=False,separators=(',',':')))
    print(f'Saved {len(rows)} proven movers; {len(errors)} unavailable: {path}')
if __name__=='__main__':main()
