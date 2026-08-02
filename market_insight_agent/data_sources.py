"""
Data layer: pulls raw prices, macro series, and headlines.
Each function returns plain Python dict/DataFrame - no analysis here,
just retrieval. Keeping this separate makes it easy to swap data
vendors later (e.g. yfinance -> Polygon.io) without touching the
indicator/synthesis logic.
"""
from __future__ import annotations
import datetime as dt
import logging

import pandas as pd
import requests
import feedparser
import yfinance as yf
from pandas_datareader import data as pdr

import config

log = logging.getLogger(__name__)


def fetch_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    """Daily OHLCV history for a single ticker."""
    df = yf.Ticker(ticker).history(period=period, interval="1d")
    if df.empty:
        log.warning("No price data returned for %s", ticker)
    return df


def fetch_fundamentals(ticker: str) -> dict:
    """Trailing P/E, forward P/E, market cap, etc. (best-effort; not all
    fields exist for indices/futures)."""
    info = yf.Ticker(ticker).info
    return {
        "trailingPE": info.get("trailingPE"),
        "forwardPE": info.get("forwardPE"),
        "fiftyTwoWeekHigh": info.get("fiftyTwoWeekHigh"),
        "fiftyTwoWeekLow": info.get("fiftyTwoWeekLow"),
    }


def fetch_fred_series(series_id: str, years_back: int = 3) -> pd.Series:
    """Pull a macro time series from FRED (free, no key needed)."""
    start = dt.datetime.now() - dt.timedelta(days=365 * years_back)
    try:
        series = pdr.DataReader(series_id, "fred", start)[series_id]
        return series.dropna()
    except Exception as e:  # FRED endpoint hiccups are common; degrade gracefully
        log.error("FRED fetch failed for %s: %s", series_id, e)
        return pd.Series(dtype=float)


def fetch_all_macro() -> dict[str, pd.Series]:
    return {name: fetch_fred_series(sid) for name, sid in config.FRED_SERIES.items()}


def fetch_news_newsapi(query: str, page_size: int = 5) -> list[dict]:
    """Requires NEWS_API_KEY. Returns list of {title, source, url, publishedAt}."""
    if not config.NEWS_API_KEY:
        return []
    resp = requests.get(
        "https://newsapi.org/v2/everything",
        params={
            "q": query,
            "sortBy": "publishedAt",
            "language": "en",
            "pageSize": page_size,
            "apiKey": config.NEWS_API_KEY,
        },
        timeout=15,
    )
    resp.raise_for_status()
    articles = resp.json().get("articles", [])
    return [
        {
            "title": a["title"],
            "source": a["source"]["name"],
            "url": a["url"],
            "publishedAt": a["publishedAt"],
        }
        for a in articles
    ]


def fetch_news_rss(limit_per_feed: int = 5) -> list[dict]:
    """Fallback that needs no API key at all."""
    items = []
    for feed_url in config.FALLBACK_RSS_FEEDS:
        parsed = feedparser.parse(feed_url)
        for entry in parsed.entries[:limit_per_feed]:
            items.append(
                {
                    "title": entry.get("title", ""),
                    "source": parsed.feed.get("title", feed_url),
                    "url": entry.get("link", ""),
                    "publishedAt": entry.get("published", ""),
                }
            )
    return items


def fetch_headlines() -> list[dict]:
    """Try NewsAPI first (better relevance via query), fall back to RSS."""
    headlines = []
    for q in config.NEWS_QUERIES:
        headlines.extend(fetch_news_newsapi(q))
    if not headlines:
        headlines = fetch_news_rss()
    return headlines
