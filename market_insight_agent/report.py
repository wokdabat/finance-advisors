"""
Orchestrates one full run: build scorecard -> build prompt -> call LLM
-> save markdown report -> (optional) push to Slack.

Functions are split into small reusable pieces (generate_report_text,
save_report, post_to_slack) so both the CLI (main.py) and the Streamlit
dashboard (app.py) can call exactly the parts they need instead of
duplicating logic.
"""
from __future__ import annotations
import datetime as dt
import logging
import os

import requests

import config
from scorecard import build_full_scorecard
from prompt_template import build_user_prompt
from llm_client import call_llm

log = logging.getLogger(__name__)


def generate_report_text(scorecard: dict) -> str:
    """Given an already-built scorecard, ask the LLM to synthesize the
    written report. Pure function: no file/network side effects besides
    the LLM call itself."""
    prompt = build_user_prompt(scorecard)
    return call_llm(prompt)


def save_report(report_text: str, timestamp: str | None = None) -> str:
    """Writes the report to a timestamped markdown file and returns the path."""
    os.makedirs(config.OUTPUT_DIR, exist_ok=True)
    timestamp = timestamp or dt.datetime.now().strftime("%Y-%m-%d_%H%M")
    out_path = os.path.join(config.OUTPUT_DIR, f"market_insight_{timestamp}.md")
    with open(out_path, "w") as f:
        f.write(f"# Market Insight Report — {timestamp}\n\n{report_text}\n")
    log.info("Report saved to %s", out_path)
    return out_path


def post_to_slack(report_text: str) -> bool:
    """Returns True on success, False otherwise. No-op (returns False)
    if no webhook is configured."""
    if not config.SLACK_WEBHOOK_URL:
        return False
    try:
        requests.post(
            config.SLACK_WEBHOOK_URL,
            json={"text": report_text[:3900]},  # Slack payload limits
            timeout=10,
        )
        return True
    except Exception as e:
        log.error("Slack post failed: %s", e)
        return False


def run_once() -> str:
    """Full pipeline used by the CLI / scheduler: fetch -> synthesize ->
    save -> (optional) Slack push."""
    scorecard = build_full_scorecard()
    report_text = generate_report_text(scorecard)
    out_path = save_report(report_text)
    if config.SLACK_WEBHOOK_URL:
        post_to_slack(report_text)
    return out_path
