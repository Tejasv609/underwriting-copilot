"""Optional LLM memo polish.

By default (no env config) the offline template renderer in nodes.py is used
verbatim — zero config, zero network. If UNDERWRITE_LLM_* env vars are set, the
memo prose is lightly rewritten via an OpenAI-compatible chat completions
endpoint. Any failure falls back to the template. The LLM never makes the
decision; it only rewords the memo.
"""

from __future__ import annotations

import os

import httpx

BASE_URL = os.environ.get("UNDERWRITE_LLM_BASE_URL", "")
API_KEY = os.environ.get("UNDERWRITE_LLM_API_KEY", "")
MODEL = os.environ.get("UNDERWRITE_LLM_MODEL", "")
TIMEOUT = float(os.environ.get("UNDERWRITE_LLM_TIMEOUT", "20"))


def _configured() -> bool:
    return bool(BASE_URL and MODEL)


def polish_memo(template_memo: str, context: dict) -> str:
    if not _configured():
        return template_memo
    try:
        with httpx.Client(timeout=TIMEOUT) as client:
            resp = client.post(
                BASE_URL.rstrip("/") + "/chat/completions",
                headers={"Authorization": f"Bearer {API_KEY}"} if API_KEY else {},
                json={
                    "model": MODEL,
                    "temperature": 0.2,
                    "max_tokens": 800,
                    "messages": [
                        {
                            "role": "system",
                            "content": (
                                "You are a credit-risk documentation assistant. Rewrite the "
                                "underwriting memo below in clear professional prose. Do NOT "
                                "change the decision, any number, or any policy citation. "
                                "Keep all sections and keep it factual."
                            ),
                        },
                        {
                            "role": "user",
                            "content": f"Decision: {context.get('decision')}. Product: {context.get('product')}.\n\n{template_memo}",
                        },
                    ],
                },
            )
            resp.raise_for_status()
            data = resp.json()
            text = data["choices"][0]["message"]["content"].strip()
            return text or template_memo
    except Exception:
        return template_memo
