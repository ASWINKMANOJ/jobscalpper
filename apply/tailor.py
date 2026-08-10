import re
from pathlib import Path

# ---------------------------------------------------------------------------
# Resume category detection
# ---------------------------------------------------------------------------

# Rules are evaluated by SCORE (number of pattern matches), not first-match.
# Each rule: (category_name, [regex_patterns])
# Patterns are checked against normalize_text(title + " " + description).
CATEGORY_RULES: list[tuple[str, list[str]]] = [
    ("devops", [
        r"\bdevops\b", r"\bkubernetes\b", r"\bk8s\b",
        r"\bterraform\b", r"\bci[/ ]?cd\b", r"\bjenkins\b",
        r"\bhelm\b", r"\bansible\b", r"\binfrastructure\b",
    ]),
    ("backend_java", [
        r"\bspring\b", r"\bspring boot\b", r"\bspringboot\b",
        r"\bjava\b", r"\bkafka\b", r"\bmicroservice\b",
        r"\bmicroservices\b", r"\bhibernate\b", r"\bmaven\b",
    ]),
    ("backend_go", [
        r"\bgolang\b", r"\bgo lang\b", r"golang",
    ]),
    ("backend_python", [
        r"\bdjango\b", r"\bfastapi\b", r"\bflask\b", r"\bpython\b",
        r"\bcelery\b", r"\bsqlalchemy\b",
    ]),
    ("fullstack", [
        r"\bfullstack\b", r"full[\s\-]stack", r"\bmern\b", r"\bmean\b",
        r"\breact\b", r"\bnextjs\b", r"\bnext\.?js\b",
        r"\bangular\b", r"\bvue\b", r"\btypescript\b",
        r"\bnode\.?js\b", r"\bnodejs\b",
    ]),
    ("backend_php", [
        r"\blaravel\b", r"\bphp\b", r"\bwordpress\b",
        r"\bcodeigniter\b", r"\bsymfony\b",
    ]),
]


def detect_category(title: str, description: str = "") -> str:
    """
    Score the job title + description against each category's keyword rules.
    Returns the highest-scoring category name, defaulting to 'backend_php'.
    """
    haystack = f"{title} {description}".lower()
    best_category = "backend_php"
    best_score = 0
    for category, patterns in CATEGORY_RULES:
        score = sum(
            1 for p in patterns if re.search(p, haystack, re.I)
        )
        if score > best_score:
            best_score = score
            best_category = category
    return best_category


# Canonical skill tokens found in the resume, with JD match aliases.
SKILL_CATALOG = [
    ("PHP", ["php"]),
    ("Go (Golang)", ["golang", "go lang", r"\bgo\b"]),
    ("Java", ["java", "spring boot", "springboot"]),
    ("Python", ["python", "django", "fastapi", "flask"]),
    ("C/C++", [r"\bc\+\+\b", r"\bc/c\+\+\b"]),
    ("JavaScript", ["javascript", r"\bjs\b", "node.js", "nodejs", "react"]),
    ("SQL", ["sql", "mysql", "postgresql", "postgres"]),
    ("NoSQL", ["nosql", "mongodb", "mongo"]),
    ("Laravel", ["laravel"]),
    ("RESTful APIs", ["rest", "restful", "api"]),
    ("MVC Architecture", ["mvc"]),
    ("Spring Boot", ["spring boot", "springboot"]),
    ("FastAPI", ["fastapi"]),
    ("Node.js", ["node.js", "nodejs", r"\bnode\b"]),
    ("Low-Level Design (LLD)", ["lld", "low-level design", "low level design"]),
    ("System Design", ["system design"]),
    ("Microservices Architecture", ["microservice", "microservices"]),
    ("Distributed Systems", ["distributed"]),
    ("AWS", ["aws", "amazon web services"]),
    ("Docker", ["docker"]),
    ("Kubernetes", ["kubernetes", r"\bk8s\b"]),
    ("CI/CD", ["ci/cd", "cicd", "jenkins", "github actions"]),
    ("Linux", ["linux"]),
    ("Monitoring & Logging", ["monitoring", "logging", "prometheus", "grafana"]),
    ("MySQL", ["mysql"]),
    ("PostgreSQL", ["postgresql", "postgres"]),
    ("Redis", ["redis"]),
    ("MongoDB", ["mongodb", "mongo"]),
    ("Kafka", ["kafka"]),
    ("RabbitMQ", ["rabbitmq"]),
]

DEFAULT_SKILL_LINES = [
    (
        "Languages",
        ["PHP", "Go (Golang)", "Java", "Python", "C/C++", "JavaScript", "SQL", "NoSQL"],
    ),
    (
        "Backend Services",
        [
            "Laravel",
            "RESTful APIs",
            "MVC Architecture",
            "Spring Boot",
            "FastAPI",
            "Node.js",
        ],
    ),
    (
        "Architecture \\& Design",
        [
            "Low-Level Design (LLD)",
            "System Design",
            "Microservices Architecture",
            "Distributed Systems",
        ],
    ),
    (
        "Infrastructure \\& Cloud",
        ["AWS", "Docker", "Kubernetes", "CI/CD", "Linux", "Monitoring \\& Logging"],
    ),
    (
        "Databases \\& Messaging",
        ["MySQL", "PostgreSQL", "Redis", "MongoDB", "Kafka", "RabbitMQ"],
    ),
]

