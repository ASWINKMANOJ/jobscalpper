"""
test_db_store.py — Tests for the SQLite data access layer.

Uses a temporary database for each test to avoid polluting the real DB.
"""

import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

# Patch DB_PATH before importing store so all tests hit a temp file
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import db.store as store

store.DB_PATH = Path(_tmp_db.name)


class _DBTestCase(unittest.TestCase):
    """Base class that reinitializes the DB before each test."""

    def setUp(self):
        # Wipe and recreate tables for isolation
        if store.DB_PATH.exists():
            store.DB_PATH.unlink()
        store.init_db()

    @classmethod
    def tearDownClass(cls):
        if store.DB_PATH.exists():
            store.DB_PATH.unlink()


class TestInitDB(_DBTestCase):
    def test_creates_tables(self):
        """init_db should create jobs and applications tables."""
        with store._conn() as con:
            tables = [
                r[0] for r in
                con.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
            ]
        self.assertIn("jobs", tables)
        self.assertIn("applications", tables)

    def test_idempotent(self):
        """Calling init_db twice should not error."""
        store.init_db()
        store.init_db()  # should not raise


class TestJobHash(_DBTestCase):
    def test_deterministic(self):
        h1 = store.job_hash("Technopark", "https://example.com/job/1")
        h2 = store.job_hash("Technopark", "https://example.com/job/1")
        self.assertEqual(h1, h2)

    def test_case_insensitive_park(self):
        h1 = store.job_hash("Technopark", "https://example.com/1")
        h2 = store.job_hash("TECHNOPARK", "https://example.com/1")
        self.assertEqual(h1, h2)

    def test_different_urls_different_hashes(self):
        h1 = store.job_hash("Technopark", "https://example.com/1")
        h2 = store.job_hash("Technopark", "https://example.com/2")
        self.assertNotEqual(h1, h2)

    def test_length_is_16(self):
        h = store.job_hash("Park", "https://example.com/job")
        self.assertEqual(len(h), 16)


class TestUpsertJob(_DBTestCase):
    def test_insert_new_job(self):
        h = store.upsert_job("Technopark", "Python Dev", "https://example.com/1")
        self.assertEqual(len(h), 16)
        with store._conn() as con:
            row = con.execute("SELECT * FROM jobs WHERE hash = ?", (h,)).fetchone()
        self.assertEqual(row["title"], "Python Dev")
        self.assertEqual(row["park"], "Technopark")
        self.assertEqual(row["seen_count"], 1)

    def test_upsert_increments_seen_count(self):
        h = store.upsert_job("Technopark", "Python Dev", "https://example.com/1")
        store.upsert_job("Technopark", "Python Dev", "https://example.com/1")
        store.upsert_job("Technopark", "Python Dev", "https://example.com/1")
        with store._conn() as con:
            row = con.execute("SELECT seen_count FROM jobs WHERE hash = ?", (h,)).fetchone()
        self.assertEqual(row["seen_count"], 3)

    def test_upsert_updates_title(self):
        h = store.upsert_job("Park", "Old Title", "https://example.com/1")
        store.upsert_job("Park", "New Title", "https://example.com/1")
        with store._conn() as con:
            row = con.execute("SELECT title FROM jobs WHERE hash = ?", (h,)).fetchone()
        self.assertEqual(row["title"], "New Title")


class TestGetNewJobs(_DBTestCase):
    def test_returns_jobs_without_applications(self):
        store.upsert_job("Park", "Job A", "https://example.com/a")
        h2 = store.upsert_job("Park", "Job B", "https://example.com/b")
        # Create an application for Job B
        store.upsert_application({
            "id": "app-b", "job_hash": h2, "status": "pending",
            "title": "Job B", "park": "Park", "url": "https://example.com/b",
        })
        new = store.get_new_jobs()
        titles = [j["title"] for j in new]
        self.assertIn("Job A", titles)
        self.assertNotIn("Job B", titles)

    def test_empty_when_all_have_applications(self):
        h = store.upsert_job("Park", "Job", "https://example.com/1")
        store.upsert_application({
            "id": "app-1", "job_hash": h, "status": "pending",
            "title": "Job", "park": "Park", "url": "https://example.com/1",
        })
        self.assertEqual(store.get_new_jobs(), [])


