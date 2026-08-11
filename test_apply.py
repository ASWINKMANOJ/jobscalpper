import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from apply.cover import build_cover_letter
from apply.jd import _extract_company, _extract_description, _pick_email, fetch_job_details
from apply.tailor import (
    build_objective,
    build_skills_block,
    detect_category,
    latex_escape,
    matched_skills,
    tailor_resume,
)
from db.store import make_application_id


ROOT = Path(__file__).resolve().parent
TEMPLATE = (ROOT / "resume" / "resume.tex").read_text(encoding="utf-8")


class TestTailor(unittest.TestCase):
    def test_matched_skills_from_jd(self):
        skills = matched_skills(
            "Looking for DevOps with AWS, Kubernetes, Docker and Go experience",
            "Devops Engineer",
        )
        self.assertIn("AWS", skills)
        self.assertIn("Kubernetes", skills)
        self.assertIn("Docker", skills)
        self.assertIn("Go (Golang)", skills)

    def test_tailor_injects_objective_and_reorders_skills(self):
        tex, skills = tailor_resume(
            TEMPLATE,
            title="Laravel Developer",
            company="Acme",
            description="Need PHP Laravel MySQL developer",
        )
        self.assertIn("OBJECTIVE", tex)
        self.assertIn("Laravel Developer", tex)
        self.assertIn("Acme", tex)
        self.assertTrue(any(s in {"PHP", "Laravel", "MySQL"} for s in skills))
        self.assertIn("% <<SKILLS_START>>", tex)
        self.assertIn(r"\textbf{Laravel}", tex)

    def test_tailor_escapes_latex_specials_in_title(self):
        tex, _ = tailor_resume(
            TEMPLATE,
            title="Engineer (HEX20_SW_J01002)",
            company="Acme & Co",
            description="Go Docker",
        )
        self.assertIn(r"HEX20\_SW\_J01002", tex)
        self.assertIn(r"Acme \& Co", tex)


class TestDetectCategory(unittest.TestCase):
    def test_devops(self):
        self.assertEqual(
            detect_category("DevOps Engineer", "kubernetes terraform ci/cd"),
            "devops",
        )

    def test_backend_java(self):
        self.assertEqual(
            detect_category("Java Developer", "spring boot microservices kafka"),
            "backend_java",
        )

    def test_backend_go(self):
        self.assertEqual(detect_category("Golang Developer", ""), "backend_go")

    def test_backend_python(self):
        self.assertEqual(
            detect_category("Python Developer", "django fastapi celery"),
            "backend_python",
        )

    def test_fullstack(self):
        self.assertEqual(
            detect_category("Fullstack Developer", "react nodejs typescript"),
            "fullstack",
        )

    def test_backend_php(self):
        self.assertEqual(
            detect_category("PHP Developer", "laravel wordpress"),
            "backend_php",
        )

    def test_defaults_to_backend_php(self):
        self.assertEqual(detect_category("Unknown Role", ""), "backend_php")

    def test_highest_score_wins(self):
        # Title says Java but description is mostly Python
        cat = detect_category("Developer", "python django fastapi flask celery")
        self.assertEqual(cat, "backend_python")


class TestBuildObjective(unittest.TestCase):
    def test_includes_title_and_company(self):
        obj = build_objective("Laravel Dev", "Acme Corp", ["PHP", "Laravel"])
        self.assertIn("Laravel Dev", obj)
        self.assertIn("Acme Corp", obj)
        self.assertIn("OBJECTIVE", obj)

    def test_without_company(self):
        obj = build_objective("Go Developer", "", ["Go (Golang)"])
        self.assertNotIn(" at ", obj)

    def test_escapes_special_chars(self):
        obj = build_objective("Dev & Ops", "A&B Corp", [])
        self.assertIn(r"Dev \& Ops", obj)
        self.assertIn(r"A\&B Corp", obj)


class TestBuildSkillsBlock(unittest.TestCase):
    def test_bolds_highlighted_skills(self):
        block = build_skills_block(["Docker", "AWS"])
        self.assertIn(r"\textbf{Docker}", block)
        self.assertIn(r"\textbf{AWS}", block)

    def test_always_bolds_php_laravel_mysql(self):
        block = build_skills_block([])
        self.assertIn(r"\textbf{PHP}", block)
        self.assertIn(r"\textbf{Laravel}", block)
        self.assertIn(r"\textbf{MySQL}", block)

    def test_contains_all_categories(self):
        block = build_skills_block([])
        self.assertIn("Languages", block)
        self.assertIn("Backend Services", block)
        self.assertIn("Infrastructure", block)


