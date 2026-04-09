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
scorer/            → Claude Haiku batch scoring (0-100 match score)
tailor/            → Claude Sonnet resume + cover letter generation → .docx
storage/           → SQLite (database.py) + profile.json (profile.py)
models/            → Job dataclass
ui.py              → Streamlit dashboard (5 pages, ~1200 lines)
main.py            → CLI entry point (argparse)
start.sh           → Startup script with preflight checks
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
- `run_cli()` in `ui.py` returns `(output: str, success: bool)` — not just a string. Always unpack both.

### `storage/profile.py`
- `profile.json` is the single source of truth for the user's resume, contact info, title, target role, and writing sample.
- **Never committed to git.** Each user has their own.
- Fields: `name`, `email`, `linkedin`, `github`, `website`, `location`, `title`, `target_role`, `resume`, `writing_sample`.
- Scorer and tailor both read from profile — `title` + `target_role` dynamically set Claude's specialisation so the tool works for any domain, not just QA.

### `scrapers/base.py`
- `BaseScraper` provides: keyword building, US-location filtering, `_title_matches_keywords()` (word-boundary aware, skips generic words), freshness cutoff via `_is_recent()`.
- All scrapers must call `_title_matches_keywords()` before appending jobs.

### `scrapers/linkedin.py`
- Also contains `fetch_descriptions()` — the headless browser that visits each job URL to extract full descriptions.
- Supports LinkedIn, Indeed, and Dice via `_SELECTORS` dict and `_SUPPORTED_SOURCES` set.

### `tailor/resume_tailor.py`
- Two-step generation: Claude Sonnet writes resume + cover letter → second Claude call (voice pass) rewrites cover letter to match candidate's writing sample.
- `_build_system_prompt(profile)` injects `title` + `target_role` from profile — no hardcoded QA references.
- Company context: fetches company website, asks Claude Haiku to extract structured intel, stores in `company_context` DB column (cached — won't re-fetch).
- Output goes to `output/<slug>/` (gitignored).

### `scorer/job_scorer.py`
- Uses Claude Haiku for cost efficiency.
- `_build_system_prompt(profile)` — same pattern as tailor, role-agnostic.
- `score_jobs_batch()` loads profile once and reuses it for the whole batch.

### `ui.py`
- Five pages: Profile, Actions, Job Board, Dashboard, My Applications.
- `run_cli(cmd)` → runs a subprocess against `main.py`, returns `(output, success)`. Detects errors via exit code + known error signal strings.
- `_show_cli_result(out, success)` → shows `st.error` on failure, `st.code` on success.
- `_claude_call(system, user, model, max_tokens)` → direct API call for UI-level features (interview prep, follow-up email) without going through CLI.
- **Session state + DB persistence pattern**: notes, interview_prep are saved to DB on change/generation and loaded from DB into session state on first card open. Don't use session state alone for anything that should survive refresh.
- Scrape banner and score output persist via `st.session_state["last_scrape_count"]` / `["last_score_output"]` — cleared by Dismiss button.

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
| scored_at | TEXT | |
| applied_at | TEXT | set automatically when status → applied |
| company_context | TEXT | Claude-extracted company intel |
| notes | TEXT | user notes, saved on change |
| interview_prep | TEXT | Claude-generated Q&A, saved to DB |

---

## What's gitignored (and why)

| Path | Reason |
|---|---|
| `jobs.db` | Personal application data |
| `profile.json` | Resume + contact info |
| `resume.txt` | Legacy fallback, removed — use profile.json |
| `output/` | Generated .docx files |
| `.claude/` | Claude Code session data |

---

## Conventions

- Copyright header on every `.py` file.
- No hardcoded QA/SDET references in prompts — always read from `profile.title` + `profile.target_role`.
- Error handling: all CLI calls go through `run_cli()` and display via `_show_cli_result()`. UI-level Claude calls use try/except with `st.error()`.
- DB migrations: add new columns to the migration loop in `init_db()` AND run `ALTER TABLE` manually on the local dev DB (it won't re-run existing migrations).
- `save_jobs()` returns a tuple — always unpack: `inserted, fuzzy_skipped = save_jobs(jobs)`.

---

## Roadmap status

**Done:**
- Multi-source scraping (9 boards)
- Freshness filter, location modes (US Remote / World Remote / Local)
- Title filtering (word-boundary, role-agnostic)
- AI scoring (Claude Haiku, 0-100)
- Resume + cover letter tailoring (Claude Sonnet → .docx)
- ATS validation
- Cover letter voice pass (writing sample calibration)
- Company context extraction (Claude Haiku, cached in DB)
- My Applications pipeline tracker
- Google Calendar integration (no OAuth)
- Interview prep generator (Claude Sonnet → .docx download, saved to DB)
- Follow-up email drafter (7+ days no response)
- Application analytics (response rate by source, score distribution)
- Notes field (persisted to DB)
- Error handling on all CLI operations
- Fuzzy duplicate detection across sources
- Role-agnostic (scorer + tailor adapt to any field via profile)
- start.sh preflight checks

**Planned / not started:**
- PDF output (CloudConvert API — needs key)
- Split ui.py into page modules
- Pin requirements.txt versions
- Auto-apply (LinkedIn Easy Apply + Greenhouse forms)
- Interview prep generator improvements (difficulty levels, follow-up questions)
