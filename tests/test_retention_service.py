import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.news import News
from app.models.news_image import NewsImage
from app.services import retention_service


class RetentionServiceTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "retention-test.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.output_directory = Path(self.temp_directory.name) / "instagram"
        self.output_directory.mkdir()
        self.now = datetime(2026, 8, 15, 12, 0, tzinfo=UTC)

        self.session_patch = patch.object(retention_service, "SessionLocal", self.Session)
        self.output_patch = patch.object(
            retention_service,
            "OUTPUT_DIRECTORY",
            self.output_directory,
        )
        self.session_patch.start()
        self.output_patch.start()

    def tearDown(self):
        self.output_patch.stop()
        self.session_patch.stop()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def _news(self, news_id: int, age_days: int, status: str = "new") -> News:
        created_at = self.now - timedelta(days=age_days)
        return News(
            id=news_id,
            title=f"Haber {news_id}",
            link=f"https://example.test/{news_id}",
            status=status,
            created_at=created_at,
            updated_at=created_at,
        )

    def test_old_news_is_archived_but_recent_news_stays_active(self):
        db = self.Session()
        db.add_all([self._news(1, 91), self._news(2, 89)])
        db.commit()
        db.close()

        result = retention_service.run_news_retention(now=self.now)

        db = self.Session()
        self.assertEqual(result.archived, 1)
        self.assertEqual(db.get(News, 1).status, "archived")
        self.assertEqual(db.get(News, 2).status, "new")
        db.close()

    def test_year_old_archived_news_is_backed_up_and_removed_with_its_visual(self):
        db = self.Session()
        old_news = self._news(3, 366, status="archived")
        db.add(old_news)
        db.add(
            NewsImage(
                news_id=3,
                image_url="https://example.test/car.jpg",
                origin="source_article",
                status="approved",
            )
        )
        db.commit()
        db.close()

        generated_visual = self.output_directory / "news-3.jpg"
        generated_visual.write_bytes(b"test-image")
        backup_path = Path(self.temp_directory.name) / "backup.db"

        with patch.object(
            retention_service,
            "_create_database_backup",
            return_value=backup_path,
        ) as backup:
            result = retention_service.run_news_retention(now=self.now)

        db = self.Session()
        self.assertEqual(result.deleted, 1)
        self.assertEqual(result.images_removed, 1)
        self.assertEqual(result.backup_path, backup_path)
        self.assertIsNone(db.get(News, 3))
        self.assertEqual(db.query(NewsImage).filter_by(news_id=3).count(), 0)
        self.assertFalse(generated_visual.exists())
        backup.assert_called_once_with(self.now)
        db.close()


if __name__ == "__main__":
    unittest.main()
