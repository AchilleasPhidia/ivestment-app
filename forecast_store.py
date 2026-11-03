"""Per-user storage and outcome tracking for forecasts recorded in Supabase."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import Any
from uuid import uuid4
from zoneinfo import ZoneInfo

import pandas as pd

from user_access import supabase_data_request


LONDON = ZoneInfo("Europe/London")


def load_forecasts(access_token: str) -> list[dict[str, Any]]:
    records = supabase_data_request(
        "GET",
        "user_forecasts",
        access_token,
        params={"select": "id,ticker,created_at,origin_date,target_date,horizon,lookback,method,confidence,spot,median,lower,upper,actual,actual_date", "order": "created_at.desc"},
    )
    if not isinstance(records, list):
        return []
    return [item for item in records if isinstance(item, dict)]


def record_forecast(
    ticker: str,
    origin_date: object,
    horizon: int,
    forecast: dict[str, Any],
    access_token: str,
) -> tuple[dict[str, Any], bool]:
    """Store a unique ticker/date/horizon/model forecast for later evaluation."""
    symbol = ticker.strip().upper()
    origin = pd.Timestamp(origin_date).date().isoformat()
    target = pd.Timestamp(forecast["future_date"]).date().isoformat()
    model = str(forecast["method"])
    records = load_forecasts(access_token)
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
        "id": uuid4().hex,
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
    was_added = supabase_data_request(
        "POST",
        "rpc/insert_my_forecast",
        access_token,
        payload={"p_row": record},
    )
    return record, bool(was_added)


def update_forecast_outcomes(ticker: str, history: pd.DataFrame, access_token: str) -> list[dict[str, Any]]:
    """Resolve due forecasts using the first available daily bar on/after target date."""
    symbol = ticker.strip().upper()
    if history is None or history.empty or "Close" not in history:
        return [item for item in load_forecasts(access_token) if item.get("ticker") == symbol]

    close = pd.to_numeric(history["Close"], errors="coerce").dropna()
    available = [(pd.Timestamp(date).date().isoformat(), float(price)) for date, price in close.items()]
    if not available:
        return [item for item in load_forecasts(access_token) if item.get("ticker") == symbol]

    records = load_forecasts(access_token)
    changed: list[dict[str, Any]] = []
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
        changed.append(item)
    for item in changed:
        supabase_data_request(
            "PATCH",
            "user_forecasts",
            access_token,
            params={"id": f"eq.{item['id']}"},
            payload={"actual_date": item["actual_date"], "actual": item["actual"]},
        )
    return [item for item in records if item.get("ticker") == symbol]
