#!/usr/bin/env python3
# Copyright (c) 2026 Adem Garic. All rights reserved.
# Unauthorized use, copying, or distribution is prohibited. See LICENSE.
"""
Job Search Automator — CLI entry point.

Usage examples:
  python main.py scrape --keywords "appium sdet" --location "Remote" --sources remoteok indeed linkedin weworkremotely
  python main.py score
  python main.py score --all
  python main.py score --id 42
  python main.py list
  python main.py list --status new --remote --min-score 70 --sort-by score
  python main.py show 42
  python main.py open 42
  python main.py stats
  python main.py status 42 applied
  python main.py fetch --source linkedin
  python main.py export --output jobs.csv
"""

import argparse
import csv
import os
import sys
import webbrowser
from typing import List

from storage.database import (
    init_db, save_jobs, get_all_jobs, get_job_by_id,
    get_unscored_jobs, get_jobs_without_description,
    update_description, save_score, update_status, stats, clear_jobs,
)
from scrapers.remoteok import RemoteOKScraper
from scrapers.indeed import IndeedScraper
from scrapers.linkedin import LinkedInScraper
from scrapers.weworkremotely import WeWorkRemotelyScraper
from scrapers.dice import DiceScraper
from scrapers.greenhouse import GreenhouseScraper
from scrapers.lever import LeverScraper
from scrapers.himalayas import HimalayanScraper
from scrapers.jobspresso import JobspressoScraper

SCRAPERS = {
    "remoteok":       RemoteOKScraper,
    "indeed":         IndeedScraper,
    "linkedin":       LinkedInScraper,
    "weworkremotely": WeWorkRemotelyScraper,
    "dice":           DiceScraper,
    "greenhouse":     GreenhouseScraper,
    "lever":          LeverScraper,
    "himalayas":      HimalayanScraper,
    "jobspresso":     JobspressoScraper,
}

VALID_STATUSES = {"new", "applied", "rejected", "interviewing", "offer"}

MATCH_EMOJI = {"excellent": "★★★★", "good": "★★★ ", "fair": "★★  ", "poor": "★   ", "unknown": "?   "}


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_scrape(args):
    # Flatten: "sdet qa appium" passed as one quoted string → split into individual terms
    keywords: List[str] = [w for phrase in args.keywords for w in phrase.split()]
    location: str = args.location
    sources: List[str] = args.sources or list(SCRAPERS.keys())
    max_results: int = args.max_results
    days_ago: int = args.days_ago

    unknown = set(sources) - set(SCRAPERS)
    if unknown:
        print(f"Unknown source(s): {', '.join(unknown)}. Available: {', '.join(SCRAPERS)}")
        sys.exit(1)

    all_jobs = []
    for source in sources:
        scraper = SCRAPERS[source](keywords=keywords, location=location,
                                   max_results=max_results, days_ago=days_ago)
        jobs = scraper.scrape()
        all_jobs.extend(jobs)

    if not all_jobs:
        print("No jobs found.")
        return

    inserted, fuzzy_skipped = save_jobs(all_jobs)
    url_skipped = len(all_jobs) - inserted - fuzzy_skipped
    print(f"\nDone. Saved {inserted} new job(s) "
          f"(skipped {url_skipped} exact duplicate(s), {fuzzy_skipped} fuzzy duplicate(s)).")
    if inserted:
        print("Run  python main.py score  to rank them against your resume.")


def cmd_fetch(args):
    """Fetch full job descriptions by visiting each job URL with a headless browser."""
    from scrapers.linkedin import fetch_descriptions, _SUPPORTED_SOURCES

    source = args.source
    jobs = get_jobs_without_description(source=source)

    # If no source filter, limit to sources we can actually fetch from
    if not source:
        jobs = [j for j in jobs if j.get("source", "") in _SUPPORTED_SOURCES]

    if not jobs:
        print(f"No jobs missing descriptions{' for source: ' + source if source else ''}.")
        return

    print(f"Fetching descriptions for {len(jobs)} job(s) via headless browser…\n")

    fetched = 0

    def on_progress(current, total, job, desc):
        pass  # progress is printed inline by the fetcher

    results = fetch_descriptions(jobs, on_progress=on_progress)

    for job_id, desc in results:
        if desc:
            update_description(job_id, desc)
            fetched += 1

    print(f"\nDone. Fetched descriptions for {fetched}/{len(jobs)} job(s).")
    if fetched:
        print("Run  python main.py score  to score them against your resume.")


