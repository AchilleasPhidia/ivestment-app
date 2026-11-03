"""Local JSON storage for one user's portfolio and ticker watchlist."""

from __future__ import annotations

import json
from math import exp, isfinite, log
import re
from pathlib import Path
from uuid import uuid4

import pandas as pd


DATA_DIR = Path(__file__).resolve().parent / "data"
PORTFOLIO_PATH = DATA_DIR / "portfolio.json"
TRANSACTIONS_PATH = DATA_DIR / "transactions.json"
WATCHLIST_PATH = DATA_DIR / "watchlist.json"
PORTFOLIO_COLUMNS = ["ticker", "shares", "average_cost"]
TRANSACTION_COLUMNS = ["id", "date", "ticker", "action", "shares", "price", "fees", "notes"]
DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "LLOY.L", "SHEL.L"]
TICKER_PATTERN = re.compile(r"^[A-Z0-9^.=/-]{1,20}$")


def load_portfolio() -> pd.DataFrame:
    if not PORTFOLIO_PATH.exists():
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)
    try:
        records = json.loads(PORTFOLIO_PATH.read_text(encoding="utf-8"))
        frame = pd.DataFrame(records)
        return normalize_portfolio(frame)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)


def normalize_portfolio(frame: pd.DataFrame) -> pd.DataFrame:
    if frame is None or frame.empty:
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

    source = frame.copy()
    source.columns = [str(column).strip().lower().replace(" ", "_") for column in source.columns]
    aliases = {"average_cost": "average_cost", "avg_cost": "average_cost", "cost": "average_cost"}
    source = source.rename(columns=aliases)
    for column in PORTFOLIO_COLUMNS:
        if column not in source:
            source[column] = None

    rows: list[dict[str, object]] = []
    for _, row in source.iterrows():
        ticker_value = row.get("ticker")
        ticker = "" if pd.isna(ticker_value) else str(ticker_value).strip().upper()
        shares_value = row.get("shares")
        cost_value = row.get("average_cost")
        shares_blank = shares_value is None or pd.isna(shares_value)
        cost_blank = cost_value is None or pd.isna(cost_value)
        if not ticker and shares_blank and cost_blank:
            continue
        if not ticker:
            raise ValueError("Every holding needs a ticker symbol.")
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(f"'{ticker}' is not a valid ticker format.")
        try:
            shares = float(shares_value)
            average_cost = float(cost_value)
        except (TypeError, ValueError):
            raise ValueError(f"Enter shares and average cost for {ticker}.") from None
        if not (isfinite(shares) and isfinite(average_cost) and shares > 0 and average_cost >= 0):
            raise ValueError(f"{ticker}: shares must be above zero and average cost cannot be negative.")
        rows.append({"ticker": ticker, "shares": shares, "average_cost": average_cost})

    if not rows:
        return pd.DataFrame(columns=PORTFOLIO_COLUMNS)

    clean = pd.DataFrame(rows, columns=PORTFOLIO_COLUMNS)
    combined: list[dict[str, object]] = []
    for ticker, group in clean.groupby("ticker", sort=False):
        total_shares = float(group["shares"].sum())
        average_cost = 0.0 if (group["average_cost"] == 0).any() else float((group["shares"] * group["average_cost"]).sum()) / total_shares
        combined.append({"ticker": ticker, "shares": total_shares, "average_cost": average_cost})
    return pd.DataFrame(combined, columns=PORTFOLIO_COLUMNS)


def save_portfolio(frame: pd.DataFrame) -> pd.DataFrame:
    clean = normalize_portfolio(frame)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    PORTFOLIO_PATH.write_text(clean.to_json(orient="records", indent=2), encoding="utf-8")
    return clean


def add_holding(ticker: str, shares: float, average_cost: float) -> pd.DataFrame:
    current = load_portfolio()
    addition = pd.DataFrame([{"ticker": ticker, "shares": shares, "average_cost": average_cost}])
    return save_portfolio(pd.concat([current, addition], ignore_index=True))


def _missing(value: object) -> bool:
    if value is None:
        return True
    try:
        return bool(pd.isna(value))
    except (TypeError, ValueError):
        return False


