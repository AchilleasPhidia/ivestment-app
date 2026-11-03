from __future__ import annotations

from datetime import datetime, time
from html import escape
import importlib
from pathlib import Path
from urllib.parse import urlsplit
from zoneinfo import ZoneInfo

import pandas as pd
import numpy as np
import plotly.graph_objects as go
import streamlit as st
from plotly.subplots import make_subplots

# Streamlit can rerun a script without restarting its Python process. Reload
# our project modules so a rerun cannot retain older functions in sys.modules.
import finance_data as finance_data_module
import market_analysis as market_analysis_module
import portfolio_store as portfolio_store_module
import forecast_store as forecast_store_module
import user_access as user_access_module

finance_data_module = importlib.reload(finance_data_module)
market_analysis_module = importlib.reload(market_analysis_module)
user_access_module = importlib.reload(user_access_module)
portfolio_store_module = importlib.reload(portfolio_store_module)
forecast_store_module = importlib.reload(forecast_store_module)

from market_analysis import (
    build_daily_brief,
    calculate_forecast,
    calculate_technical_indicators,
    classify_headlines,
    evaluate_forecast,
)
from finance_data import (
    MARKET_REGIONS,
    fetch_fx_rate,
    fetch_history,
    fetch_market_news,
    fetch_movers,
    fetch_rss_status,
    fetch_ticker_metadata,
    fetch_ticker_news,
)
from forecast_store import record_forecast, update_forecast_outcomes
from portfolio_store import (
    add_transaction,
    calculate_positions,
    calculate_xirr,
    load_transactions,
    load_watchlist,
    normalize_watchlist,
    save_transactions,
    save_watchlist,
)
from user_access import logout_user, render_access_gate


APP_DIR = Path(__file__).resolve().parent
REPORT_DIR = APP_DIR / "reports"
TIMEZONE = ZoneInfo("Europe/London")
SECTOR_ETFS = {
    "technology": "XLK",
    "healthcare": "XLV",
    "financial services": "XLF",
    "financials": "XLF",
    "consumer cyclical": "XLY",
    "consumer defensive": "XLP",
    "industrials": "XLI",
    "energy": "XLE",
    "basic materials": "XLB",
    "real estate": "XLRE",
    "utilities": "XLU",
    "communication services": "XLC",
}
BASE_CURRENCIES = ("GBP", "USD", "EUR")
NEWS_TOPIC_TERMS = {
    "Rates & central banks": ("central bank", "interest rate", "rate cut", "rate hike", "federal reserve", "bank of england", "ecb", "boj", "monetary policy"),
    "Inflation & economy": ("inflation", "cpi", "jobs", "employment", "gdp", "recession", "growth", "economy", "consumer prices"),
    "Earnings & outlook": ("earnings", "results", "revenue", "profit", "guidance", "outlook", "quarterly", "forecast"),
    "Deals & corporate": ("merger", "acquisition", "buyout", "deal", "stake", "ipo", "restructuring", "layoffs"),
    "Policy & regulation": ("regulator", "regulation", "lawsuit", "investigation", "tariff", "sanction", "tax", "government"),
    "Technology": ("artificial intelligence", " ai ", "chip", "semiconductor", "software", "data centre", "technology"),
}

