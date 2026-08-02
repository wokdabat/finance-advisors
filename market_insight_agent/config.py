"""
Central configuration for the market insight agent.
Put secrets in a `.env` file (never commit it) and load via python-dotenv.
"""
import os
from dotenv import load_dotenv

load_dotenv()

# --- Tickers we track (Yahoo Finance symbols) ---
EQUITY_TICKERS = {
    "S&P 500": "^GSPC",
    "Nasdaq 100": "^NDX",
    "Russell 2000": "^RUT",
}

# Sector/momentum proxies used as rough "breadth" indicators
BREADTH_PROXY_TICKERS = {
    "Semiconductors (SOXX)": "SOXX",
    "Momentum factor (MTUM)": "MTUM",
    "Equal-weight S&P (RSP)": "RSP",
}

COMMODITY_TICKERS = {
    "Gold": "GC=F",       # Gold futures
    "Gold ETF": "GLD",    # more reliable history/volume than futures continuation
}

REAL_ESTATE_TICKERS = {
    "Homebuilders ETF (XHB)": "XHB",
    "REIT ETF (VNQ)": "VNQ",
}

# --- FRED (Federal Reserve Economic Data) series ---
# These are free, no API key required via pandas_datareader.
FRED_SERIES = {
    "30yr Mortgage Rate": "MORTGAGE30US",
    "Fed Funds Rate": "FEDFUNDS",
    "CPI (YoY inflation proxy)": "CPIAUCSL",
    "10-Year Treasury Yield": "DGS10",
    "Unemployment Rate": "UNRATE",
    "Case-Shiller Home Price Index": "CSUSHPISA",
}

# --- News ---
NEWS_API_KEY = os.getenv("NEWS_API_KEY", "")  # https://newsapi.org
NEWS_QUERIES = ["S&P 500 outlook", "gold price forecast", "housing market forecast"]
FALLBACK_RSS_FEEDS = [
    "https://www.cnbc.com/id/20910258/device/rss/rss.html",   # CNBC markets
    "https://www.investing.com/rss/news_25.rss",              # Commodities
]

# --- LLM synthesis provider ---
LLM_PROVIDER = os.getenv("LLM_PROVIDER", "anthropic")  # "anthropic" or "openai"
LLM_API_KEY = os.getenv("LLM_API_KEY", "")
LLM_MODEL = os.getenv("LLM_MODEL", "claude-sonnet-4-5")

# --- Delivery ---
SLACK_WEBHOOK_URL = os.getenv("SLACK_WEBHOOK_URL", "")
OUTPUT_DIR = os.getenv("OUTPUT_DIR", "./reports")
