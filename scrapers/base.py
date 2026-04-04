# Copyright (c) 2025 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
import re as _re
from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from models.job import Job

# Non-US place names — if any appear in a job's location we exclude it in US-only mode.
_NON_US_PLACES = {
    "ireland", "uk", "united kingdom", "germany", "france", "netherlands",
    "canada", "australia", "india", "spain", "poland", "portugal",
    "singapore", "brazil", "mexico", "argentina", "israel", "sweden",
    "denmark", "norway", "finland", "switzerland", "austria", "belgium",
    "dublin", "london", "berlin", "amsterdam", "toronto", "sydney",
    "bangalore", "bengaluru", "tel aviv", "warsaw", "lisbon", "madrid",
    "stockholm", "copenhagen", "oslo", "zurich", "brussels", "vienna",
    "paris", "milan", "rome", "prague", "budapest", "bucharest",
}


class BaseScraper(ABC):
    """Abstract base for all job board scrapers."""

    def __init__(self, keywords: List[str], location: str = "",
                 max_results: int = 50, days_ago: Optional[int] = None):
        self.keywords = keywords
        self.location = location
        self.max_results = max_results
        self.days_ago = days_ago

    @property
    def us_remote_only(self) -> bool:
        """True when the user wants remote jobs limited to US only."""
        return self.location.lower().strip() in ("remote us", "us remote")

    def _is_us_compatible(self, location: str) -> bool:
        """Return True if the location is blank, generic remote, or US-based."""
        loc = location.lower().strip()
        # Blank or generic — no specific country → include
        if not loc or loc in {"remote", "anywhere", "worldwide", "global", "unknown", ""}:
            return True
        # Explicit non-US place → exclude
        if any(place in loc for place in _NON_US_PLACES):
            return False
        # Explicit US indicators → include
        if "united states" in loc or "usa" in loc:
            return True
        # Word-boundary " us" check (e.g. "Remote, US")
        if _re.search(r'us', loc):
            return True
        # Ambiguous (could be a US city with no country) → include
        return True

    @abstractmethod
    def scrape(self) -> List[Job]:
        """Fetch jobs and return a list of Job objects."""
        ...

    def _build_query(self) -> str:
        return " ".join(self.keywords)

    def _cutoff(self) -> Optional[datetime]:
        """UTC cutoff datetime based on days_ago, or None for no filter."""
        if not self.days_ago:
            return None
        return datetime.now(timezone.utc) - timedelta(days=self.days_ago)

    def _parse_iso(self, date_str: str) -> Optional[datetime]:
        """Parse an ISO-8601 date string to an aware UTC datetime."""
        if not date_str:
            return None
        try:
            s = date_str.rstrip("Z")
            dt = datetime.fromisoformat(s)
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            return dt
        except Exception:
            return None

    def _is_recent(self, date_str: str) -> bool:
        """Return True if the date is within days_ago, or if no filter is set."""
        cutoff = self._cutoff()
        if cutoff is None:
            return True
        dt = self._parse_iso(date_str)
        if dt is None:
            return True   # can't parse → include it
        return dt >= cutoff
