"""
Turns the raw scorecard dict into a prompt for the LLM, and defines the
output format we want back. Keeping the prompt in its own file makes it
easy to iterate on wording without touching data/indicator code.
"""
import json

SYSTEM_PROMPT = """\
You are a markets analyst assistant. You will be given:
1) a structured "scorecard" of computed technical/valuation/macro signals
   for equities, gold, and real estate proxies, and
2) a handful of recent headlines.

Your job: write a concise, well-organized market insight report for a
retail investor. Rules:
- Be explicit that this is not personalized financial advice.
- Do not invent numbers that are not present in the scorecard or headlines.
- Where signals conflict, say so explicitly rather than picking a side.
- For each asset class, give a "lean" (e.g. Bullish / Neutral / Cautious /
  Bearish) AND state the 1-2 concrete data points driving that lean.
- Flag the single biggest risk that could invalidate each lean.
- End with a short "what would change my mind" section per asset class,
  so the user knows what signals to watch for next time.
- Keep it under 500 words. Use markdown headers and bullet points.
"""

USER_PROMPT_TEMPLATE = """\
Here is today's scorecard (JSON):

```json
{scorecard_json}
```

Here are recent relevant headlines:

{headlines_block}

Please produce the market insight report following the system instructions.
"""


def format_headlines(headlines: list[dict], limit: int = 8) -> str:
    if not headlines:
        return "(no headlines retrieved this run)"
    lines = []
    for h in headlines[:limit]:
        lines.append(f"- [{h.get('source', 'unknown')}] {h.get('title', '')} ({h.get('publishedAt', '')})")
    return "\n".join(lines)


def build_user_prompt(scorecard: dict) -> str:
    headlines = scorecard.get("headlines", [])
    scorecard_for_prompt = {k: v for k, v in scorecard.items() if k != "headlines"}
    return USER_PROMPT_TEMPLATE.format(
        scorecard_json=json.dumps(scorecard_for_prompt, indent=2, default=str),
        headlines_block=format_headlines(headlines),
    )
