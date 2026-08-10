"""web/app.py — Flask JSON API for JobScalpper React SPA."""

import os
import sys
import threading
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

# ── Scrape state ──────────────────────────────────────────────────────────
_scrape_status: dict = {"running": False, "message": "Idle", "log": []}
_scrape_lock = threading.Lock()


def _run_scrape() -> None:
    global _scrape_status
    with _scrape_lock:
        _scrape_status = {"running": True, "message": "Scraping portals…", "log": ["Starting scrape..."]}
    try:
        from job_scalpper import main as _scrape_main
        jobs = _scrape_main()
        count = len(jobs) if jobs else 0
        with _scrape_lock:
            _scrape_status = {
                "running": False,
                "message": f"Done — {count} jobs found.",
                "log": _scrape_status.get("log", []) + [f"Completed. {count} jobs found."],
            }
    except Exception as exc:
        with _scrape_lock:
            _scrape_status = {
                "running": False,
                "message": f"Error: {exc}",
                "log": _scrape_status.get("log", []) + [f"Error: {exc}"],
            }


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
    store.init_db()
    return jsonify(store.get_stats())


# ── API: Jobs ─────────────────────────────────────────────────────────────

@app.route("/api/jobs")
def api_jobs():
    store.init_db()
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


# ── API: Applications ──────────────────────────────────────────────────────

@app.route("/api/applications")
def api_applications():
    store.init_db()
    status_filter = request.args.get("status", "")
    apps = store.load_applications(status=status_filter or None)
    counts = {
        s: len(store.load_applications(status=s))
        for s in ("pending", "approved", "sent", "rejected")
    }
    return jsonify({"applications": apps, "counts": counts})


@app.route("/api/applications/<app_id>/approve", methods=["POST"])
def api_approve(app_id: str):
    store.init_db()
    updated = store.set_status([app_id], "approved")
    if not updated:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "status": updated[0]["status"]})


@app.route("/api/applications/<app_id>/reject", methods=["POST"])
def api_reject(app_id: str):
    store.init_db()
    updated = store.set_status([app_id], "rejected")
    if not updated:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "status": updated[0]["status"]})


@app.route("/api/applications/<app_id>/send", methods=["POST"])
def api_send(app_id: str):
    store.init_db()
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
    store.init_db()
    item = store.get_application(app_id)
    if not item:
        return jsonify({"ok": False, "error": "Not found"}), 404
    return jsonify({"ok": True, "cover_letter": item.get("cover_letter", "")})


# ── API: Scrape ────────────────────────────────────────────────────────────

@app.route("/api/scrape", methods=["POST"])
def api_scrape():
    if _scrape_status["running"]:
        return jsonify({"ok": False, "message": "Scrape already running"}), 409
    t = threading.Thread(target=_run_scrape, daemon=True)
    t.start()
    return jsonify({"ok": True, "message": "Scrape started"})


@app.route("/api/scrape/status")
def api_scrape_status():
    return jsonify(_scrape_status)


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
    """Write key-value pairs to .env file."""
    lines = []
    for k, v in data.items():
        lines.append(f"{k}={v}")
    ENV_PATH.write_text("\n".join(lines) + "\n", encoding="utf-8")


KNOWN_CONFIG_KEYS = ["GMAIL_ADDRESS", "GMAIL_APP_PASSWORD", "APPLICANT_NAME"]


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
    app.run(debug=True, host="0.0.0.0", port=5000)