def cmd_score(args):
    from scorer.job_scorer import score_jobs_batch, _load_resume

    # Determine which jobs to score
    if args.job_id:
        job = get_job_by_id(args.job_id)
        if not job:
            print(f"No job found with ID {args.job_id}.")
            sys.exit(1)
        if not job.get("description"):
            print(f"Job {args.job_id} has no description — cannot score.")
            sys.exit(1)
        jobs = [job]
    elif args.all:
        jobs = get_all_jobs()
        jobs = [j for j in jobs if j.get("description")]
    else:
        jobs = get_unscored_jobs()

    if not jobs:
        print("No jobs to score. (All jobs already scored, or none have descriptions.)")
        print("Use --all to re-score everything.")
        return

    print(f"Scoring {len(jobs)} job(s) against resume.txt …\n")

    try:
        resume_text = _load_resume()
    except FileNotFoundError as e:
        print(f"Error: {e}")
        sys.exit(1)

    def on_progress(current, total, job):
        result = results[-1][1] if results else None
        if result:
            bar = MATCH_EMOJI.get(result.match_level, "?   ")
            print(f"  [{current:>3}/{total}] {bar} {result.score:>3}/100  {job['title']} @ {job['company']}")
            if result.missing_skills:
                print(f"            gaps: {', '.join(result.missing_skills[:4])}")

    results = []

    def _progress(current, total, job):
        on_progress(current, total, job)

    results = score_jobs_batch(jobs, resume_text=resume_text, on_progress=_progress)

    saved = 0
    for job_id, result in results:
        if result is None:
            continue
        reason = (
            f"{result.highlights} | "
            f"matched: {', '.join(result.matched_skills[:5])} | "
            f"gaps: {', '.join(result.missing_skills[:5])} | "
            f"keywords: {', '.join(result.suggested_keywords)}"
        )
        save_score(job_id, result.score, reason)
        saved += 1

    print(f"\nDone. Scored {saved}/{len(jobs)} job(s).")
    print("Run  python main.py list --sort-by score  to see your ranked shortlist.")


def cmd_list(args):
    remote = None
    if args.remote:
        remote = True
    elif args.no_remote:
        remote = False

    jobs = get_all_jobs(
        status=args.status,
        remote=remote,
        source=args.source,
        keyword=args.keyword,
    )

    if args.min_score is not None:
        jobs = [j for j in jobs if j.get("score") is not None and j["score"] >= args.min_score]

    if args.sort_by == "score":
        jobs.sort(key=lambda j: (j.get("score") or -1), reverse=True)

    if not jobs:
        print("No jobs match the given filters.")
        return

    show_score = any(j.get("score") is not None for j in jobs)
    score_w = 8 if show_score else 0
    col_w = {"id": 5, "status": 14, "title": 36, "company": 22, "location": 18, "source": 10}

    header = (
        f"{'ID':<{col_w['id']}} "
        + (f"{'Score':<{score_w}} " if show_score else "")
        + f"{'Status':<{col_w['status']}} "
        f"{'Title':<{col_w['title']}} "
        f"{'Company':<{col_w['company']}} "
        f"{'Location':<{col_w['location']}} "
        f"{'Source':<{col_w['source']}}"
    )
    print(header)
    print("-" * len(header))

    for j in jobs:
        title = (j["title"] or "")[:col_w["title"] - 1]
        company = (j["company"] or "")[:col_w["company"] - 1]
        location = (j["location"] or "")[:col_w["location"] - 1]
        score_str = ""
        if show_score:
            s = j.get("score")
            score_str = f"{s:>3}/100  " if s is not None else "  -      "
        print(
            f"{j['id']:<{col_w['id']}} "
            + (score_str if show_score else "")
            + f"{j['status']:<{col_w['status']}} "
            f"{title:<{col_w['title']}} "
            f"{company:<{col_w['company']}} "
            f"{location:<{col_w['location']}} "
            f"{j['source']:<{col_w['source']}}"
        )
    print(f"\n{len(jobs)} job(s) listed.")


