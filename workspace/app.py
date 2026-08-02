"""
Market Insight Agent
=====================
A Streamlit app that gives you a technical + fundamental + sentiment based
read on whether it looks like a good time to buy, hold, or sell an asset -
stocks, gold/commodities, real estate (via REIT proxies), or crypto.

Run with:
    pip install -r requirements.txt
    streamlit run app.py

This tool is for educational purposes only and is NOT financial advice.
"""

import numpy as np
import pandas as pd
import streamlit as st
import yfinance as yf
import plotly.graph_objects as go
from plotly.subplots import make_subplots

# ----------------------------------------------------------------------------
# Page config
# ----------------------------------------------------------------------------
st.set_page_config(
    page_title="Market Insight Agent",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ----------------------------------------------------------------------------
# Asset catalog
# ----------------------------------------------------------------------------
ASSET_CATALOG = {
    "Stocks & Indices": {
        "Apple (AAPL)": "AAPL",
        "Microsoft (MSFT)": "MSFT",
        "Amazon (AMZN)": "AMZN",
        "Alphabet / Google (GOOGL)": "GOOGL",
        "NVIDIA (NVDA)": "NVDA",
        "Tesla (TSLA)": "TSLA",
        "S&P 500 Index (^GSPC)": "^GSPC",
        "Nasdaq 100 (^NDX)": "^NDX",
        "Dow Jones (^DJI)": "^DJI",
    },
    "Gold & Commodities": {
        "Gold Futures (GC=F)": "GC=F",
        "Gold ETF (GLD)": "GLD",
        "Silver Futures (SI=F)": "SI=F",
        "Crude Oil WTI (CL=F)": "CL=F",
        "Copper Futures (HG=F)": "HG=F",
    },
    "Real Estate (REIT proxies)": {
        "Vanguard Real Estate ETF (VNQ)": "VNQ",
        "iShares US Real Estate (IYR)": "IYR",
        "Schwab US REIT ETF (SCHH)": "SCHH",
        "Prologis (PLD)": "PLD",
        "American Tower (AMT)": "AMT",
        "Realty Income (O)": "O",
    },
    "Crypto": {
        "Bitcoin (BTC-USD)": "BTC-USD",
        "Ethereum (ETH-USD)": "ETH-USD",
        "Solana (SOL-USD)": "SOL-USD",
    },
}

POSITIVE_WORDS = [
    "surge", "rally", "beat", "growth", "upgrade", "bullish", "gain",
    "record high", "strong", "outperform", "soar", "jump", "boom",
    "recovery", "optimis",
]
NEGATIVE_WORDS = [
    "plunge", "crash", "miss", "downgrade", "bearish", "loss", "recall",
    "lawsuit", "weak", "underperform", "slump", "tumble", "selloff",
    "sell-off", "recession", "default", "fraud", "layoff",
]

# ----------------------------------------------------------------------------
# Data loading (cached)
# ----------------------------------------------------------------------------
@st.cache_data(ttl=900, show_spinner=False)
def load_price_data(ticker: str, period: str = "2y", interval: str = "1d") -> pd.DataFrame:
    tk = yf.Ticker(ticker)
    df = tk.history(period=period, interval=interval)
    return df


@st.cache_data(ttl=1800, show_spinner=False)
def load_info(ticker: str) -> dict:
    tk = yf.Ticker(ticker)
    try:
        info = tk.info
        return info if isinstance(info, dict) else {}
    except Exception:
        return {}


@st.cache_data(ttl=1800, show_spinner=False)
def load_news(ticker: str) -> list:
    tk = yf.Ticker(ticker)
    try:
        items = tk.news or []
    except Exception:
        items = []

    headlines = []
    for item in items[:8]:
        title, link, publisher = None, None, None
        if isinstance(item, dict):
            if "title" in item:
                title = item.get("title")
                link = item.get("link")
                publisher = item.get("publisher")
            elif "content" in item and isinstance(item["content"], dict):
                c = item["content"]
                title = c.get("title")
                publisher = (c.get("provider") or {}).get("displayName")
                url_obj = c.get("clickThroughUrl") or c.get("canonicalUrl") or {}
                link = url_obj.get("url") if isinstance(url_obj, dict) else None
        if title:
            headlines.append({"title": title, "link": link, "publisher": publisher})
    return headlines


# ----------------------------------------------------------------------------
# Indicator computation
# ----------------------------------------------------------------------------
def compute_indicators(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()
    close = out["Close"]

    out["SMA20"] = close.rolling(20).mean()
    out["SMA50"] = close.rolling(50).mean()
    out["SMA200"] = close.rolling(200).mean()

    delta = close.diff()
    gain = delta.clip(lower=0)
    loss = -delta.clip(upper=0)
    avg_gain = gain.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    avg_loss = loss.ewm(alpha=1 / 14, min_periods=14, adjust=False).mean()
    rs = avg_gain / avg_loss.replace(0, np.nan)
    out["RSI14"] = 100 - (100 / (1 + rs))

    ema12 = close.ewm(span=12, adjust=False).mean()
    ema26 = close.ewm(span=26, adjust=False).mean()
    out["MACD"] = ema12 - ema26
    out["MACD_signal"] = out["MACD"].ewm(span=9, adjust=False).mean()
    out["MACD_hist"] = out["MACD"] - out["MACD_signal"]

    std20 = close.rolling(20).std()
    out["BB_mid"] = out["SMA20"]
    out["BB_upper"] = out["BB_mid"] + 2 * std20
    out["BB_lower"] = out["BB_mid"] - 2 * std20

    return out


def compute_metrics(df: pd.DataFrame) -> dict:
    close = df["Close"]
    last_price = float(close.iloc[-1])
    prev_close = float(close.iloc[-2]) if len(close) > 1 else last_price
    day_change_pct = (last_price / prev_close - 1) * 100 if prev_close else 0.0

    window = close.tail(252)
    high_52w = float(window.max())
    low_52w = float(window.min())
    pct_from_high = (last_price / high_52w - 1) * 100 if high_52w else 0.0

    def period_return(days):
        if len(close) > days:
            past = float(close.iloc[-days - 1])
            if past:
                return (last_price / past - 1) * 100
        return None

    ret_1m = period_return(21)
    ret_3m = period_return(63)
    ret_6m = period_return(126)
    ret_1y = period_return(252)

    this_year = close[close.index.year == close.index[-1].year]
    ytd = (last_price / float(this_year.iloc[0]) - 1) * 100 if len(this_year) > 0 and this_year.iloc[0] else None

    daily_returns = close.pct_change().dropna()
    volatility = float(daily_returns.std() * np.sqrt(252) * 100) if len(daily_returns) > 5 else None

    return dict(
        price=last_price,
        day_change_pct=day_change_pct,
        high_52w=high_52w,
        low_52w=low_52w,
        pct_from_high=pct_from_high,
        ret_1m=ret_1m,
        ret_3m=ret_3m,
        ret_6m=ret_6m,
        ret_1y=ret_1y,
        ytd=ytd,
        volatility=volatility,
    )


def news_sentiment_adjustment(headlines: list):
    raw_score = 0
    for h in headlines:
        title = (h.get("title") or "").lower()
        pos = sum(w in title for w in POSITIVE_WORDS)
        neg = sum(w in title for w in NEGATIVE_WORDS)
        raw_score += pos - neg
    adj = int(np.clip(raw_score * 3, -10, 10))
    return adj


def build_score(df_ind: pd.DataFrame, metrics: dict, info: dict, headlines: list):
    reasons = []  # list of (text, weight)
    score = 0
    last = df_ind.iloc[-1]
    price = metrics["price"]

    if not pd.isna(last.get("SMA200")):
        if price > last["SMA200"]:
            score += 15
            reasons.append(("Price is above its 200-day moving average, indicating a long-term uptrend.", 15))
        else:
            score -= 15
            reasons.append(("Price is below its 200-day moving average, indicating a long-term downtrend.", -15))

    if not pd.isna(last.get("SMA50")) and not pd.isna(last.get("SMA200")):
        if last["SMA50"] > last["SMA200"]:
            score += 10
            reasons.append(("The 50-day average is above the 200-day average (a bullish 'golden cross' regime).", 10))
        else:
            score -= 10
            reasons.append(("The 50-day average is below the 200-day average (a bearish 'death cross' regime).", -10))

    rsi = last.get("RSI14")
    if not pd.isna(rsi):
        if rsi < 30:
            score += 10
            reasons.append((f"RSI is at {rsi:.0f}, suggesting the asset is oversold (potential buying opportunity).", 10))
        elif rsi > 70:
            score -= 10
            reasons.append((f"RSI is at {rsi:.0f}, suggesting the asset is overbought (elevated pull-back risk).", -10))
        else:
            reasons.append((f"RSI is at {rsi:.0f}, a neutral reading.", 0))

    if not pd.isna(last.get("MACD")) and not pd.isna(last.get("MACD_signal")):
        if last["MACD"] > last["MACD_signal"]:
            score += 10
            reasons.append(("MACD is above its signal line, a bullish momentum signal.", 10))
        else:
            score -= 10
            reasons.append(("MACD is below its signal line, a bearish momentum signal.", -10))

    if metrics.get("ret_3m") is not None:
        if metrics["ret_3m"] > 5:
            score += 5
            reasons.append((f"Strong 3-month momentum ({metrics['ret_3m']:.1f}%).", 5))
        elif metrics["ret_3m"] < -5:
            score -= 5
            reasons.append((f"Weak 3-month momentum ({metrics['ret_3m']:.1f}%).", -5))

    pct_from_high = metrics.get("pct_from_high")
    if pct_from_high is not None:
        if pct_from_high > -5:
            score += 5
            reasons.append(("Trading within 5% of its 52-week high, showing relative strength.", 5))
        elif pct_from_high < -20:
            score -= 5
            reasons.append((f"Down {abs(pct_from_high):.0f}% from its 52-week high, in a corrective phase.", -5))

    pe = info.get("trailingPE") if info else None
    if pe and pe > 0:
        if pe < 15:
            score += 10
            reasons.append((f"Trailing P/E of {pe:.1f} looks relatively cheap versus historical norms.", 10))
        elif pe > 35:
            score -= 10
            reasons.append((f"Trailing P/E of {pe:.1f} looks expensive versus historical norms.", -10))
        else:
            reasons.append((f"Trailing P/E of {pe:.1f} is in a fairly reasonable range.", 0))

    news_adj = news_sentiment_adjustment(headlines)
    if news_adj != 0:
        score += news_adj
        tone = "positive" if news_adj > 0 else "negative"
        reasons.append((f"Recent news headlines skew {tone} in tone.", news_adj))

    score = int(np.clip(score, -100, 100))
    return score, reasons


def recommendation_label(score: int):
    if score >= 50:
        return "Strong Buy", "success"
    elif score >= 20:
        return "Buy", "success"
    elif score > -20:
        return "Hold / Neutral", "warning"
    elif score > -50:
        return "Sell", "error"
    else:
        return "Strong Sell", "error"


def rule_based_narrative(name: str, recommendation: str, score: int, reasons: list) -> str:
    bullish = [r[0] for r in reasons if r[1] and r[1] > 0]
    bearish = [r[0] for r in reasons if r[1] and r[1] < 0]
    lines = [
        f"**{name}** currently scores **{score}/100** on our composite signal, "
        f"pointing to a **{recommendation}** stance."
    ]
    if bullish:
        lines.append("**Supporting factors:** " + " ".join(bullish))
    if bearish:
        lines.append("**Risks / headwinds:** " + " ".join(bearish))
    lines.append(
        "_This is an automated, rule-based read of technical and basic fundamental data - "
        "it is not financial advice. Always do your own research or consult a licensed advisor._"
    )
    return "\n\n".join(lines)


def ai_narrative(name: str, score: int, recommendation: str, reasons: list, metrics: dict, api_key: str):
    try:
        from openai import OpenAI
        client = OpenAI(api_key=api_key)
        bullet_points = "\n".join(f"- {r[0]}" for r in reasons)
        prompt = (
            f"You are a market analysis assistant. Based on the computed signals below for {name}, "
            f"write a concise, plain-English 4-6 sentence market insight. Be balanced, mention both "
            f"strengths and risks, and explicitly note this is informational, not financial advice.\n\n"
            f"Composite score: {score}/100 -> Suggested stance: {recommendation}\n"
            f"Signals:\n{bullet_points}\n\n"
            f"Key metrics: price=${metrics['price']:.2f}, YTD={metrics.get('ytd')}, "
            f"3M return={metrics.get('ret_3m')}, annualized volatility={metrics.get('volatility')}\n"
        )
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            temperature=0.4,
            max_tokens=350,
        )
        return resp.choices[0].message.content
    except Exception:
        return None


# ----------------------------------------------------------------------------
# Charting
# ----------------------------------------------------------------------------
def make_chart(df_ind: pd.DataFrame, name: str):
    fig = make_subplots(
        rows=3, cols=1, shared_xaxes=True,
        row_heights=[0.6, 0.2, 0.2], vertical_spacing=0.04,
        subplot_titles=("Price & Moving Averages", "RSI (14)", "MACD"),
    )

    fig.add_trace(
        go.Candlestick(
            x=df_ind.index, open=df_ind["Open"], high=df_ind["High"],
            low=df_ind["Low"], close=df_ind["Close"], name="Price",
        ),
        row=1, col=1,
    )
    for col, label in [("SMA20", "SMA 20"), ("SMA50", "SMA 50"), ("SMA200", "SMA 200")]:
        if col in df_ind:
            fig.add_trace(
                go.Scatter(x=df_ind.index, y=df_ind[col], name=label, line=dict(width=1)),
                row=1, col=1,
            )

    fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["RSI14"], name="RSI", line=dict(width=1)), row=2, col=1)
    fig.add_hline(y=70, line_dash="dot", line_color="red", row=2, col=1)
    fig.add_hline(y=30, line_dash="dot", line_color="green", row=2, col=1)

    fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["MACD"], name="MACD", line=dict(width=1)), row=3, col=1)
    fig.add_trace(go.Scatter(x=df_ind.index, y=df_ind["MACD_signal"], name="Signal", line=dict(width=1)), row=3, col=1)
    fig.add_trace(go.Bar(x=df_ind.index, y=df_ind["MACD_hist"], name="Histogram"), row=3, col=1)

    fig.update_layout(
        height=750, title=f"{name} - Price & Technical Indicators",
        xaxis_rangeslider_visible=False, showlegend=True,
        legend=dict(orientation="h", yanchor="bottom", y=1.02, xanchor="right", x=1),
    )
    return fig


