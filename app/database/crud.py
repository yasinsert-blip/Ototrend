import logging
from datetime import datetime, UTC, timedelta
from email.utils import parsedate_to_datetime

from sqlalchemy import desc, or_, func

from app.database.database import SessionLocal
from app.models.news import News
from app.models.source import Source
from app.services.turkish_telegram import turkish_source_keys, source_key
from app.services.news_selection import select_for_ai, UNUSABLE_PARENT_STATUSES
from app.services.news_value import score_news

logger = logging.getLogger(__name__)


VALID_STATUS = {
    "new",
    "ai_pending",
    "ai_processed",
    "ai_skipped",
    "ai_ready",
    "editor_review",
    "instagram_draft",
    "instagram_ready",
    "scheduled",
    "published",
    "archived",
    "deleted",
    "ai_error",
    "ai_failed",
}
def validate_status(status: str) -> None:
    """
    Validate workflow status.
    """
    if status not in VALID_STATUS:
        raise ValueError(f"Geçersiz status: {status}")

def parse_published_at(
    value: str | datetime | None,
) -> datetime | None:
    if not value:
        return None

    if isinstance(value, datetime):
        return value

    try:
        return parsedate_to_datetime(value)
    except Exception:
        return None


# ==========================================================
# HABER KAYDET
# ==========================================================

def save_news(
    news_list: list[dict],
) -> list[News]:

    db = SessionLocal()

    new_news = []

    duplicate_link = 0

    try:
        turkish_keys = turkish_source_keys(db.query(Source).all())

        for item in news_list:

            title = item.get("title")

            link = item.get("link")


            if not title or not link:
                continue


            # Link duplicate kontrolü
            exists = None

            if link:

                exists = (
                    db.query(News)
                    .filter(
                        News.link == link
                    )
                    .first()
                )


            if exists:

                duplicate_link += 1

                logger.info(
                    "Duplicate link: %s",
                    title,
                )

                continue



            news = News(

                title=title,

                translated_title=item.get(
                    "title_tr"
                ),

                summary=item.get(
                    "summary_tr"
                ),

                content=(
                    item.get("content")
                    or item.get("description")
                ),

                link=link,

                source=item.get(
                    "source"
                ),

                author=item.get(
                    "author"
                ),

                image_url=item.get(
                    "image_url"
                ),

                language=item.get(
                    "language",
                    "en",
                ),

                published_at=parse_published_at(
                    item.get(
                        "published_at"
                    )
                ),


                # Workflow başlangıcı

                status="new",

                ai_processed=False,

                published=False,

            )


            score_news(news)
            news.turkish_telegram_pending = source_key(news.source) in turkish_keys
            select_for_ai(db, news)
            db.add(news)
            db.flush()  # Make same-batch links and headline groups visible.

            new_news.append(news)


        db.commit()


        logger.info(
            "News import completed | New=%s | DuplicateLink=%s",
            len(new_news),
            duplicate_link,
        )


        return new_news


    except Exception:

        db.rollback()

        logger.exception(
            "Save news failed. Incoming news count=%d",
            len(news_list),
        )

        raise


    finally:

        db.close()


# ==========================================================
# HABERLER
# ==========================================================

def _visible_news_query(db):
    """Kullanıcı arayüzünde silinmiş kayıtları varsayılan olarak gizler."""
    return db.query(News).filter(
        or_(News.status.is_(None), News.status != "deleted")
    )

