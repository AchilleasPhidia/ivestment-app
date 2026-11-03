"""Local storage and outcome tracking for forecasts recorded by the user."""

from __future__ import annotations

import json
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

import pandas as pd

from portfolio_store import DATA_DIR


FORECAST_LOG_PATH = DATA_DIR / "forecast_log.json"
LONDON = ZoneInfo("Europe/London")


def load_forecasts() -> list[dict[str, Any]]:
    if not FORECAST_LOG_PATH.exists():
        return []
    try:
        saved = json.loads(FORECAST_LOG_PATH.read_text(encoding="utf-8"))
        return [item for item in saved if isinstance(item, dict)] if isinstance(saved, list) else []
    except (OSError, json.JSONDecodeError):
        return []


def _save_forecasts(records: list[dict[str, Any]]) -> None:
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary = FORECAST_LOG_PATH.with_suffix(".tmp")
    temporary.write_text(json.dumps(records, indent=2), encoding="utf-8")
    temporary.replace(FORECAST_LOG_PATH)


def record_forecast(
    ticker: str,
    origin_date: object,
    horizon: int,
    forecast: dict[str, Any],
) -> tuple[dict[str, Any], bool]:
    """Store a unique ticker/date/horizon/model forecast for later evaluation."""
    symbol = ticker.strip().upper()
    origin = pd.Timestamp(origin_date).date().isoformat()
    target = pd.Timestamp(forecast["future_date"]).date().isoformat()
    model = str(forecast["method"])
    records = load_forecasts()
    existing = next(
        (
            item
            for item in records
            if item.get("ticker") == symbol
            and item.get("origin_date") == origin
            and int(item.get("horizon", 0)) == int(horizon)
            and item.get("method") == model
            and int(item.get("lookback", 0)) == int(forecast.get("lookback", 0))
            and float(item.get("confidence", 0)) == float(forecast["confidence"])
        ),
        None,
    )
    if existing:
        return existing, False

    record = {
        "ticker": symbol,
        "created_at": datetime.now(timezone.utc).astimezone(LONDON).isoformat(timespec="seconds"),
        "origin_date": origin,
        "target_date": target,
        "horizon": int(horizon),
        "lookback": int(forecast.get("lookback", 0)),
        "method": model,
        "confidence": float(forecast["confidence"]),
        "spot": float(forecast["spot"]),
        "median": float(forecast["median"]),
        "lower": float(forecast["lower"]),
        "upper": float(forecast["upper"]),
        "actual": None,
        "actual_date": None,
    }
    records.append(record)
    _save_forecasts(records)
    return record, True


def update_forecast_outcomes(ticker: str, history: pd.DataFrame) -> list[dict[str, Any]]:
    """Resolve due forecasts using the first available daily bar on/after target date."""
    symbol = ticker.strip().upper()
    if history is None or history.empty or "Close" not in history:
        return [item for item in load_forecasts() if item.get("ticker") == symbol]

    close = pd.to_numeric(history["Close"], errors="coerce").dropna()
    available = [(pd.Timestamp(date).date().isoformat(), float(price)) for date, price in close.items()]
    if not available:
        return [item for item in load_forecasts() if item.get("ticker") == symbol]

    records = load_forecasts()
    changed = False
    for item in records:
        if item.get("ticker") != symbol or item.get("actual") is not None:
            continue
        target_date = str(item.get("target_date", ""))
        result = next(((date, price) for date, price in available if date >= target_date), None)
        if result is None:
            continue
        actual_date, actual_price = result
        item["actual_date"] = actual_date
        item["actual"] = actual_price
        changed = True
    if changed:
        _save_forecasts(records)
    return [item for item in records if item.get("ticker") == symbol]
