import json
import unittest
from unittest.mock import MagicMock, mock_open, patch

import requests

from job_scraper import (
    check_match,
    extract_infopark_jobs,
    extract_jobs_from_html,
    extract_ulcyberpark_jobs,
    is_plausible_job_title,
    is_senior_role,
    main,
    normalize_job_url,
    normalize_title,
    scrape_infopark,
    scrape_portal,
    scrape_technopark,
)


SAMPLE_HTML = """
<html>
  <body>
    <a href="/jobs/1">Senior Python Backend Engineer</a>
    <a href="/jobs/1">Senior Python Backend Engineer</a>
    <a href="/jobs/2">React Developer</a>
    <a href="https://example.com/jobs/3">Go Lang Developer</a>
    <a href="/jobs/4">Machine Learning Engineer</a>
    <a href="/jobs/5">AI Research Scientist</a>
    <a href="/jobs/6">Data Science Intern</a>
    <a href="/jobs/7">Sales Executive</a>
    <a href="#top">Python Lead</a>
    <a href="mailto:hr@example.com">Python Recruiter Contact</a>
    <a href="/jobs/8">Hi</a>
    <a href="/jobs/9">Node.js Full Stack Developer</a>
    <a href="javascript:void(0)">Java Engineer</a>
  </body>
</html>
"""

INFOPARK_HTML = """
<table>
  <tr><th>Date</th><th>Job Title</th><th>Company</th><th>Last Date</th><th></th></tr>
  <tr>
    <td>07-08-2026</td>
    <td>DevOps Engineer - Fresher</td>
    <td>Nesa Software</td>
    <td>30 Aug 2026</td>
    <td><a href="/company-jobs/details/530/25007">Details</a></td>
  </tr>
  <tr>
    <td>07-08-2026</td>
    <td>AI Search Specialist</td>
    <td>Lanware</td>
    <td>30 Sep 2026</td>
    <td><a href="/company-jobs/details/211/25018">Details</a></td>
  </tr>
  <tr>
    <td>07-08-2026</td>
    <td>Software Engineer</td>
    <td>Classic Tech</td>
    <td>30 Aug 2026</td>
    <td><a href="/company-jobs/details/340/24998">Details</a></td>
  </tr>
</table>
"""

UL_HTML = """
<table>
  <tr>
    <td>
      <a class="title">Java Technical Lead &amp; Architect</a><br/>
      <span>closing date: 30-09-2026</span>
    </td>
    <td><a href="mailto:hr@example.com">retailcloud</a></td>
    <td><a href="/jobs/job_vacancy?job_id=1668">View Details</a></td>
  </tr>
  <tr>
    <td>
      <a class="title">Devops Engineer(AWS | Kubernetes | SaaS Platform)</a><br/>
      <span>closing date: 31-08-2026</span>
    </td>
    <td><a href="mailto:x@y.com">HyperBlox</a></td>
    <td><a href="/jobs/job_vacancy?job_id=1666">View Details</a></td>
  </tr>
  <tr>
    <td>
      <a class="title">Jr. QA Engineer</a><br/>
      <span>closing date: 31-08-2026</span>
    </td>
    <td><a href="mailto:hr@example.com">retailcloud</a></td>
    <td><a href="/jobs/job_vacancy?job_id=1667">View Details</a></td>
  </tr>
</table>
"""


class TestNormalizeTitle(unittest.TestCase):
    def test_collapses_common_spellings(self):
        self.assertIn("fullstack", normalize_title("Full-Stack Developer"))
        self.assertIn("fullstack", normalize_title("Fullstack Developer"))
        self.assertIn("nodejs", normalize_title("Senior Node JS Developer"))
        self.assertIn("nodejs", normalize_title("Node.js Engineer"))
        self.assertIn("nextjs", normalize_title("Next JS / React"))
        self.assertIn("devops", normalize_title("Devops Engineer"))
        self.assertIn("devops", normalize_title("Dev Ops Engineer"))
        self.assertIn("dotnet", normalize_title(".NET Developer"))
        self.assertIn("dotnet", normalize_title("Dot Net Developer"))
        self.assertIn("backend", normalize_title("Back-end Engineer"))
        self.assertIn("frontend", normalize_title("Front End Developer"))
        self.assertIn("golang", normalize_title("Go-Lang Developer"))


