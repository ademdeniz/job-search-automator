# Job Search Automator

> **© 2026 Adem Garic — All Rights Reserved.**
> View-only. No use, copying, or distribution without written permission. See [LICENSE](LICENSE).

---

A personal job search tool that scrapes 9 job boards, scores every posting against your resume using Claude AI, tailors your resume and cover letter per role, and tracks your full application pipeline — all from a clean Streamlit UI or the terminal.

Built with Python + Claude AI (Anthropic). Fully role-agnostic — works for any field: engineering, design, HR, product, etc.

---

## Features

- **Scrape** jobs from 9 sources simultaneously: LinkedIn, Indeed, RemoteOK, WeWorkRemotely, Dice, Greenhouse, Lever, Himalayas, and Jobspresso
- **Score** every job 0–100 against your resume using Claude AI — see matched skills, missing skills, and suggested keywords per job, colour-coded on every card. Includes an AI salary estimate when the job posting doesn't list one.
- **Company red-flag signals** — one-click analysis per job: layoffs, Glassdoor rating, financial distress, executive churn. Powered by Claude Haiku, cached to DB so you only pay once per company.
- **Tailor** your resume and cover letter per job using Claude Sonnet — fetches company context from their website, generates ready-to-send `.docx` and `.pdf` files
- **Voice pass** — cover letter is rewritten to match your natural writing style using a sample you provide
- **ATS validation** — checks generated resume for formatting issues that break ATS parsers
- **Location modes** — US Remote, World Remote, Local/Hybrid (any city, state, or zip), or both in one run
- **Freshness filter** — limit results to jobs posted in the last 24h, 3 days, or 7 days
- **Fuzzy deduplication** — same job posted across multiple boards is stored once, not three times
- **Resume slots** — maintain multiple resume versions (e.g. Senior IC, Manager track, Startup) and switch the active slot from the Profile page. Scorer and tailor always use the active slot.
- **Track** your full application pipeline: applied → interviewing → offer
- **My Applications** — dedicated tracker with inline stage advancement, notes, and permanent removal
- **Google Calendar integration** — one-click "Add to Calendar" for interview scheduling (no OAuth required)
- **Interview prep generator** — Claude Sonnet generates 10 role-specific questions with difficulty rating (easy / medium / hard), a tailored answer using your real experience, and 2 follow-up questions per question. Downloadable as `.docx` or `.pdf`
- **Follow-up email drafter** — auto-drafts a short, human-sounding follow-up for applications with no response after 7+ days
- **Application analytics** — response rate by source, score distribution for responded vs. not, pipeline funnel
- **Rejection pattern analysis** — Claude Haiku scans all your rejected applications, surfaces recurring skill gaps and patterns, and gives you a concrete action plan
- **Auto-scrape scheduler** — runs the full scrape → fetch → score pipeline automatically in the background on a configurable interval (2–24 hours). Sends an HTML email alert via Gmail when high-score new jobs appear.
- **Role-agnostic** — scorer and tailor adapt to any domain via your profile (title + target role)
- **Profile page** — manage your resume, contact info, target role, and writing sample from the UI
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
| PDF output | LibreOffice (optional, free) |
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

### 3. (Optional) Install LibreOffice for PDF output

PDF download buttons appear automatically if LibreOffice is installed. If not, `.docx` still works fine.

**Mac:**
```bash
brew install --cask libreoffice
```

**Linux:**
```bash
sudo apt install libreoffice
```

### 4. Add your Anthropic API key

