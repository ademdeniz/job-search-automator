# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Greenhouse ATS scraper using the public Greenhouse boards API.

Many tech companies post jobs via Greenhouse and expose a public JSON API
at boards-api.greenhouse.io — no authentication required.

We maintain a curated list of tech companies and filter job titles against
the user's own search keywords, so this works for any role or field.
"""

import re
import requests
from typing import List

from models.job import Job
from .base import BaseScraper

API_BASE = "https://boards-api.greenhouse.io/v1/boards/{company}/jobs"

# Curated list of tech companies that use Greenhouse.
COMPANIES = [
    "anthropic", "stripe", "shopify", "airbnb", "dropbox", "zendesk",
    "datadog", "pagerduty", "twilio", "figma", "notion", "linear",
    "vercel", "supabase", "retool", "brex", "ramp", "scale",
    "benchling", "carta", "lattice", "rippling", "gusto",
    "plaid", "checkr", "mercury", "deel", "remote", "loom",
    "miro", "asana", "airtable", "segment", "mixpanel",
    "amplitude", "heap", "posthog", "launchdarkly",
    "sentry", "grafana", "dbtlabs", "airbyte", "fivetran",
    "stytch", "clerk", "auth0", "okta", "crowdstrike",
    "snyk", "lacework", "orca", "wiz", "huntress",
    "gitlab", "hashicorp", "confluent", "cockroachdb",
    "mongodb", "redis", "elastic", "dremio",
    "productboard", "pendo", "gainsight", "fullstory",
    "sendgrid", "mailchimp", "klaviyo", "iterable",
    "intercom", "freshworks", "helpscout", "front",
    "greenhouse", "lever", "workday", "bamboohr",
    "navan", "expensify",
    "faire", "shipbob", "flexport", "project44",
    "duolingo", "coursera", "instructure", "kahoot",
    "calm", "headspace", "hims", "ro", "tempus",
    "veeva", "medidata", "flatiron", "omada",
]


class GreenhouseScraper(BaseScraper):
    """Scrapes Greenhouse ATS boards, filtering by user keywords."""

    def scrape(self) -> List[Job]:
        jobs: List[Job] = []

        for company in COMPANIES:
            if len(jobs) >= self.max_results:
                break
            try:
                resp = requests.get(
                    API_BASE.format(company=company),
                    params={"content": "true"},
                    headers={"User-Agent": "job-search-automator/1.0"},
                    timeout=10,
                )
                if resp.status_code != 200:
                    continue
                data = resp.json()
            except Exception:
                continue

            for post in data.get("jobs", []):
                if len(jobs) >= self.max_results:
                    break

                title = post.get("title", "")

                # Filter on title using the user's own keywords (field-agnostic).
                if not self._title_matches_keywords(title):
                    continue

                # Date filter
                if not self._is_recent(post.get("updated_at", "")):
                    continue

                content = post.get("content", "") or ""
                import html as html_module
                content = html_module.unescape(content)
                description = re.sub(r"<[^>]+>", " ", content).strip()
                description = re.sub(r"\s+", " ", description)

                location_data = post.get("location", {})
                location = location_data.get("name", "") if location_data else ""

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
                    source="greenhouse",
                    url=post.get("absolute_url", ""),
                    description=description[:3000],
                    remote=remote,
                    posted_date=post.get("updated_at", ""),
                ))

        print(f"[Greenhouse] Found {len(jobs)} jobs.")
        return jobs
