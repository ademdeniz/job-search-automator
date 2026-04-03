"""
WeWorkRemotely scraper via their public RSS feeds.

WWR has dedicated category feeds — we hit the programming/devops
feed which covers QA, SDET, and automation roles.
"""

import html
import re
import requests
import xml.etree.ElementTree as ET
from email.utils import parsedate_to_datetime
from typing import List
from models.job import Job
from .base import BaseScraper

# Programming/dev/QA jobs only (narrower than the all-jobs feed)
RSS_URL = "https://weworkremotely.com/categories/remote-programming-jobs.rss"

# QA-specific terms — "test" alone matches too many non-QA roles
QA_TITLE_TERMS = {
    "qa", "qe", "sdet", "quality assurance", "quality engineer",
    "test automation", "automation engineer", "automation tester",
    "test engineer", "software tester", "quality analyst",
    "testing engineer", "manual tester", "software quality",
    "quality control", "qc engineer", "test lead", "qa lead",
}


class WeWorkRemotelyScraper(BaseScraper):
    """Scrapes WeWorkRemotely via public RSS feed."""

    def scrape(self) -> List[Job]:
        headers = {"User-Agent": "job-search-automator/1.0"}
        try:
            resp = requests.get(RSS_URL, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[WWR] Request failed: {e}")
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            print(f"[WWR] Failed to parse RSS: {e}")
            return []

        items = root.findall(".//item")
        query_terms = [kw.lower() for kw in self.keywords]
        jobs: List[Job] = []

        for item in items:
            if len(jobs) >= self.max_results:
                break

            title_raw   = _text(item, "title")
            link        = _text(item, "link")
            region      = _text(item, "region")
            description_raw = _text(item, "description")
            pub_date    = _text(item, "pubDate")

            # WWR title format: "Company: Job Title"
            if ": " in title_raw:
                company, title = title_raw.split(": ", 1)
            else:
                company, title = "Unknown", title_raw

            description = html.unescape(
                re.sub(r"<[^>]+>", "", description_raw or "")
            ).strip()

            # Date filter
            cutoff = self._cutoff()
            if cutoff is not None and pub_date:
                try:
                    posted_dt = parsedate_to_datetime(pub_date)
                    if posted_dt < cutoff:
                        continue
                except Exception:
                    pass

            # Must match a QA-specific term in the title (broad keyword match is too noisy)
            if not any(t in title.lower() for t in QA_TITLE_TERMS):
                continue

            jobs.append(Job(
                title=title.strip(),
                company=company.strip(),
                location=region or "Remote",
                source="weworkremotely",
                url=link,
                description=description,
                remote=True,
                posted_date=pub_date,
            ))

        print(f"[WWR] Found {len(jobs)} matching jobs.")
        return jobs


def _text(element, tag: str) -> str:
    child = element.find(tag)
    return (child.text or "").strip() if child is not None else ""
