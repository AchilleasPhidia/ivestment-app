# Market Brief

A local Streamlit market dashboard with regional mover screens, a multi-source news desk, interactive technical charts, historical forecast scoring, a watchlist, a personal portfolio, and a daily report archive. Yahoo Finance supplies market prices and ticker-level stories. Public RSS feeds add FT and BBC business headlines plus official central-bank announcements for the selected region.

## Start in VS Code

Use Python 3.10 or newer. Open this project folder in VS Code, open its PowerShell terminal, and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL and normally opens it in your browser. Yahoo and RSS responses are cached for 15 minutes. Use **Refresh market data** in the sidebar to clear the cache.

## Dashboard sections

- **Market pulse:** Choose the US, UK, German, French, or Japanese market in the sidebar. The page shows available benchmarks, an approximate local session status, the date of the latest daily price bar, and recent headlines from all configured sources. The market lens can switch between 1M, 3M, 6M, and 1Y and overlay SMA 20/50 and Bollinger Bands. The trend & risk monitor shows a 20-session return, annualised 20-session realised volatility, distance from the one-year high, and RSI (14).
- **News desk:** Filter combined Yahoo Finance, FT Markets, FT Companies, BBC Business, and regional central-bank headlines by website, publisher, theme, and age, then search the title or short RSS summary. The source dropdown includes a link to open each publisher. Story cards identify editorial coverage versus official announcements. FT RSS supplies headlines and summaries, not the full subscriber article; open FT to read it.
- **Movers:** View Yahoo’s US day-gainer/day-loser lists or regional screens for the selected market. Each move is compared with the selected market index. Load a stock’s deeper context to see recent headlines, relative performance against its sector ETF where mapped, and trading volume compared with the prior 20 daily bars.
- **Watchlist:** Edit comma-separated Yahoo symbols. Saved symbols are in `data/watchlist.json`. The page shows the latest available daily price, daily and 20-session returns, market-relative move, RSI, relative volume, and price date.
- **Portfolio:** Record dated buys and sells with quantities, per-share prices, fees, and notes. Separate purchase lots are retained and FIFO accounting calculates the remaining cost basis and realised gains. The dashboard shows portfolio value over time, holdings and sector allocation, daily and unrealised P&L, relative performance versus the selected market index, and a deep dive for each stock with price/indicator charts, company metrics, headlines, and bootstrap or EWMA scenario estimates with a historical scorecard. The portfolio value chart marks open shares to historical prices and excludes cash, dividends, and sale proceeds; see the on-screen note. New trades are stored in `data/transactions.json`. Existing `data/portfolio.json` entries appear as opening balances with unknown dates and are left intact.
- **Forecast lab:** Explore adjusted-price candlesticks with SMA 20/50, Bollinger Bands, MACD, RSI, ATR, and drawdown. The Monte Carlo view offers empirical historical-return bootstrapping or an EWMA-volatility model. The rolling scorecard compares the point-return estimate with a no-change baseline using only earlier observations. Save individual scenarios to `data/forecast_log.json`; later price bars resolve them so the dashboard can report forecast error and observed range coverage.
- **Daily brief:** The first visit to this section each day creates a Markdown report. Reports are archived by market and date in `reports/`. Select an archived report to view or download it.

## Weekday report schedule

To create a report while the dashboard is closed, run this once from PowerShell in the project folder after creating `.venv`:

```powershell
.\setup_daily_schedule.ps1
```

Windows Task Scheduler then runs `daily_report.py` on weekdays at 10:15 PM local time and saves the report under `reports/`. The task uses the signed-in Windows user and starts when an unavailable computer becomes available again. The computer must have internet access for Yahoo Finance data. The scheduled task defaults to the US market; change `--region us` in `setup_daily_schedule.ps1` to `gb`, `de`, `fr`, or `jp` to schedule another region. Run `remove_daily_schedule.ps1` to remove the task.

The report archive and local portfolio files are excluded from Git by `.gitignore`.

## Formulas and interpretation

- **SMA:** mean of the most recent 20 or 50 closes.
- **Bollinger Bands:** 20-session mean plus or minus two rolling standard deviations.
- **RSI (14):** relative strength index based on exponentially smoothed gains and losses.
- **MACD:** EMA(12) minus EMA(26), with a 9-session EMA signal line.
- **ATR (14):** exponentially smoothed true range.
- **Historical bootstrap:** samples daily log returns from the selected lookback with replacement, then compounds simulated paths.
- **EWMA volatility:** estimates volatility with decay λ = 0.94 and simulates normal daily innovations around the recent average log return.
- **Forecast scorecard:** runs a rolling point-return estimate over recent history and compares its absolute price error and directional accuracy with a no-change price baseline.
- **Portfolio lots:** buy fees are included in lot basis; sell fees reduce proceeds; sells consume the oldest available shares first (FIFO). The scenario view rescales adjusted historical-return scenarios to the latest quote and applies current holdings and FX for indicative position values.
- **Money-weighted XIRR:** discounts dated buy/sell cash flows and the current open-position value to solve for the annualised return. It is left blank when transaction dates or purchase costs are unknown and excludes dividends.

These statistics describe assumptions and historical behaviour. They are not calibrated guarantees or investment recommendations. Moving-average and RSI thresholds are descriptive conventions. Headline matches are leads to review, not proof of why a share price moved.

## Data limits

Yahoo Finance may delay prices, omit timestamps, change responses, throttle requests, or return incomplete data. The dashboard labels prices as daily bars and shows their latest available date. Market session status is approximate and does not check local exchange holidays. Regional screens depend on Yahoo’s coverage and filters, so they are not the complete set of listed companies. Some regional sector comparisons are not available; US sector ETF comparisons are mapped where possible.

Transaction, legacy holdings, watchlist, and forecast JSON files are saved in this project’s `data/` directory and excluded from Git. If the project folder is under OneDrive, those files will sync with OneDrive too. This version is intended for one local user, not a multi-user hosted service. If you deploy it for multiple users, replace the local files with authenticated, per-user storage.

## News feeds and content use

The dashboard reads public RSS metadata from FT Markets, FT Companies, and BBC Business, plus the Federal Reserve, Bank of England, ECB, or Bank of Japan feed for the selected market. It displays attributed titles, short feed summaries, timestamps, and links; it does not fetch article bodies or automate access to a signed-in account. The personal FT subscription remains useful for opening and reading linked articles.

Public feed availability does not automatically grant rights to host or redistribute publisher material. This version is intended for your local, personal dashboard. Check the current publisher feed terms before making it public or using it commercially. In particular, BBC RSS terms require permission for business use. Headlines are leads to review, not verified causes of market moves.

Feed access uses Python's standard library and is cached for 15 minutes. A feed that is unavailable or changes format is skipped without preventing the rest of the dashboard from loading. The Yahoo Finance market-price and ticker-news adapter remains subject to Yahoo/yfinance availability and may be delayed or incomplete.
