from abc import ABC, abstractmethod
from datetime import datetime, timezone, timedelta
from typing import List, Optional
from models.job import Job


class BaseScraper(ABC):
    """Abstract base for all job board scrapers."""

    def __init__(self, keywords: List[str], location: str = "",
                 max_results: int = 50, days_ago: Optional[int] = None):
        self.keywords = keywords
        self.location = location
        self.max_results = max_results
        self.days_ago = days_ago

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
