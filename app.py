from __future__ import annotations

from datetime import datetime, time
from html import escape
import hashlib
import importlib
from pathlib import Path
from urllib.parse import quote, urlsplit
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
    fetch_market_news_bundle,
    fetch_movers,
    fetch_rss_status,
    fetch_ticker_metadata,
    search_tickers,
    fetch_ticker_news,
)
from forecast_store import load_forecasts, record_forecast, update_forecast_outcomes
from powerbi_export import build_powerbi_workbook, headline_table, history_table, profile_table
from portfolio_store import (
    add_transaction,
    calculate_positions,
    calculate_xirr,
    load_transactions,
    load_watchlist,
    save_transactions,
    save_watchlist,
)
from user_access import logout_user, render_access_gate


APP_DIR = Path(__file__).resolve().parent
REPORT_DIR = APP_DIR / "reports"
TIMEZONE = ZoneInfo("Europe/London")
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
    initial_sidebar_state="auto",
)


def apply_styles() -> None:
    st.markdown(
        """
        <style>
        :root {
            color-scheme: light;
            --ink: #182230;
            --muted: #526173;
            --line: #d9e0e8;
            --surface: #ffffff;
            --canvas: #f4f6f8;
            --orange: #a94f17;
            --orange-soft: #fff2e8;
            --teal: #167b78;
            --red: #b53c4b;
        }
        html, body, [class*="css"] { font-family: Inter, "Segoe UI", Arial, sans-serif; }
        .stApp { color:var(--ink); background:var(--canvas); }
        [data-testid="stHeader"] { background:rgba(244,246,248,.94); }
        [data-testid="stDecoration"] { height:3px; background:var(--orange); }
        [data-testid="stSidebar"] { background:var(--surface); border-right:1px solid var(--line); }
        [data-testid="stSidebar"] > div:first-child { padding-top:1rem; }
        [data-testid="stCaptionContainer"] { color:var(--muted); line-height:1.55; }
        .block-container { max-width:1840px; padding:1.25rem 1.6rem 3rem; }
        h1,h2,h3,h4 { color:var(--ink); font-family:Inter, "Segoe UI", Arial, sans-serif; letter-spacing:-.025em; }
        h2 { margin-top:.25rem; }
        a { color:#17615f; }
        a:hover { color:#7b3a12; }
        .side-brand { display:flex; align-items:center; gap:.72rem; margin:.15rem 0 1.15rem; }
        .side-brand-mark { display:grid; place-items:center; width:40px; height:40px; border-radius:12px; color:#fff; background:var(--orange); font-size:1.25rem; }
        .side-brand-name { color:var(--ink); font-weight:750; font-size:.82rem; letter-spacing:.11em; }
        .side-brand-sub { display:block; color:var(--muted); margin-top:3px; font-size:.58rem; letter-spacing:.12em; }
        .user-pill { display:flex; align-items:center; gap:.55rem; margin:.55rem 0 .85rem; padding:.55rem .7rem; color:#344255; border:1px solid var(--line); border-radius:10px; background:#f8fafc; font-size:.75rem; overflow-wrap:anywhere; }
        .user-dot { width:7px; height:7px; flex:0 0 7px; border-radius:50%; background:var(--orange); }
        .st-key-logout_button button { color:#344255; background:#fff; border-color:var(--line); }
        .nav-overline,.eyebrow,.section-label { color:#7b3a12; font-size:.68rem; font-weight:650; letter-spacing:.13em; text-transform:uppercase; }
        .nav-overline { margin:.45rem 0 .35rem; }
        .eyebrow { margin:.2rem 0 .45rem; }
        .section-label { color:#526173; margin:1.3rem 0 .75rem; }
        .st-key-dashboard_section { margin:.35rem 0 1rem; }
        .hero-shell { padding:1.3rem 1.45rem; margin:.2rem 0 1rem; border:1px solid var(--line); border-radius:16px; background:var(--surface); box-shadow:0 3px 14px rgba(24,34,48,.045); }
        .hero-topline { display:flex; align-items:center; justify-content:space-between; gap:1rem; }
        .hero-kicker { color:var(--muted); font-size:.67rem; font-weight:650; letter-spacing:.12em; text-transform:uppercase; }
        .session-badge { display:inline-flex; align-items:center; gap:.45rem; padding:.34rem .66rem; border:1px solid var(--line); border-radius:999px; background:#f8fafc; color:#344255; font-size:.7rem; }
        .session-dot { width:7px; height:7px; display:inline-block; border-radius:50%; background:#7c8796; }
        .session-badge.open .session-dot { background:var(--orange); }
        .hero-title { color:var(--ink); font-size:clamp(1.8rem,3.3vw,2.6rem); font-weight:760; letter-spacing:-.05em; margin:.55rem 0 0; line-height:1.1; }
        .hero-title .hero-accent { color:var(--orange); }
        .hero-sub { color:#435267; margin:.45rem 0 .8rem; line-height:1.55; }
        .hero-meta { display:flex; flex-wrap:wrap; gap:.45rem; }
        .hero-chip { display:inline-flex; align-items:center; gap:.35rem; padding:.4rem .58rem; border:1px solid var(--line); border-radius:8px; background:#f8fafc; color:#344255; font-size:.72rem; }
        .hero-chip b { color:var(--ink); font-weight:650; }
        .metric-card,div[data-testid="stMetric"] { color:var(--ink); border:1px solid var(--line); border-radius:12px; background:var(--surface); box-shadow:0 2px 8px rgba(24,34,48,.035); }
        .metric-card { min-height:96px; padding:14px 15px; }
        .metric-card,div[data-testid="stMetric"] { position:relative; transition:transform .16s ease,box-shadow .16s ease,border-color .16s ease; }
        .metric-card:hover,div[data-testid="stMetric"]:hover,.metric-card:focus-within,div[data-testid="stMetric"]:focus-within { z-index:5; transform:scale(1.035); border-color:#c87a43; box-shadow:0 8px 22px rgba(24,34,48,.13); }
        .metric-card:hover .metric-value,div[data-testid="stMetric"]:hover [data-testid="stMetricValue"] { font-weight:800; transform:scale(1.035); transform-origin:left center; }
        .metric-label,div[data-testid="stMetricLabel"] { color:var(--muted); font-size:.72rem; }
        .metric-value,div[data-testid="stMetricValue"] { color:var(--ink); font-weight:700; overflow-wrap:anywhere; transition:transform .16s ease,font-weight .16s ease; }
        .metric-change { margin-top:5px; font-size:.74rem; font-weight:650; }
        div[data-testid="stMetricDelta"] { color:var(--orange) !important; }
        div[data-testid="stMetricDelta"] svg { fill:currentColor; }
        .small-note { color:var(--muted); font-size:.84rem; line-height:1.6; }
        .panel { padding:16px 18px; border:1px solid var(--line); border-radius:13px; background:var(--surface); box-shadow:0 2px 8px rgba(24,34,48,.035); }
        .info-note { display:flex; align-items:flex-start; gap:.62rem; padding:.75rem .85rem; border:1px solid #e6c5a7; border-left:3px solid var(--orange); border-radius:10px; background:#fff7ed; color:#66340f; font-size:.83rem; line-height:1.55; }
        .info-note-mark { display:grid; place-items:center; flex:0 0 19px; width:19px; height:19px; margin-top:1px; border:1px solid #d29a70; border-radius:50%; color:#7b3a12; font-size:.7rem; font-weight:700; }
        .news-card { padding:13px 14px; margin:0 0 .5rem; border:1px solid var(--line); border-left:3px solid var(--teal); border-radius:11px; background:var(--surface); }
        .news-card:hover { border-color:#b8cac9; border-left-color:var(--teal); background:#fbfdfd; }
        .news-meta { color:var(--muted); font-size:.68rem; letter-spacing:.045em; line-height:1.6; margin-bottom:7px; text-transform:uppercase; }
        .news-title { color:var(--ink); font-size:.9rem; font-weight:700; line-height:1.45; overflow-wrap:anywhere; }
        .news-summary { color:#435267; font-size:.82rem; line-height:1.55; margin-top:6px; overflow-wrap:anywhere; }
        .news-card a { color:#17615f !important; text-decoration:none; }
        .news-card a:hover { color:#7b3a12 !important; text-decoration:underline; }
        .source-chip { display:inline-block; padding:.16rem .42rem; margin-right:.35rem; border:1px solid #d1dae1; border-radius:999px; background:#f1f5f7; color:#344255; font-size:.62rem; }
        .stButton button,.stDownloadButton button,.stLinkButton button { color:#fff; background:var(--orange); border:1px solid var(--orange); border-radius:9px; box-shadow:none; }
        .stButton button:hover,.stDownloadButton button:hover,.stLinkButton button:hover { color:#fff; background:#873c0f; border-color:#873c0f; }
        .stButton button:focus-visible,.stDownloadButton button:focus-visible,.stLinkButton button:focus-visible { outline:3px solid #f1b47f; outline-offset:2px; }
        div[role="radiogroup"] label { color:#344255; background:#fff; border-color:var(--line); }
        div[role="radiogroup"] label:hover { border-color:#c87a43; }
        div[role="radiogroup"] label:has(input:checked) { color:#77380f !important; border-color:#e5b38f !important; background:var(--orange-soft) !important; }
        div[role="radio"] { color:#344255 !important; }
        div[role="radio"] > div:first-child { border-color:#64748b !important; }
        div[role="radio"][aria-checked="true"] { color:#77380f !important; }
        div[role="radio"][aria-checked="true"] > div:first-child { border-color:var(--orange) !important; }
        div[role="radio"][aria-checked="true"] > div:first-child::after { background:var(--orange) !important; }
        div[role="checkbox"][aria-checked="true"] > div:first-child { border-color:var(--orange) !important; background:var(--orange) !important; }
        div[role="checkbox"][aria-checked="true"] svg { color:#ffffff !important; fill:#ffffff !important; }
        .st-key-dashboard_section [role="radiogroup"] { gap:.25rem; padding:.35rem; border:1px solid var(--line); border-radius:11px; background:#fff; }
        .st-key-dashboard_section [role="radiogroup"] label { border:1px solid transparent; background:transparent; }
        input[type="radio"],input[type="checkbox"] { accent-color:var(--orange) !important; }
        [data-baseweb="tag"],div[data-testid="stMultiSelect"] [data-baseweb="tag"] { color:#542b12 !important; background:#ffead8 !important; border:1px solid #e5b38f !important; }
        [data-baseweb="tag"] *,div[data-testid="stMultiSelect"] [data-baseweb="tag"] * { color:#542b12 !important; fill:#542b12 !important; }
        [role="option"][aria-selected="true"] { color:#542b12 !important; background:#ffead8 !important; }
        [role="listbox"],[role="option"] { color:var(--ink) !important; background:#fff !important; }
        div[data-testid="stSelectbox"] label,div[data-testid="stMultiSelect"] label,div[data-testid="stTextInput"] label,div[data-testid="stNumberInput"] label,div[data-testid="stDateInput"] label { color:#344255; }
        div[data-baseweb="select"] > div,div[data-baseweb="input"] > div,div[data-baseweb="textarea"] > div { color:var(--ink) !important; background:#fff !important; border-color:#cbd5df !important; }
        div[data-baseweb="select"] span,div[data-baseweb="input"] input,div[data-baseweb="textarea"] textarea { color:var(--ink) !important; }
        div[data-baseweb="select"] > div:hover,div[data-baseweb="input"] > div:hover,div[data-baseweb="textarea"] > div:hover { border-color:var(--orange); }
        div[data-testid="stPlotlyChart"] { border:1px solid var(--line); border-radius:12px; background:#fff; }
        [data-testid="stExpander"] { border:1px solid var(--line); border-radius:11px; background:#fff; }
        [data-testid="stExpander"] summary { color:var(--ink); }
        [data-testid="stTabs"] [role="tablist"] { border-bottom-color:var(--line); }
        [data-testid="stTabs"] button[role="tab"] { color:var(--muted); }
        [data-testid="stTabs"] button[role="tab"][aria-selected="true"] { color:#7b3a12; border-bottom-color:var(--orange); }
        div[data-testid="stAlert"],div[data-testid="stDataFrame"] { border-color:var(--line); background:#fff; }
        hr { border-color:var(--line); }
        ::selection { color:#fff; background:var(--orange); }
        @media (max-width:768px) {
            .block-container { padding:1rem .8rem 2.5rem; }
            .hero-shell { padding:1rem; border-radius:12px; }
            .hero-topline { align-items:flex-start; flex-direction:column; gap:.65rem; }
            .hero-title { font-size:2rem; }
            .hero-chip { font-size:.68rem; }
            [data-testid="stHorizontalBlock"] { flex-wrap:wrap !important; gap:.65rem !important; }
            [data-testid="stHorizontalBlock"] > [data-testid="column"] { flex:1 1 100% !important; min-width:100% !important; }
            .st-key-dashboard_section [role="radiogroup"] { flex-wrap:wrap; gap:.28rem; }
            .st-key-dashboard_section [role="radiogroup"] label { padding:.42rem .58rem; font-size:.78rem; }
            .stButton button,.stDownloadButton button { min-height:44px; }
        }
        @media (max-width:420px) {
            .block-container { padding-left:.55rem; padding-right:.55rem; }
            .hero-title { font-size:1.75rem; }
            .hero-chip { width:100%; }
            .panel { padding:13px; }
            .metric-value { font-size:1.24rem; }
            [data-testid="stTabs"] button[role="tab"] { padding:.42rem .54rem; font-size:.78rem; }
        }
        </style>
        """,
        unsafe_allow_html=True,
    )
