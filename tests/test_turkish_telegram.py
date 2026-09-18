import tempfile
import unittest
from datetime import UTC, datetime, timedelta
from pathlib import Path
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from app.database.database import Base
from app.database import crud
from app.models.news import News
from app.models.source import Source
from app.services import turkish_telegram as queue
from app.services.ai_worker import _should_send_telegram


class TurkishTelegramTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.engine = create_engine(f"sqlite:///{Path(self.temp.name) / 'telegram.db'}")
        Base.metadata.create_all(self.engine)
        self.Session = sessionmaker(bind=self.engine, expire_on_commit=False)
        self.patches = [patch.object(module, 'SessionLocal', self.Session) for module in (crud, queue)]
        for item in self.patches:
            item.start()
        with self.Session() as db:
            db.add_all([
                Source(name='Motor1 Türkiye', scraper='Motor1TR', language='tr', country='Türkiye'),
                Source(name='LOG', scraper='LOG', website='https://www.log.com.tr', language='en', country='Global'),
                Source(name='Reuters Otomotiv (Google Haberler)', scraper='RSS', language='en', country='Global'),
            ])
            db.commit()
        self.now = datetime.now(UTC) + timedelta(seconds=1)

    def tearDown(self):
        for item in self.patches:
            item.stop()
        self.engine.dispose()
        self.temp.cleanup()

    def add(self, source='Motor1TR', number=1):
        return crud.save_news([dict(title='Kaynağın özgün otomobil başlığı', source=source,
            link=f'https://example.test/{number}', content='Kısa metin')])[0]

    def test_new_turkish_short_item_is_sent_without_ai(self):
        row = self.add()
        self.assertTrue(row.turkish_telegram_pending)
        self.assertEqual(row.status, 'ai_skipped')
        self.assertFalse(_should_send_telegram(row))
        with patch.object(queue, 'send_telegram_message', return_value=True) as send:
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 1)
            self.assertIn('Kaynağın özgün otomobil başlığı', send.call_args.args[0])
            self.assertIn('https://example.test/1', send.call_args.args[0])
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 0)
            self.assertEqual(send.call_count, 1)
        with self.Session() as db:
            self.assertTrue(db.get(News, row.id).telegram_sent)
            self.assertFalse(db.get(News, row.id).ai_processed)

    def test_ai_failure_duplicate_and_fact_warning_do_not_block_source_notice(self):
        row = self.add()
        with self.Session() as db:
            item = db.get(News, row.id)
            item.status = 'ai_failed'
            item.is_duplicate = True
            item.fact_check_notes = 'Hatalı AI metni'
            item.translated_title = 'Yanlış üretilen başlık'
            db.commit()
        with patch.object(queue, 'send_telegram_message', return_value=True) as send:
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 1)
            self.assertNotIn('Yanlış üretilen', send.call_args.args[0])

    def test_failure_is_retried_after_delay_and_survives_new_session(self):
        row = self.add()
        with patch.object(queue, 'send_telegram_message', return_value=False) as send:
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 0)
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 0)
            self.assertEqual(send.call_count, 1)
        with self.Session() as db:
            self.assertTrue(db.get(News, row.id).turkish_telegram_pending)
            self.assertIsNotNone(db.get(News, row.id).telegram_last_error)
        with patch.object(queue, 'send_telegram_message', return_value=True):
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now + timedelta(minutes=2)), 1)

    def test_foreign_translated_news_and_archive_are_not_enqueued(self):
        row = self.add(source='Reuters Otomotiv (Google Haberler)')
        self.assertFalse(row.turkish_telegram_pending)
        with self.Session() as db:
            db.add(News(title='Eski Türk haberi', source='LOG', link='https://example.test/old',
                        created_at=self.now - timedelta(days=10)))
            db.commit()
        with patch.object(queue, 'send_telegram_message') as send:
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 0)
            send.assert_not_called()

    def test_tr_domain_matches_and_duplicate_import_does_not_enqueue_twice(self):
        self.assertTrue(self.add(source='LOG').turkish_telegram_pending)
        self.assertEqual(crud.save_news([dict(title='Tekrar', source='LOG', link='https://example.test/1')]), [])

    def test_deleted_news_is_not_sent(self):
        row = self.add()
        with self.Session() as db:
            db.get(News, row.id).status = 'deleted'
            db.commit()
        with patch.object(queue, 'send_telegram_message') as send:
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 0)
            send.assert_not_called()

    def test_active_lease_blocks_another_delivery(self):
        row = self.add()
        with self.Session() as db:
            db.get(News, row.id).telegram_next_retry_at = self.now + timedelta(minutes=5)
            db.commit()
        with patch.object(queue, 'send_telegram_message') as send:
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 0)
            send.assert_not_called()

    def test_exception_is_retried_without_sensitive_error_text(self):
        row = self.add()
        with patch.object(queue, 'send_telegram_message', side_effect=RuntimeError('secret-token')):
            self.assertEqual(queue.deliver_turkish_notifications(now=self.now), 0)
        with self.Session() as db:
            self.assertNotIn('secret-token', db.get(News, row.id).telegram_last_error)

    def test_long_unicode_message_fits_telegram_limit(self):
        text = queue.notification_text(News(id=1, title='🚗' * 1000, source='🚗' * 100, link='https://example.test/' + '🚗' * 3000))
        self.assertLessEqual(len(text.encode('utf-16-le')) // 2, 4000)

    def test_country_and_turkish_source_aliases_are_recognized(self):
        keys = queue.turkish_source_keys([
            Source(name='DonanımHaber', scraper='DonanimHaber', language='tr-TR'),
            Source(name='Türk üretici', country='TR', language='en', scraper='RSS'),
        ])
        self.assertIn(queue.source_key('DonanimHaber'), keys)
        self.assertIn(queue.source_key('Türk üretici'), keys)
        self.assertNotIn('rss', keys)
