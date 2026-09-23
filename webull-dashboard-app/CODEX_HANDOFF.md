# Codex handoff: Webull Focus Dashboard

Use this file to continue development from any computer without relying on the
original chat history. Do not place Webull credentials in this repository.

## Repository and published outputs

- Repository: `https://github.com/i-manage-risk/NEL`
- GitHub Pages UI: `https://i-manage-risk.github.io/NEL/webull-dashboard.html`
- Windows release: `https://github.com/i-manage-risk/NEL/releases/tag/webull-dashboard-v1.0.0`
- Windows build workflow: `.github/workflows/build-webull-dashboard-windows.yml`
- Application source: `webull-dashboard-app/app.py`

## Architecture

The GitHub Pages file is a static interface. Market data comes from a local,
read-only Python service bound to `127.0.0.1:8765`. The service uses the official
Webull OpenAPI Python SDK. Credentials remain in a local `.env` file and must
never be committed.

The Windows executable is a PyInstaller one-file build. Every user supplies
their own Webull OpenAPI App Key and App Secret by renaming `.env.example` to
`.env` beside the executable.

## Current dashboard columns

- Symbol
- RVOL
- LoD
- Range
- PDH
- OR (valid opening range: 05, 15, or 30)
- P > ORH
- Delay

The table supports at most 20 symbols and sorts by RVOL descending, then Range
ascending. A symbol is highlighted when RVOL > 30%, LoD < 68%, Range < 68%, and
price is above the prior-day high.

## Calculation definitions

- RVOL: rounded `current RTH volume / SMA(volume, 50) * 100`. The current
  implementation intentionally uses RTH-only minute volume for the active or
  latest session. Webull's daily volume can be higher because it includes
  additional volume outside RTH, so the values will not always exactly match.
- ATR: Wilder ATR(14), with a 500-session warm-up.
- LoD: rounded `100 * (current price - RTH low) / ATR(14)`.
- Range: rounded `100 * (RTH high - RTH low) / ATR(14)`.
- PDH: current price strictly above the prior daily high.
- Valid OR: 05 unless the first one-minute low breaks; then 15. If the first
  five-minute low subsequently breaks, the valid OR becomes 30.
- P > ORH: current price strictly above the selected opening-range high.
- Delay: whole minutes since the latest one-minute bar closed; under three
  minutes displays green.

## Known product decisions

- Use regular-session data only for intraday calculations.
- Outside regular hours, display the latest completed regular session.
- The ATR-multiple extension from the 50-day moving average has been discussed
  but is not yet a dashboard column.
- PaperTrade data may be delayed unless the user's OpenAPI application has a
  real-time market-data entitlement.
- The application contains no order-submission code.
- Mac and Windows installations calculate independently. Credentials and live
  watchlist edits are local and are not synchronized between computers.

## Continue on a new computer

1. Clone this repository and open it as a Codex project.
2. Ask Codex to read `webull-dashboard-app/CODEX_HANDOFF.md` and
   `webull-dashboard-app/app.py` before making changes.
3. Keep `.env` local and git-ignored.
4. After changes, run the Windows workflow and verify its artifact before
   publishing a new release.