def london_now() -> datetime:
    return datetime.now(TIMEZONE)


def finite_float(value: object) -> float | None:
    try:
        number = float(value)
    except (TypeError, ValueError, OverflowError):
        return None
    return number if np.isfinite(number) else None


def ticker_option_label(symbol: str, details: dict) -> str:
    parts = [str(symbol).strip(), str(details.get("name") or "").strip(), str(details.get("exchange") or "").strip()]
    return " · ".join(part for part in parts if part)


def format_number(value: object, decimals: int = 2) -> str:
    number = finite_float(value)
    return f"{number:,.{decimals}f}" if number is not None else "—"


def format_percent(value: object) -> str:
    number = finite_float(value)
    return f"{number:+.2f}%" if number is not None else "—"


def render_metric_card(label: str, value: str, change: float | None = None, detail: str = "") -> None:
    change_html = ""
    change_value = finite_float(change)
    if change_value is not None:
        color = "#b95413" if change_value >= 0 else "#b53c4b"
        change_html = f'<div class="metric-change" style="color:{color}">{format_percent(change_value)} today</div>'
    detail_html = f'<div class="small-note">{escape(detail)}</div>' if detail else ""
    st.markdown(
        f'<div class="metric-card"><div class="metric-label">{escape(label)}</div>'
        f'<div class="metric-value">{escape(value)}</div>{change_html}{detail_html}</div>',
        unsafe_allow_html=True,
    )


def render_chart(figure: go.Figure, **kwargs) -> None:
    """Render every Plotly chart with a readable light theme and useful controls."""
    font_family = "Inter, Segoe UI, Arial, sans-serif"
    figure.update_layout(
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"family": font_family, "size": 13, "color": "#182230"},
        hoverlabel={
            "bgcolor": "#ffffff",
            "bordercolor": "#a94f17",
            "font": {"family": font_family, "size": 14, "color": "#182230"},
        },
    )
    figure.update_xaxes(tickfont={"family": font_family, "size": 12, "color": "#344255"})
    figure.update_yaxes(
        tickfont={"family": font_family, "size": 12, "color": "#344255"},
        title_font={"family": font_family, "size": 12, "color": "#344255"},
        gridcolor="#e1e7ed",
    )
    figure.update_annotations(font={"family": font_family, "size": 13, "color": "#182230"})

    config = dict(kwargs.pop("config", {}) or {})
    config.update(
        {
            "responsive": True,
            "displayModeBar": "hover",
            "displaylogo": False,
            "toImageButtonOptions": {
                "format": "png",
                "filename": "market-brief-chart",
                "width": 1400,
                "height": 800,
                "scale": 2,
            },
        }
    )
    kwargs["config"] = config
    kwargs["theme"] = None
    kwargs.setdefault("use_container_width", True)
    getattr(st, "plotly_chart")(figure, **kwargs)


def render_empty(message: str) -> None:
    st.markdown(f'<div class="panel small-note">{escape(message)}</div>', unsafe_allow_html=True)


def render_info(message: str) -> None:
    st.markdown(
        f'<div class="info-note"><span class="info-note-mark">i</span><span>{escape(message)}</span></div>',
        unsafe_allow_html=True,
    )


def open_company_explorer(symbol: str) -> None:
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        return
    st.session_state["company_explorer_query"] = symbol
    st.session_state["company_explorer_symbol"] = symbol
    st.session_state.pop("company_explorer_choice", None)
    st.session_state["dashboard_section"] = "Company explorer"


def open_forecast_lab(symbol: str) -> None:
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        return
    st.session_state["forecast_ticker"] = symbol
    st.session_state.pop("forecast_ticker_choice", None)
    st.session_state["dashboard_section"] = "Forecast lab"


def clear_forecast_choice() -> None:
    st.session_state.pop("forecast_ticker_choice", None)


def clear_company_choice() -> None:
    st.session_state.pop("company_explorer_choice", None)


def select_saved_company() -> None:
    symbol = str(st.session_state.get("company_watchlist_pick") or "").strip().upper()
    if not symbol or symbol == "CHOOSE A SAVED COMPANY":
        return
    st.session_state["company_explorer_query"] = symbol
    st.session_state["company_explorer_symbol"] = symbol
    st.session_state.pop("company_explorer_choice", None)
    st.session_state["company_watchlist_pick"] = "Choose a saved company"


def toggle_company_watchlist(symbol: str, access_token: str) -> None:
    ticker = str(symbol or "").strip().upper()
    try:
        current = load_watchlist(access_token)
        if ticker in current:
            updated = [item for item in current if item != ticker]
            save_watchlist(updated, access_token)
            st.session_state["company_watchlist_notice"] = ("success", f"{ticker} removed from your starred companies.")
            if st.session_state.get("company_watchlist_pick") == ticker:
                st.session_state["company_watchlist_pick"] = "Choose a saved company"
        else:
            save_watchlist([*current, ticker], access_token)
            st.session_state["company_watchlist_notice"] = ("success", f"{ticker} added to your starred companies.")
    except ValueError as error:
        st.session_state["company_watchlist_notice"] = ("error", f"Watchlist update failed: {error}")


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
        return "No benchmark bars returned"
    days_old = (now.date() - date_value).days
    if days_old <= 1:
        return f"Latest daily bar: {date_value:%d %b}"
    if days_old <= 4:
        return f"Last daily bar: {date_value:%d %b} ({days_old} calendar days ago)"
    return f"Stale price data · last daily bar {date_value:%d %b}"


def headline_freshness(articles: list[dict], now: datetime) -> str:
    published = [item.get("published") for item in articles if item.get("published")]
    if not published:
        return "No timestamped headlines"
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
        close = pd.to_numeric(history["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        close = close[close > 0]
        if close.empty:
            continue
        latest = float(close.iloc[-1])
        previous = float(close.iloc[-2]) if len(close) > 1 else None
        change = (latest / previous - 1) * 100 if previous is not None and previous > 0 else None
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


def render_header(region_name: str, now: datetime, benchmarks: list[dict], market_news: list[dict]) -> None:
    session, session_detail = market_session_status(region_name, now)
    benchmark_date = max((row["as_of"] for row in benchmarks if row.get("as_of")), default=None)
    price_status = data_freshness_text(benchmark_date, now)
    news_status = headline_freshness(market_news, now)
    session_class = "open" if session == "Likely open" else "closed"
    st.markdown(
        f'<section class="hero-shell">'
        f'<div class="hero-topline"><div class="hero-kicker">MARKET BRIEF &nbsp;·&nbsp; DAILY INTELLIGENCE</div>'
        f'<div class="session-badge {session_class}"><span class="session-dot"></span>{escape(session)}</div></div>'
        f'<h1 class="hero-title">Your markets, <span class="hero-accent">in context.</span></h1>'
        f'<p class="hero-sub">Daily prices, trusted headlines, company research and your private portfolio in one place.</p>'
        f'<div class="hero-meta">'
        f'<span class="hero-chip">Market <b>{escape(region_name)}</b></span>'
        f'<span class="hero-chip">Prices <b>{escape(price_status)}</b></span>'
        f'<span class="hero-chip">News <b>{escape(news_status)}</b></span>'
        f'<span class="hero-chip">Updated <b>{now:%d %b · %H:%M} London</b></span>'
        f'</div></section>',
        unsafe_allow_html=True,
    )
    st.caption(f"{session_detail}. Prices are Yahoo Finance daily bars and can be delayed; session hours do not account for exchange holidays.")
    if benchmark_date and (now.date() - benchmark_date).days > 4:
        st.warning("The latest available benchmark bar is several days old. The app labels prices by their actual bar date.")


def render_price_history(history: pd.DataFrame, title: str, color: str = "#167b78") -> None:
    if history.empty or "Close" not in history:
        render_info("Yahoo Finance returned no daily bars, so the chart is omitted.")
        return
    figure = go.Figure(
        go.Scatter(
            x=history.index,
            y=history["Close"],
            mode="lines",
            name=title,
            line={"color": color, "width": 3},
            hovertemplate="%{x|%d %b %Y}<br>Close: %{y:,.2f}<extra></extra>",
        )
    )
    figure.update_layout(
        title={"text": title, "x": 0.02, "xanchor": "left", "font": {"size": 15}},
        height=355,
        margin={"l": 10, "r": 12, "t": 50, "b": 18},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"color": "#182230", "family": "Inter, Segoe UI, Arial, sans-serif", "size": 13},
        xaxis={"showgrid": False, "zeroline": False},
        yaxis={"gridcolor": "#e1e7ed", "zeroline": False, "tickformat": ",.2f"},
        showlegend=False,
        hovermode="x unified",
    )
    render_chart(figure, use_container_width=True, config={"displayModeBar": False, "responsive": True})


def market_lens_figure(history: pd.DataFrame, title: str, visible_sessions: int, overlays: list[str]) -> go.Figure:
    indicators = calculate_technical_indicators(history).tail(visible_sessions)
    figure = go.Figure()
    figure.add_trace(
        go.Scatter(
            x=indicators.index,
            y=indicators["Close"],
            mode="lines",
            name=title,
            line={"color": "#167b78", "width": 3},
            hovertemplate="%{x|%d %b %Y}<br>Close: %{y:,.2f}<extra></extra>",
        )
    )
    if "Bollinger Bands" in overlays and {"BB_lower", "BB_upper"}.issubset(indicators.columns):
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["BB_lower"], name="Bollinger lower", line={"color": "rgba(113,85,168,.68)", "width": 1.2}, hovertemplate="%{x|%d %b %Y}<br>Lower band: %{y:,.2f}<extra></extra>"))
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["BB_upper"], name="Bollinger upper", line={"color": "rgba(113,85,168,.68)", "width": 1.2}, fill="tonexty", fillcolor="rgba(113,85,168,.08)", hovertemplate="%{x|%d %b %Y}<br>Upper band: %{y:,.2f}<extra></extra>"))
    if "SMA 20" in overlays and "SMA_20" in indicators:
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_20"], name="SMA 20", line={"color": "#7155a8", "width": 1.8}, hovertemplate="%{x|%d %b %Y}<br>SMA 20: %{y:,.2f}<extra></extra>"))
    if "SMA 50" in overlays and "SMA_50" in indicators:
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_50"], name="SMA 50", line={"color": "#b95413", "width": 1.8}, hovertemplate="%{x|%d %b %Y}<br>SMA 50: %{y:,.2f}<extra></extra>"))
    if "SMA 200" in overlays and "SMA_200" in indicators:
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_200"], name="SMA 200", line={"color": "#344255", "width": 2, "dash": "dash"}, hovertemplate="%{x|%d %b %Y}<br>SMA 200: %{y:,.2f}<extra></extra>"))
    range_columns = ["Close"]
    if "Bollinger Bands" in overlays:
        range_columns.extend(["BB_lower", "BB_upper"])
    chart_values = pd.concat(
        [pd.to_numeric(indicators[column], errors="coerce") for column in range_columns if column in indicators],
        axis=1,
    ).replace([np.inf, -np.inf], np.nan).stack().dropna()
    if not chart_values.empty:
        low, high = float(chart_values.min()), float(chart_values.max())
        padding = (high - low) * .08 if high > low else max(abs(high) * .02, 1.0)
        price_range = [max(0.0, low - padding), high + padding]
    else:
        price_range = None
    figure.update_layout(
        height=440,
        margin={"l": 72, "r": 18, "t": 74, "b": 44},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"color": "#182230", "family": "Inter, Segoe UI, Arial, sans-serif", "size": 13},
        xaxis={"showgrid": False, "zeroline": False, "rangeslider": {"visible": False}, "tickformat": "%d %b" if visible_sessions <= 63 else "%b %Y"},
        yaxis={"gridcolor": "#e1e7ed", "zeroline": False, "tickformat": ",.2f", "range": price_range, "title": {"text": "Index level", "font": {"color": "#344255", "size": 12}}},
        title={"text": f"{title} · daily close", "x": 0.02, "xanchor": "left", "font": {"size": 17, "color": "#182230"}},
        legend={"orientation": "h", "y": 1.06, "x": 0, "font": {"size": 12, "color": "#344255"}},
        hovermode="x unified",
    )
    return figure


