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


def _decode_body(data: str) -> str:
    """Base64url-decode a Gmail message part body."""
    import base64
    try:
        return base64.urlsafe_b64decode(data + "==").decode("utf-8", errors="replace")
    except Exception:
        return ""


def _parse_ical(ical_text: str) -> str:
    """
    Extract human-readable details from iCal text.
    Returns a plain-text summary of the event.
    """
    def _ical_val(key: str) -> str:
        m = re.search(rf"^{key}[;:][^\r\n]*:?(.+)$", ical_text, re.MULTILINE | re.IGNORECASE)
        if not m:
            return ""
        # Handle folded lines (iCal lines can wrap with leading space/tab)
        raw = m.group(0)
        # Strip the key prefix
        val = re.sub(rf"^{key}[^:]*:", "", raw, flags=re.IGNORECASE).strip()
        return val

    summary  = _ical_val("SUMMARY")
    start    = _ical_val("DTSTART")
    end      = _ical_val("DTEND")
    location = _ical_val("LOCATION")
    desc     = _ical_val("DESCRIPTION")
    organizer = re.search(r'CN=([^:;\r\n]+)', ical_text)
    organizer = organizer.group(1).strip() if organizer else ""

    parts = []
    if summary:  parts.append(f"Event: {summary}")
    if start:    parts.append(f"Start: {start}")
    if end:      parts.append(f"End: {end}")
    if location: parts.append(f"Location: {location}")
    if organizer: parts.append(f"Organizer: {organizer}")
    if desc:     parts.append(f"Details: {desc[:400]}")
    return "\n".join(parts)


def _extract_plain_text(payload: dict) -> str:
    """
    Recursively walk the MIME payload to find the best plain-text body.
    Handles text/plain, text/html, and text/calendar (meeting invites).
    Returns the richest available text, preferring calendar data for invites.
    """
    mime = payload.get("mimeType", "")
    body_data = payload.get("body", {}).get("data", "")

    if mime == "text/calendar" and body_data:
        ical = _decode_body(body_data)
        return _parse_ical(ical)

    if mime == "text/plain" and body_data:
        return _decode_body(body_data)

    if mime == "text/html" and body_data:
        html = _decode_body(body_data)
        text = re.sub(r"<[^>]+>", " ", html)
        text = re.sub(r"\s+", " ", text).strip()
        return text

    # Walk parts — collect all, prefer calendar > plain > html
    calendar_text = ""
    plain_text = ""
    html_text = ""
    for part in payload.get("parts", []):
        result = _extract_plain_text(part)
        sub_mime = part.get("mimeType", "")
        if result:
            if "calendar" in sub_mime:
                calendar_text = result
            elif sub_mime == "text/plain":
                plain_text = result
            elif sub_mime == "text/html":
                html_text = result
            elif not plain_text and not calendar_text:
                plain_text = result

    return calendar_text or plain_text or html_text


def _extract_text(msg: dict) -> tuple:
    """
    Extract (subject, sender, body_text) from a Gmail message dict.
    Returns up to 800 chars of body text for richer classification.
    """
    headers = {h["name"].lower(): h["value"] for h in msg.get("payload", {}).get("headers", [])}
    subject = headers.get("subject", "(no subject)")
    sender  = headers.get("from", "")
    date    = headers.get("date", "")

    body = _extract_plain_text(msg.get("payload", {}))
    if not body:
        body = msg.get("snippet", "")

    return subject, sender, body[:800], date


_CLASSIFY_PROMPT = """You are classifying emails received after a job application.
For each email below, return a JSON array where each item has:
- "index": the [N] number
- "type": one of "interview_invite", "rejection", "offer", "info_request", "confirmation", "other"
- "confidence": 0.0-1.0
- "suggested_status": "interviewing" for interview_invite/offer, "rejected" for rejection, null otherwise
- "summary": one sentence describing what the email is about
- "interview_date": date/time string if an interview is scheduled, null otherwise (e.g. "Friday April 17 at 11:00 AM ET")
- "interview_format": format if mentioned — "phone", "video", "onsite", or null
- "meeting_link": video call URL if present in the body (Zoom/Teams/Meet link), null otherwise
- "contact_name": name of the recruiter/hiring manager if mentioned, null otherwise
- "contact_email": reply-to or sender email address (extract from From header)
- "next_steps": one sentence on what action is needed, null if none

Extract interview_date, meeting_link, and contact_name carefully.
For calendar invites the body may contain iCal fields (DTSTART, LOCATION, ORGANIZER) — parse these.

Emails:
{blocks}

Return ONLY a valid JSON array, no other text."""


