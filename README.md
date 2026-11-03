# Market Brief

A Streamlit market dashboard with a compact market and news view, company research, private portfolios, and historical forecast scoring. Each account has a private portfolio, starred-company list, and forecast history stored in Supabase with row-level security. Yahoo Finance supplies market prices and ticker-level stories. Public RSS feeds add FT and BBC business headlines plus official central-bank announcements for the selected region.

## Start in VS Code

Use Python 3.10 or newer. Open this project folder in VS Code, open its PowerShell terminal, and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
streamlit run app.py
```

Streamlit prints a local URL and normally opens it in your browser. Yahoo and RSS responses are cached for 15 minutes. Use **Refresh market data** in the sidebar to clear the cache.

Before running this multi-user version, follow [USER_SETUP.md](USER_SETUP.md) to create the Supabase tables, configure email sign-in, and add the local secrets file. The app stays locked until Supabase is configured.

## Dashboard sections

- **Markets:** Choose the US, UK, German, French, or Japanese market in the sidebar. The page combines regional benchmark cards, an approximate local session status, the latest daily bar date, a price chart, trend and risk measures, and filtered headlines. Filter the combined Yahoo Finance, FT Markets, FT Companies, BBC Business, and regional central-bank coverage by publisher, theme, and age. FT RSS supplies story metadata, not the full subscriber article; open FT to read it.
- **Company explorer:** Search for a company or exact Yahoo Finance ticker, inspect the price chart, technical indicators, profile and related headlines, and tap the star to add or remove it from your private watchlist. Starred companies are available from the quick selector at the top of this page.
- **Portfolio:** Record dated buys and sells with quantities, per-share prices, fees, and notes. Separate purchase lots are retained and FIFO accounting calculates the remaining cost basis and realised gains. The dashboard shows portfolio value over time, holdings and sector allocation, daily and unrealised P&L, relative performance versus the selected market index, and a deep dive for each stock with price/indicator charts, company metrics, headlines, and bootstrap or EWMA scenario estimates with a historical scorecard. Each account's transaction ledger is private to that user. The portfolio value chart marks open shares to historical prices and excludes cash, dividends, and sale proceeds; see the on-screen note.
- **Forecast lab:** Explore adjusted-price candlesticks with SMA 20/50, Bollinger Bands, MACD, RSI, ATR, and drawdown. The Monte Carlo view offers empirical historical-return bootstrapping or an EWMA-volatility model. The rolling scorecard compares the point-return estimate with a no-change baseline using only earlier observations. Saved scenarios and their later outcomes are private to the signed-in user.
- **Daily brief:** Review the top Yahoo Finance gainers and decliners. Each ticker opens Company Explorer, and an optional detail control loads the price trend, technical context and related timestamped headlines. The first visit to this section each day also creates a Markdown summary. Reports are archived by market and date in `reports/`; download any report you want to keep.

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
- **RSI (14):** Wilder's relative strength index, seeded with the mean of the first 14 gains and losses and then smoothed recursively. A flat 14-session series is assigned RSI 50.
- **MACD:** EMA(12) minus EMA(26), with a 9-session EMA signal line.
- **ATR (14):** Wilder-smoothed true range, seeded with the mean of the first 14 true ranges.
- **Historical bootstrap:** samples daily log returns from the selected lookback with replacement, then compounds simulated paths.
- **EWMA volatility:** estimates volatility with decay λ = 0.94 and simulates normal daily innovations around the recent average log return.
- **Forecast scorecard:** runs a rolling mean-log-return point estimate and compares mean absolute percentage error (MAPE) and directional accuracy with a no-change price baseline. Each score uses only prices available at that forecast date.
- **Portfolio lots:** buy fees are included in lot basis; sell fees reduce proceeds; sells consume the oldest available shares first (FIFO). The scenario view rescales adjusted historical-return scenarios to the latest quote and applies current holdings and FX for indicative position values.
- **Money-weighted XIRR:** discounts dated buy/sell cash flows and the current open-position value to solve for the annualised return. It is left blank when dates or costs are unknown or the cash-flow pattern has multiple sign changes (which can produce multiple roots). It excludes dividends.

These statistics describe assumptions and historical behaviour. They are not calibrated guarantees or investment recommendations. Moving-average and RSI thresholds are descriptive conventions. Headline matches are leads to review, not proof of why a share price moved.

## Data limits

Yahoo Finance may delay prices, omit timestamps, change responses, throttle requests, or return incomplete data. The dashboard labels prices as daily bars and shows their latest available date. Market session status is approximate and does not check local exchange holidays. Regional screens depend on Yahoo’s coverage and filters, so they are not the complete set of listed companies. Some regional sector comparisons are not available; US sector ETF comparisons are mapped where possible.

Transaction history, watchlists, and forecast outcomes are stored in Supabase under the authenticated user's ID. Postgres row-level security policies scope reads and writes to that account. The Supabase publishable/anon key is used with each user's access token; never put a Supabase secret or service-role key in Streamlit secrets. Generated reports remain files on the app host and are not a durable per-user archive on Community Cloud. Local `data/`, `.env`, secrets, reports, and virtual environments are excluded from Git. Existing local portfolio JSON files are not migrated automatically; keep a backup and re-enter or import holdings after the private database is configured.

## News feeds and content use

The dashboard reads public RSS metadata from FT Markets, FT Companies, and BBC Business, plus the Federal Reserve, Bank of England, ECB, or Bank of Japan feed for the selected market. It displays attributed titles, short feed summaries, timestamps, and links; it does not fetch article bodies or automate access to a signed-in account. The personal FT subscription remains useful for opening and reading linked articles.

Public feed availability does not automatically grant rights to host or redistribute publisher material. This version is intended for a private workspace and invited users. Check the current publisher feed terms before making it public or using it commercially. In particular, BBC RSS terms require permission for business use. Headlines are leads to review, not verified causes of market moves.

Feed access uses Python's standard library and is cached for 15 minutes. A feed that is unavailable or changes format is skipped without preventing the rest of the dashboard from loading. The Yahoo Finance market-price and ticker-news adapter remains subject to Yahoo/yfinance availability and may be delayed or incomplete.
