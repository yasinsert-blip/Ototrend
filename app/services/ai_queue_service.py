"""AI işlem kuyruğunu güncel ve editöre anlamlı olacak şekilde tutar."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta

from sqlalchemy import and_, or_

from app.config import AI_QUEUE_MAX_AGE_HOURS, AI_REVIEW_MIN_IMPORTANCE
from app.database.database import SessionLocal
from app.models.news import News
from app.services.news_value import score_recent_unrated


ACTIVE_AI_STATUSES = ("new", "ai_pending", "ai_error")


@dataclass(frozen=True)
class AIQueueRefreshResult:
    promoted_to_review: int = 0
    marked_processed: int = 0
    skipped_as_stale: int = 0


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def review_status_for_importance(value: object) -> str:
    """AI puanını editöryal yönlendirme durumuna çevirir."""
    try:
        importance = int(value)
    except (TypeError, ValueError):
        importance = 0
    return "ai_ready" if importance >= AI_REVIEW_MIN_IMPORTANCE else "ai_processed"


def refresh_ai_queue(now: datetime | None = None) -> AIQueueRefreshResult:
    """Tarihi geçmiş ve önemsiz kayıtları AI/editör kuyruğundan çıkarır."""
    current_time = _utc_now(now)
    cutoff = current_time - timedelta(hours=AI_QUEUE_MAX_AGE_HOURS)
    db = SessionLocal()

    try:
        score_recent_unrated(db, current_time)
        active_status = News.status.in_(ACTIVE_AI_STATUSES)
        current_high_importance = and_(
            News.created_at >= cutoff,
            News.importance >= AI_REVIEW_MIN_IMPORTANCE,
        )

        promoted_to_review = (
            db.query(News)
            .filter(News.ai_processed.is_(True), active_status, current_high_importance)
            .update(
                {News.status: "ai_ready", News.updated_at: current_time},
                synchronize_session=False,
            )
        )

        marked_processed = (
            db.query(News)
            .filter(
                News.ai_processed.is_(True),
                active_status,
                or_(
                    News.created_at < cutoff,
                    News.importance.is_(None),
                    News.importance < AI_REVIEW_MIN_IMPORTANCE,
                ),
            )
            .update(
                {News.status: "ai_processed", News.updated_at: current_time},
                synchronize_session=False,
            )
        )

        skipped_as_stale = (
            db.query(News)
            .filter(
                News.ai_processed.is_(False),
                active_status,
                News.created_at < cutoff,
            )
            .update(
                {
                    News.status: "ai_skipped",
                    News.updated_at: current_time,
                    News.ai_last_error: f"Haber otomatik AI kuyruğunun {AI_QUEUE_MAX_AGE_HOURS} saatlik yaş sınırını geçti; manuel incelemeye bırakıldı.",
                    News.ai_next_retry_at: None,
                },
                synchronize_session=False,
            )
        )
        db.commit()
        return AIQueueRefreshResult(
            promoted_to_review=promoted_to_review,
            marked_processed=marked_processed,
            skipped_as_stale=skipped_as_stale,
        )
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
