import unittest
from unittest.mock import patch

from app.services import instagram_job_service


class InstagramJobServiceTests(unittest.TestCase):
    def test_background_job_reports_completion_and_draft(self):
        draft = {
            "news_id": 52,
            "message": "Haber #52 için Instagram taslağı oluşturuldu.",
            "data": {"instagram_title": "Test başlık"},
            "metrics": {},
        }

        with patch.object(instagram_job_service._executor, "submit") as submit:
            job = instagram_job_service.start_instagram_draft_job(52)

        self.assertEqual(job["status"], "queued")
        submit.assert_called_once()

        with patch.object(
            instagram_job_service,
            "create_instagram_draft",
            return_value=draft,
        ):
            instagram_job_service._run_job(job["id"], 52)

        completed = instagram_job_service.get_instagram_draft_job(job["id"])
        self.assertEqual(completed["status"], "completed")
        self.assertEqual(completed["progress"], 100)
        self.assertEqual(completed["result"], draft)

    def test_duplicate_active_news_returns_the_same_job(self):
        with patch.object(instagram_job_service._executor, "submit"):
            first = instagram_job_service.start_instagram_draft_job(53)
            second = instagram_job_service.start_instagram_draft_job(53)

        self.assertEqual(first["id"], second["id"])


if __name__ == "__main__":
    unittest.main()
