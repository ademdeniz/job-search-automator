#!/usr/bin/env python3
# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Background scheduler — runs the scrape → fetch → score pipeline automatically.

Launched by start.sh alongside the Streamlit UI. Reads scheduler config from
profile.json. Sends email notifications when high-score new jobs are found.

Usage (handled by start.sh — no need to run manually):
    python3 scheduler.py
"""

import json
import os
import smtplib
import subprocess
import sys
import time
from datetime import datetime
from email.mime.text import MIMEText
from pathlib import Path

import schedule

ROOT = Path(__file__).parent
STATE_FILE = ROOT / "scheduler_state.json"


# ── helpers ───────────────────────────────────────────────────────────────────

def _load_profile() -> dict:
    path = ROOT / "profile.json"
    if not path.exists():
        return {}
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _load_state() -> dict:
    if STATE_FILE.exists():
        try:
            with open(STATE_FILE) as f:
                return json.load(f)
        except Exception:
            pass
    return {"last_run": None, "last_found": 0, "last_alerted": 0}


def _save_state(state: dict):
    with open(STATE_FILE, "w") as f:
        json.dump(state, f, indent=2)


def _run(cmd: list) -> tuple:
    """Run a subprocess, return (stdout, returncode)."""
    result = subprocess.run(
        [sys.executable] + cmd,
        cwd=ROOT,
        capture_output=True,
        text=True,
    )
    return result.stdout + result.stderr, result.returncode


def _get_new_high_score_jobs(min_score: int, since_minutes: int = 60) -> list:
    """
    Query DB for new jobs above the min score threshold scraped recently.
    Only returns jobs scraped within the last `since_minutes` minutes
    so we don't re-notify for old jobs on every run.
    """
    try:
        import sqlite3
        from datetime import datetime, timedelta
        db = ROOT / "jobs.db"
        if not db.exists():
            return []
        cutoff = (datetime.now() - timedelta(minutes=since_minutes)).isoformat()
        conn = sqlite3.connect(db)
        conn.row_factory = sqlite3.Row
        rows = conn.execute(
            "SELECT title, company, location, score, url FROM jobs "
            "WHERE status='new' AND score >= ? AND scraped_at >= ? "
            "ORDER BY score DESC LIMIT 20",
            (min_score, cutoff),
        ).fetchall()
        conn.close()
        return [dict(r) for r in rows]
    except Exception:
        return []


def _send_email(cfg: dict, jobs: list) -> tuple:
    """
    Send a notification email via SMTP (Gmail app password).
    Returns (success: bool, error_message: str).
    """
    smtp_from = cfg.get("smtp_from", "").strip()
    smtp_pass = cfg.get("smtp_password", "").strip()
    notify_to = cfg.get("notify_email", "").strip() or smtp_from

    if not smtp_from or not smtp_pass:
        return False, "Email not configured — add Gmail address and app password."

    lines = [
        f"Job Search Automator found {len(jobs)} new high-score job(s):\n",
    ]
    for j in jobs:
        lines.append(
            f"  • {j['score']}/100 — {j['title']} @ {j['company']} ({j['location']})"
        )
        if j.get("url"):
            lines.append(f"    {j['url']}")
        lines.append("")

    lines.append("Open the Job Board to review: http://localhost:8501")

    msg = MIMEText("\n".join(lines))
    msg["Subject"] = f"🎯 {len(jobs)} new job match(es) — Job Search Automator"
    msg["From"]    = smtp_from
    msg["To"]      = notify_to

    try:
        with smtplib.SMTP_SSL("smtp.gmail.com", 465, timeout=15) as server:
            server.login(smtp_from, smtp_pass)
            server.sendmail(smtp_from, notify_to, msg.as_string())
        print(f"[Scheduler] Email sent to {notify_to}", flush=True)
        return True, ""
    except Exception as e:
        print(f"[Scheduler] Email failed: {e}", flush=True)
        return False, str(e)


# ── main job ──────────────────────────────────────────────────────────────────

def run_pipeline():
    profile  = _load_profile()
    sched    = profile.get("scheduler", {})
    if not sched.get("enabled"):
        return

    keywords   = (profile.get("target_role") or "").strip()
    min_score  = int(sched.get("min_score_alert", 70))
    sources    = sched.get("sources") or []

    if not keywords:
        print("[Scheduler] No target_role in profile — skipping.", flush=True)
        return

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    print(f"\n[Scheduler] {now} — starting pipeline (keywords: {keywords})", flush=True)

    # ── scrape ────────────────────────────────────────────────────────────────
    cmd = ["main.py", "scrape", "--keywords", keywords]
    if sources:
        cmd += ["--sources"] + sources
    out, _ = _run(cmd)
    print(f"[Scheduler] Scrape done.\n{out[-500:]}", flush=True)

    # ── fetch descriptions ─────────────────────────────────────────────────────
    out, _ = _run(["main.py", "fetch"])
    print(f"[Scheduler] Fetch done.\n{out[-300:]}", flush=True)

    # ── score ─────────────────────────────────────────────────────────────────
    out, _ = _run(["main.py", "score"])
    print(f"[Scheduler] Score done.\n{out[-300:]}", flush=True)

    # ── notify if high-score jobs found ───────────────────────────────────────
    high_score_jobs = _get_new_high_score_jobs(min_score)
    state = _load_state()

    if high_score_jobs:
        print(f"[Scheduler] {len(high_score_jobs)} job(s) above {min_score} — sending notification.", flush=True)
        ok, err = _send_email(sched, high_score_jobs)
        if not ok:
            print(f"[Scheduler] Notification skipped: {err}", flush=True)
        state["last_alerted"] = len(high_score_jobs) if ok else 0
    else:
        print(f"[Scheduler] No new jobs above {min_score}.", flush=True)
        state["last_alerted"] = 0

    state["last_run"]   = now
    state["last_found"] = len(high_score_jobs)
    _save_state(state)


# ── entry point ───────────────────────────────────────────────────────────────

def _reschedule():
    """Re-read the interval from profile and reschedule. Called every hour."""
    schedule.clear("pipeline")
    profile = _load_profile()
    hours   = int((profile.get("scheduler") or {}).get("interval_hours", 6))
    schedule.every(hours).hours.do(run_pipeline).tag("pipeline")
    print(f"[Scheduler] Pipeline scheduled every {hours}h.", flush=True)


if __name__ == "__main__":
    print("[Scheduler] Starting…", flush=True)

    # Run immediately if enabled
    profile = _load_profile()
    if (profile.get("scheduler") or {}).get("enabled"):
        run_pipeline()

    _reschedule()
    # Re-read interval config every hour so UI changes take effect
    schedule.every(1).hours.do(_reschedule)

    while True:
        schedule.run_pending()
        time.sleep(60)