def normalize_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    """Clean editable transaction rows without collapsing individual purchase lots."""
    if frame is None or frame.empty:
        return pd.DataFrame(columns=TRANSACTION_COLUMNS)

    source = frame.copy()
    source.columns = [str(column).strip().lower().replace(" ", "_") for column in source.columns]
    for column in TRANSACTION_COLUMNS:
        if column not in source:
            source[column] = None

    rows: list[dict[str, object]] = []
    seen_ids: set[str] = set()
    for _, row in source.iterrows():
        ticker_value = row.get("ticker")
        ticker = "" if _missing(ticker_value) else str(ticker_value).strip().upper()
        if not ticker and all(_missing(row.get(column)) for column in ("date", "action", "shares", "price", "fees", "notes")):
            continue
        if not ticker:
            raise ValueError("Every transaction needs a ticker symbol.")
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(f"'{ticker}' is not a valid ticker format.")

        action_value = row.get("action")
        action = "" if _missing(action_value) else str(action_value).strip().title()
        if action not in {"Opening", "Buy", "Sell"}:
            raise ValueError(f"{ticker}: transaction type must be Opening, Buy, or Sell.")
        try:
            shares = float(row.get("shares"))
            price = float(row.get("price"))
            fees_value = row.get("fees")
            fees = 0.0 if _missing(fees_value) else float(fees_value)
        except (TypeError, ValueError):
            raise ValueError(f"{ticker}: enter shares, price per share, and fees as numbers.") from None
        if not all(isfinite(value) for value in (shares, price, fees)) or shares <= 0 or price < 0 or fees < 0:
            raise ValueError(f"{ticker}: shares must be positive; price and fees cannot be negative.")
        if action in {"Buy", "Sell"} and price <= 0:
            raise ValueError(f"{ticker}: enter a price above zero for a buy or sell.")

        date_value = row.get("date")
        if _missing(date_value) or str(date_value).strip() == "":
            date_text = ""
        else:
            parsed_date = pd.to_datetime(date_value, errors="coerce")
            if pd.isna(parsed_date):
                raise ValueError(f"{ticker}: transaction date must use YYYY-MM-DD format.")
            date_text = parsed_date.date().isoformat()

        identifier_value = row.get("id")
        identifier = "" if _missing(identifier_value) else str(identifier_value).strip()
        if not identifier or identifier in seen_ids:
            identifier = uuid4().hex[:10]
        seen_ids.add(identifier)
        notes_value = row.get("notes")
        notes = "" if _missing(notes_value) else str(notes_value).strip()
        rows.append(
            {
                "id": identifier,
                "date": date_text,
                "ticker": ticker,
                "action": action,
                "shares": shares,
                "price": price,
                "fees": fees,
                "notes": notes,
            }
        )
    return pd.DataFrame(rows, columns=TRANSACTION_COLUMNS)