class TestCheckMatch(unittest.TestCase):
    def test_includes_stack_keywords(self):
        self.assertTrue(check_match("Python Developer"))
        self.assertTrue(check_match("React Frontend Engineer"))
        self.assertTrue(check_match("Golang Backend"))
        self.assertTrue(check_match("Go Developer"))
        self.assertTrue(check_match("Node.js Engineer"))
        self.assertTrue(check_match("NodeJS Developer"))
        self.assertTrue(check_match("Spring Boot Engineer"))
        self.assertTrue(check_match("Full Stack Developer"))
        self.assertTrue(check_match("DevOps Engineer - AWS"))
        self.assertTrue(check_match("Kubernetes / Docker Specialist"))
        self.assertTrue(check_match("Software Engineer"))
        self.assertTrue(check_match("MERN STACK TRAINEE"))
        self.assertTrue(check_match("Angular Developer"))
        self.assertTrue(check_match("Python Django Backend Developer"))
        self.assertTrue(check_match("Jr. PHP Developer"))

    def test_includes_writing_variants(self):
        self.assertTrue(check_match("Full-Stack Developer"))
        self.assertTrue(check_match("Dotnet Fullstack Developer with AWS Experience"))
        self.assertTrue(check_match("Node JS Developer"))
        self.assertTrue(check_match("Devops Engineer(AWS | Kubernetes)"))
        self.assertTrue(check_match("Frontend Developer (React & Next.js)"))
        self.assertTrue(check_match("Back-End Engineer"))
        self.assertTrue(check_match("Front-end Developer"))
        self.assertTrue(check_match("Go Lang Developer"))
        self.assertTrue(check_match("React JS Developer"))
        self.assertTrue(check_match(".NET Developer (Medium Level)"))
        self.assertTrue(check_match("Dot Net Developer"))

    def test_excludes_senior_positions(self):
        self.assertFalse(check_match("Senior Python Developer"))
        self.assertFalse(check_match("Sr. Java Developer"))
        self.assertFalse(check_match("Senior Node JS Developer"))
        self.assertFalse(check_match("Senior Frontend Developer (React & Next.js)"))
        self.assertFalse(check_match("Java Technical Lead & Architect"))
        self.assertFalse(check_match("Tech Lead - React"))
        self.assertFalse(check_match("Staff Software Engineer"))
        self.assertFalse(check_match("Principal Engineer - Backend"))
        self.assertFalse(check_match("Engineering Manager"))
        self.assertTrue(is_senior_role("Senior DevOps Engineer"))

    def test_excludes_ai_ml_roles(self):
        self.assertFalse(check_match("Machine Learning Engineer"))
        self.assertFalse(check_match("AI Engineer"))
        self.assertFalse(check_match("Data Science Intern"))
        self.assertFalse(check_match("NLP Research Engineer"))
        self.assertFalse(check_match("LLM Fine Tuning Engineer"))
        self.assertFalse(check_match("Computer Vision Specialist"))
        self.assertFalse(check_match("Business Analyst - Prompt Engineering and AI"))

    def test_exclusion_wins_over_inclusion(self):
        self.assertFalse(check_match("Python Machine Learning Engineer"))
        self.assertFalse(check_match("React AI Developer"))
        self.assertFalse(check_match("Backend LLM Engineer"))
        self.assertFalse(check_match("Full-Stack Tech Lead – AI Best Practices"))
        self.assertFalse(check_match("Senior Full Stack Developer – AI-Assisted"))

    def test_ignores_unrelated_titles(self):
        self.assertFalse(check_match("Sales Executive"))
        self.assertFalse(check_match("HR Business Partner"))
        self.assertFalse(check_match("Graphic Designer"))
        self.assertFalse(check_match("Jr. QA Engineer"))

    def test_word_boundaries_avoid_partial_hits(self):
        self.assertFalse(check_match("Google Ads Specialist"))
        self.assertTrue(check_match("Available Python Developer"))
        self.assertTrue(check_match("Python HTML Developer"))

    def test_case_insensitive(self):
        self.assertTrue(check_match("PYTHON DEVELOPER"))
        self.assertFalse(check_match("MACHINE LEARNING ENGINEER"))

    def test_empty_and_invalid_titles(self):
        self.assertFalse(check_match(""))
        self.assertFalse(check_match(None))
        self.assertFalse(check_match(123))


