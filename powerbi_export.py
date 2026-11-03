"""Create user-scoped Excel workbooks for local Power BI imports."""

from __future__ import annotations

from io import BytesIO
from typing import Any

import pandas as pd
from openpyxl.worksheet.table import Table, TableStyleInfo


TRANSACTION_COLUMNS = ["transaction_id", "date", "ticker", "action", "shares", "price", "fees", "notes"]
HOLDING_COLUMNS = [
    "ticker", "name", "shares", "average_cost", "cost_basis", "cost_known", "last_close", "quote_currency", "value_currency",
    "market_value_local", "market_value_base", "base_currency", "day_move_pct", "return_pct", "unrealized_base",
    "realized_base", "sector", "industry", "rsi_14", "macd", "atr_14", "volatility_20_annualized_pct",
    "max_drawdown_pct", "price_date",
]
PRICE_COLUMNS = ["date", "ticker", "asset_type", "price_basis", "open", "high", "low", "close", "volume"]
HEADLINE_COLUMNS = ["ticker", "published_at", "publisher", "source_kind", "title", "summary", "url"]
PROFILE_COLUMNS = ["ticker", "name", "sector", "industry", "currency", "exchange", "country", "market_cap", "trailing_pe", "forward_pe", "beta", "dividend_yield"]
FORECAST_COLUMNS = [
    "id", "ticker", "created_at", "origin_date", "target_date", "horizon", "lookback", "method",
    "confidence", "spot", "median", "lower", "upper", "actual", "actual_date",
]


def history_table(symbol: str, asset_type: str, history: pd.DataFrame) -> pd.DataFrame:
    """Convert Yahoo daily bars into a tidy table with an explicit ticker column."""
    if history is None or history.empty or "Close" not in history.columns:
        return pd.DataFrame(columns=PRICE_COLUMNS)

    frame = history.copy()
    dates = pd.to_datetime(frame.index, errors="coerce")
    if getattr(dates, "tz", None) is not None:
        dates = dates.tz_localize(None)
    result = pd.DataFrame({
        "date": pd.DatetimeIndex(dates).normalize(),
        "ticker": str(symbol).upper(),
        "asset_type": asset_type,
        "price_basis": "Auto-adjusted daily OHLC",
    })
    for source, target in (("Open", "open"), ("High", "high"), ("Low", "low"), ("Close", "close"), ("Volume", "volume")):
        if source in frame.columns:
            result[target] = pd.to_numeric(frame[source].to_numpy(), errors="coerce")
        else:
            result[target] = pd.NA
    return result[PRICE_COLUMNS].dropna(subset=["close"])


