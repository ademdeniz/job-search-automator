"""
Lever ATS scraper using the public Lever postings API.

Many tech companies post jobs via Lever at jobs.lever.co and expose a
public JSON API at api.lever.co — no authentication required.

We maintain a curated list of companies known to hire QA/SDET engineers
and query each one, filtering results by keyword.
"""

import re
import requests
from datetime import datetime, timezone
from typing import List

from models.job import Job
from .base import BaseScraper


def _matches_qa_title(title: str) -> bool:
    """Return True if the title contains a QA/SDET term with proper word boundaries."""
    t = title.lower()
    for term in ("qa", "qe", "qc", "sdet"):
        if re.search(r'\b' + re.escape(term) + r'\b', t):
            return True
    for term in (
        "quality assurance", "quality engineer", "test automation",
        "automation engineer", "automation tester", "test engineer",
        "software tester", "quality analyst", "testing engineer",
        "manual tester", "software quality", "quality control",
        "qc engineer", "test lead", "qa lead",
    ):
        if term in t:
            return True
    return False

API_BASE = "https://api.lever.co/v0/postings/{company}"

# Terms that must appear in the job title — narrower than user keywords to avoid false positives.
QA_TITLE_TERMS = {
    "qa", "qe", "sdet", "quality assurance", "quality engineer",
    "test automation", "automation engineer", "automation tester",
    "test engineer", "software tester", "quality analyst",
    "testing engineer", "manual tester", "software quality",
    "quality control", "qc engineer", "test lead", "qa lead",
}

# Curated list of companies that use Lever and commonly hire QA/SDET.
QA_FRIENDLY_COMPANIES = [
    "netflix", "spotify", "pinterest", "squarespace", "etsy",
    "duolingo", "robinhood", "chime", "affirm", "klarna",
    "toast", "square", "block", "cash-app",
    "lyft", "doordash", "instacart", "grubhub",
    "cloudflare", "fastly", "netlify", "digitalocean",
    "twitch", "discord", "reddit", "tumblr",
    "canva", "invisionapp", "sketch", "webflow",
    "hubspot", "drift", "salesloft", "outreach",
    "zendesk", "servicenow", "freshworks",
    "docker", "rancher", "vmware", "nutanix",
    "pendo", "appcues", "walkme", "whatfix",
    "postman", "stoplight", "swaggerhub",
    "circleci", "travis-ci", "buildkite",
    "sonarqube", "veracode", "checkmarx",
    "new-relic", "dynatrace", "appdynamics",
    "sumo-logic", "logdna", "papertrail",
    "recurly", "chargebee", "paddle", "maxio",
    "benchling", "labvantage", "sapio",
    "toast", "olo", "lightspeed",
    "flexport", "project44", "transfix", "convoy",
    "netsuite", "sage", "epicor", "infor",
    "medallia", "qualtrics", "momentive",
    "sprinklr", "hootsuite", "buffer",
    "contentful", "prismic", "sanity",
    "harness", "spinnaker", "argo",
    "snyk", "lacework", "aquasec",
    "brex", "divvy", "airbase", "spendesk",
    "remote", "deel", "papaya-global",
    "lattice", "15five", "culture-amp", "leapsome",
]


class LeverScraper(BaseScraper):
    """Scrapes Lever ATS boards for QA/SDET roles."""

    def scrape(self) -> List[Job]:
        query_terms = [kw.lower() for kw in self.keywords]
        jobs: List[Job] = []

        for company in QA_FRIENDLY_COMPANIES:
            if len(jobs) >= self.max_results:
                break
            try:
                resp = requests.get(
                    API_BASE.format(company=company),
                    params={"mode": "json"},
                    headers={"User-Agent": "job-search-automator/1.0"},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                postings = resp.json()
                if not isinstance(postings, list):
                    continue
            except Exception:
                continue

            for post in postings:
                if len(jobs) >= self.max_results:
                    break

                title = post.get("text", "")
                categories = post.get("categories", {})
                location = categories.get("location", "") or categories.get("allLocations", "")
                if isinstance(location, list):
                    location = ", ".join(location)

                # Lever returns description as HTML string
                raw = post.get("descriptionPlain", "") or post.get("description", "") or ""
                description = re.sub(r"<[^>]+>", " ", raw).strip()
                description = re.sub(r"\s+", " ", description)

                # Date filter — Lever createdAt is Unix ms
                cutoff = self._cutoff()
                if cutoff is not None:
                    created_ms = post.get("createdAt")
                    try:
                        posted_dt = datetime.fromtimestamp(int(created_ms) / 1000, tz=timezone.utc)
                        if posted_dt < cutoff:
                            continue
                    except (TypeError, ValueError):
                        pass

                # Title must match a QA-specific term with word boundaries
                if not _matches_qa_title(title):
                    continue

                # Location filter
                if self.us_remote_only:
                    if not self._is_us_compatible(location):
                        continue
                elif self.location and self.location.lower() not in ("remote", "anywhere", ""):
                    if self.location.lower() not in location.lower():
                        continue

                remote = "remote" in location.lower() or "remote" in description.lower()

                jobs.append(Job(
                    title=title,
                    company=company.replace("-", " ").title(),
                    location=location or "Unknown",
                    source="lever",
                    url=post.get("hostedUrl", "") or post.get("applyUrl", ""),
                    description=description[:3000],
                    remote=remote,
                    posted_date=str(post.get("createdAt", "")),
                ))

        print(f"[Lever] Found {len(jobs)} jobs.")
        return jobs
