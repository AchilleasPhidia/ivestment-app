"""Create and archive a regional daily brief from the command line."""

from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import pandas as pd

from market_analysis import build_daily_brief
from finance_data import MARKET_REGIONS, fetch_history, fetch_market_news, fetch_movers, fetch_ticker_news
from forecast_store import load_forecasts, update_forecast_outcomes


PROJECT_DIR = Path(__file__).resolve().parent
REPORT_DIR = PROJECT_DIR / "reports"
LONDON = ZoneInfo("Europe/London")


def build_benchmarks(region_name: str) -> list[dict]:
    rows: list[dict] = []
    for symbol, label in MARKET_REGIONS[region_name]["benchmarks"].items():
        history = fetch_history(symbol, period="5d", adjusted=False)
        if history.empty or "Close" not in history:
            continue
        close = pd.to_numeric(history["Close"], errors="coerce").dropna()
        if close.empty:
            continue
        previous = float(close.iloc[-2]) if len(close) > 1 else None
        latest = float(close.iloc[-1])
        rows.append(
            {
                "symbol": symbol,
                "label": label,
                "price": latest,
                "change": (latest / previous - 1) * 100 if previous else None,
                "as_of": pd.Timestamp(history.index[-1]).date(),
            }
        )
    return rows


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate a dated Market Brief report.")
    parser.add_argument("--region", choices=[config["code"] for config in MARKET_REGIONS.values()], default="us")
    arguments = parser.parse_args()

    region_name = next(name for name, config in MARKET_REGIONS.items() if config["code"] == arguments.region)
    config = MARKET_REGIONS[region_name]
    now = datetime.now(LONDON)
    pending_tickers = {
        item.get("ticker")
        for item in load_forecasts()
        if item.get("ticker") and item.get("actual") is None
    }
    for ticker in pending_tickers:
        price_history = fetch_history(str(ticker), period="2y", adjusted=True)
        update_forecast_outcomes(str(ticker), price_history)

    benchmarks = build_benchmarks(region_name)
    market_news = fetch_market_news(tuple(config["news"]), region_name=region_name)
    gainers = fetch_movers("gainers", count=5, region=config["code"])
    losers = fetch_movers("losers", count=5, region=config["code"])

    symbols = pd.concat([gainers.head(5), losers.head(5)], ignore_index=True).get("symbol", pd.Series(dtype=str))
    mover_news = {symbol: fetch_ticker_news(symbol, count=8) for symbol in symbols.dropna().astype(str).unique()}
    report = build_daily_brief(
        now,
        benchmarks,
        gainers,
        losers,
        market_news,
        mover_news,
    )
    report_lines = report.splitlines()
    if report_lines:
        report_lines[0] = f"# Daily market brief — {region_name} — {now:%A, %d %B %Y}"
    session_line = "Market session: Scheduled weekday report; quotes are latest available daily bars."
    session_index = next((index for index, line in enumerate(report_lines) if line.startswith("Market session:")), None)
    if session_index is None:
        generated_index = next((index for index, line in enumerate(report_lines) if line.startswith("Generated at ")), 1)
        report_lines.insert(generated_index + 1, session_line)
    else:
        report_lines[session_index] = session_line
    report = "\n".join(report_lines)

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    output = REPORT_DIR / f"market_brief_{config['code']}_{now:%Y-%m-%d}.md"
    output.write_text(report, encoding="utf-8")
    print(f"Saved daily brief: {output}")


if __name__ == "__main__":
    main()
