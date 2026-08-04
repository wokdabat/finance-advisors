"""
Streamlit dashboard for the market insight agent.

Run with:
    streamlit run app.py

Layout:
- Sidebar: refresh data, generate/regenerate the AI report, config status.
- Tabs: Equities / Gold / Real Estate / Macro & Rates (charts + raw
  signals, computed locally -- no LLM needed to view these) and an
  "AI Insight" tab (the synthesized written report) + a "History" tab
  to browse previously saved reports.

Caching: raw data pulls (prices, macro series) are cached for 15
minutes via st.cache_data so repeated interactions (switching tabs,
etc.) don't re-hit yfinance/FRED on every rerun. The LLM call is NOT
auto-cached -- it only runs when you click the "Generate" button, and
the result is kept in st.session_state so it survives reruns until you
explicitly regenerate it.
"""
from __future__ import annotations
import datetime as dt
import glob
import os

import pandas as pd
import streamlit as st
from fpdf import FPDF

import config
import data_sources as ds
import indicators as ind
import scorecard as sc
import report as rpt

CACHE_TTL_SECONDS = 15 * 60  # 15 minutes; prices/macro data don't need to be real-time


# ---------------------------------------------------------------------
# Cached data-fetch wrappers (thin pass-throughs to data_sources.py so
# Streamlit can memoize network calls independently of the CLI pipeline)
# ---------------------------------------------------------------------
@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_price_history(ticker: str, period: str = "1y") -> pd.DataFrame:
    return ds.fetch_price_history(ticker, period=period)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_fundamentals(ticker: str) -> dict:
    return ds.fetch_fundamentals(ticker)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner=False)
def cached_fred_series(series_id: str) -> pd.Series:
    return ds.fetch_fred_series(series_id)


@st.cache_data(ttl=CACHE_TTL_SECONDS, show_spinner="Building full scorecard...")
def cached_full_scorecard() -> dict:
    return sc.build_full_scorecard()


# ---------------------------------------------------------------------
# Small render helpers
# ---------------------------------------------------------------------
def render_ticker_panel(display_name: str, ticker: str, show_valuation: bool = False):
    hist = cached_price_history(ticker)
    if hist.empty:
        st.warning(f"No data returned for {display_name} ({ticker}).")
        return

    trend = ind.trend_signal(hist)
    momentum = ind.momentum_signal(hist)

    st.subheader(f"{display_name}  ·  `{ticker}`")

    cols = st.columns(5 if show_valuation else 4)
    cols[0].metric("Last price", f"{trend.get('last_price', '—')}")
    cols[1].metric("vs 52w high", f"{trend.get('pct_off_52w_high', '—')}%")
    cols[2].metric("Trend", trend.get("trend", "—").replace("_", " ").title())
    cols[3].metric("21d momentum", f"{momentum.get('momentum_pct', '—')}%")

    if show_valuation:
        fundamentals = cached_fundamentals(ticker)
        val = ind.valuation_signal(fundamentals.get("trailingPE"))
        label = val.get("valuation", "unknown")
        pe = val.get("trailing_pe", "—")
        cols[4].metric("Valuation (P/E)", f"{label} ({pe})")

    # Price + moving averages chart
    chart_df = hist[["Close"]].copy()
    chart_df["MA50"] = hist["Close"].rolling(50).mean()
    chart_df["MA200"] = hist["Close"].rolling(200).mean()
    st.line_chart(chart_df)
    st.divider()


def render_macro_panel():
    for name, series_id in config.FRED_SERIES.items():
        series = cached_fred_series(series_id)
        if series.empty:
            st.warning(f"No FRED data for {name} ({series_id}).")
            continue
        latest = series.iloc[-1]
        three_months_ago = series.iloc[max(0, len(series) - 63)]
        direction = "🔺 rising" if latest > three_months_ago else (
            "🔻 falling" if latest < three_months_ago else "→ flat"
        )
        c1, c2 = st.columns([1, 3])
        with c1:
            st.metric(name, f"{latest:.2f}", help=f"3-month trend: {direction}")
            st.caption(f"3-month trend: {direction}")
        with c2:
            st.line_chart(series.tail(365))
        st.divider()


