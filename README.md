# Job Search Automator

A personal CLI tool that scrapes job boards, scores each posting against your resume using AI, and tracks your application pipeline — all from the terminal.

Built with Python + Claude AI (Anthropic). No browser needed for scraping; no GUI required.

---

## Features

- **Scrape** jobs from RemoteOK, Indeed, and LinkedIn simultaneously
- **Score** every job 0–100 against your resume using Claude AI — know which roles are worth your time before you apply
- **Track** application status (new → applied → interviewing → offer / rejected)
- **Filter & sort** by score, remote, source, keyword, or status
- **Export** to CSV for spreadsheet workflows
- **Open** any job URL directly in your browser from the CLI

---

## Tech Stack

| Layer | Tool |
|---|---|
| Scraping (static/RSS) | `requests` |
| AI scoring | `anthropic` (Claude Haiku) |
| Storage | SQLite via `sqlite3` |
| CLI | `argparse` |

> Playwright will be added in a future phase for automated form-filling and job applications.

---

## Setup

### 1. Clone the repo

```bash
git clone https://github.com/YOUR_USERNAME/job-search-automator.git
cd job-search-automator
```

### 2. Install dependencies

```bash
pip install -r requirements.txt
```

### 3. Add your Anthropic API key

The `score` command calls Claude AI. Get a free key at [console.anthropic.com](https://console.anthropic.com).

```bash
export ANTHROPIC_API_KEY=sk-ant-...
```

To make it permanent, add the line above to your `~/.zshrc` or `~/.bashrc`.

### 4. Update your resume

Open `resume.txt` and replace the contents with your own resume in plain text. This is what Claude reads when scoring jobs against your profile.

---

## Usage

### Scrape jobs

```bash
# Scrape all sources with keywords
python main.py scrape --keywords "sdet appium mobile" --location "Remote"

# Scrape a specific source only
python main.py scrape --keywords "qa automation" --sources remoteok indeed

# Limit results per source
python main.py scrape --keywords "selenium python" --max-results 25
```

Available sources: `remoteok`, `indeed`, `linkedin`

---

### Score jobs against your resume

```bash
# Score all new (unscored) jobs
python main.py score

# Re-score everything
python main.py score --all

# Score a specific job by ID
python main.py score --id 42
```

Each job gets:
- A **score** (0–100)
- A **match level** (poor / fair / good / excellent)
- **Matched skills** found in the job description
- **Missing skills** you may want to address
- **Suggested keywords** to use in your cover letter

---

### List and filter jobs

```bash
# List all jobs
python main.py list

# Sort by AI score (highest first)
python main.py list --sort-by score

# Only show strong matches
python main.py list --min-score 70 --sort-by score

# Filter by status
python main.py list --status new

# Filter by source and remote
python main.py list --source remoteok --remote

# Search by keyword in title/company/description
python main.py list --keyword "ios"
```

---

### View a job in detail

```bash
python main.py show 42
```

Shows all fields including full description, AI score, matched/missing skills, and the URL.

---

### Open a job in your browser

```bash
python main.py open 42
```

---

### Update application status

```bash
python main.py status 42 applied
```

Valid statuses: `new` · `applied` · `interviewing` · `offer` · `rejected`

---

### Export to CSV

```bash
# Export all jobs
python main.py export

# Export with filters
python main.py export --status applied --output applied_jobs.csv
```

---

### Stats

```bash
python main.py stats
```

Shows totals by source, by status, number of scored jobs, and average match score.

---

## Project Structure

```
job-search-automator/
├── main.py               # CLI entry point — all commands live here
├── resume.txt            # Your resume in plain text (used for AI scoring)
├── requirements.txt
│
├── scrapers/
│   ├── base.py           # Abstract BaseScraper
│   ├── remoteok.py       # RemoteOK JSON API
│   ├── indeed.py         # Indeed RSS feed
│   └── linkedin.py       # LinkedIn guest API
│
├── scorer/
│   └── job_scorer.py     # Claude AI scoring logic
│
├── models/
│   └── job.py            # Job dataclass
│
└── storage/
    └── database.py       # SQLite helpers (init, save, query, update)
```

---

## Roadmap

- [x] Multi-source scraping (RemoteOK, Indeed, LinkedIn)
- [x] AI job scoring via Claude API
- [x] Status tracking and filtering
- [x] CSV export
- [ ] Resume tailoring per job description (Claude API)
- [ ] Cover letter generation (Claude API)
- [ ] Playwright-based automated applications (LinkedIn Easy Apply, Greenhouse, Lever)
- [ ] LinkedIn outreach message drafter
- [ ] Wellfound / WeWorkRemotely scrapers

---

## Notes

- `jobs.db` is excluded from git (see `.gitignore`) — it contains your personal job data
- Scoring costs ~$0.001 per job using Claude Haiku — scoring 100 jobs costs roughly $0.10
- LinkedIn scraping uses their unauthenticated guest API; it may break if LinkedIn changes their HTML structure
  
## Author
- Adem Garic — SDET / QA Engineer 4+ years in mobile and web test automation (Appium, Selenium, Jenkins, BrowserStack) [LinkedIn](https://www.linkedin.com/in/adem-garic-sdet-qa/) · [GitHub](https://github.com/ademdeniz)
  
