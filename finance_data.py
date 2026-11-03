"""Market-price and news-source adapters for the dashboard and report job."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from html import unescape
import re
from typing import Any
from urllib.request import Request, urlopen
import xml.etree.ElementTree as ET
from zoneinfo import ZoneInfo

import pandas as pd
import streamlit as st
import yfinance as yf


MARKET_REGIONS: dict[str, dict[str, Any]] = {
    "United States": {
        "code": "us",
        "timezone": "America/New_York",
        "benchmarks": {"^GSPC": "S&P 500", "^IXIC": "Nasdaq Composite", "^DJI": "Dow Jones"},
        "news": ("SPY", "QQQ", "^GSPC"),
    },
    "United Kingdom": {
        "code": "gb",
        "timezone": "Europe/London",
        "benchmarks": {"^FTSE": "FTSE 100", "^FTMC": "FTSE 250"},
        "news": ("^FTSE", "^FTMC"),
    },
    "Germany": {
        "code": "de",
        "timezone": "Europe/Berlin",
        "benchmarks": {"^GDAXI": "DAX"},
        "news": ("^GDAXI",),
    },
    "France": {
        "code": "fr",
        "timezone": "Europe/Paris",
        "benchmarks": {"^FCHI": "CAC 40"},
        "news": ("^FCHI",),
    },
    "Japan": {
        "code": "jp",
        "timezone": "Asia/Tokyo",
        "benchmarks": {"^N225": "Nikkei 225"},
        "news": ("^N225",),
    },
}

DEFAULT_REGION = "United States"
MARKET_INDICES = MARKET_REGIONS[DEFAULT_REGION]["benchmarks"]
MARKET_NEWS_SYMBOLS = MARKET_REGIONS[DEFAULT_REGION]["news"]

# Public RSS feeds provide headlines and short feed summaries only. Article
# pages stay on the publisher's site. Review each publisher's feed terms before
# making this dashboard public or using it commercially.
GLOBAL_NEWS_FEEDS: tuple[dict[str, str], ...] = (
    {"publisher": "Financial Times · Markets", "url": "https://www.ft.com/markets?format=rss", "site_url": "https://www.ft.com/markets", "kind": "Editorial"},
    {"publisher": "Financial Times · Companies", "url": "https://www.ft.com/companies?format=rss", "site_url": "https://www.ft.com/companies", "kind": "Editorial"},
    {"publisher": "BBC · Business", "url": "https://feeds.bbci.co.uk/news/business/rss.xml", "site_url": "https://www.bbc.com/news/business", "kind": "Editorial"},
)
REGION_NEWS_FEEDS: dict[str, tuple[dict[str, str], ...]] = {
    "United States": (
        {"publisher": "Federal Reserve", "url": "https://www.federalreserve.gov/feeds/press_all.xml", "site_url": "https://www.federalreserve.gov/newsevents.htm", "kind": "Official source"},
    ),
    "United Kingdom": (
        {"publisher": "Bank of England", "url": "https://www.bankofengland.co.uk/rss/news", "site_url": "https://www.bankofengland.co.uk/news", "kind": "Official source"},
    ),
    "Germany": (
        {"publisher": "European Central Bank", "url": "https://www.ecb.europa.eu/rss/press.html", "site_url": "https://www.ecb.europa.eu/press/html/index.en.html", "kind": "Official source"},
    ),
    "France": (
        {"publisher": "European Central Bank", "url": "https://www.ecb.europa.eu/rss/press.html", "site_url": "https://www.ecb.europa.eu/press/html/index.en.html", "kind": "Official source"},
    ),
    "Japan": (
        {"publisher": "Bank of Japan", "url": "https://www.boj.or.jp/en/rss/whatsnew.xml", "site_url": "https://www.boj.or.jp/en/whatsnew/", "kind": "Official source"},
    ),
}


def _first_value(source: dict[str, Any], *keys: str, default: Any = None) -> Any:
    for key in keys:
        value = source.get(key)
        if value is not None:
            return value
    return default


def _unwrap_news_item(raw: dict[str, Any]) -> dict[str, Any]:
    content = raw.get("content")
    return content if isinstance(content, dict) else raw


def _parse_article(raw: dict[str, Any], queried_symbol: str | None = None) -> dict[str, Any] | None:
    item = _unwrap_news_item(raw)
    title = _first_value(item, "title", "headline")
    if not title:
        return None

    provider = item.get("provider") or {}
    canonical = item.get("canonicalUrl") or item.get("clickThroughUrl") or {}
    url = _first_value(canonical, "url") if isinstance(canonical, dict) else None
    url = url or _first_value(item, "link", "url")

    published = item.get("pubDate") or item.get("published") or item.get("providerPublishTime")
    published_at: datetime | None = None
    if isinstance(published, (int, float)):
        published_at = datetime.fromtimestamp(published, tz=timezone.utc)
    elif isinstance(published, str):
        try:
            published_at = datetime.fromisoformat(published.replace("Z", "+00:00"))
            if published_at.tzinfo is None:
                published_at = published_at.replace(tzinfo=timezone.utc)
        except ValueError:
            published_at = None

    provider_name = _first_value(provider, "displayName", "name") if isinstance(provider, dict) else None
    symbols: list[str] = []
    finance = item.get("finance") or {}
    related = finance.get("stockTickers", []) if isinstance(finance, dict) else []
    for item_ticker in related:
        if isinstance(item_ticker, dict) and item_ticker.get("symbol"):
            symbols.append(str(item_ticker["symbol"]).upper())
    if queried_symbol:
        symbols.append(queried_symbol.upper())

    london_tz = ZoneInfo("Europe/London")
    return {
        "title": str(title).strip(),
        "summary": str(item.get("summary") or item.get("description") or "").strip(),
        "publisher": str(provider_name or item.get("publisher") or "Yahoo Finance"),
        "url": url,
        "published": published_at,
        "published_label": published_at.astimezone(london_tz).strftime("%d %b · %H:%M") if published_at else "Recent",
        "symbols": sorted(set(symbols)),
        "source_kind": "Aggregated feed",
    }


def _dedupe_sort(articles: list[dict[str, Any]]) -> list[dict[str, Any]]:
    unique: dict[str, dict[str, Any]] = {}
    for article in articles:
        key = (article.get("url") or article.get("title") or "").strip().lower()
        if key and key not in unique:
            unique[key] = article
    return sorted(
        unique.values(),
        key=lambda article: article.get("published") or datetime.min.replace(tzinfo=timezone.utc),
        reverse=True,
    )


def _local_tag(tag: str) -> str:
    return tag.rsplit("}", 1)[-1].lower()


def _clean_feed_text(value: str | None, limit: int = 420) -> str:
    if not value:
        return ""
    text = unescape(str(value))
    text = re.sub(r"<[^>]*>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:limit].rstrip()


def _parse_feed_date(value: str | None) -> datetime | None:
    if not value:
        return None
    parsed = pd.to_datetime(value, utc=True, errors="coerce")
    if pd.isna(parsed):
        return None
    return parsed.to_pydatetime()


def _read_rss_feed(feed: dict[str, str]) -> tuple[list[dict[str, Any]], str]:
    request = Request(
        feed["url"],
        headers={"User-Agent": "MarketBrief/1.0 (personal Streamlit news reader)"},
    )
    try:
        with urlopen(request, timeout=8) as response:
            payload = response.read(2_000_000)
        root = ET.fromstring(payload)
    except Exception:
        return [], "Unavailable or unreadable"

    articles: list[dict[str, Any]] = []
    for entry in root.iter():
        if _local_tag(entry.tag) not in {"item", "entry"}:
            continue
        fields: dict[str, str] = {}
        link = ""
        for child in entry:
            key = _local_tag(child.tag)
            if key == "link":
                link = child.attrib.get("href", "").strip() or (child.text or "").strip()
            elif key in {"title", "description", "summary", "encoded", "pubdate", "published", "updated", "date"}:
                if child.text:
                    fields[key] = child.text
        title = _clean_feed_text(fields.get("title"), 280)
        if not title:
            continue
        published = _parse_feed_date(
            fields.get("pubdate") or fields.get("published") or fields.get("updated") or fields.get("date")
        )
        summary = _clean_feed_text(fields.get("description") or fields.get("summary") or fields.get("encoded"))
        articles.append(
            {
                "title": title,
                "summary": summary,
                "publisher": feed["publisher"],
                "url": link,
                "published": published,
                "published_label": published.astimezone(ZoneInfo("Europe/London")).strftime("%d %b · %H:%M") if published else "Recent",
                "symbols": [],
                "source_kind": feed["kind"],
            }
        )
    return articles, "Connected"


@st.cache_data(ttl=900, show_spinner=False)
def fetch_rss_bundle(region_name: str) -> dict[str, Any]:
    """Fetch attributed RSS items and a small per-feed availability summary."""
    feeds = [*GLOBAL_NEWS_FEEDS, *REGION_NEWS_FEEDS.get(region_name, ())]
    articles: list[dict[str, Any]] = []
    statuses: list[dict[str, Any]] = []
    with ThreadPoolExecutor(max_workers=min(6, len(feeds) or 1)) as executor:
        tasks = {executor.submit(_read_rss_feed, feed): feed for feed in feeds}
        for task in as_completed(tasks):
            feed = tasks[task]
            try:
                feed_articles, status = task.result()
            except Exception:
                feed_articles, status = [], "Unavailable or unreadable"
            articles.extend(feed_articles)
            statuses.append({"publisher": feed["publisher"], "kind": feed["kind"], "status": status, "stories": len(feed_articles), "site_url": feed["site_url"], "feed_url": feed["url"]})
    return {"articles": _dedupe_sort(articles), "status": sorted(statuses, key=lambda item: item["publisher"])}


def fetch_rss_news(region_name: str) -> list[dict[str, Any]]:
    """Fetch attributed headline and summary metadata from public RSS feeds."""
    return fetch_rss_bundle(region_name)["articles"]


def fetch_rss_status(region_name: str) -> list[dict[str, Any]]:
    return fetch_rss_bundle(region_name)["status"]


def _normalize_quote(quote: dict[str, Any]) -> dict[str, Any] | None:
    symbol = _first_value(quote, "symbol", "ticker")
    if not symbol:
        return None
    price = _first_value(quote, "regularMarketPrice", "intradayprice", "price")
    previous = _first_value(quote, "regularMarketPreviousClose", "previousClose")
    pct = _first_value(quote, "percentchange", "regularMarketChangePercent")
    try:
        price = float(price) if price is not None else None
        previous = float(previous) if previous is not None else None
        pct = float(pct) if pct is not None else None
    except (TypeError, ValueError):
        pct = None
    if price is not None and previous:
        pct = (price / previous - 1) * 100
    elif pct is not None and "percentchange" not in quote and abs(pct) < 0.1:
        pct *= 100

    quote_time = _first_value(quote, "regularMarketTime", "marketTime")
    try:
        quote_time = datetime.fromtimestamp(float(quote_time), tz=timezone.utc) if quote_time else None
    except (TypeError, ValueError, OSError):
        quote_time = None

    return {
        "symbol": str(symbol).upper(),
        "name": str(_first_value(quote, "shortName", "longName", "displayName", default=symbol)),
        "price": price,
        "previous_close": previous,
        "change_pct": pct,
        "volume": pd.to_numeric(_first_value(quote, "regularMarketVolume", "dayvolume", "volume"), errors="coerce"),
        "average_volume": pd.to_numeric(_first_value(quote, "averageDailyVolume3Month", "avgdailyvol3m"), errors="coerce"),
        "market_cap": pd.to_numeric(_first_value(quote, "marketCap", "intradaymarketcap"), errors="coerce"),
        "quote_time": quote_time,
    }


@st.cache_data(ttl=900, show_spinner=False)
def fetch_history(symbol: str, period: str = "6mo", adjusted: bool = True) -> pd.DataFrame:
    """Fetch daily OHLCV history; adjusted data is used for indicators by default."""
    symbol = symbol.strip().upper()
    if not symbol:
        return pd.DataFrame()
    try:
        history = yf.Ticker(symbol).history(
            period=period,
            interval="1d",
            auto_adjust=adjusted,
            timeout=15,
        )
        if history is None or history.empty:
            return pd.DataFrame()
        history = history.copy()
        history.index = pd.to_datetime(history.index)
        return history.dropna(subset=["Close"])
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=900, show_spinner=False)
def fetch_movers(direction: str, count: int = 5, region: str = "us") -> pd.DataFrame:
    """Fetch Yahoo's US predefined screens or a broad regional equity screen."""
    direction = direction.lower().replace("day_", "")
    region = region.lower()
    if direction not in {"gainers", "losers"}:
        return pd.DataFrame()
    try:
        if region == "us":
            response = yf.screen(f"day_{direction}", count=int(count))
        else:
            from yfinance import EquityQuery

            minimum_cap = 200_000_000 if region in {"gb", "de", "fr"} else 500_000_000
            minimum_volume = 5_000 if region in {"gb", "de", "fr"} else 10_000
            change_filter = EquityQuery("gt" if direction == "gainers" else "lt", ["percentchange", 0])
            query = EquityQuery(
                "and",
                [
                    EquityQuery("eq", ["region", region]),
                    EquityQuery("gte", ["intradaymarketcap", minimum_cap]),
                    EquityQuery("gt", ["intradayprice", 1]),
                    EquityQuery("gt", ["dayvolume", minimum_volume]),
                    change_filter,
                ],
            )
            response = yf.screen(
                query,
                size=int(count),
                sortField="percentchange",
                sortAsc=(direction == "losers"),
            )
        quotes = response.get("quotes", []) if isinstance(response, dict) else []
        rows = [_normalize_quote(quote) for quote in quotes if isinstance(quote, dict)]
        frame = pd.DataFrame([row for row in rows if row])
        if not frame.empty:
            frame["change_pct"] = pd.to_numeric(frame["change_pct"], errors="coerce")
            frame = frame.sort_values("change_pct", ascending=(direction == "losers"), na_position="last")
        return frame.head(int(count)).reset_index(drop=True)
    except Exception:
        return pd.DataFrame()


