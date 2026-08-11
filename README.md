# JobScalpper

> Automated job scraper, application manager, and email sender for Kerala IT Parks — with a React dashboard.

JobScalpper watches job boards across **Infopark**, **Technopark**, and **Cyberpark**, filters postings by your skill set, tailors your resume and cover letter for each role, and sends applications via Gmail — all from a clean web dashboard.

---

## Features

- **Scrape** — Crawls Kerala IT park portals for fresh job postings and deduplicates by URL
- **Filter** — Keyword-based relevance filtering (frontend, backend, DevOps, etc.)
- **Tailor** — Generates a custom cover letter and optionally compiles a tailored LaTeX resume per application
- **Manage** — Web dashboard to review, approve, reject, and send applications
- **Send** — Delivers applications via Gmail SMTP with a tailored PDF resume attached
- **Dashboard** — React + Vite SPA with real-time scan output, animated stats, and credential management

---

## Tech Stack

| Layer | Technology |
|---|---|
| Scraper | Python · `requests` · `BeautifulSoup4` |
| Database | SQLite (via `db/store.py`) |
| API | Flask · Flask-CORS |
| Frontend | React 18 · Vite · Framer Motion · React Router |
| Email | Gmail SMTP · Python `smtplib` |
| Resume | LaTeX · Tectonic compiler |

---

## Project Structure

```
jobscalpper/
├── cli_entry.py           # Single-command launcher (jobscalpper up|scrape|…)
├── pyproject.toml         # Package config — registers `jobscalpper` command
├── job_scalpper.py        # Core scraper — scrapes all three IT park portals
├── apply/
│   ├── cli.py             # Application pipeline CLI (prepare/list/approve/send)
│   ├── config.py          # Env config and paths
│   ├── cover.py           # Cover letter generator
│   ├── jd.py              # Job description parser
│   ├── mailer.py          # Gmail SMTP sender
│   ├── pdf.py             # PDF compilation via Tectonic
│   └── tailor.py          # Resume tailoring logic
├── db/
│   ├── schema.sql         # SQLite schema
│   └── store.py           # Data access layer (jobs + applications)
├── web/
│   ├── app.py             # Flask JSON API (12 endpoints)
│   └── frontend/          # React + Vite SPA
│       └── src/
│           ├── pages/
│           │   ├── Dashboard.jsx    # Stats + recent jobs
│           │   ├── Jobs.jsx         # Job board with search/filter
│           │   ├── Applications.jsx # Approve/reject/send workflow
│           │   ├── Scan.jsx         # Real-time scrape terminal
│           │   └── Settings.jsx     # Credentials manager
│           └── components/
│               └── Toast.jsx
├── resume/                # LaTeX resume templates and compiled PDFs
├── applications/          # Generated application packages (gitignored)
├── .env.example           # Credential template
└── requirements.txt
```

---

## Quick Start

### 1. Clone and set up

```bash
git clone https://github.com/your-username/jobscalpper.git
cd jobscalpper
python -m venv venv
source venv/bin/activate        # Windows: venv\Scripts\activate
pip install -e .                # installs deps + registers `jobscalpper` command
```

### 2. Configure credentials

Copy the example env file and fill in your values:

```bash
cp .env.example .env
```

```env
GMAIL_ADDRESS=you@gmail.com
GMAIL_APP_PASSWORD=xxxx xxxx xxxx xxxx   # 16-char Google App Password
APPLICANT_NAME=Your Name
```

> **Getting a Gmail App Password:**
> 1. Enable 2-Step Verification on your Google account
> 2. Go to [myaccount.google.com/apppasswords](https://myaccount.google.com/apppasswords)
> 3. Create an app password for "JobScalpper" and paste the 16-character code above

You can also manage credentials through the **Settings** page in the web dashboard.

### 3. Launch everything

```bash
jobscalpper up
```

That's it! This starts both the Flask API (`:5000`) and the Vite dev server (`:5173`).

Open [http://localhost:5173](http://localhost:5173) in your browser.

#### Other commands

```bash
jobscalpper up --prod     # Build frontend → serve through Flask on :5000
jobscalpper scrape        # Run scraper only (no servers)
jobscalpper prepare       # Prepare applications from new scraped jobs
jobscalpper status        # Show DB stats (jobs, pending, approved, sent)
```


---

## Dashboard Pages

| Page | Description |
|---|---|
| **Dashboard** | Animated stat counters, live scrape status, recent jobs feed |
| **Job Board** | Searchable, filterable table of all scraped jobs with pagination |
| **Applications** | Tabbed view (Pending / Approved / Sent / Rejected) with inline actions |
| **Scan** | Terminal-style real-time output while scraping; start/monitor jobs |
| **Settings** | Add/edit Gmail credentials; test SMTP connection; onboarding guide |

---

## API Endpoints

The Flask backend exposes a REST JSON API at `http://localhost:5000`:

| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stats` | Dashboard stat counts |
| `GET` | `/api/jobs` | Paginated jobs (`?q=`, `?park=`, `?page=`) |
| `GET` | `/api/applications` | Applications list (`?status=`) |
| `POST` | `/api/applications/:id/approve` | Approve an application |
| `POST` | `/api/applications/:id/reject` | Reject an application |
| `POST` | `/api/applications/:id/send` | Send email for an approved application |
| `GET` | `/api/applications/:id/cover_letter` | Fetch generated cover letter |
| `POST` | `/api/scrape` | Start a scrape job |
| `GET` | `/api/scrape/status` | Poll scrape status + log output |
| `GET` | `/api/config` | Read `.env` config (password masked) |
| `POST` | `/api/config` | Write new credentials to `.env` |
| `POST` | `/api/config/test` | Test Gmail SMTP connection |

---

## CLI Usage

```bash
# Start everything (API + dashboard)
jobscalpper up

# Scrape job portals and store results
jobscalpper scrape

# Prepare applications from new scraped jobs
jobscalpper prepare

# Check database stats
jobscalpper status

# Or run modules directly
python job_scalpper.py          # scraper only
python -m apply prepare         # application pipeline
```

---

## Production Build

To serve the React app through Flask directly (single server):

```bash
jobscalpper up --prod          # Builds frontend + serves at http://localhost:5000
```


---

## Resume Setup

Place category-specific PDF resumes in the `resume/` directory following this naming convention:

```
resume/aswin_backend.pdf
resume/aswin_frontend.pdf
resume/aswin_devops.pdf
```

The mailer picks the best match based on the application category. If no category-specific PDF exists, it falls back to the compiled `pdf_path` generated by Tectonic.

---

## Requirements

- Python 3.11+
- Node.js 18+
- A Gmail account with an App Password (2FA must be enabled)
- *(Optional)* [Tectonic](https://tectonic-typesetting.github.io/) for compiling LaTeX resumes

---

## License

MIT
