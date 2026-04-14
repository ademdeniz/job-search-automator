# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Company health signal analysis using Claude Haiku.

Detects red flags like recent layoffs, low Glassdoor ratings, financial trouble,
or high churn — using Claude's training knowledge. Works for well-known companies;
returns "no data" gracefully for smaller/unknown ones.
"""

import json
import os
import textwrap
from typing import Optional

import anthropic

MODEL = "claude-haiku-4-5-20251001"

_SYSTEM = textwrap.dedent("""
    You are a job search advisor helping a candidate assess company health before applying.

    Given a company name and optional context, identify red flags using your knowledge.
    Look for: recent layoffs, mass exits, Glassdoor rating below 3.5, financial distress,
    funding issues, high executive turnover, toxic culture reports, legal/regulatory trouble.

    Return ONLY valid JSON — no markdown fences, no extra text:
    {
      "level": <0|1|2|3>,
      "flags": [<string>, ...],
      "summary": "<one sentence overall assessment>"
    }

    Level guide:
      0 — No notable concerns found (or company is unknown/too small to assess)
      1 — Minor concerns (e.g. some negative reviews, one-time restructuring years ago)
      2 — Moderate concerns (e.g. recent layoffs <12 months, declining Glassdoor, funding issues)
      3 — Serious concerns (e.g. mass layoffs, bankruptcy risk, fraud, CEO exits under pressure)

    flags: 2-5 specific signals, each ≤15 words. Empty array if level 0.
    If you have no reliable information about this company, return level 0 with an empty flags array
    and summary "No notable signals found."
""").strip()


def fetch_company_signals(company: str, job_title: str = "",
                          location: str = "") -> dict:
    """
    Assess company health red flags using Claude's training knowledge.

    Returns:
        {
            "level": int (0-3),
            "flags": list[str],
            "summary": str
        }
    """
    _key = os.environ.get("ANTHROPIC_API_KEY")
    if not _key:
        try:
            with open(os.path.expanduser("~/.zshrc")) as f:
                for line in f:
                    line = line.strip()
                    if line.startswith("export ANTHROPIC_API_KEY="):
                        os.environ["ANTHROPIC_API_KEY"] = line.split("=", 1)[1].strip().strip("'\"")
                        break
        except Exception:
            pass

    user_msg = f"Company: {company}"
    if job_title:
        user_msg += f"\nRole: {job_title}"
    if location:
        user_msg += f"\nLocation: {location}"

    client = anthropic.Anthropic()
    msg = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=_SYSTEM,
        messages=[{"role": "user", "content": user_msg}],
    )
    raw = msg.content[0].text.strip()

    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        import re
        m = re.search(r"\{.*\}", raw, re.DOTALL)
        data = json.loads(m.group()) if m else {}

    return {
        "level":   int(data.get("level", 0)),
        "flags":   data.get("flags", []),
        "summary": data.get("summary", "No notable signals found."),
    }
