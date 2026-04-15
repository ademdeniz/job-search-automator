# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
LinkedIn job scraper using Playwright (headless Chromium).

Replaces the old regex-based approach which broke whenever LinkedIn
changed their HTML structure. Playwright renders the full page so
we get reliable, structured data from the guest-accessible job search.
"""

import random
import time
from typing import List
from urllib.parse import urlencode

from models.job import Job
from .base import BaseScraper


SEARCH_URL = "https://www.linkedin.com/jobs/search/"


class LinkedInScraper(BaseScraper):
    """Scrapes LinkedIn job search using a headless Chromium browser."""

    def scrape(self) -> List[Job]:
        try:
            from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
        except ImportError:
            print("[LinkedIn] playwright not installed. Run: pip3 install playwright && python3 -m playwright install chromium")
            return []

        jobs: List[Job] = []

        _tpr = {1: "r86400", 3: "r259200", 7: "r604800"}.get(self.days_ago, "r604800")
        loc = self.location or "Remote"
        is_remote_search = loc.lower() in ("remote", "anywhere", "")
        params = {
            "keywords": self._build_query(),
            "location": "United States" if is_remote_search else loc,
            "f_TPR": _tpr,
            "f_WT": "2" if is_remote_search else "",   # Work type: Remote
            "position": 1,
            "pageNum": 0,
        }
        if not is_remote_search:
            del params["f_WT"]
        url = f"{SEARCH_URL}?{urlencode(params)}"

        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            context = browser.new_context(
                user_agent=(
                    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                    "AppleWebKit/537.36 (KHTML, like Gecko) "
                    "Chrome/120.0.0.0 Safari/537.36"
                ),
                viewport={"width": 1280, "height": 800},
            )
            page = context.new_page()

            try:
                page.goto(url, wait_until="domcontentloaded", timeout=30000)
            except PWTimeout:
                print("[LinkedIn] Page load timed out.")
                browser.close()
                return []

            # LinkedIn lazy-loads cards — scroll to trigger them
            for _ in range(3):
                page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                time.sleep(1.5)

            # Collect cards, clicking "Show more" to paginate
            while len(jobs) < self.max_results:
                cards = page.query_selector_all("ul.jobs-search__results-list > li")
                if not cards:
                    cards = page.query_selector_all(".base-card")

                for card in cards:
                    if len(jobs) >= self.max_results:
                        break
                    job = _parse_card(card)
                    if job:
                        jobs.append(job)

                # Try to load more results
                try:
                    see_more = page.query_selector("button.infinite-scroller__show-more-button")
                    if see_more and see_more.is_visible():
                        see_more.click()
                        time.sleep(2)
                        page.evaluate("window.scrollTo(0, document.body.scrollHeight)")
                        time.sleep(1.5)
                    else:
                        break
                except Exception:
                    break

            browser.close()

        # Deduplicate by URL within this batch
        seen, unique = set(), []
        for j in jobs:
            if j.url not in seen:
                seen.add(j.url)
                unique.append(j)

        print(f"[LinkedIn] Found {len(unique)} jobs.")
        return unique


def _parse_card(card) -> Job:
    """Extract a Job from a single LinkedIn job card element."""
    try:
        title_el    = card.query_selector("h3.base-search-card__title")
        company_el  = card.query_selector("h4.base-search-card__subtitle")
        location_el = card.query_selector("span.job-search-card__location")
        link_el     = card.query_selector("a.base-card__full-link")
        date_el     = card.query_selector("time")

        title    = _text(title_el)
        company  = _text(company_el)
        location = _text(location_el)
        url      = link_el.get_attribute("href").split("?")[0] if link_el else ""
        date     = date_el.get_attribute("datetime") if date_el else ""

        if not title or not url:
            return None

        remote = "remote" in location.lower()

        return Job(
            title=title,
            company=company or "Unknown",
            location=location or "Unknown",
            source="linkedin",
            url=url,
            remote=remote,
            posted_date=date,
        )
    except Exception:
        return None


_SELECTORS = {
    "linkedin": [
        ".show-more-less-html__markup",
        ".description__text",
        "div[class*='description']",
    ],
    "indeed": [
        "#jobDescriptionText",
        "div[class*='jobsearch-jobDescriptionText']",
        "div[data-testid='jobsearch-JobComponent-description']",
    ],
    "dice": [
        "div[data-testid='jobDescription']",
        ".job-description",
        "div[class*='description']",
    ],
}
_SUPPORTED_SOURCES = set(_SELECTORS.keys())


_USER_AGENTS = [
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/123.0.0.0 Safari/537.36",
    "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
]

# Stealth script: hide headless browser signals that bot-detection checks
_STEALTH_JS = """
Object.defineProperty(navigator, 'webdriver', {get: () => undefined});
Object.defineProperty(navigator, 'plugins', {get: () => [1, 2, 3, 4, 5]});
Object.defineProperty(navigator, 'languages', {get: () => ['en-US', 'en']});
window.chrome = {runtime: {}};
Object.defineProperty(navigator, 'permissions', {
    get: () => ({query: () => Promise.resolve({state: 'granted'})}),
});
"""


def fetch_descriptions(jobs: list, on_progress=None) -> List[tuple]:
    """
    Visit each job's URL with a headless browser and extract the full description.
    Supports LinkedIn, Indeed, and Dice. Other sources are skipped.

    Returns list of (job_id, description_text).
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("[Fetch] playwright not installed.")
        return []

    results = []
    total = len(jobs)

    with sync_playwright() as pw:
        browser = pw.chromium.launch(
            headless=True,
            args=[
                "--disable-blink-features=AutomationControlled",
                "--no-sandbox",
                "--disable-dev-shm-usage",
                "--disable-infobars",
                "--window-size=1280,800",
            ],
        )

        ua = random.choice(_USER_AGENTS)
        context = browser.new_context(
            user_agent=ua,
            viewport={"width": 1280, "height": 800},
            locale="en-US",
            timezone_id="America/New_York",
            extra_http_headers={
                "Accept-Language": "en-US,en;q=0.9",
                "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,image/avif,image/webp,*/*;q=0.8",
                "sec-ch-ua": '"Chromium";v="124", "Google Chrome";v="124", "Not-A.Brand";v="99"',
                "sec-ch-ua-mobile": "?0",
                "sec-ch-ua-platform": '"macOS"',
                "Upgrade-Insecure-Requests": "1",
            },
        )

        # Inject stealth script on every new page
        context.add_init_script(_STEALTH_JS)
        page = context.new_page()

        for i, job in enumerate(jobs, 1):
            source = job.get("source", "").lower()
            desc = ""
            print(f"  [{i:>3}/{total}] [{source}] Fetching: {job['title'][:45]}", flush=True)

            if source not in _SUPPORTED_SOURCES:
                print(f"           → skipped (source not supported)", flush=True)
                results.append((job["id"], desc))
                if on_progress:
                    on_progress(i, total, job, desc)
                continue

            try:
                page.goto(job["url"], wait_until="domcontentloaded", timeout=25000)
                time.sleep(random.uniform(1.5, 3.0))

                # Expand "Show more" buttons (LinkedIn + Indeed)
                for btn_sel in [
                    "button.show-more-less-html__button--more",
                    "button[id*='indeed-read-more']",
                    "button[data-testid='read-more-button']",
                ]:
                    try:
                        btn = page.query_selector(btn_sel)
                        if btn and btn.is_visible():
                            btn.click()
                            time.sleep(random.uniform(0.4, 0.9))
                    except Exception:
                        pass

                for selector in _SELECTORS.get(source, []):
                    el = page.query_selector(selector)
                    if el:
                        desc = (el.inner_text() or "").strip()
                        if len(desc) > 100:
                            break

            except PWTimeout:
                print(f"           → timeout", flush=True)
            except Exception as e:
                print(f"  [fetch] Error on job {job['id']}: {e}")

            status = f"{len(desc)} chars" if desc else "no description found"
            print(f"           → {status}", flush=True)
            results.append((job["id"], desc))
            if on_progress:
                on_progress(i, total, job, desc)

            time.sleep(random.uniform(2.0, 4.5))

        browser.close()

    return results


def _text(el) -> str:
    if el is None:
        return ""
    return (el.inner_text() or "").strip()
