"""Persist attempt timings without storing prompts or changing source content."""
from datetime import UTC, datetime, timedelta
from app.config import AI_MAX_ATTEMPTS, AI_RETRY_DELAY_MINUTES, AI_TIMEOUT
from app.models.news import News


def utc(value):
    return value.replace(tzinfo=UTC) if value.tzinfo is None else value.astimezone(UTC)


def start_timing(db, news, input_text):
    now = datetime.now(UTC)
    news.ai_run_started_at = now
    news.ai_run_finished_at = None
    news.ai_run_seconds = None
    news.ai_model_seconds = None
    news.ai_input_chars = len(input_text)
    news.ai_queue_wait_seconds = max(0, int((now - utc(news.created_at)).total_seconds()))
    db.commit()


def finish_timing(news, elapsed, metrics=None):
    news.ai_run_finished_at = datetime.now(UTC)
    news.ai_run_seconds = max(0, round(elapsed))
    if metrics is not None:
        news.ai_model_seconds = max(0, round(metrics.get("ollama_time", 0)))


def safe_ai_error(error):
    import httpx
    if isinstance(error, httpx.TimeoutException):
        return f"AI bağlantısı zaman aşımına uğradı (istek sınırı {AI_TIMEOUT} saniye)."
    return str(error)[:1000]


def recover_interrupted_runs():
    """Startup only: release attempts left unfinished by a stopped process."""
    from app.database.database import SessionLocal
    with SessionLocal() as db:
        rows = db.query(News).filter(News.ai_run_started_at.isnot(None), News.ai_run_finished_at.is_(None)).all()
        now = datetime.now(UTC)
        for news in rows:
            news.ai_run_finished_at = now
            # Unknown interrupted duration must not be presented as a measurement.
            news.ai_run_seconds = None
            if not news.ai_processed and news.status in ("new", "ai_pending", "ai_error"):
                news.ai_attempts = (news.ai_attempts or 0) + 1
                news.ai_last_error = "Uygulama durduğu için AI işlemi yarım kaldı."
                news.status = "ai_failed" if news.ai_attempts >= AI_MAX_ATTEMPTS else "ai_error"
                news.ai_next_retry_at = None if news.status == "ai_failed" else now + timedelta(minutes=AI_RETRY_DELAY_MINUTES)
        db.commit()
        return len(rows)
