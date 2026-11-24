# NEL custom scans

Open [the local dashboard](http://127.0.0.1:8765/#scans). From the NEL repository root,
start the scheduler and dashboard with `.venv/bin/python nel2/serve.py` if the
macOS service is unloaded. Run `.venv/bin/python nel2/serve.py --once` to check
for due scans without starting another server.

The service for the current Mac login is `com.nel.scan-v2`. If it needs to be
loaded again, run the following from the repository root.

```sh
launchctl bootstrap "gui/$(id -u)" "$PWD/nel2/.local/com.nel.scan-v2.plist"
```

## Schedule

Times are New York time. The scanner checks once a minute while the Mac is awake.
Potent runs 20 minutes after a regular or early close, allowing delayed quotes to
settle. Leader runs alongside Potent on the last trading session of the week.
Pre-market starts at 9:00 a.m. and can retry until 9:15 a.m. After a missed close,
the service can catch up before the next regular session if TradingView still has
the required daily bars. TradingView pre-market quotes can be delayed. The
dashboard shows each scan's session and actual capture time.

## Watchlist

All scans query TradingView's America stock feed directly and apply only the
custom scan filters. The existing NEL screener universe is independent. Dollar volume is completed-session close times regular-session share
volume. The pre-market scan checks liquidity and bucket placement using the prior
completed session.

Every scan excludes biotech industries and requires weekly volatility above 3.5%
and a completed-session move from open to close strictly outside −0.5% to +0.5%.
For pre-market, these checks use the prior completed regular session.

The Leader cutoff rounds up to the next whole ticker among eligible names with
monthly returns, using ticker ascending to break ties. Exactly $500M qualifies
for Superliquid. A missing EMA or dollar volume, or liquidity at or below $100M,
puts a retained name outside the six buckets until its data qualifies again.

Scan results, latest watchlist membership and one completed-close bucket snapshot
per session are in the local SQLite database `.local/custom-scans.sqlite3`. Each ticker
retains the latest hit date per scan. After-close snapshots preserve point-in-time
membership and bucket assignments for future migration analysis. Service output
is in `.local/scanner.log`.

The Scans table and chart cards include ADR% and the stock ATR Extension Index. ADR%
uses TradingView's ADRP when captured and otherwise uses the 14-session average
high–low range divided by the session close. The ATR Extension Index shares
the historical ranking used by NEL’s Market Strength index view. It runs
continuously from −1 to +1, centered on the 50-day SMA, with extension
multiples in a separate ATR Ext column. Positive and negative extensions are ranked separately.
Daily histories come from Yahoo Finance through each completed scan session and
can differ from TradingView daily histories. The service
caches results by ticker and session and shows a dash while history is unavailable.

During the regular session, the three performance columns use delayed TradingView
quotes when available. 1D change compares with the previous regular close,
intraday change compares with the current regular-session open, and 1M uses
TradingView's monthly performance. The table falls back to the latest completed
session before current-session quotes arrive.

## GitHub Pages

The existing NEL site reads `outputs/scan_watchlist.json`. The Refresh Scans
watchlist workflow rebuilds the snapshot from the latest published state, runs
any due scans, and publishes delayed regular-session returns about every 15
minutes. GitHub Actions queue and Pages build times can delay those updates.
Daily bucket membership is archived in `outputs/scan_bucket_history/`.
Use `python nel2/publish.py --seed-local` to initialize a new deployment from
the local database.