class TestLatexEscape(unittest.TestCase):
    def test_escapes_ampersand(self):
        self.assertEqual(latex_escape("A & B"), r"A \& B")

    def test_escapes_underscore(self):
        self.assertEqual(latex_escape("a_b"), r"a\_b")

    def test_escapes_percent(self):
        self.assertEqual(latex_escape("100%"), r"100\%")

    def test_empty_string(self):
        self.assertEqual(latex_escape(""), "")

    def test_none(self):
        self.assertEqual(latex_escape(None), "")


class TestEmailPick(unittest.TestCase):
    def test_prefers_careers_and_blocks_park_inbox(self):
        email = _pick_email(
            ["info@infopark.in", "recruitment@nesasoftware.com", "hello@nesasoftware.com"],
            "https://infopark.in/company-jobs/details/1/2",
        )
        self.assertEqual(email, "recruitment@nesasoftware.com")

    def test_returns_none_when_only_blocklisted(self):
        self.assertIsNone(
            _pick_email(["info@ulcyberpark.com"], "https://www.ulcyberpark.com/jobs/1")
        )

    def test_returns_none_for_empty_list(self):
        self.assertIsNone(_pick_email([], "https://example.com"))

    def test_filters_asset_extensions(self):
        self.assertIsNone(
            _pick_email(["logo@company.png"], "https://example.com")
        )

    def test_prefers_hr_keywords(self):
        email = _pick_email(
            ["support@company.com", "hr@company.com"],
            "https://example.com",
        )
        self.assertEqual(email, "hr@company.com")


class TestExtractCompany(unittest.TestCase):
    def _soup(self, html):
        from bs4 import BeautifulSoup
        return BeautifulSoup(html, "html.parser")

    def test_infopark_title_pattern(self):
        html = "<html><head><title>Jobs at TechCorp | Infoparks Kerala</title></head><body></body></html>"
        soup = self._soup(html)
        company = _extract_company(soup, soup.get_text(), url="", email="")
        self.assertEqual(company, "TechCorp")

    def test_company_label_in_text(self):
        html = "<html><body>Company Name: WidgetWorks Inc Contact hr@widget.com</body></html>"
        soup = self._soup(html)
        text = soup.get_text(" ", strip=True)
        company = _extract_company(soup, text, url="", email="")
        self.assertEqual(company, "WidgetWorks Inc")

    def test_domain_fallback_from_email(self):
        html = "<html><body>No company here</body></html>"
        soup = self._soup(html)
        text = soup.get_text()
        company = _extract_company(soup, text, url="", email="hr@acmecorp.com")
        self.assertEqual(company, "Acmecorp")

    def test_no_company_found(self):
        html = "<html><body>Nothing useful</body></html>"
        soup = self._soup(html)
        company = _extract_company(soup, soup.get_text(), url="", email="")
        self.assertEqual(company, "")


class TestExtractDescription(unittest.TestCase):
    def test_brief_description_pattern(self):
        text = "Some header Brief Description We need a Go developer with Docker.  Experience Required 2 years"
        desc = _extract_description(text)
        self.assertIn("Go developer", desc)

    def test_job_description_pattern(self):
        text = "Title Job Description Looking for Python Django developer Requirements BSc"
        desc = _extract_description(text)
        self.assertIn("Python Django", desc)

    def test_fallback_to_middle_chunk(self):
        text = "A" * 3000
        desc = _extract_description(text)
        self.assertLessEqual(len(desc), 2500)


class TestFetchJobDetails(unittest.TestCase):
    def test_parses_email_and_description(self):
        html = """
        <html><body>
        <h1>Nesa Software</h1>
        Contact Email: careers@hex20.space
        Brief Description We need a Go developer with Docker and AWS.
        Experience Required 1 year
        </body></html>
        """
        session = MagicMock()
        response = MagicMock()
        response.text = html
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        details = fetch_job_details("https://technopark.in/job-details/1", session=session)
        self.assertEqual(details["email"], "careers@hex20.space")
        self.assertIn("Go developer", details["description"])

    def test_returns_all_found_emails(self):
        html = "<html><body>a@test.com and b@test.com</body></html>"
        session = MagicMock()
        response = MagicMock()
        response.text = html
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        details = fetch_job_details("https://example.com/job", session=session)
        self.assertIn("a@test.com", details["emails_found"])
        self.assertIn("b@test.com", details["emails_found"])


