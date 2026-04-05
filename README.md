# Job Search Automator

> **© 2026 Adem Garic — All Rights Reserved.**
> View-only. No use, copying, or distribution without written permission. See [LICENSE](LICENSE).

---

A personal job search tool that scrapes multiple job boards, scores every posting against your resume using Claude AI, tailors your resume and cover letter per role, and tracks your full application pipeline — all from a clean Streamlit UI or the terminal.

Built with Python + Claude AI (Anthropic).

---

## Features

- **Scrape** jobs from 7 sources simultaneously: LinkedIn, Indeed, RemoteOK, WeWorkRemotely, Dice, Greenhouse, and Lever
- **Score** every job 0–100 against your resume using Claude AI — know which roles are worth your time before you apply
- **Tailor** your resume and cover letter per job using Claude Sonnet — fetches company context from their website, generates ready-to-send `.docx` files
- **ATS validation** — checks generated resume for formatting issues that break ATS parsers
- **Location modes** — US Remote, World Remote, Local/Hybrid (any city, state, or zip), or both in one run
- **Freshness filter** — limit results to jobs posted in the last 24h, 3 days, or 7 days
- **Track** your full application pipeline: applied → interviewing → offer
- **My Applications** — dedicated tracker with inline stage advancement and permanent removal
- **Profile page** — manage your resume, contact info, and links from the UI
- **Visual UI** — Streamlit dashboard with color-coded job cards, score distribution charts, and one-click actions
- **Export** to CSV for spreadsheet workflows

---

## Tech Stack

| Layer | Tool |
|---|---|
| Scraping (JS-rendered) | Playwright (headless Chromium) |
| Scraping (API/RSS) | requests |
| AI scoring + tailoring | anthropic (Claude Haiku / Sonnet) |
| Storage | SQLite via sqlite3 |
| UI | Streamlit |
| Documents | python-docx |
| CLI | argparse |

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/ademdeniz/job-search-automator.git
cd job-search-automator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
python -m playwright install chromium
```

> **Linux / WSL users:** Playwright needs system dependencies. Run this first:
> ```bash
> playwright install-deps chromium
> ```

### 3. Add your Anthropic API key

The `score` and `tailor` commands call Claude AI. Get a key at [console.anthropic.com](https://console.anthropic.com).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

To make it permanent so you don't have to re-enter it every session:

**Mac (zsh):**
```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.zshrc
source ~/.zshrc
```

**Linux (bash):**
```bash
echo 'export ANTHROPIC_API_KEY=sk-ant-...' >> ~/.bashrc
source ~/.bashrc
```

Replace `sk-ant-...` with your actual key. You can verify it was saved with:
```bash
echo $ANTHROPIC_API_KEY
```

### 4. Launch the UI and set up your profile

```bash
./start.sh
```

This opens the dashboard at **http://localhost:8501**.

**Before doing anything else, go to the 👤 Profile page** and fill in:
- Your name, email, LinkedIn, GitHub
- Target role / keywords (e.g. `SDET test automation Appium`) — used as default search terms
- Your full resume as plain text

Hit **Save Profile**. This creates `profile.json` locally (gitignored — stays on your machine).
Scoring and tailoring will not work until the profile is saved.

---

## Launching the UI

```bash
./start.sh
```

Opens the Streamlit dashboard at **http://localhost:8501**.

Five pages:

- **Job Board** — filterable, color-coded cards (🟢 excellent · 🟡 good · 🟠 fair · 🔴 poor), expandable details, inline status updates, tailor button with ATS check badge
- **Dashboard** — score distribution, jobs by source, pipeline funnel, top 10 matches
- **Actions** — scrape, fetch descriptions, score with AI, export CSV
- **My Applications** — tracks applied/interviewing/offer jobs with one-click stage advancement; preserved across fresh searches
- **Profile** — manage your resume and contact info

---

## CLI Usage

### Scrape jobs

```bash
# US remote only (default — filters out non-US locations)
python main.py scrape --keywords "sdet appium mobile" --location "Remote US"

# Worldwide remote (no country filter)
python main.py scrape --keywords "qa automation" --location "Remote"

# Local / hybrid by city or zip
python main.py scrape --keywords "qa engineer" --location "Erie, PA" --sources linkedin indeed

# Specific sources, last 3 days only
python main.py scrape --keywords "qa automation" --sources linkedin indeed --days-ago 3

