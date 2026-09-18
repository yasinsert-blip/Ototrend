import socket
import tempfile
import unittest
from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import patch

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database import crud
from app.database.database import Base
from app.models.news import News
from app.services import visual_source_service
from main import app


class ManagementApiSecurityTests(unittest.TestCase):
    def setUp(self):
        self.client = TestClient(app, raise_server_exceptions=False)

    def tearDown(self):
        self.client.close()

    def test_management_apis_require_an_authenticated_session(self):
        self.assertEqual(self.client.get("/api/news/").status_code, 401)
        self.assertEqual(self.client.get("/sources/").status_code, 401)
        self.assertEqual(self.client.post("/api/test-telegram").status_code, 401)

    def test_telegram_test_route_has_no_get_side_effect(self):
        self.assertEqual(self.client.get("/api/test-telegram").status_code, 405)

    def test_news_pagination_is_validated_before_querying(self):
        self.assertEqual(
            self.client.get("/api/news/?page_size=0").status_code,
            422,
        )


class NewsVisibilityTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "news-visibility.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session_patch = patch.object(crud, "SessionLocal", self.Session)
        self.session_patch.start()

        now = datetime.now(UTC)
        db = self.Session()
        db.add_all(
            [
                News(
                    id=1,
                    title="Aktif haber",
                    link="https://example.test/active",
                    status="editor_review",
                    created_at=now,
                    updated_at=now,
                ),
                News(
                    id=2,
                    title="Silinmiş haber",
                    link="https://example.test/deleted",
                    status="deleted",
                    created_at=now,
                    updated_at=now,
                ),
            ]
        )
        db.commit()
        db.close()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def test_deleted_news_is_hidden_from_normal_lists_and_detail_lookup(self):
        result = crud.get_news(page=1, page_size=20)

        self.assertEqual(result["total"], 1)
        self.assertEqual([item.id for item in result["items"]], [1])
        self.assertIsNone(crud.get_news_by_id(2))

    def test_inline_instagram_fields_do_not_change_workflow_status(self):
        crud.update_instagram_content(
            news_id=1,
            instagram_title="Instagram başlığı",
            instagram_caption="Instagram açıklaması",
            hashtags="#OtoTrendTR",
            image_prompt="Görsel notu",
            mark_as_draft=False,
        )

        db = self.Session()
        try:
            self.assertEqual(db.get(News, 1).status, "editor_review")
        finally:
            db.close()

    def test_publishing_sets_the_legacy_published_flag(self):
        crud.bulk_update_status([1], "published")

        db = self.Session()
        try:
            news = db.get(News, 1)
            self.assertEqual(news.status, "published")
            self.assertTrue(news.published)
        finally:
            db.close()


class VisualUrlSafetyTests(unittest.TestCase):
    def test_domain_resolving_to_private_network_is_rejected(self):
        private_address = (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("127.0.0.1", 0),
        )
        with patch.object(
            visual_source_service.socket,
            "getaddrinfo",
            return_value=[private_address],
        ):
            self.assertFalse(
                visual_source_service.is_public_http_url("https://example.test/image.jpg")
            )

    def test_domain_resolving_to_public_network_is_accepted(self):
        public_address = (
            socket.AF_INET,
            socket.SOCK_STREAM,
            6,
            "",
            ("8.8.8.8", 0),
        )
        with patch.object(
            visual_source_service.socket,
            "getaddrinfo",
            return_value=[public_address],
        ):
            self.assertTrue(
                visual_source_service.is_public_http_url("https://example.test/image.jpg")
            )


if __name__ == "__main__":
    unittest.main()
