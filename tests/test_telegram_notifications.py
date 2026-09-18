import unittest
from datetime import UTC, datetime
from types import SimpleNamespace
from unittest.mock import patch

from app.services.ai_worker import _should_send_telegram


class TelegramNotificationTests(unittest.TestCase):
    def test_only_news_after_notification_cutoff_is_eligible(self):
        with patch(
            "app.services.ai_worker.TELEGRAM_NOTIFY_AFTER",
            "2026-08-15T12:00:00+00:00",
        ):
            old_news = SimpleNamespace(
                created_at=datetime(2026, 8, 15, 11, 59, tzinfo=UTC),
                telegram_sent=False,
            )
            new_news = SimpleNamespace(
                created_at=datetime(2026, 8, 15, 12, 1, tzinfo=UTC),
                telegram_sent=False,
            )

            self.assertFalse(_should_send_telegram(old_news))
            self.assertTrue(_should_send_telegram(new_news))

    def test_already_sent_news_is_never_sent_again(self):
        with patch(
            "app.services.ai_worker.TELEGRAM_NOTIFY_AFTER",
            "2026-08-15T12:00:00+00:00",
        ):
            news = SimpleNamespace(
                created_at=datetime(2026, 8, 15, 12, 1, tzinfo=UTC),
                telegram_sent=True,
            )
            self.assertFalse(_should_send_telegram(news))


if __name__ == "__main__":
    unittest.main()