class TestGetJobsPaginated(_DBTestCase):
    def setUp(self):
        super().setUp()
        for i in range(25):
            park = "Technopark" if i % 2 == 0 else "Infopark"
            store.upsert_job(park, f"Job {i}", f"https://example.com/{i}")

    def test_pagination(self):
        jobs, total = store.get_jobs_paginated(page=1, per_page=10)
        self.assertEqual(len(jobs), 10)
        self.assertEqual(total, 25)

    def test_second_page(self):
        jobs, total = store.get_jobs_paginated(page=2, per_page=10)
        self.assertEqual(len(jobs), 10)
        self.assertEqual(total, 25)

    def test_last_page_partial(self):
        jobs, total = store.get_jobs_paginated(page=3, per_page=10)
        self.assertEqual(len(jobs), 5)

    def test_filter_by_park(self):
        jobs, total = store.get_jobs_paginated(park="Infopark", per_page=50)
        self.assertEqual(total, 12)  # odd indices 1,3,5,...,23
        for j in jobs:
            self.assertEqual(j["park"], "Infopark")

    def test_search_filter(self):
        jobs, total = store.get_jobs_paginated(search="Job 1", per_page=50)
        # Matches "Job 1", "Job 10"..."Job 19"
        self.assertGreater(total, 0)
        for j in jobs:
            self.assertIn("Job 1", j["title"])


class TestGetParks(_DBTestCase):
    def test_returns_distinct_parks(self):
        store.upsert_job("Technopark", "J1", "https://example.com/1")
        store.upsert_job("Infopark", "J2", "https://example.com/2")
        store.upsert_job("Technopark", "J3", "https://example.com/3")
        parks = store.get_parks()
        self.assertEqual(sorted(parks), ["Infopark", "Technopark"])


class TestApplications(_DBTestCase):
    def _make_app(self, app_id="test-app", status="pending", **overrides):
        data = {
            "id": app_id,
            "job_hash": None,
            "status": status,
            "category": "backend_php",
            "title": "PHP Developer",
            "park": "Technopark",
            "url": "https://example.com/job/1",
            "email": "hr@example.com",
            "company": "Acme",
            "description": "Need PHP dev",
            "matched_skills": ["PHP", "Laravel"],
            "cover_letter": "Dear...",
            "tex_path": "",
            "pdf_path": "",
        }
        data.update(overrides)
        return data

    def test_upsert_and_get(self):
        store.upsert_application(self._make_app())
        item = store.get_application("test-app")
        self.assertIsNotNone(item)
        self.assertEqual(item["title"], "PHP Developer")
        self.assertEqual(item["status"], "pending")

    def test_get_nonexistent_returns_none(self):
        self.assertIsNone(store.get_application("nonexistent"))

    def test_upsert_preserves_approved_status(self):
        """Re-upserting a pending record over an approved one keeps approved."""
        store.upsert_application(self._make_app(status="approved"))
        store.upsert_application(self._make_app(status="pending"))
        item = store.get_application("test-app")
        self.assertEqual(item["status"], "approved")

    def test_upsert_preserves_sent_status(self):
        store.upsert_application(self._make_app(status="sent"))
        store.upsert_application(self._make_app(status="pending"))
        item = store.get_application("test-app")
        self.assertEqual(item["status"], "sent")

    def test_matched_skills_deserialized(self):
        store.upsert_application(self._make_app())
        item = store.get_application("test-app")
        self.assertIsInstance(item["matched_skills"], list)
        self.assertIn("PHP", item["matched_skills"])

    def test_load_applications_all(self):
        store.upsert_application(self._make_app("a1", "pending"))
        store.upsert_application(self._make_app("a2", "approved"))
        store.upsert_application(self._make_app("a3", "sent"))
        apps = store.load_applications()
        self.assertEqual(len(apps), 3)

    def test_load_applications_by_status(self):
        store.upsert_application(self._make_app("a1", "pending"))
        store.upsert_application(self._make_app("a2", "approved"))
        store.upsert_application(self._make_app("a3", "sent"))
        pending = store.load_applications(status="pending")
        self.assertEqual(len(pending), 1)
        self.assertEqual(pending[0]["id"], "a1")

    def test_set_status(self):
        store.upsert_application(self._make_app("a1", "pending"))
        updated = store.set_status(["a1"], "approved")
        self.assertEqual(len(updated), 1)
        self.assertEqual(updated[0]["status"], "approved")
        self.assertTrue(updated[0].get("approved_at"))

    def test_set_status_nonexistent_returns_empty(self):
        updated = store.set_status(["ghost"], "approved")
        self.assertEqual(updated, [])

    def test_set_status_sent_sets_sent_at(self):
        store.upsert_application(self._make_app("a1", "approved"))
        updated = store.set_status(["a1"], "sent")
        self.assertEqual(updated[0]["status"], "sent")
        self.assertTrue(updated[0].get("sent_at"))

    def test_set_status_rejected(self):
        store.upsert_application(self._make_app("a1", "pending"))
        updated = store.set_status(["a1"], "rejected")
        self.assertEqual(updated[0]["status"], "rejected")
        self.assertTrue(updated[0].get("rejected_at"))


