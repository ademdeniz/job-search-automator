# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Jobspresso scraper using their public RSS feed.
https://jobspresso.co/?feed=job_feed
"""

import re
import requests
import xml.etree.ElementTree as ET
from typing import List

from models.job import Job
from .base import BaseScraper

RSS_URL = "https://jobspresso.co/?feed=job_feed"


class JobspressoScraper(BaseScraper):
    """Scrapes Jobspresso remote job board via RSS feed."""

    def scrape(self) -> List[Job]:
        jobs: List[Job] = []

        try:
            resp = requests.get(
                RSS_URL,
                headers={"User-Agent": "job-search-automator/1.0"},
                timeout=15,
            )
            if resp.status_code != 200:
                print(f"[Jobspresso] HTTP {resp.status_code} — skipping.")
                return jobs
            root = ET.fromstring(resp.content)
        except Exception as e:
            print(f"[Jobspresso] Failed to fetch RSS: {e}")
            return jobs

        # Namespaces used in the feed
        ns = {
            "content": "http://purl.org/rss/1.0/modules/content/",
            "job":     "http://joblisting.net/",
        }

        channel = root.find("channel")
        if channel is None:
            return jobs

        for item in channel.findall("item"):
            if len(jobs) >= self.max_results:
                break

            title   = (item.findtext("title") or "").strip()
            url     = (item.findtext("link") or "").strip()
            pub_date = (item.findtext("pubDate") or "").strip()
            company = (
                item.findtext("{https://jobspresso.co}company") or
                item.findtext("{http://purl.org/dc/elements/1.1/}creator") or ""
            ).strip()

            # Description — prefer content:encoded, fall back to description
            raw = (item.findtext("content:encoded", namespaces=ns) or
                   item.findtext("{http://purl.org/rss/1.0/modules/content/}encoded") or
                   item.findtext("description") or "")
            description = re.sub(r"<[^>]+>", " ", raw)
            description = re.sub(r"\s+", " ", description).strip()

            # Title filter
            if not self._title_matches_keywords(title):
                continue

            jobs.append(Job(
                title=title,
                company=company or "Unknown",
                location="Remote",
                source="jobspresso",
                url=url,
                description=description[:8000],
                remote=True,
                posted_date=pub_date,
            ))

        print(f"[Jobspresso] Found {len(jobs)} jobs.")
        return jobs
