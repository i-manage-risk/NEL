"""Full available index history; expanding ATR-extension index, no future observations."""
import json
from pathlib import Path
from collections import deque
from bisect import bisect_right, insort
from datetime import datetime
from zoneinfo import ZoneInfo
import yfinance as yf

MARKETS=[('spx','S&P 500 · SPY','SPY'),('nasdaq','Nasdaq 100 · QQQ','QQQ'),('russell','Russell 2000 · IWM','IWM'),('dow','Dow Jones · DIA','DIA')]

def calculate(frame):
    bars=[];closes=deque(maxlen=50);atr=None;seed=[];previous=None;positive=[];negative=[]
    now=datetime.now(ZoneInfo('America/New_York'))
    for stamp,row in frame.iterrows():
        if stamp.date()==now.date() and now.hour<16:continue
        c,h,l=map(float,(row['Close'],row['High'],row['Low']))
        if not all(__import__('math').isfinite(v) for v in (c,h,l)):continue
        tr=h-l if previous is None else max(h-l,abs(h-previous),abs(l-previous));seed.append(tr)
        if atr is None and len(seed)==14:atr=sum(seed)/14
        elif atr is not None:atr=(atr*13+tr)/14
        closes.append(c);sma=sum(closes)/50 if len(closes)==50 else None
        ext=(c-sma)/(sma*(atr/c)) if sma and atr and c>0 else None;score=None
        if ext is not None:
            population=positive if ext>0 else negative
            score=0 if abs(ext)<1e-12 else (1 if ext>0 else -1)*bisect_right(population,abs(ext))/(len(population)+1)
            if ext:insort(population,abs(ext))
        bars.append(dict(date=stamp.date().isoformat(),close=c,extension=ext,oscillator=score));previous=c
    return bars

def main():
    path=Path('outputs/index_history.json');old=json.loads(path.read_text()) if path.exists() else {};result={}
    for code,name,symbol in MARKETS:
        frame=yf.Ticker(symbol).history(period='max',auto_adjust=False,actions=False)
        if frame.empty:
            if code not in old or old[code].get('symbol')!=symbol:raise RuntimeError('Missing full history: '+symbol)
            result[code]=old[code];continue
        bars=calculate(frame)
        result[code]=dict(name=name,symbol=symbol,history=bars);print(name,len(bars),bars[0]['date'],bars[-1]['date'])
    path.write_text(json.dumps(result,separators=(',',':'),allow_nan=False)+'\n')
if __name__=='__main__':main()
