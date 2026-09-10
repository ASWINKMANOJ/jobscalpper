"""web/app.py — Flask JSON API for JobScalpper React SPA."""

import logging
import os
import sys
import tempfile
import threading
from logging.handlers import RotatingFileHandler
from pathlib import Path

from flask import Flask, jsonify, request, send_from_directory
from flask_cors import CORS

# Make root importable when running from web/
_ROOT = Path(__file__).resolve().parent.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import db.store as store

app = Flask(__name__, static_folder="frontend/dist", static_url_path="")
CORS(app)  # Allow Vite dev server to reach Flask

ENV_PATH = _ROOT / ".env"
LOG_DIR = _ROOT / "logs"

# ── File logging ──────────────────────────────────────────────────────────
LOG_DIR.mkdir(exist_ok=True)
_file_handler = RotatingFileHandler(
    LOG_DIR / "jobscraper.log",
    maxBytes=2 * 1024 * 1024,  # 2 MB per file
    backupCount=3,
    encoding="utf-8",
)
_file_handler.setFormatter(logging.Formatter(
    "%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S",
))
logging.getLogger("jobscraper").addHandler(_file_handler)
logging.getLogger("jobscraper").setLevel(logging.INFO)

# ── One-time DB init (lazy) ───────────────────────────────────────────────
_db_initialized = False
_db_init_lock = threading.Lock()


@app.before_request
def _ensure_db():
    global _db_initialized
    if _db_initialized:
        return
    with _db_init_lock:
        if not _db_initialized:
            store.init_db()
            _db_initialized = True


# ── Scrape state ──────────────────────────────────────────────────────────
_scrape_status: dict = {"running": False, "message": "Idle", "log": []}
_scrape_lock = threading.Lock()

_MAX_LOG_LINES = 500  # prevent unbounded memory growth


class _LogCapture(logging.Handler):
    """Logging handler that appends records to the scrape log list."""

    def emit(self, record):
        msg = self.format(record)
        if msg.strip():
            with _scrape_lock:
                log_list = _scrape_status.setdefault("log", [])
                log_list.append(msg)
                # Ring-buffer: drop oldest lines when cap is exceeded
                if len(log_list) > _MAX_LOG_LINES:
                    del log_list[: len(log_list) - _MAX_LOG_LINES]


def _run_scrape() -> None:
    # Mutate in-place (thread-safe); never reassign _scrape_status itself.
    with _scrape_lock:
        _scrape_status.clear()
        _scrape_status.update({"running": True, "message": "Scraping portals…", "log": ["Starting scrape..."]})

    scrape_logger = logging.getLogger("jobscraper")
    handler = _LogCapture()
    handler.setFormatter(logging.Formatter("%(message)s"))
    scrape_logger.addHandler(handler)
    scrape_logger.setLevel(logging.INFO)

    try:
        from job_scraper import main as _scrape_main

        # Read configurable page count from .env
        env = _read_env()
        scrape_pages = int(env.get("SCRAPE_PAGES", "15") or "15")
        scrape_pages = max(1, min(scrape_pages, 100))  # clamp to sane range

        jobs = _scrape_main(min_pages=scrape_pages, max_pages=max(scrape_pages, 40))
        count = len(jobs) if jobs else 0
        with _scrape_lock:
            _scrape_status["running"] = False
            _scrape_status["message"] = f"Done — {count} jobs found."
            _scrape_status["log"].append(f"Completed. {count} jobs found.")
    except Exception as exc:
        with _scrape_lock:
            _scrape_status["running"] = False
            _scrape_status["message"] = f"Error: {exc}"
            _scrape_status["log"].append(f"Error: {exc}")
    finally:
        scrape_logger.removeHandler(handler)


# ── SPA catch-all (serve React app) ──────────────────────────────────────

@app.route("/", defaults={"path": ""})
@app.route("/<path:path>")
def serve_spa(path):
    dist_dir = Path(__file__).parent / "frontend" / "dist"
    if path and (dist_dir / path).exists():
        return send_from_directory(str(dist_dir), path)
    index = dist_dir / "index.html"
    if index.exists():
        return send_from_directory(str(dist_dir), "index.html")
    return jsonify({"error": "Frontend not built. Run: cd web/frontend && npm run build"}), 503


# ── API: Stats / Dashboard ─────────────────────────────────────────────────

@app.route("/api/stats")
def api_stats():
    return jsonify(store.get_stats())


# ── API: Jobs ─────────────────────────────────────────────────────────────

