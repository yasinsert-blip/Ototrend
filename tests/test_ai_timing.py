import unittest
from datetime import UTC, datetime, timedelta
from unittest.mock import patch

from jinja2 import Environment, FileSystemLoader, select_autoescape
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.database.database import Base
from app.models.news import News
from app.services.ai_timing import start_timing, finish_timing, recover_interrupted_runs


class TimingTests(unittest.TestCase):
    def setUp(self):
        self.engine = create_engine('sqlite://')
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine)

    def tearDown(self):
        self.engine.dispose()

    def test_running_and_finished_measurements(self):
        with self.Session() as db:
            news = News(title='Test', link='https://example.test/1', content='Kaynak',
                        status='ai_pending', created_at=datetime.now(UTC)-timedelta(seconds=60))
            db.add(news)
            db.commit()
            start_timing(db, news, 'Girdi')
            with self.Session() as other:
                self.assertIsNotNone(other.get(News, news.id).ai_run_started_at)
            self.assertEqual(news.ai_input_chars, 5)
            self.assertGreaterEqual(news.ai_queue_wait_seconds, 59)
            finish_timing(news, 12.4, {'ollama_time': 10.2})
            db.commit()
            self.assertEqual(news.ai_run_seconds, 12)
            self.assertEqual(news.ai_model_seconds, 10)
            self.assertEqual(news.content, 'Kaynak')

    def test_startup_recovers_with_retry_limit_and_preserves_telegram(self):
        with self.Session() as db:
            for number, attempts in [(1, 0), (2, 2)]:
                db.add(News(title='Test', link=f'https://example.test/{number}', content='Kaynak',
                            status='ai_pending', ai_attempts=attempts, telegram_sent=True,
                            ai_run_started_at=datetime.now(UTC)))
            db.commit()
        with patch('app.database.database.SessionLocal', self.Session), patch('app.services.ai_timing.AI_MAX_ATTEMPTS', 3):
            self.assertEqual(recover_interrupted_runs(), 2)
            self.assertEqual(recover_interrupted_runs(), 0)
        with self.Session() as db:
            rows = db.query(News).order_by(News.id).all()
            self.assertEqual(rows[0].status, 'ai_error')
            self.assertIsNotNone(rows[0].ai_next_retry_at)
            self.assertEqual(rows[1].status, 'ai_failed')
            self.assertIsNone(rows[1].ai_next_retry_at)
            for news in rows:
                self.assertTrue(news.telegram_sent)
                self.assertEqual(news.content, 'Kaynak')
                self.assertIsNone(news.ai_run_seconds)

    def test_template_shows_independent_states_and_escapes_errors(self):
        template = Environment(loader=FileSystemLoader('app/templates'), autoescape=select_autoescape()).get_template('partials/news_runtime_status.html')
        news = dict(status='ai_pending', ai_run_started_at=True, telegram_sent=True)
        html = template.render(news=news)
        self.assertIn('AI işleniyor', html)
        self.assertIn('Telegram gönderildi', html)
        news.update(status='ai_error', ai_run_finished_at=True, ai_next_retry_at=True, ai_last_error='<script>bad</script>')
        html = template.render(news=news)
        self.assertIn('yeniden deneme bekliyor', html)
        self.assertNotIn('<script>', html)

    def test_ollama_client_has_configured_timeout(self):
        from app.ai.provider import client
        from app.config import AI_TIMEOUT
        self.assertEqual(client._client.timeout.read, AI_TIMEOUT)
        self.assertEqual(client._client.timeout.connect, 10)
