"""
LinkedIn job scraper using Playwright (headless Chromium).

Replaces the old regex-based approach which broke whenever LinkedIn
changed their HTML structure. Playwright renders the full page so
we get reliable, structured data from the guest-accessible job search.
"""

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

        params = {
            "keywords": self._build_query(),
            "location": self.location or "Worldwide",
            "f_TPR": "r604800",   # posted in last 7 days
            "position": 1,
            "pageNum": 0,
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


def fetch_descriptions(jobs: list, on_progress=None) -> List[tuple]:
    """
    Visit each job's LinkedIn URL with a headless browser and extract
    the full job description.

    Returns list of (job_id, description_text).
    on_progress(current, total, job) called after each fetch.
    """
    try:
        from playwright.sync_api import sync_playwright, TimeoutError as PWTimeout
    except ImportError:
        print("[LinkedIn] playwright not installed.")
        return []

    results = []
    total = len(jobs)

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

        for i, job in enumerate(jobs, 1):
            desc = ""
            print(f"  [{i:>3}/{total}] Fetching: {job['title'][:50]}", flush=True)
            try:
                page.goto(job["url"], wait_until="domcontentloaded", timeout=20000)
                time.sleep(1)

                # Expand "Show more" if present
                try:
                    btn = page.query_selector("button.show-more-less-html__button--more")
                    if btn and btn.is_visible():
                        btn.click()
                        time.sleep(0.5)
                except Exception:
                    pass

                # Try multiple selectors LinkedIn uses for job descriptions
                for selector in [
                    ".show-more-less-html__markup",
                    ".description__text",
                    ".job-details-jobs-unified-top-card__job-insight",
                    "div[class*='description']",
                ]:
                    el = page.query_selector(selector)
                    if el:
                        desc = (el.inner_text() or "").strip()
                        if len(desc) > 100:
                            break

            except PWTimeout:
                pass
            except Exception as e:
                print(f"  [fetch] Error on job {job['id']}: {e}")

            status = f"{len(desc)} chars" if desc else "no description"
            print(f"           → {status}", flush=True)
            results.append((job["id"], desc))
            if on_progress:
                on_progress(i, total, job, desc)

            time.sleep(1.2)  # polite delay between requests

        browser.close()

    return results


def _text(el) -> str:
    if el is None:
        return ""
    return (el.inner_text() or "").strip()
