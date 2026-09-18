import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.news import News
from app.services import ai_queue_service


class AIQueueServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "queue-test.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)
        self.session_patch = patch.object(ai_queue_service, "SessionLocal", self.Session)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def _news(
        self,
        news_id: int,
        *,
        age_hours: int,
        processed: bool,
        importance: int | None = None,
    ) -> News:
        created_at = self.now - timedelta(hours=age_hours)
        return News(
            id=news_id,
            title=f"Haber {news_id}",
            link=f"https://example.test/{news_id}",
            status="new",
            ai_processed=processed,
            importance=importance,
            created_at=created_at,
            updated_at=created_at,
        )

    def test_refresh_keeps_only_current_high_importance_news_in_review_queue(self):
        db = self.Session()
        db.add_all(
            [
                self._news(1, age_hours=2, processed=True, importance=8),
                self._news(2, age_hours=2, processed=True, importance=7),
                self._news(3, age_hours=25, processed=True, importance=10),
                self._news(4, age_hours=25, processed=False),
                self._news(5, age_hours=2, processed=False),
            ]
        )
        db.commit()
        db.close()

        result = ai_queue_service.refresh_ai_queue(now=self.now)

        db = self.Session()
        self.assertEqual(result.promoted_to_review, 1)
        self.assertEqual(result.marked_processed, 2)
        self.assertEqual(result.skipped_as_stale, 1)
        self.assertEqual(db.get(News, 1).status, "ai_ready")
        self.assertEqual(db.get(News, 2).status, "ai_processed")
        self.assertEqual(db.get(News, 3).status, "ai_processed")
        self.assertEqual(db.get(News, 4).status, "ai_skipped")
        self.assertIn("yaş sınırını geçti", db.get(News, 4).ai_last_error)
        self.assertIsNone(db.get(News, 4).ai_next_retry_at)
        self.assertEqual(db.get(News, 5).status, "new")
        db.close()

    def test_review_status_uses_configured_importance_threshold(self):
        self.assertEqual(ai_queue_service.review_status_for_importance(8), "ai_ready")
        self.assertEqual(ai_queue_service.review_status_for_importance(7), "ai_processed")
        self.assertEqual(ai_queue_service.review_status_for_importance(None), "ai_processed")


if __name__ == "__main__":
    unittest.main()
