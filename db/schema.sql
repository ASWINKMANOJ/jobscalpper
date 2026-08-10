-- JobScalpper SQLite Schema
-- Hash-based deduplication: job identity = SHA256(park|url)[:16]

CREATE TABLE IF NOT EXISTS jobs (
    hash        TEXT PRIMARY KEY,          -- SHA-256(park|url)[:16], stable across runs
    park        TEXT NOT NULL,
    title       TEXT NOT NULL,
    url         TEXT NOT NULL UNIQUE,
    scraped_at  TEXT NOT NULL,             -- ISO-8601 UTC
    seen_count  INTEGER NOT NULL DEFAULT 1 -- increments on every re-scrape
);

CREATE INDEX IF NOT EXISTS idx_jobs_park       ON jobs (park);
CREATE INDEX IF NOT EXISTS idx_jobs_scraped_at ON jobs (scraped_at DESC);

CREATE TABLE IF NOT EXISTS applications (
    id              TEXT PRIMARY KEY,       -- slug from make_application_id()
    job_hash        TEXT REFERENCES jobs(hash) ON DELETE SET NULL,
    status          TEXT NOT NULL DEFAULT 'pending', -- pending|approved|rejected|sent
    category        TEXT NOT NULL DEFAULT '',        -- backend_php|backend_go|...
    title           TEXT NOT NULL DEFAULT '',
    park            TEXT NOT NULL DEFAULT '',
    url             TEXT NOT NULL DEFAULT '',
    email           TEXT NOT NULL DEFAULT '',
    company         TEXT NOT NULL DEFAULT '',
    description     TEXT NOT NULL DEFAULT '',        -- first 600 chars of JD
    matched_skills  TEXT NOT NULL DEFAULT '[]',      -- JSON array
    cover_letter    TEXT NOT NULL DEFAULT '',
    tex_path        TEXT NOT NULL DEFAULT '',
    pdf_path        TEXT NOT NULL DEFAULT '',
    created_at      TEXT,
    approved_at     TEXT,
    rejected_at     TEXT,
    sent_at         TEXT
);

CREATE INDEX IF NOT EXISTS idx_apps_status   ON applications (status);
CREATE INDEX IF NOT EXISTS idx_apps_job_hash ON applications (job_hash);