def list_saved_reports() -> list[str]:
    pattern = os.path.join(config.OUTPUT_DIR, "market_insight_*.md")
    files = sorted(glob.glob(pattern), reverse=True)
    return files


_PDF_CHAR_REPLACEMENTS = {
    "—": "-", "–": "-",  # em/en dash
    "‘": "'", "’": "'",  # curly single quotes
    "“": '"', "”": '"',  # curly double quotes
    "…": "...",  # ellipsis
    " ": " ",  # non-breaking space
    "•": "-",  # bullet
    "↓": "v", "→": "->",  # flow arrows (core fonts have no arrow glyph)
}


def _pdf_safe(text: str) -> str:
    """Core PDF fonts only support Latin-1; normalize common Unicode typography
    (em dashes, curly quotes, etc. -- common in LLM-generated text) to ASCII,
    then fall back to replacing anything else so rendering never crashes."""
    for src, dst in _PDF_CHAR_REPLACEMENTS.items():
        text = text.replace(src, dst)
    return text.encode("latin-1", "replace").decode("latin-1")


def markdown_to_pdf_bytes(text: str) -> bytes:
    """Very small markdown-ish -> PDF renderer (headings, bold lines, paragraphs)."""
    text = _pdf_safe(text)
    pdf = FPDF()
    pdf.set_auto_page_break(auto=True, margin=15)
    pdf.add_page()
    pdf.set_font("helvetica", size=11)
    for raw_line in text.splitlines() or [""]:
        line = raw_line.strip()
        if line.startswith("# "):
            pdf.set_font("helvetica", "B", 16)
            pdf.multi_cell(0, 8, line[2:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", size=11)
        elif line.startswith("## "):
            pdf.set_font("helvetica", "B", 13)
            pdf.multi_cell(0, 7, line[3:], new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", size=11)
        elif line.startswith("**") and line.endswith("**"):
            pdf.set_font("helvetica", "B", 11)
            pdf.multi_cell(0, 6, line.strip("*"), new_x="LMARGIN", new_y="NEXT")
            pdf.set_font("helvetica", size=11)
        elif not line:
            pdf.ln(3)
        else:
            pdf.multi_cell(0, 6, line.replace("**", "").replace("_", ""), new_x="LMARGIN", new_y="NEXT")
    return bytes(pdf.output())


# ---------------------------------------------------------------------
# Page setup
# ---------------------------------------------------------------------
st.set_page_config(page_title="Market Insight Dashboard", page_icon="📊", layout="wide")
st.title("📊 Market Insight Dashboard")
st.caption(
    "Educational market-condition dashboard. Not personalized financial advice. "
    f"Data cached for {CACHE_TTL_SECONDS // 60} minutes."
)

if "report_text" not in st.session_state:
    st.session_state.report_text = None
    st.session_state.report_time = None

# --- Sidebar controls ---
with st.sidebar:
    st.header("Controls")

    if st.button("🔄 Refresh market data", use_container_width=True):
        st.cache_data.clear()
        st.rerun()

    st.divider()
    st.subheader("AI Insight Report")

    llm_ready = bool(config.LLM_API_KEY)
    if not llm_ready:
        st.warning("Set LLM_API_KEY in your .env to enable report generation.")

    if st.button("🤖 Generate / Regenerate report", disabled=not llm_ready, use_container_width=True):
        with st.spinner("Fetching data and asking the model..."):
            full_scorecard = cached_full_scorecard()
            text = rpt.generate_report_text(full_scorecard)
            path = rpt.save_report(text)
            st.session_state.report_text = text
            st.session_state.report_time = dt.datetime.now().strftime("%Y-%m-%d %H:%M")
            st.session_state.report_path = path
        st.success(f"Report generated and saved to {path}")

    if config.SLACK_WEBHOOK_URL and st.session_state.report_text:
        if st.button("📤 Push last report to Slack", use_container_width=True):
            ok = rpt.post_to_slack(st.session_state.report_text)
            st.success("Sent to Slack.") if ok else st.error("Slack push failed.")

    st.divider()
    st.caption(f"Tracked tickers: {len(config.EQUITY_TICKERS) + len(config.COMMODITY_TICKERS) + len(config.REAL_ESTATE_TICKERS)}")
    st.caption(f"LLM provider: {config.LLM_PROVIDER} ({config.LLM_MODEL})")


# --- Main tabs ---
tab_equities, tab_gold, tab_re, tab_macro, tab_ai, tab_history = st.tabs(
    ["📈 Equities", "🥇 Gold", "🏠 Real Estate", "🌐 Macro & Rates", "🧠 AI Insight", "🗂 History"]
)

with tab_equities:
    st.write("Trend, momentum, and rough valuation for the major U.S. equity indices.")
    for name, ticker in config.EQUITY_TICKERS.items():
        render_ticker_panel(name, ticker, show_valuation=True)

    st.subheader("Breadth proxy (sector/factor ETFs above 200-day MA)")
    proxy_histories = {
        name: cached_price_history(ticker) for name, ticker in config.BREADTH_PROXY_TICKERS.items()
    }
    breadth = ind.breadth_signal(proxy_histories)
    pct = breadth.get("pct_proxies_above_200dma")
    st.metric("% of proxies above 200dma", f"{pct}%" if pct is not None else "—")
    detail_cols = st.columns(len(breadth["detail"]) or 1)
    for col, (name, status) in zip(detail_cols, breadth["detail"].items()):
        emoji = "✅" if status == "above_200dma" else "❌"
        col.metric(name, f"{emoji} {status.replace('_', ' ')}")

with tab_gold:
    st.write("Gold futures and the GLD ETF as a more liquid/reliable price proxy.")
    for name, ticker in config.COMMODITY_TICKERS.items():
        render_ticker_panel(name, ticker)

with tab_re:
    st.write("Homebuilder and REIT ETFs as a market-based read on real estate sentiment "
             "(actual home prices/mortgage rates are in the Macro tab).")
    for name, ticker in config.REAL_ESTATE_TICKERS.items():
        render_ticker_panel(name, ticker)

with tab_macro:
    st.write("Macro backdrop: rates, inflation, and the housing-specific Case-Shiller index.")
    render_macro_panel()

with tab_ai:
    st.write(
        "This is the LLM-synthesized report: it reasons over the computed scorecard "
        "above plus recent headlines. Click **Generate / Regenerate report** in the sidebar."
    )
    if st.session_state.report_text:
        st.caption(f"Generated at {st.session_state.report_time}")
        report_stem = os.path.splitext(os.path.basename(st.session_state.get("report_path") or "market_insight_report.md"))[0]
        st.download_button(
            "⬇️ Download report (.pdf)",
            data=markdown_to_pdf_bytes(st.session_state.report_text),
            file_name=f"{report_stem}.pdf",
            mime="application/pdf",
        )
        st.markdown(st.session_state.report_text)
    else:
        st.info("No report generated yet this session. Use the sidebar button to create one.")

with tab_history:
    st.write("Previously saved reports (from `./reports` by default).")
    files = list_saved_reports()
    if not files:
        st.info("No saved reports found yet.")
    else:
        choice = st.selectbox("Choose a report", files, format_func=os.path.basename)
        if choice:
            try:
                with open(choice, encoding="utf-8") as f:
                    content = f.read()
            except UnicodeDecodeError:
                with open(choice, encoding="cp1252") as f:
                    content = f.read()
            report_stem = os.path.splitext(os.path.basename(choice))[0]
            st.download_button(
                "⬇️ Download this report (.pdf)",
                data=markdown_to_pdf_bytes(content),
                file_name=f"{report_stem}.pdf",
                mime="application/pdf",
            )
            st.markdown(content)
