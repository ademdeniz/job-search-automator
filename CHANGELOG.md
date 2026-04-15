# Changelog

All notable changes to Job Search Automator are documented here.

---

## [Unreleased]

Features in progress or planned for the next version.

---

## [0.6.0] — 2026-04-15

### Added
- **Auto-scrape scheduler** — background process (launched by `start.sh`) runs the full scrape → fetch → score pipeline on a configurable interval (2–24h). Configure from Actions → ⏰ Auto-Scrape Scheduler.
- **Email notifications** — HTML email alert via Gmail SMTP when high-score new jobs appear. Shows score badge, title, company, location, and a "View job posting →" link per job. Only fires for jobs from the current run to prevent re-alerting on old jobs.
- **Email deep link** — "Open Job Board →" CTA in emails now opens the app directly on the Job Board page (`?page=job_board` query param). URL query param routing added to `ui.py`.
- **Multiple resume slots** — maintain named resume versions (e.g. Senior IC, Manager track, Startup) from the Profile page. Scorer and tailor always use the active slot.
- **Rejection pattern analysis** — Dashboard section that aggregates skill gaps, source patterns, and score ranges from all rejected applications and asks Claude Haiku to surface concrete patterns and an action plan.
- **Salary estimate** — Claude Haiku estimates a salary range at scoring time when the job posting doesn't list one. Shown as `~$X–$Y (est.)` on job cards.
- **Company red-flag signals** — one-click analysis per job card: layoffs, Glassdoor rating, financial distress, executive churn. Powered by Claude Haiku, results cached in DB per job.
- **Interview prep v2** — difficulty ratings (easy / medium / hard) per question, tailored answer using your real experience, 2 follow-up questions per Q. Backward compatible with old format.
- **Browser fingerprinting for fetch** — UA rotation, `--disable-blink-features=AutomationControlled`, stealth init script hiding `navigator.webdriver`, realistic HTTP headers, random delays. Reduces Indeed/Dice bot detection.

### Fixed
- Post-scrape fetch/score warnings now persist across `st.rerun()` via session state instead of being lost.
- Resume slot "Add" button now uses `st.form` — fixes unreliable input capture in Streamlit.
- Email notification no longer fires for all existing `new` jobs — filters by `scraped_at >= cutoff` (60 min window).
- Email send failure now surfaces an error in the UI instead of silently claiming success.

---

## [0.5.0] — 2026-03-XX

### Added
- **Skill chips on job cards** — matched skills (✅), missing skills (❌), and suggested keywords (💡) shown on every card after scoring.
- **Auto-score after scrape** — scoring runs automatically after every scrape run, no manual step needed.
- **Auto-fetch descriptions after scrape** — headless browser fetch runs automatically before scoring so jobs have descriptions ready.
- **PDF output** — `.pdf` download via LibreOffice (free, offline). Appears alongside `.docx` if LibreOffice is installed.
- **Application analytics** on Dashboard — response rate by source, score distribution (responded vs. no response), pipeline funnel.
- **Follow-up email drafter** — auto-drafts a short follow-up for applications with no response after 7+ days.
- **Interview prep generator** — Claude Sonnet generates 10 role-specific Q&As, downloadable as `.docx`.
- **Google Calendar integration** — one-click pre-filled calendar link for interview scheduling. No OAuth required.
- **Notes per application** — free-text notes field saved to DB, survives refresh.
- **Fuzzy deduplication** — same job posted across multiple boards stored once (80% token overlap on title+company).
- **Fresh search checkbox** — clears `new`/`rejected` jobs before scraping while preserving applied+ pipeline.

### Changed
- Pages split from `ui.py` into separate modules under `pages/` — each exports `render()`.
- `run_cli()`, `show_cli_result()`, `claude_call()` moved to `pages/utils.py`.
- `ui.py` reduced to entry point + sidebar routing only.

### Fixed
- Keyword title filter reverted to not exclude mobile/web/cloud/IT — was blocking legitimate results.
- Scrape keywords now persist across tab switches using session state.
- Post-scrape banner persists after `st.rerun()`.
- Interview prep saved to DB — survives page refresh and tab switches.

---

## [0.4.0] — 2026-02-XX

### Added
- **Cover letter voice pass** — second Claude call rewrites cover letter to match candidate's natural writing style using a writing sample they provide.
- **Company context in tailoring** — fetches company website, Claude Haiku extracts structured intel, cached in DB per company.
- **ATS validation** — checks generated resume for formatting issues that break ATS parsers. Result shown as badge in UI.
- **My Applications page** — dedicated tracker with inline stage advancement (`applied → interviewing → offer`), permanent removal, notes, and applied date.
- **Role-agnostic scorer and tailor** — prompts now read from `profile.title` + `profile.target_role` instead of hardcoded QA references. Works for any field.
- **Profile page** — manage resume, contact info, title, target role, and writing sample from the UI.
- **Fetch descriptions for Indeed + Dice** — headless browser fetch extended beyond LinkedIn.
- **Description paste fallback** — paste full job description manually from a job card when fetch doesn't work.
- **Metadata extraction** — posted date, salary, job type extracted from pasted descriptions via Claude.

### Fixed
- Cover letter prompt rewritten for hook-first opener and authentic voice.
- Signature font — Brush Script MT for name, Calibri muted for title.
- Em dash banned from generated resume and cover letter (ATS incompatible).
- Download filenames use real company name, not aggregator name.
- `save_jobs()` return value changed to tuple `(inserted, fuzzy_skipped)` — callers updated.

---

## [0.3.0] — 2026-01-XX

### Added
- **Resume tailoring** — Claude Sonnet rewrites resume bullets to mirror the job's language using your exact metrics and project names. Outputs `.docx`.
- **Cover letter generation** — hook-first opener with company-specific context.
- **Location modes** — US Remote, World Remote, Local/Hybrid (any city/zip), or both in one run.
- **Freshness filter** — `--days-ago` flag limits results to jobs posted in last 24h / 3 days / 7 days.
- **Himalayas and Jobspresso scrapers** — 9 sources total.
- **`start.sh`** — preflight checks (API key, playwright, profile) before launching UI.
- **Toast notification** on profile save.

### Fixed
- Word-boundary title filter — stops scraping irrelevant roles without over-filtering.
- US-remote location enforcement in scraper base.
- Dice card parser — correctly extracts title/company/location.
- Greenhouse/Lever title filter made field-agnostic.

---

## [0.2.0] — 2025-12-XX

### Added
- **Streamlit UI** — full dashboard with Job Board, Dashboard, Actions pages.
- **Indeed scraper** (Playwright), **Dice**, **Greenhouse**, **Lever** scrapers.
- **Fetch full descriptions** — headless Playwright browser visits each job URL.
- **Score display** — colour-coded cards (🟢 excellent · 🟡 good · 🟠 fair · 🔴 poor).
- **Status tracking** — mark jobs as applied / rejected from the Job Board.
- **CSV export**.
- **CLI commands** — `list`, `show`, `open`, `status`, `stats`, `export`, `clear`.

### Changed
- LinkedIn scraper rewritten from regex to Playwright for reliability.
- WeWorkRemotely added.

---

## [0.1.0] — 2025-11-XX

### Added
- Initial release — scraping (LinkedIn), AI scoring (Claude Haiku), and basic job tracking via CLI.
- `main.py` CLI entry point with `scrape`, `fetch`, `score`, `tailor` commands.
- SQLite storage via `jobs.db`.
- `profile.json` for resume and contact info.
