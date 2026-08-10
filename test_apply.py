import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

from apply.jd import _pick_email, fetch_job_details
from apply.mailer import build_cover_letter
from apply.queue import make_application_id, save_queue, set_status, upsert_items
from apply.tailor import matched_skills, tailor_resume


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


class TestQueueAndMail(unittest.TestCase):
    def test_upsert_preserves_sent_status(self, tmp_path=None):
        path = ROOT / "applications" / "_test_queue.json"
        try:
            save_queue(
                [
                    {
                        "id": "a1",
                        "status": "sent",
                        "title": "Old",
                        "url": "https://x/1",
                        "email": "a@b.com",
                    }
                ],
                path,
            )
            upsert_items(
                [
                    {
                        "id": "a1",
                        "status": "pending",
                        "title": "New",
                        "url": "https://x/1",
                        "email": "a@b.com",
                    }
                ],
                path,
            )
            items = set_status(["missing"], "approved", path)
            self.assertEqual(items, [])
            from apply.queue import load_queue

            stored = load_queue(path)[0]
            self.assertEqual(stored["status"], "sent")
            self.assertEqual(stored["title"], "New")
        finally:
            if path.exists():
                path.unlink()

    def test_upsert_deduplicates_by_url(self):
        path = ROOT / "applications" / "_test_queue_url.json"
        try:
            save_queue(
                [
                    {
                        "id": "old-id",
                        "status": "pending",
                        "title": "Developer",
                        "url": "https://technopark.in/job-details/123",
                        "email": "a@b.com",
                    }
                ],
                path,
            )
            upsert_items(
                [
                    {
                        "id": "new-id",
                        "status": "pending",
                        "title": "Developer",
                        "url": "https://technopark.in/job-details/123",
                        "email": "a@b.com",
                    }
                ],
                path,
            )
            from apply.queue import load_queue

            stored = load_queue(path)
            self.assertEqual(len(stored), 1)
            self.assertEqual(stored[0]["id"], "old-id")
        finally:
            if path.exists():
                path.unlink()

    def test_make_id_stable(self):
        self.assertTrue(make_application_id("Infopark (Kochi)", "https://x/a/b/123").startswith("infopark-kochi"))

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


if __name__ == "__main__":
    unittest.main()