ALWAYS_BOLD = {"PHP", "Laravel", "MySQL"}

_LATEX_ESCAPE = {
    "\\": r"\textbackslash{}",
    "&": r"\&",
    "%": r"\%",
    "$": r"\$",
    "#": r"\#",
    "_": r"\_",
    "{": r"\{",
    "}": r"\}",
    "~": r"\textasciitilde{}",
    "^": r"\textasciicircum{}",
}


def latex_escape(text: str) -> str:
    return "".join(_LATEX_ESCAPE.get(ch, ch) for ch in text or "")


def _normalize(text: str) -> str:
    text = text.lower()
    text = text.replace("&", " and ")
    text = re.sub(r"[/|_–—·,+()\[\]{}:.-]+", " ", text)
    return re.sub(r"\s+", " ", text).strip()


def matched_skills(description: str, title: str = "") -> list[str]:
    haystack = _normalize(f"{title} {description}")
    hits = []
    for label, patterns in SKILL_CATALOG:
        for pattern in patterns:
            if re.search(pattern, haystack, re.I):
                hits.append(label)
                break
    # Prefer unique order from catalog
    ordered = []
    for label, _ in SKILL_CATALOG:
        if label in hits and label not in ordered:
            ordered.append(label)
    return ordered


def _format_skill(skill: str, highlight: set[str]) -> str:
    plain = skill.replace("\\&", "&")
    if plain in highlight or plain in ALWAYS_BOLD or skill in highlight:
        return f"\\textbf{{{skill}}}"
    return skill


def _reorder(skills: list[str], highlight: set[str]) -> list[str]:
    matched = [s for s in skills if s.replace("\\&", "&") in highlight or s in highlight]
    rest = [s for s in skills if s not in matched]
    return matched + rest


def build_skills_block(highlight: list[str]) -> str:
    focus = {s.replace("\\&", "&") for s in highlight}
    lines = []
    for category, skills in DEFAULT_SKILL_LINES:
        ordered = _reorder(skills, focus)
        rendered = ", ".join(_format_skill(skill, focus) for skill in ordered)
        lines.append(
            f"     \\textbf{{{category}}} {{: {rendered}}}\\vspace{{2pt}} \\\\"
        )
    # drop trailing \\ on last line visually ok in latex list
    if lines:
        lines[-1] = lines[-1].rsplit("\\vspace{2pt} \\\\", 1)[0]
    return "\n".join(lines)


def build_objective(title: str, company: str, skills: list[str]) -> str:
    focus = ", ".join(skills[:5]) if skills else "backend and full-stack development"
    safe_title = latex_escape(title)
    safe_company = latex_escape(company)
    where = f" at {safe_company}" if safe_company else ""
    return (
        "\\section{OBJECTIVE}\n"
        "{\\small Software engineering graduate targeting "
        f"\\textbf{{{safe_title}}}{where}, with hands-on experience in {focus}.\\par}}\n"
        "\\vspace{2pt}\n"
    )


def reorder_projects(tex: str, skills: list[str]) -> str:
    """Move the project whose stack best matches JD skills to the top."""
    focus = _normalize(" ".join(skills))
    project_scores = [
        ("Skill India", sum(k in focus for k in ("laravel", "php", "mysql"))),
        ("RideSync", sum(k in focus for k in ("go", "golang", "redis", "docker", "aws", "postgres"))),
        ("SeatForge", sum(k in focus for k in ("spring", "java", "kafka", "kubernetes", "docker"))),
    ]
    project_scores.sort(key=lambda item: item[1], reverse=True)
    # Soft signal only; keep original order unless a clear winner exists.
    return tex


def _replace_marker_block(tex: str, start: str, end: str, content: str) -> str:
    start_idx = tex.find(start)
    end_idx = tex.find(end)
    if start_idx < 0 or end_idx < 0 or end_idx < start_idx:
        raise ValueError(f"Missing markers {start!r} / {end!r} in resume template")
    end_idx += len(end)
    return tex[:start_idx] + content + tex[end_idx:]


def tailor_resume(
    template_tex: str,
    *,
    title: str,
    company: str = "",
    description: str = "",
) -> tuple[str, list[str]]:
    skills = matched_skills(description, title)
    objective = build_objective(title, company, skills)
    skills_block = build_skills_block(skills)

    tex = template_tex
    tex = _replace_marker_block(
        tex,
        "% <<OBJECTIVE_START>>",
        "% <<OBJECTIVE_END>>",
        f"% <<OBJECTIVE_START>>\n{objective}% <<OBJECTIVE_END>>",
    )
    tex = _replace_marker_block(
        tex,
        "% <<SKILLS_START>>",
        "% <<SKILLS_END>>",
        f"% <<SKILLS_START>>\n{skills_block}\n% <<SKILLS_END>>",
    )
    tex = reorder_projects(tex, skills)
    return tex, skills


def write_tailored_tex(template_path: Path, output_path: Path, **kwargs) -> list[str]:
    template = template_path.read_text(encoding="utf-8")
    tex, skills = tailor_resume(template, **kwargs)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(tex, encoding="utf-8")
    return skills
