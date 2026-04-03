import re
import html
import requests
import xml.etree.ElementTree as ET
from typing import List
from urllib.parse import urlencode
from models.job import Job
from .base import BaseScraper

RSS_URL = "https://www.indeed.com/rss"


class IndeedScraper(BaseScraper):
    """Scrapes Indeed via their public RSS feed."""

    def scrape(self) -> List[Job]:
        params = {
            "q": self._build_query(),
            "l": self.location,
            "limit": min(self.max_results, 25),  # RSS caps at 25
            "sort": "date",
        }
        url = f"{RSS_URL}?{urlencode(params)}"
        headers = {"User-Agent": "Mozilla/5.0 (compatible; job-search-automator/1.0)"}

        try:
            resp = requests.get(url, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[Indeed] Request failed: {e}")
            return []

        try:
            root = ET.fromstring(resp.content)
        except ET.ParseError as e:
            print(f"[Indeed] Failed to parse RSS: {e}")
            return []

        ns = {"dc": "http://purl.org/dc/elements/1.1/"}
        items = root.findall(".//item")
        jobs: List[Job] = []

        for item in items[:self.max_results]:
            title = _text(item, "title")
            link = _text(item, "link")
            description_raw = _text(item, "description")
            description = html.unescape(re.sub(r"<[^>]+>", "", description_raw or "")).strip()
            pub_date = _text(item, "pubDate")
            author = _text(item, "author") or _text(item, "dc:author", ns)

            # Indeed RSS encodes "Job Title - Company - Location" in the title
            company, location = _parse_title_parts(title)

            remote = any(word in (description or "").lower() for word in ("remote", "work from home", "wfh"))

            jobs.append(Job(
                title=title,
                company=company or "Unknown",
                location=location or self.location or "Unknown",
                source="indeed",
                url=link,
                description=description,
                remote=remote,
                posted_date=pub_date,
            ))

        print(f"[Indeed] Found {len(jobs)} jobs.")
        return jobs


def _text(element, tag: str, ns: dict = None) -> str:
    child = element.find(tag, ns) if ns else element.find(tag)
    return (child.text or "").strip() if child is not None else ""


def _parse_title_parts(title: str):
    """Indeed titles are often 'Job Title - Company - Location'."""
    parts = [p.strip() for p in title.split(" - ")]
    if len(parts) >= 3:
        return parts[-2], parts[-1]
    if len(parts) == 2:
        return parts[-1], ""
    return "", ""
