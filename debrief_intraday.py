"""Regular-session five-minute ETF traces, archived by actual close date."""
from datetime import datetime
from zoneinfo import ZoneInfo
import math
import yfinance as yf
NY=ZoneInfo('America/New_York')
def fetch_intraday(symbol,previous,cutoff):
    frame=yf.Ticker(symbol).history(period='60d',interval='5m',auto_adjust=False,prepost=False,actions=False)
    if frame.empty:raise ValueError('No five-minute history returned')
    sessions=dict((previous or {}).get('sessions',{}));fresh={}
    for stamp,row in frame.iterrows():
        local=stamp.tz_convert(NY);day=local.date().isoformat();minute=local.hour*60+local.minute
        if day>cutoff or not 570<=minute<960 or not math.isfinite(float(row['Close'])):continue
        fresh.setdefault(day,[]).append([int(stamp.timestamp()),round(float(row['Close']),6)])
    if not fresh:raise ValueError('No completed regular-session intraday bars')
    sessions.update(fresh);sessions={day:sessions[day] for day in sorted(sessions)[-260:]}
    return dict(interval='5m',source='Yahoo Finance',session='regular',sessions=sessions,refreshed_at=datetime.now(ZoneInfo('UTC')).isoformat())