def _classify_emails(emails: list, applied_jobs: list) -> list:
    """
    Use Claude Haiku to classify emails in batches of 10.

    emails: list of {"job_id", "company", "subject", "sender", "body", "date"}
    Returns list with added classification + detail fields.
    """
    if not emails:
        return []

    import anthropic
    client = anthropic.Anthropic()

    BATCH = 10
    all_results = []

    for batch_start in range(0, len(emails), BATCH):
        batch = emails[batch_start:batch_start + BATCH]

        blocks = "\n\n".join(
            f'[{i}]\nCompany: {e["company"]}\nFrom: {e["sender"]}\n'
            f'Date: {e.get("date", "")}\nSubject: {e["subject"]}\nBody: {e["body"][:500]}'
            for i, e in enumerate(batch)
        )
        prompt = _CLASSIFY_PROMPT.format(blocks=blocks)

        try:
            resp = client.messages.create(
                model="claude-haiku-4-5-20251001",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            raw = resp.content[0].text.strip()
            raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw, flags=re.S).strip()
            classifications = json.loads(raw)
        except Exception as e:
            print(f"[Gmail] Classification batch {batch_start} failed: {e}", flush=True)
            continue

        for c in classifications:
            idx = c.get("index", -1)
            if 0 <= idx < len(batch):
                all_results.append({**batch[idx], **c})

    return all_results


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

    # Build a lookup: company name (lower) → job (used for matching after fetch)
    company_job_map = {}
    for job in applied_jobs:
        key = job.get("company", "").strip().lower()
        if key:
            company_job_map[key] = job

    if not company_job_map:
        return {"results": [], "scanned": 0, "error": None}

    # Broad keyword search — no company name filter so ALL 65+ companies are covered.
    # Company matching happens in Python after fetching.
    job_keywords = (
        "interview OR invitation OR application OR applied OR position OR "
        "candidate OR hiring OR offer OR unfortunately OR regret OR "
        "\"moving forward\" OR \"next steps\" OR schedule OR assessment OR screening"
    )
    query          = f"({job_keywords}) after:{cutoff}"
    # Separate pass for Google Calendar invites (sent from calendar-notification@google.com)
    calendar_query = f"subject:Invitation after:{cutoff}"

    try:
        messages     = _search_messages(service, query, max_results=75)
        cal_messages = _search_messages(service, calendar_query, max_results=25)
        # Merge, deduplicate by message id
        seen_ids = {m["id"] for m in messages}
        for m in cal_messages:
            if m["id"] not in seen_ids:
                messages.append(m)
                seen_ids.add(m["id"])
    except Exception as e:
        return {"results": [], "scanned": 0, "error": f"Search failed: {e}"}

    if not messages:
        return {"results": [], "scanned": 0, "error": None}

    # Fetch and match emails to jobs
    emails_to_classify = []
    for msg_meta in messages:
        try:
            msg = _get_message(service, msg_meta["id"])
            subject, sender, body, date = _extract_text(msg)

            # Match to a job by company name mention
            matched_job = None
            subject_lower = (subject + " " + body).lower()
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
                    "body":    body,
                    "date":    date,
                    "msg_id":  msg_meta["id"],
                })
        except Exception:
            continue

    classified = _classify_emails(emails_to_classify, applied_jobs)

    # Filter to only actionable results — interview/offer use lower threshold
    # since calendar invites are unambiguous even at lower confidence scores
    _HIGH_VALUE = {"interview_invite", "offer"}
    actionable = [
        r for r in classified
        if r.get("type") != "other" and (
            r.get("confidence", 0) >= 0.5 if r.get("type") in _HIGH_VALUE
            else r.get("confidence", 0) >= 0.6
        )
    ]

    return {
        "results":  actionable,
        "scanned":  len(messages),
        "error":    None,
    }
