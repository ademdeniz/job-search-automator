"""
Dice.com job scraper using Playwright (headless Chromium).

Dice is one of the best US boards for SDET / QA automation / test engineering.
Cards are rendered as React web components — we locate job links and extract
surrounding text content.
"""

import re
import time
from typing import List
from urllib.parse import urlencode

from models.job import Job
from .base import BaseScraper

SEARCH_URL = "https://www.dice.com/jobs"


class DiceScraper(BaseScraper):
    """Scrapes Dice.com using a headless Chromium browser."""

    def scrape(self) -> List[Job]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            print("[Dice] playwright not installed.")
            return []

        jobs: List[Job] = []
        seen_urls = set()

        _posted = {1: "ONE", 3: "THREE", 7: "SEVEN"}.get(self.days_ago, "SEVEN")
        params = {
            "q": self._build_query(),
            "filters.postedDate": _posted,
            "language": "en",
        }
        if self.location and self.location.lower() not in ("remote", "anywhere", ""):
            params["location"] = self.location
        else:
            params["filters.workFromHome"] = "TRUE"

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
                page.goto(url, wait_until="networkidle", timeout=30000)
                time.sleep(3)
            except PWTimeout:
                print("[Dice] Page load timed out.")
                browser.close()
                return []

            page_num = 1
            while len(jobs) < self.max_results:
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(2)

                # Each unique job-detail link = one job card
                links = page.query_selector_all("a[href*='/job-detail']")
                unique_links = {}
                for link in links:
                    href = link.get_attribute("href") or ""
                    if href and href not in unique_links:
                        unique_links[href] = link

                for href, link in unique_links.items():
                    if len(jobs) >= self.max_results:
                        break
                    if href in seen_urls:
                        continue
                    seen_urls.add(href)

                    job = _parse_from_link(page, link, href)
                    if job:
                        jobs.append(job)

                # Next page button
                try:
                    next_btn = page.query_selector("button[aria-label='Next Page']") or \
                               page.query_selector("li.pagination-next a")
                    if not next_btn or not next_btn.is_visible():
                        break
                    next_btn.click()
                    time.sleep(3)
                    page_num += 1
                    if page_num > 5:
                        break
                except Exception:
                    break

            browser.close()

        print(f"[Dice] Found {len(jobs)} jobs.")
        return jobs


def _parse_from_link(page, link, href: str) -> Job:
    try:
        # Walk up the DOM to find the card container that holds all job info
        card_text = page.evaluate("""el => {
            let node = el;
            for (let i = 0; i < 8; i++) {
                node = node.parentElement;
                if (!node) break;
                if (node.innerText && node.innerText.length > 100) return node.innerText;
            }
            return el.closest('dhi-search-card')?.innerText || '';
        }""", link)

        if not card_text:
            return None

        # Dice card structure (observed):
        # line 0: Company name
        # line 1: "Easy Apply" (optional badge — skip)
        # line 2: Job title
        # line 3: Location
        # line 4: "•"
        # line 5: "Today" / "X days ago"
        # line 6+: Description snippet
        SKIP = {"easy apply", "•", "today", "new", "promoted"}

        lines = [l.strip() for l in card_text.strip().splitlines() if l.strip()]
        meaningful = [l for l in lines if l.lower() not in SKIP and not l.lower().startswith("days ago")]

        company  = meaningful[0] if len(meaningful) > 0 else ""
        title    = meaningful[1] if len(meaningful) > 1 else ""
        location = meaningful[2] if len(meaningful) > 2 else ""
        snippet  = meaningful[3] if len(meaningful) > 3 else ""

        # If title looks like a badge/CTA, it's mis-parsed — skip
        if not title or title.lower() in ("apply now", "easy apply", "new", "promoted"):
            return None

        if not title:
            return None

        remote = "remote" in (location + snippet).lower()

        return Job(
            title=title,
            company=company or "Unknown",
            location=location or ("Remote" if remote else "Unknown"),
            source="dice",
            url=href if href.startswith("http") else "https://www.dice.com" + href,
            description=snippet,
            remote=remote,
        )
    except Exception:
        return None