The `score` and `tailor` commands call Claude AI. Get a key at [console.anthropic.com](https://console.anthropic.com).

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

Replace `sk-ant-...` with your actual key.

### 5. Launch the UI and set up your profile

```bash
./start.sh
```

This opens the dashboard at **http://localhost:8501** and starts the background scheduler alongside it.

**Before doing anything else, go to the 👤 Profile page** and fill in:
- Your name, email, LinkedIn, GitHub
- Professional title (e.g. `Senior QA Engineer`) — appears in your cover letter signature
- Target role / keywords (e.g. `SDET test automation Appium`) — used as default search terms
- Your full resume as plain text (you can create multiple named slots for different role types)
- A writing sample — a paragraph you wrote naturally (LinkedIn post, email, anything). Claude uses this to match your voice in cover letters.

Hit **Save Profile**. This creates `profile.json` locally (gitignored — stays on your machine).
Scoring and tailoring will not work until the profile is saved.

---

## Launching the UI

```bash
./start.sh
```

Opens the Streamlit dashboard at **http://localhost:8501**.

Five pages:

- **Job Board** — filterable, colour-coded cards (🟢 excellent · 🟡 good · 🟠 fair · 🔴 poor), expandable details with skill chips, inline status updates, tailor button with ATS check badge and `.docx`/`.pdf` downloads
- **Dashboard** — score distribution, jobs by source, pipeline funnel, top 10 matches, application analytics, rejection pattern analysis
- **Actions** — scrape, fetch descriptions, score with AI, auto-scrape scheduler with email alerts, export CSV
- **My Applications** — tracks applied/interviewing/offer jobs with one-click stage advancement, notes, interview prep, follow-up email drafter, and Google Calendar integration
- **Profile** — manage multiple resume slots, contact info, and writing sample

---

## UI Workflow — Step by Step

### 1. Set up your profile
Go to **Profile** and fill in your name, email, LinkedIn, GitHub, professional title, target role/keywords, paste your full resume as plain text (add multiple named slots for different role types), and optionally paste a writing sample. Hit **Save Profile**. Nothing works until this is done.

### 2. Scrape jobs
Go to **Actions → Scrape Jobs**. Choose your sources, location mode (US Remote / World Remote / Local), and freshness window (1 / 3 / 7 days). Hit **Run Scrape**. New jobs appear on the Job Board immediately.

### 3. Fetch full descriptions
Scraped job cards often contain only a short preview — not the full posting.

Go to **Actions → Fetch Descriptions**. This visits each job URL with a headless browser and pulls the full description. Supports LinkedIn, Indeed, and Dice.

> **If a description is still missing or truncated:** open the job card on the Job Board, click the job link to open the original posting, copy the full description, paste it into the **"Paste full job description"** field, and hit **Save Description**.

### 4. Score jobs
Scoring runs **automatically after every scrape** — no manual step needed. Claude Haiku reads your resume and each job description and returns a 0–100 match score. Each job card then shows:
- **✅ green chips** — skills from your resume that match the job
- **❌ red chips** — skills the job wants that you're missing
- **💡 amber chips** — keywords to weave into your resume or cover letter before applying
- **Salary estimate** — AI-estimated range shown as `~$X - $Y (est.)` when the posting doesn't list one

Jobs without a description are skipped — fetch or paste descriptions first. You can also trigger scoring manually from **Actions → Score Jobs**.

### 5. Review and decide
On the **Job Board**, expand any card to see the full description, skill breakdown, and AI analysis. Use the status dropdown to mark jobs as `applied`, `rejected`, or leave them as `new`.

### 6. Tailor your resume and cover letter
From a job card on the Job Board, hit **Tailor Resume + Cover Letter**. Claude Sonnet:
1. Rewrites your resume bullets to mirror the job's language using your exact metrics and project names
2. Generates a cover letter with a hook-first opener and company-specific context (fetched from their website)
3. Runs a voice pass to rewrite the cover letter in your natural writing style

Output: `.docx` and `.pdf` (if LibreOffice is installed) download buttons appear directly in the card.

### 7. Track your pipeline
Jobs you mark as `applied` move to **My Applications**. From there you can:
- Advance them through `applied → interviewing → offer` with one click
- Add notes (saved to DB, survives refresh)
- Schedule interviews with a pre-filled Google Calendar link
- Generate interview prep (10 role-specific Q&As, downloadable as `.docx`/`.pdf`)
- Draft a follow-up email (appears automatically after 7 days with no response)

---

## Auto-Scrape Scheduler

`start.sh` launches a background scheduler alongside the UI. It runs the full scrape → fetch → score pipeline automatically on a configurable interval and emails you when high-score new jobs appear.

### Configure it

Go to **Actions → ⏰ Auto-Scrape Scheduler** in the UI and set:

| Field | Description |
|---|---|
| Enable scheduler | Toggle on/off |
| Run every | 2 / 4 / 6 / 8 / 12 / 24 hours |
| Notify when score ≥ | Only alert for jobs above this threshold (default 70) |
| Your Gmail address | The address that sends the alert |
| App password | A Gmail App Password — **not** your real password |
| Send alerts to | Where to receive alerts (can be same as sender) |

Hit **Save Scheduler Settings**, then the scheduler picks up the new config within the hour.

### Gmail App Password setup

You need a [Gmail App Password](https://myaccount.google.com/apppasswords) — Google's 16-character password for third-party SMTP access.

1. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
2. Sign in and select **Mail** + your device
3. Copy the 16-character password (format: `xxxx xxxx xxxx xxxx`)
4. Paste it into the **App password** field in the UI — never use your real Gmail password

> **2-Step Verification must be enabled on your Google account** for App Passwords to appear.

### What the email looks like

You'll receive an HTML email showing each new high-score job with its score badge, title, company, location, and a direct link that opens the Job Board in the app.

### Limitations

The scheduler runs as a background process on your machine — it requires `start.sh` to be running. If your laptop is off or the app is closed, it won't fire.

---

## CLI Usage

### Scrape jobs

```bash
# US remote only
python main.py scrape --keywords "sdet appium mobile" --location "Remote US"

# Worldwide remote
python main.py scrape --keywords "qa automation" --location "Remote"

# Local / hybrid by city or zip
python main.py scrape --keywords "qa engineer" --location "Erie, PA" --sources linkedin indeed

# Specific sources, last 3 days only
python main.py scrape --keywords "qa automation" --sources linkedin indeed --days-ago 3

# Limit results per source
python main.py scrape --keywords "selenium" --max-results 25
```

Available sources: `linkedin` `indeed` `remoteok` `weworkremotely` `dice` `greenhouse` `lever` `himalayas` `jobspresso`

Freshness: `--days-ago 1` (24h) · `--days-ago 3` · `--days-ago 7`

### Fetch full descriptions

```bash
python main.py fetch                   # all supported sources
python main.py fetch --source linkedin # LinkedIn only
```

### Score jobs against your resume

```bash
python main.py score        # score all unscored jobs
python main.py score --all  # re-score everything
python main.py score --id 42
```

Each job gets a score (0–100), match level, matched skills, missing skills, and suggested keywords.

### Tailor resume + cover letter

```bash
python main.py tailor 42
```

Generates two `.docx` files in `output/<job-slug>/`:
- `resume.docx` — bullets reworded to mirror the job's language using your exact metrics and project names
- `cover_letter.docx` — hook-first opener, company context from their website, voice-matched to your writing sample

> Job must have a description. Paste one in the UI or run `fetch` first.

### List and filter jobs

```bash
python main.py list                        # all jobs
python main.py list --sort-by score        # highest score first
python main.py list --min-score 70         # strong matches only
python main.py list --status new
python main.py list --source greenhouse
python main.py list --keyword "appium"
python main.py list --remote
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

Valid statuses: `new` · `applied` · `interviewing` · `offer` · `rejected`

---

## Project Structure

```
job-search-automator/
├── main.py               # CLI entry point — all commands
├── start.sh              # Launch UI + background scheduler: ./start.sh
├── scheduler.py          # Background scrape → fetch → score pipeline + email alerts
├── profile.json          # Your profile — created on first save in UI (gitignored)
├── requirements.txt
│
├── scrapers/
│   ├── base.py           # BaseScraper — freshness, US-location filtering, title matching
│   ├── linkedin.py       # Playwright — also handles description fetching for LinkedIn/Indeed/Dice
│   ├── indeed.py
│   ├── remoteok.py       # JSON API
│   ├── weworkremotely.py # RSS feed
│   ├── dice.py
│   ├── greenhouse.py     # Public JSON API
│   ├── lever.py          # Public JSON API
│   ├── himalayas.py
│   └── jobspresso.py
│
├── scorer/
│   ├── job_scorer.py     # Claude Haiku — batch scoring, skill matching, keyword suggestions, salary estimate
│   └── company_signals.py # Claude Haiku — company health red-flag analysis (layoffs, Glassdoor, churn)
│
├── tailor/
│   └── resume_tailor.py  # Claude Sonnet — tailored resume + cover letter → .docx
│
├── models/
│   └── job.py            # Job dataclass
│
├── storage/
│   ├── database.py       # SQLite helpers and migrations
│   └── profile.py        # Profile load/save
│
├── pages/
│   ├── utils.py          # Shared constants, helpers, PDF conversion
│   ├── job_board.py      # 📋 Job Board page
│   ├── dashboard.py      # 📊 Dashboard page
│   ├── actions.py        # 🔧 Actions page
│   ├── my_applications.py # 📁 My Applications page
│   └── profile.py        # 👤 Profile page
│
├── ui.py                 # Streamlit entry point — sidebar + page routing
└── output/               # Generated .docx/.pdf files (gitignored)
```

---

## Roadmap

- [x] Multi-source scraping (9 boards)
- [x] Freshness filter (24h / 3 days / 7 days)
- [x] Location modes — US Remote, World Remote, Local/Hybrid
- [x] Role-agnostic — adapts to any field via profile
- [x] Fuzzy deduplication across sources
- [x] AI job scoring (Claude Haiku) with matched/missing skills + keyword suggestions
- [x] Resume tailoring per job (Claude Sonnet → .docx + .pdf)
- [x] Cover letter generation with company context
- [x] Cover letter voice pass (writing sample calibration)
- [x] ATS formatting validation
- [x] My Applications pipeline tracker (applied → interviewing → offer)
- [x] Notes per application (persisted to DB)
- [x] Google Calendar integration (zero-OAuth interview scheduling)
- [x] Interview prep generator v2 — difficulty levels (easy/medium/hard), tailored answers, 2 follow-up questions per Q, .docx + .pdf download
- [x] Follow-up email drafter (7+ days, no response)
- [x] Application analytics (response rate by source, score distribution)
- [x] Profile page — manage resume, contact info, writing sample from UI
- [x] Multiple resume slots — switch active slot per role type from the Profile page
- [x] PDF output via LibreOffice (free, offline)
- [x] CSV export
- [x] Salary estimate — AI-estimated range injected at scoring time when posting doesn't list one
- [x] Company red-flag signals — layoffs, Glassdoor, financial distress, churn (Claude Haiku, cached)
- [x] Auto-scrape scheduler — background pipeline on configurable interval, HTML email alerts via Gmail
- [x] Rejection pattern analysis — Claude Haiku surfaces skill gaps and patterns from rejected applications
- [ ] Auto-apply (LinkedIn Easy Apply + Greenhouse forms)
- [ ] Job market pulse — trending roles, in-demand skills from scraped data over time

---

## Notes

- `jobs.db` and `output/` are excluded from git — they contain personal data
- `profile.json` is excluded from git — it contains your resume and contact info
- Scoring costs ~$0.001/job with Claude Haiku — 100 jobs ≈ $0.10
- Tailoring costs ~$0.01–0.02/job with Claude Sonnet
- LinkedIn scraping uses unauthenticated guest search — no login required
- PDF output requires LibreOffice installed locally — free, no API key

---

## Author

**Adem Garic** — SDET / QA Engineer
6+ years in test automation (Appium, Selenium, Jenkins, BrowserStack, AWS Device Farm)
[LinkedIn](https://linkedin.com/in/adem-garic-sdet-qa) · [GitHub](https://github.com/ademdeniz)