# ----------------------------------------------------------------------------
# Core pipeline for a single ticker
# ----------------------------------------------------------------------------
def analyze_ticker(ticker: str):
    df = load_price_data(ticker, period="2y", interval="1d")
    if df is None or df.empty:
        return None
    df_ind = compute_indicators(df)
    metrics = compute_metrics(df_ind)
    info = load_info(ticker)
    headlines = load_news(ticker)
    score, reasons = build_score(df_ind, metrics, info, headlines)
    recommendation, tone = recommendation_label(score)
    return dict(
        ticker=ticker, df_ind=df_ind, metrics=metrics, info=info,
        headlines=headlines, score=score, reasons=reasons,
        recommendation=recommendation, tone=tone,
    )


# ----------------------------------------------------------------------------
# Sidebar
# ----------------------------------------------------------------------------
st.sidebar.title("Market Insight Agent")
st.sidebar.caption("Educational tool - not financial advice.")

category = st.sidebar.selectbox("Asset class", list(ASSET_CATALOG.keys()))
preset_options = list(ASSET_CATALOG[category].keys())
preset_choice = st.sidebar.selectbox("Preset asset", preset_options)
custom_ticker = st.sidebar.text_input(
    "Or enter a custom ticker (overrides preset)",
    value="",
    placeholder="e.g. NVDA, BTC-USD, VNQ",
)
ticker = custom_ticker.strip().upper() if custom_ticker.strip() else ASSET_CATALOG[category][preset_choice]
display_name = custom_ticker.strip().upper() if custom_ticker.strip() else f"{preset_choice}"

