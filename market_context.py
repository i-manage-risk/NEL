"""Regular-session benchmark comparisons for the trading workspace."""
import json
from datetime import date, timedelta, datetime, timezone
from pathlib import Path
from etf_strength import download_prices, build_metric_history, expected_completed_session, validate_actual_close

def main():
    close = expected_completed_session()
    symbols = {'SPY':'S&P 500', 'RSP':'S&P 500 equal weight', 'QQQ':'Nasdaq 100', 'QQQE':'Nasdaq equal weight', 'IWM':'Small caps', 'DIA':'Dow 30', 'TLT':'Long Treasury bonds', 'GLD':'Gold', 'SLV':'Silver', 'IBIT':'Bitcoin', 'ETHA':'Ether', 'USO':'Crude oil', 'UNG':'Natural gas'}
    prices, errors = download_prices(symbols, close-timedelta(days=600), close)
    validate_actual_close(prices, close)
    rows = []
    for symbol, history in prices.items():
        metrics = build_metric_history(history).iloc[-1]
        rows.append({'symbol':symbol,'name':symbols[symbol],'date':history.index[-1].date().isoformat(),'performance':{key:float(metrics[f'perf_{key}']) for key in ['1w','1m','3m','6m','1y']}})
    target=Path(__file__).resolve().parent/'outputs'/'market_context.json'
    target.write_text(json.dumps({'date':close.isoformat(),'benchmarks':rows,'unavailable':sorted(errors)},allow_nan=False,separators=(',',':')))

if __name__ == '__main__':
    main()
