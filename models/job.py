from dataclasses import dataclass, field
from datetime import datetime
from typing import Optional


@dataclass
class Job:
    title: str
    company: str
    location: str
    source: str  # linkedin, indeed, simplify, remoteok
    url: str
    description: Optional[str] = None
    salary: Optional[str] = None
    job_type: Optional[str] = None       # full-time, contract, etc.
    remote: Optional[bool] = None
    posted_date: Optional[str] = None
    scraped_at: str = field(default_factory=lambda: datetime.now().isoformat())
    status: str = "new"                  # new, applied, rejected, interviewing, offer