def cmd_show(args):
    job = get_job_by_id(args.job_id)
    if not job:
        print(f"No job found with ID {args.job_id}.")
        sys.exit(1)

    remote_str = {1: "Yes", 0: "No"}.get(job.get("remote"), "Unknown")
    score_line = ""
    if job.get("score") is not None:
        score_line = f"\nMatch Score: {job['score']}/100"
        if job.get("score_reason"):
            score_line += f"\nMatch Notes: {job['score_reason']}"

    print(f"""
ID:          {job['id']}
Title:       {job['title']}
Company:     {job['company']}
Location:    {job['location']}
Remote:      {remote_str}
Source:      {job['source']}
Status:      {job['status']}
Salary:      {job['salary'] or 'N/A'}
Job Type:    {job['job_type'] or 'N/A'}
Posted:      {job['posted_date'] or 'N/A'}
Scraped:     {job['scraped_at']}{score_line}
URL:         {job['url']}

--- Description ---
{(job['description'] or 'No description available.').strip()}
""")


def cmd_open(args):
    job = get_job_by_id(args.job_id)
    if not job:
        print(f"No job found with ID {args.job_id}.")
        sys.exit(1)
    url = job.get("url", "").strip()
    if not url:
        print(f"Job {args.job_id} has no URL.")
        sys.exit(1)
    print(f"Opening: {url}")
    webbrowser.open(url)


def cmd_export(args):
    jobs = get_all_jobs(status=args.status, source=args.source)
    if not jobs:
        print("No jobs to export.")
        return

    output_path = args.output or "jobs.csv"
    fields = ["id", "score", "match_level_hint", "title", "company", "location",
              "remote", "source", "status", "salary", "job_type",
              "posted_date", "scraped_at", "url", "score_reason"]

    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fields, extrasaction="ignore")
        writer.writeheader()
        for job in jobs:
            job["remote"] = "yes" if job.get("remote") == 1 else "no"
            # derive a human-readable match level from score
            s = job.get("score")
            if s is None:
                job["match_level_hint"] = ""
            elif s >= 90:
                job["match_level_hint"] = "excellent"
            elif s >= 70:
                job["match_level_hint"] = "good"
            elif s >= 50:
                job["match_level_hint"] = "fair"
            else:
                job["match_level_hint"] = "poor"
            writer.writerow(job)

    print(f"Exported {len(jobs)} job(s) to {os.path.abspath(output_path)}")


def cmd_tailor(args):
    from tailor.resume_tailor import tailor_job
    job = get_job_by_id(args.job_id)
    if not job:
        print(f"No job found with ID {args.job_id}.")
        sys.exit(1)
    if not job.get("description"):
        print(f"Job {args.job_id} has no description. Run 'fetch' first.")
        sys.exit(1)
    # Allow overriding the company name (useful for aggregator-sourced jobs)
    if args.company:
        job = dict(job)
        job["company"] = args.company
    try:
        result = tailor_job(job)
        print(f"\nDone!")
        print(f"  Resume:       {result.resume_path}")
        print(f"  Cover letter: {result.cover_letter_path}")
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


def cmd_clear(args):
    n = clear_jobs()
    print(f"Cleared {n} job(s) from the database.")


def cmd_stats(args):
    s = stats()
    print(f"Total jobs: {s['total']}\n")
    print("By source:")
    for src, n in s["by_source"].items():
        print(f"  {src:<12} {n}")
    print("\nBy status:")
    for st, n in s["by_status"].items():
        print(f"  {st:<14} {n}")
    if s.get("scored"):
        print(f"\nScored: {s['scored']} / {s['total']}")
        print(f"Avg score (scored jobs): {s['avg_score']:.1f}")


