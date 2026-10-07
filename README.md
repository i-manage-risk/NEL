# Non-Extended Leaders (NEL)

This daily scanner recreates the mechanical portion of your workflow and writes plain CSV files. It also identifies objective Tight NEL candidates; final chart structure remains a manual review step.

It keeps US common stocks listed on NASDAQ, NYSE, and AMEX that meet all of these filters:

- 30-day average dollar volume above $30M
- 14-period ADR% above 4%
- 10-day average volume above 350K shares
- Industry does not contain “Biotech”

It takes the top 5% of stocks by TradingView performance over each of 1 month, 3 months, 6 months, and 1 year. It combines those four groups, removes duplicate tickers, and removes names more than 4 ATR% multiples above the 50-day SMA. The result is NEL, not a discretionary focus list.

## Tight Non-Extended Leaders (T-NEL)

After NEL is built, the scanner downloads three months of daily OHLC history for those symbols with `yfinance`. A stock qualifies as Tight NEL when it is above its 9-day EMA, its five-day high-low range is no more than 2.5 ATR, its current daily range is below the prior day's ATR, and either its three-day or five-day closes and true ranges satisfy the fast-coil contraction rules. RMV(15) is retained as a secondary ranking value; it is not the pass/fail rule.

The daily run writes `tight_non_extended_leaders_YYYY-MM-DD.csv` and a symbol-only `outputs/EXPORT/tight_nel_symbols_YYYY-MM-DD.csv`. The dashboard displays separate 1-, 3-, 6-, and 12-month Tight NEL tables and can export the selected Tight NEL symbol list.

The separate Themes and Sectors studies use fixed ETF universes and are dated with the actual completed market session they measure. Unlike the stock NEL list, their dates are not advanced to the next trading session.

## Super Liquid Leaders

`super-liquid.html` applies the same 1-, 3-, 6-, and 12-month leader, extension, and tightness process to the market's most liquid stocks. An underlying first needs 30-day average dollar volume above $1 billion. If that stock also has ADR% above 4%, the stock enters the candidate universe. If it misses ADR%, the scanner checks the supplied 2× ETF map and substitutes one ETF: the qualifying fund with the highest current TradingView 30-day average share volume. The ETF must trade more than 1 million shares per day and have ADR% above 4%.

The ETF is measured using its own price performance, ADR%, ATR%, SMA50 extension, and tightness, but inherits its underlying stock's industry for thematic analysis. A qualifying stock and its ETF are never both added. The daily scan refreshes the Super Liquid dashboard and symbol exports for the next market session.

The mapping lives at `data/us_leveraged_etf_map.csv`. `.github/workflows/refresh-leveraged-etfs.yml` refreshes every mapped fund's trailing 30-session average share volume and average dollar volume each Friday after the close. The mapping inventory remains the supplied list; new ETF launches can be added to that CSV as needed.

## Theme and sector ETF studies

The shared navigation bar links the stock dashboard to `themes.html` and `sectors.html`. Both ETF studies use adjusted close for 1-week, 1-, 3-, 6-, and 12-month performance, while intraday change, ADR%, ATR%, SMA50 extension, and liquidity use raw regular-session OHLC and volume. A compact centered performance chart toggles between premarket, overnight, after-hours, intraday, 1-day, 1-week, 1-month, 3-month, 6-month, and 1-year returns. Premarket is measured against the prior regular close; Overnight is the actual 8 PM–4 AM session; After hours is measured from the regular close to the final 4–8 PM price. Completed extended-session values are persisted after the live public fields clear. The Themes chart defaults to one median return per theme, with an ETF drill-down toggle. TradingView identifies its public feed as delayed by up to 15 minutes; older selected dates remain historical close snapshots.

The Themes page ranks ten unique groups per performance window. Every ETF first receives a percentile rank, then each group is scored as `70% × median member percentile + 30% × strongest member percentile`. Multiple strong funds therefore confirm a group without occupying multiple leaderboard positions. All member ETFs remain available for the NEL view. The Sectors page applies the same calculations to the eleven fixed sector ETFs and keeps the top three, without a separate NEL section. Sectors also chart the current top sectors' normalized leadership strength over the latest 30 completed sessions, using one permanent color for each sector.

ADR and liquidity are informational on these pages and never exclude an ETF. On the Themes page, NEL still means no more than 4 ATR extensions above SMA50. Clicking a group or ETF opens its current top stock holdings, excluding cash, bonds, derivatives, collateral, commodities, crypto assets, and fund holdings. Holdings include reported weight plus average dollar volume and extension when a valid U.S.-listed price history is available.

Historical rankings are backfilled from January without look-ahead: each historical row uses only data that existed through that close. Current holdings are not reconstructed historically; the drawer states when they were retrieved.

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
```

## Daily run

```bash
python focus_list.py
```

To run only the Super Liquid study:

```bash
python super_liquid.py
```

## Automatic daily run (macOS)

The installed scheduler checks once per minute and runs the scanner once after 4:25 PM New York time on regular US market days. The extra delay lets Yahoo finalize the regular-session daily close used by the ETF pages. The run refuses to publish stale ETF data and the second cloud schedule retries an hour later. Stock NEL outputs are labelled for the next US trading session, skipping weekends and market holidays. Theme and Sector snapshots keep the date of the actual completed close because they are historical studies. If the Mac wakes later that evening, it catches up automatically. It handles daylight-saving changes and writes each run to `logs/daily_scan_YYYY-MM-DD.log`.

The CSV files appear in `outputs/`:

- `Non-Extended Leaders`: leaders below the 4× ATR% extension threshold
- `NEL Symbols`: a one-column ticker list for NEL
- `Tight Non-Extended Leaders`: NEL passing the fast 3–5 day coil
- `Tight NEL Symbols`: a one-column ticker list for Tight NEL
- `Momentum Leaders`: names qualifying on momentum before the extension filter
- `Filtered Universe`: every name passing the liquidity, ADR%, and industry filters
- `Settings`: the exact run rules

To use the top 2% in each performance ranking:

```bash
python focus_list.py --top-pct 0.02
```

## Metric definitions

The TradingView screener returns `ADRP` (ADR%) and `ATRP` (ATR%) as distinct percentage fields. ADR% is only the activity filter. ATR% is retained as a percentage and applies your extension formula exactly: `ATR Extension from 50d = (Price − SMA50) / (SMA50 × ATR%)`.

Tight NEL is an objective compression shortlist, not a replacement for reviewing chart structure, nearby resistance, earnings risk, and trade location.

## Industry leadership dashboard

Every run also refreshes `industry_flow_dashboard.html`. Open it in a browser to compare industry leadership across the saved daily snapshots. It shows the 1-month, 3-month, 6-month, and 1-year views together. The NEL section lists every non-extended leader by performance window. Its theme cards always derive from the full momentum-leader file, not NEL, so extended names do not distort the strongest-industry signal. Keep prior daily CSV files in `outputs/`; the dashboard reads all of them when it is regenerated.

## GitHub Pages and cloud automation

`index.html` and `super-liquid.html` are refreshed for GitHub Pages. The GitHub Actions workflow in `.github/workflows/daily-scan.yml` schedules both stock scanners after the US close, commits the refreshed CSVs and dashboards, and works without your Mac being awake. GitHub Pages must be enabled for the repository with the `main` branch and `/ (root)` folder selected as its source.

The Breadth page has a separate after-close watcher because Stockbee publishes its Market Monitor at variable times. GitHub checks hourly through late evening in New York, rebuilds the full historical Time Machine, and commits only when the published sheet actually changes.
