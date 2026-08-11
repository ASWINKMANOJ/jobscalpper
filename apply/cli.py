"""
apply/cli.py — CLI for the application pipeline.

Sub-commands
------------
  prepare   Fetch JDs for new scraped jobs, detect category, build cover letter,
            save to DB (SQLite).  Uses pre-made aswin_{category}.pdf if present;
            falls back to LaTeX compilation.
  list      List applications in the DB queue.
  show      Show a single application with its cover letter.
  approve   Mark application(s) as approved.
  reject    Mark application(s) as rejected.
  send      Email approved applications with the category resume attached.
"""

import argparse
import shutil
import sys
from pathlib import Path

import requests

import db.store as store
from db.store import make_application_id
from .config import (
    APPLICANT_NAME,
    PENDING_DIR,
    RESUME_DIR,
    RESUME_TEMPLATE,
    SENT_DIR,
)
from .jd import fetch_job_details
from .mailer import send_application_email
from .pdf import compile_pdf
from .tailor import detect_category, matched_skills, write_tailored_tex
from .cover import build_cover_letter


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _print_item(item: dict) -> None:
    skills = item.get("matched_skills") or []
    print(f"[{item['status']}] {item['id']}")
    print(f"  {item.get('title', '-')}")
    print(f"  {item.get('company') or 'Unknown company'} | {item.get('email') or 'NO EMAIL'}")
    print(f"  category : {item.get('category', '-')}")
    print(f"  skills   : {', '.join(skills[:6]) or '-'}")
    print(f"  pdf      : {item.get('pdf_path')}")
    print(f"  url      : {item.get('url', '-')}")


# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

def cmd_prepare(args: argparse.Namespace) -> int:
    # Ensure DB exists
    store.init_db()

    new_jobs = store.get_new_jobs()
    if not new_jobs:
        print("No new jobs to prepare. Run the scraper first: python job_scalpper.py")
        return 0

    if args.limit:
        new_jobs = new_jobs[: args.limit]

    session = requests.Session()
    prepared: list[dict] = []
    skipped:  list[dict] = []

    PENDING_DIR.mkdir(parents=True, exist_ok=True)

    for index, job in enumerate(new_jobs, start=1):
        title    = job["title"]
        url      = job["url"]
        park     = job["park"]
        job_hash = job["hash"]
        app_id   = make_application_id(park, url)
        print(f"({index}/{len(new_jobs)}) {title}")

        # ── Fetch JD ──────────────────────────────────────────────────────
        try:
            details = fetch_job_details(url, session=session)
        except Exception as exc:  # noqa: BLE001
            skipped.append({"title": title, "url": url, "reason": str(exc)})
            print(f"  skip – fetch error: {exc}")
            continue

        email = details.get("email")
        if not email:
            skipped.append({"title": title, "url": url, "reason": "no usable email"})
            print("  skip – no usable hiring email")
            continue

        description = (details.get("description") or "")
        company     = (details.get("company") or "")

        # ── Category detection ────────────────────────────────────────────
        category = detect_category(title, description)

        # ── Resolve PDF ───────────────────────────────────────────────────
        category_pdf = RESUME_DIR / f"aswin_{category}.pdf"
        if category_pdf.exists():
            # Use the user-provided, category-specific PDF directly.
            pdf_path = str(category_pdf)
            tex_path = ""
            skills   = matched_skills(description, title)
            print(f"  category: {category}  (pre-made PDF)")
        else:
            # Fall back: tailor from LaTeX template and compile.
            if not RESUME_TEMPLATE.exists():
                skipped.append({
                    "title": title, "url": url,
                    "reason": f"no PDF at {category_pdf} and no resume template",
                })
                print(f"  skip – no PDF for category '{category}'")
                continue

            app_dir  = PENDING_DIR / app_id
            app_dir.mkdir(parents=True, exist_ok=True)
            tex_file = app_dir / "resume.tex"

            skills = write_tailored_tex(
                RESUME_TEMPLATE, tex_file,
                title=title, company=company, description=description,
            )
            try:
                compiled  = compile_pdf(tex_file, app_dir)
                final_pdf = app_dir / "Aswin_KM_Resume.pdf"
                if compiled != final_pdf:
                    shutil.copy2(compiled, final_pdf)
                pdf_path = str(final_pdf)
                tex_path = str(tex_file)
                print(f"  category: {category}  (compiled PDF)")
            except Exception as exc:  # noqa: BLE001
                skipped.append({"title": title, "url": url, "reason": f"pdf: {exc}"})
                print(f"  skip – PDF compilation error: {exc}")
                continue

        # ── Build cover letter & save ─────────────────────────────────────
        item: dict = {
            "id":            app_id,
            "job_hash":      job_hash,
            "status":        "pending",
            "category":      category,
            "title":         title,
            "park":          park,
            "url":           url,
            "email":         email,
            "company":       company,
            "description":   description[:600],
            "matched_skills": skills,
            "tex_path":      tex_path,
            "pdf_path":      pdf_path,
            "cover_letter":  "",
        }
        item["cover_letter"] = build_cover_letter(item)
        store.upsert_application(item)
        prepared.append(item)
        print(f"  queued  → {email} | skills={skills[:4]}")

    print(f"\nPrepared {len(prepared)} application(s).")
    print(f"Skipped  {len(skipped)}.")
    if args.show_skipped and skipped:
        print("\nSkipped details:")
        for row in skipped:
            print(f"  - {row['title']}: {row['reason']}")
    return 0


