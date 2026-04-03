from abc import ABC, abstractmethod
from typing import List
from models.job import Job


class BaseScraper(ABC):
    """Abstract base for all job board scrapers."""

    def __init__(self, keywords: List[str], location: str = "", max_results: int = 50):
        self.keywords = keywords
        self.location = location
        self.max_results = max_results

    @abstractmethod
    def scrape(self) -> List[Job]:
        """Fetch jobs and return a list of Job objects."""
        ...

    def _build_query(self) -> str:
        return " ".join(self.keywords)
