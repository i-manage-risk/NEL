"""Build an additive workspace dataset. Never modify original scanner outputs."""
from __future__ import annotations
import csv
import json
import re
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parent
FRAMES = ('1w', '1m', '3m', '6m', '1y')
PERF = dict(zip(FRAMES, ('Perf.W', 'Perf.1M', 'Perf.3M', 'Perf.6M', 'Perf.Y')))

def read_csv(path):
    if not path.exists():
        return []
    with path.open() as stream:
        return list(csv.DictReader(stream))

def number(value):
    try:
        result = float(value)
        return result if __import__('math').isfinite(result) else None
    except (TypeError, ValueError):
        return None

def build():
    from scripts.run_after_close import nyse_holidays
    snapshots = []
    for path in sorted((ROOT / 'outputs').glob('filtered_universe_*.csv')):
        stamp = re.search(r'\d{4}-\d{2}-\d{2}', path.name)[0]
        records = []
        for kind, prefix in [('liquid', ''), ('super', 'super_liquid_')]:
            tight = {row['name'] for row in read_csv(ROOT / 'outputs' / f'{prefix}tight_non_extended_leaders_{stamp}.csv')}
            for row in read_csv(ROOT / 'outputs' / f'{prefix}filtered_universe_{stamp}.csv'):
                records.append({
                    'symbol': row['name'], 'industry': row.get('industry') or 'Unclassified',
                    'description': row.get('description', ''), 'kind': kind,
                    'pair': row.get('paired_etf') or '', 'price': number(row.get('close')),
                    'adr': number(row.get('ADRP')), 'extension': number(row.get('atr_extension_from_50d')),
                    'dollarVolume': number(row.get('average_dollar_volume_30d')),
                    'performance': {frame: number(row.get(column)) for frame, column in PERF.items()},
                    'leaders': [frame for frame in FRAMES if row.get(f'is_top_{frame}', '').lower() == 'true'],
                    'tight': row['name'] in tight,
                })
        close = date.fromisoformat(stamp) - timedelta(days=1)
        while close.weekday() >= 5 or close in nyse_holidays(close.year):
            close -= timedelta(days=1)
        snapshots.append({'date': stamp, 'closeDate': close.isoformat(), 'stocks': records})
    profiles = json.loads((ROOT / 'data' / 'theme_overrides.json').read_text())
    definitions_path = ROOT / 'data' / 'stock_groups.txt'
    definitions = definitions_path.read_text() if definitions_path.exists() else ''
    groups = [{'name': match[0].strip(), 'description': match[1].strip()} for match in re.findall(r'Group: ([^\n]+)\s+Meaning: ([^\n]+)', definitions)]
    target = ROOT / 'outputs' / 'workspace.json'
    target.write_text(json.dumps({'generatedAt': datetime.now(timezone.utc).isoformat(), 'snapshots': snapshots, 'profiles': profiles, 'groups': groups}, separators=(',', ':'), allow_nan=False))
    (ROOT / 'index.html').write_text((ROOT / 'workspace.html').read_text())
    print(f'Workspace: {len(snapshots)} preserved stock snapshots')

if __name__ == '__main__':
    build()
