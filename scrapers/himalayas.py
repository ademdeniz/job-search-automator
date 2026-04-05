# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Himalayas scraper using the public Himalayas Jobs API.
https://himalayas.app/docs/remote-jobs-api
"""

import re
import requests
from typing import List

from models.job import Job
from .base import BaseScraper

BROWSE_URL = "https://himalayas.app/jobs/api"
PAGE_SIZE  = 20
MAX_PAGES  = 15   # cap at 300 total jobs scanned to avoid hammering the API


class HimalayanScraper(BaseScraper):
    """Scrapes Himalayas remote job board using their public JSON API."""

    def scrape(self) -> List[Job]:
        jobs: List[Job] = []
        offset = 0

        for _ in range(MAX_PAGES):
            if len(jobs) >= self.max_results:
                break
            try:
                resp = requests.get(
                    BROWSE_URL,
                    params={"limit": PAGE_SIZE, "offset": offset},
                    headers={"User-Agent": "job-search-automator/1.0"},
                    timeout=10,
                )
                if resp.status_code == 429:
                    print("[Himalayas] Rate limited — stopping early.")
                    break
                if resp.status_code != 200:
                    break
                data = resp.json()
            except Exception:
                break

            postings = data.get("jobs", [])
            if not postings:
                break

            for post in postings:
                if len(jobs) >= self.max_results:
                    break

                title    = post.get("title", "")
                company  = post.get("companyName", "")
                url      = post.get("applicationLink", "") or post.get("guid", "")
                pub_date = post.get("pubDate", "")

                if not self._title_matches_keywords(title):
                    continue

                if not self._is_recent(pub_date):
                    continue

                # Location / US-only filter
                restrictions = post.get("locationRestrictions", []) or []
                if self.us_remote_only and restrictions:
                    if not any(
                        r.lower() in ("united states", "us", "usa", "worldwide", "anywhere")
                        for r in restrictions
                    ):
                        continue

                location = "Remote"
                if restrictions:
                    location = "Remote — " + ", ".join(restrictions)

                raw_desc = post.get("description", "") or post.get("excerpt", "") or ""
                description = re.sub(r"<[^>]+>", " ", raw_desc)
                description = re.sub(r"\s+", " ", description).strip()

                salary = ""
                min_s = post.get("minSalary")
                max_s = post.get("maxSalary")
                if min_s and max_s:
                    currency = post.get("currency", "USD")
                    salary = f"{currency} {min_s:,} – {max_s:,}"

                jobs.append(Job(
                    title=title,
                    company=company,
                    location=location,
                    source="himalayas",
                    url=url,
                    description=description[:3000],
                    remote=True,
                    posted_date=pub_date,
                    salary=salary or None,
                ))

            if len(postings) < PAGE_SIZE:
                break
            offset += PAGE_SIZE

        print(f"[Himalayas] Found {len(jobs)} jobs.")
        return jobs