display_period = st.sidebar.select_slider(
    "Chart lookback window", options=["6mo", "1y", "2y"], value="1y"
)

st.sidebar.markdown("---")
use_ai = st.sidebar.checkbox("Use AI-generated narrative (optional)")
openai_key = None
if use_ai:
    openai_key = st.sidebar.text_input("OpenAI API key", type="password")
    st.sidebar.caption("If left blank or invalid, a rule-based narrative is used instead.")

st.sidebar.markdown("---")
watchlist_input = st.sidebar.text_area(
    "Watchlist tickers (comma-separated)",
    value="AAPL, GLD, VNQ, BTC-USD",
)

# ----------------------------------------------------------------------------
# Main layout
# ----------------------------------------------------------------------------
st.title("Market Insight Agent")
st.caption(
    "Technical + fundamental + news-sentiment read on stocks, gold/commodities, "
    "real estate (REIT proxies), and crypto. Educational use only, not financial advice."
)

tab_analysis, tab_watchlist = st.tabs(["Analysis", "Watchlist"])

with tab_analysis:
    with st.spinner(f"Fetching data for {ticker}..."):
        result = analyze_ticker(ticker)

    if result is None:
        st.error(f"Could not fetch data for '{ticker}'. Check the ticker symbol and try again.")
    else:
        m = result["metrics"]
        score = result["score"]
        recommendation = result["recommendation"]
        tone = result["tone"]

        c1, c2, c3, c4, c5 = st.columns(5)
        c1.metric("Price", f"${m['price']:.2f}", f"{m['day_change_pct']:.2f}%")
        c2.metric("52W Range", f"${m['low_52w']:.2f} - ${m['high_52w']:.2f}")
        c3.metric("From 52W High", f"{m['pct_from_high']:.1f}%")
        c4.metric("YTD Return", f"{m['ytd']:.1f}%" if m["ytd"] is not None else "N/A")
        c5.metric("Ann. Volatility", f"{m['volatility']:.1f}%" if m["volatility"] is not None else "N/A")

        banner = f"{display_name} ({ticker}) - {recommendation}  |  Composite score: {score}/100"
        if tone == "success":
            st.success(banner)
        elif tone == "warning":
            st.warning(banner)
        else:
            st.error(banner)

        narrative = None
        if use_ai and openai_key:
            narrative = ai_narrative(display_name, score, recommendation, result["reasons"], m, openai_key)
        if narrative is None:
            narrative = rule_based_narrative(display_name, recommendation, score, result["reasons"])
        st.markdown(narrative)

        with st.expander("See all contributing signals"):
            for text, weight in result["reasons"]:
                if weight > 0:
                    st.markdown(f"- (+{weight}) {text}")
                elif weight < 0:
                    st.markdown(f"- ({weight}) {text}")
                else:
                    st.markdown(f"- (neutral) {text}")

        plot_df = result["df_ind"]
        n_rows = {"6mo": 126, "1y": 252, "2y": len(plot_df)}[display_period]
        st.plotly_chart(make_chart(plot_df.tail(n_rows), display_name), use_container_width=True)

        info = result["info"] or {}
        if info:
            st.subheader("Key fundamentals")
            f1, f2, f3, f4 = st.columns(4)
            f1.metric("P/E (trailing)", f"{info.get('trailingPE'):.1f}" if info.get("trailingPE") else "N/A")
            f2.metric("Market Cap", f"${info.get('marketCap')/1e9:.1f}B" if info.get("marketCap") else "N/A")
            f3.metric("Dividend Yield", f"{info.get('dividendYield')*100:.2f}%" if info.get("dividendYield") else "N/A")
            f4.metric("Sector", info.get("sector", "N/A"))

        if result["headlines"]:
            st.subheader("Recent headlines")
            for h in result["headlines"]:
                if h.get("link"):
                    st.markdown(f"- [{h['title']}]({h['link']}) _{h.get('publisher','')}_")
                else:
                    st.markdown(f"- {h['title']} _{h.get('publisher','')}_")