def get_news(
    keyword=None,
    source=None,
    category=None,
    status=None,
    page=1,
    page_size=20,
    brand=None,
    min_importance=0,
    sort="newest",
    section="all",
):
    page_size = min(max(int(page_size), 1), 100)
    db = SessionLocal()

    try:

        query = _visible_news_query(db)
        if section != "all":
            query = query.filter(or_(News.published.is_(None), News.published.is_(False)))

        if section == "important":
            query = query.filter(News.news_value >= 60,
                News.created_at >= datetime.now(UTC) - timedelta(hours=48),
                News.status.notin_(["archived", "published"]))
        elif section == "review":
            query = query.filter(News.status.notin_(["archived", "published"]),
                or_(News.status.in_(["ai_ready", "editor_review", "ai_failed"]),
                    News.fact_check_notes.isnot(None) & (News.fact_check_notes != "")))
        elif section == "ready":
            query = query.filter(News.status.in_(["instagram_ready", "scheduled"]),
                or_(News.fact_check_notes.is_(None), News.fact_check_notes == ""))

        # Unfiltered overview shows one row per group; filters retain access
        # to every source and to skipped records. Missing parents never hide rows.
        if section in ("all", "important") and not any((keyword, source, category, status, brand, min_importance)):
            from sqlalchemy.orm import aliased
            parent = aliased(News)
            parent_exists = db.query(parent.id).filter(
                parent.id == News.duplicate_of_id,
                parent.status.notin_(UNUSABLE_PARENT_STATUSES),
            ).exists()
            query = query.filter(or_(News.duplicate_of_id.is_(None), ~parent_exists))

        if keyword:
            escaped_keyword = (
                keyword
                .replace("\\", "\\\\")
                .replace("%", "\\%")
                .replace("_", "\\_")
            )
            search_pattern = f"%{escaped_keyword}%"

            query = query.filter(
                or_(
                    News.title.ilike(search_pattern, escape="\\"),
                    News.translated_title.ilike(search_pattern, escape="\\"),
                    News.source.ilike(search_pattern, escape="\\"),
                    News.summary.ilike(search_pattern, escape="\\"),
                )
            )

        if source:
            query = query.filter(
                News.source == source
            )

        if category:
            query = query.filter(
                News.category == category
            )

        if status:
            query = query.filter(
                News.status == status
            )

        if brand:
            query = query.filter(News.brand == brand)
        if min_importance:
            query = query.filter(News.importance >= min_importance)

        ordering = {
            "news_value": (func.coalesce(News.news_value, 20).desc(), News.created_at.desc(), News.id.desc()),
            "newest": (News.created_at.desc(), News.id.desc()),
            "oldest": (News.created_at.asc(), News.id.asc()),
            "importance": (News.importance.desc(), News.created_at.desc(), News.id.desc()),
        }.get(sort, (News.created_at.desc(), News.id.desc()))

        total = query.count()
        total_pages = max(1, (total + page_size - 1) // page_size)
        page = min(max(page, 1), total_pages)

        items = (
            query
            .order_by(*ordering)
            .offset((page - 1) * page_size)
            .limit(page_size)
            .all()
        )

        grouped = {item.id: [] for item in items}
        if grouped:
            related = _visible_news_query(db).filter(
                News.duplicate_of_id.in_(list(grouped))
            ).order_by(News.id).all()
            for row in related:
                grouped[row.duplicate_of_id].append(row)
        for item in items:
            item.related_sources = grouped[item.id]

        return {
            "total": total,
            "page": page,
            "page_size": page_size,
            "total_pages": total_pages,
            "items": items,
        }

    finally:

        db.close()


# ==========================================================
# DETAY
# ==========================================================

def get_news_by_id(
    news_id: int,
) -> News | None:

    db = SessionLocal()

    try:

        news = (
            _visible_news_query(db)
            .filter(News.id == news_id)
            .first()
        )
        if news is not None:
            news.related_sources = _visible_news_query(db).filter(
                News.duplicate_of_id == news.id
            ).order_by(News.id).all()
            news.group_parent = None
            if news.duplicate_of_id:
                news.group_parent = _visible_news_query(db).filter(
                    News.id == news.duplicate_of_id,
                    News.status.notin_(UNUSABLE_PARENT_STATUSES),
                ).first()
        return news

    finally:

        db.close()

# ==========================================================
# EDITOR
# ==========================================================

def update_news_editor(
    news_id: int,
    translated_title: str,
    summary: str,
    category: str,
    brand: str,
    importance: int,
    editor_note: str,
):

    db = SessionLocal()

    try:

        news = (
            _visible_news_query(db)
            .filter(News.id == news_id)
            .first()
        )

        if news is None:
            return None

        news.translated_title = translated_title
        news.summary = summary
        news.category = category
        news.brand = brand
        news.importance = importance
        news.editor_note = editor_note
        news.updated_at = datetime.now(UTC)

        if news.status == "ai_ready":
            news.status = "editor_review"

        db.commit()
        db.refresh(news)

        return news

    except Exception:
        db.rollback()
        logger.exception(
            "Editor update failed. News ID=%s",
            news_id,
        )

        raise

    finally:

        db.close()


# ==========================================================
# INSTAGRAM
# ==========================================================

def update_instagram_content(
    news_id: int,
    instagram_title: str,
    instagram_caption: str,
    hashtags: str,
    image_prompt: str,
    mark_as_draft: bool = True,
    fact_check_notes: str | None = None,
):

    db = SessionLocal()

    try:

        news = (
            _visible_news_query(db)
            .filter(News.id == news_id)
            .first()
        )

        if news is None:
            return None

        news.instagram_title = instagram_title
        news.instagram_caption = instagram_caption
        news.hashtags = hashtags
        news.image_prompt = image_prompt
        news.updated_at = datetime.utcnow()
        if mark_as_draft:
            news.status = "instagram_draft"
        if fact_check_notes:
            news.fact_check_notes = "\n".join(dict.fromkeys(
                (news.fact_check_notes or "").splitlines() + fact_check_notes.splitlines()
            ))
        if news.fact_check_notes:
            news.status = "editor_review"

        db.commit()
        db.refresh(news)

        return news

    except Exception:
        db.rollback()
        logger.exception(
            "Instagram content update failed. News ID=%s",
            news_id,
        )

        raise

    finally:

        db.close()


# ==========================================================
# STATUS
# ==========================================================

def update_news_status(
    news_id: int,
    status: str,
):

    validate_status(status)

    db = SessionLocal()

    try:

        news = (
            _visible_news_query(db)
            .filter(News.id == news_id)
            .first()
        )

        if news is None:
            return None

        news.status = status
        if status == "published":
            news.published = True
        news.updated_at = datetime.utcnow()

        db.commit()
        db.refresh(news)

        return news

    except Exception:
        db.rollback()
        logger.exception(
            "Status update failed. News ID=%s",
            news_id,
        )

        raise

    finally:

        db.close()

# ==========================================================
# DASHBOARD
# ==========================================================

def get_news_count():

    db = SessionLocal()

    try:

        return _visible_news_query(db).count()

    finally:

        db.close()


def get_source_count():

    db = SessionLocal()

    try:

        return (
            _visible_news_query(db).with_entities(News.source)
            .distinct()
            .count()
        )

    finally:

        db.close()


def get_ai_pending_count():

    db = SessionLocal()

    try:

        return (
            db.query(News)
            .filter(
                News.ai_processed == False,
                News.status.in_(("new", "ai_pending", "ai_error")),
            )
            .count()
        )

    finally:

        db.close()


def get_ai_ready_count():

    db = SessionLocal()

    try:

        return (
            db.query(News)
            .filter(News.status == "ai_ready")
            .count()
        )

    finally:

        db.close()


def get_published_count():

    db = SessionLocal()

    try:

        return (
            _visible_news_query(db)
            .filter(News.status == "published")
            .count()
        )

    finally:

        db.close()


def get_duplicate_count():

    db = SessionLocal()

    try:

        return (
            db.query(News)
            .filter(News.is_duplicate == True)
            .count()
        )

    finally:

        db.close()

# ==========================================================
# DROPDOWNLAR
# ==========================================================

def get_sources():

    db = SessionLocal()

    try:

        rows = (
            _visible_news_query(db).with_entities(News.source)
            .distinct()
            .order_by(News.source)
            .all()
        )

        return [row[0] for row in rows if row[0]]

    finally:

        db.close()


def get_categories():

    db = SessionLocal()

    try:

        rows = (
            _visible_news_query(db).with_entities(News.category)
            .distinct()
            .order_by(News.category)
            .all()
        )

        return [row[0] for row in rows if row[0]]

    finally:

        db.close()

def get_brands():

    db = SessionLocal()

    try:

        rows = (
            _visible_news_query(db).with_entities(News.brand)
            .distinct()
            .order_by(News.brand)
            .all()
        )

        return [row[0] for row in rows if row[0]]

    finally:

        db.close()

# ==========================================================
# EDITOR LIST
# ==========================================================

def get_editor_news(
    limit: int = 100,
) -> list[News]:

    db = SessionLocal()

    try:

        return (
            _visible_news_query(db)
            .order_by(desc(News.created_at))
            .limit(limit)
            .all()
        )

    finally:

        db.close()


def get_news_by_status(
    status: str,
    limit: int = 100,
) -> list[News]:

    db = SessionLocal()

    try:

        return (
            _visible_news_query(db)
            .filter(News.status == status)
            .order_by(desc(News.created_at))
            .limit(limit)
            .all()
        )

    finally:

        db.close()

# ==========================================================
# SEARCH
# ==========================================================

def search_news(
    keyword: str,
    limit: int = 100,
) -> list[News]:

    db = SessionLocal()

    try:

        return (
            _visible_news_query(db)
            .filter(
                News.title.ilike(f"%{keyword}%")
            )
            .order_by(desc(News.created_at))
            .limit(limit)
            .all()
        )

    finally:

        db.close()

# ==========================================================
# FILTER
# ==========================================================

def filter_news(

    status: str | None = None,
    brand: str | None = None,
    category: str | None = None,
    limit: int = 100,

):

    db = SessionLocal()

    try:

        query = _visible_news_query(db)

        if status:
            query = query.filter(
                News.status == status
            )

        if brand:
            query = query.filter(
                News.brand == brand
            )

        if category:
            query = query.filter(
                News.category == category
            )

        return (
            query
            .order_by(desc(News.created_at))
            .limit(limit)
            .all()
        )

    finally:

        db.close()

# ==========================================================
# BULK STATUS
# ==========================================================

def bulk_update_status(
    news_ids: list[int],
    status: str,
) -> int:


    validate_status(status)

    db = SessionLocal()

    try:

        rows = (
            _visible_news_query(db)
            .filter(
                News.id.in_(news_ids)
            )
            .all()
        )

        for news in rows:

            news.status = status
            if status == "published":
                news.published = True
            news.updated_at = datetime.utcnow()

        db.commit()

        return len(rows)
    except Exception:
        db.rollback()

        logger.exception(
            "Bulk status update failed. Count=%d",
            len(news_ids),
        )

        raise

    finally:

        db.close()

# ==========================================================
# BULK DELETE
# ==========================================================

def bulk_delete_news(
    news_ids: list[int],
) -> int:

    db = SessionLocal()

    try:

        rows = (
            _visible_news_query(db)
            .filter(
                News.id.in_(news_ids)
            )
            .all()
        )

        count = len(rows)

        for news in rows:
            news.status = "deleted"
            news.updated_at = datetime.utcnow()

        db.commit()

        return count

    except Exception:
        db.rollback()
        logger.exception(
            "Bulk delete failed. Count=%d",
            len(news_ids),
        )

        raise

    finally:

        db.close()

# ==========================================================
# DASHBOARD
# ==========================================================

def get_editor_pending_count():

    db = SessionLocal()

    try:

        return (
            _visible_news_query(db)
            .filter(
                News.status == "editor_review"
            )
            .count()
        )

    finally:

        db.close()

# ==========================================================
# BULK AI REPROCESS
# ==========================================================

def bulk_reprocess_ai(
    news_ids: list[int],
) -> int:

    db = SessionLocal()

    try:

        rows = (
            _visible_news_query(db)
            .filter(News.id.in_(news_ids))
            .all()
        )

        queued = 0
        from app.services.news_selection import content_skip_reason
        for news in rows:
            if content_skip_reason(news):
                continue
            queued += 1

            news.ai_processed = False

            news.translated_title = None
            news.summary = None

            news.brand = None
            news.category = None
            news.importance = None

            news.instagram_title = None
            news.instagram_caption = None
            news.hashtags = None
            news.image_prompt = None

            news.editor_note = None

            news.status = "ai_pending"
            news.updated_at = datetime.utcnow()

        db.commit()

        return queued

    except Exception:
        db.rollback()
        logger.exception(
            "Bulk AI reprocess failed. Count=%d",
            len(news_ids),
        )

        raise

    finally:

        db.close()
