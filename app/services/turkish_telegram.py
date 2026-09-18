"""Durable source-headline notifications, independent of AI processing."""
import unicodedata
from datetime import UTC, datetime, timedelta
from threading import Lock
from urllib.parse import urlsplit

from sqlalchemy import or_

from app.database.database import SessionLocal
from app.models.news import News
from app.services.news_selection import plain_text
from app.services.telegram_service import send_telegram_message

_lock = Lock()


def source_key(value):
    return "".join(c for c in unicodedata.normalize("NFKD", (value or "").casefold().replace("ı", "i")) if c.isalnum())


def turkish_source_keys(sources):
    keys = set()
    for source in sources:
        language = (source.language or "").lower().replace("_", "-").split("-")[0]
        country = source_key(source.country)
        try:
            host = (urlsplit(source.website or "").hostname or "").lower()
        except ValueError:
            host = ""
        if language == "tr" or country in ("tr", "tur", "turkiye", "turkey") or host.endswith(".tr"):
            keys.add(source_key(source.name))
            if source.scraper and source.scraper.lower() not in ("rss", "html", "browser"):
                keys.add(source_key(source.scraper))
    return keys - {""}


def notification_text(news):
    # No translated or generated fields. Plain text; no Telegram HTML parsing.
    message = ("🇹🇷 Türk kaynak bildirimi\n\n"
            + plain_text(news.title)[:700] + "\n\n"
            + "Kaynak: " + plain_text(news.source)[:100] + "\n"
            + f"Haber: #{news.id}\n"
            + (news.link or "")[:2200]
            + "\n\nKaynak başlığıdır; AI doğruluk onayı değildir.")
    return message.encode("utf-16-le")[:8000].decode("utf-16-le", errors="ignore")


def deliver_turkish_notifications(limit=10, now=None):
    """Retry pending imports, including AI-skipped/duplicate/failed records.

    New imports alone set the pending flag. Existing archive is never enqueued.
    A committed lease prevents competing workers from claiming the same row.
    """
    if not _lock.acquire(blocking=False):
        return 0
    current = now or datetime.now(UTC)
    sent = 0
    try:
        with SessionLocal() as db:
            ids = [row.id for row in db.query(News.id).filter(
                News.turkish_telegram_pending.is_(True),
                News.telegram_sent.isnot(True),
                News.status != "deleted",
                or_(News.telegram_next_retry_at.is_(None), News.telegram_next_retry_at <= current),
            ).order_by(News.created_at, News.id).limit(limit).all()]
        for news_id in ids:
            with SessionLocal() as db:
                claimed = db.query(News).filter(
                    News.id == news_id, News.turkish_telegram_pending.is_(True),
                    News.telegram_sent.isnot(True), News.status != "deleted",
                    or_(News.telegram_next_retry_at.is_(None), News.telegram_next_retry_at <= current),
                ).update({News.telegram_next_retry_at: current + timedelta(minutes=5)}, synchronize_session=False)
                db.commit()
                if not claimed:
                    continue
                news = db.get(News, news_id)
                message = notification_text(news)
                attempts = int(news.telegram_attempts or 0) + 1
            try:
                success = send_telegram_message(message)
            except Exception:
                # Never log request URLs: they contain the Telegram bot token.
                success = False
            with SessionLocal() as db:
                values = {News.telegram_attempts: attempts}
                if success:
                    values.update({News.telegram_sent: True, News.turkish_telegram_pending: False,
                                   News.telegram_next_retry_at: None, News.telegram_last_error: None})
                    sent += 1
                else:
                    minutes = min(60, 2 ** min(attempts - 1, 6))
                    values.update({News.telegram_next_retry_at: current + timedelta(minutes=minutes),
                                   News.telegram_last_error: "Gönderim doğrulanamadı; yeniden denenecek."})
                db.query(News).filter(News.id == news_id).update(values, synchronize_session=False)
                db.commit()
        return sent
    finally:
        _lock.release()
