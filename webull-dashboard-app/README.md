# Webull Focus List Dashboard

Local, read-only dashboard reproducing the current TradingView table with Webull OpenAPI data.

## Setup

1. Copy `.env.example` to `.env`.
2. Put your Webull App Key and App Secret in `.env`.
3. Keep `WEBULL_ENV=paper` for the PaperTrade application shown in Webull.
4. Run:

```bash
python3 app.py
```

The dashboard opens at `http://127.0.0.1:8765`.

## Windows portable build

1. Download and extract `WebullFocusDashboard-Windows.zip`.
2. Rename `.env.example` to `.env` in the extracted folder.
3. Put your own Webull App Key and App Secret in `.env`.
4. Double-click `WebullFocusDashboard.exe`.

The executable runs only on the local computer. Never send your populated
`.env` file to anyone; each user should supply their own Webull credentials.

## Current scope

- Maximum 20 symbols.
- Webull daily and one-minute RTH bars only.
- RVOL: current RTH volume divided by the 50-session average including the active session.
- LoD: `(price - RTH low) / ATR(14) * 100`, rounded to an integer.
- Range: `(RTH high - RTH low) / ATR(14) * 100`, rounded to an integer.
- ATR uses Wilder smoothing with a 500-session warm-up to closely match Webull `ind.atr(14)`.
- PDH: current price strictly above prior-session high.
- Valid OR: 05, 15, or 30 based on the opening one- and five-minute lows.
- P > ORH: current price strictly above the selected opening-range high.
- Delay: age of the latest one-minute bar; under three minutes is green.
- Same qualification highlight and sorting as the Pine dashboard.

PaperTrade stock data may be delayed by 15 minutes unless a production OpenAPI real-time quote entitlement is attached.
