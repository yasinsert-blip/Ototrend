from datetime import datetime

from app.database.database import SessionLocal
from app.config import SOURCE_AUTO_DISABLE_FAILURES
from app.models.source import Source


def create_source(
    name,
    rss_url,
    website=None,
    scraper="rss",
    language="en",
    country="Global",
    source_type="editorial",
    brand=None,
    is_oem=False,
    enabled=True,
    fail_if_exists=False,
    priority=1,
):
    db = SessionLocal()

    try:
        exists = (
            db.query(Source)
            .filter(Source.name == name)
            .first()
        )

        if exists:
            if fail_if_exists:
                raise ValueError("Bu kaynak adı zaten kullanılıyor.")
            return exists

        source = Source(
            name=name,
            rss_url=rss_url,
            website=website,
            scraper=scraper,
            language=language,
            country=country,
            source_type=source_type,
            brand=brand,
            is_oem=is_oem,
            enabled=enabled,
            priority=priority,
        )

        db.add(source)
        db.commit()
        db.refresh(source)

        return source

    finally:
        db.close()


def get_all_sources():

    db = SessionLocal()

    try:
        return (
            db.query(Source)
            .order_by(Source.name)
            .all()
        )

    finally:
        db.close()


def get_source(source_id):

    db = SessionLocal()

    try:
        return (
            db.query(Source)
            .filter(Source.id == source_id)
            .first()
        )

    finally:
        db.close()


def update_source(
    source_id,
    name,
    rss_url,
    website,
    scraper,
    enabled,
    priority,
    source_type=None,
    brand=None,
    is_oem=None,
):

    db = SessionLocal()

    try:

        source = (
            db.query(Source)
            .filter(Source.id == source_id)
            .first()
        )

        if not source:
            return None

        duplicate = db.query(Source.id).filter(
            Source.name == name, Source.id != source_id
        ).first()
        if duplicate:
            raise ValueError("Bu kaynak adı zaten kullanılıyor.")

        source.name = name
        source.rss_url = rss_url
        source.website = website
        source.scraper = scraper
        if enabled and not source.enabled:
            source.consecutive_failures = 0
            source.auto_disabled_at = None
            source.last_error = None
        source.enabled = enabled
        source.priority = priority
        # Yönetim formunda bulunmayan OEM bilgileri düzenleme sırasında korunur.
        if source_type is not None:
            source.source_type = source_type
        if brand is not None:
            source.brand = brand
        if is_oem is not None:
            source.is_oem = is_oem

        db.commit()
        db.refresh(source)

        return source

    finally:

        db.close()


def delete_source(source_id):

    db = SessionLocal()

    try:

        source = (
            db.query(Source)
            .filter(Source.id == source_id)
            .first()
        )

        if not source:
            return False

        db.delete(source)
        db.commit()

        return True

    finally:

        db.close()


def mark_source_run(source_name: str):

    db = SessionLocal()

    try:

        source = (
            db.query(Source)
            .filter(Source.name == source_name)
            .first()
        )

        if source:
            source.last_run = datetime.utcnow()
            db.commit()

    finally:
        db.close()


def mark_source_success(source_name: str, news_count: int):

    db = SessionLocal()

    try:

        source = (
            db.query(Source)
            .filter(Source.name == source_name)
            .first()
        )

        if source:

            source.last_success = datetime.utcnow()
            source.success_count += news_count
            source.total_news += news_count
            source.last_error = None
            source.consecutive_failures = 0

            db.commit()

    finally:
        db.close()


def mark_source_error(source_name: str, error_message: str) -> bool:
    """Hatayı kaydeder; eşik aşılırsa kaynağı otomatik pasife alır."""

    db = SessionLocal()

    try:

        auto_disabled = False

        source = (
            db.query(Source)
            .filter(Source.name == source_name)
            .first()
        )

        if source:

            source.error_count += 1
            source.consecutive_failures += 1
            source.last_error = error_message
            source.last_run = datetime.utcnow()

            if source.consecutive_failures >= SOURCE_AUTO_DISABLE_FAILURES:
                source.enabled = False
                source.auto_disabled_at = datetime.utcnow()
                auto_disabled = True

            db.commit()

        return auto_disabled

    finally:
        db.close()


def enable_source(source_id: int):
    """Editörün otomatik durdurulan kaynağı kontrollü biçimde tekrar açması."""

    db = SessionLocal()

    try:
        source = db.query(Source).filter(Source.id == source_id).first()
        if source is None:
            return None

        source.enabled = True
        source.consecutive_failures = 0
        source.auto_disabled_at = None
        source.last_error = None
        db.commit()
        db.refresh(source)
        return source

    finally:
        db.close()


def disable_source(source_id: int):
    db = SessionLocal()
    try:
        source = db.get(Source, source_id)
        if source is None:
            return None
        source.enabled = False
        source.auto_disabled_at = None
        db.commit()
        return source
    finally:
        db.close()