def cmd_status(args):
    if args.new_status not in VALID_STATUSES:
        print(f"Invalid status '{args.new_status}'. Choose from: {', '.join(sorted(VALID_STATUSES))}")
        sys.exit(1)
    update_status(args.job_id, args.new_status)
    print(f"Job {args.job_id} updated to '{args.new_status}'.")


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="main.py",
        description="Automated job board scraper, scorer, and tracker.",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # --- scrape ---
    p_scrape = sub.add_parser("scrape", help="Scrape job boards and save results.")
    p_scrape.add_argument("--keywords", nargs="+", required=True,
                          help="Search keywords, e.g. --keywords appium sdet mobile")
    p_scrape.add_argument("--location", default="", help="Location filter (e.g. 'Remote')")
    p_scrape.add_argument("--sources", nargs="+", choices=list(SCRAPERS),
                          help="Which sources to scrape (default: all)")
    p_scrape.add_argument("--max-results", type=int, default=50, dest="max_results",
                          help="Max results per source (default: 50)")
    p_scrape.add_argument("--days-ago", type=int, default=None, dest="days_ago",
                          choices=[1, 3, 7],
                          help="Only include jobs posted within N days (1, 3, or 7)")

    # --- fetch ---
    p_fetch = sub.add_parser("fetch", help="Fetch full descriptions for jobs missing them (uses headless browser).")
    p_fetch.add_argument("--source", choices=list(SCRAPERS), default=None,
                         help="Only fetch for a specific source (default: all)")

    # --- score ---
    p_score = sub.add_parser("score", help="Score jobs against your resume using Claude AI.")
    score_grp = p_score.add_mutually_exclusive_group()
    score_grp.add_argument("--id", type=int, dest="job_id", metavar="JOB_ID",
                           help="Score a specific job by ID")
    score_grp.add_argument("--all", action="store_true",
                           help="Re-score all jobs (including already-scored ones)")

    # --- list ---
    p_list = sub.add_parser("list", help="List stored jobs.")
    p_list.add_argument("--status", choices=list(VALID_STATUSES), default=None)
    p_list.add_argument("--source", choices=list(SCRAPERS), default=None)
    p_list.add_argument("--keyword", default=None,
                        help="Search keyword in title, company, or description")
    p_list.add_argument("--min-score", type=int, default=None, dest="min_score",
                        help="Only show jobs with score >= N")
    p_list.add_argument("--sort-by", choices=["date", "score"], default="date", dest="sort_by",
                        help="Sort order (default: date)")
    remote_grp = p_list.add_mutually_exclusive_group()
    remote_grp.add_argument("--remote", action="store_true", default=False)
    remote_grp.add_argument("--no-remote", action="store_true", default=False, dest="no_remote")

    # --- show ---
    p_show = sub.add_parser("show", help="Show full details of a job.")
    p_show.add_argument("job_id", type=int)

    # --- open ---
    p_open = sub.add_parser("open", help="Open a job's URL in the browser.")
    p_open.add_argument("job_id", type=int)

    # --- export ---
    p_export = sub.add_parser("export", help="Export jobs to a CSV file.")
    p_export.add_argument("--output", default="jobs.csv")
    p_export.add_argument("--status", choices=list(VALID_STATUSES), default=None)
    p_export.add_argument("--source", choices=list(SCRAPERS), default=None)

    # --- stats ---
    sub.add_parser("stats", help="Show summary statistics.")

    # --- status ---
    p_status = sub.add_parser("status", help="Update a job's status.")
    p_status.add_argument("job_id", type=int)
    p_status.add_argument("new_status", choices=list(VALID_STATUSES))

    # --- tailor ---
    p_tailor = sub.add_parser("tailor", help="Generate tailored resume + cover letter for a job.")
    p_tailor.add_argument("job_id", type=int, help="Job ID from the database")
    p_tailor.add_argument("--company", default=None,
                          help="Override the company name (useful for aggregator-listed jobs)")

    # --- clear ---
    sub.add_parser("clear", help="Delete new/rejected jobs (preserves applied, interviewing, offer).")

    return parser


def main():
    init_db()
    parser = build_parser()
    args = parser.parse_args()

    commands = {
        "scrape": cmd_scrape,
        "fetch":  cmd_fetch,
        "score":  cmd_score,
        "list":   cmd_list,
        "show":   cmd_show,
        "open":   cmd_open,
        "export": cmd_export,
        "stats":  cmd_stats,
        "status": cmd_status,
        "clear":  cmd_clear,
        "tailor": cmd_tailor,
    }
    commands[args.command](args)


if __name__ == "__main__":
    main()
