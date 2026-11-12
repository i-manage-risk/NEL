#!/usr/bin/env python3
"""Run the daily scanner once, 10 minutes after a regular US market close."""

from __future__ import annotations

import os
import json
import time
import subprocess
import sys
from datetime import date, datetime, timedelta
from pathlib import Path
from zoneinfo import ZoneInfo


PROJECT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_DIR / "logs"
MARKER = PROJECT_DIR / "outputs" / ".last_scheduled_run.txt"
LOCK_DIR = PROJECT_DIR / ".daily_scan.lock"
NY_TZ = ZoneInfo("America/New_York")


def nth_weekday(year: int, month: int, weekday: int, occurrence: int) -> date:
    current = date(year, month, 1)
    while current.weekday() != weekday:
        current += timedelta(days=1)
    return current + timedelta(days=7 * (occurrence - 1))


def last_weekday(year: int, month: int, weekday: int) -> date:
    current = date(year, month + 1, 1) - timedelta(days=1) if month < 12 else date(year, 12, 31)
    while current.weekday() != weekday:
        current -= timedelta(days=1)
    return current


def observed(day: date) -> date:
    if day.weekday() == 5:
        return day - timedelta(days=1)
    if day.weekday() == 6:
        return day + timedelta(days=1)
    return day


def easter_sunday(year: int) -> date:
    """Return Western Easter using the Meeus/Jones/Butcher algorithm."""
    a = year % 19
    b, c = divmod(year, 100)
    d, e = divmod(b, 4)
    f = (b + 8) // 25
    g = (b - f + 1) // 3
    h = (19 * a + b - d - g + 15) % 30
    i, k = divmod(c, 4)
    l = (32 + 2 * e + 2 * i - h - k) % 7
    m = (a + 11 * h + 22 * l) // 451
    month = (h + l - 7 * m + 114) // 31
    day = (h + l - 7 * m + 114) % 31 + 1
    return date(year, month, day)


def nyse_holidays(year: int) -> set[date]:
    return {
        observed(date(year, 1, 1)),
        observed(date(year + 1, 1, 1)),
        nth_weekday(year, 1, 0, 3),
        nth_weekday(year, 2, 0, 3),
        easter_sunday(year) - timedelta(days=2),
        last_weekday(year, 5, 0),
        observed(date(year, 6, 19)),
        observed(date(year, 7, 4)),
        nth_weekday(year, 9, 0, 1),
        nth_weekday(year, 11, 3, 4),
        observed(date(year, 12, 25)),
    }


def scheduled_close(now: datetime) -> date | None:
    """Allow post-close retries and overnight catch-up, never an intraday stock scan."""
    now = now.astimezone(NY_TZ)
    if (9, 0) <= (now.hour, now.minute) < (16, 25):
        return None
    candidate = now.date()
    if (now.hour, now.minute) < (16, 25):
        candidate -= timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in nyse_holidays(candidate.year):
        candidate -= timedelta(days=1)
    return candidate


def should_run(now: datetime) -> bool:
    return scheduled_close(now) is not None


def next_session_date(now: datetime) -> date:
    """Return the next regular NYSE session date after today's close.

    A Friday post-close scan is therefore labelled for Monday, rather than
    for Saturday in Pakistan time.  The same applies to US market holidays.
    """
    candidate = now.astimezone(NY_TZ).date() + timedelta(days=1)
    while candidate.weekday() >= 5 or candidate in nyse_holidays(candidate.year):
        candidate += timedelta(days=1)
    return candidate


def main() -> int:
    now = datetime.now(NY_TZ)
    close = scheduled_close(now)
    if close is None:
        print("Skipping stock scan during the trading/pre-close window.", flush=True)
        return 0
    stamp = next_session_date(datetime.combine(close, datetime.min.time(), NY_TZ)).isoformat()
    LOG_DIR.mkdir(exist_ok=True)
    MARKER.parent.mkdir(exist_ok=True)
    state_path = MARKER.parent / '.scan-state.json'
    state = json.loads(state_path.read_text()) if state_path.exists() else {}
    if state.get('close') != close.isoformat() or os.environ.get('FORCE_STOCK_REFRESH') == 'true':
        state = {'close': close.isoformat(), 'completed': []}
    try:
        LOCK_DIR.mkdir()
    except FileExistsError:
        print("Another scanner process holds the local lock.", flush=True)
        return 1
    failures = []
    try:
        scanner_python = PROJECT_DIR / '.venv' / 'bin' / 'python'
        if not scanner_python.exists():
            scanner_python = Path(sys.executable)
        stages = [(name, [script, '--snapshot-date', stamp]) for name,script in [
            ('NEL','focus_list.py'), ('KK','kk_scan.py'), ('OSB','obc_scan.py'),
            ('Top D','top_d.py'), ('Superliquid','super_liquid.py')]]
        stages.append(('ETF studies', ['etf_strength.py','--close-date',close.isoformat()]))
        with (LOG_DIR / f'daily_scan_{close.isoformat()}.log').open('a', encoding='utf-8') as log:
            for name,args in stages:
                if name in state['completed']:
                    print(f'{name}: already refreshed for {close}; keeping completed output.', flush=True)
                    continue
                for attempt in range(1,3):
                    message=f'--- {name}: close {close}, attempt {attempt}/2 ---'
                    print(message, flush=True);log.write(message+'\n');log.flush()
                    process=subprocess.Popen([str(scanner_python),'-u',*args],cwd=PROJECT_DIR,
                        stdout=subprocess.PIPE,stderr=subprocess.STDOUT,text=True)
                    for line in process.stdout:
                        print(line,end='',flush=True);log.write(line);log.flush()
                    code=process.wait()
                    if code == 0:
                        state['completed'].append(name)
                        state_path.write_text(json.dumps(state))
                        break
                    if attempt == 1:
                        print(f'{name}: retrying after failure (exit {code}).',flush=True)
                        time.sleep(10)
                if code:
                    failures.append(name)
            state['failed']=failures
            state_path.write_text(json.dumps(state))
        if not failures:
            MARKER.write_text(close.isoformat()+'\n',encoding='utf-8')
        print('Refresh complete.' if not failures else 'Refresh incomplete: '+', '.join(failures),flush=True)
        return int(bool(failures))
    finally:
        LOCK_DIR.rmdir()


if __name__ == '__main__':
    sys.exit(main())
