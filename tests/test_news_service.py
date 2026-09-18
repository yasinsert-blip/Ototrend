import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.services import news_service


def source(name: str, rss_url: str) -> SimpleNamespace:
    return SimpleNamespace(
        name=name,
        rss_url=rss_url,
        scraper="RSS",
        enabled=True,
    )


class NewsServiceTests(unittest.TestCase):
    @patch("builtins.print")
    def test_duplicate_generic_feed_is_downloaded_once(self, _print):
        sources = [
            source("Marka A", "https://example.test/feed/"),
            source("Marka B", "https://EXAMPLE.test/feed"),
        ]
        fetched = []
        successful = []

        def fake_rss(**kwargs):
            fetched.append(kwargs)
            return [{"title": "Yeni haber", "link": "https://example.test/news"}]

        with (
            patch.object(news_service, "get_enabled_sources", return_value=sources),
            patch.object(news_service, "get_scraper_function", return_value=fake_rss),
            patch.object(news_service, "mark_source_run"),
            patch.object(
                news_service,
                "mark_source_success",
                side_effect=lambda name, count: successful.append((name, count)),
            ),
            patch.object(news_service, "save_news", return_value=[object()]),
        ):
            result = news_service.update_news()

        self.assertEqual(result, 1)
        self.assertEqual(len(fetched), 1)
        self.assertTrue(fetched[0]["raise_on_error"])
        self.assertEqual(successful, [("Marka A", 1), ("Marka B", 0)])

    @patch("builtins.print")
    def test_duplicate_feed_failure_is_recorded_for_each_source(self, _print):
        sources = [
            source("Marka A", "https://example.test/feed"),
            source("Marka B", "https://example.test/feed"),
        ]
        errors = []

        def unavailable_rss(**_kwargs):
            raise ConnectionError("Bağlantı kurulamadı")

        with (
            patch.object(news_service, "get_enabled_sources", return_value=sources),
            patch.object(news_service, "get_scraper_function", return_value=unavailable_rss),
            patch.object(news_service, "mark_source_run"),
            patch.object(
                news_service,
                "mark_source_error",
                side_effect=lambda name, message: errors.append((name, message)) or False,
            ),
            patch.object(news_service, "save_news") as save_news,
        ):
            result = news_service.update_news()

        self.assertEqual(result, 0)
        self.assertEqual([name for name, _ in errors], ["Marka A", "Marka B"])
        save_news.assert_not_called()

    @patch("builtins.print")
    def test_second_scan_is_skipped_while_a_scan_is_running(self, _print):
        self.assertTrue(news_service._news_scan_lock.acquire(blocking=False))
        try:
            self.assertIsNone(news_service.update_news())
        finally:
            news_service._news_scan_lock.release()


if __name__ == "__main__":
    unittest.main()
