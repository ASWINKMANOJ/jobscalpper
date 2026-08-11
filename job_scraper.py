import json
import logging
import re
import time
from urllib.parse import quote, urljoin, urlparse

import requests
from bs4 import BeautifulSoup

log = logging.getLogger("jobscraper")

try:
    from db.store import init_db, upsert_job as _db_upsert_job
    _DB_AVAILABLE = True
except ImportError:
    _DB_AVAILABLE = False

HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
        "AppleWebKit/537.36 (KHTML, like Gecko) "
        "Chrome/120.0.0.0 Safari/537.36"
    )
}

# Canonical tokens after normalize_title(). Keep single-token forms where possible.
INCLUDED_KEYWORDS = [
    "spring boot",
    "software engineer",
    "software developer",
    "web developer",
    "react native",
    "reactnative",
    "kubernetes",
    "fullstack",
    "full stack",
    "frontend",
    "front end",
    "backend",
    "back end",
    "devops",
    "dev ops",
    "nodejs",
    "node js",
    "nextjs",
    "next js",
    "reactjs",
    "react js",
    "dotnet",
    "dot net",
    "aspnet",
    "asp net",
    "golang",
    "go lang",
    "express",
    "laravel",
    "python",
    "django",
    "fastapi",
    "flask",
    "docker",
    "angular",
    "typescript",
    "react",
    "cloud",
    "java",
    "node",
    "php",
    "aws",
    "mern",
    "mean",
    "vue",
    "go",
]

EXCLUDED_KEYWORDS = [
    "artificial intelligence",
    "machine learning",
    "data scientist",
    "data science",
    "deep learning",
    "computer vision",
    "prompt engineering",
    "nlp",
    "rag",
    "llm",
    "ml",
    "ai",
]

# Mid/senior+ titles to skip (junior / mid-level roles only).
SENIOR_KEYWORDS = [
    "vice president",
    "engineering manager",
    "technical lead",
    "tech lead",
    "team lead",
    "principal",
    "architect",
    "director",
    "manager",
    "senior",
    "staff",
    "lead",
    "head",
    "chief",
    "vp",
    "sr",
]

# Collapse common spellings into canonical tokens before keyword checks.
_TITLE_ALIASES = [
    (re.compile(r"\.net\b"), "dotnet"),
    (re.compile(r"\basp\.?\s*net\b"), "aspnet"),
    (re.compile(r"\bdot\s*net\b"), "dotnet"),
    (re.compile(r"\bnode\.?\s*js\b"), "nodejs"),
    (re.compile(r"\bnext\.?\s*js\b"), "nextjs"),
    (re.compile(r"\breact\.?\s*js\b"), "reactjs"),
    (re.compile(r"\breact\s*native\b"), "reactnative"),
    (re.compile(r"\bfull[\s\-]*stack\b"), "fullstack"),
    (re.compile(r"\bback[\s\-]*end\b"), "backend"),
    (re.compile(r"\bfront[\s\-]*end\b"), "frontend"),
    (re.compile(r"\bdev[\s\-]*ops\b"), "devops"),
    (re.compile(r"\bgo[\s\-]*lang\b"), "golang"),
    (re.compile(r"\bjava\s*script\b"), "javascript"),
]

PORTALS = {
    "Technopark (Trivandrum)": "https://technopark.in/job-search",
    "Infopark (Kochi)": "https://infopark.in/companies-job",
    "UL Cyberpark (Kozhikode)": "https://www.ulcyberpark.com/jobs",
}

TECHNOPARK_JOBS_API = "https://technopark.in/api/paginated-jobs"
TECHNOPARK_DETAIL = "https://technopark.in/job-details/{job_id}?job={title}"
INFOPARK_JOBS_URL = "https://infopark.in/companies-job"

MIN_PAGES = 15
MAX_PAGES = 40
OUTPUT_FILENAME = "kerala_it_parks_jobs.json"

MIN_TITLE_LEN = 6
MAX_TITLE_LEN = 180