def load_transactions() -> pd.DataFrame:
    """Load the trade ledger, presenting old aggregate holdings as opening balances."""
    if TRANSACTIONS_PATH.exists():
        try:
            records = json.loads(TRANSACTIONS_PATH.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as error:
            raise ValueError("The transaction ledger could not be read. The file has been left unchanged.") from error
        if not isinstance(records, list):
            raise ValueError("The transaction ledger format is not a list. The file has been left unchanged.")
        return normalize_transactions(pd.DataFrame(records))

    legacy = load_portfolio()
    rows = [
        {
            "id": f"opening-{index + 1}",
            "date": "",
            "ticker": str(row["ticker"]),
            "action": "Opening",
            "shares": float(row["shares"]),
            "price": float(row["average_cost"]),
            "fees": 0.0,
            "notes": "Imported from existing holdings; original purchase date is unknown.",
        }
        for index, (_, row) in enumerate(legacy.iterrows())
    ]
    return normalize_transactions(pd.DataFrame(rows, columns=TRANSACTION_COLUMNS))


def calculate_positions(frame: pd.DataFrame) -> pd.DataFrame:
    """Calculate open FIFO lots, remaining cost basis, and realised P&L by ticker."""
    transactions = normalize_transactions(frame)
    ordered = sorted(
        enumerate(transactions.to_dict(orient="records")),
        key=lambda pair: (pair[1]["date"] or "0000-00-00", pair[0]),
    )
    books: dict[str, dict[str, object]] = {}
    for _, transaction in ordered:
        ticker = str(transaction["ticker"])
        book = books.setdefault(ticker, {"lots": [], "realized_pnl": 0.0, "realized_known": True})
        quantity = float(transaction["shares"])
        price = float(transaction["price"])
        fees = float(transaction["fees"])
        action = str(transaction["action"])
        if action in {"Opening", "Buy"}:
            unit_cost = (quantity * price + fees) / quantity
            book["lots"].append({"shares": quantity, "unit_cost": unit_cost, "cost_known": price > 0, "date": transaction["date"]})
            continue

        lots = book["lots"]
        available = sum(float(lot["shares"]) for lot in lots)
        if quantity > available + 1e-8:
            raise ValueError(f"{ticker}: this sale is for {quantity:g} shares, but only {available:g} shares are available on {transaction['date'] or 'the opening date'}.")
        remaining = quantity
        cost_removed = 0.0
        while remaining > 1e-8 and lots:
            lot = lots[0]
            lot_shares = float(lot["shares"])
            used = min(remaining, lot_shares)
            if lot["cost_known"]:
                cost_removed += used * float(lot["unit_cost"])
            else:
                book["realized_known"] = False
            remaining -= used
            lot["shares"] = lot_shares - used
            if float(lot["shares"]) <= 1e-8:
                lots.pop(0)
        book["realized_pnl"] = float(book["realized_pnl"]) + quantity * price - fees - cost_removed

    rows: list[dict[str, object]] = []
    for ticker, book in books.items():
        lots = book["lots"]
        shares = sum(float(lot["shares"]) for lot in lots)
        cost_basis = sum(float(lot["shares"]) * float(lot["unit_cost"]) for lot in lots)
        dates = [str(lot["date"]) for lot in lots if lot["date"]]
        rows.append(
            {
                "ticker": ticker,
                "shares": shares,
                "cost_basis": cost_basis,
                "average_cost": cost_basis / shares if shares > 1e-8 else 0.0,
                "realized_pnl": float(book["realized_pnl"]),
                "cost_known": all(bool(lot["cost_known"]) for lot in lots),
                "realized_known": bool(book["realized_known"]),
                "open_date": min(dates) if dates else "",
            }
        )
    return pd.DataFrame(rows, columns=["ticker", "shares", "cost_basis", "average_cost", "realized_pnl", "cost_known", "realized_known", "open_date"])


def calculate_xirr(
    frame: pd.DataFrame,
    ticker: str,
    current_price: float,
    current_shares: float,
    as_of: object,
) -> float | None:
    """Estimate annualised money-weighted return from dated trades and current value."""
    transactions = normalize_transactions(frame)
    rows = transactions[transactions["ticker"] == ticker.strip().upper()].to_dict(orient="records")
    if not rows or any(not row["date"] for row in rows):
        return None
    if any(row["action"] in {"Opening", "Buy"} and float(row["price"]) <= 0 for row in rows):
        return None

    cashflows: list[tuple[pd.Timestamp, float]] = []
    for row in rows:
        trade_date = pd.Timestamp(row["date"])
        quantity = float(row["shares"])
        gross = quantity * float(row["price"])
        fees = float(row["fees"])
        if row["action"] in {"Opening", "Buy"}:
            cashflows.append((trade_date, -(gross + fees)))
        else:
            cashflows.append((trade_date, gross - fees))
    if current_shares > 1e-8:
        cashflows.append((pd.Timestamp(as_of), float(current_shares) * float(current_price)))
    if not any(amount < 0 for _, amount in cashflows) or not any(amount > 0 for _, amount in cashflows):
        return None

    start_date = min(day for day, _ in cashflows)
    if max(day for day, _ in cashflows) <= start_date:
        return None

    def npv(rate: float) -> float:
        factor = 1 + rate
        if factor <= 0:
            return float("inf")
        total = 0.0
        for day, amount in cashflows:
            years = (day - start_date).days / 365.0
            exponent = -years * log(factor)
            if exponent > 700:
                return float("inf") if amount > 0 else float("-inf")
            term = 0.0 if exponent < -700 else amount * exp(exponent)
            total += term
        return total

    low, high = -0.9999, 1.0
    low_value, high_value = npv(low), npv(high)
    while low_value * high_value > 0 and high < 1_000_000:
        high = high * 2 + 1
        high_value = npv(high)
    if low_value * high_value > 0:
        return None
    for _ in range(120):
        middle = (low + high) / 2
        middle_value = npv(middle)
        if abs(middle_value) < 1e-8:
            return middle
        if (low_value < 0) == (middle_value < 0):
            low, low_value = middle, middle_value
        else:
            high, high_value = middle, middle_value
    return (low + high) / 2


def save_transactions(frame: pd.DataFrame) -> pd.DataFrame:
    clean = normalize_transactions(frame)
    calculate_positions(clean)  # Validate all sells before writing.
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    temporary_path = TRANSACTIONS_PATH.with_suffix(".tmp")
    temporary_path.write_text(clean.to_json(orient="records", indent=2), encoding="utf-8")
    temporary_path.replace(TRANSACTIONS_PATH)
    return clean


def add_transaction(
    action: str,
    ticker: str,
    shares: float,
    price: float,
    fees: float = 0.0,
    date: str = "",
    notes: str = "",
) -> pd.DataFrame:
    current = load_transactions()
    addition = pd.DataFrame(
        [
            {
                "id": uuid4().hex[:10],
                "date": date,
                "ticker": ticker,
                "action": action,
                "shares": shares,
                "price": price,
                "fees": fees,
                "notes": notes,
            }
        ]
    )
    return save_transactions(pd.concat([current, addition], ignore_index=True))


def load_watchlist() -> list[str]:
    if not WATCHLIST_PATH.exists():
        return DEFAULT_WATCHLIST.copy()
    try:
        saved = json.loads(WATCHLIST_PATH.read_text(encoding="utf-8"))
        if not isinstance(saved, list):
            return DEFAULT_WATCHLIST.copy()
        return normalize_watchlist(saved)
    except (OSError, json.JSONDecodeError, ValueError, TypeError):
        return DEFAULT_WATCHLIST.copy()


def normalize_watchlist(values: list[object]) -> list[str]:
    tickers: list[str] = []
    for value in values:
        if value is None or pd.isna(value):
            continue
        ticker = str(value).strip().upper()
        if not ticker:
            continue
        if not TICKER_PATTERN.fullmatch(ticker):
            raise ValueError(f"'{ticker}' is not a valid ticker format.")
        if ticker not in tickers:
            tickers.append(ticker)
    return tickers


def save_watchlist(values: list[object]) -> list[str]:
    tickers = normalize_watchlist(values)
    DATA_DIR.mkdir(parents=True, exist_ok=True)
    WATCHLIST_PATH.write_text(json.dumps(tickers, indent=2), encoding="utf-8")
    return tickers
