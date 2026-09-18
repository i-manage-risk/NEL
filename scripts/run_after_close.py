#!/usr/bin/env python3
"""Run the daily scanner once, 10 minutes after a regular US market close."""

from __future__ import annotations

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


def should_run(now: datetime) -> bool:
    return (
        now.weekday() < 5
        and now.date() not in nyse_holidays(now.year)
        and (now.hour, now.minute) >= (16, 10)
    )


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
    if not should_run(now):
        return 0
    LOG_DIR.mkdir(exist_ok=True)
    MARKER.parent.mkdir(exist_ok=True)
    if MARKER.exists() and MARKER.read_text(encoding="utf-8").strip() == now.date().isoformat():
        return 0
    try:
        LOCK_DIR.mkdir()
    except FileExistsError:
        return 0
    try:
        log_path = LOG_DIR / f"daily_scan_{now.date().isoformat()}.log"
        local_python = PROJECT_DIR / ".venv" / "bin" / "python"
        scanner_python = local_python if local_python.exists() else Path(sys.executable)
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n--- Scheduled run started {now.isoformat()} ---\n")
            result = subprocess.run(
                [str(scanner_python), "focus_list.py", "--snapshot-date", next_session_date(now).isoformat()],
                cwd=PROJECT_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            log.write(f"--- Scheduled run finished with exit code {result.returncode} ---\n")
        if result.returncode == 0:
            MARKER.write_text(now.date().isoformat() + "\n", encoding="utf-8")
        return result.returncode
    finally:
        LOCK_DIR.rmdir()


if __name__ == "__main__":
    sys.exit(main())
