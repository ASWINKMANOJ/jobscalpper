#!/usr/bin/env python3
"""
cli_entry.py — Single-command launcher for JobScraper.

Usage:
    jobscraper up            Start Flask API + Vite dev server
    jobscraper up --prod     Build frontend and serve through Flask only
    jobscraper scrape        Run job scraper
    jobscraper prepare       Prepare applications from new scraped jobs
    jobscraper status        Show DB stats
"""

import argparse
import logging
import os
import signal
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent
VENV_PYTHON = ROOT / "venv" / "bin" / "python"
FRONTEND_DIR = ROOT / "web" / "frontend"

log = logging.getLogger("jobscraper.cli")


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _python() -> str:
    """Return the venv Python path, falling back to the current interpreter."""
    if VENV_PYTHON.exists():
        return str(VENV_PYTHON)
    return sys.executable


def _ensure_frontend_deps() -> None:
    """Run npm install if node_modules is missing."""
    if not (FRONTEND_DIR / "node_modules").exists():
        log.info("Installing frontend dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(FRONTEND_DIR),
            check=True,
        )


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_up(args: argparse.Namespace) -> int:
    """Start Flask API and optionally the Vite dev server."""
    processes: list[subprocess.Popen] = []

    def _shutdown(signum=None, frame=None):
        log.info("\nShutting down...")
        for proc in processes:
            if proc.poll() is None:
                proc.terminate()
        for proc in processes:
            try:
                proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                proc.kill()
        sys.exit(0)

    signal.signal(signal.SIGINT, _shutdown)
    signal.signal(signal.SIGTERM, _shutdown)

    if args.prod:
        # Production mode: build frontend, then serve everything through Flask
        _ensure_frontend_deps()
        log.info("Building frontend for production...")
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(FRONTEND_DIR),
            check=True,
        )
        log.info("")
        log.info("╔══════════════════════════════════════════════════╗")
        log.info("║  JobScraper (production)                        ║")
        log.info("║  → http://localhost:5000                        ║")
        log.info("║  Press Ctrl+C to stop                           ║")
        log.info("╚══════════════════════════════════════════════════╝")
        log.info("")

        flask_proc = subprocess.Popen(
            [_python(), "web/app.py"],
            cwd=str(ROOT),
        )
        processes.append(flask_proc)
        flask_proc.wait()
        return flask_proc.returncode

    # Dev mode: start Flask + Vite in parallel
    _ensure_frontend_deps()

    log.info("")
    log.info("╔══════════════════════════════════════════════════╗")
    log.info("║  JobScraper (dev mode)                          ║")
    log.info("║  → API:       http://localhost:5000              ║")
    log.info("║  → Dashboard: http://localhost:5173              ║")
    log.info("║  Press Ctrl+C to stop both servers               ║")
    log.info("╚══════════════════════════════════════════════════╝")
    log.info("")

    flask_proc = subprocess.Popen(
        [_python(), "web/app.py"],
        cwd=str(ROOT),
    )
    processes.append(flask_proc)

    vite_proc = subprocess.Popen(
        ["npm", "run", "dev"],
        cwd=str(FRONTEND_DIR),
    )
    processes.append(vite_proc)

    # Wait for either process to exit
    try:
        while True:
            for proc in processes:
                if proc.poll() is not None:
                    _shutdown()
            time.sleep(0.5)
    except KeyboardInterrupt:
        _shutdown()

    return 0


def cmd_scrape(args: argparse.Namespace) -> int:
    """Run the job scraper."""
    # Import here so we only load dependencies when needed
    sys.path.insert(0, str(ROOT))
    try:
        from job_scraper import main as scrape_main
    except ImportError:
        from job_scalpper import main as scrape_main
    scrape_main()
    return 0


def cmd_prepare(args: argparse.Namespace) -> int:
    """Prepare applications from new scraped jobs."""
    sys.path.insert(0, str(ROOT))
    from apply.cli import main as apply_main
    argv = ["prepare"]
    if args.limit:
        argv.extend(["--limit", str(args.limit)])
    if args.show_skipped:
        argv.append("--show-skipped")
    return apply_main(argv)


def cmd_status(args: argparse.Namespace) -> int:
    """Show DB stats."""
    sys.path.insert(0, str(ROOT))
    from db.store import init_db, get_stats
    init_db()
    stats = get_stats()

    print("")
    print("╔══════════════════════════════════════════════════╗")
    print("║  JobScraper — Status                            ║")
    print("╠══════════════════════════════════════════════════╣")
    print(f"║  Total jobs scraped:  {stats['total_jobs']:<26}║")
    print(f"║  New (no application):{stats['new_jobs']:<26}║")
    print(f"║  Scraped today:       {stats['today_scraped']:<26}║")
    print("║──────────────────────────────────────────────────║")
    print(f"║  Pending:             {stats['pending']:<26}║")
    print(f"║  Approved:            {stats['approved']:<26}║")
    print(f"║  Sent:                {stats['sent']:<26}║")
    print(f"║  Rejected:            {stats['rejected']:<26}║")
    print("╚══════════════════════════════════════════════════╝")
    print("")
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="jobscraper",
        description="JobScraper — Automated job scraper & application manager for Kerala IT Parks",
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # up
    up_parser = sub.add_parser("up", help="Start the full stack (API + dashboard)")
    up_parser.add_argument(
        "--prod", action="store_true",
        help="Build frontend and serve through Flask (single server)",
    )
    up_parser.set_defaults(func=cmd_up)

    # scrape
    scrape_parser = sub.add_parser("scrape", help="Run job scraper")
    scrape_parser.set_defaults(func=cmd_scrape)

    # prepare
    prepare_parser = sub.add_parser("prepare", help="Prepare applications from new jobs")
    prepare_parser.add_argument("--limit", type=int, default=0)
    prepare_parser.add_argument("--show-skipped", action="store_true")
    prepare_parser.set_defaults(func=cmd_prepare)

    # status
    status_parser = sub.add_parser("status", help="Show database stats")
    status_parser.set_defaults(func=cmd_status)

    return parser


def main(argv: list[str] | None = None) -> int:
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
