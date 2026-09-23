#!/usr/bin/env python3
"""Create one opening RVOL lock after the first five NYSE minutes."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    from run_after_close import NY_TZ, nyse_holidays
except ModuleNotFoundError:  # pragma: no cover - import path for tests.
    from scripts.run_after_close import NY_TZ, nyse_holidays


PROJECT_DIR = Path(__file__).resolve().parents[1]
MARKER = PROJECT_DIR / "outputs" / ".last_opening_rvol_lock.txt"
LOCK_DIR = PROJECT_DIR / ".opening_rvol.lock"


def should_run(now: datetime) -> bool:
    return now.weekday() < 5 and now.date() not in nyse_holidays(now.year) and (now.hour, now.minute) >= (9, 35)


def main() -> int:
    now = datetime.now(NY_TZ)
    if not should_run(now):
        return 0
    MARKER.parent.mkdir(exist_ok=True)
    if MARKER.exists() and MARKER.read_text(encoding="utf-8").strip() == now.date().isoformat():
        return 0
    try:
        LOCK_DIR.mkdir()
    except FileExistsError:
        return 0
    try:
        local_python = PROJECT_DIR / ".venv" / "bin" / "python"
        scanner_python = local_python if local_python.exists() else Path(sys.executable)
        result = subprocess.run(
            [str(scanner_python), "opening_rvol.py", "--market-date", now.date().isoformat(), "--minutes-since-open", str((now.hour * 60 + now.minute) - (9 * 60 + 30))],
            cwd=PROJECT_DIR,
            check=False,
        )
        if result.returncode == 0:
            MARKER.write_text(now.date().isoformat() + "\n", encoding="utf-8")
        return result.returncode
    finally:
        LOCK_DIR.rmdir()


if __name__ == "__main__":
    sys.exit(main())