class TestGetStats(_DBTestCase):
    def test_empty_db(self):
        stats = store.get_stats()
        self.assertEqual(stats["total_jobs"], 0)
        self.assertEqual(stats["new_jobs"], 0)
        self.assertEqual(stats["pending"], 0)
        self.assertEqual(stats["sent"], 0)

    def test_with_data(self):
        h1 = store.upsert_job("Park", "Job 1", "https://example.com/1")
        store.upsert_job("Park", "Job 2", "https://example.com/2")
        store.upsert_application({
            "id": "app-1", "job_hash": h1, "status": "sent",
            "title": "Job 1", "park": "Park", "url": "https://example.com/1",
        })
        stats = store.get_stats()
        self.assertEqual(stats["total_jobs"], 2)
        self.assertEqual(stats["new_jobs"], 1)
        self.assertEqual(stats["sent"], 1)


class TestGetApplicationCounts(_DBTestCase):
    def test_empty_db(self):
        counts = store.get_application_counts()
        self.assertEqual(counts, {"pending": 0, "approved": 0, "sent": 0, "rejected": 0})

    def test_counts_correct(self):
        for i, status in enumerate(["pending", "pending", "approved", "sent", "rejected", "rejected"]):
            store.upsert_application({
                "id": f"a{i}", "status": status,
                "title": f"Job {i}", "park": "P", "url": f"https://x/{i}",
            })
        counts = store.get_application_counts()
        self.assertEqual(counts["pending"], 2)
        self.assertEqual(counts["approved"], 1)
        self.assertEqual(counts["sent"], 1)
        self.assertEqual(counts["rejected"], 2)


class TestMakeApplicationId(_DBTestCase):
    def test_technopark_job_details_url(self):
        aid = store.make_application_id(
            "Technopark (Trivandrum)",
            "https://technopark.in/job-details/12345?job=Python"
        )
        self.assertTrue(aid.startswith("technopark-triva"))
        self.assertTrue(aid.endswith("12345"))

    def test_infopark_company_jobs_url(self):
        aid = store.make_application_id(
            "Infopark (Kochi)",
            "https://infopark.in/company-jobs/details/530/25007"
        )
        self.assertEqual(aid, "infopark-kochi-25007")

    def test_ulcyberpark_job_id_param(self):
        aid = store.make_application_id(
            "UL Cyberpark (Kozhikode)",
            "https://www.ulcyberpark.com/jobs/job_vacancy?job_id=1666"
        )
        self.assertTrue(aid.startswith("ul-cyberpark-koz"))
        self.assertTrue(aid.endswith("1666"))

    def test_fallback_for_unknown_url(self):
        aid = store.make_application_id("Park", "https://example.com/careers/apply")
        self.assertTrue(aid.startswith("park-"))
        self.assertGreater(len(aid), 5)


if __name__ == "__main__":
    unittest.main()
