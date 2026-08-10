import re
from urllib.parse import urlparse

import requests
from bs4 import BeautifulSoup

from .config import EMAIL_BLOCKLIST, HEADERS

EMAIL_RE = re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")


def _clean_text(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()


def _pick_email(emails, page_url: str):
    host = urlparse(page_url).netloc.lower()
    ranked = []
    asset_exts = (".png", ".jpg", ".jpeg", ".gif", ".svg", ".webp", ".css", ".js")
    for email in emails:
        lower = email.lower()
        if lower in EMAIL_BLOCKLIST or any(lower.endswith(ext) for ext in asset_exts):
            continue
        if any(lower.endswith(x) for x in ("@infopark.in", "@ulcyberpark.com", "@technopark.in")):
            continue
        score = 0
        local = lower.split("@", 1)[0]
        if any(k in local for k in ("career", "recruit", "hr", "jobs", "talent", "apply")):
            score += 5
        if host and host.split(".")[-2:] == lower.split("@")[-1].split(".")[-2:]:
            score += 1
        ranked.append((score, lower))
    if not ranked:
        return None
    ranked.sort(key=lambda item: (-item[0], item[1]))
    return ranked[0][1]


def _clean_company_name(val: str) -> str:
    val = _clean_text(val)
    val = re.sub(r"^(?:Company(?:\s+Name)?|Organization|Organisation)\s*[:\-]\s*", "", val, flags=re.I)
    val = val.split("GROUND FLOOR")[0].split("BUILDING")[0].strip()
    return val


def _extract_company(soup: BeautifulSoup, text: str, url: str = "", email: str = "") -> str:
    # 1. Infopark title tag: '... Jobs at Company Name | Infoparks Kerala'
    title_node = soup.find("title")
    if title_node:
        t_text = title_node.get_text(strip=True)
        m = re.search(r"Jobs\s+at\s+(.+?)(?:\s*\||\s*$)", t_text, re.I)
        if m:
            cand = _clean_company_name(m.group(1))
            if 2 < len(cand) < 100 and "job" not in cand.lower():
                return cand

    # 2. Location pattern in text: 'Location - HEX20LABS INDIA PVT LTD, Trivandrum'
    m_loc = re.search(
        r"Location\s*[:\-]\s*([A-Za-z0-9\s().,-]+?)(?:,\s*Trivandrum|,\s*Kochi|,\s*Kozhikode|\s{2,}|\n|$)",
        text,
        re.I,
    )
    if m_loc:
        cand = _clean_company_name(m_loc.group(1))
        if 2 < len(cand) < 100 and "job" not in cand.lower() and "technopark" not in cand.lower():
            return cand

    # 3. Technopark header block: text immediately following '< All Jobs' link
    all_jobs_node = soup.find(lambda e: e.name == "a" and "All Jobs" in e.get_text())
    if all_jobs_node:
        parent = all_jobs_node.find_parent(["div", "section"])
        if parent:
            lines = [l.strip() for l in parent.get_text("\n", strip=True).splitlines() if l.strip()]
            try:
                idx = lines.index("All Jobs")
                if idx + 1 < len(lines):
                    cand = _clean_company_name(lines[idx + 1])
                    if 2 < len(cand) < 100 and "job" not in cand.lower():
                        return cand
            except ValueError:
                pass

    # 4. Explicit label in description (Company: Acme...)
    m_lbl = re.search(
        r"(?:Company(?:\s+Name)?|Organisation|Organization)\s*[:\-]\s*(.+?)(?:\s{2,}|Contact|Closing|Job|Location|Experience|\n)",
        text,
        re.I,
    )
    if m_lbl:
        cand = _clean_company_name(m_lbl.group(1))
        if 2 < len(cand) < 100 and "job" not in cand.lower():
            return cand

    # 5. Selector fallback
    for selector in [".company", "[class*=company]"]:
        node = soup.select_one(selector)
        if node:
            value = _clean_company_name(node.get_text(" ", strip=True))
            if 2 < len(value) < 100 and "job" not in value.lower():
                return value

    # 6. Domain fallback from email
    if email and "@" in email:
        domain = email.split("@")[-1].split(".")[0]
        if domain not in ("gmail", "yahoo", "hotmail", "outlook"):
            return domain.capitalize()

    return ""


def _extract_description(text: str) -> str:
    patterns = [
        r"Brief Description\s*(.+?)(?:Experience Required|Educational|Contact Email|Apply|Similar Jobs|$)",
        r"Job Description\s*(.+?)(?:Experience Required|Educational|Contact Email|Apply|Similar Jobs|$)",
        r"Description\s*(.+?)(?:Experience|Qualifications|Requirements|Contact Email|Apply|$)",
    ]
    for pattern in patterns:
        match = re.search(pattern, text, re.I | re.S)
        if match:
            desc = _clean_text(match.group(1))
            if len(desc) > 80:
                return desc[:4000]
    # Fallback: middle chunk of page text
    return _clean_text(text)[:2500]


def fetch_job_details(url: str, session=None) -> dict:
    """Fetch job detail page and return email, company, description."""
    http = session or requests
    response = http.get(url, headers=HEADERS, timeout=20)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")
    text = _clean_text(soup.get_text(" ", strip=True))
    emails = sorted(set(EMAIL_RE.findall(response.text)))
    email = _pick_email(emails, url)
    company = _extract_company(soup, text, url=url, email=email or "")
    description = _extract_description(text)
    return {
        "email": email,
        "company": company,
        "description": description,
        "emails_found": emails,
    }