def headline_table(symbol: str, articles: list[dict[str, Any]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for article in articles:
        published = article.get("published")
        if published is not None:
            try:
                published = pd.Timestamp(published).isoformat()
            except (TypeError, ValueError):
                published = str(published)
        rows.append({
            "ticker": str(symbol).upper(),
            "published_at": published or article.get("published_label"),
            "publisher": article.get("publisher"),
            "source_kind": article.get("source_kind"),
            "title": article.get("title"),
            "summary": article.get("summary"),
            "url": article.get("url"),
        })
    return pd.DataFrame(rows, columns=HEADLINE_COLUMNS)


def profile_table(symbol: str, metadata: dict[str, Any]) -> pd.DataFrame:
    """Normalize a Yahoo company profile for an Excel/Power BI dimension table."""
    return pd.DataFrame([{"ticker": str(symbol).upper(), **metadata}]).reindex(columns=PROFILE_COLUMNS)


def _excel_safe(frame: pd.DataFrame) -> pd.DataFrame:
    safe = frame.copy()
    for column in safe.columns:
        if isinstance(safe[column].dtype, pd.DatetimeTZDtype):
            safe[column] = safe[column].map(lambda value: value.isoformat() if pd.notna(value) else None)
        elif safe[column].dtype == "object":
            safe[column] = safe[column].map(
                lambda value: value.isoformat() if hasattr(value, "isoformat") else value
            )
    return safe


def build_powerbi_workbook(
    *,
    transactions: pd.DataFrame,
    holdings: list[dict[str, Any]],
    price_history: pd.DataFrame,
    headlines: pd.DataFrame,
    profiles: pd.DataFrame,
    forecasts: list[dict[str, Any]],
    about: dict[str, str],
) -> bytes:
    """Build a clean multi-sheet workbook containing only the supplied user's data."""
    transaction_frame = transactions.copy()
    if "id" in transaction_frame.columns:
        transaction_frame = transaction_frame.rename(columns={"id": "transaction_id"})
    if "date" not in transaction_frame.columns and "trade_date" in transaction_frame.columns:
        transaction_frame = transaction_frame.rename(columns={"trade_date": "date"})
    transaction_frame = transaction_frame.reindex(columns=TRANSACTION_COLUMNS)
    transaction_frame["date"] = pd.to_datetime(transaction_frame["date"], errors="coerce")

    holding_frame = pd.DataFrame(holdings)
    holding_rename = {
        "currency": "quote_currency",
        "major_currency": "value_currency",
        "price": "last_close",
        "rsi": "rsi_14",
        "atr": "atr_14",
        "volatility_20": "volatility_20_annualized_pct",
        "max_drawdown": "max_drawdown_pct",
        "as_of": "price_date",
    }
    holding_frame = holding_frame.rename(columns=holding_rename).reindex(columns=HOLDING_COLUMNS)
    holding_frame["price_date"] = pd.to_datetime(holding_frame["price_date"], errors="coerce")

    forecast_frame = pd.DataFrame(forecasts).reindex(columns=FORECAST_COLUMNS)
    for column in ("created_at", "origin_date", "target_date", "actual_date"):
        forecast_frame[column] = pd.to_datetime(forecast_frame[column], errors="coerce", utc=True).dt.tz_localize(None)
    price_frame = price_history.reindex(columns=PRICE_COLUMNS)
    headline_frame = headlines.reindex(columns=HEADLINE_COLUMNS)
    profile_frame = profiles.reindex(columns=PROFILE_COLUMNS)
    about_frame = pd.DataFrame([{"field": key, "value": value} for key, value in about.items()])

    sheets = {
        "Transactions": transaction_frame,
        "Holdings": holding_frame,
        "Price history": price_frame,
        "Headlines": headline_frame,
        "Company profiles": profile_frame,
        "Forecasts": forecast_frame,
        "About": about_frame,
    }
    buffer = BytesIO()
    with pd.ExcelWriter(buffer, engine="openpyxl", date_format="yyyy-mm-dd", datetime_format="yyyy-mm-dd hh:mm") as writer:
        for sheet_name, frame in sheets.items():
            _excel_safe(frame).to_excel(writer, sheet_name=sheet_name, index=False)

    buffer.seek(0)
    from openpyxl import load_workbook

    workbook = load_workbook(buffer)
    for sheet in workbook.worksheets:
        sheet.freeze_panes = "A2"
        sheet.sheet_view.showGridLines = False
        if sheet.max_row > 1 and sheet.max_column > 0:
            table = Table(displayName=f"{sheet.title.replace(' ', '')}Table", ref=sheet.dimensions)
            table.tableStyleInfo = TableStyleInfo(
                name="TableStyleMedium2",
                showFirstColumn=False,
                showLastColumn=False,
                showRowStripes=True,
                showColumnStripes=False,
            )
            sheet.add_table(table)
        for cells in sheet.columns:
            column_letter = cells[0].column_letter
            longest = max((len(str(cell.value or "")) for cell in cells[:101]), default=10)
            sheet.column_dimensions[column_letter].width = min(max(longest + 2, 12), 48)
    output = BytesIO()
    workbook.save(output)
    return output.getvalue()