def benchmark_moves_figure(benchmarks: list[dict]) -> go.Figure | None:
    rows = [
        (str(row.get("label") or row.get("symbol") or "Index"), finite_float(row.get("change")))
        for row in benchmarks
    ]
    rows = [(label, value) for label, value in rows if value is not None]
    if not rows:
        return None
    rows.sort(key=lambda item: item[1])
    labels, changes = zip(*rows)
    colors = ["#b95413" if value >= 0 else "#b53c4b" for value in changes]
    max_abs = max(abs(value) for value in changes)
    padding = max(max_abs * .3, .05)
    figure = go.Figure(
        go.Bar(
            x=list(changes),
            y=list(labels),
            orientation="h",
            marker={"color": colors, "line": {"color": "#ffffff", "width": 1}},
            text=[f"{value:+.2f}%" for value in changes],
            textposition="outside",
            textfont={"color": "#182230", "size": 13},
            cliponaxis=False,
            hovertemplate="%{y}<br>Move: %{x:+.2f}%<extra></extra>",
        )
    )
    figure.update_layout(
        height=max(145, 58 * len(rows)),
        margin={"l": 10, "r": 70, "t": 48, "b": 24},
        title={"text": "Benchmark moves · latest daily bars", "x": .02, "xanchor": "left", "font": {"size": 16, "color": "#182230"}},
        xaxis={"title": {"text": "Change versus prior close (%)", "font": {"color": "#344255"}}, "range": [-max_abs - padding, max_abs + padding], "zeroline": True, "zerolinecolor": "#526173", "zerolinewidth": 1.5, "ticksuffix": "%", "gridcolor": "#e1e7ed"},
        yaxis={"showgrid": False, "automargin": True},
        showlegend=False,
    )
    return figure


def render_market_pulse(
    region_name: str,
    benchmarks: list[dict],
    market_news: list[dict],
    now: datetime,
    feed_status: list[dict],
) -> None:
    """Compact market and news desk, with missing provider fields omitted honestly."""
    st.markdown('<div class="eyebrow">Markets</div>', unsafe_allow_html=True)
    st.markdown("## Market & news")
    st.caption("A concise market read, price trend and attributed headlines for the selected region.")

    if benchmarks:
        cards = st.columns(min(4, len(benchmarks)))
        for column, row in zip(cards, benchmarks):
            with column:
                date_label = f"Daily bar · {row['as_of']:%d %b}" if row.get("as_of") else "Daily bar"
                render_metric_card(str(row.get("label") or "Index"), format_number(row.get("price")), row.get("change"), date_label)
    else:
        render_info(f"Yahoo Finance returned no benchmark bars for {region_name}. Use Refresh market data to retry.")

    moves_figure = benchmark_moves_figure(benchmarks)
    if moves_figure is not None:
        render_chart(moves_figure, key=f"benchmark_moves_{region_name}")

    main_symbol = next(iter(MARKET_REGIONS[region_name]["benchmarks"]))
    main_label = MARKET_REGIONS[region_name]["benchmarks"][main_symbol]
    history = fetch_history(main_symbol, period="1y", adjusted=True)
    indicators = calculate_technical_indicators(history)
    if not indicators.empty:
        close = pd.to_numeric(indicators["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
        returns = close.pct_change().dropna()
        risk_values: list[tuple[str, str, str]] = []
        if len(close) >= 21:
            risk_values.append(("20-session return", format_percent((close.iloc[-1] / close.iloc[-21] - 1) * 100), "close-to-close"))
        if len(returns) >= 20:
            annualized_volatility = returns.tail(20).std(ddof=1) * np.sqrt(252) * 100
            risk_values.append(("20-session volatility", f"{annualized_volatility:.1f}%", "annualised · 252 sessions"))
        if len(close) >= 2:
            drawdown = (close.iloc[-1] / close.tail(252).max() - 1) * 100
            risk_values.append(("Drawdown from sample high", format_percent(drawdown), "latest close vs 1-year sample high"))
        latest_rsi = indicators["RSI_14"].iloc[-1] if "RSI_14" in indicators else np.nan
        if pd.notna(latest_rsi):
            risk_values.append(("RSI · 14", format_number(latest_rsi, 1), "momentum · scale 0–100"))
        if risk_values:
            st.markdown('<div class="section-label">Trend & risk</div>', unsafe_allow_html=True)
            risk_cols = st.columns(min(4, len(risk_values)))
            for column, (label, value, detail) in zip(risk_cols, risk_values):
                with column:
                    render_metric_card(label, value, detail=detail)

    source_names = sorted(
        {str(item.get("publisher") or "Unknown") for item in market_news}
        | {str(item.get("publisher") or "") for item in feed_status if item.get("publisher") and item.get("kind") != "News search"}
    )
    topics = sorted({
        topic
        for article in market_news
        for topic, terms in NEWS_TOPIC_TERMS.items()
        if any(term in f" {article.get('title', '')} {article.get('summary', '')} ".lower() for term in terms)
    })
    with st.expander("Filter headlines", expanded=False):
        filter_cols = st.columns([1.2, .9, 1.1, 1.5])
        with filter_cols[0]:
            source_filter = st.selectbox("Publisher", ["All sources", "Yahoo Finance stories", *source_names], key=f"market_source_{region_name}")
        with filter_cols[1]:
            age_filter = st.selectbox("Time range", ["24 hours", "3 days", "All available"], index=1, key=f"market_age_{region_name}")
        with filter_cols[2]:
            topic_filter = st.selectbox("Theme", ["All themes", *topics], key=f"market_topic_{region_name}")
        with filter_cols[3]:
            search = st.text_input("Search stories", placeholder="Company, rates, inflation…", key=f"market_search_{region_name}").strip().lower()

    def topic_for(article: dict) -> str:
        text = f" {article.get('title', '')} {article.get('summary', '')} ".lower()
        for topic, terms in NEWS_TOPIC_TERMS.items():
            if any(term in text for term in terms):
                return topic
        return "Other"

    cutoff_hours = {"24 hours": 24, "3 days": 72}.get(age_filter)
    filtered: list[dict] = []
    for article in market_news:
        if source_filter == "Yahoo Finance stories" and article.get("source_kind") != "Yahoo Finance":
            continue
        if source_filter not in {"All sources", "Yahoo Finance stories"} and article.get("publisher") != source_filter:
            continue
        if topic_filter != "All themes" and topic_for(article) != topic_filter:
            continue
        published = article.get("published")
        if cutoff_hours is not None:
            if published is None:
                continue
            if published.tzinfo is None:
                published = published.replace(tzinfo=TIMEZONE)
            age = (now - published.astimezone(TIMEZONE)).total_seconds() / 3600
            if age < 0 or age > cutoff_hours:
                continue
        if search and search not in f"{article.get('title', '')} {article.get('summary', '')} {article.get('publisher', '')}".lower():
            continue
        filtered.append(article)
    filtered.sort(key=lambda item: item.get("published") or datetime.min.replace(tzinfo=TIMEZONE), reverse=True)

    chart_col, news_col = st.columns([1.4, 1], gap="large")
    with chart_col:
        st.markdown(f'<div class="section-label">{escape(main_label)} · price history</div>', unsafe_allow_html=True)
        range_cols = st.columns([.8, 1.4])
        with range_cols[0]:
            range_name = st.selectbox("Chart period", ["1M", "3M", "6M", "1Y"], index=3, key=f"market_range_{region_name}")
        with range_cols[1]:
            overlays = st.multiselect("Indicators", ["SMA 20", "SMA 50", "SMA 200", "Bollinger Bands"], default=["SMA 20", "SMA 50"], key=f"market_overlays_{region_name}")
        if history.empty:
            render_info("No daily bars were returned for the benchmark, so the chart and technical metrics are omitted.")
        else:
            visible_sessions = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}[range_name]
            render_chart(market_lens_figure(history, main_label, visible_sessions, overlays))
            st.caption(f"Latest chart bar: {latest_bar_date(history):%d %b %Y}. The price axis fits the displayed range; hover a point for its exact close. Indicators describe historical prices, not forecasts.")
    with news_col:
        st.markdown('<div class="section-label">Latest headlines</div>', unsafe_allow_html=True)
        if filtered:
            for article in filtered[:4]:
                render_news_card(article)
            st.caption(f"Showing {min(4, len(filtered))} of {len(filtered)} matching stories. RSS headlines link to the publisher; FT subscriber stories open on FT.")
        elif market_news:
            render_info("No stories match these filters. Widen the time range or clear the search.")
        else:
            render_info("No stories arrived from the current feeds. Open source coverage below to see which feeds responded.")

    with st.expander(f"All matching headlines · {len(filtered)}", expanded=False):
        if filtered:
            for article in filtered[4:30]:
                render_news_card(article)
            if len(filtered) > 30:
                st.caption(f"Showing the first 30 of {len(filtered)} results.")
        else:
            st.caption("There are no matching stories to show.")
    with st.expander("Source coverage and data notes", expanded=False):
        if feed_status:
            source_table = pd.DataFrame(
                [{"Source": item.get("publisher"), "Type": item.get("kind"), "Status": item.get("status"), "Items": item.get("stories", 0)} for item in feed_status]
            )
            st.dataframe(source_table, hide_index=True, use_container_width=True)
        st.caption("Market news combines Yahoo Finance search results, Financial Times and BBC RSS metadata, and official central-bank feeds. A headline association is context to investigate, not proof of a price catalyst.")
        st.caption("Price history is fetched from Yahoo Finance and cached briefly. Daily bars may be delayed; use the displayed bar date when interpreting the chart.")


def render_company_explorer(region_name: str, access_token: str) -> None:
    st.markdown('<div class="eyebrow">Research</div>', unsafe_allow_html=True)
    st.markdown("## Company explorer")
    st.caption("Search a company, open one of your starred tickers, and inspect the price history, technical indicators and related stories.")

    try:
        watchlist = load_watchlist(access_token)
    except ValueError as error:
        watchlist = []
        render_info(f"Saved companies could not be loaded: {error}")
    notice = st.session_state.pop("company_watchlist_notice", None)
    if notice:
        kind, message = notice
        (st.error if kind == "error" else st.success)(message)
    if watchlist:
        st.selectbox(
            "★ Starred companies",
            ["Choose a saved company", *watchlist],
            key="company_watchlist_pick",
            on_change=select_saved_company,
        )
    else:
        st.caption("Your starred companies will appear here for quick access.")

    query = st.text_input(
        "Search by company or ticker",
        placeholder="Try Microsoft, MSFT or LLOY.L",
        key="company_explorer_query",
        on_change=clear_company_choice,
        help="Choose a Yahoo Finance search result below to avoid selecting the wrong ticker.",
    ).strip()
    matches = search_tickers(query) if len(query) >= 2 else []
    known_symbol = str(st.session_state.get("company_explorer_symbol") or "").upper()
    if matches is None:
        if known_symbol and query.upper() == known_symbol:
            symbol = known_symbol
        else:
            render_info("Yahoo Finance company search did not respond. Refresh market data and try again.")
            return
    elif not matches:
        if len(query) < 2:
            return
        render_info("No matching companies were returned. Check the spelling or add an exchange suffix such as .L.")
        return
    else:
        details = {match["symbol"]: match for match in matches}
        options = list(details)
        default_index = options.index(known_symbol) if known_symbol in details else 0
        symbol = st.selectbox(
            "Select the exact company",
            options=options,
            index=default_index,
            format_func=lambda item: ticker_option_label(item, details[item]),
            key="company_explorer_choice",
        )
        st.session_state["company_explorer_symbol"] = symbol

    is_saved = symbol in watchlist
    metadata = fetch_ticker_metadata(symbol)
    name = str(metadata.get("name") or details.get(symbol, {}).get("name") or symbol) if matches else str(metadata.get("name") or symbol)
    with st.spinner(f"Loading {name} prices and headlines…"):
        history = fetch_history(symbol, period="2y", adjusted=True)
        articles = fetch_ticker_news(symbol, count=10)

    heading_col, star_col = st.columns([6, 1], vertical_alignment="center")
    with heading_col:
        st.markdown(f"### {escape(name)} <span class='small-note'>· {escape(symbol)}</span>", unsafe_allow_html=True)
    with star_col:
        st.button(
            "★" if is_saved else "☆",
            key=f"company_star_{symbol}",
            help="Remove from your starred companies" if is_saved else "Add to your starred companies",
            type="secondary",
            on_click=toggle_company_watchlist,
            args=(symbol, access_token),
        )
    st.link_button("Yahoo Finance profile ↗", f"https://finance.yahoo.com/quote/{quote(symbol, safe='')}/")

    if history.empty or "Close" not in history:
        render_info("Yahoo Finance returned no daily price bars for this ticker. The saved-company control and any returned headlines remain available.")
        if articles:
            for article in articles[:6]:
                render_news_card(article)
        elif len(query) >= 2:
            st.caption("No related headlines were returned for this ticker.")
        return

    close = pd.to_numeric(history["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    indicators = calculate_technical_indicators(history)
    latest = indicators.iloc[-1] if not indicators.empty else pd.Series(dtype=float)
    returns = close.pct_change().dropna()
    metrics: list[tuple[str, str]] = []
    currency = str(metadata.get("currency") or "").strip()
    if not close.empty:
        metrics.append(("Latest adjusted close", f"{format_number(close.iloc[-1])} {currency}".strip()))
    if len(close) >= 2:
        metrics.append(("1-session move", format_percent((close.iloc[-1] / close.iloc[-2] - 1) * 100)))
    if len(close) >= 21:
        metrics.append(("20-session return", format_percent((close.iloc[-1] / close.iloc[-21] - 1) * 100)))
    rsi = latest.get("RSI_14")
    if pd.notna(rsi):
        metrics.append(("RSI · 14", format_number(rsi, 1)))
    if len(returns) >= 20:
        volatility = returns.tail(20).std(ddof=1) * np.sqrt(252) * 100
        metrics.append(("20-session volatility", f"{volatility:.1f}% annualised"))
    if metrics:
        metric_cols = st.columns(min(5, len(metrics)))
        for column, (label, value) in zip(metric_cols, metrics):
            with column:
                render_metric_card(label, value)

    profile_metrics: list[tuple[str, str]] = []
    for key, label in (("sector", "Sector"), ("industry", "Industry")):
        value = metadata.get(key)
        if value:
            profile_metrics.append((label, str(value)))
    market_cap = metadata.get("market_cap")
    if finite_float(market_cap) is not None:
        profile_metrics.append((f"Market cap · {currency}".strip(" ·"), f"{finite_float(market_cap) / 1e9:,.2f}B"))
    for key, label in (("trailing_pe", "Trailing P/E"), ("beta", "Beta")):
        value = metadata.get(key)
        if finite_float(value) is not None:
            profile_metrics.append((label, format_number(value, 2)))
    if profile_metrics:
        st.markdown('<div class="section-label">Company profile</div>', unsafe_allow_html=True)
        profile_cols = st.columns(min(5, len(profile_metrics)))
        for column, (label, value) in zip(profile_cols, profile_metrics):
            with column:
                render_metric_card(label, value)

    chart_tab, technical_tab, news_tab = st.tabs(["Price chart", "Technical indicators", "Headlines"])
    with chart_tab:
        chart_controls = st.columns([1, 2])
        with chart_controls[0]:
            chart_range = st.selectbox("History", ["1M", "3M", "6M", "1Y", "2Y"], index=3, key=f"company_range_{symbol}")
        with chart_controls[1]:
            overlays = st.multiselect("Overlay indicators", ["SMA 20", "SMA 50", "SMA 200", "Bollinger Bands"], default=["SMA 20", "SMA 50"], key=f"company_overlays_{symbol}")
        sessions = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252, "2Y": 504}[chart_range]
        render_chart(market_lens_figure(history, name, sessions, overlays), use_container_width=True, config={"displayModeBar": False, "responsive": True})
        drawdown = indicators["Drawdown"].min() * 100 if "Drawdown" in indicators and not indicators.empty else None
        date_label = latest_bar_date(history)
        notes = [f"Yahoo Finance adjusted daily bars through {date_label:%d %b %Y}" if date_label else "Yahoo Finance adjusted daily bars"]
        if drawdown is not None and pd.notna(drawdown):
            notes.append(f"maximum drawdown in this sample {drawdown:.1f}%")
        st.caption(" · ".join(notes) + ". Indicators describe observed prices, not future returns.")
        st.button("Open this ticker in Forecast Lab ↗", key=f"company_forecast_{symbol}", on_click=open_forecast_lab, args=(symbol,))
    with technical_tab:
        render_chart(forecast_figure(history, {"history": history}, "Adjusted daily price"), use_container_width=True, config={"displayModeBar": False, "responsive": True})
        indicator_values = []
        for key, label, decimals in (("MACD", "MACD", 3), ("MACD_signal", "MACD signal", 3), ("ATR_14", "ATR · 14", 2), ("RSI_14", "RSI · 14", 1)):
            value = latest.get(key)
            if finite_float(value) is not None:
                indicator_values.append(f"{label}: {format_number(value, decimals)}")
        if finite_float(metadata.get("beta")) is not None:
            indicator_values.append(f"Beta: {format_number(metadata['beta'], 2)}")
        if indicator_values:
            st.caption(" · ".join(indicator_values))
        st.caption("RSI uses Wilder's 14-session smoothing; MACD uses 12- and 26-session EMAs with a 9-session signal; ATR uses Wilder's smoothed true range.")
    with news_tab:
        if articles:
            for article in articles[:8]:
                render_news_card(article)
        else:
            st.caption("No ticker-specific stories were returned by the connected feeds.")


def forecast_figure(history: pd.DataFrame, forecast: dict, price_label: str = "Daily price") -> go.Figure:
    indicators = calculate_technical_indicators(forecast["history"]).tail(150)
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
                name=price_label,
                increasing_line_color="#167b78",
                decreasing_line_color="#b53c4b",
            ),
            row=1,
            col=1,
        )
    else:
        figure.add_trace(go.Scatter(x=indicators.index, y=indicators["Close"], name=price_label, line={"color": "#167b78", "width": 2.5}, hovertemplate="%{x|%d %b %Y}<br>Close: %{y:,.2f}<extra></extra>"), row=1, col=1)

    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["BB_lower"], name="Bollinger lower", line={"color": "rgba(113,85,168,.3)", "width": 1}), row=1, col=1)
    figure.add_trace(
        go.Scatter(x=indicators.index, y=indicators["BB_upper"], name="Bollinger band", line={"color": "rgba(113,85,168,.3)", "width": 1}, fill="tonexty", fillcolor="rgba(113,85,168,.08)"),
        row=1,
        col=1,
    )
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_20"], name="SMA 20", line={"color": "#7155a8", "width": 1.7}, hovertemplate="%{x|%d %b %Y}<br>SMA 20: %{y:,.2f}<extra></extra>"), row=1, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_50"], name="SMA 50", line={"color": "#b95413", "width": 1.7}, hovertemplate="%{x|%d %b %Y}<br>SMA 50: %{y:,.2f}<extra></extra>"), row=1, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["SMA_200"], name="SMA 200", line={"color": "#344255", "width": 2, "dash": "dash"}, hovertemplate="%{x|%d %b %Y}<br>SMA 200: %{y:,.2f}<extra></extra>"), row=1, col=1)

    hist_colors = ["#167b78" if value >= 0 else "#b53c4b" for value in indicators["MACD_histogram"].fillna(0)]
    figure.add_trace(go.Bar(x=indicators.index, y=indicators["MACD_histogram"], name="MACD histogram", marker_color=hist_colors), row=2, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["MACD"], name="MACD", line={"color": "#7155a8", "width": 1.3}), row=2, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["MACD_signal"], name="Signal", line={"color": "#b95413", "width": 1.2}), row=2, col=1)
    figure.add_trace(go.Scatter(x=indicators.index, y=indicators["RSI_14"], name="RSI 14", line={"color": "#8465b4", "width": 1.5}), row=3, col=1)
    for y_value in (30, 70):
        figure.add_hline(y=y_value, line_dash="dot", line_color="rgba(71,85,105,.34)", row=3, col=1)

    figure.update_layout(
        height=760,
        margin={"l": 68, "r": 20, "t": 92, "b": 42},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"color": "#182230", "family": "Inter, Segoe UI, Arial, sans-serif", "size": 13},
        xaxis_rangeslider_visible=False,
        legend={"orientation": "h", "y": 1.1, "x": 0, "font": {"size": 11, "color": "#344255"}},
        hovermode="x unified",
    )
    for annotation in figure.layout.annotations:
        annotation.font = {"size": 13, "color": "#182230", "family": "Inter, Segoe UI, Arial, sans-serif"}
    figure.update_xaxes(showgrid=False, zeroline=False)
    figure.update_yaxes(gridcolor="#e1e7ed", zeroline=False)
    figure.update_yaxes(title_text="Price", tickformat=",.2f", row=1, col=1, title_font={"size": 12, "color": "#344255"})
    figure.update_yaxes(title_text="MACD", tickformat=",.2f", row=2, col=1, title_font={"size": 12, "color": "#344255"})
    figure.update_yaxes(title_text="RSI", row=3, col=1, title_font={"size": 12, "color": "#344255"})
    figure.update_yaxes(range=[0, 100], row=3, col=1)
    return figure


