# CLAUDE.md — Job Search Automator

This file gives Claude Code instant context about this project. Read it before doing anything else.

---

## What this is

A personal job search automation tool. Scrapes 9 job boards, scores every posting against a resume using Claude AI, tailors resume + cover letter per role, and tracks the full application pipeline. Runs as a Streamlit UI or via CLI.

Fully role-agnostic — the user fills in their own `profile.json` (name, resume, title, target role) and the tool adapts. Works for any field: engineering, design, HR, product, etc.

---

## Architecture

```
scrapers/          → One class per job board, all extend BaseScraper
scorer/            → Claude Haiku batch scoring + company signals
tailor/            → Claude Sonnet resume + cover letter generation → .docx
storage/           → SQLite (database.py) + profile.json (profile.py)
models/            → Job dataclass
pages/             → One module per UI page, each exports render()
ui.py              → Streamlit entry point — sidebar nav + page routing
scheduler.py       → Background scrape → fetch → score pipeline + email alerts
main.py            → CLI entry point (argparse)
start.sh           → Launches UI + scheduler together
```

### Data flow

```
scrape → save_jobs() → jobs.db
       → fetch_descriptions() → update_description()
       → score_jobs_batch() → save_score()
       → tailor_job() → output/<slug>/resume.docx + cover_letter.docx
```

---

## Key files and what to know about them

### `storage/database.py`
- All DB access goes through here. SQLite at `jobs.db` (gitignored).
- `init_db()` runs on startup and handles column migrations via `ALTER TABLE ... ADD COLUMN` wrapped in try/except — safe to add new columns here.
- `save_jobs()` returns a **tuple** `(inserted, fuzzy_skipped)` — not just an int. Fuzzy duplicate detection runs on title+company (80% token overlap).
- `save_score()` accepts optional `salary_estimate` param — only adds to SET clause if provided.
- `save_company_signals(job_id, flags, level)` — stores red flag list (JSON) + level (0–3).
- `get_rejected_jobs()` — returns scored jobs with status `rejected`, used by Dashboard rejection analysis.

### `storage/profile.py`
- `profile.json` is the single source of truth for resume, contact info, title, target role, writing sample, resume slots, and scheduler config.
- **Never committed to git.** Each user has their own.
- Top-level fields: `name`, `email`, `linkedin`, `github`, `website`, `location`, `title`, `target_role`, `resume`, `writing_sample`, `resumes` (dict), `active_resume` (str), `scheduler` (dict).
- `resumes` is a dict of `{slot_name: resume_text}`. `active_resume` points to the active key. `resume` is always kept in sync with the active slot for backward compat.
- `_ensure_slots(profile)` — seeds `resumes = {"Default": resume}` if empty (backward compat).
- `_ensure_scheduler(profile)` — ensures all scheduler keys exist with defaults.
- `load_profile()` calls both ensure functions on every load.
- Scorer and tailor both read from profile — `title` + `target_role` dynamically set Claude's specialisation.

### `scrapers/base.py`
- `BaseScraper` provides: keyword building, US-location filtering, `_title_matches_keywords()` (word-boundary aware, skips generic words), freshness cutoff via `_is_recent()`.
- All scrapers must call `_title_matches_keywords()` before appending jobs.

### `scrapers/linkedin.py`
- Contains `fetch_descriptions()` — headless Playwright browser that visits each job URL to extract full descriptions.
- Supports LinkedIn, Indeed, and Dice via `_SELECTORS` dict and `_SUPPORTED_SOURCES` set.
- **Bot detection mitigations**: UA rotation (`_USER_AGENTS` list), `--disable-blink-features=AutomationControlled` browser arg, stealth init script (`_STEALTH_JS`) that hides `navigator.webdriver`, realistic HTTP headers + locale, random delays between requests (2–4.5s).

### `scorer/job_scorer.py`
- Uses Claude Haiku for cost efficiency.
- `_build_system_prompt(profile)` — role-agnostic, reads from `profile.title` + `profile.target_role`.
- `score_jobs_batch()` loads profile once and reuses for the whole batch.
- Returns `ScoreResult` dataclass with `salary_estimate: Optional[str]` field.

### `scorer/company_signals.py`
- `fetch_company_signals(company, job_title, location)` — Claude Haiku analysis of company health.
- Returns `{"level": 0–3, "flags": [...], "summary": "..."}`. Level 0=none, 1=minor, 2=moderate, 3=serious.
- Results cached in DB (`red_flags`, `red_flag_level` columns) — won't re-fetch for the same job.

