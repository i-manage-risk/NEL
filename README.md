# Non-Extended Leaders (NEL)

This daily scanner recreates the mechanical portion of your workflow and writes plain CSV files. It does not create a focus list; chart structure and tightness remain a manual review step.

It keeps US common stocks listed on NASDAQ, NYSE, and AMEX that meet all of these filters:

- 30-day average dollar volume above $30M
- 14-period ADR% above 4%
- 10-day average volume above 350K shares
- Industry does not contain “Biotech”

It takes the top 5% of stocks by TradingView performance over each of 1 month, 3 months, and 6 months. It combines those three groups, removes duplicate tickers, and removes names more than 4 ATR% multiples above the 50-day SMA. The result is NEL, not a discretionary focus list.

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

## Automatic daily run (macOS)

The installed scheduler checks once per minute and runs the scanner once after 4:10 PM New York time on regular US market days. It uses New York time for market-close and holiday checks, but stamps the output with the Pakistan date because the post-close list is for the next session. If the Mac wakes later that evening, it catches up automatically. It handles daylight-saving changes and writes each run to `logs/daily_scan_YYYY-MM-DD.log`.

The CSV files appear in `outputs/`:

- `Non-Extended Leaders`: leaders below the 4× ATR% extension threshold
- `NEL Symbols`: a one-column ticker list for NEL
- `Momentum Leaders`: names qualifying on momentum before the extension filter
- `Filtered Universe`: every name passing the liquidity, ADR%, and industry filters
- `Settings`: the exact run rules

To use the top 2% in each performance ranking:

```bash
python focus_list.py --top-pct 0.02
```

## Metric definitions

The TradingView screener returns `ADRP` (ADR%) and `ATRP` (ATR%) as distinct percentage fields. ADR% is only the activity filter. ATR% is retained as a percentage and applies your extension formula exactly: `ATR Extension from 50d = (Price − SMA50) / (SMA50 × ATR%)`.

The script intentionally leaves chart structure and tightness to your discretionary review. You create the focus list after reviewing NEL charts. A next iteration can add objective candidates such as distance from 10/21 EMA, ATR contraction, consecutive tight closes, relative volume, and a TradingView chart link.

## Industry leadership dashboard

Every run also refreshes `industry_flow_dashboard.html`. Open it in a browser to compare industry leadership across the saved daily snapshots. It shows the 1-month, 3-month, and 6-month views together. The NEL section lists every non-extended leader by performance window. Its theme cards always derive from the full momentum-leader file, not NEL, so extended names do not distort the strongest-industry signal. Keep prior daily CSV files in `outputs/`; the dashboard reads all of them when it is regenerated.

## GitHub Pages and cloud automation

`index.html` is refreshed with the dashboard for GitHub Pages. The GitHub Actions workflow in `.github/workflows/daily-scan.yml` schedules the scanner after the US close, commits the refreshed CSVs and dashboard, and works without your Mac being awake. GitHub Pages must be enabled for the repository with the `main` branch and `/ (root)` folder selected as its source.
