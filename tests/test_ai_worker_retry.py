import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.news import News
from app.services import ai_worker


class AIWorkerRetryTests(unittest.TestCase):
    def setUp(self):
        self.temp_directory = tempfile.TemporaryDirectory()
        database_path = Path(self.temp_directory.name) / "ai-worker-retry.db"
        self.engine = create_engine(f"sqlite:///{database_path}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.session_patch = patch.object(ai_worker, "SessionLocal", self.Session)
        self.session_patch.start()

    def tearDown(self):
        self.session_patch.stop()
        self.engine.dispose()
        self.temp_directory.cleanup()

    def _add_news(self, news_id: int = 1) -> None:
        now = datetime.now(UTC)
        db = self.Session()
        db.add(
            News(
                id=news_id,
                title="Test otomobil haberi",
                content=(
                    "Üretici yeni elektrikli otomobilin Avrupa pazarına yönelik üretim planlarını açıkladı. "
                    "Fabrikada gelecek yıl başlayacak üretim için ek çalışanlar alınacak ve mevcut tesisler yenilenecek. "
                    "Şirket batarya kapasitesi, şarj altyapısı, servis hizmetleri ve bayi eğitimleri hakkında bilgi verdi. "
                    "Fiyatlar ile teslimat tarihleri siparişler açılmadan önce her ülke için ayrıca duyurulacak."
                ),
                link=f"https://example.test/{news_id}",
                status="new",
                ai_processed=False,
                created_at=now,
                updated_at=now,
            )
        )
        db.commit()
        db.close()

    @patch("builtins.print")
    def test_timeout_records_duration_and_schedules_retry(self, _print):
        import httpx
        self._add_news()
        with patch.object(ai_worker, "refresh_ai_queue"), patch.object(
            ai_worker, "process", side_effect=httpx.ReadTimeout("private request")
        ), patch.object(ai_worker, "add_failure"), patch.object(ai_worker, "print_summary"):
            ai_worker.process_ai_news(limit=1)
        with self.Session() as db:
            news = db.get(News, 1)
            self.assertEqual(news.status, "ai_error")
            self.assertEqual(news.ai_attempts, 1)
            self.assertIsNotNone(news.ai_next_retry_at)
            self.assertIsNotNone(news.ai_run_started_at)
            self.assertIsNotNone(news.ai_run_finished_at)
            self.assertIsNotNone(news.ai_run_seconds)
            self.assertGreater(news.ai_input_chars, 0)
            self.assertNotIn("private request", news.ai_last_error)
            self.assertFalse(news.telegram_sent)

    @patch("builtins.print")
    def test_failed_draft_waits_then_leaves_automatic_queue(self, _print):
        self._add_news()

        with patch.object(ai_worker, "refresh_ai_queue"), patch.object(
            ai_worker, "process", side_effect=ValueError("Türkçe kalite hatası")
        ), patch.object(ai_worker, "add_failure"), patch.object(
            ai_worker, "print_summary"
        ), patch.object(ai_worker, "AI_MAX_ATTEMPTS", 2), patch.object(
            ai_worker, "AI_RETRY_DELAY_MINUTES", 15
        ):
            ai_worker.process_ai_news(limit=1)

            db = self.Session()
            news = db.get(News, 1)
            self.assertEqual(news.status, "ai_error")
            self.assertEqual(news.ai_attempts, 1)
            self.assertIsNotNone(news.ai_next_retry_at)
            db.close()

            # Bekleme süresi dolmadan aynı haber ikinci kez model çağırmaz.
            ai_worker.process_ai_news(limit=1)

            db = self.Session()
            news = db.get(News, 1)
            news.ai_next_retry_at = datetime.now(UTC) - timedelta(minutes=1)
            db.commit()
            db.close()

            ai_worker.process_ai_news(limit=1)

        db = self.Session()
        news = db.get(News, 1)
        self.assertEqual(news.status, "ai_failed")
        self.assertEqual(news.ai_attempts, 2)
        self.assertIsNone(news.ai_next_retry_at)
        db.close()

    @patch("builtins.print")
    def test_success_clears_previous_retry_state(self, _print):
        self._add_news(2)
        db = self.Session()
        news = db.get(News, 2)
        news.status = "ai_error"
        news.ai_attempts = 1
        news.ai_last_error = "Önceki hata"
        news.ai_next_retry_at = None
        db.commit()
        db.close()

        result = {
            "title_tr": "Türkçe test başlığı",
            "summary_tr": "Türkçe test özeti.",
            "brand": "Test",
            "category": "Other",
            "importance": 7,
        }
        metrics = {
            "prompt_kb": 0.1,
            "prompt_time": 0.1,
            "ollama_time": 0.1,
            "parse_time": 0.1,
            "response_kb": 0.1,
        }

        with (
            patch.object(ai_worker, "refresh_ai_queue"),
            patch.object(ai_worker, "process", return_value=(result, metrics)) as process,
            patch.object(ai_worker, "_should_send_telegram", return_value=False),
            patch.object(ai_worker, "add_success"),
            patch.object(ai_worker, "print_summary"),
        ):
            ai_worker.process_ai_news(limit=1)

        self.assertEqual(process.call_count, 1)

        db = self.Session()
        try:
            news = db.get(News, 2)
            self.assertTrue(news.ai_processed)
            self.assertEqual(news.status, "ai_processed")
            self.assertEqual(news.ai_attempts, 0)
            self.assertIsNone(news.ai_last_error)
            self.assertIsNone(news.ai_next_retry_at)
        finally:
            db.close()


if __name__ == "__main__":
    unittest.main()
