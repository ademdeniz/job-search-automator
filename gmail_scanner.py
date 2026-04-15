# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Gmail inbox scanner — detects responses from companies you applied to.

Requires a Google Cloud project with the Gmail API enabled:
  1. Go to console.cloud.google.com → APIs & Services → Enable "Gmail API"
  2. Create OAuth 2.0 credentials (Desktop app) → download as credentials.json
  3. Place credentials.json in the repo root (gitignored)
  4. First run opens a browser tab for Google sign-in → stores token.json locally

Scopes: gmail.readonly (read-only — never sends or deletes anything)
"""

import json
import os
import re
from pathlib import Path

ROOT = Path(__file__).parent
CREDENTIALS_FILE = ROOT / "credentials.json"
TOKEN_FILE       = ROOT / "token.json"
SCOPES           = ["https://www.googleapis.com/auth/gmail.readonly"]


# ── OAuth helpers ─────────────────────────────────────────────────────────────

def _get_gmail_service():
    """
    Authenticate and return a Gmail API service object.
    Raises FileNotFoundError if credentials.json is missing.
    Raises ImportError if google-auth packages are not installed.
    """
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build

    if not CREDENTIALS_FILE.exists():
        raise FileNotFoundError(
            "credentials.json not found. See the Gmail Setup section in Actions to get started."
        )

    creds = None
    if TOKEN_FILE.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_FILE), SCOPES)

    if not creds or not creds.valid:
        if creds and creds.expired and creds.refresh_token:
            creds.refresh(Request())
        else:
            flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_FILE), SCOPES)
            creds = flow.run_local_server(port=0)
        with open(TOKEN_FILE, "w") as f:
            f.write(creds.to_json())

    return build("gmail", "v1", credentials=creds)


def is_configured() -> bool:
    """True if credentials.json exists (setup complete)."""
    return CREDENTIALS_FILE.exists()


def is_authenticated() -> bool:
    """True if token.json exists (user has completed OAuth flow)."""
    return TOKEN_FILE.exists()


# ── Core scanner ──────────────────────────────────────────────────────────────

def _search_messages(service, query: str, max_results: int = 50) -> list:
    """Run a Gmail search query and return list of message metadata dicts."""
    result = service.users().messages().list(
        userId="me", q=query, maxResults=max_results
    ).execute()
    return result.get("messages", [])


def _get_message(service, msg_id: str) -> dict:
    """Fetch a single message with full payload."""
    return service.users().messages().get(
        userId="me", id=msg_id, format="full"
    ).execute()


def _extract_text(msg: dict) -> tuple:
    """
    Extract (subject, body_snippet) from a Gmail message dict.
    Returns plain text — strips HTML tags from body if needed.
    """
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "(no subject)")
    sender  = headers.get("from", "")
    snippet = msg.get("snippet", "")

    # snippet is plain text and usually enough for classification (200 chars)
    return subject, sender, snippet


def _classify_emails(emails: list, applied_jobs: list) -> list:
    """
    Use Claude Haiku to classify a batch of emails and match them to jobs.

    emails: list of {"job_id", "company", "subject", "sender", "snippet"}
    Returns list of {"job_id", "company", "subject", "sender", "snippet",
                      "type", "confidence", "suggested_status", "summary"}
    """
    if not emails:
        return []

    import anthropic
    client = anthropic.Anthropic()

    # Build compact prompt — one email per line
    email_lines = "\n".join(
        f'[{i}] Company: {e["company"]} | From: {e["sender"]} | '
        f'Subject: {e["subject"]} | Snippet: {e["snippet"][:200]}'
        for i, e in enumerate(emails)
    )

    prompt = f"""You are classifying emails received after a job application.
For each email below, return a JSON array where each item has:
- "index": the [N] number
- "type": one of "interview_invite", "rejection", "offer", "info_request", "confirmation", "other"
- "confidence": 0.0-1.0
- "suggested_status": "interviewing" for interview_invite/offer, "rejected" for rejection, null otherwise
- "summary": one short sentence describing what the email is about

Emails:
{email_lines}

