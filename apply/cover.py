"""
apply/cover.py — Smart, rule-based cover letter generator.

All placeholders are filled from data already present in the application item.
No LLM API calls. No external network requests.

Template tokens
---------------
{{salutation}}       — "Hiring Team" or "Hiring Team at <Company>"
{{role}}             — job title
{{at_company}}       — " at <Company>" or ""
{{primary_skills}}   — top 3 matched skills, comma-joined
{{highlight_project}}— project name chosen by category
{{project_detail}}   — one-line project achievement sentence
{{park_line}}        — sourcing sentence for the park portal
"""

from .config import APPLICANT_NAME, GMAIL_ADDRESS

# ---------------------------------------------------------------------------
# Category → project highlight mapping
# ---------------------------------------------------------------------------

_PROJECT_HIGHLIGHTS: dict[str, tuple[str, str]] = {
    "backend_php": (
        "Skill India",
        "built a dual-module course management platform with Laravel and MySQL, "
        "implementing role-based authentication, CRUD workflows, and a real-time admin dashboard",
    ),
    "backend_go": (
        "RideSync",
        "architected a high-performance ride-hailing backend in Go achieving sub-2 ms "
        "ride matching across 10,000+ simultaneous WebSocket streams with zero data races",
    ),
    "backend_java": (
        "SeatForge",
        "built a distributed seat-reservation system using Spring Boot and Kafka, "
        "achieving 3× throughput and sustaining 5,000 RPS under Kubernetes",
    ),
    "backend_python": (
        "RideSync",
        "designed high-performance asynchronous backend services, reducing database I/O "
        "overhead by 99.8 % through batch-processing workers and clean RESTful API design",
    ),
    "devops": (
        "RideSync",
        "deployed cloud-native services on AWS with Docker, Kubernetes, and Redis, "
        "reducing infrastructure overhead while maintaining high availability",
    ),
    "fullstack": (
        "Skill India",
        "delivered a full-stack web application with Laravel, MySQL, and a modern "
        "frontend, handling authentication, real-time data, and admin analytics end-to-end",
    ),
}

_DEFAULT_HIGHLIGHT = _PROJECT_HIGHLIGHTS["backend_php"]

# ---------------------------------------------------------------------------
# Park sourcing sentences
# ---------------------------------------------------------------------------

_PARK_LINES: dict[str, str] = {
    "technopark":  "I came across this opening on the Technopark (Trivandrum) portal",
    "infopark":    "I found this opportunity listed on the Infopark (Kochi) job board",
    "ulcyberpark": "I noticed this role on the UL Cyberpark (Kozhikode) careers portal",
}

_COVER_TEMPLATE = """\
{salutation}

I am writing to express my interest in the {role} position{at_company}.

My background in {primary_skills} aligns well with this opportunity. \
Most recently, I worked on {highlight_project}, where I {project_detail}.

{park_line}, and I am excited by the prospect of contributing to your team.

Please find my resume attached. I would welcome the opportunity to discuss \
how my experience can add value to your organisation.

Best regards,
{name}
{email}
"""


def build_cover_letter(item: dict) -> str:
    """
    Build a personalised cover letter from the application item.
    All logic is deterministic — no API calls required.
    """
    company   = (item.get("company") or "").strip()
    title     = (item.get("title") or "Software Engineer").strip()
    category  = (item.get("category") or "backend_php").strip()
    park      = (item.get("park") or "").lower()
    skills    = item.get("matched_skills") or []

    # Salutation
    if company and company.lower() not in (title.lower(), ""):
        salutation = f"Dear Hiring Team at {company},"
        at_company = f" at {company}"
    else:
        salutation = "Dear Hiring Team,"
        at_company = ""

    # Primary skills (top 3)
    primary_skills = (
        ", ".join(skills[:3]) if skills else "backend development and system design"
    )

    # Project highlight (category-based)
    project_name, project_detail = _PROJECT_HIGHLIGHTS.get(
        category, _DEFAULT_HIGHLIGHT
    )

    # Park sourcing line
    park_line = "I came across this opening"
    for key, sentence in _PARK_LINES.items():
        if key in park:
            park_line = sentence
            break

    return _COVER_TEMPLATE.format(
        salutation        = salutation,
        role              = title,
        at_company        = at_company,
        primary_skills    = primary_skills,
        highlight_project = project_name,
        project_detail    = project_detail,
        park_line         = park_line,
        name              = APPLICANT_NAME,
        email             = GMAIL_ADDRESS,
    )
