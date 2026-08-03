"""
Indicator layer: turns raw prices/macro series into a small set of
interpretable signals. This is deliberately simple/transparent (no
black-box ML) so you can see exactly why the agent says what it says.
"""
from __future__ import annotations
import pandas as pd


def trend_signal(price_history: pd.DataFrame) -> dict:
    """Classic moving-average trend read."""
    if price_history.empty or len(price_history) < 200:
        return {"trend": "insufficient_data"}

    close = price_history["Close"]
    last_price = close.iloc[-1]
    ma50 = close.rolling(50).mean().iloc[-1]
    ma200 = close.rolling(200).mean().iloc[-1]

    if last_price > ma50 > ma200:
        trend = "uptrend"
    elif last_price < ma50 < ma200:
        trend = "downtrend"
    else:
        trend = "mixed"

    return {
        "trend": trend,
        "last_price": round(float(last_price), 2),
        "ma50": round(float(ma50), 2),
        "ma200": round(float(ma200), 2),
        "pct_off_52w_high": round(
            float((last_price / close.tail(252).max() - 1) * 100), 2
        ),
    }


def momentum_signal(price_history: pd.DataFrame, window_days: int = 21) -> dict:
    """Short-term momentum: % change over the last N trading days."""
    if price_history.empty or len(price_history) <= window_days:
        return {"momentum_pct": None}
    close = price_history["Close"]
    change = (close.iloc[-1] / close.iloc[-window_days] - 1) * 100
    return {"momentum_pct": round(float(change), 2)}


def valuation_signal(trailing_pe: float | None, historical_avg_pe: float = 18.0) -> dict:
    """Very rough valuation heuristic vs. long-run historical average P/E.
    Treat this as a talking point, not gospel -- fair-value P/E shifts
    with rates/growth expectations."""
    if trailing_pe is None:
        return {"valuation": "unknown"}
    premium_pct = (trailing_pe / historical_avg_pe - 1) * 100
    if premium_pct > 25:
        label = "rich"
    elif premium_pct < -10:
        label = "cheap"
    else:
        label = "fair"
    return {
        "valuation": label,
        "trailing_pe": trailing_pe,
        "premium_vs_historical_avg_pct": round(premium_pct, 1),
    }


def macro_regime(macro: dict[str, pd.Series]) -> dict:
    """Summarize macro backdrop: rate direction, inflation trend, yield level."""
    out = {}
    for name, series in macro.items():
        if series.empty:
            out[name] = {"latest": None, "trend_3m": None}
            continue
        latest = series.iloc[-1]
        three_months_ago = series.iloc[max(0, len(series) - 63)]  # ~63 trading/calendar rows
        direction = "rising" if latest > three_months_ago else (
            "falling" if latest < three_months_ago else "flat"
        )
        out[name] = {
            "latest": round(float(latest), 2),
            "trend_3m": direction,
        }
    return out


def breadth_signal(proxy_price_histories: dict[str, pd.DataFrame]) -> dict:
    """Rough breadth proxy: how many of our sector/factor ETFs are in an
    uptrend (price > 200dma). Not a substitute for true market-internals
    data (e.g. % of S&P 500 members above 200dma), but a usable stand-in
    if you don't have a paid data feed."""
    above, total = 0, 0
    detail = {}
    for name, hist in proxy_price_histories.items():
        if hist.empty or len(hist) < 200:
            continue
        total += 1
        close = hist["Close"]
        is_above = close.iloc[-1] > close.rolling(200).mean().iloc[-1]
        above += int(is_above)
        detail[name] = "above_200dma" if is_above else "below_200dma"
    pct = round(above / total * 100, 1) if total else None
    return {"pct_proxies_above_200dma": pct, "detail": detail}