def technical_buy_candidate(symbol: str, name: str, history: pd.DataFrame) -> dict | None:
    """Score five visible technical checks; this is a screen, not a buy recommendation."""
    if history is None or history.empty or "Close" not in history:
        return None
    indicators = calculate_technical_indicators(history)
    close = pd.to_numeric(indicators.get("Close"), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if len(close) < 201 or indicators.empty:
        return None
    latest = indicators.iloc[-1]
    close_value = finite_float(latest.get("Close"))
    sma50 = finite_float(latest.get("SMA_50"))
    sma200 = finite_float(latest.get("SMA_200"))
    macd = finite_float(latest.get("MACD"))
    macd_signal = finite_float(latest.get("MACD_signal"))
    rsi = finite_float(latest.get("RSI_14"))
    if any(value is None for value in (close_value, sma50, sma200, macd, macd_signal, rsi)):
        return None
    return_20 = (float(close.iloc[-1]) / float(close.iloc[-21]) - 1) * 100
    checks = [
        ("Price above SMA 50", close_value > sma50),
        ("SMA 50 above SMA 200", sma50 > sma200),
        ("Positive 20-session return", return_20 > 0),
        ("MACD above signal", macd > macd_signal),
        ("RSI in 40–70 range", 40 <= rsi <= 70),
    ]
    passed = [label for label, result in checks if result]
    return {
        "symbol": symbol,
        "name": name,
        "score": len(passed),
        "checks": passed,
        "check_count": len(checks),
        "return_20": return_20,
        "rsi": rsi,
        "as_of": latest_bar_date(history),
    }


def buy_candidate_figure(candidates: list[dict]) -> go.Figure | None:
    if not candidates:
        return None
    shown = sorted(candidates, key=lambda item: (item["score"], item["return_20"]), reverse=True)[:6]
    colors = ["#a94f17" if item["score"] >= 4 else "#d18a54" for item in shown]
    figure = go.Figure(
        go.Bar(
            x=[item["score"] for item in shown],
            y=[item["symbol"] for item in shown],
            orientation="h",
            marker={"color": colors, "line": {"color": "#ffffff", "width": 1}},
            text=[f"{item['score']}/{item['check_count']}" for item in shown],
            textposition="outside",
            textfont={"color": "#182230", "size": 13},
            cliponaxis=False,
            customdata=[[item["name"], item["return_20"], item["rsi"]] for item in shown],
            hovertemplate="%{customdata[0]}<br>Checks passed: %{x}/5<br>20-session return: %{customdata[1]:+.2f}%<br>RSI 14: %{customdata[2]:.1f}<extra></extra>",
        )
    )
    figure.update_layout(
        height=max(220, 54 * len(shown)),
        margin={"l": 36, "r": 60, "t": 62, "b": 36},
        title={"text": "Potential buy-watch setups · technical checks passed", "x": .02, "xanchor": "left", "font": {"size": 17, "color": "#182230"}},
        xaxis={"range": [0, 5.7], "tickmode": "array", "tickvals": [0, 1, 2, 3, 4, 5], "title": {"text": "Equal-weight checks (out of 5)"}, "gridcolor": "#e1e7ed"},
        yaxis={"autorange": "reversed", "showgrid": False},
        showlegend=False,
    )
    return figure


def render_buy_setup_screen(region_name: str, selected_ticker: str, selected_history: pd.DataFrame, access_token: str) -> None:
    region_code = MARKET_REGIONS[region_name]["code"]
    st.markdown("#### Potential buy-watch setups")
    st.caption("A small technical screen of your starred companies, the selected ticker and recent regional movers. It checks trend, momentum and RSI only; it does not assess valuation, company quality or your circumstances.")

    try:
        saved_tickers = load_watchlist(access_token)
    except ValueError:
        saved_tickers = []
    gainers = fetch_movers("gainers", count=5, region=region_code)
    losers = fetch_movers("losers", count=5, region=region_code)
    mover_tickers = lambda frame: frame.get("symbol", pd.Series(dtype=str)).dropna().astype(str).str.upper().tolist() if frame is not None and not frame.empty else []
    universe = list(dict.fromkeys([selected_ticker.upper(), *saved_tickers[:4], *mover_tickers(gainers)[:3], *mover_tickers(losers)[:3]]))
    universe = [symbol for symbol in universe if symbol][:11]
    signature = tuple(universe)
    state_key = f"buy_setup_scan_{region_code}"
    if st.button("Scan these tickers", key=f"run_buy_setup_scan_{region_code}", type="secondary"):
        records: list[dict] = []
        omitted = 0
        with st.spinner(f"Checking daily trend and momentum for {len(universe)} tickers…"):
            for symbol in universe:
                name = symbol
                if symbol == selected_ticker.upper() and selected_history is not None and not selected_history.empty:
                    history = selected_history
                else:
                    metadata = fetch_ticker_metadata(symbol)
                    name = str(metadata.get("name") or symbol)
                    history = fetch_history(symbol, period="2y", adjusted=True)
                candidate = technical_buy_candidate(symbol, name, history)
                if candidate is None:
                    omitted += 1
                elif candidate["score"] >= 3:
                    records.append(candidate)
        st.session_state[state_key] = {
            "signature": signature,
            "candidates": sorted(records, key=lambda item: (item["score"], item["return_20"]), reverse=True),
            "omitted": omitted,
            "checked": len(universe),
            "as_of": london_now(),
        }

    scan = st.session_state.get(state_key)
    if not scan or scan.get("signature") != signature:
        st.caption("Run the screen when you want a fresh set of candidates. It may take a few moments to load Yahoo daily bars.")
        return
    if scan["candidates"]:
        figure = buy_candidate_figure(scan["candidates"])
        if figure is not None:
            render_chart(figure)
        try:
            current_watchlist = set(load_watchlist(access_token))
        except ValueError:
            current_watchlist = set()
        for candidate in scan["candidates"][:6]:
            card_cols = st.columns([3.4, 1, 1])
            with card_cols[0]:
                st.markdown(f"**{escape(candidate['name'])} · {escape(candidate['symbol'])}**")
                passed = ", ".join(candidate["checks"])
                as_of = f" · bars through {candidate['as_of']:%d %b}" if candidate.get("as_of") else ""
                st.caption(f"{candidate['score']}/5 checks · 20-session return {candidate['return_20']:+.2f}% · RSI 14 {candidate['rsi']:.1f}{as_of}. Passed: {passed}.")
            with card_cols[1]:
                st.button("View analysis", key=f"buy_setup_open_{region_code}_{candidate['symbol']}", on_click=open_company_explorer, args=(candidate["symbol"],), use_container_width=True)
            with card_cols[2]:
                already_saved = candidate["symbol"] in current_watchlist
                st.button("★ Saved" if already_saved else "☆ Star", key=f"buy_setup_star_{region_code}_{candidate['symbol']}", on_click=toggle_company_watchlist, args=(candidate["symbol"], access_token), use_container_width=True)
    else:
        render_info("No tickers in this small screen passed at least three of the five technical checks today.")
    if scan.get("omitted"):
        st.caption(f"{scan['omitted']} of {scan['checked']} tickers were excluded because there was not enough complete daily history for the checks.")
    if scan.get("as_of"):
        st.caption(f"Screen refreshed {scan['as_of']:%d %b · %H:%M London}. Yahoo's latest daily bar dates are shown per candidate.")


def render_forecast_lab(region_name: str, access_token: str) -> None:
    st.markdown('<div class="eyebrow">Research tools</div>', unsafe_allow_html=True)
    st.markdown("## Forecast lab")
    st.caption("Indicators describe historical price behaviour. Simulated ranges are scenarios, not guarantees or recommendations.")

    ticker_query = st.text_input(
        "Search company or ticker",
        value=st.session_state.get("forecast_ticker", "AAPL"),
        key="forecast_ticker",
        on_change=clear_forecast_choice,
        help="Choose a search result below so the forecast uses an exact Yahoo Finance symbol.",
    ).strip()
    ticker_matches = search_tickers(ticker_query) if len(ticker_query) >= 2 else []
    if ticker_matches is None:
        render_info("Yahoo Finance ticker search did not respond. Refresh market data and try again.")
        return
    if not ticker_matches:
        if len(ticker_query) >= 2:
            render_info("No matching ticker was returned. Check the company name or exchange suffix.")
        return
    ticker_details = {match["symbol"]: match for match in ticker_matches}
    ticker_options = list(ticker_details)
    requested_symbol = str(ticker_query).upper()
    default_index = ticker_options.index(requested_symbol) if requested_symbol in ticker_options else 0
    ticker = st.selectbox(
        "Use this exact ticker",
        ticker_options,
        index=default_index,
        format_func=lambda symbol: ticker_option_label(symbol, ticker_details[symbol]),
        key="forecast_ticker_choice",
    )
    horizon_col, lookback_col, confidence_col, model_col = st.columns([.85, .9, .9, 1.35])
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
        render_info("There is not enough valid daily price history for these settings. Try a shorter lookback or a ticker with a longer price record.")
        render_buy_setup_screen(region_name, ticker, history, access_token)
        return

    metadata = fetch_ticker_metadata(ticker)
    quote_currency = str(metadata.get("currency") or "").strip()
    price_suffix = f" {quote_currency}" if quote_currency else ""
    metric_cols = st.columns(5)
    with metric_cols[0]:
        st.metric("Adjusted close", f"{format_number(forecast['spot'])}{price_suffix}")
    with metric_cols[1]:
        st.metric("Median scenario", f"{format_number(forecast['median'])}{price_suffix}", delta=format_percent(forecast["median_return"]))
    with metric_cols[2]:
        st.metric(f"{confidence}% lower range", f"{format_number(forecast['lower'])}{price_suffix}")
    with metric_cols[3]:
        st.metric(f"{confidence}% upper range", f"{format_number(forecast['upper'])}{price_suffix}")
    with metric_cols[4]:
        st.metric("Annualised volatility", f"{forecast['annualized_vol']:.1f}%")
    forecast_bar = latest_bar_date(history)
    if forecast_bar:
        st.caption(f"{ticker} · adjusted daily bars through {forecast_bar:%d %b %Y} · future dates are weekdays and do not account for exchange holidays.")

    st.markdown("#### Price structure and indicators")
    render_chart(forecast_figure(history, forecast, "Adjusted daily price"))
    indicators = calculate_technical_indicators(history)
    latest = indicators.iloc[-1]
    indicator_details = []
    for key, label, decimals in (("RSI_14", "RSI · 14", 1), ("MACD", "MACD", 3), ("ATR_14", "ATR · 14", 2)):
        value = latest.get(key)
        if value is not None and pd.notna(value):
            indicator_details.append(f"{label} {format_number(value, decimals)}")
    formula_note = "SMA is the mean of the latest 20/50/200 closes; Bollinger Bands are the 20-session mean ±2 standard deviations. RSI and ATR use Wilder smoothing; MACD uses EMA(12) − EMA(26) and a 9-session signal."
    if indicator_details:
        formula_note += " Latest: " + " · ".join(indicator_details) + "."
    formula_note += f" Maximum historical drawdown in this sample: {forecast['max_drawdown']:.1f}%."
    st.caption(formula_note)

    st.markdown("#### Monte Carlo price range")
    displayed_history = forecast["history"].tail(120)
    last_date = displayed_history.index[-1]
    forecast_dates = [last_date, *forecast["future_dates"]]
    low_path = [forecast["spot"], *forecast["lower_path"]]
    median_path = [forecast["spot"], *forecast["median_path"]]
    high_path = [forecast["spot"], *forecast["upper_path"]]
    figure = go.Figure()
    figure.add_trace(go.Scatter(x=displayed_history.index, y=displayed_history["Close"], mode="lines", name="Adjusted close", line={"color": "#7155a8", "width": 2.6}, hovertemplate="%{x|%d %b %Y}<br>Close: %{y:,.2f}<extra></extra>"))
    figure.add_trace(go.Scatter(x=forecast_dates, y=low_path, mode="lines", line={"width": 0}, name=f"{confidence}% lower scenario", hovertemplate="%{x|%d %b %Y}<br>Lower: %{y:,.2f}<extra></extra>"))
    figure.add_trace(go.Scatter(x=forecast_dates, y=high_path, mode="lines", line={"width": 0}, fill="tonexty", fillcolor="rgba(22,123,120,.14)", name=f"{confidence}% upper scenario", hovertemplate="%{x|%d %b %Y}<br>Upper: %{y:,.2f}<extra></extra>"))
    figure.add_trace(go.Scatter(x=forecast_dates, y=median_path, mode="lines+markers", name="Median path", line={"color": "#167b78", "width": 2.8, "dash": "dash"}, marker={"size": 7, "color": "#167b78"}, hovertemplate="%{x|%d %b %Y}<br>Median: %{y:,.2f}<extra></extra>"))
    figure.update_layout(height=450, margin={"l": 82, "r": 42, "t": 78, "b": 38}, paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font={"color": "#182230", "family": "Inter, Segoe UI, Arial, sans-serif", "size": 13}, title={"text": "Simulated price paths · historical close and range", "x": 0.02, "xanchor": "left", "font": {"size": 17, "color": "#182230"}}, xaxis={"showgrid": False}, yaxis={"gridcolor": "#e1e7ed", "zeroline": False, "tickformat": ",.2f", "title": {"text": f"Price{price_suffix}"}}, legend={"orientation": "h", "y": 1.04, "x": 0, "font": {"size": 11, "color": "#344255"}}, hovermode="x unified")
    render_chart(figure)
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
            st.metric("Historical drift MAPE", f"{score['model_mae_pct']:.2f}%")
        with score_cols[3]:
            st.metric("No-change baseline error", f"{score['baseline_mae_pct']:.2f}%", delta=f"{score['mae_improvement_pct']:+.1f}% vs baseline")
        st.caption("Rolling check of a mean-log-return point estimate against a no-change baseline. This score is separate from the selected simulation range and does not predict future accuracy.")

    st.markdown("#### Track this forecast")
    st.caption("Record the current scenario to your private account. When Yahoo later has a daily bar on or after its target date, the app adds the actual result to this scorecard.")
    if st.button("Save forecast for tracking", key=f"record_forecast_{ticker}_{horizon}_{lookback}_{confidence}_{method}"):
        _, was_added = record_forecast(ticker, forecast["history"].index[-1], horizon, forecast, access_token)
        if was_added:
            st.success("Forecast saved. Its outcome will be checked when the target date has a price bar.")
        else:
            render_info("This ticker, date, horizon, and model combination is already being tracked.")

    tracked = update_forecast_outcomes(ticker, history, access_token)
    resolved: list[tuple[dict, list[float]]] = []
    for item in tracked:
        values = [finite_float(item.get(key)) for key in ("actual", "median", "spot", "lower", "upper")]
        if all(value is not None for value in values):
            actual_value, median_value, spot_value, lower_value, upper_value = values
            if actual_value > 0 and median_value > 0 and spot_value > 0 and lower_value > 0 and lower_value <= upper_value:
                resolved.append((item, values))
    if resolved:
        median_errors: list[float] = []
        baseline_errors: list[float] = []
        range_hits: list[bool] = []
        for _, values in resolved:
            actual_value, median_value, spot_value, lower_value, upper_value = values
            median_errors.append(abs(actual_value / median_value - 1) * 100)
            baseline_errors.append(abs(actual_value / spot_value - 1) * 100)
            range_hits.append(lower_value <= actual_value <= upper_value)
        tracked_values: list[tuple[str, str]] = [("Resolved forecasts", f"{len(resolved):,}")]
        if median_errors:
            tracked_values.append(("Median absolute percentage error", f"{pd.Series(median_errors).median():.2f}%"))
        if baseline_errors:
            tracked_values.append(("No-change baseline error", f"{pd.Series(baseline_errors).median():.2f}%"))
        if range_hits:
            tracked_values.append(("Observed range coverage", f"{sum(range_hits) / len(range_hits) * 100:.1f}%"))
        tracked_cols = st.columns(min(4, len(tracked_values)))
        for column, (label, value) in zip(tracked_cols, tracked_values):
            with column:
                st.metric(label, value)
        tracked_table = pd.DataFrame(
            [
                {
                    "Forecast date": item["origin_date"],
                    "Target date": item["target_date"],
                    "Actual bar": item.get("actual_date"),
                    "Model": item["method"],
                    "Median": format_number(item["median"]),
                    "Actual": format_number(item["actual"]),
                    "Absolute % error": format_percent(abs(float(item["actual"]) / float(item["median"]) - 1) * 100),
                    "Within range": "Yes" if float(item["lower"]) <= float(item["actual"]) <= float(item["upper"]) else "No",
                }
                for item, _ in sorted(resolved, key=lambda entry: entry[0].get("created_at", ""), reverse=True)[:20]
            ]
        )
        st.dataframe(tracked_table, hide_index=True, use_container_width=True)
        st.caption("Percentage errors compare each actual close with the saved median. Observed range coverage is descriptive; small tracked samples cannot establish that future ranges are calibrated.")
    else:
        st.caption("No saved forecasts for this ticker have reached their target date yet.")

    render_buy_setup_screen(region_name, ticker, history, access_token)


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
    window = pd.to_numeric(series.tail(visible_sessions), errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    low, high = float(window.min()), float(window.max())
    padding = (high - low) * .08 if high > low else max(abs(high) * .02, 1.0)
    figure = go.Figure(
        go.Scatter(
            x=window.index,
            y=window.values,
            mode="lines",
            name="Open holdings",
            line={"color": "#167b78", "width": 3},
            hovertemplate=f"%{{x|%d %b %Y}}<br>{base_currency} %{{y:,.2f}}<extra></extra>",
        )
    )
    figure.update_layout(
        height=370,
        margin={"l": 12, "r": 14, "t": 66, "b": 24},
        paper_bgcolor="#ffffff",
        plot_bgcolor="#ffffff",
        font={"color": "#182230", "family": "Inter, Segoe UI, Arial, sans-serif", "size": 13},
        xaxis={"showgrid": False, "tickformat": "%d %b" if visible_sessions <= 63 else "%b %Y"},
        yaxis={"gridcolor": "#e1e7ed", "zeroline": False, "tickprefix": f"{base_currency} ", "tickformat": ",.2f", "range": [max(0, low - padding), high + padding], "title": {"text": f"Portfolio value · {base_currency}"}},
        title={"text": f"Historical holdings value · {base_currency}", "x": 0.02, "xanchor": "left", "font": {"size": 17, "color": "#182230"}},
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
        figure.add_trace(go.Scatter(x=indexed.index, y=indexed["Holding"], mode="lines", name="Holding", line={"color": "#167b78", "width": 2.4}))
        figure.add_trace(go.Scatter(x=indexed.index, y=indexed[benchmark_name], mode="lines", name=benchmark_name, line={"color": "#7155a8", "width": 1.8}))
    figure.add_hline(y=0, line_color="rgba(71,85,105,.34)", line_dash="dot")
    figure.update_layout(height=380, margin={"l": 12, "r": 12, "t": 76, "b": 24}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#526173", "family": "Manrope", "size": 11}, xaxis={"showgrid": False}, yaxis={"gridcolor": "rgba(71,85,105,.14)", "ticksuffix": "%"}, title={"text": f"Holding vs {benchmark_name} · rebased return", "x": 0.02, "xanchor": "left", "font": {"size": 14, "color": "#182230"}}, legend={"orientation": "h", "y": 1.04, "x": 0, "font": {"size": 9}}, hovermode="x unified")
    return figure


def build_portfolio_forecast_history(positions: list[dict], current_value: float) -> pd.DataFrame:
    """Create a current-share-weighted, adjusted-price series for the whole portfolio."""
    components: dict[str, pd.Series] = {}
    for position in positions:
        ticker = str(position.get("ticker") or "").strip().upper()
        shares = finite_float(position.get("shares"))
        price_scale = finite_float(position.get("price_scale"))
        fx_rate = finite_float(position.get("fx_rate"))
        if not ticker or shares is None or shares <= 0 or price_scale is None or fx_rate is None or fx_rate <= 0:
            return pd.DataFrame()

        history = fetch_history(ticker, period="2y", adjusted=True)
        close = _date_indexed_close(history)
        close = close.where(np.isfinite(close) & (close > 0)).dropna()
        if close.empty:
            return pd.DataFrame()
        components[ticker] = close * shares * price_scale * fx_rate

    if not components or not np.isfinite(current_value) or current_value <= 0:
        return pd.DataFrame()
    aligned_values = pd.concat(components, axis=1, join="inner").dropna()
    if len(aligned_values) < 21:
        return pd.DataFrame()
    total_value = aligned_values.sum(axis=1)
    if (total_value <= 0).any() or not np.isfinite(total_value.to_numpy(dtype=float)).all():
        return pd.DataFrame()
    scaled_value = total_value * (current_value / float(total_value.iloc[-1]))
    return pd.DataFrame({"Close": scaled_value}, index=aligned_values.index)


def portfolio_scenario_figure(
    history: pd.DataFrame,
    forecast: dict,
    confidence: int,
    currency: str = "",
    subject: str = "Holding",
) -> go.Figure:
    close = _date_indexed_close(history).tail(100)
    dates = [close.index[-1], *forecast["future_dates"]]
    low = [forecast["spot"], *forecast["lower_path"]]
    median = [forecast["spot"], *forecast["median_path"]]
    high = [forecast["spot"], *forecast["upper_path"]]
    figure = go.Figure()
    prefix = f"{currency} " if currency else ""
    figure.add_trace(go.Scatter(x=close.index, y=close.values, name=f"Recent {subject.lower()}", line={"color": "#7155a8", "width": 2.5}, hovertemplate=f"%{{x|%d %b %Y}}<br>{prefix}%{{y:,.2f}}<extra></extra>"))
    figure.add_trace(go.Scatter(x=dates, y=low, line={"width": 0}, name=f"{confidence}% lower", showlegend=False, hovertemplate=f"%{{x|%d %b %Y}}<br>Lower: {prefix}%{{y:,.2f}}<extra></extra>"))
    figure.add_trace(go.Scatter(x=dates, y=high, line={"width": 0}, fill="tonexty", fillcolor="rgba(22,123,120,.14)", name=f"{confidence}% upper", hovertemplate=f"%{{x|%d %b %Y}}<br>Upper: {prefix}%{{y:,.2f}}<extra></extra>"))
    figure.add_trace(go.Scatter(x=dates, y=median, mode="lines+markers", name="Median scenario", line={"color": "#167b78", "width": 2.5, "dash": "dash"}, marker={"size": 6}, hovertemplate=f"%{{x|%d %b %Y}}<br>Median: {prefix}%{{y:,.2f}}<extra></extra>"))
    figure.update_layout(height=430, margin={"l": 82, "r": 24, "t": 76, "b": 36}, paper_bgcolor="#ffffff", plot_bgcolor="#ffffff", font={"color": "#182230", "family": "Inter, Segoe UI, Arial, sans-serif", "size": 13}, xaxis={"showgrid": False}, yaxis={"gridcolor": "#e1e7ed", "zeroline": False, "tickformat": ",.2f", "tickprefix": prefix}, title={"text": f"{subject} estimate · central {confidence}% scenario range", "x": 0.02, "xanchor": "left", "font": {"size": 17, "color": "#182230"}}, legend={"orientation": "h", "y": 1.04, "x": 0, "font": {"size": 11, "color": "#344255"}}, hovermode="x unified")
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


def clear_powerbi_search_choice() -> None:
    st.session_state.pop("powerbi_search_choice", None)


def add_powerbi_export_ticker(symbol: str) -> None:
    symbol = str(symbol or "").strip().upper()
    if not symbol:
        return
    extras = list(st.session_state.get("powerbi_extra_tickers", []))
    if symbol not in extras:
        extras.append(symbol)
    st.session_state["powerbi_extra_tickers"] = extras
    selected = list(st.session_state.get("powerbi_export_tickers", []))
    if symbol not in selected:
        selected.append(symbol)
    st.session_state["powerbi_export_tickers"] = selected


def render_powerbi_export(
    transactions: pd.DataFrame,
    holdings: list[dict],
    access_token: str,
    region_name: str,
    base_currency: str,
) -> None:
    """Fetch requested Yahoo data on demand and offer a private local workbook download."""
    ledger_tickers = sorted(
        {
            str(value).strip().upper()
            for value in transactions.get("ticker", [])
            if pd.notna(value) and str(value).strip()
        }
    )
    holding_tickers = sorted({str(item.get("ticker") or "").strip().upper() for item in holdings if item.get("ticker")})
    period_labels = {"6 months": "6mo", "1 year": "1y", "2 years": "2y", "5 years": "5y"}

    with st.expander("Export a private workbook for Power BI", expanded=False):
        st.caption("Choose which Yahoo data to fetch now, then download an Excel snapshot for Power BI Desktop. The selected region’s benchmark is always included. Your browser controls where the file is saved; daily bar dates vary by market.")
        extra_tickers = list(st.session_state.get("powerbi_extra_tickers", []))
        search_query = st.text_input(
            "Add another Yahoo ticker to this export",
            placeholder="Search a company or ticker, e.g. Microsoft or MSFT",
            key="powerbi_search_query",
            on_change=clear_powerbi_search_choice,
        ).strip()
        search_matches = search_tickers(search_query) if len(search_query) >= 2 else []
        if search_matches is None:
            st.caption("Yahoo ticker search is temporarily unavailable. You can still export your portfolio tickers.")
        elif search_matches:
            search_details = {item["symbol"]: item for item in search_matches}
            search_cols = st.columns([3, 1])
            with search_cols[0]:
                selected_search_ticker = st.selectbox(
                    "Choose a Yahoo result",
                    options=list(search_details),
                    format_func=lambda symbol: ticker_option_label(symbol, search_details[symbol]),
                    key="powerbi_search_choice",
                )
            with search_cols[1]:
                st.button(
                    "Add ticker",
                    key="add_powerbi_export_ticker",
                    on_click=add_powerbi_export_ticker,
                    args=(selected_search_ticker,),
                    use_container_width=True,
                )
        elif len(search_query) >= 2:
            st.caption("No matching Yahoo Finance securities found.")

        with st.form("powerbi_export_options"):
            ticker_options = sorted(set([*ledger_tickers, *extra_tickers]))
            default_tickers = holding_tickers or ledger_tickers
            default_tickers = sorted(set([*default_tickers, *extra_tickers]))
            export_tickers = st.multiselect(
                "Tickers to fetch from Yahoo Finance",
                ticker_options,
                default=default_tickers,
                key="powerbi_export_tickers",
                help="The workbook always includes your full private transaction ledger. Yahoo price history and headlines are fetched only for the tickers selected here.",
            )
            export_cols = st.columns([1, 1, 1])
            with export_cols[0]:
                price_range = st.selectbox("Daily price history", list(period_labels), index=1, key="powerbi_export_period")
            with export_cols[1]:
                include_headlines = st.checkbox("Fetch ticker headlines", value=True, key="powerbi_export_include_news")
            with export_cols[2]:
                headline_count = st.selectbox("Headlines per ticker", [5, 10, 20], index=1, key="powerbi_export_headline_count", disabled=not include_headlines)
            prepare = st.form_submit_button("Fetch Yahoo data and prepare workbook", type="primary", use_container_width=True)

        transaction_signature = hashlib.sha256(
            transactions.to_json(orient="split", date_format="iso").encode("utf-8")
        ).hexdigest()
        settings_signature = hashlib.sha256(
            f"{transaction_signature}|{price_range}|{include_headlines}|{headline_count}|{','.join(export_tickers)}|{region_name}|{base_currency}".encode("utf-8")
        ).hexdigest()
        if st.session_state.get("powerbi_export_signature") not in (None, settings_signature):
            st.session_state.pop("powerbi_export_bytes", None)
            st.session_state.pop("powerbi_export_signature", None)
            st.session_state.pop("powerbi_exported_at", None)

        if prepare:
            try:
                with st.spinner("Fetching the selected Yahoo price history and headlines…"):
                    price_frames = [
                        history_table(symbol, "Equity", fetch_history(symbol, period=period_labels[price_range], adjusted=True))
                        for symbol in export_tickers
                    ]
                    benchmark_symbol = next(iter(MARKET_REGIONS[region_name]["benchmarks"]))
                    benchmark_history = fetch_history(benchmark_symbol, period=period_labels[price_range], adjusted=True)
                    price_frames.append(history_table(benchmark_symbol, "Market benchmark", benchmark_history))
                    price_history = pd.concat(price_frames, ignore_index=True) if price_frames else pd.DataFrame()

                    profile_symbols = list(dict.fromkeys([*export_tickers, benchmark_symbol]))
                    profile_frames = [profile_table(symbol, fetch_ticker_metadata(symbol)) for symbol in profile_symbols]
                    profiles = pd.concat(profile_frames, ignore_index=True) if profile_frames else pd.DataFrame()

                    headline_frames = []
                    if include_headlines:
                        for symbol in export_tickers:
                            headline_frames.append(headline_table(symbol, fetch_ticker_news(symbol, count=int(headline_count))))
                    headlines = pd.concat(headline_frames, ignore_index=True) if headline_frames else pd.DataFrame()
                    forecast_rows = load_forecasts(access_token)
                    generated_at = london_now()
                    workbook_bytes = build_powerbi_workbook(
                        transactions=transactions,
                        holdings=[{**item, "base_currency": base_currency} for item in holdings],
                        price_history=price_history,
                        headlines=headlines,
                        profiles=profiles,
                        forecasts=forecast_rows,
                        about={
                            "Exported at · London": generated_at.isoformat(timespec="seconds"),
                            "Market region": region_name,
                            "Portfolio base currency": base_currency,
                            "Yahoo price history": price_range,
                            "Yahoo tickers selected": ", ".join(export_tickers) or "None",
                            "Yahoo headlines included": "Yes" if include_headlines else "No",
                            "Snapshot note": "A point-in-time export. Yahoo price history uses auto-adjusted daily OHLC bars; refresh by preparing a new workbook.",
                        },
                    )
                st.session_state["powerbi_export_bytes"] = workbook_bytes
                st.session_state["powerbi_export_signature"] = settings_signature
                st.session_state["powerbi_exported_at"] = generated_at.strftime("%d %b %Y · %H:%M London")
                st.success("Workbook prepared. Download it below, then import it in Power BI using Get data → Excel workbook.")
            except ValueError as error:
                st.error(f"Could not prepare the private export: {error}")
                return

        if (
            st.session_state.get("powerbi_export_bytes")
            and st.session_state.get("powerbi_export_signature") == settings_signature
        ):
            st.download_button(
                "Download Power BI workbook (.xlsx)",
                data=st.session_state["powerbi_export_bytes"],
                file_name="market_brief_powerbi_export.xlsx",
                mime="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
                key="download_powerbi_workbook",
                use_container_width=True,
            )
            st.caption(f"Snapshot prepared {st.session_state.get('powerbi_exported_at', '')}. The workbook contains only this signed-in user’s transactions, holdings and saved forecasts.")


def render_portfolio(region_name: str, access_token: str) -> None:
    st.markdown('<div class="eyebrow">Your investments</div>', unsafe_allow_html=True)
    st.markdown("## Portfolio")
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
        ticker_query = st.text_input(
            "Search company or ticker",
            placeholder="Type a company name or symbol, e.g. Apple or AAPL",
            key="portfolio_ticker_search",
            help="Search text is only used to find matches. Choose a result below; trades can only use a selected ticker.",
        ).strip()
        ticker_matches = search_tickers(ticker_query) if len(ticker_query) >= 2 else []
        ticker = ""
        if len(ticker_query) < 2:
            st.caption("Type at least two characters to search, then select the matching security from the dropdown.")
        elif ticker_matches is None:
            st.warning("Yahoo Finance ticker search is temporarily unavailable. Try again later; your search text will not be recorded as a ticker.")
        elif not ticker_matches:
            render_info("No matching stocks or funds found. Try a company name or its Yahoo Finance symbol, such as LLOY.L.")
        else:
            ticker_details = {match["symbol"]: match for match in ticker_matches}
            ticker = st.selectbox(
                "Choose a matching ticker",
                options=list(ticker_details),
                format_func=lambda symbol: ticker_option_label(symbol, ticker_details[symbol]),
                key="portfolio_ticker_choice",
            )
        with st.form("portfolio_trade_form"):
            trade_cols = st.columns([.9, 1, 1, 1, 1.05, 1.4])
            with trade_cols[0]:
                action = st.selectbox("Action", ["Buy", "Sell"])
            with trade_cols[1]:
                trade_date = st.date_input("Trade date", value=london_now().date())
            with trade_cols[2]:
                shares = st.number_input("Shares", min_value=0.000001, value=1.0, step=1.0, format="%.6f")
            with trade_cols[3]:
                price = st.number_input("Price / share", min_value=0.000001, value=1.0, step=0.01, format="%.4f")
            with trade_cols[4]:
                fees = st.number_input("Fees", min_value=0.0, value=0.0, step=0.01, format="%.4f")
            with trade_cols[5]:
                note = st.text_input("Note", placeholder="Broker or reason (optional)")
            submitted = st.form_submit_button("Add transaction", type="primary", use_container_width=True, disabled=not ticker)
        if submitted:
            try:
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
        render_powerbi_export(transactions, [], access_token, region_name, base_currency)
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
                "sector": metadata.get("sector") or "",
                "industry": metadata.get("industry") or "",
                "currency": "GBp" if pence_quote else (raw_currency if raw_currency != "?" else ""),
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
                            "volatility_20": float(close.pct_change().dropna().tail(20).std(ddof=1) * (252 ** 0.5) * 100) if len(close) >= 21 else None,
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

    metric_values = [
        (f"Market value · {base_currency}", market_total, None),
        (f"Open cost basis · {base_currency}", basis_total, None),
        (f"Unrealised P&L · {base_currency}", unrealized_total, format_percent(unrealized_total / basis_total * 100) if unrealized_total is not None and basis_total else None),
        (f"Realised P&L · {base_currency}", realized_total, None),
        (f"Total P&L · {base_currency}", combined_gain, format_percent(combined_gain / basis_total * 100) if combined_gain is not None and basis_total else None),
    ]
    visible_metrics = [(label, value, delta) for label, value, delta in metric_values if value is not None]
    metric_columns = st.columns(min(5, len(visible_metrics))) if visible_metrics else []
    for column, (label, value, delta) in zip(metric_columns, visible_metrics):
        with column:
            st.metric(label, format_number(value), delta=delta)
    if day_total is not None:
        st.caption(f"Daily change across open positions: {format_number(day_total)} {base_currency} · based on the latest Yahoo Finance daily bar versus the previous bar.")
    if not all_market_values:
        render_info("Some open holdings have no current price or FX quote, so full portfolio totals are omitted until every position can be valued.")
    if not all_open_costs_known:
        st.caption("An opening balance has no recorded purchase cost. Add or edit its cost in the transaction ledger before relying on portfolio P&L.")
    if realized_total is None and realized_rows:
        st.caption("Realised P&L needs the original lot costs and a current FX quote for every affected sale.")

    render_powerbi_export(transactions, active_positions, access_token, region_name, base_currency)

    portfolio_history = portfolio_value_history(transactions, active_positions, historical_prices, base_currency)
    view_tabs = st.tabs(["Portfolio value", "Allocation", "Holdings table", "Portfolio forecast"])
    with view_tabs[0]:
        chart_controls = st.columns([1, 3])
        with chart_controls[0]:
            portfolio_range = st.radio("History", ["1M", "3M", "6M", "1Y"], horizontal=True, key="portfolio_range")
        visible = {"1M": 21, "3M": 63, "6M": 126, "1Y": 252}[portfolio_range]
        if len(portfolio_history) >= 2:
            render_chart(portfolio_value_figure(portfolio_history, base_currency, visible), use_container_width=True, config={"displayModeBar": False, "responsive": True})
            st.caption("Historical value marks the shares held on each date to daily closes and FX history where available. Legacy opening balances have no purchase date, so they are treated as held throughout the available chart history. Cash, dividends and sale proceeds are excluded; this is a holdings-value chart, not a cash-flow-adjusted return chart.")
        else:
            render_empty("Historical holdings value will appear when price history is available for every open position.")
    with view_tabs[1]:
        allocations = [position for position in active_positions if position.get("market_value_base") is not None and position["market_value_base"] > 0] if all_market_values else []
        allocation_col, sector_col = st.columns(2, gap="large")
        with allocation_col:
            if allocations:
                figure = go.Figure(go.Pie(labels=[f"{item['ticker']} · {item['name']}" for item in allocations], values=[item["market_value_base"] for item in allocations], hole=.66, marker={"colors": ["#167b78", "#7155a8", "#b95413", "#8465b4", "#b53c4b", "#2a898a", "#b53c4b", "#da853d"]}))
                figure.update_layout(
                    height=410,
                    margin={"l": 8, "r": 8, "t": 62, "b": 76},
                    paper_bgcolor="rgba(0,0,0,0)",
                    font={"color": "#526173", "family": "Manrope", "size": 10},
                    legend={"orientation": "h", "y": -0.14, "x": 0.5, "xanchor": "center", "font": {"size": 9}},
                    title={"text": f"Holdings mix · {base_currency}", "x": 0.02, "xanchor": "left", "font": {"size": 14, "color": "#182230"}},
                )
                render_chart(figure, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            else:
                render_info("Allocation appears when every open holding has a current price and FX rate; partial totals are not presented as the full portfolio.")
        with sector_col:
            sector_values: dict[str, float] = {}
            for position in allocations:
                sector = str(position.get("sector") or "Unclassified")
                sector_values[sector] = sector_values.get(sector, 0.0) + float(position["market_value_base"])
            if sector_values:
                sector_frame = pd.Series(sector_values).sort_values()
                figure = go.Figure(go.Bar(x=sector_frame.values, y=sector_frame.index, orientation="h", marker={"color": "#7155a8"}, text=[f"{value / market_total * 100:.1f}%" if market_total else "" for value in sector_frame.values], textposition="outside", hovertemplate="%{y}<br>Value: %{x:,.2f}<extra></extra>"))
                figure.update_layout(height=410, margin={"l": 8, "r": 38, "t": 62, "b": 20}, paper_bgcolor="rgba(0,0,0,0)", plot_bgcolor="rgba(0,0,0,0)", font={"color": "#526173", "family": "Manrope", "size": 10}, xaxis={"showgrid": False, "visible": False}, yaxis={"showgrid": False}, showlegend=False, title={"text": "Sector exposure · share of portfolio", "x": 0.02, "xanchor": "left", "font": {"size": 14, "color": "#182230"}})
                render_chart(figure, use_container_width=True, config={"displayModeBar": False, "responsive": True})
            else:
                render_info("Sector exposure appears when Yahoo Finance supplies company profiles and current holding prices.")
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
                    "Quote currency": position["currency"] or None,
                    f"Value · {base_currency}": position.get("market_value_base"),
                    "Weight %": weight,
                    "Day move %": position.get("day_move_pct"),
                    f"Open P&L · {base_currency}": position.get("unrealized_base"),
                    "RSI 14": position.get("rsi"),
                    "Price date": position.get("as_of"),
                }
            )
        st.dataframe(pd.DataFrame(table_rows), hide_index=True, use_container_width=True, column_config={"Shares": st.column_config.NumberColumn(format="%.4f"), "Average cost / share": st.column_config.NumberColumn(format="%.4f"), "Last close": st.column_config.NumberColumn(format="%.4f"), "Weight %": st.column_config.NumberColumn(format="%.1f%%"), "Day move %": st.column_config.NumberColumn(format="%.2f%%"), "RSI 14": st.column_config.NumberColumn(format="%.1f")})

    with view_tabs[3]:
        st.markdown("### Whole-portfolio estimate")
        st.caption("Simulate the combined holdings as one portfolio, preserving how the stocks moved together in the historical daily bars.")
        forecast_controls = st.columns([1, 1, 1, 1.35])
        with forecast_controls[0]:
            portfolio_horizon = st.selectbox("Trading days ahead", [5, 20, 60], index=1, key="portfolio_forecast_horizon")
        with forecast_controls[1]:
            portfolio_lookback = st.selectbox("Return history", [40, 60, 90, 120], index=1, key="portfolio_forecast_lookback")
        with forecast_controls[2]:
            portfolio_confidence = st.selectbox("Scenario range", [80, 90, 95], index=1, key="portfolio_forecast_confidence")
        with forecast_controls[3]:
            portfolio_method = st.selectbox("Simulation model", ["Historical bootstrap", "EWMA volatility"], key="portfolio_forecast_model")

        portfolio_signature = (
            tuple(
                (
                    item["ticker"],
                    round(float(item["shares"]), 8),
                    round(float(item.get("price") or 0.0), 6),
                    round(float(item.get("fx_rate") or 0.0), 8),
                    round(float(item.get("price_scale") or 0.0), 8),
                )
                for item in active_positions
            ),
            base_currency,
            round(float(market_total or 0.0), 6),
            portfolio_horizon,
            portfolio_lookback,
            portfolio_confidence,
            portfolio_method,
        )
        portfolio_forecast_message = None
        if st.button(
            "Calculate portfolio estimate",
            key="calculate_portfolio_forecast",
            type="primary",
            disabled=market_total is None,
        ):
            with st.spinner("Aligning daily history for all open holdings and simulating portfolio paths…"):
                portfolio_history = build_portfolio_forecast_history(active_positions, float(market_total or 0.0))
                portfolio_forecast = calculate_forecast(
                    portfolio_history,
                    portfolio_horizon,
                    portfolio_lookback,
                    portfolio_confidence / 100,
                    portfolio_method,
                    simulations=4000,
                ) if not portfolio_history.empty else None
            if portfolio_forecast is None:
                st.session_state.pop("portfolio_forecast_result", None)
                portfolio_forecast_message = "There is not enough overlapping daily price history for every holding at this lookback. Try a shorter history window or check the selected tickers."
            else:
                st.session_state["portfolio_forecast_result"] = {
                    "signature": portfolio_signature,
                    "history": portfolio_history,
                    "forecast": portfolio_forecast,
                }

        stored_portfolio_forecast = st.session_state.get("portfolio_forecast_result")
        if stored_portfolio_forecast and stored_portfolio_forecast.get("signature") == portfolio_signature:
            portfolio_forecast = stored_portfolio_forecast["forecast"]
            estimate_currency = base_currency
            estimate_metrics = st.columns(5)
            with estimate_metrics[0]:
                st.metric("Current portfolio value", f"{estimate_currency} {format_number(portfolio_forecast['spot'])}")
            with estimate_metrics[1]:
                st.metric("Median estimate", f"{estimate_currency} {format_number(portfolio_forecast['median'])}", delta=format_percent(portfolio_forecast["median_return"]))
            with estimate_metrics[2]:
                st.metric(f"{portfolio_confidence}% lower", f"{estimate_currency} {format_number(portfolio_forecast['lower'])}")
            with estimate_metrics[3]:
                st.metric(f"{portfolio_confidence}% upper", f"{estimate_currency} {format_number(portfolio_forecast['upper'])}")
            with estimate_metrics[4]:
                st.metric("Annualised volatility", f"{portfolio_forecast['annualized_vol']:.1f}%")
            future_day = portfolio_forecast["future_date"]
            st.caption(f"Estimated through {future_day:%d %b %Y} · weekday estimate, exchange holidays not included.")
            render_chart(
                portfolio_scenario_figure(
                    stored_portfolio_forecast["history"],
                    portfolio_forecast,
                    portfolio_confidence,
                    estimate_currency,
                    "Portfolio value",
                )
            )
            if portfolio_method == "Historical bootstrap":
                portfolio_formula = f"The app values the current share quantities across common adjusted daily bars, scales that series to today’s portfolio value, then resamples the latest {portfolio_lookback} daily log returns for {portfolio_forecast['simulations']:,} simulated paths."
            else:
                portfolio_formula = f"The app values the current share quantities across common adjusted daily bars, scales that series to today’s portfolio value, then simulates {portfolio_forecast['simulations']:,} paths using EWMA volatility (λ = 0.94) from the latest {portfolio_lookback} daily log returns."
            st.markdown(f'<div class="panel small-note">{escape(portfolio_formula)} Future share quantities and FX rates are held constant. Adjusted history includes past corporate-action effects; future dividends, fees, deposits and trades are not projected. This estimate remains in the current session. The range is a scenario, not a promise.</div>', unsafe_allow_html=True)
        elif market_total is None:
            render_info("A complete current price and currency conversion for every open holding is required before the portfolio estimate can be calculated.")
        elif portfolio_forecast_message:
            render_info(portfolio_forecast_message)
        else:
            st.caption("Choose the horizon, return history and model, then calculate to fetch the overlapping price history for your holdings.")

    st.markdown('<div class="section-label">Holding deep dive</div>', unsafe_allow_html=True)
    labels = {position["ticker"]: f"{position['ticker']} · {position['name']}" for position in active_positions}
    selected_ticker = st.selectbox("Choose a holding", list(labels), format_func=lambda symbol: labels[symbol], key="portfolio_selected_ticker")
    st.button("Open full company analysis ↗", key=f"company_explorer_portfolio_{selected_ticker}", on_click=open_company_explorer, args=(selected_ticker,))
    selected = next(position for position in active_positions if position["ticker"] == selected_ticker)
    detail_history = fetch_history(selected_ticker, period="2y", adjusted=True)
    detail_meta = metadata_by_ticker.get(selected_ticker, {})
    xirr = calculate_xirr(transactions, selected_ticker, float(selected.get("price") or 0.0), float(selected["shares"]), selected.get("as_of") or london_now().date()) if selected.get("price") is not None else None
    holding_metrics: list[tuple[str, str, str | None]] = [("Shares held", format_number(selected["shares"], 4), None)]
    if selected.get("price") is not None:
        selected_currency = str(selected.get("currency") or "").strip()
        holding_metrics.append(("Latest close", f"{format_number(selected['price'])} {selected_currency}".strip(), None))
    if selected.get("market_value_base") is not None:
        holding_metrics.append(("Position value", f"{format_number(selected['market_value_base'])} {base_currency}", None))
    if selected.get("unrealized_base") is not None:
        holding_metrics.append(("Open P&L", f"{format_number(selected['unrealized_base'])} {base_currency}", format_percent(selected.get("return_pct")) if selected.get("return_pct") is not None else None))
    if selected.get("realized_base") is not None:
        holding_metrics.append(("Realised P&L", f"{format_number(selected['realized_base'])} {base_currency}", None))
    if xirr is not None:
        holding_metrics.append(("Money-weighted XIRR", format_percent(xirr * 100), None))
    detail_columns = st.columns(min(6, len(holding_metrics)))
    for column, (label, value, delta) in zip(detail_columns, holding_metrics):
        with column:
            st.metric(label, value, delta=delta)
    if xirr is not None:
        st.caption("XIRR annualises dated buys and sells plus today’s open position value. It excludes dividends.")
    else:
        st.caption("XIRR appears when the recorded purchases have dates and known costs; dividends are not included.")

    detail_tabs = st.tabs(["Price & indicators", "Relative performance", "Scenario estimate", "Recent news"])
    with detail_tabs[0]:
        fundamental_metrics: list[tuple[str, str]] = []
        for key, label in (("sector", "Sector"), ("industry", "Industry")):
            if selected.get(key):
                fundamental_metrics.append((label, str(selected[key])))
        market_cap = detail_meta.get("market_cap")
        if market_cap is not None and pd.notna(market_cap):
            fundamental_metrics.append((f"Market cap · {detail_meta.get('currency') or selected['currency']}", f"{float(market_cap) / 1e9:,.2f}B"))
        for key, label, decimals in (("trailing_pe", "Trailing P/E", 2), ("beta", "Beta", 2)):
            value = detail_meta.get(key)
            if value is not None and pd.notna(value):
                fundamental_metrics.append((label, format_number(value, decimals)))
        if fundamental_metrics:
            fundamental_cols = st.columns(min(5, len(fundamental_metrics)))
            for column, (label, value) in zip(fundamental_cols, fundamental_metrics):
                with column:
                    render_metric_card(label, value)
        if not detail_history.empty:
            render_chart(forecast_figure(detail_history, {"history": detail_history}, "Adjusted daily price"), use_container_width=True, config={"displayModeBar": False, "responsive": True})
            technical_values = []
            for key, label, decimals, suffix in (("rsi", "RSI · 14", 1, ""), ("macd", "MACD", 3, ""), ("atr", "ATR · 14", 2, f" {selected['currency']}"), ("volatility_20", "20-session volatility", 1, "% annualised"), ("max_drawdown", "Maximum sample drawdown", 1, "%")):
                value = selected.get(key)
                if value is not None and pd.notna(value):
                    technical_values.append(f"{label}: {format_number(value, decimals)}{suffix}")
            if technical_values:
                st.caption(" · ".join(technical_values))
        else:
            render_info("Yahoo Finance returned no daily bars for this holding; its chart and indicators are omitted.")
    with detail_tabs[1]:
        benchmark_history = fetch_history(main_benchmark_symbol, period="2y", adjusted=True)
        if not detail_history.empty and not benchmark_history.empty:
            render_chart(portfolio_relative_figure(detail_history, benchmark_history, main_benchmark_name), use_container_width=True, config={"displayModeBar": False, "responsive": True})
            st.caption(f"Both series are rebased to 0% at the first shared daily bar. This compares price performance with {main_benchmark_name}; it does not include a cash-flow adjustment for your trades.")
        else:
            render_info("Yahoo Finance returned no shared daily bars for this comparison.")
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
                (f"Median · {horizon}d", forecast["median"] * price_scale, forecast["median_return"]),
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
            render_chart(portfolio_scenario_figure(detail_history, forecast, confidence), use_container_width=True, config={"displayModeBar": False, "responsive": True})
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
                    st.metric("Historical drift MAPE", f"{score['model_mae_pct']:.2f}%")
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
    _, status_detail = market_session_status(region_name, now)
    report = build_daily_brief(
        now,
        benchmarks,
        gainers,
        losers,
        market_news,
        headlines_by_ticker,
        market_name=region_name,
        market_status=status_detail,
    )
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    path = REPORT_DIR / f"market_brief_{region_code}_{now:%Y-%m-%d}.md"
    path.write_text(report, encoding="utf-8")
    return report, path


def render_daily_movers(region_name: str, gainers: pd.DataFrame, losers: pd.DataFrame) -> None:
    """Show the daily top movers here with links and on-demand supporting analytics."""
    region_code = MARKET_REGIONS[region_name]["code"]
    st.markdown('<div class="section-label">Top market movers</div>', unsafe_allow_html=True)
    st.caption("The screen ranks recent price moves. Headline matches are possible context to investigate, not proof of cause.")
    columns = st.columns(2, gap="large")
    for column, title, frame, direction in (
        (columns[0], "Leading gainers", gainers, "gainer"),
        (columns[1], "Leading decliners", losers, "decliner"),
    ):
        with column:
            st.markdown(f"### {title}")
            if frame is None or frame.empty:
                render_info(f"Yahoo Finance returned no {direction} rows for {region_name} right now. Refresh later to retry.")
                continue
            for _, mover in frame.head(5).iterrows():
                symbol = str(mover.get("symbol") or "").strip().upper()
                if not symbol:
                    continue
                name = str(mover.get("name") or symbol)
                move = finite_float(mover.get("change_pct"))
                if move is None:
                    continue
                label = f"{symbol} · {name} · {format_percent(move)}"
                with st.expander(label):
                    mover_metrics = [("Screen move", format_percent(move))]
                    price = mover.get("price")
                    if finite_float(price) is not None:
                        mover_metrics.insert(0, ("Yahoo screener price", format_number(price)))
                    detail_columns = st.columns(len(mover_metrics))
                    for detail_column, (metric_label, metric_value) in zip(detail_columns, mover_metrics):
                        with detail_column:
                            st.metric(metric_label, metric_value)
                    quote_time = pd.to_datetime(mover.get("quote_time"), utc=True, errors="coerce")
                    if pd.notna(quote_time):
                        st.caption(f"Yahoo screener quote: {quote_time.tz_convert(TIMEZONE):%d %b · %H:%M London}.")
                    st.button(
                        f"View {symbol} company analysis ↗",
                        key=f"daily_mover_open_{region_code}_{direction}_{symbol}",
                        use_container_width=True,
                        on_click=open_company_explorer,
                        args=(symbol,),
                    )
                    show_context = st.checkbox(
                        "Show price and headline context",
                        key=f"daily_mover_context_{region_code}_{direction}_{symbol}",
                    )
                    if not show_context:
                        continue
                    with st.spinner(f"Loading supporting data for {symbol}…"):
                        metadata = fetch_ticker_metadata(symbol)
                        history = fetch_history(symbol, period="6mo", adjusted=True)
                        articles = fetch_ticker_news(symbol, count=8)
                    if not history.empty and "Close" in history:
                        close = pd.to_numeric(history["Close"], errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
                        indicators = calculate_technical_indicators(history)
                        latest = indicators.iloc[-1] if not indicators.empty else pd.Series(dtype=float)
                        metrics: list[tuple[str, str]] = []
                        if len(close) >= 21:
                            metrics.append(("20-session return", format_percent((close.iloc[-1] / close.iloc[-21] - 1) * 100)))
                        rsi = latest.get("RSI_14")
                        if finite_float(rsi) is not None:
                            metrics.append(("RSI · 14", format_number(rsi, 1)))
                        if metadata.get("sector"):
                            metrics.append(("Sector", str(metadata["sector"])))
                        if metrics:
                            metric_columns = st.columns(min(3, len(metrics)))
                            for metric_column, (metric_label, metric_value) in zip(metric_columns, metrics):
                                with metric_column:
                                    render_metric_card(metric_label, metric_value)
                        render_chart(market_lens_figure(history, name, 126, []), use_container_width=True, config={"displayModeBar": False, "responsive": True})
                        bar_date = latest_bar_date(history)
                        bar_label = f"through {bar_date:%d %b %Y}" if bar_date else "from the returned daily bars"
                        st.caption(f"Technical values use daily bars {bar_label}. RSI is Wilder's 14-session calculation; it describes momentum, not a forecast.")
                    else:
                        render_info("Yahoo Finance returned no daily bars for this ticker. Headline context is shown when available.")
                    driver, evidence = classify_headlines(articles)
                    st.markdown(f"**Possible news context:** {escape(driver)}")
                    if evidence:
                        for article in evidence[:3]:
                            render_news_card(article)
                    else:
                        st.caption("No recent, timestamped related headline was found in the connected feeds.")


def render_daily_brief(region_name: str, now: datetime, benchmarks: list[dict], market_news: list[dict]) -> None:
    region_code = MARKET_REGIONS[region_name]["code"]
    report_date = f"{now:%Y-%m-%d}"
    session_state_date_key = f"daily_report_date_{region_code}"
    session_state_content_key = f"daily_report_content_{region_code}"
    report_path = REPORT_DIR / f"market_brief_{region_code}_{report_date}.md"

    st.markdown('<div class="eyebrow">Today</div>', unsafe_allow_html=True)
    st.markdown("## Daily brief")
    st.caption("A readable daily summary with direct company research links and the evidence behind major moves.")

    gainers, losers = fetch_movers("gainers", count=5, region=region_code), fetch_movers("losers", count=5, region=region_code)
    render_daily_movers(region_name, gainers, losers)
    st.markdown('<div class="section-label">Written market summary</div>', unsafe_allow_html=True)
    st.caption("A report is created the first time this region's Daily brief is opened each day. Cloud-hosted report files may not persist after a restart; download reports you want to keep.")
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
        st.markdown('<div class="side-brand"><span class="side-brand-mark">◈</span><span class="side-brand-name">MARKET BRIEF<span class="side-brand-sub">INTELLIGENCE DESK</span></span></div>', unsafe_allow_html=True)
        st.markdown(f'<div class="user-pill"><span class="user-dot"></span><span>{escape(str(user_session["email"]))}</span></div>', unsafe_allow_html=True)
        st.button("Sign out", key="logout_button", use_container_width=True, on_click=logout_user)
        region_name = st.selectbox("Market region", list(MARKET_REGIONS), key="market_region")
        st.caption("Sets the market indices, price charts and regional headlines.")
        if st.button("↻  Refresh market data", key="refresh_market_data", use_container_width=True):
            st.cache_data.clear()
            st.rerun()
        st.markdown("---")
        st.caption("Yahoo Finance prices · publisher RSS · official central-bank updates")

    region_config = MARKET_REGIONS[region_name]
    with st.spinner(f"Loading {region_name} benchmarks and headlines…"):
        benchmarks = load_benchmarks(region_name)
        news_bundle = fetch_market_news_bundle(tuple(region_config["news"]), region_name=region_name)
        market_news = news_bundle["articles"]
        news_sources = [news_bundle["status"], *fetch_rss_status(region_name)]
    render_header(region_name, now, benchmarks, market_news)

    sections = ["Markets", "Company explorer", "Portfolio", "Forecast lab", "Daily brief"]
    section_icons = {
        "Markets": "◉",
        "Company explorer": "⌕",
        "Portfolio": "▣",
        "Forecast lab": "∿",
        "Daily brief": "≡",
    }
    previous_page = st.session_state.get("dashboard_section")
    if previous_page in {"Market pulse", "News desk"}:
        st.session_state["dashboard_section"] = "Markets"
    elif previous_page == "Movers":
        st.session_state["dashboard_section"] = "Daily brief"
    elif previous_page == "Watchlist":
        st.session_state["dashboard_section"] = "Company explorer"
    elif previous_page not in sections:
        st.session_state["dashboard_section"] = "Markets"
    st.markdown('<div class="nav-overline">Your workspace</div>', unsafe_allow_html=True)
    page = st.radio(
        "Dashboard section",
        sections,
        horizontal=True,
        label_visibility="collapsed",
        key="dashboard_section",
        format_func=lambda section: f"{section_icons[section]}  {section}",
    )

    if page == "Markets":
        render_market_pulse(region_name, benchmarks, market_news, now, news_sources)
    elif page == "Company explorer":
        render_company_explorer(region_name, access_token)
    elif page == "Portfolio":
        render_portfolio(region_name, access_token)
    elif page == "Forecast lab":
        render_forecast_lab(region_name, access_token)
    elif page == "Daily brief":
        render_daily_brief(region_name, now, benchmarks, market_news)

    st.markdown(
        '<br><div class="small-note">Data sources and dates are shown beside figures. Headline links are context to verify; simulations are historical scenarios, not promises.</div>',
        unsafe_allow_html=True,
    )


if __name__ == "__main__":
    main()
