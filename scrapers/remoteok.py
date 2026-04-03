import time
import requests
from typing import List
from models.job import Job
from .base import BaseScraper

API_URL = "https://remoteok.com/api"


class RemoteOKScraper(BaseScraper):
    """Scrapes RemoteOK via their public JSON API."""

    def scrape(self) -> List[Job]:
        headers = {"User-Agent": "job-search-automator/1.0"}
        try:
            resp = requests.get(API_URL, headers=headers, timeout=15)
            resp.raise_for_status()
        except requests.RequestException as e:
            print(f"[RemoteOK] Request failed: {e}")
            return []

        data = resp.json()
        # First element is metadata, skip it
        postings = [p for p in data if isinstance(p, dict) and "id" in p]

        query_terms = [kw.lower() for kw in self.keywords]
        jobs: List[Job] = []

        for post in postings:
            if len(jobs) >= self.max_results:
                break

            # Match against tags, position, and description
            searchable = " ".join([
                post.get("position", ""),
                post.get("description", ""),
                " ".join(post.get("tags", [])),
            ]).lower()

            if not any(term in searchable for term in query_terms):
                continue

            # Location filter (RemoteOK is remote-only, but check if user wants specific region)
            loc_filter = self.location.lower()
            if loc_filter and loc_filter not in ("remote", "anywhere", ""):
                loc_field = (post.get("location") or "").lower()
                if loc_filter not in loc_field:
                    continue

            salary = None
            sal_min = post.get("salary_min")
            sal_max = post.get("salary_max")
            if sal_min or sal_max:
                salary = f"${sal_min or '?'}–${sal_max or '?'}"

            jobs.append(Job(
                title=post.get("position", "Unknown"),
                company=post.get("company", "Unknown"),
                location=post.get("location") or "Remote",
                source="remoteok",
                url=post.get("url", ""),
                description=post.get("description", ""),
                salary=salary,
                job_type="full-time",
                remote=True,
                posted_date=post.get("date", ""),
            ))

        print(f"[RemoteOK] Found {len(jobs)} matching jobs.")
        return jobs
