"""
test_web_api.py — Tests for the Flask JSON API endpoints.

Uses Flask's test client (no actual HTTP server needed).
"""

import json
import os
import tempfile
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

# Redirect DB to temp file before importing app
_tmp_db = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
_tmp_db.close()

import db.store as store
store.DB_PATH = Path(_tmp_db.name)

from web.app import app


class _APITestCase(unittest.TestCase):
    """Base class that resets the DB and provides a test client."""

    def setUp(self):
        if store.DB_PATH.exists():
            store.DB_PATH.unlink()
        store.init_db()

        # Reset the lazy init flag so before_request runs
        import web.app as web_app
        web_app._db_initialized = True  # skip lazy init, we already did it

        app.config["TESTING"] = True
        self.client = app.test_client()

    @classmethod
    def tearDownClass(cls):
        if store.DB_PATH.exists():
            store.DB_PATH.unlink()


class TestStatsEndpoint(_APITestCase):
    def test_stats_empty_db(self):
        resp = self.client.get("/api/stats")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertEqual(data["total_jobs"], 0)
        self.assertEqual(data["pending"], 0)

    def test_stats_with_data(self):
        store.upsert_job("Park", "Job 1", "https://example.com/1")
        store.upsert_job("Park", "Job 2", "https://example.com/2")
        resp = self.client.get("/api/stats")
        data = resp.get_json()
        self.assertEqual(data["total_jobs"], 2)
        self.assertEqual(data["new_jobs"], 2)


class TestJobsEndpoint(_APITestCase):
    def setUp(self):
        super().setUp()
        for i in range(15):
            park = "Technopark" if i < 10 else "Infopark"
            store.upsert_job(park, f"Job {i}", f"https://example.com/{i}")

    def test_default_pagination(self):
        resp = self.client.get("/api/jobs")
        data = resp.get_json()
        self.assertEqual(data["total"], 15)
        self.assertEqual(len(data["jobs"]), 15)
        self.assertIn("Technopark", data["parks"])
        self.assertIn("Infopark", data["parks"])

    def test_custom_page_size(self):
        resp = self.client.get("/api/jobs?per_page=5&page=1")
        data = resp.get_json()
        self.assertEqual(len(data["jobs"]), 5)
        self.assertEqual(data["total_pages"], 3)

    def test_filter_by_park(self):
        resp = self.client.get("/api/jobs?park=Infopark")
        data = resp.get_json()
        self.assertEqual(data["total"], 5)
        for job in data["jobs"]:
            self.assertEqual(job["park"], "Infopark")

    def test_search_filter(self):
        resp = self.client.get("/api/jobs?q=Job%201")
        data = resp.get_json()
        self.assertGreater(data["total"], 0)


class TestApplicationsEndpoint(_APITestCase):
    def _insert_app(self, app_id, status="pending"):
        store.upsert_application({
            "id": app_id, "status": status,
            "title": "Dev", "park": "Park", "url": f"https://x/{app_id}",
            "email": "hr@test.com", "company": "Co",
        })

    def test_list_all(self):
        self._insert_app("a1", "pending")
        self._insert_app("a2", "approved")
        resp = self.client.get("/api/applications")
        data = resp.get_json()
        self.assertEqual(len(data["applications"]), 2)
        self.assertEqual(data["counts"]["pending"], 1)
        self.assertEqual(data["counts"]["approved"], 1)

    def test_filter_by_status(self):
        self._insert_app("a1", "pending")
        self._insert_app("a2", "sent")
        resp = self.client.get("/api/applications?status=sent")
        data = resp.get_json()
        self.assertEqual(len(data["applications"]), 1)
        self.assertEqual(data["applications"][0]["id"], "a2")


class TestApproveRejectEndpoints(_APITestCase):
    def setUp(self):
        super().setUp()
        store.upsert_application({
            "id": "app-1", "status": "pending",
            "title": "Dev", "park": "Park", "url": "https://x/1",
        })

    def test_approve(self):
        resp = self.client.post("/api/applications/app-1/approve")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["status"], "approved")

    def test_reject(self):
        resp = self.client.post("/api/applications/app-1/reject")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["status"], "rejected")

    def test_approve_nonexistent(self):
        resp = self.client.post("/api/applications/ghost/approve")
        self.assertEqual(resp.status_code, 404)

    def test_reject_nonexistent(self):
        resp = self.client.post("/api/applications/ghost/reject")
        self.assertEqual(resp.status_code, 404)


class TestSendEndpoint(_APITestCase):
    def test_send_not_found(self):
        resp = self.client.post("/api/applications/ghost/send",
                                json={})
        self.assertEqual(resp.status_code, 404)

    def test_send_not_approved(self):
        store.upsert_application({
            "id": "app-1", "status": "pending",
            "title": "Dev", "park": "P", "url": "https://x/1",
            "email": "hr@test.com",
        })
        resp = self.client.post("/api/applications/app-1/send", json={})
        self.assertEqual(resp.status_code, 400)
        self.assertIn("not approved", resp.get_json()["error"])


class TestCoverLetterEndpoint(_APITestCase):
    def test_cover_letter(self):
        store.upsert_application({
            "id": "app-1", "status": "pending",
            "title": "Dev", "park": "P", "url": "https://x/1",
            "cover_letter": "Hello world",
        })
        resp = self.client.get("/api/applications/app-1/cover_letter")
        data = resp.get_json()
        self.assertTrue(data["ok"])
        self.assertEqual(data["cover_letter"], "Hello world")

    def test_cover_letter_not_found(self):
        resp = self.client.get("/api/applications/ghost/cover_letter")
        self.assertEqual(resp.status_code, 404)


class TestScrapeEndpoints(_APITestCase):
    def test_scrape_status_idle(self):
        resp = self.client.get("/api/scrape/status")
        data = resp.get_json()
        self.assertFalse(data["running"])

    @patch("web.app._run_scrape")
    def test_start_scrape(self, mock_run):
        resp = self.client.post("/api/scrape")
        self.assertEqual(resp.status_code, 200)
        self.assertTrue(resp.get_json()["ok"])


class TestConfigEndpoints(_APITestCase):
    def test_get_config(self):
        resp = self.client.get("/api/config")
        self.assertEqual(resp.status_code, 200)
        data = resp.get_json()
        # Should have the known keys
        self.assertIn("GMAIL_ADDRESS", data)
        self.assertIn("has_credentials", data)

    def test_password_is_masked(self):
        resp = self.client.get("/api/config")
        data = resp.get_json()
        if data.get("GMAIL_APP_PASSWORD"):
            self.assertEqual(data["GMAIL_APP_PASSWORD"], "••••••••••••••••")


if __name__ == "__main__":
    unittest.main()
