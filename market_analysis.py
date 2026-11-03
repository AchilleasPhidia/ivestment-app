"""Transparent technical indicators, forecast scenarios, and report rendering."""

from __future__ import annotations

from datetime import datetime, timezone
from math import exp, log, sqrt
from typing import Any

import numpy as np
import pandas as pd


DRIVER_TERMS = {
    "Earnings and results": ("earnings", "results", "revenue", "profit", "eps", "quarter", "beat estimates", "miss estimates"),
    "Company outlook": ("guidance", "outlook", "forecast", "raises its forecast", "cuts forecast", "expects"),
    "Analyst rating or target": ("upgrade", "downgrade", "price target", "rating", "overweight", "underweight"),
    "Deal or corporate action": ("acquisition", "acquire", "merger", "buyout", "deal", "stake sale", "spinoff"),
    "Legal or regulatory news": ("lawsuit", "investigation", "probe", "regulator", "antitrust", "fine", "settlement", "approval"),
    "Product, contract or operations": ("launch", "product", "contract", "order", "recall", "production", "partnership"),
    "Macro or sector news": ("federal reserve", "fed signals", "interest rates", "inflation", "tariff", "oil prices", "bond yields", "sector"),
}


def classify_headlines(articles: list[dict[str, Any]]) -> tuple[str, list[dict[str, Any]]]:
    """Label recent coverage and return the headlines that support the label."""
    now = datetime.now(timezone.utc)
    recent: list[dict[str, Any]] = []
    for article in articles:
        published = article.get("published")
        if published is None:
            continue
        if published.tzinfo is None:
            published = published.replace(tzinfo=timezone.utc)
        age_seconds = (now - published.astimezone(timezone.utc)).total_seconds()
        if 0 <= age_seconds <= 72 * 3600:
            recent.append(article)

    if not recent:
        return "No recent, timestamped headline matched this ticker.", []

    scores: list[tuple[int, str]] = []
    for category, terms in DRIVER_TERMS.items():
        score = sum(
            term in f"{article.get('title', '')} {article.get('summary', '')}".lower()
            for article in recent
            for term in terms
        )
        if score:
            scores.append((score, category))
    if not scores:
        return "Recent company coverage is available; the headline wording does not point to a clear catalyst.", recent
    scores.sort(reverse=True)
    return f"Recent headlines point to {scores[0][1].lower()}.", recent


def _wilder_smooth(values: pd.Series, period: int) -> pd.Series:
    """Wilder's smoothed moving average, seeded with a simple average."""
    raw = pd.to_numeric(values, errors="coerce").to_numpy(dtype=float)
    smoothed = np.full(raw.shape, np.nan, dtype=float)
    run_values: list[float] = []
    average = np.nan
    for index, value in enumerate(raw):
        if not np.isfinite(value):
            run_values = []
            average = np.nan
            continue
        if not np.isfinite(average):
            run_values.append(float(value))
            if len(run_values) < period:
                continue
            average = float(np.mean(run_values[-period:]))
        else:
            average = ((period - 1) * average + float(value)) / period
        smoothed[index] = average
    return pd.Series(smoothed, index=values.index, name=values.name)


