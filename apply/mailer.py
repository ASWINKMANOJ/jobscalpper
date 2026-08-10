"""
apply/mailer.py — Email sending with category-aware PDF selection.

Cover letter generation is delegated to apply/cover.py (rule-based, no LLM).
PDF selection priority:
  1. resume/aswin_{category}.pdf  — user-provided, category-specific resume
  2. item['pdf_path']             — compiled/tailored PDF from prepare step
"""

import smtplib
from email.mime.application import MIMEApplication
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

from .config import APPLICANT_NAME, GMAIL_ADDRESS, GMAIL_APP_PASSWORD, RESUME_DIR
from .cover import build_cover_letter  # noqa: F401 – re-exported for convenience


def _resolve_pdf(item: dict) -> Path:
    """
    Return the best PDF to attach for this application.

    Priority:
      1. resume/aswin_{category}.pdf  (user-provided, category-specific)
      2. item['pdf_path']             (compiled tailored PDF)
    """
    category = (item.get("category") or "").strip()
    if category:
        candidate = RESUME_DIR / f"aswin_{category}.pdf"
        if candidate.exists():
            return candidate

    fallback = Path(item.get("pdf_path") or "")
    if fallback.exists():
        return fallback

    raise RuntimeError(
        f"No PDF found for application {item.get('id')}. "
        f"Expected resume/aswin_{category}.pdf or a compiled pdf_path."
    )


def send_application_email(
    item: dict,
    pdf_path: Path | None = None,
    dry_run: bool = False,
) -> str:
    """
    Send a job application email with the tailored resume attached.

    Parameters
    ----------
    item     : application dict (from db.store or apply/cli)
    pdf_path : explicit PDF override; if None, _resolve_pdf() is used
    dry_run  : if True, return a preview string without sending
    """
    if not dry_run and not GMAIL_APP_PASSWORD:
        raise RuntimeError(
            "GMAIL_APP_PASSWORD is not set. "
            "Create a Gmail App Password and put it in .env"
        )
    if not item.get("email"):
        raise RuntimeError(f"No recipient email for application {item.get('id')}")

    # Resolve which PDF to attach
    pdf = Path(pdf_path) if pdf_path else _resolve_pdf(item)
    if not pdf.exists():
        raise RuntimeError(f"PDF not found: {pdf}")

    subject      = f"Application for {item['title']} — {APPLICANT_NAME}"
    cover_letter = item.get("cover_letter") or build_cover_letter(item)

    if dry_run:
        return (
            f"DRY-RUN  to={item['email']}"
            f"  subject={subject!r}"
            f"  pdf={pdf}"
            f"  category={item.get('category', '-')}"
        )

    message = MIMEMultipart()
    message["From"]    = GMAIL_ADDRESS
    message["To"]      = item["email"]
    message["Subject"] = subject
    message.attach(MIMEText(cover_letter, "plain", "utf-8"))

    with pdf.open("rb") as fh:
        attachment = MIMEApplication(fh.read(), _subtype="pdf")
    attachment.add_header(
        "Content-Disposition",
        "attachment",
        filename=f"{APPLICANT_NAME.replace(' ', '_')}_Resume.pdf",
    )
    message.attach(attachment)

    with smtplib.SMTP("smtp.gmail.com", 587, timeout=30) as smtp:
        smtp.starttls()
        smtp.login(GMAIL_ADDRESS, GMAIL_APP_PASSWORD)
        smtp.send_message(message)

    return f"sent  to={item['email']}  subject={subject!r}  pdf={pdf}"
