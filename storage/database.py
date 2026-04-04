import sqlite3
import os
from typing import List, Optional
from models.job import Job

DB_PATH = os.path.join(os.path.dirname(__file__), "..", "jobs.db")


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_connection()
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            title        TEXT NOT NULL,
            company      TEXT NOT NULL,
            location     TEXT,
            source       TEXT,
            url          TEXT UNIQUE,
            description  TEXT,
            salary       TEXT,
            job_type     TEXT,
            remote       INTEGER,
            posted_date  TEXT,
            scraped_at   TEXT,
            status       TEXT DEFAULT 'new',
            score        INTEGER,
            score_reason TEXT,
            scored_at    TEXT
        )
    """)
    # Migrate existing DBs that pre-date the score columns
    for col, definition in [("score", "INTEGER"), ("score_reason", "TEXT"), ("scored_at", "TEXT")]:
        try:
            conn.execute(f"ALTER TABLE jobs ADD COLUMN {col} {definition}")
        except Exception:
            pass  # column already exists
    conn.commit()
    conn.close()
    print("[DB] Database initialised.")


def save_jobs(jobs: List[Job]) -> int:
    """Insert jobs, skip duplicates (by URL). Returns count of newly inserted."""
    conn = get_connection()
    inserted = 0
    for job in jobs:
        try:
            conn.execute("""
                INSERT INTO jobs
                    (title, company, location, source, url, description,
                     salary, job_type, remote, posted_date, scraped_at, status)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?)
            """, (
                job.title, job.company, job.location, job.source, job.url,
                job.description, job.salary, job.job_type,
                1 if job.remote else 0,
                job.posted_date, job.scraped_at, job.status,
            ))
            inserted += 1
        except sqlite3.IntegrityError:
            pass  # duplicate URL — skip
    conn.commit()
    conn.close()
    return inserted


def update_status(job_id: int, status: str):
    conn = get_connection()
    conn.execute("UPDATE jobs SET status=? WHERE id=?", (status, job_id))
    conn.commit()
    conn.close()


def get_job_by_id(job_id: int) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute("SELECT * FROM jobs WHERE id=?", (job_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_jobs(status: Optional[str] = None, remote: Optional[bool] = None,
                 source: Optional[str] = None, keyword: Optional[str] = None) -> List[dict]:
    conn = get_connection()
    clauses, params = [], []
    if status:
        clauses.append("status=?"); params.append(status)
    if remote is not None:
        clauses.append("remote=?"); params.append(1 if remote else 0)
    if source:
        clauses.append("source=?"); params.append(source)
    if keyword:
        pat = f"%{keyword}%"
        clauses.append("(title LIKE ? OR company LIKE ? OR description LIKE ?)")
        params.extend([pat, pat, pat])
    where = ("WHERE " + " AND ".join(clauses)) if clauses else ""
    rows = conn.execute(f"SELECT * FROM jobs {where} ORDER BY scraped_at DESC", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def save_score(job_id: int, score: int, reason: str):
    from datetime import datetime
    conn = get_connection()
    conn.execute(
        "UPDATE jobs SET score=?, score_reason=?, scored_at=? WHERE id=?",
        (score, reason, datetime.now().isoformat(), job_id),
    )
    conn.commit()
    conn.close()


def update_description(job_id: int, description: str):
    conn = get_connection()
    conn.execute("UPDATE jobs SET description=? WHERE id=?", (description, job_id))
    conn.commit()
    conn.close()


def get_jobs_without_description(source: Optional[str] = None) -> List[dict]:
    conn = get_connection()
    clauses = ["(description IS NULL OR description = '')"]
    params = []
    if source:
        clauses.append("source=?")
        params.append(source)
    where = "WHERE " + " AND ".join(clauses)
    rows = conn.execute(f"SELECT * FROM jobs {where} ORDER BY id", params).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_unscored_jobs() -> List[dict]:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE score IS NULL AND description IS NOT NULL AND description != '' ORDER BY scraped_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def delete_job(job_id: int):
    """Permanently delete a single job by ID."""
    conn = get_connection()
    conn.execute("DELETE FROM jobs WHERE id=?", (job_id,))
    conn.commit()
    conn.close()


def clear_jobs() -> int:
    """Delete only new/rejected jobs — preserves applied, interviewing, and offer records.
    Returns count of deleted rows."""
    conn = get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM jobs WHERE status IN ('new', 'rejected')"
    ).fetchone()[0]
    conn.execute("DELETE FROM jobs WHERE status IN ('new', 'rejected')")
    conn.commit()
    conn.close()
    return n


def get_applied_jobs() -> list:
    """Return all jobs that are in-progress (applied / interviewing / offer)."""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM jobs WHERE status IN ('applied', 'interviewing', 'offer') ORDER BY scraped_at DESC"
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def stats() -> dict:
    conn = get_connection()
    total     = conn.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
    by_source = conn.execute("SELECT source, COUNT(*) as n FROM jobs GROUP BY source").fetchall()
    by_status = conn.execute("SELECT status, COUNT(*) as n FROM jobs GROUP BY status").fetchall()
    scored    = conn.execute("SELECT COUNT(*) FROM jobs WHERE score IS NOT NULL").fetchone()[0]
    avg_row   = conn.execute("SELECT AVG(score) FROM jobs WHERE score IS NOT NULL").fetchone()[0]
    conn.close()
    return {
        "total": total,
        "by_source": {r["source"]: r["n"] for r in by_source},
        "by_status": {r["status"]: r["n"] for r in by_status},
        "scored": scored,
        "avg_score": round(avg_row or 0, 1),
    }