st.set_page_config(
    page_title="Market Brief",
    page_icon="◈",
    layout="wide",
    initial_sidebar_state="expanded",
)


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        @import url('https://fonts.googleapis.com/css2?family=DM+Mono:wght@400;500&family=Manrope:wght@400;500;600;700;800&display=swap');
        :root { --ink:#eaf0f6; --muted:#91a2b6; --line:rgba(161,181,204,.15); --mint:#a6f0ca; }
        html, body, [class*="css"] { font-family:'Manrope',sans-serif; }
        .stApp { background:radial-gradient(ellipse at 82% -10%,rgba(47,88,78,.26),transparent 35%),#0a1017; color:var(--ink); }
        [data-testid="stHeader"] { background:transparent; }
        [data-testid="stSidebar"] { background:#0d141d; border-right:1px solid var(--line); }
        .block-container { max-width:1460px; padding-top:2rem; padding-bottom:4rem; }
        h1,h2,h3 { color:var(--ink); letter-spacing:-.04em; }
        .eyebrow,.section-label { color:var(--mint); font:.73rem 'DM Mono',monospace; letter-spacing:.12em; text-transform:uppercase; }
        .section-label { color:#91a2b6; margin:1.1rem 0 .9rem; }
        .hero-title { color:var(--ink); font-size:2.6rem; font-weight:800; line-height:1.1; letter-spacing:-.065em; margin:0; }
        .hero-sub { color:var(--muted); font-size:.96rem; margin:.6rem 0 1.2rem; }
        .metric-card { min-height:108px; padding:16px 18px; border:1px solid var(--line); border-radius:15px; background:linear-gradient(145deg,rgba(24,35,48,.96),rgba(16,24,34,.96)); }
        .metric-label { color:#91a2b6; font-size:.74rem; letter-spacing:.04em; }
        .metric-value { color:var(--ink); font-size:1.42rem; font-weight:700; letter-spacing:-.045em; margin-top:8px; }
        .metric-change { font: .76rem 'DM Mono',monospace; margin-top:4px; }
        .panel { padding:18px 20px; border:1px solid var(--line); border-radius:15px; background:linear-gradient(145deg,rgba(20,30,42,.96),rgba(14,22,32,.96)); }
        .news-card { padding:12px 0; border-bottom:1px solid var(--line); }
        .news-card:last-child { border-bottom:0; }
        .news-meta { color:#8798ac; font:.68rem 'DM Mono',monospace; letter-spacing:.04em; margin-bottom:7px; text-transform:uppercase; }
        .news-title { color:var(--ink); font-weight:650; line-height:1.45; }
        .news-summary { color:#9aabbd; font-size:.82rem; line-height:1.55; margin-top:5px; }
        .source-chip { display:inline-block; color:#bfeeda; background:rgba(166,240,202,.09); border:1px solid rgba(166,240,202,.18); border-radius:999px; padding:2px 7px; margin-right:6px; font-size:.62rem; letter-spacing:.05em; }
        .news-card a:hover { color:#a6f0ca !important; }
        .news-card:hover { background:rgba(166,240,202,.025); }
        .small-note { color:#91a2b6; font-size:.78rem; line-height:1.55; }
        div[data-testid="stDataFrame"] { overflow:hidden; border:1px solid var(--line); border-radius:12px; }
        .stButton button,.stDownloadButton button { color:#d9f9e8; font-weight:650; background:rgba(166,240,202,.09); border:1px solid rgba(166,240,202,.38); border-radius:9px; }
        .stButton button:hover,.stDownloadButton button:hover { color:#fff; border-color:var(--mint); }
        div[data-testid="stMetric"] { padding:11px 15px; border:1px solid var(--line); border-radius:14px; background:linear-gradient(145deg,rgba(24,35,48,.96),rgba(16,24,34,.96)); }
        div[data-testid="stMetricLabel"] { color:#91a2b6; }
        div[data-testid="stMetricValue"] { color:var(--ink); }
        div[role="radiogroup"] { gap:.4rem; }
        div[role="radiogroup"] label { padding:.38rem .75rem; border:1px solid var(--line); border-radius:999px; background:rgba(17,25,35,.75); transition:all .15s ease; }
        div[role="radiogroup"] label:hover { border-color:rgba(166,240,202,.5); }
        div[data-testid="stSelectbox"] label, div[data-testid="stMultiSelect"] label { color:#9aabbd; }
        div[data-testid="stPlotlyChart"] { border:1px solid rgba(161,181,204,.08); border-radius:14px; overflow:hidden; background:rgba(14,22,32,.55); }
        hr { border-color:var(--line); }
        </style>
        """,
        unsafe_allow_html=True,
    )


def london_now() -> datetime:
    return datetime.now(TIMEZONE)


def format_number(value: object, decimals: int = 2) -> str:
    try:
        number = float(value)
        return f"{number:,.{decimals}f}" if pd.notna(number) else "—"
    except (TypeError, ValueError):
        return "—"


def format_percent(value: object) -> str:
    try:
        number = float(value)
        return f"{number:+.2f}%" if pd.notna(number) else "—"
    except (TypeError, ValueError):
        return "—"


def render_metric_card(label: str, value: str, change: float | None = None, detail: str = "") -> None:
    change_html = ""
    if change is not None and pd.notna(change):
        color = "#a6f0ca" if change >= 0 else "#ff8e8e"
        change_html = f'<div class="metric-change" style="color:{color}">{format_percent(change)} today</div>'
    detail_html = f'<div class="small-note">{escape(detail)}</div>' if detail else ""
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>{change_html}{detail_html}</div>',
        unsafe_allow_html=True,
    )


def render_empty(message: str) -> None:
    st.markdown(f'<div class="panel small-note">{escape(message)}</div>', unsafe_allow_html=True)


def render_news_card(article: dict) -> None:
    title = escape(str(article.get("title") or "Untitled story"))
    publisher = escape(str(article.get("publisher") or "Yahoo Finance"))
    published = escape(str(article.get("published_label") or "Recent"))
    kind = escape(str(article.get("source_kind") or "Market feed"))
    summary = str(article.get("summary") or "").strip()
    if len(summary) > 360:
        summary = summary[:357].rstrip() + "…"
    summary_html = f'<div class="news-summary">{escape(summary)}</div>' if summary else ""
    url = article.get("url")
    safe_url = ""
    if url:
        parsed = urlsplit(str(url))
        if parsed.scheme in {"http", "https"}:
            safe_url = escape(str(url), quote=True)
    if safe_url:
        title = f'<a href="{safe_url}" target="_blank" rel="noopener noreferrer" style="color:inherit;text-decoration:none">{title}</a>'
    st.markdown(
        f'<div class="news-card"><div class="news-meta"><span class="source-chip">{kind}</span>{publisher} · {published}</div>'
        f'<div class="news-title">{title}</div>{summary_html}</div>',
        unsafe_allow_html=True,
    )


def market_session_status(region_name: str, now: datetime) -> tuple[str, str]:
    """Estimate regular-session status; public holidays are intentionally not inferred."""
    config = MARKET_REGIONS[region_name]
    local = now.astimezone(ZoneInfo(config["timezone"]))
    weekday = local.weekday() < 5
    clock = local.time().replace(tzinfo=None)
    sessions = {
        "United States": [(time(9, 30), time(16, 0))],
        "United Kingdom": [(time(8, 0), time(16, 30))],
        "Germany": [(time(9, 0), time(17, 30))],
        "France": [(time(9, 0), time(17, 30))],
        "Japan": [(time(9, 0), time(11, 30)), (time(12, 30), time(15, 30))],
    }
    is_open = weekday and any(start <= clock < end for start, end in sessions[region_name])
    label = "Likely open" if is_open else "Outside usual hours"
    return label, f"{label} · {local:%H:%M} local time · holidays not checked"


def latest_bar_date(history: pd.DataFrame) -> datetime.date | None:
    if history is None or history.empty:
        return None
    try:
        return pd.Timestamp(history.index[-1]).date()
    except (IndexError, TypeError, ValueError):
        return None


def data_freshness_text(date_value: datetime.date | None, now: datetime) -> str:
    if date_value is None:
        return "Price data unavailable"
    days_old = (now.date() - date_value).days
    if days_old <= 1:
        return f"Latest daily bar: {date_value:%d %b}"
    if days_old <= 4:
        return f"Last daily bar: {date_value:%d %b} ({days_old} calendar days ago)"
    return f"Stale price data · last daily bar {date_value:%d %b}"


def headline_freshness(articles: list[dict], now: datetime) -> str:
    published = [item.get("published") for item in articles if item.get("published")]
    if not published:
        return "Headline timestamps unavailable"
    newest = max(published)
    if newest.tzinfo is None:
        newest = newest.replace(tzinfo=TIMEZONE)
    age_hours = max(0, (now - newest.astimezone(TIMEZONE)).total_seconds() / 3600)
    if age_hours < 24:
        return f"Latest headline {age_hours:.0f}h ago"
    if age_hours < 72:
        return f"Latest headline {age_hours / 24:.1f}d ago"
    return f"News feed quiet · latest {newest.astimezone(TIMEZONE):%d %b %H:%M}"


def load_benchmarks(region_name: str) -> list[dict]:
    rows: list[dict] = []
    for symbol, label in MARKET_REGIONS[region_name]["benchmarks"].items():
        history = fetch_history(symbol, period="5d", adjusted=False)
        if history.empty or "Close" not in history:
            continue
        close = pd.to_numeric(history["Close"], errors="coerce").dropna()
        if close.empty:
            continue
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) > 1 else None
        change = (latest / previous - 1) * 100 if previous else None
        rows.append(
            {
                "symbol": symbol,
                "label": label,
                "price": latest,
                "change": change,
                "as_of": latest_bar_date(history),
            }
        )
    return rows


def get_daily_change(symbol: str) -> float | None:
    history = fetch_history(symbol, period="5d", adjusted=False)
    close = pd.to_numeric(history.get("Close", pd.Series(dtype=float)), errors="coerce").dropna()
    if len(close) < 2:
        return None
    return float((close.iloc[-1] / close.iloc[-2] - 1) * 100)


def get_volume_multiple(history: pd.DataFrame, current_volume: object = None) -> float | None:
    if history.empty or "Volume" not in history:
        return None
    volumes = pd.to_numeric(history["Volume"], errors="coerce").dropna()
    if len(volumes) < 6:
        return None
    reference = float(volumes.iloc[:-1].tail(20).mean())
    try:
        current = float(current_volume)
        if pd.isna(current):
            raise ValueError
    except (TypeError, ValueError):
        current = float(volumes.iloc[-1])
    return current / reference if reference > 0 else None


def format_quote_time(value: object) -> str:
    if value is None or pd.isna(value):
        return "—"
    try:
        return pd.Timestamp(value).to_pydatetime().astimezone(TIMEZONE).strftime("%d %b %H:%M")
    except (TypeError, ValueError, OverflowError):
        return "—"


def render_header(region_name: str, now: datetime, benchmarks: list[dict], market_news: list[dict]) -> None:
    session, session_detail = market_session_status(region_name, now)
    benchmark_date = max((row["as_of"] for row in benchmarks if row.get("as_of")), default=None)
    price_status = data_freshness_text(benchmark_date, now)
    news_status = headline_freshness(market_news, now)

    st.markdown('<div class="eyebrow">Daily market intelligence</div>', unsafe_allow_html=True)
    st.markdown('<h1 class="hero-title">The market, in focus.</h1>', unsafe_allow_html=True)
    st.markdown(
        f'<div class="hero-sub">Prices, catalysts, risk indicators and a portfolio view · '
        f'<span style="font-family:DM Mono,monospace">{now:%d %b %Y · %H:%M} London</span></div>',
        unsafe_allow_html=True,
    )
    st.caption(f"**{region_name} session:** {session_detail}  |  **Price freshness:** {price_status}  |  **Headlines:** {news_status}  |  Daily bars are not live quotes.")
    if session == "Likely open":
        st.info("The selected market appears to be in its usual session hours. Holiday calendars are not checked, and Yahoo daily bars may still reflect the previous close.")
    if benchmark_date and (now.date() - benchmark_date).days > 4:
        st.warning("The latest benchmark data is several days old. Refresh later or check Yahoo Finance directly.")


def render_price_history(history: pd.DataFrame, title: str, color: str = "#a6f0ca") -> None:
    if history.empty or "Close" not in history:
        render_empty("Price history is temporarily unavailable.")
        return
    figure = go.Figure(
        go.Scatter(
            x=history.index,
            y=history["Close"],
            mode="lines",
            name=title,
            line={"color": color, "width": 2.2},
            fill="tozeroy",
            fillcolor="rgba(166,240,202,.07)",
        )
    )
    figure.update_layout(
        height=355,
        margin={"l": 8, "r": 8, "t": 12, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#91a2b6", "family": "Manrope"},
        xaxis={"showgrid": False, "zeroline": False},
        yaxis={"gridcolor": "rgba(145,162,182,.12)", "zeroline": False, "tickformat": ",.0f"},
        showlegend=False,
        hovermode="x unified",
    )
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})


def market_lens_figure(history: pd.DataFrame, title: str, visible_sessions: int, overlays: list[str]) -> go.Figure:
    indicators = calculate_technical_indicators(history).tail(visible_sessions)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=indicators.index,
            y=indicators["Close"],
            mode="lines",
            name=title,
            line={"color": "#a6f0ca", "width": 2.4},
            fill="tozeroy",
            fillcolor="rgba(166,240,202,.045)",
        )
    )
    if "Bollinger Bands" in overlays and {"BB_lower", "BB_upper"}.issubset(indicators.columns):
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["BB_lower"], name="Lower band", line={"color": "rgba(133,166,255,.25)", "width": 1}, hoverinfo="skip"))
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["BB_upper"], name="Bollinger range", line={"color": "rgba(133,166,255,.25)", "width": 1}, fill="tonexty", fillcolor="rgba(133,166,255,.08)"))
    if "SMA 20" in overlays and "SMA_20" in indicators:
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_20"], name="SMA 20", line={"color": "#85a6ff", "width": 1.3}))
    if "SMA 50" in overlays and "SMA_50" in indicators:
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_50"], name="SMA 50", line={"color": "#f2c879", "width": 1.3}))
    figure.update_layout(
        height=390,
        margin={"l": 10, "r": 12, "t": 16, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#91a2b6", "family": "Manrope", "size": 11},
        xaxis={"showgrid": False, "zeroline": False, "rangeslider": {"visible": False}},
        yaxis={"gridcolor": "rgba(145,162,182,.12)", "zeroline": False, "tickformat": ",.0f"},
        legend={"orientation": "h", "y": 1.08, "x": 0},
        hovermode="x unified",
    )
    return figure


def render_news_desk(region_name: str, market_news: list[dict], now: datetime, feed_status: list[dict]) -> None:
    st.markdown('<div class="section-label">The news desk</div>', unsafe_allow_html=True)
    st.caption("Headlines and short feed summaries are attributed and link to the publisher. FT RSS shows story metadata; open FT to read subscriber articles. Source context is not proof of a price catalyst.")
    source_names = sorted(
        {str(item.get("publisher") or "Unknown") for item in market_news}
        | {str(item.get("publisher") or "") for item in feed_status if item.get("publisher")}
    )
    def topic_for(article: dict) -> str:
        text = f" {article.get('title', '')} {article.get('summary', '')} ".lower()
        for topic, terms in NEWS_TOPIC_TERMS.items():
            if any(term in text for term in terms):
                return topic
        return "Other"

    topic_names = sorted({topic_for(article) for article in market_news})
    filter_cols = st.columns([1.1, .9, 1.25, 1.6])
    with filter_cols[0]:
        source_filter = st.selectbox("Website / source", ["All sources", "Yahoo Finance news partners", *source_names], key=f"news_source_{region_name}")
    with filter_cols[1]:
        age_filter = st.selectbox("Time window", ["24 hours", "3 days", "All available"], index=1, key=f"news_age_{region_name}")
    with filter_cols[2]:
        topic_filter = st.selectbox("Theme", ["All themes", *topic_names], key=f"news_topic_{region_name}")
    with filter_cols[3]:
        search = st.text_input("Search headlines", placeholder="Company, rates, inflation…", key=f"news_search_{region_name}").strip().lower()
    chosen_site = next((item for item in feed_status if item.get("publisher") == source_filter), None)
    if source_filter == "Yahoo Finance news partners":
        st.link_button("Open Yahoo Finance news ↗", "https://finance.yahoo.com/news/")
    elif chosen_site:
        st.link_button(f"Open {source_filter} website ↗", chosen_site["site_url"])

    cutoff_hours = {"24 hours": 24, "3 days": 72}.get(age_filter)
    filtered: list[dict] = []
    for article in market_news:
        if source_filter == "Yahoo Finance news partners":
            if article.get("source_kind") != "Aggregated feed":
                continue
        elif source_filter != "All sources" and article.get("publisher") != source_filter:
            continue
        if topic_filter != "All themes" and topic_for(article) != topic_filter:
            continue
        published = article.get("published")
        if cutoff_hours is not None and published is not None:
            if published.tzinfo is None:
                published = published.replace(tzinfo=TIMEZONE)
            if (now - published.astimezone(TIMEZONE)).total_seconds() > cutoff_hours * 3600:
                continue
        if search and search not in f"{article.get('title', '')} {article.get('summary', '')} {article.get('publisher', '')}".lower():
            continue
        filtered.append(article)
    filtered.sort(key=lambda item: item.get("published") or datetime.min.replace(tzinfo=TIMEZONE), reverse=True)

    visible_publishers = len({str(item.get("publisher") or "Unknown") for item in filtered})
    newest = next((item.get("published_label") for item in filtered if item.get("published_label")), "—")
    overview = st.columns(3)
    with overview[0]:
        render_metric_card("Stories in view", f"{len(filtered):,}", detail=age_filter)
    with overview[1]:
        render_metric_card("Publishers represented", f"{visible_publishers}", detail="editorial + official sources")
    with overview[2]:
        render_metric_card("Newest timestamp", newest, detail="London time where supplied")

    topic_counts = pd.Series([topic_for(article) for article in market_news]).value_counts().drop(labels=["Other"], errors="ignore").head(6)
    if not topic_counts.empty:
        topic_figure = go.Figure(go.Bar(
            x=topic_counts.values,
            y=topic_counts.index,
            orientation="h",
            marker={"color": ["#a6f0ca", "#85a6ff", "#c89bff", "#f2c879", "#79d6db", "#ff9f8b"][:len(topic_counts)]},
            text=topic_counts.values,
            textposition="outside",
            hovertemplate="%{y}: %{x} headlines<extra></extra>",
        ))
        topic_figure.update_layout(
            height=max(170, 38 * len(topic_counts)),
            margin={"l": 8, "r": 30, "t": 8, "b": 8},
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font={"color": "#91a2b6", "family": "Manrope", "size": 11},
            xaxis={"showgrid": False, "visible": False},
            yaxis={"showgrid": False, "autorange": "reversed"},
            showlegend=False,
        )
        theme_col, explanation_col = st.columns([1.2, 1])
        with theme_col:
            st.markdown('<div class="section-label">Keyword topic pulse</div>', unsafe_allow_html=True)
            st.plotly_chart(topic_figure, use_container_width=True, config={"displayModeBar": False})
        with explanation_col:
            st.markdown('<div class="section-label">How to read it</div>', unsafe_allow_html=True)
            st.markdown('<div class="panel small-note">Themes are grouped from words in the headline and short feed summary. This is a navigation aid, not sentiment analysis and not a measure of market impact. Use the theme filter above to narrow the story list.</div>', unsafe_allow_html=True)

    with st.expander("Sources and coverage", expanded=False):
        st.markdown("**Editorial headlines:** Financial Times Markets, Financial Times Companies, BBC Business and Yahoo Finance. **Official updates:** " + ", ".join(sorted({str(item.get("publisher")) for item in market_news if item.get("source_kind") == "Official source"})) + ".")
        st.caption("FT and BBC feeds provide headline metadata and summaries, not article bodies. Review publisher terms before hosting or redistributing the dashboard. Official central-bank feeds add primary announcements, not independent reporting.")
        if feed_status:
            source_table = pd.DataFrame(
                [
                    {
                        "RSS source": item["publisher"],
                        "Type": item["kind"],
                        "Feed status": f"{item['status']} · {item['stories']} items",
                        "Website": item["site_url"],
                    }
                    for item in feed_status
                ]
            )
            st.dataframe(source_table, hide_index=True, use_container_width=True, column_config={"Website": st.column_config.LinkColumn("Website", display_text="Open ↗")})
        st.caption("RSS feeds are cached for 15 minutes. Use Refresh market data in the sidebar to retry unavailable feeds.")

    if not market_news:
        render_empty("No stories arrived from the current feeds. Check the availability table above and refresh later.")
        return
    if not filtered:
        render_empty("Nothing matches those filters. Try a wider time window or clear the search.")
        return
    for article in filtered[:30]:
        render_news_card(article)
    if len(filtered) > 30:
        st.caption(f"Showing 30 of {len(filtered)} matching stories.")


def render_market_pulse(region_name: str, benchmarks: list[dict], market_news: list[dict]) -> None:
    st.markdown('<div class="section-label">Market snapshot</div>', unsafe_allow_html=True)
    if benchmarks:
        cards = st.columns(min(4, len(benchmarks)))
        for column, row in zip(cards, benchmarks):
            with column:
                render_metric_card(row["label"], format_number(row["price"]), row.get("change"), f"Daily bar · {row.get('as_of') or 'date unavailable'}")
    else:
        render_empty(f"No {region_name} benchmark prices are available right now.")

    main_symbol = next(iter(MARKET_REGIONS[region_name]["benchmarks"]))
    main_label = MARKET_REGIONS[region_name]["benchmarks"][main_symbol]
    history = fetch_history(main_symbol, period="1y", adjusted=True)
    indicators = calculate_technical_indicators(history)
    if not indicators.empty:
        close = pd.to_numeric(indicators["Close"], errors="coerce").dropna()
        returns = close.pct_change().dropna()
        move_20 = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else None
        volatility_20 = float(returns.tail(20).std(ddof=1) * (252 ** 0.5) * 100) if len(returns) >= 10 else None
        drawdown_1y = float((close.iloc[-1] / close.tail(252).max() - 1) * 100) if len(close) > 1 else None
        latest_rsi = indicators["RSI_14"].iloc[-1] if "RSI_14" in indicators else None
        st.markdown('<div class="section-label">Trend & risk monitor</div>', unsafe_allow_html=True)
        risk_cols = st.columns(4)
        values = [
            ("20-session return", format_percent(move_20), None, "directional context"),
            ("Realised volatility · 20d", f"{volatility_20:.1f}%" if volatility_20 is not None else "—", None, "annualised from daily returns"),
            ("Drawdown from 1y high", format_percent(drawdown_1y), None, "distance below recent peak"),
            ("RSI · 14", format_number(latest_rsi, 1), None, "momentum measure · 0–100"),
        ]
        for column, (label, value, change, detail) in zip(risk_cols, values):
            with column:
                render_metric_card(label, value, change, detail)

    chart_col, news_col = st.columns([1.5, 1], gap="large")
    with chart_col:
        st.markdown(f'<div class="section-label">{escape(main_label)} · market lens</div>', unsafe_allow_html=True)
        range_cols = st.columns([1, 2.2])
        with range_cols[0]:
            range_name = st.radio("Chart range", ["1M", "3M", "6M", "1Y"], horizontal=True, key=f"lens_range_{region_name}")
        with range_cols[1]:
            overlays = st.multiselect("Overlays", ["SMA 20", "SMA 50", "Bollinger Bands"], default=["SMA 20", "SMA 50"], key=f"lens_overlays_{region_name}")
        visible_sessions = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}[range_name]
        if history.empty:
            render_empty("Price history is temporarily unavailable.")
        else:
            st.plotly_chart(market_lens_figure(history, main_label, visible_sessions, overlays), use_container_width=True, config={"displayModeBar": False})
        st.caption("Realised volatility = standard deviation of the last 20 daily returns × √252. RSI, moving averages and bands describe historical behaviour; they are not forecasts.")

    with news_col:
        st.markdown('<div class="section-label">Latest across your sources</div>', unsafe_allow_html=True)
        if market_news:
            for article in market_news[:6]:
                render_news_card(article)
            st.button("Open News desk filters ↓", key="go_news_desk", on_click=lambda: st.session_state.update({"dashboard_section": "News desk"}))
        else:
            render_empty("No headlines are available. Refresh later or open the News desk to review source coverage.")


def render_mover_details(mover: pd.Series, region_name: str, benchmark_move: float | None) -> None:
    symbol = str(mover.get("symbol", ""))
    if not symbol:
        return
    name = str(mover.get("name", symbol))
    move = mover.get("change_pct")
    relative = float(move) - benchmark_move if pd.notna(move) and benchmark_move is not None else None
    with st.expander(f"{symbol} · {name} · {format_percent(move)}"):
        context_col, action_col = st.columns([1.25, 1])
        with context_col:
            st.metric(f"Move relative to {region_name} index", format_percent(relative))
            quote_label = format_quote_time(mover.get("quote_time"))
            if quote_label != "—":
                st.caption(f"Yahoo screener quote time: {quote_label} London")
        with action_col:
            load_context = st.button("Load catalyst and volume context", key=f"context_{region_name}_{symbol}")
        if not load_context:
            st.caption("Open the details to see recent headlines, unusual volume, and sector comparison.")
            return

        with st.spinner(f"Loading context for {symbol}…"):
            metadata = fetch_ticker_metadata(symbol)
            history = fetch_history(symbol, period="3mo", adjusted=False)
            articles = fetch_ticker_news(symbol, count=8)
            sector = str(metadata.get("sector") or "")
            etf = SECTOR_ETFS.get(sector.lower()) if region_name == "United States" else None
            sector_move = get_daily_change(etf) if etf else None

        average_volume_multiple = get_volume_multiple(history, mover.get("volume"))
        info_cols = st.columns(3)
        with info_cols[0]:
            st.metric("Sector", sector or "Unavailable")
        with info_cols[1]:
            st.metric("Volume vs 20-session average", f"{average_volume_multiple:.1f}×" if average_volume_multiple is not None else "Unavailable")
        with info_cols[2]:
            sector_relative = float(move) - sector_move if pd.notna(move) and sector_move is not None else None
            st.metric(f"Move relative to {etf or 'sector ETF'}", format_percent(sector_relative))
        if history.empty:
            st.caption("Daily price history was unavailable, so the volume comparison could not be calculated.")

        driver, evidence = classify_headlines(articles)
        st.markdown(f"**Possible headline context:** {driver}")
        st.caption("Headline matches are evidence to review, not proof that a story caused the price move.")
        if evidence:
            for article in evidence[:3]:
                render_news_card(article)
        else:
            render_empty("No recent, timestamped Yahoo Finance headline matched this ticker.")


def render_mover_table(frame: pd.DataFrame, benchmark_move: float | None, region_name: str) -> None:
    if frame.empty:
        render_empty("Yahoo Finance did not return mover data. Try refreshing later; market holidays and quiet sessions can also leave the screen empty.")
        return
    table = frame.copy()
    table["relative"] = table["change_pct"].map(
        lambda value: float(value) - benchmark_move if pd.notna(value) and benchmark_move is not None else None
    )
    table["as_of"] = table["quote_time"].map(format_quote_time)
    display = table[["symbol", "name", "price", "change_pct", "relative", "volume", "as_of"]].copy()
    display.columns = ["Ticker", "Company", "Price", "Move", f"Vs {region_name} index", "Volume", "Quote time (London)"]
    display["Price"] = display["Price"].map(lambda value: format_number(value, 2))
    display["Move"] = display["Move"].map(format_percent)
    display[f"Vs {region_name} index"] = display[f"Vs {region_name} index"].map(format_percent)
    display["Volume"] = display["Volume"].map(lambda value: f"{int(value):,}" if pd.notna(value) else "—")
    st.dataframe(display, hide_index=True, use_container_width=True)
    for _, mover in table.iterrows():
        render_mover_details(mover, region_name, benchmark_move)


def render_movers(region_name: str, benchmarks: list[dict]) -> tuple[pd.DataFrame, pd.DataFrame]:
    region_code = MARKET_REGIONS[region_name]["code"]
    benchmark_move = benchmarks[0].get("change") if benchmarks else None
    st.markdown('<div class="section-label">Top movers · selected market</div>', unsafe_allow_html=True)
    if region_name == "United States":
        st.caption("Yahoo’s predefined US day-gainer and day-loser screens use capitalization, price, and volume filters.")
    else:
        st.caption("Yahoo regional screens use market, price, market-capitalization, volume, and direction filters; coverage varies by exchange.")
    count = st.slider("Companies per side", min_value=3, max_value=10, value=5, key=f"mover_count_{region_code}")
    with st.spinner(f"Loading {region_name} gainers and decliners…"):
        gainers = fetch_movers("gainers", count=count, region=region_code)
        losers = fetch_movers("losers", count=count, region=region_code)
    left, right = st.columns(2, gap="large")
    with left:
        st.markdown("### ↑  Leading gainers")
        render_mover_table(gainers, benchmark_move, region_name)
    with right:
        st.markdown("### ↓  Leading decliners")
        render_mover_table(losers, benchmark_move, region_name)
    return gainers, losers


def ticker_update(symbol: str, benchmark_move: float | None) -> dict | None:
    history = fetch_history(symbol, period="3mo", adjusted=False)
    if history.empty:
        return None
    close = pd.to_numeric(history["Close"], errors="coerce").dropna()
    if close.empty:
        return None
    indicators = calculate_technical_indicators(history)
    day_move = float((close.iloc[-1] / close.iloc[-2] - 1) * 100) if len(close) > 1 else None
    month_move = float((close.iloc[-1] / close.iloc[-21] - 1) * 100) if len(close) >= 21 else None
    latest = indicators.iloc[-1] if not indicators.empty else pd.Series(dtype=float)
    volume_ratio = get_volume_multiple(history)
    return {
        "ticker": symbol,
        "last_close": float(close.iloc[-1]),
        "day_move": day_move,
        "month_move": month_move,
        "relative_move": day_move - benchmark_move if day_move is not None and benchmark_move is not None else None,
        "rsi": latest.get("RSI_14"),
        "volume_ratio": volume_ratio,
        "as_of": latest_bar_date(history),
        "history": history,
        "indicators": indicators,
    }


def render_watchlist(region_name: str, benchmarks: list[dict], access_token: str) -> None:
    st.markdown('<div class="section-label">Personal watchlist</div>', unsafe_allow_html=True)
    st.caption("This watchlist is private to your signed-in account. Enter Yahoo Finance symbols separated by commas.")
    tickers = load_watchlist(access_token)
    with st.form("watchlist_form"):
        ticker_text = st.text_input("Watchlist tickers", value=", ".join(tickers), placeholder="AAPL, MSFT, LLOY.L")
        save_watchlist_clicked = st.form_submit_button("Save watchlist")
    if save_watchlist_clicked:
        try:
            tickers = save_watchlist(normalize_watchlist(ticker_text.split(",")), access_token)
            st.success("Watchlist saved.")
        except ValueError as error:
            st.error(str(error))
    if not tickers:
        render_empty("Add one or more tickers above to follow them here.")
        return

    benchmark_move = benchmarks[0].get("change") if benchmarks else None
    with st.spinner("Refreshing watchlist prices and indicators…"):
        updates = [ticker_update(symbol, benchmark_move) for symbol in tickers]
    updates = [update for update in updates if update]
    if not updates:
        render_empty("No price history is available for the current watchlist.")
        return

    table = pd.DataFrame(
        [
            {
                "Ticker": item["ticker"],
                "Last close": format_number(item["last_close"]),
                "Day move": format_percent(item["day_move"]),
                "20-session return": format_percent(item["month_move"]),
                f"Vs {region_name} today": format_percent(item["relative_move"]),
                "RSI (14)": format_number(item["rsi"], 1),
                "Volume / 20-day avg": f"{item['volume_ratio']:.1f}×" if item["volume_ratio"] is not None else "—",
                "Price date": str(item["as_of"] or "—"),
            }
            for item in updates
        ]
    )
    st.dataframe(table, hide_index=True, use_container_width=True)
    for item in updates:
        with st.expander(f"{item['ticker']} · latest update"):
            info_cols = st.columns(4)
            with info_cols[0]:
                st.metric("Last close", format_number(item["last_close"]))
            with info_cols[1]:
                st.metric("20-session return", format_percent(item["month_move"]))
            with info_cols[2]:
                st.metric("RSI (14)", format_number(item["rsi"], 1))
            with info_cols[3]:
                st.metric("Volume vs average", f"{item['volume_ratio']:.1f}×" if item["volume_ratio"] is not None else "—")
            if st.button("Load latest headlines", key=f"watch_news_{item['ticker']}"):
                articles = fetch_ticker_news(item["ticker"], count=5)
                if articles:
                    for article in articles[:3]:
                        render_news_card(article)
                else:
                    render_empty("No ticker headlines are currently available.")


def forecast_figure(history: pd.DataFrame, forecast: dict) -> go.Figure:
    window = forecast["history"].tail(150)
    indicators = calculate_technical_indicators(window)
    indicators = indicators.tail(150)
    figure = make_subplots(
        rows=3,
        cols=1,
        shared_xaxes=True,
        vertical_spacing=0.045,
        row_heights=[0.57, 0.23, 0.20],
        subplot_titles=("Price, moving averages & Bollinger Bands", "MACD (12, 26, 9)", "RSI (14)"),
    )

    if all(column in indicators for column in ("Open", "High", "Low", "Close")):
        figure.add_trace(
            go.Candlestick(
                x=indicators.index,
                open=indicators["Open"],
                high=indicators["High"],
                low=indicators["Low"],
                close=indicators["Close"],
                name="Adjusted daily price",
                increasing_line_color="#a6f0ca",
                decreasing_line_color="#ff8e8e",
            ),
            row=1,
            col=1,
        )
    else:
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["Close"], name="Close", line={"color": "#a6f0ca"}), row=1, col=1)

    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["BB_lower"], name="Bollinger lower", line={"color": "rgba(133,166,255,.4)", "width": 1}), row=1, col=1)
    figure.add_trace(
        go.Scatter(x=indicators.index, y=indicators["BB_upper"], name="Bollinger band", line={"color": "rgba(133,166,255,.4)", "width": 1}, fill="tonexty", fillcolor="rgba(133,166,255,.08)"),
        row=1,
        col=1,
    )
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_20"], name="SMA 20", line={"color": "#85a6ff", "width": 1.2}), row=1, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_50"], name="SMA 50", line={"color": "#f2c879", "width": 1.2}), row=1, col=1)

    hist_colors = ["#a6f0ca" if value >= 0 else "#ff8e8e" for value in indicators["MACD_histogram"].fillna(0)]
    figure.add_trace(go.Bar(x=indicators.index, y=indicators["MACD_histogram"], name="MACD histogram", marker_color=hist_colors), row=2, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["MACD"], name="MACD", line={"color": "#85a6ff", "width": 1.3}), row=2, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["MACD_signal"], name="Signal", line={"color": "#f2c879", "width": 1.2}), row=2, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["RSI_14"], name="RSI 14", line={"color": "#c89bff", "width": 1.5}), row=3, col=1)
    for y_value in (30, 70):
        figure.add_hline(y=y_value, line_dash="dot", line_color="rgba(145,162,182,.45)", row=3, col=1)

    figure.update_layout(
        height=720,
        margin={"l": 10, "r": 10, "t": 45, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#91a2b6", "family": "Manrope", "size": 11},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "y": 1.02},
        hovermode="x unified",
    )
    figure.update_xaxes(showgrid=False, zeroline=False)
    figure.update_yaxes(gridcolor="rgba(145,162,182,.12)", zeroline=False)
    figure.update_yaxes(range=[0, 100], row=3, col=1)
    return figure


def render_forecast_lab(access_token: str) -> None:
    st.markdown('<div class="section-label">Technical analysis & scenario estimates</div>', unsafe_allow_html=True)
    st.caption("Indicators describe historical price behaviour. Simulated ranges are scenarios, not guarantees or recommendations.")

    ticker_col, horizon_col, lookback_col, confidence_col, model_col = st.columns([1.1, .85, .9, .9, 1.35])
    with ticker_col:
        ticker = st.text_input("Yahoo Finance ticker", value="AAPL", help="Examples: AAPL, MSFT, NVDA, LLOY.L").strip().upper()
    with horizon_col:
        horizon = st.slider("Days ahead", 1, 30, 5)
    with lookback_col:
        lookback = st.slider("Lookback", 20, 120, 60, step=10)
    with confidence_col:
        confidence = st.selectbox("Range", [80, 90, 95], index=1)
    with model_col:
        method = st.selectbox("Simulation model", ["Historical bootstrap", "EWMA volatility"])

    simulations = st.slider("Simulation paths", min_value=1000, max_value=10000, value=3000, step=1000)
    history = fetch_history(ticker, period="2y", adjusted=True) if ticker else pd.DataFrame()
    forecast = calculate_forecast(history, horizon, lookback, confidence / 100, method, simulations) if not history.empty else None
    if forecast is None:
        render_empty("Price history is unavailable or too short for this ticker. Check the symbol and try again.")
        return

    metric_cols = st.columns(5)
    with metric_cols[0]:
        st.metric("Adjusted close", format_number(forecast["spot"]))
    with metric_cols[1]:
        st.metric("Median scenario", format_number(forecast["median"]), delta=format_percent(forecast["expected_return"]))
    with metric_cols[2]:
        st.metric(f"{confidence}% lower range", format_number(forecast["lower"]))
    with metric_cols[3]:
        st.metric(f"{confidence}% upper range", format_number(forecast["upper"]))
    with metric_cols[4]:
        st.metric("Annualised volatility", f"{forecast['annualized_vol']:.1f}%")

    st.markdown("#### Price structure and indicators")
    st.plotly_chart(forecast_figure(history, forecast), use_container_width=True, config={"displayModeBar": False})
    indicators = calculate_technical_indicators(history)
    latest = indicators.iloc[-1]
    st.caption(
        f"SMA = simple moving average; Bollinger Bands = 20-session mean ± 2 standard deviations; "
        f"RSI (14) = exponentially smoothed relative strength index; MACD = EMA(12) − EMA(26), with a 9-session signal line; "
        f"ATR (14) = smoothed true range. Latest RSI {format_number(latest.get('RSI_14'), 1)}, "
        f"MACD {format_number(latest.get('MACD'))}, ATR {format_number(latest.get('ATR_14'))}; "
        f"maximum historical drawdown in this sample {forecast['max_drawdown']:.1f}%."
    )

    st.markdown("#### Monte Carlo price range")
    displayed_history = forecast["history"].tail(120)
    last_date = displayed_history.index[-1]
    forecast_dates = [last_date, *forecast["future_dates"]]
    low_path = [forecast["spot"], *forecast["lower_path"]]
    median_path = [forecast["spot"], *forecast["median_path"]]
    high_path = [forecast["spot"], *forecast["upper_path"]]
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=displayed_history.index, y=displayed_history["Close"], mode="lines", name="Adjusted close", line={"color": "#85a6ff", "width": 2}))
    figure.add_trace(go.Scatter(x=forecast_dates, y=low_path, mode="lines", line={"width": 0}, showlegend=False, hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=forecast_dates, y=high_path, mode="lines", line={"width": 0}, fill="tonexty", fillcolor="rgba(166,240,202,.14)", name=f"{confidence}% simulation range", hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=forecast_dates, y=median_path, mode="lines+markers", name="Median path", line={"color": "#a6f0ca", "width": 2, "dash": "dash"}, marker={"size": 5}))
    figure.update_layout(height=380, margin={"l": 8, "r": 8, "t": 18, "b": 8}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#91a2b6", "family": "Manrope"}, xaxis={"showgrid": False}, yaxis={"gridcolor": "rgba(145,162,182,.12)", "zeroline": False}, legend={"orientation": "h", "y": 1.08}, hovermode="x unified")
    st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
    if method == "Historical bootstrap":
        formula = f"The model resamples the last {lookback} daily log returns with replacement and compounds {simulations:,} paths. The shaded range uses the central {confidence}% of simulated terminal prices; it assumes sampled returns remain relevant and independent."
    else:
        formula = f"The model simulates {simulations:,} normally distributed paths using mean daily log return and EWMA volatility (decay λ = 0.94) estimated from the last {lookback} sessions. The shaded range uses the central {confidence}% of simulated terminal prices."
    st.markdown(f'<div class="panel small-note">{escape(formula)}</div>', unsafe_allow_html=True)

    st.markdown("#### Rolling forecast scorecard")
    score = evaluate_forecast(history, lookback=lookback, horizon=horizon, test_days=126)
    if score is None:
        st.caption("There is not enough history for the selected horizon and lookback to create a rolling scorecard.")
    else:
        score_cols = st.columns(4)
        with score_cols[0]:
            st.metric("Out-of-sample days", f"{score['samples']:,}")
        with score_cols[1]:
            st.metric("Directional accuracy", f"{score['directional_accuracy_pct']:.1f}%")
        with score_cols[2]:
            st.metric("Model mean abs. error", f"{score['model_mae_pct']:.2f}%")
        with score_cols[3]:
            st.metric("No-change baseline error", f"{score['baseline_mae_pct']:.2f}%", delta=f"{score['mae_improvement_pct']:+.1f}% vs baseline")
        st.caption("Rolling historical check: each estimate uses only earlier data and is compared with a no-change price baseline. It evaluates the point-return model, not the simulated range, and is not evidence of future performance.")

    st.markdown("#### Track this forecast")
    st.caption("Record the current scenario to your private account. When Yahoo later has a daily bar on or after its target date, the app adds the actual result to this scorecard.")
    if st.button("Save forecast for tracking", key=f"record_forecast_{ticker}_{horizon}_{lookback}_{confidence}_{method}"):
        _, was_added = record_forecast(ticker, forecast["history"].index[-1], horizon, forecast, access_token)
        if was_added:
            st.success("Forecast saved. Its outcome will be checked when the target date has a price bar.")
        else:
            st.info("This ticker, date, horizon, and model combination is already being tracked.")

    tracked = update_forecast_outcomes(ticker, history, access_token)
    resolved = [item for item in tracked if item.get("actual") is not None]
    if resolved:
        median_errors = [abs(float(item["actual"]) / float(item["median"]) - 1) * 100 for item in resolved if item.get("median")]
        baseline_errors = [abs(float(item["actual"]) / float(item["spot"]) - 1) * 100 for item in resolved if item.get("spot")]
        range_hits = [float(item["lower"]) <= float(item["actual"]) <= float(item["upper"]) for item in resolved]
        tracked_cols = st.columns(4)
        with tracked_cols[0]:
            st.metric("Resolved forecasts", f"{len(resolved):,}")
        with tracked_cols[1]:
            st.metric("Median absolute error", f"{pd.Series(median_errors).median():.2f}%" if median_errors else "—")
        with tracked_cols[2]:
            st.metric("No-change baseline error", f"{pd.Series(baseline_errors).median():.2f}%" if baseline_errors else "—")
        with tracked_cols[3]:
            st.metric("Observed range coverage", f"{sum(range_hits) / len(range_hits) * 100:.1f}%")
        tracked_table = pd.DataFrame(
            [
                {
                    "Forecast date": item["origin_date"],
                    "Target date": item["target_date"],
                    "Actual bar": item.get("actual_date"),
                    "Model": item["method"],
                    "Median": format_number(item["median"]),
                    "Actual": format_number(item["actual"]),
                    "Absolute error": format_percent(abs(float(item["actual"]) / float(item["median"]) - 1) * 100),
                    "Within range": "Yes" if float(item["lower"]) <= float(item["actual"]) <= float(item["upper"]) else "No",
                }
                for item in sorted(resolved, key=lambda record: record.get("created_at", ""), reverse=True)[:20]
            ]
        )
        st.dataframe(tracked_table, hide_index=True, use_container_width=True)
        st.caption("Observed range coverage is descriptive. Small tracked samples cannot establish that future ranges are calibrated.")
    else:
        st.caption("No saved forecasts for this ticker have reached their target date yet.")


def _date_indexed_close(history: pd.DataFrame) -> pd.Series:
    if history is None or history.empty or "Close" not in history:
        return pd.Series(dtype=float)
    close = pd.to_numeric(history["Close"], errors="coerce").dropna().copy()
    index = pd.DatetimeIndex(pd.to_datetime(close.index))
    if index.tz is not None:
        index = index.tz_localize(None)
    close.index = index.normalize()
    return close.groupby(level=0).last().sort_index()


def portfolio_value_history(
    transactions: pd.DataFrame,
    positions: list[dict],
    histories: dict[str, pd.DataFrame],
    base_currency: str,
) -> pd.Series:
    """Mark each day's open shares to historical closes, including dated trades."""
    closes = {position["ticker"]: _date_indexed_close(histories.get(position["ticker"], pd.DataFrame())) for position in positions}
    date_values = sorted({day for series in closes.values() for day in series.index})
    if not date_values or any(closes.get(position["ticker"], pd.Series(dtype=float)).empty for position in positions):
        return pd.Series(dtype=float)
    dates = pd.DatetimeIndex(date_values)
    transaction_rows = transactions.to_dict(orient="records")
    portfolio_values: dict[str, pd.Series] = {}

    for position in positions:
        symbol = position["ticker"]
        close = closes[symbol].reindex(dates).ffill()
        shares = np.zeros(len(dates), dtype=float)
        for row in transaction_rows:
            if str(row.get("ticker", "")).upper() != symbol:
                continue
            action = str(row.get("action", ""))
            quantity = float(row.get("shares") or 0.0)
            date_text = str(row.get("date") or "").strip()
            if action == "Opening" and not date_text:
                shares += quantity
                continue
            if not date_text:
                continue
            start = int(dates.searchsorted(pd.Timestamp(date_text).normalize(), side="left"))
            if start >= len(dates):
                continue
            shares[start:] += quantity if action in {"Opening", "Buy"} else -quantity

        major_currency = position["major_currency"]
        if major_currency == base_currency:
            fx = pd.Series(1.0, index=dates)
        else:
            fx_history = fetch_history(f"{major_currency}{base_currency}=X", period="1y", adjusted=False)
            fx_close = _date_indexed_close(fx_history)
            if fx_close.empty:
                inverse_history = fetch_history(f"{base_currency}{major_currency}=X", period="1y", adjusted=False)
                inverse = _date_indexed_close(inverse_history)
                fx_close = (1 / inverse.replace(0, np.nan)).dropna() if not inverse.empty else inverse
            if fx_close.empty:
                fallback_rate = position.get("fx_rate")
                if fallback_rate is None:
                    return pd.Series(dtype=float)
                fx = pd.Series(float(fallback_rate), index=dates)
            else:
                fx = fx_close.reindex(dates).ffill().bfill()

        values = close.to_numpy(dtype=float) * shares * float(position["price_scale"]) * fx.to_numpy(dtype=float)
        values[shares <= 0] = 0.0
        portfolio_values[symbol] = pd.Series(values, index=dates)

    combined = pd.DataFrame(portfolio_values).sum(axis=1, min_count=len(positions)).dropna()
    combined.name = f"Portfolio value · {base_currency}"
    return combined


def portfolio_value_figure(series: pd.Series, base_currency: str, visible_sessions: int) -> go.Figure:
    window = series.tail(visible_sessions)
    figure = go.Figure(
        go.Scatter(
            x=window.index,
            y=window.values,
            mode="lines",
            name="Open holdings",
            line={"color": "#a6f0ca", "width": 2.5},
            fill="tozeroy",
            fillcolor="rgba(166,240,202,.08)",
            hovertemplate=f"%{{x|%d %b %Y}}<br>{base_currency} %{{y:,.2f}}<extra></extra>",
        )
    )
    figure.update_layout(
        height=370,
        margin={"l": 8, "r": 12, "t": 20, "b": 8},
        paper_bgcolor="rgba(0,0,0,0)",
        plot_bgcolor="rgba(0,0,0,0)",
        font={"color": "#91a2b6", "family": "Manrope", "size": 11},
        xaxis={"showgrid": False},
        yaxis={"gridcolor": "rgba(145,162,182,.12)", "zeroline": False, "tickprefix": f"{base_currency} "},
        hovermode="x unified",
        showlegend=False,
    )
    return figure


def portfolio_relative_figure(stock_history: pd.DataFrame, benchmark_history: pd.DataFrame, benchmark_name: str) -> go.Figure:
    stock = _date_indexed_close(stock_history).rename("Holding")
    benchmark = _date_indexed_close(benchmark_history).rename(benchmark_name)
    combined = pd.concat([stock, benchmark], axis=1).dropna()
    figure = go.Figure()
    if len(combined) >= 2:
        indexed = (combined / combined.iloc[0] - 1) * 100
        figure.add_trace(go.Scatter(x=indexed.index, y=indexed["Holding"], mode="lines", name="Holding", line={"color": "#a6f0ca", "width": 2.4}))
        figure.add_trace(go.Scatter(x=indexed.index, y=indexed[benchmark_name], mode="lines", name=benchmark_name, line={"color": "#85a6ff", "width": 1.8}))
    figure.add_hline(y=0, line_color="rgba(145,162,182,.38)", line_dash="dot")
    figure.update_layout(height=360, margin={"l": 8, "r": 10, "t": 12, "b": 8}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#91a2b6", "family": "Manrope"}, xaxis={"showgrid": False}, yaxis={"gridcolor": "rgba(145,162,182,.12)", "ticksuffix": "%"}, legend={"orientation": "h", "y": 1.08}, hovermode="x unified")
    return figure


def portfolio_scenario_figure(history: pd.DataFrame, forecast: dict, confidence: int) -> go.Figure:
    close = _date_indexed_close(history).tail(100)
    dates = [close.index[-1], *forecast["future_dates"]]
    low = [forecast["spot"], *forecast["lower_path"]]
    median = [forecast["spot"], *forecast["median_path"]]
    high = [forecast["spot"], *forecast["upper_path"]]
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=close.index, y=close.values, name="Recent daily close", line={"color": "#85a6ff", "width": 2}))
    figure.add_trace(go.Scatter(x=dates, y=low, line={"width": 0}, showlegend=False, hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=dates, y=high, line={"width": 0}, fill="tonexty", fillcolor="rgba(166,240,202,.14)", name=f"{confidence}% scenario range", hoverinfo="skip"))
    figure.add_trace(go.Scatter(x=dates, y=median, mode="lines+markers", name="Median scenario", line={"color": "#a6f0ca", "width": 2, "dash": "dash"}, marker={"size": 5}))
    figure.update_layout(height=370, margin={"l": 8, "r": 10, "t": 16, "b": 8}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#91a2b6", "family": "Manrope"}, xaxis={"showgrid": False}, yaxis={"gridcolor": "rgba(145,162,182,.12)", "zeroline": False}, legend={"orientation": "h", "y": 1.08}, hovermode="x unified")
    return figure


def render_transaction_ledger(transactions: pd.DataFrame, access_token: str) -> None:
    with st.expander("Trade history · edit or export", expanded=False):
        st.caption("Each purchase is kept as a separate lot. Sales use FIFO cost matching. Edit or remove rows here; sales that exceed shares held are rejected.")
        edited = st.data_editor(
            transactions,
            num_rows="dynamic",
            hide_index=True,
            use_container_width=True,
            key="transactions_editor",
            column_config={
                "id": st.column_config.TextColumn("Ref", disabled=True, width="small"),
                "date": st.column_config.TextColumn("Date · YYYY-MM-DD", help="Leave blank for an opening balance with unknown date"),
                "ticker": st.column_config.TextColumn("Ticker"),
                "action": st.column_config.SelectboxColumn("Type", options=["Opening", "Buy", "Sell"]),
                "shares": st.column_config.NumberColumn("Shares", min_value=0.000001, format="%.6f"),
                "price": st.column_config.NumberColumn("Price / share", min_value=0.0, format="%.4f"),
                "fees": st.column_config.NumberColumn("Fees", min_value=0.0, format="%.4f"),
                "notes": st.column_config.TextColumn("Notes", width="large"),
            },
        )
        action_cols = st.columns([1, 1, 3])
        with action_cols[0]:
            if st.button("Save ledger changes", key="save_transactions", type="primary"):
                try:
                    save_transactions(edited, access_token)
                    st.session_state["portfolio_notice"] = "Trade history saved. Holdings and FIFO P&L have been recalculated."
                    st.rerun()
                except ValueError as error:
                    st.error(str(error))
        with action_cols[1]:
            st.download_button("Export CSV", data=transactions.to_csv(index=False).encode("utf-8"), file_name="portfolio_transactions.csv", mime="text/csv", key="export_transactions")


def render_portfolio(region_name: str, access_token: str) -> None:
    st.markdown('<div class="eyebrow">Your investments</div>', unsafe_allow_html=True)
    st.markdown('<h2 style="margin:0 0 .3rem">Portfolio command centre</h2>', unsafe_allow_html=True)
    st.caption("Track every buy and sell, see what is driving your exposure, and inspect each holding. Your transaction history is private to your signed-in account. Prices are the latest Yahoo Finance daily bars; values are indicative.")

    settings = st.columns([1, 3])
    with settings[0]:
        base_currency = st.selectbox("Summary currency", BASE_CURRENCIES, index=0, key="portfolio_base_currency")
    try:
        transactions = load_transactions(access_token)
    except ValueError as error:
        st.error(str(error))
        return
    if notice := st.session_state.pop("portfolio_notice", None):
        st.success(notice)

    with st.expander("＋  Record a purchase or sale", expanded=not bool(transactions.empty)):
        st.caption("Record shares, execution price, transaction date and fees in the ticker's quote currency. For London Stock Exchange symbols quoted in GBp, enter price and fees in pence.")
        with st.form("portfolio_trade_form"):
            trade_cols = st.columns([.9, 1.15, 1, 1, 1, 1.05, 1.4])
            with trade_cols[0]:
                action = st.selectbox("Action", ["Buy", "Sell"])
            with trade_cols[1]:
                ticker = st.text_input("Ticker", placeholder="AAPL or LLOY.L").strip().upper()
            with trade_cols[2]:
                trade_date = st.date_input("Trade date", value=london_now().date())
            with trade_cols[3]:
                shares = st.number_input("Shares", min_value=0.000001, value=1.0, step=1.0, format="%.6f")
            with trade_cols[4]:
                price = st.number_input("Price / share", min_value=0.000001, value=1.0, step=0.01, format="%.4f")
            with trade_cols[5]:
                fees = st.number_input("Fees", min_value=0.0, value=0.0, step=0.01, format="%.4f")
            with trade_cols[6]:
                note = st.text_input("Note", placeholder="Broker or reason (optional)")
            submitted = st.form_submit_button("Add transaction", type="primary", use_container_width=True)
        if submitted:
            try:
                if not ticker:
                    raise ValueError("Enter a ticker symbol.")
                add_transaction(action, ticker, shares, price, fees, trade_date.isoformat(), note, access_token)
                st.session_state.pop("transactions_editor", None)
                st.session_state["portfolio_notice"] = f"{action} recorded for {ticker}. Your holdings have been recalculated."
                st.rerun()
            except ValueError as error:
                st.error(str(error))

    try:
        position_frame = calculate_positions(transactions)
    except ValueError as error:
        st.error(f"The current transaction ledger cannot be valued: {error}")
        render_transaction_ledger(transactions, access_token)
        return

    position_rows = position_frame.to_dict(orient="records")
    open_rows = [position for position in position_rows if float(position["shares"]) > 1e-8]
    if not open_rows:
        render_empty("No open positions yet. Record your first buy above. Completed sales remain in Trade history.")
        realized = sum(float(position["realized_pnl"]) for position in position_rows if position.get("realized_known", True))
        if position_rows:
            st.metric("Realised P&L · quote currencies mixed", format_number(realized))
        render_transaction_ledger(transactions, access_token)
        return

    main_benchmark_symbol = next(iter(MARKET_REGIONS[region_name]["benchmarks"]))
    main_benchmark_name = MARKET_REGIONS[region_name]["benchmarks"][main_benchmark_symbol]
    with st.spinner("Updating prices, company profiles and portfolio analytics…"):
        positions: list[dict] = []
        historical_prices: dict[str, pd.DataFrame] = {}
        metadata_by_ticker: dict[str, dict] = {}
        for item in position_rows:
            symbol = str(item["ticker"])
            metadata = fetch_ticker_metadata(symbol)
            metadata_by_ticker[symbol] = metadata
            raw_currency = str(metadata.get("currency") or "?")
            pence_quote = raw_currency in {"GBp", "GBX"} and symbol.endswith((".L", ".IL"))
            scale = 0.01 if pence_quote else 1.0
            major_currency = "GBP" if pence_quote else raw_currency.upper()
            fx_rate = fetch_fx_rate(major_currency, base_currency) if major_currency != "?" else None
            position = {
                **item,
                "name": metadata.get("name") or symbol,
                "sector": metadata.get("sector") or "Unavailable",
                "industry": metadata.get("industry") or "Unavailable",
                "currency": "GBp" if pence_quote else raw_currency,
                "major_currency": major_currency,
                "price_scale": scale,
                "fx_rate": fx_rate,
                "metadata": metadata,
            }
            if float(item["shares"]) > 1e-8:
                history = fetch_history(symbol, period="1y", adjusted=False)
                historical_prices[symbol] = history
                close = pd.to_numeric(history.get("Close", pd.Series(dtype=float)), errors="coerce").dropna()
                if not close.empty:
                    price_now = float(close.iloc[-1])
                    previous = float(close.iloc[-2]) if len(close) > 1 else None
                    indicators = calculate_technical_indicators(history)
                    latest = indicators.iloc[-1] if not indicators.empty else pd.Series(dtype=float)
                    local_value = float(item["shares"]) * price_now * scale
                    cost_local = float(item["cost_basis"]) * scale
                    position.update(
                        {
                            "price": price_now,
                            "previous": previous,
                            "day_move_pct": (price_now / previous - 1) * 100 if previous else None,
                            "market_value_local": local_value,
                            "market_value_base": local_value * fx_rate if fx_rate is not None else None,
                            "cost_basis_local": cost_local,
                            "cost_basis_base": cost_local * fx_rate if fx_rate is not None and item.get("cost_known", True) else None,
                            "unrealized_base": (local_value - cost_local) * fx_rate if fx_rate is not None and item.get("cost_known", True) else None,
                            "realized_base": float(item["realized_pnl"]) * scale * fx_rate if fx_rate is not None and item.get("realized_known", True) else None,
                            "return_pct": (local_value / cost_local - 1) * 100 if cost_local > 0 and item.get("cost_known", True) else None,
                            "rsi": latest.get("RSI_14"),
                            "macd": latest.get("MACD"),
                            "atr": latest.get("ATR_14"),
                            "volume_ratio": get_volume_multiple(history),
                            "volatility_20": float(close.pct_change().dropna().tail(20).std(ddof=1) * (252 ** 0.5) * 100) if len(close) > 10 else None,
                            "max_drawdown": float(indicators["Drawdown"].min() * 100) if "Drawdown" in indicators and not indicators.empty else None,
                            "as_of": latest_bar_date(history),
                        }
                    )
            if float(item["shares"]) <= 1e-8:
                position["realized_base"] = float(item["realized_pnl"]) * scale * fx_rate if fx_rate is not None and item.get("realized_known", True) else None
            positions.append(position)

    active_positions = [position for position in positions if position["shares"] > 1e-8]
    priced_positions = [position for position in active_positions if position.get("price") is not None]
    all_market_values = len(priced_positions) == len(active_positions) and all(position.get("market_value_base") is not None for position in priced_positions)
    all_open_costs_known = all(position.get("cost_known", True) for position in active_positions)
    all_basis_values = all_market_values and all_open_costs_known and all(position.get("cost_basis_base") is not None for position in active_positions)
    realized_rows = [position for position in positions if float(position.get("realized_pnl") or 0) != 0]
    all_realized_known = all(position.get("realized_known", True) and position.get("realized_base") is not None for position in realized_rows)
    realized_total = sum(float(position["realized_base"]) for position in realized_rows) if all_realized_known else None
    market_total = sum(float(position["market_value_base"]) for position in priced_positions) if all_market_values else None
    basis_total = sum(float(position["cost_basis_base"]) for position in active_positions) if all_basis_values else None
    unrealized_total = market_total - basis_total if market_total is not None and basis_total is not None else None
    combined_gain = realized_total + unrealized_total if realized_total is not None and unrealized_total is not None else None
    day_total = sum(float(position["shares"]) * (float(position["price"]) - float(position["previous"])) * float(position["price_scale"]) * float(position["fx_rate"]) for position in priced_positions if position.get("previous") is not None and position.get("fx_rate") is not None) if len(priced_positions) == len(active_positions) and all(position.get("previous") is not None and position.get("fx_rate") is not None for position in active_positions) else None

    metrics = st.columns(5)
    metric_values = [
        (f"Market value · {base_currency}", format_number(market_total), None),
        (f"Open cost basis · {base_currency}", format_number(basis_total), None),
        (f"Unrealised P&L · {base_currency}", format_number(unrealized_total), format_percent(unrealized_total / basis_total * 100) if unrealized_total is not None and basis_total else None),
        (f"Realised P&L · {base_currency}", format_number(realized_total), None),
        (f"Total P&L · {base_currency}", format_number(combined_gain), format_percent(combined_gain / basis_total * 100) if combined_gain is not None and basis_total else None),
    ]
    for column, (label, value, delta) in zip(metrics, metric_values):
        with column:
            st.metric(label, value, delta=delta)
    if day_total is not None:
        st.caption(f"Daily change across open positions: {format_number(day_total)} {base_currency} · based on latest daily close versus previous close.")
    if not all_market_values:
        st.info("Some holding prices or FX rates are unavailable, so portfolio-wide base-currency totals and charts are incomplete.")
    if not all_open_costs_known:
        st.caption("An opening balance has no recorded purchase cost. Add or edit its cost in the transaction ledger before relying on portfolio P&L.")
    if realized_total is None and realized_rows:
        st.caption("Realised P&L is unavailable for one or more sales because the original lot cost or FX rate is missing.")

    portfolio_history = portfolio_value_history(transactions, active_positions, historical_prices, base_currency)
    view_tabs = st.tabs(["Portfolio value", "Allocation", "Holdings table"])
    with view_tabs[0]:
        chart_controls = st.columns([1, 3])
        with chart_controls[0]:
            portfolio_range = st.radio("History", ["1M", "3M", "6M", "1Y"], horizontal=True, key="portfolio_range")
        visible = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}[portfolio_range]
        if len(portfolio_history) >= 2:
            st.plotly_chart(portfolio_value_figure(portfolio_history, base_currency, visible), use_container_width=True, config={"displayModeBar": False})
            st.caption("Historical value marks the shares held on each date to daily closes and FX history where available. Legacy opening balances have no purchase date, so they are treated as held throughout the available chart history. Cash, dividends and sale proceeds are excluded; this is a holdings-value chart, not a cash-flow-adjusted return chart.")
        else:
            render_empty("Historical holdings value will appear when price history is available for every open position.")
    with view_tabs[1]:
        allocations = [position for position in active_positions if position.get("market_value_base") is not None and position["market_value_base"] > 0]
        allocation_col, sector_col = st.columns(2, gap="large")
        with allocation_col:
            if allocations:
                figure = go.Figure(go.Pie(labels=[f"{item['ticker']} · {item['name']}" for item in allocations], values=[item["market_value_base"] for item in allocations], hole=.66, marker={"colors": ["#a6f0ca", "#85a6ff", "#f2c879", "#c89bff", "#ff8e8e", "#79d5e6", "#ff9f8b", "#93d3a2"]}))
                figure.update_layout(height=390, margin={"l": 8, "r": 8, "t": 22, "b": 8}, paper_bgcolor="rgba(0,0,0,0)", font={"color": "#91a2b6", "family": "Manrope"}, legend={"orientation": "h", "y": -.08}, title=f"Holdings mix · {base_currency}")
                st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
            else:
                render_empty("Allocation needs current prices and FX rates for your holdings.")
        with sector_col:
            sector_values: dict[str, float] = {}
            for position in allocations:
                sector = str(position.get("sector") or "Unavailable")
                sector_values[sector] = sector_values.get(sector, 0.0) + float(position["market_value_base"])
            if sector_values:
                sector_frame = pd.Series(sector_values).sort_values()
                figure = go.Figure(go.Bar(x=sector_frame.values, y=sector_frame.index, orientation="h", marker={"color": "#85a6ff"}, text=[f"{value / market_total * 100:.1f}%" if market_total else "" for value in sector_frame.values], textposition="outside", hovertemplate="%{y}<br>Value: %{x:,.2f}<extra></extra>"))
                figure.update_layout(height=390, margin={"l": 8, "r": 35, "t": 22, "b": 8}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#91a2b6", "family": "Manrope"}, xaxis={"showgrid": False, "visible": False}, yaxis={"showgrid": False}, showlegend=False, title="Sector exposure")
                st.plotly_chart(figure, use_container_width=True, config={"displayModeBar": False})
            else:
                render_empty("Sector exposure is not available from the current company profiles.")
    with view_tabs[2]:
        total_for_weight = market_total or 0.0
        table_rows = []
        for position in active_positions:
            weight = float(position["market_value_base"]) / total_for_weight * 100 if position.get("market_value_base") is not None and total_for_weight else None
            table_rows.append(
                {
                    "Ticker": position["ticker"],
                    "Company": position["name"],
                    "Sector": position["sector"],
                    "Shares": position["shares"],
                    "Average cost / share": position["average_cost"] if position.get("cost_known", True) else None,
                    "Last close": position.get("price"),
                    "Quote currency": position["currency"],
                    f"Value · {base_currency}": position.get("market_value_base"),
                    "Weight %": weight,
                    "Day move %": position.get("day_move_pct"),
                    f"Open P&L · {base_currency}": position.get("unrealized_base"),
                    "RSI 14": position.get("rsi"),
                    "Price date": str(position.get("as_of") or "—"),
                }
            )
        st.dataframe(pd.DataFrame(table_rows), hide_index=True, use_container_width=True, column_config={"Shares": st.column_config.NumberColumn(format="%.4f"), "Average cost / share": st.column_config.NumberColumn(format="%.4f"), "Last close": st.column_config.NumberColumn(format="%.4f"), "Weight %": st.column_config.NumberColumn(format="%.1f%%"), "Day move %": st.column_config.NumberColumn(format="%.2f%%"), "RSI 14": st.column_config.NumberColumn(format="%.1f")})

    st.markdown('<div class="section-label">Holding deep dive</div>', unsafe_allow_html=True)
    labels = {position["ticker"]: f"{position['ticker']} · {position['name']}" for position in active_positions}
    selected_ticker = st.selectbox("Choose a holding", list(labels), format_func=lambda symbol: labels[symbol], key="portfolio_selected_ticker")
    selected = next(position for position in active_positions if position["ticker"] == selected_ticker)
    detail_history = fetch_history(selected_ticker, period="2y", adjusted=True)
    detail_meta = metadata_by_ticker.get(selected_ticker, {})
    xirr = calculate_xirr(transactions, selected_ticker, float(selected.get("price") or 0.0), float(selected["shares"]), selected.get("as_of") or london_now().date()) if selected.get("price") is not None else None
    details = st.columns(6)
    with details[0]:
        st.metric("Last close", f"{format_number(selected.get('price'))} {selected['currency']}")
    with details[1]:
        st.metric("Shares held", format_number(selected["shares"], 4))
    with details[2]:
        st.metric("Position value", f"{format_number(selected.get('market_value_base'))} {base_currency}")
    with details[3]:
        st.metric("Open P&L", f"{format_number(selected.get('unrealized_base'))} {base_currency}", delta=format_percent(selected.get("return_pct")) if selected.get("return_pct") is not None else None)
    with details[4]:
        st.metric("Realised P&L", f"{format_number(selected.get('realized_base'))} {base_currency}")
    with details[5]:
        st.metric("Money-weighted XIRR", format_percent(xirr * 100) if xirr is not None else "—")
    st.caption("XIRR annualises dated buys and sells plus today’s open position value. It is unavailable when a purchase date or cost is unknown, and it excludes dividends.")

    detail_tabs = st.tabs(["Price & indicators", "Relative performance", "Scenario estimate", "Recent news"])
    with detail_tabs[0]:
        fundamental_cols = st.columns(5)
        market_cap = detail_meta.get("market_cap")
        market_cap_text = f"{float(market_cap) / 1e9:.2f}B" if market_cap is not None and pd.notna(market_cap) else "—"
        metrics = [
            ("Sector", selected["sector"]),
            ("Industry", selected["industry"]),
            ("Market cap", market_cap_text),
            ("Trailing P/E", format_number(detail_meta.get("trailing_pe"), 1)),
            ("Beta", format_number(detail_meta.get("beta"), 2)),
        ]
        for column, (label, value) in zip(fundamental_cols, metrics):
            with column:
                render_metric_card(label, value)
        if not detail_history.empty:
            st.plotly_chart(forecast_figure(detail_history, {"history": detail_history}), use_container_width=True, config={"displayModeBar": False})
            st.caption(f"RSI 14: {format_number(selected.get('rsi'), 1)} · MACD: {format_number(selected.get('macd'))} · ATR 14: {format_number(selected.get('atr'))} {selected['currency']} · 20-session annualised volatility: {format_number(selected.get('volatility_20'), 1)}% · maximum drawdown in available sample: {format_number(selected.get('max_drawdown'), 1)}%.")
        else:
            render_empty("Price history for this holding is temporarily unavailable.")
    with detail_tabs[1]:
        benchmark_history = fetch_history(main_benchmark_symbol, period="2y", adjusted=True)
        if not detail_history.empty and not benchmark_history.empty:
            st.plotly_chart(portfolio_relative_figure(detail_history, benchmark_history, main_benchmark_name), use_container_width=True, config={"displayModeBar": False})
            st.caption(f"Both series are rebased to 0% at the first shared daily bar. This compares price performance with {main_benchmark_name}; it does not include a cash-flow adjustment for your trades.")
        else:
            render_empty("The holding or benchmark history is temporarily unavailable.")
    with detail_tabs[2]:
        control_cols = st.columns([.8, 1, 1, .9])
        with control_cols[0]:
            horizon = st.selectbox("Trading days", [5, 20, 60], index=1, key=f"portfolio_horizon_{selected_ticker}")
        with control_cols[1]:
            lookback = st.selectbox("Return lookback", [40, 60, 90, 120], index=1, key=f"portfolio_lookback_{selected_ticker}")
        with control_cols[2]:
            confidence = st.selectbox("Scenario range", [80, 90, 95], index=1, key=f"portfolio_confidence_{selected_ticker}")
        with control_cols[3]:
            method = st.selectbox("Model", ["Historical bootstrap", "EWMA volatility"], key=f"portfolio_model_{selected_ticker}")
        forecast = calculate_forecast(detail_history, horizon, lookback, confidence / 100, method, simulations=2000) if not detail_history.empty else None
        if forecast is None:
            render_empty("There is not enough price history for this scenario. Try a shorter lookback or refresh the ticker data.")
        else:
            price_scale = float(selected["price"]) / float(forecast["spot"]) if selected.get("price") and forecast.get("spot") else 1.0
            scenario_factor = float(selected["shares"]) * float(selected["price_scale"]) * float(selected["fx_rate"] or 0.0)
            scenario_cols = st.columns(4)
            scenario_values = [
                (f"Median · {horizon}d", forecast["median"] * price_scale, forecast["expected_return"]),
                (f"{confidence}% lower", forecast["lower"] * price_scale, None),
                (f"{confidence}% upper", forecast["upper"] * price_scale, None),
                ("Annualised volatility", forecast["annualized_vol"], None),
            ]
            for column, (label, value, delta) in zip(scenario_cols, scenario_values):
                with column:
                    suffix = "%" if label == "Annualised volatility" else f" {selected['currency']} / share"
                    st.metric(label, f"{format_number(value, 1)}{suffix}", delta=format_percent(delta) if delta is not None else None)
            if scenario_factor:
                st.caption(f"Median position-value scenario: {format_number(forecast['median'] * price_scale * scenario_factor)} {base_currency}; lower and upper scenarios: {format_number(forecast['lower'] * price_scale * scenario_factor)} to {format_number(forecast['upper'] * price_scale * scenario_factor)} {base_currency}. Uses the current share quantity and current FX conversion.")
            st.plotly_chart(portfolio_scenario_figure(detail_history, forecast, confidence), use_container_width=True, config={"displayModeBar": False})
            if method == "Historical bootstrap":
                scenario_formula = f"{forecast['simulations']:,} paths resample the last {lookback} daily log returns with replacement, then compound them over {horizon} trading days."
            else:
                scenario_formula = f"{forecast['simulations']:,} paths use the last {lookback} daily log returns and EWMA volatility with λ = 0.94 over {horizon} trading days."
            st.markdown(f'<div class="panel small-note">{escape(scenario_formula)} The shaded band is the central {confidence}% of simulated prices, not a confidence guarantee. Historical close data includes corporate-action adjustments; the position-value conversion scales it to the latest quote.</div>', unsafe_allow_html=True)
            score = evaluate_forecast(detail_history, lookback=lookback, horizon=horizon, test_days=126)
            if score:
                score_cols = st.columns(3)
                with score_cols[0]:
                    st.metric("Historical test windows", f"{score['samples']:,}")
                with score_cols[1]:
                    st.metric("Model mean abs. error", f"{score['model_mae_pct']:.2f}%")
                with score_cols[2]:
                    st.metric("No-change baseline error", f"{score['baseline_mae_pct']:.2f}%")
                st.caption(f"Historical direction accuracy: {score['directional_accuracy_pct']:.1f}% across prior rolling test windows. The scorecard evaluates historical point estimates; it does not validate future simulated ranges.")
            if st.button("Save this scenario to Forecast lab tracking", key=f"save_portfolio_forecast_{selected_ticker}_{horizon}_{lookback}_{method}"):
                _, was_added = record_forecast(selected_ticker, forecast["history"].index[-1], horizon, forecast, access_token)
                st.success("Scenario saved for later scoring." if was_added else "This matching scenario is already being tracked.")
    with detail_tabs[3]:
        articles = fetch_ticker_news(selected_ticker, count=8)
        if articles:
            for article in articles[:6]:
                render_news_card(article)
        else:
            render_empty("No recent headlines are available for this ticker.")

    render_transaction_ledger(transactions, access_token)


def save_report_for_region(now: datetime, region_name: str, benchmarks: list[dict], market_news: list[dict], gainers: pd.DataFrame, losers: pd.DataFrame) -> tuple[str, Path]:
    from analysis import build_daily_brief

    region_code = MARKET_REGIONS[region_name]["code"]
    headlines_by_ticker = {
        symbol: fetch_ticker_news(symbol, count=8)
        for symbol in pd.concat([gainers.head(5), losers.head(5)], ignore_index=True).get("symbol", pd.Series(dtype=str)).dropna().astype(str).unique()
    }
    status, status_detail = market_session_status(region_name, now)
    report = build_daily_brief(
        now,
        benchmarks,
        gainers,
        losers,
        market_news,
        headlines_by_ticker,
    )
    report_lines = report.splitlines()
    if report_lines:
        report_lines[0] = f"# Daily market brief — {region_name} — {now:%A, %d %B %Y}"
    session_line = f"Market session: {status_detail}"
    session_index = next((index for index, line in enumerate(report_lines) if line.startswith("Market session:")), None)
    if session_index is None:
        generated_index = next((index for index, line in enumerate(report_lines) if line.startswith("Generated at ")), 1)
        report_lines.insert(generated_index + 1, session_line)
    else:
        report_lines[session_index] = session_line
    report = "\n".join(report_lines)
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"market_brief_{region_code}_{now:%Y-%m-%d}.md"
    path.write_text(report, encoding="utf-8")
    return report, path


def render_daily_brief(region_name: str, now: datetime, benchmarks: list[dict], market_news: list[dict]) -> None:
    region_code = MARKET_REGIONS[region_name]["code"]
    report_date = f"{now:%Y-%m-%d}"
    session_state_date_key = f"daily_report_date_{region_code}"
    session_state_content_key = f"daily_report_content_{region_code}"
    report_path = REPORT_DIR / f"market_brief_{region_code}_{report_date}.md"

    st.markdown('<div class="section-label">Daily report archive</div>', unsafe_allow_html=True)
    st.caption(f"A dated report is created the first time this market’s Daily brief is opened each day. A scheduled task can create it while the dashboard is closed.")

    gainers, losers = fetch_movers("gainers", count=5, region=region_code), fetch_movers("losers", count=5, region=region_code)
    auto_created = False
    regenerated = False
    if st.session_state.get(session_state_date_key) != report_date:
        if report_path.exists():
            st.session_state[session_state_content_key] = report_path.read_text(encoding="utf-8")
            st.session_state[session_state_date_key] = report_date
        else:
            with st.spinner("Creating today’s report with recent mover headlines…"):
                content, _ = save_report_for_region(now, region_name, benchmarks, market_news, gainers, losers)
            st.session_state[session_state_content_key] = content
            st.session_state[session_state_date_key] = report_date
            auto_created = True

    action_col, _ = st.columns([1.4, 4])
    with action_col:
        if st.button("Regenerate today’s report", type="primary", key=f"regenerate_{region_code}"):
            with st.spinner("Refreshing the report’s headline matches…"):
                content, _ = save_report_for_region(now, region_name, benchmarks, market_news, gainers, losers)
            st.session_state[session_state_content_key] = content
            st.session_state[session_state_date_key] = report_date
            regenerated = True
    if auto_created:
        st.success(f"Created {report_path.relative_to(APP_DIR)}")
    elif regenerated:
        st.success(f"Updated {report_path.relative_to(APP_DIR)}")

    archive = sorted(REPORT_DIR.glob("market_brief_*.md"), reverse=True) if REPORT_DIR.exists() else []
    if not archive:
        render_empty("No reports have been archived for this market yet.")
        return
    selected_report = st.selectbox(
        "Browse saved reports",
        options=archive,
        format_func=lambda path: path.stem.replace("market_brief_", ""),
        key=f"report_archive_{region_code}",
    )
    if selected_report == report_path and st.session_state.get(session_state_content_key):
        content = st.session_state[session_state_content_key]
    else:
        try:
            content = selected_report.read_text(encoding="utf-8")
        except OSError:
            content = "This report could not be read from disk."
    st.markdown(content)
    st.download_button(
        "Download selected report",
        data=content,
        file_name=selected_report.name,
        mime="text/markdown",
        key=f"download_report_{region_code}",
    )


def main() -> None:
    apply_styles()
    user_session = render_access_gate()
    if user_session is None:
        return
    access_token = str(user_session["access_token"])
    now = london_now()

    with st.sidebar:
        st.markdown("## ◈ Market Brief")
        st.caption("Daily market intelligence")
        st.caption(f"Signed in as {user_session['email']}")
        st.button("Sign out", use_container_width=True, on_click=logout_user)
        region_name = st.selectbox("Market region", list(MARKET_REGIONS), key="market_region")
        st.caption("Market selection changes the benchmarks, headlines, and mover screen.")
        if st.button("↻  Refresh market data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.caption("Prices use Yahoo Finance daily bars. Headlines combine Yahoo Finance with FT, BBC Business and official central-bank feeds.")

    region_config = MARKET_REGIONS[region_name]
    with st.spinner(f"Loading {region_name} benchmarks and headlines…"):
        benchmarks = load_benchmarks(region_name)
        market_news = fetch_market_news(tuple(region_config["news"]), region_name=region_name)
    render_header(region_name, now, benchmarks, market_news)

    sections = ["Market pulse", "News desk", "Movers", "Watchlist", "Portfolio", "Forecast lab", "Daily brief"]
    page = st.radio("Dashboard section", sections, horizontal=True, label_visibility="collapsed", key="dashboard_section")

    if page == "Market pulse":
        render_market_pulse(region_name, benchmarks, market_news)
    elif page == "News desk":
        render_news_desk(region_name, market_news, now, fetch_rss_status(region_name))
    elif page == "Movers":
        render_movers(region_name, benchmarks)
    elif page == "Watchlist":
        render_watchlist(region_name, benchmarks, access_token)
    elif page == "Portfolio":
        render_portfolio(region_name, access_token)
    elif page == "Forecast lab":
        render_forecast_lab(access_token)
    elif page == "Daily brief":
        render_daily_brief(region_name, now, benchmarks, market_news)

    st.markdown(
        '<br><div class="small-note">Prices: Yahoo Finance daily bars · News: attributed publisher feeds · '
        'Headline matches are clues, and model outputs are illustrative scenarios.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
