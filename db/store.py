"""
db/store.py — SQLite data access layer.

Deduplication strategy: every job is identified by
  hash = SHA-256(park.lower() + "|" + url.strip())[:16]
Re-scraping the same URL only increments seen_count; it never creates a duplicate row.
"""

import hashlib
import json
import re
import sqlite3
from contextlib import contextmanager
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlparse

_ROOT = Path(__file__).resolve().parent.parent
DB_PATH = _ROOT / "jobscalpper.db"
_SCHEMA = Path(__file__).parent / "schema.sql"


# ---------------------------------------------------------------------------
# Connection helpers
# ---------------------------------------------------------------------------

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


@contextmanager
def _conn():
    con = sqlite3.connect(DB_PATH)
    con.row_factory = sqlite3.Row
    con.execute("PRAGMA journal_mode=WAL")
    con.execute("PRAGMA foreign_keys=ON")
    try:
        yield con
        con.commit()
    except Exception:
        con.rollback()
        raise
    finally:
        con.close()


def init_db() -> None:
    """Create tables if they do not exist. Safe to call multiple times."""
    schema = _SCHEMA.read_text(encoding="utf-8")
    with _conn() as con:
        con.executescript(schema)


# ---------------------------------------------------------------------------
# Hash helper
# ---------------------------------------------------------------------------

def job_hash(park: str, url: str) -> str:
    """Stable 16-char hex ID for a (park, url) pair."""
    key = f"{park.lower().strip()}|{url.strip()}"
    return hashlib.sha256(key.encode()).hexdigest()[:16]


# ---------------------------------------------------------------------------
# Jobs
# ---------------------------------------------------------------------------

def upsert_job(park: str, title: str, url: str) -> str:
    """
    Insert a new job or increment seen_count if the URL already exists.
    Returns the job hash.
    """
    h = job_hash(park, url)
    with _conn() as con:
        con.execute(
            """
            INSERT INTO jobs (hash, park, title, url, scraped_at, seen_count)
            VALUES (?, ?, ?, ?, ?, 1)
            ON CONFLICT(hash) DO UPDATE SET
                seen_count  = seen_count + 1,
                scraped_at  = excluded.scraped_at,
                title       = excluded.title
            """,
            (h, park, title, url, _now()),
        )
    return h


def get_new_jobs() -> list[dict]:
    """Return jobs that have no application record yet."""
    with _conn() as con:
        rows = con.execute(
            """
            SELECT j.* FROM jobs j
            WHERE NOT EXISTS (
                SELECT 1 FROM applications a WHERE a.job_hash = j.hash
            )
            ORDER BY j.scraped_at DESC
            """
        ).fetchall()
    return [dict(r) for r in rows]


def get_jobs_paginated(
    park: str = "",
    search: str = "",
    page: int = 1,
    per_page: int = 50,
) -> tuple[list[dict], int]:
    """Paginated job listing with optional park/search filters."""
    offset = (page - 1) * per_page
    conditions: list[str] = []
    params: list = []

    if park:
        conditions.append("j.park = ?")
        params.append(park)
    if search:
        conditions.append("(j.title LIKE ? OR j.url LIKE ?)")
        params.extend([f"%{search}%", f"%{search}%"])

    where = ("WHERE " + " AND ".join(conditions)) if conditions else ""

    with _conn() as con:
        total: int = con.execute(
            f"SELECT COUNT(*) FROM jobs j {where}", params
        ).fetchone()[0]
        rows = con.execute(
            f"""
            SELECT j.*,
                   a.status   AS app_status,
                   a.id       AS app_id,
                   a.category AS app_category
            FROM jobs j
            LEFT JOIN applications a ON a.job_hash = j.hash
            {where}
            ORDER BY j.scraped_at DESC
            LIMIT ? OFFSET ?
            """,
            params + [per_page, offset],
        ).fetchall()

    return [dict(r) for r in rows], total


def get_parks() -> list[str]:
    """Return distinct park names for filter dropdowns."""
    with _conn() as con:
        rows = con.execute(
            "SELECT DISTINCT park FROM jobs ORDER BY park"
        ).fetchall()
    return [r[0] for r in rows]


# ---------------------------------------------------------------------------
# Applications
# ---------------------------------------------------------------------------

def _deserialize(item: dict) -> dict:
    """Convert JSON-string fields back to Python objects."""
    raw = item.get("matched_skills")
    if isinstance(raw, str):
        try:
            item["matched_skills"] = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            item["matched_skills"] = []
    return item


def upsert_application(data: dict) -> None:
    """
    Insert a new application or update an existing one.
    Preserves status/timestamps if already approved/sent/rejected.
    """
    with _conn() as con:
        con.execute(
            """
            INSERT INTO applications (
                id, job_hash, status, category, title, park, url,
                email, company, description, matched_skills,
                cover_letter, tex_path, pdf_path, created_at
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            ON CONFLICT(id) DO UPDATE SET
                category       = excluded.category,
                title          = excluded.title,
                park           = excluded.park,
                url            = excluded.url,
                email          = excluded.email,
                company        = excluded.company,
                description    = excluded.description,
                matched_skills = excluded.matched_skills,
                cover_letter   = excluded.cover_letter,
                tex_path       = excluded.tex_path,
                pdf_path       = excluded.pdf_path,
                -- Only reset status when it was still 'pending'
                status = CASE
                    WHEN applications.status IN ('approved', 'sent', 'rejected')
                    THEN applications.status
                    ELSE excluded.status
                END
            """,
            (
                data["id"],
                data.get("job_hash"),
                data.get("status", "pending"),
                data.get("category", ""),
                data.get("title", ""),
                data.get("park", ""),
                data.get("url", ""),
                data.get("email", ""),
                data.get("company", ""),
                data.get("description", ""),
                json.dumps(data.get("matched_skills") or []),
                data.get("cover_letter", ""),
                data.get("tex_path", ""),
                data.get("pdf_path", ""),
                data.get("created_at") or _now(),
            ),
        )