class TestTitleAndUrlHelpers(unittest.TestCase):
    def test_plausible_title_length(self):
        self.assertTrue(is_plausible_job_title("Python Dev"))
        self.assertFalse(is_plausible_job_title("Hi"))
        self.assertFalse(is_plausible_job_title("x" * 200))
        self.assertFalse(is_plausible_job_title(""))
        self.assertFalse(is_plausible_job_title(None))

    def test_normalize_relative_and_absolute_urls(self):
        page = "https://technopark.in/job-search"
        self.assertEqual(
            normalize_job_url("/careers/123", page),
            "https://technopark.in/careers/123",
        )
        self.assertEqual(
            normalize_job_url("https://other.example/job/1", page),
            "https://other.example/job/1",
        )

    def test_normalize_rejects_non_http_links(self):
        page = "https://technopark.in/job-search"
        self.assertIsNone(normalize_job_url("#section", page))
        self.assertIsNone(normalize_job_url("mailto:a@b.com", page))
        self.assertIsNone(normalize_job_url("javascript:void(0)", page))
        self.assertIsNone(normalize_job_url("", page))
        self.assertIsNone(normalize_job_url(None, page))


class TestExtractJobsFromHtml(unittest.TestCase):
    def test_extracts_matching_jobs_and_dedupes(self):
        jobs = extract_jobs_from_html(
            SAMPLE_HTML,
            "Generic Park",
            "https://example.com/jobs",
        )
        titles = [job["Title"] for job in jobs]
        urls = [job["URL"] for job in jobs]

        self.assertNotIn("Senior Python Backend Engineer", titles)
        self.assertIn("React Developer", titles)
        self.assertIn("Go Lang Developer", titles)
        self.assertIn("Node.js Full Stack Developer", titles)
        self.assertNotIn("Machine Learning Engineer", titles)
        self.assertNotIn("Sales Executive", titles)
        self.assertEqual(urls.count("https://example.com/jobs/1"), 0)

    def test_empty_html_returns_empty_list(self):
        self.assertEqual(extract_jobs_from_html("", "Park", "https://example.com"), [])


class TestPortalParsers(unittest.TestCase):
    def test_infopark_reads_title_from_table_not_link_text(self):
        jobs = extract_infopark_jobs(
            INFOPARK_HTML,
            "Infopark (Kochi)",
            "https://infopark.in/jobs",
        )
        titles = [job["Title"] for job in jobs]
        self.assertIn("DevOps Engineer - Fresher", titles)
        self.assertIn("Software Engineer", titles)
        self.assertNotIn("AI Search Specialist", titles)
        self.assertTrue(
            any("25007" in job["URL"] for job in jobs),
        )

    def test_ulcyberpark_uses_details_url_and_title_anchor(self):
        jobs = extract_ulcyberpark_jobs(
            UL_HTML,
            "UL Cyberpark (Kozhikode)",
            "https://www.ulcyberpark.com/jobs",
        )
        by_title = {job["Title"]: job for job in jobs}
        self.assertNotIn("Java Technical Lead & Architect", by_title)
        self.assertIn("Devops Engineer(AWS | Kubernetes | SaaS Platform)", by_title)
        self.assertNotIn("Jr. QA Engineer", by_title)
        self.assertEqual(
            by_title["Devops Engineer(AWS | Kubernetes | SaaS Platform)"]["URL"],
            "https://www.ulcyberpark.com/jobs/job_vacancy?job_id=1666",
        )