class TestCoverLetter(unittest.TestCase):
    def test_cover_letter_contains_title(self):
        text = build_cover_letter(
            {
                "title": "Python Developer",
                "company": "Acme",
                "matched_skills": ["Python", "Django"],
            }
        )
        self.assertIn("Python Developer", text)
        self.assertIn("Acme", text)

    def test_cover_letter_fallback_when_company_matches_title(self):
        text = build_cover_letter(
            {
                "title": "Python Developer",
                "company": "Python Developer",
                "matched_skills": ["Python"],
            }
        )
        self.assertIn("Dear Hiring Team,", text)
        self.assertNotIn("Dear Hiring Team at Python Developer", text)

    def test_technopark_park_line(self):
        text = build_cover_letter({
            "title": "Go Developer", "park": "Technopark (Trivandrum)",
            "matched_skills": ["Go (Golang)"],
        })
        self.assertIn("Technopark", text)

    def test_infopark_park_line(self):
        text = build_cover_letter({
            "title": "PHP Dev", "park": "Infopark (Kochi)",
            "matched_skills": [],
        })
        self.assertIn("Infopark", text)

    def test_ulcyberpark_park_line_uses_generic_fallback(self):
        # NOTE: "ulcyberpark" key doesn't match "ul cyberpark" (space),
        # so the generic line fires. This is a known quirk.
        text = build_cover_letter({
            "title": "React Dev", "park": "UL Cyberpark (Kozhikode)",
            "matched_skills": [],
        })
        self.assertIn("I came across this opening", text)

    def test_backend_go_project_highlight(self):
        text = build_cover_letter({
            "title": "Go Developer", "category": "backend_go",
            "matched_skills": ["Go (Golang)"],
        })
        self.assertIn("RideSync", text)

    def test_devops_project_highlight(self):
        text = build_cover_letter({
            "title": "DevOps Engineer", "category": "devops",
            "matched_skills": ["Docker", "AWS"],
        })
        self.assertIn("RideSync", text)

    def test_fullstack_project_highlight(self):
        text = build_cover_letter({
            "title": "Fullstack Dev", "category": "fullstack",
            "matched_skills": [],
        })
        self.assertIn("Skill India", text)

    def test_default_skills_fallback(self):
        text = build_cover_letter({
            "title": "Dev", "matched_skills": [],
        })
        self.assertIn("backend development and system design", text)

    def test_top_3_skills_used(self):
        text = build_cover_letter({
            "title": "Dev",
            "matched_skills": ["PHP", "Laravel", "MySQL", "Docker", "AWS"],
        })
        self.assertIn("PHP", text)
        self.assertIn("Laravel", text)
        self.assertIn("MySQL", text)


class TestApplicationId(unittest.TestCase):
    def test_make_id_stable(self):
        self.assertTrue(
            make_application_id("Infopark (Kochi)", "https://x/a/b/123")
            .startswith("infopark-kochi")
        )

    def test_numeric_id_from_url(self):
        aid = make_application_id("Park", "https://example.com/job-details/42")
        self.assertIn("42", aid)


class TestResolvePdf(unittest.TestCase):
    def test_resolve_pdf_uses_category_pdf(self):
        """When a category-specific PDF exists, it should be returned."""
        from apply.mailer import _resolve_pdf
        item = {"category": "backend_php", "pdf_path": "/other/path.pdf", "id": "t1"}
        # The real resume/aswin_backend_php.pdf exists in the repo
        pdf = _resolve_pdf(item)
        self.assertIn("aswin_backend_php.pdf", str(pdf))

    @patch("apply.mailer.RESUME_DIR", Path("/fake/nonexistent/resume"))
    def test_resolve_pdf_raises_when_no_pdf(self):
        from apply.mailer import _resolve_pdf
        item = {"category": "ghost", "pdf_path": "/also/nonexistent.pdf", "id": "t1"}
        with self.assertRaises(RuntimeError):
            _resolve_pdf(item)


class TestFindLatexEngine(unittest.TestCase):
    @patch("apply.pdf.TECTONIC_BIN", Path("/nonexistent/tectonic"))
    @patch("shutil.which", return_value=None)
    def test_returns_none_when_no_engine(self, mock_which):
        from apply.pdf import find_latex_engine
        self.assertIsNone(find_latex_engine())

    @patch("apply.pdf.TECTONIC_BIN", Path("/nonexistent/tectonic"))
    @patch("shutil.which", side_effect=lambda name: "/usr/bin/pdflatex" if name == "pdflatex" else None)
    def test_finds_pdflatex(self, mock_which):
        from apply.pdf import find_latex_engine
        result = find_latex_engine()
        self.assertIsNotNone(result)
        self.assertIn("pdflatex", result[0])


if __name__ == "__main__":
    unittest.main()
