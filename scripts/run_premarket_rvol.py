#!/usr/bin/env python3
"""Run the premarket RVOL scanner once at 9:00 AM New York time."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

try:
    # Direct execution: `python scripts/run_premarket_rvol.py`.
    from run_after_close import NY_TZ, nyse_holidays
except ModuleNotFoundError:  # pragma: no cover - used when imported by tests.
    from scripts.run_after_close import NY_TZ, nyse_holidays


PROJECT_DIR = Path(__file__).resolve().parents[1]
LOG_DIR = PROJECT_DIR / "logs"
MARKER = PROJECT_DIR / "outputs" / ".last_premarket_rvol_run.txt"
LOCK_DIR = PROJECT_DIR / ".premarket_rvol.lock"


def should_run(now: datetime) -> bool:
    return (
        now.weekday() < 5
        and now.date() not in nyse_holidays(now.year)
        and (now.hour, now.minute) >= (9, 0)
    )


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
        local_python = PROJECT_DIR / ".venv" / "bin" / "python"
        scanner_python = local_python if local_python.exists() else Path(sys.executable)
        log_path = LOG_DIR / f"premarket_rvol_{now.date().isoformat()}.log"
        with log_path.open("a", encoding="utf-8") as log:
            log.write(f"\n--- Premarket RVOL scan started {now.isoformat()} ---\n")
            result = subprocess.run(
                [str(scanner_python), "premarket_rvol.py", "--snapshot-date", now.date().isoformat()],
                cwd=PROJECT_DIR,
                stdout=log,
                stderr=subprocess.STDOUT,
                text=True,
                check=False,
            )
            log.write(f"--- Premarket RVOL scan finished with exit code {result.returncode} ---\n")
        if result.returncode == 0:
            MARKER.write_text(now.date().isoformat() + "\n", encoding="utf-8")
        return result.returncode
    finally:
        LOCK_DIR.rmdir()


if __name__ == "__main__":
    sys.exit(main())
