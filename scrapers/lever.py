# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Lever ATS scraper using the public Lever postings API.

Many tech companies post jobs via Lever at jobs.lever.co and expose a
public JSON API at api.lever.co — no authentication required.

We maintain a curated list of tech companies and filter job titles against
the user's own search keywords, so this works for any role or field.
"""

import re
import requests
from datetime import datetime, timezone
from typing import List

from models.job import Job
from .base import BaseScraper

API_BASE = "https://api.lever.co/v0/postings/{company}"

# Curated list of tech companies that use Lever.
COMPANIES = [
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
    "olo", "lightspeed",
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
    """Scrapes Lever ATS boards, filtering by user keywords."""

    def scrape(self) -> List[Job]:
        jobs: List[Job] = []

        for company in COMPANIES:
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

                # Filter on title using the user's own keywords (field-agnostic).
                if not self._title_matches_keywords(title):
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
                    description=description[:8000],
                    remote=remote,
                    posted_date=str(post.get("createdAt", "")),
                ))

        print(f"[Lever] Found {len(jobs)} jobs.")
        return jobs
