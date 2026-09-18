from collections import Counter
from datetime import UTC, datetime, timedelta

from sqlalchemy import func, or_
from sqlalchemy.orm import Session

from app.models.news import News
from app.models.source import Source


def get_dashboard_stats(db: Session) -> dict:
    """
    Dashboard ve Editor ekranlarında kullanılacak
    genel istatistikleri döndürür.
    """

    visible_news = db.query(News).filter(
        or_(News.status.is_(None), News.status != "deleted")
    )

    status_counts = dict(
        visible_news.with_entities(News.status, func.count(News.id))
        .group_by(News.status)
        .all()
    )

    today = datetime.now(UTC).date()
    days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    cutoff = datetime.combine(days[0], datetime.min.time(), tzinfo=UTC)

    recent_dates = visible_news.with_entities(News.created_at).filter(
        News.created_at >= cutoff
    ).all()

    daily_counts = Counter(
        created_at.date()
        for (created_at,) in recent_dates
        if created_at is not None
    )

    return {
        "total_news": sum(status_counts.values()),
        "active_sources": db.query(Source)
        .filter(Source.enabled.is_(True))
        .count(),
        "new": status_counts.get("new", 0),
        "ai_pending": sum(
            status_counts.get(status, 0)
            for status in ("new", "ai_pending", "ai_error")
        ),
        "ai_processed": status_counts.get("ai_processed", 0),
        "ai_ready": status_counts.get("ai_ready", 0),
        "editor_review": status_counts.get("editor_review", 0),
        "instagram_ready": status_counts.get("instagram_ready", 0),
        "scheduled": status_counts.get("scheduled", 0),
        "published": status_counts.get("published", 0),
        "archived": status_counts.get("archived", 0),
        "weekly_news": {
            "labels": [day.strftime("%d.%m") for day in days],
            "values": [daily_counts[day] for day in days],
        },
    }
