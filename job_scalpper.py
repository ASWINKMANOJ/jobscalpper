"""
job_scalpper.py — Backwards-compatibility wrapper for job_scraper.py.
"""

from job_scraper import *  # noqa: F403

if __name__ == "__main__":
    import logging
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    main()  # noqa: F405