@app.route("/api/jobs")
def api_jobs():
    page        = request.args.get("page", 1, type=int)
    park_filter = request.args.get("park", "")
    search      = request.args.get("q", "")
    per_page    = request.args.get("per_page", 50, type=int)

    jobs_list, total = store.get_jobs_paginated(
        park=park_filter, search=search, page=page, per_page=per_page
    )
    parks       = store.get_parks()
    total_pages = max(1, (total + per_page - 1) // per_page)

    return jsonify({
        "jobs": jobs_list,
        "total": total,
        "page": page,
        "per_page": per_page,
        "total_pages": total_pages,
        "parks": parks,
    })


@app.route("/api/jobs/unapplied")
def api_jobs_unapplied():
    limit = request.args.get("limit", 100, type=int)
    unapplied_jobs = store.get_unapplied_jobs(limit=limit)
    return jsonify({"jobs": unapplied_jobs, "count": len(unapplied_jobs)})


@app.route("/api/jobs/<job_hash>/prepare", methods=["POST"])
def api_job_prepare(job_hash: str):
    job = store.get_job_by_hash(job_hash)
    if not job:
        return jsonify({"ok": False, "error": "Job not found"}), 404
    try:
        from apply.cli import prepare_single_job
        app_item = prepare_single_job(job)
        return jsonify({"ok": True, "application": app_item})
    except ValueError as exc:
        return jsonify({"ok": False, "error": str(exc)}), 400
    except Exception as exc:
        return jsonify({"ok": False, "error": f"Unexpected error: {exc}"}), 500


@app.route("/api/jobs/prepare-all", methods=["POST"])
def api_jobs_prepare_all():
    new_jobs = store.get_new_jobs()
    if not new_jobs:
        return jsonify({"ok": True, "prepared_count": 0, "message": "No new jobs to prepare"})

    from apply.cli import prepare_single_job
    prepared = []
    failed = []
    for j in new_jobs:
        try:
            item = prepare_single_job(j)
            prepared.append(item["id"])
        except Exception as exc:
            failed.append({"hash": j["hash"], "title": j["title"], "error": str(exc)})

    return jsonify({
        "ok": True,
        "prepared_count": len(prepared),
        "failed_count": len(failed),
        "failed": failed,
    })


# ── API: Applications ──────────────────────────────────────────────────────

@app.route("/api/applications")
def api_applications():
    status_filter = request.args.get("status", "")
    apps = store.load_applications(status=status_filter or None)
    counts = store.get_application_counts()
    return jsonify({"applications": apps, "counts": counts})


@app.route("/api/applications/<app_id>/approve", methods=["POST"])
def api_approve(app_id: str):
    updated = store.set_status([app_id], "approved")
    if not updated:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "status": updated[0]["status"]})


@app.route("/api/applications/<app_id>/reject", methods=["POST"])
def api_reject(app_id: str):
    updated = store.set_status([app_id], "rejected")
    if not updated:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "status": updated[0]["status"]})


@app.route("/api/applications/<app_id>/send", methods=["POST"])
def api_send(app_id: str):
    data    = request.get_json(silent=True) or {}
    dry_run = bool(data.get("dry_run", False))
    item    = store.get_application(app_id)
    if not item:
        return jsonify({"ok": False, "error": "Not found"}), 404
    if item["status"] != "approved" and not dry_run:
        return jsonify({"ok": False, "error": "Application is not approved"}), 400
    try:
        from apply.mailer import send_application_email
        result = send_application_email(item, dry_run=dry_run)
        if not dry_run:
            store.set_status([app_id], "sent")
        return jsonify({"ok": True, "result": result})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


@app.route("/api/applications/<app_id>/cover_letter")
def api_cover_letter(app_id: str):
    item = store.get_application(app_id)
    if not item:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "cover_letter": item.get("cover_letter", "")})


# ── API: Batch Application Actions ─────────────────────────────────────────

@app.route("/api/applications/batch/approve", methods=["POST"])
def api_batch_approve():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"ok": False, "error": "No IDs provided"}), 400
    updated = store.set_status(ids, "approved")
    return jsonify({"ok": True, "count": len(updated)})


@app.route("/api/applications/batch/reject", methods=["POST"])
def api_batch_reject():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    if not ids:
        return jsonify({"ok": False, "error": "No IDs provided"}), 400
    updated = store.set_status(ids, "rejected")
    return jsonify({"ok": True, "count": len(updated)})


@app.route("/api/applications/batch/send", methods=["POST"])
def api_batch_send():
    data = request.get_json(silent=True) or {}
    ids = data.get("ids", [])
    dry_run = bool(data.get("dry_run", False))
    if not ids:
        return jsonify({"ok": False, "error": "No IDs provided"}), 400

    from apply.mailer import send_application_email
    sent = []
    failed = []
    for app_id in ids:
        item = store.get_application(app_id)
        if not item:
            failed.append({"id": app_id, "error": "Not found"})
            continue
        if item["status"] != "approved" and not dry_run:
            failed.append({"id": app_id, "error": "Not approved"})
            continue
        try:
            result = send_application_email(item, dry_run=dry_run)
            if not dry_run:
                store.set_status([app_id], "sent")
            sent.append(app_id)
        except Exception as exc:
            failed.append({"id": app_id, "error": str(exc)})

    return jsonify({
        "ok": True,
        "sent_count": len(sent),
        "failed_count": len(failed),
        "failed": failed,
    })


