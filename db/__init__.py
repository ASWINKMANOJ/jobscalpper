"""Database package for jobscraper."""
from .store import (
    init_db,
    job_hash,
    upsert_job,
    get_new_jobs,
    get_jobs_paginated,
    get_parks,
    upsert_application,
    load_applications,
    get_application,
    set_status,
    get_stats,
    get_application_counts,
    make_application_id,
)

__all__ = [
    "init_db",
    "job_hash",
    "upsert_job",
    "get_new_jobs",
    "get_jobs_paginated",
    "get_parks",
    "upsert_application",
    "load_applications",
    "get_application",
    "set_status",
    "get_stats",
    "get_application_counts",
    "make_application_id",
]
