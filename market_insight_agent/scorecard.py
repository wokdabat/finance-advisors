"""
Assembles the full scorecard: fetches everything from data_sources and
runs it through indicators.py, producing one structured dict that gets
handed to the LLM synthesis step. This is the one function main.py calls.
"""
from __future__ import annotations
import logging

import config
import data_sources as ds
import indicators as ind

log = logging.getLogger(__name__)


def build_equity_scorecard() -> dict:
    out = {}
    for name, ticker in config.EQUITY_TICKERS.items():
        hist = ds.fetch_price_history(ticker)
        fundamentals = ds.fetch_fundamentals(ticker)
        out[name] = {
            **ind.trend_signal(hist),
            **ind.momentum_signal(hist),
            **ind.valuation_signal(fundamentals.get("trailingPE")),
        }

    proxy_histories = {
        name: ds.fetch_price_history(ticker)
        for name, ticker in config.BREADTH_PROXY_TICKERS.items()
    }
    out["_breadth_proxy"] = ind.breadth_signal(proxy_histories)
    return out


def build_gold_scorecard() -> dict:
    out = {}
    for name, ticker in config.COMMODITY_TICKERS.items():
        hist = ds.fetch_price_history(ticker)
        out[name] = {
            **ind.trend_signal(hist),
            **ind.momentum_signal(hist),
        }
    return out


def build_real_estate_scorecard() -> dict:
    out = {}
    for name, ticker in config.REAL_ESTATE_TICKERS.items():
        hist = ds.fetch_price_history(ticker)
        out[name] = {**ind.trend_signal(hist), **ind.momentum_signal(hist)}
    return out


def build_macro_scorecard() -> dict:
    macro_series = ds.fetch_all_macro()
    return ind.macro_regime(macro_series)


def build_full_scorecard() -> dict:
    log.info("Building equity scorecard...")
    equities = build_equity_scorecard()
    log.info("Building gold scorecard...")
    gold = build_gold_scorecard()
    log.info("Building real estate scorecard...")
    real_estate = build_real_estate_scorecard()
    log.info("Building macro scorecard...")
    macro = build_macro_scorecard()
    log.info("Fetching headlines...")
    headlines = ds.fetch_headlines()

    return {
        "equities": equities,
        "gold": gold,
        "real_estate": real_estate,
        "macro": macro,
        "headlines": headlines,
    }