@st.cache_data(ttl=3600, show_spinner=False)
def fetch_ticker_metadata(symbol: str) -> dict[str, Any]:
    """Fetch basic profile fields for sector-relative mover context."""
    symbol = symbol.strip().upper()
    if not symbol:
        return {}
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.get_info()
        if not isinstance(info, dict):
            info = {}
        if not info:
            try:
                fast_info = ticker.fast_info
                info = {"currency": fast_info.get("currency")}
            except Exception:
                info = {}
        return {
            "name": info.get("shortName") or info.get("longName") or symbol,
            "sector": info.get("sectorDisp") or info.get("sector"),
            "industry": info.get("industryDisp") or info.get("industry"),
            "currency": info.get("currency"),
            "exchange": info.get("exchangeDisp") or info.get("exchange"),
            "country": info.get("country"),
            "market_cap": pd.to_numeric(info.get("marketCap"), errors="coerce"),
            "trailing_pe": pd.to_numeric(info.get("trailingPE"), errors="coerce"),
            "forward_pe": pd.to_numeric(info.get("forwardPE"), errors="coerce"),
            "beta": pd.to_numeric(info.get("beta"), errors="coerce"),
            "dividend_yield": pd.to_numeric(info.get("dividendYield"), errors="coerce"),
        }
    except Exception:
        return {}


