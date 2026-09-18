import json
import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from starlette.requests import Request

from main import app
from app.views import news as news_view


class FakeRequest:
    def __init__(self, *, ajax=True):
        self.session = {"authenticated": True}
        self.headers = {"X-Requested-With": "XMLHttpRequest"} if ajax else {}


class NewsViewTests(unittest.TestCase):
    @staticmethod
    def _authenticated_request(path="/news/41"):
        return Request(
            {
                "type": "http",
                "method": "GET",
                "path": path,
                "raw_path": path.encode(),
                "query_string": b"",
                "headers": [],
                "scheme": "http",
                "server": ("testserver", 80),
                "client": ("testclient", 50000),
                "root_path": "",
                "app": app,
                "router": app.router,
                "session": {"authenticated": True},
            }
        )

    def test_news_detail_renders_a_complete_editorial_view(self):
        item = SimpleNamespace(
            id=41,
            title="Original headline",
            translated_title="Türkçe haber başlığı",
            source="Test Kaynak",
            category="Elektrikli",
            status="ai_ready",
            published_at=datetime(2026, 8, 16, 10, 30, tzinfo=UTC),
            created_at=datetime(2026, 8, 16, 10, 30, tzinfo=UTC),
            brand="Test Marka",
            importance=8,
            summary="Haber özeti burada.",
            content=None,
            instagram_title=None,
            instagram_caption=None,
            hashtags=None,
            language="tr",
            link="https://example.test/news",
        )
        with patch.object(news_view, "get_news_by_id", return_value=item):
            response = news_view.news_detail(self._authenticated_request(), 41)

        html = response.body.decode("utf-8")
        self.assertEqual(response.status_code, 200)
        self.assertIn("Haber özeti", html)
        self.assertIn("Türkçe haber başlığı", html)
        self.assertIn("Instagram taslağı", html)

    def test_editor_page_uses_the_responsive_main_layout(self):
        stats = {
            "total_news": 0,
            "ai_pending": 0,
            "ai_ready": 0,
            "editor_review": 0,
            "instagram_ready": 0,
            "published": 0,
        }
        template = news_view.templates.get_template("editor.html")
        html = template.render(
            request=self._authenticated_request("/editor"),
            news_list=[],
            brands=[],
            categories=[],
            stats=stats,
        )

        self.assertIn("Haber akışını inceleyin", html)
        self.assertIn("editor-optional-column", html)
        self.assertIn("max-width: 1599.98px", html)
        self.assertIn('class="menu-item active"', html)

    def test_news_detail_does_not_depend_on_bulk_request_values(self):
        item = SimpleNamespace(id=41, title="Test haberi")
        with patch.object(news_view, "get_news_by_id", return_value=item), patch.object(
            news_view.templates, "TemplateResponse", return_value="rendered"
        ) as render:
            response = news_view.news_detail(FakeRequest(), 41)

        self.assertEqual(response, "rendered")
        self.assertEqual(render.call_args.kwargs["context"]["news"], item)

    def test_bulk_instagram_generation_returns_successful_ids(self):
        with patch.object(news_view, "create_instagram_draft") as create_draft:
            response = news_view.bulk_action(
                FakeRequest(),
                action="instagram_generate",
                news_ids=[11, 12],
            )

        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 200)
        self.assertTrue(payload["success"])
        self.assertEqual(payload["completed_ids"], [11, 12])
        self.assertEqual(payload["failed_ids"], [])
        self.assertEqual(create_draft.call_count, 2)

    def test_bulk_instagram_generation_limits_selection_to_three(self):
        response = news_view.bulk_action(
            FakeRequest(),
            action="instagram_generate",
            news_ids=[1, 2, 3, 4],
        )

        payload = json.loads(response.body)
        self.assertEqual(response.status_code, 422)
        self.assertFalse(payload["success"])
        self.assertIn("en fazla 3", payload["message"])


if __name__ == "__main__":
    unittest.main()
