"""Haberleri yaşına göre arşivleyen ve güvenli biçimde temizleyen servis."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
import logging
from pathlib import Path
import sqlite3
import os

from sqlalchemy import or_

from app.config import (
    NEWS_ARCHIVE_AFTER_DAYS,
    NEWS_DELETE_AFTER_DAYS,
    NEWS_RETENTION_ENABLED,
)
from app.database.database import SessionLocal, engine
from app.models.news import News
from app.models.news_image import NewsImage
from app.services.instagram_visual_service import OUTPUT_DIRECTORY


logger = logging.getLogger(__name__)

BACKUP_DIRECTORY = Path(os.environ['OTOTREND_DATA_DIR']) / 'backups' / 'news-retention' if os.getenv('OTOTREND_DATA_DIR') else Path("backups/news-retention")
DELETE_BATCH_SIZE = 500


@dataclass(frozen=True)
class RetentionResult:
    """Tek bir saklama çalıştırmasının özeti."""

    archived: int = 0
    deleted: int = 0
    images_removed: int = 0
    backup_path: Path | None = None
    skipped: bool = False


def _utc_now(now: datetime | None = None) -> datetime:
    value = now or datetime.now(UTC)
    if value.tzinfo is None:
        return value.replace(tzinfo=UTC)
    return value.astimezone(UTC)


def _create_database_backup(now: datetime) -> Path:
    """SQLite veritabanının çevrimiçi ve tutarlı bir yedeğini oluşturur."""
    if not engine.url.drivername.startswith("sqlite"):
        raise RuntimeError(
            "Kalıcı haber temizliği yalnızca otomatik veritabanı yedeği "
            "oluşturulabildiğinde çalışır."
        )

    database_name = engine.url.database
    if not database_name or database_name == ":memory:":
        raise RuntimeError("Kalıcı haber temizliği için dosya tabanlı SQLite gerekli.")

    source_path = Path(database_name)
    if not source_path.is_absolute():
        source_path = Path.cwd() / source_path
    if not source_path.is_file():
        raise RuntimeError("Haber veritabanı yedekleme için bulunamadı.")

    BACKUP_DIRECTORY.mkdir(parents=True, exist_ok=True)
    timestamp = now.strftime("%Y%m%d-%H%M%S")
    backup_path = BACKUP_DIRECTORY / f"news-before-retention-{timestamp}.db"

    try:
        with sqlite3.connect(str(source_path)) as source_connection:
            with sqlite3.connect(str(backup_path)) as backup_connection:
                source_connection.backup(backup_connection)
    except sqlite3.Error as exc:
        if backup_path.exists():
            backup_path.unlink()
        raise RuntimeError("Haber veritabanı yedeği oluşturulamadı.") from exc

    return backup_path


def _remove_generated_images(news_ids: list[int]) -> int:
    """Kalıcı olarak silinen haberlere ait yerel Instagram çıktılarını kaldırır."""
    removed = 0
    for news_id in news_ids:
        image_path = OUTPUT_DIRECTORY / f"news-{news_id}.jpg"
        try:
            if image_path.is_file():
                image_path.unlink()
                removed += 1
        except OSError:
            logger.warning("Eski Instagram görseli silinemedi: %s", image_path)
    return removed


def run_news_retention(now: datetime | None = None) -> RetentionResult:
    """90 günü geçen haberleri arşivler, 1 yılı geçen arşivleri yedekli siler."""
    if not NEWS_RETENTION_ENABLED:
        logger.info("Haber saklama politikası devre dışı.")
        return RetentionResult(skipped=True)

    current_time = _utc_now(now)
    archive_cutoff = current_time - timedelta(days=NEWS_ARCHIVE_AFTER_DAYS)
    delete_cutoff = current_time - timedelta(days=NEWS_DELETE_AFTER_DAYS)

    db = SessionLocal()
    try:
        active_status = or_(
            News.status.is_(None),
            News.status.notin_(("archived", "deleted")),
        )
        archived = (
            db.query(News)
            .filter(News.created_at < archive_cutoff, active_status)
            .update(
                {
                    News.status: "archived",
                    News.updated_at: current_time,
                },
                synchronize_session=False,
            )
        )
        db.commit()

        permanent_ids = [
            news_id
            for (news_id,) in (
                db.query(News.id)
                .filter(
                    News.created_at < delete_cutoff,
                    News.status.in_(("archived", "deleted")),
                )
                .order_by(News.created_at.asc())
                .limit(DELETE_BATCH_SIZE)
                .all()
            )
        ]

        if not permanent_ids:
            if archived:
                logger.info("Haber saklama tamamlandı | Arşivlenen=%s", archived)
            return RetentionResult(archived=archived)

        # Veritabanından fiziksel silme yapılmadan hemen önce yedek alınır.
        backup_path = _create_database_backup(current_time)
        db.query(NewsImage).filter(NewsImage.news_id.in_(permanent_ids)).delete(
            synchronize_session=False
        )
        deleted = (
            db.query(News)
            .filter(News.id.in_(permanent_ids))
            .delete(synchronize_session=False)
        )
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("Haber saklama işlemi tamamlanamadı.")
        raise
    finally:
        db.close()

    images_removed = _remove_generated_images(permanent_ids)
    logger.info(
        "Haber saklama tamamlandı | Arşivlenen=%s Silinen=%s Görsel=%s Yedek=%s",
        archived,
        deleted,
        images_removed,
        backup_path,
    )
    return RetentionResult(
        archived=archived,
        deleted=deleted,
        images_removed=images_removed,
        backup_path=backup_path,
    )
