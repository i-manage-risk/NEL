#!/usr/bin/env python3
"""Refresh Breadth only during the post-close Stockbee publishing window."""
from datetime import datetime, time
import json
import os
from pathlib import Path
import sys
from zoneinfo import ZoneInfo

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
from breadth_dashboard import OUT, YEAR_GIDS, fetch_year, main


def should_check(now: datetime) -> bool:
    evening_window = now.weekday() < 5 and now.time() >= time(16, 20)
    # Tuesday-Saturday morning is the final catch-up for the preceding
    # Monday-Friday session, including an unusually late Friday publish.
    morning_catch_up = 1 <= now.weekday() <= 5 and now.time() < time(10)
    return evening_window or morning_catch_up


def source_changed(year: int) -> bool:
    if not OUT.exists() or year not in YEAR_GIDS:
        return True
    saved = {row["date"]: row for row in json.loads(OUT.read_text())}
    incoming = fetch_year((year, YEAR_GIDS[year]))
    completed = [row for row in incoming if row["up4"] is not None and row["down4"] is not None]
    if not completed:
        raise RuntimeError("No completed rows returned by Stockbee")
    newest = sorted(completed, key=lambda row: row["date"])[-10:]
    return any(
        row["date"] not in saved or any(value is not None and saved[row["date"]].get(key) != value
                                         for key, value in row.items())
        for row in newest
    )


if __name__ == "__main__":
    new_york = datetime.now(ZoneInfo("America/New_York"))
    if should_check(new_york) or os.environ.get("GITHUB_EVENT_NAME") == "workflow_dispatch":
        print(f"Checking Stockbee after close at {new_york:%Y-%m-%d %H:%M %Z}")
        if source_changed(new_york.year):
            main()
        else:
            print("Published breadth is already current.")
    else:
        print(f"Skipping Breadth refresh before close/weekend at {new_york:%Y-%m-%d %H:%M %Z}")