Return ONLY a valid JSON array, no other text."""

    try:
        resp = client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        raw = resp.content[0].text.strip()
        # Strip markdown code fences if present
        raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
        classifications = json.loads(raw)
    except Exception as e:
        print(f"[Gmail] Classification failed: {e}")
        return []

    results = []
    for c in classifications:
        idx = c.get("index", -1)
        if 0 <= idx < len(emails):
            results.append({**emails[idx], **c})
    return results


# ── Public API ────────────────────────────────────────────────────────────────

def scan_for_responses(applied_jobs: list, days_back: int = 30) -> dict:
    """
    Scan Gmail inbox for responses from companies in applied_jobs.

    applied_jobs: list of job dicts (must have 'id', 'company', 'title')
    days_back: how far back to search (default 30 days)

    Returns:
    {
      "results": list of classified email matches,
      "scanned": int — number of emails examined,
      "error": str or None
    }
    """
    if not applied_jobs:
        return {"results": [], "scanned": 0, "error": None}

    try:
        service = _get_gmail_service()
    except FileNotFoundError as e:
        return {"results": [], "scanned": 0, "error": str(e)}
    except Exception as e:
        return {"results": [], "scanned": 0, "error": f"Auth error: {e}"}

    from datetime import datetime, timedelta
    cutoff = (datetime.now() - timedelta(days=days_back)).strftime("%Y/%m/%d")

    # Build company name search terms — quote multi-word names
    company_terms = []
    for job in applied_jobs:
        name = job.get("company", "").strip()
        if name:
            company_terms.append(f'"{name}"' if " " in name else name)

    if not company_terms:
        return {"results": [], "scanned": 0, "error": None}

    # Deduplicate
    unique_terms = list(dict.fromkeys(company_terms))[:30]  # cap at 30 to keep query short
    company_query = " OR ".join(unique_terms)

    # Job-related keywords to filter noise
    job_keywords = (
        "interview OR application OR applied OR position OR role OR opportunity OR "
        "candidate OR hiring OR offer OR unfortunately OR regret OR moving forward OR "
        "next steps OR schedule OR assessment OR screening"
    )

    query = f"({company_query}) ({job_keywords}) after:{cutoff}"

    try:
        messages = _search_messages(service, query, max_results=50)
    except Exception as e:
        return {"results": [], "scanned": 0, "error": f"Search failed: {e}"}

    if not messages:
        return {"results": [], "scanned": 0, "error": None}

    # Build a lookup: company name (lower) → job
    company_job_map = {}
    for job in applied_jobs:
        key = job.get("company", "").strip().lower()
        if key:
            company_job_map[key] = job

    # Fetch and match emails to jobs
    emails_to_classify = []
    for msg_meta in messages:
        try:
            msg = _get_message(service, msg_meta["id"])
            subject, sender, snippet = _extract_text(msg)

            # Match to a job by company name mention
            matched_job = None
            subject_lower = (subject + " " + snippet).lower()
            for company_key, job in company_job_map.items():
                if company_key and company_key in subject_lower:
                    matched_job = job
                    break
                # Also check if sender domain contains company name fragment
                sender_lower = sender.lower()
                if company_key and len(company_key) > 4:
                    # Use first significant word of company name
                    first_word = company_key.split()[0]
                    if len(first_word) > 4 and first_word in sender_lower:
                        matched_job = job
                        break

            if matched_job:
                emails_to_classify.append({
                    "job_id":  matched_job["id"],
                    "company": matched_job["company"],
                    "title":   matched_job.get("title", ""),
                    "subject": subject,
                    "sender":  sender,
                    "snippet": snippet,
                    "msg_id":  msg_meta["id"],
                })
        except Exception:
            continue

    classified = _classify_emails(emails_to_classify, applied_jobs)

    # Filter to only actionable results (confidence >= 0.6, not "other")
    actionable = [
        r for r in classified
        if r.get("confidence", 0) >= 0.6 and r.get("type") != "other"
    ]

    return {
        "results":  actionable,
        "scanned":  len(messages),
        "error":    None,
    }
