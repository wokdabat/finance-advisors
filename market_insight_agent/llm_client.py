"""
Thin wrapper so the rest of the codebase doesn't care which LLM vendor
you use. Swap providers by changing config.LLM_PROVIDER; add new
branches here as needed.
"""
import config
from prompt_template import SYSTEM_PROMPT


def call_llm(user_prompt: str) -> str:
    if config.LLM_PROVIDER == "anthropic":
        return _call_anthropic(user_prompt)
    elif config.LLM_PROVIDER == "openai":
        return _call_openai(user_prompt)
    else:
        raise ValueError(f"Unknown LLM_PROVIDER: {config.LLM_PROVIDER}")


def _call_anthropic(user_prompt: str) -> str:
    import anthropic

    client = anthropic.Anthropic(api_key=config.LLM_API_KEY)
    message = client.messages.create(
        model=config.LLM_MODEL,
        max_tokens=1500,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_prompt}],
    )
    return message.content[0].text


def _call_openai(user_prompt: str) -> str:
    from openai import OpenAI

    client = OpenAI(api_key=config.LLM_API_KEY)
    resp = client.chat.completions.create(
        model=config.LLM_MODEL,
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user", "content": user_prompt},
        ],
        max_tokens=1500,
    )
    return resp.choices[0].message.content