def load_applications(status: str | None = None) -> list[dict]:
    with _conn() as con:
        if status:
            rows = con.execute(
                "SELECT * FROM applications WHERE status = ? ORDER BY created_at DESC",
                (status,),
            ).fetchall()
        else:
            rows = con.execute(
                "SELECT * FROM applications ORDER BY created_at DESC"
            ).fetchall()
    return [_deserialize(dict(r)) for r in rows]


def get_application(app_id: str) -> dict | None:
    with _conn() as con:
        row = con.execute(
            "SELECT * FROM applications WHERE id = ?", (app_id,)
        ).fetchone()
    return _deserialize(dict(row)) if row else None


def set_status(app_ids: list[str], status: str) -> list[dict]:
    """Update status (and the matching timestamp) for a list of application IDs."""
    _VALID_STATUSES = {"pending", "approved", "rejected", "sent"}
    if status not in _VALID_STATUSES:
        raise ValueError(f"Invalid status {status!r}; must be one of {_VALID_STATUSES}")

    # Map status → (SQL template, needs timestamp param).
    # Column names are literal strings here — never interpolated from user input.
    _STATUS_SQL = {
        "approved": ("UPDATE applications SET status = ?, approved_at = ? WHERE id = ?", True),
        "rejected": ("UPDATE applications SET status = ?, rejected_at = ? WHERE id = ?", True),
        "sent":     ("UPDATE applications SET status = ?, sent_at = ? WHERE id = ?",     True),
        "pending":  ("UPDATE applications SET status = ?, created_at = ? WHERE id = ?",  True),
    }

    sql, needs_ts = _STATUS_SQL[status]
    now = _now()
    updated: list[dict] = []
    with _conn() as con:
        for app_id in app_ids:
            if needs_ts:
                con.execute(sql, (status, now, app_id))
            else:
                con.execute(
                    "UPDATE applications SET status = ? WHERE id = ?",
                    (status, app_id),
                )
            row = con.execute(
                "SELECT * FROM applications WHERE id = ?", (app_id,)
            ).fetchone()
            if row:
                updated.append(_deserialize(dict(row)))
    return updated


# ---------------------------------------------------------------------------
# Dashboard stats
# ---------------------------------------------------------------------------

def get_stats() -> dict:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    with _conn() as con:
        total_jobs    = con.execute("SELECT COUNT(*) FROM jobs").fetchone()[0]
        new_jobs      = con.execute(
            "SELECT COUNT(*) FROM jobs j WHERE NOT EXISTS "
            "(SELECT 1 FROM applications a WHERE a.job_hash = j.hash)"
        ).fetchone()[0]
        today_scraped = con.execute(
            "SELECT COUNT(*) FROM jobs WHERE scraped_at LIKE ?",
            (f"{today}%",),
        ).fetchone()[0]
        pending       = con.execute(
            "SELECT COUNT(*) FROM applications WHERE status='pending'"
        ).fetchone()[0]
        approved      = con.execute(
            "SELECT COUNT(*) FROM applications WHERE status='approved'"
        ).fetchone()[0]
        sent          = con.execute(
            "SELECT COUNT(*) FROM applications WHERE status='sent'"
        ).fetchone()[0]
        rejected      = con.execute(
            "SELECT COUNT(*) FROM applications WHERE status='rejected'"
        ).fetchone()[0]
    return {
        "total_jobs":    total_jobs,
        "new_jobs":      new_jobs,
        "today_scraped": today_scraped,
        "pending":       pending,
        "approved":      approved,
        "sent":          sent,
        "rejected":      rejected,
    }


# ---------------------------------------------------------------------------
# Application counts (single query)
# ---------------------------------------------------------------------------

def get_application_counts() -> dict:
    """Return status counts in a single GROUP BY query."""
    counts = {"pending": 0, "approved": 0, "sent": 0, "rejected": 0}
    with _conn() as con:
        rows = con.execute(
            "SELECT status, COUNT(*) FROM applications GROUP BY status"
        ).fetchall()
    for row in rows:
        if row[0] in counts:
            counts[row[0]] = row[1]
    return counts


# ---------------------------------------------------------------------------
# Application ID helper (moved from apply/queue.py)
# ---------------------------------------------------------------------------

def make_application_id(park: str, url: str) -> str:
    """Generate a stable, slug-style application ID from park + URL."""
    slug = re.sub(r"[^a-z0-9]+", "-", park.lower()).strip("-")[:16]
    for pattern in (
        r"/job-details/(\d+)",
        r"/company-jobs/details/\d+/(\d+)",
        r"job_id=(\d+)",
        r"/(\d+)/?$",
    ):
        match = re.search(pattern, url)
        if match:
            return f"{slug}-{match.group(1)}"
    tail = re.sub(r"[^a-zA-Z0-9]+", "-", urlparse(url).path)[-36:].strip("-")
    return f"{slug}-{tail or 'job'}"
