"""Publish only the inputs the Debrief needs for its saved session selector."""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def build(outputs):
    def read(name):
        return json.loads((outputs / name).read_text())

    calendar = read("workspace_calendar.json")["snapshots"]
    first_close = min(row.get("closeDate") or row["date"] for row in calendar)

    def window(rows, date_key, previous):
        ordered = sorted(rows, key=lambda row: row[date_key])
        past = [row for row in ordered if row[date_key] < first_close]
        return past[-previous:] + [row for row in ordered if row[date_key] >= first_close]

    flow = read("flow_market.json")
    symbols = {entry["symbol"] for group in flow["groups"].values() for entry in group} | {"RSP"}
    series = {}
    for symbol, source in flow["series"].items():
        if symbol not in symbols:
            continue
        rows = window(source["history"], "date", 23)
        series[symbol] = {
            "name": source["name"],
            "history": [{key: row.get(key) for key in ("date", "close", "extension", "oscillator")} for row in rows],
        }
        intraday = source.get("intraday", {}).get("sessions", {})
        if intraday:
            series[symbol]["intraday"] = {"sessions": {day: bars for day, bars in intraday.items() if day >= first_close}}

    markets = []
    for market in read("positioning.json")["markets"]:
        rows = window(market["history"], "date", 3)
        markets.append({
            **{key: market[key] for key in ("name", "etf", "code")},
            "history": [{
                "date": row["date"],
                "release_date": row.get("release_date"),
                "participants": {key: {"indices": {"5y": row["participants"].get(key, {}).get("indices", {}).get("5y")}}
                                 for key in ("large", "commercials", "small")},
            } for row in rows],
        })
    return {
        "market": {"series": series, "groups": flow["groups"]},
        "breadth": window(read("breadth_market_monitor.json"), "date", 1),
        "cot": {"markets": markets},
    }


def main():
    outputs = ROOT / "outputs"
    target = outputs / "debrief_data.json"
    body = json.dumps(build(outputs), separators=(",", ":"), allow_nan=False) + "\n"
    if not target.exists() or target.read_text() != body:
        staged = target.with_suffix(".tmp")
        staged.write_text(body)
        staged.replace(target)
    print(f"Debrief payload: {len(body):,} bytes")


if __name__ == "__main__":
    main()