def normalize_title(title):
    """Lowercase and unify punctuation/spellings so keyword checks stay simple."""
    text = title.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[/|_–—·,+()\[\]{}:]+", " ", text)
    for pattern, replacement in _TITLE_ALIASES:
        text = pattern.sub(replacement, text)
    text = re.sub(r"[-]+", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text


def _compile_patterns(keywords):
    ordered = sorted(set(keywords), key=len, reverse=True)
    return [re.compile(r"\b" + re.escape(kw) + r"\b") for kw in ordered]


_INCLUDED_PATTERNS = _compile_patterns(INCLUDED_KEYWORDS)
_EXCLUDED_PATTERNS = _compile_patterns(EXCLUDED_KEYWORDS)
_SENIOR_PATTERNS = _compile_patterns(SENIOR_KEYWORDS)


def is_senior_role(title):
    if not title or not isinstance(title, str):
        return False
    normalized = normalize_title(title)
    return any(pattern.search(normalized) for pattern in _SENIOR_PATTERNS)


def check_match(title):
    """Return True for matching mid/junior tech roles (no AI/ML, no senior+)."""
    if not title or not isinstance(title, str):
        return False

    normalized = normalize_title(title)

    if any(pattern.search(normalized) for pattern in _EXCLUDED_PATTERNS):
        return False
    if any(pattern.search(normalized) for pattern in _SENIOR_PATTERNS):
        return False

    return any(pattern.search(normalized) for pattern in _INCLUDED_PATTERNS)


def is_plausible_job_title(title):
    if not title or not isinstance(title, str):
        return False
    length = len(title.strip())
    return MIN_TITLE_LEN <= length <= MAX_TITLE_LEN


def normalize_job_url(href, page_url):
    """Resolve relative links and drop non-http(s) URLs."""
    if not href or not isinstance(href, str):
        return None

    href = href.strip()
    if href.startswith(("#", "mailto:", "javascript:", "tel:")):
        return None

    absolute = urljoin(page_url, href)
    parsed = urlparse(absolute)
    if parsed.scheme not in ("http", "https") or not parsed.netloc:
        return None

    return absolute


def _dedupe_jobs(jobs):
    unique = {}
    for job in jobs:
        unique.setdefault(job["URL"], job)
    return list(unique.values())


def extract_jobs_from_html(html, park_name, page_url):
    """Fallback: scan anchor text for matching job titles."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for a_tag in soup.find_all("a", href=True):
        title_text = a_tag.get_text(" ", strip=True)
        if not is_plausible_job_title(title_text) or not check_match(title_text):
            continue

        link = normalize_job_url(a_tag["href"], page_url)
        if not link:
            continue

        jobs.append({"Park": park_name, "Title": title_text, "URL": link})

    return _dedupe_jobs(jobs)


def extract_infopark_jobs(html, park_name, page_url):
    """Infopark puts the title in a table cell; the link text is just 'Details'."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        title_text = cells[1].get_text(" ", strip=True)
        if not is_plausible_job_title(title_text) or not check_match(title_text):
            continue

        link_tag = row.find("a", href=True)
        link = normalize_job_url(link_tag["href"], page_url) if link_tag else None
        if not link:
            continue

        jobs.append({"Park": park_name, "Title": title_text, "URL": link})

    return _dedupe_jobs(jobs)


def extract_ulcyberpark_jobs(html, park_name, page_url):
    """UL Cyberpark: title in first cell, details URL in the last cell."""
    soup = BeautifulSoup(html, "html.parser")
    jobs = []

    for row in soup.select("table tr"):
        cells = row.find_all("td")
        if len(cells) < 2:
            continue

        title_tag = cells[0].find("a")
        title_text = (
            title_tag.get_text(" ", strip=True)
            if title_tag
            else cells[0].get_text(" ", strip=True).split("closing date")[0].strip()
        )
        if not is_plausible_job_title(title_text) or not check_match(title_text):
            continue

        details = None
        for a_tag in row.find_all("a", href=True):
            href = a_tag["href"]
            if "job_vacancy" in href or "View Details" in a_tag.get_text(" ", strip=True):
                details = normalize_job_url(href, page_url)
                if details:
                    break

        if not details:
            continue

        jobs.append({"Park": park_name, "Title": title_text, "URL": details})

    return _dedupe_jobs(jobs)


def scrape_technopark(park_name, session=None, min_pages=MIN_PAGES, max_pages=MAX_PAGES):
    """Technopark is an Inertia app; listings come from a JSON API."""
    http = session or requests
    jobs = []
    page = 1
    pages_needed = min_pages

    while page <= pages_needed and page <= max_pages:
        log.info("  page %d/%d...", page, pages_needed)
        response = http.get(
            TECHNOPARK_JOBS_API,
            params={"page": page, "search": "", "type": ""},
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        payload = response.json()
        rows = payload.get("data") or []

        api_last = payload.get("last_page") or page
        pages_needed = max(api_last, min_pages)

        for row in rows:
            title_text = (row.get("job_title") or "").strip()
            job_id = row.get("id")
            if not job_id or not is_plausible_job_title(title_text):
                continue
            if not check_match(title_text):
                continue

            link = TECHNOPARK_DETAIL.format(job_id=job_id, title=quote(title_text))
            jobs.append({"Park": park_name, "Title": title_text, "URL": link})

        page += 1
        if page <= pages_needed:
            time.sleep(0.5)  # rate-limit: be polite to the server

    return _dedupe_jobs(jobs)


def scrape_infopark(park_name, session=None, min_pages=MIN_PAGES, max_pages=MAX_PAGES):
    """Walk Infopark pagination (companies-job?page=N), at least min_pages."""
    http = session or requests
    jobs = []
    page = 1
    pages_needed = min_pages
    empty_streak = 0

    while page <= pages_needed and page <= max_pages:
        log.info("  page %d/%d...", page, pages_needed)
        response = http.get(
            INFOPARK_JOBS_URL,
            params={"page": page},
            headers=HEADERS,
            timeout=15,
        )
        response.raise_for_status()
        page_jobs = extract_infopark_jobs(response.text, park_name, response.url)
        jobs.extend(page_jobs)

        soup = BeautifulSoup(response.text, "html.parser")
        page_numbers = []
        for a_tag in soup.find_all("a", href=True):
            if "companies-job" in a_tag["href"] and a_tag.get_text(strip=True).isdigit():
                page_numbers.append(int(a_tag.get_text(strip=True)))
        if page_numbers:
            pages_needed = max(max(page_numbers), min_pages)

        row_count = len(soup.select("table tr"))
        if row_count <= 1:
            empty_streak += 1
            if empty_streak >= 2 and page >= min_pages:
                break
        else:
            empty_streak = 0

        page += 1
        if page <= pages_needed:
            time.sleep(0.5)  # rate-limit: be polite to the server

    return _dedupe_jobs(jobs)


def scrape_portal(park_name, url, session=None, min_pages=MIN_PAGES, max_pages=MAX_PAGES):
    log.info("Scraping %s...", park_name)
    http = session or requests

    try:
        if "technopark.in" in url:
            return scrape_technopark(park_name, session=http,
                                     min_pages=min_pages, max_pages=max_pages)
        if "infopark.in" in url:
            return scrape_infopark(park_name, session=http,
                                   min_pages=min_pages, max_pages=max_pages)

        response = http.get(url, headers=HEADERS, timeout=15)
        response.raise_for_status()
        html = response.text

        if "ulcyberpark.com" in url:
            return extract_ulcyberpark_jobs(html, park_name, url)
        return extract_jobs_from_html(html, park_name, url)

    except (requests.exceptions.RequestException, ValueError, KeyError) as e:
        log.error("Error fetching data from %s: %s", park_name, e)
        return []


def write_jobs_json(jobs, output_filename=OUTPUT_FILENAME):
    """Always refresh/overwrite the output file with the latest scrape."""
    with open(output_filename, "w", encoding="utf-8") as f:
        json.dump(jobs, f, indent=4, ensure_ascii=False)
    return output_filename


def main(portals=None, output_filename=OUTPUT_FILENAME, session=None,
         min_pages=MIN_PAGES, max_pages=MAX_PAGES):
    if _DB_AVAILABLE:
        init_db()

    portals = portals if portals is not None else PORTALS
    all_matched_jobs = []

    for name, url in portals.items():
        matched_jobs = scrape_portal(name, url, session=session,
                                     min_pages=min_pages, max_pages=max_pages)
        all_matched_jobs.extend(matched_jobs)

        # Persist to DB (hash-based dedup)
        if _DB_AVAILABLE:
            for job in matched_jobs:
                _db_upsert_job(job["Park"], job["Title"], job["URL"])

        log.info("Found %d suitable roles at %s.", len(matched_jobs), name)

    write_jobs_json(all_matched_jobs, output_filename)

    if not all_matched_jobs:
        log.info("No exact matches found today. Wrote empty list to '%s'.", output_filename)
        return []

    log.info("-" * 60)
    for idx, job in enumerate(all_matched_jobs, start=1):
        log.info("%d. %s", idx, job["Title"])
        log.info("   Location: %s", job["Park"])
        log.info("   Link:     %s", job["URL"])
        log.info("-" * 60)

    log.info("Success! Refreshed '%s' with %d jobs.", output_filename, len(all_matched_jobs))
    return all_matched_jobs


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(message)s",
    )
    main()
