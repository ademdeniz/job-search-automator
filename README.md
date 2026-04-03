# Job Search Automator

A personal job search tool that scrapes multiple job boards, scores every posting against your resume using Claude AI, tailors your resume and cover letter per role, and tracks your full application pipeline — all from a clean Streamlit UI or the terminal.

Built with Python + Claude AI (Anthropic).

---

## Features

- **Scrape** jobs from 7 sources simultaneously: LinkedIn, Indeed, RemoteOK, WeWorkRemotely, Dice, Greenhouse, and Lever
- **Score** every job 0–100 against your resume using Claude AI — know which roles are worth your time before you apply
- **Tailor** your resume and cover letter per job using Claude Sonnet — generates ready-to-send `.docx` files
- **Location modes** — Remote (US-filtered), Erie PA local/hybrid, or both in one run
- **Freshness filter** — limit results to jobs posted in the last 24h, 3 days, or 7 days
- **Track** application status: new → applied → interviewing → offer / rejected
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

### 3. Add your Anthropic API key

The `score` and `tailor` commands call Claude AI. Get a key at [console.anthropic.com](https://console.anthropic.com).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

To make it permanent, add the line above to your `~/.zshrc` or `~/.bashrc`.

### 4. Update your resume

Open `resume.txt` and replace the contents with your own resume in plain text. This is what Claude reads when scoring and tailoring.

---

## Launching the UI

```bash
./start.sh
```

Opens the Streamlit dashboard at **http://localhost:8501**.

Three pages:
- **Job Board** — filterable, color-coded cards (🟢 excellent · 🟡 good · 🟠 fair · 🔴 poor), expandable details, inline status updates, tailor button
- **Dashboard** — score distribution, jobs by source, pipeline funnel, top 10 matches
- **Actions** — scrape, fetch descriptions, score with AI, export CSV

---

## CLI Usage

### Scrape jobs

```bash
# Scrape all sources, remote only
python main.py scrape --keywords "sdet appium mobile" --location "Remote"

# Specific sources, last 3 days only
python main.py scrape --keywords "qa automation" --sources linkedin indeed --days-ago 3

# Erie PA local/hybrid (LinkedIn + Indeed)
python main.py scrape --keywords "qa engineer" --location "Erie, PA" --sources linkedin indeed

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
- `resume.docx` — bullets reworded to mirror the job's language, professional summary tailored to the role
- `cover_letter.docx` — specific to the role and company, with letterhead

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
python main.py clear                # delete all jobs (fresh start)
```

Valid statuses: `new` · `applied` · `interviewing` · `offer` · `rejected`

---

## Project Structure

```
job-search-automator/
├── main.py               # CLI entry point — all commands
├── start.sh              # Launch UI: ./start.sh
├── resume.txt            # Your resume in plain text (AI scoring + tailoring)
├── requirements.txt
│
├── scrapers/
│   ├── base.py           # BaseScraper with days_ago / freshness helpers
│   ├── linkedin.py       # Playwright — US remote or geographic search
│   ├── indeed.py         # Playwright — with date filter
│   ├── remoteok.py       # JSON API
│   ├── weworkremotely.py # RSS — programming jobs feed
│   ├── dice.py           # Playwright — with date filter
│   ├── greenhouse.py     # Public JSON API — 60+ curated QA-friendly companies
│   └── lever.py          # Public JSON API — 60+ curated QA-friendly companies
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
│   └── database.py       # SQLite helpers
│
├── ui.py                 # Streamlit dashboard
└── output/               # Generated .docx files (gitignored)
```

---

## Roadmap

- [x] Multi-source scraping (7 boards)
- [x] Freshness filter (24h / 3 days / 7 days)
- [x] Location modes (Remote US / Erie PA local / Both)
- [x] AI job scoring (Claude Haiku)
- [x] Status tracking and filtering
- [x] Streamlit visual dashboard
- [x] Resume tailoring per job (Claude Sonnet → .docx)
- [x] Cover letter generation (Claude Sonnet → .docx)
- [x] CSV export
- [ ] Auto-apply with Playwright (LinkedIn Easy Apply + Greenhouse forms)
- [ ] LinkedIn outreach message drafter
- [ ] Multi-user SaaS mode

---

## Notes

- `jobs.db` and `output/` are excluded from git — they contain personal data
- Scoring costs ~$0.001/job with Claude Haiku — 100 jobs ≈ $0.10
- Tailoring costs ~$0.01–0.02/job with Claude Sonnet
- LinkedIn scraping uses the unauthenticated guest search — no login required

---

## Author

**Adem Garic** — SDET / QA Engineer  
6+ years in test automation (Appium, Selenium, Jenkins, BrowserStack, AWS Device Farm)  
[LinkedIn](https://linkedin.com/in/adem-garic-sdet-qa) · [GitHub](https://github.com/ademdeniz)
