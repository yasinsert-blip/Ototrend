import unittest
from unittest.mock import patch

from fastapi import FastAPI
from starlette.requests import Request
from starlette.staticfiles import StaticFiles

from app.models.news import News
from app.scrapers.rss.common import _feed_image_url
from app.services import visual_source_service
from app.views.news import instagram_editor


class VisualSourceServiceTests(unittest.TestCase):
    def test_extract_article_image_prefers_open_graph(self):
        html = """
            <html><head>
                <meta property="og:image" content="/images/model.jpg">
                <meta name="twitter:image" content="/images/ignored.jpg">
            </head></html>
        """

        with patch.object(
            visual_source_service,
            "is_public_http_url",
            return_value=True,
        ):
            image_url = visual_source_service.extract_article_image(
                html,
                "https://example.com/news/model",
            )

        self.assertEqual(image_url, "https://example.com/images/model.jpg")

    def test_extract_article_image_uses_json_ld_when_metadata_missing(self):
        html = """
            <script type="application/ld+json">
                {"@type":"NewsArticle","image":{"url":"https://cdn.example/car.jpg"}}
            </script>
        """

        with patch.object(
            visual_source_service,
            "is_public_http_url",
            return_value=True,
        ):
            image_url = visual_source_service.extract_article_image(
                html,
                "https://example.com/news/model",
            )

        self.assertEqual(image_url, "https://cdn.example/car.jpg")

    def test_only_reusable_licenses_are_accepted(self):
        self.assertTrue(
            visual_source_service._is_reusable_license("CC BY-SA 4.0", "")
        )
        self.assertTrue(
            visual_source_service._is_reusable_license("", "Public domain")
        )
        self.assertFalse(
            visual_source_service._is_reusable_license("CC BY-NC 4.0", "")
        )
        self.assertFalse(
            visual_source_service._is_reusable_license("All rights reserved", "")
        )

    def test_feed_image_uses_media_rss_before_enclosure(self):
        item = {
            "media_content": [{"url": "/media/main.jpg"}],
            "enclosures": [{"type": "image/jpeg", "href": "/media/second.jpg"}],
        }

        image_url = _feed_image_url(item, "https://example.com/rss")

        self.assertEqual(image_url, "https://example.com/media/main.jpg")

    def test_instagram_editor_renders_automatic_visual_status(self):
        app = FastAPI()
        app.mount("/static", StaticFiles(directory="app/static"), name="static")
        request = Request(
            {
                "type": "http",
                "method": "GET",
                "path": "/instagram/7",
                "headers": [],
                "app": app,
                "session": {"authenticated": True},
            }
        )
        news = News(
            id=7,
            title="Test haberi",
            link="https://example.com/test",
        )

        with patch("app.views.news.get_news_by_id", return_value=news), patch(
            "app.views.news.get_selected_visual", return_value=None
        ):
            response = instagram_editor(request, 7)

        self.assertIn("Otomatik görsel kaynağı", response.body.decode("utf-8"))
        self.assertIn("Görsel bulunamadı", response.body.decode("utf-8"))


if __name__ == "__main__":
    unittest.main()
