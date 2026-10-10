"""Official CFTC Legacy Futures Only, 156-report net-position range index."""
from __future__ import annotations
import json
from datetime import datetime, timedelta, timezone
from pathlib import Path
import requests

ROOT = Path(__file__).resolve().parent
ENDPOINT = 'https://publicreporting.cftc.gov/resource/6dca-aqww.json'
MARKETS = {
    '13874A': ('S&P 500', 'SPY', 'Equity index'),
    '209742': ('Nasdaq 100', 'QQQ', 'Equity index'),
    '239742': ('Russell 2000', 'IWM', 'Equity index'),
    '088691': ('Gold', 'GLD', 'Metals'),
    '084691': ('Silver', 'SLV', 'Metals'),
    '085692': ('Copper', 'CPER', 'Metals'),
    '067651': ('WTI crude oil', 'USO', 'Energy'),
    '023651': ('Natural gas', 'UNG', 'Energy'),
    '133741': ('Bitcoin', 'IBIT', 'Crypto'),
    '146021': ('Ether', 'ETHA', 'Crypto'),
}
PARTICIPANTS = {'commercials': 'comm', 'large': 'noncomm', 'small': 'nonrept'}

def range_index(values, length=156):
    if len(values) < length:
        return None
    window = values[-length:]
    low, high = min(window), max(window)
    return round(100 * (window[-1] - low) / (high - low), 2) if high != low else None

def build_market(code, rows):
    name, etf, group = MARKETS[code]
    dates = [row['report_date_as_yyyy_mm_dd'][:10] for row in rows]
    if len(set(dates)) != len(dates):
        raise ValueError(f'Duplicate weekly reports for {code}')
    history, running = [], {key: [] for key in PARTICIPANTS}
    for row in sorted(rows, key=lambda r: r['report_date_as_yyyy_mm_dd']):
        participants = {}
        for key, prefix in PARTICIPANTS.items():
            long = int(row[f'{prefix}_positions_long_all'])
            short = int(row[f'{prefix}_positions_short_all'])
            net = long - short
            running[key].append(net)
            participants[key] = {'long': long, 'short': short, 'net': net, 'index': range_index(running[key]), 'netPctOI': round(100 * net / int(row['open_interest_all']), 2) if int(row['open_interest_all']) else None}
        if sum(item['net'] for item in participants.values()) != 0:
            raise ValueError(f'Position balance failed for {code}')
        history.append({'date': row['report_date_as_yyyy_mm_dd'][:10], 'participants': participants})
    return {'name': name, 'etf': etf, 'group': group, 'code': code, 'contract': rows[-1]['market_and_exchange_names'] if rows else '', 'history': history[-157:], 'reports': len(rows)}

def main():
    start = (datetime.now(timezone.utc) - timedelta(weeks=320)).date().isoformat()
    codes = ','.join(f"'{code}'" for code in MARKETS)
    columns = ['market_and_exchange_names','cftc_contract_market_code','report_date_as_yyyy_mm_dd','open_interest_all','futonly_or_combined']
    columns += [f'{prefix}_positions_{side}_all' for prefix in PARTICIPANTS.values() for side in ['long','short']]
    response = requests.get(ENDPOINT, params={'$select': ','.join(columns), '$where': f"cftc_contract_market_code in ({codes}) AND report_date_as_yyyy_mm_dd >= '{start}T00:00:00'", '$order': 'report_date_as_yyyy_mm_dd ASC', '$limit': 10000}, timeout=60)
    response.raise_for_status()
    rows = response.json()
    if not rows or any(row['futonly_or_combined'] != 'FutOnly' for row in rows):
        raise ValueError('Missing or unexpected official report type')
    markets = [build_market(code, [row for row in rows if row['cftc_contract_market_code'] == code]) for code in MARKETS]
    if any(not market['history'] for market in markets):
        raise ValueError('Missing CFTC market; preserve previous complete dataset')
    payload = {'source': ENDPOINT, 'fetchedAt': datetime.now(timezone.utc).isoformat(), 'lookback': 156, 'reportType': 'Legacy futures only', 'markets': markets}
    target = ROOT / 'outputs' / 'positioning.json'
    temp = target.with_suffix('.tmp')
    temp.write_text(json.dumps(payload, separators=(',', ':'), allow_nan=False))
    temp.replace(target)
    print(f'Official CFTC: {len(markets)} markets, latest report {max(m["history"][-1]["date"] for m in markets)}')

if __name__ == '__main__':
    main()