# Limit results per source
python main.py scrape --keywords "selenium" --max-results 25
```

Available sources: `linkedin` `indeed` `remoteok` `weworkremotely` `dice` `greenhouse` `lever`

Freshness: `--days-ago 1` (24h) · `--days-ago 3` · `--days-ago 7`

### Fetch full descriptions (LinkedIn)

LinkedIn cards don't include full descriptions — visit each job page to extract them:

```bash
python main.py fetch --source linkedin
```

### Score jobs against your resume

```bash
# Score all new (unscored) jobs
python main.py score

# Re-score everything
python main.py score --all

# Score a specific job by ID
python main.py score --id 42
```

Each job gets a score (0–100), match level, matched skills, missing skills, and suggested keywords.

### Tailor resume + cover letter for a specific job

```bash
python main.py tailor 42
```

Generates two `.docx` files in `output/<job-slug>/`:
- `resume.docx` — bullets reworded to mirror the job's language using your exact metrics and project names; professional summary tailored to the role
- `cover_letter.docx` — references the company by name and product/mission (fetched from their website); letterhead with your contact info

> Job must have a description. If missing, paste one in the UI or run `fetch` first.

### List and filter jobs

```bash
python main.py list                            # all jobs
python main.py list --sort-by score            # highest score first
python main.py list --min-score 70             # strong matches only
python main.py list --status new               # by status
python main.py list --source greenhouse        # by source
python main.py list --keyword "appium"         # search title/company/description
python main.py list --remote                   # remote only
```

### Other commands

```bash
python main.py show 42              # full detail view of a job
python main.py open 42              # open job URL in browser
python main.py status 42 applied    # update application status
python main.py stats                # summary by source, status, avg score
python main.py export               # export all jobs to CSV
python main.py clear                # delete new/rejected jobs (preserves applied+)
```

Valid statuses: `new` · `applied` · `interviewing` · `offer`

---

## Project Structure

```
job-search-automator/
├── main.py               # CLI entry point — all commands
├── start.sh              # Launch UI: ./start.sh
├── profile.json          # Your profile — created on first save in UI (gitignored)
├── requirements.txt
│
├── scrapers/
│   ├── base.py           # BaseScraper — freshness, US-location filtering
│   ├── linkedin.py       # Playwright — US remote or geographic search
│   ├── indeed.py         # Playwright — with date filter
│   ├── remoteok.py       # JSON API
│   ├── weworkremotely.py # RSS — programming jobs feed
│   ├── dice.py           # Playwright — with date filter
│   ├── greenhouse.py     # Public JSON API — curated QA-friendly companies
│   └── lever.py          # Public JSON API — curated QA-friendly companies
│
├── scorer/
│   └── job_scorer.py     # Claude Haiku — batch scoring, 0-100 match score
│
├── tailor/
│   └── resume_tailor.py  # Claude Sonnet — tailored resume + cover letter → .docx
│
├── models/
│   └── job.py            # Job dataclass
│
├── storage/
│   ├── database.py       # SQLite helpers
│   └── profile.py        # Profile load/save
│
├── ui.py                 # Streamlit dashboard (5 pages)
└── output/               # Generated .docx files (gitignored)
```

---

## Roadmap

- [x] Multi-source scraping (7 boards)
- [x] Freshness filter (24h / 3 days / 7 days)
- [x] Location modes — US Remote, World Remote, Local/Hybrid (any location)
- [x] QA/SDET-specific title filtering (word-boundary matching)
- [x] AI job scoring (Claude Haiku)
- [x] Status tracking and filtering
- [x] Streamlit visual dashboard
- [x] My Applications tracker — pipeline with stage advancement
- [x] Resume tailoring per job (Claude Sonnet → .docx)
- [x] Cover letter generation with company context
- [x] ATS formatting validation
- [x] Profile page — manage resume and contact info from UI
- [x] CSV export
- [ ] Auto-apply with Playwright (LinkedIn Easy Apply + Greenhouse forms)
- [ ] Interview prep generator
- [ ] Follow-up email drafter

---

## Notes

- `jobs.db` and `output/` are excluded from git — they contain personal data
- `profile.json` is excluded from git — it contains your personal resume and contact info
- Scoring costs ~$0.001/job with Claude Haiku — 100 jobs ≈ $0.10
- Tailoring costs ~$0.01–0.02/job with Claude Sonnet
- LinkedIn scraping uses the unauthenticated guest search — no login required

---

## Author

**Adem Garic** — SDET / QA Engineer
6+ years in test automation (Appium, Selenium, Jenkins, BrowserStack, AWS Device Farm)
[LinkedIn](https://linkedin.com/in/adem-garic-sdet-qa) · [GitHub](https://github.com/ademdeniz)
