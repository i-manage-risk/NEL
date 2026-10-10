# Market workspace

The home page organizes research into Briefing, Environment, Leadership,
Positioning, Screener and Review. Existing detailed pages and historical CSVs
remain available. Stock details default to one window and one section; use
All windows / All sections for the expanded view.

## Data preservation and refresh

`python workspace_data.py` rebuilds an additive `outputs/workspace.json` and
the homepage from saved scans; it does not write to original scan files.
The daily workflow runs this after scanning. Benchmark context is optional:
if its refresh fails, the previous dated dataset remains visibly dated.
CFTC refresh runs Friday evening with a Saturday retry. Breadth retains its
existing late-publication polling workflow.

Stock dates label the next session; the workspace derives the preceding NYSE
session as the close date. ETF and breadth selection never exceeds that close.
COT is explicitly latest-published context, not a historical backtest.

## Definitions and limitations

- The briefing is a custom rule-based review aid inspired by the supplied
  Stockbee specification, not an independently validated trading strategy.
- Relative return is the ETF return minus SPY return in percentage points.
  Rankings do not measure capital flows or predict probabilities of profit.
- COT uses official CFTC Legacy futures-only net positions and a transparent
  156-report minimum/maximum range index. It is **not** CMR's proprietary
  oscillator. Commercial and speculative net positions balance each other;
  they are not independent confirmations. Price confirmation remains manual.
- The requested 20-day breadth symbols lack a verified accessible feed.
  They are marked unavailable, not replaced by T2108 (40-day breadth).
- Three owner-provided Crypto classifications seed the editable taxonomy.
  Unreviewed stocks retain explicitly marked vendor groups. Local edits have
  effective dates and do not overwrite original data. Existing detailed tables
  retain their vendor classifications; the custom grouping is in the workspace.
- Notes, watchlist, screens and classification edits are browser-local. Export
  a backup from Review. They do not sync to the repository or other devices.
- The exact Jeff Sun RS Thrust formula was not verified or reproduced.

## Primary references

- [CFTC Commitments of Traders](https://www.cftc.gov/MarketReports/CommitmentsofTraders/index.htm)
- [Official Legacy futures-only API](https://publicreporting.cftc.gov/resource/6dca-aqww.json)
- [CMR member methodology guide](https://www.crowdedmarketreport.com/wp-content/uploads/2023/04/CMR-New-Member-Guide-2023.pdf)
- [Stockbee Market Monitor](https://stockbee.blogspot.com/p/mm.html)

User-supplied `groups.txt`, COT script and Stockbee specification inform the
configuration but are not represented as official source methodology.
