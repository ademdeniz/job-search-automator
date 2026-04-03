"""
Job fit scorer using Claude API.

Reads the candidate's resume from resume.txt (project root) and scores
each job description on a 0-100 scale, returning a structured result with
matched skills, gaps, and a one-line summary.
"""

import json
import os
import textwrap
from dataclasses import dataclass
from typing import List, Optional

import anthropic

RESUME_PATH = os.path.join(os.path.dirname(__file__), "..", "resume.txt")

# Use Haiku for cost-efficient batch scoring — fast and accurate enough for fit analysis.
MODEL = "claude-haiku-4-5-20251001"

SYSTEM_PROMPT = textwrap.dedent("""
    You are a senior technical recruiter and career coach who specialises in QA / SDET roles.
    Your job is to analyse how well a candidate's resume matches a specific job posting.

    Return ONLY valid JSON — no markdown fences, no extra text — in exactly this shape:
    {
      "score": <integer 0-100>,
      "match_level": "<poor|fair|good|excellent>",
      "matched_skills": [<string>, ...],
      "missing_skills": [<string>, ...],
      "highlights": "<one sentence: why this is or isn't a strong fit>",
      "suggested_keywords": [<string>, ...]
    }

    Scoring guide:
      90-100  Excellent — almost all required skills present, strong seniority match
      70-89   Good      — most core skills present, minor gaps
      50-69   Fair      — some overlap but notable gaps or seniority mismatch
      0-49    Poor      — significant skill or domain mismatch

    suggested_keywords: 3-5 terms from the job description the candidate should weave
    into their resume or cover letter if they apply.
""").strip()


@dataclass
class ScoreResult:
    score: int
    match_level: str
    matched_skills: List[str]
    missing_skills: List[str]
    highlights: str
    suggested_keywords: List[str]
    raw: dict


def _load_resume() -> str:
    if not os.path.exists(RESUME_PATH):
        raise FileNotFoundError(
            f"resume.txt not found at {RESUME_PATH}. "
            "Run: python main.py resume --set  (or create resume.txt manually)"
        )
    with open(RESUME_PATH, encoding="utf-8") as f:
        return f.read().strip()


def score_job(title: str, company: str, description: str,
              resume_text: Optional[str] = None) -> ScoreResult:
    """Score a single job against the candidate's resume."""
    if resume_text is None:
        resume_text = _load_resume()

    client = anthropic.Anthropic()  # reads ANTHROPIC_API_KEY from env

    user_message = textwrap.dedent(f"""
        ## Candidate Resume
        {resume_text}

        ## Job Posting
        Title:   {title}
        Company: {company}

        {description}
    """).strip()

    message = client.messages.create(
        model=MODEL,
        max_tokens=512,
        system=SYSTEM_PROMPT,
        messages=[{"role": "user", "content": user_message}],
    )

    raw_text = message.content[0].text.strip()
    try:
        data = json.loads(raw_text)
    except json.JSONDecodeError:
        # Claude occasionally wraps in a code fence despite instructions — strip it
        import re
        match = re.search(r"\{.*\}", raw_text, re.DOTALL)
        if match:
            data = json.loads(match.group())
        else:
            raise ValueError(f"Could not parse JSON from scorer response:\n{raw_text}")

    return ScoreResult(
        score=int(data.get("score", 0)),
        match_level=data.get("match_level", "unknown"),
        matched_skills=data.get("matched_skills", []),
        missing_skills=data.get("missing_skills", []),
        highlights=data.get("highlights", ""),
        suggested_keywords=data.get("suggested_keywords", []),
        raw=data,
    )


def score_jobs_batch(jobs: list, resume_text: Optional[str] = None,
                     on_progress=None) -> List[tuple]:
    """
    Score a list of job dicts.
    Returns list of (job_id, ScoreResult).
    on_progress(current, total, job) called after each scored job.
    """
    if resume_text is None:
        resume_text = _load_resume()

    results = []
    total = len(jobs)
    for i, job in enumerate(jobs, 1):
        try:
            result = score_job(
                title=job["title"],
                company=job["company"],
                description=job.get("description", ""),
                resume_text=resume_text,
            )
        except Exception as e:
            print(f"  [scorer] Error scoring job {job['id']} ({job['title']}): {e}")
            result = None

        results.append((job["id"], result))
        if on_progress:
            on_progress(i, total, job)

    return results