@app.route("/api/applications/approve-all-pending", methods=["POST"])
def api_approve_all_pending():
    pending = store.load_applications(status="pending")
    if not pending:
        return jsonify({"ok": True, "count": 0, "message": "No pending applications"})
    ids = [a["id"] for a in pending]
    updated = store.set_status(ids, "approved")
    return jsonify({"ok": True, "count": len(updated)})


@app.route("/api/applications/send-all-approved", methods=["POST"])
def api_send_all_approved():
    approved = store.load_applications(status="approved")
    if not approved:
        return jsonify({"ok": True, "sent_count": 0, "message": "No approved applications"})

    from apply.mailer import send_application_email
    sent = []
    failed = []
    for item in approved:
        try:
            send_application_email(item, dry_run=False)
            store.set_status([item["id"]], "sent")
            sent.append(item["id"])
        except Exception as exc:
            failed.append({"id": item["id"], "error": str(exc)})

    return jsonify({
        "ok": True,
        "sent_count": len(sent),
        "failed_count": len(failed),
        "failed": failed,
    })


# ── API: Scrape ────────────────────────────────────────────────────────────

@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    with _scrape_lock:
        if _scrape_status["running"]:
            return jsonify({"ok": False, "message": "Scrape already running"}), 409
    t = threading.Thread(target=_run_scrape, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Scrape started"})


@app.route("/api/scrape/status")
def api_scrape_status():
    with _scrape_lock:
        status_copy = dict(_scrape_status)
        # Deep-copy the log list to avoid mutation during serialisation
        status_copy["log"] = list(_scrape_status.get("log", []))
    return jsonify(status_copy)


# ── API: Config (.env management) ─────────────────────────────────────────

def _read_env() -> dict:
    """Read .env file and return a dict of key-value pairs."""
    env = {}
    if ENV_PATH.exists():
        for line in ENV_PATH.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, _, v = line.partition("=")
                env[k.strip()] = v.strip()
    return env


def _write_env(data: dict) -> None:
    """Write key-value pairs to .env file atomically (temp + rename)."""
    content = "\n".join(f"{k}={v}" for k, v in data.items()) + "\n"
    # Write to a temp file in the same directory, then atomically replace.
    fd, tmp_path = tempfile.mkstemp(dir=str(ENV_PATH.parent), suffix=".env.tmp")
    try:
        os.write(fd, content.encode("utf-8"))
        os.close(fd)
        os.replace(tmp_path, str(ENV_PATH))
    except Exception:
        os.close(fd) if not os.get_inheritable(fd) else None
        if os.path.exists(tmp_path):
            os.unlink(tmp_path)
        raise


KNOWN_CONFIG_KEYS = [
    "GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "APPLICANT_NAME",
    "SCRAPE_PAGES", "RESUME_PREFIX",
]


@app.route("/api/config", methods=["GET"])
def api_config_get():
    env = _read_env()
    result = {}
    for key in KNOWN_CONFIG_KEYS:
        val = env.get(key, "")
        if key == "GMAIL_APP_PASSWORD" and val:
            result[key] = "••••••••••••••••"  # mask it
        else:
            result[key] = val
    result["has_credentials"] = bool(env.get("GMAIL_ADDRESS") and env.get("GMAIL_APP_PASSWORD"))
    return jsonify(result)


@app.route("/api/config", methods=["POST"])
def api_config_post():
    data = request.get_json(silent=True) or {}
    env  = _read_env()
    for key in KNOWN_CONFIG_KEYS:
        if key in data and data[key] not in ("", "••••••••••••••••", None):
            env[key] = data[key]
    _write_env(env)
    # Reload env vars into current process
    from dotenv import load_dotenv
    load_dotenv(ENV_PATH, override=True)
    return jsonify({"ok": True, "message": "Configuration saved."})


@app.route("/api/config/test", methods=["POST"])
def api_config_test():
    """Send a dry-run test to verify SMTP credentials."""
    env = _read_env()
    if not env.get("GMAIL_ADDRESS") or not env.get("GMAIL_APP_PASSWORD"):
        return jsonify({"ok": False, "error": "Credentials not configured"}), 400
    try:
        import smtplib
        with smtplib.SMTP("smtp.gmail.com", 587, timeout=10) as smtp:
            smtp.starttls()
            smtp.login(env["GMAIL_ADDRESS"], env["GMAIL_APP_PASSWORD"])
        return jsonify({"ok": True, "message": "SMTP connection successful!"})
    except Exception as exc:
        return jsonify({"ok": False, "error": str(exc)}), 500


# ── Entry point ───────────────────────────────────────────────────────────

if __name__ == "__main__":
    store.init_db()
    _db_initialized = True
    app.run(debug=True, host="0.0.0.0", port=5000)
