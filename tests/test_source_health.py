import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.database import source_crud
from app.models.source import Source


class SourceHealthTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "sources-test.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session_patch = patch.object(source_crud, "SessionLocal", self.Session)
        self.session_patch.start()

        db = self.Session()
        db.add(Source(name="Test RSS", rss_url="https://example.test/feed", enabled=True))
        db.commit()
        db.close()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def _source(self) -> Source:
        db = self.Session()
        source = db.query(Source).filter_by(name="Test RSS").first()
        db.expunge(source)
        db.close()
        return source

    def test_third_consecutive_failure_auto_disables_source(self):
        self.assertFalse(source_crud.mark_source_error("Test RSS", "Bağlantı hatası"))
        self.assertFalse(source_crud.mark_source_error("Test RSS", "Bağlantı hatası"))
        self.assertTrue(source_crud.mark_source_error("Test RSS", "Bağlantı hatası"))

        source = self._source()
        self.assertFalse(source.enabled)
        self.assertEqual(source.consecutive_failures, 3)
        self.assertIsNotNone(source.auto_disabled_at)

    def test_success_resets_consecutive_failure_counter(self):
        source_crud.mark_source_error("Test RSS", "Geçici hata")
        source_crud.mark_source_success("Test RSS", 2)

        source = self._source()
        self.assertTrue(source.enabled)
        self.assertEqual(source.consecutive_failures, 0)
        self.assertIsNone(source.last_error)


if __name__ == "__main__":
    unittest.main()