@st.cache_data(ttl=900, show_spinner=False)
def fetch_fx_rate(source_currency: str, target_currency: str) -> float | None:
    """Return units of the target currency for one unit of the source currency."""
    source = source_currency.strip().upper()
    target = target_currency.strip().upper()
    if not source or not target:
        return None
    if source == target:
        return 1.0
    for pair, inverse in ((f"{source}{target}=X", False), (f"{target}{source}=X", True)):
        history = fetch_history(pair, period="5d", adjusted=False)
        if history.empty or "Close" not in history:
            continue
        close = pd.to_numeric(history["Close"], errors="coerce").dropna()
        if close.empty or float(close.iloc[-1]) == 0:
            continue
        rate = float(close.iloc[-1])
        return 1 / rate if inverse else rate
    return None


@st.cache_data(ttl=900, show_spinner=False)
def fetch_ticker_news(symbol: str, count: int = 8) -> list[dict[str, Any]]:
    symbol = symbol.strip().upper()
    if not symbol:
        return []
    try:
        raw_items = yf.Ticker(symbol).get_news(count=count, tab="news") or []
    except Exception:
        return []
    parsed = [_parse_article(item, queried_symbol=symbol) for item in raw_items if isinstance(item, dict)]
    return _dedupe_sort([article for article in parsed if article])


@st.cache_data(ttl=900, show_spinner=False)
def fetch_market_news(
    symbols: tuple[str, ...] = MARKET_NEWS_SYMBOLS,
    per_symbol: int = 8,
    region_name: str = DEFAULT_REGION,
) -> list[dict[str, Any]]:
    """Combine Yahoo market headlines with public publisher RSS metadata."""
    articles: list[dict[str, Any]] = []
    for symbol in symbols:
        try:
            raw_items = yf.Ticker(symbol).get_news(count=per_symbol, tab="news") or []
        except Exception:
            continue
        for item in raw_items:
            if isinstance(item, dict):
                parsed = _parse_article(item, queried_symbol=symbol)
                if parsed:
                    articles.append(parsed)
    for article in fetch_rss_news(region_name):
        articles.append(article)
    return _dedupe_sort(articles)
