"""Database package for jobscalpper."""
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
]
