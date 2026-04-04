# Copyright (c) 2025 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Indeed job scraper using Playwright (headless Chromium).

Replaces the old RSS-based approach which was unreliable and capped at 25 results.
Playwright renders the full search page and extracts job cards with descriptions.
"""

import re
import html
import time
from typing import List
from urllib.parse import urlencode

from models.job import Job
from .base import BaseScraper

SEARCH_URL = "https://www.indeed.com/jobs"


class IndeedScraper(BaseScraper):
    """Scrapes Indeed job search using a headless Chromium browser."""

    def scrape(self) -> List[Job]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            print("[Indeed] playwright not installed.")
            return []

        jobs: List[Job] = []
        seen_urls = set()

        _fromage = {1: "1", 3: "3", 7: "7"}.get(self.days_ago, "7")
        params = {
            "q": self._build_query(),
            "l": self.location or "Remote",
            "sort": "date",
            "fromage": _fromage,
        }
        url = f"{SEARCH_URL}?{urlencode(params)}"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 900},
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
                time.sleep(2)
            except PWTimeout:
                print("[Indeed] Page load timed out.")
                browser.close()
                return []

            page_num = 0
            while len(jobs) < self.max_results:
                # Scroll to load all cards
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)

                cards = page.query_selector_all("div.job_seen_beacon")
                if not cards:
                    cards = page.query_selector_all("div.cardOutline")
                if not cards:
                    break

                for card in cards:
                    if len(jobs) >= self.max_results:
                        break
                    job = _parse_card(card)
                    if job and job.url and job.url not in seen_urls:
                        seen_urls.add(job.url)
                        jobs.append(job)

                # Try next page
                try:
                    next_btn = page.query_selector("a[data-testid='pagination-page-next']")
                    if not next_btn or not next_btn.is_visible():
                        break
                    next_btn.click()
                    time.sleep(2.5)
                    page_num += 1
                    if page_num >= 4:  # max 4 pages
                        break
                except Exception:
                    break

            browser.close()

        print(f"[Indeed] Found {len(jobs)} jobs.")
        return jobs


def _parse_card(card) -> Job:
    try:
        title_el    = card.query_selector("h2.jobTitle span[title]") or card.query_selector("h2.jobTitle span")
        company_el  = card.query_selector("span[data-testid='company-name']") or card.query_selector(".companyName")
        location_el = card.query_selector("div[data-testid='text-location']") or card.query_selector(".companyLocation")
        link_el     = card.query_selector("a.jcs-JobTitle") or card.query_selector("h2.jobTitle a")
        salary_el   = card.query_selector("div[data-testid='attribute_snippet_testid']")
        snippet_el  = card.query_selector("div.job-snippet") or card.query_selector("div[data-testid='jobsnippet_footer']")

        title    = _text(title_el)
        company  = _text(company_el)
        location = _text(location_el)
        salary   = _text(salary_el) if salary_el else None
        snippet  = _text(snippet_el) if snippet_el else ""

        href = link_el.get_attribute("href") if link_el else ""
        if href and not href.startswith("http"):
            href = "https://www.indeed.com" + href
        # Strip tracking params — keep just the base URL
        href = href.split("&")[0] if "&" in href else href

        if not title or not href:
            return None

        remote = any(w in (location + snippet).lower() for w in ("remote", "work from home", "wfh"))

        return Job(
            title=title,
            company=company or "Unknown",
            location=location or "Unknown",
            source="indeed",
            url=href,
            description=snippet,
            salary=salary,
            remote=remote,
        )
    except Exception:
        return None


def _text(el) -> str:
    if el is None:
        return ""
    return (el.inner_text() or "").strip()