def cmd_list(args: argparse.Namespace) -> int:
    store.init_db()
    items = store.load_applications(status=args.status or None)
    if not items:
        print("No applications in queue.")
        return 0
    for item in items:
        _print_item(item)
        print()
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    store.init_db()
    item = store.get_application(args.id)
    if not item:
        print(f"Unknown application id: {args.id}")
        return 1
    _print_item(item)
    print("\n--- cover letter ---")
    print(item.get("cover_letter") or "")
    print("\n--- description excerpt ---")
    print(item.get("description") or "")
    return 0


def cmd_approve(args: argparse.Namespace) -> int:
    store.init_db()
    ids = list(args.ids)
    if args.all_pending:
        ids = [item["id"] for item in store.load_applications(status="pending")]
    if not ids:
        print("No ids to approve.")
        return 1
    updated = store.set_status(ids, "approved")
    print(f"Approved {len(updated)} application(s).")
    for item in updated:
        print(f"  {item['id']} → {item['email']}")
    return 0


def cmd_reject(args: argparse.Namespace) -> int:
    store.init_db()
    updated = store.set_status(list(args.ids), "rejected")
    print(f"Rejected {len(updated)} application(s).")
    return 0


def cmd_send(args: argparse.Namespace) -> int:
    store.init_db()
    items = store.load_applications(status="approved")
    if args.ids:
        wanted = set(args.ids)
        items  = [i for i in items if i["id"] in wanted]
    if not items:
        print("No approved applications to send.")
        return 0

    sent_count = 0
    for item in items:
        try:
            result = send_application_email(item, dry_run=args.dry_run)
            print(result)
            if not args.dry_run:
                store.set_status([item["id"]], "sent")
                # Archive a copy in sent/
                dest = SENT_DIR / item["id"]
                dest.mkdir(parents=True, exist_ok=True)
                pdf = Path(item.get("pdf_path") or "")
                if pdf.exists():
                    shutil.copy2(pdf, dest / pdf.name)
                sent_count += 1
        except Exception as exc:  # noqa: BLE001
            print(f"FAILED {item['id']}: {exc}")

    print(f"\nDone. sent={sent_count}  dry_run={args.dry_run}")
    return 0


# ---------------------------------------------------------------------------
# Parser
# ---------------------------------------------------------------------------

def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="python -m apply",
        description=(
            "Tailor resumes and send Gmail applications. "
            "Uses SQLite (jobscalpper.db) as the data store."
        ),
    )
    sub = parser.add_subparsers(dest="command", required=True)

    # prepare
    prepare = sub.add_parser(
        "prepare",
        help="Fetch JDs for new jobs, detect category, build queue"
    )
    prepare.add_argument(
        "--limit", type=int, default=0, help="Only prepare first N new jobs"
    )
    prepare.add_argument("--show-skipped", action="store_true")
    prepare.set_defaults(func=cmd_prepare)

    # list
    list_cmd = sub.add_parser("list", help="List applications in the DB")
    list_cmd.add_argument(
        "--status",
        choices=["pending", "approved", "rejected", "sent"],
        default=None,
    )
    list_cmd.set_defaults(func=cmd_list)

    # show
    show = sub.add_parser("show", help="Show one application + cover letter")
    show.add_argument("id")
    show.set_defaults(func=cmd_show)

    # approve
    approve = sub.add_parser("approve", help="Approve application(s)")
    approve.add_argument("ids", nargs="*")
    approve.add_argument("--all-pending", action="store_true")
    approve.set_defaults(func=cmd_approve)

    # reject
    reject = sub.add_parser("reject", help="Reject application(s)")
    reject.add_argument("ids", nargs="+")
    reject.set_defaults(func=cmd_reject)

    # send
    send = sub.add_parser("send", help="Send approved applications via Gmail")
    send.add_argument("ids", nargs="*")
    send.add_argument("--dry-run", action="store_true")
    send.set_defaults(func=cmd_send)

    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args   = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