with tab_watchlist:
    tickers = [t.strip().upper() for t in watchlist_input.split(",") if t.strip()]
    rows = []
    if tickers:
        with st.spinner("Scoring watchlist..."):
            for t in tickers:
                r = analyze_ticker(t)
                if r is None:
                    rows.append({"Ticker": t, "Price": None, "1D %": None, "Score": None, "Recommendation": "N/A"})
                    continue
                rows.append({
                    "Ticker": t,
                    "Price": round(r["metrics"]["price"], 2),
                    "1D %": round(r["metrics"]["day_change_pct"], 2),
                    "Score": r["score"],
                    "Recommendation": r["recommendation"],
                })
    if rows:
        watch_df = pd.DataFrame(rows).sort_values("Score", ascending=False, na_position="last")

        def color_score(val):
            if val is None or pd.isna(val):
                return ""
            if val >= 50:
                return "background-color: #1e7d32; color: white"
            elif val >= 20:
                return "background-color: #4caf50; color: white"
            elif val > -20:
                return "background-color: #ffb300; color: black"
            elif val > -50:
                return "background-color: #e53935; color: white"
            else:
                return "background-color: #b71c1c; color: white"

        styled = watch_df.style.applymap(color_score, subset=["Score"])
        st.dataframe(styled, use_container_width=True, hide_index=True)
    else:
        st.info("Add tickers in the sidebar (comma-separated) to build a watchlist.")

st.markdown("---")
st.caption(
    "Data via Yahoo Finance (yfinance). Signals are a simplified rule-based composite of "
    "technical indicators, basic valuation, and news tone. This tool does not constitute "
    "financial advice - always do your own research or consult a licensed advisor."
)