### `tailor/resume_tailor.py`
- Two-step generation: Claude Sonnet writes resume + cover letter → second Claude call (voice pass) rewrites cover letter to match candidate's writing sample.
- `_build_system_prompt(profile)` injects `title` + `target_role` from profile — no hardcoded role references.
- Company context: fetches company website, asks Claude Haiku to extract structured intel, stores in `company_context` DB column (cached — won't re-fetch).
- Output goes to `output/<slug>/` (gitignored).

### `pages/` modules
- Each page exports `render()`. `ui.py` calls the active page's `render()` based on sidebar radio.
- `pages/utils.py` — shared constants (`VALID_STATUSES`, `SOURCES`, `ERIE_SOURCES`), `run_cli()`, `show_cli_result()`, `claude_call()`, `render_company_signals()`.
- `run_cli(cmd)` → runs subprocess against `main.py`, returns `(output: str, success: bool)`. Always unpack both.
- `show_cli_result(out, ok)` → `st.error` on failure, `st.code` on success.
- `claude_call(system, user, model, max_tokens)` → direct Anthropic API call for UI-level features.

### `ui.py`
- Streamlit entry point. Imports all page modules and calls `render()` based on sidebar radio selection.
- Reads `?page=` query param on load (`st.query_params`) to support direct deep links (e.g. from email notifications) — maps slug to page label and sets radio index accordingly.
- **Session state + DB persistence pattern**: notes and interview_prep are saved to DB on change/generation and loaded from DB into session state on first card open. Don't use session state alone for anything that should survive refresh.
- Scrape banner persists via `st.session_state["last_scrape_count"]` (dict with `count`, `scored`, `no_desc`) — cleared by Dismiss button.

### `scheduler.py`
- Background process launched by `start.sh` alongside the Streamlit UI.
- `run_pipeline()` — reads profile, runs scrape → fetch → score, then calls `_get_new_high_score_jobs()` and `_send_email()` if high-score jobs found.
- `_get_new_high_score_jobs(min_score, since_minutes=60)` — only queries jobs scraped within the last N minutes so old jobs don't re-trigger alerts.
- `_send_email(cfg, jobs)` — Gmail SMTP via `smtplib.SMTP_SSL`. Returns `(bool, error_str)` tuple — always check both.
- `_reschedule()` — re-reads interval from profile every hour so UI config changes take effect without restart.
- `scheduler_state.json` — persists last run timestamp and count for the status display in the UI.

---

## DB columns (jobs table)

| Column | Type | Notes |
|---|---|---|
| id | INTEGER PK | |
| title, company, location | TEXT | |
| source | TEXT | linkedin, indeed, dice, etc. |
| url | TEXT UNIQUE | dedup key |
| description | TEXT | full job description |
| salary, job_type, posted_date | TEXT | extracted from description |
| remote | INTEGER | 0/1 |
| scraped_at | TEXT | ISO datetime |
| status | TEXT | new, applied, interviewing, offer, rejected |
| score | INTEGER | 0-100 |
| score_reason | TEXT | Claude's highlights sentence |
| missing_skills | TEXT | JSON list — used by rejection analysis |
| salary_estimate | TEXT | AI-estimated range, shown when posting has no salary |
| scored_at | TEXT | |
| applied_at | TEXT | set automatically when status → applied |
| company_context | TEXT | Claude-extracted company intel (cached) |
| red_flags | TEXT | JSON list of flag strings from company signals |
| red_flag_level | INTEGER | 0=none 1=minor 2=moderate 3=serious |
| notes | TEXT | user notes, saved on change |
| interview_prep | TEXT | Claude-generated Q&A JSON, saved to DB |

---

## What's gitignored (and why)

| Path | Reason |
|---|---|
| `jobs.db` | Personal application data |
| `profile.json` | Resume + contact info |
| `resume.txt` | Legacy fallback, removed — use profile.json |
| `output/` | Generated .docx files |
| `scheduler_state.json` | Runtime state, machine-specific |
| `.claude/` | Claude Code session data |

---

## Conventions

- Copyright header on every `.py` file.
- No hardcoded role references in prompts — always read from `profile.title` + `profile.target_role`.
- Error handling: all CLI calls go through `run_cli()` and display via `show_cli_result()`. UI-level Claude calls use try/except with `st.error()`.
- DB migrations: add new columns to the migration loop in `init_db()` AND run `ALTER TABLE` manually on the local dev DB (it won't re-run existing migrations).
- `save_jobs()` returns a tuple — always unpack: `inserted, fuzzy_skipped = save_jobs(jobs)`.
- `_send_email()` returns a tuple — always unpack: `ok, err = _send_email(cfg, jobs)`.

---

## Roadmap status

**Done:**
- Multi-source scraping (9 boards)
- Freshness filter, location modes (US Remote / World Remote / Local)
- Title filtering (word-boundary, role-agnostic)
- AI scoring (Claude Haiku, 0-100) with matched/missing skills + keyword suggestions
- Salary estimate — AI-estimated range at scoring time when posting has no salary
- Company red-flag signals (Claude Haiku, cached in DB)
- Resume + cover letter tailoring (Claude Sonnet → .docx)
- ATS validation
- Cover letter voice pass (writing sample calibration)
- Company context extraction (Claude Haiku, cached in DB)
- Multiple resume slots (switch active slot from Profile page)
- My Applications pipeline tracker
- Google Calendar integration (no OAuth)
- Interview prep generator v2 — difficulty levels, tailored answers, follow-up questions, .docx download
- Follow-up email drafter (7+ days no response)
- Application analytics (response rate by source, score distribution)
- Rejection pattern analysis (Claude Haiku — surfaces skill gaps from rejected applications)
- Auto-scrape scheduler (background pipeline + Gmail HTML email alerts)
- Notes field (persisted to DB)
- Error handling on all CLI operations
- Fuzzy duplicate detection across sources
- Role-agnostic (scorer + tailor adapt to any field via profile)
- start.sh preflight checks + scheduler launch
- PDF output via LibreOffice (free, offline)
- CSV export

**Planned / not started:**
- Auto-apply (LinkedIn Easy Apply + Greenhouse forms)
- Job market pulse — trending roles and skills from scraped data over time
- Pin requirements.txt versions
