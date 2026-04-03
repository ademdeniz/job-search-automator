import re
import html
import time
import requests
from typing import List
from urllib.parse import urlencode
from models.job import Job
from .base import BaseScraper

SEARCH_URL = "https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search"


class LinkedInScraper(BaseScraper):
    """
    Scrapes LinkedIn's unauthenticated guest job search API.
    Returns HTML fragments — we parse them with regex to avoid a heavy
    dependency on BeautifulSoup (add it if you want richer parsing).
    """

    def scrape(self) -> List[Job]:
        jobs: List[Job] = []
        start = 0
        batch = 25

        while len(jobs) < self.max_results:
            params = {
                "keywords": self._build_query(),
                "location": self.location,
                "start": start,
                "count": batch,
                "f_TPR": "r86400",   # posted in last 24 h
            }
            url = f"{SEARCH_URL}?{urlencode(params)}"
            headers = {
                "User-Agent": (
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
            }

            try:
                resp = requests.get(url, headers=headers, timeout=15)
                resp.raise_for_status()
            except requests.RequestException as e:
                print(f"[LinkedIn] Request failed (start={start}): {e}")
                break

            body = resp.text
            if not body.strip():
                break  # no more results

            batch_jobs = _parse_linkedin_html(body)
            if not batch_jobs:
                break

            jobs.extend(batch_jobs)
            start += batch
            time.sleep(1)  # be polite

        jobs = jobs[: self.max_results]
        print(f"[LinkedIn] Found {len(jobs)} jobs.")
        return jobs


# ---------------------------------------------------------------------------
# Minimal HTML parser using regex (works on LinkedIn's guest API fragments)
# ---------------------------------------------------------------------------

_CARD_RE = re.compile(
    r'<li[^>]*class="[^"]*result-card[^"]*"[^>]*>(.*?)</li>',
    re.DOTALL,
)
_TITLE_RE = re.compile(r'class="[^"]*job-result-card__title[^"]*"[^>]*>([^<]+)<', re.DOTALL)
_COMPANY_RE = re.compile(r'class="[^"]*job-result-card__subtitle[^"]*"[^>]*>([^<]+)<', re.DOTALL)
_LOCATION_RE = re.compile(r'class="[^"]*job-result-card__location[^"]*"[^>]*>([^<]+)<', re.DOTALL)
_LINK_RE = re.compile(r'href="(https://www\.linkedin\.com/jobs/view/[^"?]+)', re.DOTALL)
_DATE_RE = re.compile(r'<time[^>]*datetime="([^"]+)"', re.DOTALL)


def _parse_linkedin_html(body: str) -> List[Job]:
    jobs = []
    for card_match in _CARD_RE.finditer(body):
        card = card_match.group(1)
        title = _first(re.search(_TITLE_RE, card))
        company = _first(re.search(_COMPANY_RE, card))
        location = _first(re.search(_LOCATION_RE, card))
        link = _first(re.search(_LINK_RE, card))
        date = _first(re.search(_DATE_RE, card))

        if not title or not link:
            continue

        remote = "remote" in (location or "").lower()

        jobs.append(Job(
            title=html.unescape(title.strip()),
            company=html.unescape(company.strip()) if company else "Unknown",
            location=html.unescape(location.strip()) if location else "Unknown",
            source="linkedin",
            url=link,
            remote=remote,
            posted_date=date,
        ))

    return jobs


def _first(match) -> str:
    if match is None:
        return ""
    return match.group(1) if match.lastindex else ""