class TestScrapePortal(unittest.TestCase):
    def test_scrape_infopark_walks_multiple_pages(self):
        session = MagicMock()
        response = MagicMock()
        response.text = INFOPARK_HTML + '<a href="https://infopark.in/companies-job?page=2">2</a>'
        response.url = "https://infopark.in/companies-job?page=1"
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        jobs = scrape_infopark(
            "Infopark (Kochi)",
            session=session,
            min_pages=2,
            max_pages=2,
        )
        self.assertEqual(session.get.call_count, 2)
        self.assertGreaterEqual(len(jobs), 2)
        self.assertTrue(any("DevOps" in job["Title"] for job in jobs))

    def test_scrape_technopark_respects_min_pages_and_skips_senior(self):
        session = MagicMock()
        response = MagicMock()
        response.raise_for_status = MagicMock()
        response.json.return_value = {
            "current_page": 1,
            "last_page": 1,
            "data": [
                {"id": 1, "job_title": "Senior Node JS Developer"},
                {"id": 2, "job_title": "AI Architect"},
                {"id": 3, "job_title": "Sales Executive"},
                {"id": 4, "job_title": "Python Developer"},
            ],
        }
        session.get.return_value = response

        jobs = scrape_technopark(
            "Technopark (Trivandrum)",
            session=session,
            min_pages=3,
            max_pages=3,
        )
        self.assertEqual(session.get.call_count, 3)
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0]["Title"], "Python Developer")
        self.assertIn("/job-details/4", jobs[0]["URL"])

    def test_scrape_portal_handles_request_errors(self):
        session = MagicMock()
        session.get.side_effect = requests.exceptions.Timeout("timed out")
        jobs = scrape_portal(
            "UL Cyberpark (Kozhikode)",
            "https://www.ulcyberpark.com/jobs",
            session=session,
        )
        self.assertEqual(jobs, [])


class TestMain(unittest.TestCase):
    def test_main_aggregates_and_rewrites_json(self):
        session = MagicMock()
        response = MagicMock()
        response.text = INFOPARK_HTML
        response.url = "https://infopark.in/companies-job?page=1"
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        portals = {"Infopark (Kochi)": "https://infopark.in/companies-job"}
        fake_file = mock_open()

        with patch("job_scraper.scrape_infopark") as mocked_scrape:
            mocked_scrape.return_value = [
                {
                    "Park": "Infopark (Kochi)",
                    "Title": "DevOps Engineer - Fresher",
                    "URL": "https://infopark.in/company-jobs/details/530/25007",
                }
            ]
            with patch("builtins.open", fake_file):
                jobs = main(portals=portals, output_filename="out.json", session=session)

        self.assertEqual(len(jobs), 1)
        written = "".join(call.args[0] for call in fake_file().write.call_args_list)
        payload = json.loads(written)
        self.assertEqual(payload[0]["Park"], "Infopark (Kochi)")

    def test_main_rewrites_json_even_when_empty(self):
        session = MagicMock()
        response = MagicMock()
        response.text = "<table><tr><td>1</td><td>Sales Manager Role</td><td>Co</td><td>x</td><td><a href='/j/1'>Details</a></td></tr></table>"
        response.url = "https://infopark.in/companies-job"
        response.raise_for_status = MagicMock()
        session.get.return_value = response

        fake_file = mock_open()
        with patch("job_scraper.scrape_infopark", return_value=[]):
            with patch("builtins.open", fake_file):
                jobs = main(
                    portals={"Infopark (Kochi)": "https://infopark.in/companies-job"},
                    output_filename="out.json",
                    session=session,
                )

        self.assertEqual(jobs, [])
        fake_file.assert_called_once()
        written = "".join(call.args[0] for call in fake_file().write.call_args_list)
        self.assertEqual(json.loads(written), [])


if __name__ == "__main__":
    unittest.main()