def calculate_technical_indicators(history: pd.DataFrame) -> pd.DataFrame:
    """Add moving averages, Bollinger Bands, RSI, MACD, ATR, and drawdown."""
    if history is None or history.empty or "Close" not in history:
        return pd.DataFrame()
    frame = history.copy()
    close = pd.to_numeric(frame["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    close = close.where(close > 0)
    frame["Close"] = close

    frame["SMA_20"] = close.rolling(20, min_periods=20).mean()
    frame["SMA_50"] = close.rolling(50, min_periods=50).mean()
    frame["SMA_200"] = close.rolling(200, min_periods=200).mean()
    frame["EMA_12"] = close.ewm(span=12, adjust=False, min_periods=12).mean()
    frame["EMA_26"] = close.ewm(span=26, adjust=False, min_periods=26).mean()
    frame["MACD"] = frame["EMA_12"] - frame["EMA_26"]
    frame["MACD_signal"] = frame["MACD"].ewm(span=9, adjust=False, min_periods=9).mean()
    frame["MACD_histogram"] = frame["MACD"] - frame["MACD_signal"]

    delta = close.diff()
    gain = _wilder_smooth(delta.clip(lower=0), 14)
    loss = _wilder_smooth(-delta.clip(upper=0), 14)
    relative_strength = gain / loss.replace(0, np.nan)
    frame["RSI_14"] = 100 - 100 / (1 + relative_strength)
    frame.loc[(loss == 0) & (gain > 0), "RSI_14"] = 100
    frame.loc[(gain == 0) & (loss > 0), "RSI_14"] = 0
    frame.loc[(gain == 0) & (loss == 0) & gain.notna() & loss.notna(), "RSI_14"] = 50

    rolling_mid = close.rolling(20, min_periods=20).mean()
    rolling_std = close.rolling(20, min_periods=20).std(ddof=0)
    frame["BB_mid"] = rolling_mid
    frame["BB_upper"] = rolling_mid + 2 * rolling_std
    frame["BB_lower"] = rolling_mid - 2 * rolling_std

    if all(column in frame.columns for column in ("High", "Low")):
        high = pd.to_numeric(frame["High"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        low = pd.to_numeric(frame["Low"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        previous_close = close.shift(1)
        true_range = pd.concat(
            [(high - low), (high - previous_close).abs(), (low - previous_close).abs()],
            axis=1,
        ).max(axis=1)
        true_range = true_range.where(true_range >= 0)
        frame["ATR_14"] = _wilder_smooth(true_range, 14)

    frame["Drawdown"] = close / close.cummax() - 1
    if "Volume" in frame:
        volume = pd.to_numeric(frame["Volume"], errors="coerce").replace([np.inf, -np.inf], np.nan)
        frame["Volume_SMA_20"] = volume.rolling(20, min_periods=20).mean()
    return frame


def calculate_forecast(
    history: pd.DataFrame,
    horizon: int,
    lookback: int,
    confidence: float,
    method: str = "Historical bootstrap",
    simulations: int = 3000,
    seed: int = 42,
) -> dict[str, Any] | None:
    """Simulate price paths from resampled returns or an EWMA-volatility model."""
    if history is None or history.empty or "Close" not in history:
        return None
    close = pd.to_numeric(history["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan)
    close = close.where(close > 0).dropna()
    lookback = max(20, int(lookback))
    simulations = max(100, int(simulations))
    if len(close) < lookback + 1:
        return None

    returns = np.diff(np.log(close.to_numpy(dtype=float)))[-lookback:]
    horizon = max(1, int(horizon))
    confidence = min(max(float(confidence), 0.5), 0.99)
    rng = np.random.default_rng(seed)
    daily_drift = float(np.mean(returns))

    if method == "EWMA volatility":
        decay = 0.94
        weights = decay ** np.arange(len(returns) - 1, -1, -1, dtype=float)
        weights /= weights.sum()
        daily_volatility = float(np.sqrt(np.sum(weights * np.square(returns))))
        simulated_returns = rng.normal(daily_drift, daily_volatility, size=(simulations, horizon))
    else:
        daily_volatility = float(np.std(returns, ddof=1))
        simulated_returns = rng.choice(returns, size=(simulations, horizon), replace=True)

    spot = float(close.iloc[-1])
    cumulative_returns = np.clip(np.cumsum(simulated_returns, axis=1), -40, 40)
    paths = spot * np.exp(cumulative_returns)
    quantile_tail = (1 - confidence) / 2
    lower_path = np.quantile(paths, quantile_tail, axis=0)
    median_path = np.quantile(paths, 0.5, axis=0)
    upper_path = np.quantile(paths, 1 - quantile_tail, axis=0)
    terminal = paths[:, -1]
    last_date = pd.Timestamp(close.index[-1])
    future_dates = [last_date + pd.offsets.BDay(day) for day in range(1, horizon + 1)]

    return {
        "history": history.loc[close.index],
        "spot": spot,
        "lookback": int(lookback),
        "median": float(np.median(terminal)),
        "lower": float(np.quantile(terminal, quantile_tail)),
        "upper": float(np.quantile(terminal, 1 - quantile_tail)),
        "median_return": (float(np.median(terminal)) / spot - 1) * 100,
        "annualized_vol": daily_volatility * sqrt(252) * 100,
        "daily_drift": daily_drift,
        "daily_volatility": daily_volatility,
        "lower_path": lower_path,
        "median_path": median_path,
        "upper_path": upper_path,
        "future_dates": future_dates,
        "future_date": future_dates[-1],
        "method": method,
        "confidence": confidence,
        "simulations": int(simulations),
        "max_drawdown": float((close / close.cummax() - 1).min() * 100),
    }


def evaluate_forecast(
    history: pd.DataFrame,
    lookback: int = 60,
    horizon: int = 1,
    test_days: int = 126,
) -> dict[str, float | int] | None:
    """Rolling out-of-sample comparison against a no-change price baseline."""
    if history is None or history.empty or "Close" not in history:
        return None
    close_series = pd.to_numeric(history["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if (close_series <= 0).any():
        return None
    close = close_series.to_numpy(dtype=float)
    horizon = max(1, int(horizon))
    lookback = max(20, int(lookback))
    start = max(int(lookback), len(close) - int(test_days) - horizon)
    end = len(close) - horizon
    if end <= start:
        return None

    model_errors: list[float] = []
    baseline_errors: list[float] = []
    direction_hits: list[bool] = []
    for origin in range(start, end):
        observed = close[origin]
        actual = close[origin + horizon]
        train = np.diff(np.log(close[max(0, origin - lookback):origin + 1]))
        if len(train) < lookback:
            continue
        predicted = observed * exp(float(np.mean(train)) * horizon)
        model_errors.append(abs(predicted / actual - 1) * 100)
        baseline_errors.append(abs(observed / actual - 1) * 100)
        direction_hits.append((predicted >= observed) == (actual >= observed))

    if not model_errors:
        return None
    model_mae = float(np.mean(model_errors))
    baseline_mae = float(np.mean(baseline_errors))
    return {
        "samples": len(model_errors),
        "model_mae_pct": model_mae,
        "baseline_mae_pct": baseline_mae,
        "directional_accuracy_pct": float(np.mean(direction_hits) * 100),
        "mae_improvement_pct": (baseline_mae - model_mae) / baseline_mae * 100 if baseline_mae else 0.0,
    }


def _pct(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:+.2f}%" if np.isfinite(number) else "n/a"
    except (TypeError, ValueError):
        return "n/a"


def _price(value: Any) -> str:
    try:
        number = float(value)
        return f"{number:,.2f}" if np.isfinite(number) else "n/a"
    except (TypeError, ValueError):
        return "n/a"


def build_daily_brief(
    generated_at: datetime,
    benchmarks: list[dict[str, Any]],
    gainers: pd.DataFrame,
    losers: pd.DataFrame,
    market_news: list[dict[str, Any]],
    mover_news: dict[str, list[dict[str, Any]]] | None = None,
    market_name: str = "United States",
    market_status: str = "",
) -> str:
    """Create the dated Markdown report saved by the app and scheduled runner."""
    has_catalyst_lookup = mover_news is not None
    mover_news = mover_news or {}
    headline_publishers = sorted({str(article.get("publisher")) for article in market_news if article.get("publisher")})
    headline_sources = ", ".join(headline_publishers) if headline_publishers else "Yahoo Finance and public publisher feeds"
    lines = [
        f"# Daily market brief — {market_name} — {generated_at:%A, %d %B %Y}",
        "",
        f"Generated at {generated_at:%H:%M} London time.",
        f"Market session: {market_status or 'Check the dashboard for current market hours.'}",
        "",
        f"> Prices use Yahoo Finance daily bars. Headlines use {headline_sources}. Prices and feeds can be delayed or incomplete. Feed metadata links to each publisher; this brief is for research and education, not investment advice.",
        "",
        "## Market snapshot",
        "",
    ]
    if benchmarks:
        for row in benchmarks:
            lines.append(f"- **{row['label']}**: {_price(row.get('price'))} ({_pct(row.get('change'))} today; latest daily bar {row.get('as_of', 'date unavailable')})")
    else:
        lines.append("- Benchmark data was unavailable when this report was created.")

    for label, frame in (("Top gainers", gainers), ("Top decliners", losers)):
        lines.extend(["", f"## {label}", ""])
        if frame is None or frame.empty:
            lines.append("Yahoo Finance did not return mover data.")
            continue
        for _, row in frame.head(5).iterrows():
            symbol = str(row.get("symbol", "?"))
            name = str(row.get("name", symbol))
            lines.append(f"- **{symbol} — {name}**: {_pct(row.get('change_pct'))} (price {_price(row.get('price'))})")
            if has_catalyst_lookup:
                driver, evidence = classify_headlines(mover_news.get(symbol, []))
                if evidence:
                    lines.append(f"  - Possible headline context: {driver}")
                    for article in evidence[:2]:
                        title = article.get("title", "Untitled story")
                        url = article.get("url")
                        publisher = article.get("publisher") or "Yahoo Finance"
                        lines.append(f"  - [{title}]({url}) — {publisher}" if url else f"  - {title} — {publisher}")
                else:
                    lines.append("  - Possible headline context: no recent, timestamped Yahoo headline found.")

    lines.extend(["", "## Market headlines", ""])
    if market_news:
        for article in market_news[:8]:
            title = article.get("title", "Untitled story")
            url = article.get("url")
            publisher = article.get("publisher") or "Yahoo Finance"
            date_label = article.get("published_label") or "Recent"
            headline = f"[{title}]({url})" if url else title
            lines.append(f"- {headline} — {publisher}, {date_label}")
    else:
        lines.append("No market headlines were returned by the available feeds.")

    lines.extend(
        [
            "",
            "## Method and limitations",
            "",
            "Mover screens apply market, price, capitalization, and liquidity filters. Headline matches are leads for further reading, not verified causes. The forecast lab uses either empirical return resampling or an EWMA-volatility simulation. The scorecard is a rolling historical comparison against a no-change baseline; past results do not establish future performance.",
            "",
        ]
    )
    return "\n".join(lines)
