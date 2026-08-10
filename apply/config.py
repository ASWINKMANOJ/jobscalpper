import os
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parent.parent
load_dotenv(ROOT / ".env")

JOBS_JSON = ROOT / "kerala_it_parks_jobs.json"
RESUME_TEMPLATE = ROOT / "resume" / "resume.tex"
RESUME_DIR = ROOT / "resume"
APPLICATIONS_DIR = ROOT / "applications"
PENDING_DIR = APPLICATIONS_DIR / "pending"
SENT_DIR = APPLICATIONS_DIR / "sent"
QUEUE_PATH = APPLICATIONS_DIR / "queue.json"  # kept for backward compat
DB_PATH = ROOT / "jobscalpper.db"

GMAIL_ADDRESS = os.getenv("GMAIL_ADDRESS", "aswinkmanoj101@gmail.com")
GMAIL_APP_PASSWORD = os.getenv("GMAIL_APP_PASSWORD", "")
APPLICANT_NAME = os.getenv("APPLICANT_NAME", "Aswin K M")

# Ignore park-wide / generic inboxes that are not hiring contacts.
EMAIL_BLOCKLIST = {
    "info@infopark.in",
    "info@ulcyberpark.com",
    "info@technopark.in",
    "noreply@technopark.in",
    "no-reply@technopark.in",
}

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

TECTONIC_BIN = ROOT / "bin" / "tectonic"
