# Finance Advisors

An AI-powered financial market insight platform built on **Vercel's [eve](https://eve.dev)** framework. All work in this repository — the eve agent scaffold, the Streamlit dashboards, and the AI-generated market reports — was built using eve.

> Educational project. Nothing in this repository is financial advice.

## Overview

This repo contains an **eve agent** (TypeScript, powered by Claude via the Vercel AI SDK) alongside **two independent Streamlit dashboards** that surface market data and technical signals for equities, gold/commodities, real estate, and crypto.

## The two dashboards

### 1. `market_insight_agent/` — Market Insight Dashboard

The primary, actively developed dashboard. A multi-tab Streamlit app plus a standalone CLI/scheduler for automated report generation.

- **Tabs:** Equities, Gold, Real Estate, Macro & Rates, AI Insight, History
- **Signals computed locally (no LLM required to view):** trend, 21-day momentum, valuation (P/E), and a sector/factor breadth proxy (`indicators.py`)
- **Breadth proxy tickers:** Semiconductors (SOXX), Momentum factor (MTUM), Equal-weight S&P (RSP)
- **Macro data:** pulled from FRED — 30yr mortgage rate, Fed funds rate, CPI, 10-year Treasury yield, unemployment rate, Case-Shiller home price index
- **AI Insight tab:** generates a synthesized written report via an LLM (Anthropic or OpenAI, configurable), optionally pushed to Slack via webhook, with a **PDF download button** for the generated report
- **History tab:** browse previously generated markdown reports (saved under `reports/`), each downloadable as a **PDF**
- **CLI mode** (`main.py`): run a single report (`--once`) or schedule a daily run (`--schedule "08:30"`) via APScheduler
- **Caching:** price/macro data cached 15 minutes via `st.cache_data` so tab switches don't re-hit yfinance/FRED

Run it with:
```bash
cd market_insight_agent
pip install -r requirements.txt
cp .env.example .env   # fill in your own values — never commit .env
streamlit run app.py
```

### 2. `workspace/` — Market Insight Agent (standalone)

A single-file, self-contained Streamlit + Plotly app covering a broader asset catalog with lightweight news-sentiment scoring.

- **Asset catalog:** Stocks & Indices (AAPL, MSFT, AMZN, GOOGL, NVDA, TSLA, S&P 500, Nasdaq 100, Dow Jones), Gold & Commodities (Gold/Silver futures, GLD, Crude Oil, Copper), Real Estate REIT proxies (VNQ, IYR, SCHH, PLD, AMT, O), Crypto (BTC, ETH, SOL)
- **Sentiment:** simple positive/negative keyword scoring over headlines
- **Charts:** interactive Plotly candlestick/subplot charts
- **PDF download button:** the Analysis tab's generated ticker report (metrics, recommendation, narrative, signals, headlines) can be downloaded as a PDF

Run it with:
```bash
cd workspace
pip install -r requirements.txt
streamlit run app.py
```

## Repository structure

```
financial-advisors/
├── agent/
│   └── agent.ts              # eve agent definition (Claude Sonnet 5 via @ai-sdk/anthropic)
├── market_insight_agent/     # Dashboard #1 — full-featured, multi-tab Streamlit app
│   ├── app.py                 # Streamlit UI (tabs, charts, AI report controls)
│   ├── config.py               # Tickers, FRED series, LLM/Slack/env config
│   ├── data_sources.py         # yfinance / FRED / news fetchers
│   ├── indicators.py           # Trend, momentum, valuation, breadth signal calculations
│   ├── scorecard.py             # Aggregates signals into a full scorecard for the LLM
│   ├── prompt_template.py       # LLM prompt construction
│   ├── llm_client.py            # Anthropic/OpenAI client wrapper
│   ├── report.py                 # Report generation, saving, Slack push
│   ├── main.py                    # CLI entry point (--once / --schedule)
│   ├── reports/                    # Saved markdown reports (generated output)
│   ├── requirements.txt
│   └── .env.example                # Template — copy to .env, fill in secrets, never commit
├── workspace/                 # Dashboard #2 — standalone single-file Streamlit app
│   ├── app.py
│   └── requirements.txt
├── package.json                # eve project manifest (build/dev/start scripts)
├── tsconfig.json
├── AGENTS.md                    # eve-specific agent instructions
├── CLAUDE.md
└── README.md                    # this file
```

## Tech stack

- **Agent framework:** [eve](https://eve.dev) (Vercel)
- **Agent runtime:** TypeScript, [Vercel AI SDK](https://sdk.vercel.ai), `@ai-sdk/anthropic`
- **Model:** Claude Sonnet 5
- **Dashboards:** Python, Streamlit, Plotly
- **PDF generation:** `fpdf2`
- **Data sources:** yfinance, FRED (via `pandas_datareader`), NewsAPI/RSS fallback
- **Report delivery:** Slack incoming webhooks

## Environment variables

Each dashboard has its own `.env` (see `market_insight_agent/.env.example` for the full list — `LLM_PROVIDER`, `LLM_API_KEY`, `LLM_MODEL`, `NEWS_API_KEY`, `SLACK_WEBHOOK_URL`, `OUTPUT_DIR`). The eve agent itself is configured via `.env.local` at the repo root. **Never commit real `.env`/`.env.local` files** — both are excluded via `.gitignore`.
